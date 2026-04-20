# NanoClaw Integration

Connect ADHED to NanoClaw (or OpenClaw) so your container agents can manage tasks through chat.

## What you get

- A `life-cli.py` script that wraps the ADHED REST API
- A `SKILL.md` that tells agents how to use it
- Task creation, listing, state changes, projects, rules — all via chat

## Setup

### 1. Copy skills into your NanoClaw project

```bash
cp -r integrations/nanoclaw/life/ /path/to/your/nanoclaw/container/skills/life/
```

### 2. Add environment variables

Add these to your NanoClaw `.env` (values from ADHED's `.adhed-credentials`):

```bash
TASKSTORE_URL=http://host.docker.internal:8100
TASKSTORE_API_KEY=<API_KEY from .adhed-credentials>
TASKSTORE_USER_ID=<USER_ID from .adhed-credentials>
TASKSTORE_TEAM_ID=<TEAM_ID from .adhed-credentials>
```

### 3. Wire container-runner to pass env vars

Your `src/container-runner.ts` needs to pass `TASKSTORE_*` environment variables into containers. If your fork does not already do this, see [qwibitai/nanoclaw#1867](https://github.com/qwibitai/nanoclaw/pull/1867) for the upstream env passthrough implementation.

### 4. Rebuild

```bash
cd /path/to/your/nanoclaw
npm run build
./container/build.sh
```

### 5. Restart NanoClaw

```bash
# macOS
launchctl kickstart -k gui/$(id -u)/com.nanoclaw

# Linux
systemctl --user restart nanoclaw
```

### 6. Create a dedicated Tasks room

In your messaging channel (WhatsApp, Telegram, Slack, etc.), create a dedicated group or room for task management. This gives the agent clear context that messages in this room are task-related.

## Usage

Once configured, you can talk to your agent in the Tasks room:

- "Add a task: call the dentist, priority 2"
- "What's in progress?"
- "Move 'call the dentist' to done"
- "Show me overdue items"
- "Create a project for kitchen renovation"

The agent calls `life-cli.py` under the hood — it never improvises raw API calls.

## File Reference

| File | Purpose |
|------|---------|
| `life/life-cli.py` | Deterministic CLI wrapping the ADHED API |
| `life/SKILL.md` | Agent instructions: commands, allowed tools, usage patterns |
