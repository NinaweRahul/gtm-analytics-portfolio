-- ============================================
-- WEEK 1: FUNNEL ANALYSIS VIEWS
-- ============================================

-- ============================================
-- VIEW 1: ACCOUNT FUNNEL STAGES
-- ============================================

CREATE OR REPLACE VIEW vw_account_funnel AS
SELECT 
    a.account_id,
    a.account_name,
    a.segment,
    a.region,
    a.signup_date,
    a.account_status,
    
    -- Funnel Stage 1: Signed up (everyone)
    1 as stage_signup,
    
    -- Funnel Stage 2: Created campaign
    CASE WHEN c.account_id IS NOT NULL THEN 1 ELSE 0 END as stage_campaign_created,
    
    -- Funnel Stage 3: Had impressions
    CASE WHEN ae_imp.account_id IS NOT NULL THEN 1 ELSE 0 END as stage_had_impressions,
    
    -- Funnel Stage 4: Had clicks
    CASE WHEN ae_clicks.account_id IS NOT NULL THEN 1 ELSE 0 END as stage_had_clicks,
    
    -- Funnel Stage 5: Had conversions
    CASE WHEN ae_conv.account_id IS NOT NULL THEN 1 ELSE 0 END as stage_had_conversions,
    
    -- Aggregate metrics
    COALESCE(SUM(ae.impressions), 0) as total_impressions,
    COALESCE(SUM(ae.clicks), 0) as total_clicks,
    COALESCE(SUM(ae.conversions), 0) as total_conversions,
    COALESCE(SUM(ae.spend), 0) as total_spend,
    
    -- Calculated rates
    CASE 
        WHEN SUM(ae.impressions) > 0 
        THEN ROUND((SUM(ae.clicks)::NUMERIC / SUM(ae.impressions)) * 100, 2)
        ELSE 0 
    END as ctr_percent,
    
    CASE 
        WHEN SUM(ae.clicks) > 0 
        THEN ROUND((SUM(ae.conversions)::NUMERIC / SUM(ae.clicks)) * 100, 2)
        ELSE 0 
    END as cvr_percent
    
FROM accounts a

-- Check if campaign exists
LEFT JOIN (SELECT DISTINCT account_id FROM campaigns) c 
    ON a.account_id = c.account_id

-- Check if had impressions
LEFT JOIN (SELECT DISTINCT account_id FROM ad_events WHERE impressions > 0) ae_imp 
    ON a.account_id = ae_imp.account_id

-- Check if had clicks
LEFT JOIN (SELECT DISTINCT account_id FROM ad_events WHERE clicks > 0) ae_clicks 
    ON a.account_id = ae_clicks.account_id

-- Check if had conversions
LEFT JOIN (SELECT DISTINCT account_id FROM ad_events WHERE conversions > 0) ae_conv 
    ON a.account_id = ae_conv.account_id

-- Get aggregate metrics
LEFT JOIN ad_events ae ON a.account_id = ae.account_id

WHERE a.account_status = 'Active'

GROUP BY 
    a.account_id, a.account_name, a.segment, a.region, 
    a.signup_date, a.account_status,
    c.account_id, ae_imp.account_id, ae_clicks.account_id, ae_conv.account_id;

COMMENT ON VIEW vw_account_funnel IS 'Account progression through funnel stages';

-- ============================================
-- VIEW 2: FUNNEL CONVERSION SUMMARY
-- ============================================

CREATE OR REPLACE VIEW vw_funnel_summary AS
SELECT 
    segment,
    region,
    
    -- Funnel counts
    COUNT(*) as total_signups,
    SUM(stage_campaign_created) as reached_campaign,
    SUM(stage_had_impressions) as reached_impressions,
    SUM(stage_had_clicks) as reached_clicks,
    SUM(stage_had_conversions) as reached_conversions,
    
    -- Conversion rates
    ROUND((SUM(stage_campaign_created)::NUMERIC / COUNT(*)) * 100, 1) as signup_to_campaign_pct,
    ROUND((SUM(stage_had_impressions)::NUMERIC / NULLIF(SUM(stage_campaign_created), 0)) * 100, 1) as campaign_to_impression_pct,
    ROUND((SUM(stage_had_clicks)::NUMERIC / NULLIF(SUM(stage_had_impressions), 0)) * 100, 1) as impression_to_click_pct,
    ROUND((SUM(stage_had_conversions)::NUMERIC / NULLIF(SUM(stage_had_clicks), 0)) * 100, 1) as click_to_conversion_pct,
    
    -- Overall conversion
    ROUND((SUM(stage_had_conversions)::NUMERIC / COUNT(*)) * 100, 1) as overall_conversion_pct,
    
    -- Aggregate metrics
    SUM(total_spend) as total_spend,
    AVG(ctr_percent) as avg_ctr,
    AVG(cvr_percent) as avg_cvr
    
FROM vw_account_funnel
GROUP BY segment, region
ORDER BY segment, region;

COMMENT ON VIEW vw_funnel_summary IS 'Funnel conversion rates by segment and region';

-- ============================================
-- VIEW 3: PRODUCT TYPE PERFORMANCE
-- ============================================

CREATE OR REPLACE VIEW vw_product_performance AS
SELECT 
    c.product_type,
    a.segment,
    
    COUNT(DISTINCT c.campaign_id) as campaign_count,
    COUNT(DISTINCT c.account_id) as account_count,
    
    SUM(ae.impressions) as total_impressions,
    SUM(ae.clicks) as total_clicks,
    SUM(ae.conversions) as total_conversions,
    SUM(ae.spend) as total_spend,
    
    -- Performance metrics
    ROUND((SUM(ae.clicks)::NUMERIC / NULLIF(SUM(ae.impressions), 0)) * 100, 2) as ctr_percent,
    ROUND((SUM(ae.conversions)::NUMERIC / NULLIF(SUM(ae.clicks), 0)) * 100, 2) as cvr_percent,
    ROUND(SUM(ae.spend) / NULLIF(SUM(ae.clicks), 0), 2) as cpc,
    ROUND(SUM(ae.spend) / NULLIF(SUM(ae.conversions), 0), 2) as cpa
    
FROM campaigns c
JOIN accounts a ON c.account_id = a.account_id
LEFT JOIN ad_events ae ON c.campaign_id = ae.campaign_id

WHERE a.account_status = 'Active'

GROUP BY c.product_type, a.segment
ORDER BY c.product_type, a.segment;

COMMENT ON VIEW vw_product_performance IS 'Performance metrics by product type and segment';
