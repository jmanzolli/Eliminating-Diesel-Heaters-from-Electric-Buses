#!/bin/bash
# v11 campaign (2026-11). Model and instances rebuilt after the audit of
# 2026-11-11 (reviews/2026-11-11-code-audit.md):
#   - weekday service from the TTC GTFS feed, blocks as scheduled, as
#     vehicle-days (build_instances_v11.py); the blocking rule only where a
#     vehicle-day cannot be served without a heater
#   - non-heating auxiliary load and cabin heat over every hour in service
#   - shoulder-season heat in the off-season scenario
#   - three-phase lexicographic solves; frontier caps re-solved if the
#     baseline emissions move at the monotonicity check (H2)
#   - reference cases with the observed (heater-first) dispatch
#   - reliability on the non-heating energy residual, snow day as its own level
#   - division: per-route solves, coordinated cases started from the complete
#     shared-pool solution
# All solver processes share one thread budget (V11_THREADS, default 56 of the
# 80 cores; other users keep about 25 busy), so time-limited solves do not run
# on an oversubscribed host. Every stage resumes (a label already in its
# output file is skipped), so the script can be relaunched.
#
# Usage:  nohup ./run_all_v11.sh > run_all_v11.log 2>&1 &
#         V11_SMOKE=1 ./run_all_v11.sh     # short end-to-end rehearsal
#         V11_PARTS="corridor" or "division" or "corridor division" (default)
cd "$(dirname "$0")"
PY=${PY:-$HOME/grbenv/bin/python}
[ -x "$PY" ] || PY=python3
export GRB_LICENSE_FILE=${GRB_LICENSE_FILE:-$HOME/gurobi.lic}

IN=${V11_IN:-route52_inputs_v11g_sched.json}       # corridor, blocks as scheduled (main)
ALT=${V11_ALT:-route52_inputs_v11g.json}           # corridor, blocking rule (variant)
GIN=${V11_GIN:-garage_inputs_v11g_sched.json}      # division, blocks as scheduled
PARTS=${V11_PARTS:-"corridor division"}
SMOKE=${V11_SMOKE:-0}
BUDGET=${V11_THREADS:-56}
TAG=v11
if [ "$SMOKE" = 1 ]; then
  TAG=v11smoke
  export CAMP_TLIM=120 CAMP_TLIM_HARD=180 EVPI_TLIM=120
  REL_N=2; NC=1; HEDGE_TLIM=20
  DIV_TLIM=300; DIV_TLIM_SUB=90
  VARIANTS="sev130"; CAPEX="20000"; GAMMAS="100"; EPS="1.00 0.20 0.00"; LAMS="2000"
  LEVELS="trac snow"; RELDESIGNS="econ_lam0 eps_0.00"
  SENS="batt_50 frozen_z"
else
  export CAMP_TLIM=${CAMP_TLIM:-5400} CAMP_TLIM_HARD=${CAMP_TLIM_HARD:-10800}
  REL_N=${REL_N:-1000}; NC=${REL_CHUNKS:-5}; HEDGE_TLIM=${REL_HEDGE_TLIM:-120}
  DIV_TLIM=${DIV_TLIM:-43200}; DIV_TLIM_SUB=${DIV_TLIM_SUB:-7200}
  VARIANTS="sev115 sev130 hp plug30 plug60 coldw wear phi055 phi060 heat094 heat1035 fuel070 fuel115 fracw"
  CAPEX="15000 17500 20000 25000 30000"; GAMMAS="25,50,75,100"
  EPS="1.00 0.70 0.50 0.35 0.20 0.10 0.00"; LAMS="200 500 1000 2000 3500 5000 10000"
  LEVELS="trac data cv0.20 snow"
  RELDESIGNS="econ_lam0 eps_0.00 relmatch_eps0_r25 relmatch_eps0_r50 relmatch_eps0_r75 relmatch_eps0_r100 det_designday"
  SENS="ffh_om_500 ffh_om_2000 grid_100 grid_300 batt_150 batt_100 batt_300 batt_50 derate_mild derate_harsh reserve_25 reserve_50 spare_15 precond_tau_0.25 precond_tau_1.0 ffh_capex_5000 ffh_capex_15000 frozen_z"
