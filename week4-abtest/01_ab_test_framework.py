"""
A/B Testing Framework for Ad Products
Compare Auto-Bidding vs Manual Bidding strategies
"""

import pandas as pd
import numpy as np
from sqlalchemy import text
from scipy import stats
import matplotlib.pyplot as plt
import seaborn as sns
import sys

sys.path.append('../shared-sql')
from db_config import get_engine

# Set style
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)

print("="*70)
print("WEEK 4: A/B TESTING FRAMEWORK")
print("="*70)

# ============================================
# 1. LOAD EXPERIMENT DATA
# ============================================

def load_ab_test_data():
    """
    Load campaign data for A/B test: Manual vs Auto Bidding
    """
    
    print("\nLoading A/B test data...")
    
    engine = get_engine()
    
    query = """
    SELECT 
        c.campaign_id,
        c.bidding_strategy,
        a.segment,
        a.region,
        
        -- Aggregate metrics
        SUM(ae.clicks) as total_clicks,
        SUM(ae.spend) as total_cost,
        SUM(ae.conversions) as total_conversions,
        SUM(ae.impressions) as total_impressions,
        
        -- Calculated metrics
        CASE 
            WHEN SUM(ae.clicks) > 0 
            THEN SUM(ae.spend) / SUM(ae.clicks)
            ELSE 0 
        END as cpc,
        
        CASE 
            WHEN SUM(ae.clicks) > 0 
            THEN (SUM(ae.conversions)::NUMERIC / SUM(ae.clicks)) * 100
            ELSE 0 
        END as cvr,
        
        CASE 
            WHEN SUM(ae.spend) > 0 
            THEN (SUM(ae.conversions) * 50) / SUM(ae.spend)  -- Assuming $50 per conversion value
            ELSE 0 
        END as roas
        
    FROM campaigns c
    JOIN accounts a ON c.account_id = a.account_id
    LEFT JOIN ad_events ae ON c.campaign_id = ae.campaign_id
    
    WHERE c.bidding_strategy IN ('Manual', 'Auto')
    AND ae.date >= CURRENT_DATE - 90
    AND a.account_status = 'Active'
    
    GROUP BY c.campaign_id, c.bidding_strategy, a.segment, a.region
    HAVING SUM(ae.clicks) > 50  -- Minimum sample size
    """
    
    df = pd.read_sql(text(query), engine)
    
    print(f"Loaded {len(df)} campaigns")
    print(f"Manual: {len(df[df['bidding_strategy']=='Manual'])}")
    print(f"Auto: {len(df[df['bidding_strategy']=='Auto'])}")
    
    return df

# ============================================
# 2. STATISTICAL ANALYSIS
# ============================================

def run_ab_analysis(df, metric='roas'):
    """
    Perform statistical test for A/B comparison
    """
    
    control = df[df['bidding_strategy'] == 'Manual'][metric]
    treatment = df[df['bidding_strategy'] == 'Auto'][metric]
    
    # Remove infinities and NaNs
    control = control.replace([np.inf, -np.inf], np.nan).dropna()
    treatment = treatment.replace([np.inf, -np.inf], np.nan).dropna()
    
    if len(control) == 0 or len(treatment) == 0:
        return None, None, None
    
    # T-test
    t_stat, p_value = stats.ttest_ind(treatment, control)
    
    # Effect size (Cohen's d)
    pooled_std = np.sqrt(
        ((len(control)-1) * control.std()**2 + (len(treatment)-1) * treatment.std()**2) / 
        (len(control) + len(treatment) - 2)
    )
    
    if pooled_std > 0:
        cohens_d = (treatment.mean() - control.mean()) / pooled_std
    else:
        cohens_d = 0
    
    # Results
    results = {
        'metric': metric,
        'control_mean': control.mean(),
        'control_std': control.std(),
        'control_n': len(control),
        'treatment_mean': treatment.mean(),
        'treatment_std': treatment.std(),
        'treatment_n': len(treatment),
        'lift_percent': ((treatment.mean() - control.mean()) / control.mean()) * 100 if control.mean() != 0 else 0,
        'p_value': p_value,
        'is_significant': p_value < 0.05,
        'cohens_d': cohens_d,
        't_stat': t_stat
    }
    
    return results, control, treatment

# ============================================
# 3. VISUALIZATION
# ============================================

