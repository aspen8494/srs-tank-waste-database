#!/usr/bin/env python3
"""Parse ALL SRS PA/SA inventory tables into normalized CSVs.

Each parser handles a specific table's flattened-text layout. Validation counts
are printed at the end and written to parse_report.json.
"""
import csv
import json
import re
from pathlib import Path

RAW = Path("/Users/aspen_mb/Documents/Savannah_RiverTF/data_raw")
OUT = Path("/Users/aspen_mb/Documents/Savannah_RiverTF/data_processed")
OUT.mkdir(exist_ok=True)

NUM_RE = re.compile(r"^[<>]?\d*\.?\d+E[+-]?\d+$|^[<>]?\d*\.?\d+$")


def toks_of(text, start, end, drop_pat=None):
    seg = text[start:end]
    lines = [l.strip() for l in seg.split("\n") if l.strip()]
    if drop_pat:
        lines = [l for l in lines if not drop_pat.match(l)]
    return lines


def parse_val(tok):
    tok = tok.strip().replace(",", "")
    lt = tok.startswith("<")
    if lt:
        tok = tok[1:]
    try:
        v = float(tok)
        return v, ("lt" if lt else "num")
    except ValueError:
        return None, "bad"


def write_csv(path, rows):
    if not rows:
        return
    fields = []
    for r in rows:
        for k in r.keys():
            if k not in fields:
                fields.append(k)
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)


REPORT = {}

DROP_PA = re.compile(
    r"^(Table \d+\.\d+-\d+.*|\(Continued\)$|Tank \d+ Special Analysis for the|Performance Assessment for the|"
    r"SRR-CWDA-\d+-\d+.*|H-Tank Farm at the|F-Tank Farm at the|Savannah River Site$|Revision \d$|"
    r"February 2015$|January 2013$|January 2015$|June 2012$|Page \d+ of \d+|\[SRR-CWDA.*|"
    r"Not determined.*|ND\s+Not determined.*|Notes?[:.].*|Green font.*|Red font.*|Shaded cells.*|"
    r"Shaded.*|Green indicates.*|Pink indicates.*|Industrial Wastewater Closure Module$|"
    r"for the Liquid Waste Tanks 18 and 19$|F-Area Tank Farm Savannah River Site$|October 2011$|\d+ of \d+$)"
)


# ---------------------------------------------------------------
# 1. HTF SA (Tank 16) Table 6.2-2: assigned rad inventory per HTF waste tank (transposed: rows=tanks, cols=nuclides)
# ---------------------------------------------------------------
def parse_htf_assigned_rad():
    t = (RAW / "Tank16_SpecialAnalysis_Rev1.txt").read_text(errors="replace")
    blocks = [(74546, 78247), (78247, 82080), (82080, 85956), (85956, 89762)]
    # split multi-value lines into tokens first
    def tokenize(lines):
        toks = []
        for l in lines:
            toks.extend(l.split())
        return toks
    # build global col order from block headers (drop the table title words by starting after '2032' or '(Continued)')
    TITLE_WORDS = {"Table", "6.2-2:", "Assigned", "Radiological", "Inventory", "(Ci)", "at",
                   "Closure", "Decayed", "to", "Year", "2032", "6.2-2", "(Continued)", "Tank"}
    all_cols = []
    block_hdrs = []
    for (s, e) in blocks:
        lines = toks_of(t, s, e, DROP_PA)
        hdr = []
        for l in lines:
            if re.match(r"^\d{1,2}$", l):
                break
            for tok in l.split():
                if tok in TITLE_WORDS:
                    continue
                hdr.append(tok)
        block_hdrs.append(hdr)
        for h in hdr:
            if h not in all_cols:
                all_cols.append(h)
    data = {}
    for bi, (s, e) in enumerate(blocks):
        lines = toks_of(t, s, e, DROP_PA)
        # skip header
        body_start = 0
        for j, l in enumerate(lines):
            if re.match(r"^\d{1,2}$", l):
                body_start = j
                break
        toks = tokenize(lines[body_start:])
        cur = None
        for tok in toks:
            if re.match(r"^\d{1,2}$", tok):
                cur = int(tok)
                data.setdefault(cur, [])
            elif cur is not None:
                v, f = parse_val(tok)
                if v is not None:
                    data[cur].append(v)
    rows = []
    for tank in sorted(data):
        nums = data[tank]
        rec = {"tank_id": tank, "source": "SRR-CWDA-2014-00106 Table 6.2-2",
               "basis": "PA-assigned closure inventory, decayed to 2032", "farm": "HTF"}
        if len(nums) == len(all_cols):
            for name, v in zip(all_cols, nums):
                rec[name] = v
            rec["sum_curies"] = sum(nums)
            rec["n_values"] = len(nums)
        else:
            rec["parse_warning"] = f"got {len(nums)} values, expected {len(all_cols)}"
        rows.append(rec)
    write_csv(OUT / "htf_assigned_rad_by_tank.csv", rows)
    REPORT["htf_assigned_rad_cols"] = len(all_cols)
    REPORT["htf_assigned_rad_col_list"] = all_cols
    REPORT["htf_assigned_rad_rows"] = len(rows)
    REPORT["htf_assigned_rad_ok"] = sum(1 for r in rows if "parse_warning" not in r)
    return rows


