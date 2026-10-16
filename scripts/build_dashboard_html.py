#!/usr/bin/env python3
"""Generate the SRS vs Hanford comparison dashboard HTML. v2 - lazy tab rendering, fixed JS quoting."""
import json
from pathlib import Path

BASE = Path("/Users/aspen_mb/Documents/Savannah_RiverTF")
DATA = json.load(open(BASE / "dashboard" / "dashboard_data.json"))
OUT = BASE / "dashboard" / "srs_hanford_comparison.html"

html = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SRS vs Hanford Tank Waste Comparison</title>
<style>
:root{
  --bg:#0d1117; --panel:#161b22; --panel2:#1c2129; --border:#30363d;
  --fg:#e6edf3; --muted:#8b949e; --accent:#58a6ff; --srs:#f0883e; --hf:#79c0ff;
  font-size:15px;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}
header{padding:22px 28px 10px;border-bottom:1px solid var(--border)}
h1{margin:0 0 4px;font-size:1.45rem;letter-spacing:.2px}
h1 .vs{color:var(--muted);font-weight:400}
.sub{color:var(--muted);font-size:.85rem}
nav.tabs{display:flex;gap:6px;padding:14px 28px 0;border-bottom:1px solid var(--border);flex-wrap:wrap}
nav.tabs button{background:none;border:1px solid transparent;border-bottom:none;color:var(--muted);
  padding:8px 16px;font-size:.9rem;cursor:pointer;border-radius:8px 8px 0 0}
