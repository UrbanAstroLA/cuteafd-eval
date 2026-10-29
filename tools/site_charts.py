#!/usr/bin/env python3
"""Chart grammar of the results site (imported by tools/build_site.py). Static SVG, standard library only.

One grammar wherever a difference is shown:
  difference (forest) chart   one row per thing compared; x = difference from a named reference (a solid line,
                              labelled); a shaded band around it = the reference's own run-to-run spread where the data
                              has it; point + 95% interval, solid when the interval excludes the reference, light and
                              dashed when it does not; direction words at both ends of the axis; the value and its
                              interval in a text column on the right, so nothing is colour-only.
  settings map                x = cost (time to first token, % change against CuteAFD as shipped), y = remaining
                              difference from the vLLM fork on the most sensitive slice; dashed lines at the vLLM fork
                              and at CuteAFD as shipped.
  tails and position          exceedance curve (share of positions above a KL, log-log), KL by history (profile lines),
                              concentration strip (share of the total KL carried by the top 1/5/10% of positions).
Encoding, fixed: vLLM fork = blue circle, CuteAFD = orange triangle; a hollow triangle = a CuteAFD setting that does not
fit a serving launch on two RTX PRO 6000s with that checkpoint (its precision comes from a scoring launch). Colours come
from CSS variables, so the light and dark palettes follow prefers-color-scheme. Hover text is a native <title> per mark;
every figure carries a table view.
"""
import html, math

E = html.escape
MINUS = "−"


def sg(x, nd=4):
    """Signed number with a typographic minus; a non-zero value that would print as 0 gets one more decimal."""
    if x == 0: return "0"
    while abs(x) < 0.5 * 10 ** -nd and nd < 7: nd += 1
    s = f"{x:+.{nd}f}"
    return s.replace("-", MINUS)


def ci_txt(lo, hi, nd=4):
    return f"[{sg(lo, nd)}, {sg(hi, nd)}]"


def rx(x, nd=2):
    return f"{x:.{nd}f}x"


def tw(s, px=6.4):
    """Rough text width at the chart font size (12.5px system-ui)."""
    return len(str(s)) * px


def tx(x, y, s, cls="", anchor="start"):
    c = f' class="{cls}"' if cls else ""
    return f'<text{c} x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}">{E(str(s))}</text>'


def svg_open(W, H, label):
    return f'<svg viewBox="0 0 {W:.0f} {H:.0f}" role="img" aria-label="{E(label)}">'


def marker(x, y, who, hollow=False, size=4.6, cls_extra=""):
    """vLLM fork = circle (blue), CuteAFD = triangle (orange); hollow = does not fit a serving launch on 2x RTX."""
    k = ("mk-v" if who == "v" else "mk-c") + ("-o" if hollow else "") + (f" {cls_extra}" if cls_extra else "")
    if who == "v":
        return f'<circle class="{k}" cx="{x:.1f}" cy="{y:.1f}" r="{size:.1f}"/>'
    s = size * 1.25
    return (f'<path class="{k}" d="M{x:.1f},{y - s:.1f} L{x + s * 0.95:.1f},{y + s * 0.62:.1f} '
            f'L{x - s * 0.95:.1f},{y + s * 0.62:.1f} Z"/>')


def tip(title, inner):
    return f"<g><title>{E(title)}</title>{inner}</g>"


# ------------------------------------------------------------------ scales and ticks

def nice_step(span, n=5):
    raw = span / max(n, 1)
    mag = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag: return m * mag
    return 10 * mag


def lin_domain(vals, pad=0.06, n=5):
    a, b = min(vals), max(vals)
    if a == b: a, b = a - 1e-3, b + 1e-3
    span = b - a; a -= span * pad; b += span * pad
    st = nice_step(b - a, n)
    a2, b2 = math.floor(a / st) * st, math.ceil(b / st) * st
    ticks, t = [], a2
    while t <= b2 + st * 1e-6:
        ticks.append(round(t, 10)); t += st
    return a2, b2, ticks, st


