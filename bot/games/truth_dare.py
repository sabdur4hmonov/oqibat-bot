"""Pure truth-answer validation. Dares use the existing typed challenge engine."""

from datetime import datetime


def can_answer(state, user_id, kind, sent_at, message_id):
    return (
        state.get("phase") == "truth"
        and user_id == state["target"]
        and kind in {"text", "voice"}
        and message_id > state.get("answer_after_id", 0)
        and datetime.fromisoformat(state["answer_from"])
        <= sent_at
        <= datetime.fromisoformat(state["answer_until"])
    )
