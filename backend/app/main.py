from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get(f"{settings.api_v1_prefix}/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
