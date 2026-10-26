
import re
import time
from pathlib import Path

import numpy as np
import requests
from pypdf import PdfReader
from rank_bm25 import BM25Okapi
from sentence_transformers import CrossEncoder, SentenceTransformer


# ============================================================
# CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DOCS_DIR = BASE_DIR / "data" / "docs"

EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:3b"

CHUNK_SIZE = 180
CHUNK_OVERLAP = 35
DEFAULT_TOP_K = 5
RRF_K = 60
CANDIDATE_MULTIPLIER = 4


# ============================================================
# DOCUMENT LOADING
# ============================================================

def load_documents():
    """Load Markdown, text and PDF files from data/docs."""
    if not DOCS_DIR.exists():
        raise FileNotFoundError(
            f"Knowledge base directory not found: {DOCS_DIR}"
        )

    documents = []

    for path in sorted(DOCS_DIR.rglob("*")):
        if not path.is_file():
            continue

        suffix = path.suffix.lower()

        try:
            if suffix in {".md", ".txt"}:
                text = path.read_text(encoding="utf-8").strip()

                if text:
                    documents.append({
                        "source": path.name,
                        "page": None,
                        "text": text,
                    })

            elif suffix == ".pdf":
                reader = PdfReader(str(path))

                for page_number, page in enumerate(reader.pages, start=1):
                    text = (page.extract_text() or "").strip()

                    if text:
                        documents.append({
                            "source": path.name,
                            "page": page_number,
                            "text": text,
                        })

        except Exception as exc:
            print(f"Skipping {path.name}: {exc}")

    if not documents:
        raise ValueError(
            f"No readable Markdown, TXT or PDF documents found in {DOCS_DIR}"
        )

    return documents


# ============================================================
# CHUNKING
# ============================================================

