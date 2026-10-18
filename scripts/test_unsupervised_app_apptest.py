#!/usr/bin/env python3
"""AppTest verification for dashboard/unsupervised_app.py — the truth gate."""
from streamlit.testing.v1 import AppTest

APP = "/Users/aspen_mb/Documents/Savannah_RiverTF/dashboard/unsupervised_app.py"

at = AppTest.from_file(APP, default_timeout=180).run()
assert not at.exception, f"EXCEPTION: {at.exception}"

# --- structure: 6 tabs
tab_labels = [t.label for t in at.tabs]
assert tab_labels == ["Overview", "Taxonomy explorer", "SRS projections", "Anomalies",
                      "Dataspace", "Methods"], tab_labels
print("tabs OK:", tab_labels)

# --- overview metrics (4 overview + 6 dataspace/projection metrics)
assert len(at.metric) >= 4, f"expected >=4 metrics, got {len(at.metric)}"
print("metrics OK:", len(at.metric))

# --- sidebar panel radio (options are format_func'd labels)
panel_radio = next(r for r in at.radio if r.key == "panel")
assert panel_radio.options == ["Sludge elements", "Salt anions/cations", "Radionuclides"]
print("panel radio OK:", panel_radio.options)

# --- exercise sidebar panel switching (sludge -> salt -> rad -> sludge)
for val in ["salt", "rad", "sludge"]:
    panel_radio.set_value(val).run()
    assert not at.exception, f"exception after panel={val}: {at.exception}"
print("panel switching OK (all 3 panels render without exception)")

# --- charts render: count plotly arrows after switching back
at.run()
assert not at.exception
n_plots = len(at.get("plotly_chart"))
assert n_plots >= 6, f"expected >=6 plotly charts, got {n_plots}"
print(f"plotly charts OK: {n_plots}")

# --- exercise dataspace 'Compare to another point' mode
mode_radio = next(r for r in at.radio if r.label == "Point B")
mode_radio.set_value("Compare to another point").run()
assert not at.exception, f"exception in point-vs-point mode: {at.exception}"
sel_b = next(s for s in at.selectbox if s.label == "Point B")
# cross-panel Point B (last option = rad panel) -> graceful info, no crash
sel_b.set_value(sel_b.options[-1]).run()
assert not at.exception, f"exception after cross-panel Point B: {at.exception}"
# same-panel Point B (option 1 = sludge) -> metrics render
sel_b.set_value(sel_b.options[1]).run()
assert not at.exception, f"exception after same-panel Point B: {at.exception}"
metrics_now = [m.label for m in at.metric]
assert "Shared support k" in metrics_now and "Aitchison distance" in metrics_now
print("dataspace point-vs-point OK:", metrics_now)

# --- anomaly threshold slider
slider = next(s for s in at.slider if s.label == "Outlier-score threshold")
slider.set_value(0.95).run()
assert not at.exception, f"exception after slider: {at.exception}"
print("anomaly slider OK at 0.95")

# --- proj track radio
track_radio = next(r for r in at.radio if r.label == "Track")
track_radio.set_value("closure-2032").run()
assert not at.exception, f"exception after track switch: {at.exception}"
track_radio.set_value("both").run()
assert not at.exception, f"exception after track=both: {at.exception}"
print("projection track radio OK")

print("\nAppTest gate: ALL PASS")
