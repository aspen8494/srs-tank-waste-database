#!/usr/bin/env python3
"""Build cross-site feature matrices for unsupervised waste-composition learning.

Stage 1 (this script): SQLite -> tidy composition vectors.
  - Hanford BBI: 433 tank x phase points, layer rows SUMMED to (tank, phase).
  - SRS SRNL measured samples: unit-harmonized to mass-fraction basis.
  - SRS closure-residual per-tank vectors (separate, flagged basis track).
  - Two chemistry panels (sludge-element, salt-anion) built on analytes BOTH
    sites actually report, so projection is closed-set.
  - Radionuclide panel: names canonicalized, decay-corrected to 2025-10-01,
    equilibrium daughters folded into parents.

Key math: CLR (centered log-ratio) is scale-invariant, so SRS units
(mg/L, ug/g slurry, M, Ci/gal...) need no density conversion -- every analyte
in one sample shares the same unknown scale factor, which CLR cancels.

Outputs (data_processed/unsupervised/):
  points_meta.csv        one row per point (site, basis, phase, volume, flags)
  X_sludge.csv           wide CLR-ready mass-fraction matrix (ppm basis)
  X_salt.csv             same, salt panel
  X_rad.csv              wide activity-fraction matrix (decay-corrected)
  presence_sludge.csv / presence_salt.csv / presence_rad.csv  0/1 masks
  build_report.json      panel definitions, unit conversion log, caveats
"""
import json
import math
import sqlite3
from collections import defaultdict
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

BASE = Path("/Users/aspen_mb/Documents/Savannah_RiverTF")
DB = BASE / "srs_tank_waste.db"
OUT = BASE / "data_processed" / "unsupervised"
OUT.mkdir(parents=True, exist_ok=True)

DECAY_REF = date(2025, 10, 1)  # common decay reference (Hanford BBI effective 2025-10-01)

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
report = {"decay_reference": DECAY_REF.isoformat(), "notes": [], "unit_conversions": [],
          "layer_sum_dedup": {}, "rad_dropped": {}, "rad_folded": {}}

# ---------------------------------------------------------------- panels ----
# Sludge-element panel: elements both sites report as ELEMENT mass.
# Hanford BBI element analytes (kg) vs SRS SRNL sludge-batch elements (ug/g slurry).
SLUDGE_PANEL = ["Al", "Ba", "B", "Ca", "Cd", "Cr", "Cu", "Fe", "Hg", "K", "La",
                "Li", "Mg", "Mn", "Mo", "Na", "Nd", "Ni", "P", "Pb", "Rh", "Ru",
                "S", "Sb", "Si", "Sn", "Sr", "Th", "Ti", "U", "V", "Zn", "Zr",
                "Ag", "Be", "Ce", "Co", "Zr"]
SLUDGE_PANEL = list(dict.fromkeys(SLUDGE_PANEL))  # dedupe keep order
# SRS reports S_total / S as sulfur; Hanford has S. SRS P = phosphorus vs Hanford PO4
# handled by converting Hanford PO4 -> P mass in sludge panel? No: Hanford sludge BBI
# reports both P and PO4? Check: keep P if present else derive from PO4 * (P/PO4=30.97/94.97)

# Salt-anion/cation panel: SWPF filtrate chemistry vs Hanford supernate chemistry.
SALT_PANEL = ["Na", "K", "Al", "Si", "Hg",           # cations (element mass)
             "OH", "NO3", "NO2", "CO3", "SO4", "PO4", "C2O4", "F", "Cl", "TOC"]
# SRS 'Free OH' (M) -> OH mass; 'Carbonate' -> CO3; SRS reports element mass for Na/K/Al/Si/Hg.
# Hanford 'Free OH' is reported as OH- kg; 'TIC as CO3' is CO3 kg.

