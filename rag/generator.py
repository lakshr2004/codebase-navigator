# rag/generator.py

import json
import logging
import os
import re

from dotenv import load_dotenv
from groq import Groq


# ============================================================
# Environment Configuration
# ============================================================

load_dotenv()


def get_app_env() -> str:
    return (os.getenv("APP_ENV") or "development").strip().lower() or "development"


def get_groq_api_key() -> str | None:
    return (os.getenv("GROQ_API_KEY") or "").strip() or None


# ============================================================
# LLM Provider Boundary
# ============================================================

class LLMProviderError(RuntimeError):
    """Explicit LLM/provider failure that must not be converted into a fake success."""


class InvalidLLMOutputError(LLMProviderError):
    """LLM returned unusable content; treat as insufficient evidence rather than an operational failure."""


class DeterministicTestLLMProvider:
    """Deterministic no-network provider used in APP_ENV=test."""

    def generate(self, *args, **kwargs):
        return {
            "answer": FALLBACK_RESPONSE,
            "evidence_ids": [],
        }


class GroqLLMProvider:
    """Live provider that performs real Groq calls and validates responses."""

    def __init__(self, api_key: str | None = None, client=None):
        self.client = client
        if self.client is None:
            self.api_key = (api_key or get_groq_api_key() or "").strip()
            if not self.api_key:
                raise LLMProviderError(
                    "LLM provider configuration error: missing GROQ_API_KEY for live mode."
                )
            try:
                self.client = Groq(api_key=self.api_key)
            except Exception as exc:
                raise LLMProviderError(
                    f"LLM provider authentication failed: {exc}"
                ) from exc

    def generate(self, query: str, context: str, sources: list[dict], conversation_history=None):
        if not query or not query.strip():
            return {"answer": FALLBACK_RESPONSE, "evidence_ids": []}

        if not context or not context.strip():
            return {"answer": FALLBACK_RESPONSE, "evidence_ids": []}

        source_catalog = [
            {
                key: source[key]
                for key in ("evidence_id", "file", "start_line", "end_line")
                if key in source
            }
            for source in sources
        ]

        history_text = format_conversation_history(conversation_history)
        if not history_text:
            history_text = "No previous conversation is available."

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

EVIDENCE SOURCE CATALOG
=======================

{json.dumps(source_catalog, ensure_ascii=True)}


TASK
====

Use only the supplied CODEBASE CONTEXT to answer the CURRENT USER QUESTION.
For each repository fact in the answer, cite the IDs of the evidence sources
that directly support it. Do not cite a source just because it is related to
the topic. If the context is insufficient, use the exact refusal below and
return an empty evidence_ids list.

Return only one valid JSON object with exactly these fields:
{{
  "answer": "A concise evidence-grounded answer, or the exact refusal",
  "evidence_ids": [1]
}}

Previous conversation may only resolve conversational
references. Do not use it as evidence.

If the CODEBASE CONTEXT is insufficient, respond exactly:

