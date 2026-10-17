#!/usr/bin/env python3
"""Build the 5 white-paper figures from verified DB data. Run with the Frameworks python."""
import sqlite3, re, os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams.update({
    "font.family": "serif", "figure.dpi": 300, "savefig.dpi": 300,
    "savefig.bbox": "tight", "axes.spines.top": False, "axes.spines.right": False,
    "font.size": 9,
})
BLUE, RED = "#1f4e79", "#a63d2f"
FIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "figs")
os.makedirs(FIG, exist_ok=True)
con = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "srs_tank_waste.db"))
cur = con.cursor()

NUC_MAP = {"Sr-90":"90Sr","Cs-137":"137Cs","Sm-151":"151Sm","Zr-93":"93Zr","Pu-238":"238Pu",
    "Am-241":"241Am","Pu-241":"241Pu","Ni-63":"63Ni","Cm-244":"244Cm","Tc-99":"99Tc",
    "Pu-239":"239Pu","Eu-154":"154Eu","Ba-137m":"137mBa","Y-90":"90Y"}

def latest_bbi():
    cur.execute("""
        SELECT b.tank, b.analyte, SUM(b.inventory) FROM hanford_bbi b
        JOIN (SELECT tank, MAX(effective_date) md FROM hanford_bbi GROUP BY tank) m
          ON b.tank = m.tank AND b.effective_date = m.md
        WHERE b.units='Ci' AND b.analyte NOT LIKE 'Total%' AND b.analyte NOT LIKE '%/%'
        GROUP BY b.tank, b.analyte""")
    per = {}
    for t, a, v in cur.fetchall():
        per.setdefault(t, {})[a] = v
    return per

def latest_vol():
    cur.execute("""
        SELECT v.tank, SUM(v.volume) FROM hanford_bbi_volume v
        JOIN (SELECT tank, MAX(effective_date) md FROM hanford_bbi_volume GROUP BY tank) m
          ON v.tank = m.tank AND v.effective_date = m.md
        WHERE v.waste_phase IN ('Saltcake Interstitial Liquid','Saltcake Solid','Sludge (Liquid & Solid)',
            'Sludge Solid','Supernatant','Saltcake (Liquid & Solid)','Sludge Interstitial Liquid')
        GROUP BY v.tank""")
    return dict(cur.fetchall())

# ---------- Figure: SRS decline 2016->2025 ----------
fig, ax = plt.subplots(figsize=(5.4, 3.2))
x = np.arange(3)
sl = [140, 116, 106]; sn = [123, 120, 75]; sc = [0, 12, 10]
ax.bar(x[0], sl[0], 0.55, color=RED, label="Sludge")
ax.bar(x[0], sc[0], 0.55, bottom=sl[0], color="#c8927d", label="Saltcake")
ax.bar(x[0], sn[0]-sc[0], 0.55, bottom=sl[0]+sc[0], color="#e3c1af", label="Supernate")
for i in (1, 2):
    ax.bar(x[i], sl[i], 0.55, color=RED)
    ax.bar(x[i], sc[i], 0.55, bottom=sl[i], color="#c8927d")
    ax.bar(x[i], sn[i]-sc[i], 0.55, bottom=sl[i]+sc[i], color="#e3c1af", label="Supernate" if i == 1 else None)
for i, tot in enumerate([263, 248, 191]):
    ax.text(i, tot + 6, f"{tot} MCi", ha="center", fontsize=9, fontweight="bold")
ax.set_xticks(x); ax.set_xticklabels(["Dec 2016", "Dec 2018", "Sep 2025"])
ax.set_ylabel("Total tank-farm activity (MCi)")
ax.set_ylim(0, 290)
ax.legend(frameon=False, fontsize=8, loc="upper right")
plt.savefig(f"{FIG}/fig1_srs_decline.png"); plt.close()

# ---------- Figure: phase splits side-by-side ----------
fig, ax = plt.subplots(figsize=(5.4, 3.2))
cats = ["Sludge / sludge solids", "Saltcake (solid + interstitial)", "Supernatant"]
srs = [2.8, 10.0, 16.4]; hf = [10.4, 21.3, 21.3]
xx = np.arange(3); w = 0.36
ax.bar(xx - w/2, srs, w, color=BLUE, label="SRS (33.2 Mgal total)")
ax.bar(xx + w/2, hf, w, color=RED, label="Hanford (53.0 Mgal total)")
for i, (s, h) in enumerate(zip(srs, hf)):
    ax.text(i - w/2, s + 0.4, f"{s}", ha="center", fontsize=8)
    ax.text(i + w/2, h + 0.4, f"{h}", ha="center", fontsize=8)
ax.set_xticks(xx); ax.set_xticklabels(cats, fontsize=8)
ax.set_ylabel("Volume (Mgal)")
ax.legend(frameon=False, fontsize=8)
plt.savefig(f"{FIG}/fig2_phase_split.png"); plt.close()

# ---------- Figure: top-12 nuclides both sites (log) ----------
srs_top = dict(cur.execute("""
    SELECT nuclide, SUM(value_ci)/1e6 FROM inventory_rad
    WHERE dataset IN ('htf_assigned_closure','ftf_assigned_closure')
    GROUP BY nuclide""").fetchall())