def visualize_ab_test(control, treatment, results, metric='ROAS'):
    """Create visualization for A/B test"""
    
    if control is None or treatment is None:
        print(f"Skipping {metric} visualization - insufficient data")
        return
    
    fig, axes = plt.subplots(1, 2, figsize=(15, 5))
    
    # 1. Distribution comparison
    axes[0].hist(control, bins=20, alpha=0.6, label='Manual (Control)', color='#3498db', edgecolor='black')
    axes[0].hist(treatment, bins=20, alpha=0.6, label='Auto (Treatment)', color='#e74c3c', edgecolor='black')
    axes[0].axvline(control.mean(), color='#3498db', linestyle='--', linewidth=2, label=f'Manual Mean: {control.mean():.2f}')
    axes[0].axvline(treatment.mean(), color='#e74c3c', linestyle='--', linewidth=2, label=f'Auto Mean: {treatment.mean():.2f}')
    axes[0].set_xlabel(metric, fontsize=12, fontweight='bold')
    axes[0].set_ylabel('Frequency', fontsize=12, fontweight='bold')
    axes[0].set_title(f'{metric} Distribution: Manual vs Auto Bidding', fontsize=13, fontweight='bold')
    axes[0].legend(fontsize=10)
    axes[0].grid(alpha=0.3)
    
    # 2. Box plot comparison
    data_to_plot = [control, treatment]
    bp = axes[1].boxplot(data_to_plot, labels=['Manual', 'Auto'], patch_artist=True,
                         boxprops=dict(facecolor='lightblue', color='black'),
                         medianprops=dict(color='red', linewidth=2),
                         whiskerprops=dict(color='black'),
                         capprops=dict(color='black'))
    axes[1].set_ylabel(metric, fontsize=12, fontweight='bold')
    axes[1].set_title(f'{metric} Comparison', fontsize=13, fontweight='bold')
    axes[1].grid(axis='y', alpha=0.3)
    
    # Add statistical annotation
    significance = "Statistically Significant" if results['is_significant'] else "Not Significant"
    effect_size = "Large" if abs(results['cohens_d']) > 0.8 else "Medium" if abs(results['cohens_d']) > 0.5 else "Small"
    
    annotation_text = (
        f"Lift: {results['lift_percent']:+.1f}%\n"
        f"p-value: {results['p_value']:.4f}\n"
        f"{significance}\n"
        f"Effect Size: {effect_size} (d={results['cohens_d']:.2f})"
    )
    
    axes[1].text(
        0.5, 0.98, annotation_text,
        transform=axes[1].transAxes,
        ha='center', va='top',
        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.8),
        fontsize=10, fontweight='bold'
    )
    
    plt.tight_layout()
    plt.savefig(f'../images/week4_abtest_{metric.lower()}.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print(f"{metric} visualization saved")

# ============================================
# 4. COMPREHENSIVE REPORT
# ============================================

def generate_ab_report(all_results):
    """Generate comprehensive A/B test report"""
    
    print("\n" + "="*70)
    print("A/B TEST RESULTS: MANUAL VS AUTO BIDDING")
    print("="*70)
    
    report_df = pd.DataFrame(all_results).T
    
    for metric in report_df.index:
        row = report_df.loc[metric]
        
        print(f"\n{'='*70}")
        print(f"{metric.upper()}")
        print(f"{'='*70}")
        print(f"  Control (Manual):   {row['control_mean']:.3f} (n={int(row['control_n'])}, std={row['control_std']:.3f})")
        print(f"  Treatment (Auto):   {row['treatment_mean']:.3f} (n={int(row['treatment_n'])}, std={row['treatment_std']:.3f})")
        print(f"  Lift:               {row['lift_percent']:+.2f}%")
        print(f"  P-value:            {row['p_value']:.4f}")
        print(f"  Significant:        {'YES' if row['is_significant'] else 'NO'} (α=0.05)")
        print(f"  Effect Size (d):    {row['cohens_d']:.3f} ", end="")
        
        # Interpret effect size
        abs_d = abs(row['cohens_d'])
        if abs_d < 0.2:
            print("(Negligible)")
        elif abs_d < 0.5:
            print("(Small)")
        elif abs_d < 0.8:
            print("(Medium)")
        else:
            print("(Large)")
        
        # Business recommendation
        print(f"\nRecommendation:")
        if row['is_significant'] and row['lift_percent'] > 5:
            print(f"Auto-bidding shows {row['lift_percent']:.1f}% improvement")
            print(f"Consider promoting Auto-bidding to users")
        elif row['is_significant'] and row['lift_percent'] < -5:
            print(f"Manual bidding performs {abs(row['lift_percent']):.1f}% better")
            print(f"Investigate Auto-bidding algorithm issues")
        else:
            print(f"No significant difference detected")
            print(f"May need larger sample size or longer test duration")
    
    print("\n" + "="*70)
    
    return report_df

# ============================================
# 5. SAVE RESULTS
# ============================================

def save_results(report_df, all_results):
    """Save test results"""
    
    print("\nSaving results...")
    
    # Save detailed results
    report_df.to_csv('ab_test_results.csv')
    print("Results saved to ab_test_results.csv")
    
    # Create summary
    summary = []
    for metric, results in all_results.items():
        summary.append({
            'metric': metric,
            'winner': 'Auto' if results['treatment_mean'] > results['control_mean'] else 'Manual',
            'lift_percent': results['lift_percent'],
            'significant': results['is_significant'],
            'recommendation': 'Adopt Auto' if results['is_significant'] and results['lift_percent'] > 5 else 'Keep Testing'
        })
    
    summary_df = pd.DataFrame(summary)
    summary_df.to_csv('ab_test_summary.csv', index=False)
    print("Summary saved to ab_test_summary.csv")

# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    
    # Load data
    df = load_ab_test_data()
    
    if len(df) < 10:
        print("\nWarning: Very small sample size - results may not be reliable")
        print("This is expected with synthetic data.")
    
    # Analyze multiple metrics
    all_results = {}
    metrics_to_test = ['roas', 'cvr', 'cpc']
    
    print("\n" + "="*70)
    print("RUNNING A/B TESTS")
    print("="*70)
    
    for metric in metrics_to_test:
        print(f"\nAnalyzing {metric.upper()}...")
        results, control, treatment = run_ab_analysis(df, metric)
        
        if results is not None:
            all_results[metric] = results
            visualize_ab_test(control, treatment, results, metric.upper())
        else:
            print(f"Insufficient data for {metric}")
    
    if len(all_results) > 0:
        # Generate report
        report = generate_ab_report(all_results)
        
        # Save results
        save_results(report, all_results)
        
        print("\n" + "="*70)
        print("WEEK 4: A/B TESTING FRAMEWORK COMPLETE!")
        print("="*70)
    else:
        print("\nNo valid A/B test results - insufficient data")
        print("Framework is ready but needs more diverse bidding strategy data")