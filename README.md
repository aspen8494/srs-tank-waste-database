# SRS Tank Waste — Savannah River Site Inventory Database & Comparison Dashboards

A Best-Basis-Inventory-style research dataset for the **Savannah River Site (SRS) F- and H-Area Tank Farms**
(51 waste tanks), assembled from public DOE/NRC/SRNS documents, plus a live pull of the **Hanford Site's**
177-tank Best-Basis Inventory (BBI) from PNNL PHOENIX — with Streamlit and static-HTML dashboards comparing
the two sites' remaining waste inventories, radionuclide inventories, and chemical compositions.

Built for data-science / machine-learning work on real tank-waste characterization data. Every row carries
its `dataset` / `basis` / `source` provenance so different bases (current vs closure-residual) can't be mixed
accidentally.

## Headline numbers

| | SRS (2025-09-30 WCS) | Hanford (BBI effective 2025-10-01) |
|---|---|---|
| Remaining volume | **33.2 Mgal** (43 tanks) | **53.0 Mgal** (177 tanks) |
| Remaining activity | **191 MCi** | **122.6 MCi** |
| Phases | sludge 2.8 Mgal / 106 MCi · supernate 16.4 / 75 · saltcake 10 / 10 | sludge · supernatant · saltcake (BBI 7-phase split) |
| Curie density | 5.8 MCi/Mgal (salt-dominated, Cs-137 rich) | 2.3 MCi/Mgal |

**Important basis caveat** — SRS does not publish a per-tank *current* BBI like Hanford's. Public per-tank SRS
data are **closure-residual inventories** (conservative PA/SA bases, decayed to 2032) — what will remain in each
tank *after* waste removal. SRS *current measured* waste composition (DWPF sludge batches, SWPF salt batches)
comes from SRNL qualification reports and is included as a separate dataset. See `reports/DB_README.md` § the
critical caveat.

## Repository layout

```
srs_tank_waste.db            # SQLite: 56.7k rows, 9 tables (the ML-ready artifact)
├── tanks                    # 51 SRS tanks: farm, type, capacity, status, closure
├── inventory_rad            # SRS per-tank × nuclide (57 nuclides), Ci — closure-residual + measured actuals
├── inventory_chem           # SRS per-tank × chemical (27 analytes), kg
├── current_inventory        # farm-level phase totals, snapshots 2025/2018/2016
├── current_waste_samples   # 607 rows: SRNL measured samples (SB11, SB10, Salt Batches 8–14, PRFT)
├── hanford_bbi              # Hanford BBI: 46,600 rows (54 radionuclides + 140 chemicals × 7 phases × 177 tanks)
├── hanford_bbi_volume       # Hanford per-tank phase volumes (kL)
├── sources                  # 19 source documents with doc numbers, years, URLs
└── dataset_notes            # methodology caveats per dataset

dashboard/
├── app.py                   # Streamlit app (6 interactive tabs, Plotly, DB-backed)
├── srs_hanford_comparison.html  # self-contained static HTML version (no server needed)
├── dashboard_data.json      # data payload for the HTML version
└── README.md

scripts/                     # fully reproducible pipeline (parse PDFs → build DB → export → dashboards)
├── locate_tables.py, parse_all_tables.py, parse_ftf_tables.py, parse_htf_pa_tables.py
├── parse_srnl_reports.py    # SRNL batch-report parser (6 table layouts)
├── build_database.py        # SQLite schema + load
├── add_current_waste_to_db.py
├── export_ml_data.py        # tidy long CSV + wide pivots for ML
├── build_dashboard_data.py, build_dashboard_html.py

data_raw/                    # 19 source PDFs (LWSP, PAs, SAs, SRNL reports) + extracted .txt
data_processed/              # parsed CSVs, JSON (ml_inventory_long.csv, wide pivots, hanford_bbi_*.json)
reports/DB_README.md         # data dictionary, validation log, caveats
```

## Quickstart

```bash
# dashboards
uv venv .venv --python 3.12 && uv pip install streamlit plotly pandas   # or your preferred installer
.venv/bin/streamlit run dashboard/app.py
#   → http://localhost:8635  (or whatever port Streamlit prints)

# or the zero-dependency version
open dashboard/srs_hanford_comparison.html

# query the database
sqlite3 srs_tank_waste.db "SELECT nuclide, SUM(value_ci) FROM inventory_rad
  WHERE dataset='htf_assigned_closure' GROUP BY nuclide ORDER BY 2 DESC LIMIT 10"
```

## Data sources (all public)

**SRS (12 + 7 documents, in `data_raw/` and registered in the `sources` table):**
- SRS Liquid Waste System Plan Rev 24 (SRMC-LWP-2023-00001, data as of 2025-09-30)
- Tank 16 Special Analysis for the HTF PA (SRR-CWDA-2014-00106) — Tables 6.2-2/3: assigned rad+chem for all 29 HTF tanks
- Tanks 5 & 6 SA for the FTF PA (SRR-CWDA-2012-00106) — Tables 6.1-1/2: all 22 FTF tanks
- HTF PA Rev 1 (SRR-CWDA-2010-00128) — Tables 3.4-9/10 (original per-tank basis)
- Tanks 18/19 SA + Closure Module (SRR-CWDA-2010-00106 / -00003) — measured actuals
- §3116 Basis documents (HTF draft, FTF final), HTF PA Rev 1, tank facts & closure fact sheets
- SRNL current-waste characterizations: SRNL-STI-2024-00492 (SB11 Tank 51), -2024-00240 (SB10 Tank 40),
  -2024-00436 (Salt Batches 8–9), -2025-00489 (Salt Batches 10–13), -2025-00012 (Salt Batch 14, Tank 21H),
  OSTI 2473257/2483548 (Tank 38 solids, PRFT batches 15/22/26)

**Hanford:** PNNL PHOENIX TankFarmService REST API — `BBIWaste` / `BBIVolume` for all 177 tanks
(effective 2025-10-01, decay date 2022-01-01). Upstream source is TWINS; official snapshot is HNF-EP-0182.

## Validation performed

- Parsed per-tank totals reproduce each source table's own "Total Curies by Tank" row (e.g. FTF tanks 25–28 = 1.2E+04, tank 34 = 1.2E+05)
- Tanks 18/19 residuals cross-checked across two independent documents — identical
- HTF assigned values match HTF PA 3.4-9 where no revision occurred; Tank 16 actuals match its SA tables
- Hanford pull: 177/177 tanks, 46,600 rows; site totals consistent with published BBI (~122.6 MCi)
- Streamlit app exercised via `streamlit.testing.v1.AppTest` (0 exceptions, drill-down + selectors tested)

## Caveats

- **Decay bases differ**: Hanford BBI decayed to 2022-01-01; SRS PA values to 2032; SRS farm totals are a 2025 measurement.
- **SRS per-tank = closure residuals** (4,000 gal/tank assigned basis, HTF max-of-group) — not current contents.
- **Chemical bases differ**: SRS per-tank kg are elements on residual sludge; Hanford kg include supernate salts.
- Ba-137m / Y-90 are daughters counted with parents at both sites — treat as families (Cs-137+Ba-137m, Sr-90+Y-90).

## License / data rights

The compiled dataset and code here are provided as-is for research use. The underlying source documents are
public DOE/NRC/SRNS publications; each remains the property of its issuing organization. No warranty is made
as to fitness for any regulatory or operational purpose.
