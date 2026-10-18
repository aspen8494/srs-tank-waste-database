# Unsupervised Cross-Site Waste Taxonomy — Methods & Findings

**Date:** 2026-10-16/17
**Code:** `scripts/build_unsupervised_features.py` · `scripts/run_unsupervised_clustering.py` · `scripts/build_unsupervised_dashboard.py`
**Data:** `srs_tank_waste.db` — Hanford BBI (PNNL PHOENIX pull; per-tank effective dates 2015-07-01 … 2026-05-01; decay dates 2015-07-01 / 2022-01-01) and SRS public data (SRNL qualification reports 2023–2025; HTF/FTF PA/SA closure inventories)
**Dashboard:** `dashboard/unsupervised_analysis.html` (self-contained, no dependencies)

---

## 1. Objective and design choices

Goal: an unsupervised cross-site similarity mapping between Hanford (177 tanks, Best-Basis
Inventory, *current* waste) and SRS Savannah River (51 tanks; current composition known only
through 17 SRNL qualification samples; per-tank public data are closure residuals) — which
Hanford tank-phases are compositionally most similar to SRS sludge batches, salt batches, and
processing-stream samples, and which analytes drive the separation.

Locked-in design (user decisions):

1. **Primary goal** — cross-site similarity mapping (not taxonomy discovery alone).
2. **Point granularity** — two-stage: cluster Hanford tank×phase points, project SRS samples onto the taxonomy.
3. **SRS basis handling** — two labeled tracks: SRNL measured samples ("current") and closure-residual
   vectors ("closure-2032"), never mixed without a basis flag.
4. **Feature spaces** — chemistry primary (two panels), radionuclide signature secondary.
5. **Deliverable** — reproducible scripts + self-contained HTML dashboard + methods report.

## 2. Feature engineering

### 2.1 Units and scale invariance

The two sites report concentrations in incompatible units — Hanford kg-inventories per tank-phase;
SRS mg/L (with density 1.27–1.33 g/mL), µg/g slurry, mg/kg slurry, molar, pCi/mL, dpm/g, Ci/gal.
Because every analyte within one sample shares a single unknown scale factor, and the centered
log-ratio (CLR) transform is scale-invariant, CLR removes the entire unit problem: a composition
multiplied by any constant has the identical CLR coordinates. Physical conversions are still applied
where possible (mg/L→µg/g via measured density; Free OH molar→OH mass; PO₄→P for the sludge panel)
so reported mass fractions are physically meaningful — but no comparison depends on them.

### 2.2 Panels (closed analyte sets)

| Panel | n Hanford points | Features kept (presence floor) | Dropped |
|---|---|---|---|
| Sludge elements | 158 | 25 (floor 0.40) | Rh, Ru, Sn, S (rarely reported) |
| Salt anions/cations | 258 | 15 (floor 0.70) | — |
| Radionuclides | 415 | 41 (floor 0.50) | 34 rare nuclides (e.g. Cf, Bk isotopes, K-40, Al-26) |

Sludge panel: Al Ba B Ca Cd Cr Cu Fe Hg K La Li Mg Mn Mo Na Nd Ni P Pb Sb Si Sn Sr Th Ti U V Zn Zr Ag Be Ce Co (S dropped).
Salt panel: Na K Al Si Hg OH NO₃ NO₂ CO₃ SO₄ PO₄ C₂O₄ F Cl TOC.
Rad panel: 41 nuclides including ³H ¹⁴C ⁶⁰Co ⁹⁰Sr ⁹⁹Tc ¹⁰⁶Ru ¹²⁵Sb ¹²⁶Sn ¹²⁹I ¹³⁷Cs ¹⁵¹Sm ¹⁵²Eu ¹⁵⁴Eu ¹⁵⁵Eu ²²⁶Ra ²²⁷Ac ²²⁹Th ²³¹Pa ²³²Th ²³²U ²³³U ²³⁴U ²³⁵U ²³⁶U ²³⁷Np ²³⁸Pu ²³⁸U ²³⁹Pu ²⁴⁰Pu ²⁴¹Am ²⁴¹Pu ²⁴²Cm ²⁴²Pu ²⁴³Am ²⁴³Cm ²⁴⁴Cm ⁵⁹Ni ⁶³Ni ⁷⁹Se ⁹³Zr ⁹³ᵐNb (+¹²⁸Sn-type trace nuclides in some SRS samples).

### 2.3 Missing data = neutral, not zero

An absent measurement is **not** a zero concentration. Each point's present analytes are closed
to mass fractions; the geometric mean g of the point's present values is computed; absent
analytes are replaced by g, giving them CLR coordinate 0 — the neutral point of Aitchison
geometry, exerting **zero pull** on any distance or cluster boundary (in contrast to zero
imputation, which fabricates strong "absence" signals).

