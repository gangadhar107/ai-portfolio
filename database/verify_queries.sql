-- Verification Queries — Run these after inserting test data
-- All 4 must return expected results before Phase 1 is complete

-- Query 1: SELECT all applications
SELECT * FROM applications ORDER BY date_applied DESC;

-- Query 2: JOIN applications with visits (which companies viewed your portfolio?)
SELECT 
    a.company_name,
    a.position,
    a.outcome,
    COUNT(v.id) AS total_visits,
    MIN(v.timestamp) AS first_visit,
    MAX(v.timestamp) AS last_visit
FROM applications a
LEFT JOIN visits v ON a.ref_code = v.ref_code
GROUP BY a.id, a.company_name, a.position, a.outcome
ORDER BY total_visits DESC;

-- Query 3: FILTER by outcome — show only pending applications that were viewed
SELECT 
    a.company_name,
    a.position,
    a.date_applied,
    COUNT(v.id) AS view_count
FROM applications a
JOIN visits v ON a.ref_code = v.ref_code
WHERE a.outcome = 'pending'
GROUP BY a.id, a.company_name, a.position, a.date_applied;

-- Query 4: COUNT visits per ref code
SELECT 
    rc.ref_code,
    a.company_name,
    a.position,
    COUNT(v.id) AS visit_count,
    rc.is_active
FROM ref_codes rc
JOIN applications a ON rc.application_id = a.id
LEFT JOIN visits v ON rc.ref_code = v.ref_code
GROUP BY rc.ref_code, a.company_name, a.position, rc.is_active
ORDER BY visit_count DESC;
