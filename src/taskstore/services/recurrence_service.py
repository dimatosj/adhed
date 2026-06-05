import re
import uuid
from datetime import datetime, timedelta

from croniter import croniter
from dateutil.relativedelta import relativedelta
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.engine.audit import record_audit
from taskstore.models.enums import AuditAction, ScheduleType
from taskstore.models.recurrence import Recurrence
from taskstore.schemas.recurrence import RecurrenceCreate, RecurrenceResponse, RecurrenceUpdate
from taskstore.utils.time import now_utc

INTERVAL_RE = re.compile(r"^(\d+)([dwm])$")


def parse_interval(expr: str) -> timedelta | relativedelta:
    m = INTERVAL_RE.match(expr)
    if not m:
        raise ValueError(f"Invalid interval expression: {expr}. Use Nd, Nw, or Nm.")
    n, unit = int(m.group(1)), m.group(2)
    if unit == "d":
        return timedelta(days=n)
    if unit == "w":
        return timedelta(weeks=n)
    if unit == "m":
        return relativedelta(months=n)
    raise ValueError(f"Unknown unit: {unit}")


def compute_next_due(schedule_type: ScheduleType, schedule_expr: str, after: datetime) -> datetime:
    naive = after.replace(tzinfo=None) if after.tzinfo else after
    if schedule_type == ScheduleType.CRON:
        cron = croniter(schedule_expr, naive)
        return cron.get_next(datetime)
    else:
        delta = parse_interval(schedule_expr)
        return naive + delta


def validate_schedule(schedule_type: ScheduleType, schedule_expr: str) -> None:
    if schedule_type == ScheduleType.CRON:
        if not croniter.is_valid(schedule_expr):
            raise HTTPException(status_code=422, detail=f"Invalid cron expression: {schedule_expr}")
    else:
        if not INTERVAL_RE.match(schedule_expr):
            raise HTTPException(
                status_code=422,
                detail=f"Invalid interval expression: {schedule_expr}. Use Nd, Nw, or Nm.",
            )


def render_title(template: str, due_date: datetime) -> str:
    return template.replace("{date}", due_date.strftime("%Y-%m-%d"))


async def create_recurrence(
    db: AsyncSession,
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    data: RecurrenceCreate,
) -> RecurrenceResponse:
    validate_schedule(data.schedule_type, data.schedule_expr)

    next_due = data.next_due_at
    if next_due is None:
        next_due = compute_next_due(data.schedule_type, data.schedule_expr, now_utc())
    elif next_due.tzinfo:
        next_due = next_due.replace(tzinfo=None)

    recurrence = Recurrence(
        team_id=team_id,
        created_by=user_id,
        title_template=data.title_template,
        description_template=data.description_template,
        issue_defaults=data.issue_defaults,
        schedule_type=data.schedule_type,
        schedule_expr=data.schedule_expr,
        next_due_at=next_due,
    )
    db.add(recurrence)
    await db.flush()
    await record_audit(db, team_id, "recurrence", recurrence.id, AuditAction.CREATE, user_id)
    await db.commit()
    await db.refresh(recurrence)
    return RecurrenceResponse.model_validate(recurrence)


async def list_recurrences(
    db: AsyncSession,
    team_id: uuid.UUID,
    *,
    active: bool | None = None,
    schedule_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[RecurrenceResponse], int]:
    if limit > 200:
        limit = 200

    query = select(Recurrence).where(Recurrence.team_id == team_id)
    count_query = select(func.count()).select_from(Recurrence).where(Recurrence.team_id == team_id)

    if active is not None:
        query = query.where(Recurrence.active == active)
        count_query = count_query.where(Recurrence.active == active)

    if schedule_type:
        query = query.where(Recurrence.schedule_type == schedule_type)
        count_query = count_query.where(Recurrence.schedule_type == schedule_type)

    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    query = query.order_by(Recurrence.next_due_at.asc()).offset(offset).limit(limit)
    result = await db.execute(query)
    recurrences = list(result.scalars().all())

    return [RecurrenceResponse.model_validate(r) for r in recurrences], total


async def get_recurrence(db: AsyncSession, recurrence_id: uuid.UUID) -> RecurrenceResponse:
    result = await db.execute(select(Recurrence).where(Recurrence.id == recurrence_id))
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recurrence not found")
    return RecurrenceResponse.model_validate(rec)


async def get_recurrence_raw(db: AsyncSession, recurrence_id: uuid.UUID) -> Recurrence:
    result = await db.execute(select(Recurrence).where(Recurrence.id == recurrence_id))
    rec = result.scalar_one_or_none()
    if not rec:
        raise HTTPException(status_code=404, detail="Recurrence not found")
    return rec


async def update_recurrence(
    db: AsyncSession,
    recurrence_id: uuid.UUID,
    data: RecurrenceUpdate,
    user_id: uuid.UUID,
) -> RecurrenceResponse:
    rec = await get_recurrence_raw(db, recurrence_id)
    update_data = data.model_dump(exclude_unset=True)

    new_type = update_data.get("schedule_type", rec.schedule_type)
    new_expr = update_data.get("schedule_expr", rec.schedule_expr)

    if "schedule_type" in update_data or "schedule_expr" in update_data:
        validate_schedule(new_type, new_expr)
        if "next_due_at" not in update_data:
            update_data["next_due_at"] = compute_next_due(new_type, new_expr, now_utc())

    for field, value in update_data.items():
        setattr(rec, field, value)

    await db.flush()
    await record_audit(db, rec.team_id, "recurrence", rec.id, AuditAction.UPDATE, user_id)
    await db.commit()
    await db.refresh(rec)
    return RecurrenceResponse.model_validate(rec)


async def delete_recurrence(
    db: AsyncSession,
    recurrence_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    rec = await get_recurrence_raw(db, recurrence_id)
    await record_audit(db, rec.team_id, "recurrence", rec.id, AuditAction.DELETE, user_id)
    await db.delete(rec)
    await db.commit()
