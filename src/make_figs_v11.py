"""Manuscript figures from the v11 campaign (TR-C manuscript, main.tex), in the
house style of make_figs_m2.py. Overwrites, in ../overleaf-git/figures/m2/:

  fig3_ops          heat by source and diesel per band, baseline D0
  fig_robust        cost of removing the heaters by variant, with certified
                    ranges (a); heaters kept against the installed heater price (b)
  fig4_frontier     every recorded design, the lower convex hull and the design
                    ladder D0-D4 (a); annual cost by component, D0-D4 (b)
  fig5_uncertainty  days above the reserve and days with every trip completed,
                    by band, data-implied heat variation
  fig_division      four plans: cost interval, heater-equipped buses, emissions
  figS_routes       per-route heater share, route planned alone

  fig_severe_day    one severe day of D0 and D4 (state of charge, site load),
                    heat by band, cost by component (v11b fixed-design data)
  fig_price         depot load of D0 and D4 against the energy price (v11b)

  fig_weather       days per band in each winter (input data, redrawn for size only)

Every figure is saved at one of two exact widths, FULL (the text width of the
cas-sc page, 16.5 cm) or NARROW, and included in main.tex at natural size, so
type is 8 pt in all of them.

Inputs: v11_results/results_v11.json (postprocess_v11.py) and the v11b figure
data in v11b_results/ (run_tighten_v11.sh, stage 2).
Usage (from code/): python3 make_figs_v11.py
"""
import json
import os
import sys

sys.argv = sys.argv[:1] + ["v9rev"]       # make_figs_m2 loads its own archive at import
import make_figs_m2 as M                   # noqa: E402
from make_figs_m2 import (BANDS, BLBL, BLUE, BOX, CM, GREEN, GRID, INK, MUTED,  # noqa: E402
                          OCHRE, ROSE, W1, W2, panel, plt, save)
import numpy as np                         # noqa: E402
from matplotlib.lines import Line2D        # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))

# ------------------------------------------------------------- styles
# FIG_STYLE picks one of three validated looks (palettes pass the dataviz
# validator: lightness band, chroma floor, CVD and normal-vision separation).
#   a  clean sans (house style): Helvetica, light horizontal grid, framed legends
#   b  serif journal: STIX Two (the text font of the paper), closed axes with
#      inward ticks, no grid, frameless legends, Okabe-Ito colours
#   c  minimal: Helvetica Neue, offset open axes (seaborn ticks), no grid,
#      frameless legends, Paul Tol vibrant colours
# FIG_OUT redirects the output (style previews); default is the manuscript folder.
STYLE = os.environ.get("FIG_STYLE", "c")   # chosen by the authors, 2026-11-16
STYLES = {
    "a": dict(colors=("#3F6FB5", "#2E9443", "#E06377", "#B58A1B"), rc={}),
    "b": dict(colors=("#0072B2", "#009E73", "#D55E00", "#E69F00"), rc={
        "font.family": "serif", "font.serif": ["STIX Two Text", "STIXGeneral", "Times"],
        "mathtext.fontset": "stix", "axes.grid": False,
        "axes.spines.top": True, "axes.spines.right": True, "axes.linewidth": 0.6,
        "axes.edgecolor": "#222222", "xtick.direction": "in", "ytick.direction": "in",
        "xtick.top": True, "ytick.right": True, "legend.frameon": False,
        "font.size": 8.5, "axes.labelsize": 8.5, "xtick.labelsize": 8, "ytick.labelsize": 8,
        "legend.fontsize": 7.8}),
    "c": dict(colors=("#3366AA", "#11AA99", "#992288", "#EE3333"), rc={
        "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial"],
        "axes.grid": False, "axes.edgecolor": "#555555", "axes.linewidth": 0.7,
        "xtick.color": "#333333", "ytick.color": "#333333",
        "xtick.major.size": 3.5, "ytick.major.size": 3.5, "legend.frameon": False}),
}
plt.rcParams.update(STYLES[STYLE]["rc"])
BLUE, GREEN, ROSE, OCHRE = STYLES[STYLE]["colors"]
M.BLUE, M.GREEN, M.ROSE, M.OCHRE = BLUE, GREEN, ROSE, OCHRE
if os.environ.get("FIG_OUT"):
    M.OUT = os.environ["FIG_OUT"]
    os.makedirs(M.OUT, exist_ok=True)

