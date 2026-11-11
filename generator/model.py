"""Ticket generation: volumes, priorities, response and resolution times.

The generator draws from one ``random.Random`` seeded by the caller, in a fixed
order, so the same seed always gives the same tickets. Nothing here reads the
clock, the environment or the system time zone database.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from . import reference as ref
from .calendars import CALENDARS, SupportClock, ZONES, build_windows

DEFAULT_SEED = 2025
TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"

# Weekday profiles, Monday first. They are normalised to an average of 1.
_DOW_USER = [1.40, 1.15, 1.00, 0.95, 0.85, 0.05, 0.05]
_DOW_CHANGE = [0.60, 1.40, 1.50, 1.40, 0.90, 0.0, 0.0]
_DOW_PROBLEM = [1.0, 1.0, 1.0, 1.0, 1.0, 0.05, 0.05]


def _norm(profile):
    mean = sum(profile) / len(profile)
    return [x / mean for x in profile]


DOW_FACTOR = {
    "incident": _norm(_DOW_USER), "service_request": _norm(_DOW_USER),
    "problem": _norm(_DOW_PROBLEM), "change": _norm(_DOW_CHANGE),
}
MONTH_FACTOR = {1: 1.15, 2: 1.0, 3: 1.05, 4: 0.95, 5: 0.95, 6: 1.0,
                7: 0.95, 8: 0.85, 9: 1.10, 10: 1.05, 11: 1.05, 12: 0.85}
MONTH_END_FACTOR = {"incident": 1.20, "service_request": 1.35, "problem": 1.0, "change": 0.8}
HOLIDAY_FACTOR = 0.15
HOUR_WEIGHTS = {8: 7, 9: 14, 10: 14, 11: 11, 12: 7, 13: 9, 14: 11, 15: 11, 16: 9, 17: 7}
OUT_OF_HOURS_SHARE = 0.07
BAD_MONTH_SLOWDOWN = 3.0   # resolution times for the bad team in the bad month
FTC_SCALE = 1.7            # lifts the first contact probabilities in reference.py
RESOLUTION_TARGETS = {(t, p): res for t, p, _r, res, _b in ref.SLA_TARGETS}


@dataclass(frozen=True)
class Config:
    seed: int = DEFAULT_SEED
    start: date = date(2024, 12, 1)          # first local day of the period
    end: date = date(2025, 11, 30)           # last local day of the period
    as_of: datetime = datetime(2025, 12, 1)  # extract time, UTC: later events are blank
    scale: float = 1.0                       # multiplies ticket volumes
    bad_year: int = 2025                     # the deliberate bad month ...
    bad_month: int = 11
    bad_team: str = "APP"                    # ... for this team


def poisson(rng: random.Random, lam: float) -> int:
    """Knuth's method for small means, normal approximation for large ones."""
    if lam <= 0:
        return 0
    if lam > 30:
        return max(0, round(rng.gauss(lam, math.sqrt(lam))))
    limit, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def lognormal_minutes(rng: random.Random, median: float, sigma: float) -> int:
    return max(1, round(median * math.exp(rng.gauss(0, sigma))))


def month_end_days(first: date, last: date) -> set:
    """First weekday of each month and last two weekdays of each month."""
    days = set()
    d = first
    while d <= last:
        month_days = []
        m = d.month
        while d <= last and d.month == m:
            if d.weekday() < 5:
                month_days.append(d)
            d += timedelta(days=1)
        if month_days:
            days.add(month_days[0])
            days.update(month_days[-2:])
    return days


def _clocks(cfg: Config):
    windows = {}
    clocks = {}
    first = cfg.start - timedelta(days=7)
    last = date(2028, 12, 31)
    for code, cal in CALENDARS.items():
        windows[code] = build_windows(cal, first, last)
        clocks[code] = SupportClock(windows[code])
    clocks["24X7"] = SupportClock(None)
    return windows, clocks


def _weighted(rng, items, weights):
    return rng.choices(items, weights=weights, k=1)[0]


