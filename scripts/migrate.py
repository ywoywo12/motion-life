"""Apply SQL migrations in order. Usage: python -m scripts.migrate [--reset]

--reset drops and recreates the public schema (refused when ML_ENV=production).
"""
import sys
from pathlib import Path

from app import config, db

MIG_DIR = config.ROOT / "migrations"


def run(reset: bool = False, quiet: bool = False):
    p = db.pool()
    c = p.acquire()
    try:
        if reset:
            if config.IS_PROD:
                raise SystemExit("refusing --reset in production")
            c.execute("DROP SCHEMA IF EXISTS public CASCADE")
            c.execute("CREATE SCHEMA public")
        c.execute("CREATE TABLE IF NOT EXISTS schema_migrations (name text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
        done = {r["name"] for r in c.execute("SELECT name FROM schema_migrations").rows}
        for f in sorted(Path(MIG_DIR).glob("*.sql")):
            if f.name in done:
                continue
            sql = f.read_text(encoding="utf-8")
            sql = sql.replace("CREATE TABLE schema_migrations (", "CREATE TABLE IF NOT EXISTS schema_migrations (")
            c.execute("BEGIN")
            try:
                _exec_script(c, sql)
                c.execute("INSERT INTO schema_migrations(name) VALUES (%s)", [f.name])
                c.execute("COMMIT")
            except Exception:
                c.execute("ROLLBACK")
                raise
            if not quiet:
                print("applied", f.name)
    finally:
        p.release(c)


def _exec_script(c, sql: str):
    """Split on statement boundaries while respecting $$ bodies and quotes."""
    stmts, buf, i, n = [], [], 0, len(sql)
    in_dollar = in_quote = in_comment = False
    while i < n:
        ch = sql[i]
        if in_comment:
            buf.append(ch)
            if ch == "\n":
                in_comment = False
            i += 1
            continue
        if not in_dollar and not in_quote and sql.startswith("--", i):
            in_comment = True
            i += 1
            buf.append(ch)
            continue
        if not in_quote and sql.startswith("$$", i):
            in_dollar = not in_dollar
            buf.append("$$")
            i += 2
            continue
        if not in_dollar and ch == "'":
            in_quote = not in_quote
        if ch == ";" and not in_dollar and not in_quote:
            s = "".join(buf).strip()
            if s and not all(l.strip().startswith("--") or not l.strip() for l in s.splitlines()):
                stmts.append(s)
            buf = []
        else:
            buf.append(ch)
        i += 1
    s = "".join(buf).strip()
    if s and not all(l.strip().startswith("--") or not l.strip() for l in s.splitlines()):
        stmts.append(s)
    for s in stmts:
        c.execute(s)


if __name__ == "__main__":
    run(reset="--reset" in sys.argv)
