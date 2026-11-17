"""Finish the Route 52 core part after the sharded solves (v9 acceleration;
v11 changes noted below).

Mirrors the bookkeeping of campaign_v9_part.py "core" on the merged core file
(CAMP_OUT): frontier_labels, breakpoint_prices, and the baseline-monotonicity
re-solve (H2). Modes:
  python core_finish_v9.py bps        print the breakpoint prices (one per line)
  python core_finish_v9.py loose      print frontier labels with abs gap > ABS_GAP
  python core_finish_v9.py h2         H2 only; prints CAPS_STALE if the baseline
                                      emissions moved away from the cap basis
  python core_finish_v9.py drop_caps  remove the eps_* records (before re-solving
                                      the frontier on the corrected basis)
  python core_finish_v9.py final      write the keys, run H2, dedup, dump

v11: H2 re-solves the baseline with the same three-phase lexicographic method
as core0_v11.py (the plain cost minimisation it used before leaves the
baseline emissions an arbitrary tie at lambda = 0). The frontier caps are
fractions of the baseline emissions at the time they were solved
("eps_1.00" carries that basis as its cap); if H2 moves the baseline
emissions by more than CAPS_TOL the caps are stale and the frontier has to
be re-solved (run_all_v11.sh does this after the "h2" mode).

v11b (mid-run fix, 13 Nov 2026): H2 compares other plans against the
baseline's cost incumbent ("obj" at lambda = 0), not its reported F1, and
requires them to be cheaper by more than LEX_TOL. A plan within LEX_TOL is a
tie under the lexicographic definition. The first H2 pass re-solved for a
plan 141 CAD below the incumbent; the re-solve came out worse, dedup kept the
old record, and the final pass would have repeated it. All plans within
LEX_TOL of the best known cost are stored in "baseline_ties", lowest
emissions first. "h2check" prints what H2 would do without solving.
"""
import re
import sys

import campaign_v5 as C

FRACS = (1.0, 0.7, 0.5, 0.35, 0.2, 0.1, 0.0)
CAPS_TOL_REL, CAPS_TOL_ABS = 0.02, 0.05       # share of basis, tonnes


def frontier_state():
    recs = {r["label"]: r for r in C.OUT["runs"]}
    # an infeasible cap is stored as a record without results; skip it
    frontier = [recs[f"eps_{f:.2f}"] for f in FRACS
                if "co2_t" in recs.get(f"eps_{f:.2f}", {})]
    infeasible = [l for l in (f"eps_{f:.2f}" for f in FRACS)
                  if l in recs and "co2_t" not in recs[l]]
    fr = sorted(frontier, key=lambda r: -r["co2_t"])
    bps = []
    for a, b in zip(fr, fr[1:]):
        dc, de = b["F1"] - a["F1"], a["co2_t"] - b["co2_t"]
        if de > 1e-3 and dc > 0:
            bps.append(round(dc / de, 0))
    return recs, frontier, infeasible, sorted(set(bps))


CMP = re.compile(r"^(eps_|lam_|bp_lam_|policy_lam|econ_lam0)")


def baseline_cost(b0):
    """Best cost incumbent of the lexicographic baseline. At lambda = 0 the
    solver objective is the cost, and "obj" keeps the phase-1 incumbent, while
    "F1" is the cost of the reported solution, which phase 2 may place up to
    LEX_TOL above it to cut emissions."""
    return min(b0["obj"], b0["F1"])


def dominating(b0):
    """Records that beat the baseline's cost incumbent by more than LEX_TOL.
    Anything closer is a tie under the lexicographic definition (minimum
    emissions within LEX_TOL of the minimum cost), not a cheaper plan."""
    c0 = baseline_cost(b0)
    return [r for r in C.OUT["runs"] if CMP.match(r["label"])
            and r["label"] != "econ_lam0"
            and r.get("F1", 9e18) < c0 - C.LEX_TOL]


def record_ties(b0):
    """Store every recorded plan within LEX_TOL of the best known cost, lowest
    emissions first; post-processing reports the first as the baseline."""
    c_best = min([baseline_cost(b0)] + [r["F1"] for r in C.OUT["runs"]
                  if CMP.match(r["label"]) and "F1" in r])
    ties = sorted(({"label": r["label"], "F1": round(r["F1"], 1),
                    "co2_t": r.get("co2_t"), "n_ffh": r.get("n_ffh")}
                   for r in C.OUT["runs"] if CMP.match(r["label"])
                   and "F1" in r and r["F1"] <= c_best + C.LEX_TOL),
                  key=lambda t: (t["co2_t"], t["F1"]))
    C.OUT["baseline_ties"] = {"best_cost": round(c_best, 1),
                              "tol": C.LEX_TOL, "plans": ties}
    return ties


