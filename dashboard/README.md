# SRS vs Hanford Comparison Dashboards

## Streamlit app (recommended — interactive, DB-backed)
```bash
cd /Users/aspen_mb/Documents/Savannah_RiverTF
.venv/bin/streamlit run dashboard/app.py --server.port 8635
# open http://localhost:8635
```

Six tabs: Overview (metrics + head-to-head + scale context) · Phases & Farms (treemaps, farm scatter) ·
Radionuclides (log bars, share, table) · Tank Explorer (228-tank log-log scatter, per-tank drill-down with
top-20 nuclide charts) · Current Chemistry (SB11/SB10/salt-batch measured data) · Methods & Caveats.

Data: `srs_tank_waste.db` (SQLite, 56.7k rows) — SRS 51 tanks (PA/SA closure residuals + SRNL current-waste
samples) and Hanford 177-tank Best-Basis Inventory (PHOENIX, effective 2025-10-01, decay 2022-01-01).

## Static HTML version
`dashboard/srs_hanford_comparison.html` — self-contained single file (no server needed), same six sections.

## Verified
- Streamlit AppTest: 0 exceptions, 6 tabs, 8 dataframes, 6 metrics; drill-down exercised for 241-AZ-101
  and Tank 40 (HTF); salt-batch selector exercised.
- Live in-browser: title/metrics/tabs render; 10 Plotly charts in DOM. (Headless Lightpanda lacks
  canvas `measureText`, so chart *canvas painting* only fully works in real browsers — app logic is clean.)

---

# Unsupervised Waste Taxonomy Explorer

## Streamlit app
```bash
.venv/bin/streamlit run dashboard/unsupervised_app.py --server.port 8643
# open http://localhost:8643
```

Six tabs: Overview (quality metrics per feature space + basis caveat) · Taxonomy explorer (KMeans
selection sweep, UMAP of CLR space with SRS stars + outlier rings, cluster profiles, clusters×waste_type
and clusters×phase heatmaps) · SRS projections (all-samples table, distance-percentile strip, per-sample
deep dive with top-5 analogs and driving analytes) · Anomalies (HDBSCAN outlier-score histogram + threshold
table) · Dataspace (pick any two points from any site/basis — live shared-support Aitchison distance, k,
fraction comparison, CLR difference) · Methods.

Requires the analysis artifacts in `data_processed/unsupervised/` (build via
`scripts/run_unsupervised_clustering.py`). Panel switch (sludge/salt/rad) in the sidebar drives every tab.

## Static HTML version
`dashboard/unsupervised_analysis.html` — self-contained single file (no server, no deps), same content
in canvas rendering.

## Verified (unsupervised app)
- Streamlit AppTest: 0 exceptions; 6 tabs; 10 metrics; 9 plotly charts; panel switching exercised
  (sludge→salt→rad→sludge); Dataspace point-vs-point (same-panel and cross-panel), anomaly slider at 0.95,
  projection track radio all exercised.
- Live in-browser: Streamlit's React/WebSocket shell does not hydrate in the headless Lightpanda engine
  (static HTML dashboards render fine in the same engine). AppTest is the logic truth gate; open in a real
  browser for the full experience.

## White paper (paper/unsup/)
`Unsupervised_Taxonomy_White_Paper.{pdf,docx}` — 21 pp, 8 figures, 3 tables. Explains and interprets the
unsupervised model: CLR/Aitchison geometry, neutral-point imputation, Ward/KMeans/HDBSCAN/UMAP, GLOSH
failure modes, calibrated analog-reading rules, full caveat ledger. Built content-as-data
(content_u1/content_u2.py) → render_unsup.py; every number traced live to
`paper/unsup/verify_numbers.py` and gated by `paper/unsup/qa_unsup.py` (38/38: numeric claims vs ledger,
math OCR, cluster-size sums, no-overclaim guard). Regenerate: `.venv/bin/python paper/unsup/render_unsup.py`
then `.venv/bin/python paper/unsup/qa_unsup.py`.
