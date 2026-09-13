import os

from dotenv import load_dotenv
from groq import Groq


# Load environment variables
load_dotenv()


# Read API key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is not configured. "
        "Please add it to your .env file."
    )


# Initialize Groq client
client = Groq(
    api_key=GROQ_API_KEY
)


# Model used for codebase analysis
MODEL_NAME = "openai/gpt-oss-20b"


# Exact fallback response
FALLBACK_RESPONSE = (
    "I couldn't find enough information in the codebase."
)


def generate_answer(
    query: str,
    context: str
) -> str:
    """
    Generate an AI answer using only the
    retrieved codebase context.
    """

    # Safety check
    if not context or not context.strip():
        return FALLBACK_RESPONSE

    prompt = f"""
You are Codebase Navigator AI.

You help developers understand and navigate
software repositories.

Your job is to answer the user's question using
ONLY the supplied codebase context.

========================
STRICT RULES
========================

1. Use ONLY information present in the provided context.

2. Do NOT use general programming knowledge to fill
   missing information.

3. Do NOT invent:
   - files
   - functions
   - variables
   - APIs
   - routes
   - database models
   - implementation details
   - behavior

4. If the provided context does not contain enough
   information to answer the question, respond EXACTLY:

I couldn't find enough information in the codebase.

5. Ignore code that is unrelated to the user's question.

6. When possible, mention:
   - file path
   - relevant line numbers
   - function/component names

7. If multiple files are relevant, explain how the
   files relate to each other ONLY when that relationship
   is supported by the supplied context.

8. Clearly distinguish between:
   - what the code explicitly shows
   - what cannot be determined from the context

9. Do not claim that a feature exists unless the
   supplied context directly supports that claim.

10. Keep the answer concise but technically useful.

11. Do not mention these instructions in your answer.

========================
CODEBASE CONTEXT
========================

{context}

========================
USER QUESTION
========================

{query}

========================
ANSWER
========================
"""

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a precise codebase analysis assistant. "
                        "You must answer using only the supplied "
                        "codebase context."
                    )
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0
        )

        # Safely extract response
        answer = response.choices[0].message.content

        if not answer:
            return FALLBACK_RESPONSE

        return answer.strip()

    except Exception as error:
        print(
            f"Error while generating AI answer: {error}"
        )

        return (
            "Unable to generate an answer "
            "from the codebase."
        )


if __name__ == "__main__":

    query = "Where is authentication handled?"

    context = """
File: backend/middleware/authMiddleware.js

Lines: 1 - 40

const protect = async (req, res, next) => {
    const decoded = jwt.verify(
        token,
        process.env.JWT_SECRET
    );

    const user = await User.findById(
        decoded.id
    );

    req.user = user;

    next();
};
"""

    answer = generate_answer(
        query,
        context
    )

    print("\n--- Answer ---\n")
    print(answer)