#!/usr/bin/env python3
"""Parse SRNL current-waste characterization reports into JSON. v2 - verified layouts.

All tables in these PDFs flatten to one token per line. Layouts:
  SB11 Tank 51: element/method/value rows (value = 3rd token group, first numeric after method)
  SB10: nuclide/5-numbers rows (Ci/gal = 4th number)
  Salt batches 8-13 (FY23/FY24): chemistry component rows w/ N batch columns; rad analyte rows w/ N batch columns
  Salt Batch 14: analyte/WAC/result rows
  PRFT: element rows; rad rows = nuclide/uCi-per-g first numeric
Output: data_processed/srnl_current_waste.json
"""
import json
import re
from pathlib import Path

RAW = Path("/Users/aspen_mb/Documents/Savannah_RiverTF/data_raw")
OUT = Path("/Users/aspen_mb/Documents/Savannah_RiverTF/data_processed")

NUMTOK = re.compile(r"^[<>]\s*[\d.]+E[+-]?\d+$|^[<>]\s*[\d.]+$|^[\d.]+E[+-]?\d+$|^[\d.]+$")


def numtok(tok):
    tok = tok.strip().rstrip("*").rstrip("a").rstrip("b").rstrip("c").strip()
    flag = ""
    if tok and tok[0] in "<>":
        flag = tok[0]
        tok = tok[1:].strip()
    if not NUMTOK.match(tok):
        return None, ""
    try:
        return float(tok), flag
    except ValueError:
        return None, ""


def lines_between(text, start_marker, end_marker=None, occurrence=-1):
    occ = [m.start() for m in re.finditer(re.escape(start_marker), text)]
    if not occ:
        return []
    s = occ[occurrence]
    if end_marker:
        occ2 = [m.start() for m in re.finditer(re.escape(end_marker), text) if m.start() > s + len(start_marker)]
        e = occ2[0] if occ2 else s + 9000
    else:
        e = s + 9000
    seg = text[s:e]
    # cut trailing footnote lines
    cut = seg.find("*RSD")
    if cut > 0:
        seg = seg[:cut]
    return [l.strip() for l in seg.split("\n") if l.strip()]


ELEM_SET = set("Ag Al As B Ba Be Bi Ca Cd Ce Co Cr Cs Cu Fe Gd K La Li Mg Mn Mo Na Nb Nd Ni P Pb Pr Pu Rh Ru S Sb Si Sm Sn Sr Th Ti Tl U V W Y Zn Zr Hg".split())
ANIONS = ["Bromide", "Chloride", "Fluoride", "Formate", "Nitrate", "Nitrite", "Oxalate",
          "Phosphate", "Sulfate", "Carbonate", "Free OH", "Total Organic", "TOC", "Cs-137"]


