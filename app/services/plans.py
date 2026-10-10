"""Treatment plans: versioned drafts, strict state machine, review/approval (no self-approval)."""
from __future__ import annotations

from .. import rbac
from ..audit import audit
from ..clinical import safety as safety_rules
from ..errors import Conflict, Forbidden, NotFound, RuleBlocked, ValidationError
from .. import validation as v
from . import assessment as asvc, catalog

STATUS_LABELS = {
    "DRAFT": "مسودة", "SUBMITTED": "بانتظار المراجعة", "CHANGES_REQUESTED": "أُعيدت للتعديل", "ESCALATED": "مصعّدة للمدير",
    "ON_HOLD": "معلّقة", "APPROVED": "معتمدة", "SUPERSEDED": "مستبدلة بإصدار أحدث", "CLOSED": "مغلقة",
}
ACTION_LABELS = {
    "SUBMIT": "إرسال للمراجعة", "APPROVE": "اعتماد", "REQUEST_CHANGES": "إعادة للتعديل", "ESCALATE": "تصعيد للمدير",
    "HOLD": "تعليق العلاج/إحالة", "RESUME": "إعادة إلى المراجعة", "SUPERSEDE": "استبدال", "CLOSE": "إغلاق", "REVISE": "إنشاء إصدار معدّل",
}
CATEGORY_LABELS = {"DEVICE": "أجهزة", "MANUAL": "علاج يدوي", "GYM": "تمارين الصالة", "HOME": "برنامج منزلي",
                   "EDUCATION": "تثقيف/إرشادات", "OTHER": "أخرى"}

# action -> (allowed from-states, to-state)
TRANSITIONS = {
    "SUBMIT": (("DRAFT",), "SUBMITTED"),
    "APPROVE": (("SUBMITTED", "ESCALATED"), "APPROVED"),
    "REQUEST_CHANGES": (("SUBMITTED", "ESCALATED"), "CHANGES_REQUESTED"),
    "ESCALATE": (("SUBMITTED",), "ESCALATED"),
    "HOLD": (("SUBMITTED", "ESCALATED", "APPROVED"), "ON_HOLD"),
    "RESUME": (("ON_HOLD",), "SUBMITTED"),
}
REVIEW_ACTIONS = ("APPROVE", "REQUEST_CHANGES", "ESCALATE", "HOLD", "RESUME")
REVISABLE = ("CHANGES_REQUESTED", "ON_HOLD", "APPROVED")


def _plan(d, episode_id):
    return d.one("SELECT * FROM treatment_plans WHERE episode_id=%s", [episode_id])


def versions(d, plan_id):
    return d.all("""SELECT pv.*, a.full_name AS author_name, ap.full_name AS approved_by_name
                    FROM plan_versions pv JOIN users a ON a.id=pv.author_id LEFT JOIN users ap ON ap.id=pv.approved_by
                    WHERE pv.plan_id=%s ORDER BY pv.version_no DESC""", [plan_id])


def items(d, version_id):
    return d.all("SELECT * FROM plan_items WHERE plan_version_id=%s ORDER BY position", [version_id])


def decisions(d, version_ids):
    if not version_ids:
        return []
    return d.all("""SELECT ad.*, u.full_name AS actor_name, pv.version_no FROM approval_decisions ad
                    JOIN users u ON u.id=ad.actor_id JOIN plan_versions pv ON pv.id=ad.plan_version_id
                    WHERE ad.plan_version_id = ANY(%s::uuid[]) ORDER BY ad.at""", ["{" + ",".join(version_ids) + "}"])


def approved_version(d, episode_id):
    return d.one("""SELECT pv.* FROM plan_versions pv JOIN treatment_plans tp ON tp.id=pv.plan_id
                    WHERE tp.episode_id=%s AND pv.status='APPROVED'""", [episode_id])


# ───────────── validation ─────────────

