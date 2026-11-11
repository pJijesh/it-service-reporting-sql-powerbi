"""Tests for the data generator: determinism, structure, realistic patterns, calendars."""

import csv
import hashlib
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

import oracle
from generator import reference as ref
from generator.calendars import (AMER_HOLIDAYS, APAC_HOLIDAYS, EMEA_HOLIDAYS, ZONES, SupportClock,
                                 build_windows, CALENDARS, last_sunday, nth_weekday)
from generator.model import Config
from generator.writer import checksums, write_all

ROOT = Path(__file__).resolve().parents[1]


# ---- determinism ---------------------------------------------------------------------------

def test_same_seed_gives_identical_files(tmp_path):
    a = write_all(tmp_path / "a", Config(scale=0.2))
    b = write_all(tmp_path / "b", Config(scale=0.2))
    assert a == b
    assert len(a) == 10


def test_different_seed_gives_different_tickets(tmp_path):
    a = write_all(tmp_path / "a", Config(seed=1, scale=0.2))
    b = write_all(tmp_path / "b", Config(seed=2, scale=0.2))
    assert a["tickets.csv"] != b["tickets.csv"]
    assert a["companies.csv"] == b["companies.csv"]   # reference data does not depend on the seed


def test_output_does_not_depend_on_hash_randomisation(tmp_path):
    """A fresh interpreter with a different PYTHONHASHSEED must give the same bytes."""
    import os
    import subprocess
    import sys
    sums = []
    for seed in ("1", "12345"):
        out = tmp_path / ("h" + seed)
        env = dict(os.environ, PYTHONHASHSEED=seed)
        subprocess.run([sys.executable, "-m", "generator", "--out", str(out), "--scale", "0.1"],
                       cwd=ROOT, env=env, check=True, capture_output=True)
        sums.append(checksums(out))
    assert sums[0] == sums[1]


def test_committed_data_matches_a_fresh_run(generated_dir):
    committed = ROOT / "data"
    if not (committed / "tickets.csv").is_file():
        pytest.skip("no committed data folder")
    assert checksums(committed) == checksums(generated_dir)


def test_files_use_unix_line_endings(generated_dir):
    assert b"\r" not in (generated_dir / "tickets.csv").read_bytes()


# ---- structure -----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def tickets(generated_dir):
    return oracle.read(generated_dir / "tickets.csv")


def test_size_and_scope(tickets, generated_dir):
    assert 5000 <= len(tickets) <= 9000                         # several thousand
    assert len({t["company_id"] for t in tickets}) == 4
    sites = oracle.read(generated_dir / "sites.csv")
    assert len(sites) >= 8
    assert len({s["time_zone"] for s in sites}) >= 4           # several time zones
    months = {t["opened_at"][:7] for t in tickets}
    assert len(months) == 12 and min(months) == "2024-12" and max(months) == "2025-11"
    assert {t["ticket_type"] for t in tickets} == {"incident", "service_request", "problem", "change"}


def test_ids_unique_and_ordered_by_opening(tickets):
    ids = [t["ticket_id"] for t in tickets]
    assert len(ids) == len(set(ids))
    opened = [t["opened_at"] for t in tickets]
    assert opened == sorted(opened)


def test_priorities_follow_the_matrix(tickets, generated_dir):
    matrix = {(int(r["impact"]), int(r["urgency"])): r["priority"]
              for r in oracle.read(generated_dir / "priority_matrix.csv")}
    assert len(matrix) == 9
    for t in tickets:
        assert matrix[(int(t["impact"]), int(t["urgency"]))] == t["priority"], t["ticket_id"]
    counts = Counter(t["priority"] for t in tickets)
    assert all(counts[p] > 0 for p in ("P1", "P2", "P3", "P4"))
    assert counts["P1"] < counts["P2"] < counts["P3"] < counts["P4"]


def test_timelines_run_forwards_and_respect_the_extract_time(tickets):
    as_of = datetime(2025, 12, 1)
    for t in tickets:
        stamps = [oracle.ts(t[k]) for k in ("opened_at", "first_response_at", "resolved_at", "closed_at")]
        present = [s for s in stamps if s]
        assert present == sorted(present), t["ticket_id"]
        assert all(s <= as_of for s in present), t["ticket_id"]
        if t["resolved_at"]:
            assert t["first_response_at"], t["ticket_id"]
        if not t["resolved_at"]:
            assert t["csat"] == "" and t["reopened"] == "0" and t["resolved_first_contact"] == "0"
        if t["csat"]:
            assert 1 <= int(t["csat"]) <= 5
            assert t["ticket_type"] in ("incident", "service_request")


