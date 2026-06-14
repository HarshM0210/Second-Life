"""Reproducible Phase 2.1 eval runner — writes data/eval/*.json.

Fixes the methodology: pools 50 distractor negatives/query so NDCG@10 actually
measures ranking (raw ESCI had ~2.7 candidates/query — too thin). Picks the
better embedder by NDCG, then measures the two-stage Qwen3-Reranker on top of it.

    python -m scripts.run_eval
"""
from __future__ import annotations

import json
import time
from pathlib import Path

from sentence_transformers import SentenceTransformer

from recommend.esci_loader import load_esci
from recommend.eval_harness import evaluate

OUT = Path(__file__).resolve().parent.parent / "data" / "eval"
NUM_NEG = 50
DATASET = f"tasksource/esci test (US, small_version, 500q) + {NUM_NEG} pooled negatives/query"


def make_embed_fn(model_name: str, trust: bool = False):
    model = SentenceTransformer(model_name, trust_remote_code=trust)
    return lambda texts: model.encode(texts, normalize_embeddings=True, batch_size=64).tolist()


def main():
    data = load_esci()
    OUT.mkdir(parents=True, exist_ok=True)

    embedders = [
        ("baseline_bge_small", "BAAI/bge-small-en-v1.5", 384, False),
        ("gte_modernbert_base", "Alibaba-NLP/gte-modernbert-base", 768, True),
    ]

    scored = []
    for fname, model_name, dim, trust in embedders:
        t = time.time()
        r = evaluate(make_embed_fn(model_name, trust), data, k=10, num_negatives=NUM_NEG)
        r.update(model=model_name, dim=dim, num_negatives=NUM_NEG, dataset=DATASET)
        (OUT / f"{fname}.json").write_text(json.dumps(r, indent=2))
        print(f"{fname:24} ndcg@10={r['ndcg@10']:.4f} avg_cand={r['avg_candidates']:.1f} ({time.time()-t:.0f}s)")
        scored.append((r["ndcg@10"], model_name, dim, trust))

    # Two-stage on the better embedder.
    best_ndcg, best_model, best_dim, best_trust = max(scored)
    from recommend.cross_encoder import cross_encoder_rerank

    t = time.time()
    r = evaluate(
        make_embed_fn(best_model, best_trust), data, k=10, num_negatives=NUM_NEG,
        reranker_fn=cross_encoder_rerank, rerank_top_n=20, max_queries=120,
    )
    r.update(
        model=f"{best_model} + Qwen/Qwen3-Reranker-0.6B",
        pipeline="embed -> retrieve -> cross-encoder rerank top-20 -> business rerank",
        num_negatives=NUM_NEG, rerank_top_n=20,
        dataset=DATASET + " (120-query cap for CE cost)",
        retrieval_only_ndcg=best_ndcg,
    )
    (OUT / "two_stage_qwen3_reranker.json").write_text(json.dumps(r, indent=2))
    print(f"{'two_stage_qwen3':24} ndcg@10={r['ndcg@10']:.4f} (retrieval-only={best_ndcg:.4f}) ({time.time()-t:.0f}s)")


if __name__ == "__main__":
    main()
