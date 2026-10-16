#!/usr/bin/env python3
"""SRS vs Hanford Tank Farm Waste Comparison — Streamlit dashboard.

Data: srs_tank_waste.db (SQLite, 56.7k rows — SRS PAs/SAs/LWSP/SRNL batches + Hanford PHOENIX BBI).
Run:  streamlit run dashboard/app.py
"""
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

BASE = Path("/Users/aspen_mb/Documents/Savannah_RiverTF")
DB = BASE / "srs_tank_waste.db"
SRS_COLOR = "#f0883e"      # orange
HF_COLOR = "#79c0ff"       # light blue
SRS_COLOR_DARK = "#d29922"

st.set_page_config(page_title="SRS vs Hanford Tank Waste", page_icon="☢", layout="wide",
                   initial_sidebar_state="expanded")


# ---------------------------------------------------------------- data loading
@st.cache_data(ttl=3600)
def q(sql, params=()):
    conn = sqlite3.connect(DB)
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


@st.cache_data(ttl=3600)
def load_all():
    d = {}
    d["srs_tanks"] = q("""SELECT t.tank_id, t.farm, t.tank_type, t.capacity_gal, t.status, t.closure_date,
            t.service_function, t.residual_volume_gal,
            COALESCE(SUM(CASE WHEN r.dataset IN ('htf_assigned_closure','ftf_assigned_closure') THEN r.value_ci END),0) AS ci_assigned,
            SUM(CASE WHEN r.dataset IN ('tank18_19_actual','tank16_final_actual') THEN r.value_ci END) AS ci_actual,
            COALESCE(SUM(CASE WHEN c.dataset IN ('htf_assigned_closure','ftf_assigned_closure') THEN c.value_kg END),0) AS kg
        FROM tanks t
        LEFT JOIN inventory_rad r ON r.tank_id = t.tank_id
        LEFT JOIN inventory_chem c ON c.tank_id = t.tank_id
        GROUP BY t.tank_id ORDER BY t.tank_id""")
    d["hf_tanks"] = q("""SELECT b.tank, MAX(b.tank_name) AS tank_name,
            SUM(CASE WHEN b.units='Ci' THEN b.inventory END) AS ci,
            SUM(CASE WHEN b.units='kg' THEN b.inventory END) AS kg
        FROM hanford_bbi b GROUP BY b.tank""")
    vols = q("""SELECT tank, waste_phase, SUM(volume) AS kL FROM hanford_bbi_volume
        WHERE units='kL' AND waste_phase NOT LIKE 'Drained%' AND waste_phase NOT LIKE 'Retained%'
        GROUP BY tank, waste_phase""")
    d["hf_vols"] = vols
    d["hf_tanks"]["kL"] = d["hf_tanks"]["tank"].map(vols.groupby("tank")["kL"].sum())
    d["hf_tanks"]["farm"] = d["hf_tanks"]["tank"].apply(hf_farm)
    # site totals
    d["hf_total_ci"] = d["hf_tanks"]["ci"].sum()
    d["hf_total_mgal"] = d["hf_tanks"]["kL"].sum() / 3785.412
    hf_by_phase = q("""SELECT CASE WHEN waste_phase LIKE 'Supernatant%' THEN 'Supernatant'
             WHEN waste_phase LIKE 'Saltcake%' THEN 'Saltcake' ELSE 'Sludge' END AS grp,
             SUM(inventory) AS ci FROM hanford_bbi WHERE units='Ci' GROUP BY grp""")
    d["hf_phase_ci"] = dict(zip(hf_by_phase["grp"], hf_by_phase["ci"]))
    hf_phase_vol = vols.copy()
    hf_phase_vol["grp"] = hf_phase_vol["waste_phase"].apply(
        lambda p: "Supernatant" if p.startswith("Supernatant") else ("Saltcake" if "Saltcake" in p else "Sludge"))
    d["hf_phase_mgal"] = (hf_phase_vol.groupby("grp")["kL"].sum() / 3785.412).to_dict()
    # top nuclides
    d["srs_top"] = q("""SELECT nuclide AS n, SUM(value_ci) AS v FROM inventory_rad
        WHERE dataset IN ('htf_assigned_closure','ftf_assigned_closure')
        GROUP BY nuclide ORDER BY v DESC LIMIT 40""")
    d["hf_top"] = q("""SELECT analyte AS n, SUM(inventory) AS v FROM hanford_bbi
        WHERE units='Ci' GROUP BY analyte ORDER BY v DESC LIMIT 40""")
    # current-waste samples
    d["samples"] = q("SELECT sample, sample_type, report, sample_year, matrix, category, analyte, value, unit, flag, note FROM current_waste_samples")
    d["srs_rad_detail"] = q("""SELECT t.tank_id, t.farm, r.nuclide, r.value_ci
        FROM inventory_rad r JOIN tanks t ON t.tank_id=r.tank_id
        WHERE r.dataset IN ('htf_assigned_closure','ftf_assigned_closure')""")
    return d


