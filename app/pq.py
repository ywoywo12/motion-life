"""Minimal PostgreSQL client built on the official libpq C library (via ctypes).

Why: in the build sandbox no Python PostgreSQL driver could be installed.
libpq handles authentication (SCRAM), TLS and the wire protocol; this module only
wraps PQexecParams with *server-side* parameter binding (no string interpolation),
so SQL injection protection is identical to psycopg's.

In production, if `psycopg` (v3) is installed, `app.db` uses it instead.
"""
from __future__ import annotations

import ctypes
import ctypes.util
import datetime as _dt
import json
import re
import uuid
from decimal import Decimal

_lib_path = ctypes.util.find_library("pq") or "libpq.so.5"
_pq = ctypes.CDLL(_lib_path)

_pq.PQconnectdb.argtypes = [ctypes.c_char_p]
_pq.PQconnectdb.restype = ctypes.c_void_p
_pq.PQstatus.argtypes = [ctypes.c_void_p]
_pq.PQstatus.restype = ctypes.c_int
_pq.PQerrorMessage.argtypes = [ctypes.c_void_p]
_pq.PQerrorMessage.restype = ctypes.c_char_p
_pq.PQfinish.argtypes = [ctypes.c_void_p]
_pq.PQfinish.restype = None
_pq.PQexecParams.argtypes = [
    ctypes.c_void_p, ctypes.c_char_p, ctypes.c_int, ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_char_p), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int,
]
_pq.PQexecParams.restype = ctypes.c_void_p
_pq.PQexec.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
_pq.PQexec.restype = ctypes.c_void_p
_pq.PQresultStatus.argtypes = [ctypes.c_void_p]
_pq.PQresultStatus.restype = ctypes.c_int
_pq.PQresultErrorField.argtypes = [ctypes.c_void_p, ctypes.c_int]
_pq.PQresultErrorField.restype = ctypes.c_char_p
_pq.PQresultErrorMessage.argtypes = [ctypes.c_void_p]
_pq.PQresultErrorMessage.restype = ctypes.c_char_p
_pq.PQntuples.argtypes = [ctypes.c_void_p]
_pq.PQntuples.restype = ctypes.c_int
_pq.PQnfields.argtypes = [ctypes.c_void_p]
_pq.PQnfields.restype = ctypes.c_int
_pq.PQfname.argtypes = [ctypes.c_void_p, ctypes.c_int]
_pq.PQfname.restype = ctypes.c_char_p
_pq.PQftype.argtypes = [ctypes.c_void_p, ctypes.c_int]
_pq.PQftype.restype = ctypes.c_uint
_pq.PQgetvalue.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
_pq.PQgetvalue.restype = ctypes.c_void_p
_pq.PQgetlength.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
_pq.PQgetlength.restype = ctypes.c_int
_pq.PQgetisnull.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
_pq.PQgetisnull.restype = ctypes.c_int
_pq.PQcmdTuples.argtypes = [ctypes.c_void_p]
_pq.PQcmdTuples.restype = ctypes.c_char_p
_pq.PQclear.argtypes = [ctypes.c_void_p]
_pq.PQclear.restype = None
_pq.PQtransactionStatus.argtypes = [ctypes.c_void_p]
_pq.PQtransactionStatus.restype = ctypes.c_int

CONNECTION_OK = 0
PGRES_COMMAND_OK = 1
PGRES_TUPLES_OK = 2
PG_DIAG_SQLSTATE = ord("C")
PG_DIAG_CONSTRAINT_NAME = ord("n")
PQTRANS_INERROR = 3
PQTRANS_UNKNOWN = 4


class DatabaseError(Exception):
    def __init__(self, message: str, sqlstate: str | None = None, constraint: str | None = None):
        super().__init__(message)
        self.sqlstate = sqlstate
        self.constraint = constraint


class IntegrityError(DatabaseError):
    pass


def _parse_ts(s: str):
    # e.g. 2026-10-10 12:30:01.123456+03 / +03:30
    s = s.replace(" ", "T", 1)
    m = re.match(r"^(.*[T\d:.]+)([+-]\d\d)(:?\d\d)?$", s)
    if m and m.group(3) is None:
        s = m.group(1) + m.group(2) + ":00"
    return _dt.datetime.fromisoformat(s)


