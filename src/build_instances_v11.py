"""
v11 instances from the TTC GTFS feed (2026-11-11).

Replaces the synthetic all-day blocks of the v5-v10 instances (one bus per
headway slot, cycling 05:15-21:45) with the scheduled weekday service:

  trips         every weekday trip (service_id 1) of the instance routes, with
                its scheduled times, distance, stop count and terminals; a
                block whose main route is an instance route also keeps the
                trips it interlines on other routes
  pieces        the trips of one GTFS block form a piece; a piece is cut
                  - where the block leaves the instance routes or pauses for
                    more than GAP_CUT_H,
                  - by the BLOCKING RULE: before the trip that would take the
                    piece past MAX_PIECE_H hours or MAX_PIECE_KM kilometres.
                    The rule follows the telemetry: no battery-electric bus
                    served more than 17.3 h or 257 km in a day on Route 52,
                    and on longer blocks the operator replaced it in the
                    evening. "none" disables the rule (blocks as scheduled).
  heater-free   in the as-scheduled instances, the blocking rule is applied
  split         only to the GTFS blocks of vehicle-days that no heater-free
                bus could serve on some band day even with maximum charging
                (heaterfree_infeasible); everything else stays as scheduled
  vehicle-days  pieces of one route are chained onto one bus when the bus can
                return to the depot, stay MIN_DEPOT_H, and drive out again,
                and the day stays within MAX_DAY_KM (99th percentile of the
                observed vehicle-days). Greedy, earliest-returned bus first.
  deadheads     depot to terminal by great-circle distance x CIRCUITY at
                DEADHEAD_KMH, for every pull-out, pull-in, midday return and
                relief trip
  sites         the depot and every terminal with at least MIN_SITE_BUSH
                bus-hours of scheduled layover per weekday

Trips that start before the model day or end after it (night-network tails)
are dropped and counted in the summary.

Also taken from the telemetry workbook, for the v11 inputs:
  pax_per_h             boardings per hour in service (fleet)
  offseason heat        delivered cabin heat per hour in service, Apr-Oct
  ffh_share_obs         observed share of cabin heat supplied by the diesel
                        heater, by band (reference dispatch)
  obs_diesel_L_busday   observed heater fuel per bus-day, by band

Usage:
  GTFS_DIR=<unzipped feed> python3 build_instances_v11.py
Writes route52_inputs_v11g.json and garage_inputs_v11g.json (blocking rule),
the same with suffix _sched (blocks as scheduled, main case), and
instances_v11g_summary.json.
"""
import json
import math
import os
import re
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
GTFS = os.environ["GTFS_DIR"]
TTC_XLSX = os.environ.get("TTC_XLSX", os.path.join(
    HERE, "data", "TTC_Preprocessed_version2_2.xlsx"))
ROUTES = ["35", "36", "52", "84", "96", "99", "108", "120", "165",
          "927", "935", "952", "984", "996"]
SERVICE_ID = "1"                 # weekday
DAY_START_H = 3.5                # model day 03:30 - 27:30
DAY_END_H = DAY_START_H + 24.0
GAP_CUT_H = 1.0
MAX_PIECE_H = 15.0
MAX_PIECE_KM = 250.0
MIN_DEPOT_H = 2.0
MAX_DAY_KM = 340.0
DEPOT_LATLON = (43.7480, -79.5310)       # Arrow Road garage
CIRCUITY = 1.3
DEADHEAD_KMH = 30.0
CLUSTER_M = 400.0
MIN_SITE_BUSH = 5.0


def hav_km(a, b):
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
    return 2 * 6371.0 * math.asin(math.sqrt(h))


def slug(name):
    name = re.sub(r"\b(at|opposite|side|bus|bay|platform)\b", " ", name, flags=re.I)
    parts = re.findall(r"[A-Za-z0-9]+", name)[:3]
    return (parts[0].lower() + "".join(p.capitalize() for p in parts[1:])) if parts else "site"