# ---------------------------------------------------------------
# 2. HTF SA Table 6.2-3: assigned chemical inventory per HTF waste tank (kg)
# ---------------------------------------------------------------
def parse_htf_assigned_chem():
    t = (RAW / "Tank16_SpecialAnalysis_Rev1.txt").read_text(errors="replace")
    # Two page blocks: 89762..93824 (cols Ag..I) and 93824..97662 (cols Mn..Zn)
    blocks = [(89762, 93824), (93824, 97662)]
    TITLE_WORDS = {"Table", "6.2-3:", "Assigned", "Chemical", "Inventory", "(kg)", "at",
                   "Closure", "(Continued)", "Tank"}
    all_cols = []
    for (s, e) in blocks:
        lines = toks_of(t, s, e, DROP_PA)
        hdr = []
        for l in lines:
            if re.match(r"^\d{1,2}$", l):
                break
            for tok in l.split():
                if tok in TITLE_WORDS:
                    continue
                hdr.append(tok)
        for h in hdr:
            if h not in all_cols:
                all_cols.append(h)
    data = {}
    for (s, e) in blocks:
        lines = toks_of(t, s, e, DROP_PA)
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
                v, f = parse_val(tok)
                if v is not None:
                    data[cur].append(v)
    rows = []
    for tank in sorted(data):
        nums = data[tank]
        rec = {"tank_id": tank, "source": "SRR-CWDA-2014-00106 Table 6.2-3",
               "basis": "PA-assigned closure chemical inventory", "farm": "HTF"}
        if len(nums) == len(all_cols):
            for name, v in zip(all_cols, nums):
                rec[name] = v
            rec["sum_kg"] = sum(nums)
        else:
            rec["parse_warning"] = f"got {len(nums)} values, expected {len(all_cols)}"
        rows.append(rec)
    REPORT["htf_assigned_chem_cols"] = len(all_cols)
    REPORT["htf_assigned_chem_col_list"] = all_cols
    write_csv(OUT / "htf_assigned_chem_by_tank.csv", rows)
    REPORT["htf_assigned_chem_rows"] = len(rows)
    REPORT["htf_assigned_chem_ok"] = sum(1 for r in rows if "parse_warning" not in r)
    return rows


