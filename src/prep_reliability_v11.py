"""
Inputs for the out-of-sample reliability protocol, v11 model (2026-11-11).
Same decomposition as prep_reliability_v10.py, but the residual is that of
the NON-HEATING battery energy of a bus-day (net battery energy minus electric
cabin heat), because the v11 model carries the auxiliary load:

    r = (net - eHeat) / (traction interface x distance + P_aux(band) x hours)

The harness applies the drawn multiplier to traction and auxiliary energy
alike. Protocol of 2026-11-09 (items M2-M4): Runs on the analysis machine (needs the telemetry workbook and
the ECCC daily files; no solver).

Writes rel_inputs_v11.json with
  traction   Route 52 bus-day residual ratios (observed / planning interface)
             with their date and ambient temperature, decomposed as
             log r = mu_band + f_date + e:
               mu_band   band-conditional mean of log r (bands with fewer
                         than MIN_BAND_N bus-days borrow the mean of all
                         bus-days below -5 C, the "cold subset")
               f_date    date effects (mean log r of a date, centred), the
                         day-level factor common to every block of a day
               e         within-date deviations, block level
  temps      ECCC Toronto daily mean temperatures of the 24 winters
             (Nov-Mar 2002-03 .. 2025-26), grouped by band; the band counts
             reproduce data_v9/eccc_winter_bands_v9.json for 23 of 24
             winters (2002-03 differs by one day filled from the backup
             station)
  heat       residual scale of the companion thermal model (sigma = 1.66 kW
             on trip-averaged heating demand), used to derive a block-level
             heat-demand CV from the planning demand at the drawn temperature

Usage: python3 prep_reliability_v11.py
"""
import collections
import json
import os

import numpy as np
import pandas as pd

os.environ.setdefault("ROUTE_INPUTS", "route52_inputs_v11g.json")
import route52_prototype as R

HERE = os.path.dirname(os.path.abspath(__file__))
TTC_XLSX = os.environ.get("TTC_XLSX", os.path.join(HERE, "data",
                                                   "TTC_Preprocessed_version2_2.xlsx"))
OUT = os.environ.get("PREP_OUT", "rel_inputs_v11.json")
MIN_BAND_N = 30
SIGMA_HEAT_KW = 1.66


def band(T):
    # winter-day bands (Nov-Mar): every day at or above 0 C is "mild", as in
    # the planning weights; the off-season is a separate period, not a band
    if T >= 0:
        return "mild"
    if T >= -5:
        return "cold"
    if T >= -10:
        return "verycold"
    if T >= -15:
        return "extreme"
    return "severe"


# ------------------------------------------------------------- traction
df = pd.read_excel(TTC_XLSX)
df["route"] = (df["Route  Number"].astype(str).str.strip()
               .str.replace(r"\.0$", "", regex=True))
t = df[(df["route"] == "52") & (df["Distance [km]"] > 3)
       & (df["DT Energy Used [kWh]"] > 0)
       & df["Avg Ambient Temp [degC]"].notna()
       & (df["Vehicle Speed [km/h]"] > 5)].copy()
t["ekm"] = t["DT Energy Used [kWh]"] / t["Distance [km]"]
t = t[(t["ekm"] > 0.3) & (t["ekm"] < 4)]
assert R.aux_kw(0.0) > 0, "inputs carry no auxiliary load (need v11 inputs)"
t = t[t["Time_Total [hr]"] > 0].copy()
t["obs"] = t["Net Energy Used [kWh]"] - t["eHeat Energy Used [kWh]"]
t["pred"] = [R.e_traction_per_km(T, v) * km + R.aux_kw(T) * h for T, v, km, h in
             zip(t["Avg Ambient Temp [degC]"], t["Vehicle Speed [km/h]"],
                 t["Distance [km]"], t["Time_Total [hr]"])]
t["ratio"] = t["obs"] / t["pred"]
t["ratio_traction_only"] = t["ekm"] / np.array([
    R.e_traction_per_km(T, v) for T, v in
    zip(t["Avg Ambient Temp [degC]"], t["Vehicle Speed [km/h]"])])
