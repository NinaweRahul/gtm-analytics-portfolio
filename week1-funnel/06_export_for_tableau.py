"""
Export funnel data for Tableau visualization
"""

import pandas as pd
import sys
sys.path.append('../shared-sql')
from db_config import get_engine

def export_tableau_data():
    """Export clean datasets for Tableau"""
    
    print("="*60)
    print("EXPORTING DATA FOR TABLEAU")
    print("="*60)
    
    engine = get_engine()
    
    # Export 1: Account-level funnel
    print("\nExporting account funnel data...")
    funnel_accounts = pd.read_sql("SELECT * FROM vw_account_funnel", engine)
    funnel_accounts.to_csv('tableau_account_funnel.csv', index=False)
    print(f"Exported {len(funnel_accounts)} accounts")
    
    # Export 2: Funnel summary
    print("\nExporting funnel summary...")
    funnel_summary = pd.read_sql("SELECT * FROM vw_funnel_summary", engine)
    funnel_summary.to_csv('tableau_funnel_summary.csv', index=False)
    print(f"Exported {len(funnel_summary)} summary records")
    
    # Export 3: Product performance
    print("\nExporting product performance...")
    product_perf = pd.read_sql("SELECT * FROM vw_product_performance", engine)
    product_perf.to_csv('tableau_product_performance.csv', index=False)
    print(f"Exported {len(product_perf)} product records")
    
    # Export 4: Daily trends
    print("\nExporting daily trends...")
    daily_trends = pd.read_sql("""
        SELECT 
            ae.date,
            a.segment,
            c.product_type,
            SUM(ae.impressions) as impressions,
            SUM(ae.clicks) as clicks,
            SUM(ae.conversions) as conversions,
            SUM(ae.spend) as spend
        FROM ad_events ae
        JOIN campaigns c ON ae.campaign_id = c.campaign_id
        JOIN accounts a ON ae.account_id = a.account_id
        WHERE a.account_status = 'Active'
        GROUP BY ae.date, a.segment, c.product_type
        ORDER BY ae.date
    """, engine)
    daily_trends.to_csv('tableau_daily_trends.csv', index=False)
    print(f"Exported {len(daily_trends)} daily records")
    
    print("\n" + "="*60)
    print("ALL TABLEAU EXPORTS COMPLETE!")
    print("="*60)


if __name__ == "__main__":
    export_tableau_data()