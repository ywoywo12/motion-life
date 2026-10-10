"""Treatment sessions (bound to an approved plan version), S6/S12 progress reviews, outcomes report."""
from __future__ import annotations

from .. import rbac
from ..audit import audit
from ..errors import Conflict, NotFound, RuleBlocked, ValidationError
from .. import validation as v
from . import assessment as asvc, catalog, plans as psvc

MILESTONES = {"S6": 6, "S12": 12}
DECISIONS = {"CONTINUE": "متابعة الخطة", "MODIFY_PLAN": "تعديل الخطة (إصدار جديد)", "DISCHARGE": "إنهاء البرنامج",
             "REFER": "إحالة", "HOLD": "تعليق"}


def list_sessions(d, episode_id):
    rows = d.all("""SELECT s.*, u.full_name AS therapist_name, pv.version_no AS plan_version_no
                    FROM sessions s JOIN users u ON u.id=s.therapist_id JOIN plan_versions pv ON pv.id=s.plan_version_id
                    WHERE s.episode_id=%s ORDER BY s.session_no""", [episode_id])
    if rows:
        ivs = d.all("SELECT * FROM session_interventions WHERE session_id = ANY(%s::uuid[]) ORDER BY title",
                    ["{" + ",".join(r["id"] for r in rows) + "}"])
        by = {}
        for i in ivs:
            by.setdefault(i["session_id"], []).append(i)
        for r in rows:
            r["interventions"] = by.get(r["id"], [])
    return rows


def due_reviews(d, episode_id, session_count=None):
    if session_count is None:
        session_count = d.scalar("SELECT count(*) FROM sessions WHERE episode_id=%s", [episode_id])
    done = {r["milestone"] for r in d.all("SELECT milestone FROM progress_reviews WHERE episode_id=%s", [episode_id])}
    return [m for m, n in MILESTONES.items() if session_count >= n and m not in done]