### 2.4 Below-detection values

SRS '<' entries (n=38) are halved (DL/2, standard practice). Hanford BBI sub-DL estimates
(n=4,792 tank-phase-analyte keys) enter as reported, per standard BBI interpretation.

### 2.5 Radionuclide corrections

- Names canonicalized (SRS `Pu-238` ↔ Hanford `238Pu` etc., both directions, including
  Am/Cm/Cf/Bk style differences).
- Secular-equilibrium daughters folded into parents: ⁹⁰Y→⁹⁰Sr, ¹³⁷ᵐBa→¹³⁷Cs.
- Decay-corrected to the common reference 2025-10-01 from each Hanford tank's own BBI decay
  date (2015-07-01 for 38 tanks, 2022-01-01 for 139).
- Short-lived ¹⁰⁶Ru (t½ 0.31 y) and ¹⁴⁴Ce (t½ 0.28 y) — inventoried only in trace amounts,
  effectively vanished by 2025; kept where the 2025-corrected inventory survives.
- SRS closure vectors (decayed to 2032) corrected backwards to 2025-10-01 where half-life > 5 y,
  capped at 10× to avoid unbounded growth; shorter-lived species left as-is (conservative).

### 2.6 Hanford layer dedup

BBI rows collapse to (tank, phase, analyte): 8,275 layer duplicates (tanks with multiple waste
layers — e.g. U110's CWR1/1C/R1 sludges) summed into 36,421 distinct keys; `<` qualifier
propagates if any summed component was sub-detection.

## 3. Models

- **CLR** on the closed compositions (Aitchison geometry) — see §2.1.
- **Ward hierarchical clustering** (final taxonomy) — deterministic, produces dendrograms,
  robust to the neutral-replacement geometry. K per panel chosen by max silhouette over a
  KMeans k=2..12 sweep, restricted to the interpretable range 4–9.
- **KMeans** (k-sweep) — model-selection instrument; agreement with Ward quantified by ARI.
- **HDBSCAN** (min_cluster_size ≈ n/25, min_samples=1) — density-based anomaly flagging only.
- **UMAP** (n_neighbors=15, min_dist=0.1) — 2-D visualization; SRS points projected via
  `reducer.transform()`, never re-fit, so they sit relative to the Hanford geometry.
- **Projection metrics** — per SRS point: nearest Ward centroid (Euclidean on CLR), percentile
  of its distance within the target cluster's own member-to-centroid distance distribution,
  and top-5 nearest Hanford tank-phases by **shared-support Aitchison distance**
  (only analytes measured on both sides count; k = support size reported alongside).

## 4. Results summary

### 4.1 Hanford taxonomy quality

| Panel | n | K | Ward silhouette | ARI vs KMeans | Cophenetic | HDBSCAN k / noise |
|---|---|---|---|---|---|---|
| Sludge elements | 158 | 6 | 0.248 | 0.79 | 0.77 | 7 / 73 |
| Salt anions/cations | 258 | 4 | 0.286 | 0.75 | 0.76 | 7 / 123 |
| Radionuclides | 415 | 8 | 0.192 | 0.71 | 0.74 | 4 / 153 |

External validation: clusters cross-tabulate cleanly against BBI waste_type codes and phases
(e.g. salt panel C0 = CWP2/CWR1 supernatants; C2 = A2 saltcake-slurry supernates), without
those labels ever entering the fit. Moderate silhouettes reflect genuine waste heterogeneity
(the BFI itself spans continuous blending gradients), not algorithm failure — Ward/KMeans
agreement (ARI 0.71–0.79) shows the structure is method-stable.

### 4.2 Cross-site findings (headline)

Context for interpreting distances: within Hanford's own clusters, nearest-neighbor shared-Aitchison
distances run median 3.3 / p90 6.4 / max 10.7 (sludge panel), median 1.5 / p90 3.9 / max 9.1 (salt
panel), and median 3.1 / p90 8.9 / max 16.9 (rad panel). An SRS top-analog distance below p90 means
"as close as a typical Hanford tank-phase is to its own cluster-mates."

1. **SRS salt batches have real Hanford analogs in both chemistry and radionuclide space.**
   In *radionuclide* space the SWPF batches (10–13) project at the 68–74th percentile of their
   cluster with top-analog distances 2.6–3.4 — closer than the Hanford median same-cluster
   neighbor (3.12): genuinely strong analogs. Their nearest radionuclide-space analogs are
   AP108/AZ102/AN104/BX104 supernates — high-¹³⁷Cs salt liquors. In *salt-chemistry* space the
   same batches sit at the 96.9–98.2nd percentile (distances 3.78–5.38 vs p90 3.93): at or just
   beyond the cluster edge — near-analogs, not twins. The consistent pairing is physical:
   B108/CWP2 and BX104/CWR1 supernates (boehmite/zeolite-aged salt waste); the higher-nitrate
   2024–25 batches (10, 13) map to the CWR1-type cluster.
2. **PRFT batches (DWPF MST/SS feed) are outside Hanford's taxonomy.** All three PRFT batches sit
   at the 100th percentile of their assigned sludge cluster; in rad space their top analogs
   (11.2–11.4, k≈9) exceed Hanford's p90 (8.86). Driver: their monosodium-titanate (MST) content
   (Ti ≈ 12,200–16,200 µg/g) — an engineered sorbent Hanford does not use. Their sludge-space
   cluster membership rests on only 4 shared analytes (weak support), so "no Hanford analog" is
   the correct reading.
3. **SRS sludge batches land within Hanford's normal sludge spread — at its outer half.**
   SB11 (Tank 51) projects 94.4th percentile but its top-analog distance (5.31 over k=4) is
   *below* Hanford's same-cluster p90 (6.42): U104 sludge solid is a fair analog (REDOX-type,
   similar Al/Fe/U balance), though measured on only 4 shared elements. SB10 has no element
   chemistry (rad-only report), so its sludge-space projection is correctly refused
   (insufficient data) rather than fabricated; in rad space its top analogs are T201/T204
   supernates at 9.6–11.3 (k=10–12), above p90 — SRS sludge-batch rad signatures are more
   Cs-loaded than Hanford sludge phases.
