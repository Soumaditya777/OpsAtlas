
import json
import re
from pathlib import Path

from rag import build_rag

BASE_DIR = Path(__file__).resolve().parent
DATASET_PATH = BASE_DIR / "data" / "answer_eval.json"
OUTPUT_PATH = BASE_DIR / "data" / "answer_eval_results.json"

ABSTENTION_PHRASES = (
    "not documented",
    "does not provide",
    "does not specify",
    "not specified",
    "not available in the documentation",
    "couldn't find relevant evidence",
    "insufficient evidence",
)


def normalize_source(source):
    return Path(source).name.lower()


def evaluate_answers():
    with DATASET_PATH.open(encoding="utf-8") as file:
        dataset = json.load(file)

    rag = build_rag()
    results = []

    for index, item in enumerate(dataset, start=1):
        question = item["question"]
        answerable = item["answerable"]

        print(f"\n[{index}/{len(dataset)}] {question}")

        output = rag.answer(question, top_k=5)
        answer = output.get("answer", "")
        citations = output.get("citations", [])
        retrieval = output.get("retrieval", [])

        marker_ids = {
            int(n) for n in re.findall(r"\[(\d+)\]", answer)
        }
        citation_ids = {
            c["citation_id"] for c in citations
        }

        markers_resolve = (
            bool(marker_ids) and marker_ids.issubset(citation_ids)
        )

        retrieved_sources = {
            normalize_source(x["source"]) for x in retrieval
        }
        citation_sources = {
            normalize_source(x["source"]) for x in citations
        }

        sources_in_retrieval = citation_sources.issubset(
            retrieved_sources
        )

        expected_sources = {
            normalize_source(s)
            for s in item.get("expected_sources", [])
        }
        expected_found = retrieved_sources & expected_sources

        source_recall = (
            len(expected_found) / len(expected_sources)
            if expected_sources else None
        )

        abstention_language = any(
            phrase in answer.lower() for phrase in ABSTENTION_PHRASES
        )

        # For answerable questions, citations must resolve.
        citation_pass = (
            markers_resolve and sources_in_retrieval
            if answerable else None
        )

        # For unanswerable questions, look for an explicit abstention.
        # This is a heuristic and still needs manual review.
        abstention_pass = (
            abstention_language and not citations
            if not answerable else None
        )

        checks = {
            "has_citation_markers": bool(marker_ids),
            "citation_ids_resolve": markers_resolve,
            "citation_sources_in_retrieval": sources_in_retrieval,
            "citation_quality_pass": citation_pass,
            "abstention_quality_pass": abstention_pass,
            "expected_sources_retrieved": sorted(expected_found),
            "source_recall_at_5": source_recall,
            "manual_answer_review_required": True,
        }

        result = {
            "question": question,
            "answerable": answerable,
            "answer": answer,
            "citations": citations,
            "retrieval": retrieval,
            "checks": checks,
        }
        results.append(result)

        print("Answer:", answer[:500])
        print("Citation check:", citation_pass)
        print("Abstention check:", abstention_pass)
        print("Expected sources found:", sorted(expected_found))

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(results, file, indent=2, ensure_ascii=False)

    answerable_results = [r for r in results if r["answerable"]]
    unanswerable_results = [r for r in results if not r["answerable"]]

    citation_passes = sum(
        r["checks"]["citation_quality_pass"] is True
        for r in answerable_results
    )
    abstention_passes = sum(
        r["checks"]["abstention_quality_pass"] is True
        for r in unanswerable_results
    )

    print("\n========== ANSWER EVALUATION ==========")
    print(f"Questions evaluated: {len(results)}")
    print(
        f"Answerable citation checks: {citation_passes}/"
        f"{len(answerable_results)}"
    )
    print(
        f"Unanswerable abstention checks: {abstention_passes}/"
        f"{len(unanswerable_results)}"
    )
    print("Factual correctness and claim-level support still require manual review.")
    print(f"Results saved to: {OUTPUT_PATH}")


if __name__ == "__main__":
    evaluate_answers()
