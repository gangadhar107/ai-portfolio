-- conversion_by_position.sql
-- Conversion rate broken down by position type
SELECT 
    a.position,
    COUNT(*) AS total_applied,
    COUNT(CASE WHEN v.ref_code IS NOT NULL THEN 1 END) AS viewed,
    COUNT(CASE WHEN a.outcome = 'got_call' THEN 1 END) AS got_call,
    ROUND(
        CASE 
            WHEN COUNT(*) > 0 
            THEN COUNT(CASE WHEN a.outcome = 'got_call' THEN 1 END)::NUMERIC / COUNT(*) * 100 
            ELSE 0 
        END, 1
    ) AS conversion_pct
FROM applications a
LEFT JOIN (SELECT DISTINCT ref_code FROM visits) v ON a.ref_code = v.ref_code
GROUP BY a.position
ORDER BY total_applied DESC;
