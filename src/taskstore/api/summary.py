import uuid

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_db, get_team as get_authed_team, verified_team
from taskstore.models.team import Team
from taskstore.schemas.common import Envelope
from taskstore.schemas.summary import SummaryData
from taskstore.services.summary_service import get_summary

router = APIRouter(tags=["summary"])


@router.get(
    "/api/v1/teams/{team_id}/summary",
    response_model=Envelope[SummaryData],
)
async def get_summary_endpoint(
    team_id: uuid.UUID,
    authed_team: Team = Depends(verified_team),
    db: AsyncSession = Depends(get_db),
    x_user_id: str | None = Header(None, alias="X-User-Id"),
):

    user_id = None
    if x_user_id:
        try:
            user_id = uuid.UUID(x_user_id)
        except ValueError:
            pass

    summary = await get_summary(db, team_id, user_id=user_id)
    return Envelope(data=summary)
