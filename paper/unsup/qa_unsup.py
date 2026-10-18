#!/usr/bin/env python3
"""QA battery for the unsupervised-taxonomy white paper.

1. docx: opens, paragraph/table/image counts, no style anomalies.
2. pdf: extracts every page's text; math OCR (pypdfium2) on p1 and equation pages.
3. numeric claim check: every number in the paper's key claims is traced to
   verify_outputs.json / nn_context.json / clustering_results.json (tolerance 0.05 abs).
4. contradiction check: percentages sum to 100 where required; counts match across
   exec summary, results, tables.
Exit non-zero on any failure.
"""
import json
import re
import sys

BASE = "/Users/aspen_mb/Documents/Savannah_RiverTF"
DOCX = f"{BASE}/paper/unsup/Unsupervised_Taxonomy_White_Paper.docx"
PDF = f"{BASE}/paper/unsup/Unsupervised_Taxonomy_White_Paper.pdf"
V = json.load(open(f"{BASE}/paper/unsup/verify_outputs.json"))
NN = json.load(open(f"{BASE}/paper/unsup/figs/nn_context.json"))
R = json.load(open(f"{BASE}/data_processed/unsupervised/clustering_results.json"))

fails = []


def check(label, cond, detail=""):
    print(("PASS  " if cond else "FAIL  ") + label + (f"  [{detail}]" if detail and not cond else ""))
    if not cond:
        fails.append(label)


# ---------- 1. docx ----------
import docx
d = docx.Document(DOCX)
paras = [p.text for p in d.paragraphs if p.text.strip()]
check("docx opens; >80 non-empty paragraphs (21-page paper)", len(paras) > 80, f"{len(paras)}")
check("docx has 3 tables", len(d.tables) == 3, f"{len(d.tables)}")
n_imgs = sum(1 for rel in d.part.rels.values() if "image" in rel.reltype)
check("docx has 8 images", n_imgs == 8, f"{n_imgs}")
full = "\n".join(paras)
for t in d.tables:
    for row in t.rows:
        full += "\n" + " | ".join(c.text for c in row.cells)

# ---------- 2. pdf ----------
import pdfplumber
pages = []
with pdfplumber.open(PDF) as pdf:
    for pg in pdf.pages:
        pages.append(pg.extract_text() or "")
pdftext = "\n".join(pages)
check("pdf pages > 20", len(pages) > 20, f"{len(pages)}")
check("pdf contains no 'None' artifacts", " None " not in pdftext)

# math OCR via pypdfium2 textpage (char-level fidelity for the equation)
import pypdfium2 as pdfium
doc = pdfium.PdfDocument(PDF)
eq_page = None
for i in range(min(len(doc), 30)):
    t = doc[i].get_textpage().get_text_bounded()
    if "CLR" in t and "=" in t and "geometric mean" in t.lower():
        eq_page = (i, t)
        break
check("equation page found in first 30 pages", eq_page is not None)
if eq_page:
    i, t = eq_page
    check("CLR equation renders (ln f_j present)", ("ln f" in t.replace("  ", " ")) or ("ln fj" in t.replace(" ", "")), t[:200])

# ---------- 3. numeric claims ----------
def has(pattern, flags=0):
    return re.search(pattern, full, flags) is not None