RES = json.load(open(os.path.join(HERE, "v11_results", "results_v11.json")))
COR = RES["corridor"]
DES = COR["designs"]
UB0 = COR["UB0"]
LAD = dict(zip(["D0", "D1", "D2", "D3", "D4"], COR["ladder"]))
REL = RES["reliability"]
V11B = os.path.join(HERE, "v11b_results")


FULL, NARROW, PAD = 16.4 * CM, 12.0 * CM, 0.03
WIDTH = {"fig_weather": FULL, "fig3_ops": NARROW, "fig_robust": FULL, "fig4_frontier": FULL,
         "fig5_uncertainty": FULL, "fig_severe_day": FULL, "fig_division": FULL,
         "figS_routes": NARROW, "fig_price": NARROW}


def save(fig, name):            # noqa: F811  (replaces the house save: exact width)
    """Save cropped to the artists, at exactly WIDTH[name]: the canvas is
    widened or narrowed until the cropped width matches, so text keeps its size."""
    target = WIDTH[name]            # inches (CM converts cm to inches)
    if STYLE == "c":                # open axes, pulled away from the data
        import seaborn as sns
        for ax in fig.axes:
            if ax.axison:
                sns.despine(ax=ax, offset=4)
    for _ in range(15):
        fig.canvas.draw()
        w = fig.get_tightbbox(fig.canvas.get_renderer()).width + 2 * PAD
        if abs(w - target) < 0.002:
            break
        fw, fh = fig.get_size_inches()
        fig.set_size_inches(max(1.0, fw + (target - w)), fh)
    fig.savefig(f"{M.OUT}/{name}.pdf", bbox_inches="tight", pad_inches=PAD)
    if not os.environ.get("FIG_OUT"):
        fig.savefig(f"ieee_figs/m2/{name}.png", bbox_inches="tight", pad_inches=PAD)
    plt.close(fig)
    print(f"wrote {name} ({w * 2.54:.2f} cm)")


M.save = save                   # figures drawn by make_figs_m2 use it too


def hours(ax, t0, step, fmt="{:02d}"):
    """Clock ticks on an axis that runs from t0 to t0 + 24 h."""
    ticks = np.arange(np.ceil(t0 / step) * step, t0 + 24.01, step)
    ax.set_xticks(ticks, [fmt.format(int(t % 24)) for t in ticks])


def load_b(fn):
    return json.load(open(os.path.join(V11B, fn)))


def clock_label(t0):
    h, m = int(t0), int(round(60 * (t0 - int(t0))))
    return f"{h:02d}:{m:02d}"


# ------------------------------------------------------------- weather (input)
def fig_weather():
    wea = json.load(open(os.path.join(HERE, "data_v9", "eccc_winter_bands_v9.json")))["winters"]
    yrs = list(wea)
    cnt = {b: np.array([wea[y][b] * 151.0 / wea[y]["n"] for y in yrs]) for b in BANDS}
    fig, ax = plt.subplots(figsize=(W2, 5.8 * CM))
    x = np.arange(len(yrs))
    bottom = np.zeros(len(yrs))
    for b, lab, col in zip(reversed(BANDS), reversed(BLBL), reversed(M.RAMP)):
        ax.bar(x, cnt[b], 0.78, bottom=bottom, color=col, edgecolor="white", linewidth=0.5,
               label=lab)
        bottom += cnt[b]
    ax.set_xlim(-0.6, len(yrs) - 0.4)
    ax.set_ylim(0, 151)
    ax.set_yticks([0, 50, 100, 150])
    ax.set_xticks(x[::2], [f"{y[:4]}–{y[5:]}" for y in yrs][::2])
    ax.tick_params(axis="x", labelsize=7)
    ax.set_ylabel("Days per winter")
    h, l = ax.get_legend_handles_labels()
    ax.legend(h[::-1], l[::-1], ncols=5, loc="lower center", bbox_to_anchor=(0.5, 1.03))
    save(fig, "fig_weather")


