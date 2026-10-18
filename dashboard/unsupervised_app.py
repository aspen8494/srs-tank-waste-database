#!/usr/bin/env python3
"""Unsupervised Cross-Site Waste Taxonomy — Streamlit explorer.

Explores the dataspace and results of the two-stage Hanford/SRS unsupervised
analysis (scripts/build_unsupervised_features.py + run_unsupervised_clustering.py).

Run:  .venv/bin/streamlit run dashboard/unsupervised_app.py --server.port 8643
Data: data_processed/unsupervised/{clustering_results,panel_defs,build_report}.json
      + X_*.csv / presence_*.csv / meta_*.csv
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE = Path("/Users/aspen_mb/Documents/Savannah_RiverTF")
UNSUP = BASE / "data_processed" / "unsupervised"

PANELS = ["sludge", "salt", "rad"]
PANEL_LABEL = {"sludge": "Sludge elements", "salt": "Salt anions/cations", "rad": "Radionuclides"}
PANEL_DESC = {
    "sludge": "Element chemistry of sludge/solid phases — mass-fraction CLR",
    "salt": "Anion/cation chemistry of supernate & saltcake — mass-fraction CLR",
    "rad": "Activity signature, decay-corrected to 2025-10-01 — activity-fraction CLR",
}
CLUSTER_COLORS = ["#58a6ff", "#f0883e", "#3fb950", "#d2a8ff", "#ffa657",
                  "#79c0ff", "#7ee787", "#ff7b72", "#56d4dd", "#e3b341"]
SRS_COLOR = "#f0883e"
CL_COLOR = "#d2a8ff"

st.set_page_config(page_title="Unsupervised Waste Taxonomy", page_icon="🧭", layout="wide",
                   initial_sidebar_state="expanded")


# ---------------------------------------------------------------- data layer
@st.cache_data(ttl=3600)
def load_results():
    return json.load(open(UNSUP / "clustering_results.json"))


@st.cache_data(ttl=3600)
def load_panel_defs():
    return json.load(open(UNSUP / "panel_defs.json"))


@st.cache_data(ttl=3600)
def load_build_report():
    return json.load(open(UNSUP / "build_report.json"))


@st.cache_data(ttl=3600)
def load_matrices(name):
    X = pd.read_csv(UNSUP / f"X_{name}.csv", index_col=0)
    P = pd.read_csv(UNSUP / f"presence_{name}.csv", index_col=0)
    meta = pd.read_csv(UNSUP / f"meta_{name}.csv").set_index("point_id")
    clr = pd.read_csv(UNSUP / f"X_{name}_clr.csv", index_col=0)
    return X, P, meta, clr


@st.cache_data(ttl=3600)
def scatter_frame(name):
    """One DataFrame per panel: Hanford + projected SRS/closure points with UMAP coords."""
    R = load_results()
    s1 = R["stage1"][name]
    rows = []
    for pid, xy in s1["umap_hf"].items():
        _, tank, phase = pid.split("|", 2)
        rows.append({
            "point_id": pid, "tank": tank, "phase": phase, "site": "Hanford",
            "kind": "Hanford BBI (current)",
            "x": xy[0], "y": xy[1], "cluster": s1["labels"][pid],
            "outlier": s1["hdbscan"]["outlier_scores"].get(pid, 0.0),
        })
    for track, kind in (("measured", "SRS measured"), ("closure", "SRS closure 2032")):
        for r in R["stage2"][name][track]:
            if "umap_xy" not in r:
                continue
            label = r["point_id"].split("|", 1)[1]
            rows.append({
                "point_id": r["point_id"],
                "tank": label.split("|")[0],
                "phase": label.split("|", 1)[1] if "|" in label else "",
                "site": "SRS", "kind": kind,
                "x": r["umap_xy"][0], "y": r["umap_xy"][1],
                "cluster": r.get("nearest_cluster"),
                "outlier": None, "pctl": r.get("cluster_dist_pctl"),
            })
    df = pd.DataFrame(rows)
    df["cluster_str"] = df["cluster"].apply(lambda c: f"C{c}" if c is not None and c == c else "—")
    return df


def shared_aitchison(clr_a, pres_a, clr_b, pres_b):
    """Aitchison distance over the shared support + support size."""
    m = (pres_a > 0) & (pres_b > 0)
    k = int(m.sum())
    if k < 2:
        return None, k
    d = clr_a[m].to_numpy(dtype=float) - clr_b[m].to_numpy(dtype=float)
    d = d - d.mean()
    return float(np.sqrt((d ** 2).sum())), k


R = load_results()
PD = load_panel_defs()
BR = load_build_report()

# ------------------------------------------------------------------ sidebar
st.sidebar.title("🧭 Waste Taxonomy Explorer")
panel = st.sidebar.radio("Feature space", PANELS, format_func=lambda p: PANEL_LABEL[p],
                         key="panel", help="Three closed analyte panels; see Methods.")
st.sidebar.caption(PANEL_DESC[panel])
kept = PD[panel]["kept"]
st.sidebar.caption(f"{PD[panel]['n_points']} Hanford points · {len(kept)} features · "
                   f"{len(PD[panel]['dropped'])} dropped by presence floor")
st.sidebar.divider()
st.sidebar.caption("Two-stage unsupervised learning:\n\n"
                   "**1.** Hanford BBI tank×phase compositions → Ward clusters on CLR space\n\n"
                   "**2.** SRS samples & closure vectors projected: nearest centroid + "
                   "shared-support Aitchison analogs\n\n"
                   "Missing analyte = neutral (CLR 0), never zero. Basis tracks never mixed.")

s1 = R["stage1"][panel]

# ------------------------------------------------------------------- tabs
tab_over, tab_tax, tab_proj, tab_anom, tab_data, tab_meth = st.tabs(
    ["Overview", "Taxonomy explorer", "SRS projections", "Anomalies", "Dataspace", "Methods"])

# ================================================================== OVERVIEW
with tab_over:
    c = BR["counts"]
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Hanford points (current BBI)", c["hf_points"],
              f"{c['hf_sludge']} sludge · {c['hf_salt']} salt/supernate")
    m2.metric("SRS measured samples", c["srs_samples"], "SRNL reports 2023–2025")
    m3.metric("SRS closure vectors", c["srs_closure"], "flagged 2032 basis — separate track")
    m4.metric("Feature spaces", 3, "elements · anions · nuclides")

    st.subheader("Clustering quality per feature space")
    qual_rows = []
    for nm in PANELS:
        q = R["stage1"][nm]
        qual_rows.append({
            "Panel": PANEL_LABEL[nm], "Hanford points": q["n_points"],
            "Features": len(PD[nm]["kept"]), "K (Ward)": q["chosen_k"],
            "Silhouette": q["ward_silhouette_at_k"], "ARI vs KMeans": q["ward_ari_vs_kmeans"],
            "Cophenetic": q["ward_cophenetic"],
            "HDBSCAN k": q["hdbscan"]["n_clusters"], "Noise": q["hdbscan"]["n_noise"],
        })
    st.dataframe(pd.DataFrame(qual_rows).set_index("Panel"), width="stretch")

    st.info(
        "**How to read this.** Ward clusters define the Hanford taxonomy per feature space; "
        "K chosen by max KMeans silhouette in the interpretable 4–9 range. ARI vs KMeans "
        "(0.71–0.79) shows the structure is method-stable. Moderate silhouettes reflect real "
        "waste heterogeneity — the BBI spans continuous blending gradients — not algorithm "
        "failure. HDBSCAN provides independent density-based anomaly flags.", icon="🧭")
    st.warning(
        "**Basis caveat (the one that matters).** SRS publishes no per-tank current inventory. "
        "Per-tank SRS vectors here are *closure residuals* (post-cleaning, decayed to 2032) — "
        "they enter only the flagged closure track. SRS *current* composition exists publicly "
        "only as the 17 SRNL samples. Hanford's BBI is current waste. Projection percentiles "
        "quantify how far each SRS point sits from Hanford's taxonomy — large percentiles mean "
        "\"no true analog\", which is informative, not an error.", icon="⚠️")

# ================================================================== TAXONOMY
with tab_tax:
    st.subheader(f"{PANEL_LABEL[panel]} — Hanford taxonomy")
    pts = scatter_frame(panel)

    # ---- KMeans sweep
    sweep = pd.DataFrame(s1["kmeans_sweep"])
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=sweep["k"], y=sweep["silhouette"], name="silhouette",
                             mode="lines+markers", line=dict(color="#58a6ff")))
    fig.add_trace(go.Scatter(x=sweep["k"], y=sweep["calinski_harabasz"], name="Calinski-Harabasz",
                             mode="lines+markers", yaxis="y2", line=dict(color="#3fb950")))
    fig.add_trace(go.Scatter(x=sweep["k"], y=sweep["davies_bouldin"], name="Davies-Bouldin (↓)",
                             mode="lines+markers", yaxis="y3", line=dict(color="#ff7b72")))
    fig.update_layout(
        title=f"KMeans model selection — chosen K = {s1['chosen_k']} (max silhouette in 4–9)",
        xaxis=dict(title="k", dtick=1),
        yaxis=dict(title="silhouette", showgrid=False),
        yaxis2=dict(title="Calinski-Harabasz", overlaying="y", side="right", showgrid=False),
        yaxis3=dict(title="Davies-Bouldin", overlaying="y", side="right", position=0.92,
                    showgrid=False),
        height=340, margin=dict(l=10, r=90, t=50, b=10), legend=dict(orientation="h", y=1.18))
    st.plotly_chart(fig, width="stretch", key="sweep")

    # ---- UMAP scatter
    left, right = st.columns([3, 2])
    with left:
        hf = pts[pts["site"] == "Hanford"].copy()
        hf["cluster_str"] = hf["cluster"].apply(lambda c: f"C{c}")
        fig = px.scatter(hf, x="x", y="y", color="cluster_str",
                         color_discrete_sequence=CLUSTER_COLORS,
                         custom_data=["tank", "phase", "outlier"],
                         labels={"x": "UMAP 1", "y": "UMAP 2", "cluster_str": "cluster"},
                         hover_name="tank")
        fig.update_traces(
            marker=dict(size=7, opacity=0.85,
                        line=dict(width=0.5, color="#0d1117")),
            hovertemplate="<b>%{customdata[0]}</b> %{customdata[1]}"
                          "<br>cluster %{fullData.name} · outlier %{customdata[2]:.3f}"
                          "<extra></extra>")
        # anomaly rings
        an = hf[hf["outlier"] > 0.85]
        if len(an):
            fig.add_trace(go.Scatter(x=an["x"], y=an["y"], mode="markers", name="outlier >0.85",
                                     marker=dict(size=12, color="rgba(0,0,0,0)",
                                                 line=dict(color="#ff7b72", width=1.5)),
                                     hoverinfo="skip"))
        # SRS / closure stars
        for kind, sym, col in (("SRS measured", "star", SRS_COLOR),
                               ("SRS closure 2032", "star-diamond", CL_COLOR)):
            sub = pts[pts["kind"] == kind]
            if len(sub):
                fig.add_trace(go.Scatter(
                    x=sub["x"], y=sub["y"], mode="markers", name=kind,
                    marker=dict(symbol=sym, size=13, color=col,
                                line=dict(width=1, color="#0d1117")),
                    customdata=np.stack([sub["tank"], sub["phase"],
                                         sub["cluster"].fillna(-1).astype(int).astype(str),
                                         sub["pctl"].fillna(-1)], axis=-1),
                    hovertemplate="<b>%{customdata[0]}</b> %{customdata[1]}"
                                  "<br>→ cluster %{customdata[2]} (projected)"
                                  "<br>distance pctl %{customdata[3]:.0f}%<extra></extra>"))
        fig.update_layout(title="UMAP of CLR space (Hanford-fitted; SRS transformed onto it)",
                          height=520, margin=dict(l=10, r=10, t=50, b=10),
                          legend=dict(orientation="h", y=-0.08),
                          xaxis=dict(visible=False), yaxis=dict(visible=False))
        st.plotly_chart(fig, width="stretch", key="umap")

    # ---- cluster profiles
    with right:
        st.markdown("**Cluster profiles** — mean fraction of top analytes")
        prof_keys = sorted(s1["cluster_profiles"].keys())
        # STATIC option space across panels (AppTest-safe: keyed widget whose
        # options never change between reruns). Clusters absent in this panel
        # degrade gracefully below.
        cl = st.selectbox("Cluster", [f"C{i}" for i in range(10)], key="prof_cluster")
        cl_idx = int(cl[1:])
        if cl_idx not in prof_keys:
            st.info(f"Cluster {cl} does not exist in this panel "
                    f"({PANEL_LABEL[panel]} has C{prof_keys[0]}–C{prof_keys[-1]}). "
                    "Switch panels or pick another cluster.", icon="ℹ️")
            cl_ok = False
        else:
            cl_ok = True
        if cl_ok:
            prof = s1["cluster_profiles"][cl_idx]
            top = pd.Series(prof["top_analytes"]).sort_values()
            figp = px.bar(x=top.values, y=top.index, orientation="h",
                          labels={"x": "mean fraction", "y": ""},
                          color_discrete_sequence=["#58a6ff"])
            figp.update_layout(height=360, margin=dict(l=10, r=10, t=30, b=10),
                               xaxis=dict(type="log"))
            st.plotly_chart(figp, width="stretch", key="profile")

    st.caption(f"Phases per cluster: " + " · ".join(
        f"C{c}: {dict((R['stage1'][panel]['cluster_x_phase'][c] or {}))}" for c in
        sorted(s1["cluster_profiles"].keys())))

    # ---- crosstabs (external validation)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Clusters × BBI waste_type** (external labels, never used in fitting)")
        ct = pd.DataFrame(s1["cluster_x_wastetype"]).fillna(0).astype(int)
        st.plotly_chart(px.imshow(ct, text_auto=True, aspect="auto", color_continuous_scale="Blues",
                                  labels=dict(x="waste_type", y="cluster")),
                        width="stretch", key="ct_wt")
    with c2:
        st.markdown("**Clusters × phase**")
        cp = pd.DataFrame(s1["cluster_x_phase"]).fillna(0).astype(int)
        st.plotly_chart(px.imshow(cp, text_auto=True, aspect="auto", color_continuous_scale="Blues",
                                  labels=dict(x="phase", y="cluster")),
                        width="stretch", key="ct_ph")

# ============================================================ SRS PROJECTIONS
with tab_proj:
    st.subheader("SRS samples projected onto the Hanford taxonomy")
    st.caption("Nearest Ward centroid + percentile of that distance within the cluster's own "
               "member distances (0% = dead center, ≥95% = at/beyond the edge) + top-5 analogs "
               "by shared-support Aitchison distance (k = analytes counted).")

    prows = []
    for nm in PANELS:
        for track, label in (("measured", "current"), ("closure", "closure-2032")):
            for r in R["stage2"][nm][track]:
                a0 = (r.get("top5_analogs") or [{}])[0]
                prows.append({
                    "panel": PANEL_LABEL[nm], "point": r["point_id"].split("|", 1)[1],
                    "track": label, "cluster": (f"C{r['nearest_cluster']}"
                                                if r.get("nearest_cluster") is not None else "—"),
                    "dist": r.get("centroid_dist"), "pctl": r.get("cluster_dist_pctl"),
                    "top analog": (f"{a0.get('tank', '')} {a0.get('phase', '')}"
                                   if a0 else "—"),
                    "d(Ait)": a0.get("d_aitchison"), "k": a0.get("n_shared"),
                })
    pdf = pd.DataFrame(prows)

    tr = st.radio("Track", ["current", "closure-2032", "both"], horizontal=True, key="proj_track")
    show = pdf if tr == "both" else pdf[pdf["track"] == tr]
    st.dataframe(show, width="stretch", height=430, hide_index=True)

    st.plotly_chart(
        px.strip(pdf.dropna(subset=["pctl"]), x="panel", y="pctl", color="track",
                 stripmode="group", color_discrete_map={"current": SRS_COLOR,
                                                        "closure-2032": CL_COLOR},
                 labels={"pctl": "distance percentile within cluster (%)"},
                 hover_data=["point", "cluster", "dist"]),
        width="stretch", key="pctl_strip")

    st.markdown("#### Per-sample deep dive")
    meas = [r for r in R["stage2"][panel]["measured"]]
    # NOTE: options must BE labels (AppTest cannot round-trip format_func state)
    by_label = {r["point_id"].split("|", 1)[1]: r for r in meas}
    # STATIC option space: all SRS measured samples across all panels (AppTest-
    # safe); samples without data in this panel degrade gracefully.
    all_meas_labels = []
    for nm in PANELS:
        for rr in R["stage2"][nm]["measured"]:
            lb = rr["point_id"].split("|", 1)[1]
            if lb not in all_meas_labels:
                all_meas_labels.append(lb)
    pick_label = st.selectbox("SRS sample (measured)", all_meas_labels, key="proj_sample")
    if pick_label in by_label:
        r = by_label[pick_label]
    else:
        r = None
        st.info(f"**{pick_label}** has no measured data in the {PANEL_LABEL[panel]} panel — "
                "switch feature space (sidebar) or the SRS projections table above for its "
                "other-panel results.", icon="ℹ️")
    if r is not None and r.get("status") == "insufficient_data":
        st.info("Insufficient shared analytes in this panel to project — see Methods "
                "(SRS report panels differ by matrix).", icon="ℹ️")
    elif r is not None:
        a, b, c3 = st.columns(3)
        a.metric("Nearest cluster", f"C{r['nearest_cluster']}")
        b.metric("Centroid distance", f"{r['centroid_dist']:.2f}",
                 f"{r['cluster_dist_pctl']:.0f}th pctl")
        c3.metric("Cluster p95", f"{r['cluster_dist_p95']:.2f}",
                  ("outside" if r["cluster_dist_pctl"] >= 95 else "inside"), delta_color="inverse")
        d1, d2 = st.columns(2)
        with d1:
            st.markdown("**Top-5 Hanford analogs**")
            for i, an in enumerate(r["top5_analogs"], 1):
                st.markdown(
                    f"{i}. **{an['tank']}** {an['phase']}  \n"
                    f"   <span style='color:#8b949e'>{an['waste_type']} · "
                    f"d={an['d_aitchison']:.2f} · k={an['n_shared']} shared · "
                    f"cluster C{an['cluster']}</span>", unsafe_allow_html=True)
        with d2:
            st.markdown("**Driving analytes** (|CLR − cluster centroid|)")
            drv = pd.Series(r["driving_analytes"]).sort_values()
            figd = px.bar(x=drv.values, y=drv.index, orientation="h",
                          labels={"x": "|Δ CLR|", "y": ""}, color_discrete_sequence=["#ffa657"])
            figd.update_layout(height=300, margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(figd, width="stretch", key="driving")

# ================================================================== ANOMALIES
with tab_anom:
    st.subheader(f"Density-based anomaly candidates — {PANEL_LABEL[panel]}")
    st.caption("HDBSCAN outlier scores (0–1, higher = more anomalous; GLOSH). Threshold slider "
               "filters the table; the UMAP rings in Taxonomy explorer mark >0.85.")
    X, P, meta, clr = load_matrices(panel)
    scores = pd.Series(s1["hdbscan"]["outlier_scores"])
    thresh = st.slider("Outlier-score threshold", 0.5, 1.0, 0.85, 0.01, key="anom_thresh")

    h1, h2 = st.columns([2, 3])
    with h1:
        figh = px.histogram(x=scores.values, nbins=60, labels={"x": "outlier score", "y": "count"},
                            color_discrete_sequence=["#58a6ff"])
        figh.add_vline(x=thresh, line_color="#ff7b72", annotation_text=f"{thresh:.2f}")
        figh.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(figh, width="stretch", key="anom_hist")
    with h2:
        flagged = scores[scores >= thresh].sort_values(ascending=False)
        rows = []
        for pid, sc in flagged.items():
            _, tank, phase = pid.split("|", 2)
            wt = meta.loc[pid].get("waste_type", "NA") if pid in meta.index else "NA"
            rows.append({"tank": tank, "phase": phase, "cluster": f"C{s1['labels'][pid]}",
                         "score": round(float(sc), 3), "waste_type": str(wt)})
        st.dataframe(pd.DataFrame(rows), width="stretch", height=320, hide_index=True)
        st.caption(f"{len(flagged)} of {len(scores)} points ≥ {thresh:.2f} · "
                   f"HDBSCAN noise labels: {s1['hdbscan']['n_noise']}")

# ================================================================== DATASPACE
with tab_data:
    st.subheader(f"Dataspace explorer — {PANEL_LABEL[panel]}")
    st.caption("Pick any two points (any site, any basis) — or compare one point against its "
               "cluster centroid. Distances are computed live on the shared support "
               "(only analytes present on both sides count), exactly as in the analysis.")

    X, P, meta, clr = load_matrices(panel)
    labels = pd.Series(s1["labels"])

    def label_of(pid):
        site = ("Hanford" if pid.startswith("HF|") else
                "SRS" if pid.startswith("SRS|") else "SRS-closure")
        return f"{site} · {pid.split('|', 1)[1]}"

    all_ids = list(clr.index)
    id_by_label = {label_of(p): p for p in all_ids}
    # STATIC option space across panels: union of every point in every panel's
    # CLR matrix (AppTest-safe: options never change between reruns). Points not
    # present in the current panel degrade gracefully below.
    all_labels = []
    for nm in PANELS:
        _, _, _, clr_n = load_matrices(nm)
        for p in clr_n.index:
            lb = label_of(p)
            if lb not in all_labels:
                all_labels.append(lb)
    id_by_label_all = dict(id_by_label)  # current-panel resolution
    all_ids_flat = []
    for nm in PANELS:
        _, _, _, clr_n = load_matrices(nm)
        all_ids_flat.extend(clr_n.index)
    label_all = {}
    for p in all_ids_flat:
        label_all.setdefault(label_of(p), p)

    sel_a = st.selectbox("Point A", all_labels, key="ds_a")
    mode = st.radio("Point B", ["Compare to cluster centroid", "Compare to another point"],
                    horizontal=True)
    sel_b = None
    if mode == "Compare to another point":
        sel_b = st.selectbox("Point B", all_labels, key="ds_b")

    pid_a = id_by_label.get(sel_a)
    if pid_a is None:
        st.info(f"**{sel_a}** is not in the {PANEL_LABEL[panel]} CLR matrix — switch the "
                "feature space (sidebar) to where this point lives.", icon="ℹ️")
        st.stop()

    pres_a = (P.loc[pid_a] > 0) & (X.loc[pid_a] > 0)

    if sel_b is None:
        cid = s1["labels"][pid_a]
        members = [p for p in clr.index if s1["labels"][p] == cid]
        cent = clr.loc[members].mean(axis=0)
        pres_b = pd.Series(1, index=clr.columns)
        vec_b, name_b = cent, f"centroid of C{cid} ({len(members)} members)"
    else:
        pid_b = label_all.get(sel_b)
        if pid_b is None or pid_b not in clr.index:
            st.info(f"**{sel_b}** is not in the {PANEL_LABEL[panel]} CLR matrix — switch the "
                    "feature space (sidebar) to where this point lives.", icon="ℹ️")
            st.stop()
        vec_b = clr.loc[pid_b]
        pres_b = (P.loc[pid_b] > 0) & (X.loc[pid_b] > 0)
        name_b = label_of(pid_b)

    dist, k = shared_aitchison(clr.loc[pid_a], pres_a, vec_b, pres_b)

    m1, m2, m3 = st.columns(3)
    m1.metric("Shared support k", k if k else "—", "analytes counted")
    m2.metric("Aitchison distance", f"{dist:.2f}" if dist is not None else "—",
              None if dist is not None else "k < 2")
    if sel_b is None:
        cid = s1["labels"][pid_a]
        mem_d = [float(np.linalg.norm(clr.loc[m] - vec_b)) for m in members
                 if (P.loc[m] > 0).sum() >= 2]
        pctl = float(100 * np.mean(np.asarray(mem_d) < dist)) if dist is not None else None
        m3.metric("vs cluster members", f"{pctl:.0f}th pctl" if pctl is not None else "—",
                  f"{len(members)} members")

    # fraction comparison
    fa = X.loc[pid_a].where(pres_a).dropna()
    fb = (X.loc[pid_b].where(pres_b).dropna() if sel_b is not None
          else pd.Series(dtype=float))
    comp = pd.DataFrame({"A": fa})
    if len(fb):
        comp["B"] = fb.reindex(comp.index)
    comp = comp.sort_values("A", ascending=False).head(18)
    figc = px.bar(comp, barmode="group", log_y=True,
                  labels={"value": "fraction (log)", "index": ""})
    figc.update_layout(height=380, margin=dict(l=10, r=10, t=30, b=10),
                       legend=dict(orientation="h", y=1.12))
    st.plotly_chart(figc, width="stretch", key="ds_fracs")

    cap_a = f"**A** = {label_of(pid_a)}"
    cap_b = f" · **B** = {name_b}" if sel_b is not None else ""
    st.caption(cap_a + cap_b + " — bars show mass/activity fractions over each point's own "
                                "measured analytes (log scale); gaps = not reported.")

    with st.expander("CLR difference on shared support (A − B)"):
        if dist is not None:
            m = pres_a & pres_b
            diff = (clr.loc[pid_a][m] - vec_b[m]).sort_values()
            figdiff = px.bar(x=diff.values, y=diff.index, orientation="h",
                             color=diff.values, color_continuous_scale="RdBu_r",
                             color_continuous_midpoint=0,
                             labels={"x": "Δ CLR (A − B)", "y": ""})
            figdiff.update_layout(height=max(240, 24 * len(diff)), margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(figdiff, width="stretch", key="ds_diff")
            st.caption("Positive = A relatively enriched; negative = depleted "
                       "(relative to the shared geometric mean).")
        else:
            st.caption("Shared support too small (<2) for a CLR difference.")

# =================================================================== METHODS
with tab_meth:
    st.markdown("""
