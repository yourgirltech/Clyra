from fastapi import APIRouter

router = APIRouter(tags=["ai"])


@router.get("/ai")
async def ai_placeholder() -> dict[str, str]:
    return {"status": "placeholder", "message": "AI assistant endpoints coming soon."}