def hf_farm(tid):
    if tid.startswith(("AN", "AP", "AW", "AZ", "AY", "BX", "BY", "SX", "SY", "TX", "TY")):
        return tid[:2] + "-Farm"
    return tid[0] + "-Farm"


D = load_all()

SRS_CUR = {"total_mgal": 33.2, "total_mci": 191.0,
           "sludge": (2.8, 106.0), "supernate": (16.4, 75.0), "saltcake": (10.0, 10.0)}
HF_CUR = {"total_mgal": round(D["hf_total_mgal"], 1),
          "total_mci": round(D["hf_total_ci"] / 1e6, 1),
          "sludge": (D["hf_phase_mgal"].get("Sludge", 0), D["hf_phase_ci"].get("Sludge", 0) / 1e6),
          "supernate": (D["hf_phase_mgal"].get("Supernatant", 0), D["hf_phase_ci"].get("Supernatant", 0) / 1e6),
          "saltcake": (D["hf_phase_mgal"].get("Saltcake", 0), D["hf_phase_ci"].get("Saltcake", 0) / 1e6)}

# ---------------------------------------------------------------- header
st.markdown("""
# Savannah River Site vs Hanford — Tank Farm Waste Comparison
Interactive comparison of remaining waste inventory, radiological and chemical content.
SRS: LWSP Rev 24 · PAs/SAs · SRNL batch characterizations — Hanford: PHOENIX Best-Basis Inventory (effective 2025-10-01, decay 2022-01-01).
""")
st.caption("Data loaded from srs_tank_waste.db (SRS 51 tanks + Hanford 177 tanks, 56.7k rows).")

tab_over, tab_phase, tab_rad, tab_tank, tab_chem, tab_meth = st.tabs(
    ["Overview", "Phases & Farms", "Radionuclides", "Tank Explorer", "Current Chemistry", "Methods & Caveats"])