LOG_TICKS = [0.25, 0.33, 0.5, 0.67, 0.8, 0.9, 1.0, 1.1, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 4.0, 6.0]
LOG_PRI = {1.0: 0, 0.5: 1, 2.0: 1, 4.0: 1, 0.25: 1, 0.8: 2, 1.25: 2, 1.5: 2, 0.67: 2, 3.0: 2, 0.33: 3, 6.0: 3,
           0.9: 3, 1.1: 3, 1.75: 4, 2.5: 4}


def log_domain(vals, pad=0.05):
    a, b = math.log(min(vals)), math.log(max(vals))
    span = max(b - a, math.log(1.3)); a -= span * pad; b += span * pad
    lo, hi = math.exp(a), math.exp(b)
    ticks = [t for t in LOG_TICKS if lo <= t <= hi]
    for lvl in (4, 3, 2):
        if len(ticks) > 7: ticks = [t for t in ticks if LOG_PRI[t] < lvl]
    return lo, hi, ticks


def fmt_tick(v, kind, step=None):
    if kind == "log": return f"{v:g}x"
    if kind == "pct": return "0" if abs(v) < 1e-12 else f"{v:+.0f}%".replace("-", MINUS)
    if abs(v) < 1e-12: return "0"
    nd = max(0, -int(math.floor(math.log10(step)))) if step else 3
    if step and abs(step * 10 ** nd - round(step * 10 ** nd)) > 1e-9: nd += 1
    return sg(v, nd)


# ------------------------------------------------------------------ difference (forest) chart

def forest(rows, *, ref, ref_who, scale="lin", left, right, aria, W=640, label_w=196, value_w=170, unit_fmt=None):
    """rows: dicts {label, sub, est, lo, hi, band (lo, hi) in data units, who 'v'|'c', hollow, resolved, value, title,
    dots [(value, title, resolved)], muted} or {section: text}. scale 'lin' (reference 0) or 'log' (reference 1).
    resolved: None -> from the interval (excludes the reference); True/False to force (e.g. a published reading)."""
    r0 = 1.0 if scale == "log" else 0.0
    vals = [r0]
    for r in rows:
        if "section" in r: continue
        for k in ("est", "lo", "hi"):
            if r.get(k) is not None: vals.append(r[k])
        if r.get("band"): vals += list(r["band"])
        vals += [d[0] for d in r.get("dots", [])]
    if scale == "log":
        d0, d1, ticks = log_domain(vals); step = None
        T = lambda v: math.log(v)
    else:
        d0, d1, ticks, step = lin_domain(vals)
        T = lambda v: v
    PL, PR = label_w + 8, W - value_w - 6
    X = lambda v: PL + (PR - PL) * (T(v) - T(d0)) / (T(d1) - T(d0))
    y = 30; body = []; rowpos = []
    for r in rows:
        if "section" in r:
            y += 6
            body.append(f'<rect class="secbg" x="0" y="{y - 3:.1f}" width="{tw(r["section"], 7.0) + 8:.1f}" height="18"/>'
                        + tx(2, y + 10, r["section"], "sec"))
            y += 20; continue
        h = 34 if r.get("sub") else 26
        rowpos.append((r, y + h / 2)); y += h
    yb = y + 4
    H = yb + 42
    o = [svg_open(W, H, aria)]
    for t in ticks:
        if abs(t - r0) < 1e-12: continue
        o.append(f'<line class="grid" x1="{X(t):.1f}" x2="{X(t):.1f}" y1="24" y2="{yb:.1f}"/>')
        o.append(tx(X(t), yb + 14, fmt_tick(t, scale if scale == "log" else (unit_fmt or "lin"), step), "tick", "middle"))
    o.append(tx(X(r0), yb + 14, fmt_tick(r0, scale if scale == "log" else (unit_fmt or "lin"), step), "tick", "middle"))
    o.append(tx(PL, yb + 31, "← " + left, "dir"))
    o.append(tx(PR, yb + 31, right + " →", "dir", "end"))
    for r, cy in rowpos:
        band = r.get("band")
        if band and X(band[1]) - X(band[0]) >= 0.6:
            o.append(f'<rect class="nband" x="{X(band[0]):.1f}" y="{cy - 9:.1f}" width="{X(band[1]) - X(band[0]):.1f}" height="18" rx="2"/>')
    o.append(f'<line class="ref ref-{ref_who}" x1="{X(r0):.1f}" x2="{X(r0):.1f}" y1="22" y2="{yb:.1f}"/>')
    o.append(tx(X(r0), 15, ref, "lab", "middle" if PL + 40 < X(r0) < PR - 40 else ("start" if X(r0) <= PL + 40 else "end")))
    o += body
    for r, cy in rowpos:
        g = []
        lab_y = cy + 4 if not r.get("sub") else cy - 2
        g.append(tx(label_w, lab_y, r["label"], "lab" + (" mut" if r.get("muted") else ""), "end"))
        if r.get("sub"): g.append(tx(label_w, cy + 11, r["sub"], "sub", "end"))
        g.append(f'<rect class="hit" x="0" y="{cy - 12:.1f}" width="{W}" height="24"/>')
        for v, t, res in r.get("dots", []):
            g.append(tip(t, marker(X(v), cy, r.get("who", "c"), size=3.3, cls_extra="dot" + ("" if res else " unres"))))
        lo, hi, est = r.get("lo"), r.get("hi"), r.get("est")
        res = r.get("resolved")
        if res is None and lo is not None: res = lo > r0 or hi < r0
        if lo is not None:
            g.append(f'<line class="wk wk-{r.get("who", "c")}{"" if res else " unres"}" x1="{X(lo):.1f}" x2="{X(hi):.1f}" '
                     f'y1="{cy:.1f}" y2="{cy:.1f}"/>')
        if est is not None:
            g.append(marker(X(est), cy, r.get("who", "c"), r.get("hollow", False), size=4.6 if not r.get("dots") else 5.2,
                            cls_extra="unres" if r.get("resolved") is False else ""))
        g.append(tx(PR + 12, cy + 4, r.get("value", ""), "val"))
        o.append(f'<g><title>{E(r.get("title", r["label"]))}</title>{"".join(g)}</g>')
    o.append("</svg>")
    return "".join(o)


