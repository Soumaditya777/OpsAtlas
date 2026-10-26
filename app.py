
import time

import streamlit as st

from rag import build_rag


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="OpsAtlas",
    page_icon="🔎",
    layout="wide",
)

st.title("🔎 OpsAtlas")
st.caption(
    "Local-first RAG · Hybrid Search · RRF · Reranking · Citations"
)

st.markdown(
    """
    Ask questions about your technical operations documentation.
    OpsAtlas retrieves relevant passages and generates answers using
    your local language model.
    """
)


# ============================================================
# LOAD RAG PIPELINE
# ============================================================

@st.cache_resource
def get_rag():
    return build_rag()


with st.sidebar:
    st.header("Configuration")
    st.write("**LLM:** Ollama · Qwen 2.5 3B")
    st.write("**Embeddings:** BGE Small EN")
    st.write("**Retrieval:** Dense + BM25 + RRF")
    st.write("**Reranking:** Cross-encoder")
    st.divider()

    top_k = st.slider(
        "Evidence passages",
        min_value=1,
        max_value=10,
        value=5,
        help="Number of passages used to construct the answer.",
    )

    if st.button("Clear conversation", width="stretch"):
        st.session_state.messages = []
        st.rerun()


try:
    with st.spinner("Loading the local knowledge base..."):
        rag = get_rag()

    st.success(
        f"Knowledge base ready · {len(rag.chunks)} chunks indexed"
    )

except Exception as exc:
    st.error(f"Could not load the knowledge base: {exc}")
    st.info(
        "Check that your documents exist in data/docs and that "
        "the required Python packages and models are available."
    )
    st.stop()


# ============================================================
# SESSION STATE
# ============================================================

if "messages" not in st.session_state:
    st.session_state.messages = []


# ============================================================
# EXAMPLE QUESTIONS
# ============================================================

st.subheader("Try an example")

examples = [
    "What evidence should I collect before escalating an incident?",
    "How should I investigate database connection pool exhaustion?",
    "What should I verify before rolling back a database migration?",
]

example_columns = st.columns(len(examples))

for index, example in enumerate(examples):
    with example_columns[index]:
        if st.button(
            example,
            key=f"example_{index}",
            width="stretch",
        ):
            st.session_state.pending_question = example


# ============================================================
# DISPLAY CONVERSATION
# ============================================================

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

        if message["role"] == "assistant":
            citations = message.get("citations", [])

            if citations:
                with st.expander("View source citations"):
                    for citation in citations:
                        page = (
                            f" · Page {citation['page']}"
                            if citation.get("page") is not None
                            else ""
                        )

                        st.markdown(
                            f"**[{citation['citation_id']}] "
                            f"{citation['source']}{page}**"
                        )
                        st.caption(citation["quote"])

            retrieval = message.get("retrieval", [])

            if retrieval:
                with st.expander("Retrieval diagnostics"):
                    diagnostic_rows = []

                    for item in retrieval:
                        diagnostic_rows.append({
                            "Source": item.get("source", ""),
                            "Page": item.get("page"),
                            "RRF score": round(
                                item.get("rrf_score", 0.0), 5
                            ),
                            "Reranker score": (
                                round(item["rerank_score"], 4)
                                if "rerank_score" in item
                                else None
                            ),
                            "Passage": item.get("text", ""),
                        })

                    st.dataframe(
                        diagnostic_rows,
                        width="stretch",
                        hide_index=True,
                    )

            if message.get("latency_seconds") is not None:
                st.caption(
                    f"Response time: "
                    f"{message['latency_seconds']:.2f} seconds"
                )

            if message.get("abstained"):
                st.caption(
                    "The system abstained or used an evidence fallback."
                )


# ============================================================
# QUESTION INPUT
# ============================================================

pending_question = st.session_state.pop(
    "pending_question",
    None,
)

question = st.chat_input("Ask a question about your runbooks...")

if pending_question:
    question = pending_question


# ============================================================
# GENERATE RESPONSE
# ============================================================

if question and question.strip():
    question = question.strip()

    st.session_state.messages.append({
        "role": "user",
        "content": question,
    })

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        answer_placeholder = st.empty()

        with st.spinner("Retrieving evidence and generating answer..."):
            try:
                result = rag.answer(question, top_k=top_k)

                answer = result["answer"]
                answer_placeholder.markdown(answer)

                citations = result.get("citations", [])
                retrieval = result.get("retrieval", [])
                latency = result.get(
                    "latency_seconds",
                    None,
                )
                abstained = result.get("abstained", False)

                if citations:
                    with st.expander("View source citations"):
                        for citation in citations:
                            page = (
                                f" · Page {citation['page']}"
                                if citation.get("page") is not None
                                else ""
                            )

                            st.markdown(
                                f"**[{citation['citation_id']}] "
                                f"{citation['source']}{page}**"
                            )
                            st.caption(citation["quote"])

                if retrieval:
                    with st.expander("Retrieval diagnostics"):
                        diagnostic_rows = []

                        for item in retrieval:
                            diagnostic_rows.append({
                                "Source": item.get("source", ""),
                                "Page": item.get("page"),
                                "RRF score": round(
                                    item.get("rrf_score", 0.0), 5
                                ),
                                "Reranker score": (
                                    round(item["rerank_score"], 4)
                                    if "rerank_score" in item
                                    else None
                                ),
                                "Passage": item.get("text", ""),
                            })

                        st.dataframe(
                            diagnostic_rows,
                            width="stretch",
                            hide_index=True,
                        )

                if latency is not None:
                    st.caption(f"Response time: {latency:.2f} seconds")

                if abstained:
                    st.info(
                        "OpsAtlas abstained or returned an evidence fallback."
                    )

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": answer,
                    "citations": citations,
                    "retrieval": retrieval,
                    "latency_seconds": latency,
                    "abstained": abstained,
                })

            except Exception as exc:
                error_message = (
                    f"Something went wrong while generating the answer: {exc}"
                )
                answer_placeholder.error(error_message)

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": error_message,
                    "citations": [],
                    "retrieval": [],
                    "abstained": True,
                })
