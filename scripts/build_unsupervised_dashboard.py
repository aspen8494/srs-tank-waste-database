#!/usr/bin/env python3
"""Generate the cross-site unsupervised-learning dashboard (self-contained HTML).

Reads data_processed/unsupervised/clustering_results.json and renders
dashboard/unsupervised_analysis.html with zero external dependencies:
  Tab 1  Overview      - method summary, point counts, K + quality metrics per panel
  Tab 2-4  Panel tabs  - UMAP scatter (Hanford clusters + SRS/closure points),
                         cluster profile bars, dendrogram, SRS sample analog cards
  Tab 5  Analog finder - every SRS sample -> nearest Hanford analogs (all panels)
  Tab 6  Anomalies     - HDBSCAN noise points + outlier scores per panel
  Tab 7  Methods       - pipeline, caveats, repro commands
"""
import json
from pathlib import Path

BASE = Path("/Users/aspen_mb/Documents/Savannah_RiverTF")
IN = BASE / "data_processed" / "unsupervised"
OUT = BASE / "dashboard" / "unsupervised_analysis.html"

R = json.load(open(IN / "clustering_results.json"))
PD = json.load(open(IN / "panel_defs.json"))
BR = json.load(open(IN / "build_report.json"))

PANELS = ["sludge", "salt", "rad"]
PANEL_LABEL = {
    "sludge": "Sludge space",
    "salt": "Salt space",
    "rad": "Radionuclide space",
}
PANEL_DESC = {
    "sludge": "Element chemistry of solid/sludge phases (mass-fraction CLR)",
    "salt": "Anion/cation chemistry of supernate & saltcake (mass-fraction CLR)",
    "rad": "Activity signature, decay-corrected to 2025-10-01 (activity-fraction CLR)",
}
CLUSTER_COLORS = ["#58a6ff", "#f0883e", "#3fb950", "#d2a8ff", "#ffa657",
                  "#79c0ff", "#7ee787", "#ff7b72", "#56d4dd", "#e3b341"]

def jdump(o):
    return json.dumps(o, separators=(",", ":")).replace("</", "<\\/")

# ---------------------------------------------------------------- payload ----
payload = {}
for nm in PANELS:
    s1 = R["stage1"][nm]
    pts = []
    for pid, xy in s1["umap_hf"].items():
        site, tank, phase = pid.split("|", 2)
        m = R["stage1"][nm]
        pts.append({
            "id": pid, "tank": tank, "phase": phase,
            "x": xy[0], "y": xy[1],
            "cluster": s1["labels"][pid],
            "site": "Hanford",
            "basis": "BBI current",
            "outlier": s1["hdbscan"]["outlier_scores"].get(pid),
            "vol": None})
    # SRS + closure points (projected)
    for tr, kind in (("measured", "SRS"), ("closure", "SRS-closure")):
        for r in R["stage2"][nm][tr]:
            if "umap_xy" not in r:
                continue
            label = r["point_id"].split("|", 1)[1]
            pts.append({
                "id": r["point_id"], "tank": label.split("|")[0],
                "phase": label.split("|", 1)[1] if "|" in label else "",
                "x": r["umap_xy"][0], "y": r["umap_xy"][1],
                "cluster": r.get("nearest_cluster"),
                "site": kind,
                "basis": r["basis"],
                "pctl": r.get("cluster_dist_pctl"),
                "proj": r})
    payload[nm] = {
        "points": pts,
        "profiles": s1["cluster_profiles"],
        "k": s1["chosen_k"],
        "sweep": s1["kmeans_sweep"],
        "ward_sil": s1["ward_silhouette_at_k"],
        "ward_ari": s1["ward_ari_vs_kmeans"],
        "ward_coph": s1["ward_cophenetic"],
        "hdbscan": {"n_clusters": s1["hdbscan"]["n_clusters"],
                    "noise": s1["hdbscan"]["n_noise"]},
        "cluster_x_phase": s1["cluster_x_phase"],
        "cluster_x_wastetype": s1["cluster_x_wastetype"],
        "dendro": s1.get("dendrogram_trunc"),
        "kept_cols": PD[nm]["kept"],
        "dropped_cols": PD[nm]["dropped"],
        "n_points": s1["n_points"],
    }

all_proj = {nm: R["stage2"][nm] for nm in PANELS}
meta_payload = {
    "build": {k: BR[k] for k in ("counts", "sludge_coverage", "salt_coverage",
                                 "rad_coverage", "srs_dl_halved",
                                 "hf_below_detection_rows", "layer_sum_dedup")},
    "projections": all_proj,
}

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Unsupervised Cross-Site Waste Taxonomy — Hanford & SRS</title>
<style>
:root{
  --bg:#0d1117; --panel:#161b22; --panel2:#1c2129; --border:#30363d;
  --fg:#e6edf3; --muted:#8b949e; --accent:#58a6ff; --srs:#f0883e; --hf:#79c0ff;
  font-size:15px;
}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);
  font-family:-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}