# ---------------------------------------------------------------- Overview
with tab_over:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("SRS remaining waste", "33.2 Mgal", "191 MCi · 43 tanks")
    c2.metric("Hanford remaining waste", f"{HF_CUR['total_mgal']} Mgal", f"{HF_CUR['total_mci']:.0f} MCi · 177 tanks")
    c3.metric("SRS curie density", "5.8 MCi/Mgal", "salt-dominated")
    c4.metric("Hanford curie density", f"{HF_CUR['total_mci']/HF_CUR['total_mgal']:.1f} MCi/Mgal", "sludge-dominated")
    c5.metric("SRS waste processed", "~46 MCi", "227 → 191 MCi since 2022")
    c6.metric("Hanford BBI rows", "46,600", "54 nuclides × 177 tanks")

    st.info("⚠ **Basis difference:** SRS per-tank curie values are **closure-residual inventories** (PA/SA basis, "
            "decayed to 2032) — the public per-tank analog to Hanford's BBI. Farm-level **current** SRS inventory "
            "(33.2 Mgal / 191 MCi) is a 2025 measurement. Hanford numbers are live BBI (decay 2022-01-01).",
            icon="⚠️")

    l, r = st.columns(2)
    with l:
        st.markdown("#### Head-to-head: current farm inventory")
        comp = pd.DataFrame({
            "Metric": ["Total volume (Mgal)", "Total activity (MCi)", "Sludge (Mgal)", "Supernate (Mgal)",
                       "Saltcake (Mgal)", "Sludge activity (MCi)", "Salt waste activity (MCi)", "Tanks remaining"],
            "SRS": [SRS_CUR["total_mgal"], SRS_CUR["total_mci"], SRS_CUR["sludge"][0], SRS_CUR["supernate"][0],
                    SRS_CUR["saltcake"][0], SRS_CUR["sludge"][1], SRS_CUR["supernate"][1] + SRS_CUR["saltcake"][1], 43],
            "Hanford": [HF_CUR["total_mgal"], HF_CUR["total_mci"], HF_CUR["sludge"][0], HF_CUR["supernate"][0],
                        HF_CUR["saltcake"][0], HF_CUR["sludge"][1], HF_CUR["supernate"][1] + HF_CUR["saltcake"][1], 177],
        })
        comp["Ratio (SRS/HF)"] = (comp["SRS"] / comp["Hanford"]).round(2)
        st.dataframe(comp.set_index("Metric").style.format(precision=1), width='stretch')
    with r:
        st.markdown("#### Scale context")
        rows = [
            ("SRS share of Hanford volume", SRS_CUR["total_mgal"] / HF_CUR["total_mgal"],
             "yet SRS holds MORE curies — its salt waste is Cs-137 rich"),
            ("SRS salt waste share of volume", (SRS_CUR["supernate"][0] + SRS_CUR["saltcake"][0]) / SRS_CUR["total_mgal"],
             "sludge (9% of volume) holds 54% of SRS curies"),
            ("Hanford sludge share of volume", HF_CUR["sludge"][0] / HF_CUR["total_mgal"],
             "direct vitrification feed; supernatant feeds TSCR"),
        ]
        fig = go.Figure()
        for i, (lab, frac, note) in enumerate(rows):
            fig.add_bar(y=[f"<b>{lab}</b><br><span style='font-size:10px;color:#8b949e'>{note}</span>"],
                       x=[frac * 100], orientation="h", marker_color=[SRS_COLOR, HF_COLOR, "#a371f7"][i],
                       text=[f"{frac*100:.0f}%"], textposition="inside", showlegend=False)
        fig.update_layout(barmode="overlay", xaxis_title="% ", yaxis=dict(showticklabels=False),
                          margin=dict(l=10, r=10, t=10, b=10), height=280,
                          xaxis=dict(range=[0, 100], gridcolor="#30363d"), plot_bgcolor="#0e1117",
                          paper_bgcolor="#0e1117", font=dict(color="#e6edf3"))
        st.plotly_chart(fig, width='stretch')

