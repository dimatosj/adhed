import logging
import uuid

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.engine.audit import record_audit
from taskstore.models.enums import AuditAction
from taskstore.models.fragment import Fragment
from taskstore.schemas.fragment import FragmentCreate, FragmentResponse, FragmentUpdate, TopicCount

logger = logging.getLogger(__name__)

FRAGMENT_SORT_COLUMNS = frozenset({"created_at", "updated_at", "type"})


def _to_response(frag: Fragment) -> FragmentResponse:
    return FragmentResponse(
        id=frag.id,
        team_id=frag.team_id,
        text=frag.text,
        type=frag.type,
        summary=frag.summary,
        subtype=frag.subtype,
        source_url=frag.source_url,
        topics=frag.topics,
        domains=frag.domains,
        entities=frag.entities,
        source=frag.source,
        created_by=frag.created_by,
        created_at=frag.created_at,
        updated_at=frag.updated_at,
    )


async def create_fragment(
    db: AsyncSession, team_id: uuid.UUID, user_id: uuid.UUID, data: FragmentCreate,
) -> FragmentResponse:
    frag = Fragment(
        team_id=team_id,
        text=data.text,
        type=data.type,
        summary=data.summary,
        subtype=data.subtype,
        source_url=data.source_url,
        topics=data.topics,
        domains=data.domains,
        entities=data.entities,
        source=data.source.model_dump() if data.source else None,
        created_by=user_id,
    )
    db.add(frag)
    await db.flush()
    await record_audit(db, team_id, "fragment", frag.id, AuditAction.CREATE, user_id)
    await db.commit()
    await db.refresh(frag)
    return _to_response(frag)


async def get_fragment(db: AsyncSession, fragment_id: uuid.UUID) -> FragmentResponse:
    result = await db.execute(select(Fragment).where(Fragment.id == fragment_id))
    frag = result.scalar_one_or_none()
    if not frag:
        raise HTTPException(status_code=404, detail="Fragment not found")
    return _to_response(frag)


async def update_fragment(
    db: AsyncSession, fragment_id: uuid.UUID, user_id: uuid.UUID, data: FragmentUpdate,
) -> FragmentResponse:
    result = await db.execute(select(Fragment).where(Fragment.id == fragment_id))
    frag = result.scalar_one_or_none()
    if not frag:
        raise HTTPException(status_code=404, detail="Fragment not found")

    changes = {}
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "source" and value is not None:
            value = value if isinstance(value, dict) else value.model_dump()
        old = getattr(frag, field)
        if old != value:
            changes[field] = {"old": str(old), "new": str(value)}
        setattr(frag, field, value)

    if changes:
        await record_audit(db, frag.team_id, "fragment", frag.id, AuditAction.UPDATE, user_id, changes)
    await db.commit()
    await db.refresh(frag)
    return _to_response(frag)


async def delete_fragment(
    db: AsyncSession, fragment_id: uuid.UUID, user_id: uuid.UUID,
) -> None:
    result = await db.execute(select(Fragment).where(Fragment.id == fragment_id))
    frag = result.scalar_one_or_none()
    if not frag:
        raise HTTPException(status_code=404, detail="Fragment not found")
    await record_audit(db, frag.team_id, "fragment", frag.id, AuditAction.DELETE, user_id)
    await db.delete(frag)
    await db.commit()


async def list_fragments(
    db: AsyncSession,
    team_id: uuid.UUID,
    fragment_type: list[str] | None = None,
    subtype: list[str] | None = None,
    domain: list[str] | None = None,
    topic: str | None = None,
    project_id: str | None = None,
    issue_id: str | None = None,
    entity_name: str | None = None,
    title_search: str | None = None,
    created_by: uuid.UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    sort: str = "created_at",
    order: str = "desc",
) -> tuple[list[FragmentResponse], int]:
    query = select(Fragment).where(Fragment.team_id == team_id)

    if fragment_type:
        query = query.where(Fragment.type.in_(fragment_type))

    if subtype:
        query = query.where(Fragment.subtype.in_(subtype))

    if domain:
        for d in domain:
            query = query.where(Fragment.domains.any(d))

    if topic:
        query = query.where(Fragment.topics.any(topic))

    if project_id:
        query = query.where(
            Fragment.source["linked_project_id"].astext == project_id
        )

    if issue_id:
        query = query.where(
            Fragment.source["linked_issue_id"].astext == issue_id
        )

    if entity_name:
        escaped = entity_name.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        query = query.where(
            Fragment.entities.cast(str).ilike(f"%{escaped}%")
        )

    if title_search:
        query = query.where(Fragment.text_search.match(title_search))

    if created_by:
        query = query.where(Fragment.created_by == created_by)

    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()

    sort_col = sort if sort in FRAGMENT_SORT_COLUMNS else "created_at"
    col = getattr(Fragment, sort_col)
    if order == "asc":
        query = query.order_by(col.asc())
    else:
        query = query.order_by(col.desc())

    query = query.limit(min(limit, 200)).offset(offset)
    result = await db.execute(query)
    fragments = list(result.scalars().all())

    return [_to_response(f) for f in fragments], total


async def list_topics(db: AsyncSession, team_id: uuid.UUID) -> list[TopicCount]:
    result = await db.execute(
        text("""
            SELECT topic, count(*) as cnt
            FROM fragments, unnest(topics) AS topic
            WHERE team_id = :team_id
            GROUP BY topic
            ORDER BY cnt DESC
        """),
        {"team_id": str(team_id)},
    )
    return [TopicCount(topic=row[0], count=row[1]) for row in result.all()]
