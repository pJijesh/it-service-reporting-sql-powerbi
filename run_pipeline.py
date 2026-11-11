"""Run the whole pipeline: generate data, load SQLite, export the Power BI fact table, build the report.

    python run_pipeline.py                       # writes data/, build/, model/ and reports/ here
    python run_pipeline.py --workdir /tmp/run    # writes them under another folder
    python run_pipeline.py --month 2025-06       # report for a different month

Standard library only. Exit status is 0 on success and 2 on bad input.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from generator.model import DEFAULT_SEED, Config
from generator.writer import write_all
from reports.build_report import Data, build
from sql.loader import InputError, build_database, data_quality_warnings, export_model


def run(workdir: Path, seed: int = DEFAULT_SEED, month: str | None = None, commentary=None,
        report_dir: Path | None = None) -> dict:
    workdir = Path(workdir)
    data_dir, db_path, model_dir = workdir / "data", workdir / "build" / "service_reporting.db", workdir / "model"
    report_dir = Path(report_dir) if report_dir else workdir / "reports"

    print("1/4 Generating synthetic data (seed %d) in %s" % (seed, data_dir))
    write_all(data_dir, Config(seed=seed))

    print("2/4 Loading %s into SQLite and creating views" % data_dir)
    conn = build_database(data_dir, db_path)
    try:
        warnings = data_quality_warnings(conn)
        for w in warnings:
            print("    data quality warning: " + w)
        n = conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0]

        print("3/4 Exporting the Power BI fact table to %s" % model_dir)
        fact = export_model(conn, model_dir)

        print("4/4 Building the monthly report in %s" % report_dir)
        month = month or Data(conn).months()[-1]
        if commentary is None:
            default = report_dir / ("commentary-%s.md" % month)
            commentary = default if default.is_file() else None
        report = build(conn, month, report_dir, commentary)
    finally:
        conn.close()
    print("Done: %d tickets, report %s" % (n, report))
    return {"tickets": n, "database": db_path, "fact": fact, "report": report, "warnings": warnings}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Run the whole service reporting pipeline.")
    parser.add_argument("--workdir", default=".", help="folder to write data/, build/, model/ and reports/ into")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="random seed (default: %d)" % DEFAULT_SEED)
    parser.add_argument("--month", help="report month as YYYY-MM (default: latest month)")
    parser.add_argument("--commentary", help="Markdown file with hand-written commentary for the report")
    args = parser.parse_args(argv)
    try:
        run(Path(args.workdir), args.seed, args.month, args.commentary)
    except InputError as exc:
        print("Input problems:", file=sys.stderr)
        for p in exc.problems:
            print("  - " + p, file=sys.stderr)
        return 2
    except ValueError as exc:
        print("Error: %s" % exc, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
