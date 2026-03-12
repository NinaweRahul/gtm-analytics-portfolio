-- ============================================
-- TEST FUNNEL VIEWS
-- ============================================

-- Test 1: Overall funnel counts
SELECT 
    SUM(stage_signup) as signups,
    SUM(stage_campaign_created) as created_campaigns,
    SUM(stage_had_impressions) as had_impressions,
    SUM(stage_had_clicks) as had_clicks,
    SUM(stage_had_conversions) as had_conversions
FROM vw_account_funnel;

-- Test 2: Funnel by segment
SELECT 
    segment,
    total_signups,
    reached_campaign,
    reached_clicks,
    reached_conversions,
    signup_to_campaign_pct,
    overall_conversion_pct
FROM vw_funnel_summary
ORDER BY segment;

-- Test 3: Product performance
SELECT 
    product_type,
    segment,
    campaign_count,
    ctr_percent,
    cvr_percent,
    cpc
FROM vw_product_performance
ORDER BY ctr_percent DESC;

-- Test 4: Top performing accounts
SELECT 
    account_name,
    segment,
    total_spend,
    total_conversions,
    ctr_percent,
    cvr_percent
FROM vw_account_funnel
WHERE total_spend > 0
ORDER BY total_spend DESC
LIMIT 10;