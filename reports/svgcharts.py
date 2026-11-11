"""Small SVG chart writer. Standard library only, deterministic output.

Three chart types are enough for a service report: a line chart, stacked columns and
horizontal grouped bars. Colours come from the Okabe-Ito palette, which stays distinct
for most kinds of colour blindness, and every line also carries a direct label so the
chart does not rely on colour alone. Each file has a title and a description for
screen readers. The background is solid white so the image reads on dark pages too.
"""

from __future__ import annotations

import math
from xml.sax.saxutils import escape

FONT = "system-ui, -apple-system, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif"
INK, MUTED, GRID = "#1f2933", "#52606d", "#d9dee3"
PALETTE = ["#0072B2", "#D55E00", "#009E73", "#CC79A7", "#E69F00", "#56B4E9", "#7a7a7a"]


def _f(x: float) -> str:
    return ("%.1f" % x).rstrip("0").rstrip(".")


def nice_ticks(lo: float, hi: float, target: int = 5):
    """Round tick values from at or below lo to at or above hi."""
    span = (hi - lo) if hi > lo else 1.0
    mag = 10 ** math.floor(math.log10(span / target))
    step = mag
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if span / step <= target:
            break
    ticks, v = [], math.floor(lo / step) * step
    while True:
        ticks.append(round(v, 6))
        if v >= hi - 1e-9:
            break
        v += step
    return ticks


class Canvas:
    def __init__(self, width, height, title, desc):
        self.w, self.h = width, height
        self.parts = []
        self.title, self.desc = title, desc

    def add(self, text):
        self.parts.append(text)

    def text(self, x, y, s, size=12, anchor="start", fill=INK, weight="normal", halo=False):
        extra = ' stroke="#ffffff" stroke-width="3" paint-order="stroke"' if halo else ""
        self.add('<text x="%s" y="%s" font-size="%d" text-anchor="%s" fill="%s" font-weight="%s"%s>%s</text>'
                 % (_f(x), _f(y), size, anchor, fill, weight, extra, escape(str(s))))

    def render(self) -> str:
        head = ('<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" '
                'role="img" aria-labelledby="t d" font-family="%s">\n'
                '<title id="t">%s</title>\n<desc id="d">%s</desc>\n'
                '<rect width="100%%" height="100%%" fill="#ffffff"/>\n'
                % (self.w, self.h, self.w, self.h, FONT.replace('"', "'"),
                   escape(self.title), escape(self.desc)))
        return head + "\n".join(self.parts) + "\n</svg>\n"


def _frame(c, heading, subtitle):
    c.text(24, 28, heading, size=16, weight="bold")
    if subtitle:
        c.text(24, 47, subtitle, size=12, fill=MUTED)


def _y_axis(c, left, right, top, bottom, lo, hi, fmt, label):
    ticks = [t for t in nice_ticks(lo, hi) if lo - 1e-9 <= t <= hi + 1e-9]
    span = hi - lo
    for t in ticks:
        y = bottom - (t - lo) / span * (bottom - top)
        c.add('<line x1="%d" y1="%s" x2="%d" y2="%s" stroke="%s" stroke-width="1"/>'
              % (left, _f(y), right, _f(y), GRID))
        c.text(left - 8, y + 4, fmt(t), size=11, anchor="end", fill=MUTED)
    if label:
        c.add('<text transform="translate(14 %s) rotate(-90)" font-size="11" text-anchor="middle" fill="%s">%s</text>'
              % (_f((top + bottom) / 2), MUTED, escape(label)))


def line_chart(path, heading, subtitle, categories, series, y_range, y_label="", fmt=None,
               target=None, target_label="", desc=""):
    """series: list of dicts with name, values (None allowed), color (optional), emphasis (bool)."""
    fmt = fmt or (lambda v: "%g" % v)
    w, h, left, right, top, bottom = 760, 400, 56, 150, 66, 350
    c = Canvas(w, h, heading, desc or subtitle)
    _frame(c, heading, subtitle)
    lo, hi = y_range
    _y_axis(c, left, w - right, top, bottom, lo, hi, fmt, y_label)
    n = len(categories)
    xs = [left + 14 + i * ((w - right - left - 28) / max(n - 1, 1)) for i in range(n)]
    for x, cat in zip(xs, categories):
        c.text(x, bottom + 20, cat, size=11, anchor="middle", fill=MUTED)

    def ypos(v):
        return bottom - (min(max(v, lo), hi) - lo) / (hi - lo) * (bottom - top)

    if target is not None:
        y = ypos(target)
        c.add('<line x1="%d" y1="%s" x2="%d" y2="%s" stroke="%s" stroke-width="1.5" stroke-dasharray="6 4"/>'
              % (left, _f(y), w - right, _f(y), MUTED))
        c.text(w - right + 6, y + 4, target_label or "target", size=11, fill=MUTED)

    label_ys = []
    for i, s in enumerate(series):
        color = s.get("color") or PALETTE[i % len(PALETTE)]
        width = 3 if s.get("emphasis") else 2
        pts = [(x, ypos(v)) for x, v in zip(xs, s["values"]) if v is not None]
        c.add('<polyline fill="none" stroke="%s" stroke-width="%d" stroke-linejoin="round" points="%s"/>'
              % (color, width, " ".join("%s,%s" % (_f(x), _f(y)) for x, y in pts)))
        for x, y in pts:
            c.add('<circle cx="%s" cy="%s" r="%s" fill="%s"/>' % (_f(x), _f(y), 3.5 if s.get("emphasis") else 2.5, color))
        if pts:
            ly = pts[-1][1] + 4
            while any(abs(ly - o) < 13 for o in label_ys):  # keep direct labels apart
                ly += 13
            label_ys.append(ly)
            c.text(pts[-1][0] + 10, ly, s["name"], size=11, fill=color, weight="bold")
    c.add('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>' % (left, bottom, w - right, bottom, MUTED))
    path.write_text(c.render(), encoding="utf-8")