fi
RES=campaign_${TAG}_results.json
CORE=sh_core_${TAG}.json
DIV=campaign_division_${TAG}.json
L=lanes_$TAG; LOGS=logs_$TAG; LOGD=logs_div_$TAG; SH=shards_$TAG; SLOTS=slots_$TAG
mkdir -p $L $LOGS $LOGD $SH
rm -rf $SLOTS; mkdir -p $SLOTS

# ---------------------------------------------------------- thread budget
# launch THREADS LOG cmd... : wait until THREADS fit in the budget, then run
# cmd (a command or a shell function) in the background with its output in
# LOG, and register it; sets LASTPID.
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
camp () {  # camp THREADS OUT INPUTS script args...
  local th=$1 out=$2 inp=$3; shift 3
  env ROUTE_INPUTS=$inp CAMP_OUT=$out CAMP_LOGDIR=$LOGS CAMP_THREADS=$th \
      CAMP_MEM_GB=12 CAMP_NODEFILE_GB=8 REVIEW_SRC=$RES "$PY" "$@"; }
has () { "$PY" -c "import json,sys; d=json.load(open('$1')); sys.exit(0 if any(r.get('label')=='$2' and 'F1' in r for r in d.get('runs',[])) else 1)" 2>/dev/null; }

echo "run_all_v11 started $(date) on $(hostname) ($(nproc) cores, budget $BUDGET threads) | smoke=$SMOKE | parts: $PARTS"
"$PY" -c "import gurobipy as gp; m=gp.Model(); m.addVar(); m.update(); print('licence OK', gp.gurobi.version())" || exit 1
for f in $IN $ALT $GIN; do
  ROUTE_INPUTS=$f "$PY" - <<'EOF' || exit 1
import os, route52_prototype as R
assert R.EXPLICIT and R.aux_kw(0.0) > 0 and R.HEAT_KW_FIXED and R.FFH_SHARE_OBS
print("check", os.environ["ROUTE_INPUTS"], "| vehicle-days", R.N_BLOCKS, "| sites", len(R.SITES),
      "| aux kW", R.aux_kw(-20.0), "| off-season heat kW", R.HEAT_KW_FIXED,
      "| days", {w: R.SCEN[w][1] for w in R.SCEN})
assert sum(R.SCEN[w][1] for w in R.SCEN) == 365
EOF
done

# ============================================================== DIVISION
division () {
  local DENV="ROUTE_INPUTS=$GIN DIV_LOGDIR=$LOGD DIV_NODEFILE_GB=16 DIV_TLIM=$DIV_TLIM DIV_TLIM_SUB=$DIV_TLIM_SUB DIV_MIPGAP=0.005"
  # ---- fragmented plan: one process per route, then the common-basis merge
  local ROUTES; ROUTES=$("$PY" -c "import json; print(' '.join(sorted({str(v['route']) for v in json.load(open('$GIN'))['vehicle_days']}, key=int)))")
  [ "$SMOKE" = 1 ] && ROUTES="99 120 108"
  echo "division routes: $ROUTES"
  local AP=()
  for r in $ROUTES; do
    launch 2 $L/div_route_$r.log run_soft "fragmented route $r" env $DENV DIV_MEM_GB=12 DIV_THREADS=2 \
        DIV_ROUTES=$r DIV_OUT=div_A_route_${r}_$TAG.json "$PY" campaign_division_v5.py A
    AP+=($LASTPID)
  done
  wait "${AP[@]}"
  # ---- shared pool (C), saving its complete solution
  launch 16 $L/div_C.log run_soft "division C" env $DENV DIV_MEM_GB=40 DIV_THREADS=16 \
      DIV_OUT=div_C_$TAG.json DIV_SAVE_SOL=div_C_sol_$TAG.json "$PY" campaign_division_v5.py C
  wait $LASTPID
  # ---- full coordination (D) and route-locked (B), started from C's solution
  local BP=()
  for c in D B; do
    launch 12 $L/div_$c.log run_soft "division $c" env $DENV DIV_MEM_GB=32 DIV_THREADS=12 \
        DIV_OUT=div_${c}_$TAG.json DIV_START_SOL=div_C_sol_$TAG.json DIV_START_ROUTELOCK=1 \
        DIV_START_FROM=div_C_$TAG.json:C_shared_infra_frozen_z "$PY" campaign_division_v5.py $c
    BP+=($LASTPID)
  done
  wait "${BP[@]}"
  # ---- merge the cases into one file
  "$PY" - <<EOF
import json, os
out = {"cases": {}, "meta": {"inputs": "$GIN", "tag": "$TAG"}}
for c in "CDB":
    fn = f"div_{c}_$TAG.json"
    if os.path.exists(fn):
        out["cases"].update(json.load(open(fn))["cases"])
json.dump(out, open("$DIV", "w"), indent=1)
print("division cases:", sorted(out["cases"]))
EOF
  if [ "$SMOKE" = 1 ]; then echo "(smoke: fragmented merge skipped, 3 routes only)"
  else run_soft "merge fragmented" env ROUTE_INPUTS=$GIN "$PY" merge_fragmented_v9.py $DIV div_A_route_*_$TAG.json > $L/div_merge.log 2>&1; fi
  touch DIVISION_${TAG}_DONE
  echo "=== division done $(date)"
}