def split_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping word-based chunks."""
    words = text.split()

    if not words:
        return []

    if overlap >= chunk_size:
        raise ValueError("Chunk overlap must be smaller than chunk size.")

    chunks = []
    start = 0

    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunk = " ".join(words[start:end]).strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(words):
            break

        start = end - overlap

    return chunks


def chunk_documents(documents):
    """Chunk documents while retaining source and page metadata."""
    chunks = []

    for document in documents:
        for chunk in split_text(document["text"]):
            chunks.append({
                "source": document["source"],
                "page": document.get("page"),
                "text": chunk,
            })

    if not chunks:
        raise ValueError("Document loading produced no text chunks.")

    return chunks


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def tokenize(text):
    """Simple lexical tokenization for BM25."""
    return re.findall(r"\b[a-zA-Z0-9_]+\b", text.lower())


def normalize_source(source):
    return Path(str(source)).name.lower()


# ============================================================
# TARGETED ABSTENTION SAFEGUARDS
# ============================================================

def missing_specific_fact(question, evidence):
    """
    Avoid guessing specific values that are not documented.
    These are targeted safeguards, not a general entailment checker.
    """
    question_lower = question.lower()
    evidence_text = " ".join(
        item.get("text", "") for item in evidence
    )

    exact_fact_patterns = [
        (
            ("phone number" in question_lower
             or "telephone number" in question_lower
             or "contact number" in question_lower),
            r"\b(?:\+?\d[\d\s().-]{7,}\d)\b",
            "The on-call engineer's phone number is not documented "
            "in the retrieved evidence.",
        ),
        (
            ("connection pool size" in question_lower
             or "pool size" in question_lower
             or "how many connections" in question_lower),
            r"\b\d+\s*(?:connections?|conn)\b",
            "The exact database connection-pool size is not documented "
            "in the retrieved evidence.",
        ),
    ]

    for applies, pattern, message in exact_fact_patterns:
        if applies and not re.search(pattern, evidence_text, re.I):
            return message

    return None


# ============================================================
# HYBRID RETRIEVAL: DENSE + BM25 + RRF + RERANKING
# ============================================================

class HybridRAG:
    def __init__(self, chunks):
        if not chunks:
            raise ValueError("HybridRAG requires at least one chunk.")

        self.chunks = chunks

        print(f"Loading embedding model: {EMBEDDING_MODEL}")
        self.embedder = SentenceTransformer(EMBEDDING_MODEL)

        print("Embedding knowledge base...")
        texts = [chunk["text"] for chunk in chunks]

        self.embeddings = self.embedder.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

        self.tokenized_chunks = [tokenize(text) for text in texts]
        self.bm25 = BM25Okapi(self.tokenized_chunks)

        print(f"Loading reranker: {RERANKER_MODEL}")
        self.reranker = CrossEncoder(RERANKER_MODEL)

        print(f"Indexed {len(self.chunks)} chunks.")

    def dense_search(self, question, limit):
        """Return chunk indices ranked by cosine similarity."""
        query_embedding = self.embedder.encode(
            [question],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )[0]

        scores = self.embeddings @ query_embedding
        ranked = np.argsort(scores)[::-1][:limit]

        return [
            {
                "index": int(index),
                "score": float(scores[index]),
            }
            for index in ranked
        ]

    def sparse_search(self, question, limit):
        """Return chunk indices ranked by BM25."""
        scores = self.bm25.get_scores(tokenize(question))
        ranked = np.argsort(scores)[::-1][:limit]

        return [
            {
                "index": int(index),
                "score": float(scores[index]),
            }
            for index in ranked
        ]

    def reciprocal_rank_fusion(self, dense_results, sparse_results):
        """Fuse ranked lists using reciprocal rank fusion."""
        fused_scores = {}

        for results in (dense_results, sparse_results):
            for rank, result in enumerate(results, start=1):
                index = result["index"]
                fused_scores[index] = (
                    fused_scores.get(index, 0.0)
                    + 1.0 / (RRF_K + rank)
                )

        return sorted(
            fused_scores.items(),
            key=lambda item: item[1],
            reverse=True,
        )

    def retrieve(self, question, top_k=DEFAULT_TOP_K, use_reranker=True):
        """Run dense + sparse retrieval, RRF fusion and optional reranking."""
        if not question.strip():
            return []

        top_k = max(1, min(int(top_k), len(self.chunks)))
        candidate_count = min(
            len(self.chunks),
            max(top_k, top_k * CANDIDATE_MULTIPLIER),
        )

        dense_results = self.dense_search(question, candidate_count)
        sparse_results = self.sparse_search(question, candidate_count)

        fused_results = self.reciprocal_rank_fusion(
            dense_results,
            sparse_results,
        )

        candidates = []

        for index, rrf_score in fused_results[:candidate_count]:
            item = dict(self.chunks[index])
            item["chunk_index"] = index
            item["rrf_score"] = float(rrf_score)
            candidates.append(item)

        if use_reranker and candidates:
            pairs = [
                (question, item["text"])
                for item in candidates
            ]

            rerank_scores = self.reranker.predict(pairs)

            for item, score in zip(candidates, rerank_scores):
                item["rerank_score"] = float(score)

            candidates.sort(
                key=lambda item: item["rerank_score"],
                reverse=True,
            )

        return candidates[:top_k]

    # ========================================================
    # ANSWER GENERATION
    # ========================================================

    def generate_answer(self, question, evidence):
        """Generate one answer from retrieved evidence. No retry."""
        evidence_text = "\n\n".join(
            (
                f"[{index}] Source: {item['source']}"
                + (
                    f", page {item['page']}"
                    if item.get("page") is not None
                    else ""
                )
                + f"\n{item['text']}"
            )
            for index, item in enumerate(evidence, start=1)
        )

        prompt = f"""
You are OpsAtlas, a technical operations assistant.

Answer the question directly using the evidence below.

QUESTION:
{question}

EVIDENCE:
{evidence_text}

STRICT RULES:
- Answer the specific question asked.
- Synthesize a useful answer from the evidence.
- Use only claims supported by the evidence.
- Every factual bullet must include a citation like [1] or [2].
- Place citations directly beside the claims they support.
- Cite the source that actually supports each claim.
- Only use citation IDs present in the EVIDENCE section.
- Never invent technical steps, configuration values, phone
  numbers, or company policies.
- If the evidence does not answer the question, clearly say so.
- Do not claim evidence is missing if it explicitly answers
  the question.
- For exact values or contact details absent from the evidence,
  explicitly state that they are not documented.
- Do not claim to have performed actions or verified live systems.
- Keep the answer concise, using 3–6 bullets when appropriate.

