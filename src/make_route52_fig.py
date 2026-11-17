"""Route 52 schematic (Fig. 2 of the paper): writes route-52.svg and route52.html.

Topology from the TTC GTFS feed S1000544, weekday service:
  52A Lawrence Stn - Pearson Airport (via Dixon Rd)
  52B Lawrence Stn - Westwood Square (via Dixon Rd)
  52F Sunnybrook Hospital (Raab Blvd) - The Westway at Royal York
  52G Lawrence West Stn - Martin Grove (via The Westway)
Candidate charging sites (Section 4.1): Lawrence Stn, Westwood Square,
Lawrence West Stn, Pearson Airport, The Westway at Royal York, Raab Blvd.
"""
import os
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else os.path.dirname(os.path.abspath(__file__))

BLUE, GREEN, ORANGE, PURPLE = "#0659D2", "#068A19", "#F85F03", "#7B2FBE"
RED, GREY, INK = "#F20F0E", "#6F6F6F", "#000000"
FONT = "'Open Sans','Helvetica Neue',Helvetica,Arial,sans-serif"
W, H = 800, 414

# levels and stops
YT, YU, YG, YD = 307, 262, 209, 352          # trunk, Dixon, Westwood, Westway
XS, XL, XLW = 725, 620, 500                   # Sunnybrook, Lawrence, Lawrence West
XK, XR = 300, 300                             # Dixon fork, Royal York
XP, XW, XM = 150, 95, 150                     # Pearson, Westwood, Martin Grove

out = []
add = out.append


def line(d, color):
    add(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="8" '
        f'stroke-linecap="butt" stroke-linejoin="round"/>')
    add(f'<path d="{d}" fill="none" stroke="#FFFFFF" stroke-width="2.4" '
        f'stroke-linejoin="round"/>')


def chevrons(xs, y, color):
    for x in xs:
        add(f'<rect x="{x-7}" y="{y-2}" width="14" height="4" fill="{color}"/>')
        for dx in (-4, 1):
            add(f'<polyline points="{x+dx},{y-3.2} {x+dx+3.4},{y} {x+dx},{y+3.2}" '
                f'fill="none" stroke="#FFFFFF" stroke-width="1.5"/>')


def stop(x, y):
    add(f'<circle cx="{x}" cy="{y}" r="9" fill="#FFFFFF" stroke="{INK}" stroke-width="1.8"/>')


def text(x, y, s, size=13, weight=700, fill=INK, anchor="middle"):
    add(f'<text x="{x}" y="{y}" font-family="{FONT}" font-size="{size}" '
        f'font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{s}</text>')


def charger(x, y, k=1.0):
    """Charging-station pictogram centred at (x, y)."""
    add(f'<g transform="translate({x},{y}) scale({k})" fill="none" stroke="{INK}" '
        f'stroke-width="1.3" stroke-linejoin="round" stroke-linecap="round">'
        '<rect x="-8" y="-10" width="11" height="19" rx="1.2" fill="#FFFFFF"/>'
        '<rect x="-6" y="-8" width="7" height="5"/>'
        '<path d="M-10,9.6 H5"/>'
        f'<path d="M-1.6,-1 L-4.2,3.4 H-1.6 L-3,7 L0.2,2.2 H-2.2 Z" fill="{INK}" stroke-width="0.6"/>'
        '<path d="M3,3 H5.2 V6.2 a1.9,1.9 0 0 0 3.8,0 V-2.6"/>'
        '<path d="M6.8,-2.6 h4.4 v2.2 a2.2,2.2 0 0 1 -4.4,0 Z" fill="#FFFFFF"/>'
        '<path d="M7.9,-2.6 v-2.6 M10.1,-2.6 v-2.6"/>'
        '</g>')


def badge(x, y, color):
    add(f'<circle cx="{x}" cy="{y}" r="14" fill="#FFFFFF" stroke="{color}" stroke-width="1.8"/>')


