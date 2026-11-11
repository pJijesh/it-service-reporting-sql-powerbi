"""Cross-check the SQL views on the full generated data set against independent Python."""

from collections import defaultdict
from datetime import timedelta

import pytest

import oracle


@pytest.fixture(scope="module")
def data(generated_dir):
    return oracle.Dataset(generated_dir)


def q(db, sql, *params):
    return db.execute(sql, params).fetchall()


def test_every_ticket_support_minute_count_matches_python(generated_db, data):
    """SQL and Python agree on the resolution clock for every measured ticket."""
    sql = {r[0]: r[1] for r in q(generated_db, "SELECT ticket_id, resolution_clock_minutes FROM fact_ticket "
                                                "WHERE has_sla = 1 AND timeline_ok = 1")}
    checked = 0
    for t in data.tickets:
        m = data.measure(t)
        if m is None:
            continue
        assert sql[t["ticket_id"]] == m["resolution_minutes"], t["ticket_id"]
        checked += 1
    assert checked > 4000 and checked == len(sql)


def test_outcome_states_match_python(generated_db, data):
    sql = {r[0]: (r[1], r[2]) for r in q(generated_db, "SELECT ticket_id, response_state, resolution_state "
                                                       "FROM fact_ticket WHERE has_sla = 1")}
    for t in data.tickets:
        m = data.measure(t)
        if m:
            assert sql[t["ticket_id"]] == (m["response"], m["resolution"]), t["ticket_id"]


def test_sla_compliance_matches_python_for_every_group(generated_db, data):
    expected = data.sla_counts(lambda t: (t["opened_at"][:7], t["company_id"], t["ticket_type"], t["priority"]))
    got = {r[:4]: list(r[4:]) for r in q(
        generated_db, "SELECT month, company_id, ticket_type, priority, response_measured, response_met, "
                      "resolution_measured, resolution_met FROM sla_compliance")}
    assert got == expected


def test_team_sla_matches_python(generated_db, data):
    expected = data.sla_counts(lambda t: (t["opened_at"][:7], t["assignee_team"], t["ticket_type"]))
    got = {r[:3]: list(r[3:]) for r in q(
        generated_db, "SELECT month, team_id, ticket_type, response_measured, response_met, "
                      "resolution_measured, resolution_met FROM sla_compliance_team")}
    assert got == expected


def test_p1_uses_elapsed_time_and_others_use_support_hours(generated_db):
    pairs = q(generated_db, "SELECT DISTINCT clock_basis, priority FROM fact_ticket WHERE has_sla = 1")
    assert ("24X7", "P1") in pairs and ("SUPPORT_HOURS", "P1") not in pairs
    assert all(basis == "SUPPORT_HOURS" for basis, priority in pairs if priority != "P1")
    bad = q(generated_db, "SELECT COUNT(*) FROM fact_ticket WHERE clock_basis = '24X7' AND "
                          "resolution_clock_minutes <> resolution_elapsed_minutes")[0][0]
    assert bad == 0
    shorter = q(generated_db, "SELECT COUNT(*) FROM fact_ticket WHERE clock_basis = 'SUPPORT_HOURS' AND "
                              "resolution_support_minutes > resolution_elapsed_minutes")[0][0]
    assert shorter == 0   # support minutes can never exceed elapsed minutes


def test_backlog_month_end_matches_python(generated_db, data):
    months = [r[0] for r in q(generated_db, "SELECT DISTINCT year_month FROM dim_date ORDER BY 1")]
    for month in months:
        year, mon = int(month[:4]), int(month[5:])
        boundary = oracle.datetime(year + (mon == 12), mon % 12 + 1, 1)
        expected = len(data.open_at(boundary))
        got = q(generated_db, "SELECT COALESCE(SUM(open_tickets), 0) FROM backlog_month_end WHERE month = ?", month)[0][0]
        assert got == expected, month
    # The last month end is the extract time, so it must equal the open ticket count.
    open_now = q(generated_db, "SELECT COUNT(*) FROM tickets WHERE resolved_at IS NULL")[0][0]
    assert open_now == q(generated_db, "SELECT SUM(open_tickets) FROM backlog_month_end WHERE month = ?",
                         months[-1])[0][0]
    assert open_now == q(generated_db, "SELECT SUM(open_tickets) FROM backlog_ageing")[0][0]


def test_backlog_ageing_buckets_match_python(generated_db, data):
    expected = defaultdict(int)
    for t in data.tickets:
        if not t["resolved_at"]:
            days = int((data.as_of - oracle.ts(t["opened_at"])) / timedelta(days=1))
            bucket = ("0 to 1 days" if days < 2 else "2 to 5 days" if days < 6 else "6 to 10 days"
                      if days < 11 else "11 to 30 days" if days < 31 else "Over 30 days")
            expected[bucket] += 1
    got = dict(q(generated_db, "SELECT age_bucket, SUM(open_tickets) FROM backlog_ageing GROUP BY age_bucket"))
    assert got == dict(expected)


