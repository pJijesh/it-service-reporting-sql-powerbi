"""Load the CSV files into SQLite, check them, and create the reporting views.

    python -m sql.loader --data data --db build/service_reporting.db
    python -m sql.loader --data data --db build/service_reporting.db --export-model model

Bad input stops the load with every problem listed (file, line and reason) and exit
status 2. Nothing is written to the database until the whole input has been checked.
Standard library only.
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAX_ERRORS_PER_FILE = 25

TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class InputError(Exception):
    """Raised when the CSV files cannot be loaded. ``problems`` is a list of strings."""

    def __init__(self, problems):
        super().__init__("%d problem(s) found in the input" % len(problems))
        self.problems = problems


# Converters take the raw text and return the value to store, or raise ValueError.
def _text(v):
    if v == "":
        raise ValueError("must not be blank")
    return v


def _opt_text(v):
    return v if v != "" else None


def _int(v):
    try:
        return int(v)
    except ValueError:
        raise ValueError("%r is not a whole number" % v) from None


def _opt_int(v):
    return None if v == "" else _int(v)


def _float(v):
    try:
        return float(v)
    except ValueError:
        raise ValueError("%r is not a number" % v) from None


def _flag(v):
    if v not in ("0", "1"):
        raise ValueError("%r is not 0 or 1" % v)
    return int(v)


def _date(v):
    try:
        return date.fromisoformat(v).isoformat()
    except ValueError:
        raise ValueError("%r is not a date in the form YYYY-MM-DD" % v) from None


def _ts(v):
    """UTC timestamp in the form 2025-03-04T09:15:00Z, stored as 2025-03-04 09:15:00."""
    if not TS_RE.match(v):
        raise ValueError("%r is not a UTC timestamp in the form YYYY-MM-DDTHH:MM:SSZ" % v)
    try:
        datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise ValueError("%r is not a real date and time" % v) from None
    return v[:10] + " " + v[11:19]


def _opt_ts(v):
    return None if v == "" else _ts(v)


def _enum(*allowed):
    def convert(v):
        if v not in allowed:
            raise ValueError("%r is not one of %s" % (v, ", ".join(allowed)))
        return v
    return convert


def _int_range(lo, hi):
    def convert(v):
        n = _int(v)
        if not lo <= n <= hi:
            raise ValueError("%d is outside %d to %d" % (n, lo, hi))
        return n
    return convert


def _opt_int_range(lo, hi):
    inner = _int_range(lo, hi)
    return lambda v: None if v == "" else inner(v)


PRIORITY = _enum("P1", "P2", "P3", "P4")

# (table, file, [(column, converter), ...]) in the order tables must be loaded.
SPECS = [
    ("extract_info", "extract_info.csv", [
        ("group_name", _text), ("period_start", _date), ("period_end", _date),
        ("as_of_utc", _ts), ("seed", _opt_int), ("generator_version", _opt_text)]),
    ("companies", "companies.csv", [
        ("company_id", _text), ("company_name", _text), ("sector", _text)]),
    ("support_calendars", "support_calendars.csv", [
        ("calendar_code", _text), ("calendar_name", _text), ("time_zone", _text),
        ("open_local", _text), ("close_local", _text), ("note", _opt_text)]),
    ("support_windows", "support_windows.csv", [
        ("calendar_code", _text), ("local_date", _date), ("open_utc", _ts), ("close_utc", _ts)]),
    ("sites", "sites.csv", [
        ("site_id", _text), ("company_id", _text), ("site_name", _text), ("country", _text),
        ("time_zone", _text), ("support_calendar", _text), ("headcount", _int_range(0, 10**6))]),
    ("teams", "teams.csv", [
        ("team_id", _text), ("team_name", _text), ("fte", _float), ("description", _opt_text)]),
    ("priority_matrix", "priority_matrix.csv", [
        ("impact", _int_range(1, 3)), ("urgency", _int_range(1, 3)), ("priority", PRIORITY),
        ("priority_name", _text)]),
    ("sla_targets", "sla_targets.csv", [
        ("ticket_type", _enum("incident", "service_request")), ("priority", PRIORITY),
        ("response_target_minutes", _int_range(1, 10**7)),
        ("resolution_target_minutes", _int_range(1, 10**7)),
        ("clock_basis", _enum("24X7", "SUPPORT_HOURS"))]),
    ("dim_date", "dim_date.csv", [
        ("date_key", _int), ("date", _date), ("year", _int), ("quarter", _int),
        ("month_number", _int), ("month_name", _text), ("year_month", _text),
        ("month_start", _date), ("week_start", _date), ("day_of_week", _int_range(1, 7)),
        ("day_name", _text), ("is_weekend", _flag), ("is_uk_bank_holiday", _flag),
        ("is_uk_working_day", _flag)]),
    ("tickets", "tickets.csv", [
        ("ticket_id", _text),
        ("ticket_type", _enum("incident", "service_request", "problem", "change")),
        ("company_id", _text), ("site_id", _text), ("category", _text), ("priority", PRIORITY),
        ("impact", _int_range(1, 3)), ("urgency", _int_range(1, 3)), ("opened_at", _ts),
        ("first_response_at", _opt_ts), ("resolved_at", _opt_ts), ("closed_at", _opt_ts),
        ("reopened", _flag), ("resolved_first_contact", _flag), ("assignee_team", _text),
        ("csat", _opt_int_range(1, 5))]),
]


def read_table(data_dir: Path, filename: str, columns):
    """Read one CSV and convert every row. Returns (rows, problems)."""
    path = data_dir / filename
    if not path.is_file():
        return [], ["%s: file not found in %s" % (filename, data_dir)]
    problems, rows = [], []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        header = next(reader, None)
        if header is None:
            return [], ["%s: file is empty" % filename]
        header = [h.strip() for h in header]
        names = [c for c, _ in columns]
        missing = [n for n in names if n not in header]
        if missing:
            return [], ["%s: missing column(s) %s" % (filename, ", ".join(missing))]
        index = {n: header.index(n) for n in names}
        for line_no, raw in enumerate(reader, start=2):
            if not raw or all(cell.strip() == "" for cell in raw):
                continue
            if len(raw) != len(header):
                problems.append("%s line %d: expected %d fields, found %d"
                                % (filename, line_no, len(header), len(raw)))
                continue
            values = []
            for name, convert in columns:
                try:
                    values.append(convert(raw[index[name]].strip()))
                except ValueError as exc:
                    problems.append("%s line %d, column %s: %s" % (filename, line_no, name, exc))
                    values.append(None)
            rows.append((line_no, values))
            if len(problems) >= MAX_ERRORS_PER_FILE:
                problems.append("%s: stopped after %d problems" % (filename, MAX_ERRORS_PER_FILE))
                break
    return rows, problems


def check_references(tables) -> list:
    """Cross-file checks with line numbers: duplicate IDs and unknown references."""
    problems = []

    def col(table, name):
        names = [c for c, _ in next(s[2] for s in SPECS if s[0] == table)]
        return names.index(name)

    def keys(table, name):
        i = col(table, name)
        return {r[i] for _ln, r in tables[table]}

    companies, teams = keys("companies", "company_id"), keys("teams", "team_id")
    calendars, sites = keys("support_calendars", "calendar_code"), keys("sites", "site_id")
    site_company = {r[0]: r[1] for _ln, r in tables["sites"]}

    for _ln, r in tables["sites"]:
        if r[1] not in companies:
            problems.append("sites.csv line %d: unknown company_id %r" % (_ln, r[1]))
        if r[5] not in calendars:
            problems.append("sites.csv line %d: unknown support_calendar %r" % (_ln, r[5]))
    for _ln, r in tables["support_windows"]:
        if r[0] not in calendars:
            problems.append("support_windows.csv line %d: unknown calendar_code %r" % (_ln, r[0]))

    seen = {}
    t_names = [c for c, _ in SPECS[-1][2]]
    for ln, r in tables["tickets"]:
        row = dict(zip(t_names, r))
        if row["ticket_id"] in seen:
            problems.append("tickets.csv line %d: duplicate ticket_id %s (first seen on line %d)"
                            % (ln, row["ticket_id"], seen[row["ticket_id"]]))
        seen[row["ticket_id"]] = ln
        if row["company_id"] not in companies:
            problems.append("tickets.csv line %d: unknown company_id %r" % (ln, row["company_id"]))
        if row["site_id"] not in sites:
            problems.append("tickets.csv line %d: unknown site_id %r" % (ln, row["site_id"]))
        elif site_company[row["site_id"]] != row["company_id"]:
            problems.append("tickets.csv line %d: site %s belongs to company %s, not %s"
                            % (ln, row["site_id"], site_company[row["site_id"]], row["company_id"]))
        if row["assignee_team"] not in teams:
            problems.append("tickets.csv line %d: unknown assignee_team %r" % (ln, row["assignee_team"]))
        if len(problems) > 200:
            problems.append("stopped checking references after 200 problems")
            break
    if len(tables["extract_info"]) != 1:
        problems.append("extract_info.csv: expected exactly one data row")
    return problems


def validate(data_dir) -> dict:
    """Read and check every file. Raises InputError listing all problems found."""
    data_dir = Path(data_dir)
    tables, problems = {}, []
    for table, filename, columns in SPECS:
        rows, errs = read_table(data_dir, filename, columns)
        tables[table] = rows
        problems.extend(errs)
    if not problems:
        problems.extend(check_references(tables))
    if problems:
        raise InputError(problems)
    return tables


def _run_script(conn, path: Path) -> None:
    conn.executescript(path.read_text(encoding="utf-8"))


def build_database(data_dir, db_path) -> sqlite3.Connection:
    """Create a fresh database from the CSV files. Returns an open connection."""
    tables = validate(data_dir)
    db_path = Path(db_path)
    if str(db_path) != ":memory:":
        db_path.parent.mkdir(parents=True, exist_ok=True)
        if db_path.exists():
            db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    try:
        _run_script(conn, HERE / "schema.sql")
        for table, _filename, columns in SPECS:
            marks = ", ".join("?" for _ in columns)
            names = ", ".join(c for c, _ in columns)
            conn.executemany("INSERT INTO %s (%s) VALUES (%s)" % (table, names, marks),
                             [values for _ln, values in tables[table]])
        for view_file in sorted((HERE / "views").glob("*.sql")):
            _run_script(conn, view_file)
        conn.commit()
    except sqlite3.Error as exc:
        conn.close()
        raise InputError(["database rejected the data: %s" % exc]) from exc
    return conn


def data_quality_warnings(conn) -> list:
    rows = conn.execute("SELECT check_name, failing_tickets FROM data_quality_checks "
                        "WHERE failing_tickets > 0 ORDER BY check_name").fetchall()
    return ["%s: %d ticket(s)" % (name, n) for name, n in rows]


def export_model(conn, out_dir) -> Path:
    """Write fact_ticket to CSV for the Power BI model. UTC timestamps in ISO 8601 form."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    cursor = conn.execute("SELECT * FROM fact_ticket ORDER BY opened_at, ticket_id")
    columns = [d[0] for d in cursor.description]
    ts_cols = {"opened_at", "first_response_at", "resolved_at", "closed_at"}
    path = out / "fact_ticket.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(columns)
        for row in cursor:
            writer.writerow([
                (v[:10] + "T" + v[11:] + "Z") if (c in ts_cols and v) else ("" if v is None else v)
                for c, v in zip(columns, row)])
    return path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m sql.loader",
        description="Load service desk CSV files into SQLite and create the reporting views.")
    parser.add_argument("--data", default="data", help="folder holding the CSV files (default: data)")
    parser.add_argument("--db", default="build/service_reporting.db",
                        help="database file to create, replacing any existing file")
    parser.add_argument("--export-model", metavar="DIR",
                        help="also write fact_ticket.csv, the Power BI fact table, to DIR")
    args = parser.parse_args(argv)
    try:
        conn = build_database(args.data, args.db)
    except InputError as exc:
        print("Input problems (%d):" % len(exc.problems), file=sys.stderr)
        for problem in exc.problems:
            print("  - " + problem, file=sys.stderr)
        return 2
    with conn:
        n_tickets = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]
        n_views = conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE type = 'view'").fetchone()[0]
        print("Loaded %d tickets and created %d views in %s" % (n_tickets, n_views, args.db))
        for warning in data_quality_warnings(conn):
            print("Data quality warning: " + warning)
        if args.export_model:
            print("Wrote " + str(export_model(conn, args.export_model)))
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
