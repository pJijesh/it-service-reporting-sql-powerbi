"""Write the generated tables as CSV files with a fixed layout."""

from __future__ import annotations

import csv
import hashlib
from datetime import date, timedelta
from pathlib import Path

from . import __version__
from . import reference as ref
from .calendars import CALENDARS, EMEA_HOLIDAYS
from .model import TS_FORMAT, Config, generate_tickets

TICKET_COLUMNS = [
    "ticket_id", "ticket_type", "company_id", "site_id", "category", "priority", "impact",
    "urgency", "opened_at", "first_response_at", "resolved_at", "closed_at", "reopened",
    "resolved_first_contact", "assignee_team", "csat",
]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]
DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def write_csv(path: Path, columns, rows) -> None:
    """Write rows (sequences or dicts) with Unix line endings, so output is the same on every OS."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for row in rows:
            writer.writerow([row[c] for c in columns] if isinstance(row, dict) else row)


def build_dim_date(first: date, last: date):
    holidays = set(EMEA_HOLIDAYS)
    rows = []
    d = first
    while d <= last:
        dow = d.weekday()
        rows.append([
            int(d.strftime("%Y%m%d")), d.isoformat(), d.year, (d.month - 1) // 3 + 1, d.month,
            MONTH_NAMES[d.month - 1], "%04d-%02d" % (d.year, d.month),
            d.replace(day=1).isoformat(), (d - timedelta(days=dow)).isoformat(), dow + 1,
            DAY_NAMES[dow], int(dow >= 5), int(d in holidays),
            int(dow < 5 and d not in holidays),
        ])
        d += timedelta(days=1)
    return rows


DIM_DATE_COLUMNS = [
    "date_key", "date", "year", "quarter", "month_number", "month_name", "year_month",
    "month_start", "week_start", "day_of_week", "day_name", "is_weekend",
    "is_uk_bank_holiday", "is_uk_working_day",
]


def write_all(out_dir, cfg: Config = Config()) -> dict:
    """Generate and write every CSV. Returns a mapping of file name to SHA-256."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    tickets, windows = generate_tickets(cfg)

    write_csv(out / "tickets.csv", TICKET_COLUMNS, tickets)
    write_csv(out / "companies.csv", ["company_id", "company_name", "sector"], ref.COMPANIES)
    write_csv(out / "sites.csv", ["site_id", "company_id", "site_name", "country", "time_zone",
                                  "support_calendar", "headcount"], ref.SITES)
    write_csv(out / "teams.csv", ["team_id", "team_name", "fte", "description"], ref.TEAMS)
    write_csv(out / "sla_targets.csv", ["ticket_type", "priority", "response_target_minutes",
                                        "resolution_target_minutes", "clock_basis"], ref.SLA_TARGETS)
    write_csv(out / "priority_matrix.csv", ["impact", "urgency", "priority", "priority_name"], [
        [i, u, p, ref.PRIORITY_NAMES[p]] for (i, u), p in sorted(ref.PRIORITY_MATRIX.items())])
    write_csv(out / "support_calendars.csv", ["calendar_code", "calendar_name", "time_zone",
                                              "open_local", "close_local", "note"], [
        [c.code, c.name, c.zone, c.open_local, c.close_local, c.note]
        for c in (CALENDARS[k] for k in sorted(CALENDARS))])
    write_csv(out / "support_windows.csv", ["calendar_code", "local_date", "open_utc", "close_utc"],
              windows)
    write_csv(out / "dim_date.csv", DIM_DATE_COLUMNS, build_dim_date(cfg.start, cfg.end))
    write_csv(out / "extract_info.csv", ["group_name", "period_start", "period_end", "as_of_utc",
                                         "seed", "generator_version"], [[
        ref.GROUP_NAME, cfg.start.isoformat(), cfg.end.isoformat(),
        cfg.as_of.strftime(TS_FORMAT), cfg.seed, __version__]])
    return checksums(out)


def checksums(out_dir) -> dict:
    result = {}
    for path in sorted(Path(out_dir).glob("*.csv")):
        result[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result