# ---------------------------------------------------------------
# 3. HTF SA Table 6.2-4: assigned annulus rad inventory per tank (2 blocks)
# ---------------------------------------------------------------
def parse_htf_annulus_rad():
    t = (RAW / "Tank16_SpecialAnalysis_Rev1.txt").read_text(errors="replace")
    # Transposed: rows=nuclides, cols = Tanks 9..16 (2 page blocks)
    NUCLIDE_RE = re.compile(r"^(Ac-|Al-|Am-|Ba-|C-|Cf-|Cl-|Cm-|Co-|Cs-|Eu-|H-|I-|K-|Nb-|Ni-|Np-|Pa-|Pd-|Pt-|Pu-|Ra-|Se-|Sm-|Sn-|Sr-|Tc-|Th-|U-|Y-|Zr-)")
    blocks = [(97662, 100206), (100206, 102784)]
    tanks = [9, 10, 11, 12, 13, 14, 15, 16]
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
            elif cur is not None and NUM_RE.match(l):
                for tok in l.split():
                    v, f = parse_val(tok)
                    vals.append((v, f))
        flush()
        for nuc, nums in rows.items():
            d = data.setdefault(nuc, {})
            for tank, v in zip(tanks, nums):
                d[tank] = v
    rows_out = []
    for nuc in sorted(data):
        rec = {"nuclide": nuc, "source": "SRR-CWDA-2014-00106 Table 6.2-4",
               "basis": "PA-assigned annulus inventory (Ci), decayed to 2032", "farm": "HTF"}
        for tank in tanks:
            v = data[nuc].get(tank)
            if v is not None:
                rec[f"tank_{tank}"] = v
        rows_out.append(rec)
    write_csv(OUT / "htf_assigned_annulus_rad_by_tank.csv", rows_out)
    REPORT["htf_annulus_rad_rows"] = len(rows_out)
    REPORT["htf_annulus_rad_nuclides"] = len(data)
    return rows_out


# ---------------------------------------------------------------
# 4. Tank 16 final residual (Tables 5.0-1 rad, 5.0-2 chem) - rows=nuclides, 2 value cols (HTF PA value, Final value)
# ---------------------------------------------------------------
def parse_tank16_final():
    t = (RAW / "Tank16_SpecialAnalysis_Rev1.txt").read_text(errors="replace")
    # rad: 43784..46071; chem: 46071..47226; annulus rad: 47226..49500
    def parse_pair(start, end, names):
        lines = toks_of(t, start, end, DROP_PA)
        # lines: name, v1, v2, (blank), name, v1, v2 ...
        rows = []
        cur = None
        for l in lines:
            if NUM_RE.match(l):
                v, f = parse_val(l)
                if cur is not None:
                    cur.setdefault("vals", []).append((v, f))
            else:
                if cur is not None and len(cur["vals"]) >= 2:
                    rows.append(cur)
                cur = {"name": l, "vals": []}
        if cur is not None and len(cur["vals"]) >= 2:
            rows.append(cur)
        out = []
        for r in rows:
            if len(r["vals"]) >= 2:
                out.append({"analyte": r["name"], "value_pa": r["vals"][0][0],
                            "value_final": r["vals"][1][0],
                            "final_lt": r["vals"][1][1] == "lt"})
        return out

    rad = parse_pair(43784, 46071, None)
    for r in rad:
        r["kind"] = "radionuclide"
        r["unit"] = "Ci"
        r["source"] = "SRR-CWDA-2014-00106 Table 5.0-1"
    chem = parse_pair(46071, 47226, None)
    for r in chem:
        r["kind"] = "chemical"
        r["unit"] = "kg"
        r["source"] = "SRR-CWDA-2014-00106 Table 5.0-2"
    ann = parse_pair(47226, 49500, None)
    for r in ann:
        r["kind"] = "radionuclide_annulus"
        r["unit"] = "Ci"
        r["source"] = "SRR-CWDA-2014-00106 Table 5.0-3"
    allr = rad + chem + ann
    write_csv(OUT / "tank16_final_residual.csv", allr)
    REPORT["tank16_final_rad"] = len(rad)
    REPORT["tank16_final_chem"] = len(chem)
    REPORT["tank16_final_annulus"] = len(ann)
    return allr


