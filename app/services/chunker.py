import tiktoken

from app.config import settings

_enc = tiktoken.get_encoding("cl100k_base")


def _token_len(text: str) -> int:
    return len(_enc.encode(text))


def split_into_chunks(text: str) -> list[str]:
    """Split text into overlapping chunks that respect sentence boundaries."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current_tokens: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = _token_len(para)

        if current_len + para_len > settings.chunk_size and current_tokens:
            chunks.append(" ".join(current_tokens))
            # keep overlap: walk back from end until we've collected overlap tokens
            overlap_tokens: list[str] = []
            overlap_len = 0
            for token in reversed(current_tokens):
                t_len = _token_len(token)
                if overlap_len + t_len > settings.chunk_overlap:
                    break
                overlap_tokens.insert(0, token)
                overlap_len += t_len
            current_tokens = overlap_tokens
            current_len = overlap_len

        # paragraph itself is larger than chunk_size — split by sentences
        if para_len > settings.chunk_size:
            sentences = _split_sentences(para)
            for sentence in sentences:
                s_len = _token_len(sentence)
                if current_len + s_len > settings.chunk_size and current_tokens:
                    chunks.append(" ".join(current_tokens))
                    current_tokens = []
                    current_len = 0
                current_tokens.append(sentence)
                current_len += s_len
        else:
            current_tokens.append(para)
            current_len += para_len

    if current_tokens:
        chunks.append(" ".join(current_tokens))

    return [c for c in chunks if c.strip()]


def _split_sentences(text: str) -> list[str]:
    """Naive sentence splitter on '. ', '! ', '? '."""
    import re
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [p.strip() for p in parts if p.strip()]
