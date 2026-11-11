-- team_load: workload and outcome by resolving team and month.
--
-- Combines four measures that use different cohorts, so read the column notes:
--   assigned_tickets       tickets opened in the month and assigned to the team
--   resolved_tickets       tickets the team resolved in the month (any open month)
--   month_end_open         tickets the team still held open at month end (all types)
--   tickets_per_fte        assigned_tickets divided by the team's FTE
--   resolution_met_pct     service level outcome for tickets opened in the month
-- When assigned_tickets exceeds resolved_tickets, the backlog is growing.
CREATE VIEW team_load AS
WITH months AS (
    SELECT DISTINCT year_month AS month FROM dim_date
),
assigned AS (
    SELECT opened_month AS month, assignee_team AS team_id, COUNT(*) AS assigned_tickets
    FROM fact_ticket GROUP BY opened_month, assignee_team
),
resolved AS (
    SELECT resolved_month AS month, assignee_team AS team_id, COUNT(*) AS resolved_tickets
    FROM fact_ticket WHERE resolved_at IS NOT NULL GROUP BY resolved_month, assignee_team
),
open_at_end AS (
    SELECT month, team_id, SUM(open_tickets) AS month_end_open
    FROM backlog_month_end GROUP BY month, team_id
),
service AS (
    SELECT month, team_id, SUM(resolution_measured) AS measured, SUM(resolution_met) AS met
    FROM sla_compliance_team GROUP BY month, team_id
)
SELECT
    m.month,
    t.team_id,
    t.team_name,
    t.fte,
    COALESCE(a.assigned_tickets, 0)                          AS assigned_tickets,
    COALESCE(r.resolved_tickets, 0)                          AS resolved_tickets,
    COALESCE(o.month_end_open, 0)                            AS month_end_open,
    ROUND(COALESCE(a.assigned_tickets, 0) / t.fte, 1)        AS tickets_per_fte,
    ROUND(100.0 * s.met / NULLIF(s.measured, 0), 1)          AS resolution_met_pct
FROM months m
CROSS JOIN teams t
LEFT JOIN assigned   a ON a.month = m.month AND a.team_id = t.team_id
LEFT JOIN resolved   r ON r.month = m.month AND r.team_id = t.team_id
LEFT JOIN open_at_end o ON o.month = m.month AND o.team_id = t.team_id
LEFT JOIN service    s ON s.month = m.month AND s.team_id = t.team_id;
