-- volume_trend: tickets opened and resolved each month, with the change on the month before.
--
-- UNION ALL of two event lists, then one aggregate, because not every database has
-- FULL OUTER JOIN and this form works on all of them.
-- LAG looks at the previous month for the same company and ticket type.
CREATE VIEW volume_trend AS
WITH events AS (
    SELECT opened_month AS month, company_id, ticket_type, 1 AS opened, 0 AS resolved
    FROM fact_ticket
    UNION ALL
    SELECT resolved_month, company_id, ticket_type, 0, 1
    FROM fact_ticket
    WHERE resolved_at IS NOT NULL
),
monthly AS (
    SELECT month, company_id, ticket_type, SUM(opened) AS opened, SUM(resolved) AS resolved
    FROM events
    GROUP BY month, company_id, ticket_type
)
SELECT
    m.month,
    m.company_id,
    m.ticket_type,
    m.opened,
    m.resolved,
    m.opened - m.resolved                                            AS net_backlog_change,
    LAG(m.opened) OVER (PARTITION BY m.company_id, m.ticket_type ORDER BY m.month)
                                                                     AS prev_month_opened,
    ROUND(100.0 * (m.opened - LAG(m.opened) OVER (PARTITION BY m.company_id, m.ticket_type
                                                  ORDER BY m.month))
          / NULLIF(LAG(m.opened) OVER (PARTITION BY m.company_id, m.ticket_type
                                       ORDER BY m.month), 0), 1)     AS mom_change_pct
FROM monthly m;

-- volume_by_weekday: demand by day of the week (UTC date of opening), all ticket types.
-- Average per day divides by the number of such days in the period, so a month with five
-- Mondays does not look busier than it is.
CREATE VIEW volume_by_weekday AS
WITH tickets_by_day AS (
    SELECT d.day_of_week, d.day_name, COUNT(*) AS tickets
    FROM tickets t
    JOIN dim_date d ON d.date = substr(t.opened_at, 1, 10)
    GROUP BY d.day_of_week, d.day_name
),
days AS (
    SELECT day_of_week, COUNT(*) AS days_in_period FROM dim_date GROUP BY day_of_week
)
SELECT
    b.day_of_week,
    b.day_name,
    b.tickets,
    n.days_in_period,
    ROUND(1.0 * b.tickets / n.days_in_period, 1) AS avg_tickets_per_day
FROM tickets_by_day b
JOIN days n ON n.day_of_week = b.day_of_week;
