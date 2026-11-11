-- data_quality_checks: one row per check, with the number of tickets that fail it.
-- On clean data every row is zero. See docs/ticket-data-quality.md for why each matters.
-- The loader prints any non-zero rows after loading.
CREATE VIEW data_quality_checks AS
SELECT 'resolved before opened' AS check_name, COUNT(*) AS failing_tickets
FROM tickets WHERE resolved_at IS NOT NULL AND resolved_at < opened_at
UNION ALL
SELECT 'first response before opened', COUNT(*)
FROM tickets WHERE first_response_at IS NOT NULL AND first_response_at < opened_at
UNION ALL
SELECT 'first response after resolved', COUNT(*)
FROM tickets WHERE first_response_at IS NOT NULL AND resolved_at IS NOT NULL
                   AND first_response_at > resolved_at
UNION ALL
SELECT 'closed without a resolution time', COUNT(*)
FROM tickets WHERE closed_at IS NOT NULL AND resolved_at IS NULL
UNION ALL
SELECT 'closed before resolved', COUNT(*)
FROM tickets WHERE closed_at IS NOT NULL AND resolved_at IS NOT NULL AND closed_at < resolved_at
UNION ALL
SELECT 'resolved with no first response recorded', COUNT(*)
FROM tickets WHERE resolved_at IS NOT NULL AND first_response_at IS NULL
UNION ALL
SELECT 'priority does not match impact and urgency', COUNT(*)
FROM tickets t JOIN priority_matrix m ON m.impact = t.impact AND m.urgency = t.urgency
WHERE t.priority <> m.priority
UNION ALL
SELECT 'first contact fix flag on an unresolved ticket', COUNT(*)
FROM tickets WHERE resolved_first_contact = 1 AND resolved_at IS NULL
UNION ALL
SELECT 'reopened flag on an unresolved ticket', COUNT(*)
FROM tickets WHERE reopened = 1 AND resolved_at IS NULL
UNION ALL
SELECT 'satisfaction score on an unresolved ticket', COUNT(*)
FROM tickets WHERE csat IS NOT NULL AND resolved_at IS NULL
UNION ALL
SELECT 'timestamp after the extract time', COUNT(*)
FROM tickets t CROSS JOIN extract_info e
WHERE t.opened_at > e.as_of_utc OR t.first_response_at > e.as_of_utc
   OR t.resolved_at > e.as_of_utc OR t.closed_at > e.as_of_utc;