header{padding:22px 28px 10px;border-bottom:1px solid var(--border)}
h1{margin:0 0 4px;font-size:1.4rem;letter-spacing:.2px}
.sub{color:var(--muted);font-size:.85rem;max-width:900px;line-height:1.45}
nav.tabs{display:flex;gap:6px;padding:14px 28px 0;border-bottom:1px solid var(--border);flex-wrap:wrap}
nav.tabs button{background:none;border:1px solid transparent;border-bottom:none;color:var(--muted);
  padding:8px 16px;font-size:.9rem;cursor:pointer;border-radius:8px 8px 0 0}
nav.tabs button.active{color:var(--fg);background:var(--panel);border-color:var(--border);position:relative;top:1px}
main{padding:20px 28px 80px}
section.tab{display:none}
section.tab.active{display:block}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin:14px 0 22px}
.card{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:13px 16px}
.card .label{color:var(--muted);font-size:.7rem;text-transform:uppercase;letter-spacing:.8px;margin-bottom:5px}
.card .big{font-size:1.45rem;font-weight:700;line-height:1.1}
.card .foot{margin-top:5px;font-size:.72rem;color:var(--muted)}
.panel{background:var(--panel);border:1px solid var(--border);border-radius:10px;padding:16px;margin-bottom:18px}
.panel h2{margin:0 0 4px;font-size:1rem}
.panel .desc{color:var(--muted);font-size:.8rem;margin-bottom:12px}
.grid2{display:grid;grid-template-columns:3fr 2fr;gap:18px}
@media(max-width:1000px){.grid2{grid-template-columns:1fr}}
canvas{display:block;width:100%;border-radius:8px}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:.74rem;color:var(--muted);margin-top:8px}
.legend i{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px;vertical-align:-1px}
table{width:100%;border-collapse:collapse;font-size:.8rem}
th{color:var(--muted);text-align:left;font-weight:600;padding:6px 9px;border-bottom:1px solid var(--border);
  font-size:.7rem;text-transform:uppercase;letter-spacing:.5px}
