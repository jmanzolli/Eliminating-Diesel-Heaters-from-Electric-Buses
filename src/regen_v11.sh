#!/bin/bash
# Regenerate the v11 post-processing, tables and data figures of the paper from
# the archived result files. No solver is needed.
#
# The v11 scripts were run from a working directory code/ next to the
# manuscript directory overleaf-git/. This script rebuilds that layout from the
# repository and runs the generators in it.
#
# Usage (from anywhere):  src/regen_v11.sh [work_dir]     default: ./_regen_v11
# Output: work_dir/overleaf-git/{tables_v6,supp_tables,figures/m2}
#         work_dir/code/v11_results/{RESULTS_v11.md,results_v11.json}
set -e
ROOT=$(cd "$(dirname "$0")/.." && pwd)
W=${1:-$ROOT/_regen_v11}
PY=${PY:-python3}
mkdir -p "$W"/code/{v11_results,v11b_results,server_v11,data_v9} \
         "$W"/overleaf-git/{tables_v6,supp_tables,figures/m2}
cp "$ROOT"/src/*.py "$W"/code/
cp "$ROOT"/results/v11/*.json "$W"/code/v11_results/
tar -xzf "$ROOT"/results/v11/shards_v11.tar.gz -C "$W"/code/v11_results
cp "$ROOT"/results/v11b/*.json "$W"/code/v11b_results/
tar -xzf "$ROOT"/results/v11b/tighten_v11.tar.gz -C "$W"/code/v11b_results
cp "$ROOT"/configs/ladder_v11.json "$W"/code/server_v11/
cp "$ROOT"/configs/eccc_winter_bands_v9.json "$W"/code/data_v9/
# make_figs_v11.py imports the plotting helpers of make_figs_m2.py, which reads
# the v9 archive when it is imported
mkdir -p "$W"/code/v9rev
cp "$ROOT"/results/campaign_v9rev_results.json "$W"/code/v9rev/
cd "$W"/code
$PY postprocess_v11.py
$PY make_tables_v11.py
FIG_OUT="$W"/overleaf-git/figures/m2 $PY make_figs_v11.py
$PY make_route52_fig.py "$W"/overleaf-git/figures
echo "done: $W"
