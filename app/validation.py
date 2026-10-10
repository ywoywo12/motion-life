"""Small schema-validation helpers with Arabic error messages.

Every service validates its input with these before writing. Unknown keys are ignored.
"""
from __future__ import annotations

import datetime as dt
import re
import uuid

from .errors import ValidationError

_CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def clean_text(v, max_len=5000):
    if v is None:
        return None
    if not isinstance(v, (str, int, float)):
        raise ValidationError("قيمة نصية غير صالحة")
    s = _CTRL.sub("", str(v)).strip()
    if len(s) > max_len:
        raise ValidationError(f"النص أطول من الحد المسموح ({max_len} حرفاً)")
    return s or None


def s(data, key, label, *, required=False, max_len=300, pattern=None):
    v = clean_text(data.get(key), max_len)
    if required and not v:
        raise ValidationError(f"الحقل «{label}» مطلوب", details={"field": key})
    if v and pattern and not re.fullmatch(pattern, v):
        raise ValidationError(f"صيغة «{label}» غير صحيحة", details={"field": key})
    return v


def choice(data, key, label, options, *, required=False):
    v = data.get(key)
    if v in (None, ""):
        if required:
            raise ValidationError(f"الحقل «{label}» مطلوب", details={"field": key})
        return None
    if v not in options:
        raise ValidationError(f"قيمة «{label}» غير مقبولة", details={"field": key})
    return v


def num(data, key, label, *, required=False, lo=None, hi=None, integer=False):
    v = data.get(key)
    if v in (None, ""):
        if required:
            raise ValidationError(f"الحقل «{label}» مطلوب", details={"field": key})
        return None
    try:
        n = float(v)
    except (TypeError, ValueError):
        raise ValidationError(f"«{label}» يجب أن يكون رقماً", details={"field": key})
    if integer:
        if n != int(n):
            raise ValidationError(f"«{label}» يجب أن يكون عدداً صحيحاً", details={"field": key})
        n = int(n)
    if lo is not None and n < lo or hi is not None and n > hi:
        raise ValidationError(f"«{label}» خارج النطاق ({lo}–{hi})", details={"field": key})
    return n


def date(data, key, label, *, required=False, not_future=True):
    v = data.get(key)
    if v in (None, ""):
        if required:
            raise ValidationError(f"الحقل «{label}» مطلوب", details={"field": key})
        return None
    try:
        d = dt.date.fromisoformat(str(v)[:10])
    except ValueError:
        raise ValidationError(f"تاريخ «{label}» غير صالح", details={"field": key})
    if d.year < 1900 or (not_future and d > dt.date.today() + dt.timedelta(days=1)):
        raise ValidationError(f"تاريخ «{label}» خارج النطاق المقبول", details={"field": key})
    return d.isoformat()


def boolean(data, key, default=False):
    v = data.get(key, default)
    if isinstance(v, bool):
        return v
    return str(v).lower() in ("1", "true", "on", "yes")


def uid(v, label="المعرّف"):
    try:
        return str(uuid.UUID(str(v)))
    except (ValueError, TypeError):
        raise ValidationError(f"{label} غير صالح")


def int_version(data, key="version"):
    v = data.get(key)
    try:
        return int(v)
    except (TypeError, ValueError):
        raise ValidationError("رقم الإصدار مطلوب لمنع الكتابة فوق تعديلات الآخرين", details={"field": key})


_AR_DIAC = re.compile(r"[ً-ْٰـ]")


def normalize_name(name: str) -> str:
    n = _AR_DIAC.sub("", name or "")
    n = re.sub("[أإآٱ]", "ا", n).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    n = re.sub(r"\s+", " ", n).strip().lower()
    return n


def normalize_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    trans = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
    digits = re.sub(r"\D", "", phone.translate(trans))
    if digits.startswith("00963"):
        digits = "0" + digits[5:]
    elif digits.startswith("963"):
        digits = "0" + digits[3:]
    return digits or None