def _csat(rng, breached: bool, reopened: bool, ftc: bool, bad: bool) -> int:
    base = [2, 4, 9, 27, 58]
    if breached:
        base = [10, 15, 25, 30, 20]
    if reopened:
        base = [20, 25, 25, 18, 12]
    if ftc and not reopened:
        base = [1, 2, 6, 24, 67]
    if bad:
        base = [x + y for x, y in zip(base, [14, 14, 6, -6, -28])]
        base = [max(1, x) for x in base]
    return _weighted(rng, [1, 2, 3, 4, 5], base)


def generate_tickets(cfg: Config):
    """Return (tickets, support_windows) as lists of dict rows, in output order."""
    rng = random.Random(cfg.seed)
    windows, clocks = _clocks(cfg)
    sla_basis = {(t, p): basis for t, p, _r, _s, basis in ref.SLA_TARGETS}
    me_days = month_end_days(cfg.start - timedelta(days=40), cfg.end + timedelta(days=40))
    period_start_utc = datetime.combine(cfg.start, datetime.min.time())
    raw = []
    seq = 0

    for site_id, company_id, _name, _country, tz_name, cal_code, headcount in sorted(ref.SITES):
        zone = ZONES[tz_name]
        holidays = set(CALENDARS[cal_code].holidays)
        local_day = cfg.start
        while local_day <= cfg.end:
            dow = local_day.weekday()
            is_workday = dow < 5 and local_day not in holidays
            for ttype in ref.TICKET_TYPES:
                lam = (headcount * ref.PER_HEAD_MONTHLY[ttype] * 12 / 365 * cfg.scale
                       * DOW_FACTOR[ttype][dow] * MONTH_FACTOR[local_day.month])
                if local_day in me_days:
                    lam *= MONTH_END_FACTOR[ttype]
                if local_day in holidays:
                    lam *= HOLIDAY_FACTOR
                bad_month = (local_day.year, local_day.month) == (cfg.bad_year, cfg.bad_month)
                if bad_month and ttype == "incident":
                    lam *= 1.10
                for _ in range(poisson(rng, lam)):
                    seq += 1
                    ticket = _make_ticket(rng, cfg, zone, cal_code, clocks, sla_basis, ttype,
                                          site_id, company_id, local_day, is_workday,
                                          local_day in me_days, bad_month)
                    if ticket["opened_at"] < period_start_utc or ticket["opened_at"] >= cfg.as_of:
                        continue
                    ticket["_seq"] = seq
                    raw.append(ticket)
            local_day += timedelta(days=1)

    raw.sort(key=lambda t: (t["opened_at"], t["_seq"]))
    counters = {t: 0 for t in ref.TICKET_TYPES}
    rows = []
    for t in raw:
        counters[t["ticket_type"]] += 1
        t["ticket_id"] = "%s-%06d" % (ref.TYPE_PREFIX[t["ticket_type"]], counters[t["ticket_type"]])
        rows.append(_censor(t, cfg.as_of))
    window_rows = [
        {"calendar_code": code, "local_date": w[2].isoformat(),
         "open_utc": w[0].strftime(TS_FORMAT), "close_utc": w[1].strftime(TS_FORMAT)}
        for code in sorted(windows) for w in windows[code]
        if w[2] <= cfg.end + timedelta(days=5)
    ]
    return rows, window_rows