def _parse_content(data):
    c = data.get("content") or {}
    return {
        "impression": v.s(c, "impression", "التشخيص الوظيفي/الانطباع السريري", max_len=2000),
        "certainty": v.choice(c, "certainty", "درجة اليقين", ("LOW", "MODERATE", "HIGH")),
        "rationale": v.s(c, "rationale", "المبررات", max_len=2000),
        "alternatives": v.s(c, "alternatives", "البدائل/الاحتمالات الأخرى", max_len=2000),
        "goal_ids": [v.uid(g, "الهدف") for g in (c.get("goal_ids") or [])][:20],
        "sessions_planned": v.num(c, "sessions_planned", "عدد الجلسات المخطط", lo=1, hi=60, integer=True),
        "frequency_per_week": v.num(c, "frequency_per_week", "عدد الجلسات أسبوعياً", lo=1, hi=7, integer=True),
        "reassessment": v.s(c, "reassessment", "خطة إعادة التقييم", max_len=500),
        "phases_note": v.s(c, "phases_note", "ملاحظة المراحل", max_len=1000),
        "general_precautions": v.s(c, "general_precautions", "احتياطات عامة", max_len=1000),
    }


def _parse_items(data, equipment, exercises=None, programs=None):
    raw = data.get("items") or []
    if not isinstance(raw, list) or len(raw) > 40:
        raise ValidationError("بنود الخطة غير صالحة")
    out = []
    for i, it in enumerate(raw):
        cat = v.choice(it, "category", "فئة البند", tuple(CATEGORY_LABELS), required=True)
        eq = v.s(it, "equipment_code", "الجهاز", max_len=20)
        prog = v.s(it, "program_code", "برنامج الجهاز", max_len=30)
        prog_label = None
        if cat == "DEVICE":
            if not eq or eq not in equipment:
                raise ValidationError(f"البند {i + 1}: اختر جهازاً من الكتالوج")
            if prog:
                pi = (programs or {}).get(prog)
                if not pi or pi[0] != eq:
                    raise ValidationError(f"البند {i + 1}: البرنامج لا يتبع الجهاز المختار")
                prog_label = f"{pi[1]['ar']} — {pi[1]['en']}"
        else:
            eq = None
            prog = None
        exc = v.s(it, "exercise_code", "التمرين", max_len=20)
        if exc and exc not in (exercises or {}):
            raise ValidationError(f"البند {i + 1}: تمرين غير موجود في المكتبة")
        if cat not in ("GYM", "HOME", "OTHER"):
            exc = None
        out.append({
            "position": i, "category": cat, "equipment_code": eq,
            "title": v.s(it, "title", "اسم الإجراء/التمرين", required=True, max_len=200),
            "target": v.s(it, "target", "الهدف من الإجراء", max_len=300),
            "dosage": v.s(it, "dosage", "الجرعة/المعايير", max_len=500),
            "method": v.s(it, "method", "طريقة التنفيذ", max_len=1000),
            "precautions": v.s(it, "precautions", "الاحتياطات", max_len=1000),
            "progression_criteria": v.s(it, "progression_criteria", "معايير التقدم", max_len=500),
            "stop_criteria": v.s(it, "stop_criteria", "معايير التوقف", max_len=500),
            "phase": v.choice(it, "phase", "المرحلة", ("1", "2", "3", "1-2", "2-3", "1-3")),
            "contraindications_reviewed": v.boolean(it, "contraindications_reviewed"),
            "exercise_code": exc, "program_code": prog, "program_label": prog_label,
        })
    return out


