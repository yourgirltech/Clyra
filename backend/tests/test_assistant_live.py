"""ONE real call to the actual Claude API for 07-assistant-agent — not
mocked. Unlike test_assistant.py (where the model's tool-selection decision
is scripted), this lets the real model decide for itself which tool(s) to
call for a real question against the real seeded database.

Deliberately kept out of test_assistant.py: everything there runs without
network access or credentials; this file requires a real ANTHROPIC_API_KEY
and spends real tokens, so it's opt-in, not part of the default test run.
Run explicitly:

    .venv/Scripts/python.exe -m pytest tests/test_assistant_live.py -v -s

(-s so the printed conversation isn't captured/hidden by pytest.)
"""

import os

import pytest

from app.agents.assistant import AssistantFailure, AssistantTurn, run_assistant
from app.core.config import get_settings

_settings = get_settings()
_has_key = bool(_settings.anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY"))

pytestmark = pytest.mark.skipif(
    not _has_key,
    reason="ANTHROPIC_API_KEY not set — this test makes a real Claude API call",
)


def test_real_claude_answers_which_claims_need_attention():
    from app.db.database import SessionLocal

    db = SessionLocal()
    try:
        question = "Which claims need my attention today?"
        result = run_assistant(db, clinic_id=1, message=question)

        print("\n" + "=" * 78)
        print("07-assistant-agent live conversation")
        print("=" * 78)
        print(f"USER: {question}")

        if isinstance(result, AssistantFailure):
            print(f"\nFAILURE — reason: {result.reason}\ndetail: {result.detail}")
            pytest.fail(f"run_assistant returned a failure: {result.reason} — {result.detail}")

        assert isinstance(result, AssistantTurn)

        print(f"\nASSISTANT: {result.reply}")
        print(f"\nTOOL CALLS ({len(result.tool_calls)}):")
        for call in result.tool_calls:
            print(f"  - {call['tool']}({call['input']}) -> {call['result']}")
        print("\n" + "=" * 78)

        # Grounded, not just "the call succeeded": it must have actually
        # looked something up rather than answering from general knowledge.
        assert len(result.tool_calls) > 0
        assert result.reply.strip() != ""
    finally:
        db.close()
