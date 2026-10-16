#!/usr/bin/env python3
"""Parse SRS PA/SA inventory tables from extracted PDF text into normalized CSVs.

Handles the flattened-text format produced by pymupdf where table rows appear as:
    Tank \n v1 \n v2 \n ... \n vN \n Tank2 \n ...
i.e. tank id followed by its row of values, and per-nuclide rows as:
    Nuclide \n v1 \n v2 ... \n Total

Outputs:
  data_processed/inventory_rad_waste_tanks.csv   (HTF SA Table 6.2-2 assigned rad, per tank x nuclide)
  data_processed/inventory_chem_waste_tanks.csv  (HTF SA Table 6.2-3 assigned chem, per tank x chemical)
  data_processed/inventory_rad_annulus.csv       (HTF SA Table 6.2-4 assigned annulus rad)
  data_processed/inventory_chem_annulus.csv      (HTF SA Table 6.2-5 assigned annulus chem)
  data_processed/tank16_final.csv                (Tank 16 SA Tables 5.0-1/2 final residual)
  data_processed/ftf_rad.csv                     (FTF SA Table 6.1-1 revised FTF rad)
  data_processed/ftf_chem.csv                    (FTF SA Table 6.1-2 revised FTF chem)
  data_processed/tank18_19.csv                   (T18/19 SA Table 5.0-1/2)
  parse_report.json                              (validation summary)
"""
import csv
import json
import re
from pathlib import Path

RAW = Path("/Users/aspen_mb/Documents/Savannah_RiverTF/data_raw")
OUT = Path("/Users/aspen_mb/Documents/Savannah_RiverTF/data_processed")
OUT.mkdir(exist_ok=True)

SCI = re.compile(r"^[<>]?\d*\.?\d+E[+-]?\d+$|^[<>]?\d*\.?\d+$|^ND$|^0\.0E[+-]?\d+$")


def read(fname):
    return (RAW / fname).read_text(errors="replace")


def next_title_pos(text, start, patterns):
    """Find the earliest position > start matching any pattern."""
    best = None
    for pat in patterns:
        m = re.search(pat, text[start:])
        if m and (best is None or start + m.start() < best):
            best = start + m.start()
    return best


def parse_number(tok):
    tok = tok.strip().replace(",", "")
    if tok in ("ND", "Not determined"):
        return None, "ND"
    lt = False
    if tok.startswith("<"):
        lt = True
        tok = tok[1:]
    try:
        v = float(tok)
    except ValueError:
        return None, "unparsed"
    return v, ("lt" if lt else "num")


def parse_table(text, start, end, tank_ids=None, nuclides=None):
    """Parse flattened rows into dict rows. Mode detection: rows keyed by tank id or by analyte name."""
    seg = text[start:end]
    # tokenize into lines
    lines = [l.strip() for l in seg.split("\n") if l.strip()]
    # drop page furniture
    drop = re.compile(r"^(Table \d|Tank 16 Special|Performance Assessment|SRR-CWDA|H-Tank Farm|Tanks 5 and 6|Revision \d|February 201|January 201|Page \d+|\[SRR|ND\s*$|Not determined|\d+ of \d+|Tank \d+ Special)", re.I)
    lines = [l for l in lines if not drop.match(l)]
    return lines


def segment_rows(lines, row_keys):
    """Group token stream into rows: a new row starts when a token matches a row key (nuclide name or tank id).
    Everything until the next row key belongs to the current row."""
    keys_re = re.compile(r"^(" + "|".join(row_keys) + r")$")
    rows = []
    current = None
    for tok in lines:
        if keys_re.match(tok):
            if current:
                rows.append(current)
            current = {"key": tok, "vals": []}
        elif current is not None:
            current["vals"].append(tok)
    if current:
        rows.append(current)
    return rows


NUCLIDES = [
    "Ac-227", "Al-26", "Am-241", "Am-242m", "Am-243", "Ba-137m", "C-14", "Cf-249", "Cf-251",
    "Cl-36", "Cm-243", "Cm-244", "Cm-245", "Cm-247", "Cm-248", "Co-60", "Cs-135", "Cs-137",
    "Eu-152", "Eu-154", "H-3", "I-129", "K-40", "Nb-94", "Ni-59", "Ni-63", "Np-237", "Pa-231",
    "Pd-107", "Pt-193", "Pu-238", "Pu-239", "Pu-240", "Pu-241", "Pu-242", "Pu-244", "Ra-226",
    "Ra-228", "Se-79", "Sm-151", "Sn-126", "Sr-90", "Tc-99", "Th-229", "Th-230", "Th-232",
    "U-232", "U-233", "U-234", "U-235", "U-236", "U-238", "Y-90", "Zr-93",
]