# ------------------------------------------------------------- operation (D0)
def fig_ops():
    so = DES[LAD["D0"]]["scen_ops"]
    x = np.arange(len(BANDS))
    pre = np.array([so[w]["precond_kWh"] for w in BANDS])
    qel = np.array([so[w]["q_el_kWh"] for w in BANDS])
    qff = np.array([so[w]["q_ffh_kWh"] for w in BANDS])
    dsl = np.array([so[w]["diesel_L"] for w in BANDS])
    xt = [f"{l}\n{so[w]['T']:+.1f}°C".replace("-", "−") for l, w in zip(BLBL, BANDS)]
    fig, (a, b) = plt.subplots(2, 1, figsize=(W1, 8.4 * CM), sharex=True,
                               gridspec_kw={"height_ratios": [1.7, 1], "hspace": 0.2})
    if (pre / (pre + qel + qff)).max() < 0.01:
        # preconditioning below 1% of delivered heat in every band (it is in
        # Table tab:scen): too thin to draw, so it is counted with the electric heater
        qel, pre = qel + pre, np.zeros(len(BANDS))
    else:
        a.bar(x, pre, 0.62, color="#9AA7B8", edgecolor="white", lw=0.6,
              label="Preconditioning")
    a.bar(x, qel, 0.62, bottom=pre, color=BLUE, edgecolor="white", lw=0.6,
          label="Electric heater")
    a.bar(x, qff, 0.62, bottom=pre + qel, color=OCHRE, edgecolor="white", lw=0.6,
          label="Diesel heater")
    tot = pre + qel + qff
    for i in range(len(BANDS)):
        if qff[i] / tot[i] > 0.03:
            a.text(i, tot[i] + 0.015 * tot.max(), f"{100 * qff[i] / tot[i]:.0f}% diesel",
                   ha="center", va="bottom", fontsize=7, color=INK)
    a.set_ylabel("Cabin heat (kWh/day)")
    a.set_ylim(0, tot.max() * 1.1)
    a.legend(loc="lower center", bbox_to_anchor=(0.5, 1.02), ncols=3)
    panel(a, "a")
    b.bar(x, dsl, 0.62, color=OCHRE, edgecolor="white", lw=0.6)
    for i, v in enumerate(dsl):
        if v > 5:
            b.text(i, v + 0.02 * dsl.max(), f"{v:.0f}", ha="center", va="bottom", fontsize=7)
    b.set_ylabel("Diesel (L/day)")
    b.set_ylim(0, dsl.max() * 1.2)
    b.set_xticks(x, xt)
    panel(b, "b")
    save(fig, "fig3_ops")