# ------------------------------------------------------------------ settings map (decision chart)

def settings_map(points, *, aria, shipped_y, xlabel, ylabel, gutter=None, W=640, H=340):
    """points: {label, x (TTFT % change, None = speed not measured -> gutter column), y, lo, hi, hollow, title}.
    y = remaining difference from the vLLM fork; dashed lines at 0 (vLLM fork) and at shipped_y (CuteAFD as shipped)."""
    meas = [p for p in points if p.get("x") is not None]
    gut = [p for p in points if p.get("x") is None]
    L, T_, B_ = 58, 46, 52
    Rg = 214 if gut else 0
    R = W - 14 - Rg
    xv = [p["x"] for p in meas] + [0.0]
    x0, x1, xt, xs = lin_domain(xv, pad=0.25, n=5)
    yv = [0.0, shipped_y] + [p["lo"] for p in points if p.get("lo") is not None] + [p["hi"] for p in points if p.get("hi") is not None] + [p["y"] for p in points]
    y0, y1, yt, ys = lin_domain(yv, pad=0.05, n=5)
    X = lambda v: L + (R - L) * (v - x0) / (x1 - x0)
    Y = lambda v: T_ + (H - T_ - B_) * (y1 - v) / (y1 - y0)
    o = [svg_open(W, H, aria)]
    for t in yt:
        o.append(f'<line class="grid" x1="{L}" x2="{R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}"/>' + tx(L - 6, Y(t) + 4, fmt_tick(t, "lin", ys), "tick", "end"))
    for t in xt:
        o.append(f'<line class="grid" x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{T_}" y2="{H - B_}"/>' + tx(X(t), H - B_ + 15, fmt_tick(t, "pct"), "tick", "middle"))
    o.append(f'<line class="axis" x1="{L}" x2="{R}" y1="{H - B_}" y2="{H - B_}"/>')
    o.append(tx(L, H - B_ + 32, "← sooner first token", "dir") + tx(R, H - B_ + 32, "later first token →", "dir", "end"))
    o.append(tx((L + R) / 2, H - 4, xlabel, "sub", "middle"))
    o.append(tx(2, 13, ylabel, "sub"))
    o.append(tx(2, 30, "↑ further from the vLLM fork · ↓ closer", "dir"))
    xr = R + Rg if gut else R
    o.append(f'<line class="refd ref-v" x1="{L}" x2="{xr}" y1="{Y(0):.1f}" y2="{Y(0):.1f}"/>' + tx(L + 4, Y(0) - 5, "vLLM fork", "lab"))
    o.append(f'<line class="refd ref-c" x1="{L}" x2="{xr}" y1="{Y(shipped_y):.1f}" y2="{Y(shipped_y):.1f}"/>'
             + tx(L + 4, Y(shipped_y) - 5, "CuteAFD as shipped", "lab"))
    if gut:
        gx0 = R + 10
        o.append(f'<rect class="gutter" x="{gx0}" y="{T_}" width="{Rg - 12}" height="{H - T_ - B_}" rx="4"/>')
        o.append(tx(gx0 + (Rg - 12) / 2, T_ + 13, gutter or "speed not measured", "tick", "middle"))
        # two columns (serves on 2x RTX, does not), markers stepped across, labels stacked to the right of each column
        cols = [[p for p in gut if not p.get("hollow")], [p for p in gut if p.get("hollow")]]
        cx0 = gx0 + 12
        for col in cols:
            col.sort(key=lambda p: -p["y"])
            for i, p in enumerate(col): p["_x"] = cx0 + i * 14
            labx = cx0 + max(len(col) - 1, 0) * 14 + 10
            ys = []
            for p in col:
                ly = Y(p["y"]) + 4
                if ys and ly - ys[-1] < 13: ly = ys[-1] + 13
                ys.append(ly); p["_lab"] = (labx, ly)
            if col: cx0 = labx + max(tw(p["label"], 6.0) for p in col) + 16
    for p in meas: p["_x"] = X(p["x"])
    boxes = [(L, Y(0) - 16, L + 4 + tw("vLLM fork"), Y(0) - 2), (L, Y(shipped_y) - 16, L + 4 + tw("CuteAFD as shipped"), Y(shipped_y) - 2)]
    marks = []
    for p in points:
        cx, cy = p["_x"], Y(p["y"])
        res = p["lo"] > 0 or p["hi"] < 0 if p.get("lo") is not None else True
        g = [f'<rect class="hit" x="{cx - 12:.1f}" y="{min(Y(p.get("hi", p["y"])), cy - 12):.1f}" width="24" '
             f'height="{max(Y(p.get("lo", p["y"])) - Y(p.get("hi", p["y"])), 24):.1f}"/>']
        if p.get("lo") is not None:
            g.append(f'<line class="wk wk-c{"" if res else " unres"}" x1="{cx:.1f}" x2="{cx:.1f}" y1="{Y(p["lo"]):.1f}" y2="{Y(p["hi"]):.1f}"/>')
        g.append(marker(cx, cy, "c", p.get("hollow", False), 5))
        marks.append((p, cx, cy, g))
        boxes.append((cx - 7, cy - 7, cx + 7, cy + 7))
        if p.get("lo") is not None: boxes.append((cx - 2, Y(p["hi"]), cx + 2, Y(p["lo"])))
    in_gut = lambda p: p.get("x") is None
    for p, cx, cy, g in sorted(marks, key=lambda m: m[2]):
        w = tw(p["label"], 6.0); placed = None
        if in_gut(p):
            lx, ly = p["_lab"]
            g.append(f'<line class="lead" x1="{cx + 6:.1f}" x2="{lx - 3:.1f}" y1="{cy:.1f}" y2="{ly - 4:.1f}"/>' + tx(lx, ly, p["label"], "plab"))
            o.append(tip(p["title"], "".join(g))); continue
        cands = [(cx + 9, cy + 4, "start"), (cx - 9, cy + 4, "end"), (cx, cy - 10, "middle"), (cx, cy + 17, "middle"),
                 (cx + 9, cy - 9, "start"), (cx + 9, cy + 16, "start"), (cx - 9, cy - 9, "end"), (cx - 9, cy + 16, "end")]
        if in_gut(p): cands = [(cx + 8, cy + 4, "start"), (cx - 8, cy + 4, "end"), (cx + 8, cy - 9, "start"), (cx + 8, cy + 16, "start"),
                               (cx - 8, cy - 9, "end"), (cx - 8, cy + 16, "end"), (cx, cy - 12, "middle"), (cx, cy + 19, "middle")]
        for lx, ly, anc in cands:
            bx0 = lx if anc == "start" else lx - w if anc == "end" else lx - w / 2
            box = (bx0, ly - 11, bx0 + w, ly + 2)
            if box[0] < 2 or box[2] > W - 2 or box[1] < T_ - 4 or box[3] > H - B_ + 2: continue
            if in_gut(p) and box[0] < R + 10: continue
            if any(not (box[2] < b[0] or box[0] > b[2] or box[3] < b[1] or box[1] > b[3]) for b in boxes): continue
            placed = (lx, ly, anc, box); break
        if placed is None:
            lx, ly, anc = cands[0]; bx0 = lx if anc == "start" else lx - w if anc == "end" else lx - w / 2
            placed = (lx, ly, anc, (bx0, ly - 11, bx0 + w, ly + 2))
        boxes.append(placed[3])
        g.append(tx(placed[0], placed[1], p["label"], "plab", placed[2]))
        o.append(tip(p["title"], "".join(g)))
    o.append("</svg>")
    return "".join(o)


