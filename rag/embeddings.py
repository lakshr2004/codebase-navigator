from sentence_transformers import SentenceTransformer


model = SentenceTransformer("all-MiniLM-L6-v2")


def generate_embedding(text: str) -> list[float]:
    embedding = model.encode(text)

    return embedding.tolist()


if __name__ == "__main__":
    text = "User authentication using JWT"

    embedding = generate_embedding(text)

    print("Embedding generated successfully")
    print("Vector dimension:", len(embedding))
    print("First 5 values:", embedding[:5])