# ------------------------------------------------------------- robustness
def fig_robust():
    V = RES["variants"]
    order = ["phi055", "phi060", "heat094", "heat1035", "fuel070", "fuel115", "sev115",
             "sev130", "plug30", "plug60", "wear", "coldw", "fracw", "hp"]
    rows = []
    for v in order:
        r = V.get(v)
        if not r or "premium" not in r:
            continue
        e = r["econ"]["F1"]
        rows.append((r["name"].replace("-6%", "−6%"), 100 * r["premium"] / e,
                     100 * r["premium_lo"] / e, 100 * r["premium_hi"] / e))
    hf = DES[LAD["D4"]]
    base = (100 * (hf["F1"] - UB0) / UB0, 100 * hf["cert_lo"] / UB0, 100 * hf["cert_hi"] / UB0)
    rows.sort(key=lambda r: r[1])
    n = len(rows)
    y = np.arange(n)
    fig, (a, b) = plt.subplots(1, 2, figsize=(W2, 7.6 * CM),
                               gridspec_kw={"width_ratios": [1.55, 1], "wspace": 0.34})
    a.grid(axis="y", visible=False)
    a.grid(axis="x", color=GRID, lw=0.6)
    a.axvspan(base[1], base[2], color="#EDEDED", zorder=0, lw=0)
    a.axvline(base[0], color=INK, lw=0.8)
    for yi, (lab, p, lo, hi) in zip(y, rows):
        a.hlines(yi, lo, hi, color=MUTED, lw=0.9, zorder=2)
        a.plot(p, yi, "o", color=ROSE if p > base[0] else BLUE, ms=4.6, mec="white",
               mew=0.5, zorder=3)
        a.text(hi + 0.04, yi, f"{p:.2f}", va="center", fontsize=6.8, color=MUTED)
    a.set_yticks(y, [r[0] for r in rows])
    a.set_xlim(0, max(r[3] for r in rows) + 0.45)
    a.set_xlabel("Cost of removing all heaters (% of annual fleet cost)")
    a.text(base[0] + 0.03, n - 0.35, f"Base case {base[0]:.2f}%", fontsize=7, ha="left",
           va="bottom", color=INK)
    a.set_ylim(-0.6, n + 0.3)
    panel(a, "a", x=-0.6)
    cap = RES["capex"]["runs"]
    sens = RES["sensitivities"]
    pts = [(0.0, DES[LAD["D0"]]["n_ffh"])]
    pts += [(5.0, sens["ffh_capex_5000"]["best"]["n_ffh"]),
            (15.0, sens["ffh_capex_15000"]["best"]["n_ffh"])]
    pts += [(float(c) / 1e3, r["n_ffh"]) for c, r in cap.items()]
    pts.sort()
    b.plot([p[0] for p in pts], [p[1] for p in pts], "o", color=OCHRE, ms=5, mec="white",
           mew=0.6, zorder=3)
    env = RES["capex"]["envelope"]
    ex = [c / 1e3 for c, _ in env] + [35.0]
    ey = [nh for _, nh in env] + [env[-1][1]]
    ex = [x for x in ex if x <= 35.0]
    ey = ey[:len(ex)]
    b.step(ex + [35.0], ey + [ey[-1]], where="post", color=MUTED, lw=0.9, ls=(0, (2, 2)),
           zorder=2, label="Best known design")
    b.axvspan(3.0, 5.0, color="#EFEFEF", zorder=0, lw=0)
    b.text(4.0, 2.0, "retail unit\nprice", fontsize=6.8, color=MUTED, ha="center")
    b.set_xlim(-1, 32)
    b.set_ylim(0, 16)
    b.set_yticks([0, 4, 8, 12, 16])
    b.set_xlabel("Installed cost per heater (kCAD)")
    b.set_ylabel(f"Heaters kept (of {sum(DES[LAD['D0']]['fleet'].values())} buses)")
    b.legend(loc="upper right")
    panel(b, "b", x=-0.14)
    save(fig, "fig_robust")


