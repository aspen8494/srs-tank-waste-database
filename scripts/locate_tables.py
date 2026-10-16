#!/usr/bin/env python3
"""Locate SRS PA/SA inventory tables in extracted PDF text and report their token structure.

Writes a JSON index of table locations to data_processed/table_index.json and prints
compact summaries only (no big table dumps).
"""
import json
import re
import sys
from pathlib import Path

RAW = Path("/Users/aspen_mb/Documents/Savannah_RiverTF/data_raw")
OUT = Path("/Users/aspen_mb/Documents/Savannah_RiverTF/data_processed")
OUT.mkdir(exist_ok=True)

# Files to index
FILES = {
    "htf_sa_tank16": "Tank16_SpecialAnalysis_Rev1.txt",
    "ftf_sa_tank5_6": "SA_Tank5_6_FTF_full.txt",
    "sa_tank18_19": "Tank18_19_SpecialAnalysis.txt",
    "closure_mod_18_19": "ClosureModule_Tanks18_19.txt",
    "htf_pa": "HTF_PA_Rev1.txt",
}

# Table-title regexes of interest (title -> canonical key)
TABLES = [
    ("htf_sa_tank16", "assigned_rad_waste_tanks", r"Table 6\.2-2:\s+Assigned Radiological Inventory \(Ci\) at Closure Decayed to Year 2032"),
    ("htf_sa_tank16", "assigned_chem_waste_tanks", r"Table 6\.2-3:\s+Assigned Chemical Inventory \(kg\) at Closure"),
    ("htf_sa_tank16", "assigned_rad_annulus", r"Table 6\.2-4:\s+Assigned Annulus Radiological Inventory at Closure Decayed\s+to Year 2032"),
    ("htf_sa_tank16", "assigned_chem_annulus", r"Table 6\.2-5:\s+Assigned Annulus Chemical Inventory at Closure"),
    ("htf_sa_tank16", "tank16_final_rad", r"Table 5\.0-1:\s+Tank 16 Radionuclide Inventory \(Ci\)"),
    ("htf_sa_tank16", "tank16_final_chem", r"Table 5\.0-2:\s+Tank 16 Chemical Inventory \(kg\)"),
    ("htf_sa_tank16", "tank16_final_rad_annulus", r"Table 5\.0-3:\s+Tank 16 Annulus Radionuclide Inventory \(Ci\)"),
    ("htf_sa_tank16", "tank16_final_chem_annulus", r"Table 5\.0-4:\s+Tank 16 Annulus Chemical Inventory \(kg\)"),
    ("ftf_sa_tank5_6", "ftf_rad", r"Table 6\.1-1:\s+Revised FTF Radionuclide Inventories \(Ci\)"),
    ("ftf_sa_tank5_6", "ftf_chem", r"Table 6\.1-2:\s+Revised FTF Chemical Inventories \(kg\)"),
    ("ftf_sa_tank5_6", "ftf_annulus_rad", r"Table 6\.1-3"),
    ("ftf_sa_tank5_6", "ftf_annulus_chem", r"Table 6\.1-4"),
    ("sa_tank18_19", "tank18_19_rad", r"Table 5\.0-1:\s+Tanks 18 and 19 Radionuclide Inventories \(Ci\)"),
    ("sa_tank18_19", "tank18_19_chem", r"Table 5\.0-2:\s+Tanks 18 and 19 Chemical Inventories \(kg\)"),
    ("closure_mod_18_19", "t18_19_residual_rad", r"Table 4\.3-4:\s+Residual Radiological Inventories for Tanks 18 and 19"),
    ("closure_mod_18_19", "t18_19_residual_chem", r"Table 4\.3-5:\s+Residual Chemical Inventories for Tanks 18 and 19"),
    ("htf_pa", "htf_type1_rad", r"Table 3\.4-1"),
    ("htf_pa", "htf_type1_chem", r"Table 3\.4-2"),
    ("htf_pa", "htf_type2_rad", r"Table 3\.4-3"),
    ("htf_pa", "htf_type2_chem", r"Table 3\.4-4"),
    ("htf_pa", "htf_type4_rad", r"Table 3\.4-7"),
    ("htf_pa", "htf_type4_chem", r"Table 3\.4-8"),
]

NUM = re.compile(r"^-?\d+\.?\d*E[+-]\d+$|^-?\d+\.?\d*$|^(ND|<\s*\d\S*|Not\s+determined)$")


def main():
    index = {}
    for key, fname in FILES.items():
        p = RAW / fname
        if not p.exists():
            index[key] = {"error": "missing"}
            continue
        text = p.read_text(errors="replace")
        for _, tkey, pat in [t for t in TABLES if t[0] == key]:
            occ = [m.start() for m in re.finditer(pat, text)]
            index.setdefault(key, {})[tkey] = {
                "occurrences": occ,
                "count": len(occ),
                "title_snippet": text[occ[-1]:occ[-1] + 90].replace("\n", " ") if occ else "",
            }
    (OUT / "table_index.json").write_text(json.dumps(index, indent=1))
    # Compact print
    for key, tables in index.items():
        if "error" in tables:
            print(f"{key}: MISSING FILE")
            continue
        for tkey, info in tables.items():
            print(f"{key}.{tkey}: n={info['count']} at {info['occurrences'][:6]}")


if __name__ == "__main__":
    main()