# ============================================================== CORRIDOR
finish () {  # finish MODE [THREADS] : core_finish_v9.py on the core file
  env ROUTE_INPUTS=$IN CAMP_OUT=$CORE CAMP_LOGDIR=$LOGS CAMP_THREADS=${2:-14} \
      CAMP_MEM_GB=24 CAMP_NODEFILE_GB=8 "$PY" core_finish_v9.py "$1"; }
relmatch_lane () {
  run_soft "reserve designs" env RELMATCH_GAMMAS=$GAMMAS ROUTE_INPUTS=$IN CAMP_OUT=relmatch_$TAG.json \
      CAMP_LOGDIR=$LOGS CAMP_THREADS=4 CAMP_MEM_GB=12 "$PY" relmatch_run.py
  run_soft "design day" env REVIEW_SRC=$CORE ROUTE_INPUTS=$IN CAMP_OUT=rev_designday_$TAG.json \
      CAMP_LOGDIR=$LOGS CAMP_THREADS=4 "$PY" review_runs_v9.py designday; }
# follow-ups that need the merged archive $RES, in three parallel lanes
post_lane1 () {
  run_soft "reference: observed dispatch on D0" env REVIEW_SRC=$RES ROUTE_INPUTS=$IN \
      CAMP_OUT=ref_obs_$TAG.json CAMP_LOGDIR=$LOGS CAMP_THREADS=4 "$PY" ref_runs_v11.py refobs_d0
  run_soft "design-day eval" env REVIEW_DD=rev_designday_$TAG.json ROUTE_INPUTS=$IN \
      CAMP_OUT=rev_ddeval_$TAG.json CAMP_LOGDIR=$LOGS CAMP_THREADS=4 REVIEW_SRC=$RES "$PY" review_runs_v10.py ddeval; }
post_lane2 () {
  run_soft "D0 eval" camp 4 rev_d0eval_$TAG.json $IN review_runs_v10.py d0eval
  run_soft "band check" env ROUTE_INPUTS=$IN DETBAND_RES=$RES DETBAND_OUT=detband_$TAG.json \
      DETBAND_SLACK_ONLY=1 DETBAND_LABELS=det_meanT,econ_lam0,eps_0.00 "$PY" detband_check.py; }
post_lane3 () {
  run_soft "soft heat balance and VSS" env ROUTE_INPUTS=$IN CAMP_OUT=evpi_vss_results_$TAG.json \
      CAMP_LOGDIR=$LOGS EVPI_SRC=$RES EVPI_OUT=evpi_vss_$TAG.json CAMP_THREADS=6 "$PY" evpi_vss_run.py; }

