-- reopen_rate: share of resolved tickets that were reopened after resolution.
--
-- Cohort: month of resolution. Caution: a ticket resolved late in the most recent
-- month has had little time to be reopened, so the latest month tends to look slightly
-- better than it will finally be. Read the latest month with that in mind.
CREATE VIEW reopen_rate AS
SELECT
    f.resolved_month                                              AS month,
    f.company_id,
    f.assignee_team                                               AS team_id,
    COUNT(*)                                                      AS resolved_tickets,
    SUM(f.reopened)                                               AS reopened_tickets,
    ROUND(100.0 * SUM(f.reopened) / COUNT(*), 1)                  AS reopen_pct
FROM fact_ticket f
WHERE f.ticket_type IN ('incident', 'service_request')
  AND f.resolved_at IS NOT NULL AND f.timeline_ok = 1
GROUP BY f.resolved_month, f.company_id, f.assignee_team;
