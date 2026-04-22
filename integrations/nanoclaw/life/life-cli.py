#!/usr/bin/env python3
"""Deterministic life/task management CLI for NanoClaw container agents.

Wraps the taskstore REST API. All operations go through this script —
the agent never calls the API directly.

Usage:
    life-cli.py issue create --title "..." [--priority 0-4] [--label name] ...
    life-cli.py issue list [--state-type started,unstarted] [--assignee me] ...
    life-cli.py issue get <id>
    life-cli.py issue update <id> [--title "..."] [--state "In Progress"] ...
    life-cli.py issue delete <id>
    life-cli.py issue search "query"
    life-cli.py issue add-subtask <parent-id> --title "..." [--priority N]
    life-cli.py issue convert-to-project <id>
    life-cli.py issue batch-create --titles "item1" "item2" ...
    life-cli.py project list [--state planned|started|paused|completed|canceled]
    life-cli.py project create --name "..." [--description "..."] [--lead user-id]
    life-cli.py project get <id>
    life-cli.py project update <id> [--state started] [--name "..."]
    life-cli.py project stalled
    life-cli.py summary
    life-cli.py overdue
    life-cli.py triage
    life-cli.py rules list
    life-cli.py rules test <rule-id> --issue <issue-id>
    life-cli.py reboot
    life-cli.py triage-all --action accept|decline
    life-cli.py notifications [--mark-read]
    life-cli.py fragment create --text "..." --type person [--summary "..."] [--topics a,b]
    life-cli.py fragment list [--type person] [--domain "..."] [--topic "..."] [--search "..."]
    life-cli.py fragment get <id>
    life-cli.py fragment delete <id>
    life-cli.py fragment topics
    life-cli.py label list
    life-cli.py label create --name "..." [--color "#hex"]
    life-cli.py states list
"""

import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration (from environment)
# ---------------------------------------------------------------------------

TASKSTORE_URL = os.environ.get("TASKSTORE_URL", "http://host.docker.internal:8100")
TASKSTORE_API_KEY = os.environ.get("TASKSTORE_API_KEY", "")
TASKSTORE_USER_ID = os.environ.get("TASKSTORE_USER_ID", "")
TASKSTORE_TEAM_ID = os.environ.get("TASKSTORE_TEAM_ID", "")

# State type constants (as used by the API)
STATE_TYPE_TRIAGE = "triage"
STATE_TYPE_UNSTARTED = "unstarted"
STATE_TYPE_STARTED = "started"
STATE_TYPE_COMPLETED = "completed"
STATE_TYPE_CANCELLED = "cancelled"

PRIORITY_LABELS = {0: "P0", 1: "P1", 2: "P2", 3: "P3", 4: "P4"}

STATE_EMOJI = {
    STATE_TYPE_TRIAGE: "🟡",
    STATE_TYPE_UNSTARTED: "⚪",
    STATE_TYPE_STARTED: "🔵",
    STATE_TYPE_COMPLETED: "✅",
    STATE_TYPE_CANCELLED: "❌",
}

STATE_DISPLAY = {
    STATE_TYPE_TRIAGE: "TRIAGE",
    STATE_TYPE_UNSTARTED: "TODO",
    STATE_TYPE_STARTED: "IN PROGRESS",
    STATE_TYPE_COMPLETED: "DONE",
    STATE_TYPE_CANCELLED: "CANCELLED",
}

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def _headers() -> Dict[str, str]:
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if TASKSTORE_API_KEY:
        h["X-API-Key"] = TASKSTORE_API_KEY
    if TASKSTORE_USER_ID:
        h["X-User-Id"] = TASKSTORE_USER_ID
    return h


def _team_path(path: str) -> str:
    """Prefix a path with /api/v1/teams/{team_id} if it starts with /."""
    team_id = get_team_id()
    entity_prefixes = ("/issues/", "/projects/", "/rules/", "/notifications/")
    if any(path.startswith(p) for p in entity_prefixes):
        return f"/api/v1{path}"
    # Fragment by ID is entity-level, but /fragments and /fragments/topics are team-scoped
    if path.startswith("/fragments/") and path != "/fragments/topics":
        return f"/api/v1{path}"
    # Team-scoped paths
    return f"/api/v1/teams/{team_id}{path}"