# ---------------------------------------------------------------- Phases & Farms
with tab_phase:
    p1, p2 = st.columns(2)
    with p1:
        st.markdown("#### SRS waste phases")
        srs_phase = pd.DataFrame([
            ("Supernate", SRS_CUR["supernate"][0], SRS_CUR["supernate"][1]),
            ("Saltcake", SRS_CUR["saltcake"][0], SRS_CUR["saltcake"][1]),
            ("Sludge", SRS_CUR["sludge"][0], SRS_CUR["sludge"][1]),
        ], columns=["Phase", "Mgal", "MCi"])
        fig = px.treemap(srs_phase, path=["Phase"], values="Mgal", color="Phase",
                         color_discrete_map={"Supernate": SRS_COLOR, "Saltcake": SRS_COLOR_DARK, "Sludge": "#a371f7"},
                         custom_data=["MCi"])
        fig.update_traces(texttemplate="<b>%{label}</b><br>%{value:.1f} Mgal<br>%{customdata[0]:.0f} MCi")
        fig.update_layout(margin=dict(l=5, r=5, t=5, b=5), height=380,
                          paper_bgcolor="#0e1117", font=dict(color="#e6edf3"))
        st.plotly_chart(fig, width='stretch')
    with p2:
        st.markdown("#### Hanford waste phases (BBI)")
        hf_phase = pd.DataFrame([(k, HF_CUR[k][0], HF_CUR[k][1]) for k in ("supernate", "saltcake", "sludge")],
                                columns=["Phase", "Mgal", "MCi"]).replace(
            {"supernate": "Supernatant", "saltcake": "Saltcake", "sludge": "Sludge"})
        fig = px.treemap(hf_phase, path=["Phase"], values="Mgal", color="Phase",
                         color_discrete_map={"Supernatant": HF_COLOR, "Saltcake": "#388bfd", "Sludge": "#a371f7"},
                         custom_data=["MCi"])
        fig.update_traces(texttemplate="<b>%{label}</b><br>%{value:.1f} Mgal<br>%{customdata[0]:.0f} MCi")
        fig.update_layout(margin=dict(l=5, r=5, t=5, b=5), height=380,
                          paper_bgcolor="#0e1117", font=dict(color="#e6edf3"))
        st.plotly_chart(fig, width='stretch')

    st.markdown("#### Per-farm distribution")
    srs_f = D["srs_tanks"].groupby("farm").agg(n=("tank_id", "count"), cap_gal=("capacity_gal", "sum"),
                                              ci=("ci_assigned", "sum")).reset_index()
    srs_f["site"] = "SRS"
    srs_f["Mgal"] = (srs_f["cap_gal"] / 1e6).round(2)
    hf_f = D["hf_tanks"].groupby("farm").agg(n=("tank", "count"), kL=("kL", "sum"), ci=("ci", "sum")).reset_index()
    hf_f["site"] = "Hanford"
    hf_f["Mgal"] = (hf_f["kL"] / 3785.412).round(2)
    farms = pd.concat([
        srs_f[["site", "farm", "n", "Mgal", "ci"]].rename(columns={"farm": "Farm", "n": "Tanks", "ci": "Activity (Ci)"}),
        hf_f[["site", "farm", "n", "Mgal", "ci"]].rename(columns={"farm": "Farm", "n": "Tanks", "ci": "Activity (Ci)"}),
    ])
    farms["Site"] = farms["site"]
    fig = px.scatter(farms, x="Mgal", y="Activity (Ci)", size="Tanks", color="Site", text="Farm", log_y=True,
                     color_discrete_map={"SRS": SRS_COLOR, "Hanford": HF_COLOR}, size_max=42,
                     hover_name="Farm", hover_data=["Tanks"])
    fig.update_traces(textposition="top center", textfont=dict(size=9))
    fig.update_layout(height=430, margin=dict(l=10, r=10, t=20, b=10),
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
                      font=dict(color="#e6edf3"), xaxis=dict(gridcolor="#30363d"), yaxis=dict(gridcolor="#30363d"))
    st.plotly_chart(fig, width='stretch')
    st.caption("SRS farm Mgal = total tank capacity (current per-tank volumes are not public); Hanford Mgal = BBI wet volume. "
               "Activity basis: SRS assigned closure residuals (2032), Hanford BBI (2022 decay).")
    st.dataframe(farms.drop(columns="site").sort_values("Activity (Ci)", ascending=False),
                 width='stretch', height=320)

