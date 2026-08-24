from fastapi import APIRouter

router = APIRouter(tags=["automations"])


@router.get("/automations")
async def automations_placeholder() -> dict[str, str]:
    return {"status": "placeholder", "message": "Automation endpoints coming soon."}
