"""A small hand-built data set with answers worked out by hand.

Everything here is written out explicitly and does not use the generator, so the
tests check the SQL against an independent description of the data.

Layout: extract time is Friday 2025-03-14 12:00 UTC. Two support calendars:
  EMEA  Monday to Friday 08:00 to 18:00 UTC (March is before the UK clocks change)
  APAC  Monday to Friday 00:00 to 10:00 UTC (08:00 to 18:00 in Singapore)
Targets (minutes, response / resolution):
  incident P1 15 / 240 on a 24 by 7 clock     incident P2 30 / 480    support hours
  incident P3 120 / 1200 support hours        incident P4 240 / 2400  support hours
  service request P3 240 / 2400 support hours
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

AS_OF = "2025-03-14T12:00:00Z"

# id, type, company, site, category, priority, impact, urgency, opened, response, resolved,
# closed, reopened, first contact fix, team, csat.   Times are "MM-DD HH:MM" in 2025, UTC.
TICKETS = [
    ("INC-1", "incident", "C01", "S1", "Network and Wi-Fi", "P1", 1, 1, "03-07 17:00", "03-07 17:10", "03-08 02:00", "03-13 02:00", 0, 0, "INF", ""),
    ("INC-2", "incident", "C01", "S1", "Network and Wi-Fi", "P1", 1, 1, "03-03 09:00", "03-03 09:20", "03-03 11:00", "03-08 11:00", 0, 0, "INF", ""),
    ("INC-3", "incident", "C01", "S1", "Business application", "P3", 2, 2, "03-07 17:30", "03-10 08:30", "03-11 10:00", "", 0, 0, "APP", ""),
    ("INC-4", "incident", "C01", "S1", "Business application", "P3", 2, 2, "03-04 10:00", "03-04 10:30", "03-07 10:00", "03-12 10:00", 0, 0, "APP", ""),
    ("INC-5", "incident", "C01", "S1", "Password and access", "P3", 2, 2, "03-05 09:00", "03-05 09:10", "03-05 09:50", "03-10 09:50", 0, 1, "SD", 5),
    ("INC-6", "incident", "C01", "S1", "Business application", "P2", 1, 2, "03-13 16:00", "", "", "", 0, 0, "APP", ""),
    ("INC-7", "incident", "C01", "S1", "Business application", "P3", 2, 2, "03-03 12:00", "03-03 12:20", "", "", 0, 0, "APP", ""),
    ("REQ-1", "service_request", "C01", "S1", "Access request", "P3", 2, 2, "03-10 09:00", "03-10 09:30", "03-12 09:00", "03-13 09:00", 1, 0, "IAM", 3),
    ("REQ-2", "service_request", "C02", "S2", "Software install", "P3", 2, 2, "03-10 00:30", "03-10 00:45", "03-10 09:30", "03-12 09:30", 0, 1, "SD", 4),
    ("INC-8", "incident", "C02", "S2", "Network and Wi-Fi", "P4", 3, 3, "03-07 09:00", "03-10 00:30", "03-10 02:00", "03-13 02:00", 0, 0, "FLD", ""),
    ("PRB-1", "problem", "C01", "S1", "Application defect", "P3", 2, 2, "03-03 09:00", "03-04 09:00", "", "", 0, 0, "INF", ""),
    ("CHG-1", "change", "C01", "S1", "Patching and maintenance", "P4", 3, 3, "03-04 09:00", "03-04 12:00", "03-06 09:00", "03-07 09:00", 0, 0, "INF", ""),
    ("INC-9", "incident", "C01", "S1", "Business application", "P2", 1, 2, "03-10 09:00", "03-10 09:25", "03-10 15:00", "03-12 15:00", 0, 0, "APP", ""),
    ("INC-10", "incident", "C01", "S1", "Password and access", "P4", 3, 3, "03-11 08:00", "03-11 10:00", "03-11 12:00", "03-14 12:00", 0, 0, "SD", ""),
    # Deliberately bad: resolved before it was opened. Must be excluded from measures and flagged.
    ("REQ-3", "service_request", "C01", "S1", "Access request", "P3", 2, 2, "03-12 10:00", "03-12 10:30", "03-12 09:00", "03-12 12:00", 0, 0, "IAM", ""),
    # Opened in February, resolved in March. Resolution used exactly 2400 support minutes.
    ("INC-11", "incident", "C01", "S1", "Network and Wi-Fi", "P4", 3, 3, "02-26 10:00", "02-26 10:30", "03-04 10:00", "03-09 10:00", 0, 0, "FLD", ""),
]


def _ts(text: str) -> str:
    """'03-07 17:00' or '02-26 10:00' to '2025-03-07T17:00:00Z'. Blank stays blank."""
    if not text:
        return ""
    return "2025-%s:00Z" % text.replace(" ", "T")


def _write(path: Path, header, rows):
    with open(path, "w", newline="", encoding="utf-8") as h:
        w = csv.writer(h, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def weekdays(first: date, last: date):
    d = first
    while d <= last:
        if d.weekday() < 5:
            yield d
        d += timedelta(days=1)


def build(out_dir, tickets=None) -> Path:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    _write(out / "extract_info.csv",
           ["group_name", "period_start", "period_end", "as_of_utc", "seed", "generator_version"],
           [["Fixture group", "2025-02-01", "2025-03-31", AS_OF, "", ""]])
    _write(out / "companies.csv", ["company_id", "company_name", "sector"],
           [["C01", "Test Company One", "Testing"], ["C02", "Test Company Two", "Testing"]])
    _write(out / "support_calendars.csv",
           ["calendar_code", "calendar_name", "time_zone", "open_local", "close_local", "note"],
           [["APAC", "Asia Pacific", "Asia/Singapore", "08:00", "18:00", ""],
            ["EMEA", "EMEA", "Europe/London", "08:00", "18:00", ""]])
    rows = []
    for d in weekdays(date(2025, 2, 24), date(2025, 3, 21)):
        rows.append(["EMEA", d.isoformat(), "%sT08:00:00Z" % d.isoformat(), "%sT18:00:00Z" % d.isoformat()])
        rows.append(["APAC", d.isoformat(), "%sT00:00:00Z" % d.isoformat(), "%sT10:00:00Z" % d.isoformat()])
    _write(out / "support_windows.csv", ["calendar_code", "local_date", "open_utc", "close_utc"], rows)
    _write(out / "sites.csv",
           ["site_id", "company_id", "site_name", "country", "time_zone", "support_calendar", "headcount"],
           [["S1", "C01", "London", "United Kingdom", "Europe/London", "EMEA", 100],
            ["S2", "C02", "Singapore", "Singapore", "Asia/Singapore", "APAC", 50]])
    _write(out / "teams.csv", ["team_id", "team_name", "fte", "description"],
           [["SD", "Service Desk", 2.0, ""], ["INF", "Infrastructure", 1.0, ""],
            ["APP", "Application Support", 2.5, ""], ["IAM", "Identity and Security", 1.0, ""],
            ["FLD", "Field Services", 1.0, ""]])
    _write(out / "priority_matrix.csv", ["impact", "urgency", "priority", "priority_name"],
           [[1, 1, "P1", "Critical"], [1, 2, "P2", "High"], [1, 3, "P3", "Medium"],
            [2, 1, "P2", "High"], [2, 2, "P3", "Medium"], [2, 3, "P4", "Low"],
            [3, 1, "P3", "Medium"], [3, 2, "P4", "Low"], [3, 3, "P4", "Low"]])
    _write(out / "sla_targets.csv",
           ["ticket_type", "priority", "response_target_minutes", "resolution_target_minutes", "clock_basis"],
           [["incident", "P1", 15, 240, "24X7"], ["incident", "P2", 30, 480, "SUPPORT_HOURS"],
            ["incident", "P3", 120, 1200, "SUPPORT_HOURS"], ["incident", "P4", 240, 2400, "SUPPORT_HOURS"],
            ["service_request", "P3", 240, 2400, "SUPPORT_HOURS"]])
    names = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
             "October", "November", "December"]
    dates = []
    d = date(2025, 2, 1)
    while d <= date(2025, 3, 31):
        dow = d.weekday()
        dates.append([int(d.strftime("%Y%m%d")), d.isoformat(), d.year, (d.month - 1) // 3 + 1, d.month,
                      names[d.month - 1], d.strftime("%Y-%m"), d.replace(day=1).isoformat(),
                      (d - timedelta(days=dow)).isoformat(), dow + 1, d.strftime("%A"), int(dow >= 5),
                      0, int(dow < 5)])
        d += timedelta(days=1)
    _write(out / "dim_date.csv",
           ["date_key", "date", "year", "quarter", "month_number", "month_name", "year_month", "month_start",
            "week_start", "day_of_week", "day_name", "is_weekend", "is_uk_bank_holiday", "is_uk_working_day"],
           dates)
    header = ["ticket_id", "ticket_type", "company_id", "site_id", "category", "priority", "impact", "urgency",
              "opened_at", "first_response_at", "resolved_at", "closed_at", "reopened", "resolved_first_contact",
              "assignee_team", "csat"]
    body = []
    for t in (tickets if tickets is not None else TICKETS):
        t = list(t)
        for i in (8, 9, 10, 11):
            t[i] = _ts(t[i])
        body.append(t)
    _write(out / "tickets.csv", header, body)
    return out
