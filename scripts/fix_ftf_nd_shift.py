#!/usr/bin/env python3
"""ND-aware positional re-parse of FTF SA Tables 6.1-1 (radionuclides) and 6.1-2 (chemicals),
Tanks 5&6 SA (SRR-CWDA-2012-00106). Fixes the ND left-shift + total-row bleed from the first parse.

Verified structure:
  Rad pages A (x2): header tanks 1..8,17..20 (12 cols); pages B (x2): tanks 25..47 (10 cols + 'Total Curies by' col = 11 values)
  Chem pages A/B: same tank columns, no total column
  Values: 'X.XE+NN'; 'ND' = not determined; 'NE' = not established (chem only)
  Combined header/footer tokens: 'Total Curies by' + 'Radionuclide'; footer 'Total', 'Curies by', 'Tank'

Validates every tank's nuclide sum against the table's own 'Total Curies by Tank' row before writing.
"""
import re, sqlite3, csv, datetime

DB = "/Users/aspen_mb/Documents/Savannah_RiverTF/srs_tank_waste.db"
SRC = "/Users/aspen_mb/Documents/Savannah_RiverTF/data_raw/SA_Tank5_6_FTF_full.txt"
src = open(SRC).read()

NUM = re.compile(r"^\d\.\dE[+-]\d\d$")
# Chemical analytes in FTF Table 6.1-2 (allowlist beats heuristics on this document)
CHEMS = {"Ag", "Al", "As", "B", "Ba", "Ca", "Cd", "Cr", "Cu", "Fe", "Hg", "K", "Mg", "Mn", "Mo",
         "Na", "Ni", "NO2", "NO3", "Pb", "S", "Si", "U", "Zn", "Cl", "F", "Free OH", "NiCO3", "RaSO4"}

def segments(pattern):
    out = []
    for m in re.finditer(pattern, src):
        seg = src[m.end():]
        end = len(seg)
        for p in (r"\nTanks 5 and 6 Special Analysis", r"\[SRR-CWDA", r"Revised FTF"):
            mm = re.search(p, seg)
            if mm:
                end = min(end, mm.start())
        toks = [t.strip() for t in seg[:end].split("\n")]
        i = 0
        while i < len(toks) and toks[i] == "":
            i += 1
        tanks = []
        while i < len(toks) and re.match(r"^\d+$", toks[i]):
            tanks.append(int(toks[i])); i += 1
        while i < len(toks) and (toks[i] == "" or toks[i].startswith("Total Curies") or toks[i] == "Radionuclide"):
            i += 1
        out.append((tanks, toks, i))
    return out

def parse_with_flags(pattern, chem_mode):
    rows, flags = {}, {}
    for tanks, toks, i in segments(pattern):
        ncol = len(tanks)
        while i < len(toks):
            t = toks[i]
            if (not t) or NUM.match(t) or t in ("ND", "NE") or t.startswith("[") or t.startswith("Page"):
                i += 1; continue
            if t in ("Total", "Curies by", "Tank") or t.startswith("Total"):
                i += 1
                continue
            is_nuc = re.match(r"^[A-Z][a-z]?-\d{1,3}m?$", t)
            ok_name = (t in CHEMS) if chem_mode else bool(is_nuc)
            if not ok_name:
                i += 1; continue
            name = t; i += 1
            vals = []
            while i < len(toks) and len(vals) < ncol:
                tk = toks[i]
                if NUM.match(tk) or tk in ("ND", "NE"):
                    vals.append(tk); i += 1
                else:
                    break
            if len(vals) == ncol:
                d = rows.setdefault(name, {})
                fl = flags.setdefault(name, {})
                for tank, v in zip(tanks, vals):
                    if v in ("ND", "NE"):
                        d[tank] = 0.0; fl[tank] = v
                    else:
                        d[tank] = float(v.replace("E", "e")); fl[tank] = ""
    return rows, flags

def table_totals(pattern):
    totals = {}
    for tanks, toks, i in segments(pattern):
        ncol = len(tanks)
        j = i
        while j < len(toks):
            if toks[j] == "Total" and j + 1 < len(toks) and toks[j + 1] == "Curies by":
                k = j + 2
                if k < len(toks) and toks[k] == "Tank":
                    k += 1
                vals = []
                while k < len(toks) and len(vals) < ncol:
                    tk = toks[k]
                    if NUM.match(tk):
                        vals.append(float(tk.replace("E", "e"))); k += 1
                    else:
                        break
                if len(vals) == ncol:
                    totals.update(dict(zip(tanks, vals)))
                j = k
            else:
                j += 1
    return totals

RAD_PAT = r"Revised FTF Radionuclide Inventories \(Ci\)(?: \(Continued\))? \n"
CHEM_PAT = r"Revised FTF Chemical Inventories \(kg\)(?: \(Continued\))? \n"

rad_rows, rad_flags = parse_with_flags(RAD_PAT, chem_mode=False)
chem_rows, chem_flags = parse_with_flags(CHEM_PAT, chem_mode=True)
rad_totals = table_totals(RAD_PAT)

print(f"radionuclides parsed: {len(rad_rows)}")
print(f"chemicals parsed: {len(chem_rows)} -> {sorted(chem_rows.keys())}")
print("Total-by-tank row:", {k: f"{v:.2e}" for k, v in sorted(rad_totals.items())})

print("\n=== VALIDATION: sum-of-nuclides vs the table's own Total row ===")
ok, bad = 0, []
for tank, tot in sorted(rad_totals.items()):
    s = sum(d.get(tank, 0.0) for d in rad_rows.values())
    if abs(s - tot) <= max(0.05 * tot, 2.0):   # printed totals are rounded to 2 significant figures
        ok += 1
    else:
        bad.append((tank, s, tot))
print(f"match within 2%: {ok}/{len(rad_totals)}")
for t, s, tot in bad:
    print(f"  MISMATCH tank {t}: parsed sum {s:,.0f} vs printed total {tot:,.0f} (ratio {s/tot:.2f})")

if not bad and ok >= 20:
    con = sqlite3.connect(DB)
    cur = con.cursor()
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    for tbl, rows, flags, val_col in (
        ("inventory_rad", rad_rows, rad_flags, "value_ci"),
        ("inventory_chem", chem_rows, chem_flags, "value_kg"),
    ):
        name_col = "nuclide" if tbl == "inventory_rad" else "chemical"
        bak = f"/Users/aspen_mb/Documents/Savannah_RiverTF/data_processed/{tbl}_ftf_PRE-FIX2_{stamp}.csv"
        with open(bak, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["tank_id", name_col, val_col, "value_flag", "basis", "source_id"])
            for r in cur.execute(f"SELECT tank_id, {name_col}, {val_col}, value_flag, basis, source_id "
                                 f"FROM {tbl} WHERE dataset='ftf_assigned_closure'"):
                w.writerow(r)
        cur.execute(f"DELETE FROM {tbl} WHERE dataset='ftf_assigned_closure'")
        n = 0
        for name, d in rows.items():
            for tank, v in d.items():
                cur.execute(f"""INSERT INTO {tbl} (tank_id, dataset, {name_col}, {val_col}, value_flag, basis, source_id)
                    VALUES (?, 'ftf_assigned_closure', ?, ?, ?, 'assigned closure residual (decayed to 2032)', 4)""",
                    (tank, name, v, flags.get(name, {}).get(tank, "")))
                n += 1
        con.commit()
        print(f"{tbl}: backup {bak}; replaced with {n} rows")
    con.close()
    print("DB UPDATED")
else:
    print("NOT WRITING — validation failed; fix parser first")