t = t[(t["ratio"] > 0.3) & (t["ratio"] < 3.0)].copy()
t["date"] = pd.to_datetime(t["Date"]).dt.strftime("%Y-%m-%d")
t["T"] = t["Avg Ambient Temp [degC]"].astype(float)
t["band"] = [band(T) for T in t["T"]]
t["lr"] = np.log(t["ratio"])
n_all = len(t)
# v11: winter bus-days only (Nov-Mar). The auxiliary load includes summer air
# conditioning, whose day-to-day variation is not part of a winter day; with
# all months the residual sd is 0.098, against 0.063 in the winter months.
_mon = pd.to_datetime(t["Date"]).dt.month
t = t[_mon.isin([11, 12, 1, 2, 3])].copy()
# The snow day of 26 December 2025 (16.5 mm of precipitation at -4.8 C;
# fleet-wide drivetrain energy 1.17 kWh/km against about 0.75) is one date and
# cannot support a frequency. It is taken out of the pool and kept as a
# separate stress level: its fleet-wide non-heating energy ratio relative to
# the other winter days.
SNOW_DATE = "2025-12-26"
_all = df[(df["Distance [km]"] > 3) & (df["DT Energy Used [kWh]"] > 0)
          & df["Avg Ambient Temp [degC]"].notna() & (df["Time_Total [hr]"] > 0)
          & pd.to_datetime(df["Date"]).dt.month.isin([11, 12, 1, 2, 3])].copy()
_all["obs"] = _all["Net Energy Used [kWh]"] - _all["eHeat Energy Used [kWh]"]
_all["pred"] = [R.e_traction_per_km(T, v) * km + R.aux_kw(T) * h for T, v, km, h in
                zip(_all["Avg Ambient Temp [degC]"], _all["Vehicle Speed [km/h]"],
                    _all["Distance [km]"], _all["Time_Total [hr]"])]
_snow = pd.to_datetime(_all["Date"]).dt.strftime("%Y-%m-%d") == SNOW_DATE
_r_snow = float(_all[_snow]["obs"].sum() / _all[_snow]["pred"].sum())
_r_rest = float(_all[~_snow]["obs"].sum() / _all[~_snow]["pred"].sum())
SNOW = {"date": SNOW_DATE, "n_fleet_runs": int(_snow.sum()),
        "ratio": round(_r_snow / _r_rest, 4),
        "log_ratio": round(float(np.log(_r_snow / _r_rest)), 5),
        "route52_bus_days_removed": int((pd.to_datetime(t["Date"]).dt.strftime(
            "%Y-%m-%d") == SNOW_DATE).sum())}
t = t[pd.to_datetime(t["Date"]).dt.strftime("%Y-%m-%d") != SNOW_DATE].copy()
print("pool size", len(t), "winter bus-days of", n_all, "(v10 traction pool: 1377, all months)")

cold = t[t["T"] < -5]
mu_cold = float(cold["lr"].mean())
mu = {}
band_n = {}
for w in ("mild", "cold", "verycold", "extreme", "severe"):
    sub = t[t["band"] == w]
    band_n[w] = int(len(sub))
    mu[w] = float(sub["lr"].mean()) if len(sub) >= MIN_BAND_N else mu_cold

# day factor and within-date residuals, after removing the band mean
t["lr_c"] = t["lr"] - t["band"].map(lambda w: mu.get(w, mu["mild"]))
g = t.groupby("date")["lr_c"]
date_mean = g.mean()
date_n = g.size()
multi = date_n[date_n >= 2].index
f_date = (date_mean[multi] - date_mean[multi].mean()).values
within = (t[t["date"].isin(multi)]["lr_c"]
          - t[t["date"].isin(multi)]["date"].map(date_mean)).values
# small-sample correction: the date mean of n bus-days carries 1/n of the
# within-date variance, so the raw spread of date means overstates the day
# factor. Shrink the empirical date effects to the method-of-moments
# between-date variance.
s2_within = float(np.var(within, ddof=1))
n_bar = float(date_n[multi].mean())
s2_dates = float(np.var(f_date, ddof=1))
s2_between = max(0.0, s2_dates - s2_within / n_bar)
shrink = float(np.sqrt(s2_between / s2_dates)) if s2_dates > 0 else 0.0
f_date_shrunk = f_date * shrink
# within-date deviations are deflated by sqrt(n/(n-1)) on average; rescale
within = within * float(np.sqrt(n_bar / (n_bar - 1)))

