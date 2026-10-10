"""Jinja filters, globals and JSON encoding."""
from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal
from zoneinfo import ZoneInfo

from flask.json.provider import DefaultJSONProvider

from .. import rbac
from ..clinical import engine, safety
from ..services import assessment as asvc, plans as psvc

TZ = ZoneInfo("Asia/Damascus")
MONTHS = ["كانون الثاني", "شباط", "آذار", "نيسان", "أيار", "حزيران", "تموز", "آب", "أيلول", "تشرين الأول",
          "تشرين الثاني", "كانون الأول"]


def _default(o):
    if isinstance(o, dt.datetime):
        return o.isoformat()
    if isinstance(o, dt.date):
        return o.isoformat()
    if isinstance(o, Decimal):
        return float(o)
    raise TypeError


class JSONProvider(DefaultJSONProvider):
    default = staticmethod(_default)
    ensure_ascii = False
    sort_keys = False


def fmt_date(v):
    if not v:
        return "—"
    if isinstance(v, str):
        try:
            v = dt.date.fromisoformat(v[:10])
        except ValueError:
            return v
    if isinstance(v, dt.datetime):
        v = v.astimezone(TZ).date()
    return f"{v.day} {MONTHS[v.month - 1]} {v.year}"


def fmt_dt(v):
    if not v:
        return "—"
    if isinstance(v, str):
        v = dt.datetime.fromisoformat(v)
    v = v.astimezone(TZ)
    return f"{fmt_date(v.date())} — {v:%H:%M}"


def fmt_num_date(v):
    """Numeric date dd/mm/yyyy (wrapped LTR when rendered)."""
    if not v:
        return "—"
    if isinstance(v, str):
        v = dt.date.fromisoformat(v[:10])
    if isinstance(v, dt.datetime):
        v = v.astimezone(TZ).date()
    return f"{v.day:02d}/{v.month:02d}/{v.year}"


def age(bd):
    a = safety.age_on(bd)
    return "—" if a is None else f"{a} سنة"


def tojson_attr(v):
    return json.dumps(v, ensure_ascii=False, default=_default)


def register(app):
    app.json_provider_class = JSONProvider
    app.json = JSONProvider(app)
    app.jinja_env.filters.update(date=fmt_date, dt=fmt_dt, ndate=fmt_num_date, age=age, j=tojson_attr)
    app.jinja_env.globals.update(
        ROLE_NAMES=rbac.ROLE_NAMES, SAFETY_LABELS=safety.STATUS_LABELS, FLAG_LABELS=safety.FLAG_LABELS,
        PLAN_STATUS=psvc.STATUS_LABELS, ACTION_LABELS=psvc.ACTION_LABELS, CATEGORY_LABELS=psvc.CATEGORY_LABELS,
        RESULT_LABELS=asvc.RESULT_LABELS, SIDE_LABELS=asvc.SIDE_LABELS, SENSORY_LABELS=asvc.SENSORY_LABELS,
        REFLEX_LABELS=asvc.REFLEX_LABELS, REPEATED_RESPONSES=asvc.REPEATED_RESPONSES, STATUS_LABELS=engine.STATUS_LABELS,
        display_value=engine.display_value, has_perm=rbac.has_perm,
        SEVERITY_LABELS={"CRITICAL": "حرج", "HIGH": "مرتفع", "MEDIUM": "متوسط", "INFO": "معلومة"},
        SEVERITY_ICONS={"CRITICAL": "⛔", "HIGH": "⚠", "MEDIUM": "◆", "INFO": "ℹ"},
        SAFETY_ICONS={"EMERGENCY": "⛔", "NEEDS_REVIEW": "⚠", "INCOMPLETE": "◌", "NOT_CONFIRMED": "◌", "NO_FLAGS_REPORTED": "✓"},
        GOAL_STATUS={"ACTIVE": "نشط", "ACHIEVED": "تحقق", "PARTIAL": "تحقق جزئياً", "NOT_ACHIEVED": "لم يتحقق", "DROPPED": "أُلغي"},
        TIMEPOINTS={"BASELINE": "البداية", "S6": "بعد الجلسة 6", "S12": "بعد الجلسة 12", "DISCHARGE": "عند الإنهاء", "OTHER": "أخرى"},
        CERTAINTY={"LOW": "منخفضة", "MODERATE": "متوسطة", "HIGH": "مرتفعة"},
    )
