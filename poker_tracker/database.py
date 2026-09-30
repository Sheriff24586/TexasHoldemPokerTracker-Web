from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional


class TrackerDB:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.conn = sqlite3.connect(self.path)
        self.conn.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self):
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                name TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                hand_number INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT NOT NULL,
                state_json TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                hand_number INTEGER NOT NULL,
                sequence_number INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                player_name TEXT NOT NULL,
                street TEXT NOT NULL,
                action TEXT NOT NULL,
                amount INTEGER NOT NULL,
                pot_before INTEGER NOT NULL,
                pot_after INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY(session_id) REFERENCES sessions(id)
            );
            """
        )
        self.conn.commit()

    def new_session(self, name: str = "Poker Session") -> int:
        cur = self.conn.execute(
            "INSERT INTO sessions(created_at, name) VALUES (?, ?)",
            (datetime.now().isoformat(timespec="seconds"), name),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def save_snapshot(self, session_id: int, state: dict):
        self.conn.execute(
            """
            INSERT INTO snapshots(session_id, hand_number, created_at, status, state_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                session_id,
                int(state["hand_number"]),
                datetime.now().isoformat(timespec="seconds"),
                state["hand_status"],
                json.dumps(state),
            ),
        )
        self.conn.commit()
    def record_action(
        self,
        session_id: int,
        hand_number: int,
        sequence_number: int,
        player_id: int,
        player_name: str,
        street: str,
        action: str,
        amount: int,
        pot_before: int,
        pot_after: int,
    ):
        self.conn.execute(
            """
            INSERT INTO actions(
                session_id,
                hand_number,
                sequence_number,
                player_id,
                player_name,
                street,
                action,
                amount,
                pot_before,
                pot_after,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                hand_number,
                sequence_number,
                player_id,
                player_name,
                street,
                action,
                amount,
                pot_before,
                pot_after,
                datetime.now().isoformat(timespec="seconds"),
            ),
        )
        self.conn.commit()
    def latest_snapshot(self, session_id: int) -> Optional[dict]:
        row = self.conn.execute(
            """
            SELECT state_json FROM snapshots
            WHERE session_id=?
            ORDER BY id DESC LIMIT 1
            """,
            (session_id,),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def session_summaries(self) -> List[tuple]:
        return self.conn.execute(
            """
            SELECT s.id, s.name, s.created_at,
                   COALESCE(MAX(sn.hand_number), 0)
            FROM sessions s
            LEFT JOIN snapshots sn ON sn.session_id=s.id
            GROUP BY s.id
            ORDER BY s.id DESC
            """
        ).fetchall()

    def close(self):
        self.conn.close()

    def action_history(self, session_id: int) -> List[tuple]:
        return self.conn.execute(
            """
            SELECT
                hand_number,
                sequence_number,
                player_name,
                street,
                action,
                amount,
                pot_before,
                pot_after,
                created_at
            FROM actions
            WHERE session_id = ?
            ORDER BY hand_number ASC, sequence_number ASC, id ASC
            """,
        (session_id,),
    ).fetchall()