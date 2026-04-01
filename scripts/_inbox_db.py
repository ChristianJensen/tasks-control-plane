"""SQLite data access layer for the Relay inbox."""

import json
import os
import sqlite3
from datetime import datetime, timezone

VALID_TRANSITIONS = {
    "new": {"triaging", "dismissed"},
    "triaging": {"actionable", "dismissed"},
    "actionable": {"promoted", "dismissed"},
    "promoted": set(),
    "dismissed": set(),
}


def init_db(cp_dir):
    """Create .relay/inbox.db if needed, return connection."""
    relay_dir = os.path.join(cp_dir, ".relay")
    os.makedirs(relay_dir, exist_ok=True)
    db_path = os.path.join(relay_dir, "inbox.db")
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS inbox_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            source_type TEXT NOT NULL,
            title TEXT NOT NULL,
            payload TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'new',
            triage_report TEXT,
            triage_session_id TEXT,
            triage_mode TEXT,
            promoted_to TEXT,
            received_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    # Migration: add triage_mode if missing (existing DBs)
    try:
        conn.execute("SELECT triage_mode FROM inbox_items LIMIT 0")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE inbox_items ADD COLUMN triage_mode TEXT")
    conn.commit()
    return conn


def _now():
    return datetime.now(timezone.utc).isoformat()


def _row_to_dict(row):
    if row is None:
        return None
    d = dict(row)
    for field in ("payload", "triage_report"):
        if d.get(field):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d


def create_item(conn, source, source_type, title, payload):
    now = _now()
    cur = conn.execute(
        "INSERT INTO inbox_items (source, source_type, title, payload, status, received_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'new', ?, ?)",
        (source, source_type, title, json.dumps(payload), now, now),
    )
    conn.commit()
    return _row_to_dict(
        conn.execute("SELECT * FROM inbox_items WHERE id = ?", (cur.lastrowid,)).fetchone()
    )


def list_items(conn, status=None):
    if status:
        rows = conn.execute(
            "SELECT * FROM inbox_items WHERE status = ? ORDER BY received_at DESC",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM inbox_items ORDER BY received_at DESC"
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_item(conn, item_id):
    row = conn.execute(
        "SELECT * FROM inbox_items WHERE id = ?", (int(item_id),)
    ).fetchone()
    return _row_to_dict(row)


def update_status(conn, item_id, new_status, **kwargs):
    item = get_item(conn, int(item_id))
    if not item:
        raise ValueError(f"Item {item_id} not found")
    current = item["status"]
    if new_status != "dismissed" and new_status not in VALID_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid transition: {current} -> {new_status}")
    updates = ["status = ?", "updated_at = ?"]
    params = [new_status, _now()]
    if "triage_report" in kwargs and kwargs["triage_report"] is not None:
        updates.append("triage_report = ?")
        params.append(json.dumps(kwargs["triage_report"]))
    if "promoted_to" in kwargs and kwargs["promoted_to"] is not None:
        updates.append("promoted_to = ?")
        params.append(kwargs["promoted_to"])
    if "triage_session_id" in kwargs and kwargs["triage_session_id"] is not None:
        updates.append("triage_session_id = ?")
        params.append(kwargs["triage_session_id"])
    if "triage_mode" in kwargs and kwargs["triage_mode"] is not None:
        updates.append("triage_mode = ?")
        params.append(kwargs["triage_mode"])
    params.append(int(item_id))
    conn.execute(f"UPDATE inbox_items SET {', '.join(updates)} WHERE id = ?", params)
    conn.commit()
    return get_item(conn, item_id)
