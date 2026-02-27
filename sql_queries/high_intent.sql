-- high_intent.sql
-- Applications viewed more than 1 time — signals genuine interest
SELECT 
    a.id,
    a.company_name,
    a.position,
    a.date_applied,
    a.outcome,
    COUNT(v.id) AS view_count,
    COUNT(DISTINCT DATE(v.timestamp)) AS unique_days_viewed
FROM applications a
INNER JOIN visits v ON a.ref_code = v.ref_code
GROUP BY a.id
HAVING COUNT(v.id) > 1
ORDER BY view_count DESC;