# ---------------------------------------------------------------
# 5. Tanks 18/19 SA: Tables 5.0-1 (rad, Ci) and 5.0-2 (chem, kg) - rows=analyte, cols=T18, T19
# ---------------------------------------------------------------
def parse_tank18_19():
    t = (RAW / "Tank18_19_SpecialAnalysis.txt").read_text(errors="replace")
    out = []

    def parse_pair(start, end, kind, unit, source):
        lines = toks_of(t, start, end, DROP_PA)
        rows = []
        cur = None
        for l in lines:
            if NUM_RE.match(l):
                v, f = parse_val(l)
                if cur is not None:
                    cur["vals"].append((v, f))
            else:
                if cur is not None and len(cur["vals"]) >= 2:
                    rows.append(cur)
                cur = {"name": l.replace(" ", ""), "vals": []}
        if cur is not None and len(cur["vals"]) >= 2:
            rows.append(cur)
        res = []
        for r in rows:
            if len(r["vals"]) >= 2:
                res.append({"analyte": r["name"], "kind": kind, "unit": unit,
                            "tank18": r["vals"][0][0], "tank19": r["vals"][1][0],
                            "source": source})
        return res

    rad = parse_pair(53034, 54836, "radionuclide", "Ci", "SRR-CWDA-2010-00106 Table 5.0-1 (actual residual)")
    chem = parse_pair(54836, 56400, "chemical", "kg", "SRR-CWDA-2010-00106 Table 5.0-2 (actual residual)")
    out = rad + chem
    write_csv(OUT / "tank18_19_residual.csv", out)
    REPORT["tank18_19_rad"] = len(rad)
    REPORT["tank18_19_chem"] = len(chem)
    return out


# ---------------------------------------------------------------
# 6. Closure Module 18/19: Tables 4.3-3 (chem kg) & 4.3-4 (rad Ci) - same as #5 but from closure module (verify cross-source)
# ---------------------------------------------------------------
def parse_closure_18_19():
    t = (RAW / "ClosureModule_Tanks18_19.txt").read_text(errors="replace")
    # Table 4.3-3 at ~ (find), Table 4.3-4 at 208190
    i_chem = t.rfind("Table 4.3-3:  Residual Chemical Inventories for Tanks 18 and 19")
    i_rad = 208190
    # chem ends at table 4.3-4 start
    out = []

    def parse_pair(start, end, kind, unit, source):
        lines = toks_of(t, start, end, DROP_PA)
        rows = []
        cur = None
        for l in lines:
            if NUM_RE.match(l):
                v, f = parse_val(l)
                if cur is not None:
                    cur["vals"].append((v, f))
            else:
                if cur is not None and len(cur["vals"]) >= 2:
                    rows.append(cur)
                cur = {"name": l.replace(" ", ""), "vals": []}
        if cur is not None and len(cur["vals"]) >= 2:
            rows.append(cur)
        res = []
        for r in rows:
            if len(r["vals"]) >= 2:
                res.append({"analyte": r["name"], "kind": kind, "unit": unit,
                            "tank18": r["vals"][0][0], "tank19": r["vals"][1][0], "source": source})
        return res

    chem = parse_pair(i_chem, i_rad, "chemical", "kg", "SRR-CWDA-2010-00003 Table 4.3-3")
    rad = parse_pair(i_rad, i_rad + 5200, "radionuclide", "Ci", "SRR-CWDA-2010-00003 Table 4.3-4")
    write_csv(OUT / "tank18_19_residual_closuremodule.csv", chem + rad)
    REPORT["closure_18_19_rad"] = len(rad)
    REPORT["closure_18_19_chem"] = len(chem)
    return chem + rad


if __name__ == "__main__":
    parse_htf_assigned_rad()
    parse_htf_assigned_chem()
    parse_htf_annulus_rad()
    parse_tank16_final()
    parse_tank18_19()
    parse_closure_18_19()
    (OUT / "parse_report.json").write_text(json.dumps(REPORT, indent=1))
    print(json.dumps(REPORT, indent=1))