# Radionuclide panel: canonical names; equilibrium daughters folded.
RAD_ALIAS = {  # SRS-style -> canonical (Hanford-style)
    "Pu-238": "238Pu", "Pu-239": "239Pu", "Pu-240": "240Pu", "Pu-241": "241Pu",
    "Pu-242": "242Pu", "U-233": "233U", "U-234": "234U", "U-235": "235U",
    "U-236": "236U", "U-238": "238U", "Sr-90": "90Sr", "Y-90": "90Y",
    "Tc-99": "99Tc", "I-129": "129I", "C-14": "14C", "H-3": "3H",
    "Cs-137": "137Cs", "Cs-134": "134Cs", "Cs-135": "135Cs", "Ba-137m": "137mBa",
    "Sn-126": "126Sn", "Np-237": "237Np", "Cm-244": "244Cm", "Am-241": "241Am",
    "Co-60": "60Co", "Ni-59": "59Ni", "Ni-63": "63Ni", "Se-79": "79Se",
    "Zr-93": "93Zr", "Nb-93m": "93mNb", "Sb-125": "125Sb", "Ru-106": "106Ru",
    "Cd-113m": "113mCd", "Sm-151": "151Sm", "Eu-154": "154Eu", "Eu-155": "155Eu",
    "Th-229": "229Th", "Th-230": "230Th", "Th-232": "232Th", "Pa-231": "231Pa",
    "Ra-226": "226Ra", "Ac-227": "227Ac", "Ce-144": "144Ce", "Pd-107": "Pd-107",
    "Sn-121m": "121mSn", "Te-125m": "125mTe", "Pm-147": "147Pm", "Pb-210": "210Pb",
    "Cl-36": "36Cl",
    # aliases whose SRS form differs only by position of mass number
    "Am-242m": "242mAm", "Am-243": "243Am", "Bk-247": "247Bk", "Cf-249": "249Cf",
    "Cf-250": "250Cf", "Cf-251": "251Cf", "Cf-252": "252Cf", "Cm-242": "242Cm",
    "Cm-243": "243Cm", "Cm-245": "245Cm", "Cm-246": "246Cm", "Cm-247": "247Cm",
    "Cm-248": "248Cm", "Nb-94": "94Nb", "Pu-244": "244Pu", "Ra-228": "228Ra",
    "U-232": "232U", "Ba-133": "133Ba", "Eu-152": "152Eu", "K-40": "40K",
    "Al-26": "26Al", "Pt-193": "193Pt",
}
# Hanford combined keys
HF_COMBINED = {"239/240Pu": None, "243/244Cm": None, "144Ce/Pr": "144Ce", "TotalAlpha": None,
               "228Ac": None, "228Ra": None, "228Th": None, "94Nb": "94Nb", "137mBa": None,
               "90Y": None, "242Cm": "242Cm", "151Sm": "151Sm", "152Eu": "152Eu",
               "59Ni": "59Ni", "63Ni": "63Ni", "226Ra": "226Ra", "227Ac": "227Ac",
               "93Zr": "93Zr", "231Pa": "231Pa", "79Se": "79Se", "121mSn": None}
# Equilibrium daughters in secular eq with parent -> fold into parent (avoid double count)
FOLD = {"90Y": "90Sr", "137mBa": "137Cs", "228Ac": None, "144Ce": "144Ce"}

# Half-lives (yr) for decay correction to DECAY_REF
HALF_LIFE_YR = {
    "3H": 12.32, "14C": 5700.0, "36Cl": 301000.0, "60Co": 5.272, "59Ni": 76000.0,
    "63Ni": 101.2, "79Se": 327000.0, "90Sr": 28.79, "90Y": 0.025, "93Zr": 1.53e6,
    "93mNb": 16.1, "94Nb": 20300.0, "99Tc": 2.111e5, "106Ru": 0.3125, "113mCd": 14.1,
    "121mSn": 55.0, "125Sb": 2.76, "125mTe": 0.0, "126Sn": 2.3e5, "129I": 1.57e7,
    "137Cs": 30.08, "137mBa": 0.00000086, "144Ce": 0.28, "147Pm": 2.62,
    "151Sm": 90.0, "152Eu": 13.54, "154Eu": 8.59, "155Eu": 4.75,
    "210Pb": 22.2, "226Ra": 1600.0, "227Ac": 21.77, "229Th": 7917.0,
    "230Th": 75400.0, "231Pa": 32760.0, "232Th": 1.405e10, "232U": 68.9,
    "233U": 1.592e5, "234U": 245500.0, "235U": 7.04e8, "236U": 2.342e7,
    "237Np": 2.144e6, "238Pu": 87.7, "238U": 4.468e9, "239Pu": 24110.0,
    "240Pu": 6563.0, "241Am": 432.2, "241Pu": 14.33, "242Cm": 0.446,
    "242Pu": 375000.0, "243Am": 7370.0, "243Cm": 29.1, "244Cm": 18.1,
}
MOLAR = {"PO4": 94.971, "P": 30.974, "CO3": 60.008, "C2O4": 88.019, "NO3": 62.004,
         "NO2": 46.006, "SO4": 96.06, "OH": 17.007, "TOC": 12.011, "F": 18.998,
         "Cl": 35.453}


