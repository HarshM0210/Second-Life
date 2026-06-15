"""
Tests for the optional DINOv2 anomaly backend wiring.

These deliberately avoid requiring torch: they exercise the resilient-fallback
logic and the env-gated backend selector with stubs, so they run anywhere.
"""

import importlib

from app.models.results import AnomalyResult
from app.services.anomaly_detector import AnomalyDetector
from app.services.dinov2_anomaly import (
    DinoV2Unavailable,
    ResilientAnomalyDetector,
)


class _Boom:
    def detect(self, images, category):
        raise DinoV2Unavailable("no bank / no torch")


class _Good:
    def __init__(self):
        self.called = False

    def detect(self, images, category):
        self.called = True
        return AnomalyResult(
            anomaly_severity=0.42, heatmap_uri="s3://heatmaps/x.png", model_available=True
        )


def test_resilient_falls_back_on_primary_failure():
    good = _Good()
    det = ResilientAnomalyDetector(_Boom(), good)
    res = det.detect([], "Electronics")
    assert good.called is True
    assert res.anomaly_severity == 0.42


def test_resilient_uses_primary_when_it_succeeds():
    primary = _Good()
    fallback = _Good()
    det = ResilientAnomalyDetector(primary, fallback)
    res = det.detect([], "Electronics")
    assert primary.called is True
    assert fallback.called is False
    assert res.anomaly_severity == 0.42


def test_default_backend_is_opencv(monkeypatch):
    monkeypatch.delenv("ANOMALY_BACKEND", raising=False)
    po = importlib.import_module("app.services.pipeline_orchestrator")
    det = po._build_anomaly_detector()
    assert isinstance(det, AnomalyDetector)


def test_dinov2_backend_selects_resilient_wrapper(monkeypatch):
    monkeypatch.setenv("ANOMALY_BACKEND", "dinov2")
    po = importlib.import_module("app.services.pipeline_orchestrator")
    det = po._build_anomaly_detector()
    # Wrapper is selected even though torch isn't needed until .detect() runs.
    assert isinstance(det, ResilientAnomalyDetector)
