"""
community_publish.py - GENERATED, DO NOT EDIT.

Derived from bin/publish.py by bin/vendor_render.py. Contains only the
render path: card_html, cfg_title, moves, render_still, render_video, usd.
Edit bin/publish.py and re-run the generator; never edit this file.
"""
import base64, datetime, json, os, re, subprocess, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

UP, DN = "&#9650;", "&#9660;"

def usd(v, dp=0):
    return "${:,.{}f}".format(v, dp) if v is not None else "n/a"

def moves(d):
    """Direction words and arrows for the year-over-year figures.

    Every one of these used to be a Riverstone literal baked into the video and
    flyer templates, which meant community #2 would have rendered Riverstone's
    year over year on its own slides.
    """
    p, v = d.get("yoy_price_pct"), d.get("yoy_volume_pct")
    m = {}
    m["price_pct"] = "{:.1f}%".format(abs(p)) if p is not None else None
    m["vol_pct"] = "{:.0f}%".format(abs(v)) if v is not None else None
    m["price_arrow"] = (UP if (p or 0) > 0 else DN) if p is not None else ""
    m["vol_arrow"] = (UP if (v or 0) > 0 else DN) if v is not None else ""
    m["price_cls"] = ("up" if (p or 0) > 0 else "dn") if p is not None else ""
    m["vol_cls"] = ("up" if (v or 0) > 0 else "dn") if v is not None else ""
    m["price_word"] = ("rose" if (p or 0) > 0 else "fell") if p is not None else "held"
    m["vol_word"] = ("rose" if (v or 0) > 0 else "fell") if v is not None else "held"
    m["price_yoy"] = ("{} {} year over year".format(m["price_arrow"], m["price_pct"])
                      if p is not None else "year over year change not available")
    # The headline only claims a divergence when the data actually diverges.
    if p is not None and v is not None:
        if v > 0 and p < 0:
            m["headline"] = "More homes sold.<br>For less money."
        elif v < 0 and p > 0:
            m["headline"] = "Fewer homes sold.<br>For more money."
        elif v > 0 and p > 0:
            m["headline"] = "More homes sold.<br>At higher prices."
        elif v < 0 and p < 0:
            m["headline"] = "Fewer homes sold.<br>At lower prices."
        else:
            m["headline"] = "A market holding steady."
    else:
        m["headline"] = "{} in the last year.".format(d["community"])
    return m