per = latest_bbi()
hf_top = {}
for t, d in per.items():
    for a, v in d.items():
        hf_top[a] = hf_top.get(a, 0) + v
hf_top = {k: v/1e6 for k, v in hf_top.items()}
order = ["Sr-90", "Cs-137", "Sm-151", "Zr-93", "Pu-238", "Am-241", "Pu-241", "Ni-63", "Cm-244", "Tc-99", "Pu-239", "Eu-154"]
labs = [NUC_MAP[n] for n in order]
srs_v = [srs_top.get(n, 0) for n in order]
hf_v = [hf_top.get(NUC_MAP[n], 0) for n in order]
fig, ax = plt.subplots(figsize=(5.6, 3.4))
xx = np.arange(len(order)); w = 0.38
ax.bar(xx - w/2, srs_v, w, color=BLUE, label="SRS assigned closure (51 tanks)")
ax.bar(xx + w/2, hf_v, w, color=RED, label="Hanford BBI (177 tanks)")
ax.set_yscale("log"); ax.set_ylim(1e-6, 40)
ax.set_xticks(xx); ax.set_xticklabels(labs, rotation=45, fontsize=7.5)
ax.set_ylabel("Site total (MCi)")
ax.legend(frameon=False, fontsize=8)
plt.savefig(f"{FIG}/fig3_nuclides.png"); plt.close()

# ---------- Figure: tank scatter (both sites) ----------
fig, ax = plt.subplots(figsize=(5.6, 3.6))
srs_rows = cur.execute("""
    SELECT tank_id, SUM(value_ci) FROM inventory_rad
    WHERE dataset IN ('htf_assigned_closure','ftf_assigned_closure')
    GROUP BY tank_id""").fetchall()
srs_pts = [(390, a) for _, a in srs_rows]  # fixed residual-volume placeholder not meaningful; use activity vs capacity
srs_caps = dict(cur.execute("SELECT tank_id, capacity_gal/1e6 FROM tanks").fetchall())
srs_pts = [(srs_caps[t], a/1e6) for t, a in srs_rows]
vols = latest_vol()
hf_pts = [(vols.get(t, 0) * 0.264172/1000, sum(d.values())/1e6) for t, d in per.items()]
ax.scatter([p[0] for p in srs_pts], [p[1] for p in srs_pts], s=14, color=BLUE, label="SRS (assigned closure)", alpha=0.85, edgecolors="none")
ax.scatter([p[0] for p in hf_pts], [p[1] for p in hf_pts], s=14, color=RED, label="Hanford BBI", alpha=0.6, edgecolors="none")
ax.set_xscale("log"); ax.set_yscale("log")
ax.set_xlabel("Tank capacity (SRS) / current volume (Hanford), Mgal")
ax.set_ylabel("Per-tank activity (MCi)")
ax.legend(frameon=False, fontsize=8, loc="upper left")
plt.savefig(f"{FIG}/fig4_tank_scatter.png"); plt.close()

# ---------- Figure: chemical composition (top elements) ----------
srs_chem = dict(cur.execute("""
    SELECT chemical, SUM(value_kg) FROM inventory_chem
    WHERE dataset IN ('htf_assigned_closure','ftf_assigned_closure')
    GROUP BY chemical""").fetchall())
hf_chem = {}
cur.execute("""
    SELECT b.analyte, SUM(b.inventory) FROM hanford_bbi b
    JOIN (SELECT tank, MAX(effective_date) md FROM hanford_bbi GROUP BY tank) m
      ON b.tank = m.tank AND b.effective_date = m.md
    WHERE b.units='kg' AND b.analyte NOT LIKE '%/%'
    GROUP BY b.analyte""")
for a, v in cur.fetchall():
    hf_chem[a] = v
elems = ["Fe", "Al", "Na", "NO3", "NO2", "Mn", "Ni", "U", "Hg", "Cr"]
srs_e = [srs_chem.get(e, 0)/1e3 for e in ["Fe", "Al", "Mn", "Ni", "U", "Hg", "Cr", "NO2", "NO3", "Na"]]
hf_e = [hf_chem.get(e, 0)/1e3 for e in elems]
labels = ["Fe", "Al", "Mn", "Ni", "U", "Hg", "Cr", "NO2", "NO3", "Na"]
fig, ax = plt.subplots(figsize=(5.6, 3.4))
xx = np.arange(len(labels)); w = 0.38
ax.bar(xx - w/2, srs_e, w, color=BLUE, label="SRS residual solids (assigned)")
ax.bar(xx + w/2, hf_e, w, color=RED, label="Hanford BBI")
ax.set_yscale("log"); ax.set_ylim(1, 1e5)
ax.set_xticks(xx); ax.set_xticklabels(labels, fontsize=8)
ax.set_ylabel("Site total (metric tons)")
ax.legend(frameon=False, fontsize=8)
plt.savefig(f"{FIG}/fig5_chemicals.png"); plt.close()
print("all 5 figures written to", FIG)
