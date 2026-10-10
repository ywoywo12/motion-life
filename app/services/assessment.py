"""Lumbar assessment: safety screening, exam results with safety gating, goals, baseline outcomes, finalisation."""
from __future__ import annotations

from .. import rbac
from ..audit import audit
from ..clinical import engine, safety
from ..errors import Forbidden, NotFound, RuleBlocked, ValidationError
from .. import validation as v
from . import catalog, questionnaire as qsvc

LUMBAR = "LUMBAR_ASSESSMENT"
HISTORY = "MEDICAL_HISTORY"

RESULTS = ("POSITIVE", "NEGATIVE", "INCONCLUSIVE", "NOT_DONE", "RECORDED")
RESULT_LABELS = {"POSITIVE": "إيجابي", "NEGATIVE": "سلبي", "INCONCLUSIVE": "غير حاسم", "NOT_DONE": "لم يُجرَ",
                 "RECORDED": "مُسجّل"}
SIDES = ("LEFT", "RIGHT", "BILATERAL", "CENTRAL", "NA")
SIDE_LABELS = {"LEFT": "يسار", "RIGHT": "يمين", "BILATERAL": "الجهتان", "CENTRAL": "مركزي", "NA": "—"}
GRADES = ("0", "1", "2", "3", "4", "5", "NT")
SENSORY = ("NORMAL", "REDUCED", "ABSENT", "INCREASED", "NT")
SENSORY_LABELS = {"NORMAL": "طبيعي", "REDUCED": "ناقص", "ABSENT": "غائب", "INCREASED": "زائد", "NT": "لم يُفحص"}
REFLEX = ("NORMAL", "REDUCED", "ABSENT", "BRISK", "NT")
REFLEX_LABELS = {"NORMAL": "طبيعي", "REDUCED": "ناقص", "ABSENT": "غائب", "BRISK": "مشتد", "NT": "لم يُفحص"}
REPEATED_RESPONSES = {"BETTER": "تحسن", "WORSE": "تفاقم", "CENTRALIZED": "تمركز", "PERIPHERALIZED": "انتشار محيطي",
                      "NO_EFFECT": "لا تغيير"}


def _assessment(d, episode_id):
    a = d.one("SELECT * FROM assessments WHERE episode_id=%s", [episode_id])
    if not a:
        raise NotFound()
    return a


def current_exam_results(d, assessment_id):
    rows = d.all("""SELECT r.*, u.full_name AS recorded_by_name FROM exam_results r JOIN users u ON u.id=r.recorded_by
                    WHERE r.assessment_id=%s AND r.superseded_at IS NULL ORDER BY r.recorded_at""", [assessment_id])
    for r in rows:
        r["value_num"] = float(r["value_num"]) if r["value_num"] is not None else None
    return rows


def current_safety(d, episode_id):
    return d.one("SELECT * FROM safety_screenings WHERE episode_id=%s AND is_current", [episode_id])


