"""Questionnaire engine: branching (show_if), validation and completeness.

`answers` everywhere is a mapping: code -> {"status": ANSWERED|UNKNOWN|NOT_ASKED|NOT_APPLICABLE, "value": ...}
A missing code means NOT_ASKED. Nothing is ever defaulted to "No".

The same show_if DSL is evaluated client-side in static/js/questionnaire.js for live UI;
the server is authoritative (validation, completeness, safety).
"""
from __future__ import annotations

import datetime as dt

from ..errors import ValidationError

STATUSES = ("ANSWERED", "UNKNOWN", "NOT_ASKED", "NOT_APPLICABLE")
STATUS_LABELS = {"ANSWERED": "مُجاب", "UNKNOWN": "غير معروف", "NOT_ASKED": "لم يُسأل", "NOT_APPLICABLE": "لا ينطبق"}
TRI_LABELS = {"YES": "نعم", "NO": "لا"}


def _val(answers, code):
    a = answers.get(code)
    if not a or a.get("status") != "ANSWERED":
        return None
    return a.get("value")


def eval_cond(cond, answers, ctx=None) -> bool:
    if not cond:
        return True
    ctx = ctx or {}
    if "all" in cond:
        return all(eval_cond(c, answers, ctx) for c in cond["all"])
    if "any" in cond:
        return any(eval_cond(c, answers, ctx) for c in cond["any"])
    if "sex" in cond:
        return ctx.get("sex") == cond["sex"]
    v = _val(answers, cond["q"])
    if "answered" in cond:
        return (v is not None and v != [] and v != "") == bool(cond["answered"])
    if v is None:
        return False
    if "eq" in cond:
        return v == cond["eq"]
    if "in" in cond:
        return v in cond["in"]
    if "includes" in cond:
        return isinstance(v, list) and cond["includes"] in v
    if "includes_any" in cond:
        return isinstance(v, list) and any(x in v for x in cond["includes_any"])
    if "not_in" in cond:
        if isinstance(v, list):
            return len(v) > 0 and not all(x in cond["not_in"] for x in v)
        return v not in cond["not_in"]
    if "gte" in cond:
        return isinstance(v, (int, float)) and v >= cond["gte"]
    raise ValueError("unknown condition %r" % cond)


def visible_codes(questions, answers, ctx=None) -> set:
    # Iterate to a fixed point so that chained conditions resolve regardless of order.
    vis = set()
    for _ in range(4):
        new = {q["code"] for q in questions if eval_cond(q.get("show_if"), answers, ctx)}
        if new == vis:
            break
        vis = new
    return vis


def normalize_value(q: dict, status: str, value):
    """Validate a single answer against its definition. Returns the cleaned value."""
    if status not in STATUSES:
        raise ValidationError("حالة إجابة غير صالحة")
    if status == "NOT_APPLICABLE" and not q.get("allow_na"):
        raise ValidationError(f"«لا ينطبق» غير مسموح للسؤال: {q['text']}")
    if status != "ANSWERED":
        return None
    t = q["type"]
    opts = {o["v"] for o in q.get("options") or []}
    if t == "tri":
        if value not in ("YES", "NO"):
            raise ValidationError("القيمة يجب أن تكون نعم أو لا")
        return value
    if t == "choice":
        if value not in opts:
            raise ValidationError(f"خيار غير صالح للسؤال: {q['text']}")
        return value
    if t == "multi":
        if not isinstance(value, list) or not value or any(x not in opts for x in value):
            raise ValidationError(f"اختيارات غير صالحة للسؤال: {q['text']}")
        ex = q.get("exclusive")
        if ex and ex in value and len(value) > 1:
            raise ValidationError(f"لا يمكن الجمع بين «لا يوجد» وخيارات أخرى: {q['text']}")
        return list(dict.fromkeys(value))
    if t in ("text", "longtext"):
        if not isinstance(value, str) or not value.strip():
            raise ValidationError(f"النص فارغ: {q['text']}")
        limit = 300 if t == "text" else 5000
        if len(value) > limit:
            raise ValidationError(f"النص أطول من {limit} حرفاً")
        return value.strip()
    if t == "date":
        try:
            d = dt.date.fromisoformat(str(value))
        except ValueError:
            raise ValidationError("تاريخ غير صالح")
        if d > dt.date.today() + dt.timedelta(days=1) or d.year < 1900:
            raise ValidationError("التاريخ خارج النطاق المقبول")
        return d.isoformat()
    if t in ("number", "scale010"):
        try:
            n = float(value)
        except (TypeError, ValueError):
            raise ValidationError("رقم غير صالح")
        lo, hi = (0, 10) if t == "scale010" else (q.get("min", -1e9), q.get("max", 1e9))
        if n < lo or n > hi:
            raise ValidationError(f"القيمة يجب أن تكون بين {lo} و{hi}")
        if t == "scale010":
            if n != int(n):
                raise ValidationError("مقياس الألم رقم صحيح من 0 إلى 10")
            return int(n)
        return n if n != int(n) else int(n)
    raise ValidationError("نوع سؤال غير معروف")


def completeness(questions, answers, ctx=None, sections=None):
    """Required questions that are visible but not answered (UNKNOWN / NOT_ASKED count as missing)."""
    vis = visible_codes(questions, answers, ctx)
    missing = []
    for q in questions:
        if sections and q["section"] not in sections:
            continue
        if not q.get("required") or q["code"] not in vis:
            continue
        a = answers.get(q["code"]) or {"status": "NOT_ASKED"}
        if a["status"] in ("ANSWERED", "NOT_APPLICABLE"):
            continue
        missing.append({"code": q["code"], "text": q["text"], "section": q["section"],
                        "status": a["status"], "status_label": STATUS_LABELS[a["status"]]})
    return missing


def display_value(q: dict, a: dict | None) -> str:
    if not a or a.get("status") == "NOT_ASKED":
        return "لم يُسأل"
    if a["status"] != "ANSWERED":
        return STATUS_LABELS[a["status"]]
    v = a.get("value")
    labels = {o["v"]: o["label"] for o in q.get("options") or []}
    if q["type"] == "tri":
        return TRI_LABELS.get(v, str(v))
    if q["type"] == "choice":
        return labels.get(v, str(v))
    if q["type"] == "multi":
        return "، ".join(labels.get(x, x) for x in v)
    if q["type"] == "scale010":
        return f"{v} / 10"
    if q["type"] == "number" and q.get("unit"):
        return f"{v} {q['unit']}"
    return str(v)
