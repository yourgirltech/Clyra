"""A deterministic stand-in for `anthropic.Anthropic`, used only when
`Settings.mock_anthropic` is true (env `MOCK_ANTHROPIC=1`). Exists for the
Playwright E2E journey (frontend/e2e/), which drives the real running app —
real HTTP, real Postgres, real Commander routing — end to end, and needs
02-reasoning-agent/03-recommendation-agent to not spend real tokens or
return nondeterministic output while doing it.

Deliberately generic: `issue_explanations`/`cited_issue_types` are left
empty rather than echoing back whatever issues the real seeded claim
happens to have. Both agents validate that any issue_type they claim to
cite was actually in their input (`cited - given` must be empty) — an empty
set trivially satisfies that check no matter which real claim the E2E test
picks, so this fake never needs to know the claim's actual issues.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.agents.reasoning import ReasoningOutput
from app.agents.recommendation import RecommendationOption, RecommendationOutput

FAKE_REASONING_OUTPUT = ReasoningOutput(
    issue_explanations=[],
    cross_issue_notes="",
    uncertainty_notes="",
    summary="(mock_anthropic) Deterministic summary for E2E testing.",
)

FAKE_RECOMMENDATION_OUTPUT = RecommendationOutput(
    primary=RecommendationOption(
        action_type="follow_up",
        rationale="(mock_anthropic) An internal follow-up task is warranted for E2E testing.",
        cited_issue_types=[],
        confidence="High",
    ),
    secondary_options=[],
)


class _FakeMessages:
    def parse(self, **kwargs: Any) -> SimpleNamespace:
        output_format = kwargs.get("output_format")
        if output_format is ReasoningOutput:
            return SimpleNamespace(parsed_output=FAKE_REASONING_OUTPUT)
        if output_format is RecommendationOutput:
            return SimpleNamespace(parsed_output=FAKE_RECOMMENDATION_OUTPUT)
        raise AssertionError(f"FakeAnthropicClient: unexpected output_format {output_format!r}")


class FakeAnthropicClient:
    """Duck-types the one surface both agents call: `.messages.parse(...)`."""

    def __init__(self) -> None:
        self.messages = _FakeMessages()
