#!/usr/bin/env python3
"""
render_community.py - render community market-report assets on a GitHub runner.

WHY THIS RUNS HERE AND NOT ON ROGER'S MAC
Buffer accepts media only as a public file URL and offers no upload endpoint.
Nothing in the Cowork session can move local binary to a public host: Zapier's
GitHub "Create or Update File" stores its content field verbatim rather than
base64-decoding it, the browser file_upload tool is broken, Lofty's media
library rejects video, and passing bytes as base64 through the conversation is
prohibitively large. The content-machine pipeline solved this first: push a
small TEXT spec, and let GitHub's own compute produce the binaries and commit
them. The bytes are born here, so they never cross a text field.

SINGLE SOURCE OF TRUTH
This script does NOT contain the card design. It imports card_html() from
community_publish.py, which is a verbatim copy of bin/publish.py re-pushed on
every cycle. Section 4a of the operating manual exists because the approved card
once lived in one script while the video kept its own copy, and the logo and
phone number silently disappeared from the video for a week. Do not inline any
markup here.

INPUTS  community-specs/*.json   written by publish.py --spec-out
OUTPUTS assets/<basename>.png, -vertical.mp4, -horizontal.mp4
"""
import base64, glob, json, os, sys, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import community_publish as P  # the real card_html, vendored per cycle

SPEC_DIR = os.path.join(ROOT, "community-specs")
OUT_DIR = os.path.join(ROOT, "assets")
LOGO_B64 = os.path.join(HERE, "phr_logo.b64")


def data_uri_from_url(url, mime, label):
    """Fetch a remote asset and inline it, matching publish.asset_uri()."""
    if not url:
        return None
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            b = r.read()
        print("  {}: fetched {:,} bytes from URL".format(label, len(b)))
        return "data:{};base64,".format(mime) + base64.b64encode(b).decode()
    except Exception as e:
        print("  {}: FETCH FAILED ({})".format(label, e))
        return None


def render(spec_path):
    spec = json.load(open(spec_path))
    d, pricing, recent = spec["d"], spec.get("P") or {}, spec.get("R") or []
    base = spec["basename"]
    print("rendering {}".format(base))

    # Logo: prefer a committed base64 copy, which is known to carry true alpha.
    # Zapier cannot push binary, so that file is committed as TEXT. If absent,
    # fall back to the CDN copy. The brokerage name also appears as on-screen
    # text, so a missing logo degrades the design without breaking the Florida
    # advertising requirement (section 6).
    if os.path.exists(LOGO_B64):
        d["logo"] = "data:image/png;base64," + open(LOGO_B64).read().strip()
        print("  logo: committed base64")
    else:
        d["logo"] = data_uri_from_url(d.get("logo_url"), "image/png", "logo")
    d["photo"] = data_uri_from_url(d.get("photo_url"), "image/jpeg", "photo")
    if not d["photo"]:
        print("  photo missing, card falls back to the gradient hero")

    os.makedirs(OUT_DIR, exist_ok=True)
    still = os.path.join(OUT_DIR, base + ".png")
    P.render_still(P.card_html(d, pricing, recent, 1080, 1350, "still"),
                   still, 1080, 1350)
    print("  {}.png  ({:,} bytes)".format(base, os.path.getsize(still)))

    for label, w, h, mode in (("vertical", 1080, 1920, "vertical"),
                              ("horizontal", 1920, 1080, "wide")):
        out = os.path.join(OUT_DIR, "{}-{}.mp4".format(base, label))
        _, n = P.render_video(P.card_html(d, pricing, recent, w, h, mode), out, w, h)
        print("  {}-{}.mp4  ({} frames, {:,} bytes)".format(
            base, label, n, os.path.getsize(out)))

    # Mark the spec done so a later push does not re-render it. Renders are
    # expensive (about 1600 frames across both cuts) and this workflow triggers
    # on any change under community-specs/.
    os.rename(spec_path, spec_path + ".done")


def main():
    specs = sorted(glob.glob(os.path.join(SPEC_DIR, "*.json")))
    if not specs:
        print("no pending specs")
        return
    for s in specs:
        render(s)


if __name__ == "__main__":
    main()
