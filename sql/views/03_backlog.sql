-- Backlog views. Backlog means tickets not yet resolved (not "not yet closed").
-- A resolved ticket waiting for its automatic closure is finished work.

-- backlog_ageing: the open backlog at the extract time, by age.
-- Age is calendar days since opening. Support-hours age would be fairer to a ticket
-- raised before a weekend, but board members read calendar days without explanation.
-- resolution_breached counts open tickets that are already past their resolution
-- target (only incidents and service requests have one).
CREATE VIEW backlog_ageing AS
WITH bucketed AS (
    SELECT
        CASE WHEN f.open_age_days < 2  THEN 1
             WHEN f.open_age_days < 6  THEN 2
             WHEN f.open_age_days < 11 THEN 3
             WHEN f.open_age_days < 31 THEN 4
             ELSE 5 END                                  AS age_bucket_order,
        CASE WHEN f.open_age_days < 2  THEN '0 to 1 days'
             WHEN f.open_age_days < 6  THEN '2 to 5 days'
             WHEN f.open_age_days < 11 THEN '6 to 10 days'
             WHEN f.open_age_days < 31 THEN '11 to 30 days'
             ELSE 'Over 30 days' END                     AS age_bucket,
        f.company_id,
        f.assignee_team                                  AS team_id,
        f.ticket_type,
        f.priority,
        f.open_age_days,
        f.resolution_state
    FROM fact_ticket f
    WHERE f.is_open = 1
)
SELECT
    age_bucket_order,
    age_bucket,
    company_id,
    team_id,
    ticket_type,
    priority,
    COUNT(*)                                             AS open_tickets,
    MAX(open_age_days)                                   AS oldest_age_days,
    SUM(CASE WHEN resolution_state = 'breached' THEN 1 ELSE 0 END) AS resolution_breached
FROM bucketed
GROUP BY age_bucket_order, age_bucket, company_id, team_id, ticket_type, priority;

-- backlog_month_end: how many tickets were open at the end of each month.
-- A ticket is open at a moment if it was opened before it and not resolved before it.
-- The end of a month is midnight at the start of the next month, UTC.
CREATE VIEW backlog_month_end AS
WITH months AS (
    SELECT DISTINCT year_month, datetime(month_start, '+1 month') AS month_end_utc
    FROM dim_date
)
SELECT
    m.year_month                       AS month,
    f.company_id,
    f.assignee_team                    AS team_id,
    f.ticket_type,
    COUNT(*)                           AS open_tickets
FROM months m
JOIN fact_ticket f
  ON f.opened_at < m.month_end_utc
 AND (f.resolved_at IS NULL OR f.resolved_at >= m.month_end_utc)
GROUP BY m.year_month, f.company_id, f.assignee_team, f.ticket_type;