4. **Anomaly flags (HDBSCAN outlier score > 0.85):** 87 sludge-panel points, 138 salt-panel
   points, and 1 rad-panel point (BX105-class saltcake solid). The chem-space flags concentrate
   in tank-phases with unusual layered waste types; rad space is much more homogeneous. All are
   candidates for data-quality review rather than confirmed errors — see the dashboard's
   Anomalies tab for the ranked list.

### 4.3 Coverage honesty

SRS measured samples carry 37% (sludge) / 77% (salt) / 25% (rad) of the panel analytes on
average — SRNL qualification panels differ by matrix. Projection percentiles and support sizes
(k) quantify how much measurement each analog claim rests on. SB10 slurry/dried and SB14
filtrate have rad-only or no shared chemistry; they are reported as "insufficient data" for the
chemistry panels — never imputed.

## 5. Caveats

1. **Basis asymmetry (the big one).** SRS per-tank vectors are closure residuals (conservative
   PA bases, decayed to 2032, max-of-group assignments) — post-cleaning remains, not current
   waste. They appear only in the flagged closure track. SRS *current* composition exists
   publicly only as the 17 SRNL samples. Hanford's BBI is current waste. Large projection
   percentiles mean "no true analog at Hanford" — informative, not erroneous.
2. Hanford decay dates vary by tank vintage (2015 vs 2022); the 2025-10-01 correction
   normalizes them but cannot recover waste transfers after each tank's effective date.
3. Hanford organic analytes (DVP list: phthalates, ketones, aromatics) are excluded by the
   presence floors and would need a dedicated organics panel.
4. SRS closure chem panel is 18–27 analytes, HTF/FTF differ (18 vs 27) — closure-track
   comparisons across farms carry that asymmetry.
5. The salt panel's Formate was dropped (reported by only 3 Hanford tanks) even though SRS
   reports it; formate-driven differences between sites are therefore invisible in this panel.
6. UMAP is for visualization; cluster assignments come from Ward on full CLR space.

## 6. Reproducibility

```bash
cd Savannah_RiverTF
source .venv/bin/activate            # python 3.12; scikit-learn, umap-learn, hdbscan, pandas
python scripts/build_unsupervised_features.py       # DB -> X_*.csv, presence_*.csv, meta_*.csv
python scripts/run_unsupervised_clustering.py       # -> clustering_results.json, X_*_clr.csv
python scripts/build_unsupervised_dashboard.py      # -> dashboard/unsupervised_analysis.html
open dashboard/unsupervised_analysis.html
```

Artifacts in `data_processed/unsupervised/`: `X_sludge.csv` `X_salt.csv` `X_rad.csv`
(mass/activity fractions), `presence_*.csv` (0/1 masks), `meta_*.csv` (per-point site/basis/
phase/volume/waste_type), `X_*_clr.csv` (CLR matrices), `clustering_results.json` (everything:
sweeps, labels, profiles, dendrograms, projections, outlier scores), `panel_defs.json`,
`build_report.json`.

Random seeds fixed (numpy 42, UMAP random_state=42) — reruns reproduce exactly, except UMAP
coords may differ slightly across library versions (labels and all distances unaffected).