def api_request(method: str, path: str, body: Optional[dict] = None, params: Optional[dict] = None) -> Any:
    """Make an authenticated API request. Returns parsed JSON or raises SystemExit on error."""
    full_path = _team_path(path)
    url = f"{TASKSTORE_URL.rstrip('/')}{full_path}"
    if params:
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        if query:
            url = f"{url}?{query}"

    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read()
            if raw:
                return json.loads(raw)
            return {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            err = json.loads(raw)
            msg = err.get("error") or err.get("message") or str(err)
        except Exception:
            msg = raw.decode(errors="replace")
        print(f"❌ API error {e.code}: {msg}", file=sys.stderr)
        sys.exit(1)
    except urllib.error.URLError as e:
        print(f"❌ Connection error: {e.reason}", file=sys.stderr)
        print(f"   Is the taskstore running at {TASKSTORE_URL}?", file=sys.stderr)
        sys.exit(1)


def api_get(path: str, params: Optional[dict] = None) -> Any:
    return api_request("GET", path, params=params)


def api_post(path: str, body: dict) -> Any:
    return api_request("POST", path, body=body)


def api_patch(path: str, body: dict) -> Any:
    return api_request("PATCH", path, body=body)


def api_delete(path: str) -> Any:
    return api_request("DELETE", path)


# ---------------------------------------------------------------------------
# State/label resolution helpers
# ---------------------------------------------------------------------------

_states_cache: Optional[List[dict]] = None
_labels_cache: Optional[List[dict]] = None
_team_id_cache: Optional[str] = None


def get_team_id() -> str:
    global _team_id_cache
    if _team_id_cache:
        return _team_id_cache
    if TASKSTORE_TEAM_ID:
        _team_id_cache = TASKSTORE_TEAM_ID
    else:
        die("TASKSTORE_TEAM_ID environment variable is required")
    return _team_id_cache


def get_states() -> List[dict]:
    global _states_cache
    if _states_cache is not None:
        return _states_cache
    try:
        team_id = get_team_id()
        result = api_get(f"/teams/{team_id}/states")
        _states_cache = result if isinstance(result, list) else result.get("data", [])
    except SystemExit:
        _states_cache = []
    return _states_cache


def resolve_state_id(name: str) -> Optional[str]:
    """Find state_id by state name (case-insensitive)."""
    states = get_states()
    nl = name.lower()
    for s in states:
        if s.get("name", "").lower() == nl:
            return s.get("id")
    # Partial match
    for s in states:
        if nl in s.get("name", "").lower():
            return s.get("id")
    return None


def find_state_by_type(state_type: str) -> Optional[dict]:
    """Return first state matching the given type."""
    states = get_states()
    for s in states:
        if s.get("type") == state_type:
            return s
    return None


def get_state_id_for_type(state_type: str) -> Optional[str]:
    s = find_state_by_type(state_type)
    return s.get("id") if s else None


def get_labels() -> List[dict]:
    global _labels_cache
    if _labels_cache is not None:
        return _labels_cache
    try:
        result = api_get("/labels")
        _labels_cache = result if isinstance(result, list) else result.get("data", [])
    except SystemExit:
        _labels_cache = []
    return _labels_cache


def resolve_label_id(name: str) -> Optional[str]:
    labels = get_labels()
    nl = name.lower()
    for lb in labels:
        if lb.get("name", "").lower() == nl:
            return lb.get("id")
    return None


def resolve_assignee(val: str) -> str:
    if val.lower() == "me":
        return TASKSTORE_USER_ID
    return val


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_priority(p: Optional[int]) -> str:
    if p is None:
        return ""
    return PRIORITY_LABELS.get(p, f"P{p}")


def fmt_due(due_str: Optional[str]) -> Optional[str]:
    if not due_str:
        return None
    try:
        d = date.fromisoformat(due_str[:10])
        today = date.today()
        delta = (d - today).days
        if delta < 0:
            return f"⚠️ {abs(delta)}d overdue"
        elif delta == 0:
            return "due today"
        elif delta <= 7:
            return f"due in {delta}d"
        else:
            return f"due {d.strftime('%b %d')}"
    except ValueError:
        return due_str


def fmt_issue_line(issue: dict) -> str:
    title = issue.get("title", "(no title)")
    state_name = issue.get("state", {}).get("name", "") if isinstance(issue.get("state"), dict) else ""
    priority = issue.get("priority")
    p_str = fmt_priority(priority)
    due = fmt_due(issue.get("dueDate") or issue.get("due_date"))

    parts = [f"  • {title}"]
    tags = []
    if p_str:
        tags.append(f"[{p_str}]")
    if due:
        tags.append(f"— {due}")
    if tags:
        parts.append(" ".join(tags))
    return " ".join(parts)


def fmt_issue_detail(issue: dict) -> str:
    title = issue.get("title", "(no title)")
    state = issue.get("state") or {}
    state_name = state.get("name", "?") if isinstance(state, dict) else str(state)
    priority = issue.get("priority")
    p_str = fmt_priority(priority)
    due = issue.get("dueDate") or issue.get("due_date")
    assignee = issue.get("assignee") or {}
    assignee_name = assignee.get("name", "") if isinstance(assignee, dict) else ""
    project = issue.get("project") or {}
    project_name = project.get("name", "") if isinstance(project, dict) else ""
    labels = issue.get("labels") or []
    label_names = [lb.get("name", "") if isinstance(lb, dict) else str(lb) for lb in labels]
    issue_id = issue.get("identifier") or issue.get("id", "")

    lines = [f"📋 {title} [{state_name}] {p_str}"]
    meta = []
    if due:
        meta.append(f"Due: {due[:10]}")
    if assignee_name:
        meta.append(f"Assigned: {assignee_name}")
    if project_name:
        meta.append(f"Project: {project_name}")
    if meta:
        lines.append("   " + " | ".join(meta))
    if label_names:
        lines.append(f"   Labels: {', '.join(label_names)}")
    if issue_id:
        lines.append(f"   ID: {issue_id}")
    desc = issue.get("description") or ""
    if desc:
        lines.append(f"   {desc[:200]}")
    return "\n".join(lines)


def fmt_issues_grouped(issues: List[dict]) -> str:
    """Group issues by state type for list output."""
    STATE_ORDER = [
        STATE_TYPE_TRIAGE,
        STATE_TYPE_STARTED,
        STATE_TYPE_UNSTARTED,
        STATE_TYPE_COMPLETED,
        STATE_TYPE_CANCELLED,
    ]

    grouped: Dict[str, List[dict]] = {}
    for issue in issues:
        state = issue.get("state") or {}
        st = state.get("type", STATE_TYPE_UNSTARTED) if isinstance(state, dict) else STATE_TYPE_UNSTARTED
        grouped.setdefault(st, []).append(issue)

    lines = []
    for st in STATE_ORDER:
        bucket = grouped.get(st, [])
        if not bucket:
            continue
        emoji = STATE_EMOJI.get(st, "⚫")
        label = STATE_DISPLAY.get(st, st.upper())
        lines.append(f"{emoji} {label} ({len(bucket)})")
        for issue in bucket:
            lines.append(fmt_issue_line(issue))
        lines.append("")

    # Any leftover state types not in our order
    for st, bucket in grouped.items():
        if st not in STATE_ORDER:
            lines.append(f"⚫ {st.upper()} ({len(bucket)})")
            for issue in bucket:
                lines.append(fmt_issue_line(issue))
            lines.append("")

    return "\n".join(lines).strip()


def days_overdue(due_str: str) -> int:
    """Return number of days overdue (positive = overdue). 0 if not overdue."""
    try:
        d = date.fromisoformat(due_str[:10])
        return (date.today() - d).days
    except ValueError:
        return 0


# ---------------------------------------------------------------------------
# Issue commands
# ---------------------------------------------------------------------------

def parse_args(argv: List[str]) -> Dict[str, Any]:
    """Very minimal key=value arg parser for --flag value style args."""
    result: Dict[str, Any] = {"_positional": []}
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg.startswith("--"):
            key = arg[2:].replace("-", "_")
            if i + 1 < len(argv) and not argv[i + 1].startswith("--"):
                result[key] = argv[i + 1]
                i += 2
            else:
                result[key] = True
                i += 1
        else:
            result["_positional"].append(arg)
            i += 1
    return result


def collect_multi(argv: List[str], flag: str) -> List[str]:
    """Collect all values after --flag until the next --flag."""
    result = []
    i = 0
    while i < len(argv):
        if argv[i] == f"--{flag}":
            i += 1
            while i < len(argv) and not argv[i].startswith("--"):
                result.append(argv[i])
                i += 1
        else:
            i += 1
    return result


def cmd_issue_create(argv: List[str]):
    args = parse_args(argv)
    title = args.get("title")
    if not title:
        print("❌ --title is required", file=sys.stderr)
        sys.exit(1)

    body: Dict[str, Any] = {"title": title}
    if "priority" in args:
        body["priority"] = int(args["priority"])
    if "project" in args:
        body["projectId"] = args["project"]
    if "estimate" in args:
        body["estimate"] = int(args["estimate"])
    if "due" in args:
        body["dueDate"] = args["due"]
    if "type" in args:
        body["type"] = args["type"]
    if "assignee" in args:
        body["assigneeId"] = resolve_assignee(args["assignee"])
    if "label" in args:
        label_id = resolve_label_id(args["label"])
        if label_id:
            body["labelIds"] = [label_id]
        else:
            print(f"⚠️  Label '{args['label']}' not found — creating issue without label")

    issue = api_post("/issues", body)
    identifier = issue.get("identifier") or issue.get("id", "")
    print(f"✅ Created: {title}")
    print(f"   ID: {identifier}")
    if issue.get("url"):
        print(f"   URL: {issue['url']}")


def cmd_issue_list(argv: List[str]):
    args = parse_args(argv)
    params: Dict[str, Any] = {}

    if "state_type" in args:
        params["stateType"] = args["state_type"]
    if "assignee" in args:
        params["assigneeId"] = resolve_assignee(args["assignee"])
    if "label" in args:
        params["labelName"] = args["label"]
    if "project" in args:
        params["projectId"] = args["project"]
    if "overdue" in args:
        params["overdue"] = "true"
    if "priority" in args:
        params["priority"] = args["priority"]
    if "search" in args:
        params["search"] = args["search"]
    if "estimate_lte" in args:
        params["estimateLte"] = args["estimate_lte"]
    if "limit" in args:
        params["limit"] = args["limit"]

    result = api_get("/issues", params)
    issues = result if isinstance(result, list) else result.get("data", result.get("issues", []))
    if not issues:
        print("No issues found.")
        return
    print(fmt_issues_grouped(issues))


def cmd_issue_get(argv: List[str]):
    if not argv:
        print("❌ Usage: issue get <id>", file=sys.stderr)
        sys.exit(1)
    issue_id = argv[0]
    issue = api_get(f"/issues/{issue_id}")
    print(fmt_issue_detail(issue))

    # Show subtasks if any
    subtasks = issue.get("children") or issue.get("subIssues") or []
    if subtasks:
        print(f"\n  Subtasks ({len(subtasks)}):")
        for sub in subtasks:
            print(f"    • {sub.get('title', '?')} [{fmt_priority(sub.get('priority'))}]")


def cmd_issue_update(argv: List[str]):
    if not argv:
        print("❌ Usage: issue update <id> [--title ...] [--priority N] [--state 'Name'] ...", file=sys.stderr)
        sys.exit(1)
    issue_id = argv[0]
    args = parse_args(argv[1:])

    body: Dict[str, Any] = {}
    if "title" in args:
        body["title"] = args["title"]
    if "priority" in args:
        body["priority"] = int(args["priority"])
    if "due" in args:
        body["dueDate"] = args["due"]
    if "assignee" in args:
        body["assigneeId"] = resolve_assignee(args["assignee"])
    if "state" in args:
        state_id = resolve_state_id(args["state"])
        if not state_id:
            print(f"❌ State '{args['state']}' not found. Run 'states list' to see available states.", file=sys.stderr)
            sys.exit(1)
        body["stateId"] = state_id

    if not body:
        print("❌ No fields to update. Provide at least one of: --title, --priority, --state, --due, --assignee")
        sys.exit(1)

    issue = api_patch(f"/issues/{issue_id}", body)
    print(f"✅ Updated issue {issue_id}")
    if "title" in body:
        print(f"   Title: {body['title']}")
    if "stateId" in body:
        print(f"   State: {args.get('state')}")


def cmd_issue_delete(argv: List[str]):
    if not argv:
        print("❌ Usage: issue delete <id>", file=sys.stderr)
        sys.exit(1)
    issue_id = argv[0]
    api_delete(f"/issues/{issue_id}")
    print(f"🗑️  Deleted issue {issue_id}")


def cmd_issue_search(argv: List[str]):
    if not argv:
        print("❌ Usage: issue search 'query text'", file=sys.stderr)
        sys.exit(1)
    query = " ".join(argv)
    result = api_get("/issues", {"search": query})
    issues = result if isinstance(result, list) else result.get("data", result.get("issues", []))
    if not issues:
        print(f"No issues found for: {query}")
        return
    print(f"🔍 Found {len(issues)} issue(s) for '{query}':\n")
    print(fmt_issues_grouped(issues))


def cmd_issue_add_subtask(argv: List[str]):
    if not argv:
        print("❌ Usage: issue add-subtask <parent-id> --title '...' [--priority N]", file=sys.stderr)
        sys.exit(1)
    parent_id = argv[0]
    args = parse_args(argv[1:])
    title = args.get("title")
    if not title:
        print("❌ --title is required", file=sys.stderr)
        sys.exit(1)

    body: Dict[str, Any] = {"title": title, "parentId": parent_id}
    if "priority" in args:
        body["priority"] = int(args["priority"])

    issue = api_post("/issues", body)
    identifier = issue.get("identifier") or issue.get("id", "")
    print(f"✅ Created subtask: {title}")
    print(f"   ID: {identifier} (parent: {parent_id})")


def cmd_issue_convert_to_project(argv: List[str]):
    if not argv:
        print("❌ Usage: issue convert-to-project <id>", file=sys.stderr)
        sys.exit(1)
    issue_id = argv[0]
    result = api_post(f"/issues/{issue_id}/convert-to-project", {})
    project_id = result.get("id", "")
    project_name = result.get("name", "")
    print(f"✅ Converted issue {issue_id} to project: {project_name} (ID: {project_id})")


def cmd_issue_batch_create(argv: List[str]):
    titles = collect_multi(argv, "titles")
    if not titles:
        # Fallback: treat all positional args as titles
        args = parse_args(argv)
        titles = args.get("_positional", [])
    if not titles:
        print("❌ Usage: issue batch-create --titles 'item1' 'item2' ...", file=sys.stderr)
        sys.exit(1)

    created = []
    errors = []
    for title in titles:
        try:
            issue = api_post("/issues", {"title": title})
            created.append(issue.get("identifier") or issue.get("id", title))
        except SystemExit:
            errors.append(title)

    print(f"✅ Created {len(created)} issue(s):")
    for iid in created:
        print(f"   • {iid}")
    if errors:
        print(f"❌ Failed to create {len(errors)}: {', '.join(errors)}")


# ---------------------------------------------------------------------------
# Project commands
# ---------------------------------------------------------------------------

def cmd_project_list(argv: List[str]):
    args = parse_args(argv)
    params: Dict[str, Any] = {}
    if "state" in args:
        params["state"] = args["state"]

    result = api_get("/projects", params)
    projects = result if isinstance(result, list) else result.get("data", result.get("projects", []))
    if not projects:
        print("No projects found.")
        return

    lines = [f"📁 Projects ({len(projects)})\n" + "━" * 22]
    for p in projects:
        name = p.get("name", "(no name)")
        state = p.get("state", "?")
        pid = p.get("identifier") or p.get("id", "")
        lead = p.get("lead") or {}
        lead_name = lead.get("name", "") if isinstance(lead, dict) else ""
        desc = p.get("description") or ""
        line = f"  [{state}] {name}"
        if lead_name:
            line += f" — {lead_name}"
        if pid:
            line += f" ({pid})"
        lines.append(line)
        if desc:
            lines.append(f"     {desc[:100]}")
    print("\n".join(lines))


def cmd_project_create(argv: List[str]):
    args = parse_args(argv)
    name = args.get("name")
    if not name:
        print("❌ --name is required", file=sys.stderr)
        sys.exit(1)

    body: Dict[str, Any] = {"name": name}
    if "description" in args:
        body["description"] = args["description"]
    if "lead" in args:
        body["leadId"] = resolve_assignee(args["lead"])

    project = api_post("/projects", body)
    pid = project.get("identifier") or project.get("id", "")
    print(f"✅ Created project: {name} (ID: {pid})")


def cmd_project_get(argv: List[str]):
    if not argv:
        print("❌ Usage: project get <id>", file=sys.stderr)
        sys.exit(1)
    project_id = argv[0]
    project = api_get(f"/projects/{project_id}")
    name = project.get("name", "?")
    state = project.get("state", "?")
    desc = project.get("description") or ""
    pid = project.get("identifier") or project.get("id", "")
    lead = project.get("lead") or {}
    lead_name = lead.get("name", "") if isinstance(lead, dict) else ""

    lines = [f"📁 {name} [{state}]"]
    if pid:
        lines.append(f"   ID: {pid}")
    if lead_name:
        lines.append(f"   Lead: {lead_name}")
    if desc:
        lines.append(f"   {desc}")

    # Issues in this project
    issues_result = api_get("/issues", {"projectId": project_id, "limit": "50"})
    issues = issues_result if isinstance(issues_result, list) else issues_result.get("data", [])
    if issues:
        lines.append(f"\n  Issues ({len(issues)}):")
        for issue in issues[:20]:
            lines.append(fmt_issue_line(issue))
        if len(issues) > 20:
            lines.append(f"  ... and {len(issues) - 20} more")

    print("\n".join(lines))


def cmd_project_update(argv: List[str]):
    if not argv:
        print("❌ Usage: project update <id> [--state started] [--name '...']", file=sys.stderr)
        sys.exit(1)
    project_id = argv[0]
    args = parse_args(argv[1:])

    body: Dict[str, Any] = {}
    if "state" in args:
        body["state"] = args["state"]
    if "name" in args:
        body["name"] = args["name"]
    if "description" in args:
        body["description"] = args["description"]

    if not body:
        print("❌ No fields to update.")
        sys.exit(1)

    api_patch(f"/projects/{project_id}", body)
    print(f"✅ Updated project {project_id}")


def cmd_project_stalled(argv: List[str]):
    """List started projects with no recent activity (no started issues)."""
    result = api_get("/projects", {"state": "started"})
    projects = result if isinstance(result, list) else result.get("data", [])
    if not projects:
        print("No started projects.")
        return

    stalled = []
    for p in projects:
        pid = p.get("id") or p.get("identifier", "")
        issues_result = api_get("/issues", {"projectId": pid, "stateType": "started"})
        issues = issues_result if isinstance(issues_result, list) else issues_result.get("data", [])
        if not issues:
            stalled.append(p)

    if not stalled:
        print("✅ No stalled projects — all started projects have active issues.")
        return

    lines = [f"⚠️  Stalled Projects ({len(stalled)})", "━" * 22]
    for p in stalled:
        name = p.get("name", "?")
        pid = p.get("identifier") or p.get("id", "")
        lines.append(f"  • {name} ({pid}) — no active issues")
    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Summary, overdue, triage
# ---------------------------------------------------------------------------

def cmd_summary(_argv: List[str]):
    """Dashboard overview."""
    all_issues = api_get("/issues", {"limit": "200"})
    issues = all_issues if isinstance(all_issues, list) else all_issues.get("data", all_issues.get("issues", []))

    today = date.today()

    triage_issues = []
    started_issues = []
    overdue_issues = []
    due_soon_issues = []

    for issue in issues:
        state = issue.get("state") or {}
        st = state.get("type", "") if isinstance(state, dict) else ""
        due_raw = issue.get("dueDate") or issue.get("due_date")

        if st == STATE_TYPE_TRIAGE:
            triage_issues.append(issue)
        if st == STATE_TYPE_STARTED:
            started_issues.append(issue)

        if due_raw:
            try:
                d = date.fromisoformat(due_raw[:10])
                delta = (d - today).days
                if delta < 0 and st not in (STATE_TYPE_COMPLETED, STATE_TYPE_CANCELLED):
                    overdue_issues.append((issue, abs(delta)))
                elif 0 <= delta <= 7 and st not in (STATE_TYPE_COMPLETED, STATE_TYPE_CANCELLED):
                    due_soon_issues.append((issue, delta))
            except ValueError:
                pass

    overdue_issues.sort(key=lambda x: x[1], reverse=True)
    due_soon_issues.sort(key=lambda x: x[1])

    lines = [
        "📊 Dashboard",
        "━" * 20,
        f"Triage: {len(triage_issues)} item{'s' if len(triage_issues) != 1 else ''} waiting",
        f"In Progress: {len(started_issues)}",
        f"Overdue: {len(overdue_issues)}" + (" ⚠️" if overdue_issues else ""),
        f"Due Soon: {len(due_soon_issues)}",
        "",
    ]

    if overdue_issues:
        lines.append("⚠️  OVERDUE")
        for issue, days in overdue_issues[:10]:
            title = issue.get("title", "?")
            lines.append(f"  • {title} — {days} day{'s' if days != 1 else ''} overdue")
        if len(overdue_issues) > 10:
            lines.append(f"  ... and {len(overdue_issues) - 10} more")
        lines.append("")

    if due_soon_issues:
        lines.append("📅 DUE SOON")
        for issue, days in due_soon_issues[:10]:
            title = issue.get("title", "?")
            if days == 0:
                lines.append(f"  • {title} — today")
            else:
                lines.append(f"  • {title} — in {days} day{'s' if days != 1 else ''}")
        if len(due_soon_issues) > 10:
            lines.append(f"  ... and {len(due_soon_issues) - 10} more")
        lines.append("")

    if started_issues:
        lines.append("🔵 IN PROGRESS")
        for issue in started_issues[:10]:
            lines.append(fmt_issue_line(issue))

    print("\n".join(lines).strip())


def cmd_overdue(_argv: List[str]):
    result = api_get("/issues", {"overdue": "true"})
    issues = result if isinstance(result, list) else result.get("data", result.get("issues", []))
    if not issues:
        print("✅ No overdue issues!")
        return

    today = date.today()
    pairs = []
    for issue in issues:
        due_raw = issue.get("dueDate") or issue.get("due_date")
        days = 0
        if due_raw:
            try:
                d = date.fromisoformat(due_raw[:10])
                days = (today - d).days
            except ValueError:
                pass
        pairs.append((issue, days))
    pairs.sort(key=lambda x: x[1], reverse=True)

    lines = [f"⚠️  Overdue Issues ({len(pairs)})", "━" * 22]
    for issue, days in pairs:
        title = issue.get("title", "?")
        p = fmt_priority(issue.get("priority"))
        line = f"  • {title}"
        if p:
            line += f" [{p}]"
        line += f" — {days} day{'s' if days != 1 else ''} overdue"
        lines.append(line)
    print("\n".join(lines))


def cmd_triage(_argv: List[str]):
    result = api_get("/issues", {"stateType": STATE_TYPE_TRIAGE})
    issues = result if isinstance(result, list) else result.get("data", result.get("issues", []))
    if not issues:
        print("✅ Triage is empty!")
        return

    lines = [f"🟡 TRIAGE ({len(issues)} items)", "━" * 22]
    for issue in issues:
        title = issue.get("title", "?")
        p = fmt_priority(issue.get("priority"))
        iid = issue.get("identifier") or issue.get("id", "")
        line = f"  • {title}"
        if p:
            line += f" [{p}]"
        if iid:
            line += f" ({iid})"
        lines.append(line)
    lines.append("\nUse 'issue update <id> --state Backlog' to accept or '--state Cancelled' to decline.")
    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------

def cmd_rules_list(_argv: List[str]):
    result = api_get("/rules")
    rules = result if isinstance(result, list) else result.get("data", [])
    if not rules:
        print("No automation rules found.")
        return

    lines = [f"⚙️  Rules ({len(rules)})", "━" * 22]
    for r in rules:
        name = r.get("name", "?")
        rid = r.get("id", "")
        enabled = "✅" if r.get("enabled") else "⏸️"
        lines.append(f"  {enabled} {name} ({rid})")
    print("\n".join(lines))


def cmd_rules_test(argv: List[str]):
    if not argv:
        print("❌ Usage: rules test <rule-id> --issue <issue-id>", file=sys.stderr)
        sys.exit(1)
    args = parse_args(argv)
    rule_id = args["_positional"][0] if args["_positional"] else None
    issue_id = args.get("issue")
    if not rule_id or not issue_id:
        print("❌ Usage: rules test <rule-id> --issue <issue-id>", file=sys.stderr)
        sys.exit(1)

    result = api_post(f"/rules/{rule_id}/test", {"issueId": issue_id})
    matched = result.get("matched", False)
    print(f"Rule {rule_id} {'✅ MATCHED' if matched else '❌ did not match'} issue {issue_id}")
    if result.get("reason"):
        print(f"  Reason: {result['reason']}")


# ---------------------------------------------------------------------------
# Bulk operations
# ---------------------------------------------------------------------------

def cmd_reboot(_argv: List[str]):
    """Move all started issues back to backlog and show triage count."""
    started_result = api_get("/issues", {"stateType": STATE_TYPE_STARTED})
    started = started_result if isinstance(started_result, list) else started_result.get("data", [])

    backlog_state_id = get_state_id_for_type(STATE_TYPE_UNSTARTED)
    if not backlog_state_id and started:
        print("❌ Could not find a backlog/unstarted state. Run 'states list' to check.", file=sys.stderr)
        sys.exit(1)

    moved = 0
    for issue in started:
        issue_id = issue.get("id")
        if issue_id and backlog_state_id:
            try:
                api_patch(f"/issues/{issue_id}", {"stateId": backlog_state_id})
                moved += 1
            except SystemExit:
                pass

    triage_result = api_get("/issues", {"stateType": STATE_TYPE_TRIAGE})
    triage = triage_result if isinstance(triage_result, list) else triage_result.get("data", [])

    print(f"🔄 Reboot complete!")
    print(f"   Moved {moved} in-progress issue{'s' if moved != 1 else ''} back to backlog")
    print(f"   Triage: {len(triage)} item{'s' if len(triage) != 1 else ''} waiting")
    print("")
    print("Pick your top 3 for today 🎯")


def cmd_triage_all(argv: List[str]):
    args = parse_args(argv)
    action = args.get("action", "accept")
    if action not in ("accept", "decline"):
        print("❌ --action must be 'accept' or 'decline'", file=sys.stderr)
        sys.exit(1)

    triage_result = api_get("/issues", {"stateType": STATE_TYPE_TRIAGE})
    triage = triage_result if isinstance(triage_result, list) else triage_result.get("data", [])
    if not triage:
        print("✅ Triage is already empty!")
        return

    target_state_type = STATE_TYPE_UNSTARTED if action == "accept" else STATE_TYPE_CANCELLED
    target_state_id = get_state_id_for_type(target_state_type)
    if not target_state_id:
        print(f"❌ Could not find a {target_state_type} state.", file=sys.stderr)
        sys.exit(1)

    moved = 0
    for issue in triage:
        issue_id = issue.get("id")
        if issue_id:
            try:
                api_patch(f"/issues/{issue_id}", {"stateId": target_state_id})
                moved += 1
            except SystemExit:
                pass

    verb = "accepted (→ backlog)" if action == "accept" else "declined (→ cancelled)"
    print(f"✅ {verb} {moved} triage issue{'s' if moved != 1 else ''}")


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

def cmd_notifications(argv: List[str]):
    args = parse_args(argv)
    result = api_get("/notifications")
    notifications = result if isinstance(result, list) else result.get("data", [])

    if not notifications:
        print("📭 No notifications.")
        return

    lines = [f"🔔 Notifications ({len(notifications)})", "━" * 22]
    unread = [n for n in notifications if not n.get("readAt")]
    read = [n for n in notifications if n.get("readAt")]

    for n in unread:
        ntype = n.get("type", "notification")
        actor = n.get("actor") or {}
        actor_name = actor.get("name", "") if isinstance(actor, dict) else ""
        issue = n.get("issue") or {}
        issue_title = issue.get("title", "") if isinstance(issue, dict) else ""
        msg = f"  🔵 {ntype}"
        if actor_name:
            msg += f" from {actor_name}"
        if issue_title:
            msg += f": {issue_title}"
        lines.append(msg)

    if read:
        lines.append(f"\n  ({len(read)} read notification{'s' if len(read) != 1 else ''})")

    print("\n".join(lines))

    if "mark_read" in args:
        nids = [n["id"] for n in unread if n.get("id")]
        if nids:
            api_post("/notifications/mark-read", {"ids": nids})
            print(f"\n✅ Marked {len(nids)} notification{'s' if len(nids) != 1 else ''} as read")


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------

def cmd_label_list(_argv: List[str]):
    labels = get_labels()
    if not labels:
        print("No labels found.")
        return

    lines = [f"🏷️  Labels ({len(labels)})", "━" * 22]
    for lb in labels:
        name = lb.get("name", "?")
        color = lb.get("color", "")
        lid = lb.get("id", "")
        line = f"  • {name}"
        if color:
            line += f" ({color})"
        lines.append(line)
    print("\n".join(lines))


def cmd_label_create(argv: List[str]):
    args = parse_args(argv)
    name = args.get("name")
    if not name:
        print("❌ --name is required", file=sys.stderr)
        sys.exit(1)

    body: Dict[str, Any] = {"name": name}
    if "color" in args:
        body["color"] = args["color"]

    label = api_post("/labels", body)
    lid = label.get("id", "")
    print(f"✅ Created label: {name} (ID: {lid})")


# ---------------------------------------------------------------------------
# States
# ---------------------------------------------------------------------------

def cmd_states_list(_argv: List[str]):
    states = get_states()
    if not states:
        print("No states found.")
        return

    lines = [f"🗂️  States ({len(states)})", "━" * 22]
    by_type: Dict[str, List[dict]] = {}
    for s in states:
        st = s.get("type", "other")
        by_type.setdefault(st, []).append(s)

    for st in [STATE_TYPE_TRIAGE, STATE_TYPE_UNSTARTED, STATE_TYPE_STARTED, STATE_TYPE_COMPLETED, STATE_TYPE_CANCELLED, "other"]:
        bucket = by_type.get(st, [])
        if not bucket:
            continue
        emoji = STATE_EMOJI.get(st, "⚫")
        lines.append(f"\n{emoji} {st.upper()}")
        for s in bucket:
            name = s.get("name", "?")
            sid = s.get("id", "")
            lines.append(f"  • {name} ({sid})")
    print("\n".join(lines))


# ---------------------------------------------------------------------------
# Fragments
# ---------------------------------------------------------------------------

FRAGMENT_TYPE_EMOJI = {
    "person": "👤",
    "place": "📍",
    "credential": "🔑",
    "memory": "💭",
    "idea": "💡",
    "resource": "🔗",
    "journal": "📓",
}


def cmd_fragment_create(argv: List[str]):
    args = parse_args(argv)
    text = args.get("text")
    ftype = args.get("type")
    if not text:
        print("❌ --text is required", file=sys.stderr)
        sys.exit(1)
    if not ftype:
        print("❌ --type is required (person|place|credential|memory|idea|resource|journal)", file=sys.stderr)
        sys.exit(1)
    body: Dict[str, Any] = {"text": text, "type": ftype}
    if args.get("summary"):
        body["summary"] = args["summary"]
    if args.get("topics"):
        body["topics"] = [t.strip() for t in args["topics"].split(",")]
    if args.get("domains"):
        body["domains"] = [d.strip() for d in args["domains"].split(",")]
    source: Dict[str, str] = {}
    if args.get("room"):
        source["room"] = args["room"]
    if args.get("project"):
        source["linked_project_id"] = args["project"]
    if args.get("issue"):
        source["linked_issue_id"] = args["issue"]
    if source:
        body["source"] = source
    resp = api_post("/fragments", body)
    frag = resp.get("data", resp)
    emoji = FRAGMENT_TYPE_EMOJI.get(frag.get("type", ""), "📝")
    print(f"{emoji} Created {frag.get('type', '')} fragment: {frag['id']}")
    print(f"   {frag.get('text', '')[:80]}")


def cmd_fragment_list(argv: List[str]):
    args = parse_args(argv)
    params: Dict[str, Any] = {}
    if args.get("type"):
        params["type"] = args["type"]
    if args.get("domain"):
        params["domain"] = args["domain"]
    if args.get("topic"):
        params["topic"] = args["topic"]
    if args.get("search"):
        params["title_search"] = args["search"]
    if args.get("project"):
        params["project_id"] = args["project"]
    if args.get("limit"):
        params["limit"] = args["limit"]
    resp = api_get("/fragments", params=params)
    frags = resp.get("data", resp)
    if not frags:
        print("No fragments found.")
        return
    for frag in frags:
        emoji = FRAGMENT_TYPE_EMOJI.get(frag.get("type", ""), "📝")
        summary = frag.get("summary") or frag.get("text", "")[:60]
        topics = ", ".join(frag.get("topics") or [])
        topic_str = f"  [{topics}]" if topics else ""
        print(f"  {emoji} {frag['id'][:8]}  {frag.get('type', ''):12s} {summary}{topic_str}")


def cmd_fragment_get(argv: List[str]):
    if not argv:
        print("❌ Usage: fragment get <id>", file=sys.stderr)
        sys.exit(1)
    frag_id = argv[0]
    resp = api_get(f"/fragments/{frag_id}")
    frag = resp.get("data", resp)
    emoji = FRAGMENT_TYPE_EMOJI.get(frag.get("type", ""), "📝")
    print(f"{emoji} {frag.get('type', '')} fragment: {frag['id']}")
    print(f"   Text:    {frag.get('text', '')}")
    if frag.get("summary"):
        print(f"   Summary: {frag['summary']}")
    if frag.get("topics"):
        print(f"   Topics:  {', '.join(frag['topics'])}")
    if frag.get("domains"):
        print(f"   Domains: {', '.join(frag['domains'])}")
    if frag.get("entities"):
        for ent in frag["entities"]:
            print(f"   Entity:  {ent.get('name', '')} ({ent.get('type', '')})")
    if frag.get("source"):
        src = frag["source"]
        parts = []
        if src.get("room"):
            parts.append(f"room: {src['room']}")
        if src.get("linked_project_id"):
            parts.append(f"project: {src['linked_project_id'][:8]}")
        if src.get("linked_issue_id"):
            parts.append(f"issue: {src['linked_issue_id'][:8]}")
        if parts:
            print(f"   Source:  {', '.join(parts)}")


def cmd_fragment_delete(argv: List[str]):
    if not argv:
        print("❌ Usage: fragment delete <id>", file=sys.stderr)
        sys.exit(1)
    frag_id = argv[0]
    api_delete(f"/fragments/{frag_id}")
    print(f"🗑️  Deleted fragment {frag_id[:8]}")


def cmd_fragment_topics(argv: List[str]):
    resp = api_get("/fragments/topics")
    topics = resp.get("data", resp)
    if not topics:
        print("No topics yet.")
        return
    for t in topics:
        print(f"  {t['topic']:30s} ({t['count']})")


# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------

def cmd_help(_argv: List[str] = None):
    print("""📋 Life CLI — Task & Project Management

Issues:
  issue create --title "..." [--priority 0-4] [--label name] [--assignee me|id]
               [--project id] [--estimate N] [--due YYYY-MM-DD] [--type task|reference|idea]
  issue list   [--state-type started,unstarted] [--assignee me|id] [--label name]
               [--project id] [--overdue] [--priority 1,2] [--search "text"] [--limit N]
  issue get    <id>
  issue update <id> [--title "..."] [--priority N] [--state "Name"] [--due YYYY-MM-DD]
  issue delete <id>
  issue search "query"
  issue add-subtask <parent-id> --title "..." [--priority N]
  issue convert-to-project <id>
  issue batch-create --titles "item1" "item2" ...

Projects:
  project list   [--state planned|started|paused|completed|canceled]
  project create --name "..." [--description "..."] [--lead user-id]
  project get    <id>
  project update <id> [--state started] [--name "..."]
  project stalled

Fragments:
  fragment create --text "..." --type person|place|credential|memory|idea|resource|journal
                  [--summary "..."] [--topics a,b] [--domains a,b] [--room id] [--project id]
  fragment list   [--type person] [--domain "..."] [--topic "..."] [--search "..."] [--limit N]
  fragment get    <id>
  fragment delete <id>
  fragment topics

Summary:
  summary        Dashboard with overdue + due soon
  overdue        All overdue issues
  triage         Items waiting in triage

Bulk:
  reboot         Move all in-progress → backlog, show triage
  triage-all --action accept|decline

Rules:
  rules list
  rules test <rule-id> --issue <issue-id>

Other:
  notifications  [--mark-read]
  label list
  label create --name "..." [--color "#hex"]
  states list

Environment: TASKSTORE_URL, TASKSTORE_API_KEY, TASKSTORE_USER_ID""")


# ---------------------------------------------------------------------------
# Main dispatcher
# ---------------------------------------------------------------------------

ISSUE_SUBCOMMANDS = {
    "create": cmd_issue_create,
    "list": cmd_issue_list,
    "get": cmd_issue_get,
    "update": cmd_issue_update,
    "delete": cmd_issue_delete,
    "search": cmd_issue_search,
    "add-subtask": cmd_issue_add_subtask,
    "convert-to-project": cmd_issue_convert_to_project,
    "batch-create": cmd_issue_batch_create,
}

PROJECT_SUBCOMMANDS = {
    "list": cmd_project_list,
    "create": cmd_project_create,
    "get": cmd_project_get,
    "update": cmd_project_update,
    "stalled": cmd_project_stalled,
}

RULES_SUBCOMMANDS = {
    "list": cmd_rules_list,
    "test": cmd_rules_test,
}

LABEL_SUBCOMMANDS = {
    "list": cmd_label_list,
    "create": cmd_label_create,
}

STATES_SUBCOMMANDS = {
    "list": cmd_states_list,
}

FRAGMENT_SUBCOMMANDS = {
    "create": cmd_fragment_create,
    "list": cmd_fragment_list,
    "get": cmd_fragment_get,
    "delete": cmd_fragment_delete,
    "topics": cmd_fragment_topics,
}


def main():
    argv = sys.argv[1:]

    if not argv or argv[0] in ("-h", "--help", "help"):
        cmd_help()
        return

    top = argv[0]
    rest = argv[1:]

    if top == "issue":
        if not rest or rest[0] in ("-h", "--help"):
            print("Usage: issue <create|list|get|update|delete|search|add-subtask|convert-to-project|batch-create> ...")
            print("       issue <subcommand> --help  for subcommand options")
            return
        sub = rest[0]
        sub_argv = rest[1:]
        fn = ISSUE_SUBCOMMANDS.get(sub)
        if fn is None:
            print(f"❌ Unknown issue subcommand: {sub}", file=sys.stderr)
            print(f"   Available: {', '.join(ISSUE_SUBCOMMANDS)}", file=sys.stderr)
            sys.exit(1)
        fn(sub_argv)

    elif top == "project":
        if not rest or rest[0] in ("-h", "--help"):
            print("Usage: project <list|create|get|update|stalled> ...")
            return
        sub = rest[0]
        sub_argv = rest[1:]
        fn = PROJECT_SUBCOMMANDS.get(sub)
        if fn is None:
            print(f"❌ Unknown project subcommand: {sub}", file=sys.stderr)
            print(f"   Available: {', '.join(PROJECT_SUBCOMMANDS)}", file=sys.stderr)
            sys.exit(1)
        fn(sub_argv)

    elif top == "rules":
        if not rest or rest[0] in ("-h", "--help"):
            print("Usage: rules <list|test> ...")
            return
        sub = rest[0]
        sub_argv = rest[1:]
        fn = RULES_SUBCOMMANDS.get(sub)
        if fn is None:
            print(f"❌ Unknown rules subcommand: {sub}", file=sys.stderr)
            sys.exit(1)
        fn(sub_argv)

    elif top == "label":
        if not rest or rest[0] in ("-h", "--help"):
            print("Usage: label <list|create> ...")
            return
        sub = rest[0]
        sub_argv = rest[1:]
        fn = LABEL_SUBCOMMANDS.get(sub)
        if fn is None:
            print(f"❌ Unknown label subcommand: {sub}", file=sys.stderr)
            sys.exit(1)
        fn(sub_argv)

    elif top == "states":
        if not rest or rest[0] in ("-h", "--help"):
            print("Usage: states list")
            return
        sub = rest[0]
        sub_argv = rest[1:]
        fn = STATES_SUBCOMMANDS.get(sub)
        if fn is None:
            print(f"❌ Unknown states subcommand: {sub}", file=sys.stderr)
            sys.exit(1)
        fn(sub_argv)

    elif top == "fragment":
        if not rest or rest[0] in ("-h", "--help"):
            print("Usage: fragment <create|list|get|delete|topics> ...")
            print("       fragment <subcommand> --help  for subcommand options")
            return
        sub = rest[0]
        sub_argv = rest[1:]
        fn = FRAGMENT_SUBCOMMANDS.get(sub)
        if fn is None:
            print(f"❌ Unknown fragment subcommand: {sub}", file=sys.stderr)
            print(f"   Available: {', '.join(FRAGMENT_SUBCOMMANDS)}", file=sys.stderr)
            sys.exit(1)
        fn(sub_argv)

    elif top == "summary":
        cmd_summary(rest)
    elif top == "overdue":
        cmd_overdue(rest)
    elif top == "triage":
        cmd_triage(rest)
    elif top == "reboot":
        cmd_reboot(rest)
    elif top == "triage-all":
        cmd_triage_all(rest)
    elif top == "notifications":
        cmd_notifications(rest)
    else:
        print(f"❌ Unknown command: {top}. Run '--help' for usage.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