# ------------------------------------------------------------------ trips
tr = pd.read_csv(f"{GTFS}/trips.txt", dtype=str)
rt = pd.read_csv(f"{GTFS}/routes.txt", dtype=str)[["route_id", "route_short_name"]]
tr = tr.merge(rt, on="route_id")
tr = tr[tr.service_id == SERVICE_ID]
blocks_touch = set(tr[tr.route_short_name.isin(ROUTES)].block_id)
tr = tr[tr.block_id.isin(blocks_touch)]
st = pd.read_csv(f"{GTFS}/stop_times.txt", dtype={"trip_id": str, "stop_id": str},
                 usecols=["trip_id", "arrival_time", "departure_time", "stop_id",
                          "stop_sequence", "shape_dist_traveled"])
st = st[st.trip_id.isin(set(tr.trip_id))].sort_values(["trip_id", "stop_sequence"])


def _sec(s):
    p = s.str.split(":", expand=True).astype(float)
    return p[0] + p[1] / 60 + p[2] / 3600


st["a"], st["d"] = _sec(st.arrival_time), _sec(st.departure_time)
g = st.groupby("trip_id")
tt = pd.DataFrame({"start": g.d.first(), "end": g.a.last(),
                   "km": (g.shape_dist_traveled.last() - g.shape_dist_traveled.first()) / 1000,
                   "stops": g.size(), "s0": g.stop_id.first(), "s1": g.stop_id.last()})
tr = tr.merge(tt, left_on="trip_id", right_index=True)
stops = pd.read_csv(f"{GTFS}/stops.txt", dtype={"stop_id": str}).set_index("stop_id")
feed = pd.read_csv(f"{GTFS}/feed_info.txt", dtype=str).iloc[0].to_dict()

# terminal clusters (greedy, by layover-relevant stops)
term_ids = pd.concat([tr.s0, tr.s1]).value_counts().index.tolist()
clusters = []          # {lat, lon, ids, name}
cl_of = {}
for sid in term_ids:
    p = (float(stops.loc[sid, "stop_lat"]), float(stops.loc[sid, "stop_lon"]))
    for k, c in enumerate(clusters):
        if hav_km(p, (c["lat"], c["lon"])) * 1000 <= CLUSTER_M:
            c["ids"].append(sid)
            cl_of[sid] = k
            break
    else:
        clusters.append({"lat": p[0], "lon": p[1], "ids": [sid],
                         "name": str(stops.loc[sid, "stop_name"])})
        cl_of[sid] = len(clusters) - 1
tr["c0"], tr["c1"] = tr.s0.map(cl_of), tr.s1.map(cl_of)
DH_KM = {k: round(CIRCUITY * hav_km(DEPOT_LATLON, (c["lat"], c["lon"])), 2)
         for k, c in enumerate(clusters)}


def dh_km(k):
    return max(1.0, DH_KM[k])


def dh_h(k):
    return dh_km(k) / DEADHEAD_KMH


def hop_km(a, b):
    """Repositioning distance between two terminal clusters."""
    if a == b:
        return 0.0
    return round(CIRCUITY * hav_km((clusters[a]["lat"], clusters[a]["lon"]),
                                   (clusters[b]["lat"], clusters[b]["lon"])), 3)


# main route of every GTFS block, by scheduled kilometres
MAIN_OF_BLOCK = (tr.groupby(["block_id", "route_short_name"]).km.sum()
                 .reset_index().sort_values("km")
                 .drop_duplicates("block_id", keep="last")
                 .set_index("block_id").route_short_name.to_dict())