# ------------------------------------------------------------------ tails and position

def exceedance(series, *, aria, xlabel, W=640, H=300):
    """series: {name, who, values (sorted ascending), width, dash, marks [(kl, share, title)]}. Log-log."""
    L, R, T_, B_ = 64, W - 150, 16, 52
    allv = [v for s in series for v in s["values"] if v > 0]
    n_max = max(len(s["values"]) for s in series)
    x0 = 10 ** math.floor(math.log10(max(min(v for s in series for v in s["values"] if v > 0), 1e-5) if allv else 1e-4))
    x0 = max(x0, 1e-4)
    x1 = 10 ** math.ceil(math.log10(max(allv)))
    y0 = 10 ** math.floor(math.log10(1.0 / n_max)); y1 = 1.0
    X = lambda v: L + (R - L) * (math.log10(v) - math.log10(x0)) / (math.log10(x1) - math.log10(x0))
    Y = lambda v: T_ + (H - T_ - B_) * (math.log10(y1) - math.log10(v)) / (math.log10(y1) - math.log10(y0))
    o = [svg_open(W, H, aria)]
    k = math.log10(x0)
    while k <= math.log10(x1) + 1e-9:
        v = 10 ** k
        o.append(f'<line class="grid" x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{T_}" y2="{H - B_}"/>'
                 + tx(X(v), H - B_ + 15, f"{v:g}", "tick", "middle")); k += 1
    k = 0
    while 10 ** k >= y0 - 1e-15:
        v = 10 ** k
        lab = f"{100 * v:g}%"
        o.append(f'<line class="grid" x1="{L}" x2="{R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/>' + tx(L - 6, Y(v) + 4, lab, "tick", "end")); k -= 1
    o.append(tx((L + R) / 2, H - B_ + 32, xlabel, "sub", "middle"))
    o.append(tx(L, H - 4, "← smaller KL", "dir") + tx(R, H - 4, "larger KL →", "dir", "end"))
    ends = []
    import bisect
    for s in series:
        vals = s["values"]; n = len(vals)
        pts = []
        steps = 72
        for i in range(steps + 1):
            x = 10 ** (math.log10(x0) + (math.log10(x1) - math.log10(x0)) * i / steps)
            share = (n - bisect.bisect_right(vals, x)) / n
            if share <= 0: break
            pts.append((X(x), Y(max(share, y0))))
        cls = ("ln-v" if s["who"] == "v" else "ln-c") + (" thin" if s.get("thin") else "") + (" dsh" if s.get("dash") else "")
        o.append(f'<polyline class="{cls}" points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}"/>')
        for kl, share, t in s.get("marks", []):
            if kl <= 0: continue
            o.append(tip(t, f'<circle class="hit" cx="{X(kl):.1f}" cy="{Y(share):.1f}" r="11"/>' + marker(X(kl), Y(share), s["who"], size=3.6)))
        if s.get("label") and pts: ends.append([pts[-1][1], pts[-1][0], s["label"]])
    ends.sort()
    for i in range(1, len(ends)):
        if ends[i][0] - ends[i - 1][0] < 14: ends[i][0] = ends[i - 1][0] + 14
    for y, x, lab in ends:
        o.append(tx(R + 8, y + 4, lab, "sub"))
    o.append("</svg>")
    return "".join(o)