def recompute_safety(d, user, episode, patient):
    """Evaluate the rule engine and persist (new screening row only when the result changes); sync alerts."""
    lumbar = qsvc.answers_plain(d, patient["id"], episode["id"])
    history = qsvc.answers_plain(d, patient["id"], None)
    a = _assessment(d, episode["id"])
    res = safety.evaluate(lumbar, history, patient, current_exam_results(d, a["id"]))
    cur = current_safety(d, episode["id"])
    changed = (not cur or cur["status"] != res["status"] or cur["triggered"] != res["triggered"]
               or cur["missing"] != res["missing"] or cur["flags"] != res["flags"])
    if changed:
        d.execute("UPDATE safety_screenings SET is_current=false WHERE episode_id=%s AND is_current", [episode["id"]])
        d.execute("""INSERT INTO safety_screenings(episode_id, status, triggered, missing, flags, rules_version, computed_by)
                     VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                  [episode["id"], res["status"], res["triggered"], res["missing"], res["flags"], res["rules_version"], user["id"]])
        audit(d, user, "SAFETY_EVALUATED", "episode", episode["id"], patient_id=patient["id"],
              details={"status": res["status"], "rules": [t["rule"] for t in res["triggered"]],
                       "missing": len(res["missing"]), "previous": cur["status"] if cur else None})
    _sync_alerts(d, user, episode, patient, res)
    if res["status"] == "EMERGENCY" and episode["status"] == "OPEN":
        d.execute("UPDATE clinical_episodes SET status='ON_HOLD', hold_reason=%s, version=version+1 WHERE id=%s",
                  ["تعليق آلي: مسار إسعافي في فرز السلامة", episode["id"]])
        _hold_open_plans(d, user, episode, "تعليق آلي: ظهر مسار إسعافي في فرز السلامة")
        audit(d, user, "EPISODE_AUTO_HOLD", "episode", episode["id"], patient_id=patient["id"],
              reason="EMERGENCY safety status")
    return res


def _hold_open_plans(d, user, episode, comment):
    rows = d.all("""SELECT pv.id, pv.status FROM plan_versions pv JOIN treatment_plans tp ON tp.id=pv.plan_id
                    WHERE tp.episode_id=%s AND pv.status IN ('SUBMITTED','ESCALATED','APPROVED','DRAFT')""", [episode["id"]])
    for r in rows:
        if r["status"] == "DRAFT":
            continue  # drafts stay editable but cannot be submitted while safety is EMERGENCY
        d.execute("UPDATE plan_versions SET status='ON_HOLD', updated_at=now() WHERE id=%s", [r["id"]])
        d.execute("""INSERT INTO approval_decisions(plan_version_id, action, from_status, to_status, actor_id, actor_role, comment)
                     VALUES (%s,'HOLD',%s,'ON_HOLD',%s,%s,%s)""", [r["id"], r["status"], user["id"], user["role_code"], comment])


def _sync_alerts(d, user, episode, patient, res):
    sev_map = {"EMERGENCY": "CRITICAL", "URGENT": "HIGH", "REVIEW": "MEDIUM"}
    active = {}
    for t in res["triggered"]:
        active[t["rule"]] = t
    open_rows = d.all("SELECT id, code FROM alerts WHERE episode_id=%s AND status <> 'RESOLVED' AND code LIKE %s",
                      [episode["id"], "SAFETY:%"])
    open_codes = {r["code"]: r for r in open_rows}
    for rule, t in active.items():
        code = "SAFETY:" + rule
        if code not in open_codes:
            d.execute("""INSERT INTO alerts(patient_id, episode_id, severity, code, message, details, created_by)
                         VALUES (%s,%s,%s,%s,%s,%s,%s)""",
                      [patient["id"], episode["id"], sev_map[t["severity"]], code, t["message"],
                       {"because": t["because"], "action": t["action"]}, user["id"]])
    for code, r in open_codes.items():
        if code[len("SAFETY:"):] not in active:
            d.execute("UPDATE alerts SET status='RESOLVED', resolved_at=now() WHERE id=%s", [r["id"]])
            audit(d, user, "ALERT_AUTO_RESOLVED", "alert", r["id"], patient_id=patient["id"],
                  reason="القاعدة لم تعد منطبقة بعد تعديل الإجابات")


def save_lumbar_answers(d, user, episode_id, items):
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    _require_writer(d, user, p)
    if ep["status"] == "CLOSED":
        raise RuleBlocked("الحلقة مغلقة")
    out = qsvc.save_answers(d, user, p, ep, LUMBAR, items, {"sex": p["sex"]})
    if out["saved"]:
        _mark_assessment_dirty(d, ep["id"])
    out["safety"] = recompute_safety(d, user, ep, p)
    return out


def save_history_answers(d, user, patient_id, items):
    p = rbac.load_patient_scoped(d, user, patient_id, "clinical")
    _require_writer(d, user, p)
    out = qsvc.save_answers(d, user, p, None, HISTORY, items, {"sex": p["sex"]})
    if out["saved"]:
        for ep in d.all("SELECT * FROM clinical_episodes WHERE patient_id=%s AND status <> 'CLOSED'", [p["id"]]):
            recompute_safety(d, user, ep, p)
    return out


def _require_writer(d, user, patient):
    rbac.require_perm(user, "clinical.write")
    # load_*_scoped already enforces the patient scope (assignment / department / director)


def _mark_assessment_dirty(d, episode_id):
    d.execute("UPDATE assessments SET status='IN_PROGRESS', updated_at=now(), version=version+1 WHERE episode_id=%s", [episode_id])


# ───────────── exam ─────────────

def recommended_tests(lumbar_answers, tests_catalog, flags, sex=None):
    out = []
    for code, t in tests_catalog.items():
        cond = t.get("recommend_if")
        always = t["category"] in ("observation", "rom")
        rec = always or (cond is not None and engine.eval_cond(cond, lumbar_answers, {"sex": sex}))
        blocked = [f for f in t.get("blocked_by", []) if f in flags]
        out.append({"code": code, "recommended": bool(rec), "blocked_by": blocked})
    return out


def test_gate(safety_row, test):
    """Returns None if recording a real result is allowed, else the Arabic reason."""
    st = safety_row["status"] if safety_row else "NOT_CONFIRMED"
    if st in ("NOT_CONFIRMED", "INCOMPLETE"):
        return "أكمل فرز السلامة أولاً: لا تُسجَّل نتائج الاختبارات قبل حسم أسئلة السلامة الإلزامية."
    flags = set(safety_row["flags"] or [])
    if st == "EMERGENCY" and test.get("provocative"):
        return "المسار إسعافي: الاختبارات الاستفزازية معلّقة."
    blocked = [safety.FLAG_LABELS.get(f, f) for f in test.get("blocked_by", []) if f in flags]
    if blocked:
        return "الاختبار محجوب: " + "، ".join(blocked)
    return None


def record_exam_result(d, user, episode_id, data):
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    _require_writer(d, user, p)
    if ep["status"] == "CLOSED":
        raise RuleBlocked("الحلقة مغلقة")
    a = _assessment(d, ep["id"])
    tests = catalog.tests(d)
    raw_code = v.s(data, "test_code", "الاختبار", required=True, max_len=60)
    base_code, _, sub = raw_code.partition(":")
    t = tests.get(base_code)
    if not t:
        raise ValidationError("اختبار غير موجود في الكتالوج المنشور")
    if t.get("sublevels") and sub not in [s[0] for s in t["sublevels"]]:
        raise ValidationError("مستوى غير صالح لهذا الاختبار")
    side = v.choice(data, "side", "الجهة", SIDES) or "NA"
    if t.get("sides") and side == "NA":
        raise ValidationError("حدّد الجهة لهذا الاختبار")
    result = v.choice(data, "result", "النتيجة", RESULTS, required=True)
    not_done_reason = v.s(data, "not_done_reason", "سبب عدم الإجراء", max_len=300)
    if result == "NOT_DONE":
        if not not_done_reason:
            raise ValidationError("سبب عدم إجراء الاختبار مطلوب")
    else:
        gate = test_gate(current_safety(d, ep["id"]), t)
        if gate:
            raise RuleBlocked(gate, code="SAFETY_GATE")
    rt = t["result_type"]
    value_num = value_text = None
    details = {}
    if result != "NOT_DONE":
        if rt == "posneg":
            if result not in ("POSITIVE", "NEGATIVE", "INCONCLUSIVE"):
                raise ValidationError("النتيجة يجب أن تكون إيجابي/سلبي/غير حاسم")
            value_num = v.num(data, "value_num", "الزاوية/القيمة", lo=0, hi=180)
            details["reproduces_familiar"] = v.boolean(data, "reproduces_familiar")
        elif rt in ("value", "rom"):
            value_num = v.num(data, "value_num", "القيمة", lo=-50, hi=1000)
            value_text = v.s(data, "value_text", "الوصف", max_len=300)
            if value_num is None and not value_text:
                raise ValidationError("أدخل قيمة أو وصفاً")
            details["symptoms"] = v.s(data, "symptoms", "الأعراض المرافقة", max_len=300)
            result = "RECORDED" if result not in ("RECORDED",) else result
        elif rt == "grade":
            value_text = v.choice(data, "value_text", "الدرجة", GRADES, required=True)
            result = "RECORDED"
        elif rt == "sensory":
            value_text = v.choice(data, "value_text", "الإحساس", SENSORY, required=True)
            result = "RECORDED"
        elif rt == "reflex":
            value_text = v.choice(data, "value_text", "المنعكس", REFLEX, required=True)
            result = "RECORDED"
        elif rt == "repeated":
            details = {
                "movement": v.s(data, "movement", "الحركة المستخدمة", required=True, max_len=120),
                "reps": v.num(data, "reps", "عدد التكرارات", lo=1, hi=100, integer=True, required=True),
                "before": v.s(data, "before", "الأعراض قبل", required=True, max_len=300),
                "after": v.s(data, "after", "الأعراض بعد", required=True, max_len=300),
                "response": v.choice(data, "response", "الاستجابة", tuple(REPEATED_RESPONSES), required=True),
            }
            result = "RECORDED"
        else:  # text
            value_text = v.s(data, "value_text", "الوصف", required=True, max_len=1000)
            result = "RECORDED"
    notes = v.s(data, "notes", "ملاحظات", max_len=1000)
    prev = d.one("""SELECT * FROM exam_results WHERE assessment_id=%s AND test_code=%s AND side=%s AND superseded_at IS NULL""",
                 [a["id"], raw_code, side])
    amended_reason = None
    if prev:
        amended_reason = v.s(data, "amend_reason", "سبب تعديل النتيجة", max_len=300)
        if prev["recorded_by"] != user["id"] and not amended_reason:
            raise ValidationError("تعديل نتيجة سجّلها مستخدم آخر يتطلب ذكر السبب (لا تعديل صامت)", code="AMEND_REASON_REQUIRED")
        d.execute("UPDATE exam_results SET superseded_at=now() WHERE id=%s", [prev["id"]])
    rid = d.scalar(
        """INSERT INTO exam_results(assessment_id, test_code, catalog_version, side, result, value_num, value_text, unit, details,
                                    not_done_reason, notes, recorded_by, amended_reason)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
        [a["id"], raw_code, t["catalog_version"], side, result, value_num, value_text, t.get("unit"), details,
         not_done_reason if result == "NOT_DONE" else None, notes, user["id"], amended_reason])
    _mark_assessment_dirty(d, ep["id"])
    audit(d, user, "EXAM_RESULT_AMEND" if prev else "EXAM_RESULT_RECORD", "exam_result", rid, patient_id=p["id"],
          reason=amended_reason, details={"test": raw_code, "side": side, "result": result,
                                          "previous_by": prev["recorded_by"] if prev else None})
    if base_code == "NEURO_DERMATOMES":
        recompute_safety(d, user, ep, p)
    return rid


