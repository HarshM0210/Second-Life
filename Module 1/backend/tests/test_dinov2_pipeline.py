"""
Full-pipeline test for the DINOv2 anomaly backend using real web-sourced
reference images (Module 1/backend/storage/dinov2/refs).

1. Direct detector: builds the per-category memory bank from the downloaded
   reference images and verifies a defaced image scores higher than a clean one
   (proves the real DINOv2 model path runs — the direct detector raises rather
   than falling back, so a returned result means the model ran).
2. End-to-end: drives the real /api/returns/{id}/submit endpoint with
   ANOMALY_BACKEND=dinov2 and base64 data: image URIs, and confirms a defaced
   item grades strictly lower than the clean one.
"""

import base64
import os

import aiosqlite
import numpy as np
import pytest
import pytest_asyncio

torch = pytest.importorskip("torch")
cv2 = pytest.importorskip("cv2")

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.config.database import init_db  # noqa: E402
from app.main import app  # noqa: E402

REFS = os.path.join(os.path.dirname(__file__), "..", "storage", "dinov2", "refs")
REFS = os.path.abspath(REFS)
ELEC_DIR = os.path.join(REFS, "electronics")

pytestmark = pytest.mark.skipif(
    not (os.path.isdir(ELEC_DIR) and len(os.listdir(ELEC_DIR)) >= 2),
    reason="DINOv2 reference images not present",
)

TEST_DB = "test_dinov2_pipeline.db"

ELECTRONICS_QA = {
    "return_reason": "Item is defective / not working",
    "functional_status": "Not functional — does not power on / completely broken",
    "physical_condition": "Minor cosmetic damage (light scratches, small dents)",
    "accessories": "Yes — all accessories present",
    "original_packaging": "Yes — original box with all inserts",
    "ownership_duration": "Used briefly (less than a week)",
    "factory_reset": "Yes — fully reset, personal data removed",
    "liquid_damage": "No — never exposed to liquid or impact",
}


def _first_image():
    for name in sorted(os.listdir(ELEC_DIR)):
        img = cv2.imread(os.path.join(ELEC_DIR, name))
        if img is not None and img.size > 0:
            return cv2.resize(img, (224, 224))
    raise RuntimeError("no decodable reference image")


def _deface(img):
    out = img.copy()
    out[150:210, 40:150] = (15, 15, 15)  # large dark "damage" block
    return out


def _data_uri(img):
    ok, buf = cv2.imencode(".jpg", img)
    return "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()


def test_dinov2_detector_separates_clean_from_defaced(monkeypatch):
    monkeypatch.setenv("DINOV2_REF_DIR", REFS)
    from app.services.dinov2_anomaly import DinoV2AnomalyDetector

    det = DinoV2AnomalyDetector()
    clean = _first_image()
    defaced = _deface(clean)

    r_clean = det.detect([clean], "Electronics")     # raises if model path fails
    r_defaced = det.detect([defaced], "Electronics")

    assert r_clean.model_available is True
    assert r_defaced.model_available is True
    assert r_defaced.anomaly_severity > r_clean.anomaly_severity, (
        f"defaced ({r_defaced.anomaly_severity}) should exceed clean ({r_clean.anomaly_severity})"
    )


@pytest_asyncio.fixture
async def db(monkeypatch):
    monkeypatch.setattr("app.config.database.DATABASE_PATH", TEST_DB)
    monkeypatch.setattr("app.services.health_score.DATABASE_PATH", TEST_DB)
    monkeypatch.setattr("app.services.disposition_router.DATABASE_PATH", TEST_DB)
    monkeypatch.setattr("app.services.return_window.DATABASE_PATH", TEST_DB)

    async def _get_test_db():
        conn = await aiosqlite.connect(TEST_DB)
        conn.row_factory = aiosqlite.Row
        return conn

    monkeypatch.setattr("app.routers.returns.get_db", _get_test_db)

    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)
    await init_db()
    async with aiosqlite.connect(TEST_DB) as conn:
        for rid in ("RET-DINO-CLEAN", "RET-DINO-DEF"):
            await conn.execute(
                """INSERT INTO returns (id, order_id, product_id, customer_id, category, delivery_date, initiated_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (rid, "ORD-D", "PROD-D", "CUST-D", "Electronics", "2026-05-01", "2026-05-15T10:00:00", "initiated"),
            )
        await conn.commit()
    yield
    if os.path.exists(TEST_DB):
        os.remove(TEST_DB)


@pytest.mark.asyncio
async def test_full_pipeline_dinov2_defaced_grades_lower(db, monkeypatch):
    monkeypatch.setenv("ANOMALY_BACKEND", "dinov2")
    monkeypatch.setenv("DINOV2_REF_DIR", REFS)

    clean = _first_image()
    defaced = _deface(clean)

    def payload(img):
        return {
            "qa_answers": ELECTRONICS_QA,
            "image_uris": [_data_uri(img)],
            "video_frame_uris": [],
            "catalog_metadata": {
                "category": "Electronics", "original_price": 24999.0,
                "purchase_date": "2026-05-01", "warranty_remaining_months": 5,
            },
        }

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r1 = await client.post("/api/returns/RET-DINO-CLEAN/submit", json=payload(clean))
        r2 = await client.post("/api/returns/RET-DINO-DEF/submit", json=payload(defaced))

    assert r1.status_code == 200 and r2.status_code == 200
    clean_card = r1.json()["health_card"]
    defaced_card = r2.json()["health_card"]

    assert 0 <= clean_card["health_score"] <= 100
    assert 0 <= defaced_card["health_score"] <= 100
    # The visible damage must pull the health score down.
    assert defaced_card["health_score"] < clean_card["health_score"], (
        f"clean={clean_card['health_score']} defaced={defaced_card['health_score']}"
    )
