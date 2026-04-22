# dev-dashboard Integration

CLI tool for managing ADHED from [dev-dashboard](https://github.com/you/dev-dashboard) agents and workflows.

## What This Is

A bash CLI that wraps the full ADHED REST API. Designed for dev-dashboard's EM and dev agents to create, assign, track, and manage issues without raw curl commands. Complements (does not replace) the NanoClaw `life-cli.py` integration.

## Requirements

- bash 4+
- curl
- jq

## Setup

1. Copy `adhed` to a directory in your PATH:
   ```bash
   cp adhed ~/.local/bin/adhed
   chmod +x ~/.local/bin/adhed
   ```

2. Configure credentials (one of):
   - **Config file** (`~/.config/dev-dashboard/config.json`):
     ```json
     {
       "adhed_url": "http://localhost:8100",
       "adhed_api_key": "adhed_...",
       "adhed_team_id": "your-team-uuid",
       "adhed_user_id": "your-user-uuid"
     }
     ```
   - **Environment variables**: `ADHED_URL`, `ADHED_API_KEY`, `ADHED_TEAM_ID`, `ADHED_USER_ID`
   - **CLI flags**: `--url`, `--api-key`, `--team-id`, `--user-id`

   Priority: flags > env vars > config file.

3. Test: `adhed health`

## Usage

```bash
adhed --help               # Full command reference
adhed issues list           # List all issues
adhed issues create "title" # Create an issue
adhed summary               # Dashboard stats
```

Run any command with `--json` for raw API output.

## Commands

| Command | Description |
|---------|-------------|
| `adhed health` | Check ADHED connection |
| `adhed issues list\|create\|show\|update\|delete` | Issue CRUD |
| `adhed issues batch-create\|batch-update` | Batch operations (stdin JSON) |
| `adhed issues convert <id>` | Promote issue to project |
| `adhed issues comment <id> "text"` | Add comment |
| `adhed projects list\|create\|update` | Project management |
| `adhed labels list\|create\|delete` | Label management |
| `adhed states list\|create` | Workflow state management |
| `adhed rules list\|create\|update\|delete` | Rules engine management |
| `adhed comments list\|create <issue-id>` | Comment management |
| `adhed audit` | View audit log |
| `adhed notifications` | View notifications |
| `adhed fragments list\|create` | Knowledge fragment management |
| `adhed users list` | List team members |
| `adhed teams show\|update` | Team configuration |
| `adhed summary` | Dashboard summary stats |
