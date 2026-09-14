import os
import warnings
from sentence_transformers import SentenceTransformer

# Suppress unauthenticated HF Hub warning if desired
warnings.filterwarnings("ignore", message=".*unauthenticated requests to the HF Hub.*")

MODEL_NAME = "all-MiniLM-L6-v2"

_embedding_model = None


def get_embedding_model() -> SentenceTransformer:
    global _embedding_model
    if _embedding_model is None:
        token = os.getenv("HF_TOKEN") or None
        _embedding_model = SentenceTransformer(MODEL_NAME, token=token)
    return _embedding_model


class _ModelProxy:
    def encode(self, *args, **kwargs):
        return get_embedding_model().encode(*args, **kwargs)


model = _ModelProxy()


def generate_embedding(text: str) -> list[float]:
    """
    Generate a normalized embedding for a single text.
    """
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    if not text.strip():
        raise ValueError("text cannot be empty")

    embedding = get_embedding_model().encode(
        text,
        normalize_embeddings=True
    )

    return embedding.tolist()


def generate_embeddings(
    texts: list[str],
    batch_size: int = 32
) -> list[list[float]]:
    """
    Generate normalized embeddings for multiple texts.
    """
    if not texts:
        return []

    if batch_size <= 0:
        raise ValueError(
            "batch_size must be greater than 0"
        )

    embeddings = get_embedding_model().encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True
    )

    return embeddings.tolist()