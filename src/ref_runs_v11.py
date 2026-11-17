"""Reference cases for current practice (v11, audit items A4-A5).

In the telemetry the diesel heater is the primary heat source: it supplies
78% of cabin heat on winter days at or above 0 C, 96-97% in the cold and very
cold bands and 76% below -10 C. The cost-optimal baseline does the opposite.
These runs fix the heater's share of cabin heat at the observed share of each
band ("ffh_share_obs" in the inputs) on a fleet with a heater on every bus:

  refobs      least-cost equipment under the observed dispatch; "ref_observed"
  refobs_d0   the design of the economic baseline (econ_lam0 in REVIEW_SRC)
              operated with the observed dispatch; "ref_observed_d0"

The difference between ref_observed and econ_lam0 is what dispatch alone
changes; diesel_by_scen divided by the number of buses is comparable with the
observed litres per bus-day ("obs_diesel_L_busday" in instances_v11g_summary).

Run: ROUTE_INPUTS=<inputs> CAMP_OUT=<file> [REVIEW_SRC=<results>] \
     python ref_runs_v11.py <mode>
"""
import json
import os
import sys

import campaign_v5 as C
import route52_prototype as R

mode = sys.argv[1]
assert R.FFH_SHARE_OBS, "inputs carry no observed heater shares"
if mode == "refobs":
    C.solve("ref_observed", lam=0.0, tlim=C.TLIM_HARD, dispatch_obs=True,
            ffh_all=True, fix_fleet_total=True)
elif mode == "refobs_d0":
    src = {r["label"]: r for r in json.load(open(os.environ["REVIEW_SRC"]))["runs"]}
    C.solve("ref_observed_d0", lam=0.0, tlim=C.TLIM,
            fix_design=C.design_from_record(src["econ_lam0"]), dispatch_obs=True)
else:
    raise SystemExit(f"unknown mode {mode}")
C.dedup_runs()
C._dump()
for r in C.OUT["runs"]:
    if "F1" in r:
        print(f"  {r['label']}: F1 {r['F1']:,.1f} gap {r.get('abs_gap', 0):,.0f} "
              f"ffh {r['n_ffh']} co2 {r['co2_t']} diesel {r['diesel_L']:,.0f} L "
              f"ch {r['chargers']}", flush=True)