nav.tabs button.active{color:var(--fg);background:var(--panel);border-color:var(--border);position:relative;top:1px}
main{padding:20px 28px 60px}
section.tab{display:none}
section.tab.active{display:block}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px;margin:18px 0 24px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:14px 16px}
.card .label{color:var(--muted);font-size:.72rem;text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px}
.card .big{font-size:1.55rem;font-weight:700;line-height:1.1}
.card .unit{font-size:.85rem;color:var(--muted);font-weight:400}
.card.srs .big{color:var(--srs)} .card.hf .big{color:var(--hf)}
.card .foot{margin-top:6px;font-size:.72rem;color:var(--muted)}
.grid2{display:grid;grid-template-columns:1fr 1fr;gap:18px}
.grid2 > div{min-width:0}
@media(max-width:980px){.grid2{grid-template-columns:1fr}}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:18px}
.panel h2{margin:0 0 4px;font-size:1.02rem}
.panel .desc{color:var(--muted);font-size:.8rem;margin-bottom:12px}
.bar{display:flex;height:26px;border-radius:6px;overflow:hidden;border:1px solid var(--border);margin:10px 0 4px;background:var(--panel2)}
.bar div{height:100%;position:relative}
.bar .seg span{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:.68rem;color:#0d1117;font-weight:700;white-space:nowrap;overflow:hidden}
.legend{display:flex;gap:16px;flex-wrap:wrap;font-size:.75rem;color:var(--muted);margin-top:8px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px}
table{width:100%;border-collapse:collapse;font-size:.82rem}
th{color:var(--muted);text-align:left;font-weight:600;padding:7px 10px;border-bottom:1px solid var(--border);font-size:.72rem;text-transform:uppercase;letter-spacing:.5px}
td{padding:7px 10px;border-bottom:1px solid var(--panel2)}
tr:hover td{background:var(--panel2)}
.num{text-align:right;font-variant-numeric:tabular-nums}
.tanklist{max-height:560px;overflow-y:auto}
.controls{display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-bottom:12px}
.controls label{font-size:.78rem;color:var(--muted)}
.controls select,.controls input[type=range]{accent-color:var(--accent)}
.controls select{background:var(--panel2);color:var(--fg);border:1px solid var(--border);border-radius:6px;padding:5px 8px;font-size:.8rem}
.pill{display:inline-block;padding:2px 9px;border-radius:20px;font-size:.68rem;font-weight:600;letter-spacing:.4px}
.pill.srs{background:rgba(240,136,62,.16);color:var(--srs);border:1px solid rgba(240,136,62,.4)}
.pill.hf{background:rgba(121,192,255,.14);color:var(--hf);border:1px solid rgba(121,192,255,.4)}
.note{background:rgba(210,153,34,.08);border:1px solid rgba(210,153,34,.35);color:#e3b341;
  border-radius:8px;padding:10px 14px;font-size:.78rem;margin:12px 0}
.note.blue{background:rgba(88,166,255,.07);border-color:rgba(88,166,255,.3);color:var(--accent)}
footer{padding:18px 28px;border-top:1px solid var(--border);color:var(--muted);font-size:.72rem}
a{color:var(--accent)}
.hbar-row{display:grid;grid-template-columns:120px 1fr 150px;gap:10px;align-items:center;margin:5px 0;font-size:.8rem}
.hbar-row .nm{text-align:right;color:var(--fg);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.hbar-row .trk{background:var(--panel2);border-radius:4px;height:16px;overflow:hidden;position:relative}
.hbar-row .fill{height:100%;border-radius:4px}
.hbar-row .val{font-variant-numeric:tabular-nums;color:var(--muted);font-size:.72rem}
canvas{display:block}
#tankDetail{min-height:3.2em}
</style>
</head>
<body>
<header>
  <h1>Savannah River Site <span class="vs">vs</span> Hanford — Tank Farm Waste Comparison</h1>
  <div class="sub">Interactive comparison of remaining waste inventory, radiological & chemical content.
  SRS: LWSP Rev 24 / PAs & SAs / SRNL batch characterizations · Hanford: PHOENIX Best-Basis Inventory.
  Built <span id="built"></span> · <a href="#" id="dl">download underlying data (JSON)</a></div>
</header>
<nav class="tabs">
  <button data-tab="overview" class="active">Overview</button>
  <button data-tab="phase">Phases & Farms</button>
  <button data-tab="rad">Radionuclides</button>
  <button data-tab="tanks">Tank Explorer</button>
  <button data-tab="chem">Current Chemistry</button>
  <button data-tab="methods">Methods & Caveats</button>
</nav>
<main>
<section class="tab active" id="tab-overview">
  <div class="cards" id="cards-overview"></div>
  <div class="note">⚠ <b>Basis difference:</b> SRS per-tank curie values throughout are <b>closure-residual
  inventories</b> (conservative PA/SA basis, decayed to 2032) — the public per-tank analog to Hanford's BBI. Farm-level
  <b>current</b> SRS inventory (33.2 Mgal / 191 MCi) is a 2025 measurement shown separately. Hanford numbers are live BBI (decay date 2022-01-01).</div>
  <div class="grid2">
    <div class="panel"><h2>Head-to-head: current farm inventory</h2>
      <div class="desc">Remaining waste in each site's tank farms (SRS 2025-09-30 WCS; Hanford BBI effective 2025-10-01)</div>
      <div id="head2head"></div>
    </div>
    <div class="panel"><h2>Scale context</h2>
      <div class="desc">Where each site stands</div>
      <div id="scalectx"></div>
    </div>
  </div>
</section>
<section class="tab" id="tab-phase">
  <div class="cards" id="cards-phase"></div>
  <div class="grid2">
    <div class="panel"><h2>SRS — waste phases <span class="pill srs">SRS</span></h2>
      <div class="desc">Area ∝ volume; labels show MCi where measured. Source: LWSP Rev 24 (2025-09-30).</div>
      <div style="width:100%"><canvas id="srsPhase"></canvas></div>
    </div>
    <div class="panel"><h2>Hanford — waste phases <span class="pill hf">Hanford</span></h2>
      <div class="desc">Volume share by BBI phase (wet phases; drained voids & retained gas excluded).</div>
      <div style="width:100%"><canvas id="hfPhase"></canvas></div>
    </div>
  </div>
  <div class="panel"><h2>Per-farm distribution</h2>
    <div class="desc">Tanks grouped by farm: volume and activity basis.</div>
    <div id="farms" style="overflow-x:auto"></div>
  </div>
</section>
<section class="tab" id="tab-rad">
  <div class="panel"><h2>Top radionuclides by site (log-scaled bars)</h2>
    <div class="desc">Total Ci. SRS = closure-residual inventories (51 tanks, decayed 2032); Hanford = BBI totals (177 tanks, decayed 2022).</div>
    <div id="radbars"></div>
    <div class="legend" id="radlegend"></div>
  </div>
  <div class="grid2">
    <div class="panel"><h2>Radionuclide share of site total</h2>
      <div class="desc">Top 8 nuclides as % of each site's total (orange SRS / blue HF).</div><div id="radshare"></div>
    </div>
    <div class="panel"><h2>Site comparison table</h2>
      <div class="desc">Ci per nuclide.</div>
      <div class="tanklist" id="radtable"></div>
    </div>
  </div>
</section>
<section class="tab" id="tab-tanks">
  <div class="controls">
    <label>Y-axis: <select id="sizeMetric">
      <option value="vol">Volume (kgal)</option>
      <option value="kg">Chemical mass (kg)</option>
    </select></label>
    <label>Min activity (Ci): <input type="range" id="minCi" min="-2" max="7" step="1" value="-2">
      <span id="minCiLabel" style="color:var(--fg)">≥ 0.01 Ci</span></label>
    <label>Highlight: <select id="highlight">
      <option value="">none</option><option value="top10">Top 10 by activity</option>
    </select></label>
  </div>
  <div class="panel"><h2>Each tank, one bubble (log X = activity Ci, log Y = selected metric)</h2>
    <div class="desc"><span class="pill srs">SRS</span> 51 tanks (activity = closure-residual basis; volume = capacity) ·
      <span class="pill hf">Hanford</span> 177 tanks (BBI). Click a bubble for detail.</div>
    <div class="scatter"><canvas id="tanks"></canvas></div>
    <div id="tankDetail" style="margin-top:10px;font-size:.8rem;color:var(--muted)">Click a bubble for tank detail.</div>
  </div>
  <div class="grid2">
    <div class="panel"><h2>SRS tanks <span class="pill srs">SRS</span></h2>
      <div class="tanklist"><table id="srsTable"></table></div>
    </div>
    <div class="panel"><h2>Hanford tanks (top by activity) <span class="pill hf">Hanford</span></h2>
      <div class="tanklist"><table id="hfTable"></table></div>
    </div>
  </div>
</section>
<section class="tab" id="tab-chem">
  <div class="note blue">ℹ Hanford's BBI publishes per-tank kg for ~140 chemical analytes (in the SQLite DB, table hanford_bbi, units=kg).
  SRS's public per-tank chemical data are closure-residual elementals. This tab shows SRS's <b>current measured waste chemistry</b>
  from SRNL batch characterization reports — the closest public equivalent of a BBI sample basis.</div>
  <div class="grid2">
    <div class="panel"><h2>SRS current waste — Sludge Batch 11 (Tank 51, 2024) <span class="pill srs">SRS</span></h2>
      <div class="desc">DWPF feed-prep slurry: elemental composition (µg/g slurry, log-scaled bars).</div>
      <div id="sb11chem" class="tanklist"></div>
    </div>
    <div class="panel"><h2>SRS current waste — Salt Batch chemistry (SWPF feed) <span class="pill srs">SRS</span></h2>
      <div class="desc">Filtrate major components, mg/L. Bars: Salt Batch 8 (2024, orange) vs Salt Batch 12 (2025, gold).</div>
      <div id="saltchem" class="tanklist"></div>
    </div>
  </div>
  <div class="panel"><h2>SRS current waste — radionuclide concentrations</h2>
    <div class="desc">DWPF Sludge Batch 10 (Tank 40 sample, 2023): µCi/g dried solids — the DWPF feed basis. Plus SWPF Salt Batch 14 filtrate (pCi/mL).</div>
    <div class="tanklist" id="currad"></div>
  </div>
</section>
<section class="tab" id="tab-methods">
  <div class="panel"><h2>Data provenance</h2>
    <table>
      <tr><th>Site</th><th>Dataset</th><th>Source</th><th>As-of / basis</th></tr>
      <tr><td><span class="pill srs">SRS</span></td><td>Farm current inventory (33.2 Mgal / 191 MCi)</td><td>Liquid Waste System Plan Rev 24 (SRMC-LWP-2023-00001), WCS Curie & Volume Inventory Report</td><td>2025-09-30</td></tr>
      <tr><td><span class="pill srs">SRS</span></td><td>Per-tank radionuclides (54 nuclides) & chemicals (27 analytes)</td><td>Tank 16 SA (SRR-CWDA-2014-00106) Tbl 6.2-2/3; Tanks 5&6 SA (SRR-CWDA-2012-00106) Tbl 6.1-1/2; HTF PA (SRR-CWDA-2010-00128) Tbl 3.4-9/10; actuals for tanks 5/6/12/16/18/19</td><td>closure residual, decayed 2032</td></tr>
      <tr><td><span class="pill srs">SRS</span></td><td>Current waste chemistry (SB11, SB10, Salt Batches 8-14, PRFT)</td><td>SRNL-STI-2024-00492, -2024-00240, -2024-00436, -2025-00489, -2025-00012, OSTI 2473257/2483548</td><td>2023-2025 samples</td></tr>
      <tr><td><span class="pill hf">HF</span></td><td>Best-Basis Inventory (46,600 rows: 54 radionuclides + 140 chemicals × 7 phases)</td><td>PNNL PHOENIX TankFarmService API (BBIWaste / BBIVolume, all 177 tanks)</td><td>effective 2025-10-01, decay 2022-01-01</td></tr>
    </table>
  </div>
  <div class="panel"><h2>Caveats (read before comparing)</h2>
    <ul style="line-height:1.7;font-size:.85rem;color:var(--muted)">
      <li><b>Decay dates differ</b>: Hanford BBI decayed to 2022-01-01; SRS PA values decayed to 2032. The site-level current difference (191 vs ~123 MCi) is dominated by real inventory, not decay.</li>
      <li><b>SRS per-tank = closure residuals</b>: what will remain AFTER waste removal (4,000 gal/tank assigned basis). NOT today's tank contents. HTF values are conservative max-of-group assignments.</li>
      <li><b>Hanford totals include all 177 tanks</b> incl. inactive single-shell farms; both sites' totals shrink as processing continues (SRS: 91% of curies in salt waste targeted by SWPF/DWPF; Hanford: DFLAW vitrification + TSCR).</li>
      <li><b>Chemical bases differ</b>: SRS per-tank kg are elements on residual sludge; Hanford kg include supernate salts (Na nitrate/nitrite dominate mass). The Current Chemistry tab gives the fair waste-type comparison.</li>
      <li>Ba-137m / Y-90 are daughters counted with parents at both sites — treat as families (Cs-137+Ba-137m, Sr-90+Y-90).</li>
    </ul>
  </div>
  <div class="panel"><h2>Files</h2>
    <div style="font-size:.8rem;line-height:1.8">
      <code>srs_tank_waste.db</code> — combined SQLite (SRS + Hanford BBI)<br>
      <code>dashboard/dashboard_data.json</code> — this dashboard's data ·
      <code>data_processed/srnl_current_waste.json</code> — SRNL batch parse ·
      <code>data_raw/</code> — 19 source PDFs · <code>scripts/</code> — reproducible pipeline
    </div>
  </div>
</section>
</main>
<footer>Assembled by Hermes agent from public DOE/NRC/PNNL sources · SRS: LWSP Rev 24 + 4 PA/SA documents + 7 SRNL characterization reports · Hanford: PHOENIX BBI API (published 2025-12-31) · See Methods & Caveats for basis differences.</footer>
<script>
const DATA = __DATA__;
const fmt = (v, d=2) => {
  if (v === null || v === undefined || isNaN(v)) return '—';
  const a = Math.abs(v);
  if (a >= 1e6) return (v/1e6).toFixed(1)+'M';
  if (a >= 1e3) return (v/1e3).toFixed(a>=1e4?0:1)+'k';
  if (a >= 1) return v.toFixed(d);
  if (a >= 0.01) return v.toFixed(a>=0.1?2:3);
  if (a === 0) return '0';
  return v.toExponential(1);
};
const K = Object.keys, V = Object.values, E = Object.entries;
function h(tag, attrs, ...kids){
  const e=document.createElement(tag);
  for(const [k,v] of E(attrs||{})){
    if(k==='onclick') e.onclick=v;
    else if(k==='style') e.setAttribute('style',v);
    else e.setAttribute(k,v);
  }
  for(const c of kids.flat(9)){
    if(c==null) continue;
    e.append(c.nodeType?c:document.createTextNode(c));
  }
  return e;
}
function plot(cv, w, hh){
  const r=window.devicePixelRatio||1;
  cv.width=Math.max(10,Math.round(w*r)); cv.height=Math.max(10,Math.round(hh*r));
  cv.style.width=w+'px'; cv.style.height=hh+'px';
  const ctx=cv.getContext('2d'); ctx.setTransform(r,0,0,r,0,0);
  return ctx;
}
document.getElementById('built').textContent = new Date().toLocaleDateString('en-US',{year:'numeric',month:'short',day:'numeric'});
document.getElementById('dl').onclick = () => {
  const blob = new Blob([JSON.stringify(DATA,null,1)],{type:'application/json'});
  const a = document.createElement('a'); a.href=URL.createObjectURL(blob); a.download='dashboard_data.json'; a.click();
};
const RENDER = {};
const rendered = {};
function activateTab(name){
  document.querySelectorAll('nav.tabs button').forEach(x=>x.classList.toggle('active', x.dataset.tab===name));
  document.querySelectorAll('section.tab').forEach(x=>x.classList.toggle('active', x.id==='tab-'+name));
  if (RENDER[name] && !rendered[name]) {
    try { RENDER[name](); rendered[name]=true; } catch(e) { console.error('render '+name, e); }
  }
}
document.querySelectorAll('nav.tabs button').forEach(b=>b.onclick=()=>activateTab(b.dataset.tab));

/* ============ OVERVIEW (rendered immediately) ============ */
const S = DATA.srs_current, H = DATA.hanford_current;
(function cards(){
  const items=[
    ['srs','SRS remaining waste','33.2','Mgal','191 MCi · 43 tanks · 2025-09-30'],
    ['hf','Hanford remaining waste',H.total_mgal.toFixed(1),'Mgal',H.total_mci.toFixed(0)+' MCi · 177 tanks · BBI 2025-10'],
    ['srs','SRS curie density','5.8','MCi/Mgal','191 MCi ÷ 33.2 Mgal — salt-dominated'],
    ['hf','Hanford curie density',(H.total_mci/H.total_mgal).toFixed(1),'MCi/Mgal',H.total_mci.toFixed(0)+' MCi ÷ '+H.total_mgal.toFixed(1)+' Mgal'],
    ['srs','SRS waste processed','~46','MCi removed','since SRMC contract start (227→191 MCi)'],
    ['hf','Hanford farms','12','farms','67 single-shell + 28 double-shell tanks in BBI'],
  ];
  document.getElementById('cards-overview').append(...items.map(([cls,label,big,unit,foot])=>
    h('div',{class:'card '+cls},
      h('div',{class:'label'},label),
      h('div',{class:'big'},big,' ',h('span',{class:'unit'},unit)),
      h('div',{class:'foot'},foot))));
  const rows=[
    ['Total volume (Mgal)', S.total_mgal, H.total_mgal, v=>v.toFixed(1)],
    ['Total activity (MCi)', S.total_mci, H.total_mci, v=>v.toFixed(0)],
    ['Sludge (Mgal)', S.sludge.mgal, H.sludge.mgal, v=>v.toFixed(1)],
    ['Supernate (Mgal)', S.supernate.mgal, H.supernate.mgal, v=>v.toFixed(1)],
    ['Saltcake (Mgal)', S.saltcake.mgal, H.saltcake.mgal, v=>v.toFixed(1)],
    ['Sludge activity (MCi)', S.sludge.mci, H.sludge.mci, v=>v.toFixed(0)],
    ['Salt waste activity (MCi)', (S.supernate.mci+S.saltcake.mci), (H.total_mci-H.sludge.mci), v=>v.toFixed(0)],
    ['Tanks remaining', 43, 177, v=>v.toFixed(0)],
  ];
  const t=h('table',{},h('tr',{},h('th',{},'Metric'),h('th',{},'SRS'),h('th',{},'Hanford'),h('th',{},'Ratio SRS/HF')));
  rows.forEach(([lab,a,b,f])=>{
    const ratio=(a&&b)?(a/b):null;
    t.append(h('tr',{},h('td',{},lab),
      h('td',{class:'num',style:'color:var(--srs);font-weight:600'},f(a)),
      h('td',{class:'num',style:'color:var(--hf);font-weight:600'},f(b)),
      h('td',{class:'num',style:'color:var(--muted)'},ratio?ratio.toFixed(2)+'×':'—')));
  });
  document.getElementById('head2head').append(t);
  const el=document.getElementById('scalectx');
  const items2=[
    ['SRS volume = '+(S.total_mgal/H.total_mgal*100).toFixed(0)+'% of Hanford volume', S.total_mgal/H.total_mgal,
     'yet SRS holds MORE curies (191 vs '+H.total_mci.toFixed(0)+' MCi): its salt waste is Cs-137 rich'],
    ['SRS salt waste share of volume', (S.supernate.mgal+S.saltcake.mgal)/S.total_mgal,
     'SWPF + DSP + Saltstone process it; sludge (9% of volume) holds 54% of SRS curies'],
    ['Hanford sludge share of volume', H.sludge.mgal/H.total_mgal,
     'direct vitrification at DFLAW; Hanford supernatant feeds TSCR'],
  ];
  items2.forEach(([lab,frac,note])=>{
    el.append(h('div',{style:'margin:12px 0'},
      h('div',{style:'font-size:.8rem;margin-bottom:4px'},lab),
      h('div',{class:'bar'},
        h('div',{class:'seg',style:'width:'+Math.max(1,frac*100).toFixed(0)+'%;background:linear-gradient(90deg,var(--srs),var(--hf))'},
          h('span',{},(frac*100).toFixed(0)+'%'))),
      h('div',{style:'font-size:.72rem;color:var(--muted);margin-top:2px'},note)));
  });
})();

/* ============ PHASES ============ */
function phaseChart(cvId, phases, colors){
  const cv=document.getElementById(cvId);
  const wrap=cv.parentElement;
  const cw=(wrap.clientWidth>300?wrap.clientWidth:window.innerWidth*0.46);
  const W=Math.max(280,cw-10), Hh=430;
  const ctx=plot(cv,W,Hh);
  const total=phases.reduce((s,p)=>s+p.mgal,0);
  const area=m=>total>0? m/total*(W*Hh) : 0;
  const rows=[];
  function layout(items,x,y,w,hh){
    if(items.length===0||w<=0||hh<=0) return;
    if(items.length===1){rows.push(Object.assign({},items[0],{x,y,w,hh}));return;}
    let acc=0,k=0; const half=items.reduce((s,p)=>s+area(p.mgal),0)/2;
    for(;k<items.length-1;k++){acc+=area(items[k].mgal);if(acc>=half)break;}
    const g1=items.slice(0,k+1),g2=items.slice(k+1);
    const a1=g1.reduce((s,p)=>s+area(p.mgal),0);
    const frac=(w*hh)>0?a1/(w*hh):0.5;
    if(w>hh){const w1=w*frac;layout(g1,x,y,w1,hh);layout(g2,x+w1,y,w-w1,hh);}
    else{const h1=hh*frac;layout(g1,x,y,w,h1);layout(g2,x,y+h1,w,hh-h1);}
  }
  layout([...phases].sort((a,b)=>b.mgal-a.mgal),0,0,W,Hh);
  rows.forEach(p=>{
    if(p.w<1||p.hh<1) return;
    ctx.fillStyle=colors[p.name]||'#666';
    ctx.fillRect(p.x+1,p.y+1,p.w-2,p.hh-2);
    if(p.w>80&&p.hh>44){
      ctx.fillStyle='#0d1117';ctx.textAlign='left';
      ctx.font='700 13px -apple-system,sans-serif';
      ctx.fillText(p.name,p.x+8,p.y+20);
      ctx.font='12px -apple-system,sans-serif';
      ctx.fillText(p.mgal.toFixed(1)+' Mgal'+(p.mci!=null?' · '+p.mci.toFixed(0)+' MCi':''),p.x+8,p.y+38);
    } else if(p.w>44&&p.hh>24){
      ctx.fillStyle='#0d1117';ctx.textAlign='left';ctx.font='10px -apple-system';
      ctx.fillText(p.name,p.x+5,p.y+14);
      ctx.fillText(p.mgal.toFixed(1)+'M',p.x+5,p.y+26);
    }
  });
}
RENDER.phase = function(){
  phaseChart('srsPhase',[
    {name:'Supernate',mgal:S.supernate.mgal,mci:S.supernate.mci},
    {name:'Saltcake',mgal:S.saltcake.mgal,mci:S.saltcake.mci},
    {name:'Sludge',mgal:S.sludge.mgal,mci:S.sludge.mci},
  ],{Supernate:'#f0883e',Saltcake:'#d29922',Sludge:'#a371f7'});
  const agg={};
  DATA.hf_tanks.forEach(t=>E(t.phases).forEach(([p,v])=>agg[p]=(agg[p]||0)+v));
  const map={'Supernatant':'Supernatant','Saltcake Solid':'Saltcake Solid','Saltcake (Liquid & Solid)':'Saltcake (L&S)',
    'Saltcake Interstitial Liquid':'Saltcake Interstitial Liq.','Sludge (Liquid & Solid)':'Sludge (L&S)',
    'Sludge Solid':'Sludge Solid','Sludge Interstitial Liquid':'Sludge Interstitial Liq.'};
  const phases=E(agg).map(([p,v])=>({name:map[p]||p,mgal:v/3785.412}));
  const mci={Supernatant:H.supernate.mci,'Sludge (L&S)':H.sludge.mci};
  phases.forEach(p=>p.mci=(p.name in mci)?mci[p.name]:null);
  phaseChart('hfPhase',phases,{Supernatant:'#79c0ff','Saltcake Solid':'#58a6ff','Saltcake (L&S)':'#388bfd',
    'Saltcake Interstitial Liq.':'#1f6feb','Sludge (L&S)':'#a371f7','Sludge Solid':'#8957e5','Sludge Interstitial Liq.':'#6e40c9'});
  const el=document.getElementById('farms');
  el.innerHTML='';
  const srsF={},hfF={};
  DATA.srs_tanks.forEach(t=>{srsF[t.farm]=srsF[t.farm]||{n:0,ci:0,cap:0};srsF[t.farm].n++;srsF[t.farm].ci+=t.ci;srsF[t.farm].cap+=t.cap_kL||0;});
  DATA.hf_tanks.forEach(t=>{hfF[t.farm]=hfF[t.farm]||{n:0,ci:0,vol:0};hfF[t.farm].n++;hfF[t.farm].ci+=t.ci;hfF[t.farm].vol+=t.vol_kL||0;});
  const t=h('table',{},h('tr',{},h('th',{},'Site'),h('th',{},'Farm'),h('th',{},'Tanks'),
    h('th',{class:'num'},'Capacity / BBI volume (Mgal)'),h('th',{class:'num'},'Activity basis (Ci)')));
  E(srsF).forEach(([f,v])=>t.append(h('tr',{},
    h('td',{},h('span',{class:'pill srs'},'SRS')),h('td',{},f+'-Tank Farm'),h('td',{class:'num'},''+v.n),
    h('td',{class:'num'},(v.cap/1000).toFixed(1)),h('td',{class:'num'},fmt(v.ci)))));
  E(hfF).sort((a,b)=>b[1].ci-a[1].ci).forEach(([f,v])=>t.append(h('tr',{},
    h('td',{},h('span',{class:'pill hf'},'HF')),h('td',{},f),h('td',{class:'num'},''+v.n),
    h('td',{class:'num'},(v.vol/3785.412).toFixed(2)),h('td',{class:'num'},fmt(v.ci)))));
  el.append(t);
};

/* ============ RADIONUCLIDES ============ */
RENDER.rad = function(){
  const srs={},hf={};
  function hfName(n){const m=n.match(/^([A-Z][a-z]?)-(\d+)(m?)$/);return m?m[2]+m[1]+(m[3]||''):n;}
  DATA.srs_top.forEach(({n,v})=>srs[n]=v);
  DATA.hf_top.forEach(({n,v})=>hf[n]=v);
  const srsHf={};E(srs).forEach(([n,v])=>srsHf[hfName(n)]=v);
  const all=[...new Set([...K(srsHf),...K(hf)])];
  const totals={srs:E(srsHf).reduce((s,[,v])=>s+v,0),hf:E(hf).reduce((s,[,v])=>s+v,0)};
  const rows=all.map(n=>({n,srs:srsHf[n]||0,hf:hf[n]||0}));
  rows.sort((a,b)=>Math.max(b.srs,b.hf)-Math.max(a.srs,a.hf));
  const show=rows.slice(0,16);
  const maxV=Math.max(...show.flatMap(r=>[r.srs,r.hf]));
  const el=document.getElementById('radbars'); el.innerHTML='';
  show.forEach(r=>{
    const wS=Math.max(0.5,Math.log10(Math.max(r.srs,1e-12))/Math.log10(maxV)*100);
    const wH=Math.max(0.5,Math.log10(Math.max(r.hf,1e-12))/Math.log10(maxV)*100);
    el.append(h('div',{class:'hbar-row'},
      h('div',{class:'nm'},r.n),
      h('div',{},h('div',{class:'trk',style:'height:30px'},
        h('div',{class:'fill',style:'position:absolute;top:0;height:13px;background:var(--srs);width:'+wS.toFixed(1)+'%'}),
        h('div',{class:'fill',style:'position:absolute;bottom:0;height:13px;background:var(--hf);width:'+wH.toFixed(1)+'%'}))),
      h('div',{class:'val'},'SRS '+fmt(r.srs)+' · HF '+fmt(r.hf))));
  });
  document.getElementById('radlegend').append(
    h('span',{},h('i',{style:'background:var(--srs)'}),'SRS (closure residual, decayed 2032)'),
    h('span',{},h('i',{style:'background:var(--hf)'}),'Hanford (BBI, decayed 2022)'),
    h('span',{},'bar length ∝ log₁₀(Ci)'));
  const share=document.getElementById('radshare'); share.innerHTML='';
  show.slice(0,8).forEach(r=>{
    const ps=totals.srs?r.srs/totals.srs*100:0, ph=totals.hf?r.hf/totals.hf*100:0;
    share.append(h('div',{style:'margin:7px 0'},
      h('div',{style:'font-size:.75rem;margin-bottom:3px'},r.n),
      h('div',{class:'bar',style:'height:16px'},
        h('div',{class:'seg',style:'width:'+ps.toFixed(1)+'%;background:var(--srs)'},h('span',{},ps>4?ps.toFixed(0)+'%':'')),
        h('div',{class:'seg',style:'width:'+ph.toFixed(1)+'%;background:var(--hf)'},h('span',{},ph>4?ph.toFixed(0)+'%':'')))));
  });
  const tbl=document.getElementById('radtable'); tbl.innerHTML='';
  const t=h('table',{},h('tr',{},h('th',{},'Nuclide'),h('th',{class:'num'},'SRS Ci'),h('th',{class:'num'},'HF Ci'),h('th',{class:'num'},'HF/SRS')));
  rows.slice(0,30).forEach(r=>t.append(h('tr',{},h('td',{},r.n),
    h('td',{class:'num',style:'color:var(--srs)'},r.srs?fmt(r.srs):'—'),
    h('td',{class:'num',style:'color:var(--hf)'},r.hf?fmt(r.hf):'—'),
    h('td',{class:'num',style:'color:var(--muted)'},(r.srs>0&&r.hf>0)?(r.hf/r.srs).toFixed(1)+'×':'—'))));
  tbl.append(t);
};

/* ============ TANK EXPLORER ============ */
RENDER.tanks = function(){
  const cv=document.getElementById('tanks');
  const detail=document.getElementById('tankDetail');
  const SRS_COL='rgba(240,136,62,.8)',HF_COL='rgba(121,192,255,.6)';
  function draw(){
    const wrap=cv.parentElement;
    const cw=(wrap.clientWidth>400?wrap.clientWidth:window.innerWidth*0.92);
    const W=Math.max(320,cw-10),Hh=520;
    const ctx=plot(cv,W,Hh);
    ctx.clearRect(0,0,W,Hh);
    const yMode=document.getElementById('sizeMetric').value;
    const minV=Math.pow(10,parseFloat(document.getElementById('minCi').value));
    document.getElementById('minCiLabel').textContent='≥ '+fmt(minV);
    const padL=64,padB=42,padT=16,padR=16;
    const xMin=-2,xMax=8.4,yMin=-2,yMax=3.8;
    const X=v=>padL+(v-xMin)/(xMax-xMin)*(W-padL-padR);
    const Y=v=>Hh-padB-(v-yMin)/(yMax-yMin)*(Hh-padB-padT);
    ctx.strokeStyle='rgba(48,54,61,.6)';ctx.fillStyle='#8b949e';ctx.font='10px -apple-system';
    for(let e=xMin;e<=xMax;e++){const x=X(e);ctx.beginPath();ctx.moveTo(x,padT);ctx.lineTo(x,Hh-padB);ctx.stroke();
      if(e%2===0){ctx.textAlign='center';ctx.fillText('1e'+e,x,Hh-padB+14);}}
    for(let e=yMin;e<=yMax;e++){const y=Y(e);ctx.beginPath();ctx.moveTo(padL,y);ctx.lineTo(W-padR,y);ctx.stroke();
      ctx.textAlign='right';ctx.fillText('1e'+e,padL-6,y+3);}
    ctx.textAlign='center';ctx.fillText('Activity per tank (Ci, log)',(padL+W-padR)/2,Hh-8);
    ctx.save();ctx.translate(12,(padT+Hh-padB)/2);ctx.rotate(-Math.PI/2);
    ctx.fillText(yMode==='vol'?'Volume (kgal, log)':'Chemical mass (kg, log)',0,0);ctx.restore();
    const pts=[];
    const yvS=t=>yMode==='vol'?t.cap_kL/3785.412:t.kg;
    const yvH=t=>yMode==='vol'?t.vol_kgal:t.kg;
    DATA.srs_tanks.forEach(t=>{if(t.ci>0&&yvS(t)>0)pts.push({x:t.ci,y:yvS(t),t,site:'srs'});});
    DATA.hf_tanks.forEach(t=>{if(t.ci>0&&yvH(t)>0)pts.push({x:t.ci,y:yvH(t),t,site:'hf'});});
    const hl=document.getElementById('highlight').value;
    let topIds=new Set();
    if(hl==='top10'){[...pts].sort((a,b)=>b.x-a.x).slice(0,10).forEach(p=>topIds.add(p.site+'-'+p.t.id));}
    const logs=pts.map(p=>Math.log10(p.y)).sort((a,b)=>a-b);
    const lo=logs[Math.floor(logs.length*0.03)],hi=logs[Math.floor(logs.length*0.97)]||lo+1;
    const rad=p=>{const f=(Math.log10(p.y)-lo)/((hi-lo)||1);return 2.5+Math.max(0,Math.min(1,f))*12;};
    pts.sort((a,b)=>b.y-a.y).reverse();
    pts.forEach(p=>{
      if(p.x<minV) return;
      p._x=X(Math.log10(p.x));p._y=Y(Math.log10(p.y));p._r=rad(p);
      ctx.beginPath();ctx.arc(p._x,p._y,p._r,0,7);
      ctx.globalAlpha=(p.site==='srs')?0.85:0.6;
      ctx.fillStyle=p.site==='srs'?SRS_COL:HF_COL;ctx.fill();
      if(topIds.has(p.site+'-'+p.t.id)){ctx.globalAlpha=1;ctx.strokeStyle='#fff';ctx.lineWidth=1.5;ctx.stroke();}
      ctx.globalAlpha=1;
    });
    cv.__pts=pts;
  }
  cv.onclick=ev=>{
    const r=cv.getBoundingClientRect();const mx=ev.clientX-r.left,my=ev.clientY-r.top;
    const hit=(cv.__pts||[]).filter(p=>{const dx=mx-p._x,dy=my-p._y;return dx*dx+dy*dy<=(p._r+4)**2;})
      .sort((a,b)=>(a._r>b._r?1:-1))[0];
    if(!hit){detail.innerHTML='Click a bubble for tank detail.';return;}
    const t=hit.t;
    if(hit.site==='srs'){
      detail.innerHTML='<b style="color:var(--srs)">SRS Tank '+t.id+'</b> ('+t.farm+', Type '+t.type+') — '+t.status+
        (t.closure?' · closed '+t.closure:'')+'<br>Capacity: '+fmt(t.cap_kL)+' kL ('+(t.cap_gal/1e6).toFixed(2)+' Mgal)'+
        ' · Assigned closure activity: '+fmt(t.ci)+' Ci · Chemicals: '+fmt(t.kg)+' kg'+
        (t.residual_gal?' · Residual at closure: '+t.residual_gal.toLocaleString()+' gal':'')+
        '<br>Top nuclides (assigned): '+t.top.map(x=>x.n+' '+fmt(x.v)).join(' · ');
    }else{
      detail.innerHTML='<b style="color:var(--hf)">Hanford '+t.name+'</b> ('+t.farm+')'+
        '<br>BBI wet volume: '+t.vol_kL.toLocaleString(undefined,{maximumFractionDigits:0})+' kL ('+t.vol_kgal.toFixed(3)+' Mgal)'+
        ' · Activity: '+fmt(t.ci)+' Ci · Chemical mass: '+fmt(t.kg)+' kg'+
        '<br>Top nuclides: '+t.top.map(x=>x.n+' '+fmt(x.v)).join(' · ');
    }
  };
  ['sizeMetric','minCi','highlight'].forEach(id=>document.getElementById(id).addEventListener('input',draw));
  draw();
  const st=document.getElementById('srsTable'); st.innerHTML='';
  st.append(h('tr',{},h('th',{},'Tank'),h('th',{},'Type'),h('th',{},'Status'),h('th',{class:'num'},'Cap (Mgal)'),h('th',{class:'num'},'Assigned Ci'),h('th',{class:'num'},'Chem kg')));
  DATA.srs_tanks.forEach(t=>st.append(h('tr',{},h('td',{},t.id),h('td',{},t.type),
    h('td',{},t.status+(t.closure?' ('+t.closure+')':'')),
    h('td',{class:'num'},(t.cap_kL/3785.412).toFixed(2)),
    h('td',{class:'num',style:'color:var(--srs)'},fmt(t.ci)),h('td',{class:'num'},fmt(t.kg,0)))));
  const ht=document.getElementById('hfTable'); ht.innerHTML='';
  ht.append(h('tr',{},h('th',{},'Tank'),h('th',{},'Farm'),h('th',{class:'num'},'Vol (kL)'),h('th',{class:'num'},'Ci'),h('th',{class:'num'},'Chem kg'),h('th',{},'Top nuclide')));
  [...DATA.hf_tanks].sort((a,b)=>b.ci-a.ci).forEach(t=>ht.append(h('tr',{},h('td',{},t.name),h('td',{},t.farm),
    h('td',{class:'num'},t.vol_kL.toLocaleString(undefined,{maximumFractionDigits:0})),
    h('td',{class:'num',style:'color:var(--hf)'},fmt(t.ci)),h('td',{class:'num'},fmt(t.kg,0)),
    h('td',{},t.top[0]?t.top[0].n:'—'))));
};

/* ============ CHEMISTRY ============ */
RENDER.chem = function(){
  const sb=DATA.srs_samples['Tank 51 Sludge Batch 11']||[];
  const els=sb.filter(x=>x.cat==='element'&&x.unit==='ug/g slurry').sort((a,b)=>b.value-a.value);
  const max=Math.max(...els.map(e=>e.value),1e-9);
  const el1=document.getElementById('sb11chem'); el1.innerHTML='';
  els.forEach(e=>{
    el1.append(h('div',{class:'hbar-row'},
      h('div',{class:'nm'},e.analyte),
      h('div',{},h('div',{class:'trk'},h('div',{class:'fill',style:'background:var(--srs);width:'+Math.max(0.6,Math.log10(e.value)/Math.log10(max)*100).toFixed(1)+'%'}))),
      h('div',{class:'val'},fmt(e.value)+' µg/g')));
  });
  const s8=DATA.srs_samples['SWPF Salt Batch 8 (Tank 40, SRNL filtered)']||[];
  const s12=DATA.srs_samples['SWPF Salt Batch 12 (SWPF-AL filtered)']||[];
  const m8={},m12={};
  s8.filter(x=>x.cat==='component').forEach(x=>m8[x.analyte]=x.value);
  s12.filter(x=>x.cat==='component').forEach(x=>m12[x.analyte]=x.value);
  const comps=[...new Set([...K(m8),...K(m12)])];
  const cmax=Math.max(...comps.flatMap(c=>[m8[c]||0,m12[c]||0]),1e-9);
  const el2=document.getElementById('saltchem'); el2.innerHTML='';
  comps.sort((a,b)=>(m12[b]||m8[b]||0)-(m12[a]||m8[a]||0)).forEach(c=>{
    el2.append(h('div',{class:'hbar-row'},
      h('div',{class:'nm'},c),
      h('div',{},h('div',{class:'trk',style:'height:28px'},
        h('div',{class:'fill',style:'position:absolute;top:0;height:12px;background:#f0883e;width:'+(((m8[c]||0)/cmax)*100).toFixed(1)+'%'}),
        h('div',{class:'fill',style:'position:absolute;bottom:0;height:12px;background:#d29922;width:'+(((m12[c]||0)/cmax)*100).toFixed(1)+'%'}))),
      h('div',{class:'val'},fmt(m8[c]||0)+' / '+fmt(m12[c]||0)+' mg/L')));
  });
  el2.append(h('div',{style:'font-size:.7rem;color:var(--muted);margin-top:6px'},
    'orange = Salt Batch 8 (2024) · gold = Salt Batch 12 (2025) · SWPF feed is ~5-8 M Na nitrate/nitrite'));
  const s10=DATA.srs_samples['Tank 40 Sludge Batch 10']||[];
  const sb10=s10.filter(x=>x.unit==='uCi/g dried solids'&&x.value>0).sort((a,b)=>b.value-a.value).slice(0,20);
  const s14=DATA.srs_samples['SWPF Salt Batch 14 (Tank 21H)']||[];
  const sb14=s14.filter(x=>x.cat==='radionuclide').sort((a,b)=>b.value-a.value);
  const el3=document.getElementById('currad'); el3.innerHTML='';
  const t=h('table',{},h('tr',{},h('th',{},'Sample'),h('th',{},'Analyte'),h('th',{class:'num'},'Value'),h('th',{},'Units')));
  sb10.forEach(x=>t.append(h('tr',{},h('td',{},h('span',{class:'pill srs'},'SB10 sludge')),h('td',{},x.analyte),
    h('td',{class:'num'},fmt(x.value)),h('td',{},x.unit))));
  sb14.forEach(x=>t.append(h('tr',{},h('td',{},h('span',{class:'pill srs'},'Salt Batch 14')),h('td',{},x.analyte),
    h('td',{class:'num'},fmt(x.value)),h('td',{},x.unit))));
  el3.append(t);
};
</script>
</body>
</html>
"""
html = html.replace("__DATA__", json.dumps(DATA))
OUT.write_text(html)
print(f"wrote {OUT} ({len(html)/1024:.0f} KB)")