def profile(cats, series, *, aria, ylabel, W=640, H=250):
    """KL by history: cats = [(label, sub)], series = {name, who, values, titles}. Direct labels at the right end."""
    L, R, T_, B_ = 58, W - 168, 22, 46
    vals = [v for s in series for v in s["values"]] + [0.0]
    y0, y1, yt, ys = lin_domain(vals, pad=0.04, n=4)
    y0 = max(y0, 0.0)
    X = lambda i: L + 30 + i * (R - L - 60) / max(len(cats) - 1, 1)
    Y = lambda v: T_ + (H - T_ - B_) * (y1 - v) / (y1 - y0)
    o = [svg_open(W, H, aria), tx(2, 12, ylabel, "sub")]
    for t in yt:
        if t < y0 - 1e-12: continue
        o.append(f'<line class="{"axis" if abs(t) < 1e-12 else "grid"}" x1="{L}" x2="{R}" y1="{Y(t):.1f}" y2="{Y(t):.1f}"/>'
                 + tx(L - 6, Y(t) + 4, f"{t:.{max(0, -int(math.floor(math.log10(ys))))}f}", "tick", "end"))
    for i, (c, sub) in enumerate(cats):
        o.append(tx(X(i), H - B_ + 15, c, "tick", "middle") + tx(X(i), H - B_ + 29, sub, "sub", "middle"))
    ends = []
    for s in series:
        pts = [(X(i), Y(v)) for i, v in enumerate(s["values"])]
        o.append(f'<polyline class="{"ln-v" if s["who"] == "v" else "ln-c"}" points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}"/>')
        for (a, b), t in zip(pts, s["titles"]):
            o.append(tip(t, f'<circle class="hit" cx="{a:.1f}" cy="{b:.1f}" r="12"/>' + marker(a, b, s["who"], size=4.2)))
        ends.append([pts[-1][1], f'{s["name"]} {s["values"][-1]:.4f}'])
    ends.sort()
    for i in range(1, len(ends)):
        if ends[i][0] - ends[i - 1][0] < 14: ends[i][0] = ends[i - 1][0] + 14
    for y, lab in ends:
        o.append(tx(X(len(cats) - 1) + 14, y + 4, lab, "sub"))
    o.append("</svg>")
    return "".join(o)


