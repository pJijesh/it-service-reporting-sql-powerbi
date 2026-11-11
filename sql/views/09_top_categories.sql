-- top_categories: what people raise tickets about, ranked within each month and type.
-- Cohort: month opened. RANK gives tied categories the same rank. To list the top five,
-- filter on rank_in_month <= 5 (see reports/build_report.py).
-- resolution_breached and avg_resolution_clock_minutes cover the tickets that have an outcome.
CREATE VIEW top_categories AS
WITH counted AS (
    SELECT
        f.opened_month AS month,
        f.ticket_type,
        f.category,
        COUNT(*) AS tickets,
        SUM(CASE WHEN f.resolution_state = 'breached' THEN 1 ELSE 0 END) AS resolution_breached,
        AVG(CASE WHEN f.resolved_at IS NOT NULL THEN 1.0 * f.resolution_clock_minutes END)
            AS avg_resolution_clock_minutes
    FROM fact_ticket f
    GROUP BY f.opened_month, f.ticket_type, f.category
)
SELECT
    month,
    ticket_type,
    category,
    tickets,
    ROUND(100.0 * tickets / SUM(tickets) OVER (PARTITION BY month, ticket_type), 1) AS share_pct,
    RANK() OVER (PARTITION BY month, ticket_type ORDER BY tickets DESC)            AS rank_in_month,
    resolution_breached,
    ROUND(avg_resolution_clock_minutes, 1)                                         AS avg_resolution_clock_minutes
FROM counted;
