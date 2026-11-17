#!/bin/bash
# v11b (2026-11-15): tighten the v11 corridor results. Runs after run_all_v11.sh
# in the same directory and reads its outputs; writes only new files.
#   - corridor: econ_lam0 bound (case base) and cost minima capped at the
#     emissions of the ladder designs D1-D3 (cap:D1..D3), longer limits
#   - every sensitivity (cost only) and every variant except the blocking rule:
#     ladder designs D0-D4 evaluated with the first stage fixed, then a free
#     re-solve started from the complete solution of the cheapest one
#   - figure data (severe day, price response) for D0 and D4
#   - reliability of the reported baseline design (policy_lam100_ops) at the
#     four levels; the v11 reliability used the econ_lam0 incumbent, which
#     lacks D0's 250 kW depot grid upgrade
# Same thread budget and resume rules as run_all_v11.sh.
#
# Usage:  nohup ./run_tighten_v11.sh > run_tighten_v11.log 2>&1 &
#         TIGHT_SMOKE=1 ./run_tighten_v11.sh     # short rehearsal (smoke_ files)
cd "$(dirname "$0")"
PY=${PY:-$HOME/grbenv/bin/python}
[ -x "$PY" ] || PY=python3
export GRB_LICENSE_FILE=${GRB_LICENSE_FILE:-$HOME/gurobi.lic}
IN=route52_inputs_v11g_sched.json
BUDGET=${V11_THREADS:-56}
SMOKE=${TIGHT_SMOKE:-0}
if [ "$SMOKE" = 1 ]; then
  T=tighten_v11smoke; export TIGHT_FIX_TLIM=30 TIGHT_FREE_TLIM=30 FIGSEV_TLIM=60 FIGD_TLIM=60
  CORE_TLIM=30; CASES_SENS="derate_harsh"; CASES_VAR="hp"; CAPS="D2"
  REL_N=2; NC=1; LEVELS="trac"; HEDGE_TLIM=20
else
  T=tighten_v11; export TIGHT_FIX_TLIM=${TIGHT_FIX_TLIM:-900} TIGHT_FREE_TLIM=${TIGHT_FREE_TLIM:-7200}
  CORE_TLIM=${CORE_TLIM:-21600}
  CASES_VAR="hp wear sev115 sev130 plug30 plug60 coldw phi055 phi060 heat094 heat1035 fuel070 fuel115 fracw"
  CASES_SENS="ffh_om_500 ffh_om_2000 grid_100 grid_300 batt_50 batt_100 batt_150 batt_300 derate_mild derate_harsh reserve_25 reserve_50 precond_tau_0.25 precond_tau_1.0 ffh_capex_5000 ffh_capex_15000 frozen_z"
  CAPS="D1 D2 D3"
  REL_N=1000; NC=5; LEVELS="trac data cv0.20 snow"; HEDGE_TLIM=120
fi
L=lanes_$T; LOGS=logs_$T; SLOTS=slots_$T
mkdir -p $T $L $LOGS
rm -rf $SLOTS; mkdir -p $SLOTS

used () {
  local s=0 f p
  for f in $SLOTS/*; do
    [ -e "$f" ] || continue
    p=${f##*/}
    if kill -0 "$p" 2>/dev/null; then s=$((s + $(cat "$f"))); else rm -f "$f"; fi
  done
  echo $s
}
launch () {
  local th=$1 log=$2; shift 2
  [ "$th" -gt "$BUDGET" ] && th=$BUDGET
  while [ $(( $(used) + th )) -gt "$BUDGET" ]; do sleep 15; done
  ( "$@" ) > "$log" 2>&1 &
  LASTPID=$!
  echo "$th" > $SLOTS/$LASTPID
}
run_soft () { local n="$1"; shift; echo "=== $n === $(date)"
  if "$@"; then echo "--- $n OK $(date)"; else echo "!!! $n FAILED (exit $?) $(date)"; fi; }
tight () {  # tight THREADS INPUTS CASE [extra env...]
  local th=$1 inp=$2 cs=$3; shift 3
  local nm; nm=$(echo "$cs" | tr ':.' '__')
  env ROUTE_INPUTS=$inp CAMP_OUT=$T/$nm.json CAMP_LOGDIR=$LOGS/$nm CAMP_THREADS=$th \
      CAMP_MEM_GB=12 CAMP_NODEFILE_GB=8 TIGHT_LADDER=ladder_v11.json "$@" \
      "$PY" tighten_v11.py "$cs"; }