def decay_factor(nuclide, from_date):
    """Activity multiplier to bring 'value Ci at from_date' to DECAY_REF."""
    hl = HALF_LIFE_YR.get(nuclide)
    if hl is None or hl <= 0.5:  # unknown or ~equilibrium/short: leave as-is
        return 1.0
    yrs = (DECAY_REF - from_date).days / 365.2425
    return math.exp(-math.log(2) * yrs / hl)


# ------------------------------------------------------- Hanford BBI rows ----
print("Loading Hanford BBI ...")
rows = con.execute("""
    SELECT tank, waste_phase, physical_state, analyte, inventory, units, qualifier, decay_date
    FROM hanford_bbi""").fetchall()

# Sum layer rows to (tank, phase, analyte). Qualifier: '<' wins (conservative), then blank.
agg = {}
n_groups = n_multi = 0
for r in rows:
    key = (r["tank"], r["waste_phase"], r["analyte"])
    v = r["inventory"]
    if v is None:
        continue
    q = (r["qualifier"] or "").strip()
    if key in agg:
        n_multi += 1
        cur_v, cur_q, unit, ddate = agg[key]
        agg[key] = (cur_v + v, "<" if ("<" in cur_q or "<" in q) else cur_q, unit, ddate)
    else:
        n_groups += 1
        agg[key] = (v, q, r["units"], r["decay_date"])
report["layer_sum_dedup"] = {
    "distinct_tank_phase_analyte": n_groups, "layer_rows_collapsed": n_multi}

# volume per (tank, phase) + waste_type labels (external validation for clustering)
vol = defaultdict(float)
wtype = defaultdict(set)
for r in con.execute("SELECT tank, waste_phase, waste_type, volume FROM hanford_bbi_volume"):
    vol[(r["tank"], r["waste_phase"])] += r["volume"] or 0.0
    wtype[(r["tank"], r["waste_phase"])].add(r["waste_type"] or "NA")

phases_by_tank = defaultdict(set)
for (tk, ph) in [(k[0], k[1]) for k in agg]:
    phases_by_tank[tk].add(ph)

hf_meta, hf_chem_raw, hf_rad_raw = [], defaultdict(dict), defaultdict(dict)
for (tk, ph, an), (v, q, unit, ddate) in agg.items():
    pid = f"HF|{tk}|{ph}"
    if unit == "kg":
        hf_chem_raw[pid][an] = (v, q)
    else:  # Ci
        # canonicalize + fold
        can = HF_COMBINED.get(an, an)
        if can is None:            # 239/240Pu & 243/244Cm combined keys & totals: drop for panel
            report["rad_dropped"][an] = report["rad_dropped"].get(an, 0) + 1
            continue
        if FOLD.get(can, can) != can:   # equilibrium daughter
            parent = FOLD[can]
            if parent:
                hf_rad_raw[pid][parent] = hf_rad_raw[pid].get(parent, 0.0) + v
                report["rad_folded"][can] = report["rad_folded"].get(can, 0) + 1
            continue
        d = date.fromisoformat(ddate) if ddate else DECAY_REF
        hf_rad_raw[pid][can] = hf_rad_raw[pid].get(can, 0.0) + v * decay_factor(can, d)

for tk, phs in phases_by_tank.items():
    for ph in phs:
        pid = f"HF|{tk}|{ph}"
        hf_meta.append({"point_id": pid, "site": "Hanford", "basis": "BBI_current",
                        "tank": tk, "phase": ph, "volume_kL": round(vol.get((tk, ph), 0.0), 2),
                        "waste_type": "|".join(sorted(wtype.get((tk, ph), {"NA"})))})