# ───────────── goals & outcomes ─────────────

def add_goal(d, user, episode_id, data):
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    _require_writer(d, user, p)
    g = d.one("""INSERT INTO goals(episode_id, description, measure, baseline_value, target_value, unit, target_date, created_by)
                 VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
              [ep["id"], v.s(data, "description", "وصف الهدف", required=True, max_len=300),
               v.s(data, "measure", "طريقة القياس", required=True, max_len=200),
               v.s(data, "baseline_value", "قيمة البداية", max_len=60),
               v.s(data, "target_value", "القيمة المستهدفة", required=True, max_len=60),
               v.s(data, "unit", "الوحدة", max_len=30),
               v.date(data, "target_date", "التاريخ المستهدف", not_future=False), user["id"]])
    _mark_assessment_dirty(d, ep["id"])
    audit(d, user, "GOAL_ADD", "goal", g["id"], patient_id=p["id"])
    return g


def update_goal_status(d, user, episode_id, goal_id, status, reason=None):
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    _require_writer(d, user, p)
    status = v.choice({"s": status}, "s", "حالة الهدف", ("ACTIVE", "ACHIEVED", "PARTIAL", "NOT_ACHIEVED", "DROPPED"), required=True)
    n = d.execute("UPDATE goals SET status=%s, updated_at=now() WHERE id=%s::uuid AND episode_id=%s",
                  [status, v.uid(goal_id), ep["id"]]).rowcount
    if not n:
        raise NotFound()
    audit(d, user, "GOAL_STATUS", "goal", goal_id, patient_id=p["id"], reason=reason, details={"status": status})


def list_goals(d, episode_id):
    return d.all("SELECT * FROM goals WHERE episode_id=%s ORDER BY created_at", [episode_id])


def record_outcome(d, user, episode_id, data, progress_review_id=None, session_id=None):
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    _require_writer(d, user, p)
    outs = catalog.outcomes(d)
    code = v.s(data, "measure_code", "المقياس", required=True, max_len=40)
    oc = outs.get(code)
    if not oc:
        raise ValidationError("مقياس غير معروف")
    if not oc.get("enabled", True):
        raise RuleBlocked("هذا المقياس غير مفعّل (يتطلب ترخيصاً). " + (oc.get("note") or ""))
    label = v.s(data, "label", "اسم النشاط", max_len=120, required=bool(oc.get("labelled")))
    tp = v.choice(data, "timepoint", "نقطة القياس", ("BASELINE", "S6", "S12", "DISCHARGE", "OTHER"), required=True)
    val = v.num(data, "value", "القيمة", required=True, lo=oc.get("min"), hi=oc.get("max"))
    prev = d.one("""SELECT id FROM outcome_measures WHERE episode_id=%s AND measure_code=%s AND COALESCE(label,'')=COALESCE(%s,'')
                    AND timepoint=%s AND superseded_at IS NULL AND timepoint <> 'OTHER'""", [ep["id"], code, label, tp])
    if prev:
        d.execute("UPDATE outcome_measures SET superseded_at=now() WHERE id=%s", [prev["id"]])
    oid = d.scalar("""INSERT INTO outcome_measures(episode_id, measure_code, label, timepoint, value_num, unit, progress_review_id, session_id, recorded_by)
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                   [ep["id"], code, label, tp, val, oc.get("unit"), progress_review_id, session_id, user["id"]])
    audit(d, user, "OUTCOME_RECORD", "outcome", oid, patient_id=p["id"], details={"measure": code, "timepoint": tp, "label": label})
    return oid