def icon_plane(x, y, c):
    badge(x, y, c)
    add(f'<path transform="translate({x},{y}) rotate(45)" fill="{c}" d="M0,-10 C1.3,-10 1.7,-8 1.7,-6.5 '
        'V-2.6 L9.5,2.6 V4.6 L1.7,2.2 V6.2 L4,8 V9.6 L0,8.6 L-4,9.6 V8 L-1.7,6.2 V2.2 '
        'L-9.5,4.6 V2.6 L-1.7,-2.6 V-6.5 C-1.7,-8 -1.3,-10 0,-10 Z"/>')


def icon_building(x, y, c):
    badge(x, y, c)
    add(f'<g transform="translate({x},{y})" fill="{c}">'
        '<path d="M-8,8 V-2 H-3 V-7 H3 V-2 H8 V8 Z"/>'
        '<g fill="#FFFFFF"><rect x="-1.2" y="-5" width="2.4" height="2.2"/>'
        '<rect x="-6" y="0" width="2.2" height="2"/><rect x="-1.1" y="0" width="2.2" height="2"/>'
        '<rect x="3.8" y="0" width="2.2" height="2"/><rect x="-6" y="3.6" width="2.2" height="2"/>'
        '<rect x="3.8" y="3.6" width="2.2" height="2"/><rect x="-1.3" y="4" width="2.6" height="4"/></g></g>')


def icon_tree(x, y, c):
    badge(x, y, c)
    add(f'<g transform="translate({x},{y})" fill="{c}">'
        '<circle cx="0" cy="-3.6" r="4.6"/><circle cx="-4" cy="0.2" r="3.9"/>'
        '<circle cx="4" cy="0.2" r="3.9"/><rect x="-1.2" y="1" width="2.4" height="8"/></g>')


def icon_hospital(x, y, c):
    badge(x, y, c)
    add(f'<g transform="translate({x},{y})" fill="{c}">'
        '<rect x="-2.6" y="-8" width="5.2" height="16"/><rect x="-8" y="-2.6" width="16" height="5.2"/></g>')


def icon_depot(x, y):
    add(f'<circle cx="{x}" cy="{y}" r="22" fill="#FFFFFF" stroke="{GREY}" stroke-width="2.2"/>')
    add(f'<g transform="translate({x},{y})" fill="{GREY}">'
        '<path d="M-14,11 V-3 L0,-12 L14,-3 V11 H9.5 V-1 H-9.5 V11 Z"/>'
        '<rect x="-2" y="-8.6" width="4" height="3" fill="#FFFFFF"/>'
        '<rect x="-7" y="1.4" width="14" height="9" rx="1.6"/>'
        '<rect x="-5.4" y="3" width="10.8" height="3.4" fill="#FFFFFF"/>'
        '<circle cx="-4" cy="8.4" r="0.9" fill="#FFFFFF"/><circle cx="4" cy="8.4" r="0.9" fill="#FFFFFF"/>'
        '<rect x="-6" y="10.4" width="2.6" height="1.8"/><rect x="3.4" y="10.4" width="2.6" height="1.8"/></g>')


add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
    f'role="img" aria-labelledby="t d">')
add('<title id="t">TTC Route 52 and its candidate charging sites</title>')
add('<desc id="d">Schematic of the four branches of TTC Route 52 (52A, 52B, 52F, 52G), '
    'the Arrow Road depot, and the six terminals that are candidate opportunity-charging sites.</desc>')
add(f'<rect width="{W}" height="{H}" fill="#FFFFFF"/>')

# ---- deadhead (under the lines) ----
add(f'<path d="M{XLW},187 V{YT-9}" stroke="{GREY}" stroke-width="3.4" stroke-dasharray="8 6" fill="none"/>')

# ---- exclusive sections ----
line(f"M{XL},{YT} H{XS}", PURPLE)                                              # 52F east
line(f"M{XK},{YU} H{XP}", BLUE)                                                # 52A
line(f"M{XK+6},{YU} H{XK-6} Q{XK-18},{YU} {XK-24},{YU-10} L{XK-45},{YG+10} "
     f"Q{XK-51},{YG} {XK-63},{YG} H{XW}", GREEN)                                # 52B