# ------------------------------------------------------------------ pieces
def make_pieces(routes, split):
    """Pieces of the given routes; each piece is a list of trip dicts."""
    pieces, dropped_km, kept_km = [], 0.0, 0.0
    sub = tr.sort_values(["block_id", "start"])
    other_km = 0.0
    for bid, b in sub.groupby("block_id"):
        cur = []
        prev_end = None
        for r in b.itertuples():
            # A block whose main route is an instance route is kept whole
            # within the model day, including trips it interlines on other
            # routes (the bus drives them); a block mainly on other routes
            # contributes only its instance-route trips.
            inst = (r.route_short_name in routes
                    or MAIN_OF_BLOCK.get(bid) in routes)
            inday = (r.start - dh_h(r.c0) >= DAY_START_H
                     and r.end + dh_h(r.c1) <= DAY_END_H)
            if inst and not inday:
                dropped_km += r.km
            if not (inst and inday):
                if cur:
                    pieces.append(cur)
                cur, prev_end = [], None
                continue
            trip = {"route": r.route_short_name, "start": r.start, "end": r.end,
                    "km": r.km, "stops": int(r.stops), "c0": r.c0, "c1": r.c1,
                    "block": bid}
            cut = False
            if cur:
                if r.start - prev_end > GAP_CUT_H:
                    cut = True
                elif split is True or (split and bid in split):
                    # per-block scale on the limits (targeted split only)
                    f = split[bid] if isinstance(split, dict) else 1.0
                    h = r.end + dh_h(r.c1) - (cur[0]["start"] - dh_h(cur[0]["c0"]))
                    km = (sum(t["km"] for t in cur) + r.km
                          + dh_km(cur[0]["c0"]) + dh_km(r.c1))
                    cut = h > f * MAX_PIECE_H or km > f * MAX_PIECE_KM
            if cut:
                pieces.append(cur)
                cur = []
            cur.append(trip)
            prev_end = r.end
            kept_km += r.km
            if r.route_short_name not in routes:
                other_km += r.km
        if cur:
            pieces.append(cur)
    make_pieces.other_km = other_km
    return pieces, kept_km, dropped_km


def main_route(piece):
    km = {}
    for t in piece:
        km[t["route"]] = km.get(t["route"], 0.0) + t["km"]
    return max(km, key=km.get)


def chain(pieces):
    """Greedy chaining of pieces into vehicle-days, per main route."""
    days = []
    by_route = {}
    for p in pieces:
        by_route.setdefault(main_route(p), []).append(p)
    for r in sorted(by_route, key=int):
        free = []                      # (time back at depot, index into days)
        for p in sorted(by_route[r], key=lambda q: q[0]["start"]):
            out = p[0]["start"] - dh_h(p[0]["c0"])
            back = p[-1]["end"] + dh_h(p[-1]["c1"])
            km = sum(t["km"] for t in p) + dh_km(p[0]["c0"]) + dh_km(p[-1]["c1"])
            free.sort()
            pick = None
            for j, (tb, k) in enumerate(free):
                if tb + MIN_DEPOT_H <= out and days[k]["km"] + km <= MAX_DAY_KM:
                    pick = j
                    break
            if pick is None:
                days.append({"route": r, "pieces": [p], "km": km})
                free.append((back, len(days) - 1))
            else:
                _, k = free.pop(pick)
                days[k]["pieces"].append(p)
                days[k]["km"] += km
                free.append((back, k))
    return days


def to_vehicle_days(days, site_of):
    """Model records: trips with service hours and deadheads, dwells."""
    out = []
    for d in days:
        trips, dwells = [], []
        P = d["pieces"]
        for pi, p in enumerate(P):
            for ti, t in enumerate(p):
                dur = t["end"] - t["start"]
                rec = {"route": t["route"], "dist_km": round(t["km"], 3),
                       "dur_h": round(dur, 4),
                       "speed": round(t["km"] / dur, 2) if dur > 0 else 0.0,
                       "f_stop": round(t["stops"] / dur, 2) if dur > 0 else 0.0,
                       "start_h": round(t["start"], 4), "end_h": round(t["end"], 4),
                       "dead_km": 0.0, "svc_h": dur}
                if ti == 0:                       # drive out from the depot
                    rec["dead_km"] += dh_km(t["c0"])
                    rec["svc_h"] += dh_h(t["c0"])
                last_of_piece = ti == len(p) - 1
                if last_of_piece:                 # drive back to the depot
                    rec["dead_km"] += dh_km(t["c1"])
                    rec["svc_h"] += dh_h(t["c1"])
                else:                             # terminal layover
                    nxt = p[ti + 1]
                    rec["svc_h"] += max(0.0, nxt["start"] - t["end"])
                    # a change of terminal (rare: 3 a day in the division)
                    # adds the repositioning hop; the bus can then charge at
                    # the departure terminal for the rest of the layover
                    hop = hop_km(t["c1"], nxt["c0"])
                    rec["dead_km"] += hop
                    site = site_of.get(nxt["c0"], "none")
                    s_dw = min(nxt["start"], t["end"] + hop / DEADHEAD_KMH)
                    dwells.append([site, round(s_dw, 4), round(nxt["start"], 4)])
                if last_of_piece and pi < len(P) - 1:
                    nxt = P[pi + 1][0]
                    dwells.append(["depot", round(t["end"] + dh_h(t["c1"]), 4),
                                   round(nxt["start"] - dh_h(nxt["c0"]), 4)])
                rec["dead_km"] = round(rec["dead_km"], 3)
                rec["svc_h"] = round(rec["svc_h"], 4)
                trips.append(rec)
        first, last = P[0][0], P[-1][-1]
        out.append({"route": d["route"], "n_pieces": len(P),
                    "gtfs_blocks": sorted({t["block"] for p in P for t in p}),
                    "pullout_h": round(first["start"] - dh_h(first["c0"]), 4),
                    "pullin_h": round(last["end"] + dh_h(last["c1"]), 4),
                    "trips": trips, "dwells": dwells})
        assert len(dwells) == len(trips) - 1
    return out