def list_outcomes(d, episode_id):
    rows = d.all("""SELECT o.*, u.full_name AS recorded_by_name FROM outcome_measures o JOIN users u ON u.id=o.recorded_by
                    WHERE o.episode_id=%s AND o.superseded_at IS NULL ORDER BY o.measure_code, o.label, o.recorded_at""", [episode_id])
    for r in rows:
        r["value_num"] = float(r["value_num"])
    return rows


# ───────────── view & finalisation ─────────────

def finalization_blockers(d, ep, p, qn, lumbar, safety_row, exam_rows, goals, outcomes):
    blockers = []
    st = safety_row["status"] if safety_row else "NOT_CONFIRMED"
    if st in ("NOT_CONFIRMED", "INCOMPLETE") or (safety_row and safety_row["missing"]):
        blockers.append("فرز السلامة غير مكتمل: " + "، ".join(m["text"] for m in (safety_row["missing"] if safety_row else [])[:5]))
    missing = engine.completeness([q for q in qn["questions"] if q["section"] != "SAFETY"], lumbar, {"sex": p["sex"]})
    if missing:
        blockers.append("أسئلة إلزامية غير مجابة: " + "، ".join(m["text"] for m in missing[:6])
                        + ("…" if len(missing) > 6 else ""))
    tests = catalog.tests(d)
    flags = set(safety_row["flags"] or []) if safety_row else set()
    rec = recommended_tests(lumbar, tests, flags, p["sex"])
    done_codes = {r["test_code"].split(":")[0] for r in exam_rows}
    lacking = [tests[r["code"]]["name_ar"] for r in rec if r["recommended"] and r["code"] not in done_codes]
    if lacking:
        blockers.append("اختبارات مستطبة دون نتيجة أو سبب عدم إجراء: " + "، ".join(lacking))
    if not [g for g in goals if g["status"] == "ACTIVE"]:
        blockers.append("أضف هدفاً واحداً قابلاً للقياس على الأقل")
    if not [o for o in outcomes if o["timepoint"] == "BASELINE"]:
        blockers.append("سجّل قياساً واحداً على الأقل كنقطة بداية (مثل شدة الألم أو نشاط خاص بالمريض)")
    return blockers


