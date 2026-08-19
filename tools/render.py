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

CARD OVERFLOW GUARD (added 2026-08-18): every card template is a fixed
1080x1350 canvas with overflow:hidden and a flex spacer meant to push the
stats/footer block to the bottom. If the headline (or other content above the
spacer) renders taller than expected -- e.g. a manually-broken headline line
that is too wide for the canvas at full size and wraps onto an extra line --
the footer and its separator silently slide past the bottom edge and get
clipped with no error, because page.screenshot() only captures the fixed
viewport. render_card() now measures the footer's position after the initial
render; if it overflows, it shrinks the headline font-size in small steps and
re-measures until it fits (this also tends to un-wrap an overlong line). If it
still doesn't fit at the shrink floor, the card is NOT committed: a diagnostic
report is written to assets/_debug/<slug>.json (measured overflow, the exact
headline text, and the shrink attempts) and the spec is skipped with a clear
error, the same way a malformed video spec is skipped today.

VIDEO LOOP (added 2026-08-19): both video templates finish revealing every
element by roughly t=6.5s. The previous default rendered only 7.6s of clip, so
the completed card (headline, stats, logo, tagline, compliance footer all on
screen together) held for about one second before the file ended. That is too
short to read, and short enough that feeds treated the clip as truncated and
scrolled past it. Videos are now built from a CYCLE that ends with a real hold
and is then repeated: "cycle" seconds of animation played "loops" times
(defaults 10.5s x 2, about 21s total). Because the templates clamp their
animation once the reveal finishes, a 10.5s cycle naturally holds the finished
card still and readable for about 4s before restarting, with no template edit.
Frames past the first cycle are hard-linked from the frames already captured
rather than re-screenshotted, so the longer clip costs almost no extra render
time. Any spec may override cycle / loops / duration / fps under "video".
"""
import json
import os
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
FONTS = ASSETS / "fonts"
DEBUG = ASSETS / "_debug"

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

# Card overflow guard tuning: never shrink the headline below this fraction of
# its authored size, and step down by this many px each attempt.
H1_SHRINK_FLOOR_RATIO = 0.75
H1_SHRINK_STEP_PX = 4

# Video timing (see VIDEO LOOP in the module docstring). Both templates finish
# their reveal by about 6.5s, so a 10.5s cycle ends with roughly 4s of the
# completed card held still. Two loops give about 21s with a restart in the
# middle, which keeps motion in the feed instead of a long frozen tail.
VIDEO_CYCLE_SECONDS = 10.5
VIDEO_LOOPS = 2


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


def fonts_css() -> str:
    """@font-face block loading the repo-bundled fonts, so cards/videos render
    identically on any machine (GitHub's runner need not have these installed)."""
    def u(name):
        return f"file://{FONTS / name}"
    faces = [
        ("Lora", "Lora-Variable.ttf", "100 900", "normal"),
        ("Lora", "Lora-Italic-Variable.ttf", "100 900", "italic"),
        ("GFS Baskerville", "GFSBaskerville.otf", "400", "normal"),
        ("Caladea", "Caladea-Regular.ttf", "400", "normal"),
        ("Caladea", "Caladea-Bold.ttf", "700", "normal"),
        ("Caladea", "Caladea-Italic.ttf", "400", "italic"),
        ("DejaVu Sans Mono", "DejaVuSansMono.ttf", "400", "normal"),
        ("DejaVu Sans Mono", "DejaVuSansMono-Bold.ttf", "700", "normal"),
    ]
    return "\n".join(
        f"@font-face{{font-family:'{fam}';src:url('{u(f)}');"
        f"font-weight:{w};font-style:{s};font-display:block}}"
        for fam, f, w, s in faces
    )


def inject_fonts(html: str) -> str:
    # Insert the @font-face block at the top of the first <style> so template
    # CSS resolves to the bundled fonts before falling back to system fonts.
    return html.replace("<style>", "<style>\n" + fonts_css() + "\n", 1)


def expand_design_spec(cfg: dict) -> dict:
    """Turn a {design, ...content} spec into an inline card/video spec by
    filling the design's templates. Raises on unknown design / missing template."""
    design = cfg["design"]
    dc = DESIGN_CONFIG.get(design)
    if dc is None:
        raise ValueError(f"unknown design '{design}'")
    content = {k: v for k, v in cfg.items() if k not in CONTROL_KEYS}
    out = {"slug": cfg.get("slug", "post")}

    chtml = inject_fonts(inject_data(inject_logos((TEMPLATES / dc["card"]).read_text()), content))
    out["card"] = {"html": chtml, "width": 1080, "height": 1350}

    pal = dict(dc["palette"])
    pal["logo"] = logo_url(pal.get("logo", "white"))
    vdata = dict(content)
    vdata["palette"] = pal
    vhtml = inject_fonts(inject_data(inject_logos((TEMPLATES / dc["video"]).read_text()), vdata))
    vconf = cfg.get("video") if isinstance(cfg.get("video"), dict) else {}
    cycle = vconf.get("cycle", VIDEO_CYCLE_SECONDS)
    loops = vconf.get("loops", VIDEO_LOOPS)
    out["video"] = {"html": vhtml, "width": 1080, "height": 1920,
                    "fps": vconf.get("fps", 25), "cycle": cycle, "loops": loops,
                    "duration": vconf.get("duration", round(cycle * loops, 3))}
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


def _measure_footer(page):
    """Return {foot_bottom, h1_font_size, h1_text} or None if the template has
    no .foot / h1 (not all templates need the overflow guard)."""
    return page.evaluate(
        """() => {
            const foot = document.querySelector('.foot');
            const h1 = document.querySelector('h1');
            if (!foot || !h1) return null;
            return {
                foot_bottom: foot.getBoundingClientRect().bottom,
                h1_font_size: parseFloat(getComputedStyle(h1).fontSize),
                h1_text: h1.innerText,
            };
        }"""
    )


def render_card(page, spec_dir: Path, name: str, cfg: dict, out: Path) -> None:
    page.set_viewport_size({"width": cfg["width"], "height": cfg["height"]})
    page.goto(f"file://{spec_dir / cfg['file']}")
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(600)

    canvas_h = cfg["height"]
    m = _measure_footer(page)
    if m is None:
        # Template has no .foot/h1 pair (shouldn't happen for card templates
        # today, but don't block rendering over it).
        page.screenshot(path=str(out))
        print(f"rendered {out.name}")
        return

    original_font = m["h1_font_size"]
    foot_bottom_original = m["foot_bottom"]
    overflow = foot_bottom_original - canvas_h
    current = original_font
    floor = original_font * H1_SHRINK_FLOOR_RATIO
    attempts = []

    while overflow > 0 and current - H1_SHRINK_STEP_PX >= floor:
        current -= H1_SHRINK_STEP_PX
        page.evaluate(f"document.querySelector('h1').style.fontSize = '{current}px'")
        page.wait_for_timeout(80)
        m = _measure_footer(page)
        overflow = m["foot_bottom"] - canvas_h
        attempts.append({
            "h1_font_size": round(current, 1),
            "footer_bottom": round(m["foot_bottom"], 1),
            "overflow_px": round(overflow, 1),
        })

    if overflow > 0:
        # Auto-shrink couldn't fit it within the allowed range. Do NOT commit
        # a clipped card. Write a diagnostic report with exact measurements so
        # the offending text can be rewritten precisely, then fail loudly.
        DEBUG.mkdir(parents=True, exist_ok=True)
        report = {
            "slug": name,
            "canvas_height": canvas_h,
            "footer_bottom_no_shrink": round(foot_bottom_original, 1),
            "overflow_px_no_shrink": round(foot_bottom_original - canvas_h, 1),
            "h1_font_size_original": round(original_font, 1),
            "h1_font_size_at_floor": round(current, 1),
            "footer_bottom_at_floor": round(m["foot_bottom"], 1),
            "overflow_px_at_floor": round(overflow, 1),
            "h1_text": m["h1_text"],
            "shrink_attempts": attempts,
            "note": ("Auto-shrink alone could not fit this card's content within the "
                     "1350px canvas. Shorten the headline (or whichever field is tall) "
                     "and recommit the spec under a new slug; see FUTURE.md / the "
                     "Memory Ledger CONFIG UPDATE (2026-08-18) for the standing process."),
        }
        (DEBUG / f"{name}.json").write_text(json.dumps(report, indent=2))
        raise ValueError(
            f"card overflow unresolved: footer sits {overflow:.0f}px past the "
            f"{canvas_h}px canvas even after shrinking the headline from "
            f"{original_font:.0f}px to {current:.0f}px; diagnostic written to "
            f"assets/_debug/{name}.json"
        )

    page.screenshot(path=str(out))
    if current != original_font:
        print(f"rendered {out.name} (headline auto-shrunk {original_font:.0f}px -> {current:.0f}px to fit)")
    else:
        print(f"rendered {out.name}")


def render_video(page, spec_dir: Path, name: str, cfg: dict, out: Path) -> None:
    fps = cfg.get("fps", 25)
    duration = cfg.get("duration", 24.0)
    # Length of one animation pass. Frames past it repeat the cycle rather than
    # holding a frozen final frame. A spec with no "cycle" gets cycle ==
    # duration, i.e. exactly the old single-pass behaviour.
    cycle = cfg.get("cycle") or duration
    n_frames = int(fps * duration)
    n_cycle = max(1, min(n_frames, int(fps * cycle)))
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
            path = f"{td}/f{i:05d}.png"
            if i < n_cycle:
                page.evaluate(f"seek({i / fps})")
                page.screenshot(path=path)
            else:
                # Reuse an already-captured frame from the first cycle instead
                # of re-rendering it. Hard link where possible, copy otherwise.
                src = f"{td}/f{i % n_cycle:05d}.png"
                try:
                    os.link(src, path)
                except OSError:
                    shutil.copyfile(src, path)
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
    if n_cycle < n_frames:
        print(f"rendered {out.name} ({duration:.1f}s = {cycle:.1f}s cycle x "
              f"{n_frames / n_cycle:.2g}, {n_cycle} unique frames)")
    else:
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
