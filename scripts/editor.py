#!/usr/bin/env python3
"""Local native-editor launcher and timestamped review inbox. Python 3.10+."""
import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
import uuid
import webbrowser

RUNTIME = ".promo-editor"
ASSET = Path(__file__).resolve().parents[1] / "assets/editor-shell.html"
LOCK = threading.RLock()


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".writing")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for attempt in range(5):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 4:
                raise
            # Windows readers/watchers may briefly hold a handle without delete sharing.
            time.sleep(0.05)


def now():
    return datetime.now(timezone.utc).isoformat()


class NoteStore:
    def __init__(self, project):
        self.path = Path(project) / RUNTIME / "comments.json"

    def read(self):
        with LOCK:
            if not self.path.exists():
                return []
            value = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(value, list):
                raise ValueError("留言文件格式错误；保留原文件并修复 JSON 数组")
            return value

    def add(self, data):
        if not isinstance(data, dict):
            raise ValueError("留言必须是对象")
        text = data.get("text", "")
        position = data.get("time", 0)
        obj = data.get("object", "")
        if not isinstance(text, str) or not text.strip() or len(text) > 4000:
            raise ValueError("请填写1—4000字的留言")
        if (isinstance(position, bool) or not isinstance(position, (int, float))
                or not math.isfinite(position) or position < 0):
            raise ValueError("时间必须是大于等于0的有限秒数")
        if not isinstance(obj, str) or len(obj) > 1000:
            raise ValueError("对象名称不能超过1000字")
        context = data.get("context", {})
        if not isinstance(context, dict) or len(json.dumps(context)) > 24000:
            raise ValueError("定位上下文过大或格式错误")
        note = {"id": uuid.uuid4().hex[:12], "created": now(), "time": position,
                "object": obj, "text": text.strip(), "context": context, "status": "open"}
        with LOCK:
            notes = self.read()
            if len(notes) >= 1000:
                raise ValueError("本项目已达1000条留言；请先归档已处理留言")
            atomic_json(self.path, notes + [note])
        return note

    def resolve(self, note_id, reply):
        if not isinstance(reply, str) or not reply.strip() or len(reply) > 4000:
            raise ValueError("请填写完成说明，最多4000字")
        with LOCK:
            notes = self.read()
            for note in notes:
                if note["id"] == note_id:
                    note.update(status="done", reply=reply.strip(), resolved=now())
                    atomic_json(self.path, notes)
                    return note
            raise ValueError("没有找到该留言ID")


def local_cli(project, engine):
    package, binary = ("hyperframes", "hyperframes") if engine == "hyperframes" else ("@remotion/cli", "remotion")
    folder = project / "node_modules" / package
    manifest = folder / "package.json"
    if not manifest.is_file():
        raise ValueError(f"缺少本项目依赖 {manifest}；按项目README安装后重试，不会自动联网安装")
    try:
        bins = json.loads(manifest.read_text(encoding="utf-8"))["bin"]
        entry = bins if isinstance(bins, str) else bins[binary]
    except (ValueError, KeyError, TypeError):
        raise ValueError(f"引擎依赖声明损坏或无CLI入口：{manifest}；按项目锁文件修复依赖")
    cli = (folder / entry).resolve()
    if not cli.is_file() or not cli.is_relative_to(folder.resolve()):
        raise ValueError("本地CLI入口不可读或越出依赖包目录")
    node = shutil.which("node")
    if not node:
        raise ValueError("找不到Node；请按项目要求安装Node后重试")
    return [node, str(cli)]


def engine_command(project, engine, port, entry):
    base = local_cli(project, engine)
    if engine == "hyperframes":
        return base + ["preview", "--foreground", "--no-open", "--port", str(port)]
    return base + ["studio"] + ([entry] if entry else []) + ["--no-open", "--port", str(port)]


def request_json(url, payload=None, token=None, timeout=3):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["X-Editor-Token"] = token
    request = Request(url, json.dumps(payload).encode("utf-8") if payload is not None else None, headers)
    with urlopen(request, timeout=timeout) as response:
        return json.load(response)