def layover_bus_hours(pieces):
    bh = {}
    for p in pieces:
        for a, b in zip(p, p[1:]):
            if a["c1"] == b["c0"]:
                bh[a["c1"]] = bh.get(a["c1"], 0.0) + max(0.0, b["start"] - a["end"])
    return bh


def build(routes, split, name):
    """split: True (blocking rule everywhere), False (as scheduled), or a set
    of GTFS block ids to which the blocking rule applies."""
    pieces, kept_km, dropped_km = make_pieces(set(routes), split)
    bh = layover_bus_hours(pieces)
    site_of, used = {}, set()
    for k, h in sorted(bh.items(), key=lambda kv: -kv[1]):
        if h >= MIN_SITE_BUSH:
            s = slug(clusters[k]["name"])
            while s in used or s == "depot":
                s += "2"
            used.add(s)
            site_of[k] = s
    days = chain(pieces)
    vds = to_vehicle_days(days, site_of)
    km = np.array([sum(t["dist_km"] + t["dead_km"] for t in v["trips"]) for v in vds])
    hrs = np.array([sum(t["svc_h"] for t in v["trips"]) for v in vds])
    ts = np.arange(DAY_START_H, DAY_END_H, 0.25)
    peak = max(sum(1 for v in vds for t in v["trips"]
                   if t["start_h"] <= x < t["end_h"]) for x in ts)
    summ = {"instance": name, "routes": routes, "blocking_rule": (split if isinstance(split, bool) else f"partial: {len(split)} blocks"),
            "gtfs_blocks": len({t["block"] for p in pieces for t in p}),
            "pieces": len(pieces), "vehicle_days": len(vds),
            "peak_buses_on_trips": int(peak),
            "trips": int(sum(len(v["trips"]) for v in vds)),
            "revenue_km": round(kept_km, 0),
            "km_on_other_routes": round(make_pieces.other_km, 0),
            "dropped_km_share": round(dropped_km / (kept_km + dropped_km), 4),
            "km_mean": round(float(km.mean()), 1), "km_p90": round(float(np.quantile(km, .9)), 1),
            "km_max": round(float(km.max()), 1),
            "svc_h_mean": round(float(hrs.mean()), 2), "svc_h_max": round(float(hrs.max()), 2),
            "share_multi_piece": round(float(np.mean([v["n_pieces"] > 1 for v in vds])), 3),
            "by_route": {r: int(sum(v["route"] == r for v in vds)) for r in routes},
            "sites": {s: {"layover_bus_h": round(bh[k], 1), "stop": clusters[k]["name"],
                          "deadhead_km": dh_km(k)} for k, s in site_of.items()}}
    return vds, ["depot"] + sorted(site_of.values()), summ


# ------------------------------------------------------------ telemetry
df = pd.read_excel(TTC_XLSX)
df["mon"] = pd.to_datetime(df["Date"]).dt.month
tel = df[(df["Distance [km]"] > 3) & (df["Time_Total [hr]"] > 0)
         & df["Avg Ambient Temp [degC]"].notna()].copy()
GAM, KAP = 0.3301, 0.0117
tel["phi"] = 1.0 / (1.0 + np.exp(-(GAM + KAP * tel["Avg Ambient Temp [degC]"])))
tel["qff"] = tel["phi"] * 35.0 * tel["Aux. Heating Time [hr]"]
tel["q"] = tel["qff"] + tel["eHeat Energy Used [kWh]"]
tel["L"] = tel["Aux. Heating Time [hr]"] * (3.6 / 0.837)