### Pipeline (reproducible)

```bash
cd Savannah_RiverTF && source .venv/bin/activate
python scripts/build_unsupervised_features.py     # DB → X_*.csv, presence_*.csv, meta_*.csv
python scripts/run_unsupervised_clustering.py     # CLR, Ward, KMeans sweep, HDBSCAN, UMAP, projection
python scripts/build_unsupervised_dashboard.py    # static HTML version
streamlit run dashboard/unsupervised_app.py       # this app
```

### Feature engineering

- **Scale invariance.** Every analyte in a sample shares one unknown scale factor; CLR cancels
  it — mg/L, µg/g, kg and Ci/gal bases become directly comparable without density assumptions.
  Physical conversions are still applied where possible (mg/L→µg/g via measured density
  1.27–1.33 g/mL; PO₄→P; molar Free OH→mass) so displayed fractions are meaningful, but no
  comparison depends on them.
- **Missing = neutral.** Absent analytes → the point's own geometric mean → CLR 0: zero pull on
  distances, unlike zero-imputation which fabricates absence signals.
- **Below detection.** SRS '<' → DL/2 (38 substitutions); Hanford sub-DL rows (4,792 keys)
  enter as reported (standard BBI practice).
- **Decay.** Hanford nuclides corrected from per-tank BBI dates (2015-07 / 2022-01) to
  2025-10-01; ⁹⁰Y→⁹⁰Sr and ¹³⁷ᵐBa→¹³⁷Cs folded (secular equilibrium); short-lived
  ¹⁰⁶Ru/¹⁴⁴Ce effectively vanish by 2025. SRS closure vectors un-decayed where t½ > 5 y,
  capped 10×.
