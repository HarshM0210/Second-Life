"""Central service registry for the Second Life Commerce pipeline.

One place that knows where every module lives. Ports are aligned to resolve the
README conflicts (Module 1 and Module 3 both claimed :8000):

    Module 1  Grading / Fraud / Quality      :8000
    Module 2  Recommend (+ Customer_Profile) :8001
    Module 4  Green Coin                     :8002   (Module 3 hardcodes this)
    Module 3  Return Prevention              :8003
    Module 5  P2P Exchange                   :8005

Every URL is overridable via environment variable so the same code runs in the
demo, in CI, and against remote deployments.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _url(env_key: str, default: str) -> str:
    return os.environ.get(env_key, default).rstrip("/")


@dataclass(frozen=True)
class Services:
    grading: str = _url("M1_GRADING_URL", "http://localhost:8000")
    recommend: str = _url("M2_RECOMMEND_URL", "http://localhost:8001")
    green_coin: str = _url("M4_GREEN_COIN_URL", "http://localhost:8002")
    prevention: str = _url("M3_PREVENTION_URL", "http://localhost:8003")
    p2p: str = _url("M5_P2P_URL", "http://localhost:8005")

    def as_dict(self) -> dict[str, str]:
        return {
            "module_1_grading": self.grading,
            "module_2_recommend": self.recommend,
            "module_3_prevention": self.prevention,
            "module_4_green_coin": self.green_coin,
            "module_5_p2p": self.p2p,
        }


SERVICES = Services()

# HTTP timeouts (seconds). Grading runs a model pipeline; give it room.
TIMEOUT_DEFAULT = 10.0
TIMEOUT_GRADING = 30.0