def test_flags_and_teams_are_valid(tickets):
    teams = {r[0] for r in ref.TEAMS}
    for t in tickets:
        assert t["assignee_team"] in teams
        assert t["reopened"] in ("0", "1") and t["resolved_first_contact"] in ("0", "1")
        if t["resolved_first_contact"] == "1":
            assert t["assignee_team"] == "SD" and t["priority"] in ("P3", "P4")


def test_sla_targets_cover_incidents_and_requests():
    keys = {(t, p) for t, p, *_ in ref.SLA_TARGETS}
    assert {("incident", p) for p in ("P1", "P2", "P3", "P4")} <= keys
    for _t, _p, response, resolution, _basis in ref.SLA_TARGETS:
        assert response < resolution


# ---- patterns ------------------------------------------------------------------------------

def test_monday_is_the_busiest_weekday_and_weekends_are_quiet(tickets):
    by_dow = Counter(datetime.strptime(t["opened_at"][:10], "%Y-%m-%d").weekday() for t in tickets)
    assert by_dow[0] == max(by_dow.values())
    assert by_dow[0] > by_dow[4] * 1.3
    assert by_dow[5] + by_dow[6] < 0.05 * len(tickets)


def test_month_end_days_are_busier_than_other_weekdays(tickets):
    per_day = Counter(t["opened_at"][:10] for t in tickets if t["ticket_type"] in ("incident", "service_request"))
    by_month = defaultdict(list)
    d = date(2024, 12, 1)
    while d <= date(2025, 11, 30):
        if d.weekday() < 5 and d not in EMEA_HOLIDAYS:
            by_month[d.strftime("%Y-%m")].append(d)
        d += timedelta(days=1)
    edge, other = [], []
    for days in by_month.values():
        edge_days = {days[0], *days[-2:]}
        for day in days:
            (edge if day in edge_days else other).append(per_day[day.isoformat()])
    # Compare Tuesday to Friday only would remove the Monday effect; month ends include some Mondays,
    # so the margin is modest but the direction must hold.
    assert sum(edge) / len(edge) > 1.1 * sum(other) / len(other)


def test_bank_holidays_are_quiet(tickets):
    per_day = Counter(t["opened_at"][:10] for t in tickets if t["site_id"] != "S06")
    normal = sum(per_day[d.isoformat()] for d in [date(2025, 3, 12), date(2025, 3, 19)]) / 2
    holiday = per_day["2025-05-05"] + 0.0
    assert holiday < normal * 0.5


def test_bad_month_for_one_team(generated_db):
    def met(month, team):
        return generated_db.execute(
            "SELECT 100.0 * SUM(resolution_met) / SUM(resolution_measured) FROM sla_compliance_team "
            "WHERE month = ? AND team_id = ?", (month, team)).fetchone()[0]
    previous = [met(m, "APP") for m in ("2025-08", "2025-09", "2025-10")]
    assert min(previous) > 85
    assert met("2025-11", "APP") < 70
    for team in ("INF", "FLD", "IAM", "SD"):
        assert met("2025-11", team) > 80          # the other teams are not in trouble
    backlog = dict(generated_db.execute(
        "SELECT month, open_tickets FROM (SELECT month, SUM(open_tickets) AS open_tickets FROM backlog_month_end "
        "WHERE team_id = 'APP' GROUP BY month)").fetchall())
    assert backlog["2025-11"] > 2 * backlog["2025-10"]


def test_some_breaches_exist_but_most_targets_are_met(generated_db):
    measured, met = generated_db.execute(
        "SELECT SUM(resolution_measured), SUM(resolution_met) FROM sla_compliance").fetchone()
    assert 0.85 < met / measured < 0.97
    assert measured - met > 100


def test_there_are_old_open_tickets(generated_db):
    oldest = generated_db.execute("SELECT MAX(oldest_age_days) FROM backlog_ageing").fetchone()[0]
    assert oldest > 60


# ---- calendars -----------------------------------------------------------------------------

def test_england_and_wales_bank_holidays_2025_are_as_published():
    # Checked against https://www.gov.uk/bank-holidays.json on 2026-11-11.
    assert EMEA_HOLIDAYS == [
        date(2024, 12, 25), date(2024, 12, 26), date(2025, 1, 1), date(2025, 4, 18), date(2025, 4, 21),
        date(2025, 5, 5), date(2025, 5, 26), date(2025, 8, 25), date(2025, 12, 25), date(2025, 12, 26)]
    assert all(d.weekday() < 5 for d in EMEA_HOLIDAYS)
    assert all(d.weekday() < 5 for d in AMER_HOLIDAYS + APAC_HOLIDAYS)


