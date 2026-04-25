import uuid

from fastapi import HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.engine.audit import record_audit
from taskstore.models.enums import AuditAction, SessionState
from taskstore.models.session import Session
from taskstore.schemas.session import SessionCreate, SessionResponse, SessionUpdate
from taskstore.utils.time import now_utc


async def create_session(
    db: AsyncSession,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    data: SessionCreate,
) -> SessionResponse:
    session = Session(
        team_id=team_id,
        created_by=user_id,
        type=data.type,
        payload=data.payload,
    )
    db.add(session)
    await db.flush()
    await record_audit(db, team_id, "session", session.id, AuditAction.CREATE, user_id)
    await db.commit()
    await db.refresh(session)
    return SessionResponse.model_validate(session)


async def list_sessions(
    db: AsyncSession,
    team_id: uuid.UUID,
    *,
    session_type: str | None = None,
    state: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[SessionResponse], int]:
    if limit > 200:
        limit = 200

    query = select(Session).where(Session.team_id == team_id)
    count_query = select(func.count()).select_from(Session).where(Session.team_id == team_id)

    if session_type:
        query = query.where(Session.type == session_type)
        count_query = count_query.where(Session.type == session_type)

    if state:
        query = query.where(Session.state == state)
        count_query = count_query.where(Session.state == state)

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    query = query.order_by(Session.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    sessions = list(result.scalars().all())

    return [SessionResponse.model_validate(s) for s in sessions], total


async def get_session(db: AsyncSession, session_id: uuid.UUID) -> SessionResponse:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return SessionResponse.model_validate(session)


async def get_session_raw(db: AsyncSession, session_id: uuid.UUID) -> Session:
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


async def update_session(
    db: AsyncSession,
    session_id: uuid.UUID,
    data: SessionUpdate,
    user_id: uuid.UUID,
) -> SessionResponse:
    session = await get_session_raw(db, session_id)
    update_data = data.model_dump(exclude_unset=True)

    if "state" in update_data:
        new_state = update_data["state"]
        if new_state in (SessionState.COMPLETED, SessionState.ABANDONED) and session.completed_at is None:
            session.completed_at = now_utc()

    for field, value in update_data.items():
        setattr(session, field, value)

    await db.flush()
    await record_audit(db, session.team_id, "session", session.id, AuditAction.UPDATE, user_id)
    await db.commit()
    await db.refresh(session)
    return SessionResponse.model_validate(session)
