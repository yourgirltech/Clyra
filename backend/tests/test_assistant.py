"""Tests for 07-assistant-agent (backend/app/agents/assistant.py).

The LLM's *decisions* are mocked throughout (a scripted response stands in
for "the model decided to call tool X" or "the model answered directly") —
what's under test is that the manual tool-use loop dispatches to the right
Python function, executes it against the real seeded database, and enforces
grounding/no-action correctly. The one real Claude API call, deciding for
itself which tool to use, lives in test_assistant_live.py.
"""

import inspect
from types import SimpleNamespace

import pytest

from app.agents import assistant as assistant_module
from app.agents.assistant import (
    TOOL_DEFS,
    AssistantFailure,
    AssistantTurn,
    run_assistant,
)

CLINIC_ID = 1


def text_block(text):
    return SimpleNamespace(type="text", text=text)


def tool_use_block(id_, name, input_):
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=input_)


def fake_response(stop_reason, content):
    return SimpleNamespace(stop_reason=stop_reason, content=content)


class ScriptedMessages:
    """Stands in for client.messages — .create() pops the next scripted response."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if not self._responses:
            raise AssertionError("ScriptedMessages ran out of canned responses")
        return self._responses.pop(0)


class ScriptedClient:
    def __init__(self, responses):
        self.messages = ScriptedMessages(responses)


@pytest.fixture
def db():
    from app.db.database import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# One test per tool: the model "decides" (scripted) to call it, the manual
# loop dispatches to the real Python function against the real seeded DB,
# and produces a grounded final answer.
# ---------------------------------------------------------------------------

def test_tool_get_claim(db):
    client = ScriptedClient([
        fake_response("tool_use", [tool_use_block("t1", "get_claim", {"claim_id": "CL-10002"})]),
        fake_response("end_turn", [text_block("CL-10002 is High risk, $3826.33, payer DistPayerHigh.")]),
    ])

    result = run_assistant(db, CLINIC_ID, "Tell me about CL-10002.", client=client)

    assert isinstance(result, AssistantTurn)
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0]["tool"] == "get_claim"
    assert result.tool_calls[0]["result"]["found"] is True
    assert result.tool_calls[0]["result"]["risk_level"] == "High"
    assert "CL-10002" in result.reply


def test_tool_get_claim_including_terminal_status(db):
    # Per spec: claim lookup works on terminal claims too (Paid/Denied/etc.) —
    # read-only, no different from any other claim_id.
    from app import models

    paid_claim = db.query(models.Claim).filter(models.Claim.status == "Paid").first()
    assert paid_claim is not None, "seeded data must include at least one Paid claim for this test"

    client = ScriptedClient([
        fake_response("tool_use", [tool_use_block("t1", "get_claim", {"claim_id": paid_claim.claim_id})]),
        fake_response("end_turn", [text_block(f"{paid_claim.claim_id} is Paid.")]),
    ])

    result = run_assistant(db, CLINIC_ID, f"What's the status of {paid_claim.claim_id}?", client=client)

    assert isinstance(result, AssistantTurn)
    assert result.tool_calls[0]["result"]["found"] is True
    assert result.tool_calls[0]["result"]["status"] == "Paid"


def test_tool_get_claims_by_risk(db):
    client = ScriptedClient([
        fake_response("tool_use", [tool_use_block("t1", "get_claims_by_risk", {"level": "High"})]),
        fake_response("end_turn", [text_block("Several claims are High risk right now.")]),
    ])

    result = run_assistant(db, CLINIC_ID, "Show me my highest-risk claims.", client=client)

    assert isinstance(result, AssistantTurn)
    assert result.tool_calls[0]["tool"] == "get_claims_by_risk"
    assert result.tool_calls[0]["result"]["level"] == "High"
    assert result.tool_calls[0]["result"]["count"] > 0


def test_tool_get_overdue_claims(db):
    client = ScriptedClient([
        fake_response("tool_use", [tool_use_block("t1", "get_overdue_claims", {})]),
        fake_response("end_turn", [text_block("A few claims are overdue for follow-up.")]),
    ])

    result = run_assistant(db, CLINIC_ID, "Which claims are waiting too long?", client=client)

    assert isinstance(result, AssistantTurn)
    assert result.tool_calls[0]["tool"] == "get_overdue_claims"
    assert result.tool_calls[0]["result"]["count"] > 0


def test_tool_get_claims_by_payer(db):
    client = ScriptedClient([
        fake_response("tool_use", [tool_use_block("t1", "get_claims_by_payer", {"payer": "DistPayerHigh"})]),
        fake_response("end_turn", [text_block("DistPayerHigh has a few claims open.")]),
    ])

    result = run_assistant(db, CLINIC_ID, "Which claims does DistPayerHigh have?", client=client)

    assert isinstance(result, AssistantTurn)
    assert result.tool_calls[0]["tool"] == "get_claims_by_payer"
    assert result.tool_calls[0]["result"]["count"] > 0
    assert all("DistPayerHigh" in c["payer"] for c in result.tool_calls[0]["result"]["claims"])


def test_tool_analyze_claim(db):
    client = ScriptedClient([
        fake_response("tool_use", [tool_use_block("t1", "analyze_claim", {"claim_id": "CL-10002"})]),
        fake_response("end_turn", [text_block("CL-10002 is flagged for missing authorization, among other issues.")]),
    ])

    result = run_assistant(db, CLINIC_ID, "Why was CL-10002 flagged?", client=client)

    assert isinstance(result, AssistantTurn)
    assert result.tool_calls[0]["tool"] == "analyze_claim"
    issue_types = {i["issue_type"] for i in result.tool_calls[0]["result"]["issues"]}
    assert "missing_authorization" in issue_types
    assert result.tool_calls[0]["result"]["risk_score"] == 100


def test_multiple_tool_calls_in_one_turn(db):
    # The model can ask for two tools in a single turn (e.g. look up the
    # claim, then run the rule engine on it) — both must execute and both
    # results must come back before the final answer.
    client = ScriptedClient([
        fake_response(
            "tool_use",
            [
                tool_use_block("t1", "get_claim", {"claim_id": "CL-10002"}),
                tool_use_block("t2", "analyze_claim", {"claim_id": "CL-10002"}),
            ],
        ),
        fake_response("end_turn", [text_block("CL-10002 is High risk with a missing authorization.")]),
    ])

    result = run_assistant(db, CLINIC_ID, "Tell me everything about CL-10002.", client=client)

    assert isinstance(result, AssistantTurn)
    assert {c["tool"] for c in result.tool_calls} == {"get_claim", "analyze_claim"}


# ---------------------------------------------------------------------------
# Grounding: never invent data not actually looked up via a tool call.
# ---------------------------------------------------------------------------

def test_refuses_to_invent_claim_data_not_looked_up(db):
    client = ScriptedClient([
        fake_response("tool_use", [tool_use_block("t1", "get_claim", {"claim_id": "CL-10002"})]),
        fake_response(
            "end_turn",
            [text_block("CL-10002 looks fine, and CL-99999 also seems concerning.")],  # CL-99999 never looked up
        ),
    ])

    result = run_assistant(db, CLINIC_ID, "Tell me about CL-10002.", client=client)

    assert isinstance(result, AssistantFailure)
    assert result.reason == "ungrounded_output"
    assert "CL-99999" in result.detail


def test_grounding_check_ignores_claim_ids_that_were_looked_up_even_if_not_found(db):
    # A tool call that comes back "not found" still counts as "looked up" —
    # the model is allowed to say "CL-00000 doesn't exist" without that
    # being treated as an invented claim.
    client = ScriptedClient([
        fake_response("tool_use", [tool_use_block("t1", "get_claim", {"claim_id": "CL-00000"})]),
        fake_response("end_turn", [text_block("I couldn't find a claim with ID CL-00000.")]),
    ])

    result = run_assistant(db, CLINIC_ID, "Tell me about CL-00000.", client=client)

    assert isinstance(result, AssistantTurn)
    assert result.tool_calls[0]["result"]["found"] is False


# ---------------------------------------------------------------------------
# Never executes an action, regardless of phrasing — it explains instead.
# ---------------------------------------------------------------------------

def test_explains_the_approval_flow_instead_of_acting(db):
    # No tool call at all here — the model (per the system prompt) just
    # explains directly, because there is nothing it *could* call to act.
    client = ScriptedClient([
        fake_response(
            "end_turn",
            [text_block(
                "I can't send that reminder myself — please approve it from the claim's detail page, "
                "and the automation layer will handle it once you do."
            )],
        ),
    ])

    result = run_assistant(db, CLINIC_ID, "Go ahead and send the payer reminder for CL-10002.", client=client)

    assert isinstance(result, AssistantTurn)
    assert result.tool_calls == []
    assert "approve" in result.reply.lower() or "can't" in result.reply.lower()


def test_no_tool_can_execute_an_action():
    # Structural guarantee, not just a prompt instruction: the tool set is
    # exactly the five read-only tools — nothing that sends, approves, or
    # executes exists for the model to call in the first place.
    names = {t["name"] for t in TOOL_DEFS}
    assert names == {
        "get_claim",
        "get_claims_by_risk",
        "get_overdue_claims",
        "get_claims_by_payer",
        "analyze_claim",
    }


def test_never_imports_escalation_dispatch_or_commander():
    # This agent sits outside Commander's rule table and must never route a
    # failure to 06-escalation-agent — escalation is for pipeline automation
    # failures, not "I don't know." Confirmed structurally: the module has no
    # import dependency on any of them (the module docstring *discusses* this
    # design choice in prose, which is fine — this checks actual imports).
    import ast

    tree = ast.parse(inspect.getsource(assistant_module))
    imported_modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported_modules.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imported_modules.add(alias.name)

    for forbidden in ("app.agents.escalation", "app.agents.dispatch", "app.agents.commander"):
        assert forbidden not in imported_modules, f"assistant.py must not import {forbidden}"


# ---------------------------------------------------------------------------
# Failure paths: never crash, always a structured AssistantFailure.
# ---------------------------------------------------------------------------

def test_llm_exception_returns_structured_failure_not_a_crash(db):
    class ExplodingMessages:
        def create(self, **kwargs):
            raise RuntimeError("network exploded")

    class ExplodingClient:
        messages = ExplodingMessages()

    result = run_assistant(db, CLINIC_ID, "Anything?", client=ExplodingClient())

    assert isinstance(result, AssistantFailure)
    assert result.reason == "llm_call_failed"
    assert "network exploded" in result.detail


def test_max_iterations_exceeded_returns_failure_not_infinite_loop(db):
    from app.agents.assistant import MAX_TOOL_ITERATIONS

    # The model keeps calling a tool forever and never gives a final answer.
    responses = [
        fake_response("tool_use", [tool_use_block(f"t{i}", "get_overdue_claims", {})])
        for i in range(MAX_TOOL_ITERATIONS)
    ]
    client = ScriptedClient(responses)

    result = run_assistant(db, CLINIC_ID, "Loop forever.", client=client)

    assert isinstance(result, AssistantFailure)
    assert result.reason == "llm_call_failed"
    assert str(MAX_TOOL_ITERATIONS) in result.detail