def concentration(rows, *, aria, W=640, names=None):
    """rows: (label, [(who, share, title)]). x = share of the panel's total KL, 0-100%."""
    L, R = 150, W - 210
    X = lambda v: L + (R - L) * v
    y = 18; o = []
    H = 18 + len(rows) * 28 + 40
    o.append(svg_open(W, H, aria))
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        o.append(f'<line class="grid" x1="{X(t):.1f}" x2="{X(t):.1f}" y1="10" y2="{H - 34}"/>' + tx(X(t), H - 20, f"{100 * t:.0f}%", "tick", "middle"))
    o.append(tx(L, H - 4, "← less concentrated", "dir") + tx(R, H - 4, "more concentrated →", "dir", "end"))
    for lab, marks in rows:
        cy = y + 12
        g = [tx(L - 8, cy + 4, lab, "lab", "end"), f'<line class="grid" x1="{L}" x2="{R}" y1="{cy}" y2="{cy}"/>']
        for who, v, t in marks:
            g.append(tip(t, f'<circle class="hit" cx="{X(v):.1f}" cy="{cy}" r="11"/>' + marker(X(v), cy + (2 if who == "c" else 0), who, size=4.6)))
        g.append(tx(R + 12, cy + 4, " \u00b7 ".join(f"{n} {100 * v:.0f}%" for n, v in [((names or {"v": "vLLM", "c": "CuteAFD"})[w], v) for w, v, _ in marks]), "val"))
        o.append("<g>" + "".join(g) + "</g>"); y += 28
    o.append("</svg>")
    return "".join(o)


