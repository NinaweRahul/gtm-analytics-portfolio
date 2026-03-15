"""
Customer Lifetime Value Prediction Model 
Predict 12-month LTV using first 30 days of behavior
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import LabelEncoder
import matplotlib.pyplot as plt
import seaborn as sns
import joblib
import sys
import os

sys.path.append('../shared-sql')
from db_config import get_engine

# Set style
sns.set_style('whitegrid')
plt.rcParams['figure.figsize'] = (12, 6)

print("="*70)
print("WEEK 2: CUSTOMER LTV PREDICTION MODEL")
print("="*70)

# ============================================
# 1. FEATURE ENGINEERING
# ============================================

def create_ltv_features():
    """
    Create features from first 30 days to predict 90-day LTV
    Modified to work with 90-day dataset
    """
    
    print("\nCreating LTV prediction features...")
    
    engine = get_engine()
    
    query = """
    WITH account_first_30 AS (
        SELECT 
            a.account_id,
            a.segment,
            a.region,
            a.signup_date,
            
            -- First 30-day metrics
            COALESCE(SUM(CASE WHEN ae.date <= a.signup_date + 30 THEN ae.spend END), 0) as spend_30d,
            COALESCE(SUM(CASE WHEN ae.date <= a.signup_date + 30 THEN ae.clicks END), 0) as clicks_30d,
            COALESCE(SUM(CASE WHEN ae.date <= a.signup_date + 30 THEN ae.conversions END), 0) as conversions_30d,
            
            -- Campaign diversity
            COUNT(DISTINCT CASE WHEN ae.date <= a.signup_date + 30 THEN c.campaign_id END) as num_campaigns_30d,
            COUNT(DISTINCT CASE WHEN ae.date <= a.signup_date + 30 THEN c.product_type END) as num_product_types_30d,
            
            -- Activity patterns
            COUNT(DISTINCT CASE WHEN ae.date <= a.signup_date + 30 THEN ae.date END) as active_days_30d,
            MIN(CASE WHEN ae.spend > 0 THEN ae.date END) - a.signup_date as days_to_first_spend,
            
            -- Target: 90-day LTV (total spend in 90 days)
            COALESCE(SUM(CASE WHEN ae.date <= a.signup_date + 90 THEN ae.spend END), 0) as ltv_90d
            
        FROM accounts a
        LEFT JOIN campaigns c ON a.account_id = c.account_id
        LEFT JOIN ad_events ae ON c.campaign_id = ae.campaign_id
        
        WHERE a.signup_date <= CURRENT_DATE - 60  -- At least 60 days old
        AND a.account_status = 'Active'
        
        GROUP BY a.account_id, a.segment, a.region, a.signup_date
    )
    SELECT * FROM account_first_30
    WHERE spend_30d > 0  -- Only activated accounts
    """
    
    df = pd.read_sql(text(query), engine)
    print(f"Loaded {len(df)} accounts with 60+ days of history")
    print(f"Predicting 90-day LTV from first 30 days")
    
    return df

# ============================================
# 2. PREPARE TRAINING DATA
# ============================================

def prepare_training_data(df):
    """Encode categorical variables and split data"""
           
    # Encode categoricals
    le_segment = LabelEncoder()
    le_region = LabelEncoder()
    
    df['segment_encoded'] = le_segment.fit_transform(df['segment'])
    df['region_encoded'] = le_region.fit_transform(df['region'])
    
    # Create additional features
    df['spend_per_day_30d'] = df['spend_30d'] / df['active_days_30d'].replace(0, 1)
    df['clicks_per_campaign'] = df['clicks_30d'] / df['num_campaigns_30d'].replace(0, 1)
    df['conversions_per_click'] = df['conversions_30d'] / df['clicks_30d'].replace(0, 1)
    
    # Handle infinities and NaNs
    df['days_to_first_spend'] = df['days_to_first_spend'].fillna(30)  # If never spent, use 30
    df.replace([np.inf, -np.inf], 0, inplace=True)
    df.fillna(0, inplace=True)
    
    # Select features
    feature_cols = [
        'segment_encoded', 'region_encoded',
        'spend_30d', 'clicks_30d', 'conversions_30d',
        'num_campaigns_30d', 'num_product_types_30d', 'active_days_30d',
        'days_to_first_spend',
        'spend_per_day_30d', 'clicks_per_campaign', 'conversions_per_click'
    ]
    
    X = df[feature_cols]
    y = df['ltv_90d']
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )
    
    print(f"Training set: {len(X_train)} samples")
    print(f"Test set: {len(X_test)} samples")
    print(f"Features: {len(feature_cols)}")
    
    return X_train, X_test, y_train, y_test, feature_cols, (le_segment, le_region)

# ============================================
# 3. TRAIN MODEL
# ============================================

def train_ltv_model(X_train, y_train, X_test, y_test):
    """Train Random Forest model"""
    
    print("\nTraining LTV prediction model...")
    
    model = RandomForestRegressor(
        n_estimators=100,
        max_depth=15,
        min_samples_split=10,
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    
    # Predictions
    y_pred_train = model.predict(X_train)
    y_pred_test = model.predict(X_test)
    
    # Metrics
    results = {
        'train_r2': r2_score(y_train, y_pred_train),
        'test_r2': r2_score(y_test, y_pred_test),
        'train_mae': mean_absolute_error(y_train, y_pred_train),
        'test_mae': mean_absolute_error(y_test, y_pred_test),
        'train_rmse': np.sqrt(mean_squared_error(y_train, y_pred_train)),
        'test_rmse': np.sqrt(mean_squared_error(y_test, y_pred_test))
    }
    
    print(f"\nModel Performance:")
    print(f"Test R-square Score: {results['test_r2']:.3f}")
    print(f"Test MAE: ${results['test_mae']:,.2f}")
    print(f"Test RMSE: ${results['test_rmse']:,.2f}")
    
    return model, results, y_pred_test

# ============================================
# 4. VISUALIZE RESULTS
# ============================================

def visualize_results(model, feature_cols, X_test, y_test, y_pred_test):
    """Create visualizations for model results"""
    
    print("\nCreating visualizations...")
    
    # Feature importance
    importances = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nTop 10 Most Important Features:")
    print(importances.head(10).to_string(index=False))
    
    # Create visualizations
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Feature importance
    importances.head(10).plot(
        x='feature', y='importance', kind='barh', 
        ax=axes[0,0], color='steelblue', legend=False
    )
    axes[0,0].set_title('Top 10 Feature Importance', fontsize=14, fontweight='bold')
    axes[0,0].set_xlabel('Importance', fontsize=12)
    axes[0,0].invert_yaxis()
    
    # 2. Actual vs Predicted
    axes[0,1].scatter(y_test, y_pred_test, alpha=0.5, s=30)
    axes[0,1].plot([y_test.min(), y_test.max()], 
                   [y_test.min(), y_test.max()], 
                   'r--', lw=2, label='Perfect Prediction')
    axes[0,1].set_xlabel('Actual 12-Month LTV ($)', fontsize=12)
    axes[0,1].set_ylabel('Predicted 12-Month LTV ($)', fontsize=12)
    axes[0,1].set_title('Actual vs Predicted LTV', fontsize=14, fontweight='bold')
    axes[0,1].legend()
    axes[0,1].grid(alpha=0.3)
    
    # 3. Residuals
    residuals = y_test - y_pred_test
    axes[1,0].scatter(y_pred_test, residuals, alpha=0.5, s=30)
    axes[1,0].axhline(y=0, color='r', linestyle='--', lw=2)
    axes[1,0].set_xlabel('Predicted LTV ($)', fontsize=12)
    axes[1,0].set_ylabel('Residuals ($)', fontsize=12)
    axes[1,0].set_title('Residual Plot', fontsize=14, fontweight='bold')
    axes[1,0].grid(alpha=0.3)
    
    # 4. Prediction error distribution
    axes[1,1].hist(residuals, bins=50, edgecolor='black', alpha=0.7)
    axes[1,1].axvline(x=0, color='r', linestyle='--', lw=2)
    axes[1,1].set_xlabel('Prediction Error ($)', fontsize=12)
    axes[1,1].set_ylabel('Frequency', fontsize=12)
    axes[1,1].set_title('Distribution of Prediction Errors', fontsize=14, fontweight='bold')
    axes[1,1].grid(alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('../images/week2_ltv_model_results.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print("Visualizations saved to ../images/week2_ltv_model_results.png")
    
    return importances

# ============================================
# 5. SAVE MODEL
# ============================================

def save_model(model, results, importances):
    """Save model and results"""
    
    print("\nSaving model...")
    
    # Create models directory if needed
    os.makedirs('../models', exist_ok=True)
    
    # Save model
    joblib.dump(model, '../models/ltv_model.pkl')
    print("Model saved to ../models/ltv_model.pkl")
    
     # Save results
    results_df = pd.DataFrame([results])
    results_df.to_csv('ltv_model_results.csv', index=False)
    print("Results saved to ltv_model_results.csv")
    
    # Save feature importance
    importances.to_csv('ltv_feature_importance.csv', index=False)
    print("Feature importance saved to ltv_feature_importance.csv")

# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    
    # Load and prepare data
    df = create_ltv_features()
    
    if len(df) < 50:
        print("\nWarning: Not enough data (need accounts with 12+ months history)")
    
    X_train, X_test, y_train, y_test, feature_cols, encoders = prepare_training_data(df)
    
    # Train model
    model, results, y_pred_test = train_ltv_model(X_train, y_train, X_test, y_test)
    
    # Visualize
    importances = visualize_results(model, feature_cols, X_test, y_test, y_pred_test)
    
    # Save
    save_model(model, results, importances)
    
    print("\n" + "="*70)
    print("WEEK 2: LTV MODEL COMPLETE!")
    print("="*70)
    print(f"\nKey Metrics:")
    print(f"R-square Score: {results['test_r2']:.3f} (explains {results['test_r2']*100:.1f}% of variance)")
    print(f"Predicting 90-day LTV from first 30 days of behavior")
    print(f"Average Error: ${results['test_mae']:,.2f}")
    print(f"\nTop Predictor: {importances.iloc[0]['feature']}")