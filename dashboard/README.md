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
