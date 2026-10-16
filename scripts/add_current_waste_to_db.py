#!/usr/bin/env python3
"""Add SRNL current-waste characterization data (sludge batches, salt batches, PRFT) to the SQLite DB.

Creates tables: current_waste_samples (one row per sample×analyte×category).
Then re-exports ml long CSV including current-waste rows.
"""
import csv
import json
import sqlite3
from pathlib import Path

BASE = Path("/Users/aspen_mb/Documents/Savannah_RiverTF")
OUT = BASE / "data_processed"
DB = BASE / "srs_tank_waste.db"
DATA = json.load(open(OUT / "srnl_current_waste.json"))


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS current_waste_samples(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        sample TEXT, sample_type TEXT, report TEXT, sample_year INTEGER,
        matrix TEXT,            -- slurry / supernate / dried_solids / filtrate
        category TEXT,          -- element / anion / radionuclide
        analyte TEXT,
        value REAL, unit TEXT, flag TEXT, note TEXT)""")
    cur.execute("DELETE FROM current_waste_samples")

    n = 0

    def add(sample, stype, report, year, matrix, cat, an, val, unit, flag="", note=""):
        nonlocal n
        if val is None:
            return
        cur.execute("INSERT INTO current_waste_samples(sample,sample_type,report,sample_year,matrix,category,analyte,value,unit,flag,note) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (sample, stype, report, year, matrix, cat, an, val, unit, flag, note))
        n += 1

    # ---- Tank 51 Sludge Batch 11 (current DWPF feed prep batch) ----
    s11 = DATA["tank51_sludge_batch11"]
    rep, yr = s11["report"], s11["sample_year"]
    for el, d in s11["slurry_elemental_ug_per_g"].items():
        add("Tank 51 Sludge Batch 11", "sludge_batch", rep, yr, "slurry", "element", el,
            d["value"], "ug/g slurry", d["flag"])
    for nuc, d in s11["slurry_U_Pu_isotopes_dpm_per_g"].items():
        add("Tank 51 Sludge Batch 11", "sludge_batch", rep, yr, "slurry", "radionuclide", nuc,
            d["value"], "dpm/g slurry", d["flag"])
    for el, d in s11["supernate_elemental_mg_per_L"].items():
        add("Tank 51 Sludge Batch 11 (supernate)", "sludge_batch", rep, yr, "supernate", "element", el,
            d["value"], "mg/L", d["flag"])
    for an, d in s11["supernate_anions_mg_per_L"].items():
        unit = "M" if an == "Free OH" else ("dpm/mL" if an == "Cs-137" else "mg/L")
        cat = "radionuclide" if an == "Cs-137" else "anion"
        add("Tank 51 Sludge Batch 11 (supernate)", "sludge_batch", rep, yr, "supernate", cat, an,
            d["value"], unit, d["flag"])
    for el, d in s11["soluble_split_Na_Cr_Hg_S"].items():
        add("Tank 51 Sludge Batch 11", "sludge_batch", rep, yr, "slurry", "element", el + "_total",
            d["total_ug_per_g"], "ug/g slurry", note="total")
        add("Tank 51 Sludge Batch 11", "sludge_batch", rep, yr, "slurry", "element", el + "_soluble",
            d["soluble_mg_per_kg"], "mg/kg slurry", note="soluble fraction")

    # ---- DWPF Sludge Batch 10 (Tank 40 sample; full 61-nuclide list w/ Ci/gal) ----
    sb10 = DATA["dwpf_sludge_batch10"]
    for nuc, d in sb10["radionuclides"].items():
        add("Tank 40 Sludge Batch 10", "sludge_batch", sb10["report"], sb10["sample_year"],
            "slurry", "radionuclide", nuc, d["Ci_per_gal_slurry"], "Ci/gal slurry", d["flag"],
            f"uCi/g dried solids={d['uCi_per_g_dried_solids']}; wt%={d['wt_pct_total_solids']}")
        add("Tank 40 Sludge Batch 10", "sludge_batch", sb10["report"], sb10["sample_year"],
            "dried_solids", "radionuclide", nuc, d["uCi_per_g_dried_solids"], "uCi/g dried solids", d["flag"])

    # ---- SWPF Salt Batches 8-14 ----
    for rec in DATA["swpf_salt_batches"]:
        for sample, d in rec["samples"].items():
            yr = rec["sample_year"]
            for comp, v in d.get("chem_mg_per_L", {}).items():
                add(sample, "salt_batch", rec["report"], yr, "filtrate", "component", comp, v, "mg/L")
            for nuc, v in d.get("rad_pCi_per_mL", {}).items():
                add(sample, "salt_batch", rec["report"], yr, "filtrate", "radionuclide", nuc, v, "pCi/mL")
            for nuc, v in d.get("wac_limits", {}).items():
                if v is not None:
                    add(sample + " [WAC limit]", "salt_batch", rec["report"], yr, "filtrate", "wac_limit", nuc, v, "pCi/mL")

    # ---- PRFT batches (sludge washing/envelopment feed) ----
    pr = DATA["prft"]
    bcols = ["PRFT Batch 15", "PRFT Batch 22", "PRFT Batch 26"]
    for el, vals in pr["slurry_chem_by_element"].items():
        for b, v in zip(bcols, vals):
            add(b, "prft", pr["report"], pr["sample_year"], "slurry", "element", el, v, "ug/g slurry (verify)")
    for b, rads in pr["batch_rad_uCi_per_g"].items():
        for nuc, d in rads.items():
            add(f"PRFT Batch {b}", "prft", pr["report"], pr["sample_year"], "dried_solids",
                "radionuclide", nuc, d["uCi_per_g_dried_solids"], "uCi/g dried solids", d["flag"])
    conn.commit()

    # validation
    print(json.dumps({
        "rows_added": n,
        "by_sample_type": dict(cur.execute("SELECT sample_type, COUNT(*) FROM current_waste_samples GROUP BY sample_type")),
        "by_matrix": dict(cur.execute("SELECT matrix, COUNT(*) FROM current_waste_samples GROUP BY matrix")),
        "distinct_samples": [r[0] for r in cur.execute("SELECT DISTINCT sample FROM current_waste_samples")],
    }, indent=1))

    # ---- update sources registry ----
    new_sources = [
        (13, "Tank 51H Sludge Batch 11 qualification sample characterization", "SRNL-STI-2024-00492", 2024,
         "https://www.osti.gov/biblio/2476963", "SRNL_SludgeBatch11_Tank51_qualification.pdf"),
        (14, "DWPF Sludge Batch 10 radionuclide determination (Tank 40 sample)", "SRNL-STI-2024-00240", 2024,
         "https://www.osti.gov/biblio/2477578", "SRNL_DWPF_SludgeBatch10_radionuclides.pdf"),
        (15, "SWPF Salt Batch 8 and 9 qualification summary (FY23)", "SRNL-STI-2024-00436", 2024,
         "https://www.osti.gov/biblio/2483485", "SRNL_FY23_SaltWasteQualification.pdf"),
        (16, "SWPF Salt Batches 10-13 qualification summary (FY24)", "SRNL-STI-2025-00489", 2025,
         "https://www.osti.gov/biblio/2997593", "SRNL_FY24_SaltWasteQualification.pdf"),
        (17, "Salt Batch 14 qualification sample analytical results (Tank 21H)", "SRNL-STI-2025-00012", 2025,
         "https://www.osti.gov/biblio/2500772", "SRNL_SaltBatch14_Tank21H_qualification.pdf"),
        (18, "PRFT Batches 15/22/26 slurry and solids characterization", "SRNL (OSTI 2473257)", 2025,
         "https://www.osti.gov/biblio/2473257", "SRNL_Tank38_solids_analyses.pdf"),
        (19, "Tank 38 washed and dried solids chemical/radionuclide analyses", "SRNL-STI-2024-00506", 2024,
         "https://www.osti.gov/biblio/2483548", "SRNL_PRFT_Batches15_22_26.pdf"),
    ]
    for s in new_sources:
        cur.execute("INSERT OR REPLACE INTO sources VALUES(?,?,?,?,?,?)", s)
    conn.commit()
    conn.close()
    print("sources registered: 13-19")


if __name__ == "__main__":
    main()