def h2():
    """Re-solve the baseline if a recorded design beats it by more than
    LEX_TOL; return True if the frontier caps no longer match the baseline
    emissions."""
    recs = {r["label"]: r for r in C.OUT["runs"]}
    b0 = recs.get("econ_lam0")
    assert b0 and "F1" in b0, "no economic baseline in the core file"
    cheaper = dominating(b0)
    if cheaper:
        best = min(cheaper, key=lambda r: r["F1"])
        print(f"baseline dominated by {best['label']} "
              f"({best['F1']:,.0f} < {baseline_cost(b0):,.0f} - {C.LEX_TOL:.0f}); "
              f"re-solving", flush=True)
        C.solve("econ_lam0", eps=1e6, lam=0.0, lexicographic=True,
                tlim=C.TLIM_HARD, force=True,
                mip_start=C.design_from_record(best))
        C.dedup_runs()
        b1 = {r["label"]: r for r in C.OUT["runs"]}["econ_lam0"]
        if dominating(b1):
            print(f"WARNING baseline still beaten after the re-solve "
                  f"(cost {baseline_cost(b1):,.0f}); see baseline_ties",
                  flush=True)
    recs = {r["label"]: r for r in C.OUT["runs"]}
    ties = record_ties(recs["econ_lam0"])
    print("baseline ties (within %.0f CAD of %s): " % (
        C.LEX_TOL, f"{C.OUT['baseline_ties']['best_cost']:,.0f}") +
        "; ".join(f"{t['label']} {t['co2_t']} t" for t in ties), flush=True)
    basis = recs.get("eps_1.00", {}).get("eps")
    new = recs["econ_lam0"]["co2_t"]
    stale = (basis is not None
             and abs(new - basis) > max(CAPS_TOL_ABS, CAPS_TOL_REL * basis))
    C.OUT["caps_basis_co2_t"] = basis
    C.OUT["baseline_co2_t"] = new
    C.OUT["caps_stale"] = bool(stale)
    C._dump()
    return stale


mode = sys.argv[1]
recs, frontier, infeasible_caps, bps = frontier_state()

if mode == "bps":
    for v in bps[:3]:
        print(int(v))
elif mode == "loose":
    for r in frontier:
        if r.get("abs_gap", 0) > C.ABS_GAP:
            print(r["label"])
elif mode == "h2check":   # dry run: what H2 would do, no solve, no write
    b0 = {r["label"]: r for r in C.OUT["runs"]}["econ_lam0"]
    d = dominating(b0)
    print(f"baseline cost {baseline_cost(b0):,.1f} (F1 {b0['F1']:,.1f}, "
          f"co2 {b0['co2_t']} t); dominating: "
          + (", ".join(f"{r['label']} {r['F1']:,.0f}" for r in d) or "none"))
    for t in record_ties(b0):
        print("  tie", t)
elif mode == "h2":
    if h2():
        print(f"CAPS_STALE basis {C.OUT['caps_basis_co2_t']} t, "
              f"baseline {C.OUT['baseline_co2_t']} t", flush=True)
elif mode == "drop_caps":
    n0 = len(C.OUT["runs"])
    C.OUT["runs"] = [r for r in C.OUT["runs"] if not r["label"].startswith("eps_")]
    for k in ("frontier_labels", "infeasible_caps", "breakpoint_prices"):
        C.OUT.pop(k, None)
    C._dump()
    print(f"dropped {n0 - len(C.OUT['runs'])} frontier records", flush=True)
elif mode == "final":
    stale = h2()
    recs, frontier, infeasible_caps, bps = frontier_state()
    C.OUT["frontier_labels"] = [r["label"] for r in frontier]
    C.OUT["infeasible_caps"] = infeasible_caps
    C.OUT["breakpoint_prices"] = bps
    C.dedup_runs()
    C._dump()
    if stale:
        print(f"!!! frontier caps were set from {C.OUT['caps_basis_co2_t']} t; "
              f"final baseline {C.OUT['baseline_co2_t']} t", flush=True)
    print("core finished:", len(C.OUT["runs"]), "runs; breakpoints", bps)
else:
    sys.exit(f"unknown mode {mode}")
