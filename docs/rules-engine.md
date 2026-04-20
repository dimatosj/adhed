# Rules Engine

ADHED includes a server-side rules engine that evaluates conditions and executes actions on every write operation. Rules are deterministic: given the same state, they always produce the same outcome.

## Concept

A rule consists of:

1. **Trigger** — which event activates the rule
2. **Conditions** — a tree of predicates that must all pass
3. **Actions** — what happens when conditions match (label, reject, notify, etc.)

Rules are evaluated in priority order (lower number = evaluated first). When a `reject` action fires, the entire operation is rolled back and the client receives HTTP 422.

---

## Triggers

Rules fire on specific events. Each trigger provides context about what happened.

| Trigger | Fires when |
|---------|-----------|
| `issue.created` | A new issue is created |
| `issue.state_changed` | An issue moves to a different state category |
| `issue.assigned` | An issue's assignee changes |
| `issue.updated` | Any field on an issue is updated (always fires on PATCH) |
| `issue.comment_added` | A comment is added to an issue |
| `project.state_changed` | A project's state changes |

Multiple triggers can fire on a single operation. For example, updating an issue's state and assignee in one PATCH fires: `issue.state_changed`, `issue.assigned`, and `issue.updated`.

---

## Condition Types

Conditions form a tree. Each leaf condition has a `type` and evaluates to true or false.

### Leaf Conditions

| Type | Keys | Description |
|------|------|-------------|
| `field_equals` | `field`, `value` | Issue field equals the value |
| `field_in` | `field`, `values` | Issue field is one of the listed values |
| `field_is_null` | `field` | Issue field is null/unset |
| `field_not_null` | `field` | Issue field has a value |
| `field_contains` | `field`, `value` | Issue field contains substring (case-insensitive) |
| `field_gt` | `field`, `value` | Issue field is greater than value |
| `field_lt` | `field`, `value` | Issue field is less than value |
| `field_gte` | `field`, `value` | Issue field is greater than or equal to value |
| `field_lte` | `field`, `value` | Issue field is less than or equal to value |
| `label_has` | `value` | Issue has a label with this name |
| `count_query` | `where`, `operator`, `value` | Count matching issues, compare result (requires DB) |
| `estimate_sum` | `where`, `operator`, `value` | Sum estimates of matching issues, compare result (requires DB) |

### Composite Conditions

| Type | Keys | Description |
|------|------|-------------|
| `and` | `conditions` (array) | All sub-conditions must be true |
| `or` | `conditions` (array) | At least one sub-condition must be true |
| `not` | `condition` (single) | Inverts the inner condition |

### count_query

Counts issues matching a filter and compares to a threshold. Used for WIP limits and capacity checks.

```json
{
  "type": "count_query",
  "where": {
    "state_type": ["started"],
    "assignee": "$current_user"
  },
  "operator": ">=",
  "value": 5
}
```

**Where clause filters:**

| Filter | Type | Description |
|--------|------|-------------|
| `state_type` | string or list | Match issues in these state categories |
| `state_type_not_in` | string or list | Exclude issues in these state categories |
| `assignee` | string | Match by assignee (supports `$current_user`) |
| `project_id` | string | Match by project |
| `parent_id` | string | Match by parent issue |

**Operators:** `>=`, `<=`, `>`, `<`, `==`

### estimate_sum

Sums the `estimate` field of matching issues and compares to a threshold. Same `where` clause as `count_query`.

```json
{
  "type": "estimate_sum",
  "where": {
    "state_type": ["started"],
    "assignee": "$current_user"
  },
  "operator": ">=",
  "value": 20
}
```

---

## Context Variables

The rules engine provides a `RuleContext` with information about the current operation. Conditions can reference these fields.

### Resolvable fields (via `field` key)

| Field name | Source | Description |
|------------|--------|-------------|
| `title` | issue | Issue title |
| `description` | issue | Issue description |
| `type` | issue | Issue type (task, reference, idea) |
| `priority` | issue | Priority (0-4) |
| `estimate` | issue | Effort estimate |
| `assignee_id` | issue | Current assignee UUID |
| `project_id` | issue | Current project UUID |
| `parent_id` | issue | Parent issue UUID |
| `state` | issue | Current state name |
| `state_type` | issue | Current state category |
| `from_state` | context | Previous state name (on state change) |
| `from_state_type` | context | Previous state category (on state change) |
| `to_state` | context | Target state name (on state change) |
| `to_state_type` | context | Target state category (on state change) |
| `current_user` | context | UUID of the acting user |

### Value references (via `value` key)

| Reference | Resolves to |
|-----------|------------|
| `$current_user` | UUID of the acting user |
| `$current.<field>` | Current value of the issue field (e.g. `$current.priority`) |

