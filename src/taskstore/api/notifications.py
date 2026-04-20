import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_db, get_team as get_authed_team
from taskstore.models.notification import Notification
from taskstore.models.team import Team
from taskstore.schemas.common import Envelope, Meta
from taskstore.schemas.notification import NotificationResponse

router = APIRouter(tags=["notifications"])


@router.get(
    "/api/v1/teams/{team_id}/notifications",
    response_model=Envelope[list[NotificationResponse]],
)
async def list_notifications_endpoint(
    team_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
    user_id: uuid.UUID | None = Query(None),
):
    if authed_team.id != team_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    query = (
        select(Notification)
        .where(Notification.team_id == team_id, Notification.read.is_(False))
    )
    if user_id is not None:
        query = query.where(Notification.user_id == user_id)
    query = query.order_by(Notification.created_at.desc())

    result = await db.execute(query)
    notifications = list(result.scalars().all())
    return Envelope(
        data=[NotificationResponse.model_validate(n) for n in notifications],
        meta=Meta(total=len(notifications)),
    )


@router.post(
    "/api/v1/notifications/{notification_id}/read",
    response_model=Envelope[NotificationResponse],
)
async def mark_notification_read_endpoint(
    notification_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id)
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=404, detail="Notification not found")
    if notification.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")

    notification.read = True
    await db.commit()
    await db.refresh(notification)
    return Envelope(data=NotificationResponse.model_validate(notification))


@router.post(
    "/api/v1/teams/{team_id}/notifications/read-all",
    status_code=200,
)
async def mark_all_read_endpoint(
    team_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    if authed_team.id != team_id:
        raise HTTPException(status_code=403, detail="Forbidden")

    await db.execute(
        update(Notification)
        .where(Notification.team_id == team_id, Notification.read.is_(False))
        .values(read=True)
    )
    await db.commit()
    return Envelope(data={"marked_all_read": True})
