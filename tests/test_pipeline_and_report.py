"""End-to-end run of the whole pipeline, and checks on the report it writes."""

import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from run_pipeline import main as pipeline_main, run

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def pipeline(tmp_path_factory):
    work = tmp_path_factory.mktemp("pipeline")
    result = run(work, commentary=ROOT / "reports" / "commentary-2025-11.md")
    return work, result


def test_pipeline_produces_every_artefact(pipeline):
    work, result = pipeline
    assert (work / "data" / "tickets.csv").is_file()
    assert (work / "build" / "service_reporting.db").is_file()
    assert (work / "model" / "fact_ticket.csv").is_file()
    assert (work / "reports" / "board-pack-2025-11.md").is_file()
    assert len(list((work / "reports" / "charts").glob("*.svg"))) == 4
    assert result["tickets"] > 5000 and result["warnings"] == []


def test_pipeline_output_equals_committed_files(pipeline):
    """The committed data, model, report and charts are exactly what a fresh run produces."""
    work, _ = pipeline
    for rel in ("data/tickets.csv", "data/dim_date.csv", "model/fact_ticket.csv",
                "reports/board-pack-2025-11.md", "reports/charts/sla-trend.svg",
                "reports/charts/volume-by-type.svg", "reports/charts/backlog-by-team.svg",
                "reports/charts/team-resolution.svg"):
        committed = ROOT / rel
        if not committed.is_file():
            pytest.skip("committed file %s not present" % rel)
        assert (work / rel).read_bytes() == committed.read_bytes(), rel


def test_pipeline_twice_gives_identical_bytes(pipeline, tmp_path):
    work, _ = pipeline
    run(tmp_path, commentary=ROOT / "reports" / "commentary-2025-11.md")
    for rel in ("data/tickets.csv", "model/fact_ticket.csv", "reports/board-pack-2025-11.md",
                "reports/charts/sla-trend.svg"):
        assert (work / rel).read_bytes() == (tmp_path / rel).read_bytes(), rel


def test_charts_are_well_formed_svg_with_titles(pipeline):
    work, _ = pipeline
    for svg in sorted((work / "reports" / "charts").glob("*.svg")):
        root = ET.parse(svg).getroot()
        assert root.tag.endswith("svg")
        titles = [e for e in root.iter() if e.tag.endswith("title")]
        descs = [e for e in root.iter() if e.tag.endswith("desc")]
        assert titles and titles[0].text and descs and descs[0].text, svg.name
        assert root.get("role") == "img"


def test_report_headline_numbers_match_the_database(pipeline):
    import sqlite3
    work, _ = pipeline
    text = (work / "reports" / "board-pack-2025-11.md").read_text(encoding="utf-8")
    conn = sqlite3.connect(work / "build" / "service_reporting.db")
    measured, met = conn.execute("SELECT SUM(resolution_measured), SUM(resolution_met) FROM sla_compliance "
                                 "WHERE month = '2025-11'").fetchone()
    expected = "%.1f%%" % round(100.0 * met / measured, 1)
    row = next(l for l in text.splitlines() if l.startswith("| Resolution within target"))
    assert row.split("|")[2].strip() == expected
    opened = conn.execute("SELECT SUM(opened) FROM volume_trend WHERE month = '2025-11'").fetchone()[0]
    assert "| Tickets opened | %d |" % opened in text
    conn.close()


def test_commentary_figures_agree_with_the_tables(pipeline):
    """The hand-written commentary quotes numbers. They must still be true of the data."""
    work, _ = pipeline
    text = (work / "reports" / "board-pack-2025-11.md").read_text(encoding="utf-8")
    teams = next(l for l in text.splitlines() if l.startswith("| Application Support |"))
    cells = [c.strip() for c in teams.split("|")[1:-1]]
    assert cells[5] == "61.5%" and cells[3] == "59"     # resolution met, open at month end
    commentary = (ROOT / "reports" / "commentary-2025-11.md").read_text(encoding="utf-8")
    assert "61.5%" in commentary and "from 21 to 59" in commentary and "92.7%" in commentary
    assert "(51 to 98)" in commentary and "from 4.11 to 2.98" in commentary
    import sqlite3
    conn = sqlite3.connect(work / "build" / "service_reporting.db")
    csat = {m: conn.execute("SELECT ROUND(1.0 * SUM(csat_total) / SUM(responses), 2) FROM csat_summary "
                            "WHERE team_id = 'APP' AND month = ?", (m,)).fetchone()[0] for m in ("2025-10", "2025-11")}
    assert csat == {"2025-10": 4.11, "2025-11": 2.98}
    # "lowest of the twelve months" for both resolution and response
    by_month = conn.execute("SELECT month, 1.0 * SUM(resolution_met) / SUM(resolution_measured), "
                            "1.0 * SUM(response_met) / SUM(response_measured) FROM sla_compliance GROUP BY month").fetchall()
    assert min(by_month, key=lambda r: r[1])[0] == "2025-11" and min(by_month, key=lambda r: r[2])[0] == "2025-11"
    conn.close()
    cats = next(l for l in text.splitlines() if "Business application" in l and l.startswith("| 1 |"))
    assert "| 98 |" in cats
    # Marrowdene Engineering is called the most affected company: it must have the lowest result.
    companies = {}
    for line in text.splitlines():
        m = re.match(r"\| (Fennick Packaging|Quillon Foods|Marrowdene Engineering|Pelham Rook Retail) \|", line)
        if m:
            companies[m.group(1)] = float(line.split("|")[5].strip().rstrip("%"))
    assert min(companies, key=companies.get) == "Marrowdene Engineering"


def test_report_for_another_month_and_bad_month_argument(tmp_path):
    from sql.loader import build_database
    from generator.writer import write_all
    from generator.model import Config
    from reports.build_report import build
    write_all(tmp_path / "data", Config(scale=0.3))
    conn = build_database(tmp_path / "data", tmp_path / "db.sqlite")
    path = build(conn, "2025-06", tmp_path / "out")
    assert path.name == "board-pack-2025-06.md"
    assert "June 2025" in path.read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="not in the data"):
        build(conn, "2019-01", tmp_path / "out")
    conn.close()


def test_report_cli_errors_are_readable(tmp_path):
    out = subprocess.run([sys.executable, "-m", "reports.build_report", "--db", str(tmp_path / "none.db")],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 2 and "Database not found" in out.stderr


def test_pipeline_cli_entry_point(tmp_path):
    out = subprocess.run([sys.executable, "run_pipeline.py", "--workdir", str(tmp_path), "--month", "2025-09"],
                         cwd=ROOT, capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    assert "4/4 Building the monthly report" in out.stdout
    assert (tmp_path / "reports" / "board-pack-2025-09.md").is_file()


def test_pipeline_rejects_a_month_outside_the_data(tmp_path, capsys):
    assert pipeline_main(["--workdir", str(tmp_path), "--month", "2030-01"]) == 2
    assert "not in the data" in capsys.readouterr().err
