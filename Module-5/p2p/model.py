"""Neural quantile-MLP — the Phase B pricing model (post-2023, ensemble-free).

A single network: periodic/PLR numeric-feature embeddings (Gorishniy et al. line) →
MLP trunk → three pinball-loss heads (q10/q50/q90). No boosting, no bagging, no
ensembling. Trained in log-price space; quantiles are sorted at inference so the
interval can never cross (q10 ≤ q50 ≤ q90). Torch + CUDA if available.
"""
from __future__ import annotations

import math

import numpy as np

from p2p.config import CONFIG

QUANTILES = (0.1, 0.5, 0.9)


def _torch():
    import torch
    return torch


class _PeriodicEmbedding:
    pass  # placeholder so static importers don't choke before torch is available


def _build_modules():
    """Build nn.Module classes lazily (only when torch is importable)."""
    import torch
    import torch.nn as nn

    class PeriodicEmbedding(nn.Module):
        """Each scaled numeric feature → [sin(2π f·x), cos(2π f·x)] over learned f."""
        def __init__(self, n_features: int, k: int = 16, sigma: float = 0.5):
            super().__init__()
            self.coeffs = nn.Parameter(torch.randn(n_features, k) * sigma)

        def forward(self, x):                      # x: (B, F)
            v = 2 * math.pi * x.unsqueeze(-1) * self.coeffs   # (B, F, k)
            return torch.cat([torch.sin(v), torch.cos(v)], dim=-1).flatten(1)

    class QuantileMLP(nn.Module):
        def __init__(self, n_features: int, k: int = 16, hidden: int = 256,
                     n_q: int = 3, dropout: float = 0.2):
            super().__init__()
            self.embed = PeriodicEmbedding(n_features, k)
            d = n_features * 2 * k + n_features    # embeddings ⊕ raw scaled features
            self.trunk = nn.Sequential(
                nn.Linear(d, hidden), nn.ReLU(), nn.Dropout(dropout),
                nn.Linear(hidden, hidden), nn.ReLU(), nn.Dropout(dropout),
            )
            self.head = nn.Linear(hidden, n_q)

        def forward(self, x):
            return self.head(self.trunk(torch.cat([self.embed(x), x], dim=1)))

    return QuantileMLP


def _pinball(pred, target, quantiles):
    import torch
    t = target.unsqueeze(1)
    e = t - pred
    q = torch.tensor(quantiles, device=pred.device).unsqueeze(0)
    return torch.maximum(q * e, (q - 1.0) * e).mean()