# ------------------------------------------------------------- frontier
def fig_frontier():
    f0 = UB0
    caps = [r for l, r in DES.items() if l.startswith("eps_")
            or (l.startswith("t_cap_") and l.endswith("_free"))]
    fixd = [r for l, r in DES.items() if "_fix_" in l and r["co2_t"] <= DES[LAD["D0"]]["co2_t"]]
    lams = [r for l, r in DES.items() if l.startswith(("lam_", "bp_lam_", "policy_lam100"))
            and not l.endswith("_ops")]
    ties = [DES[t["label"]] for t in COR["ties"]] + [DES["econ_lam0"]]
    hull = [DES[l] for l in COR["hull"]]
    fig, (ax, d) = plt.subplots(1, 2, figsize=(W2, 7.4 * CM),
                                gridspec_kw={"width_ratios": [1.45, 1], "wspace": 0.3})
    top = 150
    ax.plot([r["co2_t"] for r in hull], [(r["F1"] - f0) / 1e3 for r in hull],
            color="#7A7A7A", lw=1.0, zorder=2, label="Lower convex hull")
    ax.plot([r["co2_t"] for r in caps], [(r["F1"] - f0) / 1e3 for r in caps], "o",
            color=BLUE, ms=4.5, mec="white", mew=0.5, zorder=3, label="Emissions cap")
    ax.plot([r["co2_t"] for r in lams], [(r["F1"] - f0) / 1e3 for r in lams], "D",
            mfc="white", mec=ROSE, mew=1.1, ms=4.2, zorder=3, label="Carbon price")
    ax.plot([r["co2_t"] for r in fixd], [(r["F1"] - f0) / 1e3 for r in fixd], "^",
            mfc="white", mec=GREEN, mew=0.9, ms=4.2, zorder=3,
            label="Fixed design, cost only")
    ax.plot([r["co2_t"] for r in ties], [(r["F1"] - f0) / 1e3 for r in ties], "s",
            mfc="white", mec=MUTED, mew=0.9, ms=4.0, zorder=3,
            label="Cost ties (0.5 kCAD)")
    labels = {"D0": ("D0: cost-only", (31.0, 17)),
              "D1": ("D1: + 450 kW at Westway", (7.5, 23)),
              "D2": ("D2: + charger at Pearson", (6.0, 50)),
              "D3": ("D3: + depot reconfig.", (4.0, 76)),
              "D4": ("D4: heater-free", (3.0, 128))}
    for kk, (txt, xy) in labels.items():
        r = DES[LAD[kk]]
        ax.annotate(txt, (r["co2_t"], (r["F1"] - f0) / 1e3), xytext=xy,
                    textcoords="data", fontsize=6.8, ha="left", va="center", bbox=BOX,
                    arrowprops=dict(arrowstyle="-", color="#8A8A8A", lw=0.6, shrinkB=3),
                    zorder=5)
    seg = COR["segments"]
    ax.text(17.5, -6.0, f"about {seg[0]['price'] / 1e3:.1f} kCAD/t", fontsize=6.8,
            color=INK)
    ax.text(1.2, 100, f"about {seg[-1]['price'] / 1e3:.0f} kCAD/t", fontsize=6.8,
            color=INK, ha="left")
    ax.set_xlim(-1.0, 44)
    ax.set_ylim(-9, top)
    ax.set_xlabel("Onboard emissions (t CO$_2$/yr)")
    ax.set_ylabel("Cost over design D0 (kCAD/yr)")
    ax.legend(loc="center right", bbox_to_anchor=(1.0, 0.66), fontsize=6.8)
    panel(ax, "a", x=-0.1)
    cats = ["Chargers and grid", "Electricity and demand charges",
            "Heater maintenance and diesel"]
    cols = [GREEN, "#9AA7B8", OCHRE]
    lbls = [(k, LAD[k]) for k in ("D0", "D1", "D2", "D3", "D4")]
    vals = np.array([((DES[l]["cost_parts"]["charger_site_capital"]
                       + DES[l]["cost_parts"]["grid_capital"]) / 1e3,
                      (DES[l]["cost_parts"]["demand_charges"]
                       + DES[l]["cost_parts"]["electricity"]) / 1e3,
                      (DES[l]["cost_parts"]["ffh_om"] + DES[l]["cost_parts"]["diesel_cost"]) / 1e3)
                     for _, l in lbls])
    y = np.arange(len(lbls))
    left = np.zeros(len(lbls))
    d.grid(axis="y", visible=False)
    d.grid(axis="x", color=GRID, lw=0.6)
    for ci in range(3):
        d.barh(y, vals[:, ci], 0.6, left=left, color=cols[ci], edgecolor="white",
               lw=0.5, label=cats[ci])
        left += vals[:, ci]
    for yi, tot in zip(y, left):
        d.text(tot + 15, yi, f"{tot:,.0f}", va="center", fontsize=7)
    d.set_yticks(y, [n for n, _ in lbls])
    d.invert_yaxis()
    d.set_xlim(0, left.max() * 1.2)
    d.set_xlabel("Cost excluding buses (kCAD/yr)")
    d.legend(loc="upper center", bbox_to_anchor=(0.45, -0.2), ncols=1)
    panel(d, "b", x=-0.08)
    save(fig, "fig4_frontier")


