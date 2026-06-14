"""Market-aware policy layer — makes Renewed boost respond to live market signals.

The key demo moment: toggling inventory/demand/cost visibly flips the ranking.
Rule-based now; LinUCB bandit is future work.

Stacked score breakdown (explainable):
    final_score = similarity + renewed_boost + policy_adjustment
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MarketState:
    """Market signals that modulate the Renewed boost. All normalized [0,1]."""
    inventory_level: float = 0.5    # 0=empty, 1=glut (boost harder to clear)
    demand_intensity: float = 0.5   # 0=no demand, 1=high demand (less boost needed)
    logistics_cost: float = 0.5     # 0=cheap, 1=expensive (reduce boost for costly items)

    def to_dict(self) -> dict[str, float]:
        return {
            "inventory_level": self.inventory_level,
            "demand_intensity": self.demand_intensity,
            "logistics_cost": self.logistics_cost,
        }


@dataclass(frozen=True)
class PolicyConfig:
    """Weights for market signals on the Renewed boost. All in config, not scattered."""
    inventory_weight: float = 0.10   # extra boost when inventory is high (glut)
    demand_dampener: float = 0.06    # reduce boost when demand is already high
    logistics_penalty: float = 0.04  # reduce boost for high-logistics-cost items
    enabled: bool = True


POLICY = PolicyConfig()


def policy_adjustment(market: MarketState, is_renewed: bool, config: PolicyConfig = POLICY) -> tuple[float, list[str]]:
    """Compute the policy adjustment for an item given market state.

    Returns:
        (adjustment, reasons) where adjustment is additive to the final score.
    """
    if not config.enabled or not is_renewed:
        return 0.0, []

    adj = 0.0
    reasons: list[str] = []

    # High inventory → boost harder to clear stock
    if market.inventory_level > 0.6:
        inv_boost = config.inventory_weight * (market.inventory_level - 0.5)
        adj += inv_boost
        reasons.append(f"inventory surplus (+{inv_boost:.3f})")

    # High demand → less boost needed (items sell themselves)
    if market.demand_intensity > 0.7:
        demand_damp = -config.demand_dampener * (market.demand_intensity - 0.5)
        adj += demand_damp
        reasons.append(f"high demand ({demand_damp:.3f})")

    # High logistics cost → penalize
    if market.logistics_cost > 0.6:
        cost_pen = -config.logistics_penalty * (market.logistics_cost - 0.5)
        adj += cost_pen
        reasons.append(f"logistics cost ({cost_pen:.3f})")

    return adj, reasons
