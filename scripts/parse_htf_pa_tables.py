#!/usr/bin/env python3
"""Parse HTF PA Rev 1 Tables 3.4-9 (rad, Ci) and 3.4-10 (chem, kg) — per-tank closure estimates for all 39 HTF tanks.

Layout: rows = tanks, columns = nuclides/chemicals, split across page blocks.
Rad blocks: (462120,465725),(465725,469458),(469458,473212),(473212,476738)
Chem blocks: (476738, ~480800) cols Ag..I ; (~480800, 485308) cols Mn..Zn  (find 'Continued' boundary)
Output: data_processed/htf_pa_rad_by_tank.csv, htf_pa_chem_by_tank.csv
"""
import csv
import json
import re
from pathlib import Path

RAW = Path("/Users/aspen_mb/Documents/Savannah_RiverTF/data_raw")
OUT = Path("/Users/aspen_mb/Documents/Savannah_RiverTF/data_processed")
NUM_RE = re.compile(r"^[<>]?\d*\.?\d+E[+-]?\d+$|^[<>]?\d*\.?\d+$|^ND$")
DROP = re.compile(r"^(Table 3\.4-\d+.*|Performance Assessment for the|SRR-CWDA-2010-00128|H-Area Tank Farm at the|Revision 1|Savannah River Site|November 2012|Page \d+ of \d+|\(Continued\)|Radionuclide|Chemical)$")


def parse_blocks(text, blocks, skip_tokens):
    """rows = tanks (int ids), columns per block read from header."""
    all_cols = []
    for (s, e) in blocks:
        seg = text[s:e]
        lines = [l.strip() for l in seg.split("\n") if l.strip() and not DROP.match(l)]
        hdr = []
        for l in lines:
            if re.match(r"^\d{1,2}$", l):
                break
            for tok in l.split():
                if tok in skip_tokens:
                    continue
                hdr.append(tok)
        for h in hdr:
            if h not in all_cols:
                all_cols.append(h)
    data = {}
    for (s, e) in blocks:
        seg = text[s:e]
        lines = [l.strip() for l in seg.split("\n") if l.strip() and not DROP.match(l)]
        body_start = 0
        for j, l in enumerate(lines):
            if re.match(r"^\d{1,2}$", l):
                body_start = j
                break
        toks = []
        for l in lines[body_start:]:
            toks.extend(l.split())
        cur = None
        for tok in toks:
            if re.match(r"^\d{1,2}$", tok):
                cur = int(tok)
                data.setdefault(cur, [])
            elif cur is not None:
                tok2 = tok.lstrip("<")
                try:
                    data[cur].append(float(tok2))
                except ValueError:
                    pass
    return all_cols, data


def main():
    t = (RAW / "HTF_PA_Rev1.txt").read_text(errors="replace")
    report = {}
    # ---- rad ----
    SKIP_R = {"Tank", "Estimated", "Radiological", "Inventory", "(Ci)", "at", "Closure",
              "Table", "3.4-9:", "2032", "(Continued)", "Radionuclide"}
    blocks = [(462120, 465725), (465725, 469458), (469458, 473212), (473212, 476738)]
    cols, data = parse_blocks(t, blocks, SKIP_R)
    report["htf_pa_rad_cols"] = len(cols)
    report["htf_pa_rad_col_list"] = cols
    rows = []
    for tank in sorted(data):
        nums = data[tank]
        rec = {"tank_id": tank, "source": "SRR-CWDA-2010-00128 Table 3.4-9",
               "basis": "HTF PA estimated closure inventory (Ci), decayed to 2032", "farm": "HTF"}
        if len(nums) == len(cols):
            for c, v in zip(cols, nums):
                rec[c] = v
            rec["sum_curies"] = sum(nums)
        else:
            rec["parse_warning"] = f"got {len(nums)}, expected {len(cols)}"
        rows.append(rec)
    with open(OUT / "htf_pa_rad_by_tank.csv", "w", newline="") as f:
        fields = []
        for r in rows:
            for k in r.keys():
                if k not in fields:
                    fields.append(k)
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    report["htf_pa_rad_rows"] = len(rows)
    report["htf_pa_rad_ok"] = sum(1 for r in rows if "parse_warning" not in r)

    # ---- chem: find the continuation boundary ----
    i_start = 476738
    i_cont = t.find("Table 3.4-10:  Estimated Chemical Inventory (kg) at Closure (Continued)", i_start)
    i_end = t.find("Table 3.4-11:", i_cont)
    SKIP_C = {"Tank", "Estimated", "Chemical", "Inventory", "(kg)", "at", "Closure",
              "Table", "3.4-10:", "(Continued)", "Chemical"}
    blocks_c = [(i_start, i_cont), (i_cont, i_end)]
    cols_c, data_c = parse_blocks(t, blocks_c, SKIP_C)
    report["htf_pa_chem_cols"] = len(cols_c)
    report["htf_pa_chem_col_list"] = cols_c
    rows_c = []
    for tank in sorted(data_c):
        nums = data_c[tank]
        rec = {"tank_id": tank, "source": "SRR-CWDA-2010-00128 Table 3.4-10",
               "basis": "HTF PA estimated closure chemical inventory (kg)", "farm": "HTF"}
        if len(nums) == len(cols_c):
            for c, v in zip(cols_c, nums):
                rec[c] = v
            rec["sum_kg"] = sum(nums)
        else:
            rec["parse_warning"] = f"got {len(nums)}, expected {len(cols_c)}"
        rows_c.append(rec)
    with open(OUT / "htf_pa_chem_by_tank.csv", "w", newline="") as f:
        fields = []
        for r in rows_c:
            for k in r.keys():
                if k not in fields:
                    fields.append(k)
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows_c)
    report["htf_pa_chem_rows"] = len(rows_c)
    report["htf_pa_chem_ok"] = sum(1 for r in rows_c if "parse_warning" not in r)
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
