-- AI Portfolio Database Schema
-- Phase 1: Three core tables for the ref code tracking system

-- Create ENUM type for application outcomes
DO $$ BEGIN
    CREATE TYPE application_outcome AS ENUM ('pending', 'got_call', 'rejected', 'no_response');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Table 1: applications — stores every job application you submit
CREATE TABLE IF NOT EXISTS applications (
    id              SERIAL PRIMARY KEY,
    company_name    TEXT NOT NULL,
    person_name     TEXT,
    position        TEXT NOT NULL,
    date_applied    DATE NOT NULL,
    outcome         application_outcome DEFAULT 'pending',
    ref_code        TEXT UNIQUE,
    notes           TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Table 2: visits — logs every time a ref link is opened
CREATE TABLE IF NOT EXISTS visits (
    id              SERIAL PRIMARY KEY,
    ref_code        TEXT NOT NULL,
    timestamp       TIMESTAMPTZ DEFAULT NOW(),
    visit_count     INTEGER DEFAULT 1,
    pages_visited   TEXT,
    country         TEXT
);

-- Table 3: ref_codes — maps opaque codes to applications
CREATE TABLE IF NOT EXISTS ref_codes (
    id              SERIAL PRIMARY KEY,
    ref_code        TEXT UNIQUE NOT NULL,
    application_id  INTEGER REFERENCES applications(id) ON DELETE CASCADE,
    created_date    TIMESTAMPTZ DEFAULT NOW(),
    is_active       BOOLEAN DEFAULT TRUE
);

-- Index for fast ref_code lookups on visits table
CREATE INDEX IF NOT EXISTS idx_visits_ref_code ON visits(ref_code);

-- Index for fast ref_code lookups on ref_codes table
CREATE INDEX IF NOT EXISTS idx_ref_codes_ref_code ON ref_codes(ref_code);

-- Index for application outcome filtering
CREATE INDEX IF NOT EXISTS idx_applications_outcome ON applications(outcome);