def band(T):
    return ("mild" if T >= 0 else "cold" if T >= -5 else "verycold" if T >= -10
            else "extreme" if T >= -15 else "severe")


win = tel[tel.mon.isin([11, 12, 1, 2, 3])].copy()
win["band"] = [band(T) for T in win["Avg Ambient Temp [degC]"]]
off = tel[~tel.mon.isin([11, 12, 1, 2, 3])]
share, litres, nrun = {}, {}, {}
for w in ("mild", "cold", "verycold", "extreme", "severe"):
    s = win[win.band == w]
    nrun[w] = int(len(s))
    share[w] = float(s.qff.sum() / s.q.sum())
    litres[w] = float(s.L.mean())
# the extreme and severe bands have 52 and 4 runs: pool them
ps = win[win.band.isin(["extreme", "severe"])]
share["extreme"] = share["severe"] = float(ps.qff.sum() / ps.q.sum())
litres["extreme"] = litres["severe"] = float(ps.L.mean())
OBS = {"pax_per_h": round(float(tel["Total Passengers Onboarded"].sum()
                                / tel["Time_Total [hr]"].sum()), 1),
       "offseason_heat_kw": round(float(off.q.sum() / off["Time_Total [hr]"].sum()), 2),
       "ffh_share_obs": {**{w: round(v, 3) for w, v in share.items()},
                         "offseason": round(float(off.qff.sum() / off.q.sum()), 3)},
       "obs_diesel_L_busday": {**{w: round(v, 2) for w, v in litres.items()},
                               "offseason": round(float(off.L.mean()), 2)},
       "obs_runs": {**nrun, "offseason": int(len(off))},
       "obs_busday_hours_mean": {"winter": round(float(win["Time_Total [hr]"].mean()), 2),
                                 "offseason": round(float(off["Time_Total [hr]"].mean()), 2)}}

# ------------------------------------------------------------------ write
NOTE = (f"v11g: weekday service from the TTC GTFS feed {feed.get('feed_version')} "
        f"({feed.get('feed_start_date')}-{feed.get('feed_end_date')}); "
        "see build_instances_v11.py")
DROP = ("branches", "deadhead_km", "deadhead_min", "service_end_h")
summary = {"feed": feed, "params": {
    "DAY_START_H": DAY_START_H, "GAP_CUT_H": GAP_CUT_H, "MAX_PIECE_H": MAX_PIECE_H,
    "MAX_PIECE_KM": MAX_PIECE_KM, "MIN_DEPOT_H": MIN_DEPOT_H, "MAX_DAY_KM": MAX_DAY_KM,
    "CIRCUITY": CIRCUITY, "DEADHEAD_KMH": DEADHEAD_KMH, "MIN_SITE_BUSH": MIN_SITE_BUSH,
    "DEPOT_LATLON": DEPOT_LATLON}, "observed": OBS, "instances": []}


def heaterfree_infeasible(path):
    """Vehicle-days that no heater-free bus can serve in some band, even with
    the extended battery, the electric heater at full output and charging at
    the bus acceptance limit at every candidate terminal layover. Uses the
    model's own energy functions on the written instance."""
    import importlib
    os.environ["ROUTE_INPUTS"] = os.path.basename(path)
    import route52_prototype as R
    R = importlib.reload(R)
    bc = max((b for b in R.BUS_CLASSES if not b.ffh), key=lambda b: b.batt_nom)
    bad = {}
    for w, (T, _) in R.SCEN.items():
        cap_der, acc = R.DERATE[w]
        for blk in R.BLOCKS:
            cap = cap_der * bc.batt_nom
            E, nt, short = R.S_UP * cap, len(blk.trips), 0.0
            for i, tr in enumerate(blk.trips):
                hh = R.heat_hours(blk, i)
                q = (R.HEAT_KW_FIXED[w] if w in R.HEAT_KW_FIXED else 0.0
                     if w in R.HEATLESS else R.q_heat_rate(T, tr.f_stop, tr.speed)) * hh
                E -= (R.e_traction_per_km(T, tr.speed, route=R.trip_route(blk, i))
                      * R.trip_km(blk, i) * (1 + bc.mass_pen)
                      + R.aux_kw(T) * R.aux_hours(blk, i) + min(q, hh * R.P_ELH_RATED))
                need = R.S_LO * cap + (R.RESERVE_RETURN if i == nt - 1 else 0.0)
                short = min(short, E - need)
                if i < nt - 1:
                    site, a, e = blk.dwells[i]
                    if site in R.SITES:
                        E = min(R.S_UP * cap, E + R.ETA_CH * R.BUS_ACCEPT * acc * (e - a))
            if short < 0:
                bad.setdefault(blk.bid, {})[w] = round(short, 1)
    return bad


