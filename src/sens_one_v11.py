"""One Route 52 sensitivity or benchmark solve per process (v11).

The v9 parts "sensA", "sensB" and "bench" ran their solves in sequence, about
15 hours at the v11 time limits. This runs one label of them, with the same
modifiers, carbon price and limits, so the labels can run in parallel under
the run script's thread budget. Merge the output files with merge_campaign.py.

Labels: ffh_om_500 ffh_om_2000 grid_100 grid_300 batt_150 batt_100 batt_300
        batt_50 derate_mild derate_harsh reserve_25 reserve_50 spare_15
        precond_tau_0.25 precond_tau_1.0 ffh_capex_5000 ffh_capex_15000
        frozen_z
Run: ROUTE_INPUTS=<inputs> CAMP_OUT=<file> python sens_one_v11.py <label>
"""
import sys

import campaign_v5 as C

lab = sys.argv[1]
MODS = {
    "ffh_om_500": lambda: C.set_om(500.0), "ffh_om_2000": lambda: C.set_om(2000.0),
    "grid_100": lambda: C.set_grid(100.0), "grid_300": lambda: C.set_grid(300.0),
    "batt_150": lambda: C.set_batt(150.0), "batt_100": lambda: C.set_batt(100.0),
    "batt_300": lambda: C.set_batt(300.0), "batt_50": lambda: C.set_batt(50.0),
    "derate_mild": lambda: C.set_derate(0.002, 0.004),
    "derate_harsh": lambda: C.set_derate(0.006, 0.012),
    "reserve_25": lambda: C.set_reserve(25.0), "reserve_50": lambda: C.set_reserve(50.0),
    "precond_tau_0.25": lambda: C.set_tau(0.25), "precond_tau_1.0": lambda: C.set_tau(1.0),
    "ffh_capex_5000": lambda: C.set_ffh_capex(5000.0),
    "ffh_capex_15000": lambda: C.set_ffh_capex(15000.0),
}
if lab in MODS:
    f, g = MODS[lab]()
    C.solve(lab, mods=f, unmods=g)                 # lambda = 100, as in v9
elif lab == "spare_15":
    C.solve("spare_15", lam=100.0, spare=0.15)
elif lab == "frozen_z":
    C.solve("frozen_z", lam=100.0, freeze_z=True)
else:
    sys.exit(f"unknown label {lab}")
C.dedup_runs()
C._dump()
for r in C.OUT["runs"]:
    if "F1" in r:
        print(f"  {r['label']}: F1 {r['F1']:,.1f} gap {r.get('abs_gap', 0):,.0f} "
              f"ffh {r['n_ffh']} co2 {r['co2_t']} ch {r['chargers']}", flush=True)
    else:
        print(f"  {r['label']}: no solution", flush=True)