CHEMS = [
    "Ag", "Al", "As", "B", "Ba", "Cd", "Cl", "Co", "Cr", "Cs", "Cu", "F", "Fe", "Hg", "I",
    "K", "Mg", "Mn", "Mo", "Na", "Nb", "Ni", "NO2", "NO3", "Pb", "PO4", "Sb", "Se", "Si",
    "SO4", "Sr", "Ti", "Tl", "U", "V", "Zn", "Zr", "CN", "TOC", "PCB", "Pb-210",
]

HTF_WASTE_TANKS = [9, 10, 11, 12, 13, 14, 15, 16, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51]


def main():
    report = {}

    # ---------------- HTF SA: assigned rad (Table 6.2-2) ----------------
    text = read("Tank16_SpecialAnalysis_Rev1.txt")
    # body starts at second occurrence (74546); table spans until Table 6.2-3 body (89762)
    seg = text[74546:89762]
    lines = [l.strip() for l in seg.split("\n") if l.strip()]
    # token stream: strip continuation header lines
    drop = re.compile(r"^(Table 6\.2-2|Tank 16 Special|Performance Assessment|SRR-CWDA|H-Tank Farm|Revision 1|February 2015|\d+ of \d+|\(Continued\)|to Year 2032.*|Decayed.*)$", re.I)
    toks = [l for l in lines if not drop.match(l)]
    # Column headers: nuclide names appear as standalone tokens; tank ids are ints followed by their values
    # The layout: first all nuclide column headers (54 names), then per tank: id + 54 values + total
    # Find indices of tank ids in the token stream
    id_positions = [i for i, t in enumerate(toks) if re.match(r"^\d{1,2}$", t)]
    rows_out = []
    # Determine column order from the first header block (nuclide names in order before first tank id)
    first_id = id_positions[0]
    header_toks = toks[:first_id]
    col_names = [t for t in header_toks if not re.match(r"^[\d\.]+$", t)]
    report["htf_rad_columns_detected"] = len(col_names)
    for pos in id_positions:
        tid = int(toks[pos])
        # values: from pos+1 until next id position or end
        nxt = min([p for p in id_positions if p > pos], default=len(toks))
        vals = toks[pos + 1:nxt]
        # last value is Total Curies by Tank
        parsed = [parse_number(v) for v in vals]
        nums = [p[0] for p in parsed if p[0] is not None]
        flags = [p[1] for p in parsed]
        # map: first len(col_names) values to columns, last one is total
        rec = {"tank_id_htf": tid, "source": "SRR-CWDA-2014-00106 Table 6.2-2", "basis": "PA-assigned, decayed to 2032"}
        if len(nums) >= len(col_names) + 1:
            for name, v in zip(col_names, nums[:len(col_names)]):
                rec[name] = v
            rec["total_curies"] = nums[-1]
        else:
            rec["raw_values"] = vals
            rec["parse_warning"] = f"expected >= {len(col_names)+1} values, got {len(nums)}"
        rows_out.append(rec)
    report["htf_rad_rows"] = len(rows_out)
    with open(OUT / "inventory_rad_waste_tanks.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_out[0].keys()))
        w.writeheader()
        w.writerows(rows_out)

    # ---------------- HTF SA: assigned chem (Table 6.2-3) ----------------
    seg = text[89762:93824]
    lines = [l.strip() for l in seg.split("\n") if l.strip()]
    toks = [l for l in lines if not drop.match(l.replace("6.2-2", "6.2-3"))]
    id_positions = [i for i, t in enumerate(toks) if re.match(r"^\d{1,2}$", t)]
    first_id = id_positions[0]
    header_toks = toks[:first_id]
    col_names_c = [t for t in header_toks if not re.match(r"^[\d\.]+$", t)]
    rows_chem = []
    for pos in id_positions:
        tid = int(toks[pos])
        nxt = min([p for p in id_positions if p > pos], default=len(toks))
        vals = toks[pos + 1:nxt]
        parsed = [parse_number(v) for v in vals]
        nums = [p[0] for p in parsed if p[0] is not None]
        rec = {"tank_id_htf": tid, "source": "SRR-CWDA-2014-00106 Table 6.2-3", "basis": "PA-assigned, closure"}
        if len(nums) >= len(col_names_c) + 1:
            for name, v in zip(col_names_c, nums[:len(col_names_c)]):
                rec[name] = v
            rec["total_kg"] = nums[-1]
        else:
            rec["raw_values"] = vals
            rec["parse_warning"] = f"expected >= {len(col_names_c)+1} values, got {len(nums)}"
        rows_chem.append(rec)
    report["htf_chem_columns_detected"] = len(col_names_c)
    report["htf_chem_rows"] = len(rows_chem)
    with open(OUT / "inventory_chem_waste_tanks.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows_chem[0].keys()))
        w.writeheader()
        w.writerows(rows_chem)

    # Print compact validation summary
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
