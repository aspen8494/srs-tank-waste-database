#!/usr/bin/env python3
"""Re-verify every headline number for the unsupervised-learning manuscript, live.

Prints a verification ledger: value + source query/computation. The manuscript
content modules import from verify_outputs.json produced here.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path("/Users/aspen_mb/Documents/Savannah_RiverTF")
IN = BASE / "data_processed" / "unsupervised"
sys.path.insert(0, str(BASE / "scripts"))
from run_unsupervised_clustering import clr_transform  # noqa: E402

R = json.load(open(IN / "clustering_results.json"))
PD = json.load(open(IN / "panel_defs.json"))
BR = json.load(open(IN / "build_report.json"))
V = {}  # verification ledger

FLOOR = {"sludge": 0.40, "salt": 0.70, "rad": 0.50}

def shared_aitchison(clr_a, pres_a, clr_b, pres_b):
    m = (pres_a > 0) & (pres_b > 0)
    k = int(m.sum())
    if k < 2:
        return None, k
    d = clr_a[m].to_numpy(dtype=float) - clr_b[m].to_numpy(dtype=float)
    d = d - d.mean()
    return float(np.sqrt((d ** 2).sum())), k

# 1. dataset counts ----------------------------------------------------------
V["counts"] = BR["counts"]
V["dl2"] = BR["srs_dl_halved"]
V["hf_subdl"] = BR["hf_below_detection_rows"]
V["layer_dedup"] = BR["layer_sum_dedup"]

# 2. per-panel quality + coverage -------------------------------------------
V["panels"] = {}
for nm in ("sludge", "salt", "rad"):
    s1 = R["stage1"][nm]
    V["panels"][nm] = {
        "n_points": s1["n_points"], "n_features": len(PD[nm]["kept"]),
        "n_dropped": len(PD[nm]["dropped"]), "floor": FLOOR[nm],
        "k": s1["chosen_k"], "sil": s1["ward_silhouette_at_k"],
        "ari": s1["ward_ari_vs_kmeans"], "coph": s1["ward_cophenetic"],
        "hdb_k": s1["hdbscan"]["n_clusters"], "hdb_noise": s1["hdbscan"]["n_noise"],
        "coverage_hf": BR[f"{nm}_coverage"]["hf_mean_frac_analytes"],
        "coverage_srs": BR[f"{nm}_coverage"]["srs_mean_frac_analytes"],
    }
    sweep_best = max((s for s in s1["kmeans_sweep"] if 4 <= s["k"] <= 9),
                     key=lambda s: (s["silhouette"], s["calinski_harabasz"]))
    V["panels"][nm]["sweep_best_k"] = sweep_best["k"]
    V["panels"][nm]["sweep_best_sil"] = sweep_best["silhouette"]

# 3. SRS measured projections (all panels) -----------------------------------
V["projections"] = {}
for nm in ("sludge", "salt", "rad"):
    rows = []
    for r in R["stage2"][nm]["measured"]:
        if r.get("nearest_cluster") is None:
            continue
        a0 = r["top5_analogs"][0] if r["top5_analogs"] else {}
        rows.append({
            "point": r["point_id"].split("|", 1)[1], "cluster": r["nearest_cluster"],
            "dist": r["centroid_dist"], "pctl": r["cluster_dist_pctl"],
            "p95": r["cluster_dist_p95"],
            "analog": f"{a0.get('tank','')} {a0.get('phase','')}",
            "an_wt": a0.get("waste_type", ""), "an_d": a0.get("d_aitchison"),
            "k": a0.get("n_shared"),
        })
    V["projections"][nm] = rows

# 4. HF same-cluster nearest-neighbor context (recomputed live) --------------
V["nn_context"] = {}
for nm in ("sludge", "salt", "rad"):
    X = pd.read_csv(IN / f"X_{nm}.csv", index_col=0)
    P = pd.read_csv(IN / f"presence_{nm}.csv", index_col=0)
    hf_ids = [i for i in X.index if i.startswith("HF|") and P.loc[i].sum() > 0]
    clr, frac, Pt, cols = clr_transform(X.loc[hf_ids], P.loc[hf_ids],
                                        presence_floor=FLOOR[nm], hf_ids=hf_ids)
    labels = R["stage1"][nm]["labels"]
    ids = list(clr.index)
    nns = []
    for i, pid in enumerate(ids):
        best = None
        for j, oid in enumerate(ids):
            if i == j or labels[pid] != labels[oid]:
                continue
            d, _ = shared_aitchison(clr.loc[pid], Pt.loc[pid] > 0,
                                    clr.loc[oid], Pt.loc[oid] > 0)
            if d is not None and (best is None or d < best):
                best = d
        if best is not None:
            nns.append(best)
    nns = np.array(nns)
    V["nn_context"][nm] = {"median": round(float(np.median(nns)), 2),
                           "p90": round(float(np.percentile(nns, 90)), 2),
                           "max": round(float(nns.max()), 2), "n": int(len(nns))}

# 5. anomalies ---------------------------------------------------------------
V["anoms"] = {}
for nm in ("sludge", "salt", "rad"):
    scores = R["stage1"][nm]["hdbscan"]["outlier_scores"]
    V["anoms"][nm] = {"n85": sum(1 for v in scores.values() if v > 0.85),
                      "n90": sum(1 for v in scores.values() if v > 0.90)}
    top5 = sorted(scores.items(), key=lambda kv: -kv[1])[:5]
    V["anoms"][nm]["top5"] = [
        {"pid": p, "score": s,
         "tank": p.split("|")[1], "phase": p.split("|", 2)[2],
         "cluster": R["stage1"][nm]["labels"][p]} for p, s in top5]

# 6. key cross-site claims ---------------------------------------------------
def get_proj(nm, frag):
    for r in V["projections"][nm]:
        if frag in r["point"]:
            return r
    return None

V["claims"] = {
    "salt8_rad": get_proj("rad", "Salt Batch 8"),
    "salt13_rad": get_proj("rad", "Salt Batch 13"),
    "salt8_salt": get_proj("salt", "Salt Batch 8"),
    "sb11_sludge": get_proj("sludge", "Batch 11|slurry"),
    "prft15_sludge": get_proj("sludge", "PRFT Batch 15"),
}
# PRFT Ti values (from X_sludge.csv, live read)
Xs = pd.read_csv(IN / "X_sludge.csv", index_col=0)
V["claims"]["prft_Ti"] = {
    p.split("|")[1]: float(Xs.loc[p, "Ti"])
    for p in Xs.index if "PRFT" in p and "slurry" in p}
# SB10 rad-only evidence
V["claims"]["sb10_chem_cols"] = int((Xs.loc["SRS|Tank 40 Sludge Batch 10|slurry"] > 0).sum())

json.dump(V, open(BASE / "paper" / "unsup" / "verify_outputs.json", "w"), indent=1)

# ---- print ledger
print("=== VERIFICATION LEDGER ===")
print(f"counts: {V['counts']}")
print(f"dl2={V['dl2']} hf_subdl={V['hf_subdl']} layer_dedup={V['layer_dedup']}")
for nm in ("sludge", "salt", "rad"):
    p = V["panels"][nm]
    print(f"{nm}: n={p['n_points']} feat={p['n_features']}(+{p['n_dropped']} dropped) "
          f"k={p['k']} sil={p['sil']} ari={p['ari']} coph={p['coph']} "
          f"hdb={p['hdb_k']}/{p['hdb_noise']} covHF={p['coverage_hf']} covSRS={p['coverage_srs']} "
          f"sweep_best={p['sweep_best_k']}@{p['sweep_best_sil']}")
print("NN context:", json.dumps(V["nn_context"]))
print("anoms:", json.dumps({k: {kk: vv for kk, vv in v.items() if kk != 'top5'}
                            for k, v in V["anoms"].items()}))
print("claims:")
for k, v in V["claims"].items():
    print(f"  {k}: {json.dumps(v) if not isinstance(v, dict) or 'an_d' not in str(v) else ''}")
print("\nprojections (rad):")
for r in V["projections"]["rad"]:
    print(f"  {r['point'][:44]:<44} C{r['cluster']} d={r['dist']} pctl={r['pctl']} "
          f"top={r['analog']} d={r['an_d']} k={r['k']}")
print("projections (salt):")
for r in V["projections"]["salt"]:
    print(f"  {r['point'][:44]:<44} C{r['cluster']} d={r['dist']} pctl={r['pctl']} "
          f"top={r['analog']} d={r['an_d']} k={r['k']}")
print("projections (sludge):")
for r in V["projections"]["sludge"]:
    print(f"  {r['point'][:44]:<44} C{r['cluster']} d={r['dist']} pctl={r['pctl']} "
          f"top={r['analog']} d={r['an_d']} k={r['k']}")
