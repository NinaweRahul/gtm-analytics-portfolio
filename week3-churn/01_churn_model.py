"""
Churn Prediction Model
Predict which active accounts are at risk of churning
Churn = No spend for 15+ consecutive days after being active
"""

import pandas as pd
import numpy as np
from sqlalchemy import text
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, roc_auc_score, confusion_matrix, roc_curve
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
print("WEEK 3: CHURN RISK PREDICTION MODEL")
print("="*70)

# ============================================
# 1. CREATE CHURN FEATURES
# ============================================

def create_churn_features():
    """
    Create features to predict churn
    Churn = no activity in last 30 days after being active
    """
    
    print("\nCreating churn prediction features...")
    
    engine = get_engine()
    
    query = """
    WITH account_activity AS (
        SELECT 
            a.account_id,
            a.segment,
            a.region,
            a.signup_date,
            
            -- Recent activity (last 15 days)
            COALESCE(SUM(CASE WHEN ae.date >= CURRENT_DATE - 15 THEN ae.spend END), 0) as spend_last_15d,
            COALESCE(SUM(CASE WHEN ae.date >= CURRENT_DATE - 15 THEN ae.clicks END), 0) as clicks_last_15d,
            COALESCE(AVG(CASE WHEN ae.date >= CURRENT_DATE - 15 THEN ae.spend END), 0) as avg_daily_spend_15d,
            
            -- Previous period (15-30 days ago)
            COALESCE(SUM(CASE WHEN ae.date BETWEEN CURRENT_DATE - 30 AND CURRENT_DATE - 16 THEN ae.spend END), 0) as spend_prev_15d,
            
            -- Overall metrics
            COALESCE(SUM(ae.spend), 0) as total_spend,
            COUNT(DISTINCT ae.date) as total_active_days,
            MAX(ae.date) as last_activity_date,
            
            -- Campaign metrics
            COUNT(DISTINCT c.campaign_id) as total_campaigns,
            COUNT(DISTINCT c.product_type) as num_product_types,
            
            -- Performance trend
            COALESCE(AVG(ae.spend / NULLIF(ae.clicks, 0)), 0) as avg_cpc
            
        FROM accounts a
        LEFT JOIN campaigns c ON a.account_id = c.account_id
        LEFT JOIN ad_events ae ON c.campaign_id = ae.campaign_id
        
        WHERE a.account_status = 'Active'
        AND a.signup_date <= CURRENT_DATE - 45  -- At least 45 days old
        
        GROUP BY a.account_id, a.segment, a.region, a.signup_date
    )
    SELECT *,
           -- Spend change indicator
           CASE WHEN spend_prev_15d > 0 
                THEN (spend_last_15d - spend_prev_15d) / spend_prev_15d 
                ELSE 0 END as spend_change_ratio,
           
           -- Days since last activity
           CURRENT_DATE - last_activity_date as days_since_last_activity,
           
           -- Churn label: no spend in last 15 days but was active before
           CASE 
               WHEN last_activity_date < CURRENT_DATE - 15 AND total_spend > 0 THEN 1
               ELSE 0
           END as is_churned
           
    FROM account_activity
    WHERE total_spend > 0  -- Only accounts that were ever active
    """
    
    df = pd.read_sql(text(query), engine)
    
    print(f"Loaded {len(df)} active accounts")
    print(f"Churned: {df['is_churned'].sum()} ({df['is_churned'].mean()*100:.1f}%)")
    print(f"Active: {len(df) - df['is_churned'].sum()} ({(1-df['is_churned'].mean())*100:.1f}%)")
    
    return df

# ============================================
# 2. PREPARE TRAINING DATA
# ============================================

def prepare_churn_data(df):
    """Prepare data for classification"""
    
    print("\nPreparing training data...")
    
    # Encode categoricals
    le_segment = LabelEncoder()
    le_region = LabelEncoder()
    
    df['segment_encoded'] = le_segment.fit_transform(df['segment'])
    df['region_encoded'] = le_region.fit_transform(df['region'])
    
    # Handle infinities and NaNs
    df.replace([np.inf, -np.inf], 0, inplace=True)
    df.fillna(0, inplace=True)
    
    # Feature selection
    feature_cols = [
        'segment_encoded', 'region_encoded',
        'spend_last_15d', 'clicks_last_15d', 'avg_daily_spend_15d',
        'spend_prev_15d', 'total_spend', 'total_active_days',
        'total_campaigns', 'num_product_types',
        'avg_cpc', 'spend_change_ratio', 'days_since_last_activity'
    ]
    
    X = df[feature_cols]
    y = df['is_churned']
    
    # Check class balance
    churn_rate = y.mean()
    print(f"Churn rate: {churn_rate*100:.1f}%")
    
    if churn_rate < 0.05 or churn_rate > 0.95:
        print("Warning: Highly imbalanced classes")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    
    print(f"Training set: {len(X_train)} ({y_train.mean()*100:.1f}% churn)")
    print(f"Test set: {len(X_test)} ({y_test.mean()*100:.1f}% churn)")
    
    return X_train, X_test, y_train, y_test, feature_cols

# ============================================
# 3. TRAIN CHURN MODEL
# ============================================

