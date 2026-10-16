#!/usr/bin/env python3
"""Build the SRS Tank Farm Waste Database (SQLite) from parsed CSVs + curated metadata.

Schema (mirrors Hanford Best-Basis-Inventory concepts adapted to SRS):
  tanks               - one row per SRS waste tank (1..51): farm, type, capacity, status, construction, service
  sources             - document registry (id, title, doc_number, year, url, local_file)
  inventory_rad       - long format: (tank_id, dataset, nuclide, value_ci, value_flag, basis, source_id)
  inventory_chem      - long format: (tank_id, dataset, chemical, value_kg, value_flag, basis, source_id)
  current_inventory   - LWSP Rev 24 (Sept 30 2025 WCS) farm-level volumes & curies by phase
  residual_volumes    - actual/assigned residual volumes at closure per tank
  closure_history     - operational closure dates & methods for closed tanks
  dataset_notes       - caveats & methodology notes per dataset

Also exports tidy CSVs for ML: data_processed/ml_inventory_long.csv
"""
import csv
import json
import sqlite3
from pathlib import Path

BASE = Path("/Users/aspen_mb/Documents/Savannah_RiverTF")
OUT = BASE / "data_processed"
DB = BASE / "srs_tank_waste.db"

# ------------------------------------------------------------------ tank metadata
# Sources: 3116 Basis FTF Table 2.1-6 (FTF tanks), 3116 Basis HTF Table 2.1-6 (HTF tanks),
# LWSP Rev 22/24 Table 5-2 (service functions), srr_tank_closure.txt (closure dates)
TANKS = []
# FTF: Type I (1-8), Type III/IIIA (25,26,27,28,33,34,44,45,46,47), Type IV (17,18,19,20)
FTF = {
    "type": {**{t: "I" for t in range(1, 9)},
             **{t: "III/IIIA" for t in [25, 26, 27, 28, 33, 34, 44, 45, 46, 47]},
             **{t: "IV" for t in [17, 18, 19, 20]}},
    "cap": {**{t: 750000 for t in range(1, 9)}, **{t: 1300000 for t in [25, 26, 27, 28, 33, 34, 44, 45, 46, 47, 17, 18, 19, 20]}},
    "subtype3": {33: "III", 34: "III"},
}
HTF = {
    "type": {**{t: "I" for t in [9, 10, 11, 12]},
             **{t: "II" for t in [13, 14, 15, 16]},
             **{t: "III/IIIA" for t in [29, 30, 31, 32, 35, 36, 37, 38, 39, 40, 41, 42, 43, 48, 49, 50, 51]},
             **{t: "IV" for t in [21, 22, 23, 24]}},
    "cap": {**{t: 750000 for t in [9, 10, 11, 12]}, **{t: 1030000 for t in [13, 14, 15, 16]},
            **{t: 1300000 for t in [29, 30, 31, 32, 35, 36, 37, 38, 39, 40, 41, 42, 43, 48, 49, 50, 51, 21, 22, 23, 24]}},
    "subtype3": {29: "III", 30: "III", 31: "III", 32: "III"},
}
CLOSURE_DATES = {17: "1997-12", 20: "1997-07", 18: "2012", 19: "2012", 5: "2013", 6: "2013",
                 12: "2016", 16: "2015"}
SERVICE = {
    40: "DWPF feed tank", 51: "sludge batch prep / LTAD", 50: "Saltstone feed tank",
    49: "SWPF feed tank", 48: "precipitate storage", 39: "H-Canyon receipt",
    41: "salt blend tank", 42: "salt blend tank", 21: "TCCR / salt blend",
    43: "16H Evap support", 38: "16H Evap support", 37: "25H Evap support", 30: "25H Evap support",
    35: "storage (hybrid IIIA)", 33: "storage", 34: "storage (LTAD decants)",
    13: "sludge heel consolidation", 15: "sludge storage",
}
RESIDUAL_VOL = {  # gallons, actual where cleaned; assigned 4,000/5,000 for PA modeling
    18: 4000, 19: 2000, 5: 3300, 6: 3500, 16: 1000,
}