def _make_ticket(rng, cfg, zone, cal_code, clocks, sla_basis, ttype, site_id, company_id,
                 local_day, is_workday, is_month_end, bad_month):
    # When the ticket was opened.
    if is_workday and rng.random() > OUT_OF_HOURS_SHARE:
        hour = _weighted(rng, list(HOUR_WEIGHTS), list(HOUR_WEIGHTS.values()))
        minute_of_day = hour * 60 + rng.randrange(60)
    else:
        minute_of_day = rng.randrange(1440)
    local = datetime.combine(local_day, datetime.min.time()) + timedelta(minutes=minute_of_day)
    opened = zone.to_utc(local)

    # What it is about and who resolves it.
    cats = ref.CATEGORIES[ttype]
    weights = [c[1] * (1.5 if bad_month and c[2] == cfg.bad_team else 1.0) for c in cats]
    category, _w, cat_team, ftc_prob = _weighted(rng, cats, weights)
    joint = ref.IMPACT_URGENCY_WEIGHTS[ttype]
    impact, urgency = _weighted(rng, list(joint), list(joint.values()))
    priority = ref.PRIORITY_MATRIX[(impact, urgency)]

    ftc = priority in ("P3", "P4") and rng.random() < min(0.95, ftc_prob * FTC_SCALE)
    team = "SD" if ftc else cat_team
    bad = bad_month and team == cfg.bad_team
    load = 1.0 + (0.15 if (local_day.weekday() == 0 or is_month_end) else 0.0)

    clock = clocks["24X7"] if sla_basis.get((ttype, priority)) == "24X7" else clocks[cal_code]

    r_median, r_sigma = ref.RESPONSE_MODEL[(ttype, priority)]
    response_work = lognormal_minutes(
        rng, r_median * (1.25 if load > 1 else 1.0) * (1.6 if bad else 1.0), r_sigma)

    s_median, s_sigma = ref.RESOLUTION_MODEL[(ttype, priority)]
    if ftc:
        resolution_work = response_work + rng.randint(2, 25)
    else:
        resolution_work = lognormal_minutes(
            rng, s_median * ref.TEAM_SPEED[team] * load * (BAD_MONTH_SLOWDOWN if bad else 1.0), s_sigma)
        if ttype in ("incident", "service_request") and rng.random() < 0.012:
            resolution_work = round(resolution_work * rng.uniform(8, 40))  # stuck with a supplier
        resolution_work = max(resolution_work, response_work + 1)

    first_response = clock.add_minutes(opened, response_work)
    resolved = clock.add_minutes(opened, resolution_work)

    # Quality signals.
    reopened = False
    reopen_after = timedelta(days=rng.randint(1, 3))
    if ttype in ("incident", "service_request"):
        p = 0.17 if bad else (0.03 if ftc else (0.045 if ttype == "incident" else 0.025))
        reopened = rng.random() < p
    if reopened:
        closed = resolved + reopen_after + timedelta(days=5, minutes=rng.randrange(0, 600))
    elif ttype in ("problem", "change"):
        closed = resolved + timedelta(days=rng.randint(1, 7), minutes=rng.randrange(0, 600))
    elif rng.random() < 0.3:
        closed = resolved + timedelta(days=rng.randint(1, 4), minutes=rng.randrange(0, 600))
    else:
        closed = resolved + timedelta(days=5)

    csat = None
    if ttype in ("incident", "service_request") and rng.random() < 0.34:
        target = RESOLUTION_TARGETS.get((ttype, priority))
        breached = target is not None and resolution_work > target
        csat = _csat(rng, breached, reopened, ftc, bad)

    return {
        "ticket_type": ttype, "company_id": company_id, "site_id": site_id,
        "category": category, "priority": priority, "impact": impact, "urgency": urgency,
        "opened_at": opened, "first_response_at": first_response, "resolved_at": resolved,
        "closed_at": closed, "reopened": int(reopened), "resolved_first_contact": int(ftc),
        "assignee_team": team, "csat": csat, "_reopen_at": resolved + reopen_after,
    }


def _censor(t, as_of):
    """Blank any timestamp later than the extract time, as a live system would."""
    out = dict(t)
    for key in ("first_response_at", "resolved_at", "closed_at"):
        if out[key] is not None and out[key] > as_of:
            out[key] = None
    if out["resolved_at"] is None:
        out["resolved_first_contact"] = 0
        out["reopened"] = 0
        out["csat"] = None
    elif out["csat"] is not None and out["resolved_at"] + timedelta(days=1) > as_of:
        out["csat"] = None  # the survey has not gone out yet
    if out["reopened"] and out["_reopen_at"] > as_of:
        out["reopened"] = 0  # not reopened yet, as far as this extract can tell
    for key in ("opened_at", "first_response_at", "resolved_at", "closed_at"):
        out[key] = out[key].strftime(TS_FORMAT) if out[key] is not None else ""
    out["csat"] = "" if out["csat"] is None else out["csat"]
    return {k: v for k, v in out.items() if not k.startswith("_")}