def parse_sb11():
    t = (RAW / "SRNL_SludgeBatch11_Tank51_qualification.txt").read_text(errors="replace")
    rec = {"report": "SRNL-STI-2024-00492", "sample_ids": "HTF-51-24-85/86", "sample_year": 2024,
           "type": "sludge_batch", "tank": 51, "batch": "Sludge Batch 11 (DWPF Macro Batch 11)"}

    def elem_table(marker, nxt):
        lines = lines_between(t, marker, nxt, -1)
        out = {}
        i = 0
        while i < len(lines):
            if lines[i] in ELEM_SET:
                # scan forward to first numeric token (method tokens precede it)
                j = i + 1
                val, flag = None, ""
                while j < len(lines) and lines[j] not in ELEM_SET and not lines[j].startswith("Table"):
                    v, f = numtok(lines[j])
                    if v is not None and val is None:
                        val, flag = v, f
                        break
                    j += 1
                if val is not None:
                    out[lines[i]] = {"value": val, "flag": flag}
                i = j
            else:
                i += 1
        return out

    rec["slurry_elemental_ug_per_g"] = elem_table("Table 3-8 Slurry Elemental Composition", "Table 3-9")
    # U/Pu isotope tables use 'U-233' style nuclide tokens
    def isotope_table(marker, nxt):
        lines = lines_between(t, marker, nxt, -1)
        out = {}
        NU = re.compile(r"^(U-2\d\d|Pu-2\d\d)$")
        i = 0
        while i < len(lines):
            if NU.match(lines[i]):
                j = i + 1
                val, flag = None, ""
                while j < len(lines) and not NU.match(lines[j]) and not lines[j].startswith("Table") and not lines[j].startswith("*RSD"):
                    v, f = numtok(lines[j])
                    if v is not None and val is None:
                        val, flag = v, f
                        break
                    j += 1
                if val is not None:
                    out[lines[i]] = {"value": val, "flag": flag}
                i = j
            else:
                i += 1
        return out

    rec["slurry_U_Pu_isotopes_dpm_per_g"] = isotope_table("Table 3-9 Isotopes of Uranium and Plutonium of Slurry", "3.5 Total and Soluble")
    rec["supernate_elemental_mg_per_L"] = elem_table("Table 3-5 Elemental Composition of Supernate", "Table 3-6")
    rec["supernate_U_Pu_isotopes_dpm_per_mL"] = elem_table("Table 3-6 Isotopes of Uranium and Plutonium of Supernate", "Table 3-7")

    # Table 3-4 anions + Cs-137 (supernate)
    lines = lines_between(t, "Table 3-4 Supernate Anions and Cs-137 Results", "Table 3-5", -1)
    an = {}
    i = 0
    JOIN = {"Total Organic": "Total Organic Carbon"}
    while i < len(lines):
        tok = lines[i]
        name = JOIN.get(tok, tok)
        if tok in ANIONS or tok in JOIN.values() or name in ANIONS:
            j = i + 1
            val, flag = None, ""
            while j < len(lines) and not (lines[j] in ANIONS or lines[j] in JOIN):
                v, f = numtok(lines[j])
                if v is not None and val is None:
                    val, flag = v, f
                    break
                j += 1
            if val is not None:
                an[name] = {"value": val, "flag": flag}
            i = j
        else:
            i += 1
    rec["supernate_anions_mg_per_L"] = an

    # Table 3-10 soluble Na/Cr/Hg/S
    lines = lines_between(t, "Table 3-10 Soluble Sodium, Chromium, Sulfur, and Mercury", None, -1)
    sol = {}
    i = 0
    while i < len(lines):
        if lines[i] in ("Cr", "Hg", "Na", "S"):
            j = i + 1
            vals = []
            while j < len(lines) and lines[j] not in ("Cr", "Hg", "Na", "S") and not lines[j].startswith("*"):
                v, f = numtok(lines[j])
                if v is not None:
                    vals.append((v, f))
                j += 1
            if len(vals) >= 2:
                sol[lines[i]] = {"total_ug_per_g": vals[0][0], "soluble_mg_per_kg": vals[1][0]}
            i = j
        else:
            i += 1
    rec["soluble_split_Na_Cr_Hg_S"] = sol
    return rec