# ------------------------------------------------------------- reliability
def fig_unc():
    dd = RES["benchmarks"]["det_designday_eval"]["n_ffh"]
    series = [(LAD["D0"], f"D0, {DES[LAD['D0']]['n_ffh']} heaters", BLUE, "o"),
              ("eps_0.00", "D4, heater-free", ROSE, "s"),
              ("relmatch_eps0_r100", "Heater-free, 100 kWh reserve", GREEN, "^"),
              ("det_designday", f"Design-day, {dd} heaters", OCHRE, "D")]
    x = np.arange(len(BANDS))
    fig, (a, b) = plt.subplots(1, 2, figsize=(W2, 6.4 * CM), sharey=True,
                               gridspec_kw={"wspace": 0.08})
    for ax, key, ttl in ((a, "p_reserve_compliant", "Days above the reserve"),
                         (b, "p_trips_completed", "Days with every trip completed")):
        for d, lab, c, mk in series:
            L = REL[f"{d}|data"]
            ax.plot(x, [100 * L[w][key] for w in BANDS], color=c, marker=mk, mfc=c,
                    mec="white", mew=0.6, label=lab, alpha=0.9)
        ax.set_xticks(x, BLBL)
        ax.set_title(ttl, fontsize=8, pad=4)
        ax.set_ylim(60, 101.5)
    a.set_ylabel("Share of sampled days (%)")
    a.legend(loc="lower left")
    panel(a, "a", x=-0.06)
    panel(b, "b", x=0.02)
    save(fig, "fig5_uncertainty")