def create_session(d, user, episode_id, data):
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    rbac.require_perm(user, "session.write")
    if ep["status"] != "OPEN":
        raise RuleBlocked("الحلقة معلّقة أو مغلقة: لا تُسجّل جلسات علاج حتى يُرفع التعليق.")
    pv = psvc.approved_version(d, ep["id"])
    if not pv:
        raise RuleBlocked("لا توجد خطة معتمدة: لا تُنفّذ خطة جديدة قبل اعتمادها من مراجع مخوّل.", code="NO_APPROVED_PLAN")
    expected_pv = data.get("plan_version_id")
    if expected_pv and expected_pv != pv["id"]:
        raise Conflict("تغيّر إصدار الخطة المعتمد منذ فتح النموذج. راجع الإصدار الجديد قبل تسجيل الجلسة.", code="PLAN_VERSION_CHANGED")
    plan_items = {it["id"]: it for it in psvc.items(d, pv["id"])}
    n = d.scalar("SELECT COALESCE(max(session_no),0) FROM sessions WHERE episode_id=%s", [ep["id"]]) + 1
    sess_date = v.date(data, "session_date", "تاريخ الجلسة", required=True)
    pain_before = v.num(data, "pain_before", "الألم قبل", lo=0, hi=10, integer=True)
    pain_after = v.num(data, "pain_after", "الألم بعد", lo=0, hi=10, integer=True)
    adverse = v.boolean(data, "adverse_event")
    adverse_details = v.s(data, "adverse_details", "تفاصيل الحدث غير المرغوب", max_len=1000)
    if adverse and not adverse_details:
        raise ValidationError("صف الحدث غير المرغوب وما اتُّخذ من إجراء")
    temp_mod = v.s(data, "temp_modification", "التعديل المؤقت ومبرره", max_len=1000)
    ivs = data.get("interventions") or []
    if not isinstance(ivs, list) or not ivs:
        raise ValidationError("سجّل الإجراءات المنفذة فعلياً (أو اذكر أنها لم تُنفّذ)")
    parsed = []
    deviation = False
    for it in ivs:
        pid = it.get("plan_item_id")
        if pid:
            if pid not in plan_items:
                raise ValidationError("بند غير موجود في إصدار الخطة المعتمد")
            parsed.append({"plan_item_id": pid, "title": plan_items[pid]["title"], "performed": v.boolean(it, "performed", True),
                           "dosage_actual": v.s(it, "dosage_actual", "الجرعة الفعلية", max_len=300),
                           "is_deviation": False, "deviation_reason": None, "notes": v.s(it, "notes", "ملاحظات", max_len=500)})
        else:
            reason = v.s(it, "deviation_reason", "مبرر الإجراء غير الموجود في الخطة", max_len=500)
            if not reason:
                raise ValidationError("إجراء خارج الخطة المعتمدة يتطلب مبرراً، ويُرفع للمراجعة")
            deviation = True
            parsed.append({"plan_item_id": None, "title": v.s(it, "title", "اسم الإجراء", required=True, max_len=200),
                           "performed": True, "dosage_actual": v.s(it, "dosage_actual", "الجرعة الفعلية", max_len=300),
                           "is_deviation": True, "deviation_reason": reason, "notes": v.s(it, "notes", "ملاحظات", max_len=500)})
    needs_review = adverse or deviation or bool(temp_mod) or v.boolean(data, "needs_review")
    sid = d.scalar(
        """INSERT INTO sessions(episode_id, plan_version_id, session_no, session_date, therapist_id, pain_before, pain_after,
                                response, adverse_event, adverse_details, temp_modification, needs_review, notes)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        [ep["id"], pv["id"], n, sess_date, user["id"], pain_before, pain_after,
         v.s(data, "response", "استجابة المريض", max_len=1000), adverse, adverse_details, temp_mod, needs_review,
         v.s(data, "notes", "ملاحظات", max_len=1000)])
    for it in parsed:
        d.execute("""INSERT INTO session_interventions(session_id, plan_item_id, title, performed, dosage_actual, is_deviation,
                                                       deviation_reason, notes) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
                  [sid, it["plan_item_id"], it["title"], it["performed"], it["dosage_actual"], it["is_deviation"],
                   it["deviation_reason"], it["notes"]])
    if adverse:
        d.execute("""INSERT INTO alerts(patient_id, episode_id, severity, code, message, details, created_by)
                     VALUES (%s,%s,'HIGH',%s,%s,%s,%s)""",
                  [p["id"], ep["id"], f"SESSION_ADVERSE:{n}", f"حدث غير مرغوب في الجلسة {n}: {adverse_details[:120]}",
                   {"session_id": sid}, user["id"]])
    if deviation or temp_mod:
        d.execute("""INSERT INTO alerts(patient_id, episode_id, severity, code, message, details, created_by)
                     VALUES (%s,%s,'MEDIUM',%s,%s,%s,%s)""",
                  [p["id"], ep["id"], f"SESSION_DEVIATION:{n}", f"تعديل/إجراء خارج الخطة في الجلسة {n} يحتاج مراجعة",
                   {"session_id": sid}, user["id"]])
    audit(d, user, "SESSION_CREATE", "session", sid, patient_id=p["id"],
          details={"session_no": n, "plan_version": pv["version_no"], "adverse": adverse, "deviation": deviation})
    planned = (pv["content"] or {}).get("sessions_planned")
    return {"id": sid, "session_no": n, "plan_version_no": pv["version_no"], "due_reviews": due_reviews(d, ep["id"], n),
            "planned": planned}


