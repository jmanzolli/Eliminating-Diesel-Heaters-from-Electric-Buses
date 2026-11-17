"""
Non-heating auxiliary load for the v11 model (2026-11-11).

The telemetry reports, per run, the net energy drawn from the battery
("Net Energy Used", equal to SoC used x effective capacity on every run), the
drivetrain energy ("DT Energy Used") and the electric cabin-heater energy
("eHeat Energy Used", about 21 kW x electric heating time). The remainder,

    aux = net - drivetrain - electric heat,

is the energy of every other consumer on the bus: air compressor, low-voltage
systems, pumps and fans, battery thermal management, air conditioning in
summer. Models up to v10 did not carry it.

This script fits the remainder as a mean power per weather band on the same
filtered runs as the traction interface (make_traction_v7.py),

    P_aux(band) = sum of aux energy in the band / sum of time in service,

pools the extreme and severe bands (the severe band has four runs), and
writes
  aux_v11.json                    band powers, run counts, accuracy metrics
  <inputs>_v11*.json              every v9 inputs file with "aux_kw_bands"
  supp_tables/tab_aux_v11.tex     band table for the appendix (if TAB_OUT set)

Usage: python3 make_aux_v11.py
"""
import glob
import json
import os

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TTC_XLSX = os.environ.get("TTC_XLSX", os.path.join(
    HERE, "data", "TTC_Preprocessed_version2_2.xlsx"))
# (lo, hi, key in the inputs tables)
BANDS = {"offseason": (5, 99, "17.4"), "mild": (0, 5, "2.5"),
         "cold": (-5, 0, "-2.5"), "verycold": (-10, -5, "-7.5"),
         "extreme": (-15, -10, "-12.5"), "severe": (-99, -15, "-17.5")}
POOL = ("extreme", "severe")
KW_RANGE = (0.0, 30.0)          # plausibility filter on run-level power

df = pd.read_excel(TTC_XLSX)
df["route"] = (df["Route  Number"].astype(str).str.strip()
               .str.replace(r"\.0$", "", regex=True))
d = df[(df["Distance [km]"] > 3) & (df["DT Energy Used [kWh]"] > 0)
       & df["Avg Ambient Temp [degC]"].notna()
       & (df["Vehicle Speed [km/h]"] > 5)].copy()
d["ekm"] = d["DT Energy Used [kWh]"] / d["Distance [km]"]
d = d[(d["ekm"] > 0.3) & (d["ekm"] < 4)].copy()
n_traction = len(d)
d["T"] = d["Avg Ambient Temp [degC]"].astype(float)
d["h"] = d["Time_Total [hr]"].astype(float)
d["aux"] = (d["Net Energy Used [kWh]"] - d["DT Energy Used [kWh]"]
            - d["eHeat Energy Used [kWh]"])
d["kw"] = d["aux"] / d["h"]
d = d[(d["h"] > 0) & (d["kw"] > KW_RANGE[0]) & (d["kw"] < KW_RANGE[1])].copy()


def band_of(T):
    for w, (lo, hi, _) in BANDS.items():
        if lo <= T < hi:
            return w
    raise ValueError(T)


d["band"] = [band_of(T) for T in d["T"]]
stats = {}
for w in BANDS:
    s = d[d["band"] == w]
    stats[w] = {"n": int(len(s)), "hours": round(float(s["h"].sum()), 1),
                "kw": round(float(s["aux"].sum() / s["h"].sum()), 3),
                "kw_run_mean": round(float(s["kw"].mean()), 3),
                "kw_run_sd": round(float(s["kw"].std()), 3),
                "net_kwh_km": round(float(s["Net Energy Used [kWh]"].sum()
                                          / s["Distance [km]"].sum()), 3),
                "dt_kwh_km": round(float(s["DT Energy Used [kWh]"].sum()
                                         / s["Distance [km]"].sum()), 3),
                "eheat_kwh_km": round(float(s["eHeat Energy Used [kWh]"].sum()
                                            / s["Distance [km]"].sum()), 3),
                "aux_kwh_km": round(float(s["aux"].sum()
                                          / s["Distance [km]"].sum()), 3)}
pool = d[d["band"].isin(POOL)]
kw_pool = round(float(pool["aux"].sum() / pool["h"].sum()), 3)
used = {w: (kw_pool if w in POOL else stats[w]["kw"]) for w in BANDS}
aux_bands = {BANDS[w][2]: used[w] for w in BANDS}

