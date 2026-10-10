"""Shared test helpers. Tests always run against the separate *test* database."""
import os

if os.environ.get("ML_DEMO_SCRIPT") != "1":
    os.environ["ML_ENV"] = "test"
    os.environ["ML_TEST"] = "1"

from app import db  # noqa: E402
from app.clinical.definitions import SAFETY_QUESTIONS  # noqa: E402
from app.security import load_user  # noqa: E402
from scripts import migrate, seed  # noqa: E402

_ready = False


def reset_db():
    global _ready
    db.pool().close_all()
    migrate.run(reset=True, quiet=True)
    import io, contextlib
    with db.tx() as d, contextlib.redirect_stdout(io.StringIO()):
        seed.seed_reference(d)
        seed.seed_demo(d)
    from app.services import catalog
    catalog.clear_cache()
    _ready = True


def u(d, username):
    uid = d.scalar("SELECT id FROM users WHERE username=%s", [username])
    return load_user(d, uid)


def patient_id(d, name_like):
    return d.scalar("SELECT id FROM patients WHERE full_name LIKE %s ORDER BY created_at LIMIT 1", ["%" + name_like + "%"])


def safety_all_no(**overrides):
    items = []
    for q in SAFETY_QUESTIONS:
        val = overrides.get(q["code"], "NO")
        if val in ("UNKNOWN", "NOT_ASKED"):
            items.append({"code": q["code"], "status": val})
        else:
            items.append({"code": q["code"], "status": "ANSWERED", "value": val})
    return items


def with_base(items, current):
    for it in items:
        cur = current.get(it["code"])
        it["base_id"] = cur["id"] if cur else None
    return items


def lumbar_core():
    return [
        {"code": "LB_PRESENTING_PROBLEM", "status": "ANSWERED", "value": "ألم أسفل الظهر عند الجلوس الطويل"},
        {"code": "LB_ONSET_MODE", "status": "ANSWERED", "value": "GRADUAL"},
        {"code": "LB_DURATION_CATEGORY", "status": "ANSWERED", "value": "SUBACUTE"},
        {"code": "LB_PAIN_LOCATION", "status": "ANSWERED", "value": ["CENTRAL"]},
        {"code": "LB_DISTRIBUTION", "status": "ANSWERED", "value": "BACK_ONLY"},
        {"code": "LB_PAIN_NOW", "status": "ANSWERED", "value": 6},
        {"code": "LB_AGG", "status": "ANSWERED", "value": ["SITTING", "BENDING_FWD"]},
        {"code": "LB_NEURO_SYMPTOMS", "status": "ANSWERED", "value": ["NONE"]},
        {"code": "LB_SPINE_SURGERY", "status": "ANSWERED", "value": "NO"},
        {"code": "LB_ACTIVITY_LIMITS", "status": "ANSWERED", "value": "صعوبة الجلوس في العمل أكثر من 20 دقيقة"},
        {"code": "LB_PAIN_CLASSIFICATION", "status": "ANSWERED", "value": "LOCAL"},
        {"code": "LB_CERTAINTY", "status": "ANSWERED", "value": "MODERATE"},
        {"code": "LB_CLINICAL_IMPRESSION", "status": "ANSWERED", "value": "ألم ظهر موضعي يزداد بالجلوس والانحناء"},
    ]


def complete_assessment(d, therapist, episode_id):
    """Fill a complete, safe lumbar assessment and finalise it. Returns assessment view."""
    from app.services import assessment as asvc, questionnaire as qs
    ep = d.one("SELECT * FROM clinical_episodes WHERE id=%s", [episode_id])
    cur = qs.get_answers(d, ep["patient_id"], episode_id)
    asvc.save_lumbar_answers(d, therapist, episode_id, with_base(safety_all_no() + lumbar_core(), cur))
    view = asvc.assessment_view(d, therapist, episode_id)
    for r in view["recommended"]:
        if not r["recommended"]:
            continue
        t = view["tests"][r["code"]]
        if t["result_type"] in ("rom", "value"):
            data = {"test_code": r["code"], "result": "RECORDED", "value_num": 20, "side": "RIGHT" if t.get("sides") else "NA"}
        elif t["result_type"] == "text":
            data = {"test_code": r["code"], "result": "RECORDED", "value_text": "وصف تجريبي"}
        else:
            data = {"test_code": r["code"], "result": "NOT_DONE", "not_done_reason": "غير مستطب بعد التقييم",
                    "side": "RIGHT" if t.get("sides") else "NA"}
        if t.get("sides") and t["result_type"] in ("rom",):
            asvc.record_exam_result(d, therapist, episode_id, dict(data, side="LEFT"))
        asvc.record_exam_result(d, therapist, episode_id, data)
    g = asvc.add_goal(d, therapist, episode_id, {"description": "الجلوس 30 دقيقة دون زيادة الألم", "measure": "زمن الجلوس",
                                                  "baseline_value": "15", "target_value": "30", "unit": "دقيقة"})
    asvc.record_outcome(d, therapist, episode_id, {"measure_code": "NPRS_NOW", "timepoint": "BASELINE", "value": 6})
    asvc.record_outcome(d, therapist, episode_id, {"measure_code": "PSFS_ITEM", "label": "الجلوس في العمل", "timepoint": "BASELINE", "value": 4})
    asvc.finalize(d, therapist, episode_id, "تقييم أولي")
    return g


PLAN_DATA = {
    "content": {"impression": "ألم ظهر موضعي ميكانيكي مرتبط بالجلوس", "certainty": "MODERATE", "rationale": "حسب الفحص",
                "sessions_planned": 10, "frequency_per_week": 2, "reassessment": "بعد الجلسة 6 و12 أو عند الحاجة"},
    "items": [
        {"category": "GYM", "title": "تمارين تحكم حركي", "dosage": "3 مجموعات × 10", "stop_criteria": "زيادة الألم > 2 نقطة",
         "phase": "1-2"},
        {"category": "HOME", "title": "برنامج مشي منزلي", "dosage": "10 دقائق يومياً", "stop_criteria": "ألم ممتد للساق"},
        {"category": "DEVICE", "title": "علاج بجهاز", "equipment_code": "EQ03", "dosage": "حسب تقدير المختص وتعليمات الشركة",
         "contraindications_reviewed": True, "precautions": "لا يوجد"},
    ],
}