def submission_blockers(d, ep, p, version, its):
    """Server-side rules that must hold before a plan can be submitted or approved."""
    b = []
    c = version["content"] or {}
    if not c.get("impression"):
        b.append("أدخل التشخيص الوظيفي/الانطباع السريري")
    if not c.get("certainty"):
        b.append("حدد درجة اليقين")
    if not c.get("sessions_planned"):
        b.append("حدد عدد الجلسات المخطط (لا يُفرض عدد ثابت)")
    if not c.get("reassessment"):
        b.append("حدد خطة إعادة التقييم")
    if not its:
        b.append("أضف بنداً علاجياً واحداً على الأقل")
    safety_row = asvc.current_safety(d, ep["id"])
    flags = set(safety_row["flags"] or []) if safety_row else set()
    precaution_flags = [f for f in safety_rules.DEVICE_PRECAUTION_FLAGS if f in flags]
    for it in its:
        n = f"البند «{it['title']}»"
        if it["category"] in ("DEVICE", "GYM", "HOME", "MANUAL") and not it.get("dosage"):
            b.append(f"{n}: أدخل الجرعة/المعايير التي يحددها المختص")
        if it["category"] in ("GYM", "HOME") and not it.get("stop_criteria"):
            b.append(f"{n}: أدخل معايير التوقف")
        if it["category"] == "MANUAL" and not it.get("target"):
            b.append(f"{n}: حدد الهدف من التقنية")
        if it["category"] == "DEVICE":
            if not it.get("contraindications_reviewed"):
                b.append(f"{n}: أكّد مراجعة الموانع والاحتياطات حسب تعليمات الشركة المصنعة")
            if precaution_flags and not it.get("precautions"):
                b.append(f"{n}: يوجد لدى المريض ({'، '.join(safety_rules.FLAG_LABELS[f] for f in precaution_flags)}). "
                         "وثّق الاحتياطات حسب تعليمات الجهاز")
    st = safety_row["status"] if safety_row else "NOT_CONFIRMED"
    if st == "EMERGENCY":
        b.append("فرز السلامة إسعافي: لا يمكن إرسال أو اعتماد خطة علاج روتينية")
    elif st in ("NOT_CONFIRMED", "INCOMPLETE") or (safety_row and safety_row["missing"]):
        b.append("فرز السلامة غير مكتمل (قيم «غير معروف/لم يُسأل» لا تُعتبر نفياً)")
    if "SURGICAL_RESTRICTIONS_UNCLEAR" in flags:
        b.append("قيود الجراحة غير موثقة: لا يُعتمد بروتوكول قبل توضيح تعليمات الجراح")
    a = d.one("SELECT * FROM assessments WHERE episode_id=%s", [ep["id"]])
    if not a or a["status"] != "FINALIZED":
        b.append("أنهِ التقييم (إصدار تقييم) قبل إرسال الخطة")
    if ep["status"] != "OPEN":
        b.append("الحلقة معلّقة أو مغلقة")
    if not d.scalar("SELECT count(*) FROM goals WHERE episode_id=%s AND status='ACTIVE'", [ep["id"]]):
        b.append("لا توجد أهداف قابلة للقياس")
    return b


# ───────────── drafting ─────────────

