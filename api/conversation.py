from typing import Dict, List


# In-memory conversation storage
# session_id -> list of messages
conversation_history: Dict[str, List[dict]] = {}


def get_history(session_id: str) -> List[dict]:
    """
    Return conversation history for a session.
    """

    return conversation_history.get(
        session_id,
        []
    )


def add_message(
    session_id: str,
    role: str,
    content: str
):
    """
    Add a message to a conversation.
    """

    if session_id not in conversation_history:
        conversation_history[session_id] = []

    conversation_history[session_id].append({
        "role": role,
        "content": content
    })


def clear_history(session_id: str):
    """
    Clear conversation history for a session.
    """

    conversation_history.pop(
        session_id,
        None
    )


def build_conversation_context(
    session_id: str
) -> str:
    """
    Convert conversation history into
    text context for the LLM.
    """

    history = get_history(session_id)

    if not history:
        return ""

    context_parts = []

    for message in history:

        role = message["role"]
        content = message["content"]

        if role == "user":
            context_parts.append(
                f"User: {content}"
            )

        elif role == "assistant":
            context_parts.append(
                f"Assistant: {content}"
            )

    return "\n".join(context_parts)