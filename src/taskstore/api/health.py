"""Health endpoint — liveness + readiness via a trivial DB query."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_db

router = APIRouter(tags=["health"])


@router.get("/api/v1/health")
async def health(db: AsyncSession = Depends(get_db)):
    """Liveness + readiness check.

    Confirms the DB is reachable by running a trivial SELECT. Returns
    503 if the DB is unreachable so container orchestrators can
    restart or drain traffic.
    """
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"database unreachable: {exc}")
    return {"status": "ok"}