def paired_share(rows, *, aria, W=640):
    """Long output: rows {label, sub, v: (k, n), c: (k, n), title} or {section}. x = share passing, 0-100%."""
    L, R = 196, W - 150
    X = lambda v: L + 8 + (R - L - 16) * v
    y = 26; body = []; pos = []
    for r in rows:
        if "section" in r:
            y += 6; body.append(f'<rect class="secbg" x="0" y="{y - 3:.1f}" width="{tw(r["section"], 7.0) + 8:.1f}" height="18"/>'
                                + tx(2, y + 10, r["section"], "sec")); y += 20; continue
        pos.append((r, y + 13)); y += 26
    yb = y + 4; H = yb + 40
    o = [svg_open(W, H, aria)]
    for t in (0, 0.25, 0.5, 0.75, 1.0):
        o.append(f'<line class="grid" x1="{X(t):.1f}" x2="{X(t):.1f}" y1="20" y2="{yb}"/>' + tx(X(t), yb + 14, f"{100 * t:.0f}%", "tick", "middle"))
    o.append(tx(L + 8, yb + 31, "← fewer pass", "dir") + tx(R - 8, yb + 31, "more pass →", "dir", "end"))
    o += body
    for r, cy in pos:
        (kv, nv), (kc, nc) = r["v"], r["c"]
        fv, fc = kv / nv, kc / nc
        same = abs(fv - fc) < 1e-9
        g = [tx(L - 4, cy + 4, r["label"], "lab", "end"), f'<rect class="hit" x="0" y="{cy - 12}" width="{W}" height="24"/>']
        if not same: g.append(f'<line class="conn" x1="{X(fv):.1f}" x2="{X(fc):.1f}" y1="{cy}" y2="{cy}"/>')
        g.append(marker(X(fv), cy - (4 if same else 0), "v", size=4.4))
        g.append(marker(X(fc), cy + (4 if same else 0), "c", size=4.4))
        g.append(tx(R + 10, cy + 4, f"vLLM {kv}/{nv} · CuteAFD {kc}/{nc}", "val"))
        o.append(f'<g><title>{E(r["title"])}</title>{"".join(g)}</g>')
    o.append("</svg>")
    return "".join(o)


# ------------------------------------------------------------------ legend and figure

def swatch(kind):
    s = {"v": marker(9, 7, "v", size=4.2), "c": marker(9, 8, "c", size=4.2), "ch": marker(9, 8, "c", True, 4.2),
         "ci": '<line class="wk wk-c" x1="1" x2="17" y1="7" y2="7"/>', "ciu": '<line class="wk wk-c unres" x1="1" x2="17" y1="7" y2="7"/>',
         "band": '<rect class="nband" x="1" y="1" width="16" height="12" rx="2"/>',
         "refv": '<line class="ref ref-v" x1="9" x2="9" y1="0" y2="14"/>', "refc": '<line class="ref ref-c" x1="9" x2="9" y1="0" y2="14"/>',
         "refdv": '<line class="refd ref-v" x1="0" x2="18" y1="7" y2="7"/>', "refdc": '<line class="refd ref-c" x1="0" x2="18" y1="7" y2="7"/>',
         "dotc": marker(9, 7, "c", size=2.8, cls_extra="dot"), "dotcu": marker(9, 7, "c", size=2.8, cls_extra="dot unres"),
         "lnv": '<line class="ln-v" x1="0" x2="18" y1="7" y2="7"/>', "lnc": '<line class="ln-c" x1="0" x2="18" y1="7" y2="7"/>',
         "gut": '<rect class="gutter" x="1" y="1" width="16" height="12" rx="2"/>'}[kind]
    return f'<svg class="sw" viewBox="0 0 18 14" width="18" height="14" aria-hidden="true">{s}</svg>'


def legend(items):
    return '<div class="lg">' + "".join(f'<span>{swatch(k)}{E(t)}</span>' for k, t in items) + "</div>"


