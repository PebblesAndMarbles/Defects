import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report, confusion_matrix, roc_auc_score, precision_recall_curve, auc
from sklearn.model_selection import cross_val_score, StratifiedKFold
import matplotlib.pyplot as plt
import seaborn as sns
from collections import defaultdict
import warnings
warnings.filterwarnings('ignore')

def prepare_data_for_modeling(file_path):
    """
    Load and prepare data for Random Forest modeling with temporal structure
    """
    print("Loading and preparing data...")
    
    # Load data
    df = pd.read_csv(file_path)
    
    # Convert timestamp to datetime
    df['SUBENTITY_END_TIME'] = pd.to_datetime(df['SUBENTITY_END_TIME'])
    df['year_month'] = df['SUBENTITY_END_TIME'].dt.to_period('M')
    
    # Define feature columns (existing ones from your analysis)
    numeric_features = [
        'S_ORDER', 'S_SCAN', 'N_SCAN', 'SIF_SED', 'SIF_ETCH', 'SIF_DEFECT', 'P_ORDER',
        'FULLPM', 'FULLPM_RF', 'MINIPM', 'MINIPM_RF', 'CNTR_SS', 'PT_BTWN', 'UPT_12HRS',
        'UNW_12HRS', 'UP_12HRS', 'RAW_LEAK_RATE', 'SMOOTH_LEAK_RATE', 'DP_FAIL_15',
        'DP_FAIL_30', 'DP_FAIL_60', 'CH_BP_05_RATE', 'CH_SP_05_RATE', 'CH_BP_05',
        'CH_SP_05', 'CH_05_MWAF', 'CH_BP_10_RATE', 'CH_SP_10_RATE', 'CH_BP_10',
        'CH_SP_10', 'CH_10_MWAF', 'CH_BP_15_RATE', 'CH_SP_15_RATE', 'CH_BP_15',
        'CH_SP_15', 'CH_15_MWAF', 'CH_BP_30_RATE', 'CH_SP_30_RATE', 'CH_BP_30',
        'CH_SP_30', 'CH_30_MWAF', 'FL_BP_05_RATE', 'FL_SP_05_RATE', 'FL_BP_05',
        'FL_SP_05', 'FL_05_MWAF', 'FL_BP_10_RATE', 'FL_SP_10_RATE', 'FL_BP_10',
        'FL_SP_10', 'FL_10_MWAF', 'FL_BP_15_RATE', 'FL_SP_15_RATE', 'FL_BP_15',
        'FL_SP_15', 'FL_15_MWAF', 'FL_BP_30_RATE', 'FL_SP_30_RATE', 'FL_BP_30',
        'FL_SP_30', 'FL_30_MWAF', 'CF_BP_05_RRAT', 'CF_SP_05_RRAT', 'CF_BP_05_DRAT',
        'CF_SP_05_DRAT', 'CF_BP_10_RRAT', 'CF_SP_10_RRAT', 'CF_BP_10_DRAT',
        'CF_SP_10_DRAT', 'CF_BP_15_RRAT', 'CF_SP_15_RRAT', 'CF_BP_15_DRAT',
        'CF_SP_15_DRAT', 'CF_BP_30_RRAT', 'CF_SP_30_RRAT', 'CF_BP_30_DRAT',
        'CF_SP_30_DRAT', 'CH_05_NWAF', 'FL_05_NWAF', 'CH_05_AWAF', 'FL_05_AWAF',
        'CH_10_NWAF', 'FL_10_NWAF', 'CH_10_AWAF', 'FL_10_AWAF', 'CH_15_NWAF',
        'FL_15_NWAF', 'CH_15_AWAF', 'FL_15_AWAF', 'CH_30_NWAF', 'FL_30_NWAF',
        'CH_30_AWAF', 'FL_30_AWAF', 'CH_SS_5_TA', 'CH_SS_5_TA_CLASS', 'CH_SS_5_N',
        'FL_SS_5_TA', 'FL_SS_5_N', 'CH_SS_5_LA', 'CH_SS_5_LA_CLASS', 'FL_SS_5_LA',
        'CH_SS_5_AC', 'CH_SS_5_AC_CLASS', 'FL_SS_5_AC', 'CH_SS_5_CA', 'CH_SS_5_CA_CLASS',
        'FL_SS_5_CA', 'CH_SS_10_TA', 'CH_SS_10_TA_CLASS', 'CH_SS_10_N', 'FL_SS_10_TA',
        'FL_SS_10_N', 'CH_SS_10_LA', 'CH_SS_10_LA_CLASS', 'FL_SS_10_LA', 'CH_SS_10_AC',
        'CH_SS_10_AC_CLASS', 'FL_SS_10_AC', 'CH_SS_10_CA', 'CH_SS_10_CA_CLASS',
        'FL_SS_10_CA', 'CH_SS_15_TA', 'CH_SS_15_TA_CLASS', 'CH_SS_15_N', 'FL_SS_15_TA',
        'FL_SS_15_N', 'CH_SS_15_LA', 'CH_SS_15_LA_CLASS', 'FL_SS_15_LA', 'CH_SS_15_AC',
        'CH_SS_15_AC_CLASS', 'FL_SS_15_AC', 'CH_SS_15_CA', 'CH_SS_15_CA_CLASS',
        'FL_SS_15_CA', 'CH_SS_30_TA', 'CH_SS_30_TA_CLASS', 'CH_SS_30_N', 'FL_SS_30_TA',
        'FL_SS_30_N', 'CH_SS_30_LA', 'CH_SS_30_LA_CLASS', 'FL_SS_30_LA', 'CH_SS_30_AC',
        'CH_SS_30_AC_CLASS', 'FL_SS_30_AC', 'CH_SS_30_CA', 'CH_SS_30_CA_CLASS',
        'FL_SS_30_CA', 'CH_SS_DAYS'
    ]
    
    categorical_features = [
        'LAYER', 'DEVICE', 'PRODUCT', 'ROUTE', 'STEPPER', 'RETICLE', 'ENTITY',
        'CCMR2', 'ICCR2', 'GF', 'CV', 'SRCIP', 'PL_RECIPE'
    ]
    
    # Filter to existing columns
    numeric_features = [col for col in numeric_features if col in df.columns]
    categorical_features = [col for col in categorical_features if col in df.columns]
    
    print(f"Using {len(numeric_features)} numeric features and {len(categorical_features)} categorical features")
    
    # Create binary targets (convert rates to binary classification)
    # Using threshold of 0 (any defect presence)
    df['BP_BINARY'] = (df['BP_RATE'] > 0).astype(int)
    df['SP_BINARY'] = (df['SP_RATE'] > 0).astype(int)
    
    print(f"BP_BINARY distribution: {df['BP_BINARY'].value_counts().to_dict()}")
    print(f"SP_BINARY distribution: {df['SP_BINARY'].value_counts().to_dict()}")
    
    return df, numeric_features, categorical_features

