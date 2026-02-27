-- weekly_trend.sql
-- Weekly view trend over time (for line chart)
SELECT 
    DATE_TRUNC('week', v.timestamp)::date AS week_start,
    COUNT(*) AS total_views,
    COUNT(DISTINCT v.ref_code) AS unique_refs_viewed
FROM visits v
GROUP BY DATE_TRUNC('week', v.timestamp)
ORDER BY week_start ASC;