def test_mttr_matches_python(generated_db, data):
    totals = defaultdict(lambda: [0, 0])
    for t in data.tickets:
        m = data.measure(t)
        if m and t["ticket_type"] == "incident" and t["resolved_at"]:
            a = totals[(t["resolved_at"][:7], t["company_id"], t["assignee_team"], t["priority"])]
            a[0] += 1
            a[1] += m["resolution_minutes"]
    got = {r[:4]: [r[4], r[5]] for r in q(generated_db, "SELECT month, company_id, team_id, priority, "
                                                         "incidents_resolved, total_clock_minutes FROM mttr")}
    assert got == dict(totals)


def test_percentiles_match_python_nearest_rank(generated_db, data):
    import math
    groups = defaultdict(list)
    for t in data.tickets:
        m = data.measure(t)
        if m and t["ticket_type"] == "incident" and t["resolved_at"]:
            groups[(t["resolved_at"][:7], t["priority"])].append(m["resolution_minutes"])
    got = {r[:2]: r[2:] for r in q(generated_db, "SELECT month, priority, incidents_resolved, median_clock_minutes, "
                                                  "p90_clock_minutes FROM mttr_percentiles")}
    assert set(got) == set(groups)
    for key, values in groups.items():
        values.sort()
        n = len(values)
        assert got[key] == (n, values[math.ceil(0.5 * n) - 1], values[math.ceil(0.9 * n) - 1]), key


def test_quality_views_match_python(generated_db, data):
    resolved = [t for t in data.tickets if t["resolved_at"] and t["ticket_type"] in ("incident", "service_request")
                and data.measure(t) is not None]
    month = "2025-05"
    sub = [t for t in resolved if t["resolved_at"][:7] == month]
    ftf = q(generated_db, "SELECT SUM(resolved_tickets), SUM(fixed_first_contact) FROM first_time_fix_rate "
                          "WHERE month = ?", month)[0]
    assert ftf == (len(sub), sum(int(t["resolved_first_contact"]) for t in sub))
    reopen = q(generated_db, "SELECT SUM(resolved_tickets), SUM(reopened_tickets) FROM reopen_rate WHERE month = ?", month)[0]
    assert reopen == (len(sub), sum(int(t["reopened"]) for t in sub))
    csat = q(generated_db, "SELECT SUM(responses), SUM(csat_total) FROM csat_summary WHERE month = ?", month)[0]
    scores = [int(t["csat"]) for t in sub if t["csat"]]
    assert csat == (len(scores), sum(scores))


def test_volume_and_weekday_views_reconcile(generated_db, data):
    total = len(data.tickets)
    assert q(generated_db, "SELECT SUM(opened) FROM volume_trend")[0][0] == total
    assert q(generated_db, "SELECT SUM(tickets) FROM volume_by_weekday")[0][0] == total
    resolved = sum(1 for t in data.tickets if t["resolved_at"])
    assert q(generated_db, "SELECT SUM(resolved) FROM volume_trend")[0][0] == resolved
    # Month on month: recompute one series.
    series = q(generated_db, "SELECT month, opened, prev_month_opened, mom_change_pct FROM volume_trend "
                             "WHERE company_id = 'C01' AND ticket_type = 'incident' ORDER BY month")
    for (m1, o1, _p, _c), (m2, o2, p2, c2) in zip(series, series[1:]):
        assert p2 == o1
        assert c2 == round(100.0 * (o2 - o1) / o1, 1)
    assert series[0][2] is None


def test_top_categories_ranks_and_shares(generated_db):
    for month, ttype, share_total, first in q(
            generated_db, "SELECT month, ticket_type, ROUND(SUM(share_pct)), MIN(rank_in_month) FROM top_categories "
                          "GROUP BY month, ticket_type"):
        assert 99 <= share_total <= 101 and first == 1
    tickets = q(generated_db, "SELECT SUM(tickets) FROM top_categories")[0][0]
    assert tickets == q(generated_db, "SELECT COUNT(*) FROM tickets")[0][0]


def test_team_load_reconciles_with_other_views(generated_db):
    assigned = q(generated_db, "SELECT SUM(assigned_tickets) FROM team_load")[0][0]
    assert assigned == q(generated_db, "SELECT COUNT(*) FROM tickets")[0][0]
    assert q(generated_db, "SELECT COUNT(*) FROM team_load")[0][0] == 12 * 5
    # A team with a growing backlog has assigned > resolved over time.
    for team, a, r, end_open in q(
            generated_db, "SELECT team_id, SUM(assigned_tickets), SUM(resolved_tickets), "
                          "(SELECT month_end_open FROM team_load x WHERE x.team_id = t.team_id AND x.month = '2025-11') "
                          "FROM team_load t GROUP BY team_id"):
        assert a - r == end_open, team   # tickets in minus tickets out equals the open count at the end


def test_data_quality_is_clean_for_generated_data(generated_db):
    assert q(generated_db, "SELECT * FROM data_quality_checks WHERE failing_tickets > 0") == []


def test_views_are_readable_without_errors(generated_db):
    names = [r[0] for r in q(generated_db, "SELECT name FROM sqlite_master WHERE type = 'view' ORDER BY name")]
    assert len(names) >= 15
    for name in names:
        generated_db.execute("SELECT * FROM %s LIMIT 1" % name).fetchall()
