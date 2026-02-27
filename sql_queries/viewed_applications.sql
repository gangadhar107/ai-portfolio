-- viewed_applications.sql
-- All applications where portfolio was viewed >= 1 time
SELECT 
    a.id,
    a.company_name,
    a.position,
    a.date_applied,
    a.outcome,
    COUNT(v.id) AS view_count,
    MIN(v.timestamp) AS first_viewed,
    MAX(v.timestamp) AS last_viewed
FROM applications a
INNER JOIN visits v ON a.ref_code = v.ref_code
GROUP BY a.id
HAVING COUNT(v.id) >= 1
ORDER BY first_viewed DESC;
