#!/usr/bin/env python3
"""Build the SRS vs Hanford Tank Waste Comparison Dashboard (self-contained interactive HTML).

Data pulled live from the SQLite DB (SRS tables + Hanford BBI tables).
Output: /Users/aspen_mb/Documents/Savannah_RiverTF/dashboard/srs_hanford_comparison.html
"""
import json
import sqlite3
from pathlib import Path

BASE = Path("/Users/aspen_mb/Documents/Savannah_RiverTF")
DB = BASE / "srs_tank_waste.db"
OUT = BASE / "dashboard" / "srs_hanford_comparison.html"
OUT.parent.mkdir(exist_ok=True)


def main():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # ---------------- SRS per-tank data ----------------
    srs_tanks = []
    tank_rows = cur.execute(
        "SELECT tank_id, farm, tank_type, capacity_gal, status, closure_date, residual_volume_gal FROM tanks ORDER BY tank_id").fetchall()
    for tid, farm, ttype, cap, status, closure, resid in tank_rows:
        # per-tank Ci from assigned-closure datasets (residual basis); actuals override where present
        row = cur.execute("""SELECT SUM(value_ci) FROM inventory_rad WHERE tank_id=? AND dataset IN
                             ('htf_assigned_closure','ftf_assigned_closure')""", (tid,)).fetchone()
        ci_assigned = row[0] or 0.0
        # actual where measured (18,19,16)
        row = cur.execute("""SELECT SUM(value_ci) FROM inventory_rad WHERE tank_id=? AND dataset IN
                             ('tank18_19_actual','tank16_final_actual')""", (tid,)).fetchone()
        ci_actual = row[0]
        # per-tank chem kg
        row = cur.execute("""SELECT SUM(value_kg) FROM inventory_chem WHERE tank_id=? AND dataset IN
                             ('htf_assigned_closure','ftf_assigned_closure')""", (tid,)).fetchone()
        kg = row[0] or 0.0
        # top nuclides for hover
        top = cur.execute("""SELECT nuclide, value_ci FROM inventory_rad WHERE tank_id=? AND dataset IN
                             ('htf_assigned_closure','ftf_assigned_closure') ORDER BY value_ci DESC LIMIT 5""", (tid,)).fetchall()
        srs_tanks.append({
            "id": f"{farm[0]}-{tid}", "tank": tid, "farm": farm, "type": ttype,
            "cap_kL": round(cap * 0.003785412, 1) if cap else None,
            "cap_gal": cap, "status": status, "closure": closure,
            "residual_gal": resid,
            "ci": round(ci_assigned, 2),
            "ci_actual": round(ci_actual, 2) if ci_actual else None,
            "kg": round(kg, 1),
            "top": [{"n": n, "v": round(v, 2)} for n, v in top],
        })

    # ---------------- Hanford per-tank data ----------------
    hf_tanks = []
    tanks = [r[0] for r in cur.execute("SELECT DISTINCT tank FROM hanford_bbi_volume ORDER BY tank")]
    for tid in tanks:
        name = cur.execute("SELECT tank_name FROM hanford_bbi WHERE tank=? LIMIT 1", (tid,)).fetchone()
        vol_rows = cur.execute("""SELECT waste_phase, SUM(volume) FROM hanford_bbi_volume
                                  WHERE tank=? AND units='kL' GROUP BY waste_phase""", (tid,)).fetchall()
        vol_kL = sum(v for _, v in vol_rows)
        # exclude drained voids & retained gas from wet volume
        wet = sum(v for p, v in vol_rows if "Drained" not in p and "Retained" not in p)
        ci = cur.execute("SELECT SUM(inventory) FROM hanford_bbi WHERE tank=? AND units='Ci'", (tid,)).fetchone()[0] or 0
        kg = cur.execute("SELECT SUM(inventory) FROM hanford_bbi WHERE tank=? AND units='kg'", (tid,)).fetchone()[0] or 0
        top = cur.execute("""SELECT analyte, SUM(inventory) FROM hanford_bbi WHERE tank=? AND units='Ci'
                             GROUP BY analyte ORDER BY 2 DESC LIMIT 5""", (tid,)).fetchall()
        phases = {p: round(v, 1) for p, v in vol_rows if v and "Drained" not in p and "Retained" not in p}
        # farm = first letter group
        farm = "A-Farm" if tid.startswith("A") and not tid.startswith("AN") and not tid.startswith("AP") and not tid.startswith("AW") and not tid.startswith("AZ") else \
               {"AN": "AN-Farm", "AP": "AP-Farm", "AW": "AW-Farm", "AZ": "AZ-Farm", "AY": "AY-Farm",
                "B": "B-Farm", "BX": "BX-Farm", "BY": "BY-Farm", "C": "C-Farm", "S": "SX-Farm",
                "SY": "SY-Farm", "T": "T-Farm", "TX": "TX-Farm", "TY": "TY-Farm", "U": "U-Farm"}.get(tid[:2], "B-Farm" if tid[0] == "B" else tid[0] + "-Farm")
        hf_tanks.append({
            "id": tid, "name": name[0] if name else "241-" + tid, "farm": farm,
            "vol_kL": round(wet, 1), "vol_kgal": round(wet / 3785.412, 3),
            "ci": round(ci, 3), "kg": round(kg, 1), "phases": phases,
            "top": [{"n": n, "v": round(v, 3)} for n, v in top],
        })

    # ---------------- farm-level current inventories ----------------
    srs_current = {
        "total_mgal": 33.2, "total_mci": 191.0, "as_of": "2025-09-30",
        "sludge": {"mgal": 2.8, "mci": 106.0}, "supernate": {"mgal": 16.4, "mci": 75.0},
        "saltcake": {"mgal": 10.0, "mci": 10.0},
    }
    # Hanford phase totals (kL -> Mgal; Ci)
    hf_phases = {p: v for p, v in cur.execute("""SELECT waste_phase, SUM(volume) FROM hanford_bbi_volume
                 WHERE units='kL' AND waste_phase NOT LIKE 'Drained%' AND waste_phase NOT LIKE 'Retained%' GROUP BY waste_phase""")}
    hf_ci_total = cur.execute("SELECT SUM(inventory) FROM hanford_bbi WHERE units='Ci'").fetchone()[0]
    hf_by_phase_ci = {p: c for p, c in cur.execute("""SELECT
        CASE WHEN waste_phase LIKE 'Supernatant%' THEN 'Supernatant'
             WHEN waste_phase LIKE 'Saltcake%' THEN 'Saltcake'
             ELSE 'Sludge' END AS grp, SUM(inventory)
        FROM hanford_bbi WHERE units='Ci' GROUP BY grp""")}
    hf_salt_kL = sum(v for p, v in hf_phases.items() if "Saltcake" in p)
    hf_sludge_kL = sum(v for p, v in hf_phases.items() if "Sludge" in p)
    hf_sup_kL = sum(v for p, v in hf_phases.items() if "Supernatant" in p)
    hanford_current = {
        "total_mgal": round((hf_salt_kL + hf_sludge_kL + hf_sup_kL) / 3785.412, 1),
        "total_mci": round(hf_ci_total / 1e6, 1), "as_of": "2025-10-01 (BBI effective)",
        "sludge": {"mgal": round(hf_sludge_kL / 3785.412, 1), "mci": round(hf_by_phase_ci.get("Sludge", 0) / 1e6, 1)},
        "supernate": {"mgal": round(hf_sup_kL / 3785.412, 1), "mci": round(hf_by_phase_ci.get("Supernatant", 0) / 1e6, 1)},
        "saltcake": {"mgal": round(hf_salt_kL / 3785.412, 1), "mci": round(hf_by_phase_ci.get("Saltcake", 0) / 1e6, 1)},
        "n_tanks": 177,
    }
    # top-12 nuclides both sites
    srs_top = cur.execute("""SELECT nuclide, SUM(value_ci) FROM inventory_rad WHERE dataset IN
        ('htf_assigned_closure','ftf_assigned_closure') GROUP BY nuclide ORDER BY 2 DESC LIMIT 14""").fetchall()
    hf_top = cur.execute("""SELECT analyte, SUM(inventory) FROM hanford_bbi WHERE units='Ci'
        GROUP BY analyte ORDER BY 2 DESC LIMIT 14""").fetchall()

    # SRS current-waste samples (SB11 etc.) for the 'current chemistry' panel
    srs_samples = {}
    for sample, cat, an, val, unit in cur.execute("""SELECT sample, category, analyte, value, unit FROM current_waste_samples
            WHERE sample LIKE 'Tank 51%' OR sample LIKE 'Tank 40%' OR sample LIKE 'SWPF Salt Batch 8%' OR sample LIKE 'SWPF Salt Batch 12%'"""):
        srs_samples.setdefault(sample, []).append({"cat": cat, "analyte": an, "value": val, "unit": unit})

    conn.close()

    payload = {
        "srs_tanks": srs_tanks, "hf_tanks": hf_tanks,
        "srs_current": srs_current, "hanford_current": hanford_current,
        "srs_top": [{"n": n, "v": round(v, 1)} for n, v in srs_top],
        "hf_top": [{"n": n, "v": round(v, 1)} for n, v in hf_top],
        "srs_samples": srs_samples,
    }
    (BASE / "dashboard" / "dashboard_data.json").write_text(json.dumps(payload))
    print(f"payload: srs_tanks={len(srs_tanks)} hf_tanks={len(hf_tanks)} "
          f"srs_total_mci={srs_current['total_mci']} hf_total_mci={hanford_current['total_mci']} "
          f"srs_mgal={srs_current['total_mgal']} hf_mgal={hanford_current['total_mgal']}")


if __name__ == "__main__":
    main()
