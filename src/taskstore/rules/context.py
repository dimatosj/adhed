from dataclasses import dataclass, field
from typing import Any


@dataclass
class RuleContext:
    issue: dict = field(default_factory=dict)
    project: dict = field(default_factory=dict)
    current_user: str = ""
    from_state: str = ""
    from_state_type: str = ""
    to_state: str = ""
    to_state_type: str = ""
    old_assignee: str | None = None
    new_assignee: str | None = None
    changed_fields: list[str] = field(default_factory=list)
    comment: dict = field(default_factory=dict)

    def resolve_field(self, field_name: str) -> Any:
        # Direct trigger context fields
        if field_name in ("from_state", "from_state_type", "to_state", "to_state_type"):
            return getattr(self, field_name)
        if field_name == "current_user":
            return self.current_user
        return self.issue.get(field_name)

    def resolve_value(self, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        if value == "$current_user":
            return self.current_user
        if value.startswith("$current."):
            return self.issue.get(value[len("$current."):])
        return value