---

## Action Types

When a rule's conditions match, its actions execute.

| Type | Keys | Description |
|------|------|-------------|
| `reject` | `message` | Reject the operation (HTTP 422). Rolls back the entire transaction. |
| `set_field` | `field`, `value` | Set a field on the issue |
| `add_label` | `label` | Attach a label by name (must already exist in the team) |
| `add_comment` | `body` | Add a comment to the issue |
| `notify` | `message`, `user_id` (optional) | Create a notification. If `user_id` omitted, team-wide. |

### Template Variables in Messages

Action messages (for `reject`, `add_comment`, `notify`) support template variables:

| Variable | Replaced with |
|----------|--------------|
| `{title}` | Issue title |
| `{priority}` | Issue priority |
| `{assignee}` | Assignee ID |
| `{state}` | Target state name (or current state) |
| `{project}` | Project ID |

Example: `"message": "Urgent item created: {title} (P{priority})"`

---

## Evaluation Order

1. Rules are loaded from the database filtered by team and trigger, ordered by `priority` ASC (lower number = first).
2. For each rule, conditions are evaluated against the context.
3. If conditions pass, actions are prepared.
4. If any action is `reject`, a `RuleRejection` exception is raised immediately. The operation is rolled back. No further rules are evaluated.
5. Non-reject effects are collected and applied after the mutation.

## Pre-Commit Evaluation

Rules are evaluated **before** the mutation is applied to the database. The context reflects the issue's current (pre-mutation) state, with `to_state` and `to_state_type` reflecting where it is going. This means a `reject` action prevents the change from ever being written.

For `issue.created`, the context reflects the new issue's fields and target state.

## No Cascading

Rule effects do not trigger further rule evaluation. If a rule adds a label, that label addition does not fire `issue.updated` again. This prevents infinite loops and keeps behavior predictable.

---

## Example Rules

### 1. Auto-label health by keyword

Adds the "health" label when a new issue mentions health-related keywords.

```json
{
  "name": "Auto-label health",
  "trigger": "issue.created",
  "conditions": {
    "type": "or",
    "conditions": [
      {"type": "field_contains", "field": "title", "value": "doctor"},
      {"type": "field_contains", "field": "title", "value": "dentist"},
      {"type": "field_contains", "field": "title", "value": "gym"},
      {"type": "field_contains", "field": "title", "value": "medication"},
      {"type": "field_contains", "field": "title", "value": "vitamin"}
    ]
  },
  "actions": [{"type": "add_label", "label": "health"}],
  "priority": 100
}
```

### 2. WIP limit (max 5 in progress)

Rejects moving an issue to "started" if the user already has 5 or more started items.

```json
{
  "name": "WIP limit (5)",
  "trigger": "issue.state_changed",
  "conditions": {
    "type": "and",
    "conditions": [
      {"type": "field_equals", "field": "to_state_type", "value": "started"},
      {
        "type": "count_query",
        "where": {"state_type": ["started"], "assignee": "$current_user"},
        "operator": ">=",
        "value": 5
      }
    ]
  },
  "actions": [{"type": "reject", "message": "WIP limit reached — you already have 5 items in progress"}],
  "priority": 10
}
```

### 3. Require priority before leaving triage

Rejects moving an issue out of triage if priority is still 0 (unset).

```json
{
  "name": "Triage requires priority",
  "trigger": "issue.state_changed",
  "conditions": {
    "type": "and",
    "conditions": [
      {"type": "field_equals", "field": "from_state_type", "value": "triage"},
      {"type": "field_equals", "field": "priority", "value": 0}
    ]
  },
  "actions": [{"type": "reject", "message": "Set a priority before moving out of triage"}],
  "priority": 10
}
```

### 4. Notify on urgent item creation

Creates a notification when a priority-1 issue is created.

```json
{
  "name": "Urgent creation notification",
  "trigger": "issue.created",
  "conditions": {
    "type": "field_equals",
    "field": "priority",
    "value": 1
  },
  "actions": [{"type": "notify", "message": "Urgent item created: {title}", "user_id": "$current_user"}],
  "priority": 100
}
```

### 5. Subtask completion notification

Notifies the parent issue creator when a subtask is completed.

```json
{
  "name": "Subtask completed notification",
  "trigger": "issue.state_changed",
  "conditions": {
    "type": "and",
    "conditions": [
      {"type": "field_equals", "field": "to_state_type", "value": "completed"},
      {"type": "field_not_null", "field": "parent_id"}
    ]
  },
  "actions": [{"type": "notify", "message": "Subtask completed: {title}"}],
  "priority": 100
}
```
