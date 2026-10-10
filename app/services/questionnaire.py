"""Answer storage for versioned questionnaires (history kept; nothing defaults to "No")."""
from __future__ import annotations

from .. import rbac
from ..audit import audit
from ..clinical import engine
from ..errors import NotFound, ValidationError
from .. import validation as v
from . import catalog

SOURCES = ("PATIENT_REPORTED", "RECEPTION_ENTRY", "THERAPIST_ENTRY", "CLINICIAN_OBSERVED")
SOURCE_LABELS = {"PATIENT_REPORTED": "إجابة المريض (منقولة)", "RECEPTION_ENTRY": "إدخال الاستقبال",
                 "THERAPIST_ENTRY": "إدخال المعالج", "CLINICIAN_OBSERVED": "ملاحظة سريرية"}
NIL = "00000000-0000-0000-0000-000000000000"


def get_answers(d, patient_id, episode_id=None) -> dict:
    rows = d.all(
        """SELECT a.id, a.question_code, a.status, a.value, a.note, a.source, a.recorded_at, a.question_definition_id,
                  u.full_name AS recorded_by_name
           FROM answers a JOIN users u ON u.id = a.recorded_by
           WHERE a.patient_id=%s AND COALESCE(a.episode_id, %s::uuid) = COALESCE(%s::uuid, %s::uuid) AND a.superseded_at IS NULL""",
        [patient_id, NIL, episode_id, NIL])
    return {r["question_code"]: {"id": r["id"], "status": r["status"],
                                 "value": r["value"].get("v") if isinstance(r["value"], dict) else None, "note": r["note"],
                                 "source": r["source"], "recorded_at": r["recorded_at"].isoformat(),
                                 "recorded_by": r["recorded_by_name"], "definition_id": r["question_definition_id"]}
            for r in rows}