def encode_categorical_features(df, categorical_features, train_mask=None):
    """
    Encode categorical features using label encoding
    """
    df_encoded = df.copy()
    encoders = {}
    
    for col in categorical_features:
        if col in df.columns:
            le = LabelEncoder()
            if train_mask is not None:
                # Fit only on training data
                le.fit(df.loc[train_mask, col].astype(str))
                df_encoded[col] = le.transform(df[col].astype(str))
            else:
                # Fit on all data (for initial encoding)
                df_encoded[col] = le.fit_transform(df[col].astype(str))
            encoders[col] = le
    
    return df_encoded, encoders

def create_temporal_splits(df):
    """
    Create temporal train/test splits
    Train: Through June 2025
    Test: Each subsequent month separately
    """
    # Define training cutoff (end of June 2025)
    train_cutoff = pd.Timestamp('2025-06-30')
    
    # Training data
    train_mask = df['SUBENTITY_END_TIME'] <= train_cutoff
    train_data = df[train_mask].copy()
    
    # Test data by month
    test_months = df[df['SUBENTITY_END_TIME'] > train_cutoff]['year_month'].unique()
    test_months = sorted(test_months)
    
    test_splits = {}
    for month in test_months:
        month_mask = df['year_month'] == month
        test_splits[str(month)] = df[month_mask].copy()
    
    print(f"Training data: {len(train_data)} records (through {train_cutoff.strftime('%Y-%m-%d')})")
    print(f"Test months: {len(test_splits)} months")
    for month, data in test_splits.items():
        print(f"  {month}: {len(data)} records")
    
    return train_data, test_splits

