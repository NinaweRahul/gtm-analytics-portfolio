"""
Generate realistic advertiser funnel data
Creates 1,000 accounts with campaigns and ad events
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import random
import sys
sys.path.append('../shared-sql')
from db_config import get_engine

# Set random seed for reproducibility
np.random.seed(42)
random.seed(42)

print("="*60)
print("WEEK 1: GENERATING FUNNEL DATA")
print("="*60)

def generate_accounts(n=1000):
    """Generate advertiser accounts"""
    
    print(f"\nGenerating {n} accounts...")
    
    segments = ['SMB', 'Mid-Market', 'Enterprise']
    segment_weights = [0.70, 0.20, 0.10]  # 70% SMB, 20% MM, 10% ENT
    
    regions = ['North America', 'EMEA', 'APAC', 'LATAM']
    region_weights = [0.50, 0.25, 0.15, 0.10]
    
    accounts = []
    
    for i in range(n):
        account_id = f"ACC{str(i+1).zfill(6)}"
        segment = random.choices(segments, weights=segment_weights)[0]
        region = random.choices(regions, weights=region_weights)[0]
        
        # Signup date: last 365 days
        signup_date = datetime.now() - timedelta(days=random.randint(0, 365))
        
        # Status: 85% active, 15% inactive
        status = 'Active' if random.random() < 0.85 else 'Inactive'
        
        accounts.append({
            'account_id': account_id,
            'account_name': f'Advertiser_{i+1}',
            'segment': segment,
            'region': region,
            'signup_date': signup_date.date(),
            'account_status': status
        })
    
    df = pd.DataFrame(accounts)
    
    print(f"Generated {len(df)} accounts")
    print(f"Segments: SMB={len(df[df['segment']=='SMB'])}, "
          f"Mid-Market={len(df[df['segment']=='Mid-Market'])}, "
          f"Enterprise={len(df[df['segment']=='Enterprise'])}")
    print(f"Active: {len(df[df['account_status']=='Active'])}")
    
    return df

def generate_campaigns(accounts_df):
    """Generate campaigns for accounts"""
    
    print("\nGenerating campaigns...")
    
    product_types = ['Search', 'Display', 'Video']
    campaigns = []
    campaign_counter = 0
    
    for _, account in accounts_df.iterrows():
        
        # Only active accounts create campaigns
        if account['account_status'] != 'Active':
            continue
        
        # Engagement rate varies by segment
        if account['segment'] == 'SMB':
            engagement_prob = 0.60  # 60% create campaigns
            n_campaigns = random.choices([0, 1, 2], weights=[0.4, 0.4, 0.2])[0]
        elif account['segment'] == 'Mid-Market':
            engagement_prob = 0.75
            n_campaigns = random.choices([0, 1, 2, 3], weights=[0.25, 0.35, 0.25, 0.15])[0]
        else:  # Enterprise
            engagement_prob = 0.90
            n_campaigns = random.choices([1, 2, 3, 4, 5], weights=[0.1, 0.2, 0.3, 0.25, 0.15])[0]
        
        # Skip if not engaged
        if random.random() > engagement_prob:
            continue
        
        for _ in range(n_campaigns):
            campaign_counter += 1
            
            campaign_date = account['signup_date'] + timedelta(days=random.randint(0, 30))
            
            campaigns.append({
                'campaign_id': f"CMP{str(campaign_counter).zfill(8)}",
                'account_id': account['account_id'],
                'campaign_name': f"{account['account_name']}_Campaign_{campaign_counter}",
                'product_type': random.choice(product_types),
                'created_date': campaign_date,
                'status': 'Active'
            })
    
    df = pd.DataFrame(campaigns)
    
    print(f"Generated {len(df)} campaigns")
    print(f"Product types: Search={len(df[df['product_type']=='Search'])}, "
          f"Display={len(df[df['product_type']=='Display'])}, "
          f"Video={len(df[df['product_type']=='Video'])}")
    
    return df

def generate_ad_events(campaigns_df, accounts_df, days=90):
    """Generate daily ad performance data"""
    
    print(f"\nGenerating ad events for last {days} days...")
    
    events = []
    start_date = datetime.now() - timedelta(days=days)
    
    for _, campaign in campaigns_df.iterrows():
        account = accounts_df[accounts_df['account_id'] == campaign['account_id']].iloc[0]
        
        # Campaign only active after creation
        campaign_start = max(campaign['created_date'], start_date.date())
        
        # How many days this campaign has been running
        days_running = (datetime.now().date() - campaign_start).days
        
        if days_running <= 0:
            continue
        
        # Activity probability varies by segment
        if account['segment'] == 'SMB':
            daily_activity_prob = 0.30
            base_impressions = random.randint(500, 5000)
        elif account['segment'] == 'Mid-Market':
            daily_activity_prob = 0.50
            base_impressions = random.randint(2000, 20000)
        else:  # Enterprise
            daily_activity_prob = 0.70
            base_impressions = random.randint(10000, 100000)
        
        for day_offset in range(min(days_running, days)):
            # Not every campaign runs every day
            if random.random() > daily_activity_prob:
                continue
            
            event_date = campaign_start + timedelta(days=day_offset)
            
            # Generate metrics with realistic patterns
            impressions = int(base_impressions * random.uniform(0.8, 1.2))
            
            # CTR varies by product type
            if campaign['product_type'] == 'Search':
                ctr = random.uniform(0.02, 0.08)  # 2-8%
            elif campaign['product_type'] == 'Display':
                ctr = random.uniform(0.005, 0.02)  # 0.5-2%
            else:  # Video
                ctr = random.uniform(0.01, 0.04)  # 1-4%
            
            clicks = int(impressions * ctr)
            
            # Conversion rate: 2-10% of clicks
            cvr = random.uniform(0.02, 0.10)
            conversions = int(clicks * cvr)
            
            # Spend calculation
            if campaign['product_type'] == 'Search':
                cpc = random.uniform(1.5, 4.0)
            elif campaign['product_type'] == 'Display':
                cpc = random.uniform(0.5, 1.5)
            else:  # Video
                cpc = random.uniform(0.8, 2.0)
            
            spend = round(clicks * cpc, 2)
            
            events.append({
                'date': event_date,
                'campaign_id': campaign['campaign_id'],
                'account_id': campaign['account_id'],
                'impressions': impressions,
                'clicks': clicks,
                'conversions': conversions,
                'spend': spend
            })
    
    df = pd.DataFrame(events)
    
    print(f"Generated {len(df):,} ad events")
    print(f"Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"Total spend: ${df['spend'].sum():,.2f}")
    
    return df

def load_to_database(accounts_df, campaigns_df, events_df):
    """Load all data to PostgreSQL"""
    
    print("\nLoading data to PostgreSQL...")
    
    engine = get_engine()
    
    try:
        # Load in order (respecting foreign keys)
        accounts_df.to_sql('accounts', engine, if_exists='append', index=False)
        print(f"Loaded {len(accounts_df)} accounts")
        
        campaigns_df.to_sql('campaigns', engine, if_exists='append', index=False)
        print(f"Loaded {len(campaigns_df)} campaigns")
        
        events_df.to_sql('ad_events', engine, if_exists='append', index=False)
        print(f"Loaded {len(events_df)} ad events")
        
        print("\nDatabase loaded successfully!")
        return True
        
    except Exception as e:
        print(f"\nError loading to database: {e}")
        return False

def save_csv_backups(accounts_df, campaigns_df, events_df):
    """Save CSV backups"""
    
    print("\nSaving CSV backups...")
    
    accounts_df.to_csv('../shared-data/accounts.csv', index=False)
    campaigns_df.to_csv('../shared-data/campaigns.csv', index=False)
    events_df.to_csv('../shared-data/ad_events.csv', index=False)
    
    print("CSV backups saved to shared-data/")

if __name__ == "__main__":
    
    # Generate data
    accounts = generate_accounts(n=1000)
    campaigns = generate_campaigns(accounts)
    events = generate_ad_events(campaigns, accounts, days=90)
    
    # Save backups
    save_csv_backups(accounts, campaigns, events)
    
    # Load to database
    success = load_to_database(accounts, campaigns, events)
    
    if success:
        print("\n" + "="*60)
        print("DATA GENERATION COMPLETE!")
        print("="*60)
        print(f"\nSummary:")
        print(f"  • Accounts: {len(accounts):,}")
        print(f"  • Campaigns: {len(campaigns):,}")
        print(f"  • Ad Events: {len(events):,}")
        print(f"  • Total Ad Spend: ${events['spend'].sum():,.2f}")
    else:
        print("\nData generation failed. Check errors above.")