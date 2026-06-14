"""Single frozen config — all tunable weights/tables live here."""
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


@dataclass(frozen=True)
class P2PConfig:
    fee_rate: float = 0.12
    currency: str = "INR"
    clip_model: str = "clip-ViT-B-32"
    model_path: str = "models/quantile_gbm.joblib"          # legacy synthetic GBM (fallback baseline)
    mlp_model_path: str = "models/quantile_mlp.pt"          # Phase B: neural quantile-MLP
    seed: int = 42
    quantiles: Tuple[float, ...] = (0.1, 0.5, 0.9)
    # Min half-width of the price interval as a fraction of the point estimate.
    # Guards against quantile collapse (high == point) so the band is always visible.
    min_interval_frac: float = 0.03

    # Neural quantile-MLP training (Phase B). Dropout + weight-decay are deliberately
    # strong: they stop the net from interpolating each point and collapsing the
    # quantile interval (that's how the conditional spread / 80%-coverage survives).
    mlp_epochs: int = 150
    mlp_batch_size: int = 512
    mlp_lr: float = 2e-3
    mlp_dropout: float = 0.1
    mlp_weight_decay: float = 1e-4
    mlp_hidden: int = 256
    mlp_k: int = 16                # periodic-embedding frequencies per feature
    synth_n: int = 30000           # synthetic training rows

    # category -> (base_price, depreciation_rate, demand_factor)
    category_tables: Dict[str, Tuple[float, float, float]] = field(default_factory=lambda: {
        "electronics": (5000.0, 0.15, 0.85),
        "baby": (3000.0, 0.10, 0.90),
        "fitness": (4000.0, 0.12, 0.70),
        "kitchen": (2500.0, 0.08, 0.65),
        "fashion": (2000.0, 0.20, 0.60),
    })

    brand_multipliers: Dict[str, float] = field(default_factory=lambda: {
        "premium": 1.2,
        "standard": 1.0,
        "value": 0.85,
    })

    # (label, score) for CLIP zero-shot condition classification
    condition_prompts: List[Tuple[str, float]] = field(default_factory=lambda: [
        ("a brand new unused product", 95.0),
        ("a product in excellent condition", 85.0),
        ("a product in good condition", 70.0),
        ("a product in fair condition", 50.0),
        ("a product in poor condition", 30.0),
    ])


CONFIG = P2PConfig()
