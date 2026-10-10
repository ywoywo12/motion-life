"""Read access to published questionnaires and catalogs (cached per published version)."""
from __future__ import annotations

import threading

from ..errors import NotFound

_cache: dict = {}
_lock = threading.Lock()


def questionnaire(db, code: str) -> dict:
    """Returns the currently published questionnaire version with its question definitions."""
    v = db.one(
        """SELECT qv.id, qv.version, qv.definition, q.code, q.name FROM questionnaire_versions qv
           JOIN questionnaires q ON q.id = qv.questionnaire_id
           WHERE q.code=%s AND qv.status='PUBLISHED' ORDER BY qv.version DESC LIMIT 1""", [code])
    if not v:
        raise NotFound("الاستبيان غير منشور")
    key = ("q", v["id"])
    with _lock:
        if key in _cache:
            return _cache[key]
    qs = db.all("SELECT id, code, section, position, definition FROM question_definitions WHERE questionnaire_version_id=%s ORDER BY position",
                [v["id"]])
    questions = []
    for r in qs:
        d = dict(r["definition"])
        d["code"], d["section"], d["definition_id"] = r["code"], r["section"], r["id"]
        questions.append(d)
    out = {"id": v["id"], "code": code, "name": v["name"], "version": v["version"],
           "sections": v["definition"]["sections"], "questions": questions,
           "by_code": {q["code"]: q for q in questions}, "scope": v["definition"]["scope"]}
    with _lock:
        _cache[key] = out
    return out


def definitions_by_id(db, ids):
    if not ids:
        return {}
    rows = db.all("SELECT id, code, definition FROM question_definitions WHERE id = ANY(%s::uuid[])",
                  ["{" + ",".join(ids) + "}"])
    return {r["id"]: dict(r["definition"], code=r["code"]) for r in rows}


def items(db, kind: str, include_disabled=True) -> list[dict]:
    rows = db.all("SELECT code, version, data, review_note FROM catalogs WHERE kind=%s AND status='PUBLISHED' ORDER BY code",
                  [kind])
    out = []
    for r in rows:
        d = dict(r["data"])
        d["catalog_version"] = r["version"]
        d["review_note"] = r["review_note"]
        if include_disabled or d.get("enabled", True):
            out.append(d)
    return out


def tests(db) -> dict:
    return {t["code"]: t for t in items(db, "TEST")}


def equipment(db) -> dict:
    return {t["code"]: t for t in items(db, "EQUIPMENT")}


def exercises(db) -> dict:
    return {t["code"]: t for t in items(db, "EXERCISE")}


def program_index(db) -> dict:
    """program_code -> (equipment_code, program dict)"""
    out = {}
    for code, eq in equipment(db).items():
        for pr in eq.get("programs") or []:
            out[pr["code"]] = (code, pr)
    return out


def outcomes(db) -> dict:
    return {t["code"]: t for t in items(db, "OUTCOME")}


def clear_cache():
    with _lock:
        _cache.clear()