# Hanford chem conversions for panels:
#   PO4 -> P (x30.974/94.971) when P absent; 'Free OH' -> OH; 'TIC as CO3' -> CO3;
#   'Oxalate' -> C2O4; 'UTOTAL' -> U (sludge panel).
HF_CHEM_ALIAS = {"Free OH": "OH", "TIC as CO3": "CO3", "Oxalate": "C2O4", "UTOTAL": "U"}

def hf_chem_vector(pid, panel, kind):
    """Return dict analyte->kg for panel items; kind 'sludge'|'salt'."""
    src0 = hf_chem_raw.get(pid, {})
    src = {HF_CHEM_ALIAS.get(k, k): v for k, v in src0.items() if
           HF_CHEM_ALIAS.get(k, k) not in src0 or k != HF_CHEM_ALIAS.get(k, k)}
    # keep un-aliased originals too (alias only renames, never merges two distinct analytes)
    for k, v in src0.items():
        src.setdefault(k, v)
    out = {}
    for an in panel:
        if an == "P":  # sludge panel only; salt panel uses PO4 directly
            if "P" in src: out["P"] = src["P"][0]
            elif "PO4" in src: out["P"] = src["PO4"][0] * (30.974 / 94.971)
            continue
        if an in src: out[an] = src[an][0]
    return out

# ------------------------------------------------------ SRS sample rows ----
print("Loading SRS SRNL samples ...")
srs_rows = con.execute("""
    SELECT sample, sample_type, matrix, category, analyte, value, unit, flag, sample_year, report
    FROM current_waste_samples""").fetchall()

# density per filtrate sample (mg/L rows carry 'Density' component)
density = {}
for r in srs_rows:
    if r["analyte"] == "Density" and r["unit"] == "mg/L":
        density[r["sample"]] = r["value"]  # value like 1.31 g/mL (unit label is a DB artifact)

srs_meta, srs_chem_raw, srs_rad_raw = [], defaultdict(dict), defaultdict(dict)
for r in srs_rows:
    sm, mx, cat, an = r["sample"], r["matrix"], r["category"], r["analyte"]
    pid = f"SRS|{sm}|{mx}"
    v, unit, flag = r["value"], r["unit"], (r["flag"] or "").strip()
    if cat in ("component", "wac_limit"):
        continue
    if cat in ("element", "anion"):
        # harmonize to ppm-mass (ug per g of matrix); CLR cancels common scale per sample.
        if unit == "mg/L":
            d = density.get(sm, 1.0)  # g/mL; ug/g = mg/L / density
            mass_ppm = v / d if d else v
        elif unit in ("ug/g slurry", "ug/g slurry (verify)", "mg/kg slurry"):
            mass_ppm = v  # mg/kg == ug/g numerically
        elif unit == "M":  # molar (Free OH in supernate) -> mol/L * g/mol -> g/L -> /d -> ug/g
            mass_ppm = v * MOLAR.get({"Free OH": "OH"}.get(an, an), 100.0) * 1000.0 / density.get(sm, 1.0)
        else:
            continue
        srs_chem_raw[pid][an] = mass_ppm
    elif cat == "radionuclide":
        # canonicalize
        can = RAD_ALIAS.get(an, an)
        if can in ("Total alpha", "Total beta", "Total gamma", "Beta Count",
                   "Total alpha, Cs removed", "Total beta, Cs removed", "Total beta, without Cs"):
            continue
        if FOLD.get(can, can) != can:
            parent = FOLD[can]
            if parent:
                srs_rad_raw[pid][parent] = srs_rad_raw[pid].get(parent, 0.0) + v
            continue
        srs_rad_raw[pid][can] = srs_rad_raw[pid].get(can, 0.0) + v

# build SRS metadata: one point per sample-matrix
for r in con.execute("""SELECT DISTINCT sample, matrix, sample_year, report, sample_type
                        FROM current_waste_samples"""):
    sm, mx = r["sample"], r["matrix"]
    pid = f"SRS|{sm}|{mx}"
    if "[WAC limit]" in sm:
        continue  # WAC limit rows are limits, not measured waste
    srs_meta.append({"point_id": pid, "site": "SRS", "basis": "SRNL_measured",
                     "tank": sm, "phase": mx, "volume_kL": np.nan,
                     "sample_year": r["sample_year"], "report": r["report"]})

