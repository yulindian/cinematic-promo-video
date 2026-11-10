"""Read-only video metadata, SRT and optional loudness checks. Needs ffprobe/ffmpeg."""
import argparse
import json
import math
import re
import subprocess
import sys
from fractions import Fraction
from pathlib import Path


def command(args):
    r = subprocess.run(args, capture_output=True, encoding="utf-8", errors="replace", timeout=120)
    if r.returncode:
        raise RuntimeError(f"{args[0]} failed: {r.stderr[-1000:]}")
    return r


def srt_check(path, duration, fps, no_terminal):
    data = Path(path).read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
    errors, previous, count = [], -1.0, 0
    stamp = r"(\d{2,}):(\d{2}):(\d{2})[,.](\d{3})"
    for block in re.split(r"\n\s*\n", data) if data else []:
        count += 1
        lines = block.splitlines()
        if len(lines) < 3 or not lines[0].strip().isdigit():
            errors.append(f"SRT block {count}: missing index/timing/text")
            continue
        m = re.fullmatch(stamp + r"\s*-->\s*" + stamp, lines[1].strip())
        if not m:
            errors.append(f"SRT block {count}: invalid timing")
            continue
        n = list(map(int, m.groups()))
        def seconds(v):
            h, minute, sec, ms = v
            if minute > 59 or sec > 59:
                raise ValueError("minutes/seconds exceed 59")
            return h * 3600 + minute * 60 + sec + ms / 1000
        try:
            start, end = seconds(n[:4]), seconds(n[4:])
        except ValueError as exc:
            errors.append(f"SRT block {count}: {exc}")
            continue
        if start < 0 or end <= start or end > duration + 1 / fps:
            errors.append(f"SRT block {count}: invalid/out-of-film range")
        if start < previous:
            errors.append(f"SRT block {count}: overlaps previous caption")
        previous = end
        text = "\n".join(lines[2:]).strip()
        if not text:
            errors.append(f"SRT block {count}: empty text")
        if no_terminal and re.search(r"[，。；：！？、,.!?;:…—]$", text):
            errors.append(f"SRT block {count}: trailing punctuation")
    if count == 0:
        errors.append("SRT is empty")
    return count, errors


def inspect(args):
    result = {"media": str(Path(args.media).resolve()), "errors": [], "warnings": []}
    probe = json.loads(command(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", args.media]).stdout)
    video = next((s for s in probe["streams"] if s["codec_type"] == "video"), None)
    if not video:
        raise ValueError("No video stream")
    audio = [s for s in probe["streams"] if s["codec_type"] == "audio"]
    duration = float(probe.get("format", {}).get("duration", video.get("duration", 0)))
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Invalid media duration")
    fps = float(Fraction(video.get("avg_frame_rate") or video["r_frame_rate"]))
    if fps <= 0:
        raise ValueError("Invalid frame rate")
    result["video"] = {"width": video["width"], "height": video["height"], "fps": fps, "duration": duration, "codec": video["codec_name"]}
    result["audio"] = [{"codec": s["codec_name"], "channels": s.get("channels")} for s in audio]
    for key in ["width", "height", "fps", "duration"]:
        expected = getattr(args, key)
        if expected is None:
            continue
        actual = result["video"][key]
        tolerance = max(1 / fps, .01) if key == "duration" else (.01 if key == "fps" else 0)
        if abs(actual - expected) > tolerance:
            result["errors"].append(f"{key}: expected {expected}, got {actual}")
    if not audio:
        result["warnings"].append("No audio stream; confirm intentional silence")
    if len(audio) > 1:
        result["warnings"].append("Multiple audio streams; confirm intended delivery")
    if args.srt:
        result["captions"], errors = srt_check(args.srt, duration, fps, args.no_terminal_punctuation)
        result["errors"].extend(errors)
    if args.loudness and audio:
        output = command(["ffmpeg", "-hide_banner", "-nostdin", "-i", args.media, "-map", "0:a:0", "-af", "ebur128=peak=true:framelog=verbose", "-f", "null", "-"]).stderr
        summary = output[output.rfind("Summary:"):]
        integrated = re.search(r"\bI:\s*(-?\d+(?:\.\d+)?)\s+LUFS", summary)
        peak = re.search(r"Peak:\s*(-?\d+(?:\.\d+)?)\s+dBFS", summary)
        if not integrated or not peak:
            result["warnings"].append("Could not parse finite loudness/true peak; inspect audio manually")
        else:
            result["loudness"] = {"integrated_lufs": float(integrated[1]), "true_peak_dbtp": float(peak[1])}
            if result["loudness"]["true_peak_dbtp"] > -1:
                result["warnings"].append("True peak above -1 dBTP; review project target")
    result["passed"] = not result["errors"]
    result["visual_review"] = "Required separately; this tool does not judge frames or transitions."
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media")
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--fps", type=float)
    parser.add_argument("--duration", type=float)
    parser.add_argument("--srt")
    parser.add_argument("--no-terminal-punctuation", action="store_true")
    parser.add_argument("--loudness", action="store_true")
    parser.add_argument("--report", help="Write a new JSON report; refuses to overwrite existing files")
    args = parser.parse_args()
    try:
        if args.report and Path(args.report).resolve() in {Path(p).resolve() for p in [args.media, args.srt] if p}:
            raise ValueError("Report must not replace an input")
        result = inspect(args)
        serialized = json.dumps(result, ensure_ascii=False, indent=2)
        if args.report:
            with Path(args.report).open("x", encoding="utf-8") as handle:
                handle.write(serialized + "\n")
        print(serialized)
        return 0 if result["passed"] else 1
    except (ValueError, OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"passed": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
