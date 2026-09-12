from sentence_transformers import SentenceTransformer


MODEL_NAME = "all-MiniLM-L6-v2"

model = SentenceTransformer(MODEL_NAME)


def generate_embedding(text: str) -> list[float]:
    """
    Generate a normalized embedding for a single text.
    """

    if not isinstance(text, str):
        raise TypeError("text must be a string")

    if not text.strip():
        raise ValueError("text cannot be empty")

    embedding = model.encode(
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

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        normalize_embeddings=True
    )

    return embeddings.tolist()


if __name__ == "__main__":

    text = "User authentication using JWT"

    embedding = generate_embedding(text)

    print("Embedding generated successfully")
    print("Vector dimension:", len(embedding))
    print("First 5 values:", embedding[:5])

    texts = [
        "User authentication using JWT",
        "Movie booking API",
        "Payment verification"
    ]

    embeddings = generate_embeddings(texts)

    print("\nBatch embeddings generated successfully")
    print("Number of embeddings:", len(embeddings))
    print("Vector dimension:", len(embeddings[0]))