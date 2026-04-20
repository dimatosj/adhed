---
name: life
description: Manage tasks, projects, and life organization via the taskstore API. Use when user mentions tasks, projects, to-dos, work items, assignments, priorities, or asks about what to work on. Also handles triage, weekly review, and reboot flows.
allowed-tools: Bash(python3 /workspace/group/.claude/skills/life/life-cli.py *)
---

# Life Management — Task & Project System

ALL operations go through the CLI script. Never call the API directly.

## CLI Location

python3 /workspace/group/.claude/skills/life/life-cli.py <command> [args]

## Environment

Set TASKSTORE_URL, TASKSTORE_API_KEY, and TASKSTORE_USER_ID in the container environment.
The CLI reads these from env vars.

## Commands

### Issues
life-cli.py issue create --title "..." [--priority 0-4] [--label name] [--assignee user-id] [--project project-id] [--estimate N] [--due YYYY-MM-DD] [--type task|reference|idea]
life-cli.py issue list [--state-type started,unstarted] [--assignee me|user-id] [--label name] [--project project-id] [--overdue] [--priority 1,2] [--search "text"] [--estimate-lte N] [--limit N]
life-cli.py issue get <id>
life-cli.py issue update <id> [--title "..."] [--priority N] [--state "State Name"] [--assignee user-id] [--due YYYY-MM-DD]
life-cli.py issue delete <id>
life-cli.py issue search "query text"
life-cli.py issue add-subtask <parent-id> --title "..." [--priority N]
life-cli.py issue convert-to-project <id>
life-cli.py issue batch-create --titles "item1" "item2" "item3"

### Projects
life-cli.py project list [--state planned|started|paused|completed|canceled]
life-cli.py project create --name "..." [--description "..."] [--lead user-id]
life-cli.py project get <id>
life-cli.py project update <id> [--state started] [--name "..."]
life-cli.py project stalled

### Summary & Review
life-cli.py summary
life-cli.py overdue
life-cli.py triage

### Rules
life-cli.py rules list
life-cli.py rules test <rule-id> --issue <issue-id>

### Bulk Operations
life-cli.py reboot
life-cli.py triage-all --action accept|decline

### Notifications
life-cli.py notifications [--mark-read]

### Labels
life-cli.py label list
life-cli.py label create --name "..." [--color "#hex"]

### States
life-cli.py states list
