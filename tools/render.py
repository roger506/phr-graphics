#!/usr/bin/env python3
"""Render Content Machine specs (HTML) into PNG cards and MP4 videos.

Scans specs/*/build.json. For each spec whose outputs are missing from
assets/, renders them with headless Chromium (Playwright) and ffmpeg.
Videos always get a silent AAC audio track (TikTok rejects silent-video-
only files). Card HTML may reference ../../assets/* (e.g. the PHR logo).

build.json format:
{
  "slug": "tax-shakeup",
  "card":  {"file": "card.html",  "width": 1080, "height": 1350},
  "video": {"file": "video.html", "width": 1080, "height": 1920,
             "fps": 25, "duration": 24.0}
}
Either "card" or "video" may be omitted.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
SPECS = ROOT / "specs"
ASSETS = ROOT / "assets"


def ensure_white_logo() -> None:
    """Derive assets/phr_logo_white.png from assets/phr_logo.png if needed."""
    src = ASSETS / "phr_logo.png"
    dst = ASSETS / "phr_logo_white.png"
    if dst.exists() or not src.exists():
        return
    from PIL import Image

    im = Image.open(src).convert("RGBA")
    white = Image.new("RGBA", im.size, (255, 255, 255, 0))
    white.putalpha(im.split()[3])
    white.save(dst)
    print(f"derived {dst.name}")


def render_card(page, spec_dir: Path, name: str, cfg: dict, out: Path) -> None:
    page.set_viewport_size({"width": cfg["width"], "height": cfg["height"]})
    page.goto(f"file://{spec_dir / cfg['file']}")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(600)
    page.screenshot(path=str(out))
    print(f"rendered {out.name}")


def render_video(page, spec_dir: Path, name: str, cfg: dict, out: Path) -> None:
    fps = cfg.get("fps", 25)
    duration = cfg.get("duration", 24.0)
    n_frames = int(fps * duration)
    page.set_viewport_size({"width": cfg["width"], "height": cfg["height"]})
    page.goto(f"file://{spec_dir / cfg['file']}")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(400)
    with tempfile.TemporaryDirectory() as td:
        for i in range(n_frames):
            page.evaluate(f"seek({i / fps})")
            page.screenshot(path=f"{td}/f{i:05d}.png")
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-framerate", str(fps), "-i", f"{td}/f%05d.png",
                "-f", "lavfi", "-i",
                "anullsrc=channel_layout=stereo:sample_rate=44100",
                "-shortest", "-c:v", "libx264", "-preset", "medium",
                "-crf", "23", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "96k",
                "-movflags", "+faststart", str(out),
            ],
            check=True,
        )
    print(f"rendered {out.name}")


def main() -> int:
    if not SPECS.is_dir():
        print("no specs directory; nothing to do")
        return 0
    ASSETS.mkdir(exist_ok=True)
    ensure_white_logo()
    pending = []
    for build in sorted(SPECS.glob("*/build.json")):
        cfg = json.loads(build.read_text())
        slug = cfg["slug"]
        dirname = build.parent.name
        base = dirname if dirname.endswith(slug) else f"{dirname}-{slug}"
        jobs = []
        if "card" in cfg:
            out = ASSETS / f"{base}.png"
            if not out.exists():
                jobs.append(("card", cfg["card"], out))
        if "video" in cfg:
            out = ASSETS / f"{base}.mp4"
            if not out.exists():
                jobs.append(("video", cfg["video"], out))
        if jobs:
            pending.append((build.parent, base, jobs))
    if not pending:
        print("all specs already rendered")
        return 0
    if shutil.which("ffmpeg") is None:
        print("ffmpeg missing", file=sys.stderr)
        return 1
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        for spec_dir, base, jobs in pending:
            for kind, cfg, out in jobs:
                if kind == "card":
                    render_card(page, spec_dir, base, cfg, out)
                else:
                    render_video(page, spec_dir, base, cfg, out)
        browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