def figure(fid, title, what, charts, howto, table, legend_items=None, caption=None):
    """charts: list of (svg, spec strip html or None, heading or None). Table view is mandatory."""
    parts = [f'<figure class="fx" id="{fid}"><figcaption><div class="t">{E(title)}</div>'
             f'<p class="what"><b>What this shows.</b> {what}</p></figcaption>']
    if legend_items: parts.append(legend(legend_items))
    for svg, spec, head in charts:
        if head: parts.append(f'<div class="ch">{head}</div>')
        if spec: parts.append(f'<div class="spec">{spec}</div>')
        parts.append(f'<div class="chart">{svg}</div>')
    if caption: parts.append(f'<p class="cap">{caption}</p>')
    parts.append(f'<p class="howto"><b>How to use it.</b> {howto}</p>')
    parts.append(f'<details class="data"><summary>Table view: the exact numbers</summary>{table}</details></figure>')
    return "".join(parts)


CSS = """.fx{padding:14px 16px 12px}.fx .what,.fx .howto,.fx .cap{margin:6px 0;font-size:14px;color:var(--ink2)}.fx .cap{color:var(--ink)}
.fx .what b,.fx .howto b{color:var(--ink)}.fx .ch{font-weight:600;color:var(--ink);font-size:14px;margin:14px 0 2px}
.spec{font-size:12.5px;color:var(--ink2);background:var(--page);border:1px solid var(--ring);border-radius:6px;padding:4px 8px;margin:8px 0 0;font-variant-numeric:tabular-nums}
.chart{overflow-x:auto;-webkit-overflow-scrolling:touch}.chart svg{max-width:720px;min-width:500px;width:100%;margin:6px 0}
.lg{display:flex;flex-wrap:wrap;gap:4px 16px;font-size:12.5px;color:var(--ink2);margin:8px 0 2px}.lg span{display:inline-flex;align-items:center;gap:5px}
.lg svg.sw{display:inline-block;width:18px;height:14px;margin:0;min-width:0}
svg .tick{fill:var(--muted);font-size:11.5px;font-variant-numeric:tabular-nums}svg .dir{fill:var(--ink2);font-size:11.5px}
svg .sub{fill:var(--muted);font-size:11px}svg .sec{fill:var(--ink);font-weight:600;font-size:12.5px}
svg .val{fill:var(--ink2);font-size:12px;font-variant-numeric:tabular-nums}svg .plab{fill:var(--ink);font-size:11.5px}
svg .lab.mut{fill:var(--ink2)}svg .secbg{fill:var(--surface)}svg .lead{stroke:var(--axis);stroke-width:1}svg .nband{fill:var(--g2);opacity:.28}svg .gutter{fill:var(--grid);opacity:.45}
svg .ref{stroke-width:2}svg .refd{stroke-width:1.5;stroke-dasharray:6 4}svg .ref-v{stroke:var(--s1)}svg .ref-c{stroke:var(--s2)}
svg .mk-v{fill:var(--s1);stroke:var(--surface);stroke-width:1.5}svg .mk-c{fill:var(--s2);stroke:var(--surface);stroke-width:1.5}
svg .mk-v-o{fill:var(--surface);stroke:var(--s1);stroke-width:1.8}svg .mk-c-o{fill:var(--surface);stroke:var(--s2);stroke-width:1.8}
svg .dot{stroke-width:1}svg .dot.unres,svg .unres.mk-c,svg .unres.mk-v{opacity:.5}
svg .wk{stroke-width:2.2;stroke-linecap:round}svg .wk-v{stroke:var(--s1)}svg .wk-c{stroke:var(--s2)}svg .wk.unres{stroke-width:1.6;stroke-dasharray:3 3;opacity:.6}
svg .ln-v{stroke:var(--s1);stroke-width:2;fill:none;stroke-linejoin:round}svg .ln-c{stroke:var(--s2);stroke-width:2;fill:none;stroke-linejoin:round}
svg .thin{stroke-width:1.2;opacity:.7}svg .dsh{stroke-dasharray:5 3}
svg g:hover>.mk-v,svg g:hover>.mk-c,svg g:hover>g>.mk-c,svg g:hover>.wk{opacity:.75}
.choose li{margin:9px 0}.choose b{color:var(--ink)}.choose .ev{font-size:13px;white-space:nowrap}"""