_CONVERTERS = {
    16: lambda s: s == "t",
    20: int, 21: int, 23: int, 26: int,
    700: float, 701: float,
    1700: Decimal,
    114: json.loads, 3802: json.loads,
    2950: str,
    1082: _dt.date.fromisoformat,
    1114: lambda s: _dt.datetime.fromisoformat(s.replace(" ", "T", 1)),
    1184: _parse_ts,
}


def _adapt(v):
    if v is None:
        return None
    if isinstance(v, bool):
        return b"t" if v else b"f"
    if isinstance(v, (dict, list)):
        return json.dumps(v, ensure_ascii=False, default=str).encode()
    if isinstance(v, (_dt.datetime, _dt.date)):
        return v.isoformat().encode()
    if isinstance(v, uuid.UUID):
        return str(v).encode()
    return str(v).encode()


_PLACEHOLDER = re.compile(r"%s")


def _to_dollar(sql: str) -> str:
    n = 0

    def rep(_m):
        nonlocal n
        n += 1
        return f"${n}"

    out = _PLACEHOLDER.sub(rep, sql)
    return out.replace("%%", "%")


class Result:
    def __init__(self, rows, rowcount):
        self.rows = rows
        self.rowcount = rowcount


class Connection:
    def __init__(self, dsn: str):
        self._c = _pq.PQconnectdb(dsn.encode())
        if _pq.PQstatus(self._c) != CONNECTION_OK:
            msg = _pq.PQerrorMessage(self._c).decode(errors="replace")
            _pq.PQfinish(self._c)
            self._c = None
            raise DatabaseError("connection failed: " + msg.strip())
        self.execute("SET client_encoding TO 'UTF8'")
        self.execute("SET TIME ZONE 'UTC'")
        self.execute("SET client_min_messages TO warning")

    @property
    def ok(self) -> bool:
        return bool(self._c) and _pq.PQstatus(self._c) == CONNECTION_OK

    @property
    def in_error(self) -> bool:
        return _pq.PQtransactionStatus(self._c) in (PQTRANS_INERROR, PQTRANS_UNKNOWN)

    def execute(self, sql: str, params=()) -> Result:
        if not self._c:
            raise DatabaseError("connection closed")
        params = list(params or ())
        if params:
            q = _to_dollar(sql).encode()
            arr = (ctypes.c_char_p * len(params))(*[_adapt(p) for p in params])
            res = _pq.PQexecParams(self._c, q, len(params), None, arr, None, None, 0)
        else:
            res = _pq.PQexecParams(self._c, sql.encode(), 0, None, None, None, None, 0)
        if not res:
            raise DatabaseError(_pq.PQerrorMessage(self._c).decode(errors="replace"))
        try:
            st = _pq.PQresultStatus(res)
            if st not in (PGRES_COMMAND_OK, PGRES_TUPLES_OK):
                msg = (_pq.PQresultErrorMessage(res) or b"").decode(errors="replace").strip()
                code = _pq.PQresultErrorField(res, PG_DIAG_SQLSTATE)
                code = code.decode() if code else None
                cons = _pq.PQresultErrorField(res, PG_DIAG_CONSTRAINT_NAME)
                cons = cons.decode() if cons else None
                cls = IntegrityError if code and code.startswith("23") else DatabaseError
                raise cls(msg, code, cons)
            rows = []
            if st == PGRES_TUPLES_OK:
                nf = _pq.PQnfields(res)
                names = [_pq.PQfname(res, i).decode() for i in range(nf)]
                types = [_pq.PQftype(res, i) for i in range(nf)]
                for r in range(_pq.PQntuples(res)):
                    row = {}
                    for i in range(nf):
                        if _pq.PQgetisnull(res, r, i):
                            row[names[i]] = None
                            continue
                        ln = _pq.PQgetlength(res, r, i)
                        raw = ctypes.string_at(_pq.PQgetvalue(res, r, i), ln).decode()
                        conv = _CONVERTERS.get(types[i])
                        row[names[i]] = conv(raw) if conv else raw
                    rows.append(row)
            ct = _pq.PQcmdTuples(res)
            rowcount = int(ct) if ct else len(rows)
            return Result(rows, rowcount)
        finally:
            _pq.PQclear(res)

    def close(self):
        if self._c:
            _pq.PQfinish(self._c)
            self._c = None
