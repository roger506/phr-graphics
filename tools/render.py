#!/usr/bin/env python3
"""Render Content Machine specs (HTML) into PNG cards and MP4 videos.

Three spec formats are supported (all under specs/):

1. TEMPLATE / DATA spec  (preferred -- tiny file, one Zapier task):
   specs/YYYY-MM-DD-slug.json carrying a "design" key and the day's words:
   {
     "slug": "insurance-paradox",
     "design": "data_card",           # one of DESIGN_CONFIG below
     "kicker": "Florida Insurance ...",
     "headline": "The rate cut is real.\\nSo is your [[higher bill.]]",
     "deck": "...", "takeaway": "...",
     "stats": [{"n":"14%","label":"...","short":"cut","accent":true}, ...],
     "sources": "...", "attribution": "Roger Averbuj, Broker | ..."
   }
   render.py loads templates/<design>.html + the design's video template,
   injects the data, and renders card (1080x1350) + video (1080x1920).
   Headline convention: "\\n" -> line break, "[[x]]" -> accent span.

2. INLINE single-file spec:
   specs/YYYY-MM-DD-slug.json with "card":{"html":...} / "video":{"html":...}.

3. DIR spec:
   specs/<name>/build.json with "card":{"file":...} / "video":{"file":...}.

Videos always get a silent AAC audio track (TikTok rejects silent-video-only
files). Inline/template HTML may reference the PHR logo; template specs use the
tokens __LOGO_WHITE__ / __LOGO_DARK__ which are replaced with absolute paths.
Every spec is rendered in isolation and the job always exits 0, so one broken
or placeholder spec never fails the whole run.
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
TEMPLATES = ROOT / "templates"

# design -> card template, video family template, and the video palette.
# The card templates carry their own fixed palette; only the two shared video
# templates are palette-driven (palette is injected into window.DATA.palette).
DESIGN_CONFIG = {
    "refined_heritage": {
        "card": "refined_heritage.html", "video": "video_kinetic.html",
        "palette": {"bg": "radial-gradient(120% 70% at 50% 8%, #16324f 0%, #0d1f33 55%, #0a1826 100%)",
                    "text": "#f5f1e8", "acc": "#d8b45a", "kick": "#c9a24b",
                    "sub": "#cbb98f", "foot": "#93a4b8", "logo": "white"}},
    "data_card": {
        "card": "data_card.html", "video": "video_kinetic.html",
        "palette": {"bg": "#0f1417", "text": "#eef2f4", "acc": "#2ec4b6",
                    "kick": "#2ec4b6", "sub": "#9fb0c4", "foot": "#8a97a1", "logo": "white"}},
    "color_block": {
        "card": "color_block.html", "video": "video_kinetic.html",
        "palette": {"bg": "#0e4f4a", "text": "#ffffff", "acc": "#e7cf93",
                    "kick": "#9fe3d3", "sub": "#cfe9e2", "foot": "#cfe9e2", "logo": "white"}},
    "editorial": {
        "card": "editorial.html", "video": "video_editorial.html",
        "palette": {"bg": "#f4efe6", "text": "#20201d", "acc": "#7c2b2b",
                    "kick": "#7c2b2b", "muted": "#6d6a63", "logo": "dark"}},
    "minimal_luxury": {
        "card": "minimal_luxury.html", "video": "video_editorial.html",
        "palette": {"bg": "#efe9df", "text": "#22201c", "acc": "#8a6d2f",
                    "kick": "#9a8b6a", "muted": "#6b6558", "logo": "dark"}},
}

CONTROL_KEYS = {"design", "slug", "video", "card"}


def logo_url(kind: str) -> str:
    name = "phr_logo_white.png" if kind == "white" else "phr_logo.png"
    return f"file://{ASSETS / name}"


def inject_logos(html: str) -> str:
    return (html.replace("__LOGO_WHITE__", logo_url("white"))
                .replace("__LOGO_DARK__", logo_url("dark")))


def inject_data(html: str, data: dict) -> str:
    # ensure_ascii=True keeps the injected JS pure-ASCII (unicode -> \uXXXX),
    # avoiding any temp-file encoding pitfalls; JS unescapes at runtime.
    return html.replace("/*__DATA_SLOT__*/", "window.DATA = " + json.dumps(data) + ";")


def expand_design_spec(cfg: dict) -> dict:
    """Turn a {design, ...content} spec into an inline card/video spec by
    filling the design's templates. Raises on unknown design / missing template."""
    design = cfg["design"]
    dc = DESIGN_CONFIG.get(design)
    if dc is None:
        raise ValueError(f"unknown design '{design}'")
    content = {k: v for k, v in cfg.items() if k not in CONTROL_KEYS}
    out = {"slug": cfg.get("slug", "post")}

    chtml = inject_data(inject_logos((TEMPLATES / dc["card"]).read_text()), content)
    out["card"] = {"html": chtml, "width": 1080, "height": 1350}

    pal = dict(dc["palette"])
    pal["logo"] = logo_url(pal.get("logo", "white"))
    vdata = dict(content)
    vdata["palette"] = pal
    vhtml = inject_data(inject_logos((TEMPLATES / dc["video"]).read_text()), vdata)
    vconf = cfg.get("video") if isinstance(cfg.get("video"), dict) else {}
    out["video"] = {"html": vhtml, "width": 1080, "height": 1920,
                    "fps": vconf.get("fps", 25), "duration": vconf.get("duration", 7.6)}
    return out


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


