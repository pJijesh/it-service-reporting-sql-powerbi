"""Independent calculations in plain Python, used to check the SQL views.

Nothing in this module calls SQL. It reads the CSV files directly and counts the long way.
"""

from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

FMT = "%Y-%m-%dT%H:%M:%SZ"


def ts(text):
    return datetime.strptime(text, FMT) if text else None


def read(path):
    with open(path, newline="", encoding="utf-8") as h:
        return list(csv.DictReader(h))


def support_minutes_bruteforce(windows, start, end):
    """Step through time one minute at a time. Slow, but impossible to get subtly wrong."""
    minutes, t = 0, start
    while t < end:
        if any(o <= t < c for o, c in windows):
            minutes += 1
        t += timedelta(minutes=1)
    return minutes


def support_minutes(windows, start, end):
    """Sum of overlaps between [start, end] and each window. Fast."""
    total = timedelta(0)
    for o, c in windows:
        lo, hi = max(o, start), min(c, end)
        if hi > lo:
            total += hi - lo
    return int(total / timedelta(minutes=1))


class Dataset:
    def __init__(self, folder):
        folder = Path(folder)
        self.tickets = read(folder / "tickets.csv")
        self.sites = {r["site_id"]: r for r in read(folder / "sites.csv")}
        self.targets = {(r["ticket_type"], r["priority"]): r for r in read(folder / "sla_targets.csv")}
        self.as_of = ts(read(folder / "extract_info.csv")[0]["as_of_utc"])
        self.windows = defaultdict(list)
        for r in read(folder / "support_windows.csv"):
            self.windows[r["calendar_code"]].append((ts(r["open_utc"]), ts(r["close_utc"])))

    def measure(self, t, fast=True):
        """Return a dict of the SLA outcome for one ticket, or None if it has no service level."""
        target = self.targets.get((t["ticket_type"], t["priority"]))
        if target is None:
            return None
        opened, resp, res = ts(t["opened_at"]), ts(t["first_response_at"]), ts(t["resolved_at"])
        if (resp and resp < opened) or (res and res < opened) or (resp and res and resp > res):
            return None  # invalid timeline: not measured
        closed = ts(t["closed_at"])
        if closed and (not res or closed < res):
            return None
        cal = self.sites[t["site_id"]]["support_calendar"]
        count = support_minutes if fast else support_minutes_bruteforce

        def clock(end):
            if target["clock_basis"] == "24X7":
                return int((end - opened) / timedelta(minutes=1))
            return count(self.windows[cal], opened, end)

        resp_end = resp or res
        out = {}
        for name, end, limit in (("response", resp_end, int(target["response_target_minutes"])),
                                 ("resolution", res, int(target["resolution_target_minutes"]))):
            minutes = clock(end or self.as_of)
            if minutes > limit:
                out[name] = "breached"
            elif end is not None:
                out[name] = "met"
            else:
                out[name] = "in_flight"
            out[name + "_minutes"] = minutes
        return out

    def sla_counts(self, key):
        """Counts by key(ticket): {key: [resp_measured, resp_met, res_measured, res_met]}."""
        acc = defaultdict(lambda: [0, 0, 0, 0])
        for t in self.tickets:
            m = self.measure(t)
            if m is None:
                continue
            a = acc[key(t)]
            if m["response"] != "in_flight":
                a[0] += 1
                a[1] += m["response"] == "met"
            if m["resolution"] != "in_flight":
                a[2] += 1
                a[3] += m["resolution"] == "met"
        return dict(acc)

    def open_at(self, moment):
        return [t for t in self.tickets
                if ts(t["opened_at"]) < moment and (not t["resolved_at"] or ts(t["resolved_at"]) >= moment)]