def save_answers(d, user, patient, episode, qcode: str, items: list, ctx: dict):
    """Save a batch of answers. Each item: {code, status, value, note, source, base_id}.

    base_id = id of the answer the client last saw (None if it saw none). If the current answer
    differs, the item is reported as a conflict and NOT overwritten.
    Returns {"saved": [codes], "conflicts": [{code, current}], "answers": {...}}
    """
    rbac.require_perm(user, "clinical.write")
    qn = catalog.questionnaire(d, qcode)
    if (qn["scope"] == "episode") != (episode is not None):
        raise ValidationError("نطاق الاستبيان غير مطابق")
    if not isinstance(items, list) or len(items) > 200:
        raise ValidationError("دفعة إجابات غير صالحة")
    current = get_answers(d, patient["id"], episode["id"] if episode else None)
    saved, conflicts = [], []
    for it in items:
        code = it.get("code")
        q = qn["by_code"].get(code)
        if not q:
            raise ValidationError(f"سؤال غير معروف: {code}")
        status = it.get("status") or "ANSWERED"
        value = engine.normalize_value(q, status, it.get("value"))
        note = v.clean_text(it.get("note"), 1000)
        source = it.get("source") or "THERAPIST_ENTRY"
        if source not in SOURCES:
            raise ValidationError("مصدر الإجابة غير صالح")
        if source == "RECEPTION_ENTRY" and user["role_code"] != rbac.RECEPTION:
            source = "THERAPIST_ENTRY"
        cur = current.get(code)
        base = it.get("base_id")
        if (cur["id"] if cur else None) != (base or None):
            conflicts.append({"code": code, "current": cur})
            continue
        if cur and cur["status"] == status and cur["value"] == value and (cur["note"] or None) == note and cur["source"] == source:
            continue
        if not cur and status == "NOT_ASKED" and not note:
            continue
        if cur:
            d.execute("UPDATE answers SET superseded_at=now() WHERE id=%s", [cur["id"]])
        new_id = d.scalar(
            """INSERT INTO answers(patient_id, episode_id, question_definition_id, question_code, status, value, note, source, recorded_by)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
            [patient["id"], episode["id"] if episode else None, q["definition_id"], code, status,
             None if value is None else {"v": value}, note, source, user["id"]])
        if cur:
            d.execute("UPDATE answers SET superseded_by=%s WHERE id=%s", [new_id, cur["id"]])
        saved.append(code)
    if saved:
        audit(d, user, "ANSWERS_SAVE", "questionnaire", qcode, patient_id=patient["id"],
              details={"episode_id": episode["id"] if episode else None, "codes": saved,
                       "questionnaire_version": qn["version"]})
    return {"saved": saved, "conflicts": conflicts, "answers": get_answers(d, patient["id"], episode["id"] if episode else None)}


def unwrap(answers: dict) -> dict:
    """DB stores value as {"v": value} (so JSON null vs missing is unambiguous); expose plain values."""
    out = {}
    for k, a in answers.items():
        b = dict(a)
        val = a.get("value")
        b["value"] = val.get("v") if isinstance(val, dict) and "v" in val else val
        out[k] = b
    return out


def answers_plain(d, patient_id, episode_id=None):
    return get_answers(d, patient_id, episode_id)


def answer_history(d, user, patient, code, episode_id=None):
    rows = d.all(
        """SELECT a.status, a.value, a.note, a.source, a.recorded_at, u.full_name AS recorded_by, a.superseded_at,
                  qd.definition->>'text' AS question_text, qv.version AS questionnaire_version
           FROM answers a JOIN users u ON u.id=a.recorded_by
           JOIN question_definitions qd ON qd.id = a.question_definition_id
           JOIN questionnaire_versions qv ON qv.id = qd.questionnaire_version_id
           WHERE a.patient_id=%s AND a.question_code=%s AND COALESCE(a.episode_id, %s::uuid) = COALESCE(%s::uuid, %s::uuid)
           ORDER BY a.recorded_at DESC""", [patient["id"], code, NIL, episode_id, NIL, NIL])
    for r in rows:
        r["value"] = r["value"].get("v") if isinstance(r["value"], dict) else r["value"]
    return rows


# ───────── list entries (surgeries / medications) ─────────

def list_entries(d, patient_id):
    return d.all("""SELECT e.id, e.entry_type, e.data, e.created_at, u.full_name AS created_by_name FROM medical_history_entries e
                    JOIN users u ON u.id=e.created_by WHERE e.patient_id=%s AND e.removed_at IS NULL ORDER BY e.created_at""",
                 [patient_id])


def add_entry(d, user, patient, data):
    rbac.require_perm(user, "clinical.write")
    et = v.choice(data, "entry_type", "نوع البند", ("SURGERY", "MEDICATION"), required=True)
    if et == "SURGERY":
        payload = {"procedure": v.s(data, "procedure", "العملية/المنطقة", required=True, max_len=200),
                   "year": v.num(data, "year", "السنة", lo=1900, hi=2100, integer=True),
                   "notes": v.s(data, "notes", "ملاحظات", max_len=500)}
    else:
        payload = {"name": v.s(data, "name", "اسم الدواء", required=True, max_len=150),
                   "dose": v.s(data, "dose", "الجرعة", max_len=100),
                   "reason": v.s(data, "reason", "السبب", max_len=200)}
    eid = d.scalar("INSERT INTO medical_history_entries(patient_id, entry_type, data, created_by) VALUES (%s,%s,%s,%s) RETURNING id",
                   [patient["id"], et, payload, user["id"]])
    audit(d, user, "HISTORY_ENTRY_ADD", "history_entry", eid, patient_id=patient["id"], details={"type": et})
    return eid


def remove_entry(d, user, patient, entry_id, reason):
    rbac.require_perm(user, "clinical.write")
    reason = v.s({"r": reason}, "r", "سبب الإزالة", required=True)
    n = d.execute("UPDATE medical_history_entries SET removed_at=now(), removed_by=%s, removed_reason=%s WHERE id=%s::uuid AND patient_id=%s AND removed_at IS NULL",
                  [user["id"], reason, v.uid(entry_id), patient["id"]]).rowcount
    if not n:
        raise NotFound()
    audit(d, user, "HISTORY_ENTRY_REMOVE", "history_entry", entry_id, patient_id=patient["id"], reason=reason)


def confirm_review(d, user, patient, note=None):
    rbac.require_perm(user, "clinical.write")
    rid = d.scalar("INSERT INTO medical_history_reviews(patient_id, reviewed_by, note) VALUES (%s,%s,%s) RETURNING id",
                   [patient["id"], user["id"], v.clean_text(note, 1000)])
    audit(d, user, "HISTORY_REVIEWED", "patient", patient["id"], patient_id=patient["id"])
    return rid


def last_review(d, patient_id):
    return d.one("""SELECT r.reviewed_at, r.note, u.full_name AS reviewed_by FROM medical_history_reviews r
                    JOIN users u ON u.id=r.reviewed_by WHERE r.patient_id=%s ORDER BY r.reviewed_at DESC LIMIT 1""", [patient_id])