def collect_inline(cfg: dict, base: str, tmp: Path):
    """Build a jobs list from an inline card/video spec, writing HTML to tmp."""
    jobs = []
    for kind, ext in (("card", "png"), ("video", "mp4")):
        section = cfg.get(kind)
        if not section or "html" not in section:
            continue
        out = ASSETS / f"{base}.{ext}"
        if out.exists():
            continue
        tmp.mkdir(exist_ok=True)
        html_path = tmp / f"{kind}.html"
        html_path.write_text(section["html"], encoding="utf-8")
        section = dict(section, file=f"{kind}.html")
        jobs.append((kind, section, out))
    return jobs


def main() -> int:
    if not SPECS.is_dir():
        print("no specs directory; nothing to do")
        return 0
    ASSETS.mkdir(exist_ok=True)
    ensure_white_logo()
    pending = []
    tmp_dirs = []

    # Dir-style specs: specs/<name>/build.json referencing sibling HTML files.
    for build in sorted(SPECS.glob("*/build.json")):
        try:
            cfg = json.loads(build.read_text())
            if not isinstance(cfg, dict):
                raise ValueError("spec is not a JSON object")
        except (json.JSONDecodeError, ValueError, OSError) as e:
            print(f"SKIPPED {build.parent.name}: unreadable spec ({e})", file=sys.stderr)
            continue
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

    # Single-file specs: template/data specs OR inline-HTML specs.
    for spec_file in sorted(SPECS.glob("*.json")):
        try:
            cfg = json.loads(spec_file.read_text())
            if not isinstance(cfg, dict):
                raise ValueError("spec is not a JSON object")
        except (json.JSONDecodeError, ValueError, OSError) as e:
            # Placeholder / malformed spec (e.g. the first of a two-step commit
            # that writes a stub like "PLACEHOLDER_WILL_REPLACE"). Skip cleanly.
            print(f"SKIPPED {spec_file.name}: unreadable spec ({e})", file=sys.stderr)
            continue
        # Template/data spec -> expand into an inline card/video spec.
        if "design" in cfg:
            try:
                cfg = expand_design_spec(cfg)
            except (KeyError, ValueError, OSError) as e:
                print(f"SKIPPED {spec_file.name}: bad design spec ({e})", file=sys.stderr)
                continue
        base = spec_file.stem
        tmp = SPECS / f".tmp-{base}"
        jobs = collect_inline(cfg, base, tmp)
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
            # Each spec is isolated: a bad spec is logged and skipped so every
            # other spec still renders and the job still commits.
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
                    # Remove any partial video output so we never commit a
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
    # Always exit 0 so successfully rendered assets are committed even when some
    # specs were skipped. Broken specs surface via the SKIPPED logs.
    return 0


if __name__ == "__main__":
    sys.exit(main())