# SRS supernate anion mapping: Carbonate->CO3, Free OH(M)->OH, Nitrate->NO3 etc.
ANION_MAP = {"Nitrate": "NO3", "Nitrite": "NO2", "Carbonate": "CO3", "Sulfate": "SO4",
             "Phosphate": "PO4", "Oxalate": "C2O4", "Fluoride": "F", "Chloride": "Cl",
             "Free OH": "OH", "TOC": "TOC", "Formate": "Formate", "Bromide": "Br",
             "Sulfide": "Sulfide"}
for pid, d in list(srs_chem_raw.items()):
    nd = {}
    for an, v in d.items():
        nd[ANION_MAP.get(an, an)] = v
    srs_chem_raw[pid] = nd

# SRS filtrate cation cleanup: Na+/K+/OH- style names from component rows were category=
# 'component' -> skipped; element rows already Na, K, Al, Si, Hg.
# Salt batches: NO3-/NO2-/CO3-/SO42-/PO43-/C2O42-/HCO2-/F-/Cl- came in as components
# (category='component') -> we skipped them. Re-scan components for filtrate samples.
for r in srs_rows:
    sm, cat = r["sample"], r["category"]
    if cat != "component" or "[WAC" in sm:
        continue
    pid = f"SRS|{sm}|{r['matrix']}"
    an, v, unit = r["analyte"], r["value"], r["unit"]
    if unit == "mg/L" and density.get(sm):
        v = v / density[sm]
    m = {"Na+": "Na", "K+": "K", "Al": "Al", "Si": "Si", "Total Hg": "Hg",
         "OH-": "OH", "NO3-": "NO3", "CO32-": "CO3", "NO2-": "NO2",
         "SO42-": "SO4", "PO43-": "PO4", "C2O42-": "C2O4", "HCO2-": "Formate",
         "F-": "F", "Cl-": "Cl", "Total Organic Carbon": "TOC", "Methyl Hg": None,
         "Insoluble solids": None, "Density": None}
    tgt = m.get(an)
    if tgt:
        srs_chem_raw[pid][tgt] = v

# ------------------------------------------------ SRS closure track -------
print("Loading SRS closure-residual per-tank vectors ...")
cl_meta, cl_chem_raw, cl_rad_raw = [], defaultdict(dict), defaultdict(dict)
tank_farm = {t["tank_id"]: t["farm"] for t in
             con.execute("SELECT tank_id, farm FROM tanks")}
for r in con.execute("""SELECT ir.tank_id, ir.dataset, ir.nuclide, ir.value_ci, ir.basis
                        FROM inventory_rad ir WHERE ir.dataset IN
                        ('htf_assigned_closure','ftf_assigned_closure')"""):
    tid, ds = r["tank_id"], r["dataset"]
    pid = f"SRSCLOSE|T{tid}|{ds}"
    can = RAD_ALIAS.get(r["nuclide"], r["nuclide"])
    if FOLD.get(can, can) != can:
        parent = FOLD[can]
        if parent:
            cl_rad_raw[pid][parent] = cl_rad_raw[pid].get(parent, 0.0) + r["value_ci"]
        continue
    # closure rad decayed to 2032 already; correct BACK to 2025-10-01 (undecay) for panel? 
    # Physically: activity at 2025 = activity_at_2032 * 2^(6.25yr/HL). Valid only for
    # long-lived nuclides; short-lived ones are either in equilibrium (handled by FOLD)
    # or dominated by uncertainty -> cap at 10x (no unbounded growth).
    hl = HALF_LIFE_YR.get(can)
    v = r["value_ci"]
    if hl and hl > 5.0:
        v = v * min(2 ** ((2032 - 2025.75) / hl), 10.0)
    cl_rad_raw[pid][can] = cl_rad_raw[pid].get(can, 0.0) + v
for r in con.execute("""SELECT ic.tank_id, ic.dataset, ic.chemical, ic.value_kg, ic.basis
                        FROM inventory_chem ic WHERE ic.dataset IN
                        ('htf_assigned_closure','ftf_assigned_closure')"""):
    tid, ds = r["tank_id"], r["dataset"]
    pid = f"SRSCLOSE|T{tid}|{ds}"
    an = r["chemical"]
    if an == "Free OH": an = "OH"
    if an == "TIC as CO3": an = "CO3"
    cl_chem_raw[pid][an] = cl_chem_raw[pid].get(an, 0.0) + r["value_kg"]
