"""Run from the skill root: python -X utf8 -m unittest discover -s tests -v."""
import importlib.util
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("promo_editor", ROOT / "scripts/editor.py")
editor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(editor)


class EditorTests(unittest.TestCase):
    def setUp(self):
        (ROOT / ".tmp").mkdir(exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix="编辑器测试 ", dir=ROOT / ".tmp")
        self.project = Path(self.temp.name)
        self.store = editor.NoteStore(self.project)

    def tearDown(self):
        self.temp.cleanup()

    def test_comments_keep_position_and_resolve_across_restart(self):
        note = self.store.add({"text": "标题缩小一点", "time": 3.5, "object": "hero-title",
                               "context": {"sourceFile": "scene.html", "bounds": [1, 2, 3, 4]}})
        self.assertEqual(note["status"], "open")
        self.store.resolve(note["id"], "已调整并复核")
        restored = editor.NoteStore(self.project).read()[0]
        self.assertEqual(restored["time"], 3.5)
        self.assertEqual(restored["object"], "hero-title")
        self.assertEqual(restored["status"], "done")
        self.assertEqual(restored["reply"], "已调整并复核")

    def test_reject_invalid_notes_without_modifying_storage(self):
        for data in [{"text": ""}, {"text": "x", "time": -1},
                     {"text": "x", "time": float("nan")},
                     {"text": "x", "time": True}, {"text": "x" * 4001}]:
            with self.assertRaises(ValueError):
                self.store.add(data)
        self.assertEqual(self.store.read(), [])

    def test_remotion_and_hyperframes_are_project_local(self):
        for engine, package, name in [("hyperframes", "hyperframes", "hyperframes"),
                                      ("remotion", "@remotion/cli", "remotion")]:
            pkg = self.project / "node_modules" / package
            (pkg / "bin").mkdir(parents=True)
            (pkg / "package.json").write_text(json.dumps({"bin": {name: "bin/cli.js"}}))
            (pkg / "bin/cli.js").write_text("// test")
            command = editor.engine_command(self.project, engine, 3456, None)
            self.assertIn(str(pkg / "bin/cli.js"), command)
            self.assertIn("--port", command)
        with self.assertRaises(ValueError):
            editor.engine_command(self.project / "missing", "hyperframes", 3456, None)

    def test_missing_package_does_not_install_anything(self):
        with self.assertRaisesRegex(ValueError, "node_modules"):
            editor.engine_command(self.project, "hyperframes", 3456, None)

    def test_session_accepts_equivalent_project_path(self):
        folder = self.project / editor.RUNTIME
        folder.mkdir()
        editor.atomic_json(folder / "session.json", {
            "project": str(self.project / "unused" / ".."),
            "url": "http://127.0.0.1:3456/"
        })
        session = editor.read_session(self.project.resolve(), require_alive=False)
        self.assertEqual(session["url"], "http://127.0.0.1:3456/")

    def test_atomic_save_survives_transient_file_lock(self):
        path = self.project / "state.json"
        editor.atomic_json(path, {"saved": 1})
        replace = Path.replace
        calls = []
        def transient(source, target):
            calls.append(1)
            if len(calls) == 1:
                raise PermissionError("File is being read by another Windows process")
            return replace(source, target)
        with patch.object(Path, "replace", transient):
            editor.atomic_json(path, {"saved": 2})
        self.assertEqual(json.loads(path.read_text()), {"saved": 2})

    def test_note_api_requires_token_and_preserves_untrusted_text(self):
        server = editor.EditorServer(("127.0.0.1", 0), self.project, "hyperframes",
                                     "http://localhost:3456/#project/demo", "test-token")
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:" + str(server.server_port)
        try:
            def post(path, body, token="test-token", origin=None):
                headers = {"Content-Type": "application/json", "X-Editor-Token": token}
                if origin: headers["Origin"] = origin
                request = Request(base + path, json.dumps(body).encode(), headers, method="POST")
                with urlopen(request, timeout=3) as response:
                    return json.load(response)
            with self.assertRaises(HTTPError) as caught:
                post("/api/notes", {"text": "x"}, token="wrong")
            self.assertEqual(caught.exception.code, 403)
            caught.exception.close()
            with self.assertRaises(HTTPError) as caught:
                post("/api/notes", {"text": "x"}, origin="https://unrelated.example")
            self.assertEqual(caught.exception.code, 403)
            caught.exception.close()
            note = post("/api/notes", {"text": "<script>只是留言</script>", "time": 2})
            self.assertEqual(note["text"], "<script>只是留言</script>")
            with urlopen(base + "/api/notes", timeout=3) as response:
                notes = json.load(response)
            self.assertEqual(len(notes), 1)
            with urlopen(base, timeout=3) as response:
                self.assertIn("iframe", response.read().decode())
            with self.assertRaises(HTTPError) as caught:
                urlopen(base + "/../session.json", timeout=3)
            caught.exception.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main()
