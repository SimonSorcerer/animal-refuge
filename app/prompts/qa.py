SYSTEM_PROMPT = (
    "You are a wildlife conservation assistant. Answer the user's question using only the "
    "context provided below. If the answer is not contained in the context, say so clearly "
    "— do not hallucinate."
)


def build_user_message(retrieved_chunks: list[str], question: str) -> str:
    context = "\n\n---\n\n".join(retrieved_chunks)
    return f"Context:\n{context}\n\nQuestion: {question}\n\nAnswer:"
