import enum


class StateType(str, enum.Enum):
    TRIAGE = "triage"
    BACKLOG = "backlog"
    UNSTARTED = "unstarted"
    STARTED = "started"
    COMPLETED = "completed"
    CANCELED = "canceled"

class ProjectState(str, enum.Enum):
    PLANNED = "planned"
    STARTED = "started"
    PAUSED = "paused"
    COMPLETED = "completed"
    CANCELED = "canceled"

class TeamRole(str, enum.Enum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"

class IssueType(str, enum.Enum):
    TASK = "task"
    REFERENCE = "reference"
    IDEA = "idea"

class AuditAction(str, enum.Enum):
    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"

class RuleTrigger(str, enum.Enum):
    ISSUE_CREATED = "issue.created"
    ISSUE_STATE_CHANGED = "issue.state_changed"
    ISSUE_ASSIGNED = "issue.assigned"
    ISSUE_UPDATED = "issue.updated"
    ISSUE_COMMENT_ADDED = "issue.comment_added"
    PROJECT_STATE_CHANGED = "project.state_changed"

class FragmentType(str, enum.Enum):
    PERSON = "person"
    PLACE = "place"
    CREDENTIAL = "credential"
    MEMORY = "memory"
    IDEA = "idea"
    RESOURCE = "resource"
    JOURNAL = "journal"
