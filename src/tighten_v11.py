"""v11b: tighten the v11 corridor results (run_tighten_v11.sh).

Most v11 corridor solves stopped at the time limit with gaps of 10-40 kCAD/yr,
larger than the differences they were meant to show. Two remedies, one case
per process:

  1. fixed-design evaluation: the five ladder designs D0-D4 (ladder_v11.json)
     re-dispatched under the case's inputs with their first stage fixed
     (labels fix_D0 ... fix_D4). These close to about 1 kCAD, so the cost of
     each design under each case is well determined.
  2. free re-solve (label "free", cost only): started from the complete
     solution of the cheapest fixed design (every variable, not only the first
     stage), with a longer limit. Its incumbent can only improve on the best
     fixed design; its bound certifies how far any other design could go.

Cases
  base                  the base inputs (free solve = econ_lam0 tightened)
  cap:D1 | cap:D2 | cap:D3   cost minimum with emissions capped at that ladder
                        design's emissions, started from the design itself
                        (certifies the ladder increments)
  <sensitivity label>   as in sens_one_v11.py, but cost only (lambda = 0)
  var:<name>            the variant inputs (set ROUTE_INPUTS to the variant file)

Environment: ROUTE_INPUTS, CAMP_OUT, CAMP_LOGDIR, CAMP_THREADS (as campaign_v5),
  TIGHT_LADDER (default ladder_v11.json), TIGHT_FIX_TLIM (1800),
  TIGHT_FREE_TLIM (10800), TIGHT_SKIP_FREE=1 to stop after the evaluations.
Run: ROUTE_INPUTS=... CAMP_OUT=tighten_v11/<case>.json python tighten_v11.py <case>
"""
import json
import os
import sys

import campaign_v5 as C

case = sys.argv[1]
LADDER = json.load(open(os.environ.get("TIGHT_LADDER", "ladder_v11.json")))
FIX_TLIM = int(os.environ.get("TIGHT_FIX_TLIM", 1800))
FREE_TLIM = int(os.environ.get("TIGHT_FREE_TLIM", 10800))

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


def kw():
    """Keyword arguments of C.solve that define the case."""
    k = {"lam": 0.0}
    if case in MODS:
        f, g = MODS[case]()
        k.update(mods=f, unmods=g)
    elif case == "frozen_z":
        k["freeze_z"] = True
    elif case.startswith("cap:"):
        k["eps"] = LADDER[case[4:]]["co2_t"] + 1e-3
    elif case != "base" and not case.startswith("var:"):
        sys.exit(f"unknown case {case}")
    return k


def values(m):
    return [v.X for v in m.getVars()]


# ---- 1. fixed-design evaluations
designs = [case[4:]] if case.startswith("cap:") else list(LADDER)
best, start = None, None
for d in designs:
    lbl = f"fix_{d}"
    rec, m = C.solve(lbl, fix_design=C.design_from_record(LADDER[d]), tlim=FIX_TLIM, **kw())
    if rec is None or "F1" not in rec:
        print(f"{lbl}: no solution under {case}", flush=True)
        continue
    if m is not None and (best is None or rec["obj"] < best["obj"]):
        best, start = rec, values(m)
    elif m is None and (best is None or rec["obj"] < best["obj"]):
        best = rec                       # recorded earlier; no model to start from
    if m is not None:
        m.dispose()

# ---- 2. free re-solve from the cheapest fixed design
if os.environ.get("TIGHT_SKIP_FREE") != "1":
    if best is not None and start is None and "free" not in C.DONE:
        # resumed after the evaluations: rebuild the cheapest one for its start
        d = best["label"][4:]
        rec, m = C.solve(best["label"] + "_restart", fix_design=C.design_from_record(LADDER[d]),
                         tlim=FIX_TLIM, **kw())
        if m is not None:
            start = values(m)
            m.dispose()
    C.solve("free", tlim=FREE_TLIM, full_start=start,
            mip_start=C.design_from_record(best) if best else None, **kw())

C.dedup_runs()
C._dump()
for r in C.OUT["runs"]:
    if "F1" in r:
        print(f"  {case} {r['label']}: F1 {r['F1']:,.1f} lb {r['lb']:,.1f} gap {r['abs_gap']:,.0f} "
              f"ffh {r['n_ffh']} co2 {r['co2_t']}", flush=True)
    else:
        print(f"  {case} {r['label']}: no solution", flush=True)
