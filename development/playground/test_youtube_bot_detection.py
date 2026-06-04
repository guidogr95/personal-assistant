#!/usr/bin/env python3
"""
Full download test for YouTube bot detection bypass.
RUN THIS FROM INSIDE THE BOT CONTAINER.

What it does:
    1. Checks Node >= 22, yt-dlp-ejs, and bgutil plugin are present
    2. Verifies bgutil sidecar is responding on the Docker network
    3. Downloads a small MP4 from YouTube using mweb + bgutil + EJS
    4. Verifies the file exists, has content, and is valid media
    5. Cleans up

Usage (from host):
    docker exec -it <bot-container-name> python3 /app/development/playground/test_youtube_bot_detection.py

Usage (from inside container):
    python3 /app/development/playground/test_youtube_bot_detection.py
"""

import os
import shutil
import subprocess
import sys
import tempfile

# CONFIG — change this to any public YouTube URL
VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# bgutil sidecar address inside the Docker network
BGUTIL_URL = "http://bgutil:4416"


def run(cmd: list[str], timeout: int = 120) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    return proc.returncode, proc.stdout, proc.stderr


def check_node() -> str:
    node_path = shutil.which("node")
    if not node_path:
        print("FAIL: node not found in PATH")
        sys.exit(1)

    rc, out, _ = run([node_path, "--version"])
    version = out.strip().lstrip("v")
    major = int(version.split(".")[0])
    if major < 22:
        print(f"FAIL: Node v{version} found, EJS requires >= 22")
        sys.exit(1)

    print(f"OK: Node v{version} at {node_path}")
    return node_path


def check_python_packages() -> None:
    try:
        __import__("yt_dlp_ejs")
        print("OK: yt_dlp_ejs importable")
    except ImportError:
        print("FAIL: yt_dlp_ejs not installed")
        sys.exit(1)

    # bgutil is a yt-dlp plugin, not a standalone importable package
    import yt_dlp

    plugin_dir = os.path.join(os.path.dirname(yt_dlp.__file__), "..", "yt_dlp_plugins", "extractor")
    plugin_dir = os.path.normpath(plugin_dir)
    if os.path.exists(os.path.join(plugin_dir, "getpot_bgutil_http.py")):
        print("OK: bgutil_ytdlp_pot_provider plugin present")
    else:
        print(f"FAIL: bgutil plugin not found in {plugin_dir}")
        sys.exit(1)


def check_bgutil_reachable() -> None:
    print(f"\n--- Checking bgutil sidecar at {BGUTIL_URL} ---")
    rc, out, err = run(
        [
            "curl",
            "-s",
            "-o",
            "/dev/null",
            "-w",
            "%{http_code}",
            f"{BGUTIL_URL}/",
        ],
        timeout=10,
    )

    # bgutil root returns 404, which is fine — it means the server is up
    if rc == 0 and out.strip() in ("200", "404"):
        print(f"OK: bgutil responding (HTTP {out.strip()})")
    else:
        print(f"FAIL: bgutil not reachable at {BGUTIL_URL}")
        print(f"  curl exit={rc}, stdout={out}, stderr={err}")
        sys.exit(1)


def download_video(node_path: str) -> tuple[str, str]:
    """Download a small MP4 and return (file_path, temp_dir)."""
    print("\n--- Downloading video ---")
    print(f"URL: {VIDEO_URL}")

    tmpdir = tempfile.mkdtemp(prefix="yt_test_")
    output_template = os.path.join(tmpdir, "test.%(ext)s")

    yt_dlp_path = shutil.which("yt-dlp") or "/app/.venv/bin/yt-dlp"
    cmd = [
        yt_dlp_path,
        "--extractor-args",
        "youtube:player_client=mweb",
        "--extractor-args",
        f"youtube:bgutil_base_url={BGUTIL_URL}",
        "--js-runtimes",
        f"node:{node_path}",
        "--format",
        "best[ext=mp4][height<=360]/best[ext=mp4]/best",
        "--output",
        output_template,
        "--no-playlist",
        "--quiet",
        "--no-warnings",
        VIDEO_URL,
    ]

    rc, out, err = run(cmd, timeout=90)

    # Find the downloaded file
    files = [f for f in os.listdir(tmpdir) if os.path.isfile(os.path.join(tmpdir, f))]
    if not files:
        print("FAIL: no file downloaded")
        print(f"  yt-dlp stderr:\n{err[-2000:]}\n")
        shutil.rmtree(tmpdir, ignore_errors=True)
        sys.exit(1)

    downloaded = os.path.join(tmpdir, files[0])
    size = os.path.getsize(downloaded)
    print(f"OK: downloaded {files[0]} ({size:,} bytes)")

    if size < 1024:
        print(f"FAIL: file is only {size} bytes — likely an error page, not media")
        shutil.rmtree(tmpdir, ignore_errors=True)
        sys.exit(1)

    return downloaded, tmpdir


def verify_media(file_path: str) -> bool:
    print("\n--- Verifying downloaded file ---")

    ffprobe_path = shutil.which("ffprobe") or "/usr/bin/ffprobe"
    rc, out, err = run([ffprobe_path, "-v", "error", "-show_format", "-show_streams", file_path])
    if rc == 0 and ("codec_name=" in out or "Duration=" in out):
        print("OK: ffprobe confirms valid media file")
        return True

    print("FAIL: ffprobe could not verify media")
    print(f"  rc={rc}, out={out[:200]}, err={err[:200]}")
    return False


def main() -> None:
    print("=" * 50)
    print("YouTube Bot Detection Bypass — Full Download Test")
    print("Running FROM inside the bot container")
    print("=" * 50)

    node_path = check_node()
    check_python_packages()
    check_bgutil_reachable()

    downloaded_path, tmpdir = download_video(node_path)
    success = verify_media(downloaded_path)

    # Cleanup
    print(f"\n--- Cleaning up {tmpdir} ---")
    shutil.rmtree(tmpdir, ignore_errors=True)
    print("OK: temp files removed")

    if success:
        print("\n✅ FULL TEST PASSED")
        print("The container can download YouTube media via bgutil + mweb + EJS")
        sys.exit(0)
    else:
        print("\n❌ TEST FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