def build_tanks():
    rows = []
    for t in range(1, 52):
        if 1 <= t <= 8 or 17 <= t <= 20 or 25 <= t <= 28 or 33 <= t <= 34 or 44 <= t <= 47:
            farm = "FTF"
        else:
            farm = "HTF"
        src = FTF if farm == "FTF" else HTF
        ttype = src["type"].get(t, "")
        cap = src["cap"].get(t, "")
        subtype = src.get("subtype3", {}).get(t, "")
        closed = CLOSURE_DATES.get(t)
        status = "operationally closed" if closed else ("active / waste storage" if farm else "")
        rows.append({
            "tank_id": t, "farm": farm, "tank_type": subtype if subtype else ttype,
            "capacity_gal": cap, "status": status,
            "closure_date": closed or "",
            "service_function": SERVICE.get(t, "waste storage"),
            "residual_volume_gal": RESIDUAL_VOL.get(t, ""),
        })
    return rows


# ------------------------------------------------------------------ sources registry
SOURCES = [
    (1, "SRS Liquid Waste System Plan, Revision 24 (data as of 2025-09-30)", "SRMC-LWP-2023-00001 Rev 24", 2026,
     "https://www.energy.gov/srs/liquid-waste-system-plans", "LWSP_Rev24_Jan2026.pdf"),
    (2, "SRS Liquid Waste System Plan, Revision 22 (data as of 2018-12-31)", "SRR-LWP-2009-00001 Rev 22", 2019,
     "https://www.energy.gov/srs/liquid-waste-system-plans", "LWSP_Rev22_Jan2019.pdf"),
    (3, "Tank 16 Special Analysis for the HTF PA, Rev 1 (assigned per-tank inventories, Tables 5.0-1..3, 6.2-2..5)", "SRR-CWDA-2014-00106", 2015,
     "https://www.energy.gov/srs/articles/tank-16-special-analysis-rev-1", "Tank16_SpecialAnalysis_Rev1.pdf"),
    (4, "Tanks 5 and 6 Special Analysis for the FTF PA, Rev 1 (revised FTF inventories, Tables 6.1-1/6.1-2)", "SRR-CWDA-2012-00106", 2013,
     "https://www.nrc.gov/docs/ML1303/ML13030A075.pdf", "SA_Tank5_6_FTF_full.pdf"),
    (5, "Tanks 18 and 19 Special Analysis (actual residual inventories, Tables 5.0-1/5.0-2)", "SRR-CWDA-2010-00106", 2011,
     "https://www.energy.gov/srs/articles/tank-18tank-19-special-analysis", "Tank18_19_SpecialAnalysis.pdf"),
    (6, "Industrial Wastewater Closure Module for Tanks 18 and 19, Rev 1 (Tables 4.3-3/4.3-4)", "SRR-CWDA-2010-00003", 2011,
     "https://public.srs.gov/wp-content/uploads/2018/06/SRR-CWDA-2010-00003.pdf", "ClosureModule_Tanks18_19.pdf"),
    (7, "Basis for Section 3116 Determination for Closure of H-Tank Farm (Rev 0 draft, DOE/SRS-WD-2013-001)", "DOE/SRS-WD-2013-001", 2013,
     "https://www.energy.gov/srs/articles/draft-basis-section-3116-determination-closure-h-tank-farm", "3116_Basis_HTF_draft.pdf"),
    (8, "Basis for Section 3116 Determination for Closure of F-Tank Farm, Rev 0 (DOE/SRS-WD-2012-001)", "DOE/SRS-WD-2012-001", 2012,
     "https://www.energy.gov/srs/articles/basis-section-3116-determination-closure-f-tank-farm-srs-final", "3116_Basis_FTF_final.pdf"),
    (9, "Performance Assessment for the H-Area Tank Farm, Rev 1 (Tables 3.4-1..3.4-9)", "SRR-CWDA-2010-00128", 2012,
     "https://www.energy.gov/srs/articles/h-tank-farm-performance-assessment-rev-1", "HTF_PA_Rev1.pdf"),
    (10, "SRS High Level Waste Tank Facts fact sheet (farm composite inventory as of 2016-12-31)", "SRR fact sheet", 2017,
     "https://public.srs.gov/", "SRS_tank_facts_2017.pdf"),
    (11, "Operational Closure of Radioactive Liquid Waste Tanks (closure history)", "SRNS fact sheet", 2020,
     "https://public.srs.gov/wp-content/uploads/2021/02/srr_tank_closure.pdf", "srr_tank_closure.pdf"),
    (12, "Waste Tank Historical Review: layered saltcake/sludge histories (Tanks 14H, 26F, 28F, 44F)", "OSTI 2549244", 2024,
     "https://www.osti.gov/", "waste_tank_historical_review.pdf"),
]