def parse_sb10():
    t = (RAW / "SRNL_DWPF_SludgeBatch10_radionuclides.txt").read_text(errors="replace")
    rec = {"report": "SRNL-STI-2024-00240", "type": "sludge_batch", "batch": "SB10",
           "sample_ids": "HTF-40-23-19(1-3)", "sample_year": 2023, "tank": 40}
    occ = [m.start() for m in re.finditer(re.escape("Table 3-1. SB10 Radionuclides and Activities"), t)]
    seg = t[occ[-1]:occ[-1] + 11000]
    NU = re.compile(r"^(Cl-36|Ni-59|Co-60|Ni-63|Se-79|Sr-90|Y-90|Zr-93|Nb-93m|Tc-99|Ru-106|Pd-107|Cd-113m|Sn-121m|Sb-125|Te-125m|Sn-126|I-129|Ba-133|Cs-134|Cs-135|Cs-137|Ba-137m|Ce-144|Pm-147|Sm-151|Eu-154|Eu-155|Pb-210|Ra-226|Ac-227|Th-229|Th-230|Pa-231|Th-232|U-233|U-234|U-235|U-236|U-238|Np-237|Pu-238|Pu-239|Pu-240|Pu-241|Pu-242|Am-241|Am-242m|Cm-242|Am-243|Cm-243|Cm-244|Cm-245|Cm-246|Cm-247|Bk-247|Cm-248|Cf-249|Cf-250|Cf-251|Cf-252)(\s*\(calc\)|\s*†|\s*‡|\s*§)?$")
    rad = {}
    lines = [l.strip() for l in seg.split("\n") if l.strip()]
    i = 0
    while i < len(lines):
        m = NU.match(lines[i])
        if m:
            j = i + 1
            vals = []
            while j < len(lines) and NUMTOK.match(lines[j].strip().rstrip("*")):
                v, f = numtok(lines[j])
                vals.append((v, f))
                j += 1
            if len(vals) >= 4:
                rad[m.group(1)] = {"wt_pct_total_solids": vals[1][0],
                                   "uCi_per_g_dried_solids": vals[2][0],
                                   "Ci_per_gal_slurry": vals[3][0],
                                   "flag": vals[3][1] or vals[2][1]}
            i = max(j, i + 1)
        else:
            i += 1
    rec["radionuclides"] = rad
    return rec


def _salt_chem_table(lines, ncols, colnames):
    """Chemistry rows: component name possibly split over lines, then ncols numeric values."""
    COMPS = ["Density", "Insoluble solids", "Na+", "Al", "K+", "Si", "OH-", "NO3-", "CO32-",
             "NO2-", "SO42-", "PO43-", "C2O42-", "HCO2-", "F-", "Cl-", "Total Hg", "Methyl Hg",
             "Total Organic Carbon", "TOC"]
    chem = {c: {} for c in colnames}
    i = 0
    while i < len(lines):
        comp = None
        for c in COMPS:
            if lines[i] == c or lines[i].startswith(c + " ") or lines[i].startswith(c + "\u00a0"):
                comp = c
                break
        if comp:
            # collect numeric tokens from this line onward until ncols reached
            j = i
            toks = []
            while j < len(lines):
                toks.extend(lines[j].split())
                nums = [x for x in toks if numtok(x)[0] is not None or x.strip() == "---"]
                if len(nums) >= ncols or (j > i and any(lines[j] == c2 for c2 in COMPS)):
                    break
                j += 1
            # pair tokens in order: value (M) — take every OTHER token when parens present
            vals = []
            k = 0
            while k < len(toks) and len(vals) < ncols:
                x = toks[k]
                if x.strip() == "---":
                    vals.append(None)
                    k += 1
                    continue
                v, f = numtok(x)
                if v is not None:
                    vals.append(v)
                    # skip the following parenthetical molar value
                    if k + 1 < len(toks) and toks[k + 1].startswith("("):
                        k += 2
                        continue
                k += 1
            for c, v in zip(colnames, vals):
                if v is not None:
                    chem[c][comp] = v
            i = j + 1
        else:
            i += 1
    return chem


