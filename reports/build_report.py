"""Build the monthly service report (Markdown) and its charts (SVG) from the SQL views.

    python -m reports.build_report --db build/service_reporting.db --month 2025-11 --out reports

Every number in the report is read from the views in sql/views. The only text that does not
come from the database is the optional management commentary file, which is plain
hand-written prose clearly marked as such. Output is deterministic: the same database
gives byte-identical files.
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

from . import svgcharts as charts

GROUP = "Kelderwick Group (fictional)"

# Example targets used to colour-free "status" words in the summary table. They are
# illustrations for this data set, not recommendations. higher=True means more is better.
TARGETS = [
    # key, label, target, higher_is_better, unit
    ("resolution", "Resolution within target", 92.0, True, "%"),
    ("response", "Response within target", 92.0, True, "%"),
    ("p1_resolution", "P1 incidents resolved within target", 95.0, True, "%"),
    ("ftf", "Fixed at first contact", 35.0, True, "%"),
    ("reopen", "Reopened after resolution", 4.0, False, "%"),
    ("csat", "Customer satisfaction (1 to 5)", 4.2, True, ""),
]
TYPE_LABEL = {"incident": "Incidents", "service_request": "Service requests",
              "problem": "Problems", "change": "Changes"}
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def short_month(ym: str) -> str:
    return "%s %s" % (MONTH_ABBR[int(ym[5:7]) - 1], ym[2:4])


def long_month(ym: str) -> str:
    names = ["January", "February", "March", "April", "May", "June", "July", "August",
             "September", "October", "November", "December"]
    return "%s %s" % (names[int(ym[5:7]) - 1], ym[:4])


def prev_months(months, month, n):
    """The n months up to and including month, oldest first."""
    i = months.index(month)
    return months[max(0, i - n + 1): i + 1]


def pct(num, den):
    return None if not den else round(100.0 * num / den, 1)


def fmt_pct(v):
    return "n/a" if v is None else "%.1f%%" % v


def delta(cur, prev, unit="pts"):
    if cur is None or prev is None:
        return "n/a"
    d = round(cur - prev, 1)
    return "%+.1f %s" % (d, unit) if d != 0 else "no change"


def hours(minutes):
    return "n/a" if minutes is None else "%.1f" % (minutes / 60.0)


class Data:
    """Thin wrapper that runs queries against the views."""

    def __init__(self, conn):
        self.conn = conn

    def rows(self, sql, params=()):
        return self.conn.execute(sql, params).fetchall()

    def one(self, sql, params=()):
        return self.conn.execute(sql, params).fetchone()

    def months(self):
        return [r[0] for r in self.rows("SELECT DISTINCT year_month FROM dim_date ORDER BY 1")]

    def sla(self, months, where="", params=()):
        """(response_measured, response_met, resolution_measured, resolution_met) summed."""
        marks = ",".join("?" for _ in months)
        r = self.one("SELECT COALESCE(SUM(response_measured),0), COALESCE(SUM(response_met),0),"
                     " COALESCE(SUM(resolution_measured),0), COALESCE(SUM(resolution_met),0)"
                     " FROM sla_compliance WHERE month IN (%s) %s" % (marks, where),
                     tuple(months) + tuple(params))
        return r


def headline(d: Data, months, month):
    """Headline measures for one month: dict key -> value."""
    rm, rmet, sm, smet = d.sla([month])
    p1 = d.sla([month], "AND priority = 'P1' AND ticket_type = 'incident'")
    mt = d.one("SELECT COALESCE(SUM(incidents_resolved),0), SUM(total_clock_minutes) FROM mttr WHERE month = ?", (month,))
    ftf = d.one("SELECT COALESCE(SUM(resolved_tickets),0), COALESCE(SUM(fixed_first_contact),0) FROM first_time_fix_rate WHERE month = ?", (month,))
    ro = d.one("SELECT COALESCE(SUM(resolved_tickets),0), COALESCE(SUM(reopened_tickets),0) FROM reopen_rate WHERE month = ?", (month,))
    cs = d.one("SELECT COALESCE(SUM(responses),0), COALESCE(SUM(csat_total),0), COALESCE(SUM(resolved_tickets),0) FROM csat_summary WHERE month = ?", (month,))
    opened = d.one("SELECT COALESCE(SUM(opened),0) FROM volume_trend WHERE month = ?", (month,))[0]
    backlog = d.one("SELECT COALESCE(SUM(open_tickets),0) FROM backlog_month_end WHERE month = ?", (month,))[0]
    return {
        "resolution": pct(smet, sm), "response": pct(rmet, rm), "p1_resolution": pct(p1[3], p1[2]),
        "ftf": pct(ftf[1], ftf[0]), "reopen": pct(ro[1], ro[0]),
        "csat": round(cs[1] / cs[0], 2) if cs[0] else None, "csat_responses": cs[0],
        "mttr_minutes": (mt[1] / mt[0]) if mt[0] else None, "incidents_resolved": mt[0],
        "opened": opened, "backlog": backlog,
        "resolution_n": sm, "p1_n": p1[2],
    }


def status(value, target, higher):
    if value is None:
        return "n/a"
    ok = value >= target if higher else value <= target
    return "Met" if ok else "Not met"


def build(conn: sqlite3.Connection, month: str, out_dir: Path, commentary: Path | None = None):
    d = Data(conn)
    months = d.months()
    if month not in months:
        raise ValueError("month %s is not in the data (available: %s to %s)" % (month, months[0], months[-1]))
    i = months.index(month)
    prev = months[i - 1] if i > 0 else None
    window = prev_months(months, month, 3)
    as_of = d.one("SELECT as_of_utc FROM extract_info")[0]
    out_dir = Path(out_dir)
    (out_dir / "charts").mkdir(parents=True, exist_ok=True)

    cur = headline(d, months, month)
    old = headline(d, months, prev) if prev else {}
    roll = d.sla(window)
    rolling_resolution, rolling_response = pct(roll[3], roll[2]), pct(roll[1], roll[0])

    team_name = {r[0]: r[1] for r in d.rows("SELECT team_id, team_name FROM teams")}
    company_name = {r[0]: r[1] for r in d.rows("SELECT company_id, company_name FROM companies ORDER BY 1")}

    # ----- charts -----
    sla_series = {"Resolution": [], "Response": []}
    for m in months:
        r = d.sla([m])
        sla_series["Resolution"].append(pct(r[3], r[2]))
        sla_series["Response"].append(pct(r[1], r[0]))
    charts.line_chart(
        out_dir / "charts" / "sla-trend.svg",
        "Service level performance by month",
        "Incidents and service requests, share of tickets opened in the month that met target",
        [short_month(m) for m in months],
        [{"name": "Resolution", "values": sla_series["Resolution"], "color": charts.PALETTE[0], "emphasis": True},
         {"name": "Response", "values": sla_series["Response"], "color": charts.PALETTE[1]}],
        (80, 100), y_label="% within target", fmt=lambda v: "%g%%" % v,
        target=92.0, target_label="example target 92%",
        desc="Line chart of the percentage of tickets meeting their response and resolution targets, "
             "by month, from %s to %s." % (long_month(months[0]), long_month(months[-1])))

    vol_rows = d.rows("SELECT month, ticket_type, SUM(opened) FROM volume_trend GROUP BY month, ticket_type")
    vol = {(m, t): n for m, t, n in vol_rows}
    types = ["incident", "service_request", "problem", "change"]
    charts.stacked_columns(
        out_dir / "charts" / "volume-by-type.svg",
        "Tickets opened per month",
        "All four companies, by ticket type. Monthly total shown above each column",
        [short_month(m) for m in months],
        [{"name": TYPE_LABEL[t], "values": [vol.get((m, t), 0) for m in months],
          "color": charts.PALETTE[k]} for k, t in enumerate(types)],
        y_label="tickets opened",
        desc="Stacked column chart of tickets opened each month by type.")

    team_ids = [r[0] for r in d.rows("SELECT team_id FROM teams ORDER BY team_id")]
    bl = {(r[0], r[1]): r[2] for r in d.rows(
        "SELECT month, team_id, SUM(open_tickets) FROM backlog_month_end GROUP BY month, team_id")}
    team_series = []
    for k, t in enumerate(team_ids):
        team_series.append({"name": team_name[t], "values": [bl.get((m, t), 0) for m in months],
                            "color": charts.PALETTE[k], "emphasis": t == "APP"})
    top = max(max(s["values"]) for s in team_series)
    charts.line_chart(
        out_dir / "charts" / "backlog-by-team.svg",
        "Open tickets at month end, by team",
        "Tickets of every type opened and not yet resolved at the end of the month",
        [short_month(m) for m in months], team_series, (0, charts.nice_ticks(0, top)[-1]),
        y_label="open tickets",
        desc="Line chart of the number of open tickets at each month end for each team.")

    tr = d.rows("SELECT team_id, month, resolution_met_pct FROM team_load WHERE month IN (?, ?)",
                (prev or month, month))
    tmap = {(t, m): v for t, m, v in tr}
    labels = [team_name[t] for t in team_ids]
    series = []
    if prev:
        series.append({"name": short_month(prev), "values": [tmap.get((t, prev)) for t in team_ids],
                       "color": charts.PALETTE[5]})
    series.append({"name": short_month(month), "values": [tmap.get((t, month)) for t in team_ids],
                   "color": charts.PALETTE[0]})
    charts.grouped_hbars(
        out_dir / "charts" / "team-resolution.svg",
        "Resolution within target, by team",
        "Incidents and service requests opened in the month, per cent that met their resolution target",
        labels, series, x_max=100.0, target=92.0, target_label="example target 92%",
        value_fmt=lambda v: "%.1f%%" % v,
        desc="Horizontal bar chart of the resolution target result for each team, for %s%s."
             % (long_month(month), (" and " + long_month(prev)) if prev else ""))

    # ----- markdown -----
    L = []
    w = L.append
    w("# Monthly IT service report: %s" % long_month(month))
    w("")
    w("**%s. Board pack, IT service performance.** Prepared by the IT Manager (fictional). "
      "Data extract taken %s UTC." % (GROUP, as_of))
    w("")
    w("> This report is generated from synthetic data by `reports/build_report.py`. The group, "
      "companies, sites and people are invented. Targets shown are examples for this data set.")
    w("")

    w("## 1. Headline")
    w("")
    w("| Measure | %s | %s | Change | Example target | Status |" % (short_month(month), short_month(prev) if prev else "Previous"))
    w("| --- | ---: | ---: | ---: | ---: | --- |")
    for key, label, target, higher, unit in TARGETS:
        c, o = cur[key], old.get(key)
        if key == "csat":
            cell = "n/a" if c is None else "%.2f" % c
            ocell = "n/a" if o is None else "%.2f" % o
            ch = "n/a" if c is None or o is None else ("%+.2f" % (c - o) if round(c - o, 2) else "no change")
            tcell = "%.1f or more" % target
        else:
            cell, ocell, ch = fmt_pct(c), fmt_pct(o), delta(c, o)
            tcell = ("%.0f%% or more" if higher else "%.0f%% or less") % target
        w("| %s | %s | %s | %s | %s | %s |" % (label, cell, ocell, ch, tcell, status(c, target, higher)))
    w("")
    w("| Volume and backlog | %s | %s | Change |" % (short_month(month), short_month(prev) if prev else "Previous"))
    w("| --- | ---: | ---: | ---: |")
    po, pb = old.get("opened"), old.get("backlog")
    w("| Tickets opened | %d | %s | %s |" % (cur["opened"], "n/a" if po is None else po,
                                            "n/a" if not po else "%+.1f%%" % (100.0 * (cur["opened"] - po) / po)))
    w("| Open tickets at month end | %d | %s | %s |" % (cur["backlog"], "n/a" if pb is None else pb,
                                                       "n/a" if pb is None else "%+d" % (cur["backlog"] - pb)))
    w("| Mean time to resolve incidents (support hours) | %s | %s | |" % (
        hours(cur["mttr_minutes"]), hours(old.get("mttr_minutes"))))
    w("")
    w("Three month rolling resolution within target (%s to %s): **%s**. Response: **%s**."
      % (short_month(window[0]), short_month(window[-1]), fmt_pct(rolling_resolution), fmt_pct(rolling_response)))
    w("")
    w("Customer satisfaction is based on %d survey responses this month, from %d resolved tickets. "
      "Resolution figures cover %d measured tickets opened in the month."
      % (cur["csat_responses"], d.one("SELECT COALESCE(SUM(resolved_tickets),0) FROM csat_summary WHERE month = ?", (month,))[0],
         cur["resolution_n"]))
    w("")

    if commentary and Path(commentary).is_file():
        w("## 2. Management commentary")
        w("")
        w("*Hand-written for this fictional example. It is the only part of the report that does not come from the database.*")
        w("")
        w(Path(commentary).read_text(encoding="utf-8").strip())
        w("")
    sec = 3 if commentary and Path(commentary).is_file() else 2

    w("## %d. Service levels" % sec)
    w("")
    w("![Service level performance by month](charts/sla-trend.svg)")
    w("")
    w("Tickets opened in %s, by type and priority:" % long_month(month))
    w("")
    w("| Type | Priority | Measured | Response met | Resolution met | Still in flight |")
    w("| --- | --- | ---: | ---: | ---: | ---: |")
    for t, p, rm_, rmet_, sm_, smet_, fl in d.rows(
            "SELECT ticket_type, priority, SUM(response_measured), SUM(response_met), SUM(resolution_measured),"
            " SUM(resolution_met), SUM(resolution_in_flight) FROM sla_compliance WHERE month = ?"
            " GROUP BY ticket_type, priority ORDER BY ticket_type, priority", (month,)):
        w("| %s | %s | %d | %s | %s | %d |" % (TYPE_LABEL[t], p, sm_, fmt_pct(pct(rmet_, rm_)), fmt_pct(pct(smet_, sm_)), fl))
    w("")
    w("A ticket that is still open and already past its target counts as missed. A ticket still open "
      "and inside its target is shown as in flight and left out of the percentage until it has an outcome.")
    w("")
    w("![Resolution within target by team](charts/team-resolution.svg)")
    w("")

    w("## %d. Teams" % (sec + 1))
    w("")
    w("| Team | Assigned | Resolved | Open at month end | Tickets per FTE | Resolution met |")
    w("| --- | ---: | ---: | ---: | ---: | ---: |")
    for tid, a, r, o, f, m in d.rows(
            "SELECT team_id, assigned_tickets, resolved_tickets, month_end_open, tickets_per_fte, resolution_met_pct"
            " FROM team_load WHERE month = ? ORDER BY team_id", (month,)):
        w("| %s | %d | %d | %d | %.1f | %s |" % (team_name[tid], a, r, o, f, fmt_pct(m)))
    w("")
    w("When assigned exceeds resolved, the team's backlog is growing.")
    w("")
    w("![Open tickets at month end by team](charts/backlog-by-team.svg)")
    w("")

    w("## %d. Demand" % (sec + 2))
    w("")
    w("![Tickets opened per month](charts/volume-by-type.svg)")
    w("")
    w("Top incident categories in %s:" % long_month(month))
    w("")
    w("| Rank | Category | Tickets | Share of incidents | Resolution missed |")
    w("| ---: | --- | ---: | ---: | ---: |")
    for rk, cat, n, sh, br in d.rows(
            "SELECT rank_in_month, category, tickets, share_pct, resolution_breached FROM top_categories"
            " WHERE month = ? AND ticket_type = 'incident' AND rank_in_month <= 5 ORDER BY rank_in_month, category", (month,)):
        w("| %d | %s | %d | %.1f%% | %d |" % (rk, cat, n, sh, br))
    w("")
    w("Busiest weekday over the whole period (average tickets per day): " + ", ".join(
        "%s %.1f" % (name[:3], avg) for name, avg in d.rows(
            "SELECT day_name, avg_tickets_per_day FROM volume_by_weekday ORDER BY day_of_week")) + ".")
    w("")

    w("## %d. Backlog at the extract date" % (sec + 3))
    w("")
    w("| Age of open ticket | Tickets | Of which already past resolution target |")
    w("| --- | ---: | ---: |")
    for b, n, br in d.rows("SELECT age_bucket, SUM(open_tickets), SUM(resolution_breached) FROM backlog_ageing"
                           " GROUP BY age_bucket_order, age_bucket ORDER BY age_bucket_order"):
        w("| %s | %d | %d |" % (b, n, br))
    oldest = d.one("SELECT MAX(oldest_age_days) FROM backlog_ageing")[0]
    w("")
    w("This table is the position at the extract date, whichever month the report covers. "
      "Oldest open ticket: %s days. Problems have no resolution target, so they never count as past target." % oldest)
    w("")

    w("## %d. Quality" % (sec + 4))
    w("")
    w("| Measure | %s | %s |" % (short_month(month), short_month(prev) if prev else "Previous"))
    w("| --- | ---: | ---: |")
    w("| Fixed at first contact | %s | %s |" % (fmt_pct(cur["ftf"]), fmt_pct(old.get("ftf"))))
    w("| Reopened after resolution | %s | %s |" % (fmt_pct(cur["reopen"]), fmt_pct(old.get("reopen"))))
    w("| Satisfaction, average of responses | %s | %s |" % (
        "n/a" if cur["csat"] is None else "%.2f" % cur["csat"],
        "n/a" if old.get("csat") is None else "%.2f" % old["csat"]))
    w("| Satisfaction survey responses | %d | %s |" % (cur["csat_responses"], old.get("csat_responses", "n/a")))
    w("")
    w("Reopen rate for the latest month is provisional: recently resolved tickets have had little time to be reopened.")
    w("")

    w("## %d. Companies" % (sec + 5))
    w("")
    w("| Company | Staff | Tickets opened | Per 100 staff | Resolution met | Open at month end |")
    w("| --- | ---: | ---: | ---: | ---: | ---: |")
    for cid in sorted(company_name):
        staff = d.one("SELECT SUM(headcount) FROM sites WHERE company_id = ?", (cid,))[0]
        opened = d.one("SELECT COALESCE(SUM(opened),0) FROM volume_trend WHERE month = ? AND company_id = ?", (month, cid))[0]
        r = d.sla([month], "AND company_id = ?", (cid,))
        bk = d.one("SELECT COALESCE(SUM(open_tickets),0) FROM backlog_month_end WHERE month = ? AND company_id = ?", (month, cid))[0]
        w("| %s | %d | %d | %.1f | %s | %d |" % (company_name[cid], staff, opened, 100.0 * opened / staff, fmt_pct(pct(r[3], r[2])), bk))
    w("")

    w("## %d. How to read this report" % (sec + 6))
    w("")
    w("- Service level results use the month a ticket was opened. Time to resolve, first contact fix, reopen and satisfaction use the month it was resolved. Volume uses the month opened.")
    w("- Targets count support-hours minutes, except P1 incidents, which run on elapsed time. See [`sql/views/01_fact_ticket.sql`](../sql/views/01_fact_ticket.sql).")
    w("- Percentages are calculated from summed counts, never by averaging percentages.")
    w("- Targets in the headline table are examples for this data set.")
    w("- Definitions and cautions: [`docs/avoiding-vanity-metrics.md`](../docs/avoiding-vanity-metrics.md) and [`docs/ticket-data-quality.md`](../docs/ticket-data-quality.md).")
    w("")
    text = "\n".join(L)
    path = out_dir / ("board-pack-%s.md" % month)
    path.write_text(text, encoding="utf-8")
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m reports.build_report",
                                     description="Build the monthly service report and charts from the SQL views.")
    parser.add_argument("--db", default="build/service_reporting.db", help="database made by sql.loader")
    parser.add_argument("--month", help="report month as YYYY-MM (default: latest month in the data)")
    parser.add_argument("--out", default="reports", help="output folder (default: reports)")
    parser.add_argument("--commentary", help="optional Markdown file with hand-written commentary")
    args = parser.parse_args(argv)
    if not Path(args.db).is_file():
        print("Database not found: %s. Run python -m sql.loader first." % args.db, file=sys.stderr)
        return 2
    conn = sqlite3.connect(args.db)
    try:
        month = args.month or Data(conn).months()[-1]
        commentary = args.commentary
        if commentary is None:
            default = Path(args.out) / ("commentary-%s.md" % month)
            commentary = default if default.is_file() else None
        path = build(conn, month, Path(args.out), commentary)
    except (ValueError, sqlite3.Error) as exc:
        print("Could not build the report: %s" % exc, file=sys.stderr)
        return 2
    finally:
        conn.close()
    print("Wrote %s and 4 charts in %s" % (path, Path(args.out) / "charts"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