def assessment_view(d, user, episode_id):
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    a = _assessment(d, ep["id"])
    qn = catalog.questionnaire(d, LUMBAR)
    lumbar = qsvc.answers_plain(d, p["id"], ep["id"])
    history = qsvc.answers_plain(d, p["id"], None)
    safety_row = current_safety(d, ep["id"])
    exam_rows = current_exam_results(d, a["id"])
    goals = list_goals(d, ep["id"])
    outcomes = list_outcomes(d, ep["id"])
    tests = catalog.tests(d)
    flags = set(safety_row["flags"] or []) if safety_row else set()
    rec = recommended_tests(lumbar, tests, flags, p["sex"])
    for r in rec:
        r["gate"] = test_gate(safety_row, tests[r["code"]])
    blockers = finalization_blockers(d, ep, p, qn, lumbar, safety_row, exam_rows, goals, outcomes)
    versions = d.all("""SELECT av.id, av.version_no, av.created_at, av.note, u.full_name AS created_by_name FROM assessment_versions av
                        JOIN users u ON u.id=av.created_by WHERE av.assessment_id=%s ORDER BY av.version_no DESC""", [a["id"]])
    alerts = d.all("""SELECT al.*, (SELECT json_agg(json_build_object('user', u.full_name, 'note', k.note, 'at', k.at))
                         FROM alert_acknowledgments k JOIN users u ON u.id=k.user_id WHERE k.alert_id=al.id) AS acks
                      FROM alerts al WHERE al.episode_id=%s AND al.status <> 'RESOLVED' ORDER BY al.created_at""", [ep["id"]])
    referrals = d.all("""SELECT r.*, u.full_name AS decided_by_name FROM referrals r JOIN users u ON u.id=r.decided_by
                         WHERE r.episode_id=%s ORDER BY r.decided_at DESC""", [ep["id"]])
    audit(d, user, "ASSESSMENT_VIEW", "episode", ep["id"], patient_id=p["id"], category="ACCESS")
    return {
        "episode": ep, "patient": p, "assessment": a, "questionnaire": qn, "answers": lumbar, "history": history,
        "safety": safety_row, "exam_results": exam_rows, "tests": tests, "recommended": rec, "goals": goals,
        "outcomes": outcomes, "outcome_catalog": catalog.outcomes(d), "blockers": blockers, "versions": versions,
        "alerts": alerts, "referrals": referrals,
        "visible": sorted(engine.visible_codes(qn["questions"], lumbar, {"sex": p["sex"]})),
    }