def train_churn_model(X_train, y_train, X_test, y_test):
    """Train Random Forest classifier"""
    
    print("\nTraining churn prediction model...")
    
    model = RandomForestClassifier(
        n_estimators=100,
        max_depth=10,
        min_samples_split=20,
        class_weight='balanced',  # Handle imbalanced classes
        random_state=42,
        n_jobs=-1
    )
    
    model.fit(X_train, y_train)
    
    # Predictions
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)
    
    # Handle case where predict_proba only has one class
    if y_pred_proba.shape[1] == 1:
        # Only one class in training data, create dummy probabilities
        y_pred_proba_full = np.zeros((len(y_pred_proba), 2))
        y_pred_proba_full[:, 0] = y_pred_proba[:, 0]
        y_pred_proba = y_pred_proba_full[:, 1]
    else:
        y_pred_proba = y_pred_proba[:, 1]
    
    # Metrics
    print("\nModel Results:")
    
    # Check if test set has both classes
    unique_test = np.unique(y_test)
    unique_pred = np.unique(y_pred)
    
    if len(unique_test) > 1 and len(unique_pred) > 1:
        print(classification_report(y_test, y_pred, target_names=['Active', 'Churned']))
    else:
        print(f"Test set churn rate: {y_test.mean()*100:.1f}%")
        print(f"Predictions: {y_pred.sum()} churned out of {len(y_pred)}")
        print("Limited test set - all accounts have same class")
    
    try:
        if len(unique_test) > 1:
            roc_auc = roc_auc_score(y_test, y_pred_proba)
            print(f"\nROC-AUC Score: {roc_auc:.3f}")
        else:
            roc_auc = 0.5
            print(f"\nROC-AUC: Not calculable (single class in test set)")
    except:
        roc_auc = 0.5
        print(f"\nROC-AUC: Not calculable")
    
    return model, y_pred, y_pred_proba, roc_auc

# ============================================
# 4. VISUALIZE RESULTS
# ============================================

def visualize_results(model, feature_cols, y_test, y_pred, y_pred_proba, roc_auc):
    """Create visualizations"""
    
    print("\nCreating visualizations...")
    
    fig, axes = plt.subplots(2, 2, figsize=(16, 12))
    
    # 1. Feature importance
    importances = pd.DataFrame({
        'feature': feature_cols,
        'importance': model.feature_importances_
    }).sort_values('importance', ascending=False)
    
    print("\nTop 10 Risk Indicators:")
    print(importances.head(10).to_string(index=False))
    
    importances.head(10).plot(
        x='feature', y='importance', kind='barh',
        ax=axes[0,0], color='coral', legend=False
    )
    axes[0,0].set_title('Top 10 Churn Risk Indicators', fontsize=14, fontweight='bold')
    axes[0,0].set_xlabel('Importance', fontsize=12)
    axes[0,0].invert_yaxis()
    
    # 2. Confusion Matrix
    cm = confusion_matrix(y_test, y_pred)
    sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=axes[0,1],
                xticklabels=['Active', 'Churned'],
                yticklabels=['Active', 'Churned'])
    axes[0,1].set_title('Confusion Matrix', fontsize=14, fontweight='bold')
    axes[0,1].set_ylabel('Actual', fontsize=12)
    axes[0,1].set_xlabel('Predicted', fontsize=12)
    
    # 3. ROC Curve
    if len(np.unique(y_test)) > 1:
        fpr, tpr, _ = roc_curve(y_test, y_pred_proba)
        axes[1,0].plot(fpr, tpr, linewidth=2, label=f'ROC Curve (AUC = {roc_auc:.3f})')
        axes[1,0].plot([0, 1], [0, 1], 'k--', linewidth=2, label='Random Classifier')
        axes[1,0].set_xlabel('False Positive Rate', fontsize=12)
        axes[1,0].set_ylabel('True Positive Rate', fontsize=12)
        axes[1,0].set_title('ROC Curve', fontsize=14, fontweight='bold')
        axes[1,0].legend()
        axes[1,0].grid(alpha=0.3)
    
    # 4. Risk Score Distribution
    axes[1,1].hist(y_pred_proba[y_test == 0], bins=20, alpha=0.7, label='Active Accounts', color='green')
    axes[1,1].hist(y_pred_proba[y_test == 1], bins=20, alpha=0.7, label='Churned Accounts', color='red')
    axes[1,1].set_xlabel('Churn Probability', fontsize=12)
    axes[1,1].set_ylabel('Frequency', fontsize=12)
    axes[1,1].set_title('Churn Risk Score Distribution', fontsize=14, fontweight='bold')
    axes[1,1].legend()
    axes[1,1].grid(alpha=0.3)
    
    plt.tight_layout()
    plt.savefig('../images/week3_churn_model_results.png', dpi=300, bbox_inches='tight')
    plt.show()
    
    print("Visualizations saved")
    
    return importances

# ============================================
# 5. SAVE MODEL
# ============================================

def save_model(model, importances, roc_auc):
    """Save model and results"""
    
    print("\nSaving model...")
    
    os.makedirs('../models', exist_ok=True)
    
    joblib.dump(model, '../models/churn_model.pkl')
    print("Model saved to ../models/churn_model.pkl")
    
    importances.to_csv('churn_feature_importance.csv', index=False)
    print("Feature importance saved")
    
    results = pd.DataFrame([{'roc_auc': roc_auc}])
    results.to_csv('churn_model_results.csv', index=False)
    print("Results saved")

# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    
    # Create features
    df = create_churn_features()
    
    if len(df) < 20:
        print("\nWarning: Very small dataset - results may not be reliable")
    
    # Prepare data
    X_train, X_test, y_train, y_test, features = prepare_churn_data(df)
    
    # Train model
    model, y_pred, y_pred_proba, roc_auc = train_churn_model(X_train, y_train, X_test, y_test)
    
    # Visualize
    importances = visualize_results(model, features, y_test, y_pred, y_pred_proba, roc_auc)
    
    # Save
    save_model(model, importances, roc_auc)
    
    print("\n" + "="*70)
    print("WEEK 3: CHURN MODEL COMPLETE!")
    print("="*70)
    print(f"\nKey Metrics:")
    print(f"ROC-AUC Score: {roc_auc:.3f}")
    print(f"Top Risk Indicator: {importances.iloc[0]['feature']}")
