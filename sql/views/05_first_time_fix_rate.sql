-- first_time_fix_rate: share of resolved tickets fixed at first contact.
--
-- Definition used here: resolved_first_contact = 1 means the first-line team resolved
-- the ticket in the first interaction, with no hand-off. Definitions vary between tools,
-- so the first job before comparing this figure with anyone else's is to compare the definitions.
-- Cohort: month of resolution. Scope: incidents and service requests.
CREATE VIEW first_time_fix_rate AS
SELECT
    f.resolved_month                                              AS month,
    f.company_id,
    f.ticket_type,
    COUNT(*)                                                      AS resolved_tickets,
    SUM(f.resolved_first_contact)                                 AS fixed_first_contact,
    ROUND(100.0 * SUM(f.resolved_first_contact) / COUNT(*), 1)    AS ftf_pct
FROM fact_ticket f
WHERE f.ticket_type IN ('incident', 'service_request')
  AND f.resolved_at IS NOT NULL AND f.timeline_ok = 1
GROUP BY f.resolved_month, f.company_id, f.ticket_type;