def card_html(d, P=None, R=None, w=1080, h=1920, mode="vertical"):
    """mode: vertical (1080x1920) | wide (1920x1080) | still (1080x1350)."""
    P, R = P or {}, R or []
    wide, still = mode == "wide", mode == "still"
    S = 0.76 if wide else 1.0
    pad = int(64 * (2.1 if wide else 1))
    # Hero share is tuned per aspect so the data panel is filled rather than
    # padded out. 9:16 is by far the tallest frame, so it gets the most photo;
    # letting it keep a 44% hero left a third of the panel empty.
    hero_pct = 42 if wide else (44 if still else 58)
    # The footer is absolutely positioned, so the panel needs bottom padding it
    # cannot be allowed to run under.
    pad_b = 150 if wide else (196 if still else 190)
    ppsf = d.get("median_ppsf_12mo")
    M = moves(d)

    trs = "".join(
        '<tr class="tr" data-i="{}"><td class="a">{}</td><td class="c">{}</td>'
        '<td class="c">{}</td><td class="p">{}</td><td class="d">{}</td></tr>'.format(
            i, r["addr"], r["bd"], r["sf"], r["price"], r["date"])
        for i, r in enumerate(R))
    table = ("" if not R else
             '<div class="sec tbl" id="secB">Most recent sales</div>'
             '<table><thead id="thead"><tr><th>Address</th><th class="c">Bd</th>'
             '<th class="c">Sq Ft</th><th class="p">Sold</th><th class="d">Closed</th>'
             '</tr></thead><tbody>{}</tbody></table>'.format(trs))

    hero_inner = ('<img id="kb" src="{}">'.format(d["photo"]) if d.get("photo")
                  else '<div class="mono">{}</div>'.format(d["community"].upper()))
    grad_css = "" if d.get("photo") else """
#hero{background:
  radial-gradient(120% 90% at 18% 8%, #1d4a63 0%, rgba(29,74,99,0) 58%),
  radial-gradient(110% 80% at 88% 30%, #2a6a5a 0%, rgba(42,106,90,0) 62%),
  linear-gradient(158deg,#101d28 0%,#152a35 42%,#0d1a22 100%)}
#hero:after{background:linear-gradient(180deg,rgba(8,10,13,.46) 0%,
  rgba(8,10,13,.12) 42%,rgba(14,16,19,.55) 84%,rgba(14,16,19,.99) 100%)}
.mono{position:absolute;left:0;right:0;bottom:14%;text-align:center;
  font-size:MONOPXpx;font-weight:800;letter-spacing:.16em;
  color:rgba(255,255,255,.055);text-transform:uppercase}
""".replace("MONOPX", str(int(112 * S)))

    # The insight card is dropped whole when the export could not support it.
    ins_ok = bool(P.get("n_below_ask") and P.get("n_closed"))
    isub = ""
    if ins_ok:
        if P.get("median_reduction"):
            isub = "Median reduction {}. ".format(usd(P["median_reduction"]))
        if P.get("active_ppsf") and ppsf:
            isub += ("Homes listed today are asking <b>{}</b> per square foot than "
                     "recent sales achieved.".format(
                         "less" if P["active_ppsf"] < ppsf else "more"))
    insight = "" if not ins_ok else """
<div id="insight">
  <div class="ilab">What the data shows</div>
  <div class="ibig">{} of {} homes sold<br>below their asking price.</div>
  <div class="isub">{}</div>
</div>""".format(P["n_below_ask"], P["n_closed"], isub)

    # Timeline. Without the insight the tail collapses rather than holding six
    # dead seconds on a card that is not there.
    T = {"insOut": 20.4, "insIn": 21.2, "insEnd": 27.2, "cta": 27.6, "dur": 33.0}
    if not ins_ok:
        T = {"insOut": 20.4, "insIn": None, "insEnd": 21.0, "cta": 21.4, "dur": 26.6}
    logo = ('<img class="flogo" src="{}">'.format(d["logo"]) if d.get("logo") else "")
    clogo = ('<img class="clogo" src="{}">'.format(d["logo"]) if d.get("logo") else "")

    css = """*{margin:0;padding:0;box-sizing:border-box}
html,body{width:WPXpx;height:HPXpx;overflow:hidden;background:#0e1013}
body{font-family:'Helvetica Neue',system-ui,-apple-system,sans-serif;color:#fff;
  -webkit-font-smoothing:antialiased}
.tn{font-variant-numeric:tabular-nums}
#hero{position:absolute;top:0;left:0;right:0;height:100%;overflow:hidden}
#hero img{position:absolute;top:50%;left:50%;width:118%;height:118%;
  object-fit:cover;object-position:center 64%;transform:translate(-50%,-50%) scale(1)}
#hero:after{content:'';position:absolute;inset:0;background:linear-gradient(180deg,
  rgba(8,10,13,.86) 0%,rgba(8,10,13,.68) 24%,rgba(8,10,13,.40) 44%,
  rgba(8,10,13,.12) 62%,rgba(14,16,19,.52) 88%,rgba(14,16,19,.99) 100%)}
GRADCSS
#veil{position:absolute;inset:0;background:rgba(8,10,13,.62);opacity:0;z-index:3}
#hdr{position:absolute;left:PADpx;right:PADpx;z-index:4}
.kick{font-size:F23px;letter-spacing:.32em;text-transform:uppercase;color:#c3cbd8;
  font-weight:700;display:flex;justify-content:space-between}
.name{font-size:F116px;font-weight:800;letter-spacing:-.05em;line-height:.9;
  margin-top:F14px;text-shadow:0 2px 24px rgba(0,0,0,.6)}
.loc{font-size:F30px;color:#dbe2ec;margin-top:F12px;text-shadow:0 2px 16px rgba(0,0,0,.8)}
#panel{position:absolute;left:0;right:0;bottom:0;padding:F26px PADpx PADBpx;opacity:0}
.sec{font-size:F19px;letter-spacing:.22em;text-transform:uppercase;color:#8a94a6;
  font-weight:700;margin-bottom:F18px;opacity:0}
.sec.tbl{border-top:1px solid #232833;padding-top:F22px;margin-bottom:F6px}
#stats{display:grid;grid-template-columns:2fr 1fr 1.05fr 1.25fr;align-items:start;
  margin-bottom:F28px}
.st{padding-left:F28px;padding-right:F22px;border-left:2px solid #333c4a;opacity:0}
.st:first-child{padding-left:0;border-left:0}
.st:last-child{padding-right:0}
.st .v{font-size:F46px;font-weight:800;letter-spacing:-.038em;line-height:1;white-space:nowrap}
.st.wide .v{font-size:F56px;letter-spacing:-.045em}
.st .k{font-size:F15px;color:#8a94a6;letter-spacing:.1em;text-transform:uppercase;
  margin-top:F11px;font-weight:600;white-space:nowrap}
.st .d{font-size:F18px;margin-top:F7px;white-space:nowrap}
.dn{color:#e09443;font-weight:700}.up{color:#3fae63;font-weight:700}
table{width:100%;border-collapse:collapse}
th{text-align:left;font-size:F15px;letter-spacing:.12em;text-transform:uppercase;
  color:#6d7789;font-weight:700;padding:F10px 0 F8px}
th.c,td.c{text-align:center;width:F78px}
th.p,td.p{text-align:right;width:F196px}
th.d,td.d{text-align:right;width:F104px}
td{padding:F13px 0;border-top:1px solid #1c2028;font-size:F25px;color:#cfd5e0}
td.a{font-weight:600;color:#fff} td.p{font-weight:800;color:#fff}
td.d{color:#8a94a6;font-size:F22px}
.tr{opacity:0} #thead{opacity:0}
#insight{position:absolute;left:PADpx;right:PADpx;opacity:0;z-index:5}
.ilab{font-size:F22px;letter-spacing:.24em;text-transform:uppercase;color:#e09443;
  font-weight:700}
.ibig{font-size:F62px;font-weight:800;letter-spacing:-.03em;line-height:1.12;margin-top:F18px}
.isub{font-size:F29px;color:#c3cbd8;line-height:1.5;margin-top:F20px}
.isub b{color:#fff}
#cta{position:absolute;left:PADpx;right:PADpx;opacity:0;z-index:6;text-align:center}
.cbig{font-size:F50px;font-weight:400;color:#dbe2ec;line-height:1.35}
.cwho{font-size:F40px;font-weight:800;margin-top:F40px}
.cttl{font-size:F24px;color:#c3cbd8;margin-top:F10px}
.cph{font-size:F46px;font-weight:800;letter-spacing:-.01em;margin-top:F26px}
.clogo{height:F150px;margin-top:F34px}
#foot{position:absolute;left:PADpx;right:PADpx;bottom:F46px;display:flex;
  justify-content:space-between;align-items:center;border-top:1px solid #232833;
  padding-top:F24px;opacity:0;z-index:5}
.fwho{font-size:F28px;font-weight:800}
.fttl{font-size:F19px;color:#c3cbd8;margin-top:F7px}
.fsite{font-size:F20px;color:#dbe2ec;margin-top:F9px}
.fsite b{color:#fff;font-weight:700}
.fsite span{color:#8a94a6;font-size:F17px;border-left:1px solid #3a4150;
  padding-left:F12px;margin-left:F10px}
.flogo{height:F112px}"""
    css = css.replace("GRADCSS", grad_css).replace("WPX", str(w)).replace("HPX", str(h))
    css = css.replace("PADB", str(pad_b)).replace("PAD", str(pad))
    # F<n> tokens scale with the aspect. Done by token so the CSS above stays
    # readable and free of format-string collisions with % and {}.
    import re as _re
    css = _re.sub(r"F(\d+)", lambda mo: str(int(int(mo.group(1)) * S)), css)

    body = """
<div id="hero">{hero_inner}</div>
<div id="veil"></div>

<div id="hdr">
  <div class="kick"><span>Market Report</span><span>{month}</span></div>
  <div class="name">{name}</div>
  <div class="loc">{city}, Florida</div>
</div>

<div id="panel">
  <div class="sec" id="secA">{window}</div>
  <div id="stats">
    <div class="st wide" data-i="0"><div class="v tn" data-c="{median}" data-pre="$">$0</div>
      <div class="k">Median sale price</div>
      <div class="d">{price_move}</div></div>
    <div class="st" data-i="1"><div class="v tn" data-c="{ppsf}" data-pre="$">$0</div>
      <div class="k">Per sq ft</div><div class="d" style="color:#8a94a6">median</div></div>
    <div class="st" data-i="2"><div class="v tn" data-c="{sold}">0</div>
      <div class="k">Homes sold</div>
      <div class="d">{vol_move}</div></div>
    <div class="st" data-i="3"><div class="v tn" data-c="{dom}">0</div>
      <div class="k">Avg days on mkt</div>
      <div class="d" style="color:#8a94a6">to contract</div></div>
  </div>
  {table}
</div>
{insight}
<div id="cta">
  <div class="cbig">Thinking about what your<br>{name_t} home is worth?</div>
  <div class="cwho">{agent}</div>
  <div class="cttl">{title}</div>
  <div class="cph">{phone}</div>
  {clogo}
</div>

<div id="foot">
  <div><div class="fwho">{agent}</div><div class="fttl">{title}</div>
    <div class="fsite"><b>{phone}</b> <span>{site}</span></div></div>
  {logo}
</div>""".format(
        hero_inner=hero_inner, month=d["as_of_month"], name=d["community"].upper(),
        name_t=d["community"], city=d["city"],
        window=d["window_label"].capitalize(),
        median=int(round(d["median_price_12mo"] or 0)),
        price_move=('<span class="{}">{}{}</span> yr/yr'.format(
            M["price_cls"], M["price_arrow"], M["price_pct"]) if M["price_pct"] else ""),
        ppsf=int(round(ppsf or 0)), sold=int(d["closed_12mo"] or 0),
        vol_move=('<span class="{}">{}{}</span> yr/yr'.format(
            M["vol_cls"], M["vol_arrow"], M["vol_pct"]) if M["vol_pct"] else ""),
        dom=int(round(d.get("median_dom_12mo") or 0)), table=table, insight=insight,
        agent=d["agent"], title=cfg_title(d), phone=d["phone"], site=d["site"],
        logo=logo, clogo=clogo)

    js = """
const H=HPX, HERO_PCT=HEROPCT, T=TJSON, DUR=T.dur, STILL=ISSTILL;
const cl=(v,a,b)=>Math.max(a,Math.min(b,v));
const eo=t=>1-Math.pow(1-cl(t,0,1),3);
const eio=t=>{t=cl(t,0,1);return t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2};
const seg=(t,a,b)=>cl((t-a)/(b-a),0,1);
const fade=(t,a,b,c,d)=>Math.min(seg(t,a,b),1-seg(t,c,d));
function setTime(t){
  // hero opens full frame, contracts into its band, Ken Burns push throughout
  const shrink = eio(seg(t,2.9,4.3));
  const hPct = 100 + (HERO_PCT-100)*shrink;
  const hero=document.getElementById('hero');
  hero.style.height = hPct + '%';
  const kb=document.getElementById('kb');
  if(kb){ const z=1.0 + 0.13*(t/DUR);
    kb.style.transform='translate(-50%,-50%) scale('+z.toFixed(4)+')'; }

  // header sits centred while full frame, then rides to the top of the band
  const hdr=document.getElementById('hdr');
  const yFull = H*0.50, yBand = H*0.041;
  hdr.style.top = (yFull + (yBand-yFull)*shrink).toFixed(1)+'px';
  hdr.style.opacity = seg(t,0.35,1.6).toFixed(3);

  const panel=document.getElementById('panel');
  panel.style.opacity = seg(t,4.1,4.9).toFixed(3);
  panel.style.height = (100-HERO_PCT)+'%';

  const OUT_A=T.insOut, OUT_B=T.insOut+0.6;
  const hold=(a,b)=>STILL?1:fade(t,a,b,OUT_A,OUT_B);
  document.getElementById('secA').style.opacity = hold(4.5,5.1).toFixed(3);
  document.querySelectorAll('.st').forEach(e=>{
    const i=+e.dataset.i, a=5.1+i*0.55;
    e.style.opacity = hold(a,a+0.6).toFixed(3);
    e.style.transform='translateY('+((1-eo(seg(t,a,a+0.6)))*14).toFixed(1)+'px)';
  });
  document.querySelectorAll('[data-c]').forEach(e=>{
    const i=+e.closest('.st').dataset.i, a=5.1+i*0.55;
    const p=STILL?1:eo(seg(t,a,a+1.4)), v=(+e.dataset.c)*p;
    e.textContent=(e.dataset.pre||'')+Math.round(v).toLocaleString('en-US');
  });
  const sb=document.getElementById('secB'), th=document.getElementById('thead');
  if(sb) sb.style.opacity = hold(10.6,11.2).toFixed(3);
  if(th) th.style.opacity = hold(11.0,11.6).toFixed(3);
  document.querySelectorAll('.tr').forEach(e=>{
    const i=+e.dataset.i, a=11.6+i*0.85;
    e.style.opacity = hold(a,a+0.55).toFixed(3);
  });

  const ins=document.getElementById('insight');
  if(ins && T.insIn!==null){
    ins.style.opacity = STILL?0:fade(t,T.insIn,T.insIn+0.8,T.insEnd-0.6,T.insEnd).toFixed(3);
    ins.style.top = (H*(HERO_PCT/100) + H*0.055).toFixed(0)+'px';
    ins.style.transform='translateY('+((1-eo(seg(t,T.insIn,T.insIn+1.0)))*18).toFixed(1)+'px)';
  }

  document.getElementById('foot').style.opacity =
    (STILL?1:fade(t,12.4,13.2,T.insEnd-0.6,T.insEnd)).toFixed(3);

  // CTA: the hero eases back toward full frame behind it
  const back = eio(seg(t,T.cta-0.8,T.cta+0.8));
  if(back>0 && !STILL) hero.style.height = (hPct + (100-hPct)*back) + '%';
  document.getElementById('veil').style.opacity =
    (STILL?0:seg(t,T.cta-0.6,T.cta+0.8)).toFixed(3);
  const cta=document.getElementById('cta');
  cta.style.opacity = (STILL?0:seg(t,T.cta,T.cta+1.0)).toFixed(3);
  cta.style.top = (H*0.30).toFixed(0)+'px';
  cta.style.transform='translateY('+((1-eo(seg(t,T.cta,T.cta+1.2)))*20).toFixed(1)+'px)';
}
window.setTime=setTime; window.DUR=DUR; setTime(0);"""
    js = (js.replace("HPX", str(h)).replace("HEROPCT", str(hero_pct))
            .replace("TJSON", json.dumps(T)).replace("ISSTILL", "true" if still else "false"))

    return ("<!DOCTYPE html><html><head><meta charset=\"utf-8\"><style>" + css
            + "</style></head><body>" + body + "<script>" + js + "</script></body></html>")

