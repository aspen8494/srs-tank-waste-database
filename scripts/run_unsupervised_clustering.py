#!/usr/bin/env python3
"""Two-stage cross-site unsupervised learning on tank waste compositions.

Stage 1 (Hanford): cluster Hanford BBI tank x phase points in each panel
  (sludge-elements, salt-anion, radionuclides) using Aitchison geometry:
  mass-fraction closure -> CLR with neutral replacement for absent analytes
  (replaced at the point's geometric mean -> CLR coordinate 0, no distance pull).
  Methods: KMeans k-sweep, Ward, HDBSCAN (noise = anomaly candidates),
  UMAP for 2D. External validation: cross-tab vs BBI waste_type + phase.

Stage 2 (SRS): project SRNL measured samples + closure-residual vectors into
  the Hanford taxonomy: nearest centroid + top-5 k-NN analogs with
  shared-support Aitchison distance (only analytes present in BOTH points).

Outputs (data_processed/unsupervised/):
  clustering_results.json   metrics, cluster assignments, projections
  X_sludge_clr.csv etc.      CLR-transformed matrices used
  panel_defs.json            trimmed panels + presence stats
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import dendrogram, fcluster, linkage
from scipy.spatial.distance import pdist
from sklearn.cluster import KMeans
from sklearn.metrics import calinski_harabasz_score, davies_bouldin_score, silhouette_score
from sklearn.preprocessing import StandardScaler
import hdbscan
import umap

BASE = Path("/Users/aspen_mb/Documents/Savannah_RiverTF")
IN = BASE / "data_processed" / "unsupervised"
RNG = 42
np.random.seed(RNG)

results = {"panels": {}, "stage1": {}, "stage2": {}, "anomalies": {}, "umap": {}}
panel_defs = {}

# ------------------------------------------------------------------- utils ----
def clr_transform(X, P, presence_floor=0.70, hf_ids=None, keep_cols=None):
    """Trim columns by HF presence floor, then CLR with neutral replacement.

    Returns (Xclr DataFrame, Xfrac mass-fraction frame, P presence, kept_cols).
    Absent analyte -> geometric mean of the point's present values -> CLR == 0.
    Guard: presence requires both P==1 and X>0 (guards X=0/P=1 artifacts).
    """
    hf = X.loc[[i for i in X.index if i in (hf_ids or set())]] if hf_ids is not None else X
    pres_hf = ((P.loc[hf.index] > 0) & (X.loc[hf.index] > 0)).mean()
    cols = [c for c in X.columns if pres_hf[c] >= presence_floor]
    Xt, Pt = X[cols], P[cols]
    Pt = ((Pt > 0) & (Xt > 0)).astype(np.int8)  # re-derive presence on trimmed cols
    # mass-fraction closure over present analytes
    sums = Xt.where(Pt > 0, 0.0).sum(axis=1)
    frac = Xt.where(Pt > 0, 0.0).div(sums.replace(0, np.nan), axis=0).fillna(0.0)
    with np.errstate(divide="ignore", invalid="ignore"):
        logs = np.log(frac.where(Pt > 0).replace(0, np.nan))
        gmean = np.exp(logs.mean(axis=1, skipna=True))  # per-point geometric mean
        clr = pd.DataFrame(0.0, index=Xt.index, columns=cols)
        vals = (logs.sub(np.log(gmean), axis=0)).where(Pt > 0, 0.0).fillna(0.0)
    clr.loc[:, :] = vals.to_numpy()
    return clr, frac, Pt, cols

def shared_aitchison_dist(xa, pa, xb, pb):
    """sqrt(sum((clr_a - clr_b - mean(clr_a - clr_b))^2)) over shared support."""
    m = (pa > 0) & (pb > 0)
    k = int(m.sum())
    if k < 2:
        return np.inf, k
    d = xa[m].to_numpy() - xb[m].to_numpy()
    d = d - d.mean()
    return float(np.sqrt((d ** 2).sum())), k

# ============================================================== load panels ====
def load(name):
    X = pd.read_csv(IN / f"X_{name}.csv", index_col=0)
    P = pd.read_csv(IN / f"presence_{name}.csv", index_col=0)
    meta = pd.read_csv(IN / f"meta_{name}.csv").set_index("point_id")
    return X, P, meta

PANELS = {}
for nm in ("sludge", "salt", "rad"):
    X, P, meta = load(nm)
    hf_ids = [i for i in X.index if i.startswith("HF|")]
    srs_ids = [i for i in X.index if i.startswith("SRS|")]
    cl_ids = [i for i in X.index if i.startswith("SRSCLOSE|")]
    PANELS[nm] = dict(X=X, P=P, meta=meta, hf=hf_ids, srs=srs_ids, cl=cl_ids)
    PANELS[nm]["hf_with_data"] = [i for i in hf_ids if P.loc[i].sum() > 0]

# ============================================================ stage 1 ===========
K_RANGE = range(2, 13)

def stage1(nm, floor):
    d = PANELS[nm]
    X, P, meta = d["X"], d["P"], d["meta"]
    hf_pts = d["hf_with_data"]
    clr, frac, Pt, cols = clr_transform(X.loc[hf_pts], P.loc[hf_pts],
                                        presence_floor=floor, hf_ids=hf_pts)
    M = clr.to_numpy()
    res = {"n_points": len(hf_pts), "n_features": len(cols), "kept_cols": cols,
           "dropped_cols": [c for c in X.columns if c not in cols]}

    # --- KMeans k-sweep
    sweep = []
    for k in K_RANGE:
        km = KMeans(n_clusters=k, n_init=25, random_state=RNG).fit(M)
        lab = km.labels_
        sweep.append({
            "k": k,
            "silhouette": round(float(silhouette_score(M, lab)), 4),
            "calinski_harabasz": round(float(calinski_harabasz_score(M, lab)), 1),
            "davies_bouldin": round(float(davies_bouldin_score(M, lab)), 4),
            "inertia": round(float(km.inertia_), 1)})
    res["kmeans_sweep"] = sweep

    # --- choose K: max silhouette in 4..9 (interpretable range), tie -> higher CH
    cand = [s for s in sweep if 4 <= s["k"] <= 9]
    best = sorted(cand, key=lambda s: (s["silhouette"], s["calinski_harabasz"]))[-1]
    res["chosen_k"] = best["k"]
    res["chosen_k_reason"] = ("max silhouette in interpretable range 4-9 "
                              f"(silhouette={best['silhouette']})")

    km = KMeans(n_clusters=best["k"], n_init=50, random_state=RNG).fit(M)
    kmeans_labels = km.labels_

    # --- Ward linkage
    Z = linkage(M, method="ward")
    ward_labels = fcluster(Z, t=best["k"], criterion="maxclust") - 1
    # cophenetic correlation for fit quality
    from scipy.cluster.hierarchy import cophenet
    cop, _cd = cophenet(Z, pdist(M))
    res["ward_cophenetic"] = round(cop, 4)
    res["ward_silhouette_at_k"] = round(float(silhouette_score(M, ward_labels)), 4)
    res["ward_ari_vs_kmeans"] = None  # filled below with adjusted_rand_score
    from sklearn.metrics import adjusted_rand_score
    res["ward_ari_vs_kmeans"] = round(float(adjusted_rand_score(kmeans_labels, ward_labels)), 3)

    # --- dendrogram JSON (truncated to 60 leaves merged, full structure for viz)
    dd = dendrogram(Z, no_plot=True, labels=list(clr.index), truncate_mode=None)
    res["dendrogram"] = {
        "icoord": [[float(v) for v in row] for row in dd["icoord"]],
        "dcoord": [[float(v) for v in row] for row in dd["dcoord"]],
        "ivl": dd["ivl"], "leaves": [int(v) for v in dd["leaves"]]}

    # --- HDBSCAN (data must be a writable copy: numpy 2.5 read-only views break
    #     hdbscan's Cython boruvka kernel). min_samples=1 -> pure density-based
    #     anomaly flagging without over-aggressive noise.
    hdb = hdbscan.HDBSCAN(min_cluster_size=max(6, len(hf_pts) // 25),
                          min_samples=1).fit(M.copy(order="C"))
    hdb_labels = hdb.labels_
    n_noise = int((hdb_labels == -1).sum())
    res["hdbscan"] = {
        "n_clusters": int(hdb_labels.max() + 1),
        "n_noise": n_noise,
        "noise_points": [clr.index[i] for i in np.where(hdb_labels == -1)[0]],
        "ari_vs_kmeans": round(float(adjusted_rand_score(kmeans_labels, hdb_labels)), 3)}

    # --- final taxonomy: Ward at chosen K (robust to neutral-replacement geometry)
    labels = ward_labels
    res["method_final"] = "ward"
    res["labels"] = {pid: int(l) for pid, l in zip(clr.index, labels)}
    res["umap_params"] = {"n_neighbors": 15, "min_dist": 0.1, "metric": "euclidean",
                          "random_state": RNG}

    # --- external validation: clusters x waste_type, clusters x phase
    wt = meta.loc[clr.index, "waste_type"].fillna("NA") if "waste_type" in meta else pd.Series("NA", index=clr.index)
    ph = meta.loc[clr.index, "phase"]
    def crosstab(series):
        ct = pd.crosstab(pd.Series(labels, index=clr.index, name="cluster"), series)
        return {str(c): {str(r): int(ct.loc[c, r]) for r in ct.columns if ct.loc[c, r] > 0}
                for c in ct.index}
    res["cluster_x_wastetype"] = crosstab(wt)
    res["cluster_x_phase"] = crosstab(ph)

    # --- cluster profiles (mean mass fraction over present members) + enrichment
    prof = {}
    for c in sorted(set(labels)):
        members = clr.index[labels == c]
        f = frac.loc[members]
        pr = Pt.loc[members]
        mean_frac = f.where(pr > 0).mean().fillna(0.0)
        present_rate = pr.mean()
        top = mean_frac.sort_values(ascending=False).head(8)
        prof[int(c)] = {
            "n_members": len(members),
            "mean_presence": round(float(present_rate.mean()), 3),
            "top_analytes": {a: round(float(v), 5) for a, v in top.items()},
            "presence": {a: round(float(v), 2) for a, v in present_rate.items()}}
    res["cluster_profiles"] = prof

    # --- UMAP (fit on Hanford, transform others later)
    reducer = umap.UMAP(n_neighbors=15, min_dist=0.1, n_components=2,
                        random_state=RNG, n_jobs=1)
    emb = reducer.fit_transform(M)
    res["umap_hf"] = {clr.index[i]: [round(float(emb[i, 0]), 4), round(float(emb[i, 1]), 4)]
                      for i in range(len(clr.index))}

    # truncated dendrogram for viz: keep the last 24 merges only
    dd = dendrogram(Z, no_plot=True, truncate_mode="lastp", p=24)
    res["dendrogram_trunc"] = {
        "icoord": [[float(v) for v in row] for row in dd["icoord"]],
        "dcoord": [[float(v) for v in row] for row in dd["dcoord"]],
        "ivl": [str(v) for v in dd["ivl"]]}

    # HDBSCAN continuous outlier scores (0..1; higher = more anomalous)
    res["hdbscan"]["outlier_scores"] = {clr.index[i]: round(float(hdb.outlier_scores_[i]), 4)
                                        for i in range(len(clr.index))}

    return res, clr, frac, Pt, cols, labels, reducer, km

print("=== STAGE 1: Hanford taxonomy per panel ===")
for nm, floor in (("sludge", 0.40), ("salt", 0.70), ("rad", 0.50)):
    print(f"--- panel: {nm} (presence floor {floor}) ---")
    res, clr, frac, Pt, cols, labels, reducer, km = stage1(nm, floor)
    d = PANELS[nm]
    d.update(clr=clr, frac=frac, Pt=Pt, cols=cols, labels=labels,
             reducer=reducer, km=km)
    results["stage1"][nm] = {k: v for k, v in res.items() if k != "dendrogram"}
    results["stage1"][nm]["n_points"] = res["n_points"]
    panel_defs[nm] = {"kept": cols, "dropped": res["dropped_cols"],
                      "presence_floor": floor, "n_points": res["n_points"]}
    print(f"  points={res['n_points']} features={res['n_features']} chosen_k={res['chosen_k']} "
          f"ward_sil={res['ward_silhouette_at_k']} ari_vs_kmeans={res['ward_ari_vs_kmeans']} "
          f"hdbscan_k={res['hdbscan']['n_clusters']} noise={res['hdbscan']['n_noise']}")

# ============================================================ stage 2 ===========
print("\n=== STAGE 2: SRS projection ===")

def stage2(nm):
    d = PANELS[nm]
    clr_hf, labels_hf, cols, meta = d["clr"], d["labels"], d["cols"], d["meta"]
    X, P = d["X"], d["P"]
    reducer = d["reducer"]
    out = {"measured": [], "closure": []}
    centroids = {}
    for c in sorted(set(labels_hf)):
        members = clr_hf.index[labels_hf == c]
        centroids[c] = clr_hf.loc[members].mean(axis=0)

    # CLR for SRS + closure points on the same trimmed columns (per-point closure)
    def clr_point(pid):
        row_x, row_p = X.loc[pid, cols], P.loc[pid, cols]
        present = (row_p > 0) & (row_x > 0)  # guard X=0/P=1 artifacts
        if present.sum() < 2:
            return None, present
        frac = row_x[present] / row_x[present].sum()
        gm = np.exp(np.log(frac).mean())
        clr = pd.Series(0.0, index=cols)
        clr[present] = np.log(frac) - np.log(gm)
        return clr, present

    for pid in d["srs"] + d["cl"]:
        track = "measured" if pid in d["srs"] else "closure"
        clr_i, present = clr_point(pid)
        rec = {"point_id": pid, "basis": "SRNL_measured" if track == "measured"
               else "closure_residual_2032"}
        if clr_i is None:
            rec["status"] = "insufficient_data"
            out[track].append(rec)
            continue
        # nearest centroid (Euclidean on CLR)
        dists = {c: float(np.linalg.norm(clr_i - centroids[c])) for c in centroids}
        best_c = min(dists, key=dists.get)
        rec["nearest_cluster"] = int(best_c)
        rec["centroid_dist"] = round(dists[best_c], 4)
        rec["all_centroid_dists"] = {str(c): round(v, 4) for c, v in dists.items()}

        # projection quality: where does this distance sit within the target
        # cluster's own HF member-to-centroid distance distribution?
        members = clr_hf.index[labels_hf == best_c]
        mem_d = [float(np.linalg.norm(clr_hf.loc[m] - centroids[best_c])) for m in members]
        rec["cluster_dist_pctl"] = round(float(100 * np.mean(
            np.asarray(mem_d) < dists[best_c])), 1)
        rec["cluster_dist_p95"] = round(float(np.percentile(mem_d, 95)), 4)

        # top-5 shared-support Aitchison analogs among Hanford points
        analogs = []
        for hf_pid in clr_hf.index:
            dist, k_shared = shared_aitchison_dist(
                clr_i, present, clr_hf.loc[hf_pid], d["Pt"].loc[hf_pid, cols])
            if np.isfinite(dist):
                m = d["meta"].loc[hf_pid]
                analogs.append({"id": hf_pid, "tank": m["tank"], "phase": m["phase"],
                                "waste_type": str(m.get("waste_type", "NA")),
                                "d_aitchison": round(dist, 4),
                                "n_shared": k_shared,
                                "cluster": int(labels_hf[clr_hf.index.get_loc(hf_pid)])})
        analogs.sort(key=lambda a: a["d_aitchison"])
        rec["top5_analogs"] = analogs[:5]
        rec["mean_shared"] = round(float(np.mean([a["n_shared"] for a in analogs[:5]])), 1) \
            if analogs else 0

        # driving analytes: |clr_i - centroid| on the point's present analytes
        diff = (clr_i - centroids[best_c]).abs()
        diff = diff[present]
        rec["driving_analytes"] = {a: round(float(diff[a]), 3)
                                  for a in diff.sort_values(ascending=False).head(6).index}

        # UMAP projection onto the Hanford-fitted embedding
        try:
            xy = reducer.transform(clr_i.to_numpy().reshape(1, -1))
            rec["umap_xy"] = [round(float(xy[0, 0]), 4), round(float(xy[0, 1]), 4)]
        except Exception as e:
            rec["umap_error"] = str(e)
        out[track].append(rec)
    return out

for nm in ("sludge", "salt", "rad"):
    proj = stage2(nm)
    results["stage2"][nm] = proj
    nm_meas = proj["measured"]
    ok = [r for r in nm_meas if r.get("nearest_cluster") is not None]
    print(f"--- {nm}: {len(ok)}/{len(nm_meas)} measured samples projected")
    for r in nm_meas:
        if r.get("nearest_cluster") is not None:
            print(f"    {r['point_id'][:52]:<52} -> cluster {r['nearest_cluster']} "
                  f"(d={r['centroid_dist']}) top analog: "
                  f"{r['top5_analogs'][0]['tank']} {r['top5_analogs'][0]['phase'][:20]}"
                  if r["top5_analogs"] else "")

# anomalies: HDBSCAN noise per panel
for nm in ("sludge", "salt", "rad"):
    results["anomalies"][nm] = results["stage1"][nm]["hdbscan"]["noise_points"]

# persist
with open(IN / "clustering_results.json", "w") as f:
    json.dump(results, f, indent=1, default=str)
with open(IN / "panel_defs.json", "w") as f:
    json.dump(panel_defs, f, indent=2)
for nm in ("sludge", "salt", "rad"):
    PANELS[nm]["clr"].round(5).to_csv(IN / f"X_{nm}_clr.csv")
print(f"\nDone. Results -> {IN / 'clustering_results.json'}")