corridor () {
  local P=()
  shard () {  # shard LABEL THREADS : one frontier or price label per process
    local nm; nm=$(echo "$1" | tr ':.' '__')
    launch $2 $L/shard_$nm.log run_soft "shard $1" env CORE_SRC=$CORE ROUTE_INPUTS=$IN \
        CAMP_OUT=$SH/x_$nm.json CAMP_LOGDIR=$LOGS CAMP_THREADS=$2 CAMP_MEM_GB=12 \
        CAMP_NODEFILE_GB=8 "$PY" shard_solve_v9.py "$1"
    P+=($LASTPID); }

  # ---- 1. baselines (the frontier caps need the baseline emissions)
  launch 16 $L/core0.log run_soft "baselines" camp 16 $CORE $IN core0_v11.py
  wait $LASTPID
  has $CORE econ_lam0 || { echo "!!! no economic baseline; corridor stopped"; return 1; }

  # ---- 2. frontier caps and carbon prices, one label per process, and the
  #         runs that only need the inputs
  for e in $EPS; do shard eps_$e 4; done
  for l in $LAMS; do shard lam_$l 4; done
  launch 4 $L/ref.log run_soft "reference: observed dispatch" camp 4 ref_obs_$TAG.json $IN ref_runs_v11.py refobs
  P+=($LASTPID)
  launch 4 $L/relmatch.log relmatch_lane
  P+=($LASTPID)
  wait "${P[@]}"; P=()
  "$PY" merge_campaign.py $CORE $CORE $SH/x_*.json > $L/merge1.log 2>&1

  # ---- 3. baseline monotonicity (H2); re-solve the caps if it moved the
  #         baseline emissions away from their basis
  launch 14 $L/h2.log run_soft "baseline check (H2)" finish h2 14
  wait $LASTPID
  if grep -q CAPS_STALE $L/h2.log; then
    echo "=== baseline emissions moved; re-solving the frontier caps $(date)"
    finish drop_caps > $L/drop_caps.log 2>&1
    rm -f $SH/x_eps_*.json
    for e in $EPS; do shard eps_$e 4; done
    wait "${P[@]}"; P=()
    "$PY" merge_campaign.py $CORE $CORE $SH/x_*.json > $L/merge1b.log 2>&1
  fi

  # ---- 4. breakpoint prices, refinement of loose caps, benchmarks, sensitivities
  for v in $(finish bps 2>/dev/null | grep -E '^[0-9]+$'); do shard bp_lam_$v 4; done
  if [ "$SMOKE" != 1 ]; then
    for lb in $(finish loose 2>/dev/null | grep -E '^eps_'); do shard refine:$lb 4; done
  fi
  launch 6 $L/bench.log run_soft bench env CORE_SRC=$CORE BENCH_SKIP_FROZEN=1 \
      ROUTE_INPUTS=$IN CAMP_OUT=$SH/part_bench.json CAMP_LOGDIR=$LOGS CAMP_THREADS=6 \
      CAMP_MEM_GB=12 CAMP_NODEFILE_GB=8 "$PY" campaign_v9_part.py bench
  P+=($LASTPID)
  for s in $SENS; do   # one sensitivity per process (sens_one_v11.py)
    launch 4 $L/sens_$s.log run_soft "sensitivity $s" camp 4 $SH/part_sens_$s.json $IN sens_one_v11.py $s
    P+=($LASTPID)
  done
  wait "${P[@]}"; P=()
  "$PY" merge_campaign.py $CORE $CORE $SH/x_*.json > $L/merge2.log 2>&1
  launch 14 $L/core_finish.log run_soft "core finish" finish final 14
  wait $LASTPID
  "$PY" merge_campaign.py $RES $SH/part_*.json $CORE > $L/merge3.log 2>&1
  echo "=== frontier and benchmarks merged into $RES $(date)"

  # ---- 5. reliability assignments, variants and follow-ups (all need $RES)
  declare -A SRC
  for d in $RELDESIGNS; do
    case $d in relmatch_*) SRC[$d]=relmatch_$TAG.json;; det_designday) SRC[$d]=rev_designday_$TAG.json;; *) SRC[$d]=$RES;; esac
  done
  rel () {  # rel DESIGN THREADS [VAR=value ...] -- args...
    local d=$1 th=$2; shift 2; local extra=()
    while [ "$1" != "--" ]; do extra+=("$1"); shift; done; shift
    env ROUTE_INPUTS=$IN REL_RESULTS=${SRC[$d]} REL_DESIGN=$d REL_INPUTS=rel_inputs_v11.json \
        REL_WINTERS=eccc_winter_bands_v9.json REL_LAM=0 REL_THREADS=$th REL_HEDGE_TLIM=$HEDGE_TLIM \
        "${extra[@]}" "$PY" -u reliability_v10.py "$@"; }
  local Q=()
  for d in $RELDESIGNS; do
    launch 4 $L/assign_$d.log rel $d 4 -- assign assign_${TAG}_$d.json
    Q+=($LASTPID)
  done
  for t in $VARIANTS; do
    launch 4 $L/var_$t.log run_soft "variant $t" camp 4 addon_${t}_$TAG.json ${IN%.json}_$t.json sev_sweep_v8.py
    P+=($LASTPID)
  done
  launch 4 $L/var_altblock.log run_soft "other blocking" camp 4 addon_altblock_$TAG.json $ALT sev_sweep_v8.py
  P+=($LASTPID)
  for fc in $CAPEX; do
    launch 4 $L/capex_$fc.log run_soft "heater capital $fc" env REVIEW_CAPEX=$fc ROUTE_INPUTS=$IN \
        CAMP_OUT=rev_capex_${fc}_$TAG.json CAMP_LOGDIR=$LOGS CAMP_THREADS=4 CAMP_MEM_GB=12 \
        CAMP_NODEFILE_GB=8 REVIEW_SRC=$RES "$PY" review_runs_v10.py capex
    P+=($LASTPID)
  done
  launch 4 $L/post1.log post_lane1; P+=($LASTPID)
  launch 4 $L/post2.log post_lane2; P+=($LASTPID)
  launch 6 $L/post3.log post_lane3; P+=($LASTPID)

  # ---- 6. reliability chunks, level by level
  wait "${Q[@]}"
  for lv in $LEVELS; do
    Q=()
    for d in $RELDESIGNS; do
      [ -s assign_${TAG}_$d.json ] || { echo "!!! no assignment for $d"; continue; }
      for ((c = 0; c < NC; c++)); do
        launch 2 $L/rel_${d}_${lv}_c$c.log rel $d 2 REL_ASSIGN=assign_${TAG}_$d.json REL_LEVELS=$lv \
            REL_CHUNK=$c/$NC REL_OUT=$SH/rel_${d}_${lv}_c$c.json -- $REL_N
        Q+=($LASTPID)
      done
    done
    wait "${Q[@]}"
    for d in $RELDESIGNS; do
      [ -s assign_${TAG}_$d.json ] || continue
      S=(); for ((c = 0; c < NC; c++)); do S+=($SH/rel_${d}_${lv}_c$c.json); done
      if rel $d 2 REL_LEVELS=$lv -- merge rel_${TAG}_${d}_${lv}.json "${S[@]}" > $L/relmerge_${d}_${lv}.log 2>&1
      then echo "--- reliability $d $lv OK $(date)"; else echo "!!! reliability $d $lv FAILED"; fi
    done
  done
  wait "${P[@]}"
  run_soft "provenance" env PROV_RES=$RES PROV_OUT=provenance_$TAG.json PROV_LOGDIR=$LOGS "$PY" make_provenance_v5.py > $L/prov.log 2>&1
  touch ROUTE52_${TAG}_DONE
  echo "=== corridor done $(date)"
}

PIDS=()
case " $PARTS " in *" division "*) division > $L/division.log 2>&1 & PIDS+=($!);; esac
case " $PARTS " in *" corridor "*) corridor > $L/corridor.log 2>&1 & PIDS+=($!);; esac
wait "${PIDS[@]}"
echo "=== v11 complete $(date)"
grep -h '!!!' $L/*.log || echo "all stages OK"