# ------------------------------------------------------------- division
def fig_division():
    dv = RES["division"]
    A, B, C, D = dv["A"], dv["B"], dv["C"], dv["D"]
    lbj = dv["coord_interval"][0] / 1e3
    cases = [("Route by\nroute", A["lb_sum"] / 1e3, A["differentiating_cost"] / 1e3,
              A["n_ffh"], A["co2_t"], MUTED),
             ("Shared\nchargers", lbj, B["obj_solver"] / 1e3, B["n_ffh"], B["co2_t"], OCHRE),
             ("Shared\npool", lbj, C["obj_solver"] / 1e3, C["n_ffh"], C["co2_t"], BLUE),
             ("Full\ncoord.", lbj, D["obj_solver"] / 1e3, D["n_ffh"], D["co2_t"], GREEN)]
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(W2, 6.8 * CM),
                                  gridspec_kw={"width_ratios": [1.3, 1, 1], "wspace": 0.4})
    x = np.arange(4)
    for i, cs in enumerate(cases):
        a.vlines(i, cs[1], cs[2], color=cs[5], lw=5, alpha=0.35)
        a.plot([i - 0.16, i + 0.16], [cs[1], cs[1]], color=cs[5], lw=1.4)
        a.plot(i, cs[2], "o", color=cs[5], ms=5.5, mec="white", mew=0.6)
    a_lb, best = cases[0][1], min(cs[2] for cs in cases[1:])
    a.annotate("", xy=(0.5, best), xytext=(0.5, a_lb),
               arrowprops=dict(arrowstyle="<->", color=ROSE, lw=0.9))
    a.text(0.58, (a_lb + best) / 2, f"$\\geq${a_lb - best:.0f}", color=INK, fontsize=7.5,
           va="center")
    a.set_xticks(x, [cs[0] for cs in cases])
    a.tick_params(axis="x", labelsize=6.8)
    a.set_xlim(-0.5, 3.5)
    lo = min(cs[1] for cs in cases)
    hi = max(cs[2] for cs in cases)
    a.set_ylim(lo - 0.08 * (hi - lo), hi + 0.08 * (hi - lo))
    a.set_ylabel("Cost (kCAD/yr)")
    a.legend(handles=[Line2D([], [], marker="o", ls="", color=MUTED, mec="white", mew=0.6,
                             ms=5.5, label="Best solution"),
                      Line2D([], [], color=MUTED, lw=1.4, label="Lower bound")],
             loc="upper right")
    panel(a, "a", x=-0.12)
    for ax, kk, lab in ((b, 3, "Heater-equipped buses"), (c, 4, "Onboard emissions (t CO$_2$/yr)")):
        vals = [cs[kk] for cs in cases]
        ax.bar(x, vals, 0.66, color=[cs[5] for cs in cases], edgecolor="white", lw=0.5)
        for i, v in enumerate(vals):
            ax.text(i, v * 1.02, f"{v:.0f}", ha="center", va="bottom", fontsize=7)
        ax.set_xticks(x, [cs[0] for cs in cases])
        ax.tick_params(axis="x", labelsize=6.3)
        ax.set_ylabel(lab)
        ax.set_ylim(0, max(vals) * 1.18)
    panel(b, "b", x=-0.16)
    panel(c, "c", x=-0.16)
    save(fig, "fig_division")


# ------------------------------------------------------------- routes
def fig_routes():
    per = RES["division"]["per_route"]
    D = RES["division"]["D"]
    routes = sorted(per, key=lambda r: (per[r]["n_ffh"] / max(1, per[r]["n_buses"]),
                                        per[r]["n_buses"]))
    share = [100 * per[r]["n_ffh"] / max(1, per[r]["n_buses"]) for r in routes]
    pool = 100 * D["n_ffh"] / D["n_buses"]
    fig, ax = plt.subplots(figsize=(W1, 7.8 * CM))
    y = np.arange(len(routes))
    ax.grid(axis="y", visible=False)
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.barh(y, share, 0.66, color=[INK if r == "52" else OCHRE for r in routes],
            edgecolor="white", lw=0.5)
    for yi, r, s in zip(y, routes, share):
        ax.text(s + 1.2, yi, f"{per[r]['n_ffh']} of {per[r]['n_buses']}", va="center",
                fontsize=6.8, color=MUTED, zorder=4,
                bbox=dict(fc="white", ec="none", pad=0.8))
    ax.axvline(pool, color=BLUE, lw=1.2, ls=(0, (3, 2)))
    ax.text(pool + 1.2, len(routes) - 0.2, f"Full coordination: {D['n_ffh']} of "
            f"{D['n_buses']} ({pool:.0f}%)", fontsize=7, color=BLUE, va="bottom")
    ax.set_yticks(y, [f"Route {r}" for r in routes])
    ax.set_ylim(-0.6, len(routes) + 0.5)
    ax.set_xlabel("Heater-equipped buses when the route is planned alone (%)")
    ax.set_xlim(0, 118)
    ax.set_xticks([0, 25, 50, 75, 100])
    save(fig, "figS_routes")


