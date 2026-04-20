from sqlalchemy.ext.asyncio import AsyncSession

from taskstore.models.audit import AuditEntry
from taskstore.models.enums import AuditAction


async def record_audit(
    db: AsyncSession,
    team_id,
    entity_type: str,
    entity_id,
    action: AuditAction,
    user_id,
    changes: dict | None = None,
) -> AuditEntry:
    entry = AuditEntry(
        team_id=team_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        user_id=user_id,
        changes=changes or {},
    )
    db.add(entry)
    return entry


def compute_diff(old: dict, new: dict, fields: list[str]) -> dict:
    changes = {}
    for field in fields:
        old_val = old.get(field)
        new_val = new.get(field)
        if old_val != new_val:
            changes[field] = {"old": old_val, "new": new_val}
    return changes