def _salt_rad_table(lines, ncols, colnames):
    """Rad rows: analyte name (maybe 2 lines) then ncols values ('---' allowed)."""
    NU = ["137Cs", "137mBa", "Total gamma", "Beta Count", "Total beta, Cs removed",
          "Total beta, without Cs", "Total alpha, Cs removed", "Total alpha", "Total beta",
          "238Pu", "239Pu", "240Pu", "241Pu", "242Pu", "244Pu", "233U", "234U", "235U",
          "236U", "238U", "90Sr", "90Y", "3H", "14C", "99Tc", "126Sn", "129I", "237Np", "244Cm"]
    rad = {c: {} for c in colnames}
    # join name-split lines: if a line matches a NU prefix but the row values aren't on it, keep scanning
    i = 0
    cur = None
    vals = []
    while i < len(lines):
        l = lines[i]
        matched = None
        for nu in NU:
            if l == nu or l.startswith(nu):
                matched = nu
                break
        if matched and cur is None:
            cur = matched
            # values on the same line?
            rest = l[len(matched):].strip()
            vals = []
            for x in rest.split():
                if x.strip() == "---":
                    vals.append(None)
                else:
                    v, f = numtok(x)
                    if v is not None:
                        vals.append(v)
            i += 1
        elif cur is not None:
            # continuation: numeric lines until ncols
            for x in l.split():
                if x.strip() == "---":
                    vals.append(None)
                    continue
                v, f = numtok(x)
                if v is not None:
                    vals.append(v)
            i += 1
            if len(vals) >= ncols:
                for c, v in zip(colnames, vals[:ncols]):
                    if v is not None:
                        rad[c][cur] = v
                cur = None
                vals = []
        else:
            i += 1
    return rad


def parse_salt_batches():
    out = []
    # FY23: batches 8, 9 — 6 columns: 8f, 8uf, 9f, 9uf, 9f-AL, 9uf-AL (use SRNL filtered as primary)
    t = (RAW / "SRNL_FY23_SaltWasteQualification.txt").read_text(errors="replace")
    chem_lines = lines_between(t, "Table 3-1. SWPF Salt Batch 8 and 9 Density (g/mL) and Composition (mg/L (M)).", "Note:  molar values", -1)
    chem = _salt_chem_table(chem_lines, 3, ["sb8", "sb9_srnl", "sb9_al"])
    rad_lines = lines_between(t, "Table 3-2.  SWPF Salt Batch 8 and 9 Radionuclide Activities", "* replicates", -1)
    rad = _salt_rad_table(rad_lines, 6, ["sb8_f", "sb8_uf", "sb9_f", "sb9_uf", "sb9_f_al", "sb9_uf_al"])
    out.append({"report": "SRNL-STI-2024-00436", "sample_year": 2024, "type": "salt_batch",
                "samples": {
                    "SWPF Salt Batch 8 (Tank 40, SRNL filtered)": {"chem_mg_per_L": chem["sb8"], "rad_pCi_per_mL": rad["sb8_f"]},
                    "SWPF Salt Batch 9 (Tank 40, SRNL filtered)": {"chem_mg_per_L": chem["sb9_srnl"], "rad_pCi_per_mL": rad["sb9_f"]},
                }})
    # FY24: batches 10-13 — 4 columns
    t = (RAW / "SRNL_FY24_SaltWasteQualification.txt").read_text(errors="replace")
    chem_lines = lines_between(t, "Table 3-1. SWPF Salt Batch 10, 11, 12, and 13 Density", "Note:  molar values", -1)
    chem = _salt_chem_table(chem_lines, 4, ["sb10", "sb11", "sb12", "sb13"])
    rad_lines = lines_between(t, "Table 3-2.  SWPF Salt Batch 10 and 11 Radionuclide Activities", "Table 3-3.", -1)
    rad1011 = _salt_rad_table(rad_lines, 6, ["sb10_f_al", "sb10_uf_al", "sb10_f_srnl", "sb11_f_al", "sb11_uf_al", "sb11_f_srnl"])
    rad_lines = lines_between(t, "Table 3-3.  SWPF Salt Batch 12 and 13 Radionuclide Activities", "* replicates", -1)
    rad1213 = _salt_rad_table(rad_lines, 4, ["sb12_f_al", "sb12_uf_al", "sb13_f_al", "sb13_uf_al"])
    out.append({"report": "SRNL-STI-2025-00489", "sample_year": 2025, "type": "salt_batch",
                "samples": {
                    "SWPF Salt Batch 10 (SRNL filtered)": {"chem_mg_per_L": chem["sb10"], "rad_pCi_per_mL": rad1011["sb10_f_srnl"] or rad1011["sb10_f_al"]},
                    "SWPF Salt Batch 11 (SRNL filtered)": {"chem_mg_per_L": chem["sb11"], "rad_pCi_per_mL": rad1011["sb11_f_srnl"] or rad1011["sb11_f_al"]},
                    "SWPF Salt Batch 12 (SWPF-AL filtered)": {"chem_mg_per_L": chem["sb12"], "rad_pCi_per_mL": rad1213["sb12_f_al"]},
                    "SWPF Salt Batch 13 (SWPF-AL filtered)": {"chem_mg_per_L": chem["sb13"], "rad_pCi_per_mL": rad1213["sb13_f_al"]},
                }})
    # Salt Batch 14 (Tank 21H): analyte / WAC limit / result
    t = (RAW / "SRNL_SaltBatch14_Tank21H_qualification.txt").read_text(errors="replace")
    lines = lines_between(t, "Table 1.  Analytical Results", "Table 2.", -1)
    rad = {}
    NU = re.compile(r"^(\d{1,3}[A-Z][a-z]?|Cs-137|Sr-90|Tc-99|I-129|C-14|H-3|Np-237|Am-241|Cm-244|Se-79|Zr-93|Sn-126|Cl-36|Ni-59|Ni-63|Nb-94|Sb-125|Total alpha|Total beta)$")
    i = 0
    while i < len(lines):
        m = NU.match(lines[i])
        if m:
            j = i + 1
            vals = []
            while j < len(lines) and not NU.match(lines[j]):
                for x in lines[j].split():
                    v, f = numtok(x)
                    if v is not None:
                        vals.append((v, f))
                j += 1
            if len(vals) >= 2:
                # layout: result (uncertainty%) then WAC requirement
                rad[m.group(1)] = {"result_pCi_per_mL": vals[0][0], "flag": vals[0][1], "wac_limit": vals[1][0]}
            elif len(vals) == 1:
                rad[m.group(1)] = {"result_pCi_per_mL": vals[0][0], "flag": vals[0][1], "wac_limit": None}
            i = j
        else:
            i += 1
    sb14 = {"rad_pCi_per_mL": {k: v["result_pCi_per_mL"] for k, v in rad.items()},
            "wac_limits": {k: v["wac_limit"] for k, v in rad.items() if v["wac_limit"] is not None}}
    out.append({"report": "Salt Batch 14 qualification sample (Tank 21H), SRNL", "sample_year": 2025,
                "type": "salt_batch",
                "samples": {"SWPF Salt Batch 14 (Tank 21H)": sb14}})
    return out


