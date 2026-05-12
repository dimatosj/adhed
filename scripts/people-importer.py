#!/usr/bin/env python3
"""Quick one-off UI for reviewing and importing people fragments from Obsidian."""

import json
import os
import sys
from pathlib import Path

import requests
import yaml
from flask import Flask, jsonify, render_template_string

PEOPLE_DIR = Path(os.environ.get("PEOPLE_DIR", os.path.expanduser("~/Obsidian/Vault/3-Resources/people")))
RESOURCES_DIR = Path(os.environ.get("RESOURCES_DIR", os.path.expanduser("~/Obsidian/Vault/3-Resources")))
ADHED_URL = os.environ.get("ADHED_URL", "http://localhost:8100")
ADHED_API_KEY = os.environ.get("ADHED_API_KEY", "")
ADHED_TEAM_ID = os.environ.get("ADHED_TEAM_ID", "")
ADHED_USER_ID = os.environ.get("ADHED_USER_ID", "")

app = Flask(__name__)


def resolve_note(note_id: str) -> dict | None:
    path = RESOURCES_DIR / f"{note_id}.md"
    if not path.exists():
        for p in RESOURCES_DIR.rglob(f"{note_id}.md"):
            path = p
            break
        else:
            return None
    text = path.read_text()
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {"id": note_id, "summary": "", "topics": [], "body": text.strip()}
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        meta = {}
    body = parts[2].strip()
    return {
        "id": note_id,
        "summary": meta.get("summary", ""),
        "topics": meta.get("topics", []),
        "type": meta.get("type", ""),
        "source": meta.get("source", ""),
        "body": body[:500] + ("..." if len(body) > 500 else ""),
    }


def load_people():
    people = []
    for f in sorted(PEOPLE_DIR.glob("*.md")):
        text = f.read_text()
        parts = text.split("---", 2)
        if len(parts) < 3:
            continue
        try:
            meta = yaml.safe_load(parts[1])
        except yaml.YAMLError:
            continue
        if not meta or meta.get("type") != "person":
            continue

        note_ids = meta.get("notes", [])
        resolved_notes = []
        for nid in note_ids:
            note = resolve_note(nid)
            if note:
                resolved_notes.append(note)

        people.append({
            "file": f.name,
            "name": meta.get("name", ""),
            "first_name": meta.get("first_name", ""),
            "last_name": meta.get("last_name", ""),
            "category": meta.get("category", ""),
            "note_count": len(note_ids),
            "notes": resolved_notes,
        })
    return people


def headers():
    return {
        "X-API-Key": ADHED_API_KEY,
        "X-User-Id": ADHED_USER_ID,
        "Content-Type": "application/json",
    }