line(f"M{XR},{YD} H{XM}", ORANGE)                                              # 52G
# ---- shared sections (on top) ----
J = 420
fork_up = (f"M{XLW},{YT} H{J} Q{J-12},{YT} {J-18},{YT-10} L{J-33},{YU+10} "
           f"Q{J-39},{YU} {J-51},{YU} H{XK}")
fork_dn = (f"M{J+6},{YT} H{J} Q{J-12},{YT} {J-18},{YT+10} L{J-33},{YD-10} "
           f"Q{J-39},{YD} {J-51},{YD} H{XR}")
line(f"M{XL},{YT} H{XLW}", RED)
line(fork_dn, RED)
line(fork_up, RED)

chevrons([672], YT, PURPLE)
chevrons([560], YT, RED)
chevrons([336], YU, RED)
chevrons([336], YD, RED)
chevrons([200, 250], YU, BLUE)
chevrons([140, 195], YG, GREEN)
chevrons([200, 250], YD, ORANGE)

# ---- stops ----
for x, y in [(XS, YT), (XL, YT), (XLW, YT), (XP, YU), (XW, YG), (XR, YD), (XM, YD)]:
    stop(x, y)

# ---- end icons ----
icon_hospital(XS + 35, YT, PURPLE)
icon_plane(XP - 35, YU, BLUE)
icon_building(XW - 35, YG, GREEN)
icon_tree(XM - 35, YD, ORANGE)

# ---- candidate charging sites ----
for x, y in [(XS, YT), (XL, YT), (XLW, YT), (XP, YU), (XW, YG), (XR, YD)]:
    charger(x + 19, y - 26, 0.9)

# ---- branch labels ----
text(672, YT - 11, "52F", 13, 700, PURPLE)
text(225, YU - 11, "52A", 13, 700, BLUE)
text(168, YG - 11, "52B", 13, 700, GREEN)
text(225, YD - 11, "52G", 13, 700, ORANGE)

# ---- stop labels ----
text(XS + 12, YT + 31, "Sunnybrook"); text(XS + 12, YT + 48, "Hospital")
text(XL, YT + 31, "Lawrence"); text(XL, YT + 48, "Stn")
text(XLW, YT + 31, "Lawrence"); text(XLW, YT + 48, "West Stn")
text(XP - 18, YU + 31, "Pearson Airport")
text(XW - 18, YG + 31, "Westwood Square")
text(XR, YD + 31, "The Westway at"); text(XR, YD + 48, "Royal York")
text(XM - 18, YD + 31, "Martin Grove")

# ---- depot ----
icon_depot(XLW, 165)
text(XLW, 133, "Depot (Arrow Rd)", 13.5)
text(655, 118, "Depot charging", 12.5)
charger(727, 112, 1.5)
add('<defs><marker id="ah" viewBox="0 0 10 10" refX="8.5" refY="5" markerWidth="7" markerHeight="7" '
    'orient="auto-start-reverse"><path d="M0,0.8 L9,5 L0,9.2" fill="none" stroke="#000" stroke-width="1.6"/>'
    '</marker></defs>')
add(f'<path d="M600,124 L528,153" stroke="{INK}" stroke-width="1.5" fill="none" marker-end="url(#ah)"/>')

# ---- legend ----
LX, LY, LW_, LH = 14, 12, 348, 152
add(f'<rect x="{LX}" y="{LY}" width="{LW_}" height="{LH}" fill="#FFFFFF" stroke="{INK}" stroke-width="1.2"/>')
text(LX + 14, LY + 21, "Legend", 13.5, 700, INK, "start")
rows = [(BLUE, "52A branch (Pearson Airport)"), (GREEN, "52B branch (Westwood Square)"),
        (PURPLE, "52F branch (Sunnybrook Hospital–Royal York)"),
        (ORANGE, "52G branch (Martin Grove)"), (RED, "Section shared by two or more branches")]
y = LY + 40
for c, lab in rows:
    add(f'<rect x="{LX+14}" y="{y-6.5}" width="62" height="5" fill="{c}"/>')
    text(LX + 88, y, lab, 12, 400, INK, "start")
    y += 17.5