def finalize(d, user, episode_id, note=None):
    view = assessment_view(d, user, episode_id)
    ep, p, a = view["episode"], view["patient"], view["assessment"]
    _require_writer(d, user, p)
    if view["blockers"]:
        raise RuleBlocked("لا يمكن إنهاء التقييم بعد", details={"blockers": view["blockers"]})
    if view["safety"]["status"] == "EMERGENCY":
        # an emergency assessment can still be finalised to document the referral, but only with a referral recorded
        if not view["referrals"]:
            raise RuleBlocked("المسار إسعافي: سجّل قرار الإحالة (من قرر ومتى وإلى أين) قبل إنهاء التقييم.")
    snapshot = {
        "questionnaire_version": view["questionnaire"]["version"],
        "answers": view["answers"],
        "history": view["history"],
        "safety": {k: view["safety"][k] for k in ("status", "triggered", "missing", "flags", "rules_version")},
        "exam_results": [{k: (str(r[k]) if k in ("recorded_at",) else r[k]) for k in
                          ("test_code", "side", "result", "value_num", "value_text", "unit", "details", "not_done_reason",
                           "notes", "recorded_by_name", "recorded_at", "catalog_version")} for r in view["exam_results"]],
        "goals": [{k: (str(g[k]) if g[k] is not None and k == "target_date" else g[k]) for k in
                   ("id", "description", "measure", "baseline_value", "target_value", "unit", "target_date", "status")}
                  for g in view["goals"]],
        "outcomes": [{k: o[k] for k in ("measure_code", "label", "timepoint", "value_num", "unit")} for o in view["outcomes"]],
    }
    vn = a["current_version"] + 1
    vid = d.scalar("""INSERT INTO assessment_versions(assessment_id, version_no, snapshot, note, created_by)
                      VALUES (%s,%s,%s,%s,%s) RETURNING id""", [a["id"], vn, snapshot, v.clean_text(note, 1000), user["id"]])
    d.execute("UPDATE assessments SET status='FINALIZED', current_version=%s, updated_at=now(), version=version+1 WHERE id=%s",
              [vn, a["id"]])
    audit(d, user, "ASSESSMENT_FINALIZE", "assessment", a["id"], patient_id=p["id"], details={"version": vn})
    return {"version_id": vid, "version_no": vn}


