from fastapi import Depends, FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_db
from taskstore.api.setup import router as setup_router
from taskstore.api.teams import router as teams_router
from taskstore.api.states import router as states_router
from taskstore.api.users import router as users_router
from taskstore.api.labels import router as labels_router
from taskstore.api.issues import router as issues_router
from taskstore.api.audit import router as audit_router
from taskstore.api.rules import router as rules_router
from taskstore.api.projects import router as projects_router
from taskstore.api.comments import router as comments_router
from taskstore.api.notifications import router as notifications_router
from taskstore.api.summary import router as summary_router

app = FastAPI(title="ADHED", version="0.1.0", description="Headless task management for agents and claws")

app.include_router(setup_router)
app.include_router(teams_router)
app.include_router(states_router)
app.include_router(users_router)
app.include_router(labels_router)
app.include_router(issues_router)
app.include_router(audit_router)
app.include_router(rules_router)
app.include_router(projects_router)
app.include_router(comments_router)
app.include_router(notifications_router)
app.include_router(summary_router)


@app.get("/api/v1/health")
async def health(db: AsyncSession = Depends(get_db)):
    """Liveness + readiness check.

    Confirms the DB is reachable by running a trivial SELECT. Returns
    degraded (503) if the DB is unreachable so container orchestrators
    can restart or drain traffic.
    """
    try:
        await db.execute(text("SELECT 1"))
    except Exception as exc:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail=f"database unreachable: {exc}")
    return {"status": "ok"}
