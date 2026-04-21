import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.engine.audit import record_audit
from taskstore.models.enums import AuditAction
from taskstore.models.label import Label
from taskstore.schemas.label import LabelCreate, LabelUpdate


async def create_label(
    db: AsyncSession,
    team_id: uuid.UUID,
    data: LabelCreate,
    user_id: uuid.UUID | None = None,
) -> Label:
    label = Label(team_id=team_id, **data.model_dump())
    db.add(label)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=409,
            detail=f"Label '{data.name}' already exists in this team",
        )
    if user_id is not None:
        await record_audit(db, team_id, "label", label.id, AuditAction.CREATE, user_id)
    await db.commit()
    await db.refresh(label)
    return label


async def list_labels(db: AsyncSession, team_id: uuid.UUID) -> list[Label]:
    result = await db.execute(
        select(Label)
        .where(Label.team_id == team_id)
        .order_by(Label.name)
    )
    return list(result.scalars().all())


async def get_label(db: AsyncSession, label_id: uuid.UUID) -> Label:
    result = await db.execute(select(Label).where(Label.id == label_id))
    label = result.scalar_one_or_none()
    if not label:
        raise HTTPException(status_code=404, detail="Label not found")
    return label


async def update_label(
    db: AsyncSession,
    label_id: uuid.UUID,
    data: LabelUpdate,
    user_id: uuid.UUID | None = None,
) -> Label:
    label = await get_label(db, label_id)
    if data.name is not None:
        label.name = data.name
    if data.color is not None:
        label.color = data.color
    if data.description is not None:
        label.description = data.description
    if user_id is not None:
        await record_audit(
            db, label.team_id, "label", label.id, AuditAction.UPDATE, user_id
        )
    await db.commit()
    await db.refresh(label)
    return label


async def delete_label(
    db: AsyncSession, label_id: uuid.UUID, user_id: uuid.UUID | None = None
) -> None:
    label = await get_label(db, label_id)
    if user_id is not None:
        await record_audit(
            db, label.team_id, "label", label.id, AuditAction.DELETE, user_id
        )
    await db.delete(label)
    await db.commit()
