
import json
from pathlib import Path
from statistics import mean

from rag import build_rag


BASE_DIR = Path(__file__).resolve().parent
EVAL_FILE = BASE_DIR / "data" / "eval.json"


def normalize_source(source: str) -> str:
    """Compare source filenames consistently, regardless of path prefix."""
    return Path(source).name.lower()


def evaluate_mode(rag, dataset, k=5, use_reranker=False):
    """Evaluate retrieval using source-level relevance."""
    hit_scores = []
    recall_scores = []
    precision_scores = []
    reciprocal_ranks = []

    for item in dataset:
        relevant = {
            normalize_source(source)
            for source in item["relevant_sources"]
        }

        if not relevant:
            continue

        results = rag.retrieve(
            item["question"],
            top_k=k,
            use_reranker=use_reranker,
        )

        # Deduplicate source files while preserving their first rank.
        ranked_sources = []
        seen = set()

        for result in results:
            source = normalize_source(result["source"])

            if source not in seen:
                ranked_sources.append(source)
                seen.add(source)

        relevant_ranks = [
            rank
            for rank, source in enumerate(ranked_sources, start=1)
            if source in relevant
        ]

        hits = len(relevant_ranks)

        hit_scores.append(float(hits > 0))
        recall_scores.append(hits / len(relevant))
        precision_scores.append(hits / k)
        reciprocal_ranks.append(
            1.0 / relevant_ranks[0] if relevant_ranks else 0.0
        )

    if not hit_scores:
        print("No valid evaluation questions.")
        return

    label = "RRF + reranker" if use_reranker else "RRF only"

    print(f"\n--- {label} (K={k}) ---")
    print(f"Queries evaluated: {len(hit_scores)}")
    print(f"Source Hit@{k}:    {mean(hit_scores):.3f}")
    print(f"Source Recall@{k}: {mean(recall_scores):.3f}")
    print(f"Source MRR@{k}:    {mean(reciprocal_ranks):.3f}")
    print(f"Source Precision@{k}: {mean(precision_scores):.3f}")


def evaluate(rag, dataset, k=5):
    """Compare hybrid retrieval before and after reranking."""
    evaluate_mode(rag, dataset, k=k, use_reranker=False)
    evaluate_mode(rag, dataset, k=k, use_reranker=True)


if __name__ == "__main__":
    if not EVAL_FILE.exists():
        raise FileNotFoundError(f"Evaluation dataset not found: {EVAL_FILE}")

    with EVAL_FILE.open(encoding="utf-8") as file:
        dataset = json.load(file)

    if not isinstance(dataset, list) or not dataset:
        raise ValueError("eval.json must contain a non-empty JSON list.")

    for index, item in enumerate(dataset, start=1):
        if not item.get("question") or not item.get("relevant_sources"):
            raise ValueError(
                f"Evaluation item {index} needs question and relevant_sources."
            )

    rag = build_rag()
    evaluate(rag, dataset, k=5)
