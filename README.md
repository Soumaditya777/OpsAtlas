# OpsAtlas 🔎
### Local-First RAG for Technical Operations and Incident Response

OpsAtlas is a local-first Retrieval-Augmented Generation (RAG) system designed to answer technical operations questions using internal documentation, runbooks, and troubleshooting guides.

It combines **dense semantic search, sparse keyword retrieval, Reciprocal Rank Fusion (RRF), cross-encoder reranking, and source citations** to retrieve relevant evidence before generating answers with a locally running language model.

The goal is to make technical knowledge easier to search while keeping answers grounded in available documentation.

## ✨ Features

- **Hybrid Retrieval:** Combines dense vector search with BM25 keyword retrieval.
- **Reciprocal Rank Fusion (RRF):** Merges ranked results from multiple retrieval methods.
- **Cross-Encoder Reranking:** Reorders candidate passages based on query–passage relevance.
- **Citation-Aware Generation:** Generates answers with references to retrieved evidence and source passages.
- **Evidence-Based Abstention:** Includes safeguards for selected questions when required facts are not documented.
- **Local LLM Inference:** Uses Ollama to run the generation model locally.
- **Document Ingestion:** Supports Markdown, text, and PDF documents.
- **Interactive Interface:** Provides a Streamlit chat interface with source passages and retrieval diagnostics.
- **Retrieval Evaluation:** Compares RRF retrieval with and without reranking.
- **Answer Evaluation:** Tests citation resolution, source consistency, and selected unanswerable questions.

## 🏗️ Architecture

```text
          Technical Documentation
          (Markdown / TXT / PDF)
                    |
                    v
             Document Loading
                    |
                    v
             Text Chunking
                    |
          +---------+---------+
          |                   |
          v                   v
   Dense Embeddings       BM25 Index
   (BGE Small EN)        (Keyword Search)
          |                   |
          v                   v
    Dense Retrieval      Sparse Retrieval
          |                   |
          +---------+---------+
                    |
                    v
       Reciprocal Rank Fusion (RRF)
                    |
                    v
        Candidate Passage Selection
                    |
                    v
        Cross-Encoder Reranking
                    |
                    v
          Retrieved Evidence
                    |
                    v
         Local LLM via Ollama
                    |
                    v
      Answer with Source Citations
                    |
                    v
       Streamlit UI and Evaluation
```

## 🧰 Technology Stack

| Component | Technology |
|---|---|
| Language | Python |
| Embedding model | `BAAI/bge-small-en-v1.5` |
| Sparse retrieval | BM25 via `rank-bm25` |
| Rank fusion | Reciprocal Rank Fusion |
| Reranker | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Generation model | `qwen2.5:3b` via Ollama |
| Vector operations | NumPy |
| Document parsing | pypdf |
| User interface | Streamlit |
| Evaluation | Custom Python evaluation scripts |

## 📁 Project Structure