def save_draft(d, user, episode_id, data):
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    rbac.require_perm(user, "plan.author")
    if ep["status"] == "CLOSED":
        raise RuleBlocked("الحلقة مغلقة")
    content = _parse_content(data)
    its = _parse_items(data, catalog.equipment(d), catalog.exercises(d), catalog.program_index(d))
    plan = _plan(d, ep["id"])
    if not plan:
        plan = d.one("INSERT INTO treatment_plans(episode_id, created_by) VALUES (%s,%s) RETURNING *", [ep["id"], user["id"]])
    draft = d.one("SELECT * FROM plan_versions WHERE plan_id=%s AND status='DRAFT'", [plan["id"]])
    if draft is None:
        if d.scalar("SELECT count(*) FROM plan_versions WHERE plan_id=%s", [plan["id"]]):
            raise RuleBlocked("لا توجد مسودة مفتوحة. استخدم «إنشاء إصدار معدّل» من إصدار معاد أو معتمد.")
        draft = d.one("""INSERT INTO plan_versions(plan_id, version_no, status, content, author_id)
                         VALUES (%s,1,'DRAFT',%s,%s) RETURNING *""", [plan["id"], content, user["id"]])
        audit(d, user, "PLAN_CREATE", "plan_version", draft["id"], patient_id=p["id"], details={"version": 1})
    else:
        if draft["author_id"] != user["id"]:
            raise Forbidden("المسودة يعدّلها كاتبها فقط. يمكن للمراجع إعادتها بملاحظات.")
        lock = v.int_version(data, "lock_version")
        upd = d.one("""UPDATE plan_versions SET content=%s, updated_at=now(), lock_version=lock_version+1
                       WHERE id=%s AND lock_version=%s AND status='DRAFT' RETURNING *""", [content, draft["id"], lock])
        if not upd:
            raise Conflict("تم تعديل المسودة من نافذة أو جهاز آخر. أعد التحميل.", code="STALE_VERSION")
        draft = upd
    d.execute("DELETE FROM plan_items WHERE plan_version_id=%s", [draft["id"]])
    for it in its:
        d.execute("""INSERT INTO plan_items(plan_version_id, position, category, title, equipment_code, target, dosage, method,
                                            precautions, progression_criteria, stop_criteria, phase, contraindications_reviewed,
                                            exercise_code, program_code, program_label)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                  [draft["id"], it["position"], it["category"], it["title"], it["equipment_code"], it["target"], it["dosage"],
                   it["method"], it["precautions"], it["progression_criteria"], it["stop_criteria"], it["phase"],
                   it["contraindications_reviewed"], it["exercise_code"], it["program_code"], it["program_label"]])
    audit(d, user, "PLAN_DRAFT_SAVE", "plan_version", draft["id"], patient_id=p["id"], details={"items": len(its)})
    return draft


def revise(d, user, episode_id):
    """Create a new DRAFT version from a CHANGES_REQUESTED / ON_HOLD / APPROVED version (history kept)."""
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    rbac.require_perm(user, "plan.author")
    plan = _plan(d, ep["id"])
    if not plan:
        raise NotFound("لا توجد خطة")
    latest = d.one("SELECT * FROM plan_versions WHERE plan_id=%s ORDER BY version_no DESC LIMIT 1", [plan["id"]])
    if latest["status"] not in REVISABLE:
        raise RuleBlocked(f"لا يمكن إنشاء إصدار جديد والإصدار الأحدث بحالة «{STATUS_LABELS[latest['status']]}»")
    vn = latest["version_no"] + 1
    new = d.one("""INSERT INTO plan_versions(plan_id, version_no, status, content, author_id, based_on_version_id)
                   VALUES (%s,%s,'DRAFT',%s,%s,%s) RETURNING *""", [plan["id"], vn, latest["content"], user["id"], latest["id"]])
    for it in items(d, latest["id"]):
        d.execute("""INSERT INTO plan_items(plan_version_id, position, category, title, equipment_code, target, dosage, method,
                                            precautions, progression_criteria, stop_criteria, phase, contraindications_reviewed,
                                            exercise_code, program_code, program_label)
                     VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,false,%s,%s,%s)""",
                  [new["id"], it["position"], it["category"], it["title"], it["equipment_code"], it["target"], it["dosage"],
                   it["method"], it["precautions"], it["progression_criteria"], it["stop_criteria"], it["phase"],
                   it["exercise_code"], it["program_code"], it["program_label"]])
    d.execute("""INSERT INTO approval_decisions(plan_version_id, action, from_status, to_status, actor_id, actor_role, comment)
                 VALUES (%s,'REVISE','—','DRAFT',%s,%s,%s)""", [new["id"], user["id"], user["role_code"],
                                                                f"إصدار معدّل مبني على الإصدار {latest['version_no']}"])
    audit(d, user, "PLAN_REVISE", "plan_version", new["id"], patient_id=p["id"],
          details={"from_version": latest["version_no"], "version": vn})
    return new


# ───────────── transitions ─────────────

def _transition(d, user, version, action, to_status, comment=None, item_comments=None):
    from_status = version["status"]
    allowed, _ = TRANSITIONS[action]
    if from_status not in allowed:
        raise RuleBlocked(f"انتقال غير مسموح: «{ACTION_LABELS[action]}» من حالة «{STATUS_LABELS[from_status]}»",
                          code="INVALID_TRANSITION")
    extra = ""
    params = [to_status]
    if action == "SUBMIT":
        extra = ", submitted_at=now()"
    if action == "APPROVE":
        extra = ", approved_at=now(), approved_by=%s"
        params.append(user["id"])
    params += [version["id"], from_status]
    row = d.one(f"UPDATE plan_versions SET status=%s, updated_at=now(){extra} WHERE id=%s AND status=%s RETURNING *", params)
    if not row:
        raise Conflict("تغيّرت حالة الخطة بواسطة مستخدم آخر. أعد التحميل.", code="STALE_VERSION")
    d.execute("""INSERT INTO approval_decisions(plan_version_id, action, from_status, to_status, actor_id, actor_role, comment, item_comments)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
              [version["id"], action, from_status, to_status, user["id"], user["role_code"], comment, item_comments or {}])
    return row


