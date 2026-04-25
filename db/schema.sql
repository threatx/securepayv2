-- SecurePay Database Schema
-- Run: psql -d securepay -f db/schema.sql

-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- ENUM Types
CREATE TYPE ioc_type_enum AS ENUM ('upi_id', 'phone_number', 'url', 'telegram_id', 'email', 'app_name');
CREATE TYPE content_type_enum AS ENUM ('scam_explainer', 'prevention_tip', 'recovery_guide', 'reporting_guide', 'news_update');
CREATE TYPE source_type_enum AS ENUM ('social_media', 'complaint_portal', 'news', 'government', 'research');
CREATE TYPE submission_status_enum AS ENUM ('pending', 'verified', 'rejected');

-- Core Tables
CREATE TABLE scenarios (
    scenario_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    raw_text TEXT NOT NULL,
    summary TEXT,
    scenario_type VARCHAR[] DEFAULT '{}',
    red_flags VARCHAR[] DEFAULT '{}',
    loss_amount DECIMAL,
    is_scam BOOLEAN,
    importance_score FLOAT DEFAULT 0.5,
    is_synthetic BOOLEAN DEFAULT FALSE,
    embedding VECTOR(1024),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE iocs (
    ioc_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ioc_type ioc_type_enum NOT NULL,
    ioc_value TEXT NOT NULL,
    is_scam BOOLEAN,
    report_count INT DEFAULT 1,
    first_seen TIMESTAMP DEFAULT NOW(),
    last_seen TIMESTAMP DEFAULT NOW(),
    importance_score FLOAT DEFAULT 0.5,
    embedding VECTOR(1024),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE awareness_content (
    content_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR,
    content_text TEXT NOT NULL,
    content_type content_type_enum,
    related_scam_types VARCHAR[] DEFAULT '{}',
    importance_score FLOAT DEFAULT 0.5,
    source_url TEXT,
    publish_date DATE,
    embedding VECTOR(1024),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Source Tracking
CREATE TABLE sources (
    source_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_name VARCHAR NOT NULL,
    source_type source_type_enum,
    source_url TEXT,
    reliability_score FLOAT DEFAULT 0.5,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE scenario_sources (
    scenario_id UUID REFERENCES scenarios(scenario_id) ON DELETE CASCADE,
    source_id UUID REFERENCES sources(source_id) ON DELETE CASCADE,
    source_post_url TEXT,
    date_reported DATE,
    date_collected TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (scenario_id, source_id)
);

CREATE TABLE ioc_sources (
    ioc_id UUID REFERENCES iocs(ioc_id) ON DELETE CASCADE,
    source_id UUID REFERENCES sources(source_id) ON DELETE CASCADE,
    source_post_url TEXT,
    date_reported DATE,
    date_collected TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (ioc_id, source_id)
);

-- Community Platform
CREATE TABLE community_submissions (
    submission_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ioc_type ioc_type_enum,
    ioc_value TEXT NOT NULL,
    incident_description TEXT,
    status submission_status_enum DEFAULT 'pending',
    verified_ioc_id UUID REFERENCES iocs(ioc_id),
    importance_score FLOAT DEFAULT 0.5,
    submitted_at TIMESTAMP DEFAULT NOW(),
    reviewed_at TIMESTAMP
);

-- Junction Table
CREATE TABLE scenario_iocs (
    scenario_id UUID REFERENCES scenarios(scenario_id) ON DELETE CASCADE,
    ioc_id UUID REFERENCES iocs(ioc_id) ON DELETE CASCADE,
    context TEXT,
    PRIMARY KEY (scenario_id, ioc_id)
);

-- ============================================
-- TAXONOMY TABLES
-- ============================================

-- Scam Types (canonical categories)
CREATE TABLE scam_types (
    type_id VARCHAR PRIMARY KEY,               -- 'fake_seller'
    type_name VARCHAR NOT NULL,                -- 'Fake Seller'
    description TEXT,                          -- Canonical description for embedding
    embedding VECTOR(1024),
    created_at TIMESTAMP DEFAULT NOW()
);

-- View alias (some code references scenario_types)
CREATE VIEW scenario_types AS SELECT * FROM scam_types;

-- Mechanisms (HOW the scam works - techniques. By itself an evidence for scam)
CREATE TABLE mechanisms (
    mechanism_id VARCHAR PRIMARY KEY,           -- 'M001ABC'
    mechanism_name VARCHAR NOT NULL,            -- 'qr_code_payment_reversal'
    description TEXT NOT NULL,                  -- Description for embedding
    embedding VECTOR(1024),
    scenario_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Red Flags (WARNING SIGNS, just an indication of a scam and not by itself an evidence for a scam)
CREATE TABLE red_flags (
    red_flag_id VARCHAR PRIMARY KEY,            -- 'RF001ABC'
    red_flag_name VARCHAR NOT NULL,             -- 'urgency_pressure'
    description TEXT NOT NULL,                  -- Description for embedding
    embedding VECTOR(1024),
    scenario_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Scenario-to-Mechanisms junction (many-to-many)
-- A scenario can use MULTIPLE mechanisms (techniques)
CREATE TABLE scenario_mechanisms (
    scenario_id UUID REFERENCES scenarios(scenario_id) ON DELETE CASCADE,
    mechanism_id VARCHAR REFERENCES mechanisms(mechanism_id) ON DELETE CASCADE,
    is_primary BOOLEAN DEFAULT false,           -- Mark one as primary if needed
    PRIMARY KEY (scenario_id, mechanism_id)
);

-- Scenario-to-Red-Flags junction (many-to-many)
CREATE TABLE scenario_red_flags (
    scenario_id UUID REFERENCES scenarios(scenario_id) ON DELETE CASCADE,
    red_flag_id VARCHAR REFERENCES red_flags(red_flag_id) ON DELETE CASCADE,
    PRIMARY KEY (scenario_id, red_flag_id)
);

-- Add is_reviewed flag to scenarios
ALTER TABLE scenarios ADD COLUMN IF NOT EXISTS is_reviewed BOOLEAN DEFAULT FALSE;

-- Indexes for faster similarity search
CREATE INDEX scenarios_embedding_idx ON scenarios USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX iocs_embedding_idx ON iocs USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX awareness_embedding_idx ON awareness_content USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
