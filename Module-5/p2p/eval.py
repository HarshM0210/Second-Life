"""Offline eval — pure-numpy metrics + the synthetic-GBM baseline (Phase B, Q2).

Every Phase-B number is measured against the *old* quantile-GBM on the same held-out
synthetic split, so "the MLP helped (or matched)" is a claim with evidence.
"""
from __future__ import annotations

import numpy as np

from p2p.config import CONFIG


# --- metrics (numpy only) ---------------------------------------------------
def mae(y, p) -> float:
    return float(np.mean(np.abs(np.asarray(y) - np.asarray(p))))


def r2(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    ss_res = float(np.sum((y - p) ** 2))
    ss_tot = float(np.sum((y - y.mean()) ** 2)) or 1.0
    return 1.0 - ss_res / ss_tot


def rmsle(y, p) -> float:
    y = np.asarray(y, float)
    p = np.maximum(np.asarray(p, float), 0.0)
    return float(np.sqrt(np.mean((np.log1p(p) - np.log1p(y)) ** 2)))


def interval_coverage(y, lo, hi) -> float:
    y = np.asarray(y, float)
    return float(np.mean((y >= np.asarray(lo)) & (y <= np.asarray(hi))))


def evaluate_quantile(y, q10, q50, q90) -> dict:
    return {
        "mae": mae(y, q50),
        "r2": r2(y, q50),
        "rmsle": rmsle(y, q50),
        "coverage": interval_coverage(y, q10, q90),  # target ≈ 0.80
    }


def fmt(m: dict) -> str:
    return (f"MAE {m['mae']:.0f} | R² {m['r2']:.3f} | RMSLE {m['rmsle']:.3f} "
            f"| 80%-cov {m['coverage']:.2f}")


# --- split + baseline -------------------------------------------------------
def split(X, y, test_frac=0.2, seed=CONFIG.seed):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(X))
    cut = int(len(X) * (1 - test_frac))
    tr, te = idx[:cut], idx[cut:]
    return X[tr], y[tr], X[te], y[te]


def train_gbm_baseline(Xtr, ytr, seed=CONFIG.seed):
    """The retired quantile-GBM, kept ONLY as the eval baseline (not the live path)."""
    from sklearn.ensemble import GradientBoostingRegressor
    models = {}
    for a, label in zip((0.1, 0.5, 0.9), ("q10", "q50", "q90")):
        m = GradientBoostingRegressor(loss="quantile", alpha=a, n_estimators=200,
                                      max_depth=4, random_state=seed)
        m.fit(Xtr, ytr)
        models[label] = m
    return models


def evaluate_models(seed=CONFIG.seed) -> dict:
    """Train baseline-GBM and the neural MLP on one synthetic split; return both metrics."""
    from p2p.synth import generate_xy
    from p2p.model import PriceModel

    X, y = generate_xy(seed=seed)
    Xtr, ytr, Xte, yte = split(X, y, seed=seed)

    gbm = train_gbm_baseline(Xtr, ytr, seed)
    g10, g50, g90 = (gbm["q10"].predict(Xte), gbm["q50"].predict(Xte), gbm["q90"].predict(Xte))
    g10, g50, g90 = np.sort(np.vstack([g10, g50, g90]), axis=0)   # de-cross for fairness
    baseline = evaluate_quantile(yte, g10, g50, g90)

    mlp = PriceModel().fit(Xtr, ytr, epochs=CONFIG.mlp_epochs,
                           batch_size=CONFIG.mlp_batch_size, lr=CONFIG.mlp_lr, seed=seed)
    m10, m50, m90 = mlp.predict(Xte)
    mlp_metrics = evaluate_quantile(yte, m10, m50, m90)

    return {"baseline_gbm": baseline, "mlp": mlp_metrics}


if __name__ == "__main__":
    res = evaluate_models()
    print("baseline GBM :", fmt(res["baseline_gbm"]))
    print("neural MLP   :", fmt(res["mlp"]))
