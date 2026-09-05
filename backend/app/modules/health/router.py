"""Health check endpoint."""

from fastapi import APIRouter

from app.core.response import ApiResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> ApiResponse:
    """Health check endpoint."""
    return ApiResponse.success(data={"status": "ok"})
