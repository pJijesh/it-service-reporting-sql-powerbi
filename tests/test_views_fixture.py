"""Check every view against answers worked out by hand for the fixture in fixture_builder.py.

The expected numbers below were derived on paper from the ticket list, not copied from the SQL output.
Where it helps, the working is shown in a comment.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixture_builder as fb  # noqa: E402
import oracle  # noqa: E402
from sql.loader import build_database  # noqa: E402


@pytest.fixture(scope="module")
def folder(tmp_path_factory):
    return fb.build(tmp_path_factory.mktemp("fixture"))


@pytest.fixture(scope="module")
def db(folder):
    conn = build_database(folder, ":memory:")
    yield conn
    conn.close()


def rows(db, sql, *params):
    return db.execute(sql, params).fetchall()


# ---- the clock -------------------------------------------------------------------------

def test_clock_minutes_match_hand_working(db, folder):
    got = {r[0]: r[1:] for r in rows(
        db, "SELECT ticket_id, response_clock_minutes, resolution_clock_minutes, resolution_elapsed_minutes "
            "FROM fact_ticket")}
    # INC-1: P1 uses elapsed time. 17:00 Friday to 02:00 Saturday is 9 hours = 540 minutes.
    assert got["INC-1"] == (10, 540, 540)
    # INC-3: Friday 17:30 to Tuesday 10:00. Support minutes: Fri 30 + Mon 600 + Tue 120 = 750.
    # Elapsed: 3 days and 16.5 hours = 5310. The weekend is not charged to the clock.
    assert got["INC-3"] == (60, 750, 5310)
    # INC-4: Tuesday 10:00 to Friday 10:00: Tue 480 + Wed 600 + Thu 600 + Fri 120 = 1800.
    assert got["INC-4"][1] == 1800
    # INC-7 is still open at the extract time (Friday 14 March 12:00): 360 + 4*600 + 4*600 + 240 = 5400.
    assert got["INC-7"][1] == 5400
    # INC-8 (Singapore): Friday 09:00 to 10:00 UTC is 60, then Monday 00:00 to 02:00 UTC is 120.
    assert got["INC-8"][1] == 180
    # INC-11: exactly 2400, the target, so it counts as met.
    assert got["INC-11"][1] == 2400
    # Fixture and brute force agree for every ticket. This is the independent oracle.
    data = oracle.Dataset(folder)
    for t in data.tickets:
        m = data.measure(t, fast=False)
        if m:
            assert got[t["ticket_id"]][1] == m["resolution_minutes"], t["ticket_id"]


def test_outcome_states(db):
    got = dict(rows(db, "SELECT ticket_id, response_state || '/' || resolution_state FROM fact_ticket"))
    assert got["INC-1"] == "met/breached"
    assert got["INC-2"] == "breached/met"
    assert got["INC-6"] == "breached/in_flight"   # 360 support minutes against a 30 minute response target
    assert got["INC-7"] == "met/breached"          # open and already far past target: counts as missed
    assert got["INC-11"] == "met/met"
    assert got["PRB-1"] == "not_measured/not_measured"
    assert got["CHG-1"] == "not_measured/not_measured"
    assert got["REQ-3"] == "not_measured/not_measured"  # resolved before opened


# ---- sla_compliance --------------------------------------------------------------------

def test_sla_compliance_all_companies_march(db):
    r = rows(db, "SELECT SUM(response_measured), SUM(response_met), SUM(resolution_measured), "
                 "SUM(resolution_met), SUM(resolution_in_flight) FROM sla_compliance WHERE month = '2025-03'")[0]
    # 12 measured tickets. Response missed: INC-2 and INC-6. Resolution measured 11 (INC-6 in flight);
    # resolution met: INC-2, 3, 5, 9, 10, REQ-1, REQ-2, INC-8 = 8.
    assert r == (12, 10, 11, 8, 1)


def test_sla_compliance_percentages_by_company(db):
    got = {r[0]: r[1:] for r in rows(
        db, "SELECT company_id, SUM(response_measured), SUM(response_met), SUM(resolution_measured), "
            "SUM(resolution_met) FROM sla_compliance WHERE month = '2025-03' GROUP BY company_id")}
    assert got["C01"] == (10, 8, 9, 6)      # resolution 6 of 9 = 66.7%
    assert got["C02"] == (2, 2, 2, 2)       # 100%


def test_sla_compliance_p1_row_and_percent(db):
    r = rows(db, "SELECT response_measured, response_met, response_met_pct, resolution_measured, "
                 "resolution_met, resolution_met_pct FROM sla_compliance "
                 "WHERE month = '2025-03' AND ticket_type = 'incident' AND priority = 'P1'")
    assert r == [(2, 1, 50.0, 2, 1, 50.0)]


def test_sla_compliance_february_boundary_case(db):
    r = rows(db, "SELECT resolution_measured, resolution_met FROM sla_compliance WHERE month = '2025-02'")
    assert r == [(1, 1)]   # INC-11 used exactly 2400 of 2400 minutes


def test_sla_compliance_matches_oracle_for_every_group(db, folder):
    data = oracle.Dataset(folder)
    expected = data.sla_counts(lambda t: (t["opened_at"][:7], t["company_id"], t["ticket_type"], t["priority"]))
    got = {(r[0], r[1], r[2], r[3]): list(r[4:]) for r in rows(
        db, "SELECT month, company_id, ticket_type, priority, response_measured, response_met, "
            "resolution_measured, resolution_met FROM sla_compliance")}
    assert got == expected


def test_sla_compliance_team(db):
    r = rows(db, "SELECT resolution_measured, resolution_met, resolution_met_pct FROM sla_compliance_team "
                 "WHERE month = '2025-03' AND team_id = 'APP' AND ticket_type = 'incident'")
    # INC-3 met, INC-4 breached, INC-6 in flight, INC-7 breached, INC-9 met: 2 of 4.
    assert r == [(4, 2, 50.0)]


# ---- backlog ---------------------------------------------------------------------------

def test_backlog_ageing(db):
    got = rows(db, "SELECT age_bucket, ticket_type, priority, open_tickets, oldest_age_days, resolution_breached "
                   "FROM backlog_ageing ORDER BY age_bucket_order, ticket_type")
    assert got == [
        ("0 to 1 days", "incident", "P2", 1, 0, 0),       # INC-6, 20 hours old, still in flight
        ("11 to 30 days", "incident", "P3", 1, 11, 1),    # INC-7, exactly 11 days, past target
        ("11 to 30 days", "problem", "P3", 1, 11, 0),     # PRB-1, no service level, so never "breached"
    ]


def test_backlog_month_end(db):
    feb = rows(db, "SELECT SUM(open_tickets) FROM backlog_month_end WHERE month = '2025-02'")[0][0]
    mar = rows(db, "SELECT SUM(open_tickets) FROM backlog_month_end WHERE month = '2025-03'")[0][0]
    assert feb == 1   # INC-11 was opened 26 Feb and not resolved until 4 March
    assert mar == 3   # INC-6, INC-7, PRB-1
    by_team = dict(rows(db, "SELECT team_id, SUM(open_tickets) FROM backlog_month_end "
                            "WHERE month = '2025-03' GROUP BY team_id"))
    assert by_team == {"APP": 2, "INF": 1}


def test_backlog_matches_oracle(db, folder):
    data = oracle.Dataset(folder)
    assert len(data.open_at(oracle.ts("2025-03-01T00:00:00Z"))) == 1
    assert len(data.open_at(oracle.ts("2025-04-01T00:00:00Z"))) == 3


# ---- mttr ------------------------------------------------------------------------------

def test_mttr_march(db):
    total, n, mean_clock, mean_elapsed = rows(
        db, "SELECT SUM(total_clock_minutes), SUM(incidents_resolved), "
            "ROUND(1.0 * SUM(total_clock_minutes) / SUM(incidents_resolved), 1), "
            "ROUND(1.0 * SUM(mttr_elapsed_minutes * incidents_resolved) / SUM(incidents_resolved), 1) "
            "FROM mttr WHERE month = '2025-03'")[0]
    # Nine incidents resolved in March: 540 + 120 + 750 + 1800 + 50 + 180 + 360 + 240 + 2400 = 6440.
    assert (total, n, mean_clock) == (6440, 9, 715.6)
    # Elapsed: 540 + 120 + 5310 + 4320 + 50 + 3900 + 360 + 240 + 8640 = 23480, mean 2608.9.
    assert mean_elapsed == 2608.9


def test_mttr_percentiles_nearest_rank(db):
    got = {r[0]: r[1:] for r in rows(
        db, "SELECT priority, incidents_resolved, median_clock_minutes, p90_clock_minutes "
            "FROM mttr_percentiles WHERE month = '2025-03'")}
    assert got["P1"] == (2, 120, 540)       # sorted 120, 540
    assert got["P2"] == (1, 360, 360)
    assert got["P3"] == (3, 750, 1800)      # sorted 50, 750, 1800
    assert got["P4"] == (3, 240, 2400)      # sorted 180, 240, 2400


# ---- first time fix, reopen, csat --------------------------------------------------------

def test_first_time_fix(db):
    got = rows(db, "SELECT ticket_type, resolved_tickets, fixed_first_contact, ftf_pct FROM first_time_fix_rate "
                   "WHERE month = '2025-03' ORDER BY ticket_type, company_id")
    # REQ-3 is excluded (invalid timeline). Incidents resolved in March: 8 for C01 and INC-8 for C02.
    by = {}
    for t, n, f, _p in got:
        a = by.setdefault(t, [0, 0])
        a[0] += n
        a[1] += f
    assert by == {"incident": [9, 1], "service_request": [2, 1]}
    overall = rows(db, "SELECT ROUND(100.0 * SUM(fixed_first_contact) / SUM(resolved_tickets), 1) "
                       "FROM first_time_fix_rate WHERE month = '2025-03'")[0][0]
    assert overall == round(100 * 2 / 11, 1)


def test_reopen_rate(db):
    r = rows(db, "SELECT SUM(resolved_tickets), SUM(reopened_tickets) FROM reopen_rate WHERE month = '2025-03'")[0]
    assert r == (11, 1)   # REQ-1 reopened, out of 11 resolved


def test_csat_summary(db):
    r = rows(db, "SELECT SUM(resolved_tickets), SUM(responses), SUM(csat_total), SUM(satisfied), SUM(dissatisfied) "
                 "FROM csat_summary WHERE month = '2025-03'")[0]
    assert r == (11, 3, 12, 2, 0)       # scores 5, 3, 4: total 12, average 4.0
    one = rows(db, "SELECT 1.0 * SUM(csat_total) / SUM(responses), SUM(satisfied) FROM csat_summary "
                   "WHERE month = '2025-03' AND team_id = 'SD'")[0]
    assert one == (4.5, 2)              # INC-5 scored 5 and REQ-2 scored 4, in two different companies
    c02 = rows(db, "SELECT avg_csat, response_rate_pct FROM csat_summary "
                   "WHERE month = '2025-03' AND company_id = 'C02' AND team_id = 'SD'")[0]
    assert c02 == (4.0, 100.0)


# ---- volume, categories, team load ---------------------------------------------------------

def test_volume_trend_month_on_month(db):
    feb, mar = rows(db, "SELECT opened, resolved, prev_month_opened, mom_change_pct FROM volume_trend "
                        "WHERE company_id = 'C01' AND ticket_type = 'incident' ORDER BY month")
    assert feb == (1, 0, None, None)
    assert mar == (9, 8, 1, 800.0)      # (9 - 1) / 1 * 100


def test_volume_totals_cover_every_ticket(db):
    assert rows(db, "SELECT SUM(opened) FROM volume_trend")[0][0] == len(fb.TICKETS)


def test_volume_by_weekday(db):
    got = dict(rows(db, "SELECT day_name, tickets FROM volume_by_weekday"))
    # Opened on Mondays: INC-2? No. 03-03 is Monday: INC-2, INC-7, PRB-1 (3), 03-10: REQ-2, INC-9, REQ-1 (3) = 6.
    assert got["Monday"] == 6
    assert sum(got.values()) == len(fb.TICKETS)


def test_top_categories(db):
    got = rows(db, "SELECT category, tickets, share_pct, rank_in_month, resolution_breached FROM top_categories "
                   "WHERE month = '2025-03' AND ticket_type = 'incident' ORDER BY rank_in_month")
    assert got == [("Business application", 5, 50.0, 1, 2),
                   ("Network and Wi-Fi", 3, 30.0, 2, 1),
                   ("Password and access", 2, 20.0, 3, 0)]


def test_team_load(db):
    r = rows(db, "SELECT assigned_tickets, resolved_tickets, month_end_open, tickets_per_fte, resolution_met_pct "
                 "FROM team_load WHERE month = '2025-03' AND team_id = 'APP'")
    assert r == [(5, 3, 2, 2.0, 50.0)]  # 5 assigned / 2.5 FTE = 2.0


# ---- data quality ----------------------------------------------------------------------

def test_data_quality_checks_flag_the_bad_row(db):
    failing = dict(rows(db, "SELECT check_name, failing_tickets FROM data_quality_checks"))
    assert failing["resolved before opened"] == 1
    assert failing["first response after resolved"] == 1
    assert sum(v for k, v in failing.items() if v) == 2


def test_bad_row_is_excluded_from_all_measures(db):
    assert rows(db, "SELECT timeline_ok, response_measured, resolution_measured FROM fact_ticket "
                    "WHERE ticket_id = 'REQ-3'") == [(0, 0, 0)]
