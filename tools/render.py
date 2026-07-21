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

ALSO supported (preferred for scheduled runs -- single Zapier task):
a top-level single-file spec at specs/YYYY-MM-DD-slug.json with the HTML
inlined, so one committed file carries the whole bundle:
{
  "slug": "tax-shakeup",
  "card":  {"html": "<!DOCTYPE html>...", "width": 1080, "height": 1350},
  "video": {"html": "<!DOCTYPE html>...", "width": 1080, "height": 1920,
             "fps": 25, "duration": 24.0}
}
Inline HTML may reference ../../assets/* exactly like dir-style specs.
Output basename = the json filename stem (e.g. 2026-07-20-tax-shakeup).
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
    # A valid video spec must define a global seek(t) animation function.
    # Guard against malformed specs so we fail this spec cleanly instead of
    # crashing the whole render job (and producing no assets at all).
    if not page.evaluate("typeof window.seek === 'function'"):
        raise ValueError(
            f"{cfg['file']}: no global seek(t) function; video spec is malformed"
        )
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
    tmp_dirs = []
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
    # Single-file specs: specs/YYYY-MM-DD-slug.json with inline "html".
    for spec_file in sorted(SPECS.glob("*.json")):
        cfg = json.loads(spec_file.read_text())
        base = spec_file.stem
        jobs = []
        tmp = SPECS / f".tmp-{base}"
        for kind, ext in (("card", "png"), ("video", "mp4")):
            section = cfg.get(kind)
            if not section or "html" not in section:
                continue
            out = ASSETS / f"{base}.{ext}"
            if out.exists():
                continue
            tmp.mkdir(exist_ok=True)
            html_path = tmp / f"{kind}.html"
            html_path.write_text(section["html"])
            section = dict(section, file=f"{kind}.html")
            jobs.append((kind, section, out))
        if jobs:
            tmp_dirs.append(tmp)
            pending.append((tmp, base, jobs))
    if not pending:
        print("all specs already rendered")
        return 0
    if shutil.which("ffmpeg") is None:
        print("ffmpeg missing", file=sys.stderr)
        return 1
    failures = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            # Each spec is isolated: a bad spec (e.g. malformed video with no
            # seek function) is logged and skipped so every other spec still
            # renders and the job still commits. One bad file never fails the
            # whole run.
            for spec_dir, base, jobs in pending:
                try:
                    for kind, cfg, out in jobs:
                        if kind == "card":
                            render_card(page, spec_dir, base, cfg, out)
                        else:
                            render_video(page, spec_dir, base, cfg, out)
                except Exception as e:  # noqa: BLE001
                    failures.append((base, str(e)))
                    print(f"SKIPPED {base}: {e}", file=sys.stderr)
                    # Remove any partial card output so we never commit a
                    # half-rendered asset for a failed spec.
                    for _k, _c, _out in jobs:
                        if _out.exists() and _out.suffix == ".mp4":
                            try:
                                _out.unlink()
                            except OSError:
                                pass
            browser.close()
    finally:
        for tmp in tmp_dirs:
            shutil.rmtree(tmp, ignore_errors=True)
    if failures:
        print(f"{len(failures)} spec(s) skipped: "
              + ", ".join(b for b, _ in failures), file=sys.stderr)
    # Always exit 0 so successfully rendered assets are committed even when
    # some specs were skipped. Broken specs surface via the SKIPPED logs.
    return 0


if __name__ == "__main__":
    sys.exit(main())
