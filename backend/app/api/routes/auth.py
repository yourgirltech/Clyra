from fastapi import APIRouter

router = APIRouter(tags=["auth"])


@router.get("/auth")
async def auth_placeholder() -> dict[str, str]:
    return {"status": "placeholder", "message": "Auth endpoints coming soon."}
