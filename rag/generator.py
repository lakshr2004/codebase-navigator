import os

from dotenv import load_dotenv
from groq import Groq


load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


def generate_answer(query: str, context: str) -> str:
    prompt = f"""
You are Codebase Navigator AI, an AI assistant that helps developers
understand and navigate software repositories.

Your task is to answer the user's question using ONLY the provided
codebase context.

STRICT RULES:

1. Use only information present in the provided context.
2. Do NOT use your general programming knowledge to invent missing details.
3. If the context does not contain enough information to answer the question,
   respond exactly with:
   "I couldn't find enough information in the codebase."
4. Ignore code snippets that are unrelated to the user's question.
5. When possible, mention the relevant file names and line numbers.
6. Explain the code in a clear and developer-friendly way.
7. If multiple files are involved, explain how they work together.
8. Do not claim that a feature exists unless the provided context supports it.
9. Do not hallucinate functions, files, APIs, variables, or implementation details.

CODEBASE CONTEXT:
-----------------
{context}
-----------------

USER QUESTION:
{query}

ANSWER:
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a precise codebase analysis assistant. "
                    "Only use the supplied codebase context."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    return response.choices[0].message.content.strip()


if __name__ == "__main__":
    query = "Where is authentication handled?"

    context = """
File: backend/middleware/authMiddleware.js
Lines: 1 - 40

const protect = async (req, res, next) => {
    const decoded = jwt.verify(token, process.env.JWT_SECRET);
    const user = await User.findById(decoded.id);
    req.user = user;
    next();
};
"""

    answer = generate_answer(query, context)

    print("\n--- Answer ---\n")
    print(answer)