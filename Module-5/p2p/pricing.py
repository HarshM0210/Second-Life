"""Quote engine — neural quantile-MLP with a labeled heuristic fallback. Never crashes.

Phase B: the live path is the neural quantile-MLP (p2p.model.PriceModel). The old
quantile-GBM is retired from here (it lives on only as the eval baseline in p2p.eval).
If torch / the trained weights are unavailable, fall back to the transparent heuristic
— and SAY SO (PriceQuote.model = "heuristic-fallback"), never a silent constant.
"""
from __future__ import annotations

import logging

from p2p.schemas import FeatureVector, PriceQuote
from p2p.config import CONFIG
from p2p.synth import FEATURES

logger = logging.getLogger(__name__)

_models: dict = {}


def ensure_model():
    """Load (or train-on-first-use) the neural quantile-MLP; cache it."""
    if "mlp" in _models:
        return _models["mlp"]
    import os
    from p2p.model import PriceModel
    if not os.path.exists(CONFIG.mlp_model_path):
        from p2p import train
        train.main()
    _models["mlp"] = PriceModel.load(CONFIG.mlp_model_path)
    return _models["mlp"]


def is_model_loaded() -> bool:
    return "mlp" in _models


def _fv_row(fv: FeatureVector) -> list:
    return [getattr(fv, f) for f in FEATURES]


def _build_quote(fv: FeatureVector, point: float, low: float, high: float,
                 model_name: str = "") -> PriceQuote:
    # Clamp the median to [0, original_price] before rounding (never quote above retail).
    op = fv.original_price
    point = max(0.0, point)
    if op > 0:
        point = min(point, op)

    # Single rounding source: every figure (structured fields AND reason text) derives
    # from `gross`, so they can never disagree (P12).
    gross = round(point)
    fee = round(gross * CONFIG.fee_rate)
    net = gross - fee

    # Interval guard: force a visible, ordered band even if the heads collapse (P13).
    band = max(1, round(gross * CONFIG.min_interval_frac))
    low_r = max(0, min(round(low), gross - band))
    high_r = max(round(high), gross + band)

    conf = max(0.3, min(0.99, 1 - (high_r - low_r) / max(gross, 1)))
    reasons = [
        f"condition {int(fv.condition_score)}/100",
        f"category demand {fv.category_demand:.0%}",
        f"age {fv.age_months} months",
        f"Gross ₹{gross} − fee ₹{fee} = you get ₹{net}",
    ]
    return PriceQuote(
        gross_price=gross, low=low_r, high=high_r,
        confidence=round(conf, 2), fee=fee, net_payout=net,
        currency=CONFIG.currency, feature_source=fv.source, reasons=reasons,
        model=model_name,
    )


def _heuristic_quote(fv: FeatureVector) -> PriceQuote:
    dep = max(0, 1 - fv.category_depreciation * fv.age_months / 60)
    point = fv.original_price * (fv.condition_score / 100) * fv.brand_multiplier * dep * fv.category_demand
    return _build_quote(fv, point, point * 0.8, point * 1.2, model_name="heuristic-fallback")


def quote(fv: FeatureVector, sku_id: str = "") -> PriceQuote:
    """Predict a price quote — neural MLP first, transparent heuristic fallback."""
    try:
        model = ensure_model()
        q10, q50, q90 = model.predict([_fv_row(fv)])
        q = _build_quote(fv, float(q50[0]), float(q10[0]), float(q90[0]),
                         model_name="neural-quantile-mlp")
    except Exception as e:
        logger.warning("MLP unavailable (%s); using heuristic fallback.", e)
        q = _heuristic_quote(fv)
    q.sku_id = sku_id
    return q