HTML = """
<!DOCTYPE html>
<html>
<head>
<title>People → ADHED Importer</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, system-ui, sans-serif; background: #0d1117; color: #c9d1d9; padding: 24px; }
  h1 { font-size: 20px; margin-bottom: 8px; color: #f0f6fc; }
  .stats { color: #8b949e; font-size: 14px; margin-bottom: 20px; }
  .controls { margin-bottom: 16px; display: flex; gap: 12px; align-items: center; }
  .controls input { background: #161b22; border: 1px solid #30363d; color: #c9d1d9; padding: 6px 12px; border-radius: 6px; font-size: 14px; width: 260px; }
  .controls button { padding: 6px 16px; border-radius: 6px; border: 1px solid #30363d; font-size: 14px; cursor: pointer; }
  .btn-import { background: #238636; color: #fff; border-color: #238636; }
  .btn-import:hover { background: #2ea043; }
  .btn-import:disabled { background: #1a1e24; color: #484f58; border-color: #30363d; cursor: default; }

  .person-card { border: 1px solid #21262d; border-radius: 8px; margin-bottom: 8px; background: #161b22; }
  .person-card.removed { opacity: 0.3; }
  .person-card.imported { border-color: #238636; }
  .person-header { display: flex; align-items: center; padding: 10px 14px; cursor: pointer; gap: 12px; }
  .person-header:hover { background: #1c2128; }
  .person-name { font-weight: 600; flex: 1; font-size: 15px; }
  .person-name .note-count { color: #8b949e; font-weight: 400; font-size: 13px; margin-left: 8px; }
  .person-file { color: #484f58; font-size: 12px; margin-right: 12px; }
  .chevron { color: #484f58; font-size: 12px; transition: transform 0.15s; margin-right: 4px; }
  .chevron.open { transform: rotate(90deg); }
  .remove-btn { background: none; border: 1px solid #f8514966; color: #f85149; padding: 3px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }
  .remove-btn:hover { background: #f8514922; }
  .restore-btn { background: none; border: 1px solid #30363d; color: #8b949e; padding: 3px 10px; border-radius: 4px; cursor: pointer; font-size: 12px; }

  .notes-panel { display: none; border-top: 1px solid #21262d; padding: 0 14px 10px; }
  .notes-panel.open { display: block; }
  .note-item { padding: 10px 0; border-bottom: 1px solid #21262d; }
  .note-item:last-child { border-bottom: none; }
  .note-summary { color: #e6edf3; font-size: 14px; margin-bottom: 4px; }
  .note-topics { margin-bottom: 6px; }
  .note-topics span { display: inline-block; background: #1f6feb33; color: #58a6ff; font-size: 11px; padding: 1px 8px; border-radius: 10px; margin-right: 4px; margin-bottom: 2px; }
  .note-body { color: #8b949e; font-size: 13px; line-height: 1.5; white-space: pre-wrap; max-height: 150px; overflow-y: auto; background: #0d1117; border-radius: 4px; padding: 8px; margin-top: 6px; }
  .note-meta { color: #484f58; font-size: 11px; }
  .no-notes { color: #484f58; font-style: italic; padding: 8px 0; }

  .toast { position: fixed; top: 20px; right: 20px; background: #238636; color: white; padding: 12px 20px; border-radius: 8px; font-size: 14px; display: none; z-index: 100; }
  .toast.error { background: #da3633; }
</style>
</head>
<body>

<h1>People → ADHED Fragment Importer</h1>
<div class="stats" id="stats">Loading...</div>

<div class="controls">
  <input type="text" id="search" placeholder="Filter by name..." oninput="filterList()">
  <button class="btn-import" id="importBtn" onclick="importPeople()">Import to ADHED</button>
</div>

<div id="list"></div>

<div class="toast" id="toast"></div>

<script>
let people = [];
let removed = new Set();
let imported = new Set();
let expanded = new Set();

async function load() {
  document.getElementById('stats').textContent = 'Loading people and resolving notes...';
  const resp = await fetch('/api/people');
  people = await resp.json();
  updateStats();
  renderList();
}

function updateStats() {
  const active = people.length - removed.size;
  document.getElementById('stats').textContent =
    `${people.length} total · ${removed.size} removed · ${active} will be imported` +
    (imported.size ? ` · ${imported.size} imported` : '');
  document.getElementById('importBtn').disabled = imported.size > 0;
  if (imported.size > 0) {
    document.getElementById('importBtn').textContent = `Imported ${imported.size} people`;
  }
}

function renderList() {
  const search = document.getElementById('search').value.toLowerCase();
  const list = document.getElementById('list');
  list.innerHTML = people
    .map((p, idx) => ({p, idx}))
    .filter(({p}) => !search || p.name.toLowerCase().includes(search))
    .map(({p, idx}) => {
      const isRemoved = removed.has(idx);
      const isImported = imported.has(idx);
      const isOpen = expanded.has(idx);
      const notes = p.notes || [];

      let notesHtml = '';
      if (notes.length === 0) {
        notesHtml = '<div class="no-notes">No linked notes</div>';
      } else {
        notesHtml = notes.map(n => `
          <div class="note-item">
            <div class="note-summary">${esc(n.summary || '(no summary)')}</div>
            ${n.topics && n.topics.length ? `<div class="note-topics">${n.topics.map(t => `<span>${esc(t)}</span>`).join('')}</div>` : ''}
            <div class="note-meta">${esc(n.type || '')} · ${esc(n.source || '')} · ${esc(n.id)}</div>
            ${n.body ? `<div class="note-body">${esc(n.body)}</div>` : ''}
          </div>
        `).join('');
      }

      return `
        <div class="person-card ${isRemoved ? 'removed' : ''} ${isImported ? 'imported' : ''}">
          <div class="person-header" onclick="toggle(${idx})">
            <span class="chevron ${isOpen ? 'open' : ''}">▶</span>
            <span class="person-name">
              ${esc(p.name)}
              <span class="note-count">${notes.length} note${notes.length !== 1 ? 's' : ''}</span>
            </span>
            <span class="person-file">${esc(p.file)}</span>
            ${isRemoved
              ? `<button class="restore-btn" onclick="event.stopPropagation(); restore(${idx})">restore</button>`
              : `<button class="remove-btn" onclick="event.stopPropagation(); remove(${idx})">remove</button>`}
          </div>
          <div class="notes-panel ${isOpen ? 'open' : ''}">${notesHtml}</div>
        </div>`;
    }).join('');
}

function toggle(idx) { expanded.has(idx) ? expanded.delete(idx) : expanded.add(idx); renderList(); }
function remove(idx) { removed.add(idx); updateStats(); renderList(); }
function restore(idx) { removed.delete(idx); updateStats(); renderList(); }
function filterList() { renderList(); }

function esc(s) {
  if (!s) return '';
  const d = document.createElement('div');
  d.textContent = s;
  return d.innerHTML;
}

function toast(msg, isError) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.className = 'toast' + (isError ? ' error' : '');
  t.style.display = 'block';
  setTimeout(() => t.style.display = 'none', 4000);
}

async function importPeople() {
  const toImport = people.filter((_, i) => !removed.has(i));
  if (!toImport.length) { toast('Nothing to import', true); return; }
  document.getElementById('importBtn').disabled = true;
  document.getElementById('importBtn').textContent = `Importing ${toImport.length}...`;

  const resp = await fetch('/api/import', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({people: toImport}),
  });
  const result = await resp.json();

  if (result.error) {
    toast(result.error, true);
    document.getElementById('importBtn').disabled = false;
    document.getElementById('importBtn').textContent = 'Import to ADHED';
    return;
  }

  toImport.forEach((p) => {
    const idx = people.indexOf(p);
    imported.add(idx);
  });
  toast(`Imported ${result.imported} people as fragments`);
  updateStats();
  renderList();
}

load();
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/people")
def api_people():
    return jsonify(load_people())


@app.route("/api/import", methods=["POST"])
def api_import():
    from flask import request
    data = request.json
    people_list = data.get("people", [])

    if not ADHED_API_KEY:
        return jsonify({"error": "ADHED_API_KEY not set"}), 400

    imported = 0
    errors = []
    for p in people_list:
        all_topics = set()
        for n in p.get("notes", []):
            for t in (n.get("topics") or []):
                all_topics.add(t)

        note_summaries = [n["summary"] for n in p.get("notes", []) if n.get("summary")]
        text = p["name"]
        if note_summaries:
            text += "\n\n" + "\n".join(f"- {s}" for s in note_summaries)

        fragment = {
            "text": text,
            "type": "person",
            "summary": p["name"],
            "topics": sorted(all_topics)[:3],
            "entities": [{"name": p["name"], "type": "PERSON", "role": "subject"}],
            "source": {
                "room": "obsidian-import",
                "unresolved_reference": f"obsidian://people/{p['file']}",
            },
        }
        try:
            resp = requests.post(
                f"{ADHED_URL}/api/v1/teams/{ADHED_TEAM_ID}/fragments",
                headers=headers(),
                json=fragment,
                timeout=10,
            )
            if resp.status_code == 201:
                imported += 1
            else:
                errors.append(f"{p['name']}: {resp.status_code} {resp.text[:100]}")
        except Exception as e:
            errors.append(f"{p['name']}: {e}")

    result = {"imported": imported, "total": len(people_list)}
    if errors:
        result["errors"] = errors[:10]
    return jsonify(result)


if __name__ == "__main__":
    if not ADHED_API_KEY:
        print("Set ADHED_API_KEY, ADHED_TEAM_ID, ADHED_USER_ID env vars", file=sys.stderr)
        print(f"  export ADHED_URL={ADHED_URL}", file=sys.stderr)
        print("  export ADHED_API_KEY=adhed_...", file=sys.stderr)
        print(f"  export ADHED_TEAM_ID=...", file=sys.stderr)
        print(f"  export ADHED_USER_ID=...", file=sys.stderr)
        sys.exit(1)
    print(f"Loading people from {PEOPLE_DIR}")
    print(f"Resolving notes from {RESOURCES_DIR}")
    print(f"ADHED target: {ADHED_URL}")
    print(f"Open http://localhost:5111")
    app.run(port=5111, debug=False)
