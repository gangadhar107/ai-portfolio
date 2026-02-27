-- Seed test data for verification
-- Run this AFTER schema.sql, DELETE after verification

-- Insert 5 test applications
INSERT INTO applications (company_name, person_name, position, date_applied, outcome, ref_code, notes)
VALUES
    ('TechCorp AI', 'Sarah Chen', 'ML Engineer', '2025-01-15', 'got_call', 'abc12345', 'Strong interest in RAG experience'),
    ('DataFlow Inc', 'Mike Johnson', 'Data Scientist', '2025-01-20', 'pending', 'def67890', 'Applied through LinkedIn'),
    ('CloudScale', NULL, 'Backend Developer', '2025-02-01', 'rejected', 'ghi11223', 'Wanted 5+ years experience'),
    ('AI Solutions', 'Priya Patel', 'AI Engineer', '2025-02-10', 'no_response', 'jkl44556', NULL),
    ('NeuralNet Labs', 'James Lee', 'Full Stack Developer', '2025-02-15', 'pending', 'mno77889', 'Exciting startup');

-- Insert 5 ref_codes mapping to applications
INSERT INTO ref_codes (ref_code, application_id, is_active)
VALUES
    ('abc12345', 1, TRUE),
    ('def67890', 2, TRUE),
    ('ghi11223', 3, TRUE),
    ('jkl44556', 4, TRUE),
    ('mno77889', 5, TRUE);

-- Insert 10 test visits
INSERT INTO visits (ref_code, timestamp, visit_count, pages_visited, country)
VALUES
    ('abc12345', '2025-01-16 10:30:00+00', 1, '/, /projects', 'US'),
    ('abc12345', '2025-01-17 14:15:00+00', 2, '/, /about, /projects', 'US'),
    ('abc12345', '2025-01-18 09:00:00+00', 3, '/, /contact', 'US'),
    ('def67890', '2025-01-22 11:00:00+00', 1, '/', 'IN'),
    ('def67890', '2025-01-25 16:45:00+00', 2, '/, /projects', 'IN'),
    ('ghi11223', '2025-02-02 08:30:00+00', 1, '/', 'UK'),
    ('jkl44556', '2025-02-12 13:20:00+00', 1, '/, /projects, /about', 'US'),
    ('jkl44556', '2025-02-13 10:00:00+00', 2, '/', 'US'),
    ('mno77889', '2025-02-16 15:30:00+00', 1, '/', 'DE'),
    ('mno77889', '2025-02-17 09:45:00+00', 2, '/, /projects', 'DE');
