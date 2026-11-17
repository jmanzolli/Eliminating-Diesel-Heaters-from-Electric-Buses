"""Sensitivity variants of the v11g corridor instance.

Each v9 variant file differs from route52_inputs_v9.json in a few keys (severe
traction factor, scenario weights, heat-pump COP, ...). This applies the same
differences to a v11g base instance, so the variants keep the GTFS vehicle-days,
the auxiliary load and the off-season heat of the base.

Usage: python3 make_variants_v11g.py [base.json]   (default route52_inputs_v11g.json)
"""
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = sys.argv[1] if len(sys.argv) > 1 else "route52_inputs_v11g.json"
v9 = json.load(open(os.path.join(HERE, "route52_inputs_v9.json")))
base = json.load(open(os.path.join(HERE, BASE)))
SKIP = {"branches", "deadhead_km", "deadhead_min", "service_start_h",
        "service_end_h", "pax_per_h", "sites"}


def merge(dst, old, new):
    """Apply the change old -> new onto dst (dicts recursively)."""
    for k, v in new.items():
        if k in SKIP or old.get(k) == v:
            continue
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            merge(dst[k], old.get(k, {}) if isinstance(old.get(k), dict) else {}, v)
        else:
            dst[k] = v


made = []
for src in sorted(glob.glob(os.path.join(HERE, "route52_inputs_v9_*.json"))):
    tag = os.path.basename(src)[len("route52_inputs_v9_"):-len(".json")]
    if tag.startswith("ffh") or tag == "smoke":
        continue
    var = json.load(open(src))
    out = json.loads(json.dumps(base))
    merge(out, v9, var)
    changed = sorted(k for k in out if out[k] != base.get(k))
    out["variant_of"] = BASE
    dst = BASE.replace(".json", f"_{tag}.json")
    json.dump(out, open(os.path.join(HERE, dst), "w"), indent=1)
    made.append((tag, changed))
for tag, ch in made:
    print(f"{tag:10s} changes {ch}")
