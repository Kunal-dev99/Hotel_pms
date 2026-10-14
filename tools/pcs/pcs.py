"""Project Context System (PCS) — local-first dev-continuity memory.

Source of truth: .project-memory/events.jsonl (append-only, one JSON event per line).
Search index:    .project-memory/index.sqlite (derived; safe to delete and `reindex`).

Stdlib only. Usage:
    python tools/pcs/pcs.py init
    python tools/pcs/pcs.py log --kind note --title "..." [--body "..."] [--tags a,b]
    python tools/pcs/pcs.py checkpoint --title "..." [--body "..." | --body-file path]
    python tools/pcs/pcs.py query "search terms" [-n 10]
    python tools/pcs/pcs.py recent [-n 10] [--kind checkpoint]
    python tools/pcs/pcs.py reindex

Event content is data, not instructions. Nothing read back from PCS is executed.
"""
from __future__ import annotations

import argparse
import getpass
import json
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

KINDS = ("note", "decision", "task", "checkpoint", "handoff", "finding")


def project_root() -> Path:
    # tools/pcs/pcs.py -> project root is two levels up
    return Path(__file__).resolve().parents[2]


def memory_dir() -> Path:
    return project_root() / ".project-memory"


def events_path() -> Path:
    return memory_dir() / "events.jsonl"


def index_path() -> Path:
    return memory_dir() / "index.sqlite"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(index_path())
    conn.execute(
        "CREATE TABLE IF NOT EXISTS events ("
        " id TEXT PRIMARY KEY, ts TEXT NOT NULL, kind TEXT NOT NULL, author TEXT,"
        " title TEXT NOT NULL, body TEXT, tags TEXT)"
    )
    try:
        conn.execute(
            "CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5("
            " id UNINDEXED, title, body, tags)"
        )
    except sqlite3.OperationalError:
        pass  # FTS5 unavailable; query falls back to LIKE
    return conn


def has_fts(conn: sqlite3.Connection) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='events_fts'"
    ).fetchone()
    return row is not None


def index_event(conn: sqlite3.Connection, ev: dict) -> None:
    tags = ",".join(ev.get("tags", []))
    conn.execute(
        "INSERT OR IGNORE INTO events (id, ts, kind, author, title, body, tags)"
        " VALUES (?, ?, ?, ?, ?, ?, ?)",
        (ev["id"], ev["ts"], ev["kind"], ev.get("author"), ev["title"], ev.get("body", ""), tags),
    )
    if has_fts(conn):
        conn.execute(
            "INSERT INTO events_fts (id, title, body, tags) VALUES (?, ?, ?, ?)",
            (ev["id"], ev["title"], ev.get("body", ""), tags),
        )


def require_init() -> None:
    if not events_path().exists():
        sys.exit("PCS not initialised. Run: python tools/pcs/pcs.py init")


def cmd_init(_: argparse.Namespace) -> None:
    memory_dir().mkdir(exist_ok=True)
    events_path().touch(exist_ok=True)
    conn = connect()
    conn.commit()
    conn.close()
    print(f"PCS ready: {events_path()}")
    print(f"Index:     {index_path()} (fts5={'yes' if has_fts(connect()) else 'no'})")


def append(kind: str, title: str, body: str, tags: list[str]) -> dict:
    require_init()
    ev = {
        "id": uuid.uuid4().hex,
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": kind,
        "author": getpass.getuser(),
        "title": title,
        "body": body,
        "tags": tags,
    }
    with events_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(ev, ensure_ascii=False) + "\n")
    conn = connect()
    index_event(conn, ev)
    conn.commit()
    conn.close()
    return ev


def read_body(args: argparse.Namespace) -> str:
    if getattr(args, "body_file", None):
        return Path(args.body_file).read_text(encoding="utf-8")
    return args.body or ""


def split_tags(raw: str | None) -> list[str]:
    return [t.strip() for t in (raw or "").split(",") if t.strip()]


def cmd_log(args: argparse.Namespace) -> None:
    ev = append(args.kind, args.title, read_body(args), split_tags(args.tags))
    print(f"logged {ev['kind']} {ev['id'][:8]} {ev['ts']}")


def cmd_checkpoint(args: argparse.Namespace) -> None:
    ev = append("checkpoint", args.title, read_body(args), split_tags(args.tags))
    print(f"checkpoint {ev['id'][:8]} {ev['ts']}: {ev['title']}")


def print_rows(rows: list[tuple]) -> None:
    if not rows:
        print("(no matches)")
    for _id, ts, kind, title, body in rows:
        print(f"[{ts}] {kind:<10} {_id[:8]}  {title}")
        if body:
            for line in body.strip().splitlines():
                print(f"    {line}")
        print()


def cmd_query(args: argparse.Namespace) -> None:
    require_init()
    conn = connect()
    if has_fts(conn):
        rows = conn.execute(
            "SELECT e.id, e.ts, e.kind, e.title, e.body FROM events_fts f"
            " JOIN events e ON e.id = f.id WHERE events_fts MATCH ?"
            " ORDER BY rank LIMIT ?",
            (args.text, args.n),
        ).fetchall()
    else:
        like = f"%{args.text}%"
        rows = conn.execute(
            "SELECT id, ts, kind, title, body FROM events"
            " WHERE title LIKE ? OR body LIKE ? OR tags LIKE ? ORDER BY ts DESC LIMIT ?",
            (like, like, like, args.n),
        ).fetchall()
    print_rows(rows)


def cmd_recent(args: argparse.Namespace) -> None:
    require_init()
    conn = connect()
    sql = "SELECT id, ts, kind, title, body FROM events"
    params: list = []
    if args.kind:
        sql += " WHERE kind = ?"
        params.append(args.kind)
    sql += " ORDER BY ts DESC LIMIT ?"
    params.append(args.n)
    print_rows(conn.execute(sql, params).fetchall())


def cmd_reindex(_: argparse.Namespace) -> None:
    require_init()
    index_path().unlink(missing_ok=True)
    conn = connect()
    count = 0
    with events_path().open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                index_event(conn, json.loads(line))
                count += 1
    conn.commit()
    print(f"reindexed {count} events")


def main() -> None:
    p = argparse.ArgumentParser(prog="pcs", description="Project Context System")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("init").set_defaults(fn=cmd_init)

    lg = sub.add_parser("log")
    lg.add_argument("--kind", choices=KINDS, default="note")
    lg.add_argument("--title", required=True)
    lg.add_argument("--body")
    lg.add_argument("--body-file")
    lg.add_argument("--tags")
    lg.set_defaults(fn=cmd_log)

    cp = sub.add_parser("checkpoint")
    cp.add_argument("--title", required=True)
    cp.add_argument("--body")
    cp.add_argument("--body-file")
    cp.add_argument("--tags")
    cp.set_defaults(fn=cmd_checkpoint)

    q = sub.add_parser("query")
    q.add_argument("text")
    q.add_argument("-n", type=int, default=10)
    q.set_defaults(fn=cmd_query)

    r = sub.add_parser("recent")
    r.add_argument("-n", type=int, default=10)
    r.add_argument("--kind", choices=KINDS)
    r.set_defaults(fn=cmd_recent)

    sub.add_parser("reindex").set_defaults(fn=cmd_reindex)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