def train_random_forest_model(X_train, y_train, target_name):
    """
    Train Random Forest model with cross-validation
    """
    print(f"\nTraining Random Forest for {target_name}...")
    
    # Handle class imbalance with balanced class weights
    rf = RandomForestClassifier(
        n_estimators=200,
        max_depth=15,
        min_samples_split=10,
        min_samples_leaf=5,
        max_features='sqrt',
        class_weight='balanced',
        random_state=42,
        n_jobs=-1
    )
    
    # Cross-validation on training data
    cv_scores = cross_val_score(rf, X_train, y_train, cv=5, scoring='roc_auc')
    print(f"Cross-validation AUC scores: {cv_scores}")
    print(f"Mean CV AUC: {cv_scores.mean():.4f} (+/- {cv_scores.std() * 2:.4f})")
    
    # Train final model
    rf.fit(X_train, y_train)
    
    return rf

def evaluate_model_performance(model, X_test, y_test, month_name, target_name):
    """
    Evaluate model performance on test data
    """
    # Predictions
    y_pred = model.predict(X_test)
    y_pred_proba = model.predict_proba(X_test)[:, 1]
    
    # Metrics
    auc_score = roc_auc_score(y_test, y_pred_proba)
    
    # Precision-Recall AUC
    precision, recall, _ = precision_recall_curve(y_test, y_pred_proba)
    pr_auc = auc(recall, precision)
    
    # Classification report
    class_report = classification_report(y_test, y_pred, output_dict=True)
    
    # Confusion matrix
    cm = confusion_matrix(y_test, y_pred)
    
    results = {
        'month': month_name,
        'target': target_name,
        'n_samples': len(y_test),
        'n_positive': y_test.sum(),
        'positive_rate': y_test.mean(),
        'auc_roc': auc_score,
        'auc_pr': pr_auc,
        'precision_1': class_report['1']['precision'] if '1' in class_report else 0,
        'recall_1': class_report['1']['recall'] if '1' in class_report else 0,
        'f1_1': class_report['1']['f1-score'] if '1' in class_report else 0,
        'precision_0': class_report['0']['precision'] if '0' in class_report else 0,
        'recall_0': class_report['0']['recall'] if '0' in class_report else 0,
        'f1_0': class_report['0']['f1-score'] if '0' in class_report else 0,
        'accuracy': class_report['accuracy'],
        'tn': cm[0,0] if cm.shape == (2,2) else 0,
        'fp': cm[0,1] if cm.shape == (2,2) else 0,
        'fn': cm[1,0] if cm.shape == (2,2) else 0,
        'tp': cm[1,1] if cm.shape == (2,2) else 0
    }
    
    return results

def get_feature_importance(model, feature_names, top_n=20):
    """
    Get top feature importances
    """
    importances = model.feature_importances_
    feature_importance_df = pd.DataFrame({
        'feature': feature_names,
        'importance': importances
    }).sort_values('importance', ascending=False)
    
    return feature_importance_df.head(top_n)