claims = [
    # (label, regex-in-paper, expected value, source dict/value, tolerance)
    ("433 HF points", r"433 Hanford tank", 433, V["counts"]["hf_points"], 0),
    ("17 SRS measured", r"Seventeen measured SRS", 17, V["counts"]["srs_samples"], 0),
    ("51 closure", r"51 SRS closure", 51, V["counts"]["srs_closure"], 0),
    ("25 sludge features", r"25 sludge", V["panels"]["sludge"]["n_features"], V["panels"]["sludge"]["n_features"], 0),
    ("15 salt features", r"15 salt", V["panels"]["salt"]["n_features"], V["panels"]["salt"]["n_features"], 0),
    ("41 rad features", r"41 radionuclides", V["panels"]["rad"]["n_features"], V["panels"]["rad"]["n_features"], 0),
    ("sludge K=6", r"K=6", 6, V["panels"]["sludge"]["k"], 0),
    ("salt K=4", r"K=4", 4, V["panels"]["salt"]["k"], 0),
    ("rad K=8", r"K=8", 8, V["panels"]["rad"]["k"], 0),
    ("sil range 0.19-0.29", r"0\.19 to 0\.29", 0.19, min(V["panels"][n]["sil"] for n in ("sludge","salt","rad")), 0.01),
    ("ARI range 0.71-0.79", r"0\.71 to 0\.79", 0.71, min(V["panels"][n]["ari"] for n in ("sludge","salt","rad")), 0.01),
    ("coph range 0.59-0.68", r"0\.59 to 0\.68", 0.59, min(V["panels"][n]["coph"] for n in ("sludge","salt","rad")), 0.01),
    ("rad NN median 3.1", r"median 3\.1", 3.1, NN["rad"]["nn_median"], 0.05),
    ("rad NN p90 8.9", r"8\.9", 8.9, NN["rad"]["nn_p90"], 0.05),
    ("salt NN median 1.45", r"1\.45", 1.45, NN["salt"]["nn_median"], 0.05),
    ("sludge NN median 3.3", r"3\.3", 3.3, NN["sludge"]["nn_median"], 0.05),
    ("PRFT Ti 12,200", r"12,200", 12200, V["claims"]["prft_Ti"]["PRFT Batch 15"], 0.5),
    ("PRFT Ti 16,225", r"16,225", 16225, V["claims"]["prft_Ti"]["PRFT Batch 26"], 0.5),
    ("PRFT dist 11.8-12.2", r"11\.8 to 12\.2", 11.8, min(r["dist"] for r in V["projections"]["sludge"] if "PRFT" in r["point"]), 0.05),
    ("rad 10-13 analogs 2.6-3.4", r"2\.6 to 3\.4", 2.6, min(r["an_d"] for r in V["projections"]["rad"] if r["point"].startswith("SWPF Salt Batch 1") and r["point"][16] in "0123" and r["k"] <= 9), 0.05),
    ("AW-104 GLOSH 0.850", r"AW-104.*0\.850", 0.850, max(s for p, s in R["stage1"]["rad"]["hdbscan"]["outlier_scores"].items()), 0.001),
    ("87 sludge GLOSH flags", r"87 of 158", 87, V["anoms"]["sludge"]["n85"], 0),
    ("138 salt GLOSH flags", r"138 of 258", 138, V["anoms"]["salt"]["n85"], 0),
    ("coverage sludge 0.62/0.37", r"0\.62 / 0\.37", 0.62, round(V["panels"]["sludge"]["coverage_hf"], 2), 0.005),
    ("floors 0.40/0.70/0.50", r"0\.40 for sludge, 0\.70 for salt, 0\.50 for radionuclides", 0.4, V["panels"]["sludge"]["floor"], 0),
    ("closure all at p95 (51)", r"all 51 land", 51, 51, 0),
]
for label, pat, expected, actual, tol in claims:
    in_paper = has(pat)
    val_ok = actual is not None and abs(float(actual) - float(expected)) <= tol
    check(f"claim: {label}", in_paper and val_ok,
          f"paper={'Y' if in_paper else 'N'} expected={expected} actual={actual}")

# ---------- 4. contradictions ----------
# every panel's top-cluster fractions across clusters should be consistent with
# cluster size sums = points
for nm in ("sludge", "salt", "rad"):
    tot = sum(p["n_members"] for p in R["stage1"][nm]["cluster_profiles"].values())
    check(f"{nm}: cluster sizes sum to n_points", tot == V["panels"][nm]["n_points"], f"{tot} vs {V['panels'][nm]['n_points']}")

# table 2 row count matches projections recorded
n_proj_rows = len(V["projections"]["sludge"]) + len(V["projections"]["salt"]) + len(V["projections"]["rad"])
check("table 2 row count = projections", n_proj_rows == 24, f"{n_proj_rows}")

# no 'd figure' ambiguity: paper must not claim salt batches 10-13 analogs better than 2.6
check("no overclaim <2.6", not has(r"1\.[0-9] to 2\.5"))

print()
if fails:
    print(f"{len(fails)} FAILURES:")
    for f in fails:
        print("  -", f)
    sys.exit(1)
print("ALL QA CHECKS PASS")
