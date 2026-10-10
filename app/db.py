"""Database access: small connection pool + transaction helper.

Usage:
    with tx() as db:
        row = db.one("select * from patients where id=%s", [pid])

Placeholders are always `%s` (server-side bound parameters). Never format values into SQL.
Never write a literal percent sign in SQL text; pass LIKE patterns as parameters.
"""
from __future__ import annotations

import threading
from contextlib import contextmanager

from . import config

try:  # production preference
    import psycopg  # type: ignore
    from psycopg.rows import dict_row  # type: ignore

    BACKEND = "psycopg"
except Exception:  # pragma: no cover - depends on environment
    psycopg = None
    BACKEND = "libpq-ctypes"

from . import pq

DatabaseError = pq.DatabaseError
IntegrityError = pq.IntegrityError


class _PsycopgConn:  # pragma: no cover - not available in the build sandbox
    def __init__(self, dsn):
        self._c = psycopg.connect(dsn, autocommit=True, row_factory=dict_row)
        self._c.execute("SET TIME ZONE 'UTC'")
        self._c.execute("SET client_min_messages TO warning")

    @property
    def ok(self):
        return not self._c.closed

    @property
    def in_error(self):
        return self._c.info.transaction_status.name in ("INERROR", "UNKNOWN")

    def execute(self, sql, params=()):
        from psycopg.types.json import Jsonb  # type: ignore

        params = [Jsonb(p) if isinstance(p, (dict, list)) else p for p in (params or ())]
        try:
            cur = self._c.execute(sql, params or None)
        except psycopg.errors.IntegrityError as e:
            raise IntegrityError(str(e), e.sqlstate, getattr(e.diag, "constraint_name", None))
        except psycopg.Error as e:
            raise DatabaseError(str(e), getattr(e, "sqlstate", None))
        rows = cur.fetchall() if cur.description else []
        rows = [{k: (str(v) if v.__class__.__name__ == "UUID" else v) for k, v in r.items()} for r in rows]
        return pq.Result(rows, cur.rowcount)

    def close(self):
        self._c.close()


def _connect(dsn):
    if psycopg is not None:
        return _PsycopgConn(dsn)
    return pq.Connection(dsn)


class Pool:
    def __init__(self, dsn: str, size: int = 8):
        self.dsn = dsn
        self.size = size
        self._free: list = []
        self._lock = threading.Lock()
        self._sem = threading.BoundedSemaphore(size)

    def acquire(self):
        self._sem.acquire()
        with self._lock:
            while self._free:
                c = self._free.pop()
                if c.ok:
                    return c
                c.close()
        try:
            return _connect(self.dsn)
        except Exception:
            self._sem.release()
            raise

    def release(self, c, broken=False):
        try:
            if broken or not c.ok:
                c.close()
            else:
                with self._lock:
                    self._free.append(c)
        finally:
            self._sem.release()

    def close_all(self):
        with self._lock:
            for c in self._free:
                c.close()
            self._free.clear()


class DB:
    """Thin helper around a connection inside a transaction."""

    def __init__(self, conn):
        self.conn = conn

    def execute(self, sql, params=()):
        return self.conn.execute(sql, params)

    def all(self, sql, params=()):
        return self.conn.execute(sql, params).rows

    def one(self, sql, params=()):
        rows = self.conn.execute(sql, params).rows
        return rows[0] if rows else None

    def scalar(self, sql, params=()):
        r = self.one(sql, params)
        return next(iter(r.values())) if r else None


_pools: dict[str, Pool] = {}
_plock = threading.Lock()


def pool() -> Pool:
    dsn = config.database_url()
    with _plock:
        p = _pools.get(dsn)
        if p is None:
            p = _pools[dsn] = Pool(dsn, config.DB_POOL_SIZE)
        return p


@contextmanager
def tx():
    p = pool()
    c = p.acquire()
    broken = False
    try:
        c.execute("BEGIN")
        try:
            yield DB(c)
        except BaseException:
            try:
                c.execute("ROLLBACK")
            except Exception:
                broken = True
            raise
        else:
            c.execute("COMMIT")
    except DatabaseError:
        broken = broken or not c.ok
        raise
    finally:
        p.release(c, broken)