for tid, farm in tank_farm.items():
    for ds in ("htf_assigned_closure", "ftf_assigned_closure"):
        pid = f"SRSCLOSE|T{tid}|{ds}"
        if cl_chem_raw.get(pid) or cl_rad_raw.get(pid):
            cl_meta.append({"point_id": pid, "site": "SRS", "basis": "closure_residual_2032",
                            "tank": f"Tank {tid} ({farm})", "phase": "closure_residual",
                            "volume_kL": np.nan})

# ------------------------------------------------------- assemble mats ----
print("Assembling matrices ...")

def build_matrix(meta_list, getters, panel, kind, tag):
    """getters: list of (pid_key -> raw dict) resolvers in priority order."""
    ids = [m["point_id"] for m in meta_list]
    X = pd.DataFrame(0.0, index=ids, columns=panel, dtype=float)
    P = pd.DataFrame(0, index=ids, columns=panel, dtype=np.int8)
    for m in meta_list:
        pid = m["point_id"]
        raw = None
        for g in getters:
            raw = g(pid)
            if raw:
                break
        if not raw:
            continue
        for an in panel:
            v = raw.get(an)
            if v is not None and v > 0 and np.isfinite(v):
                X.loc[pid, an] = v
                P.loc[pid, an] = 1
    return X, P

def g_hf(pid):
    return hf_chem_vector(pid, SLUDGE_PANEL, "sludge") if pid.startswith("HF|") else None

def g_srs_sludge(pid):
    return srs_chem_raw.get(pid)

def g_srs_salt(pid):
    d = srs_chem_raw.get(pid, {})
    return d if d else None

def g_close(pid):
    return cl_chem_raw.get(pid)

# SLUDGE panel: Hanford solid/slurry points + SRS sludge/dried samples + closure
hf_sludge_pts = [m for m in hf_meta if "Sludge" in m["phase"]]
srs_sludge_pts = [m for m in srs_meta if m["phase"] in ("slurry", "dried_solids")]
Xh, Ph = build_matrix(hf_sludge_pts, [g_hf], SLUDGE_PANEL, "sludge", "hf")
Xs, Ps = build_matrix(srs_sludge_pts, [g_srs_sludge], SLUDGE_PANEL, "sludge", "srs")
Xc, Pc = build_matrix(cl_meta, [g_close], SLUDGE_PANEL, "sludge", "close")
X_sludge = pd.concat([Xh, Xs, Xc])
P_sludge = pd.concat([Ph, Ps, Pc])
meta_sludge = hf_sludge_pts + srs_sludge_pts + cl_meta

# SALT panel: Hanford Supernatant + saltcake phases; SRS filtrates + supernate
def g_hf_salt(pid):
    return hf_chem_vector(pid, SALT_PANEL, "salt") if pid.startswith("HF|") else None

hf_salt_pts = [m for m in hf_meta if "Saltcake" in m["phase"] or m["phase"] == "Supernatant"]
srs_salt_pts = [m for m in srs_meta if m["phase"] in ("filtrate", "supernate")]
Xh2, Ph2 = build_matrix(hf_salt_pts, [g_hf_salt], SALT_PANEL, "salt", "hf")
Xs2, Ps2 = build_matrix(srs_salt_pts, [g_srs_salt], SALT_PANEL, "salt", "srs")
X_salt = pd.concat([Xh2, Xs2])
P_salt = pd.concat([Ph2, Ps2])
meta_salt = hf_salt_pts + srs_salt_pts

# RAD panel: all Hanford phases + SRS samples + closure
def g_hf_rad(pid): return hf_rad_raw.get(pid)
def g_srs_rad(pid): return srs_rad_raw.get(pid)
def g_close_rad(pid): return cl_rad_raw.get(pid)

RAD_PANEL = sorted(set(HALF_LIFE_YR) & set(list(hf_rad_raw.values())[0].keys() if hf_rad_raw else set()) |
                   set())
