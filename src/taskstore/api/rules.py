import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.api.deps import get_db, get_team as get_authed_team
from taskstore.models.team import Team
from taskstore.schemas.common import Envelope, Meta
from taskstore.schemas.rule import RuleCreate, RuleResponse, RuleUpdate
from taskstore.services.rule_service import (
    create_rule,
    delete_rule,
    get_rule,
    list_rules,
    update_rule,
)

router = APIRouter(tags=["rules"])


@router.post(
    "/api/v1/teams/{team_id}/rules",
    response_model=Envelope[RuleResponse],
    status_code=201,
)
async def create_rule_endpoint(
    team_id: uuid.UUID,
    data: RuleCreate,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    if authed_team.id != team_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    rule = await create_rule(db, team_id, data)
    return Envelope(data=RuleResponse.model_validate(rule))


@router.get(
    "/api/v1/teams/{team_id}/rules",
    response_model=Envelope[list[RuleResponse]],
)
async def list_rules_endpoint(
    team_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    if authed_team.id != team_id:
        raise HTTPException(status_code=403, detail="Forbidden")
    rules = await list_rules(db, team_id)
    return Envelope(
        data=[RuleResponse.model_validate(r) for r in rules],
        meta=Meta(total=len(rules)),
    )


@router.patch(
    "/api/v1/rules/{rule_id}",
    response_model=Envelope[RuleResponse],
)
async def update_rule_endpoint(
    rule_id: uuid.UUID,
    data: RuleUpdate,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    rule = await get_rule(db, rule_id)
    if rule.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    rule = await update_rule(db, rule_id, data)
    return Envelope(data=RuleResponse.model_validate(rule))


@router.delete(
    "/api/v1/rules/{rule_id}",
    status_code=204,
)
async def delete_rule_endpoint(
    rule_id: uuid.UUID,
    authed_team: Team = Depends(get_authed_team),
    db: AsyncSession = Depends(get_db),
):
    rule = await get_rule(db, rule_id)
    if rule.team_id != authed_team.id:
        raise HTTPException(status_code=403, detail="Forbidden")
    await delete_rule(db, rule_id)