```text
opsatlas/
├── data/
│   ├── docs/
│   │   ├── runbook.md
│   │   ├── database_troubleshooting.md
│   │   ├── deployment_rollback.md
│   │   └── incident_response.md
│   ├── eval.json
│   ├── answer_eval.json
│   └── answer_eval_results.json
├── app.py
├── rag.py
├── evaluate.py
├── evaluate_answers.py
├── requirements.txt
├── .gitignore
└── README.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.11 recommended
- [Ollama](https://ollama.com/)
- Git
- Approximately 8 GB RAM can be restrictive for simultaneous model loading, so lightweight local models and a modest retrieval workload are recommended.

### 1. Clone the repository

```bash
git clone <YOUR_REPOSITORY_URL>
cd opsatlas
```

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Install and start the generation model

Install Ollama from its official website, then pull the model:

```bash
ollama pull qwen2.5:3b
```

Verify that the model is available:

```bash
ollama list
```

Ensure Ollama is running before starting OpsAtlas. If it is not running automatically, start the Ollama service using your platform's normal startup method or run:

```bash
ollama serve
```

Keep that terminal open if you start the service manually.

### 5. Launch the application

```bash
streamlit run app.py
```

Open the local URL displayed in the terminal by Streamlit.

On first launch, the embedding and reranker models may need to be downloaded. Subsequent runs can reuse the locally cached model files.

## 💬 Example Questions

Try asking OpsAtlas:

- What evidence should I collect before escalating an incident?
- How should I investigate database connection pool exhaustion?
- What should I verify before rolling back a database migration?
- What recovery checks should I perform after a deployment rollback?
- Which details should be included when escalating an incident?

Answers depend on the documents available in `data/docs/`. OpsAtlas should not be expected to know organization-specific facts that are absent from its knowledge base.

## 🔍 Retrieval Pipeline

### 1. Document ingestion and chunking

OpsAtlas loads supported documents, splits their content into overlapping text chunks, and preserves source metadata for traceability.

### 2. Hybrid retrieval

Two complementary retrieval methods are used:

- **Dense retrieval:** Embedding-based semantic similarity helps find passages with related meanings, even when the query uses different wording.
- **Sparse retrieval:** BM25 ranks passages using keyword overlap, which is useful for technical terminology, component names, and exact phrases.

### 3. Reciprocal Rank Fusion

The ranked results are combined using RRF:

\[
\operatorname{RRF}(d) =
\sum_{r \in R}
\frac{1}{k + \operatorname{rank}_{r}(d)}
\]

Here, \(d\) is a candidate document or passage, \(R\) is the set of retrieval rankings, and \(k\) is the rank-fusion constant.

RRF combines rankings without requiring the raw scores from different retrieval methods to share the same scale.

### 4. Cross-encoder reranking

A cross-encoder evaluates the relationship between the question and candidate passages. This provides a second-stage relevance ranking after the initial retrieval and fusion process.

### 5. Answer generation and citations

The retrieved passages are provided to the local language model as evidence. The generation prompt requests concise, evidence-grounded answers with citation markers that resolve to source passages.

**Important:** Citation resolution confirms that a marker maps to a retrieved source. It does not, by itself, prove that every claim is entailed by the cited passage. Claim-level citation verification remains a separate evaluation requirement.

## 📊 Evaluation

OpsAtlas includes separate evaluation scripts for retrieval quality and answer behavior.

### Retrieval evaluation

Run:

```bash
python evaluate.py
```

An initial run on a small dataset of six retrieval questions reported the following source-level metrics at \(K=5\):

| Metric | RRF only | RRF + reranker |
|---|---:|---:|
| Source Hit@5 | 1.000 | 1.000 |
| Source Recall@5 | 0.917 | 1.000 |
| Source MRR@5 | 1.000 | 1.000 |
| Source Precision@5 | 0.333 | 0.367 |

These are initial experimental results, not production benchmarks. They measure relevant **source-document retrieval**, not complete passage-level relevance or answer correctness. The dataset is small, and the results should be remeasured after changes to the corpus, chunking, retrieval settings, or models.

### Answer evaluation

Run:

```bash
python evaluate_answers.py
```

The answer evaluation dataset includes answerable questions and selected unanswerable questions. The evaluator checks citation resolution, whether cited sources appear among retrieved results, and abstention behavior for the configured cases.

These checks are useful regression tests, but they do not fully measure factual correctness, citation entailment, completeness, or hallucination rates.

## ⚙️ Configuration

The current implementation defines its main settings in `rag.py`:

| Setting | Default |
|---|---|
| Embedding model | `BAAI/bge-small-en-v1.5` |
| Reranker model | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Ollama model | `qwen2.5:3b` |
| Chunk size | 180 words |
| Chunk overlap | 35 words |
| Default retrieval count | 5 |
| RRF constant | 60 |
| Candidate multiplier | 4 |

Adjust these settings according to the size of the documentation corpus, latency requirements, available memory, and evaluation results.

## 🔒 Privacy and Limitations

- Generation runs locally through Ollama when configured as described.
- Model downloads require an initial network connection unless the models are already available locally.
- The application uses the local document corpus as its knowledge source; incomplete or outdated documentation can produce incomplete answers.
- Citation markers and source resolution are not equivalent to formal claim-level grounding verification.
- The current abstention safeguards cover selected scenarios and are not a general guarantee that unsupported answers will always be rejected.
- The current evaluation datasets are small and are intended for development and regression testing.
- Production deployment would require additional work on access control, document permissions, ingestion monitoring, prompt-injection defenses, comprehensive evaluation, logging policies, and operational reliability.

## 🛣️ Potential Improvements

- Claim-level citation entailment verification
- Broader retrieval and answer-quality benchmarks
- Automated ingestion and document change detection
- Better handling of tables, code blocks, and long technical PDFs
- Query expansion and metadata-aware retrieval
- Structured observability for retrieval latency, generation latency, and failure rates
- Document access controls and prompt-injection defenses
- Regression testing across multiple models and retrieval configurations

## 🎯 Project Goal

OpsAtlas explores how to build a practical, resource-conscious RAG system for technical knowledge retrieval, with emphasis on hybrid search, ranking quality, source traceability, evaluation, and local inference.

It is a foundation for experimenting with more reliable documentation assistants for troubleshooting, incident response, and engineering operations.

---

**Built with Python, hybrid retrieval, open-source models, and Ollama.**