# simpler: union of canonical keys seen at both sites
hf_rad_keys = set()
for d in hf_rad_raw.values(): hf_rad_keys |= set(d)
srs_rad_keys = set()
for d in srs_rad_raw.values(): srs_rad_keys |= set(d)
cl_rad_keys = set()
for d in cl_rad_raw.values(): cl_rad_keys |= set(d)
RAD_PANEL = sorted((hf_rad_keys | srs_rad_keys | cl_rad_keys))
Xr_hf, Pr_hf = build_matrix(hf_meta, [g_hf_rad], RAD_PANEL, "rad", "hf")
Xr_srs, Pr_srs = build_matrix(srs_meta, [g_srs_rad], RAD_PANEL, "rad", "srs")
Xr_cl, Pr_cl = build_matrix(cl_meta, [g_close_rad], RAD_PANEL, "rad", "close")
X_rad = pd.concat([Xr_hf, Xr_srs, Xr_cl])
P_rad = pd.concat([Pr_hf, Pr_srs, Pr_cl])
meta_rad = hf_meta + srs_meta + cl_meta

# ------------------------------------------------------------- write out ----
def write_pair(X, P, meta, name):
    X.round(6).to_csv(OUT / f"X_{name}.csv")
    P.to_csv(OUT / f"presence_{name}.csv")
    pd.DataFrame(meta).to_csv(OUT / f"meta_{name}.csv", index=False)

write_pair(X_sludge, P_sludge, meta_sludge, "sludge")
write_pair(X_salt, P_salt, meta_salt, "salt")
write_pair(X_rad, P_rad, meta_rad, "rad")

report["panels"] = {
    "sludge": SLUDGE_PANEL, "salt": SALT_PANEL, "rad": RAD_PANEL,
    "sludge_n": len(meta_sludge), "salt_n": len(meta_salt), "rad_n": len(meta_rad)}
report["counts"] = {
    "hf_points": len(hf_meta), "hf_sludge": len(hf_sludge_pts), "hf_salt": len(hf_salt_pts),
    "srs_samples": len(srs_meta), "srs_sludge": len(srs_sludge_pts),
    "srs_salt": len(srs_salt_pts), "srs_closure": len(cl_meta)}
# coverage diagnostics
for nm, P, meta in [("sludge", P_sludge, meta_sludge), ("salt", P_salt, meta_salt),
                    ("rad", P_rad, meta_rad)]:
    hf_ids = [m["point_id"] for m in meta if m["site"] == "Hanford"]
    srs_ids = [m["point_id"] for m in meta
               if m["site"] == "SRS" and m["basis"] == "SRNL_measured" and m["point_id"] in P.index]
    hf_cov = P.loc[hf_ids].mean(axis=1)
    srs_cov = P.loc[srs_ids].mean(axis=1)
    report[f"{nm}_coverage"] = {
        "hf_mean_frac_analytes": round(float(hf_cov.mean()), 3),
        "srs_mean_frac_analytes": round(float(srs_cov.mean()), 3),
        "srs_points_with_any_data": int((P.loc[srs_ids].sum(axis=1) > 0).sum()),
        "srs_points_total": len(srs_ids)}

# DL/2 handling for below-detection '<' values (both sites): the reported number
# is the detection limit; substitute DL/2 (standard practice) and flag presence.
n_dl = 0
for r in srs_rows:
    if (r["flag"] or "").strip() != "<":
        continue
    sm, cat = r["sample"], r["category"]
    pid = f"SRS|{sm}|{r['matrix']}"
    an = r["analyte"]
    can = ANION_MAP.get(an, an) if cat == "anion" else an
    if cat in ("element", "anion") and pid in srs_chem_raw and can in srs_chem_raw[pid]:
        srs_chem_raw[pid][can] = srs_chem_raw[pid][can] / 2.0
        n_dl += 1
report["srs_dl_halved"] = n_dl
# Hanford '<' rows were summed as-is during layer collapse; BBI reports the actual
# estimate below DL -- treat as-is (standard BBI practice), log count.
report["hf_below_detection_rows"] = int(sum(1 for v, q, *_ in agg.values() if "<" in q))

json.dump(report, open(OUT / "build_report.json", "w"), indent=2, default=str)
print(json.dumps({k: report[k] for k in ("counts", "sludge_coverage", "salt_coverage",
                                          "rad_coverage", "srs_dl_halved",
                                          "hf_below_detection_rows")}, indent=2))
print(f"\nDone. Files in {OUT}")
