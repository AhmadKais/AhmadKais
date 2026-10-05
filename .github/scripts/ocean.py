"""Generate an animated ocean SVG: a whale swims through a GitHub contribution
graph and eats every day that has contributions, like krill.

Usage: GITHUB_TOKEN=... python ocean.py <username> <out_dir>
Writes <out_dir>/ocean.svg.
"""
import json
import os
import random
import sys
import urllib.request

CELL, GAP = 11, 3
PITCH = CELL + GAP
GRID_X, GRID_Y = 20, 52      # top-left of the grid (room for waves above)
FLOOR_H = 34                 # sea floor strip below the grid
SPEED = 120.0                # px per second while swimming
EAT_TIME = 0.35              # seconds for the krill-burst ring
END_PAUSE = 1.5              # seconds before the loop restarts
MOUTH = 22                   # distance from whale centre to its mouth

EMPTY = "#ffffff12"
LEVELS = [EMPTY, "#0f5e7a", "#1690b3", "#2cc4e0", "#8ef0ff"]
LEVEL_INDEX = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2,
               "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}


def fetch_days(user, token):
    query = """query($login:String!){user(login:$login){contributionsCollection{
      contributionCalendar{weeks{contributionDays{weekday contributionLevel}}}}}}"""
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": query, "variables": {"login": user}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        weeks = json.load(resp)["data"]["user"]["contributionsCollection"][
            "contributionCalendar"]["weeks"]
    return [(x, d["weekday"], LEVEL_INDEX[d["contributionLevel"]])
            for x, w in enumerate(weeks) for d in w["contributionDays"]]


def center(x, y):
    return GRID_X + x * PITCH + CELL / 2, GRID_Y + y * PITCH + CELL / 2


def swim_order(targets):
    """Column by column, snaking up and down, so the whale always heads right."""
    order = []
    for i, x in enumerate(sorted({c[0] for c in targets})):
        col = sorted((c for c in targets if c[0] == x), key=lambda c: c[1], reverse=i % 2 == 1)
        order += col
    return order


WHALE = """<g id="whale">
  <g class="tail">
    <path d="M-15 0 Q-22 -2 -27 -9 Q-24 -2 -26 0 Q-24 2 -27 9 Q-22 2 -15 0 Z" fill="#3a7bd5"/>
  </g>
  <path d="M-17 0 C-12 -9 6 -11 14 -6 C19 -3 20 2 17 5 C10 10 -8 9 -17 0 Z" fill="#3a7bd5"/>
  <path d="M-12 3 C-4 8 10 8 17 4 C12 9 -4 10 -12 3 Z" fill="#cfe9ff"/>
  <path d="M-2 4 Q2 10 -5 11 Q-3 7 -6 5 Z" fill="#2f66b3"/>
  <circle cx="10" cy="-1.5" r="1.3" fill="#0b1f33"/>
  <circle cx="10.4" cy="-1.9" r="0.4" fill="#fff"/>
</g>"""