def parse_prft():
    t = (RAW / "SRNL_PRFT_Batches15_22_26.txt").read_text(errors="replace")
    rec = {"report": "SRNL PRFT Batches 15/22/26 characterization", "sample_year": 2025, "type": "prft_slurry"}
    # Table 3-2 slurry elemental (2 batch columns? check layout) - simpler: element then first numeric
    lines = lines_between(t, "Table 3-2. Elemental Composition of the PRFT Slurry", "Table 3-3", -1)
    chem = {}
    i = 0
    while i < len(lines):
        if lines[i] in ELEM_SET or lines[i] in ("Na+", "K+", "OH-", "NO3-", "NO2-", "CO3-2", "SO4-2", "F-", "Cl-", "PO4-3", "Density", "wt% Solids", "Wt % Solids"):
            j = i + 1
            vals = []
            while j < len(lines) and lines[j] not in ELEM_SET:
                v, f = numtok(lines[j])
                if v is not None:
                    vals.append(v)
                j += 1
            if vals:
                chem[lines[i]] = vals  # multiple columns = batch 15, 22, 26
            i = j
        else:
            i += 1
    rec["slurry_chem_by_element"] = chem
    # rad tables (table numbers differ per batch: 3-7, 3-8, 3-9)
    rads = {}
    for b, mk, nxt in [("15", "Table 3-7. Radionuclide Results for PRFT Batch 15", "Table 3-8."),
                       ("22", "Table 3-8. Radionuclide Results for PRFT Batch 22", "Table 3-9."),
                       ("26", "Table 3-9. Radionuclide Results for PRFT Batch 26", "Table 3-10.")]:
        lines = lines_between(t, f"{mk} Dried Unwashed Solids", nxt, -1)
        rad = {}
        NU = re.compile(r"^(\d{2,3}[A-Z][a-z]?|Nb-93m|Ni-59|Ni-63|Se-79|Zr-93|Tc-99|Sn-126|Cs-137|Sm-151|Th-229|Sr-90|I-129|C-14|H-3|Am-241|Am-243|Pu-238|Pu-239|Pu-240|Pu-241|U-233|U-234|U-235|U-236|U-238|Np-237|Cm-244)$")
        i = 0
        while i < len(lines):
            m = NU.match(lines[i])
            if m:
                j = i + 1
                val, flag = None, ""
                while j < len(lines) and not NU.match(lines[j]):
                    v, f = numtok(lines[j])
                    if v is not None and val is None:
                        val, flag = v, f
                        break
                    j += 1
                if val is not None:
                    rad[m.group(1)] = {"uCi_per_g_dried_solids": val, "flag": flag}
                i = j
            else:
                i += 1
        rads[b] = rad
    rec["batch_rad_uCi_per_g"] = rads
    return rec