# ---------------------------------------------------------------- Radionuclides
with tab_rad:
    st.markdown("#### Top radionuclides by site")
    st.caption("SRS = closure-residual inventories (51 tanks, decayed 2032) · Hanford = BBI totals (177 tanks, decayed 2022). "
               "Y-90 / Ba-137m are daughters counted with parents — treat Cs-137 and Sr-90 as families.")

    def hf_style(n):
        m = n.replace("m", "")
        parts = {"Cs": "Cs-137", "Sr": "Sr-90", "Y": "Y-90", "Ba": "Ba-137m"}
        return n  # keep HF native naming

    srs_t = D["srs_top"].head(20).copy()
    hf_t = D["hf_top"].head(20).copy()
    # normalize to compare: convert SRS 'Cs-137' -> '137Cs'
    def to_hf(name):
        if "-" in name:
            el, mass = name.split("-")
            return mass + el
        return name
    srs_t["key"] = srs_t["n"].apply(to_hf)
    hf_t["key"] = hf_t["n"]
    merged = hf_t.merge(srs_t[["key", "v"]], on="key", how="outer", suffixes=("_hf", "_srs")).fillna(0)
    merged["max"] = merged[["v_hf", "v_srs"]].max(axis=1)
    merged = merged.sort_values("max", ascending=False).head(18)

    fig = go.Figure()
    fig.add_bar(y=merged["key"], x=merged["v_srs"], orientation="h", name="SRS (assigned closure)",
                marker_color=SRS_COLOR)
    fig.add_bar(y=merged["key"], x=merged["v_hf"], orientation="h", name="Hanford (BBI)",
                marker_color=HF_COLOR)
    fig.update_layout(barmode="group", height=560, xaxis_type="log",
                      xaxis_title="Ci (log)", margin=dict(l=10, r=10, t=20, b=10),
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font=dict(color="#e6edf3"),
                      xaxis=dict(gridcolor="#30363d"), yaxis=dict(gridcolor="#30363d"))
    st.plotly_chart(fig, width='stretch')

    l, r = st.columns(2)
    with l:
        st.markdown("#### Share of site total (top 8)")
        tot_srs = D["srs_top"]["v"].sum()
        tot_hf = D["hf_top"]["v"].sum()
        merged["share_srs"] = merged["v_srs"] / tot_srs * 100
        merged["share_hf"] = merged["v_hf"] / tot_hf * 100
        sh = merged.head(8)[["key", "share_srs", "share_hf"]]
        fig = go.Figure()
        fig.add_bar(y=sh["key"], x=sh["share_srs"], orientation="h", name="SRS", marker_color=SRS_COLOR,
                    text=[f"{v:.1f}%" for v in sh["share_srs"]], textposition="auto")
        fig.add_bar(y=sh["key"], x=sh["share_hf"], orientation="h", name="Hanford", marker_color=HF_COLOR,
                    text=[f"{v:.1f}%" for v in sh["share_hf"]], textposition="auto")
        fig.update_layout(barmode="group", height=340, xaxis_title="% of site total",
                          margin=dict(l=10, r=10, t=10, b=10),
                          paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font=dict(color="#e6edf3"))
        st.plotly_chart(fig, width='stretch')
    with r:
        st.markdown("#### Comparison table")
        tbl = merged[["key", "v_srs", "v_hf"]].copy()
        tbl.columns = ["Nuclide", "SRS Ci", "HF Ci"]
        tbl["HF/SRS"] = (tbl["HF Ci"] / tbl["SRS Ci"].replace(0, float("nan"))).round(1)
        tbl = tbl.sort_values("HF Ci", ascending=False)
        st.dataframe(tbl.set_index("Nuclide").style.format({"SRS Ci": "{:,.4g}", "HF Ci": "{:,.4g}"}),
                     width='stretch', height=420)