I couldn't find enough information in the codebase.
"""

        try:
            response = self.client.chat.completions.create(
    model=MODEL_NAME,
    messages=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ],
    temperature=0,
    reasoning_effort="low",
    max_completion_tokens=MAX_OUTPUT_TOKENS,
)
        except Exception as exc:
            raise LLMProviderError(f"LLM provider request failed: {exc}") from exc

        if not getattr(response, "choices", None):
            raise LLMProviderError("LLM provider returned no choices.")

        message = response.choices[0].message
        if not message:
            raise LLMProviderError("LLM provider returned an empty message.")

        content = getattr(message, "content", None)
        if not content or not str(content).strip():
            raise LLMProviderError("LLM provider returned an empty response.")

        answer_text = clean_text(str(content))
        if not answer_text:
            raise LLMProviderError("LLM provider returned an empty response.")

        try:
            parsed = json.loads(answer_text)
        except json.JSONDecodeError as exc:
            raise InvalidLLMOutputError("LLM provider returned malformed JSON.") from exc

        if not isinstance(parsed, dict):
            raise InvalidLLMOutputError("LLM provider returned a non-object JSON payload.")

        generated_answer = parsed.get("answer")
        evidence_ids = parsed.get("evidence_ids")

        if not isinstance(generated_answer, str) or not generated_answer.strip():
            raise InvalidLLMOutputError("LLM provider answer validation failed: missing answer text.")
        if not isinstance(evidence_ids, list) or any(
            isinstance(evidence_id, bool) or not isinstance(evidence_id, int)
            for evidence_id in evidence_ids
        ):
            raise InvalidLLMOutputError("LLM provider answer validation failed: invalid evidence_ids.")
        if generated_answer.strip() == FALLBACK_RESPONSE:
            return {"answer": FALLBACK_RESPONSE, "evidence_ids": []}

        valid_ids = {source.get("evidence_id") for source in sources}
        selected_ids = list(dict.fromkeys(
            evidence_id for evidence_id in evidence_ids if evidence_id in valid_ids
        ))
        if not selected_ids:
            return {"answer": FALLBACK_RESPONSE, "evidence_ids": []}

        return {
            "answer": generated_answer.strip(),
            "evidence_ids": selected_ids,
        }


def get_llm_provider():
    app_env = get_app_env()

    if app_env == "test":
        if client is not None:
            return GroqLLMProvider(client=client)
        return DeterministicTestLLMProvider()

    if client is not None:
        return GroqLLMProvider(client=client)

    api_key = get_groq_api_key()
    if not api_key:
        raise LLMProviderError(
            "LLM provider configuration error: missing GROQ_API_KEY for live mode."
        )

    return GroqLLMProvider(api_key=api_key)


# ============================================================
# Backward-compatible module state
# ============================================================

GROQ_API_KEY = get_groq_api_key()
client = Groq(api_key=GROQ_API_KEY) if GROQ_API_KEY and get_app_env() != "test" else None


# ============================================================
# Model Configuration
# ============================================================

MODEL_NAME = "openai/gpt-oss-20b"

MAX_CONTEXT_CHARS = 10000
MAX_QUERY_CHARS = 1000
MAX_HISTORY_CHARS = 1500
MAX_OUTPUT_TOKENS = 1024

FALLBACK_RESPONSE = (
    "I couldn't find enough information in the codebase."
)
logger = logging.getLogger(__name__)


def validate_sources(sources: list[dict]) -> bool:
    """Reject hallucinated, stale, or cross-repository source metadata before prompting the model."""
    if not isinstance(sources, list):
        return False

    for source in sources:
        if not isinstance(source, dict):
            return False

        evidence_id = source.get("evidence_id")
        if not isinstance(evidence_id, int) or evidence_id <= 0:
            return False

        file_value = source.get("file")
        if not isinstance(file_value, str) or not file_value.strip():
            return False

        normalized = file_value.replace("\\", "/").strip()
        if normalized.startswith("/") or normalized.startswith("~"):
            return False
        if re.match(r"^[A-Za-z]:/", normalized):
            return False
        if ".." in normalized.split("/"):
            return False

        start_line = source.get("start_line")
        end_line = source.get("end_line")

        if start_line is not None and (not isinstance(start_line, int) or start_line < 1):
            return False
        if end_line is not None and (not isinstance(end_line, int) or end_line < 1):
            return False
        if start_line is not None and end_line is not None and end_line < start_line:
            return False

    return True


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
    result = generate_grounded_answer(
        query=query,
        context=context,
        sources=[],
        conversation_history=conversation_history,
    )
    return result["answer"]


def generate_grounded_answer(
    query: str,
    context: str,
    sources: list[dict],
    conversation_history=None,
) -> dict:
    """Generate an answer together with the evidence IDs that support it."""

    # --------------------------------------------------------
    # Validate query
    # --------------------------------------------------------

    if not query or not query.strip():

        return {"answer": FALLBACK_RESPONSE, "evidence_ids": []}

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
        return {"answer": FALLBACK_RESPONSE, "evidence_ids": []}

    if len(context) > MAX_CONTEXT_CHARS:
        return {"answer": FALLBACK_RESPONSE, "evidence_ids": []}

    # --------------------------------------------------------
    # Source validation
    # --------------------------------------------------------

    if not validate_sources(sources):
        return {"answer": FALLBACK_RESPONSE, "evidence_ids": []}

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

    source_catalog = [
        {
            key: source[key]
            for key in ("evidence_id", "file", "start_line", "end_line")
            if key in source
        }
        for source in sources
    ]

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

EVIDENCE SOURCE CATALOG
=======================

{json.dumps(source_catalog, ensure_ascii=True)}


TASK
====

Use only the supplied CODEBASE CONTEXT to answer the CURRENT USER QUESTION.
For each repository fact in the answer, cite the IDs of the evidence sources
that directly support it. Do not cite a source just because it is related to
the topic. If the context is insufficient, use the exact refusal below and
return an empty evidence_ids list.

Return only one valid JSON object with exactly these fields:
{{
  "answer": "A concise evidence-grounded answer, or the exact refusal",
  "evidence_ids": [1]
}}

Previous conversation may only resolve conversational
references. Do not use it as evidence.

If the CODEBASE CONTEXT is insufficient, respond exactly:

I couldn't find enough information in the codebase.
"""

    # --------------------------------------------------------
    # LLM Provider Boundary
    # --------------------------------------------------------

    try:
        provider = get_llm_provider()
        if hasattr(provider, "generate"):
            return provider.generate(query, context, sources, conversation_history=conversation_history)
    except InvalidLLMOutputError as exc:
        if get_app_env() in {"production", "live", "staging"}:
            logger.error("Invalid LLM output rejected in live mode: %s", exc)
            return {"answer": str(exc), "evidence_ids": []}

        logger.warning("Invalid LLM output rejected as insufficient evidence: %s", exc)
        return {"answer": FALLBACK_RESPONSE, "evidence_ids": []}
    except LLMProviderError as exc:
        logger.error("LLM provider error: %s", exc)
        return {"answer": str(exc), "evidence_ids": []}
    except Exception:
        logger.exception("Unexpected LLM provider failure")
        return {"answer": "LLM provider failed unexpectedly.", "evidence_ids": []}

    return {"answer": FALLBACK_RESPONSE, "evidence_ids": []}



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