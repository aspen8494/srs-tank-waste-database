# SRS Tank Farm Waste Database — README

**Database file:** `srs_tank_waste.db` (SQLite)
**Generated:** October 2026 · Agent-assembled from public DOE/NRC/SRNS documents (all downloaded into `data_raw/`)

## What this is

A Best-Basis-Inventory-style database for the **Savannah River Site (SRS) F- and H-Area Tank Farms**
(51 underground HLW storage tanks), assembled from DOE Performance Assessments (PA), Special
Analyses (SA), Section 3116 Basis Documents, and the SRS Liquid Waste System Plan (LWSP).

## Headline numbers (current waste in the tanks)

| Phase | Volume (Mgal) | Activity (MCi) | As of |
|---|---|---|---|
| **Total tank farm waste** | **33.2** | **191** | 2025-09-30 (WCS report) |
| Sludge | 2.8 (9%) | 106 (54%) | 2025-09-30 |
| Salt waste (supernate + saltcake) | 30.4 (91%) | 85 (45%) | 2025-09-30 |
| — Supernate | 16.4 | 75 | 2025-09-30 |
| — Saltcake | 10.0 | 10 | 2025-09-30 |

Historical baselines (also in DB): 35.0 Mgal / 248 MCi (2018-12-31); 32.5 Mgal / 263 MCi (2016-12-31).
~46 MCi removed since the SRMC contract began (227 MCi at start; 181 MCi end of Dec 2025 per LWSP Rev 24 briefing).

## Schema

| Table | Rows | Content |
|---|---|---|
| `tanks` | 51 | all 51 tanks: farm, type (I/II/III/IIIA/IV), capacity, status, closure date, service function |
| `inventory_rad` | 4817 | long-format: tank × dataset × nuclide (57 nuclides), Ci, with basis + source |
| `inventory_chem` | 1987 | long-format: tank × dataset × chemical (27 analytes), kg |
| `current_inventory` | 15 | farm-level phase volumes & curies (2025, 2018, 2016 snapshots) |
| `sources` | 12 | document registry (title, doc number, year, URL, local file) |
| `dataset_notes` | — | methodology caveats per dataset |

### Radionuclide datasets (`inventory_rad.dataset`)
| dataset | tanks | meaning |
|---|---|---|
| `htf_assigned_closure` | 29 | HTF PA-assigned residual inventories at closure (Tank 16 SA Table 6.2-2), 54 nuclides, decayed to 2032 |
| `htf_pa_closure` | 29 | HTF PA Rev 1 Tables 3.4-9 (original estimates, same 54 nuclides) |
| `htf_annulus_assigned` | 8 | annulus (secondary containment) assigned inventories, tanks 9-16 |
| `ftf_assigned_closure` | 22 | revised FTF closure inventories (Tanks 5&6 SA Table 6.1-1), 51 nuclides |
| `tank18_19_actual` | 2 | tanks 18/19 measured actual residuals (54 nuclides) |
| `tank16_final_actual` / `tank16_annulus_actual` | 1 | tank 16 actual residual + annulus |

### Chemical datasets
Same structure: `htf_assigned_closure` (27 chemicals), `htf_pa_closure` (26), `ftf_assigned_closure` (18), actuals for 16/18/19.

## The critical caveat (read before ML!)

**SRS does not publish a per-tank "current waste" Best Basis Inventory like Hanford's.**
SRS tracks current composition in its internal **WCS (Waste Characterization System)** database,
which is not publicly released per-tank. What IS public at per-tank × per-nuclide/chemical granularity:

1. **Closure residual inventories** (what remains *after* waste removal & cleaning) — conservative PA
   bases, provided here for all 51 tanks via the HTF/FTF PA + SA tables. These are the same data DOE
   uses for the §3116 determinations and NRC consultation.
2. **Actual measured residuals** for the 6 closed-but-characterized tanks (5, 6, 12, 16, 18, 19).
3. **Farm-level phase totals** for the *current* waste (33.2 Mgal / 191 MCi with sludge/supernate/saltcake split).

For ML work, the closure-residual datasets give a rich 51-tank × 54-nuclide × 27-chemical matrix with
real inter-tank variation (max-of-group assignment in HTF; measured values in FTF closed tanks), but
they represent **post-cleanup residuals, not the current tank contents**. The `basis` column on every
row states which is which. Farm-level current composition context: salt waste is >95% Cs-137/Ba-137m;
sludge holds most actinides + Sr-90; typical supernate is ~5-7 M Na nitrate/nitrite.

## Files

- `srs_tank_waste.db` — the SQLite database
- `data_processed/ml_inventory_long.csv` — 6804 tidy rows (tank × analyte × dataset)
- `data_processed/wide_rad_assigned.csv` — wide pivot: 51 tanks × 54 nuclides
- `data_processed/wide_chem_assigned.csv` — wide pivot: 51 tanks × 27 chemicals
- `data_raw/` — all source PDFs + extracted text
- `scripts/` — parsing & DB build scripts (reproducible pipeline)

## Primary sources

| # | Document | Doc number | Year |
|---|---|---|---|
| 1 | SRS Liquid Waste System Plan Rev 24 | SRMC-LWP-2023-00001 | 2026 |
| 2 | SRS Liquid Waste System Plan Rev 22 | SRR-LWP-2009-00001 | 2019 |
| 3 | Tank 16 SA for HTF PA Rev 1 | SRR-CWDA-2014-00106 | 2015 |
| 4 | Tanks 5 & 6 SA for FTF PA Rev 1 | SRR-CWDA-2012-00106 | 2013 |
| 5 | Tanks 18 & 19 SA | SRR-CWDA-2010-00106 | 2011 |
| 6 | Closure Module Tanks 18/19 Rev 1 | SRR-CWDA-2010-00003 | 2011 |
| 7 | 3116 Basis HTF (draft) | DOE/SRS-WD-2013-001 | 2013 |
| 8 | 3116 Basis FTF (final) | DOE/SRS-WD-2012-001 | 2012 |
| 9 | HTF PA Rev 1 | SRR-CWDA-2010-00128 | 2012 |
| 10-12 | SRS tank facts sheet, closure fact sheet, tank history review (OSTI 2549244) | — | 2017-2024 |

## Validation performed

- Parsed per-tank totals reproduce each table's own "Total Curies by Tank" row (e.g. FTF tanks 25-28 = 1.2E+04, tank 34 = 1.2E+05).
- Tanks 18/19 residuals cross-check between the SA (SRR-CWDA-2010-00106) and the Closure Module (SRR-CWDA-2010-00003) — identical.
- HTF assigned values (SA 6.2-2) match HTF PA 3.4-9 for shared tanks where no revision occurred (e.g. tank 41 Cs-137 = 5,500 Ci in both).
- Tank 16 SA actuals (Sr-90 9.4E+03, Cs-137 <1.5E-02, Pu-238 4.6, Tc-99 1.7) match both the assigned table and SA Table 5.0-1.
- HTF assigned grand total: 3.11e+06 Ci; FTF: 3.28e+06 Ci (consistent with SA-reported totals).
