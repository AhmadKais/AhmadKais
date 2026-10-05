"""Generate an animated SVG of a spider crawling over a GitHub contribution graph,
eating every day that has contributions.

Usage: GITHUB_TOKEN=... python spider.py <username> <out_dir>
Writes <out_dir>/spider-dark.svg and <out_dir>/spider-light.svg.
"""
import json
import math
import os
import sys
import urllib.request

CELL, GAP, PAD = 11, 3, 18
PITCH = CELL + GAP
SPEED = 200.0      # px per second while crawling
DROP_TIME = 1.6    # seconds to descend on the silk thread
EAT_TIME = 0.25    # seconds for a square to be eaten
END_PAUSE = 2.5    # seconds to rest before the loop restarts

THEMES = {
    "dark": {
        "levels": ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"],
        "spider": "#e6edf3", "eye": "#ff4d4d", "thread": "#8b949e",
    },
    "light": {
        "levels": ["#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "spider": "#1f2328", "eye": "#d1242f", "thread": "#8c959f",
    },
}
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
    return PAD + x * PITCH + CELL / 2, PAD + y * PITCH + CELL / 2


def tour(targets, start):
    """Nearest-neighbour walk over the cells to eat."""
    left, path, cur = set(targets), [], start
    while left:
        nxt = min(left, key=lambda c: (math.dist(center(*cur), center(*c)), c))
        left.remove(nxt)
        path.append(nxt)
        cur = nxt
    return path


def spider_shape(t):
    legs = []
    for side in (-1, 1):
        for i, (ax, kx, fx) in enumerate([(3, 7, 10), (1, 4, 6), (-1, -3, -5), (-3, -7, -10)]):
            phase = "a" if (i + (side > 0)) % 2 else "b"
            legs.append(
                f'<path class="leg {phase}" style="transform-origin:{ax}px {side*2}px" d="M{ax} {side*2} L{kx} {side*7} L{fx} {side*11}"/>')
    return f"""<g id="spider" transform="scale(1.3)">
  <g fill="none" stroke="{t['spider']}" stroke-width="1.3" stroke-linecap="round">{''.join(legs)}</g>
  <ellipse cx="-4" cy="0" rx="5.5" ry="4.5" fill="{t['spider']}"/>
  <circle cx="3" cy="0" r="3.2" fill="{t['spider']}"/>
  <circle cx="4.6" cy="-1.3" r="0.9" fill="{t['eye']}"/>
  <circle cx="4.6" cy="1.3" r="0.9" fill="{t['eye']}"/>
</g>"""


def build(days, t):
    weeks = max(d[0] for d in days) + 1
    width, height = PAD * 2 + weeks * PITCH - GAP, PAD * 2 + 7 * PITCH - GAP
    targets = [(x, y) for x, y, lvl in days if lvl > 0]
    if not targets:  # nothing to eat: wander the diagonal instead
        targets = [(x, x % 7) for x in range(0, weeks, 3)]

    start = (0, 0)
    order = tour(targets, start)
    sx, sy = center(*start)
    pts = [(sx, -14), (sx, sy)] + [center(*c) for c in order]
    seg = [math.dist(a, b) for a, b in zip(pts, pts[1:])]
    crawl_len = sum(seg[1:]) or 1.0
    crawl_time = crawl_len / SPEED
    total = DROP_TIME + crawl_time + END_PAUSE

    # time at which the spider reaches each point
    times, acc = [0.0, DROP_TIME], 0.0
    for s in seg[1:]:
        acc += s
        times.append(DROP_TIME + acc / SPEED)
    eaten_at = {c: times[i + 2] for i, c in enumerate(order)}

    def kt(v):
        return f"{min(max(v / total, 0), 1):.5f}"

    cells = []
    for x, y, lvl in days:
        cx, cy = PAD + x * PITCH, PAD + y * PITCH
        color = t["levels"][lvl]
        anim = ""
        if (x, y) in eaten_at and lvl > 0:
            e = eaten_at[(x, y)]
            anim = (f'<animate attributeName="fill" dur="{total:.2f}s" repeatCount="indefinite" '
                    f'calcMode="discrete" values="{color};{t["levels"][0]}" '
                    f'keyTimes="0;{kt(e + EAT_TIME / 2)}"/>')
        cells.append(f'<rect x="{cx}" y="{cy}" width="{CELL}" height="{CELL}" rx="2" '
                     f'fill="{color}">{anim}</rect>')

    path_d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    key_points = ";".join(f"{(sum(seg[:i]) / sum(seg)):.5f}" for i in range(len(pts))) + ";1"
    key_times = ";".join(kt(v) for v in times) + ";1"

    # silk thread: grows during the drop, then fades out
    thread = (f'<line x1="{sx}" y1="0" x2="{sx}" y2="0" stroke="{t["thread"]}" stroke-width="0.8">'
              f'<animate attributeName="y2" dur="{total:.2f}s" repeatCount="indefinite" '
              f'values="0;{sy};{sy};{sy}" keyTimes="0;{kt(DROP_TIME)};{kt(DROP_TIME + 0.6)};1"/>'
              f'<animate attributeName="opacity" dur="{total:.2f}s" repeatCount="indefinite" '
              f'values="1;1;0;0" keyTimes="0;{kt(DROP_TIME)};{kt(DROP_TIME + 0.6)};1"/></line>')

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">
<style>
  .leg {{ animation: walk .28s ease-in-out infinite alternate; }}
  .leg.b {{ animation-delay: -.14s; }}
  @keyframes walk {{ from {{ transform: rotate(-9deg); }} to {{ transform: rotate(9deg); }} }}
</style>
<defs>{spider_shape(t)}</defs>
{''.join(cells)}
{thread}
<use href="#spider">
  <animateMotion dur="{total:.2f}s" repeatCount="indefinite" rotate="auto" calcMode="linear"
    path="{path_d}" keyPoints="{key_points}" keyTimes="{key_times}"/>
</use>
</svg>
"""


def main():
    user, out = sys.argv[1], sys.argv[2]
    days = fetch_days(user, os.environ["GITHUB_TOKEN"])
    os.makedirs(out, exist_ok=True)
    for name, theme in THEMES.items():
        with open(os.path.join(out, f"spider-{name}.svg"), "w") as f:
            f.write(build(days, theme))


if __name__ == "__main__":
    main()
