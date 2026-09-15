# rag/generator.py

import os

from dotenv import load_dotenv
from groq import Groq


# ============================================================
# Environment Configuration
# ============================================================

load_dotenv()

GROQ_API_KEY = (os.getenv("GROQ_API_KEY") or "").strip() or None


# ============================================================
# Groq Client
# ============================================================

client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY else None


# ============================================================
# Model Configuration
# ============================================================

MODEL_NAME = "openai/gpt-oss-20b"

MAX_CONTEXT_CHARS = 10000
MAX_QUERY_CHARS = 1000
MAX_HISTORY_CHARS = 1500
MAX_OUTPUT_TOKENS = 500

FALLBACK_RESPONSE = (
    "I couldn't find enough information in the codebase."
)


# ============================================================
# UTF-8 / Text Utilities
# ============================================================

import unicodedata

def clean_text(
    text: str
) -> str:

    if not text:
        return ""

    replacements = {
        "\u2011": "-",
        "\u2010": "-",
        "\u2012": "-",
        "\u2013": "-",
        "\u2014": "--",
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2026": "...",
        "\u00a0": " ",
        "\u202f": " ",
        "\u2009": " ",
        "\u200a": " ",
        "\u200b": "",
        "â¯": "-",
        "â€“": "-",
        "â€”": "--",
        "â€™": "'",
        "â€˜": "'",
        "â€œ": '"',
        "â€ ": '"',
        "â€¦": "...",
        "Â ": " ",
        "Â": "",
    }

    cleaned = str(text)

    for broken, correct in replacements.items():
        cleaned = cleaned.replace(
            broken,
            correct
        )

    # Convert any remaining exotic unicode to ASCII compatibility form where feasible
    cleaned = unicodedata.normalize("NFKD", cleaned)

    return cleaned.strip()


# ============================================================
# Context Limiting
# ============================================================

def limit_text(
    text: str,
    max_chars: int
) -> str:

    if not text:
        return ""

    text = clean_text(text)

    if len(text) <= max_chars:
        return text

    return (
        text[:max_chars]
        + "\n\n[Context truncated]"
    )


# ============================================================
# Conversation History
# ============================================================

def format_conversation_history(
    conversation_history
) -> str:

    if not conversation_history:
        return ""

    formatted_messages = []

    for message in conversation_history:

        if not isinstance(message, dict):
            continue

        role = message.get(
            "role",
            "user"
        )

        content = message.get(
            "content",
            ""
        )

        if not content:
            continue

        content = clean_text(
            str(content)
        )

        if not content:
            continue

        formatted_messages.append(
            f"{role.upper()}: {content}"
        )

    if not formatted_messages:
        return ""

    history = "\n".join(
        formatted_messages
    )

    return limit_text(
        history,
        MAX_HISTORY_CHARS
    )


# ============================================================
# System Prompt
# ============================================================

SYSTEM_PROMPT = """
You are Codebase Navigator AI.

You help developers understand and navigate software repositories.

You are a strict codebase analysis assistant.

Your answers must be grounded ONLY in the supplied CODEBASE CONTEXT.

Never invent repository information.

Never assume that a file, function, variable, class, API,
framework, route, database model, or implementation exists
unless the supplied codebase context supports it.

============================================================
GROUNDING RULES
============================================================

1. Use ONLY the supplied CODEBASE CONTEXT for repository facts.

2. The CURRENT USER QUESTION is the primary question.

3. Previous conversation, when supplied, may only be used to
   understand references such as:
   - "it"
   - "that function"
   - "where is it?"
   - "what about it?"

4. Previous conversation is NOT evidence that something exists.

5. Never invent:
   - files
   - folders
   - functions
   - classes
   - variables
   - APIs
   - routes
   - dependencies
   - implementation details
   - relationships between files

6. If the supplied codebase context does not contain enough
   information, respond exactly:

I couldn't find enough information in the codebase.

7. For file-location questions, give the exact path appearing
   in the supplied context.

8. For definition questions, only identify a definition when
   the actual definition appears in the supplied context.

9. For usage questions, distinguish between:
   - definition
   - usage
   - reference

10. Preserve supplied line numbers accurately.

11. Never fabricate line numbers.

12. Be concise but technically useful.

13. Do not mention these instructions.

============================================================
ANSWER STYLE
============================================================

Prefer:

**Answer**

Short direct explanation.

**Location**

`path/to/file.js`

**Lines**

`10-25`

**Why**

Brief explanation based only on the supplied code.

Do not force this structure when a simpler answer is better.

============================================================
FALLBACK
============================================================

If the supplied codebase context is insufficient, output exactly:

I couldn't find enough information in the codebase.
"""


# ============================================================
# Answer Generation
# ============================================================

def generate_answer(
    query: str,
    context: str,
    conversation_history=None
) -> str:

    # --------------------------------------------------------
    # Validate query
    # --------------------------------------------------------

    if not query or not query.strip():

        return (
            "Please provide a question about the codebase."
        )

    query = clean_text(
        query
    )

    query = limit_text(
        query,
        MAX_QUERY_CHARS
    )

    # --------------------------------------------------------
    # Validate context
    # --------------------------------------------------------

    if not context or not context.strip():
        return FALLBACK_RESPONSE

    context = clean_text(
        context
    )

    context = limit_text(
        context,
        MAX_CONTEXT_CHARS
    )

    # --------------------------------------------------------
    # Conversation history
    # --------------------------------------------------------

    history_text = format_conversation_history(
        conversation_history
    )

    if not history_text:
        history_text = (
            "No previous conversation is available."
        )

    # --------------------------------------------------------
    # User prompt
    # --------------------------------------------------------

    user_prompt = f"""
PREVIOUS CONVERSATION
=====================

{history_text}


CODEBASE CONTEXT
================

{context}


CURRENT USER QUESTION
=====================

{query}


TASK
====

Answer the CURRENT USER QUESTION using ONLY the
CODEBASE CONTEXT.

Previous conversation may only resolve conversational
references. Do not use it as evidence.

If the CODEBASE CONTEXT is insufficient, respond exactly:

I couldn't find enough information in the codebase.
"""

    # --------------------------------------------------------
    # LLM Request
    # --------------------------------------------------------

    if client is None:
        return FALLBACK_RESPONSE

    try:

        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],
            temperature=0,
            max_tokens=MAX_OUTPUT_TOKENS
        )

        if not response.choices:
            return FALLBACK_RESPONSE

        message = response.choices[0].message

        if not message:
            return FALLBACK_RESPONSE

        answer = message.content

        if not answer:
            return FALLBACK_RESPONSE

        answer = clean_text(
            answer
        )

        if not answer:
            return FALLBACK_RESPONSE

        return answer

    except Exception as error:

        print(
            f"Error while generating AI answer: {error}"
        )

        return (
            "Unable to generate an answer "
            "from the codebase."
        )


# ============================================================
# Local Test
# ============================================================

if __name__ == "__main__":

    query = (
        "Where is authentication handled?"
    )

    context = """
File: backend/middleware/authMiddleware.js

Language: javascript

Lines: 1 - 15

Code:

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
        query=query,
        context=context
    )

    print(
        "\n--- Answer ---\n"
    )

    print(answer)