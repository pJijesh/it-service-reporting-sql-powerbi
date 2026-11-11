-- fact_ticket: one row per ticket with the service level clock worked out.
--
-- Every other reporting view reads from this one, and the Power BI model loads it
-- as its fact table. Putting the calendar arithmetic here, once, means the
-- reports cannot disagree about what a "minute" is.
--
-- How the clock works
--   * Response clock:   opened_at to first_response_at.
--       If no first response is recorded but the ticket is resolved, the resolution time
--       is used (a resolved ticket has plainly been answered).
--       If neither exists, the clock is still running and stops at the extract time.
--   * Resolution clock: opened_at to resolved_at, or to the extract time if still open.
--   * Basis: priorities marked 24X7 in sla_targets use plain elapsed minutes.
--       All others count only minutes inside the site's support window
--       (support_windows), so a ticket raised at 17:50 on a Friday has used
--       ten minutes by 08:00 on Monday, not 62 hours.
--   * Whole minutes, rounded down.
--
-- Outcome states (response_state and resolution_state)
--   met          measured, within target (a target met exactly counts as met)
--   breached     over target, whether or not the ticket has been answered or resolved yet
--   in_flight    not yet answered or resolved and still inside target: not counted either way
--   not_measured no service level applies (problems and changes), or the timeline is invalid
--
-- Counting open tickets that are already late as breaches, and leaving in-flight tickets out,
-- stops the figures looking better than they are when recent tickets are still open.

