import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.engine.audit import record_audit
from taskstore.models.enums import AuditAction
from taskstore.models.fragment import Fragment
from taskstore.models.fragment_link import FragmentLink
from taskstore.models.issue import Issue
from taskstore.models.project import Project
from taskstore.models.session import Session
from taskstore.schemas.fragment_link import FragmentLinkResponse

VALID_TARGET_TYPES = frozenset({"fragment", "issue", "project", "session"})

TARGET_TABLE = {
    "fragment": Fragment,
    "issue": Issue,
    "project": Project,
    "session": Session,
}


async def _validate_source(db: AsyncSession, fragment_id: uuid.UUID, team_id: uuid.UUID) -> Fragment:
    result = await db.execute(select(Fragment).where(Fragment.id == fragment_id))
    frag = result.scalar_one_or_none()
    if not frag:
        raise HTTPException(status_code=404, detail="Source fragment not found")
    if frag.team_id != team_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    return frag


async def _validate_target(db: AsyncSession, target_type: str, target_id: uuid.UUID) -> None:
    if target_type not in VALID_TARGET_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid target_type: {target_type}")
    model = TARGET_TABLE[target_type]
    result = await db.execute(select(model).where(model.id == target_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail=f"Target {target_type} not found")


def _hydrate_fragment(frag: Fragment) -> tuple[str, dict]:
    return (frag.summary or frag.text[:80]), {"fragment_type": frag.type.value if frag.type else None}


def _hydrate_issue(issue: Issue) -> tuple[str, dict]:
    return issue.title, {"state_id": str(issue.state_id), "priority": issue.priority}


def _hydrate_project(project: Project) -> tuple[str, dict]:
    return project.name, {"state": project.state.value if project.state else None}


def _hydrate_session(session: Session) -> tuple[str, dict]:
    return f"{session.type.value} session", {"state": session.state.value, "type": session.type.value}


HYDRATORS = {
    "fragment": (Fragment, _hydrate_fragment),
    "issue": (Issue, _hydrate_issue),
    "project": (Project, _hydrate_project),
    "session": (Session, _hydrate_session),
}


async def _hydrate_links(
    db: AsyncSession,
    links: list[FragmentLink],
    directions: dict[uuid.UUID, str],
) -> list[FragmentLinkResponse]:
    grouped: dict[str, list[FragmentLink]] = {}
    for link in links:
        grouped.setdefault(link.target_type, []).append(link)

    hydrated: dict[uuid.UUID, tuple[str, dict]] = {}
    for target_type, type_links in grouped.items():
        model, hydrator = HYDRATORS[target_type]
        ids = [link.target_id for link in type_links]
        result = await db.execute(select(model).where(model.id.in_(ids)))
        entities = {e.id: e for e in result.scalars().all()}
        for link in type_links:
            entity = entities.get(link.target_id)
            if entity:
                hydrated[link.id] = hydrator(entity)

    responses = []
    for link in links:
        summary, detail = hydrated.get(link.id, ("(deleted)", {}))
        responses.append(FragmentLinkResponse(
            id=link.id,
            direction=directions[link.id],
            target_type=link.target_type,
            target_id=link.target_id,
            summary=summary,
            detail=detail,
            created_at=link.created_at,
        ))
    return responses


async def create_link(
    db: AsyncSession,
    fragment_id: uuid.UUID,
    target_type: str,
    target_id: uuid.UUID,
    user_id: uuid.UUID,
    team_id: uuid.UUID,
) -> FragmentLinkResponse:
    source = await _validate_source(db, fragment_id, team_id)
    await _validate_target(db, target_type, target_id)

    link = FragmentLink(
        fragment_id=fragment_id,
        target_type=target_type,
        target_id=target_id,
        created_by=user_id,
    )
    db.add(link)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Link already exists")

    await record_audit(db, source.team_id, "fragment_link", link.id, AuditAction.CREATE, user_id)
    await db.commit()
    await db.refresh(link)

    responses = await _hydrate_links(db, [link], {link.id: "outgoing"})
    return responses[0]


async def get_links(
    db: AsyncSession,
    fragment_id: uuid.UUID,
    team_id: uuid.UUID,
    target_type_filter: str | None = None,
) -> list[FragmentLinkResponse]:
    await _validate_source(db, fragment_id, team_id)

    outgoing_q = select(FragmentLink).where(FragmentLink.fragment_id == fragment_id)
    if target_type_filter:
        outgoing_q = outgoing_q.where(FragmentLink.target_type == target_type_filter)
    outgoing_result = await db.execute(outgoing_q)
    outgoing = list(outgoing_result.scalars().all())

    incoming_q = (
        select(FragmentLink)
        .where(FragmentLink.target_type == "fragment")
        .where(FragmentLink.target_id == fragment_id)
    )
    if target_type_filter and target_type_filter != "fragment":
        incoming = []
    else:
        incoming_result = await db.execute(incoming_q)
        incoming = list(incoming_result.scalars().all())

    directions: dict[uuid.UUID, str] = {}
    for link in outgoing:
        directions[link.id] = "outgoing"

    incoming_remapped = []
    for link in incoming:
        directions[link.id] = "incoming"
        incoming_remapped.append(link)

    all_links = outgoing + incoming_remapped

    for link in incoming_remapped:
        link.target_id = link.fragment_id
        link.target_type = "fragment"

    return await _hydrate_links(db, all_links, directions)


async def delete_link(
    db: AsyncSession,
    fragment_id: uuid.UUID,
    link_id: uuid.UUID,
    user_id: uuid.UUID,
    team_id: uuid.UUID,
) -> None:
    source = await _validate_source(db, fragment_id, team_id)
    result = await db.execute(
        select(FragmentLink).where(FragmentLink.id == link_id, FragmentLink.fragment_id == fragment_id)
    )
    link = result.scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")

    await record_audit(db, source.team_id, "fragment_link", link.id, AuditAction.DELETE, user_id)
    await db.delete(link)
    await db.commit()
