-- avg_time_to_view.sql
-- Average time between application date and first portfolio view
SELECT 
    a.id,
    a.company_name,
    a.position,
    a.date_applied,
    MIN(v.timestamp) AS first_viewed,
    EXTRACT(DAY FROM MIN(v.timestamp) - a.date_applied::timestamp) AS days_to_view
FROM applications a
INNER JOIN visits v ON a.ref_code = v.ref_code
GROUP BY a.id
ORDER BY days_to_view ASC;

-- Overall average
-- SELECT ROUND(AVG(days_to_view), 1) AS avg_days_to_view FROM (above query) sub;
