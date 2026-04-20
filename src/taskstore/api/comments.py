import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_current_user, get_db, get_team as get_authed_team
from taskstore.models.team import Team
from taskstore.models.user import User
from taskstore.schemas.comment import CommentCreate, CommentResponse
from taskstore.schemas.common import Envelope, Meta
from taskstore.services.comment_service import create_comment, list_comments
from taskstore.services.issue_service import get_issue_raw

router = APIRouter(tags=["comments"])


@router.post(
    "/api/v1/issues/{issue_id}/comments",
    response_model=Envelope[CommentResponse],
    status_code=201,
)
async def create_comment_endpoint(
    issue_id: uuid.UUID,
    data: CommentCreate,
    authed_team: Team = Depends(get_authed_team),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    issue = await get_issue_raw(db, issue_id)
    if issue.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    comment = await create_comment(db, issue_id, user.id, data)
    return Envelope(data=comment)


@router.get(
    "/api/v1/issues/{issue_id}/comments",
    response_model=Envelope[list[CommentResponse]],
)
async def list_comments_endpoint(
    issue_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    issue = await get_issue_raw(db, issue_id)
    if issue.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    comments = await list_comments(db, issue_id)
    return Envelope(data=comments, meta=Meta(total=len(comments)))
