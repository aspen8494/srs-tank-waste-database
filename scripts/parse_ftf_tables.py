#!/usr/bin/env python3
"""Parse FTF SA (Tanks 5&6 SA Rev 1) Tables 6.1-1/6.1-2: revised FTF per-tank rad (Ci) + chem (kg).

Layout: transposed. Rows = nuclides/chemicals; columns = tanks.
Rad blocks: (62005,65438) cols 1-8,17-20 | (65438,68320) same cols continued
            (68320,71735) cols 25-28,33,34,44-47 + 'Total Curies by Radionuclide'
            (71735,74956) same
Chem blocks: (74956,77206) cols 1-8,17-20 | (77206,79005) cols 25-28,33,34,44-47
Output: data_processed/ftf_assigned_rad_by_tank.csv, ftf_assigned_chem_by_tank.csv
"""
import csv
import json
import re
from pathlib import Path

RAW = Path("/Users/aspen_mb/Documents/Savannah_RiverTF/data_raw")
OUT = Path("/Users/aspen_mb/Documents/Savannah_RiverTF/data_processed")
NUM_RE = re.compile(r"^[<>]?\d*\.?\d+E[+-]?\d+$|^[<>]?\d*\.?\d+$|^ND$")


def parse_val(tok):
    tok = tok.strip().replace(",", "")
    if tok == "ND":
        return None, "ND"
    lt = tok.startswith("<")
    if lt:
        tok = tok[1:]
    try:
        v = float(tok)
        return v, ("lt" if lt else "num")
    except ValueError:
        return None, "bad"


def parse_transposed(text, blocks, row_first_re, skip_tokens, n_cols_per_block):
    """Parse transposed table: rows keyed by analyte token; each row has values for the block's tank cols.
    Returns (data[analyte] = {tank_id: val}, tank_cols_in_order)."""
    data = {}
    tank_cols = []
    for bi, (s, e) in enumerate(blocks):
        seg = text[s:e]
        lines = [l.strip() for l in seg.split("\n") if l.strip()]
        # header: tokens before first analyte row
        hdr = []
        started = False
        for l in lines:
            if re.match(row_first_re, l) and not started:
                started = True
                break
            for tok in l.split():
                if tok in skip_tokens:
                    continue
                hdr.append(tok)
        if bi == 0 or (tank_cols and hdr[:2] == tank_cols[:2]):
            pass
        cols = hdr[:n_cols_per_block[bi]]
        # row parsing
        cur = None
        for l in lines[len([1 for x in lines if not re.match(row_first_re, x)]) :]:
            pass
        # simpler: iterate lines; analyte rows begin with non-numeric token
        cur = None
        vals = []
        def flush():
            if cur is not None:
                nums = [v for (v, f) in vals if v is not None]
                data.setdefault(cur, {}).setdefault(bi, nums)
        for l in lines:
            if re.match(row_first_re, l):
                flush()
                cur = l.replace(" ", "")
                vals = []
            elif NUM_RE.match(l) and cur is not None:
                for tok in l.split():
                    v, f = parse_val(tok)
                    vals.append((v, f))
        flush()
        if bi == 0 or not tank_cols:
            tank_cols = cols
        # merge into flat structure per analyte: values per block map to that block's cols
    return data, tank_cols