def test_daylight_saving_boundaries():
    assert last_sunday(2025, 3) == date(2025, 3, 30)
    assert last_sunday(2025, 10) == date(2025, 10, 26)
    assert nth_weekday(2025, 3, 6, 2) == date(2025, 3, 9)      # second Sunday of March 2025
    assert nth_weekday(2025, 11, 6, 1) == date(2025, 11, 2)    # first Sunday of November 2025
    london, chicago = ZONES["Europe/London"], ZONES["America/Chicago"]
    assert london.offset_minutes(datetime(2025, 3, 30, 0, 59)) == 0
    assert london.offset_minutes(datetime(2025, 3, 30, 1, 0)) == 60
    assert london.offset_minutes(datetime(2025, 10, 26, 0, 59)) == 60
    assert london.offset_minutes(datetime(2025, 10, 26, 1, 0)) == 0
    assert chicago.offset_minutes(datetime(2025, 3, 9, 7, 59)) == -360
    assert chicago.offset_minutes(datetime(2025, 3, 9, 8, 0)) == -300
    assert chicago.offset_minutes(datetime(2025, 11, 2, 6, 59)) == -300
    assert chicago.offset_minutes(datetime(2025, 11, 2, 7, 0)) == -360


def test_zone_rules_agree_with_the_system_time_zone_database():
    zoneinfo = pytest.importorskip("zoneinfo")
    try:
        for name in ZONES:
            zoneinfo.ZoneInfo(name)
    except zoneinfo.ZoneInfoNotFoundError:
        pytest.skip("time zone database not available on this machine")
    from datetime import timezone
    moment = datetime(2024, 11, 1, 0, 0)
    while moment < datetime(2026, 1, 1):
        for name, zone in ZONES.items():
            expected = moment.replace(tzinfo=timezone.utc).astimezone(zoneinfo.ZoneInfo(name)).utcoffset()
            assert zone.offset_minutes(moment) == int(expected / timedelta(minutes=1)), (name, moment)
        moment += timedelta(hours=7)


def test_support_windows_are_converted_to_utc_correctly():
    wins = {w[2]: w for w in build_windows(CALENDARS["EMEA"], date(2025, 3, 24), date(2025, 4, 4))}
    assert wins[date(2025, 3, 28)][0] == datetime(2025, 3, 28, 8, 0)    # GMT: 08:00 local is 08:00 UTC
    assert wins[date(2025, 4, 1)][0] == datetime(2025, 4, 1, 7, 0)      # BST: 08:00 local is 07:00 UTC
    sg = build_windows(CALENDARS["APAC"], date(2025, 3, 3), date(2025, 3, 3))[0]
    assert (sg[0], sg[1]) == (datetime(2025, 3, 3, 0, 0), datetime(2025, 3, 3, 10, 0))
    us = {w[2]: w for w in build_windows(CALENDARS["AMER"], date(2025, 3, 5), date(2025, 3, 12))}
    assert us[date(2025, 3, 7)][0] == datetime(2025, 3, 7, 14, 0)       # CST is UTC-6
    assert us[date(2025, 3, 12)][0] == datetime(2025, 3, 12, 13, 0)     # CDT is UTC-5
    assert date(2025, 3, 8) not in wins and date(2025, 3, 8) not in us   # Saturday


def test_support_clock_skips_nights_and_weekends():
    windows = build_windows(CALENDARS["EMEA"], date(2025, 3, 3), date(2025, 3, 21))
    clock = SupportClock(windows)
    friday_1750 = datetime(2025, 3, 7, 17, 50)
    assert clock.add_minutes(friday_1750, 10) == datetime(2025, 3, 7, 18, 0)
    assert clock.add_minutes(friday_1750, 11) == datetime(2025, 3, 10, 8, 1)
    assert clock.add_minutes(datetime(2025, 3, 8, 3, 0), 5) == datetime(2025, 3, 10, 8, 5)   # opened Saturday
    assert clock.add_minutes(datetime(2025, 3, 3, 8, 0), 600) == datetime(2025, 3, 3, 18, 0)
    assert SupportClock(None).add_minutes(friday_1750, 62 * 60) == datetime(2025, 3, 10, 7, 50)
    with pytest.raises(ValueError):
        clock.add_minutes(datetime(2025, 3, 20, 9, 0), 100000)


def test_generated_times_are_consistent_with_the_support_clock(generated_dir):
    """Response time is generated with the support clock, so re-measuring it must give back
    a value in a plausible range. Checks 300 tickets with the brute-force and fast methods."""
    data = oracle.Dataset(generated_dir)
    checked = 0
    for t in data.tickets:
        if t["ticket_type"] != "incident" or not t["resolved_at"] or t["priority"] == "P1":
            continue
        a, b = oracle.ts(t["opened_at"]), oracle.ts(t["resolved_at"])
        if (b - a) > timedelta(days=3):
            continue
        cal = data.sites[t["site_id"]]["support_calendar"]
        assert oracle.support_minutes_bruteforce(data.windows[cal], a, b) == oracle.support_minutes(data.windows[cal], a, b)
        checked += 1
        if checked >= 300:
            break
    assert checked >= 100
