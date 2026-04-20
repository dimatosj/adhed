import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.models.comment import Comment
from taskstore.schemas.comment import CommentCreate, CommentResponse


async def create_comment(
    db: AsyncSession,
    issue_id: uuid.UUID,
    user_id: uuid.UUID,
    data: CommentCreate,
) -> CommentResponse:
    comment = Comment(
        issue_id=issue_id,
        user_id=user_id,
        body=data.body,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return CommentResponse.model_validate(comment)


async def list_comments(
    db: AsyncSession, issue_id: uuid.UUID
) -> list[CommentResponse]:
    result = await db.execute(
        select(Comment)
        .where(Comment.issue_id == issue_id)
        .order_by(Comment.created_at.asc())
    )
    comments = list(result.scalars().all())
    return [CommentResponse.model_validate(c) for c in comments]
