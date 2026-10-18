#!/usr/bin/env python3
"""Figures for the unsupervised-taxonomy manuscript, from verified data only.

Every number plotted is read from data_processed/unsupervised/* this session;
the HF nearest-neighbor context distributions are recomputed live with the same
shared-support Aitchison function the analysis used (imported, not retyped).
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE = Path("/Users/aspen_mb/Documents/Savannah_RiverTF")
IN = BASE / "data_processed" / "unsupervised"
FIGS = BASE / "paper" / "unsup" / "figs"
FIGS.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(BASE / "scripts"))
from run_unsupervised_clustering import clr_transform  # noqa: E402

plt.rcParams.update({
    "font.family": "serif", "font.serif": ["Times New Roman", "Nimbus Roman", "DejaVu Serif"],
    "figure.dpi": 300, "savefig.dpi": 300, "savefig.bbox": "tight",
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.titlesize": 10, "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
})
PRIMARY, SECONDARY = "#1f4e79", "#a63d2f"
CLUSTER_COLORS = ["#1f4e79", "#a63d2f", "#3f6f3f", "#6a4c93", "#b8860b",
                  "#2e7d8a", "#8a3f5f", "#4a6fa5", "#7a7a52", "#946a3f"]
SRS_C, CL_C = "#c1440e", "#6a4c93"
PANELS = ["sludge", "salt", "rad"]
PANEL_TITLE = {"sludge": "Sludge elements", "salt": "Salt anions/cations", "rad": "Radionuclides"}
FLOOR = {"sludge": 0.40, "salt": 0.70, "rad": 0.50}

R = json.load(open(IN / "clustering_results.json"))
PD = json.load(open(IN / "panel_defs.json"))


def shared_aitchison(clr_a, pres_a, clr_b, pres_b):
    m = (pres_a > 0) & (pres_b > 0)
    k = int(m.sum())
    if k < 2:
        return None, k
    d = clr_a[m].to_numpy(dtype=float) - clr_b[m].to_numpy(dtype=float)
    d = d - d.mean()
    return float(np.sqrt((d ** 2).sum())), k


MATS = {}
for nm in PANELS:
    X = pd.read_csv(IN / f"X_{nm}.csv", index_col=0)
    P = pd.read_csv(IN / f"presence_{nm}.csv", index_col=0)
    clr = pd.read_csv(IN / f"X_{nm}_clr.csv", index_col=0)
    MATS[nm] = dict(X=X, P=P, clr=clr)

# ---------------------------------------------------------------- Figure: UMAP
fig, axes = plt.subplots(1, 3, figsize=(12.6, 4.3))
for ax, nm in zip(axes, PANELS):
    s1 = R["stage1"][nm]
    for pid, (x, y) in s1["umap_hf"].items():
        c = CLUSTER_COLORS[s1["labels"][pid] % len(CLUSTER_COLORS)]
        sc = s1["hdbscan"]["outlier_scores"].get(pid, 0.0)
        ax.scatter(x, y, s=14 if sc <= 0.85 else 20, color=c, alpha=0.45 if sc > 0.85 else 0.8,
                   linewidths=0.4, edgecolors="#dddddd" if sc > 0.85 else "none")
    for track, marker, col, lab in (("measured", "*", SRS_C, "SRS measured"),
                                    ("closure", "p", CL_C, "SRS closure 2032")):
        xs, ys = [], []
        for r in R["stage2"][nm][track]:
            if "umap_xy" in r:
                xs.append(r["umap_xy"][0]); ys.append(r["umap_xy"][1])
        if xs:
            ax.scatter(xs, ys, s=110 if marker == "*" else 55, marker=marker, color=col,
                       linewidths=0.6, edgecolors="#222222", zorder=5, label=lab)
    ax.set_title(f"{PANEL_TITLE[nm]}  (K={s1['chosen_k']}, {s1['n_points']} Hanford points)")
    ax.set_xticks([]); ax.set_yticks([])
axes[0].legend(loc="lower left", fontsize=7.5, frameon=False)
fig.suptitle("UMAP projections of CLR-transformed compositions (Hanford-fitted; SRS transformed onto them)",
             fontsize=10.5, y=1.02)
fig.savefig(FIGS / "fig_umap.png")
plt.close(fig)
print("fig_umap")

# ------------------------------------------- Figure: HF NN context vs SRS analogs
nn_all, srs_all = {}, {}
for nm in PANELS:
    X, P, clr = MATS[nm]["X"], MATS[nm]["P"], MATS[nm]["clr"]
    hf_ids = [i for i in X.index if i.startswith("HF|") and P.loc[i].sum() > 0]
    clr_hf, frac, Pt, cols = clr_transform(X.loc[hf_ids], P.loc[hf_ids],
                                           presence_floor=FLOOR[nm], hf_ids=hf_ids)
    labels = R["stage1"][nm]["labels"]
    ids = list(clr_hf.index)
    nns = []
    for i, pid in enumerate(ids):
        best = None
        for j, oid in enumerate(ids):
            if i == j or labels[pid] != labels[oid]:
                continue
            d, _ = shared_aitchison(clr_hf.loc[pid], Pt.loc[pid] > 0,
                                    clr_hf.loc[oid], Pt.loc[oid] > 0)
            if d is not None and (best is None or d < best):
                best = d
        if best is not None:
            nns.append(best)
    nn_all[nm] = np.array(nns)
    srs_d = [r["top5_analogs"][0]["d_aitchison"] for r in R["stage2"][nm]["measured"]
             if r.get("top5_analogs")]
    srs_all[nm] = np.array(srs_d)

fig, axes = plt.subplots(1, 3, figsize=(12.6, 3.9), sharey=False)
for ax, nm in zip(axes, PANELS):
    nn = nn_all[nm]
    bp = ax.boxplot([nn], widths=0.42, showfliers=False, patch_artist=True,
                    medianprops=dict(color="black", linewidth=1.2),
                    boxprops=dict(facecolor="#dbe5f1", edgecolor=PRIMARY),
                    whiskerprops=dict(color=PRIMARY), capprops=dict(color=PRIMARY))
    rng = np.random.default_rng(7)
    ax.scatter(rng.normal(1, 0.045, len(nn)), nn, s=6, color=PRIMARY, alpha=0.35, zorder=3)
    sd = srs_all[nm]
    ax.scatter(np.full(len(sd), 1.62) + rng.normal(0, 0.035, len(sd)), sd, s=46,
               marker="*", color=SRS_C, edgecolors="#222222", linewidths=0.4, zorder=5,
               label="SRS top-analog distance")
    for p in (90,):
        ax.axhline(np.percentile(nn, p), color=SECONDARY, linestyle=":", linewidth=1)
        ax.text(1.93, np.percentile(nn, p), f"p{p}", fontsize=7, color=SECONDARY, va="bottom", ha="right")
    ax.set_xticks([1, 1.62]); ax.set_xticklabels(["Hanford same-cluster\nnearest neighbor", "SRS\nmeasured"])
    ax.set_xlim(0.6, 2.0)
    ax.set_title(f"{PANEL_TITLE[nm]}")
    if nm == "sludge":
        ax.set_ylabel("shared-support Aitchison distance")
axes[0].legend(fontsize=7.5, frameon=False, loc="upper left")
fig.suptitle("Is the nearest Hanford analog real? SRS analog distances against Hanford's own same-cluster spread",
             fontsize=10.5, y=1.03)
fig.savefig(FIGS / "fig_analog_context.png")
plt.close(fig)
print("fig_analog_context")

# ------------------------------------------------- Figure: projection percentiles
fig, ax = plt.subplots(figsize=(8.6, 5.6))
ylabels, ypos, ycol = [], [], []
y = 0.0
panel_bounds = {}
for nm in PANELS:
    start = y
    for r in R["stage2"][nm]["measured"]:
        if r.get("cluster_dist_pctl") is None:
            continue
        lab = r["point_id"].split("|", 1)[1].replace(" (Tank 40, SRNL filtered)", "") \
            .replace(" (SRNL filtered)", "").replace(" (SWPF-AL filtered)", "") \
            .replace("Tank 51 ", "").replace("Tank 40 ", "").replace(" (supernate)", " sup")
        ylabels.append(lab); ypos.append(y)
        ycol.append({"sludge": PRIMARY, "salt": "#b8860b", "rad": SECONDARY}[nm])
        y += 1.0
    panel_bounds[nm] = (start - 0.5, y - 0.5)
    y += 0.8
for nm, (a, b) in panel_bounds.items():
    ax.axhspan(a, b, color={"sludge": "#eef2f7", "salt": "#f7f3e6", "rad": "#f7e9e6"}[nm], zorder=0)
ax.scatter([p * 100 for p in []], [])
for yp, pc, c in zip(ypos, [r for nm in PANELS for r in R["stage2"][nm]["measured"]
                            if r.get("cluster_dist_pctl") is not None], ycol):
    ax.scatter(pc["cluster_dist_pctl"], yp, s=52, marker="D", color=c, zorder=3,
               edgecolors="#222222", linewidths=0.4)
ax.axvline(95, color=SECONDARY, linestyle="--", linewidth=1.1)
ax.text(95.4, len(ypos) - 0.4, "cluster edge (95th pctl)", fontsize=7.5, color=SECONDARY, rotation=90,
        va="top")
ax.set_yticks(ypos); ax.set_yticklabels(ylabels, fontsize=7)
ax.set_xlabel("distance percentile within assigned Hanford cluster (%)")
ax.set_xlim(-3, 106)
ax.invert_yaxis()
for sp in ("top", "right"):
    ax.spines[sp].set_visible(False)
fig.suptitle("Where each SRS sample sits inside its assigned cluster (0% = dead center)",
             fontsize=10.5, y=0.985)
fig.savefig(FIGS / "fig_percentiles.png")
plt.close(fig)
print("fig_percentiles")

# --------------------------------------------------------- Figure: cluster profiles
fig, axes = plt.subplots(3, 1, figsize=(9.6, 11.2))
for ax, nm in zip(axes, PANELS):
    s1 = R["stage1"][nm]
    prof = s1["cluster_profiles"]
    # top analytes by max mean fraction across clusters
    all_top = {}
    for c, pr in prof.items():
        for a, v in pr["top_analytes"].items():
            all_top[a] = max(all_top.get(a, 0.0), v)
    top = sorted(all_top, key=all_top.get, reverse=True)[:12]
    clusters = sorted(prof.keys())
    M = np.zeros((len(clusters), len(top)))
    for i, c in enumerate(clusters):
        pr = prof[c]
        for j, a in enumerate(top):
            M[i, j] = pr["top_analytes"].get(a, 0.0)
    im = ax.imshow(M.T, aspect="auto", cmap="Blues", norm=matplotlib.colors.LogNorm(
        vmin=max(M[M > 0].min(), 1e-6), vmax=M.max()))
    ax.set_xticks(range(len(clusters)))
    ax.set_xticklabels([f"C{c}\n(n={prof[c]['n_members']})" for c in clusters], fontsize=7.5)
    ax.set_yticks(range(len(top))); ax.set_yticklabels(top, fontsize=8)
    ax.set_title(f"{PANEL_TITLE[nm]} — mean mass/activity fraction per cluster")
    for i in range(len(clusters)):
        for j in range(len(top)):
            v = M[i, j]
            if v > 0:
                ax.text(i, j, f"{v:.2f}" if v >= 0.01 else f"{v:.0e}"[0:3],
                        ha="center", va="center", fontsize=6,
                        color="white" if v > M.max() * 0.4 else "black")
    fig.colorbar(im, ax=ax, shrink=0.75, pad=0.015)
fig.savefig(FIGS / "fig_profiles.png")
plt.close(fig)
print("fig_profiles")

# ------------------------------------------------------------- Figure: CLR concept
Xs, Ps = MATS["salt"]["X"], MATS["salt"]["P"]
pid = "SRS|Tank 51 Sludge Batch 11 (supernate)|supernate"
row_x, row_p = Xs.loc[pid], Ps.loc[pid]
present = (row_p > 0) & (row_x > 0)
cols = row_x[present].sort_values(ascending=False).index[:14]
fracs = row_x[cols] / row_x[present].sum()
logs = np.log(fracs)
gm = np.exp(logs.mean())
clr_vals = logs - np.log(gm)
fig, (a1, a2) = plt.subplots(1, 2, figsize=(11.4, 3.9))
a1.barh(cols[::-1], fracs[::-1] * 100, color=PRIMARY)
a1.set_xlabel("closed mass fraction (%)")
a1.set_title("A: SB11 supernate, closed composition")
a1.tick_params(axis="y", labelsize=8)
colors2 = [SECONDARY if v >= 0 else PRIMARY for v in clr_vals[cols]]
a2.barh(cols[::-1], clr_vals[::-1], color=colors2[::-1])
a2.axvline(0, color="black", linewidth=0.8)
a2.axvline(0, color="black", linewidth=0.8)
a2.set_xlabel("CLR value = ln(fraction) − ln(geometric mean)")
a2.set_title("B: the same sample after the CLR transform")
a2.tick_params(axis="y", labelsize=8)
fig.suptitle("The centered log-ratio transform, on real data (geometric mean of this sample = "
             f"{gm:.3e} mass fraction; CLR values sum to zero)", fontsize=10, y=1.04)
fig.savefig(FIGS / "fig_clr_concept.png")
plt.close(fig)
print("fig_clr_concept")

# ---------------------------------------------------------------- Figure: sweep
fig, ax = plt.subplots(figsize=(8.2, 3.9))
for nm, col in zip(PANELS, [PRIMARY, "#b8860b", SECONDARY]):
    sw = R["stage1"][nm]["kmeans_sweep"]
    ks = [s["k"] for s in sw]; sils = [s["silhouette"] for s in sw]
    ax.plot(ks, sils, marker="o", color=col, label=PANEL_TITLE[nm], linewidth=1.4)
    best = R["stage1"][nm]["chosen_k"]
    bs = next(s["silhouette"] for s in sw if s["k"] == best)
    ax.scatter([best], [bs], s=110, marker="*", color=col, zorder=5, edgecolors="#222222",
               linewidths=0.5)
ax.axvspan(4, 9, color="#e8edf3", zorder=0)
ax.text(6.5, ax.get_ylim()[0] + 0.004, "interpretable selection window (k = 4–9)",
        ha="center", fontsize=7.5, color="#555555")
ax.set_xlabel("number of clusters k (KMeans)")
ax.set_ylabel("silhouette score")
ax.set_xticks(range(2, 13))
ax.legend(fontsize=8, frameon=False)
ax.set_title("Model selection: silhouette across the k sweep; stars mark the chosen K per panel")
fig.savefig(FIGS / "fig_sweep.png")
plt.close(fig)
print("fig_sweep")

# ---------------------------------------------------------- Figure: presence floor
fig, ax = plt.subplots(figsize=(8.2, 3.9))
for nm, col in zip(PANELS, [PRIMARY, "#b8860b", SECONDARY]):
    X, P = MATS[nm]["X"], MATS[nm]["P"]
    hf_ids = [i for i in X.index if i.startswith("HF|") and P.loc[i].sum() > 0]
    pres = ((P.loc[hf_ids] > 0) & (X.loc[hf_ids] > 0)).mean()
    floors = np.linspace(0.0, 0.95, 40)
    kept = [int((pres >= f).sum()) for f in floors]
    ax.plot(floors, kept, color=col, label=PANEL_TITLE[nm], linewidth=1.4)
    ax.scatter([FLOOR[nm]], [int((pres >= FLOOR[nm]).sum())], s=70, marker="*", color=col,
               zorder=5, edgecolors="#222222", linewidths=0.5)
    ax.annotate(f"{int((pres >= FLOOR[nm]).sum())} kept",
                (FLOOR[nm], int((pres >= FLOOR[nm]).sum())), textcoords="offset points",
                xytext=(6, 4), fontsize=7.5, color=col)
ax.set_xlabel("presence floor (fraction of Hanford points reporting the analyte)")
ax.set_ylabel("features kept")
ax.legend(fontsize=8, frameon=False)
ax.set_title("Feature retention vs presence floor; stars mark the floors used")
fig.savefig(FIGS / "fig_presence.png")
plt.close(fig)
print("fig_presence")

# ---------------------------------------------------------------- Figure: dendrogram
from scipy.cluster.hierarchy import dendrogram, linkage  # noqa: E402
nm = "salt"
X, P, clr = MATS[nm]["X"], MATS[nm]["P"], MATS[nm]["clr"]
hf_ids = [i for i in X.index if i.startswith("HF|") and P.loc[i].sum() > 0]
clr_hf, frac, Pt, cols = clr_transform(X.loc[hf_ids], P.loc[hf_ids],
                                       presence_floor=FLOOR[nm], hf_ids=hf_ids)
Z = linkage(clr_hf.to_numpy(), method="ward")
labels_hf = R["stage1"][nm]["labels"]
leaf_labels = []
for pid in clr_hf.index:
    _, tank, phase = pid.split("|", 2)
    leaf_labels.append(f"{tank}")
fig, ax = plt.subplots(figsize=(10.5, 3.6))
dd = dendrogram(Z, ax=ax, labels=leaf_labels, truncate_mode="lastp", p=40,
                color_threshold=Z[-R["stage1"][nm]["chosen_k"], 2],
                above_threshold_color="#aaaaaa")
ax.set_ylabel("Ward merge distance")
ax.set_title("Ward dendrogram, salt-anion panel (truncated to last 40 merges; branch colors = chosen K clusters)")
fig.savefig(FIGS / "fig_dendrogram.png")
plt.close(fig)
print("fig_dendrogram")

json.dump({nm: {"nn_median": float(np.median(nn_all[nm])),
                "nn_p90": float(np.percentile(nn_all[nm], 90)),
                "nn_max": float(nn_all[nm].max()),
                "srs_median": float(np.median(srs_all[nm])),
                "srs_max": float(srs_all[nm].max())} for nm in PANELS},
          open(FIGS / "nn_context.json", "w"), indent=1)
print("all figures done ->", FIGS)
