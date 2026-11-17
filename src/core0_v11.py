"""First stage of the v11 Route 52 campaign: the two baselines.

  econ_lam0       economic baseline, three-phase lexicographic from the start
                  (min cost; min emissions within LEX_TOL; min cost at those
                  emissions), so the frontier caps are fractions of the final
                  baseline emissions and its cost carries no tolerance
  policy_lam100   baseline at 100 CAD/t, the reference of the sensitivity runs
  ops metrics     fixed-design recourse records of both (margins, diagnostics)

Run: ROUTE_INPUTS=<inputs> CAMP_OUT=sh_core_v11.json python core0_v11.py
"""
import campaign_v5 as C

econ, m0 = C.solve("econ_lam0", eps=1e6, lam=0.0, lexicographic=True,
                   tlim=C.TLIM_HARD)
pol, m100 = C.solve("policy_lam100", lam=100.0)
if "ops_metrics_policy" not in C.OUT and pol and "F1" in pol:
    _, m = C.solve("policy_lam100_ops", lam=100.0, tlim=min(900, C.TLIM),
                   fix_design=C.design_from_record(pol), force=True)
    if m is not None:
        C.OUT["ops_metrics_policy"] = C.ops_metrics(m)
if "ops_metrics_econ" not in C.OUT and econ and "F1" in econ:
    _, m = C.solve("econ_lam0_ops", lam=0.0, tlim=min(900, C.TLIM),
                   fix_design=C.design_from_record(econ), force=True)
    if m is not None:
        C.OUT["ops_metrics_econ"] = C.ops_metrics(m)
C.dedup_runs()
C._dump()
for r in C.OUT["runs"]:
    if "F1" in r:
        print(f"  {r['label']}: F1 {r['F1']:,.1f} gap {r.get('abs_gap', 0):,.0f} "
              f"ffh {r['n_ffh']} co2 {r['co2_t']} ch {r['chargers']}", flush=True)