- **Presence floors.** Features kept at ≥40% (sludge), ≥70% (salt), ≥50% (rad) Hanford
  reporting; rare analytes can't drive clusters.

### Models

- **Ward** on CLR space (final taxonomy; deterministic, dendrogram-validated,
  cophenetic 0.59–0.68); K by max KMeans silhouette in 4–9; **ARI vs KMeans 0.71–0.79**.
- **HDBSCAN** (min_cluster_size ≈ n/25, min_samples=1) — anomaly flagging only.
- **UMAP** (n_neighbors=15, min_dist=0.1) — visualization only; SRS points via
  `reducer.transform()`, never re-fit.
- **Projection** — nearest centroid + percentile within the cluster's own member-distance
  distribution + top-5 analogs by **shared-support Aitchison distance** (k = support size).

### Caveats

1. **Basis asymmetry** — SRS per-tank vectors are closure residuals (2032), not current waste;
   only the 17 SRNL samples represent current SRS. Tracks never mixed without a basis flag.
2. Hanford decay-date vintages differ (2015 vs 2022); corrections normalize but can't recover
   post-effective-date transfers.
3. Hanford organics (phthalates, ketones, aromatics) fall below presence floors — a dedicated
   organics panel would be needed.
4. SRS closure chem panels differ HTF (27) vs FTF (18) analytes — cross-farm closure comparison
   carries that asymmetry.
5. Formate dropped (only 3 Hanford tanks) despite SRS reporting it.
6. UMAP coordinates are for exploration; assignments come from Ward on full CLR space.

### Files

`data_processed/unsupervised/` — X_*.csv (fractions), presence_*.csv (masks), meta_*.csv,
X_*_clr.csv, clustering_results.json, panel_defs.json, build_report.json ·
`reports/UNSUPERVISED_METHODS.md` — full write-up ·
Data: `srs_tank_waste.db` (Hanford BBI via PNNL PHOENIX; SRNL reports SRNL-STI-2024-00240/00492,
SRNL-STI-2024-00436, SRNL-STI-2025-00489, PRFT 15/22/26).
""")