# ---------------------------------------------------------------- Tank Explorer
with tab_tank:
    st.markdown("#### Tank Explorer — 228 tanks")
    lc1, lc2, lc3 = st.columns([2, 2, 2])
    y_metric = lc1.selectbox("Y-axis", ["Volume (kgal)", "Chemical mass (kg)"])
    site_sel = lc2.multiselect("Sites", ["SRS", "Hanford"], default=["SRS", "Hanford"])
    log_x = lc3.checkbox("Log X (activity)", True)

    srs_df = D["srs_tanks"].copy()
    srs_df["site"] = "SRS"
    srs_df["label"] = "Tank " + srs_df["tank_id"].astype(str) + " (" + srs_df["farm"] + ")"
    srs_df["Ci"] = srs_df["ci_assigned"]
    srs_df["kgal"] = srs_df["capacity_gal"] / 1000
    srs_df["kg"] = srs_df["kg"]
    srs_df["Volume (kgal)"] = srs_df["kgal"]
    srs_df["Chemical mass (kg)"] = srs_df["kg"]
    hf_df = D["hf_tanks"].copy()
    hf_df["site"] = "Hanford"
    hf_df["label"] = hf_df["tank_name"]
    hf_df["Ci"] = hf_df["ci"]
    hf_df["kgal"] = hf_df["kL"] / 3.785412
    hf_df["Volume (kgal)"] = hf_df["kgal"]
    hf_df["Chemical mass (kg)"] = hf_df["kg"]
    both = pd.concat([srs_df, hf_df], ignore_index=True)
    both = both[both["site"].isin(site_sel)]
    both = both[both["Ci"] > 0]

    fig = px.scatter(both, x="Ci", y=y_metric, color="site", log_y=True, log_x=log_x,
                     hover_name="label",
                     hover_data={"site": True, "Ci": ":,.4g", y_metric: ":,.4g", "kg": ":,.4g"},
                     color_discrete_map={"SRS": SRS_COLOR, "Hanford": HF_COLOR},
                     labels={"Ci": "Activity (Ci)"})
    fig.update_layout(height=560, margin=dict(l=10, r=10, t=20, b=10),
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font=dict(color="#e6edf3"),
                      xaxis=dict(gridcolor="#30363d"), yaxis=dict(gridcolor="#30363d"))
    st.plotly_chart(fig, width='stretch')
    st.caption("SRS activity = assigned closure residual (2032 decay); volume = tank capacity. "
               "Hanford = BBI Ci and wet volume. Click legend to toggle sites.")

    l, r = st.columns(2)
    with l:
        st.markdown("##### SRS tanks")
        srs_view = srs_df[["tank_id", "farm", "tank_type", "status", "closure_date", "capacity_gal",
                           "ci_assigned", "ci_actual", "kg"]].rename(columns={
            "tank_id": "Tank", "farm": "Farm", "tank_type": "Type", "status": "Status",
            "closure_date": "Closed", "capacity_gal": "Capacity (gal)",
            "ci_assigned": "Assigned Ci", "ci_actual": "Measured Ci", "kg": "Chem kg"})
        st.dataframe(srs_view.set_index("Tank"), width='stretch', height=430)
    with r:
        st.markdown("##### Hanford tanks (top 100 by activity)")
        hf_view = hf_df.sort_values("Ci", ascending=False).head(100)[
            ["tank_name", "farm", "kL", "Ci", "kg"]].rename(columns={
            "tank_name": "Tank", "farm": "Farm", "kL": "BBI volume (kL)", "Ci": "Ci", "kg": "Chem kg"})
        st.dataframe(hf_view.set_index("Tank"), width='stretch', height=430)

    # per-tank drill-down
    st.markdown("#### Per-tank drill-down")
    dtank = st.selectbox("Pick a tank", sorted(both["label"].unique()), index=None,
                         placeholder="e.g. Tank 40 (HTF) or 241-AZ-101 …")
    if dtank:
        row = both[both["label"] == dtank].iloc[0]
        if row["site"] == "SRS":
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Tank", f"{row['farm']}-{row['tank_id']}")
            m2.metric("Type", row["tank_type"])
            m3.metric("Assigned closure Ci", f"{row['ci_assigned']:,.0f}")
            m4.metric("Chemical kg", f"{row['kg']:,.0f}")
            top = D["srs_rad_detail"][D["srs_rad_detail"]["tank_id"] == row["tank_id"]].nlargest(20, "value_ci")
            fig = go.Figure(go.Bar(x=top["value_ci"], y=top["nuclide"], orientation="h",
                                   marker_color=SRS_COLOR))
            fig.update_layout(height=460, xaxis_type="log", xaxis_title="Ci",
                              margin=dict(l=10, r=10, t=10, b=10),
                              paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font=dict(color="#e6edf3"))
            st.plotly_chart(fig, width='stretch')
        else:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Tank", row["tank_name"])
            m2.metric("Farm", row["farm"])
            m3.metric("BBI Ci", f"{row['Ci']:,.0f}")
            m4.metric("BBI volume kL", f"{row['kL']:,.0f}")
            top = q("""SELECT analyte, SUM(inventory) AS v FROM hanford_bbi
                       WHERE tank=? AND units='Ci' GROUP BY analyte ORDER BY v DESC LIMIT 20""",
                    (row["tank"],))
            fig = go.Figure(go.Bar(x=top["v"], y=top["analyte"], orientation="h", marker_color=HF_COLOR))
            fig.update_layout(height=460, xaxis_type="log", xaxis_title="Ci",
                              margin=dict(l=10, r=10, t=10, b=10),
                              paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font=dict(color="#e6edf3"))
            st.plotly_chart(fig, width='stretch')