CREATE VIEW fact_ticket AS
WITH base AS (
    SELECT
        t.ticket_id, t.ticket_type, t.company_id, t.site_id, t.category, t.priority,
        t.impact, t.urgency, t.opened_at, t.first_response_at, t.resolved_at, t.closed_at,
        t.reopened, t.resolved_first_contact, t.assignee_team, t.csat,
        s.support_calendar                                   AS calendar_code,
        e.as_of_utc                                          AS as_of,
        st.response_target_minutes,
        st.resolution_target_minutes,
        st.clock_basis,
        CASE WHEN st.ticket_type IS NULL THEN 0 ELSE 1 END   AS has_sla,
        COALESCE(t.first_response_at, t.resolved_at)         AS response_end,
        COALESCE(t.first_response_at, t.resolved_at, e.as_of_utc) AS response_clock_end,
        COALESCE(t.resolved_at, e.as_of_utc)                 AS resolution_clock_end,
        -- Timestamps must run forwards. Rows that do not are kept but not measured.
        CASE WHEN (t.first_response_at IS NULL OR t.first_response_at >= t.opened_at)
              AND (t.resolved_at IS NULL OR t.resolved_at >= t.opened_at)
              AND (t.first_response_at IS NULL OR t.resolved_at IS NULL
                   OR t.first_response_at <= t.resolved_at)
              AND (t.closed_at IS NULL
                   OR (t.resolved_at IS NOT NULL AND t.closed_at >= t.resolved_at))
             THEN 1 ELSE 0 END                               AS timeline_ok
    FROM tickets t
    JOIN sites s ON s.site_id = t.site_id
    CROSS JOIN extract_info e
    LEFT JOIN sla_targets st
           ON st.ticket_type = t.ticket_type AND st.priority = t.priority
),
clocked AS (
    SELECT
        b.*,
        -- Plain elapsed minutes: difference in epoch seconds divided by 60.
        (CAST(strftime('%s', b.response_clock_end) AS INTEGER)
         - CAST(strftime('%s', b.opened_at) AS INTEGER)) / 60       AS response_elapsed_minutes,
        (CAST(strftime('%s', b.resolution_clock_end) AS INTEGER)
         - CAST(strftime('%s', b.opened_at) AS INTEGER)) / 60       AS resolution_elapsed_minutes,
        -- Support-hours minutes: add up the overlap between [opened_at, end] and every
        -- support window of the site's calendar. Two-argument MIN and MAX pick the
        -- earlier close and the later open, which gives the overlap of each window.
        COALESCE((
            SELECT SUM(MIN(CAST(strftime('%s', w.close_utc) AS INTEGER),
                           CAST(strftime('%s', b.response_clock_end) AS INTEGER))
                     - MAX(CAST(strftime('%s', w.open_utc) AS INTEGER),
                           CAST(strftime('%s', b.opened_at) AS INTEGER)))
            FROM support_windows w
            WHERE w.calendar_code = b.calendar_code
              AND w.close_utc > b.opened_at
              AND w.open_utc  < b.response_clock_end
        ), 0) / 60                                                  AS response_support_minutes,
        COALESCE((
            SELECT SUM(MIN(CAST(strftime('%s', w.close_utc) AS INTEGER),
                           CAST(strftime('%s', b.resolution_clock_end) AS INTEGER))
                     - MAX(CAST(strftime('%s', w.open_utc) AS INTEGER),
                           CAST(strftime('%s', b.opened_at) AS INTEGER)))
            FROM support_windows w
            WHERE w.calendar_code = b.calendar_code
              AND w.close_utc > b.opened_at
              AND w.open_utc  < b.resolution_clock_end
        ), 0) / 60                                                  AS resolution_support_minutes
    FROM base b
),
on_basis AS (
    SELECT
        c.*,
        CASE WHEN c.clock_basis = '24X7' THEN c.response_elapsed_minutes
             ELSE c.response_support_minutes END                    AS response_clock_minutes,
        CASE WHEN c.clock_basis = '24X7' THEN c.resolution_elapsed_minutes
             ELSE c.resolution_support_minutes END                  AS resolution_clock_minutes
    FROM clocked c
),
states AS (
    SELECT
        o.*,
        CASE
            WHEN o.has_sla = 0 OR o.timeline_ok = 0 THEN 'not_measured'
            WHEN o.response_clock_minutes > o.response_target_minutes THEN 'breached'
            WHEN o.response_end IS NOT NULL THEN 'met'
            ELSE 'in_flight'
        END AS response_state,
        CASE
            WHEN o.has_sla = 0 OR o.timeline_ok = 0 THEN 'not_measured'
            WHEN o.resolution_clock_minutes > o.resolution_target_minutes THEN 'breached'
            WHEN o.resolved_at IS NOT NULL THEN 'met'
            ELSE 'in_flight'
        END AS resolution_state
    FROM on_basis o
)
SELECT
    s.ticket_id, s.ticket_type, s.company_id, s.site_id, s.category, s.priority,
    s.impact, s.urgency, s.opened_at, s.first_response_at, s.resolved_at, s.closed_at,
    s.reopened, s.resolved_first_contact, s.assignee_team, s.csat,
    s.calendar_code, s.clock_basis, s.has_sla, s.timeline_ok,
    s.response_target_minutes, s.resolution_target_minutes,
    s.response_elapsed_minutes, s.response_support_minutes, s.response_clock_minutes,
    s.resolution_elapsed_minutes, s.resolution_support_minutes, s.resolution_clock_minutes,
    s.response_state, s.resolution_state,
    CASE WHEN s.response_state IN ('met', 'breached') THEN 1 ELSE 0 END   AS response_measured,
    CASE WHEN s.response_state = 'met' THEN 1 ELSE 0 END                   AS response_met,
    CASE WHEN s.resolution_state IN ('met', 'breached') THEN 1 ELSE 0 END AS resolution_measured,
    CASE WHEN s.resolution_state = 'met' THEN 1 ELSE 0 END                 AS resolution_met,
    substr(s.opened_at, 1, 7)                                               AS opened_month,
    substr(s.resolved_at, 1, 7)                                             AS resolved_month,
    CASE WHEN s.resolved_at IS NULL THEN 1 ELSE 0 END                       AS is_open,
    CASE WHEN s.resolved_at IS NULL
         THEN (CAST(strftime('%s', s.as_of) AS INTEGER)
               - CAST(strftime('%s', s.opened_at) AS INTEGER)) / 86400
    END                                                                     AS open_age_days
FROM states s;