def build(days, seed=7):
    rnd = random.Random(seed)
    weeks = max(d[0] for d in days) + 1
    grid_w = weeks * PITCH - GAP
    width = GRID_X * 2 + grid_w
    floor_y = GRID_Y + 7 * PITCH - GAP + 10
    height = floor_y + FLOOR_H

    targets = [(x, y) for x, y, lvl in days if lvl > 0] or [(x, 3) for x in range(0, weeks, 4)]
    order = swim_order(targets)

    mid_y = GRID_Y + 3 * PITCH + CELL / 2
    pts = [(-40.0, mid_y)] + [(cx - MOUTH, cy) for cx, cy in (center(*c) for c in order)]
    pts.append((width + 40.0, mid_y))
    seg = [((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2) ** 0.5 for a, b in zip(pts, pts[1:])]
    swim_time = sum(seg) / SPEED
    total = swim_time + END_PAUSE

    times, acc = [0.0], 0.0
    for s in seg:
        acc += s
        times.append(acc / SPEED)
    eaten_at = {c: times[i + 1] for i, c in enumerate(order)}

    def kt(v):
        return f"{min(max(v / total, 0), 1):.5f}"

    dur = f'dur="{total:.2f}s" repeatCount="indefinite"'

    cells, bursts = [], []
    for x, y, lvl in days:
        px, py = GRID_X + x * PITCH, GRID_Y + y * PITCH
        anim = ""
        if (x, y) in eaten_at and lvl > 0:
            e = eaten_at[(x, y)]
            anim = (f'<animate attributeName="fill" {dur} calcMode="discrete" '
                    f'values="{LEVELS[lvl]};{EMPTY}" keyTimes="0;{kt(e)}"/>')
            cx, cy = center(x, y)
            bursts.append(
                f'<circle cx="{cx}" cy="{cy}" r="0" fill="none" stroke="#8ef0ff" stroke-width="1.2">'
                f'<animate attributeName="r" {dur} values="0;0;9;9" '
                f'keyTimes="0;{kt(e)};{kt(e + EAT_TIME)};1"/>'
                f'<animate attributeName="opacity" {dur} values="0;1;0;0" '
                f'keyTimes="0;{kt(e)};{kt(e + EAT_TIME)};1"/></circle>')
        cells.append(f'<rect x="{px}" y="{py}" width="{CELL}" height="{CELL}" rx="2.5" '
                     f'fill="{LEVELS[lvl]}">{anim}</rect>')

    # waves: a repeating crest pattern slid sideways forever
    def wave(y, amp, period, color, secs, reverse=False):
        d = f"M{-period} {y}"
        x = -period
        while x < width + period:
            d += f" q{period/4} {-amp} {period/2} 0 t{period/2} 0"
            x += period
        d += f" V0 H{-period} Z"
        direction = "reverse" if reverse else "normal"
        return (f'<path d="{d}" fill="{color}" style="animation: drift {secs}s linear infinite {direction};'
                f' --p: {-period}px"/>')

    waves = (wave(26, 6, 80, "#1b4f8a66", 6, True) + wave(30, 5, 60, "#2a6db599", 4)
             + wave(34, 4, 46, "#3d8bd4cc", 3))

    rays = "".join(
        f'<polygon points="{x},0 {x + 34},0 {x + 90},{height} {x + 30},{height}" fill="#9fdcff" '
        f'style="animation: shimmer {rnd.uniform(4, 7):.1f}s ease-in-out infinite alternate; '
        f'animation-delay: -{rnd.uniform(0, 5):.1f}s"/>'
        for x in range(40, width, 150))

    bubbles = "".join(
        f'<circle cx="{rnd.uniform(10, width - 10):.0f}" cy="{floor_y}" r="{rnd.uniform(1.2, 3.2):.1f}" '
        f'fill="none" stroke="#bfefff" stroke-width="0.8" style="animation: rise '
        f'{rnd.uniform(5, 10):.1f}s linear infinite; animation-delay: -{rnd.uniform(0, 10):.1f}s"/>'
        for _ in range(28))

    weeds = []
    for x in range(14, width, 46):
        x += rnd.randint(-10, 10)
        h = rnd.randint(16, 30)
        weeds.append(
            f'<path d="M{x} {height} q-6 {-h/3} 0 {-h*2/3} t0 {-h/3}" fill="none" '
            f'stroke="{rnd.choice(["#1f8a5b", "#2fa36b", "#17734b"])}" stroke-width="3" stroke-linecap="round" '
            f'style="transform-origin: {x}px {height}px; animation: sway {rnd.uniform(2.5, 4):.1f}s '
            f'ease-in-out infinite alternate; animation-delay: -{rnd.uniform(0, 3):.1f}s"/>')

    path_d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    key_points = ";".join(f"{sum(seg[:i]) / sum(seg):.5f}" for i in range(len(pts))) + ";1"
    key_times = ";".join(kt(v) for v in times) + ";1"

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
<style>
  @keyframes drift {{ to {{ transform: translateX(var(--p)); }} }}
  @keyframes rise {{ 0% {{ transform: translateY(0); opacity: 0; }} 10% {{ opacity: .9; }}
                     90% {{ opacity: .6; }} 100% {{ transform: translateY(-{floor_y - 28}px); opacity: 0; }} }}
  @keyframes sway {{ from {{ transform: rotate(-7deg); }} to {{ transform: rotate(7deg); }} }}
  @keyframes shimmer {{ from {{ opacity: .02; }} to {{ opacity: .09; }} }}
  @keyframes wag {{ from {{ transform: rotate(-12deg); }} to {{ transform: rotate(12deg); }} }}
  @keyframes bob {{ from {{ transform: translateY(-1.5px); }} to {{ transform: translateY(1.5px); }} }}
  .tail {{ transform-origin: -15px 0; animation: wag .6s ease-in-out infinite alternate; }}
  .body {{ animation: bob 1.2s ease-in-out infinite alternate; }}
</style>
<defs>
  <linearGradient id="sea" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#0b3a66"/><stop offset=".55" stop-color="#072a4d"/>
    <stop offset="1" stop-color="#03152b"/>
  </linearGradient>
  {WHALE}
</defs>
<rect width="{width}" height="{height}" rx="10" fill="url(#sea)"/>
{rays}
{waves}
{''.join(cells)}
{''.join(bursts)}
{bubbles}
<path d="M0 {height} V{floor_y + 18} q{width/8} -10 {width/4} 0 t{width/4} 0 t{width/4} 0 t{width/4} 0 V{height} Z" fill="#0d2238"/>
{''.join(weeds)}
<g>
  <animateMotion {dur} calcMode="linear" path="{path_d}" keyPoints="{key_points}" keyTimes="{key_times}"/>
  <g class="body"><use href="#whale" transform="scale(1.5)"/></g>
</g>
</svg>
"""


def main():
    user, out = sys.argv[1], sys.argv[2]
    days = fetch_days(user, os.environ["GITHUB_TOKEN"])
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "ocean.svg"), "w") as f:
        f.write(build(days))


if __name__ == "__main__":
    main()
