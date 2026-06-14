"""Train the neural quantile-MLP on synthetic data. Run: python -m p2p.train

Retires the quantile-GBM from the live path; the GBM survives only as the eval
baseline in p2p.eval. Persists models/quantile_mlp.pt (weights + feature scaler).
"""
import os

from p2p.config import CONFIG
from p2p.synth import generate_xy, FEATURES
from p2p.model import PriceModel
from p2p import eval as ev


def train(seed: int = CONFIG.seed):
    X, y = generate_xy(seed=seed)
    Xtr, ytr, Xte, yte = ev.split(X, y, seed=seed)

    model = PriceModel().fit(
        Xtr, ytr, epochs=CONFIG.mlp_epochs, batch_size=CONFIG.mlp_batch_size,
        lr=CONFIG.mlp_lr, seed=seed,
    )

    q10, q50, q90 = model.predict(Xte)
    print("Neural quantile-MLP holdout:", ev.fmt(ev.evaluate_quantile(yte, q10, q50, q90)))

    os.makedirs(os.path.dirname(CONFIG.mlp_model_path), exist_ok=True)
    model.save(CONFIG.mlp_model_path)
    print(f"Saved → {CONFIG.mlp_model_path}")
    return model


main = train

if __name__ == "__main__":
    train()
