"""Loader behaviour on bad input: every problem is listed with its file and line, nothing is half loaded."""

import csv
import subprocess
import sys
from pathlib import Path

import pytest

import fixture_builder as fb
from sql.loader import InputError, build_database, main, validate

ROOT = Path(__file__).resolve().parents[1]


def rewrite(folder, filename, edit):
    path = Path(folder) / filename
    with open(path, newline="", encoding="utf-8") as h:
        rows = list(csv.reader(h))
    edit(rows)
    with open(path, "w", newline="", encoding="utf-8") as h:
        csv.writer(h, lineterminator="\n").writerows(rows)


def problems(folder):
    with pytest.raises(InputError) as info:
        validate(folder)
    return info.value.problems


@pytest.fixture()
def folder(tmp_path):
    return fb.build(tmp_path / "in")


def test_clean_fixture_loads(folder):
    conn = build_database(folder, ":memory:")
    assert conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == len(fb.TICKETS)
    conn.close()


def test_timestamps_are_stored_as_utc_text(folder):
    conn = build_database(folder, ":memory:")
    assert conn.execute("SELECT opened_at FROM tickets WHERE ticket_id = 'INC-1'").fetchone()[0] == "2025-03-07 17:00:00"
    conn.close()


def test_missing_file_is_reported(folder):
    (folder / "sla_targets.csv").unlink()
    assert any("sla_targets.csv: file not found" in p for p in problems(folder))


def test_missing_column_is_reported(folder):
    rewrite(folder, "tickets.csv", lambda rows: [r.pop(8) for r in rows])   # drop opened_at
    assert any("missing column(s) opened_at" in p for p in problems(folder))


def test_bad_timestamp_gives_line_number_and_reason(folder):
    def edit(rows):
        rows[3][8] = "2025-03-07 17:00"          # line 4 of the file
    rewrite(folder, "tickets.csv", edit)
    found = problems(folder)
    assert any("tickets.csv line 4, column opened_at" in p and "YYYY-MM-DDTHH:MM:SSZ" in p for p in found)


def test_impossible_date_is_reported(folder):
    def edit(rows):
        rows[1][8] = "2025-02-30T10:00:00Z"
    rewrite(folder, "tickets.csv", edit)
    assert any("not a real date" in p for p in problems(folder))


def test_bad_enum_flag_and_score_are_reported_together(folder):
    def edit(rows):
        rows[1][1] = "ticket"       # type
        rows[2][12] = "yes"         # reopened
        rows[3][15] = "9"           # csat
    rewrite(folder, "tickets.csv", edit)
    found = problems(folder)
    assert len(found) == 3
    assert any("line 2, column ticket_type" in p for p in found)
    assert any("line 3, column reopened" in p for p in found)
    assert any("line 4, column csat: 9 is outside 1 to 5" in p for p in found)


def test_unknown_references_are_reported(folder):
    def edit(rows):
        rows[1][2] = "C99"
        rows[2][3] = "S9"
        rows[3][14] = "XXX"
    rewrite(folder, "tickets.csv", edit)
    found = problems(folder)
    assert any("unknown company_id 'C99'" in p for p in found)
    assert any("unknown site_id 'S9'" in p for p in found)
    assert any("unknown assignee_team 'XXX'" in p for p in found)


def test_site_in_wrong_company_is_reported(folder):
    rewrite(folder, "tickets.csv", lambda rows: rows[1].__setitem__(2, "C02"))
    assert any("belongs to company C01, not C02" in p for p in problems(folder))


def test_duplicate_ticket_id_is_reported(folder):
    rewrite(folder, "tickets.csv", lambda rows: rows[2].__setitem__(0, rows[1][0]))
    assert any("duplicate ticket_id INC-1 (first seen on line 2)" in p for p in problems(folder))


def test_wrong_field_count_is_reported(folder):
    rewrite(folder, "tickets.csv", lambda rows: rows[4].append("extra"))
    assert any("tickets.csv line 5: expected 16 fields, found 17" in p for p in problems(folder))


def test_empty_file_is_reported(folder):
    (folder / "teams.csv").write_text("")
    assert any("teams.csv: file is empty" in p for p in problems(folder))


def test_logical_problems_load_but_are_flagged(folder):
    """A resolved-before-opened row is a data quality finding, not a load failure."""
    conn = build_database(folder, ":memory:")
    from sql.loader import data_quality_warnings
    warnings = data_quality_warnings(conn)
    assert "resolved before opened: 1 ticket(s)" in warnings
    conn.close()


def test_existing_database_is_replaced_not_appended(folder, tmp_path):
    db = tmp_path / "x.db"
    build_database(folder, db).close()
    conn = build_database(folder, db)
    assert conn.execute("SELECT COUNT(*) FROM tickets").fetchone()[0] == len(fb.TICKETS)
    conn.close()


def test_cli_exits_2_and_prints_every_problem(folder, tmp_path, capsys):
    rewrite(folder, "tickets.csv", lambda rows: rows[1].__setitem__(8, "yesterday"))
    code = main(["--data", str(folder), "--db", str(tmp_path / "x.db")])
    err = capsys.readouterr().err
    assert code == 2
    assert "Input problems (1):" in err and "tickets.csv line 2, column opened_at" in err
    assert not (tmp_path / "x.db").exists()      # nothing half written


def test_cli_runs_as_a_module_and_exports_the_model(folder, tmp_path):
    out = subprocess.run(
        [sys.executable, "-m", "sql.loader", "--data", str(folder), "--db", str(tmp_path / "m.db"),
         "--export-model", str(tmp_path / "model")], cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "Loaded 16 tickets" in out.stdout
    with open(tmp_path / "model" / "fact_ticket.csv", newline="", encoding="utf-8") as h:
        rows = list(csv.DictReader(h))
    assert len(rows) == 16
    inc1 = next(r for r in rows if r["ticket_id"] == "INC-1")
    assert inc1["opened_at"] == "2025-03-07T17:00:00Z" and inc1["resolution_state"] == "breached"
    assert inc1["first_response_at"] == "2025-03-07T17:10:00Z"
    inc6 = next(r for r in rows if r["ticket_id"] == "INC-6")
    assert inc6["resolved_at"] == ""