def submit(d, user, episode_id):
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    rbac.require_perm(user, "plan.author")
    plan = _plan(d, ep["id"])
    draft = plan and d.one("SELECT * FROM plan_versions WHERE plan_id=%s AND status='DRAFT'", [plan["id"]])
    if not draft:
        raise NotFound("لا توجد مسودة")
    if draft["author_id"] != user["id"]:
        raise Forbidden("يرسل المسودة كاتبها")
    its = items(d, draft["id"])
    blockers = submission_blockers(d, ep, p, draft, its)
    if blockers:
        raise RuleBlocked("لا يمكن الإرسال للمراجعة", details={"blockers": blockers})
    av = d.one("""SELECT av.id FROM assessment_versions av JOIN assessments a ON a.id=av.assessment_id
                  WHERE a.episode_id=%s ORDER BY av.version_no DESC LIMIT 1""", [ep["id"]])
    sf = asvc.current_safety(d, ep["id"])
    d.execute("UPDATE plan_versions SET assessment_version_id=%s, safety_snapshot=%s WHERE id=%s AND status='DRAFT'",
              [av["id"], {k: sf[k] for k in ("status", "triggered", "flags", "rules_version")}, draft["id"]])
    row = _transition(d, user, draft, "SUBMIT", "SUBMITTED")
    audit(d, user, "PLAN_SUBMIT", "plan_version", draft["id"], patient_id=p["id"], details={"version": draft["version_no"]})
    return row


def _load_version_for_review(d, user, version_id):
    pv = d.one("SELECT * FROM plan_versions WHERE id=%s::uuid", [v.uid(version_id)])
    if not pv:
        raise NotFound()
    plan = d.one("SELECT * FROM treatment_plans WHERE id=%s", [pv["plan_id"]])
    ep, p = rbac.load_episode_scoped(d, user, plan["episode_id"])
    return pv, ep, p


def review_blockers_for_approval(d, ep, p, pv):
    b = submission_blockers(d, ep, p, pv, items(d, pv["id"]))
    a = d.one("SELECT * FROM assessments WHERE episode_id=%s", [ep["id"]])
    latest_av = d.one("SELECT id FROM assessment_versions WHERE assessment_id=%s ORDER BY version_no DESC LIMIT 1", [a["id"]])
    if not latest_av or pv["assessment_version_id"] != latest_av["id"] or a["status"] != "FINALIZED":
        b.append("التقييم عُدّل بعد إرسال الخطة: أعد الخطة للتعديل ليُعاد إرسالها على أحدث إصدار تقييم")
    open_alerts = d.all("SELECT message FROM alerts WHERE episode_id=%s AND status='OPEN'", [ep["id"]])
    if open_alerts:
        b.append("توجد تنبيهات سلامة لم يُقرّ بها مراجع: " + "؛ ".join(x["message"][:80] for x in open_alerts))
    return b


