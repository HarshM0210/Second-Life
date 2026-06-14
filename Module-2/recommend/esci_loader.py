"""Amazon ESCI subset loader for offline evaluation.

Downloads a small English subset (~2-3k queries) from tasksource/esci on first
call and caches to disk. Falls back to synthetic fixtures if download fails.

ESCI labels mapped to graded relevance:
    Exact=3, Substitute=2, Complement=1, Irrelevant=0
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TypedDict

logger = logging.getLogger(__name__)

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "esci"
CACHE_FILE = CACHE_DIR / "esci_subset.json"
FIXTURES = Path(__file__).resolve().parent.parent / "fixtures"

LABEL_TO_GRADE = {"Exact": 3, "Substitute": 2, "Complement": 1, "Irrelevant": 0}


class ESCIQuery(TypedDict):
    query_id: int
    query: str
    products: list[dict]  # [{product_id, product_text, relevance (0-3)}]


def _download_subset(max_queries: int = 500) -> list[ESCIQuery]:
    """Stream the ESCI test split, filter to US/small_version, group by query."""
    from datasets import load_dataset

    ds = load_dataset("tasksource/esci", split="test", streaming=True)

    queries: dict[int, ESCIQuery] = {}
    count = 0
    for row in ds:
        if row["product_locale"] != "us" or row["small_version"] != 1:
            continue
        qid = row["query_id"]
        if qid not in queries:
            if len(queries) >= max_queries:
                break
            queries[qid] = {"query_id": qid, "query": row["query"], "products": []}
        queries[qid]["products"].append({
            "product_id": row["product_id"],
            "product_text": (row["product_title"] or "")[:200],
            "relevance": LABEL_TO_GRADE.get(row["esci_label"], 0),
        })
        count += 1

    logger.info(f"Downloaded {len(queries)} queries, {count} judgments")
    return list(queries.values())


def _synthetic_fallback() -> list[ESCIQuery]:
    """Build eval data from existing synthetic fixtures."""
    catalog = json.loads((FIXTURES / "catalog.json").read_text())
    return [{
        "query_id": 0,
        "query": "running shoes",
        "products": [
            {"product_id": item["sku_id"], "product_text": item["text"],
             "relevance": 3 if "running" in item["text"] else 0}
            for item in catalog
        ],
    }]


def load_esci(max_queries: int = 500, force_download: bool = False) -> list[ESCIQuery]:
    """Load ESCI subset. Downloads once and caches; falls back to fixtures offline."""
    if not force_download and CACHE_FILE.exists():
        return json.loads(CACHE_FILE.read_text())

    try:
        data = _download_subset(max_queries)
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(json.dumps(data))
        return data
    except Exception as e:
        logger.warning(f"ESCI download failed ({e}), using synthetic fallback")
        return _synthetic_fallback()