def loopback_url(value):
    parts = urlsplit(value)
    if (parts.scheme != "http" or parts.hostname not in {"localhost", "127.0.0.1", "::1"}
            or parts.username or parts.password or not parts.port):
        raise ValueError("预览地址必须是带端口的本机 http 地址")
    return value


def read_session(project, require_alive=True):
    path = project / RUNTIME / "session.json"
    if not path.exists():
        raise ValueError("本项目尚未打开看板；先运行 open")
    state = json.loads(path.read_text(encoding="utf-8"))
    if Path(state.get("project", "")).resolve() != project.resolve():
        raise ValueError("会话路径不匹配，请在原项目目录运行或重新 open")
    loopback_url(state["url"])
    if require_alive:
        health = request_json(state["url"] + "api/health")
        if health.get("sessionId") != state.get("sessionId"):
            raise ValueError("端口已被其他会话占用，请重新 open")
    return state


def find_dict(value, key):
    if isinstance(value, dict):
        if key in value:
            return value[key]
        for child in value.values():
            found = find_dict(child, key)
            if found is not None:
                return found
    return None


class EditorServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, project, engine, preview_url, token):
        super().__init__(address, Handler)
        self.project, self.engine, self.preview_url, self.token = project, engine, preview_url, token
        self.session_id = uuid.uuid4().hex
        self.notes = NoteStore(project)

    def selection(self):
        if self.engine != "hyperframes":
            raise ValueError("此路线请在留言栏手动填写时间和对象；未接通Remotion选中对象读取")
        command = local_cli(self.project, self.engine) + ["preview", "--context", "--json",
                   "--context-fields", "selection", "--port", str(urlsplit(self.preview_url).port)]
        result = subprocess.run(command, cwd=self.project, capture_output=True, encoding="utf-8",
                                errors="replace", timeout=15, **hidden_process())
        if result.returncode:
            raise ValueError("无法读取选中元素；请先在原生编辑器选择对象，再重试")
        # Some versions prefix startup diagnostics. The context document starts at a JSON line.
        value = None
        for start in [i for i, char in enumerate(result.stdout) if char == "{"]:
            try:
                value, _ = json.JSONDecoder().raw_decode(result.stdout[start:])
                break
            except json.JSONDecodeError:
                continue
        selected = find_dict(value, "selection")
        if not isinstance(selected, dict) or not selected:
            raise ValueError("尚未选择元素；先在左侧编辑器暂停并点选对象")
        return {"selection": selected}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def respond(self, value, status=200, content_type="application/json; charset=utf-8"):
        payload = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def allowed_host(self):
        return self.headers.get("Host") in {f"127.0.0.1:{self.server.server_port}", f"localhost:{self.server.server_port}"}

    def do_GET(self):
        if not self.allowed_host():
            return self.respond({"error": "无效的本机Host"}, 403)
        path = urlsplit(self.path).path
        if path == "/":
            return self.respond(ASSET.read_bytes(), content_type="text/html; charset=utf-8")
        if path == "/api/health":
            return self.respond({"sessionId": self.server.session_id})
        if path == "/api/session":
            return self.respond({"project": self.server.project.name, "engine": self.server.engine,
                                 "previewUrl": self.server.preview_url, "token": self.server.token})
        if path == "/api/notes":
            try:
                return self.respond(self.server.notes.read())
            except (ValueError, OSError) as error:
                return self.respond({"error": str(error)}, 400)
        return self.respond({"error": "没有这个接口"}, 404)

    def do_POST(self):
        origin = self.headers.get("Origin")
        origins = {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}
        if (not self.allowed_host() or self.headers.get("X-Editor-Token") != self.server.token
                or (origin and origin not in origins)):
            return self.respond({"error": "无效的本机会话"}, 403)
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 65536:
                raise ValueError("请求须为1—65536字节的JSON")
            data = json.loads(self.rfile.read(size))
            path = urlsplit(self.path).path
            if path == "/api/notes":
                return self.respond(self.server.notes.add(data))
            if path == "/api/done":
                return self.respond(self.server.notes.resolve(data.get("id"), data.get("reply")))
            if path == "/api/selection":
                return self.respond(self.server.selection())
            if path == "/api/stop":
                self.respond({"stopping": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
            return self.respond({"error": "没有这个接口"}, 404)
        except (ValueError, KeyError, AttributeError, OSError, subprocess.SubprocessError) as error:
            return self.respond({"error": str(error)}, 400)


def hidden_process():
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


def free_port():
    with socket.socket() as handle:
        handle.bind(("127.0.0.1", 0))
        return handle.getsockname()[1]


def engine_environment(browser_path):
    environment = os.environ.copy()
    if browser_path:
        browser = Path(browser_path).resolve()
        if not browser.is_file():
            raise ValueError("指定的浏览器路径不存在")
        environment["HYPERFRAMES_BROWSER_PATH"] = str(browser)
    elif os.name == "nt" and not environment.get("HYPERFRAMES_BROWSER_PATH"):
        # Reuse installed Chrome for thumbnails instead of initiating a browser download.
        for name in ["ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"]:
            if environment.get(name):
                browser = Path(environment[name]) / "Google/Chrome/Application/chrome.exe"
                if browser.is_file():
                    environment["HYPERFRAMES_BROWSER_PATH"] = str(browser)
                    break
    return environment


def stop_child(process):
    if process and process.poll() is None:
        if os.name == "nt":
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                           capture_output=True, timeout=10, **hidden_process())
        else:
            process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()


def serve(args):
    project = Path(args.project).resolve()
    folder = project / RUNTIME
    child = None
    log = None
    server = None
    try:
        preview = args.preview_url
        if not preview:
            port = args.engine_port or free_port()
            command = engine_command(project, args.engine, port, args.entry)
            log = (folder / "engine.log").open("wb")
            child = subprocess.Popen(command, cwd=project, stdin=subprocess.DEVNULL,
                                     stdout=log, stderr=subprocess.STDOUT,
                                     env=engine_environment(args.browser_path), **hidden_process())
            preview = f"http://localhost:{port}/"
            if args.engine == "hyperframes":
                preview += "#project/" + quote(project.name, safe="")
            deadline = time.monotonic() + args.timeout
            while True:
                if child.poll() is not None:
                    raise ValueError("引擎启动失败，查看本项目 .promo-editor/engine.log")
                try:
                    with urlopen(preview, timeout=1) as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise ValueError("等待引擎超时；查看engine.log，核对依赖/端口/项目入口")
                time.sleep(0.2)
        loopback_url(preview)
        server = EditorServer(("127.0.0.1", args.port), project, args.engine, preview, secrets.token_urlsafe(24))
        state = {"project": str(project), "engine": args.engine, "url": f"http://127.0.0.1:{server.server_port}/",
                 "previewUrl": preview, "token": server.token, "sessionId": server.session_id,
                 "ownsPreview": child is not None, "pid": os.getpid(), "created": now()}
        atomic_json(folder / "session.json", state)
        if child:
            def monitor():
                child.wait()
                server.shutdown()
            threading.Thread(target=monitor, daemon=True).start()
        server.serve_forever()
    finally:
        if server:
            server.server_close()
        stop_child(child)
        if log:
            log.close()


def open_editor(args):
    project = Path(args.project).resolve()
    if not project.is_dir():
        raise ValueError("项目目录不存在")
    if not ASSET.is_file():
        raise ValueError("缺少assets/editor-shell.html；请完整安装Skill的assets目录")
    try:
        state = read_session(project)
        reused = True
    except (ValueError, OSError):
        reused = False
        if args.preview_url:
            loopback_url(args.preview_url)
            with urlopen(args.preview_url, timeout=3) as response:
                if response.status != 200:
                    raise ValueError("已有预览无法访问")
        else:
            local_cli(project, args.engine)  # fail before creating processes or runtime files
        folder = project / RUNTIME
        folder.mkdir(exist_ok=True)
        lock = folder / "opening.lock"
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise ValueError("另一启动正在进行；若已中断，确认没有启动进程后移除本项目opening.lock")
        os.close(descriptor)
        launcher = None
        try:
            for name in ["launcher.log", "engine.log"]:
                path = folder / name
                if path.exists() and path.stat().st_size > 2_000_000:
                    path.replace(folder / (name + ".previous"))
            command = [sys.executable, "-X", "utf8", str(Path(__file__).resolve()), "serve", str(project),
                       "--engine", args.engine, "--port", str(args.port), "--timeout", str(args.timeout)]
            if args.preview_url:
                command += ["--preview-url", args.preview_url]
            if args.engine_port:
                command += ["--engine-port", str(args.engine_port)]
            if args.entry:
                command += ["--entry", args.entry]
            if args.browser_path:
                command += ["--browser-path", args.browser_path]
            options = hidden_process() if os.name == "nt" else {"start_new_session": True}
            with (folder / "launcher.log").open("wb") as output:
                launcher = subprocess.Popen(command, cwd=project, stdin=subprocess.DEVNULL,
                                            stdout=output, stderr=subprocess.STDOUT, **options)
            deadline = time.monotonic() + args.timeout + 5
            while True:
                if launcher.poll() is not None:
                    raise ValueError("看板启动失败，查看本项目 .promo-editor/launcher.log 和engine.log")
                try:
                    state = read_session(project)
                    break
                except (ValueError, OSError):
                    pass
                if time.monotonic() >= deadline:
                    stop_child(launcher)
                    raise ValueError("看板启动超时；查看本项目日志")
                time.sleep(0.2)
        finally:
            lock.unlink(missing_ok=True)
    if reused and state["engine"] != args.engine:
        raise ValueError("已有看板使用另一引擎；先 stop 本项目看板，再用正确的engine打开")
    opened = False if args.no_open else webbrowser.open(state["url"])
    return {"url": state["url"], "previewUrl": state["previewUrl"], "reused": reused,
            "browserOpenRequested": not args.no_open, "browserAccepted": opened,
            "uiVerified": False, "notes": str(project / RUNTIME / "comments.json")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ["open", "serve"]:
        p = commands.add_parser(name)
        p.add_argument("project")
        p.add_argument("--engine", choices=["hyperframes", "remotion"], required=True)
        p.add_argument("--preview-url", help="复用已有原生编辑器，不负责停止它")
        p.add_argument("--entry", help="Remotion入口，相对项目目录")
        p.add_argument("--browser-path", help="HyperFrames缩略图使用的已有Chrome路径，仅作用于子进程")
        p.add_argument("--port", type=int, default=0)
        p.add_argument("--engine-port", type=int)
        p.add_argument("--timeout", type=float, default=45)
        p.add_argument("--no-open", action="store_true")
    for name in ["status", "stop", "comments", "done"]:
        p = commands.add_parser(name)
        p.add_argument("project")
        if name == "comments":
            p.add_argument("--wait", type=float, default=0, help="最多等待55秒，返回未处理留言")
            p.add_argument("--all", action="store_true")
        if name == "done":
            p.add_argument("id")
            p.add_argument("--note", required=True)
    args = parser.parse_args()
    try:
        if args.command in {"open", "serve"}:
            if not 1 <= args.timeout <= 55 or not 0 <= args.port <= 65535:
                raise ValueError("timeout须为1—55秒，port须为0—65535")
            if args.engine_port is not None and not 1 <= args.engine_port <= 65535:
                raise ValueError("engine-port须为1—65535")
        if args.command == "serve":
            serve(args)
            return
        if args.command == "open":
            value = open_editor(args)
        else:
            project = Path(args.project).resolve()
            if args.command == "comments":
                if not 0 <= args.wait <= 55:
                    raise ValueError("wait须为0—55秒")
                deadline = time.monotonic() + args.wait
                while True:
                    value = NoteStore(project).read()
                    if not args.all:
                        value = [n for n in value if n["status"] == "open"]
                    if value or time.monotonic() >= deadline:
                        break
                    time.sleep(0.25)
            else:
                state = read_session(project)
                if args.command == "status":
                    value = {k: v for k, v in state.items() if k != "token"}
                elif args.command == "stop":
                    value = request_json(state["url"] + "api/stop", {}, state["token"])
                else:
                    value = request_json(state["url"] + "api/done", {"id": args.id, "reply": args.note}, state["token"])
        print(json.dumps(value, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
