-- mttr: mean time to resolve, incidents only.
--
-- "MTTR" is used for several different things in the industry (repair, recovery,
-- respond, resolve). Here it means the mean of the resolution clock for incidents
-- that were resolved in the month. The clock is the same one used for the service
-- level: elapsed minutes for 24X7 priorities, support-hours minutes otherwise.
--
-- Cohort: the month of RESOLUTION. Only resolved tickets have a time to resolve, so
-- the month they finished in is the natural period.
-- total_clock_minutes and incidents_resolved are included so that a report can
-- combine rows correctly (sum the minutes, sum the counts, divide).
CREATE VIEW mttr AS
SELECT
    f.resolved_month                                      AS month,
    f.company_id,
    f.assignee_team                                       AS team_id,
    f.priority,
    COUNT(*)                                              AS incidents_resolved,
    SUM(f.resolution_clock_minutes)                       AS total_clock_minutes,
    ROUND(1.0 * SUM(f.resolution_clock_minutes) / COUNT(*), 1) AS mttr_clock_minutes,
    ROUND(1.0 * SUM(f.resolution_elapsed_minutes) / COUNT(*), 1) AS mttr_elapsed_minutes
FROM fact_ticket f
WHERE f.ticket_type = 'incident' AND f.resolved_at IS NOT NULL AND f.timeline_ok = 1
GROUP BY f.resolved_month, f.company_id, f.assignee_team, f.priority;

-- mttr_percentiles: median and 90th percentile of the same clock, by month and priority.
-- A mean hides a long tail: a few stuck tickets can double it. The median shows the
-- typical ticket and the 90th percentile shows how bad the slow tail is.
-- Nearest-rank method: the value at rank ceil(p * n) in the sorted list. It always returns
-- a value that really occurred, and it is easy to reproduce in any tool.
CREATE VIEW mttr_percentiles AS
WITH ranked AS (
    SELECT
        f.resolved_month AS month,
        f.priority,
        f.resolution_clock_minutes AS minutes,
        ROW_NUMBER() OVER (PARTITION BY f.resolved_month, f.priority
                           ORDER BY f.resolution_clock_minutes, f.ticket_id) AS rn,
        COUNT(*)     OVER (PARTITION BY f.resolved_month, f.priority)       AS n
    FROM fact_ticket f
    WHERE f.ticket_type = 'incident' AND f.resolved_at IS NOT NULL AND f.timeline_ok = 1
)
SELECT
    month,
    priority,
    MAX(n)                                          AS incidents_resolved,
    MIN(CASE WHEN rn >= 0.5 * n THEN minutes END)   AS median_clock_minutes,
    MIN(CASE WHEN rn >= 0.9 * n THEN minutes END)   AS p90_clock_minutes
FROM ranked
GROUP BY month, priority;
