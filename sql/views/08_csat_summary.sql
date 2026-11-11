-- csat_summary: customer satisfaction from the post-resolution survey.
--
-- csat is a score from 1 (very dissatisfied) to 5 (very satisfied); blank means no response.
-- Cohort: month of resolution. Scope: incidents and service requests.
-- Only a minority of people answer a survey, so the response count is shown beside
-- the score. A score from a handful of responses is not a trend.
--   satisfied_pct    = share of responses scoring 4 or 5
--   dissatisfied_pct = share of responses scoring 1 or 2
CREATE VIEW csat_summary AS
SELECT
    f.resolved_month                                                  AS month,
    f.company_id,
    f.assignee_team                                                   AS team_id,
    COUNT(*)                                                          AS resolved_tickets,
    COUNT(f.csat)                                                     AS responses,
    ROUND(100.0 * COUNT(f.csat) / COUNT(*), 1)                        AS response_rate_pct,
    COALESCE(SUM(f.csat), 0)                                          AS csat_total,
    ROUND(1.0 * SUM(f.csat) / NULLIF(COUNT(f.csat), 0), 2)            AS avg_csat,
    SUM(CASE WHEN f.csat >= 4 THEN 1 ELSE 0 END)                      AS satisfied,
    SUM(CASE WHEN f.csat <= 2 THEN 1 ELSE 0 END)                      AS dissatisfied,
    ROUND(100.0 * SUM(CASE WHEN f.csat >= 4 THEN 1 ELSE 0 END)
          / NULLIF(COUNT(f.csat), 0), 1)                              AS satisfied_pct,
    ROUND(100.0 * SUM(CASE WHEN f.csat <= 2 THEN 1 ELSE 0 END)
          / NULLIF(COUNT(f.csat), 0), 1)                              AS dissatisfied_pct
FROM fact_ticket f
WHERE f.ticket_type IN ('incident', 'service_request')
  AND f.resolved_at IS NOT NULL AND f.timeline_ok = 1
GROUP BY f.resolved_month, f.company_id, f.assignee_team;