echo "run_tighten_v11 started $(date) on $(hostname) | budget $BUDGET | smoke=$SMOKE"
"$PY" -c "import gurobipy as gp; m=gp.Model(); m.addVar(); m.update(); print('licence OK', gp.gurobi.version())" || exit 1
P=()

# ---- 1. corridor: baseline bound and the ladder caps (longest, start first)
launch 12 $L/base.log run_soft "base" tight 12 $IN base TIGHT_FREE_TLIM=$CORE_TLIM
P+=($LASTPID)
for d in $CAPS; do
  launch 8 $L/cap_$d.log run_soft "cap $d" tight 8 $IN cap:$d TIGHT_FREE_TLIM=$CORE_TLIM
  P+=($LASTPID)
done

# ---- 2. figure data for D0 and D4 (first stage fixed)
launch 8 $L/figs.log run_soft "figure data" bash -c "
  env ROUTE_INPUTS=$IN FIGSEV_RES=figdesigns_v11.json FIGSEV_DATA=fig_severe_day_data_$T.json \
      FIGSEV_THREADS=8 '$PY' fig_severe_day.py solve &&
  env ROUTE_INPUTS=$IN FIGD_RES=figdesigns_v11.json FIGD_OUT=figdata_price_$T.json \
      CAMP_THREADS=8 '$PY' figdata_price_v9.py"
P+=($LASTPID)

# ---- 3. reliability of the reported baseline design: assignment first
rel () {  # rel THREADS [VAR=value ...] -- args...
  local th=$1; shift; local extra=()
  while [ "$1" != "--" ]; do extra+=("$1"); shift; done; shift
  env ROUTE_INPUTS=$IN REL_RESULTS=campaign_v11_results.json REL_DESIGN=policy_lam100_ops \
      REL_INPUTS=rel_inputs_v11.json REL_WINTERS=eccc_winter_bands_v9.json REL_LAM=0 \
      REL_THREADS=$th REL_HEDGE_TLIM=$HEDGE_TLIM "${extra[@]}" "$PY" -u reliability_v10.py "$@"; }
launch 4 $L/rel_assign.log rel 4 -- assign assign_${T}_policy_lam100_ops.json
RA=$LASTPID

# ---- 4. variants, then sensitivities (cost only)
for v in $CASES_VAR; do
  launch 4 $L/var_$v.log run_soft "variant $v" tight 4 ${IN%.json}_$v.json var:$v
  P+=($LASTPID)
done
for s in $CASES_SENS; do
  launch 4 $L/sens_$s.log run_soft "sensitivity $s" tight 4 $IN $s
  P+=($LASTPID)
done

# ---- 5. reliability chunks of the baseline design, level by level
wait $RA
grep -q "Traceback" $L/rel_assign.log && echo "!!! reliability assignment FAILED"
for lv in $LEVELS; do
  Q=()
  for ((c = 0; c < NC; c++)); do
    launch 2 $L/rel_${lv}_c$c.log rel 2 REL_ASSIGN=assign_${T}_policy_lam100_ops.json REL_LEVELS=$lv \
        REL_CHUNK=$c/$NC REL_OUT=$T/rel_policy_lam100_ops_${lv}_c$c.json -- $REL_N
    Q+=($LASTPID)
  done
  wait "${Q[@]}"
  S=(); for ((c = 0; c < NC; c++)); do S+=($T/rel_policy_lam100_ops_${lv}_c$c.json); done
  if rel 2 REL_LEVELS=$lv -- merge rel_${T}_policy_lam100_ops_${lv}.json "${S[@]}" > $L/relmerge_$lv.log 2>&1
  then echo "--- reliability $lv OK $(date)"; else echo "!!! reliability $lv FAILED"; fi
done

wait "${P[@]}"
F=$(grep -l -E "^!!!|Traceback" $L/*.log 2>/dev/null)
echo "=== $T complete $(date)"
[ -z "$F" ] && echo "all stages OK" || echo "!!! check: $F"