def decide(d, user, version_id, action, data):
    if action not in REVIEW_ACTIONS:
        raise ValidationError("إجراء غير معروف")
    pv, ep, p = _load_version_for_review(d, user, version_id)
    rbac.require_perm(user, "plan.review")
    if pv["status"] not in TRANSITIONS[action][0]:
        raise RuleBlocked(f"انتقال غير مسموح: «{ACTION_LABELS[action]}» من حالة «{STATUS_LABELS[pv['status']]}»",
                          code="INVALID_TRANSITION")
    if not rbac.can_review_department(user, p["department_id"]):
        raise Forbidden("لا تملك تفويض مراجعة لهذا القسم")
    if pv["author_id"] == user["id"]:
        raise Forbidden("لا يمكن لكاتب الخطة مراجعة أو اعتماد خطته", code="SELF_APPROVAL")
    if pv["status"] == "ESCALATED" and action in ("APPROVE", "REQUEST_CHANGES") and user["role_code"] != rbac.DIRECTOR:
        raise Forbidden("الخطة مصعّدة: القرار للمدير")
    if action == "ESCALATE" and user["role_code"] == rbac.DIRECTOR:
        raise RuleBlocked("المدير هو أعلى مستوى تصعيد")
    comment = v.s(data, "comment", "التعليق", max_len=3000)
    if action != "APPROVE" and not comment:
        raise ValidationError("التعليق مطلوب لهذا القرار")
    item_comments = {}
    ic = data.get("item_comments") or {}
    if isinstance(ic, dict):
        valid_ids = {it["id"] for it in items(d, pv["id"])}
        for k, val in ic.items():
            if k in valid_ids and v.clean_text(val, 1000):
                item_comments[k] = v.clean_text(val, 1000)
    if action == "APPROVE":
        if not v.boolean(data, "evidence_reviewed"):
            raise ValidationError("أكّد أنك راجعت الأدلة والقياسات والتاريخ وعلامات الخطر يدوياً")
        blockers = review_blockers_for_approval(d, ep, p, pv)
        if blockers:
            raise RuleBlocked("لا يمكن الاعتماد", details={"blockers": blockers})
        prev = approved_version(d, ep["id"])
        if prev:
            d.execute("UPDATE plan_versions SET status='SUPERSEDED', updated_at=now() WHERE id=%s", [prev["id"]])
            d.execute("""INSERT INTO approval_decisions(plan_version_id, action, from_status, to_status, actor_id, actor_role, comment)
                         VALUES (%s,'SUPERSEDE','APPROVED','SUPERSEDED',%s,%s,%s)""",
                      [prev["id"], user["id"], user["role_code"], f"استُبدل بالإصدار {pv['version_no']}"])
        row = _transition(d, user, pv, "APPROVE", "APPROVED", comment, item_comments)
    elif action == "HOLD":
        row = _transition(d, user, pv, "HOLD", "ON_HOLD", comment, item_comments)
        if v.boolean(data, "hold_episode"):
            d.execute("UPDATE clinical_episodes SET status='ON_HOLD', hold_reason=%s, version=version+1 WHERE id=%s AND status='OPEN'",
                      [comment, ep["id"]])
    else:
        to = TRANSITIONS[action][1]
        row = _transition(d, user, pv, action, to, comment, item_comments)
    audit(d, user, "PLAN_" + action, "plan_version", pv["id"], patient_id=p["id"], reason=comment,
          details={"version": pv["version_no"], "from": pv["status"], "to": row["status"]})
    return row


# ───────────── views ─────────────

def plan_view(d, user, episode_id):
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    plan = _plan(d, ep["id"])
    vs = versions(d, plan["id"]) if plan else []
    for x in vs:
        x["items"] = items(d, x["id"])
    current = vs[0] if vs else None
    blockers = submission_blockers(d, ep, p, current, current["items"]) if current and current["status"] == "DRAFT" else []
    safety_row = asvc.current_safety(d, ep["id"])
    return {
        "episode": ep, "patient": p, "plan": plan, "versions": vs, "current": current,
        "decisions": decisions(d, [x["id"] for x in vs]), "blockers": blockers,
        "equipment": catalog.equipment(d), "exercises": catalog.exercises(d), "goals": asvc.list_goals(d, ep["id"]), "safety": safety_row,
        "precaution_flags": [f for f in safety_rules.DEVICE_PRECAUTION_FLAGS if f in set(safety_row["flags"] or [])] if safety_row else [],
        "assessment": d.one("SELECT * FROM assessments WHERE episode_id=%s", [ep["id"]]),
    }