def run_comprehensive_analysis():
    """
    Run the complete Random Forest analysis with temporal validation
    """
    # File paths
    input_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\8M5CL_8M6CL_2025_LOT.csv"
    output_path = r"\\orshfs.intel.com\ORAnalysis$\1276_MAODATA\Config\etch\AME\tbatson\Defects\BE\RF_TRAIN_TEST_VALIDATION.csv"
    
    # Load and prepare data
    df, numeric_features, categorical_features = prepare_data_for_modeling(input_path)
    
    # Create temporal splits
    train_data, test_splits = create_temporal_splits(df)
    
    # Encode categorical features (fit on training data only)
    train_encoded, encoders = encode_categorical_features(
        train_data, categorical_features, train_mask=None
    )
    
    # Prepare feature matrix for training
    all_features = numeric_features + categorical_features
    X_train = train_encoded[all_features].fillna(0)  # Simple imputation
    
    # Results storage
    all_results = []
    feature_importance_results = {}
    
    # Train models for both targets
    targets = ['BP_BINARY', 'SP_BINARY']
    models = {}
    
    for target in targets:
        target_name = target.replace('_BINARY', '')
        y_train = train_encoded[target]
        
        print(f"\n{'='*60}")
        print(f"TRAINING MODEL FOR {target_name}")
        print(f"{'='*60}")
        
        # Train model
        model = train_random_forest_model(X_train, y_train, target_name)
        models[target] = model
        
        # Get feature importance
        feature_importance_results[target_name] = get_feature_importance(
            model, all_features, top_n=20
        )
        
        print(f"\nTop 10 features for {target_name}:")
        print(feature_importance_results[target_name].head(10).to_string(index=False))
        
        # Evaluate on training data
        train_results = evaluate_model_performance(
            model, X_train, y_train, 'TRAINING', target_name
        )
        all_results.append(train_results)
        
        # Evaluate on each test month
        print(f"\nEvaluating {target_name} model on test months...")
        
        for month, test_data in test_splits.items():
            # Encode test data using training encoders
            test_encoded = test_data.copy()
            for col in categorical_features:
                if col in test_data.columns and col in encoders:
                    # Handle unseen categories
                    test_values = test_data[col].astype(str)
                    encoded_values = []
                    for val in test_values:
                        if val in encoders[col].classes_:
                            encoded_values.append(encoders[col].transform([val])[0])
                        else:
                            # Assign to most frequent class in training
                            encoded_values.append(0)  # or use mode from training
                    test_encoded[col] = encoded_values
            
            X_test = test_encoded[all_features].fillna(0)
            y_test = test_encoded[target]
            
            if len(y_test) > 0:  # Only evaluate if we have test data
                test_results = evaluate_model_performance(
                    model, X_test, y_test, month, target_name
                )
                all_results.append(test_results)
                
                print(f"  {month}: AUC-ROC={test_results['auc_roc']:.4f}, "
                      f"AUC-PR={test_results['auc_pr']:.4f}, "
                      f"F1={test_results['f1_1']:.4f}")
    
    # Create comprehensive results DataFrame
    results_df = pd.DataFrame(all_results)
    
    # Add feature importance summary
    feature_summary = []
    for target_name, importance_df in feature_importance_results.items():
        for idx, row in importance_df.iterrows():
            feature_summary.append({
                'target': target_name,
                'feature': row['feature'],
                'importance': row['importance'],
                'rank': idx + 1
            })
    
    feature_summary_df = pd.DataFrame(feature_summary)
    
    # Save results
    print(f"\n{'='*60}")
    print("SAVING RESULTS")
    print(f"{'='*60}")
    
    # Save main results
    results_df.to_csv(output_path, index=False)
    print(f"Main results saved to: {output_path}")
    
    # Save feature importance
    feature_output_path = output_path.replace('.csv', '_FEATURE_IMPORTANCE.csv')
    feature_summary_df.to_csv(feature_output_path, index=False)
    print(f"Feature importance saved to: {feature_output_path}")
    
    # Print summary
    print(f"\n{'='*60}")
    print("ANALYSIS SUMMARY")
    print(f"{'='*60}")
    
    print(f"Total records analyzed: {len(df)}")
    print(f"Training records: {len(train_data)}")
    print(f"Test months: {len(test_splits)}")
    
    for target in ['BP', 'SP']:
        target_results = results_df[results_df['target'] == target]
        train_auc = target_results[target_results['month'] == 'TRAINING']['auc_roc'].iloc[0]
        test_results = target_results[target_results['month'] != 'TRAINING']
        
        if len(test_results) > 0:
            avg_test_auc = test_results['auc_roc'].mean()
            auc_degradation = train_auc - avg_test_auc
            
            print(f"\n{target} Model Performance:")
            print(f"  Training AUC-ROC: {train_auc:.4f}")
            print(f"  Average Test AUC-ROC: {avg_test_auc:.4f}")
            print(f"  Performance Degradation: {auc_degradation:.4f}")
            print(f"  Test AUC Range: {test_results['auc_roc'].min():.4f} - {test_results['auc_roc'].max():.4f}")
    
    return results_df, feature_summary_df, models

# Run the analysis
if __name__ == "__main__":
    print("Starting Random Forest Defect Classification Analysis")
    print("="*80)
    
    try:
        results_df, feature_importance_df, trained_models = run_comprehensive_analysis()
        print("\nAnalysis completed successfully!")
        
    except Exception as e:
        print(f"Error during analysis: {e}")
        import traceback
        traceback.print_exc()