def cfg_title(d):
    return d.get("agent_title") or "Real Estate Broker / Owner"

def render_still(html, out, w, h, at=17.0):
    """One frozen frame of the same card the video animates."""
    from playwright.sync_api import sync_playwright
    src = os.path.abspath(out + ".html")
    open(src, "w").write(html)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        pg.goto("file://" + src)
        pg.wait_for_timeout(500)
        pg.evaluate("t => window.setTime(t)", at)
        pg.wait_for_timeout(150)
        pg.screenshot(path=out)
        b.close()
    os.remove(src)
    return out

def render_video(html, out, w, h, fps=24, workdir=None):
    # Unique per output. A shared relative "_frames" meant two publish.py runs
    # in the same folder overwrote each other frame for frame, producing a video
    # spliced from both without either run failing.
    workdir = workdir or os.path.join(os.path.dirname(os.path.abspath(out)),
                                      "_frames_" + os.path.basename(out).split(".")[0])
    from playwright.sync_api import sync_playwright
    shutil.rmtree(workdir, ignore_errors=True)
    os.makedirs(workdir, exist_ok=True)
    src = os.path.abspath(os.path.join(workdir, "scene.html"))
    open(src, "w").write(html)
    with sync_playwright() as pw:
        b = pw.chromium.launch()
        pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
        pg.goto("file://" + src)
        pg.wait_for_timeout(400)
        dur = pg.evaluate("window.DUR")
        total = int(dur * fps)
        for f in range(total):
            pg.evaluate("t => window.setTime(t)", f / fps)
            pg.screenshot(path=os.path.join(workdir, f"{f:04d}.png"))
        b.close()
    subprocess.run(["ffmpeg", "-y", "-framerate", str(fps),
                    "-i", os.path.join(workdir, "%04d.png"),
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "19",
                    "-movflags", "+faststart", out],
                   check=True, capture_output=True)
    shutil.rmtree(workdir, ignore_errors=True)
    return out, total
