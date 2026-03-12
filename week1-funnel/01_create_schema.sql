-- ============================================
-- WEEK 1: ADVERTISER FUNNEL SCHEMA
-- ============================================

-- Drop existing tables if re-running
DROP TABLE IF EXISTS ad_events CASCADE;
DROP TABLE IF EXISTS campaigns CASCADE;
DROP TABLE IF EXISTS accounts CASCADE;

-- ============================================
-- ACCOUNTS (Advertisers)
-- ============================================
CREATE TABLE accounts (
    account_id VARCHAR(50) PRIMARY KEY,
    account_name VARCHAR(255) NOT NULL,
    segment VARCHAR(50) NOT NULL,  -- SMB, Mid-Market, Enterprise
    region VARCHAR(50) NOT NULL,
    signup_date DATE NOT NULL,
    account_status VARCHAR(20) NOT NULL,  -- Active, Inactive
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ============================================
-- CAMPAIGNS
-- ============================================
CREATE TABLE campaigns (
    campaign_id VARCHAR(50) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    campaign_name VARCHAR(255),
    product_type VARCHAR(50),  -- Search, Display, Video
    created_date DATE,
    status VARCHAR(20),
    
    -- Foreign key with CASCADE
    CONSTRAINT fk_campaign_account 
        FOREIGN KEY (account_id) 
        REFERENCES accounts(account_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- ============================================
-- AD_EVENTS (Performance data)
-- ============================================
CREATE TABLE ad_events (
    event_id SERIAL PRIMARY KEY,
    date DATE NOT NULL,
    campaign_id VARCHAR(50) NOT NULL,
    account_id VARCHAR(50) NOT NULL,
    impressions INTEGER DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    conversions INTEGER DEFAULT 0,
    spend DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Foreign keys with CASCADE
    CONSTRAINT fk_event_campaign 
        FOREIGN KEY (campaign_id) 
        REFERENCES campaigns(campaign_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE,
        
    CONSTRAINT fk_event_account 
        FOREIGN KEY (account_id) 
        REFERENCES accounts(account_id)
        ON DELETE CASCADE
        ON UPDATE CASCADE
);

-- ============================================
-- INDEXES (for performance)
-- ============================================
CREATE INDEX idx_events_date ON ad_events(date);
CREATE INDEX idx_events_account ON ad_events(account_id);
CREATE INDEX idx_events_campaign ON ad_events(campaign_id);
CREATE INDEX idx_campaigns_account ON campaigns(account_id);
