"""Synthetic P2P pricing dataset — generated from the feature parameters we control.

The 'true price' has nonlinear terms, a demand×age interaction, and — importantly —
**heteroscedastic** multiplicative noise (older / poorer items are genuinely less
predictable). That noise structure is what gives the quantile model a real interval
to learn: bands widen for uncertain items instead of being a fixed percentage.

Features (the model's inputs, identical to schemas.FeatureVector):
  condition_score, original_price, age_months,
  category_demand, category_depreciation, brand_multiplier, completeness
Target: true_price (INR).
"""
from __future__ import annotations

import numpy as np

from p2p.config import CONFIG

FEATURES = [
    "condition_score", "original_price", "age_months",
    "category_demand", "category_depreciation", "brand_multiplier", "completeness",
]


def generate(n: int = None, seed: int = CONFIG.seed) -> list:
    """Return a list of row dicts (FEATURES + true_price). Deterministic given seed."""
    n = int(n if n is not None else CONFIG.synth_n)
    rng = np.random.default_rng(seed)

    original_price = rng.uniform(500, 15000, n)
    condition_score = rng.uniform(20, 100, n)
    age_months = rng.uniform(0, 72, n)
    category_demand = rng.uniform(0.3, 1.0, n)
    category_depreciation = rng.uniform(0.05, 0.25, n)
    brand_multiplier = rng.choice([0.85, 1.0, 1.2], n)
    completeness = rng.uniform(0.0, 1.0, n)

    cond = condition_score / 100.0
    age = np.minimum(age_months, 60) / 60.0

    cond_factor = 0.15 + 0.85 * cond ** 1.25                 # poor condition hurts more
    age_factor = (1.0 - category_depreciation * age) * np.exp(-0.15 * age)
    demand_factor = 0.6 + 0.5 * category_demand
    comp_factor = 0.80 + 0.20 * completeness
    interaction = 1.0 + 0.15 * (category_demand - 0.65) * (1.0 - age)  # demand cushions age

    true = (original_price * cond_factor * age_factor * demand_factor
            * brand_multiplier * comp_factor * interaction)

    # Heteroscedastic, multiplicative (lognormal) noise: worse condition + older = noisier.
    sigma = 0.04 + 0.10 * (1.0 - cond) + 0.06 * age
    true = true * np.exp(rng.normal(0.0, sigma))
    true = np.maximum(true, 1.0)

    cols = [condition_score, original_price, age_months, category_demand,
            category_depreciation, brand_multiplier, completeness]
    return [
        {**{f: float(v[i]) for f, v in zip(FEATURES, cols)}, "true_price": float(true[i])}
        for i in range(n)
    ]


def generate_xy(n: int = None, seed: int = CONFIG.seed):
    """Vectorized (X [n,7] float32, y [n] float32) for model training/eval."""
    rows = generate(n=n, seed=seed)
    X = np.array([[r[f] for f in FEATURES] for r in rows], dtype="float32")
    y = np.array([r["true_price"] for r in rows], dtype="float32")
    return X, y
