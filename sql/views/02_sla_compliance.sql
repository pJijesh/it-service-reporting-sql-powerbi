-- sla_compliance: how often response and resolution targets were met.
--
-- Grain: opened month x company x ticket type x priority.
-- Cohort: tickets are placed in the month they were OPENED. A ticket opened on 30 June
-- and fixed on 2 July counts towards June. That keeps one ticket in one month, and the
-- month's figure can still change slightly while recent tickets are in flight.
-- Scope: incidents and service requests only. Problems and changes have no service level.
--
-- Percentages are given for convenience. When combining rows (for example two
-- companies), add the counts and divide again. Never average the percentages.

CREATE VIEW sla_compliance AS
SELECT
    f.opened_month                                                    AS month,
    f.company_id,
    c.company_name,
    f.ticket_type,
    f.priority,
    SUM(f.response_measured)                                          AS response_measured,
    SUM(f.response_met)                                               AS response_met,
    ROUND(100.0 * SUM(f.response_met) / NULLIF(SUM(f.response_measured), 0), 1)
                                                                      AS response_met_pct,
    SUM(f.resolution_measured)                                        AS resolution_measured,
    SUM(f.resolution_met)                                             AS resolution_met,
    ROUND(100.0 * SUM(f.resolution_met) / NULLIF(SUM(f.resolution_measured), 0), 1)
                                                                      AS resolution_met_pct,
    SUM(CASE WHEN f.resolution_state = 'in_flight' THEN 1 ELSE 0 END) AS resolution_in_flight
FROM fact_ticket f
JOIN companies c ON c.company_id = f.company_id
WHERE f.has_sla = 1 AND f.timeline_ok = 1
GROUP BY f.opened_month, f.company_id, c.company_name, f.ticket_type, f.priority;

-- sla_compliance_team: the same measure by resolving team, for team and board views.
CREATE VIEW sla_compliance_team AS
SELECT
    f.opened_month                                                    AS month,
    f.assignee_team                                                   AS team_id,
    t.team_name,
    f.ticket_type,
    SUM(f.response_measured)                                          AS response_measured,
    SUM(f.response_met)                                               AS response_met,
    ROUND(100.0 * SUM(f.response_met) / NULLIF(SUM(f.response_measured), 0), 1)
                                                                      AS response_met_pct,
    SUM(f.resolution_measured)                                        AS resolution_measured,
    SUM(f.resolution_met)                                             AS resolution_met,
    ROUND(100.0 * SUM(f.resolution_met) / NULLIF(SUM(f.resolution_measured), 0), 1)
                                                                      AS resolution_met_pct
FROM fact_ticket f
JOIN teams t ON t.team_id = f.assignee_team
WHERE f.has_sla = 1 AND f.timeline_ok = 1
GROUP BY f.opened_month, f.assignee_team, t.team_name, f.ticket_type;