def main():
    out = {
        "tank51_sludge_batch11": parse_sb11(),
        "dwpf_sludge_batch10": parse_sb10(),
        "swpf_salt_batches": parse_salt_batches(),
        "prft": parse_prft(),
    }
    p = OUT / "srnl_current_waste.json"
    p.write_text(json.dumps(out, indent=1))
    s11 = out["tank51_sludge_batch11"]
    sb10 = out["dwpf_sludge_batch10"]
    sb = out["swpf_salt_batches"]
    print(json.dumps({
        "sb11_slurry_elements": len(s11["slurry_elemental_ug_per_g"]),
        "sb11_slurry_UPu": len(s11["slurry_U_Pu_isotopes_dpm_per_g"]),
        "sb11_supernate_elements": len(s11["supernate_elemental_mg_per_L"]),
        "sb11_supernate_anions": len(s11["supernate_anions_mg_per_L"]),
        "sb11_soluble": len(s11["soluble_split_Na_Cr_Hg_S"]),
        "sb10_rad": len(sb10["radionuclides"]),
        "salt_chem": {k: len(v.get("chem_mg_per_L", {})) for r in sb[:2] for k, v in r["samples"].items()},
        "salt_rad": {k: len(v.get("rad_pCi_per_mL", {})) for r in sb[:2] for k, v in r["samples"].items()},
        "sb14_rad": len(sb[2]["samples"]["SWPF Salt Batch 14 (Tank 21H)"]["rad_pCi_per_mL"]),
        "prft_chem_elements": len(out["prft"]["slurry_chem_by_element"]),
        "prft_rad": {b: len(r) for b, r in out["prft"]["batch_rad_uCi_per_g"].items()},
    }, indent=1))
    # spot checks
    print("SB11 Al slurry:", s11["slurry_elemental_ug_per_g"].get("Al"))
    print("SB11 supernate Na:", s11["supernate_elemental_mg_per_L"].get("Na"))
    print("SB11 Cs-137 supernate:", s11["supernate_anions_mg_per_L"].get("Cs-137"))
    print("SB10 Cs-137:", sb10["radionuclides"].get("Cs-137"))
    print("SB8 Na:", sb[0]["samples"]["SWPF Salt Batch 8 (Tank 40, SRNL filtered)"]["chem_mg_per_L"].get("Na+"))
    print("SB8 137Cs:", sb[0]["samples"]["SWPF Salt Batch 8 (Tank 40, SRNL filtered)"]["rad_pCi_per_mL"].get("137Cs"))


if __name__ == "__main__":
    main()