def stacked_columns(path, heading, subtitle, categories, series, y_label="", desc=""):
    """series: list of dicts with name and values (all the same length as categories)."""
    w, h, left, right, top, bottom = 760, 400, 56, 150, 66, 350
    c = Canvas(w, h, heading, desc or subtitle)
    _frame(c, heading, subtitle)
    totals = [sum(s["values"][i] for s in series) for i in range(len(categories))]
    hi = nice_ticks(0, max(totals))[-1]
    _y_axis(c, left, w - right, top, bottom, 0, hi, lambda v: "%d" % v, y_label)
    n = len(categories)
    slot = (w - right - left) / n
    bar = slot * 0.62
    for i, cat in enumerate(categories):
        x0 = left + i * slot + (slot - bar) / 2
        y = bottom
        for j, s in enumerate(series):
            v = s["values"][i]
            ht = v / hi * (bottom - top)
            if ht > 0:
                c.add('<rect x="%s" y="%s" width="%s" height="%s" fill="%s"/>'
                      % (_f(x0), _f(y - ht), _f(bar), _f(ht), s.get("color") or PALETTE[j % len(PALETTE)]))
            y -= ht
        c.text(x0 + bar / 2, y - 5, "%d" % totals[i], size=10, anchor="middle", fill=MUTED)
        c.text(x0 + bar / 2, bottom + 20, cat, size=11, anchor="middle", fill=MUTED)
    ly = top + 8
    for j, s in reversed(list(enumerate(series))):
        c.add('<rect x="%d" y="%d" width="12" height="12" fill="%s"/>'
              % (w - right + 12, ly - 10, s.get("color") or PALETTE[j % len(PALETTE)]))
        c.text(w - right + 30, ly, s["name"], size=11)
        ly += 20
    c.add('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s"/>' % (left, bottom, w - right, bottom, MUTED))
    path.write_text(c.render(), encoding="utf-8")


def grouped_hbars(path, heading, subtitle, labels, series, x_max=100.0, target=None,
                  target_label="", value_fmt=None, desc=""):
    """Horizontal bars. series: list of dicts with name, values, color. One group per label."""
    value_fmt = value_fmt or (lambda v: "%.1f" % v)
    w, left, right, top = 760, 170, 70, 70
    row_h = 22 * len(series) + 18
    h = top + row_h * len(labels) + 54
    c = Canvas(w, h, heading, desc or subtitle)
    _frame(c, heading, subtitle)
    plot_w = w - left - right
    for t in nice_ticks(0, x_max):
        if t > x_max:
            continue
        x = left + t / x_max * plot_w
        c.add('<line x1="%s" y1="%d" x2="%s" y2="%d" stroke="%s"/>' % (_f(x), top - 6, _f(x), h - 44, GRID))
        c.text(x, h - 28, "%g" % t, size=11, anchor="middle", fill=MUTED)
    for i, label in enumerate(labels):
        y0 = top + i * row_h
        c.text(left - 10, y0 + 12 * len(series) + 2, label, size=12, anchor="end")
        for j, s in enumerate(series):
            v = s["values"][i]
            if v is None:
                continue
            bw = v / x_max * plot_w
            y = y0 + j * 22
            c.add('<rect x="%d" y="%d" width="%s" height="17" fill="%s"/>'
                  % (left, y, _f(bw), s.get("color") or PALETTE[j % len(PALETTE)]))
            c.text(left + bw + 6, y + 13, value_fmt(v), size=11, fill=INK, halo=True)
    if target is not None:
        x = left + target / x_max * plot_w
        c.add('<line x1="%s" y1="%d" x2="%s" y2="%d" stroke="%s" stroke-width="1.5" stroke-dasharray="6 4"/>'
              % (_f(x), top - 6, _f(x), h - 44, MUTED))
        c.text(x, top - 12, target_label or "target", size=11, anchor="middle", fill=MUTED)
    lx = left
    for j, s in enumerate(series):
        c.add('<rect x="%d" y="%d" width="12" height="12" fill="%s"/>'
              % (lx, h - 16, s.get("color") or PALETTE[j % len(PALETTE)]))
        c.text(lx + 18, h - 6, s["name"], size=11)
        lx += 28 + 7 * len(s["name"])
    path.write_text(c.render(), encoding="utf-8")
