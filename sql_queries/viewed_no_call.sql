-- viewed_no_call.sql
-- Applications that were viewed but never got a call — follow-up candidates
SELECT 
    a.id,
    a.company_name,
    a.position,
    a.date_applied,
    a.outcome,
    COUNT(v.id) AS view_count,
    MIN(v.timestamp) AS first_viewed,
    AGE(NOW(), MIN(v.timestamp)) AS time_since_first_view
FROM applications a
INNER JOIN visits v ON a.ref_code = v.ref_code
WHERE a.outcome IN ('pending', 'no_response')
GROUP BY a.id
ORDER BY first_viewed ASC;
