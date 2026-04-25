# Re-export every ORM class so `import taskstore.models` registers
# them with SQLAlchemy's metadata. The noqa lines suppress ruff's
# unused-import warnings — these imports ARE used, just indirectly.
from taskstore.models.audit import AuditEntry  # noqa: F401
from taskstore.models.comment import Comment  # noqa: F401
from taskstore.models.enums import (  # noqa: F401
    AuditAction,
    FragmentType,
    IssueType,
    ProjectState,
    RuleTrigger,
    StateType,
    TeamRole,
)
from taskstore.models.fragment import Fragment  # noqa: F401
from taskstore.models.fragment_link import FragmentLink  # noqa: F401
from taskstore.models.issue import Issue, IssueLabel  # noqa: F401
from taskstore.models.label import Label  # noqa: F401
from taskstore.models.notification import Notification  # noqa: F401
from taskstore.models.project import Project  # noqa: F401
from taskstore.models.rule import Rule  # noqa: F401
from taskstore.models.team import Team  # noqa: F401
from taskstore.models.user import TeamMembership, User  # noqa: F401
from taskstore.models.workflow_state import WorkflowState  # noqa: F401