def create_progress_review(d, user, episode_id, data):
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    rbac.require_perm(user, "session.write")
    milestone = v.choice(data, "milestone", "نوع المراجعة", ("S6", "S12", "AD_HOC", "DISCHARGE"), required=True)
    count = d.scalar("SELECT count(*) FROM sessions WHERE episode_id=%s", [ep["id"]])
    if milestone in MILESTONES and count < MILESTONES[milestone]:
        raise RuleBlocked(f"لم تُسجَّل {MILESTONES[milestone]} جلسات بعد (المسجّل: {count}). استخدم مراجعة «عند الحاجة».")
    if milestone in ("S6", "S12", "DISCHARGE") and d.scalar(
            "SELECT count(*) FROM progress_reviews WHERE episode_id=%s AND milestone=%s", [ep["id"], milestone]):
        raise Conflict("هذه المراجعة مسجلة مسبقاً")
    measures = data.get("measures") or []
    if not isinstance(measures, list):
        raise ValidationError("القياسات غير صالحة")
    if not measures:
        raise ValidationError("أدخل قياسات قابلة للمقارنة (الألم، نشاط وظيفي ثابت، القياسات الأساسية)")
    goal_status = {}
    valid_goals = {g["id"] for g in asvc.list_goals(d, ep["id"])}
    for gid, st in (data.get("goal_status") or {}).items():
        if gid in valid_goals and st in ("ACTIVE", "ACHIEVED", "PARTIAL", "NOT_ACHIEVED", "DROPPED"):
            goal_status[gid] = st
    rid = d.scalar("""INSERT INTO progress_reviews(episode_id, milestone, after_session_no, summary, decision, goal_status, created_by)
                      VALUES (%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                   [ep["id"], milestone, count, v.s(data, "summary", "ملخص المراجعة", required=True, max_len=3000),
                    v.choice(data, "decision", "القرار", tuple(DECISIONS), required=True), goal_status, user["id"]])
    tp = milestone if milestone in ("S6", "S12", "DISCHARGE") else "OTHER"
    for m in measures:
        asvc.record_outcome(d, user, ep["id"], dict(m, timepoint=tp), progress_review_id=rid)
    for gid, st in goal_status.items():
        d.execute("UPDATE goals SET status=%s, updated_at=now() WHERE id=%s", [st, gid])
    audit(d, user, "PROGRESS_REVIEW", "progress_review", rid, patient_id=p["id"], details={"milestone": milestone})
    return rid


def list_reviews(d, episode_id):
    return d.all("""SELECT r.*, u.full_name AS created_by_name FROM progress_reviews r JOIN users u ON u.id=r.created_by
                    WHERE r.episode_id=%s ORDER BY r.created_at""", [episode_id])


def outcome_table(d, episode_id):
    """Rows: measure(+label) × timepoints, with change vs BASELINE. Pain change is not equated with rehab success."""
    outs = catalog.outcomes(d)
    rows = asvc.list_outcomes(d, episode_id)
    table = {}
    for r in rows:
        key = (r["measure_code"], r["label"] or "")
        t = table.setdefault(key, {"measure_code": r["measure_code"], "label": r["label"],
                                   "name": outs.get(r["measure_code"], {}).get("name_ar", r["measure_code"]),
                                   "unit": r["unit"], "direction": outs.get(r["measure_code"], {}).get("direction"), "values": {}})
        t["values"][r["timepoint"]] = r["value_num"]
    out = []
    for t in table.values():
        base = t["values"].get("BASELINE")
        for tp in ("S6", "S12", "DISCHARGE"):
            if base is not None and tp in t["values"]:
                diff = t["values"][tp] - base
                better = (diff < 0) if t["direction"] == "lower_better" else (diff > 0)
                t.setdefault("change", {})[tp] = {"diff": round(diff, 1), "improved": better if diff != 0 else None}
        out.append(t)
    return sorted(out, key=lambda t: (t["measure_code"], t["label"] or ""))


def sessions_view(d, user, episode_id):
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    pv = psvc.approved_version(d, ep["id"])
    ss = list_sessions(d, ep["id"])
    return {"episode": ep, "patient": p, "approved": pv, "items": psvc.items(d, pv["id"]) if pv else [],
            "sessions": ss, "due": due_reviews(d, ep["id"], len(ss)), "reviews": list_reviews(d, ep["id"]),
            "outcome_catalog": catalog.outcomes(d), "goals": asvc.list_goals(d, ep["id"]),
            "planned": ((pv or {}).get("content") or {}).get("sessions_planned")}
