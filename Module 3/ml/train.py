"""
LightGBM return-risk classifier — training script.

Usage:
    python ml/train.py

Outputs:
    ml/models/lgbm_return_risk.pkl     — serialised model (joblib)
    ml/models/training_report.json     — AUC-ROC, log-loss, feature importance
"""

import json
import os
import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, log_loss

# ── Paths ─────────────────────────────────────────────────────────────────────
DATA_PATH  = "ml/data/return_prevention_dataset.csv"
MODEL_DIR  = "ml/models"
MODEL_PATH = f"{MODEL_DIR}/lgbm_return_risk.pkl"
REPORT_PATH = f"{MODEL_DIR}/training_report.json"

FEATURE_COLS = [
    "category_return_rate",
    "user_category_return_rate",
    "in_user_high_return_price_band",
    "has_size_ambiguity",
    "page_dwell_seconds",
    "is_buy_now",
    "product_review_rating",
    "seller_return_rate",
    "is_sale_active",
]
LABEL_COL = "returned"

# ── Hyperparameters ───────────────────────────────────────────────────────────
# Conservative settings that train fast on CPU and generalise well on small data.
LGBM_PARAMS = dict(
    objective="binary",
    metric="binary_logloss",
    n_estimators=300,
    learning_rate=0.05,
    num_leaves=31,
    max_depth=6,
    min_child_samples=20,
    subsample=0.8,
    colsample_bytree=0.8,
    reg_alpha=0.1,
    reg_lambda=0.1,
    random_state=42,
    n_jobs=-1,
    verbose=-1,
)


def train():
    os.makedirs(MODEL_DIR, exist_ok=True)

    # ── Load data ─────────────────────────────────────────────────────────────
    print(f"Loading dataset from {DATA_PATH} ...")
    df = pd.read_csv(DATA_PATH)
    X = df[FEATURE_COLS]
    y = df[LABEL_COL]
    print(f"  Samples: {len(df):,}  |  Return rate: {y.mean():.2%}")

    # ── Train / validation split (80 / 20 stratified) ─────────────────────────
    X_train, X_val, y_train, y_val = train_test_split(
        X, y, test_size=0.20, random_state=42, stratify=y
    )
    print(f"  Train: {len(X_train):,}  |  Val: {len(X_val):,}")

    # ── Train ─────────────────────────────────────────────────────────────────
    print("\nTraining LightGBM ...")
    model = LGBMClassifier(**LGBM_PARAMS)
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        callbacks=[],   # quiet training
    )

    # ── Evaluate ──────────────────────────────────────────────────────────────
    val_proba = model.predict_proba(X_val)[:, 1]
    auc  = roc_auc_score(y_val, val_proba)
    loss = log_loss(y_val, val_proba)

    print(f"\nValidation results:")
    print(f"  AUC-ROC  : {auc:.4f}")
    print(f"  Log-loss : {loss:.4f}")

    # ── Feature importance ────────────────────────────────────────────────────
    importance = dict(zip(
        FEATURE_COLS,
        model.feature_importances_.tolist()
    ))
    # Sort descending for display
    sorted_importance = dict(
        sorted(importance.items(), key=lambda x: x[1], reverse=True)
    )

    print("\nFeature importance (gain):")
    for feat, score in sorted_importance.items():
        bar = "█" * int(score / max(sorted_importance.values()) * 30)
        print(f"  {feat:<40} {score:>6}  {bar}")

    # ── Save model ────────────────────────────────────────────────────────────
    joblib.dump(model, MODEL_PATH)
    print(f"\nModel saved → {MODEL_PATH}")

    # ── Save report ───────────────────────────────────────────────────────────
    report = {
        "auc_roc":           round(auc, 4),
        "log_loss":          round(loss, 4),
        "n_train":           len(X_train),
        "n_val":             len(X_val),
        "return_rate_train": round(float(y_train.mean()), 4),
        "return_rate_val":   round(float(y_val.mean()), 4),
        "feature_importance": sorted_importance,
        "hyperparameters":   LGBM_PARAMS,
    }
    with open(REPORT_PATH, "w") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved  → {REPORT_PATH}")


if __name__ == "__main__":
    train()
