"""Build inspector.html — the page image beside every arm's reading of it, with disagreements marked.

Two kinds of error are shown, because they are different failures:
  RED    the text itself is wrong — a value no other arm produced, or a field that contradicts truth.
  YELLOW the text is right but in the WRONG PLACE — the running head, the page number or footnote
         text sitting inside `body`. This is the failure that makes a reader speak furniture aloud,
         and it is invisible to any character-level score.

Self-contained: page images are downscaled and embedded, so the file works offline and can be
published as-is.
"""
from __future__ import annotations

import base64
import io as _io
import json
from collections import Counter
from pathlib import Path

import yaml
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
PALETTE = ["#8c6a3f", "#b08d57", "#5f7d6b", "#6a7fa0", "#8a6a8a", "#a06a5f",
           "#5f8a8a", "#9a8a4f", "#7a6aa0", "#6a9a6a"]


def thumb(path: Path, width: int = 760, quality: int = 72) -> str:
    im = Image.open(path)
    im.thumbnail((width, width * 3))
    buf = _io.BytesIO()
    im.save(buf, "WEBP", quality=quality)
    return "data:image/webp;base64," + base64.b64encode(buf.getvalue()).decode()


def main() -> None:
    cfg = yaml.safe_load((ROOT / "arms.yaml").read_text(encoding="utf-8"))
    arms = [a for a in cfg["arms"] if (ROOT / "runs" / a["id"]).exists()]
    colours = {a["id"]: PALETTE[i % len(PALETTE)] for i, a in enumerate(arms)}
    truth = {int(f.stem[1:]): json.loads(f.read_text(encoding="utf-8"))
             for f in sorted((ROOT / "truth").glob("p*.json"))}

    pages, data = [], {}
    for img in sorted((ROOT / "pages").glob("p*.webp")):
        pg = int(img.stem[1:])
        rows = {}
        for a in arms:
            f = ROOT / "runs" / a["id"] / f"p{pg:03d}.json"
            if not f.exists():
                continue
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if "raw_text" in rec and "body" not in rec:
                import sys
                sys.path.insert(0, str(Path(__file__).parent))
                import metrics as M
                rec = {**M.recover_structure_p0(rec["raw_text"]), "_flat": True}
            rows[a["id"]] = {
                "runningHeader": rec.get("runningHeader"),
                "pageTitle": rec.get("pageTitle"),
                "printedPageNumber": rec.get("printedPageNumber"),
                "printerMark": rec.get("printerMark"),
                "body": [str(x) for x in (rec.get("body") or [])],
                "footnotes": [{"marker": n.get("marker"), "text": n.get("text", "")}
                              for n in (rec.get("footnotes") or [])],
                "flat": bool(rec.get("_flat")),
            }
        if not rows:
            continue
        pages.append(pg)
        data[pg] = {"img": thumb(img), "arms": rows,
                    "truth": {k: truth.get(pg, {}).get(k) for k in
                              ("runningHeader", "pageTitle", "printedPageNumber",
                               "printerMark", "footnoteCount", "verifiedBy")}}

    # consensus per field, so an arm alone against everyone else can be marked red
    for pg in pages:
        cons = {}
        for field in ("runningHeader", "pageTitle", "printedPageNumber", "printerMark"):
            c = Counter(json.dumps(r[field], ensure_ascii=False) for r in data[pg]["arms"].values())
            top, n = c.most_common(1)[0]
            cons[field] = {"value": json.loads(top), "agree": n, "of": sum(c.values())}
        c = Counter(len(r["footnotes"]) for r in data[pg]["arms"].values())
        cons["footnoteCount"] = {"value": c.most_common(1)[0][0],
                                 "agree": c.most_common(1)[0][1], "of": sum(c.values())}
        data[pg]["consensus"] = cons

    meta = {"arms": [{"id": a["id"], "label": a["label"], "prompt": a["prompt"],
                      "colour": colours[a["id"]], "control": bool(a.get("control"))} for a in arms],
            "pages": pages}
    html = TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False)) \
                   .replace("__META__", json.dumps(meta, ensure_ascii=False))
    (ROOT / "inspector.html").write_text(html, encoding="utf-8")
    kb = (ROOT / "inspector.html").stat().st_size // 1024
    print(f"inspector.html written - {len(arms)} arms, {len(pages)} pages, {kb} KB")


