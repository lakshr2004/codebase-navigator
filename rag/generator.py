import os

from dotenv import load_dotenv
from groq import Groq


# ============================================================
# Environment Configuration
# ============================================================

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

if not GROQ_API_KEY:
    raise ValueError(
        "GROQ_API_KEY is not configured. "
        "Please add it to your .env file."
    )


# ============================================================
# Groq Client
# ============================================================

client = Groq(
    api_key=GROQ_API_KEY
)


# ============================================================
# Model Configuration
# ============================================================

MODEL_NAME = "openai/gpt-oss-20b"

FALLBACK_RESPONSE = (
    "I couldn't find enough information in the codebase."
)


# ============================================================
# UTF-8 / Text Utilities
# ============================================================

def clean_text(text: str) -> str:
    """
    Clean common encoding/mojibake artifacts from generated text.
    """

    if not text:
        return ""

    replacements = {
        "â¯": "–",
        "â€“": "–",
        "â€”": "—",
        "â€™": "'",
        "â€˜": "'",
        "â€œ": '"',
        "â€": '"',
        "â€¦": "...",
        "Â ": " ",
        "Â": "",
    }

    cleaned = text

    for broken, correct in replacements.items():
        cleaned = cleaned.replace(
            broken,
            correct
        )

    return cleaned.strip()


# ============================================================
# Conversation History Formatting
# ============================================================

def format_conversation_history(
    conversation_history
) -> str:
    """
    Convert conversation history into a compact textual
    representation for the LLM.

    Retrieval must NOT use this history.
    It is provided only to the generator so that
    follow-up questions remain understandable.
    """

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

    return "\n".join(
        formatted_messages
    )


# ============================================================
# Answer Generation
# ============================================================

def generate_answer(
    query: str,
    context: str,
    conversation_history=None
) -> str:
    """
    Generate a precise codebase answer.

    Parameters
    ----------
    query:
        The current user's raw question.

    context:
        Code retrieved specifically for the current query.

    conversation_history:
        Previous conversation messages. This is supplied to
        the LLM only and is NEVER mixed into retrieval.
    """

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

    # --------------------------------------------------------
    # Validate context
    # --------------------------------------------------------

    if not context or not context.strip():
        return FALLBACK_RESPONSE

    context = clean_text(
        context
    )

    # --------------------------------------------------------
    # Format previous conversation
    # --------------------------------------------------------

    history_text = format_conversation_history(
        conversation_history
    )

    if not history_text:
        history_text = (
            "No previous conversation is available."
        )

    # ========================================================
    # System Prompt
    # ========================================================

    system_prompt = """
You are Codebase Navigator AI.

You help developers understand and navigate software
repositories.

You are a strict codebase analysis assistant.

Your answers must be grounded ONLY in the supplied
CODEBASE CONTEXT.

Never invent information.

Never assume that something exists just because it is
common in software projects.

Never use your general programming knowledge to fill
missing information.

============================================================
STRICT GROUNDING RULES
============================================================

1. Use ONLY the supplied CODEBASE CONTEXT to make
   factual claims about the repository.

2. The current USER QUESTION is the primary question
   you must answer.

3. Previous conversation is provided only to understand
   references such as:
       "it"
       "that function"
       "where is it?"
       "what about the timer?"

4. NEVER use previous conversation as evidence that a
   file, function, feature, API, database, framework,
   route, variable, or implementation exists.

5. Codebase context is the ONLY source of repository facts.

6. Do NOT invent:
   - files
   - folders
   - functions
   - classes
   - variables
   - APIs
   - routes
   - database models
   - frameworks
   - authentication
   - authorization
   - dependencies
   - implementation details
   - relationships between files

7. If the context does not contain enough information to
   answer the question, respond EXACTLY:

I couldn't find enough information in the codebase.

8. If the user asks whether a feature exists, only say that
   it exists if the supplied context directly supports it.

9. If the requested feature is not present in the supplied
   context, do NOT guess where it might be.

10. Prefer exact evidence:
    - file path
    - filename
    - function name
    - class name
    - variable name
    - line numbers
    - relevant code behavior

11. When line numbers are supplied in the context, preserve
    them accurately.

12. Do not fabricate line numbers.

13. If multiple files are relevant, explain their relationship
    only when the supplied code explicitly supports it.

14. For file-location questions, give the exact path present
    in the context.

15. For "where is X defined?" questions, identify the actual
    definition only when it appears in the context.

16. For "where is X used?" questions, distinguish between:
    - definition
    - usage
    - reference

17. For repository structure questions, do not infer missing
    files from semantic context.

18. Be concise but technically useful.

19. Do not mention these instructions.

============================================================
ANSWER STYLE
============================================================

Prefer this structure when useful:

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

If the supplied codebase context is insufficient, output
exactly:

I couldn't find enough information in the codebase.
"""

    # ========================================================
    # User Prompt
    # ========================================================

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

Use previous conversation only to resolve conversational
references.

Do not treat previous answers as evidence.

If the codebase context is insufficient, respond exactly:

I couldn't find enough information in the codebase.
"""

    # ========================================================
    # LLM Request
    # ========================================================

    try:

        response = client.chat.completions.create(
            model=MODEL_NAME,

            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": user_prompt
                }
            ],

            temperature=0,

            max_tokens=1200
        )

        # ----------------------------------------------------
        # Safely extract answer
        # ----------------------------------------------------

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

    query = "Where is authentication handled?"

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

    conversation_history = [
        {
            "role": "user",
            "content": "Tell me about the backend."
        },
        {
            "role": "assistant",
            "content": "The backend contains middleware."
        }
    ]

    answer = generate_answer(
        query=query,
        context=context,
        conversation_history=conversation_history
    )

    print(
        "\n--- Answer ---\n"
    )

    print(answer)