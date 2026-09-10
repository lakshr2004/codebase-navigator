import os
from dotenv import load_dotenv
from groq import Groq

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)


def generate_answer(query: str, context: str) -> str:

    prompt = f"""
You are Codebase Navigator AI.

Answer the user's question using ONLY the provided codebase context.

If the answer cannot be found in the context, say:
"I couldn't find enough information in the codebase."

Codebase Context:
{context}

User Question:
{query}

Answer:
"""

    response = client.chat.completions.create(
        model="openai/gpt-oss-20b",
        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ],
        temperature=0
    )

    return response.choices[0].message.content


if __name__ == "__main__":

    query = "Where is authentication handled?"

    context = """
File: backend/middleware/authMiddleware.js

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