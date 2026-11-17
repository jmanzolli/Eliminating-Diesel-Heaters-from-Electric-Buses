"""Route 52 branch table (tab:branches) from the TTC GTFS feed.

Writes overleaf-git/supp_tables/tab_branches_m2.tex. Same feed and service as
build_instances_v11.py: weekday service_id 1 of feed S1000544.

Branch of a trip: westbound trips carry the branch letter in the headsign
(52A/52B/52F/52G). Eastbound trips of 52A and 52B share the headsign
"52 ... towards Lawrence Station", so eastbound trips are assigned by the
western terminal they leave from. The short Pearson Terminal 1 -> Terminal 3
trips that precede each eastbound 52A trip are counted only in the total.

Leg length and run time are taken over the full-length trips of each branch and
direction (the most frequent origin-destination pair); trip counts include
short turns. Run time is scheduled departure at the first stop to arrival at
the last stop.

Usage (from code/):
  GTFS_ZIP="/path/Complete GTFS.zip" python3 make_branch_table_v11.py
  GTFS_DIR=<unzipped feed>          python3 make_branch_table_v11.py
"""
import os
import zipfile

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "..", "overleaf-git")
ROUTE = "52"
SERVICE_ID = "1"                 # weekday, as in build_instances_v11.py

# western terminal (stop-name prefix) -> branch; eastbound trips start there
WEST_TERMINAL = [("Pearson Airport Terminal 3", "52A"),
                 ("Westwood Square", "52B"),
                 ("The Westway at Royal York", "52F"),
                 ("Martin Grove Rd at Tollington", "52G")]
AIRPORT_LOOP = ("Pearson Airport Terminal 1", "Pearson Airport Terminal 3")
TERMINI = {"52A": "Lawrence Stn--Pearson Airport",
           "52B": "Lawrence Stn--Westwood Sq.",
           "52F": "Sunnybrook Hosp.--Royal York",
           "52G": "Lawrence W.\\ Stn--Martin Grove"}
BRANCHES = ["52A", "52B", "52F", "52G"]


def reader():
    if os.environ.get("GTFS_ZIP"):
        z = zipfile.ZipFile(os.environ["GTFS_ZIP"])
        return lambda name: z.open(name)
    d = os.environ["GTFS_DIR"]
    return lambda name: os.path.join(d, name)


src = reader()
feed = pd.read_csv(src("feed_info.txt"), dtype=str).iloc[0].to_dict()
rt = pd.read_csv(src("routes.txt"), dtype=str)
tr = pd.read_csv(src("trips.txt"), dtype=str)
tr = tr[tr.route_id.isin(rt[rt.route_short_name == ROUTE].route_id)
        & (tr.service_id == SERVICE_ID)]
ids = set(tr.trip_id)
st = pd.concat(c[c.trip_id.isin(ids)] for c in pd.read_csv(
    src("stop_times.txt"), dtype={"trip_id": str, "stop_id": str},
    usecols=["trip_id", "arrival_time", "departure_time", "stop_id",
             "stop_sequence", "shape_dist_traveled"], chunksize=2_000_000))
st = st.sort_values(["trip_id", "stop_sequence"])
stops = pd.read_csv(src("stops.txt"), dtype={"stop_id": str}).set_index("stop_id")


def minutes(s):
    p = s.str.split(":", expand=True).astype(float)
    return p[0] * 60 + p[1] + p[2] / 60


st["a"], st["d"] = minutes(st.arrival_time), minutes(st.departure_time)
g = st.groupby("trip_id")
tt = pd.DataFrame({"o": g.stop_id.first().map(stops.stop_name),
                   "dst": g.stop_id.last().map(stops.stop_name),
                   "km": (g.shape_dist_traveled.last()
                          - g.shape_dist_traveled.first()) / 1000,
                   "min": g.a.last() - g.d.first()})
tr = tr.merge(tt, left_on="trip_id", right_index=True)


def branch(r):
    if r.direction_id == "1":
        return r.trip_headsign.split(" - ")[1].split(" ")[0]
    if r.o.startswith(AIRPORT_LOOP[0]) and r.dst.startswith(AIRPORT_LOOP[1]):
        return "loop"
    for prefix, b in WEST_TERMINAL:
        if r.o.startswith(prefix):
            return b
    raise ValueError(f"no branch for eastbound trip {r.trip_id} from {r.o}")


tr["branch"] = tr.apply(branch, axis=1)
tr["dir"] = tr.direction_id.map({"1": "W", "0": "E"})
assert set(tr.branch) == set(BRANCHES) | {"loop"}, set(tr.branch)

rows, check = [], {}
for b in BRANCHES:
    cell = {}
    for d in ["W", "E"]:
        x = tr[(tr.branch == b) & (tr.dir == d)]
        full = x[(x.o + x.dst) == (x.o + x.dst).mode()[0]]
        cell[d] = dict(n=len(x), km=full.km.median(), mean=full["min"].mean(),
                       lo=full["min"].min(), hi=full["min"].max())
    blocks = tr[tr.branch == b].block_id.nunique()
    check[b] = cell
    rows.append(
        f"{b} & {TERMINI[b]} & {cell['W']['n']}/{cell['E']['n']} & "
        f"{cell['W']['km']:.1f}/{cell['E']['km']:.1f} & "
        f"{cell['W']['mean']:.0f}/{cell['E']['mean']:.0f} & "
        f"{cell['W']['lo']:.0f}--{cell['W']['hi']:.0f}/"
        f"{cell['E']['lo']:.0f}--{cell['E']['hi']:.0f} & {blocks} \\\\")

loop = tr[tr.branch == "loop"]
n_all, n_blocks = len(tr), tr.block_id.nunique()
body = r"""\begin{table}[pos=htbp]
\caption{Route~52 branches, westbound/eastbound, weekday service of TTC GTFS feed %s. Trips include short turns; leg length and run time refer to full-length trips. Eastbound 52A trips start at Pearson Terminal~3 and are preceded by a %.1f-km trip from Terminal~1 (%d per weekday, counted only in the total). A block can run more than one branch, so the Blocks column does not add up to the %d blocks of the route.}
\label{tab:branches}
\centering
\small
\setlength{\tabcolsep}{3pt}
\fittab{llrrrrr@{}}{
\toprule
\textbf{Branch} & \textbf{Termini} & \textbf{Trips} & \textbf{\makecell{Leg\\(km)}} &
\textbf{\makecell{Mean run\\(min)}} & \textbf{\makecell{Run range\\(min)}} &
\textbf{Blocks} \\
\midrule
%s
\midrule
All & & %d & & & & %d \\
\bottomrule
}
\end{table}
""" % (feed["feed_version"], loop.km.median(), len(loop), n_blocks,
       "\n".join(rows), n_all, n_blocks)

stamp = ("% GENERATED by make_branch_table_v11.py from the TTC GTFS feed "
         f"{feed['feed_version']}.\n% Do not edit by hand - regenerate instead.\n")
path = os.path.join(TEX, "supp_tables", "tab_branches_m2.tex")
open(path, "w").write(stamp + body)
print("wrote", os.path.relpath(path, os.path.join(HERE, "..")))
print(f"trips {n_all} (airport loop {len(loop)}), blocks {n_blocks}")
for b, c in check.items():
    print(b, {d: {k: round(v, 1) for k, v in c[d].items()} for d in c})