# ---------------------------------------------------------------- Current Chemistry
with tab_chem:
    st.info("Hanford's BBI publishes per-tank kg for ~140 chemical analytes (table `hanford_bbi`). "
            "SRS's public per-tank chemical data are closure-residual elementals. This tab shows SRS's "
            "**current measured waste chemistry** from SRNL batch reports — the closest public equivalent "
            "of a BBI sample basis.", icon="ℹ️")
    samples = D["samples"]
    l, r = st.columns(2)
    with l:
        st.markdown("##### Sludge Batch 11 — Tank 51 (2024)")
        sb11 = samples[(samples["sample"] == "Tank 51 Sludge Batch 11") &
                       (samples["unit"] == "ug/g slurry")].sort_values("value", ascending=False)
        fig = go.Figure(go.Bar(x=sb11["value"], y=sb11["analyte"], orientation="h", marker_color=SRS_COLOR))
        fig.update_xaxes(type="log", title="µg/g slurry (log)")
        fig.update_layout(height=620, margin=dict(l=10, r=10, t=10, b=10),
                          paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font=dict(color="#e6edf3"))
        st.plotly_chart(fig, width='stretch')
    with r:
        st.markdown("##### SWPF Salt Batch chemistry (filtrate, mg/L)")
        b_sel = st.selectbox("Batch", ["SWPF Salt Batch 8 (Tank 40, SRNL filtered)",
                                       "SWPF Salt Batch 9 (Tank 40, SRNL filtered)",
                                       "SWPF Salt Batch 12 (SWPF-AL filtered)",
                                       "SWPF Salt Batch 13 (SWPF-AL filtered)"])
        comp = samples[(samples["sample"] == b_sel) & (samples["category"] == "component")].sort_values("value", ascending=False)
        fig = go.Figure(go.Bar(x=comp["value"], y=comp["analyte"], orientation="h", marker_color=SRS_COLOR_DARK))
        fig.update_xaxes(type="log", title="mg/L (log)")
        fig.update_layout(height=560, margin=dict(l=10, r=10, t=10, b=10),
                          paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font=dict(color="#e6edf3"))
        st.plotly_chart(fig, width='stretch')
        st.caption("SWPF feed is ~5–8 M Na nitrate/nitrite.")

    st.markdown("##### Current radionuclide concentrations (measured samples)")
    rs = samples[(samples["sample"].isin(["Tank 40 Sludge Batch 10", "SWPF Salt Batch 14 (Tank 21H)"])) &
                 (samples["category"] == "radionuclide")]
    fig = px.bar(rs, x="analyte", y="value", color="sample", log_y=True, barmode="group",
                 color_discrete_map={"Tank 40 Sludge Batch 10": SRS_COLOR,
                                     "SWPF Salt Batch 14 (Tank 21H)": SRS_COLOR_DARK},
                 labels={"value": "concentration (log)", "analyte": ""})
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10),
                      paper_bgcolor="#0e1117", plot_bgcolor="#0e1117", font=dict(color="#e6edf3"),
                      xaxis=dict(gridcolor="#30363d"), yaxis=dict(gridcolor="#30363d"))
    st.plotly_chart(fig, width='stretch')
    st.caption("SB10 (Tank 40 sample, 2023) in µCi/g dried solids — DWPF feed basis; Salt Batch 14 (Tank 21H) in pCi/mL. "
               "Note I-129 in Salt Batch 14 (1.03E2) is now above its SWPF WAC (1.00E2 pCi/mL).")

    st.markdown("##### All measured samples (raw table)")
    st.dataframe(samples, width='stretch', height=380)