# ------------------------------------------------------------------ current inventory (LWSP Rev 24, WCS 2025-09-30)
CURRENT = [
    # farm_level, phase, volume_mgal, activity_mci, as_of, source
    ("both", "total", 33.2, 191.0, "2025-09-30", 1),
    ("both", "sludge", 2.8, 106.0, "2025-09-30", 1),
    ("both", "salt_waste_total", 30.4, 85.0, "2025-09-30", 1),
    ("both", "supernate", 16.4, 75.0, "2025-09-30", 1),
    ("both", "saltcake", 10.0, 10.0, "2025-09-30", 1),
    ("both", "total_2018", 35.0, 248.0, "2018-12-31", 2),
    ("both", "sludge_2018", 2.8, 116.0, "2018-12-31", 2),
    ("both", "salt_waste_total_2018", 32.2, 132.0, "2018-12-31", 2),
    ("both", "supernate_2018", 16.2, 120.0, "2018-12-31", 2),
    ("both", "saltcake_2018", 16.0, 12.0, "2018-12-31", 2),
    ("both", "total_2016", 32.5, 263.0, "2016-12-31", 10),
    ("both", "sludge_2016", 2.4, 140.0, "2016-12-31", 10),
    ("both", "salt_2016", 32.5, 123.0, "2016-12-31", 10),
]

NOTES = [
    ("htf_assigned_rad", "HTF PA-assigned closure inventories per tank (Table 6.2-2 of Tank 16 SA). "
     "Conservative: max inventory within each tank grouping assigned to every tank in the group; "
     "residual volume basis 4,000 gal/tank (1,000 gal Tank 16); decayed to year 2032. NOT current waste — "
     "these are residuals that will remain AFTER closure cleaning."),
    ("htf_assigned_chem", "Same basis as htf_assigned_rad for 27 chemicals (kg)."),
    ("htf_annulus_rad", "Assigned annulus inventories (leakage into secondary containment pans), decayed to 2032. "
     "Type I/II tanks have annuli; Type III/IIIA/IV do not (zeros)."),
    ("ftf_rad", "Revised FTF closure inventories (Table 6.1-1 of Tanks 5&6 SA Rev 1). Tanks 1-4,7,8,25-28,33,34,44-47 projected; "
     "tanks 18/19 (and 5/6) actual measured residuals; tanks 17/20 not re-evaluated (closed 1997)."),
    ("ftf_chem", "Same basis as ftf_rad, 18 chemicals (kg)."),
    ("tank16_final", "Tank 16 actual final residual inventory (rad Ci + chem kg) from SA Tables 5.0-1/2, plus annulus (Table 5.0-3)."),
    ("tank18_19", "Tanks 18/19 actual residual inventories (SRR-CWDA-2010-00106 Tables 5.0-1/2, cross-checked vs Closure Module 4.3-3/4)."),
    ("current_inventory", "LWSP Rev 24 (Jan 2026), WCS Curie & Volume Inventory Report dated 2025-09-30. Farm-level phase totals."),
    ("htf_pa_closure", "HTF PA Rev 1 (SRR-CWDA-2010-00128) Tables 3.4-9/3.4-10 estimated per-tank closure "
     "inventories - the ORIGINAL PA basis. The Tank 16 SA Table 6.2-2 'assigned' values (dataset htf_assigned_closure) "
     "are the later-revised versions. Differences between the two datasets show the PA revision history."),
    ("IMPORTANT_caveat", "SRS does not publish a Hanford-style per-tank BBI with current analyte concentrations per phase. "
     "The per-tank chemical/radionuclide data in this DB are CLOSURE residual inventories (post-cleaning, conservative PA basis), "
     "NOT the current in-tank waste composition. Current waste composition is tracked in the DOE Waste Characterization System (WCS), "
     "not publicly released per-tank. Farm-level current data: 33.2 Mgal / 191 MCi (2025-09-30)."),
]

def load_csv(name):
    with open(OUT / name) as f:
        return list(csv.DictReader(f))

def is_num(s):
    try:
        float(s)
        return True
    except (TypeError, ValueError):
        return False

