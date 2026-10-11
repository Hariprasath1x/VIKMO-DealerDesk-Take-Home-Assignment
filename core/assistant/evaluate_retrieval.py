import os
import sys
from pathlib import Path

repo_root = str(Path(__file__).resolve().parent.parent.parent)
if repo_root not in sys.path:
    sys.path.insert(0, repo_root)

import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "dealerdesk.settings")
django.setup()

from core.assistant.vector_store import search_parts_vector

EVALUATION_DATASET = [
    {
        "query": "BRK-1044",
        "vehicle": None,
        "target_sku": "BRK-1044",
        "description": "Exact SKU lookup",
    },
    {
        "query": "brake pads for Pulsar 150",
        "vehicle": "Bajaj Pulsar 150",
        "target_sku": "BRK-1044",
        "description": "Natural language with explicit vehicle",
    },
    {
        "query": "oil filter for Bajaj Pulsar 150",
        "vehicle": "Bajaj Pulsar 150",
        "target_sku": "FIL-1009",
        "description": "Vehicle fitment + category keyword",
    },
    {
        "query": "brak pad pulsr 150",
        "vehicle": "Bajaj Pulsar 150",
        "target_sku": "BRK-1044",
        "description": "Misspelling and typo tolerance",
    },
    {
        "query": "spark plug for Pulsar 150",
        "vehicle": "Bajaj Pulsar 150",
        "target_sku": "ELE-1018",
        "description": "Electrical category spark plug query",
    },
    {
        "query": "crash guard KTM Duke 390",
        "vehicle": "KTM Duke 390",
        "target_sku": "BDY-1015",
        "description": "Body & Styling crash guard query",
    },
    {
        "query": "brake pads Royal Enfield Hunter 350",
        "vehicle": "Royal Enfield Hunter 350",
        "target_sku": "BRK-1002",
        "description": "Hunter 350 specific brake pads",
    },
    {
        "query": "Classic 350 oil filter",
        "vehicle": "Royal Enfield Classic 350",
        "target_sku": "FIL-1001",
        "description": "Classic 350 oil filter query",
    },
    {
        "query": "authentic homemade Neapolitan pizza recipe with dough fermentation",
        "vehicle": None,
        "target_sku": None,
        "description": "Negative out-of-domain query (must return 0 results)",
    },
    {
        "query": "learn python django advanced async programming tutorial",
        "vehicle": None,
        "target_sku": None,
        "description": "Negative non-automotive query (must return 0 results)",
    },
]


def run_evaluation():
    print("=" * 60)
    print("DEALERDESK SEMANTIC RETRIEVAL BENCHMARK")
    print("Model: sentence-transformers/all-MiniLM-L6-v2")
    print("Vector Store: ChromaDB (HNSW Cosine Distance)")
    print("=" * 60)

    top_1_hits = 0
    top_5_hits = 0
    rr_total = 0.0
    evaluated_positive = 0
    negative_passed = 0
    negative_total = 0

    for idx, test_case in enumerate(EVALUATION_DATASET, 1):
        q = test_case["query"]
        veh = test_case["vehicle"]
        target = test_case["target_sku"]
        desc = test_case["description"]

        results = search_parts_vector(query=q, vehicle=veh, top_k=5)
        retrieved_skus = [r["sku"] for r in results]

        if target is None:
            negative_total += 1
            if len(results) == 0:
                negative_passed += 1
                status_str = "PASS (Correctly rejected)"
            else:
                status_str = f"FAIL (Returned {len(results)} irrelevant items)"
            print(f"[{idx:02d}] NEGATIVE: '{q[:40]}...' -> {status_str}")
        else:
            evaluated_positive += 1
            rank = None
            if target in retrieved_skus:
                rank = retrieved_skus.index(target) + 1
                rr_total += 1.0 / rank
                top_5_hits += 1
                if rank == 1:
                    top_1_hits += 1
                status_str = f"HIT at Rank #{rank}"
            else:
                status_str = f"MISS (Retrieved: {retrieved_skus})"

            print(f"[{idx:02d}] POSITIVE ({desc}): '{q}' -> Target: {target} | {status_str}")

    recall_at_1 = top_1_hits / evaluated_positive if evaluated_positive else 0.0
    recall_at_5 = top_5_hits / evaluated_positive if evaluated_positive else 0.0
    mrr = rr_total / evaluated_positive if evaluated_positive else 0.0
    negative_rejection_rate = negative_passed / negative_total if negative_total else 0.0

    print("-" * 60)
    print(f"Positive Test Cases: {evaluated_positive}")
    print(f"Recall@1: {recall_at_1 * 100:.1f}%")
    print(f"Recall@5: {recall_at_5 * 100:.1f}%")
    print(f"Mean Reciprocal Rank (MRR): {mrr:.4f}")
    print(f"Negative Out-of-Domain Rejection Rate: {negative_rejection_rate * 100:.1f}% ({negative_passed}/{negative_total})")
    print("=" * 60)

    return {
        "recall_at_1": recall_at_1,
        "recall_at_5": recall_at_5,
        "mrr": mrr,
        "negative_rejection_rate": negative_rejection_rate,
    }


if __name__ == "__main__":
    run_evaluation()
