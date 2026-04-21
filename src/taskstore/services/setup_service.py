import uuid

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.models.label import Label
from taskstore.models.team import Team
from taskstore.schemas.label import LabelCreate
from taskstore.schemas.setup import SetupRequest, SetupResponse
from taskstore.schemas.team import TeamCreate
from taskstore.schemas.user import UserCreate
from taskstore.services import team_service, user_service

DEFAULT_LABELS = [
    "health",
    "home",
    "personal",
    "family",
    "work",
    "finances",
    "social",
    "@home",
    "@errands",
    "@computer",
    "@phone",
    "someday-maybe",
    "waiting-for",
    "commitment",
]


async def run_setup(db: AsyncSession, data: SetupRequest) -> SetupResponse:
    # Check if any team already exists
    count_result = await db.execute(select(func.count()).select_from(Team))
    count = count_result.scalar()
    if count > 0:
        raise HTTPException(status_code=409, detail="Already set up")

    # Create team
    team, plaintext_api_key = await team_service.create_team(
        db, TeamCreate(name=data.team_name, key=data.team_key)
    )

    # Create user (first member becomes owner automatically)
    user, _role = await user_service.create_or_add_user(
        db, team.id, UserCreate(name=data.user_name, email=data.user_email)
    )

    # Default labels are opt-in — they're opinionated GTD-style and not
    # suitable for every team. Set include_default_labels=true in the
    # setup request to seed them.
    if data.include_default_labels:
        for label_name in DEFAULT_LABELS:
            label = Label(team_id=team.id, name=label_name)
            db.add(label)
    await db.commit()

    return SetupResponse(
        team_id=team.id,
        team_name=team.name,
        team_key=team.key,
        api_key=plaintext_api_key,
        user_id=user.id,
        user_name=user.name,
        user_email=user.email,
    )