td{padding:6px 9px;border-bottom:1px solid var(--panel2);vertical-align:top}
tr:hover td{background:var(--panel2)}
.num{text-align:right;font-variant-numeric:tabular-nums}
.tag{display:inline-block;padding:1px 8px;border-radius:10px;font-size:.7rem;font-weight:600;white-space:nowrap}
.tag.hf{background:#1f3a5f;color:#79c0ff}
.tag.srs{background:#4a2c17;color:#f0883e}
.tag.cl{background:#3b2140;color:#d2a8ff}
.small{font-size:.74rem;color:var(--muted)}
details{margin:6px 0}
summary{cursor:pointer;color:var(--accent);font-size:.85rem}
.pill{display:inline-block;background:var(--panel2);border:1px solid var(--border);border-radius:6px;
  padding:2px 8px;margin:2px 4px 2px 0;font-size:.72rem}
.pill b{color:var(--accent)}
.hint{background:#2d1f00;border:1px solid #634a00;color:#e3b341;border-radius:8px;
  padding:10px 14px;font-size:.8rem;margin:12px 0}
kbd{background:var(--panel2);border:1px solid var(--border);border-radius:4px;padding:1px 6px;font-size:.78rem}
code{background:var(--panel2);border-radius:4px;padding:1px 5px;font-size:.82rem}
pre{background:var(--panel2);border:1px solid var(--border);border-radius:8px;padding:12px;overflow-x:auto;font-size:.8rem}
</style>
</head>
<body>
<header>
  <h1>Unsupervised Cross-Site Waste Taxonomy — <span style="color:var(--hf)">Hanford BBI</span> <span style="color:var(--muted);font-weight:400">vs</span> <span style="color:var(--srs)">SRS SRNL samples</span></h1>
  <div class="sub">
    Two-stage unsupervised learning: Hanford's 433 tank&nbsp;×&nbsp;phase Best-Basis Inventory compositions define a
    waste taxonomy per feature space (Ward hierarchical clustering on Aitchison/CLR-transformed compositions);
    SRS's measured DWPF/SWPF samples and closure-residual vectors are then <i>projected</i> onto that taxonomy
    with shared-support Aitchison distances. Scale-invariant CLR geometry makes mg/L, µg/g, kg and Ci/gal
    directly comparable without density assumptions.
  </div>
</header>
<nav class="tabs" id="tabs"></nav>
<main id="main"></main>
<script id="payload" type="application/json">__PAYLOAD__</script>
<script id="metapayload" type="application/json">__META__</script>
<script>
"use strict";
const DATA = JSON.parse(document.getElementById('payload').textContent);
const META = JSON.parse(document.getElementById('metapayload').textContent);
const COLORS = __COLORS__;
const PANELS = __PANELS__;
const PANEL_LABEL = __PANEL_LABEL__;
const PANEL_DESC = __PANEL_DESC__;
let currentPanel = 'sludge';

// ------------------------------------------------------------- helpers ----
function el(tag, attrs, ...kids){
  const e = document.createElement(tag);
  for(const k in attrs||{}) e[k] = attrs[k];
  for(const kid of kids){ if(kid) e.appendChild(typeof kid==='string'?document.createTextNode(kid):kid); }
  return e;
}
function fmt(n, d=2){ return n==null ? '—' : Number(n).toFixed(d); }
function clusterTag(c, site){
  if(site==='Hanford') return `<span class="tag hf">C${c}</span>`;
  if(site==='SRS') return `<span class="tag srs">C${c} (projected)</span>`;
  return `<span class="tag cl">C${c} (projected)</span>`;
}

// ---------------------------------------------------------------- tabs ----
const TAB_DEFS = [['overview','Overview'],
  ['sludge','Sludge space'],['salt','Salt space'],['rad','Rad space'],
  ['analogs','Analog finder'],['anomalies','Anomalies'],['methods','Methods']];
const tabsNav = document.getElementById('tabs');
const main = document.getElementById('main');
const sections = {};
for(const [id,label] of TAB_DEFS){
  const b = el('button',{textContent:label, onclick:()=>activate(id)});
  b.dataset.tab = id;
  tabsNav.appendChild(b);
  const s = el('section',{className:'tab'}); s.id = 'tab-'+id;
  main.appendChild(s); sections[id] = s;
}
function activate(id){
  for(const b of tabsNav.children) b.classList.toggle('active', b.dataset.tab===id);
  for(const k in sections) sections[k].classList.toggle('active', k===id);
  currentPanel = id;
  if(PANELS.includes(id)) renderPanel(id);
}

// ------------------------------------------------------------- overview ----
(function overview(){
  const s = sections.overview;
  const cards = el('div',{className:'cards'});
  const counts = META.build.counts;
  const card = (label, big, foot) => el('div',{className:'card'}, 
    el('div',{className:'label',textContent:label}),
    el('div',{className:'big',innerHTML:big}),
    el('div',{className:'foot',innerHTML:foot||''}));
  cards.append(
    card('Hanford points', counts.hf_points, `${counts.hf_sludge} sludge · ${counts.hf_salt} salt/supernate phases`),
    card('SRS measured samples', counts.srs_samples, 'SRNL qualification reports 2023–2025'),
    card('SRS closure vectors', counts.srs_closure, 'flagged 2032-closure basis, separate track'),
    card('Feature spaces', '3', 'sludge elements · salt anions · radionuclides'));
  s.appendChild(cards);

  const grid = el('div',{className:'grid2'});
  const tbl = el('table');
  tbl.innerHTML = `<tr><th>Panel</th><th>Points</th><th>Features</th><th>K (Ward)</th>
    <th>Silhouette</th><th>ARI vs KMeans</th><th>Cophenetic</th><th>HDBSCAN k / noise</th></tr>`;
  for(const nm of PANELS){
    const d = DATA[nm];
    tbl.innerHTML += `<tr><td><b>${PANEL_LABEL[nm]}</b><br><span class="small">${d.n_points} Hanford points</span></td>
      <td class="num">${d.n_points}</td><td class="num">${d.kept_cols.length}</td>
      <td class="num"><b>${d.k}</b></td><td class="num">${fmt(d.ward_sil,3)}</td>
      <td class="num">${fmt(d.ward_ari,2)}</td><td class="num">${fmt(d.ward_coph,3)}</td>
      <td class="num">${d.hdbscan.n_clusters} / ${d.hdbscan.noise}</td></tr>`;
  }
  const left = el('div',{className:'panel'}, el('h2',{textContent:'Clustering quality per feature space'}),
    el('div',{className:'desc',textContent:'Ward hierarchical clustering on CLR-transformed compositions; K chosen by max KMeans silhouette in the interpretable 4–9 range; HDBSCAN provides density-based anomaly flags.'}), tbl);
  grid.appendChild(left);

  const right = el('div',{className:'panel'}, el('h2',{textContent:'Method in one paragraph'}),
    el('div',{className:'desc',innerHTML:`Each tank-phase composition is closed to mass fractions over its <i>measured</i> analytes and
      log-ratio transformed (CLR). Absent analytes get the neutral Aitchison replacement (CLR&nbsp;=&nbsp;0, no distance pull),
      so a missing measurement is never treated as a zero concentration. Below-detection values use DL/2
      (${META.build.srs_dl_halved} SRS substitutions; Hanford BBI reports sub-DL estimates as-is).
      Hanford's 43 radionuclides are decay-corrected to 2025-10-01 (per-tank BBI decay dates range 2015-07 to 2022-01);
      secular-equilibrium daughters (⁹⁰Y, ¹³⁷ᵐBa) fold into parents.<br><br>
      <b>Stage 1</b>: Ward taxonomy per panel (labels: ${counts.hf_points} points).<br>
      <b>Stage 2</b>: each SRS point is CLR-transformed on the same panel, assigned to the nearest centroid,
      and scored against that cluster's own member distances (percentile) — plus top-5 nearest Hanford
      analogs under <i>shared-support</i> Aitchison distance (only analytes measured on both sides count).
      <div class="hint">Basis caveat: SRS per-tank vectors are <b>closure residuals</b> (post-cleaning, decayed to 2032),
      not current waste. They enter only the flagged closure track. SRS <i>current</i> composition exists only as the
      ${counts.srs_samples} SRNL samples — that asymmetry is why projection percentiles matter.</div>`}));
  grid.appendChild(right);
  s.appendChild(grid);
})();

// -------------------------------------------------------------- scatter ----
function renderPanel(nm){
  const s = sections[nm]; s.textContent = '';
  const d = DATA[nm];
  const pts = d.points;

  // head cards
  const cards = el('div',{className:'cards'});
  const card = (l,b,f)=>el('div',{className:'card'},
    el('div',{className:'label',textContent:l}), el('div',{className:'big',innerHTML:b}),
    el('div',{className:'foot',innerHTML:f||''}));
  cards.append(
    card('Ward clusters (K)', `<b>${d.k}</b>`, `silhouette ${fmt(d.ward_sil,3)}`),
    card('Hanford points', d.points.filter(p=>p.site==='Hanford').length, `${d.kept_cols.length} features kept`),
    card('SRS samples projected', d.points.filter(p=>p.site==='SRS').length, `+ ${d.points.filter(p=>p.site==='SRS-closure').length} closure vectors`),
    card('Dropped features', d.dropped_cols.length, d.dropped_cols.slice(0,6).join(', ') + (d.dropped_cols.length>6?'…':'')));
  s.appendChild(cards);

  const grid = el('div',{className:'grid2'});
  // ---- scatter panel
  const sp = el('div',{className:'panel'});
  sp.appendChild(el('h2',{textContent:`${PANEL_LABEL[nm]} — UMAP projection`}));
  sp.appendChild(el('div',{className:'desc',innerHTML:`${PANEL_DESC[nm]}. Hanford points colored by Ward cluster;
    SRS measured (<span style="color:var(--srs)">orange</span>) and closure vectors
    (<span style="color:#d2a8ff">purple</span>) drawn as stars at their UMAP-transformed positions.
    Click any point for details.`}));
  const cv = el('canvas',{width:900,height:640,style:'width:100%;max-width:900px;height:auto'});
  sp.appendChild(cv);
  // headless/edge-case guard: if the wrapper collapses (measures <300px), size
  // from the viewport instead so the chart remains usable everywhere
  requestAnimationFrame(()=>{
    const w = cv.parentElement.clientWidth;
    if (w < 300){ cv.style.width = Math.min(900, window.innerWidth*0.9) + 'px'; }
  });
  const legend = el('div',{className:'legend'});
  for(let c=0;c<d.k;c++) legend.appendChild(el('span',{},el('i',{style:`background:${COLORS[c%COLORS.length]}`}),`Cluster ${c}`));
  legend.appendChild(el('span',{},el('i',{style:'background:var(--srs);border-radius:50%'}),'SRS measured'));
  legend.appendChild(el('span',{},el('i',{style:'background:#d2a8ff;border-radius:50%'}),'SRS closure'));
  sp.appendChild(legend);
  const info = el('div',{className:'panel',style:'display:none;margin-top:10px'});
  sp.appendChild(info);
  grid.appendChild(sp);

  // ---- cluster profiles
  const pp = el('div',{className:'panel'});
  pp.appendChild(el('h2',{textContent:'Cluster profiles'}));
  pp.appendChild(el('div',{className:'desc',innerHTML:'Mean mass (or activity) fraction of top analytes within each cluster; hover the UMAP or click a row to highlight.'}));
  const pt = el('table');
  pt.innerHTML = '<tr><th>Cluster</th><th>n</th><th>Top analytes (mean fraction)</th></tr>';
  for(const [c, prof] of Object.entries(d.profiles)){
    const chips = Object.entries(prof.top_analytes).map(([a,v])=>
      `<span class="pill">${a} <b>${v>=0.01?fmt(v*100,1)+'%':v.toExponential(1)}</b></span>`).join('');
    pt.innerHTML += `<tr><td>${clusterTag(c,'Hanford')}</td><td class="num">${prof.n_members}</td>
      <td>${chips}<br><span class="small">phases: ${
        Object.entries(d.cluster_x_phase[c]||{}).map(([p,n])=>`${p.replace(' (Liquid & Solid)','').replace(' Interstitial Liquid',' int-liqu')}: ${n}`).join(' · ')
      }</span></td></tr>`;
  }
  pp.appendChild(pt);

  // dendrogram
  const pd = el('details',{});
  pd.appendChild(el('summary',{textContent:'Dendrogram (last 24 merges, truncated)'}));
  const dcv = el('canvas',{width:820,height:300,style:'width:100%;height:auto'});
  pd.appendChild(dcv);
  pp.appendChild(pd);
  grid.appendChild(pp);
  s.appendChild(grid);

  // ---- SRS projection cards
  const proj = el('div',{className:'panel'});
  proj.appendChild(el('h2',{textContent:'SRS samples in this space'}));
  proj.appendChild(el('div',{className:'desc',innerHTML:
    `Each measured SRS sample (and closure vector, flagged) with its nearest Hanford cluster, projection percentile
     (0% = dead center of the cluster, ≥95% = at/beyond the cluster edge → weak analog), and top-5 nearest
     Hanford tank-phases by shared-support Aitchison distance (k = analytes counted).`}));
  const jt = el('table');
  jt.innerHTML = `<tr><th>Point</th><th>Basis</th><th>Nearest C</th><th>dist / pctl</th><th>Top analogs (tank · phase · type · dAit · k)</th><th>Driving analytes</th></tr>`;
  for(const [trk, label] of [['measured','SRS current'],['closure','SRS closure 2032']]){
    for(const r of META.projections[nm][trk]){
      if(r.status==='insufficient_data'){
        jt.innerHTML += `<tr><td>${r.point_id.split('|').slice(1).join(' · ')}</td>
          <td><span class="tag ${trk==='measured'?'srs':'cl'}">${label}</span></td>
          <td colspan="4" class="small">insufficient shared analytes in this panel</td></tr>`;
        continue;
      }
      const a5 = (r.top5_analogs||[]).map(a=>
        `${a.tank} ${a.phase.replace(' (Liquid & Solid)','(L&S)')} <span class="small">${a.waste_type.slice(0,14)}</span> · ${fmt(a.d_aitchison,2)} · k${a.n_shared}`
      ).join('<br>');
      const drv = Object.entries(r.driving_analytes||{}).map(([a,v])=>`<span class="pill">${a} <b>${fmt(v,1)}</b></span>`).join('');
      jt.innerHTML += `<tr><td><b>${r.point_id.split('|')[1]}</b><br><span class="small">${r.point_id.split('|')[2]||''}</span></td>
        <td><span class="tag ${trk==='measured'?'srs':'cl'}">${label}</span></td>
        <td>C${r.nearest_cluster}</td>
        <td class="num">${fmt(r.centroid_dist,2)}<br><span class="small" style="color:${(r.cluster_dist_pctl||0)>95?'#e3b341':'inherit'}">pctl ${fmt(r.cluster_dist_pctl,0)}%</span></td>
        <td class="small">${a5}</td><td>${drv}</td></tr>`;
    }
  }
  proj.appendChild(jt);
  s.appendChild(proj);

  // ---------------- draw scatter
  const ctx = cv.getContext('2d');
  const W = cv.width, H = cv.height;
  const xs = pts.map(p=>p.x), ys = pts.map(p=>p.y);
  const [x0,x1,y0,y1] = [Math.min(...xs),Math.max(...xs),Math.min(...ys),Math.max(...ys)];
  const pad = 40;
  const sx = v=>pad+(v-x0)/(x1-x0||1)*(W-2*pad);
  const sy = v=>H-pad-(v-y0)/(y1-y0||1)*(H-2*pad);
  const hasLineDash = typeof ctx.setLineDash === 'function';
  function draw(highlight){
    ctx.clearRect(0,0,W,H);
    ctx.fillStyle = '#0d1117'; ctx.fillRect(0,0,W,H);
    ctx.strokeStyle = '#21262d'; ctx.strokeRect(pad,pad,W-2*pad,H-2*pad);
    // Hanford first (background)
    for(const p of pts){
      if(p.site!=='Hanford') continue;
      ctx.beginPath();
      ctx.arc(sx(p.x),sy(p.y), highlight===p.id?7:(p.outlier>0.85?4.5:3.5), 0, 7);
      ctx.fillStyle = COLORS[p.cluster%COLORS.length];
      ctx.globalAlpha = p.outlier>0.85 ? 0.45 : 0.8;
      if(p.outlier>0.85 && hasLineDash){ ctx.setLineDash([2,2]); ctx.strokeStyle='#ff7b72'; ctx.stroke(); ctx.setLineDash([]); }
      else if (p.outlier>0.85){ ctx.strokeStyle='#ff7b72'; ctx.stroke(); }
      ctx.fill(); ctx.globalAlpha = 1;
    }
    // SRS/closure stars on top
    for(const p of pts){
      if(p.site==='Hanford') continue;
      const cx = sx(p.x), cy = sy(p.y), r = highlight===p.id?13:9;
      ctx.beginPath();
      for(let i=0;i<10;i++){
        const ang = -Math.PI/2 + i*Math.PI/5, rr = i%2?r*0.45:r;
        i?ctx.lineTo(cx+rr*Math.cos(ang),cy+rr*Math.sin(ang)):ctx.moveTo(cx+rr*Math.cos(ang),cy+rr*Math.sin(ang));
      }
      ctx.closePath();
      ctx.fillStyle = p.site==='SRS'?'#f0883e':'#d2a8ff';
      ctx.fill();
      ctx.strokeStyle = '#0d1117'; ctx.lineWidth=1.5; ctx.stroke(); ctx.lineWidth=1;
    }
  }
  draw();
  cv.onclick = ev=>{
    const rect = cv.getBoundingClientRect();
    const mx = (ev.clientX-rect.left)*W/rect.width, my=(ev.clientY-rect.top)*H/rect.height;
    const inRange = [];
    for(const p of pts){
      const dd=(sx(p.x)-mx)**2+(sy(p.y)-my)**2;
      if(dd<900) inRange.push([dd,p]);
    }
    if(inRange.length){
      // prefer SRS/closure points (drawn on top, the interactive focus), then nearest
      const rank = p => (p.site==='Hanford')?1:0;
      inRange.sort((a,b)=> rank(a[1])-rank(b[1]) || a[0]-b[0]);
      const best = inRange[0][1];
      draw(best.id); showInfo(best);
    }
  };
  function showInfo(p){
    info.style.display='block';
    let html = `<b>${p.tank}</b> <span class="small">${p.phase} · ${p.site} (${p.basis})</span><br>`;
    if(p.site==='Hanford'){
      html += `${clusterTag(p.cluster,'Hanford')} HDBSCAN outlier score ${fmt(p.outlier,3)}`;
    } else {
      const r = p.proj;
      html += `${clusterTag(r.nearest_cluster,'SRS')} centroid d=${fmt(r.centroid_dist,2)}, 
        cluster pctl ${fmt(r.cluster_dist_pctl,0)}%<br><span class="small">Top analog: ${
        (r.top5_analogs||[]).map(a=>`${a.tank} ${a.phase} (${a.waste_type})`).join(' · ')}</span>`;
    }
    info.innerHTML = html;
  }

  // ---------------- draw dendrogram
  if(d.dendro){
    const c2 = dcv.getContext('2d');
    const W2=dcv.width, H2=dcv.height;
    c2.clearRect(0,0,W2,H2); c2.fillStyle='#0d1117'; c2.fillRect(0,0,W2,H2);
    const {icoord, dcoord, ivl} = d.dendro;
    const maxD = Math.max(...dcoord.flat());
    const xg = v=>v/100*(W2-80)+40, yg = v=>H2-24-(v/maxD)*(H2-40);
    c2.strokeStyle='#58a6ff'; c2.fillStyle='#8b949e'; c2.font='10px -apple-system';
    for(let i=0;i<icoord.length;i++){
      const xs2=icoord[i], ys2=dcoord[i];
      c2.beginPath();
      c2.moveTo(xg(xs2[0]),yg(ys2[0])); c2.lineTo(xg(xs2[0]),yg(ys2[1]));
      c2.lineTo(xg(xs2[2]),yg(ys2[2])); c2.lineTo(xg(xs2[2]),yg(ys2[3]));
      c2.stroke();
      if(String(ivl[i]).length<8){ c2.fillText(ivl[i], xg(xs2[0])-6, H2-8); }
    }
  }
}

// -------------------------------------------------------------- analogs ----
(function analogs(){
  const s = sections.analogs;
  s.appendChild(el('div',{className:'panel'}, el('h2',{textContent:'Cross-site analog finder'}),
    el('div',{className:'desc',innerHTML:`For every SRS sample, its five nearest Hanford tank-phase compositions
      in <b>each</b> feature space, by shared-support Aitchison distance. k = number of shared analytes the
      distance actually used; small k means the match rests on few measurements — treat with caution.`})));
  for(const nm of PANELS){
    const p = el('div',{className:'panel'});
    p.appendChild(el('h2',{textContent:PANEL_LABEL[nm]}));
    const t = el('table');
    t.innerHTML = `<tr><th>SRS sample</th><th>Basis</th><th>→ C</th><th>pctl</th>
      <th>1st analog</th><th>2nd</th><th>3rd</th><th>4th</th><th>5th</th></tr>`;
    for(const [trk,label] of [['measured','current'],['closure','closure-2032']]){
      for(const r of META.projections[nm][trk]){
        const a = r.top5_analogs||[];
        const cell = (x)=> x?`<b>${x.tank}</b> <span class="small">${x.phase.replace(' (Liquid & Solid)','(L&S)')}<br>${fmt(x.d_aitchison,2)} · k${x.n_shared}</span>`:'—';
        t.innerHTML += `<tr><td><b>${r.point_id.split('|')[1]}</b><br><span class="small">${r.point_id.split('|')[2]||''}</span></td>
          <td><span class="tag ${trk==='measured'?'srs':'cl'}">${label}</span></td>
          <td>${r.nearest_cluster!=null?'C'+r.nearest_cluster:'—'}</td>
          <td class="num">${r.cluster_dist_pctl!=null?fmt(r.cluster_dist_pctl,0)+'%':'—'}</td>
          ${[0,1,2,3,4].map(i=>`<td>${cell(a[i])}</td>`).join('')}</tr>`;
      }
    }
    p.appendChild(t); s.appendChild(p);
  }
})();

// ------------------------------------------------------------ anomalies ----
(function anomalies(){
  const s = sections.anomalies;
  s.appendChild(el('div',{className:'panel'}, el('h2',{textContent:'Density-based anomaly candidates (HDBSCAN)'}),
    el('div',{className:'desc',innerHTML:`HDBSCAN (min_cluster_size ≈ n/25, min_samples=1) flags points in
      low-density regions. In waste-composition space these are tanks/phases whose chemistry departs from every
      family — candidates for data-quality review or genuinely unusual waste. Outlier score: 0–1, higher = more
      anomalous. Listed: all points with score > 0.85 or labeled noise.`})));
  for(const nm of PANELS){
    const d = DATA[nm];
    const p = el('div',{className:'panel'});
    p.appendChild(el('h2',{textContent:`${PANEL_LABEL[nm]} — ${d.hdbscan.noise} noise / ${d.n_points} points`}));
    const rows = d.points.filter(x=>x.site==='Hanford' && (x.outlier>0.85))
      .sort((a,b)=>b.outlier-a.outlier);
    const t = el('table');
    t.innerHTML = `<tr><th>Tank</th><th>Phase</th><th>Ward C</th><th>Outlier score</th></tr>`;
    for(const x of rows.slice(0,30)){
      t.innerHTML += `<tr><td><b>${x.tank}</b></td><td>${x.phase}</td>
        <td>C${x.cluster}</td><td class="num">${fmt(x.outlier,3)}</td></tr>`;
    }
    if(rows.length>30) t.innerHTML += `<tr><td colspan="4" class="small">+ ${rows.length-30} more…</td></tr>`;
    p.appendChild(t); s.appendChild(p);
  }
})();

// -------------------------------------------------------------- methods ----
(function methods(){
  const s = sections.methods;
  const b = META.build;
  s.innerHTML = `
  <div class="panel"><h2>Pipeline</h2>
   <div class="desc">Fully reproducible from the repo root:</div>
<pre>source .venv/bin/activate
python scripts/build_unsupervised_features.py      # SQLite -> tidy matrices (X_*.csv, presence_*.csv)
python scripts/run_unsupervised_clustering.py      # CLR, Ward, KMeans sweep, HDBSCAN, UMAP, projection
python scripts/build_unsupervised_dashboard.py    # this file</pre></div>

  <div class="panel"><h2>Feature engineering</h2>
   <div class="desc">
   <b>Units.</b> Because every analyte in a single sample shares one unknown scale factor, and CLR is
   scale-invariant, mixed SRS units (mg/L, µg/g slurry, mg/kg, molar, Ci/gal, pCi/mL, dpm/g) are directly
   comparable to Hanford kg-inventories. Physical conversions are still applied where possible
   (mg/L → µg/g via measured density 1.27–1.33 g/mL; PO₄→P factor 30.974/94.971 for the sludge panel;
   molar Free OH → mass OH) so reported mass fractions are meaningful, but <i>no comparison depends on them</i>.<br><br>
   <b>Presence floor.</b> Features kept only when reported for ≥40% (sludge), ≥70% (salt), ≥50% (rad) of Hanford points
   — prevents rare-analyte noise from driving clusters. Kept: ${PANELS.map(n=>`${DATA[n].kept_cols.length} ${n}`).join(', ')}.
   Dropped: ${PANELS.map(n=>`${DATA[n].dropped_cols.length} ${n}`).join(', ')}.
   <br><br>
   <b>Missing = neutral.</b> Absent analytes get Aitchison's neutral replacement (per-point geometric mean →
   CLR coordinate 0): they exert zero pull on any distance, unlike zero-imputation which fabricates strong signals.
   <br><br>
   <b>Below detection.</b> SRS '<' values → DL/2 (${b.srs_dl_halved} substitutions). Hanford BBI sub-DL rows
   (${b.hf_below_detection_rows}) enter as reported (standard BBI practice), flagged via qualifier.
   <br><br>
   <b>Decay.</b> Hanford radionuclides decay-corrected from per-tank BBI dates (2015-07-01 or 2022-01-01) to
   2025-10-01. Secular-equilibrium daughters (⁹⁰Y→⁹⁰Sr, ¹³⁷ᵐBa→¹³⁷Cs) folded into parents. Short-lived
   ¹⁰⁶Ru/¹⁴⁴Ce (t½ < 0.5 y) vanish by 2025 — retained only where inventory survives. SRS closure vectors
   (decayed to 2032) are corrected back where half-life > 5 y, capped at 10×.
   <br><br>
   <b>Layer dedup.</b> Hanford BBI rows collapse per (tank, phase, analyte): ${b.layer_sum_dedup.layer_rows_collapsed}
   layer duplicates summed into ${b.layer_sum_dedup.distinct_tank_phase_analyte} distinct keys.</div></div>

  <div class="panel"><h2>Model choices & why</h2>
   <div class="desc">
   <b>CLR (Aitchison) geometry</b> — compositions live on a simplex; raw concentrations would make cluster
   distances depend on total mass (a dilute supernate and a concentrated sludge of identical <i>composition</i>
   would look unrelated). CLR removes scale, leaving pure composition.<br>
   <b>Ward hierarchical</b> — deterministic, gives dendrograms (defensible grouping history), robust to the
   neutral-replacement zeros that confuse density methods. K chosen by max silhouette over KMeans sweep
   (k=2..12) restricted to the interpretable 4–9 range; Ward's own partition at that K validated against KMeans
   via ARI (sludge 0.79, salt 0.75, rad 0.71 — same structure up to relabeling).<br>
   <b>HDBSCAN</b> — density view for anomaly flagging only; its min_cluster_size ≈ n/25 with min_samples=1
   yields conservative noise sets.<br>
   <b>UMAP</b> — 2-D visualization only (n_neighbors=15, min_dist=0.1); SRS points projected via
   <code>reducer.transform()</code>, never re-fit, so they land <i>relative to the Hanford geometry</i>.<br>
   <b>Shared-support Aitchison distance</b> — for cross-site analogs only analytes measured on BOTH sides enter
   the distance (with its own centering); k reports the support size.</div></div>

  <div class="panel"><h2>Validation</h2>
   <div class="desc">External labels never used in fitting: Hanford clusters cross-tabulated against BBI
   waste_type codes (1C, CWR1, R1, DE, CWP2, 224-…) and against the BBI phase labels — see per-panel cluster
   tables. Coverage diagnostics: Hanford sludge points carry ${Math.round(b.sludge_coverage.hf_mean_frac_analytes*100)}%
   of panel analytes on average (salt ${Math.round(b.salt_coverage.hf_mean_frac_analytes*100)}%,
   rad ${Math.round(b.rad_coverage.hf_mean_frac_analytes*100)}%);
   SRS samples carry ${Math.round(b.sludge_coverage.srs_mean_frac_analytes*100)}%/${Math.round(b.salt_coverage.srs_mean_frac_analytes*100)}%/${Math.round(b.rad_coverage.srs_mean_frac_analytes*100)}%
   (sludge/salt/rad) because qualification-report panels differ per matrix.</div></div>

  <div class="panel"><h2>Basis caveat (the one that matters)</h2>
   <div class="desc">SRS publishes no per-tank current inventory. The per-tank SRS vectors here are
   <b>closure residuals</b> (conservative PA/SA bases, decayed to 2032) — what remains <i>after</i> cleaning.
   SRS <i>current</i> waste composition exists publicly only as the ${b.counts.srs_samples} SRNL qualification samples
   (SB10/SB11, Salt Batches 8–14, PRFT 15/22/26). The two bases are never mixed in one model without a basis flag;
   closure vectors appear only in the flagged closure track. Hanford's BBI is <i>current</i> waste. Projection
   percentiles quantify how far each SRS point sits from Hanford's current-waste taxonomy — large percentiles
   are informative (no true analog at Hanford), not errors.</div></div>

  <div class="panel"><h2>Files</h2>
   <div class="desc"><code>scripts/build_unsupervised_features.py</code> ·
   <code>scripts/run_unsupervised_clustering.py</code> · <code>scripts/build_unsupervised_dashboard.py</code> ·
   outputs in <code>data_processed/unsupervised/</code> (X_*.csv, presence_*.csv, meta_*.csv,
   clustering_results.json, panel_defs.json, build_report.json).
   Data: <code>srs_tank_waste.db</code> (Hanford BBI via PNNL PHOENIX, effective 2015–2026 per tank;
   SRS SRNL reports SRNL-STI-2024-00240/00492, SRNL-STI-2024-00436, SRNL-STI-2025-00489, PRFT report).</div></div>`;
})();

activate('overview');
</script>
</body>
</html>
"""

html = (HTML.replace("__PAYLOAD__", jdump(payload))
            .replace("__META__", jdump(meta_payload))
            .replace("__COLORS__", jdump(CLUSTER_COLORS))
            .replace("__PANELS__", jdump(PANELS))
            .replace("__PANEL_LABEL__", jdump(PANEL_LABEL))
            .replace("__PANEL_DESC__", jdump(PANEL_DESC)))
OUT.write_text(html)
print(f"dashboard written: {OUT} ({OUT.stat().st_size//1024} KB)")