def main():
    t = (RAW / "SA_Tank5_6_FTF_full.txt").read_text(errors="replace")
    report = {}

    # ---- Radionuclides (Table 6.1-1) ----
    NUCLIDE_RE = re.compile(r"^(Ac-|Al-|Am-|Ba-|C-|Cf-|Cl-|Cm-|Co-|Cs-|Eu-|H-|I-|K-|Nb-|Ni-|Np-|Pa-|Pd-|Pt-|Pu-|Ra-|Se-|Sm-|Sn-|Sr-|Tc-|Th-|U-|Y-|Zr-)")
    SKIP = {"Table", "6.1-1:", "Revised", "FTF", "Radionuclide", "Inventories", "(Ci)",
            "(Continued)", "Total", "Curies", "by", "Radionuclide"}
    blocks = [(62005, 65438), (65438, 68320), (68320, 71735), (71735, 74956)]
    ncols = [12, 12, 11, 11]  # 10 tanks + Total col for blocks 2/3
    # Parse per block: data[nuclide][block] = [values]
    data = {}
    for bi, (s, e) in enumerate(blocks):
        seg = t[s:e]
        lines = [l.strip() for l in seg.split("\n") if l.strip()]
        cur = None
        vals = []
        rows = {}

        def flush():
            if cur is not None:
                nums = [v for (v, f) in vals if v is not None]
                rows[cur] = nums

        for l in lines:
            if NUCLIDE_RE.match(l):
                flush()
                cur = l.replace(" ", "")
                vals = []
            elif cur is not None and (NUM_RE.match(l) or l.startswith("ND")):
                for tok in l.split():
                    v, f = parse_val(tok)
                    vals.append((v, f))
        flush()
        data[bi] = rows
    # tanks for blocks 0/1: 1,2,3,4,5,6,7,8,17,18,19,20 ; blocks 2/3: 25,26,27,28,33,34,44,45,46,47 + Total
    tanks_a = [1, 2, 3, 4, 5, 6, 7, 8, 17, 18, 19, 20]
    tanks_b = [25, 26, 27, 28, 33, 34, 44, 45, 46, 47]
    rad_rows = []
    nuclides = sorted(set(data[0]) | set(data[1]) | set(data[2]) | set(data[3]))
    for nuc in nuclides:
        rec = {"nuclide": nuc}
        for bi, tanks in [(0, tanks_a), (1, tanks_a), (2, tanks_b), (3, tanks_b)]:
            vals = data.get(bi, {}).get(nuc, [])
            for tank, v in zip(tanks, vals):
                rec[f"tank_{tank}"] = v
            if bi in (2, 3) and len(vals) > len(tanks):
                rec["total_by_radionuclide"] = vals[len(tanks)]
        rad_rows.append(rec)
    # transpose to per-tank
    out_rows = []
    all_tanks = tanks_a + tanks_b
    for tank in all_tanks:
        rec = {"tank_id": tank, "farm": "FTF", "source": "SRR-CWDA-2012-00106 Table 6.1-1",
               "basis": "revised FTF closure inventory (projected; tanks 18/19 = actual shaded)"}
        s = 0.0
        for r in rad_rows:
            v = r.get(f"tank_{tank}")
            if v is not None:
                rec[r["nuclide"]] = v
                s += v
        rec["sum_curies"] = s
        out_rows.append(rec)
    with open(OUT / "ftf_assigned_rad_by_tank.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    report["ftf_rad_rows"] = len(out_rows)
    report["ftf_rad_nuclides"] = len(rad_rows)
    # sanity: tank 18 Cs-137 should be ~9.2E+03 (actual)
    r18 = next(r for r in out_rows if r["tank_id"] == 18)
    report["check_t18_cs137"] = r18.get("Cs-137")
    report["check_t18_sum"] = r18.get("sum_curies")

    # ---- Chemicals (Table 6.1-2) ----
    CHEM_RE = re.compile(r"^(Ag|Al|As|B|Ba|Cd|Cl|Co|Cr|Cs|Cu|F|Fe|Hg|I|K|Mg|Mn|Mo|Na|Nb|Ni|NO2|NO3|Pb|PO4|Sb|Se|Si|SO4|Sr|Ti|Tl|U|V|Zn|Zr)$")
    SKIP_C = {"Table", "6.1-2:", "Revised", "FTF", "Chemical", "Inventories", "(kg)", "(Continued)"}
    blocks_c = [(74956, 77206), (77206, 79005)]
    ncols_c = [12, 10]
    data_c = {}
    for bi, (s, e) in enumerate(blocks_c):
        seg = t[s:e]
        lines = [l.strip() for l in seg.split("\n") if l.strip()]
        cur = None
        vals = []
        rows = {}

        def flush2():
            if cur is not None:
                nums = [v for (v, f) in vals if v is not None]
                rows[cur] = nums

        for l in lines:
            if CHEM_RE.match(l):
                flush2()
                cur = l
                vals = []
            elif cur is not None and NUM_RE.match(l):
                for tok in l.split():
                    v, f = parse_val(tok)
                    vals.append((v, f))
        flush2()
        data_c[bi] = rows
    chem_rows = []
    chemicals = sorted(set(data_c[0]) | set(data_c[1]))
    for ch in chemicals:
        rec = {"chemical": ch}
        for bi, tanks in [(0, tanks_a), (1, tanks_b)]:
            vals = data_c.get(bi, {}).get(ch, [])
            for tank, v in zip(tanks, vals):
                rec[f"tank_{tank}"] = v
        chem_rows.append(rec)
    out_c = []
    for tank in all_tanks:
        rec = {"tank_id": tank, "farm": "FTF", "source": "SRR-CWDA-2012-00106 Table 6.1-2",
               "basis": "revised FTF closure chemical inventory (kg)"}
        s = 0.0
        for r in chem_rows:
            v = r.get(f"tank_{tank}")
            if v is not None:
                rec[r["chemical"]] = v
                s += v
        rec["sum_kg"] = s
        out_c.append(rec)
    with open(OUT / "ftf_assigned_chem_by_tank.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out_c[0].keys()))
        w.writeheader()
        w.writerows(out_c)
    report["ftf_chem_rows"] = len(out_c)
    report["ftf_chem_analytes"] = len(chem_rows)
    r18c = next(r for r in out_c if r["tank_id"] == 18)
    report["check_t18_chem_Al"] = r18c.get("Al")
    report["check_t18_chem_U"] = r18c.get("U")
    print(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
