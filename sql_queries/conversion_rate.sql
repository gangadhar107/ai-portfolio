-- conversion_rate.sql
-- Overall view-to-call conversion rate
SELECT 
    COUNT(*) AS total_applications,
    COUNT(CASE WHEN v.ref_code IS NOT NULL THEN 1 END) AS viewed,
    COUNT(CASE WHEN a.outcome = 'got_call' THEN 1 END) AS got_call,
    ROUND(
        CASE 
            WHEN COUNT(*) > 0 
            THEN COUNT(CASE WHEN a.outcome = 'got_call' THEN 1 END)::NUMERIC / COUNT(*) * 100 
            ELSE 0 
        END, 1
    ) AS overall_conversion_pct,
    ROUND(
        CASE 
            WHEN COUNT(CASE WHEN v.ref_code IS NOT NULL THEN 1 END) > 0 
            THEN COUNT(CASE WHEN a.outcome = 'got_call' THEN 1 END)::NUMERIC / 
                 COUNT(CASE WHEN v.ref_code IS NOT NULL THEN 1 END) * 100 
            ELSE 0 
        END, 1
    ) AS view_to_call_pct
FROM applications a
LEFT JOIN (SELECT DISTINCT ref_code FROM visits) v ON a.ref_code = v.ref_code;