# ------------------------------------------------------------- severe day (v11b)
def fig_sevday():
    D = load_b("fig_severe_day_data_tighten_v11.json")
    d0, d4 = D["designs"]["econ_lam0"], D["designs"]["eps_0.00"]   # D0 and D4 equipment
    t0 = D["steps_h"][0] - 0.125
    fig, (a, b) = plt.subplots(1, 2, figsize=(W2, 6.6 * CM), gridspec_kw={"wspace": 0.26})
    a.plot(d0["soc_h"], d0["soc_kWh"], color=BLUE, lw=1.3, label="D0")
    a.plot(d4["soc_h"], d4["soc_kWh"], color=ROSE, lw=1.3, label="D4")
    a.axhline(d0["floor_kWh"], color=MUTED, lw=0.8, ls=(0, (2, 2)))
    a.text(t0 + 0.4, d0["floor_kWh"] + 8, "State-of-charge floor", fontsize=6.8, color=MUTED)
    a.set_xlim(t0, t0 + 24)
    a.set_ylim(0, 1.08 * max(max(d0["soc_kWh"]), max(d4["soc_kWh"])))
    hours(a, t0, 4)
    a.set_xlabel("Hour of day")
    a.set_ylabel("Battery energy of one block (kWh)")
    a.legend(loc="lower left", bbox_to_anchor=(0.0, 0.16), ncols=2)
    panel(a, "a")
    hrs = D["steps_h"]
    b.step(hrs, d0["depot_kW"], where="mid", color=BLUE, lw=1.2, label="D0 depot")
    b.step(hrs, d4["depot_kW"], where="mid", color=ROSE, lw=1.2, label="D4 depot")
    b.step(hrs, d4["terminal_kW"], where="mid", color=ROSE, lw=1.0, ls=(0, (3, 2)),
           label="D4 terminals")
    b.set_xlim(t0, t0 + 24)
    hours(b, t0, 4)
    b.set_xlabel("Hour of day")
    b.set_ylabel("Site load (kW)")
    b.set_ylim(0, 1.32 * max(max(d0["depot_kW"]), max(d4["depot_kW"]), max(d4["terminal_kW"])))
    b.legend(loc="upper center", ncols=3, columnspacing=0.9, handlelength=1.4)
    panel(b, "b")
    save(fig, "fig_severe_day")


# ------------------------------------------------------------- depot load and price (v11b)
def fig_price():
    D = load_b("figdata_price_tighten_v11.json")
    t0 = D["t0_h"]
    hrs = np.array(D["hours"])
    clock = np.where(hrs < t0 - 1e-9, hrs + 24, hrs)
    fig, (a, b) = plt.subplots(2, 1, figsize=(W1, 7.6 * CM), sharex=True,
                               gridspec_kw={"height_ratios": [2.2, 1], "hspace": 0.22})
    des = D["designs"]
    top = 0.0
    for lb, w, col, ls, lab in (("econ_lam0", "mild", BLUE, (0, (3, 2)), "D0, mild day"),
                                ("econ_lam0", "severe", BLUE, "-", "D0, severe day"),
                                ("eps_0.00", "severe", ROSE, "-", "D4, severe day")):
        y = np.array(des[lb]["scen"][w]["depot_kW"])
        top = max(top, y.max())
        a.step(clock, y, where="mid", color=col, ls=ls, lw=1.3, label=lab)
    a.set_ylabel("Depot load (kW)")
    a.set_ylim(0, top * 1.42)
    a.legend(loc="upper left", ncols=3)
    panel(a, "a")
    pr = np.array(D["price"]["mild"]) * 100
    b.step(clock, pr, where="mid", color=MUTED, lw=1.1)
    b.set_ylabel("Price (¢/kWh)")
    b.set_ylim(np.floor(pr.min()) - 0.5, np.ceil(pr.max()) + 0.5)
    hours(b, t0, 3)
    b.set_xlabel("Hour of day")
    b.set_xlim(clock.min(), clock.max())
    panel(b, "b")
    save(fig, "fig_price")


if __name__ == "__main__":
    for f in (fig_weather, fig_ops, fig_robust, fig_frontier, fig_unc, fig_sevday,
              fig_routes, fig_division, fig_price):
        f()