class PriceModel:
    """Wrapper: standardizes features, trains/predicts quantiles in price space."""

    def __init__(self, x_mean=None, x_std=None, state_dict=None, n_features=7,
                 k=None, hidden=None, dropout=None, cal_scale=1.0):
        self.x_mean = x_mean
        self.x_std = x_std
        self.n_features = n_features
        self.k = k if k is not None else CONFIG.mlp_k
        self.hidden = hidden if hidden is not None else CONFIG.mlp_hidden
        self.dropout = dropout if dropout is not None else CONFIG.mlp_dropout
        # Conformal interval scale (CQR): multiplies the raw q10/q90 offsets so the
        # central interval hits the target coverage on held-out data. 1.0 = uncalibrated.
        self.cal_scale = cal_scale
        self._state_dict = state_dict
        self._model = None  # lazily materialized torch module

    def _new_module(self):
        Mod = _build_modules()
        return Mod(self.n_features, k=self.k, hidden=self.hidden, dropout=self.dropout)

    # --- training -----------------------------------------------------------
    def fit(self, X, y, epochs=None, batch_size=None, lr=None, seed=42,
            weight_decay=None, device=None):
        import torch
        torch.manual_seed(seed)
        np.random.seed(seed)
        dev = device or ("cuda" if torch.cuda.is_available() else "cpu")
        epochs = epochs if epochs is not None else CONFIG.mlp_epochs
        batch_size = batch_size if batch_size is not None else CONFIG.mlp_batch_size
        lr = lr if lr is not None else CONFIG.mlp_lr
        weight_decay = weight_decay if weight_decay is not None else CONFIG.mlp_weight_decay

        X = np.asarray(X, dtype="float32")
        y = np.asarray(y, dtype="float32")
        # Carve a calibration split for conformal interval scaling (15%).
        rng = np.random.default_rng(seed)
        perm = rng.permutation(len(X))
        n_cal = max(200, int(0.15 * len(X)))
        cal_idx, fit_idx = perm[:n_cal], perm[n_cal:]
        Xf, yf = X[fit_idx], y[fit_idx]
        Xc, yc = X[cal_idx], y[cal_idx]

        self.x_mean = Xf.mean(axis=0)
        self.x_std = Xf.std(axis=0) + 1e-6
        Xs = (Xf - self.x_mean) / self.x_std
        yl = np.log1p(yf)

        self._model = self._new_module().to(dev)
        opt = torch.optim.Adam(self._model.parameters(), lr=lr, weight_decay=weight_decay)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=epochs)

        Xt = torch.tensor(Xs, device=dev)
        yt = torch.tensor(yl, device=dev)
        n = len(Xt)
        self._model.train()
        for _ in range(epochs):
            order = torch.randperm(n, device=dev)
            for i in range(0, n, batch_size):
                idx = order[i:i + batch_size]
                opt.zero_grad()
                loss = _pinball(self._model(Xt[idx]), yt[idx], QUANTILES)
                loss.backward()
                opt.step()
            sched.step()
        self._model.eval()
        self._state_dict = {k: v.cpu() for k, v in self._model.state_dict().items()}

        # Conformal calibration (CQR): pick the interval scale that yields ~80%
        # coverage on the held-out calibration split.
        ql = self._log_quantiles(Xc)                  # (n_cal, 3) sorted log-space
        yc_log = np.log1p(yc)
        lo_off = np.maximum(ql[:, 1] - ql[:, 0], 1e-6)
        hi_off = np.maximum(ql[:, 2] - ql[:, 1], 1e-6)
        score = np.maximum((ql[:, 1] - yc_log) / lo_off, (yc_log - ql[:, 1]) / hi_off)
        target = QUANTILES[2] - QUANTILES[0]          # 0.8 central coverage
        self.cal_scale = float(np.quantile(score, target))
        return self

    # --- inference ----------------------------------------------------------
    def _ensure_model(self):
        if self._model is None:
            self._model = self._new_module()
            self._model.load_state_dict(self._state_dict)
            self._model.eval()

    def _log_quantiles(self, X):
        """Raw sorted log-space quantiles (n,3); q[:,0]≤q[:,1]≤q[:,2]. No conformal scaling."""
        import torch
        self._ensure_model()
        dev = next(self._model.parameters()).device     # match model's device (CPU/GPU)
        X = np.asarray(X, dtype="float32").reshape(-1, self.n_features)
        Xs = (X - self.x_mean) / self.x_std
        with torch.no_grad():
            out = self._model(torch.tensor(Xs, dtype=torch.float32, device=dev))
            out, _ = torch.sort(out, dim=1)          # enforce q10 ≤ q50 ≤ q90
        return out.cpu().numpy()

    def predict(self, X):
        """Return conformally-calibrated (q10, q50, q90) price arrays."""
        ql = self._log_quantiles(X)
        q50 = ql[:, 1]
        lo = q50 - self.cal_scale * (q50 - ql[:, 0])   # widen/narrow to target coverage
        hi = q50 + self.cal_scale * (ql[:, 2] - q50)
        return (np.maximum(np.expm1(lo), 0.0),
                np.maximum(np.expm1(q50), 0.0),
                np.maximum(np.expm1(hi), 0.0))

    # --- persistence --------------------------------------------------------
    def save(self, path):
        import torch
        torch.save({
            "state_dict": self._state_dict,
            "x_mean": self.x_mean, "x_std": self.x_std,
            "n_features": self.n_features, "k": self.k,
            "hidden": self.hidden, "dropout": self.dropout,
            "cal_scale": self.cal_scale,
        }, path)

    @classmethod
    def load(cls, path) -> "PriceModel":
        import torch
        blob = torch.load(path, map_location="cpu", weights_only=False)
        return cls(x_mean=blob["x_mean"], x_std=blob["x_std"],
                   state_dict=blob["state_dict"], n_features=blob["n_features"],
                   k=blob["k"], hidden=blob.get("hidden"), dropout=blob.get("dropout"),
                   cal_scale=blob.get("cal_scale", 1.0))
