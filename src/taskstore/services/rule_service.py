import uuid

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.models.rule import Rule
from taskstore.rules.actions import validate_actions
from taskstore.schemas.rule import RuleCreate, RuleUpdate


async def create_rule(db: AsyncSession, team_id: uuid.UUID, data: RuleCreate) -> Rule:
    actions = data.actions
    if isinstance(actions, dict):
        actions = [actions]

    try:
        validate_actions(actions)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    rule = Rule(
        team_id=team_id,
        name=data.name,
        description=data.description,
        trigger=data.trigger,
        conditions=data.conditions,
        actions=actions,
        priority=data.priority,
        enabled=data.enabled,
    )
    db.add(rule)
    await db.flush()
    await db.commit()
    await db.refresh(rule)
    return rule


async def list_rules(db: AsyncSession, team_id: uuid.UUID) -> list[Rule]:
    result = await db.execute(
        select(Rule)
        .where(Rule.team_id == team_id)
        .order_by(Rule.priority.asc(), Rule.created_at.asc())
    )
    return list(result.scalars().all())


async def get_rule(db: AsyncSession, rule_id: uuid.UUID) -> Rule:
    result = await db.execute(select(Rule).where(Rule.id == rule_id))
    rule = result.scalar_one_or_none()
    if not rule:
        raise HTTPException(status_code=404, detail="Rule not found")
    return rule


async def update_rule(db: AsyncSession, rule_id: uuid.UUID, data: RuleUpdate) -> Rule:
    rule = await get_rule(db, rule_id)
    update_data = data.model_dump(exclude_unset=True)

    # Normalise actions to list
    if "actions" in update_data and isinstance(update_data["actions"], dict):
        update_data["actions"] = [update_data["actions"]]

    if "actions" in update_data:
        try:
            validate_actions(update_data["actions"])
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    for field, value in update_data.items():
        setattr(rule, field, value)

    await db.commit()
    await db.refresh(rule)
    return rule


async def delete_rule(db: AsyncSession, rule_id: uuid.UUID) -> None:
    rule = await get_rule(db, rule_id)
    await db.delete(rule)
    await db.commit()
