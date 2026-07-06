# File: models/train_phishing.py
# Trains phishing detector using numerical features (no TF-IDF).
# Model: XGBoost on 15 structured features.
# Input:  data/phishing_train.csv
# Output: models/phishing/model.pkl + metadata.json

import os
import sys
import json
import pandas as pd
import numpy as np
from datetime import datetime
from xgboost import XGBClassifier
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import classification_report, confusion_matrix, accuracy_score
import joblib

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from features.feature_extractor import FEATURE_COLUMNS


def train_phishing_model():
    print("=" * 60)
    print("Training Phishing Model — XGBoost (Feature-Based)")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_path = os.path.join(base_dir, 'data', 'phishing_train.csv')

    if not os.path.exists(data_path):
        print(f"ERROR: {data_path} not found. Run data/prepare_phishing.py first.")
        return

    # ── Load Data ──────────────────────────────────────────────
    df = pd.read_csv(data_path)
    print(f"\nLoaded {len(df)} samples")
    print(df['label'].value_counts())

    missing = [c for c in FEATURE_COLUMNS if c not in df.columns]
    if missing:
        print(f"ERROR: Missing feature columns: {missing}")
        return

    X = df[FEATURE_COLUMNS].values
    # Binary: 1 = phishing, 0 = legitimate
    y = (df['label'] == 'phishing').astype(int)

    print(f"\nPhishing: {y.sum()}  |  Legitimate: {(y==0).sum()}")

    # ── Train / Test Split ─────────────────────────────────────
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, stratify=y, random_state=42
    )
    print(f"Train: {len(X_train)}  |  Test: {len(X_test)}")

    # ── Class weight for imbalance ─────────────────────────────
    neg = int((y_train == 0).sum())
    pos = int((y_train == 1).sum())
    scale_pos_weight = neg / pos if pos > 0 else 1.0
    print(f"scale_pos_weight: {scale_pos_weight:.2f}")

    # ── Train Model ────────────────────────────────────────────
    print("\nTraining XGBoost...")
    model = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.05,
        scale_pos_weight=scale_pos_weight,
        eval_metric='logloss',
        random_state=42,
        n_jobs=-1,
        verbosity=0,
    )
    model.fit(X_train, y_train)

    # ── Cross Validation ───────────────────────────────────────
    print("Running 5-fold cross validation...")
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    cv_scores = cross_val_score(model, X_train, y_train,
                                cv=cv, scoring='accuracy', n_jobs=-1)
    print(f"CV Scores : {cv_scores.round(4)}")
    print(f"CV Mean   : {cv_scores.mean():.4f}  (+/- {cv_scores.std():.4f})")

    # ── Evaluate ───────────────────────────────────────────────
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)

    print(f"\nTest Accuracy: {accuracy:.4f}")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred,
                                target_names=['legitimate', 'phishing']))
    print("Confusion Matrix:")
    print(confusion_matrix(y_test, y_pred))

    # ── Feature Importance ─────────────────────────────────────
    print("\nTop Feature Importances:")
    importances = model.feature_importances_
    for name, imp in sorted(zip(FEATURE_COLUMNS, importances),
                            key=lambda x: x[1], reverse=True):
        print(f"  {name:<25} {imp:.4f}")

    # ── Save ───────────────────────────────────────────────────
    model_dir = os.path.join(base_dir, 'models', 'phishing')
    os.makedirs(model_dir, exist_ok=True)

    model_path = os.path.join(model_dir, 'model.pkl')
    joblib.dump(model, model_path)
    print(f"\nModel saved → {model_path}")

    metadata = {
        'model_name': 'phishing_detector',
        'version': '3.0.0',
        'model_type': 'XGBoost',
        'feature_based': True,
        'features': FEATURE_COLUMNS,
        'trained_date': datetime.now().isoformat(),
        'accuracy': float(accuracy),
        'cv_mean_accuracy': float(cv_scores.mean()),
        'cv_std': float(cv_scores.std()),
        'num_samples': len(df),
        'phishing_samples': int(y.sum()),
        'legitimate_samples': int((y == 0).sum()),
    }
    metadata_path = os.path.join(model_dir, 'metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    print(f"Metadata saved → {metadata_path}")

    print("\n" + "=" * 60)
    print("✅ Phishing model training complete!")
    print(f"   Test Accuracy : {accuracy:.4f}")
    print(f"   CV Accuracy   : {cv_scores.mean():.4f}")
    print("=" * 60)

    return model, metadata


if __name__ == '__main__':
    train_phishing_model()