# accuracy of the band-power interface (same aggregation levels as traction)
d["pred_kw"] = d["band"].map(used)
d["pred"] = d["pred_kw"] * d["h"]
metrics = {
    "run_MAE_kW": round(float((d["pred_kw"] - d["kw"]).abs().mean()), 3),
    "run_cv": round(float((d["kw"] / d["pred_kw"]).std()), 3),
    "band_energy_ratio": {w: round(float(
        d[d["band"] == w]["pred"].sum() / d[d["band"] == w]["aux"].sum()), 4)
        for w in BANDS},
}
rt = d.groupby("route").agg(pred=("pred", "sum"), obs=("aux", "sum"), n=("aux", "size"))
rt = rt[rt["n"] >= 30]
metrics["route_energy_MAPE_pct"] = round(float(
    (100 * (rt["pred"] / rt["obs"] - 1).abs()).mean()), 2)
r52 = d[d["route"] == "52"]
metrics["r52"] = {"n": int(len(r52)),
                  "aux_energy_ratio_pred_over_obs": round(float(
                      r52["pred"].sum() / r52["aux"].sum()), 4),
                  "aux_kwh_km": round(float(r52["aux"].sum()
                                            / r52["Distance [km]"].sum()), 3),
                  "net_kwh_km": round(float(r52["Net Energy Used [kWh]"].sum()
                                            / r52["Distance [km]"].sum()), 3)}

out = {"note": "aux = net battery energy - drivetrain - electric cabin heat; "
               "band power = band aux energy / band time in service; "
               "extreme and severe pooled",
       "n_traction_pool": n_traction, "n_runs": int(len(d)),
       "kw_filter": list(KW_RANGE), "bands": stats, "pooled": list(POOL),
       "kw_pooled": kw_pool, "aux_kw_used": used, "aux_kw_bands": aux_bands,
       "metrics": metrics}
json.dump(out, open(os.path.join(HERE, "aux_v11.json"), "w"), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != "bands"}, indent=1))
for w, s in stats.items():
    print(f"{w:10s} n {s['n']:5d}  kW {s['kw']:.2f}  net {s['net_kwh_km']:.3f} "
          f"= dt {s['dt_kwh_km']:.3f} + heat {s['eheat_kwh_km']:.3f} "
          f"+ aux {s['aux_kwh_km']:.3f} kWh/km")

# ---------------------------------------------------------------- inputs
NOTE = ("v11: non-heating auxiliary load, mean power per band (kW) from "
        "make_aux_v11.py; extreme and severe bands pooled")
made = []
for src in sorted(glob.glob(os.path.join(HERE, "route52_inputs_v9*.json"))
                  + glob.glob(os.path.join(HERE, "garage_inputs_v9*.json"))):
    inp = json.load(open(src))
    inp["aux_kw_bands"] = aux_bands
    inp["aux_note"] = NOTE
    dst = src.replace("_v9", "_v11")
    json.dump(inp, open(dst, "w"), indent=1)
    made.append(os.path.basename(dst))
print("inputs written:", ", ".join(made))

# ---------------------------------------------------------------- table
tab_dir = os.environ.get("TAB_OUT")
if tab_dir:
    names = {"mild": "Mild", "cold": "Cold", "verycold": "Very cold",
             "extreme": "Extreme", "severe": "Severe", "offseason": "Off-season"}
    rows = []
    for w in ("mild", "cold", "verycold", "extreme", "severe", "offseason"):
        s = stats[w]
        rows.append(f"{names[w]} & {s['n']:,} & {s['net_kwh_km']:.2f} & "
                    f"{s['dt_kwh_km']:.2f} & {s['eheat_kwh_km']:.2f} & "
                    f"{s['aux_kwh_km']:.2f} & {s['kw']:.1f} & {used[w]:.1f} \\\\")
    tex = ("% GENERATED by make_aux_v11.py from the telemetry workbook.\n"
           "% Do not edit by hand - regenerate instead.\n"
           "\\begin{table}[pos=htbp]\n"
           "\\caption{Net battery energy by weather band and its components "
           "on the filtered runs, and the auxiliary power used in the model.}\n"
           "\\label{tab:aux}\n\\centering\n\\small\n"
           "\\fittabnat{@{}lrrrrrrr@{}}{\n\\toprule\n"
           "\\textbf{Band} & \\textbf{Runs} & \\textbf{Net} & "
           "\\textbf{Drivetrain} & \\textbf{Electric heat} & "
           "\\textbf{Auxiliary} & \\textbf{Auxiliary} & \\textbf{Model} \\\\\n"
           " & & \\multicolumn{4}{c}{(kWh/km)} & (kW) & (kW) \\\\\n"
           "\\midrule\n" + "\n".join(rows) + "\n\\bottomrule\n}\n\\end{table}\n")
    open(os.path.join(tab_dir, "tab_aux_v11.tex"), "w").write(tex)
    print("table written to", tab_dir)