TEMPLATE = r"""<meta charset="utf-8">
<title>Side by Side</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400&family=Noto+Naskh+Arabic:wght@400;600&display=swap">
<style>
:root{--paper:#f0efe9;--card:#fbfaf6;--ink:#1a1815;--muted:#6a675e;--rule:#d9d6cc;
 --accent:#9e2b25;--good:#3d6b55;--warn:#a8762b;--shade:#e6e4dc;
 --red:rgba(158,43,37,.20);--yellow:rgba(168,118,43,.26);--diff:rgba(106,127,160,.13);
 color-scheme:light}
@media(prefers-color-scheme:dark){:root:not([data-theme="light"]){--paper:#141312;--card:#1d1b18;
 --ink:#e9e5db;--muted:#9b968a;--rule:#332f2a;--accent:#d4736a;--good:#7aa98e;--warn:#c99a52;
 --shade:#232019;--red:rgba(212,115,106,.24);--yellow:rgba(201,154,82,.26);
 --diff:rgba(140,160,196,.14);color-scheme:dark}}
:root[data-theme="dark"]{--paper:#141312;--card:#1d1b18;--ink:#e9e5db;--muted:#9b968a;
 --rule:#332f2a;--accent:#d4736a;--good:#7aa98e;--warn:#c99a52;--shade:#232019;
 --red:rgba(212,115,106,.24);--yellow:rgba(201,154,82,.26);--diff:rgba(140,160,196,.14);
 color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);margin:0;
 font:400 15px/1.6 "IBM Plex Sans",-apple-system,BlinkMacSystemFont,sans-serif}
.wrap{max-width:1500px;margin:0 auto;padding:28px 20px 60px}
h1{font:500 27px/1.15 Spectral,Georgia,serif;margin:0 0 5px;letter-spacing:-.015em}
.sub{color:var(--muted);margin:0 0 16px;max-width:76ch;font-size:14px}
.bar{display:flex;gap:14px;flex-wrap:wrap;align-items:end;padding:14px 0 15px;
 border-top:1px solid var(--rule);border-bottom:1px solid var(--rule);margin-bottom:20px}
.fld{display:flex;flex-direction:column;gap:5px}
.fld span{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:var(--muted)}
select{font:inherit;font-size:14px;padding:6px 10px;background:var(--card);color:var(--ink);
 border:1px solid var(--rule);border-radius:3px;min-width:210px}
button{font:inherit;font-size:13px;padding:7px 13px;background:var(--card);color:var(--ink);
 border:1px solid var(--rule);border-radius:3px;cursor:pointer}
button:hover{border-color:var(--muted)}
button:focus-visible,select:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:12.5px;color:var(--muted);
 margin-left:auto;align-items:center}
.key{display:inline-flex;align-items:center;gap:6px}
.sw{width:14px;height:14px;border-radius:2px;border:1px solid var(--rule)}
.stage{display:grid;grid-template-columns:minmax(230px,330px) 1fr;gap:22px;align-items:start}
.pagecol{position:sticky;top:14px}
.pagecol img{width:100%;display:block;border:1px solid var(--rule);border-radius:3px;
 background:var(--card)}
.pagecap{font-size:12px;color:var(--muted);margin-top:8px;display:flex;
 justify-content:space-between;gap:8px}
.cmp{border:1px solid var(--rule);border-radius:3px;overflow:hidden;background:var(--card)}
.hdr{display:grid;grid-template-columns:118px 1fr 1fr;border-bottom:1px solid var(--ink);
 position:sticky;top:0;background:var(--card);z-index:2}
.hdr div{padding:10px 13px;font:600 12.5px/1.3 "IBM Plex Sans",sans-serif;
 display:flex;align-items:center;gap:8px}
.hdr div+div{border-left:1px solid var(--rule)}
.swatch{width:9px;height:9px;border-radius:50%;flex:none}
.tagp{margin-left:auto;font:400 10px/1 "IBM Plex Sans",sans-serif;text-transform:uppercase;
 letter-spacing:.06em;color:var(--muted);border:1px solid var(--rule);border-radius:2px;
 padding:3px 5px;white-space:nowrap}
.row{display:grid;grid-template-columns:118px 1fr 1fr;border-bottom:1px solid var(--rule)}
.row:last-child{border-bottom:0}
.row.differs{background:var(--diff)}
.rk{padding:9px 13px;font-size:11px;text-transform:uppercase;letter-spacing:.06em;
 color:var(--muted);white-space:nowrap}
.rv{padding:9px 13px;min-width:0;overflow-wrap:anywhere;border-left:1px solid var(--rule)}
.ar{font-family:"Noto Naskh Arabic",serif;direction:rtl;unicode-bidi:isolate;font-size:15.5px;
 line-height:1.95}
.mono{font-family:"IBM Plex Mono",monospace;font-size:13px}
.bad{background:var(--red);border-radius:2px;padding:0 3px;box-shadow:inset 0 -2px 0 var(--accent)}
.mis{background:var(--yellow);border-radius:2px;padding:0 3px}
.none{color:var(--muted);font-style:italic;font-size:12.5px}
.body p{margin:0 0 8px}.body p:last-child{margin:0}
.fn{margin:0 0 6px;font-size:14px}
.fnm{color:var(--muted);font-family:"IBM Plex Mono",monospace;font-size:11.5px;margin-left:6px}
.tally{font-size:12px;color:var(--muted);padding:9px 13px;border-top:1px solid var(--rule);
 display:flex;gap:18px;flex-wrap:wrap}
.tally b{color:var(--ink);font-weight:600;font-family:"IBM Plex Mono",monospace}
@media(max-width:1000px){
 .stage{grid-template-columns:1fr}.pagecol{position:static;max-width:420px}
 .hdr,.row{grid-template-columns:92px 1fr 1fr}
}
</style>
<div class="wrap">
<h1>Side by Side</h1>
<p class="sub">One page, two readings, aligned field by field. <b>Red</b> disagrees with the
verified truth or stands alone against every other model. <b>Yellow</b> is text that is correct but
filed in the wrong place &mdash; page furniture sitting inside the body, which no character-level
score can see. A tinted row is one where the two models simply disagree with each other.</p>

<div class="bar">
  <label class="fld"><span>Page</span><select id="pg"></select></label>
  <label class="fld"><span>Left</span><select id="a"></select></label>
  <label class="fld"><span>Right</span><select id="b"></select></label>
  <label class="fld"><span>&nbsp;</span><button id="swap" type="button">Swap</button></label>
  <div class="legend">
    <span class="key"><span class="sw" style="background:var(--red)"></span>wrong</span>
    <span class="key"><span class="sw" style="background:var(--yellow)"></span>misplaced</span>
    <span class="key"><span class="sw" style="background:var(--diff)"></span>models disagree</span>
  </div>
</div>

<div class="stage">
  <div class="pagecol">
    <img id="img" alt="the scanned page">
    <div class="pagecap"><span id="cap"></span><span id="vby"></span></div>
  </div>
  <div class="cmp">
    <div class="hdr"><div>field</div><div id="ha"></div><div id="hb"></div></div>
    <div id="rows"></div>
    <div class="tally" id="tally"></div>
  </div>
</div>
</div>
<script id="d" type="application/json">__DATA__</script>
<script id="m" type="application/json">__META__</script>
<script>
const DATA = JSON.parse(document.getElementById('d').textContent);
const META = JSON.parse(document.getElementById('m').textContent);
const FIELDS = [['runningHeader','running head'],['pageTitle','page title'],
                ['printedPageNumber','page no.'],['printerMark','printer mark']];

const norm = s => (s??'').toString().normalize('NFKC')
  .replace(/[أإآٱ]/g,'ا').replace(/ى/g,'ي').replace(/ة/g,'ه')
  .replace(/[ً-ْٰـ]/g,'')
  .replace(/[٠-٩]/g,c=>c.charCodeAt(0)-0x0660)
  .replace(/[۰-۹]/g,c=>c.charCodeAt(0)-0x06F0)
  .replace(/\s+/g,' ').trim();
const esc = s => (s??'').toString().replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));

// RED only where there is real evidence: the hand-verified truth contradicts it, or this arm is
// alone against every other arm. A close vote is never enough to call one model wrong.
function isWrong(pg, arm, field){
  const d = DATA[pg], mine = d.arms[arm][field], t = d.truth[field];
  if (t !== undefined && t !== null) return norm(mine) !== norm(t);
  const c = d.consensus[field];
  return !!(c && c.of >= 3 && c.agree >= c.of - 1 && norm(mine) !== norm(c.value));
}

// Page furniture: what the page prints OUTSIDE the body. Found inside body => misplaced.
function furniture(pg){
  const d = DATA[pg], out = [];
  for (const [f] of FIELDS){
    const v = d.truth[f] ?? d.consensus[f]?.value;
    if (v && norm(v).length >= 3) out.push(norm(v));
  }
  return out;
}

function markBody(paras, furn){
  let hits = 0;
  const html = paras.map(p => {
    let out = esc(p);
    const n = norm(p);
    for (const f of furn){
      if (!n.includes(f)) continue;
      const re = new RegExp(f.split(' ')
        .map(w => w.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'))
        .join('[\\s\\u064B-\\u0652]*'), 'g');
      out = out.replace(re, m => { hits++; return `<span class="mis" title="misplaced: page furniture inside the body">${m}</span>`; });
    }
    return `<p>${out}</p>`;
  }).join('');
  return {html, hits};
}

function cell(pg, arm, field){
  const v = DATA[pg].arms[arm][field];
  if (v == null) return {html:'<span class="none">null</span>', wrong:false};
  const wrong = isWrong(pg, arm, field);
  const cls = 'ar' + (wrong ? ' bad' : '');
  return {html:`<span class="${cls}">${esc(v)}</span>`, wrong};
}

function render(){
  const pg = document.getElementById('pg').value;
  const A = document.getElementById('a').value, B = document.getElementById('b').value;
  const d = DATA[pg];
  document.getElementById('img').src = d.img;
  document.getElementById('cap').textContent = 'PDF page ' + pg;
  document.getElementById('vby').textContent = d.truth.verifiedBy ? ('truth: ' + d.truth.verifiedBy) : 'truth: adjudicated';

  const meta = Object.fromEntries(META.arms.map(a => [a.id, a]));
  for (const [side, id] of [['ha', A], ['hb', B]]){
    const a = meta[id];
    document.getElementById(side).innerHTML =
      `<span class="swatch" style="background:${a.colour}"></span>${a.label}` +
      `<span class="tagp">${a.prompt}${a.control ? ' · control' : ''}</span>`;
  }

  const furn = furniture(pg);
  const rows = [];
  let wrongA = 0, wrongB = 0, disagree = 0;

  for (const [k, label] of FIELDS){
    const ca = cell(pg, A, k), cb = cell(pg, B, k);
    if (ca.wrong) wrongA++;
    if (cb.wrong) wrongB++;
    const differs = norm(d.arms[A][k]) !== norm(d.arms[B][k]);
    if (differs) disagree++;
    rows.push(`<div class="row${differs ? ' differs' : ''}"><div class="rk">${label}</div>` +
              `<div class="rv">${ca.html}</div><div class="rv">${cb.html}</div></div>`);
  }

  const na = d.arms[A].footnotes.length, nb = d.arms[B].footnotes.length;
  const tc = d.truth.footnoteCount;
  const fa = (tc != null && tc !== na), fb = (tc != null && tc !== nb);
  if (fa) wrongA++;
  if (fb) wrongB++;
  if (na !== nb) disagree++;
  const fmt = (n, bad) => `<span class="mono${bad ? ' bad' : ''}">${n}</span>` +
    (tc != null ? ` <span class="none">(page has ${tc})</span>` : '');
  rows.push(`<div class="row${na !== nb ? ' differs' : ''}"><div class="rk">footnotes</div>` +
            `<div class="rv">${fmt(na, fa)}</div><div class="rv">${fmt(nb, fb)}</div></div>`);

  const ba = markBody(d.arms[A].body, furn), bb = markBody(d.arms[B].body, furn);
  rows.push('<div class="row"><div class="rk">body</div>' +
    `<div class="rv ar body">${d.arms[A].body.length ? ba.html : '<span class="none">empty</span>'}</div>` +
    `<div class="rv ar body">${d.arms[B].body.length ? bb.html : '<span class="none">empty</span>'}</div></div>`);

  const app = arm => d.arms[arm].footnotes.length
    ? d.arms[arm].footnotes.map(x =>
        `<p class="fn ar">${esc(x.text).slice(0,300)}<span class="fnm">${esc(x.marker ?? '—')}</span></p>`).join('')
    : '<span class="none">none</span>';
  rows.push('<div class="row"><div class="rk">apparatus</div>' +
            `<div class="rv">${app(A)}</div><div class="rv">${app(B)}</div></div>`);

  document.getElementById('rows').innerHTML = rows.join('');
  document.getElementById('tally').innerHTML =
    `<span>fields wrong &mdash; left <b>${wrongA}</b> &middot; right <b>${wrongB}</b></span>` +
    `<span>misplaced spans &mdash; left <b>${ba.hits}</b> &middot; right <b>${bb.hits}</b></span>` +
    `<span>rows where they disagree <b>${disagree}</b></span>`;
}

const sel = document.getElementById('pg');
META.pages.forEach(p => { const o = document.createElement('option'); o.value = p; o.textContent = 'p' + p; sel.appendChild(o); });
sel.value = META.pages.includes(93) ? 93 : META.pages[0];

for (const side of ['a','b']){
  const s = document.getElementById(side);
  META.arms.forEach(a => { const o = document.createElement('option'); o.value = a.id; o.textContent = a.label; s.appendChild(o); });
}
// open on the comparison that matters: production against the cheapest schema arm
document.getElementById('a').value = META.arms.some(x => x.id === 'A_gemini25_P0') ? 'A_gemini25_P0' : META.arms[0].id;
document.getElementById('b').value = META.arms.some(x => x.id === 'J_35lite_P1') ? 'J_35lite_P1'
  : META.arms[Math.min(1, META.arms.length - 1)].id;

['pg','a','b'].forEach(id => document.getElementById(id).addEventListener('change', render));
document.getElementById('swap').addEventListener('click', () => {
  const a = document.getElementById('a'), b = document.getElementById('b');
  [a.value, b.value] = [b.value, a.value]; render();
});
render();
</script>
"""


if __name__ == "__main__":
    main()