def diff_versions(old_items, new_items, old_content, new_content):
    changes = []
    for k in sorted(set(old_content or {}) | set(new_content or {})):
        if (old_content or {}).get(k) != (new_content or {}).get(k):
            changes.append({"field": k, "old": (old_content or {}).get(k), "new": (new_content or {}).get(k)})
    key = lambda it: (it["category"], it["title"])
    om = {key(i): i for i in old_items}
    nm = {key(i): i for i in new_items}
    fields = ("equipment_code", "program_code", "exercise_code", "target", "dosage", "method", "precautions", "progression_criteria", "stop_criteria", "phase")
    for k, it in nm.items():
        if k not in om:
            changes.append({"item": it["title"], "change": "added"})
        else:
            diff = [f for f in fields if (om[k].get(f) or None) != (it.get(f) or None)]
            if diff:
                changes.append({"item": it["title"], "change": "modified", "fields": diff})
    for k, it in om.items():
        if k not in nm:
            changes.append({"item": it["title"], "change": "removed"})
    return changes


def review_view(d, user, version_id):
    pv, ep, p = _load_version_for_review(d, user, version_id)
    if not (rbac.has_perm(user, "plan.review") and rbac.can_review_department(user, p["department_id"])):
        raise Forbidden("لا تملك صلاحية المراجعة لهذا القسم")
    view = asvc.assessment_view(d, user, ep["id"])
    av = d.one("SELECT * FROM assessment_versions WHERE id=%s", [pv["assessment_version_id"]]) if pv["assessment_version_id"] else None
    its = items(d, pv["id"])
    prev = None
    if pv["based_on_version_id"]:
        prev = d.one("SELECT * FROM plan_versions WHERE id=%s", [pv["based_on_version_id"]])
    diff = diff_versions(items(d, prev["id"]), its, prev["content"], pv["content"]) if prev else []
    vs = versions(d, pv["plan_id"])
    return {
        "version": pv, "items": its, "episode": ep, "patient": p, "assessment_version": av, "view": view,
        "decisions": decisions(d, [x["id"] for x in vs]), "versions": vs, "previous": prev, "diff": diff,
        "approval_blockers": review_blockers_for_approval(d, ep, p, pv) if pv["status"] in ("SUBMITTED", "ESCALATED") else [],
        "is_author": pv["author_id"] == user["id"],
        "can_decide": pv["author_id"] != user["id"] and (pv["status"] != "ESCALATED" or user["role_code"] == rbac.DIRECTOR),
        "equipment": catalog.equipment(d), "exercises": catalog.exercises(d), "history_q": catalog.questionnaire(d, "MEDICAL_HISTORY"),
    }


def review_queue(d, user):
    rbac.require_perm(user, "plan.review")
    cond, params = rbac.patient_scope_sql(user, "p", "clinical")
    rows = d.all(
        f"""SELECT pv.id, pv.version_no, pv.status, pv.submitted_at, pv.author_id, a.full_name AS author_name,
                   p.full_name AS patient_name, p.file_no, p.department_id, e.id AS episode_id, e.title,
                   s.status AS safety_status,
                   (SELECT count(*) FROM alerts al WHERE al.episode_id=e.id AND al.status='OPEN') AS open_alerts,
                   (SELECT max(severity) FROM alerts al WHERE al.episode_id=e.id AND al.status='OPEN') AS max_sev
            FROM plan_versions pv JOIN treatment_plans tp ON tp.id=pv.plan_id JOIN clinical_episodes e ON e.id=tp.episode_id
            JOIN patients p ON p.id=e.patient_id JOIN users a ON a.id=pv.author_id
            LEFT JOIN safety_screenings s ON s.episode_id=e.id AND s.is_current
            WHERE pv.status IN ('SUBMITTED','ESCALATED','ON_HOLD') AND ({cond})
            ORDER BY (pv.status='ESCALATED') DESC, (s.status='NEEDS_REVIEW') DESC, pv.submitted_at""", params)
    out = []
    for r in rows:
        r["can_decide"] = (r["author_id"] != user["id"] and rbac.can_review_department(user, r["department_id"])
                           and (r["status"] != "ESCALATED" or user["role_code"] == rbac.DIRECTOR))
        out.append(r)
    return out