# ───────────── alerts & referrals ─────────────

def acknowledge_alert(d, user, alert_id, note):
    al = d.one("SELECT * FROM alerts WHERE id=%s::uuid", [v.uid(alert_id)])
    if not al:
        raise NotFound()
    p = rbac.load_patient_scoped(d, user, al["patient_id"], "clinical")
    note = v.s({"n": note}, "n", "ملاحظة الإقرار (ما الذي رُوجع وما القرار)", required=True, max_len=1000)
    if len(note) < 3:
        raise ValidationError("الملاحظة قصيرة جداً")
    d.execute("INSERT INTO alert_acknowledgments(alert_id, user_id, note) VALUES (%s,%s,%s)", [al["id"], user["id"], note])
    if rbac.is_supervisor_of(user, p) or user["role_code"] == rbac.DIRECTOR:
        d.execute("UPDATE alerts SET status='ACKNOWLEDGED' WHERE id=%s AND status='OPEN'", [al["id"]])
    audit(d, user, "ALERT_ACK", "alert", al["id"], patient_id=p["id"], reason=note)


def record_referral(d, user, episode_id, data):
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    rbac.require_perm(user, "clinical.write")
    urgency = v.choice(data, "urgency", "درجة الإلحاح", ("EMERGENCY", "URGENT", "ROUTINE"), required=True)
    rid = d.scalar("""INSERT INTO referrals(episode_id, urgency, destination, reason, patient_informed, decided_by)
                      VALUES (%s,%s,%s,%s,%s,%s) RETURNING id""",
                   [ep["id"], urgency, v.s(data, "destination", "جهة الإحالة", required=True, max_len=200),
                    v.s(data, "reason", "سبب الإحالة", required=True, max_len=1000),
                    v.boolean(data, "patient_informed"), user["id"]])
    audit(d, user, "REFERRAL_DECISION", "referral", rid, patient_id=p["id"], details={"urgency": urgency})
    return rid