add(f'<path d="M{LX+14},{y-4} H{LX+76}" stroke="{GREY}" stroke-width="4.6" stroke-dasharray="7 5"/>')
text(LX + 88, y, "Deadhead (depot pull-out/pull-in)", 12, 400, INK, "start")
y += 17.5
charger(LX + 45, y - 4, 0.72)
text(LX + 88, y, "Candidate opportunity-charging site", 12, 400, INK, "start")
add("</svg>")

svg = "\n".join(o for o in out if o)
open(os.path.join(OUT, "route-52.svg"), "w").write(svg)

html = """<title>Route 52 Schematic</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap">
<style>
/* layout: one figure on a paper-white sheet, caption and data notes below */
:root { --bg:#eef0f3; --sheet:#ffffff; --fg:#16181d; --muted:#565c68; --rule:#d5d9e0; --accent:#0659D2;
  --font:'Open Sans','Helvetica Neue',Helvetica,Arial,sans-serif; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --bg:#14161a; --fg:#eceef2; --muted:#a6adba; --rule:#343944; --accent:#7fb0ff; color-scheme:dark } }
:root[data-theme="dark"] { --bg:#14161a; --fg:#eceef2; --muted:#a6adba; --rule:#343944; --accent:#7fb0ff; color-scheme:dark }
body { background:var(--bg); color:var(--fg); font-family:var(--font); font-size:15px; line-height:1.55;
  padding-block:28px; padding-left:max(16px, env(safe-area-inset-left, 0px)); padding-right:max(16px, env(safe-area-inset-right, 0px)); }
main { max-width:920px; margin:0 auto; display:flex; flex-direction:column; gap:18px; }
h1 { font-size:22px; font-weight:700; margin:0; text-wrap:balance; }
p { margin:0; max-width:68ch; }
.sheet { background:var(--sheet); border:1px solid var(--rule); border-radius:4px; padding:10px; overflow-x:auto; }
.sheet svg { display:block; width:100%; min-width:640px; height:auto; }
.cap { color:var(--muted); font-size:13.5px; }
table { border-collapse:collapse; font-size:13.5px; font-variant-numeric:tabular-nums; min-width:520px; }
.tw { overflow-x:auto; }
th, td { text-align:left; padding:6px 14px 6px 0; border-bottom:1px solid var(--rule); }
th { font-weight:600; color:var(--muted); }
td.n { text-align:right; }
</style>
<main>
<h1>TTC Route 52 and its candidate charging sites</h1>
<div class="sheet">__SVG__</div>
<p class="cap">Figure 2 of the paper, redrawn from the weekday service of TTC GTFS feed S1000544. The drawing is a schematic: positions follow the order of the stops from west to east, and distances are not to scale. The sheet stays white in both themes because it is the figure as printed.</p>
<div class="tw"><table>
<thead><tr><th>Branch</th><th>Termini</th><th>Trips W/E</th><th>Leg (km)</th><th>Charging candidate at</th></tr></thead>
<tbody>
<tr><td>52A</td><td>Lawrence Stn to Pearson Airport</td><td class="n">77/75</td><td class="n">21.5</td><td>both ends</td></tr>
<tr><td>52B</td><td>Lawrence Stn to Westwood Square</td><td class="n">57/54</td><td class="n">23.9</td><td>both ends</td></tr>
<tr><td>52F</td><td>Sunnybrook Hospital to The Westway at Royal York</td><td class="n">64/68</td><td class="n">14.5</td><td>both ends</td></tr>
<tr><td>52G</td><td>Lawrence West Stn to Martin Grove</td><td class="n">67/64</td><td class="n">11.9</td><td>Lawrence West Stn only</td></tr>
</tbody></table></div>
<p class="cap">Martin Grove has less than 5.0 bus-hours of layover per weekday, so it is not a candidate site. The Sunnybrook Hospital terminal is the stop at Raab Boulevard and Hospital Road.</p>
</main>
"""
open(os.path.join(OUT, "route52.html"), "w").write(html.replace("__SVG__", svg))
print("ok")
