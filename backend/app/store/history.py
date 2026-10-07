"""Saved conversations: one SQLite file (Python's built-in sqlite3, no server).

Each answered question is stored with everything needed to show it again exactly as it was:
the answer, citations, diagram, every agent event and the full evidence, plus the repository
and commit it was asked about. The file lives in workspace/ (git-ignored), so analysed code
never leaves this machine.
"""

import json
import sqlite3
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS conversations (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    repo_name  TEXT NOT NULL,
    repo_root  TEXT NOT NULL,
    repo_commit TEXT,
    model      TEXT,
    question   TEXT NOT NULL,
    answer     TEXT NOT NULL,
    stopped    TEXT NOT NULL,
    rounds     INTEGER NOT NULL,
    seconds    REAL NOT NULL,
    citations  TEXT NOT NULL,   -- JSON
    diagram    TEXT,
    events     TEXT NOT NULL,   -- JSON list of {type, data}
    evidence   TEXT NOT NULL    -- JSON object id -> evidence
);
CREATE INDEX IF NOT EXISTS conversations_repo ON conversations (repo_root, id);
"""
SUMMARY_COLUMNS = "id, created_at, repo_name, repo_commit, question, stopped, rounds, seconds"


class HistoryStore:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        # A short-lived connection per call: the API answers from several threads.
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        return db

    def save(self, *, repo_name: str, repo_root: str, repo_commit: str | None, model: str, question: str,
             answer: str, stopped: str, rounds: int, seconds: float, citations: dict, diagram: str | None,
             events: list[dict], evidence: dict) -> int:
        with self._connect() as db:
            cur = db.execute(
                "INSERT INTO conversations (created_at, repo_name, repo_root, repo_commit, model, question, answer,"
                " stopped, rounds, seconds, citations, diagram, events, evidence)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (time.strftime("%Y-%m-%d %H:%M:%S"), repo_name, repo_root, repo_commit, model, question, answer,
                 stopped, rounds, seconds, json.dumps(citations), diagram, json.dumps(events, default=str),
                 json.dumps(evidence, default=str)),
            )
            return int(cur.lastrowid)

    def list(self, repo_root: str | None = None, limit: int = 50) -> list[dict]:
        """Newest first; only one repository's conversations when repo_root is given."""
        query = f"SELECT {SUMMARY_COLUMNS} FROM conversations"
        args: tuple = ()
        if repo_root is not None:
            query += " WHERE repo_root = ?"
            args = (repo_root,)
        query += " ORDER BY id DESC LIMIT ?"
        with self._connect() as db:
            return [dict(row) for row in db.execute(query, (*args, max(1, min(limit, 500))))]

    def get(self, conversation_id: int) -> dict | None:
        with self._connect() as db:
            row = db.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,)).fetchone()
        if row is None:
            return None
        record = dict(row)
        for key in ("citations", "events", "evidence"):
            record[key] = json.loads(record[key])
        return record

    def delete(self, conversation_id: int) -> bool:
        with self._connect() as db:
            return db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,)).rowcount > 0
