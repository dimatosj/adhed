import asyncio
import logging
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import taskstore.models  # noqa: F401 — register all models
from taskstore.engine.audit import record_audit
from taskstore.logging_config import configure_logging
from taskstore.models.enums import AuditAction, StateType
from taskstore.models.issue import Issue
from taskstore.models.recurrence import Recurrence
from taskstore.models.workflow_state import WorkflowState
from taskstore.services.recurrence_service import compute_next_due, render_title
from taskstore.utils.time import now_utc

configure_logging(
    level=os.environ.get("LOG_LEVEL", "info"),
    fmt=os.environ.get("LOG_FORMAT", "plain"),
)
logger = logging.getLogger("taskstore.scheduler")

POLL_INTERVAL = int(os.environ.get("SCHEDULER_POLL_INTERVAL", "60"))

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://adhed:adhed@localhost:5433/adhed",
)


async def get_default_backlog_state(db: AsyncSession, team_id) -> WorkflowState | None:
    result = await db.execute(
        select(WorkflowState)
        .where(WorkflowState.team_id == team_id, WorkflowState.type == StateType.BACKLOG)
        .order_by(WorkflowState.position)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def spawn_issue(db: AsyncSession, rec: Recurrence) -> Issue:
    title = render_title(rec.title_template, rec.next_due_at)

    state = await get_default_backlog_state(db, rec.team_id)
    if not state:
        raise RuntimeError(f"No backlog state for team {rec.team_id}")

    defaults = rec.issue_defaults or {}

    issue = Issue(
        team_id=rec.team_id,
        title=title,
        description=rec.description_template,
        priority=defaults.get("priority", 0),
        state_id=state.id,
        assignee_id=defaults.get("assignee_id"),
        project_id=defaults.get("project_id"),
        custom_fields=defaults.get("custom_fields"),
        created_by=rec.created_by,
    )
    db.add(issue)
    await db.flush()

    await record_audit(
        db,
        rec.team_id,
        "recurrence_spawn",
        issue.id,
        AuditAction.CREATE,
        rec.created_by,
        changes={"recurrence_id": str(rec.id)},
    )

    return issue


async def process_due_recurrences(session_factory: async_sessionmaker) -> int:
    now = now_utc()
    spawned = 0

    async with session_factory() as db:
        result = await db.execute(
            select(Recurrence).where(
                Recurrence.active == True,  # noqa: E712
                Recurrence.next_due_at <= now,
            )
        )
        due_recurrences = list(result.scalars().all())

    for rec in due_recurrences:
        try:
            async with session_factory() as db:
                result = await db.execute(select(Recurrence).where(Recurrence.id == rec.id))
                rec = result.scalar_one_or_none()
                if not rec or not rec.active or rec.next_due_at > now:
                    continue

                issue = await spawn_issue(db, rec)

                rec.last_spawned_at = now
                rec.last_spawned_issue_id = issue.id
                rec.next_due_at = compute_next_due(rec.schedule_type, rec.schedule_expr, now)

                while rec.next_due_at <= now:
                    rec.next_due_at = compute_next_due(
                        rec.schedule_type,
                        rec.schedule_expr,
                        rec.next_due_at,
                    )

                await db.commit()
                spawned += 1
                logger.info(
                    "spawned_issue",
                    extra={
                        "recurrence_id": str(rec.id),
                        "issue_id": str(issue.id),
                        "title": issue.title,
                        "next_due": rec.next_due_at.isoformat(),
                    },
                )
        except Exception:
            logger.exception("spawn_failed", extra={"recurrence_id": str(rec.id)})

    return spawned


async def run_scheduler():
    logger.info("scheduler_start", extra={"poll_interval": POLL_INTERVAL})

    engine = create_async_engine(DATABASE_URL, echo=False)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    try:
        while True:
            try:
                spawned = await process_due_recurrences(session_factory)
                if spawned:
                    logger.info("scheduler_tick", extra={"spawned": spawned})
            except Exception:
                logger.exception("scheduler_tick_error")
            await asyncio.sleep(POLL_INTERVAL)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_scheduler())
