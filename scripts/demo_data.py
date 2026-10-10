"""Build a richer SYNTHETIC demo scenario in the development DB (after `python -m scripts.seed`).

- سامر تجريبي الأول: full pathway (history, safe assessment, approved plan, 6 sessions, review after session 6)
- خالد تجريبي الثاني: assessment in progress with a safety signal (cancer history) that needs clinical review
- ريم تجريبية الثالثة: new patient, nothing entered (to try the flow yourself)
"""
import datetime as dt
import os

os.environ["ML_DEMO_SCRIPT"] = "1"

from app import config, db
from app.services import assessment as asvc, episodes, plans, questionnaire as qs, sessions
from tests import support as S  # noqa: E402  (helpers only; does NOT switch DB here)

if config.IS_PROD and not config.ALLOW_DEMO:
    raise SystemExit("refusing in production")


def history(d, user, pid, extra=()):
    cur = qs.get_answers(d, pid)
    items = [
        {"code": "HX_MAIN_PROBLEM", "status": "ANSWERED", "value": "ألم أسفل الظهر يزداد مع الجلوس في العمل"},
        {"code": "HX_ONSET_MODE", "status": "ANSWERED", "value": ["GRADUAL"]},
        {"code": "HX_PAIN_NOW", "status": "ANSWERED", "value": 6},
        {"code": "HX_IMPLANTS", "status": "ANSWERED", "value": ["NONE"]},
        {"code": "HX_MED_CLASSES", "status": "ANSWERED", "value": ["NONE"]},
        {"code": "HX_MAIN_GOAL", "status": "ANSWERED", "value": "أن أجلس في العمل ساعة دون ألم"},
        {"code": "HX_DECLARATION_PAPER", "status": "ANSWERED", "value": "YES"},
    ] + list(extra)
    asvc.save_history_answers(d, user, pid, S.with_base(items, cur))


with db.tx() as d:
    if d.scalar("SELECT count(*) FROM clinical_episodes"):
        print("demo episodes already exist — skipped")
        raise SystemExit(0)
    ta, tb = S.u(d, "therapist.a"), S.u(d, "therapist.b")
    head = S.u(d, "head.men")
    samer, khaled = S.patient_id(d, "سامر"), S.patient_id(d, "خالد")

    history(d, ta, samer)
    ep = episodes.create_episode(d, ta, samer, {"region": "LUMBAR", "title": "ألم أسفل الظهر الميكانيكي"})
    S.complete_assessment(d, ta, ep["id"])
    plans.save_draft(d, ta, ep["id"], S.PLAN_DATA)
    plans.submit(d, ta, ep["id"])
    pv = plans.plan_view(d, ta, ep["id"])["current"]
    plans.decide(d, head, pv["id"], "APPROVE", {"evidence_reviewed": True, "comment": "خطة مناسبة"})
    pv = plans.approved_version(d, ep["id"])
    its = plans.items(d, pv["id"])
    start = dt.date.today() - dt.timedelta(days=21)
    for i in range(6):
        sessions.create_session(d, ta, ep["id"], {
            "session_date": (start + dt.timedelta(days=3 * i)).isoformat(), "pain_before": 6 - i // 2, "pain_after": 5 - i // 2,
            "response": "استجابة جيدة، تحمل التمارين", "interventions": [{"plan_item_id": it["id"]} for it in its[:2]]})
    sessions.create_progress_review(d, ta, ep["id"], {
        "milestone": "S6", "summary": "تحسن تحمل الجلوس إلى 25 دقيقة، والألم 4/10", "decision": "CONTINUE",
        "measures": [{"measure_code": "NPRS_NOW", "value": 4}, {"measure_code": "PSFS_ITEM", "label": "الجلوس في العمل", "value": 6}]})

    history(d, tb, khaled, [{"code": "HX_COND_CANCER", "status": "ANSWERED", "value": "YES"}])
    ep2 = episodes.create_episode(d, tb, khaled, {"region": "LUMBAR", "title": "ألم ظهر مع امتداد للساق اليمنى"})
    cur = qs.get_answers(d, khaled, ep2["id"])
    core = [x for x in S.lumbar_core() if x["code"] not in ("LB_DISTRIBUTION", "LB_NEURO_SYMPTOMS")] + [
        {"code": "LB_DISTRIBUTION", "status": "ANSWERED", "value": "BELOW_KNEE"},
        {"code": "LB_DISTRIBUTION_SIDE", "status": "ANSWERED", "value": "RIGHT"},
        {"code": "LB_NEURO_SYMPTOMS", "status": "ANSWERED", "value": ["TINGLING"]},
        {"code": "LB_NEURO_CHANGE", "status": "ANSWERED", "value": "STABLE"},
        {"code": "LB_NEURO_DISTRIBUTION", "status": "ANSWERED", "value": "وخز على الوجه الوحشي للساق اليمنى"}]
    asvc.save_lumbar_answers(d, tb, ep2["id"], S.with_base(S.safety_all_no(SF_CANCER_HISTORY="YES") + core, cur))
print("demo scenario created")