trac = {"residual_of": "non-heating battery energy (traction + auxiliary)",
        "pool": "Route 52 bus-days, Nov-Mar, snow day excluded",
        "n_bus_days_all_months": int(n_all), "snow_day": SNOW,
        "sd_log_traction_only": round(float(np.log(t["ratio_traction_only"]).std()), 4),
        "n_bus_days": int(len(t)), "n_dates": int(date_n.size),
        "n_dates_multi": int(len(multi)), "mean_bus_days_per_date": round(n_bar, 2),
        "band_n": band_n, "min_band_n": MIN_BAND_N,
        "mu_log_ratio": {w: round(v, 5) for w, v in mu.items()},
        "mean_ratio_by_band": {w: round(float(np.exp(v)), 4) for w, v in mu.items()},
        "pooled_mean_ratio": round(float(t["ratio"].mean()), 4),
        "cold_subset_n": int(len(cold)),
        "cold_mean_ratio": round(float(cold["ratio"].mean()), 4),
        "sd_log_total": round(float(t["lr"].std()), 4),
        "sd_log_between_dates": round(float(np.sqrt(s2_between)), 4),
        "sd_log_within_date": round(float(np.sqrt(s2_within)), 4),
        "share_var_between_dates": round(s2_between / (s2_between + s2_within), 3),
        "date_effect_shrink": round(shrink, 3),
        "f_date": [round(float(x), 5) for x in f_date_shrunk],
        "within": [round(float(x), 5) for x in within]}

# ------------------------------------------------------------- weather
def load(fn):
    return {f["properties"]["LOCAL_DATE"][:10]: f["properties"]["MEAN_TEMPERATURE"]
            for f in json.load(open(os.path.join(HERE, "data_v9", fn)))["features"]}
a = load("eccc_daily_6158355.json")
b = load("eccc_daily_6158350.json")
ref = json.load(open(os.path.join(HERE, "data_v9", "eccc_winter_bands_v9.json")))
temps = collections.defaultdict(list)
match = 0
for wint, c in ref["winters"].items():
    y = int(wint[:4])
    cnt = collections.Counter()
    for d in sorted(set(a) | set(b)):
        yy, mm = int(d[:4]), int(d[5:7])
        if (yy == y and mm in (11, 12)) or (yy == y + 1 and mm in (1, 2, 3)):
            T = a.get(d)
            T = b.get(d) if T is None else T
            if T is None:
                continue
            cnt[band(T)] += 1
            temps[band(T)].append(float(T))
    match += all(cnt[k] == c[k] for k in ("mild", "cold", "verycold", "extreme", "severe"))

# ------------------------------------------------------------- heat
# block-level CV implied by sigma at the band representative temperature,
# for the record (the harness recomputes it per draw at the drawn T)
cv_ref = {}
for w in ("mild", "cold", "verycold", "extreme", "severe"):
    T = R.SCEN[w][0]
    qs = [R.q_heat_rate(T, tr.f_stop, tr.speed) for blk in R.BLOCKS for tr in blk.trips]
    cv_ref[w] = round(SIGMA_HEAT_KW / float(np.mean(qs)), 3)

out = {"traction": trac,
       "temps": {w: sorted(round(x, 1) for x in v) for w, v in temps.items()},
       "temps_note": ("ECCC climate-daily mean temperature, Toronto City "
                      "6158355 with 6158350 filling gaps; Nov-Mar winters "
                      f"2002-03..2025-26; band counts match the planning "
                      f"weights in {match} of {len(ref['winters'])} winters"),
       "heat": {"sigma_kW": SIGMA_HEAT_KW,
                "source": "companion thermal model residual scale on "
                          "trip-averaged heating demand (Appendix A.2)",
                "cv_at_band_T": cv_ref}}
json.dump(out, open(OUT, "w"), indent=1)
print(json.dumps({k: v for k, v in trac.items() if k not in ("f_date", "within")},
                 indent=1))
print({w: (len(v), min(v), max(v), round(float(np.mean(v)), 2))
       for w, v in out["temps"].items()})
print(out["temps_note"])
print("heat CV at band T:", cv_ref)