Return only the answer with citations.
""".strip()

        response = requests.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "num_predict": 450,
                },
            },
            timeout=180,
        )

        response.raise_for_status()
        answer = response.json().get("response", "").strip()

        if not answer:
            raise ValueError("Ollama returned an empty answer.")

        print("DEBUG: Raw Ollama answer:", repr(answer))
        return answer

    # ========================================================
    # CITATION RESOLUTION
    # ========================================================

    @staticmethod
    def resolve_citations(answer, evidence):
        """Resolve citation markers to their corresponding evidence chunks."""
        marker_ids = {
            int(value)
            for value in re.findall(r"\[(\d+)\]", answer)
        }

        citations = []

        for citation_id in sorted(marker_ids):
            if not 1 <= citation_id <= len(evidence):
                continue

            item = evidence[citation_id - 1]

            citations.append({
                "citation_id": citation_id,
                "source": item["source"],
                "page": item.get("page"),
                "quote": item["text"],
            })

        return citations

    @staticmethod
    def evidence_fallback(evidence):
        """Show retrieved evidence instead of an uncited generated answer."""
        if not evidence:
            return (
                "I couldn't find relevant evidence in the available "
                "documentation."
            )

        lines = [
            "I couldn't generate a sufficiently supported answer. "
            "Review the retrieved evidence below:"
        ]

        for index, item in enumerate(evidence, start=1):
            page = (
                f", page {item['page']}"
                if item.get("page") is not None
                else ""
            )

            lines.append(
                f"\n[{index}] **Source: {item['source']}{page}**\n"
                f"{item['text']}"
            )

        return "\n".join(lines)

    # ========================================================
    # COMPLETE RAG PIPELINE
    # ========================================================

    def answer(self, question, top_k=DEFAULT_TOP_K):
        question = question.strip()

        if not question:
            raise ValueError("Question cannot be empty.")

        start_time = time.perf_counter()

        evidence = self.retrieve(
            question,
            top_k=top_k,
            use_reranker=True,
        )

        if not evidence:
            return {
                "question": question,
                "answer": (
                    "I couldn't find relevant evidence in the "
                    "available documentation."
                ),
                "citations": [],
                "retrieval": [],
                "abstained": True,
                "latency_seconds": time.perf_counter() - start_time,
            }

        abstention = missing_specific_fact(question, evidence)

        if abstention:
            return {
                "question": question,
                "answer": abstention,
                "citations": [],
                "retrieval": evidence,
                "abstained": True,
                "latency_seconds": time.perf_counter() - start_time,
            }

        try:
            answer = self.generate_answer(question, evidence)

            valid_ids = set(range(1, len(evidence) + 1))

            def validate_marker(match):
                citation_id = int(match.group(1))
                return (
                    match.group(0)
                    if citation_id in valid_ids
                    else ""
                )

            answer = re.sub(
                r"\[(\d+)\]",
                validate_marker,
                answer,
            ).strip()

            citations = self.resolve_citations(answer, evidence)

            if not citations:
                answer = self.evidence_fallback(evidence)
                citations = self.resolve_citations(answer, evidence)

            return {
                "question": question,
                "answer": answer,
                "citations": citations,
                "retrieval": evidence,
                "abstained": False,
                "latency_seconds": time.perf_counter() - start_time,
            }

        except (
            requests.RequestException,
            ValueError,
            KeyError,
            TypeError,
        ) as exc:
            print(f"Answer generation failed: {exc}")

            return {
                "question": question,
                "answer": self.evidence_fallback(evidence),
                "citations": self.resolve_citations(
                    self.evidence_fallback(evidence),
                    evidence,
                ),
                "retrieval": evidence,
                "abstained": True,
                "latency_seconds": time.perf_counter() - start_time,
            }


# ============================================================
# FACTORY
# ============================================================

def build_rag():
    documents = load_documents()
    chunks = chunk_documents(documents)
    return HybridRAG(chunks)


# ============================================================
# OPTIONAL TERMINAL CHAT
# ============================================================

if __name__ == "__main__":
    rag = build_rag()

    print("\nOpsAtlas ready. Type 'exit' to quit.\n")

    while True:
        question = input("You: ").strip()

        if question.lower() in {"exit", "quit"}:
            break

        if not question:
            continue

        result = rag.answer(question)

        print("\nOpsAtlas:\n")
        print(result["answer"])
        print(f"\nLatency: {result['latency_seconds']:.2f}s\n")
