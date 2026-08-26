import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.assistant import AssistantFailure, AssistantTurn, run_assistant
from app.api.routes.claims import get_current_clinic
from app.db.database import get_db

router = APIRouter(tags=["ai"])
logger = logging.getLogger("clyra.assistant")


@router.get("/ai")
async def ai_placeholder() -> dict[str, str]:
    return {"status": "placeholder", "message": "AI assistant endpoints coming soon."}


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class AssistantRequest(BaseModel):
    message: str
    history: list[ChatMessage] = []


class AssistantToolCall(BaseModel):
    tool: str
    input: dict
    result: dict


class AssistantResponse(BaseModel):
    reply: str
    tool_calls: list[AssistantToolCall] = []
    ok: bool = True


@router.post("/ai/assistant", response_model=AssistantResponse)
def ask_assistant(
    body: AssistantRequest,
    clinic_id: int = Depends(get_current_clinic),
    db: Session = Depends(get_db),
) -> AssistantResponse:
    history = [{"role": m.role, "content": m.content} for m in body.history]
    result = run_assistant(db, clinic_id, body.message, history)

    if isinstance(result, AssistantFailure):
        # 07-assistant-agent never escalates to 06 and never crashes the
        # endpoint — a failure is still a plain chat reply, per spec.
        logger.warning("assistant turn failed: reason=%s detail=%s", result.reason, result.detail)
        if result.reason == "ungrounded_output":
            reply = "I wasn't able to give a fully grounded answer to that — could you ask about a specific claim, or rephrase?"
        else:
            reply = "I wasn't able to reach the AI service just now — please try again in a moment."
        return AssistantResponse(reply=reply, tool_calls=[], ok=False)

    return AssistantResponse(
        reply=result.reply,
        tool_calls=[AssistantToolCall(tool=c["tool"], input=c["input"], result=c["result"]) for c in result.tool_calls],
        ok=True,
    )
