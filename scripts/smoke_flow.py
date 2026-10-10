"""Quick service-level run of the full pathway against the test DB (developer smoke check)."""
from tests import support as S  # sets ML_ENV=test
from app import db
from app.services import episodes, plans, sessions

S.reset_db()
with db.tx() as d:
    ta = S.u(d, "therapist.a")
    head = S.u(d, "head.men")
    pid = S.patient_id(d, "سامر")
    ep = episodes.create_episode(d, ta, pid, {"region": "LUMBAR", "title": "ألم أسفل الظهر"})
    S.complete_assessment(d, ta, ep["id"])
    dr = plans.save_draft(d, ta, ep["id"], S.PLAN_DATA)
    print("blockers", plans.plan_view(d, ta, ep["id"])["blockers"])
    plans.submit(d, ta, ep["id"])
    pv = plans.plan_view(d, ta, ep["id"])["current"]
    plans.decide(d, head, pv["id"], "APPROVE", {"evidence_reviewed": True, "comment": "معتمد"})
    pv = plans.approved_version(d, ep["id"])
    its = plans.items(d, pv["id"])
    r = sessions.create_session(d, ta, ep["id"], {"session_date": "2026-10-10", "pain_before": 6, "pain_after": 4,
                                                  "interventions": [{"plan_item_id": its[0]["id"], "performed": True}]})
    print("session", r)
print("OK")