def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS tanks(
        tank_id INTEGER PRIMARY KEY, farm TEXT, tank_type TEXT, capacity_gal INTEGER,
        status TEXT, closure_date TEXT, service_function TEXT, residual_volume_gal REAL)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS sources(
        source_id INTEGER PRIMARY KEY, title TEXT, doc_number TEXT, year INTEGER, url TEXT, local_file TEXT)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS inventory_rad(
        id INTEGER PRIMARY KEY AUTOINCREMENT, tank_id INTEGER, dataset TEXT, nuclide TEXT,
        value_ci REAL, value_flag TEXT, basis TEXT, source_id INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS inventory_chem(
        id INTEGER PRIMARY KEY AUTOINCREMENT, tank_id INTEGER, dataset TEXT, chemical TEXT,
        value_kg REAL, value_flag TEXT, basis TEXT, source_id INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS current_inventory(
        id INTEGER PRIMARY KEY AUTOINCREMENT, scope TEXT, phase TEXT, volume_mgal REAL,
        activity_mci REAL, as_of TEXT, source_id INTEGER)""")
    cur.execute("""CREATE TABLE IF NOT EXISTS dataset_notes(dataset TEXT PRIMARY KEY, note TEXT)""")
    cur.execute("""CREATE INDEX IF NOT EXISTS idx_rad_tank ON inventory_rad(tank_id, dataset)""")
    cur.execute("""CREATE INDEX IF NOT EXISTS idx_chem_tank ON inventory_chem(tank_id, dataset)""")

    # tanks
    cur.execute("DELETE FROM tanks")
    for r in build_tanks():
        cur.execute("INSERT INTO tanks VALUES(?,?,?,?,?,?,?,?)",
                    (r["tank_id"], r["farm"], r["tank_type"], r["capacity_gal"], r["status"],
                     r["closure_date"], r["service_function"], r["residual_volume_gal"]))
    # sources
    cur.execute("DELETE FROM sources")
    for s in SOURCES:
        cur.execute("INSERT INTO sources VALUES(?,?,?,?,?,?)", s)
    # current inventory
    cur.execute("DELETE FROM current_inventory")
    for row in CURRENT:
        cur.execute("INSERT INTO current_inventory(scope,phase,volume_mgal,activity_mci,as_of,source_id) VALUES(?,?,?,?,?,?)", row)
    # notes
    cur.execute("DELETE FROM dataset_notes")
    for k, v in NOTES:
        cur.execute("INSERT INTO dataset_notes VALUES(?,?)", (k, v))

    # rad long-format
    cur.execute("DELETE FROM inventory_rad")
    def insert_rad(tank_id, dataset, analyte, val, flag, basis, src):
        if val is None or val == "":
            return
        cur.execute("INSERT INTO inventory_rad(tank_id,dataset,nuclide,value_ci,value_flag,basis,source_id) VALUES(?,?,?,?,?,?,?)",
                    (tank_id, dataset, analyte, val, flag, basis, src))

    # HTF assigned (29 tanks, 54 nuclides, wide->long)
    for r in load_csv("htf_assigned_rad_by_tank.csv"):
        tid = int(r["tank_id"])
        basis = r["basis"]
        for k, v in r.items():
            if k.startswith(("tank_id", "source", "basis", "farm", "sum_curies", "n_values", "parse_warning")):
                continue
            if is_num(v):
                insert_rad(tid, "htf_assigned_closure", k, float(v), "", basis, 3)
    # FTF assigned (22 tanks)
    for r in load_csv("ftf_assigned_rad_by_tank.csv"):
        tid = int(r["tank_id"])
        basis = r["basis"]
        for k, v in r.items():
            if k.startswith(("tank_id", "source", "basis", "farm", "sum_curies", "total_by_radionuclide")):
                continue
            if is_num(v):
                insert_rad(tid, "ftf_assigned_closure", k, float(v), "", basis, 4)
    # Tank 16 final (long already)
    for r in load_csv("tank16_final_residual.csv"):
        kind = r["kind"]
        val = r.get("value_final") or ""
        flag = "lt" if r.get("final_lt") in ("True", "true", "1") else ""
        if kind == "radionuclide":
            insert_rad(16, "tank16_final_actual", r["analyte"], val, flag, "actual final residual (2032)", 3)
        elif kind == "radionuclide_annulus":
            insert_rad(16, "tank16_annulus_actual", r["analyte"], val, flag, "actual annulus residual", 3)
    # Tanks 18/19 (long already, 2 tanks)
    for r in load_csv("tank18_19_residual.csv"):
        for tcol, tid in [("tank18", 18), ("tank19", 19)]:
            if r["kind"] == "radionuclide" and is_num(r.get(tcol)):
                insert_rad(tid, "tank18_19_actual", r["analyte"], r[tcol], "", "actual residual at closure", 5)
    # annulus assigned (nuclide rows x tanks 9-16)
    for r in load_csv("htf_assigned_annulus_rad_by_tank.csv"):
        for k, v in r.items():
            if k.startswith("tank_") and is_num(v):
                insert_rad(int(k.split("_")[1]), "htf_annulus_assigned", r["nuclide"], float(v), "", r["basis"], 3)

    # chem long-format
    cur.execute("DELETE FROM inventory_chem")
    def insert_chem(tank_id, dataset, analyte, val, flag, basis, src):
        if val is None or val == "":
            return
        cur.execute("INSERT INTO inventory_chem(tank_id,dataset,chemical,value_kg,value_flag,basis,source_id) VALUES(?,?,?,?,?,?,?)",
                    (tank_id, dataset, analyte, val, flag, basis, src))
    for r in load_csv("htf_assigned_chem_by_tank.csv"):
        tid = int(r["tank_id"])
        for k, v in r.items():
            if k.startswith(("tank_id", "source", "basis", "farm", "sum_kg", "parse_warning")):
                continue
            if is_num(v):
                insert_chem(tid, "htf_assigned_closure", k, float(v), "", r["basis"], 3)
    for r in load_csv("ftf_assigned_chem_by_tank.csv"):
        tid = int(r["tank_id"])
        for k, v in r.items():
            if k.startswith(("tank_id", "source", "basis", "farm", "sum_kg")):
                continue
            if is_num(v):
                insert_chem(tid, "ftf_assigned_closure", k, float(v), "", r["basis"], 4)
    for r in load_csv("tank16_final_residual.csv"):
        if r["kind"] == "chemical" and is_num(r.get("value_final")):
            flag = "lt" if r.get("final_lt") in ("True", "true", "1") else ""
            insert_chem(16, "tank16_final_actual", r["analyte"], r["value_final"], flag, "actual final residual", 3)
    for r in load_csv("tank18_19_residual.csv"):
        for tcol, tid in [("tank18", 18), ("tank19", 19)]:
            if r["kind"] == "chemical" and is_num(r.get(tcol)):
                insert_chem(tid, "tank18_19_actual", r["analyte"], r[tcol], "", "actual residual at closure", 5)


    # HTF PA estimated closure inventories (Tables 3.4-9/3.4-10) — original PA basis (pre-SA revision)
    for r in load_csv("htf_pa_rad_by_tank.csv"):
        tid = int(r["tank_id"])
        for k, v in r.items():
            if k.startswith(("tank_id", "source", "basis", "farm", "sum_curies", "parse_warning")):
                continue
            if is_num(v):
                insert_rad(tid, "htf_pa_closure", k, float(v), "", r["basis"], 9)
    for r in load_csv("htf_pa_chem_by_tank.csv"):
        tid = int(r["tank_id"])
        for k, v in r.items():
            if k.startswith(("tank_id", "source", "basis", "farm", "sum_kg", "parse_warning")):
                continue
            if is_num(v):
                insert_chem(tid, "htf_pa_closure", k, float(v), "", r["basis"], 9)

    conn.commit()

    # validation summary
    n_tanks = cur.execute("SELECT COUNT(*) FROM tanks").fetchone()[0]
    n_rad = cur.execute("SELECT COUNT(*), COUNT(DISTINCT tank_id), COUNT(DISTINCT nuclide) FROM inventory_rad").fetchone()
    n_chem = cur.execute("SELECT COUNT(*), COUNT(DISTINCT tank_id), COUNT(DISTINCT chemical) FROM inventory_chem").fetchone()
    n_cur = cur.execute("SELECT COUNT(*) FROM current_inventory").fetchone()[0]
    print(json.dumps({
        "db": str(DB), "tanks": n_tanks,
        "rad_rows": n_rad[0], "rad_tanks": n_rad[1], "rad_nuclides": n_rad[2],
        "chem_rows": n_chem[0], "chem_tanks": n_chem[1], "chem_analytes": n_chem[2],
        "current_rows": n_cur,
    }, indent=1))
    conn.close()

if __name__ == "__main__":
    main()