def write(base, routes, split, out, name, split_infeasible=False):
    inp = json.load(open(os.path.join(HERE, base)))
    vds, sites, summ = build(routes, split, name)
    forced = {}
    if split_infeasible:
        # write once, find the vehicle-days a heater-free bus cannot serve,
        # and apply the blocking rule to their GTFS blocks only
        tmp = {**{k: v for k, v in inp.items() if k not in DROP},
               "vehicle_days": vds, "sites": sites, "service_start_h": DAY_START_H,
               "pax_per_h": OBS["pax_per_h"], "ffh_share_obs": OBS["ffh_share_obs"]}
        for w, sc in tmp["scenarios"].items():
            if not sc.get("heat", True):
                sc["heat_kw"] = OBS["offseason_heat_kw"]
        tp = os.path.join(HERE, "_tmp_" + out)
        json.dump(tmp, open(tp, "w"))
        # The blocking rule is applied to the GTFS blocks of the infeasible
        # vehicle-days. A block that stays infeasible (short enough to pass
        # the rule, but with too few charging stops) gets its limits scaled
        # down by 0.75 per round until every vehicle-day can be served.
        scale, rounds = {}, []
        for it in range(6):
            bad = heaterfree_infeasible(tp)
            rounds.append({str(b): v for b, v in bad.items()})
            if not bad:
                break
            for b in bad:
                for blk_id in vds[b]["gtfs_blocks"]:
                    scale[blk_id] = scale.get(blk_id, 1.0 / 0.75) * 0.75
            vds, sites, summ = build(routes, dict(scale), name)
            tmp.update({"vehicle_days": vds, "sites": sites})
            json.dump(tmp, open(tp, "w"))
        os.remove(tp)
        assert not bad, f"vehicle-days still infeasible without a heater: {bad}"
        forced = {"rounds": rounds,
                  "gtfs_blocks_split": {b: round(f, 3) for b, f in sorted(scale.items())}}
        summ["heaterfree_split"] = forced
        print(f"   heater-free split: limit scale per GTFS block {forced['gtfs_blocks_split']}, "
              f"rounds {len(rounds)}")
    for k in DROP:
        inp.pop(k, None)
    if split_infeasible:
        inp["heaterfree_split"] = forced
    inp.update({"vehicle_days": vds, "sites": sites, "instance_name": name,
                "service_start_h": DAY_START_H, "instance_note": NOTE,
                "pax_per_h": OBS["pax_per_h"], "ffh_share_obs": OBS["ffh_share_obs"]})
    for w, sc in inp["scenarios"].items():
        if not sc.get("heat", True):
            sc["heat_kw"] = OBS["offseason_heat_kw"]
    json.dump(inp, open(os.path.join(HERE, out), "w"), indent=1)
    summary["instances"].append(summ)
    print(json.dumps({k: v for k, v in summ.items() if k != "sites"}))
    print("   sites:", {s: v["layover_bus_h"] for s, v in summ["sites"].items()})


write("route52_inputs_v11.json", ["52"], True, "route52_inputs_v11g.json", "route52_gtfs")
write("route52_inputs_v11.json", ["52"], False, "route52_inputs_v11g_sched.json",
      "route52_gtfs_as_scheduled", split_infeasible=True)
write("garage_inputs_v11.json", ROUTES, True, "garage_inputs_v11g.json", "arrow_road_gtfs")
write("garage_inputs_v11.json", ROUTES, False, "garage_inputs_v11g_sched.json",
      "arrow_road_gtfs_as_scheduled", split_infeasible=True)
json.dump(summary, open(os.path.join(HERE, "instances_v11g_summary.json"), "w"), indent=1)
print(json.dumps(OBS))