# ---------------------------------------------------------------- Methods
with tab_meth:
    st.markdown("#### Data provenance")
    prov = pd.DataFrame([
        ["SRS", "Farm current inventory (33.2 Mgal / 191 MCi)",
         "Liquid Waste System Plan Rev 24 (SRMC-LWP-2023-00001), WCS Curie & Volume Inventory Report", "2025-09-30"],
        ["SRS", "Per-tank radionuclides (54) & chemicals (27)",
         "Tank 16 SA (SRR-CWDA-2014-00106) Tbl 6.2-2/3; Tanks 5&6 SA (SRR-CWDA-2012-00106) Tbl 6.1-1/2; "
         "HTF PA (SRR-CWDA-2010-00128) Tbl 3.4-9/10; measured actuals tanks 5/6/12/16/18/19", "closure residual, 2032 decay"],
        ["SRS", "Current waste chemistry (SB11, SB10, Salt Batches 8–14, PRFT)",
         "SRNL-STI-2024-00492, -2024-00240, -2024-00436, -2025-00489, -2025-00012, OSTI 2473257/2483548", "2023–2025 samples"],
        ["Hanford", "Best-Basis Inventory (46,600 rows: 54 radionuclides + 140 chemicals × 7 phases)",
         "PNNL PHOENIX TankFarmService API (BBIWaste / BBIVolume, all 177 tanks)", "effective 2025-10-01, decay 2022-01-01"],
    ], columns=["Site", "Dataset", "Source", "As-of / basis"])
    st.dataframe(prov, width='stretch', hide_index=True)

    st.markdown("#### Caveats (read before comparing)")
    st.markdown("""
- **Decay dates differ**: Hanford BBI decayed to 2022-01-01; SRS PA values decayed to 2032. The site-level
  current difference (191 vs ~123 MCi) is dominated by real inventory, not decay.
- **SRS per-tank = closure residuals**: what will remain AFTER waste removal (4,000 gal/tank assigned basis).
  NOT today's tank contents. HTF values are conservative max-of-group assignments.
- **Hanford totals include all 177 tanks** incl. inactive single-shell farms; both sites' totals shrink as
  processing continues.
- **Chemical bases differ**: SRS per-tank kg are elements on residual sludge; Hanford kg include supernate
  salts (Na nitrate/nitrite dominate mass). The Current Chemistry tab gives the fair waste-type comparison.
- Ba-137m / Y-90 are daughters counted with parents at both sites — treat as families.
""")

    st.markdown("#### Source documents registry")
    src = q("SELECT source_id, title, doc_number, year, url, local_file FROM sources ORDER BY source_id")
    st.dataframe(src, width='stretch', hide_index=True)

st.divider()
st.caption("Assembled by Hermes agent from public DOE/NRC/PNNL sources · SRS: LWSP Rev 24 + 4 PA/SA documents + 7 SRNL "
           "characterization reports · Hanford: PHOENIX BBI API (published 2025-12-31). "
           "SQLite: srs_tank_waste.db · Scripts: scripts/ · Raw PDFs: data_raw/")
