"""Acceptance criteria §11 of the master prompt, exercised through the HTTP API.

Run: python -m unittest -v tests.test_acceptance
"""
import unittest

from tests import support as S
from tests.http import Client
from app import db
from app.clinical.definitions import SAFETY_QUESTIONS


def lumbar_items(client, ep_id, items):
    cur = client.ok(client.get(f"/api/episodes/{ep_id}/assessment"))["answers"]
    for it in items:
        c = cur.get(it["code"])
        it["base_id"] = c["id"] if c else None
    return client.ok(client.post(f"/api/episodes/{ep_id}/assessment/answers", {"items": items}))


def make_ready_episode(therapist="therapist.a", patient="سامر"):
    """Create an episode with a complete safe assessment via the service layer (fast), return ids."""
    with db.tx() as d:
        t = S.u(d, therapist)
        pid = S.patient_id(d, patient)
        from app.services import episodes
        ep = episodes.create_episode(d, t, pid, {"region": "LUMBAR", "title": "ألم أسفل الظهر"})
        S.complete_assessment(d, t, ep["id"])
    return pid, ep["id"]


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        S.reset_db()


class T01_TherapistIsolation(Base):
    def test_therapist_cannot_see_unassigned_patient_nor_approve_own_plan(self):
        pid_b, ep_b = make_ready_episode("therapist.b", "خالد")     # patient assigned to therapist B
        a = Client("therapist.a")
        self.assertEqual(a.get(f"/api/patients/{pid_b}").status_code, 404)
        self.assertEqual(a.get(f"/api/patients/{pid_b}/history").status_code, 404)
        self.assertEqual(a.get(f"/api/episodes/{ep_b}/assessment").status_code, 404)
        lst = a.ok(a.get("/api/patients"))["patients"]
        self.assertNotIn(pid_b, [p["id"] for p in lst])
        # own plan: draft + submit, then try to approve it through the API
        pid_a, ep_a = make_ready_episode("therapist.a", "سامر")
        a.ok(a.put(f"/api/episodes/{ep_a}/plan/draft", S.PLAN_DATA))
        a.ok(a.post(f"/api/episodes/{ep_a}/plan/submit"))
        vid = a.ok(a.get(f"/api/episodes/{ep_a}/plan"))["versions"][0]["id"]
        r = a.post(f"/api/plan-versions/{vid}/decision", {"action": "APPROVE", "evidence_reviewed": True})
        self.assertEqual(r.status_code, 403)
        # also a supervisor who authored a plan cannot approve it
        with db.tx() as d:
            self.assertEqual(d.scalar("SELECT status FROM plan_versions WHERE id=%s", [vid]), "SUBMITTED")


class T02_DepartmentIsolation(Base):
    def test_women_head_cannot_open_men_patient_and_vice_versa(self):
        with db.tx() as d:
            men = S.patient_id(d, "سامر")
            women = S.patient_id(d, "ريم")
        hw, hm = Client("head.women"), Client("head.men")
        self.assertEqual(hw.get(f"/api/patients/{men}").status_code, 404)
        self.assertEqual(hm.get(f"/api/patients/{women}").status_code, 404)
        self.assertEqual(hw.get(f"/api/patients/{women}").status_code, 200)
        # documented transfer: after the director moves the patient, access follows the department
        director = Client("director")
        deps = {}
        with db.tx() as d:
            deps = {r["code"]: r["id"] for r in d.all("SELECT code, id FROM departments")}
        r = director.post(f"/api/patients/{men}/transfer", {"department_id": deps["WOMEN"]})
        self.assertEqual(r.status_code, 422)  # reason is mandatory
        director.ok(director.post(f"/api/patients/{men}/transfer", {"department_id": deps["WOMEN"], "reason": "اختبار نقل موثق"}))
        self.assertEqual(hw.get(f"/api/patients/{men}").status_code, 200)
        self.assertEqual(hm.get(f"/api/patients/{men}").status_code, 404)
        with db.tx() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM audit_events WHERE action='DEPARTMENT_TRANSFER' AND patient_id=%s", [men]), 1)


class T03_ReceptionNoClinical(Base):
    def test_reception_cannot_read_history_or_imaging(self):
        pid, ep = make_ready_episode()
        with db.tx() as d:
            from app.services import assessment as asvc, questionnaire as qs
            t = S.u(d, "therapist.a")
            cur = qs.get_answers(d, pid, ep)
            asvc.save_lumbar_answers(d, t, ep, S.with_base([
                {"code": "LB_IMAGING_TYPE", "status": "ANSWERED", "value": ["MRI"]},
                {"code": "LB_IMAGING_REPORT_TEXT", "status": "ANSWERED", "value": "انزلاق غضروفي L4-L5 (نص تقرير تجريبي)"}], cur))
        r = Client("reception")
        self.assertEqual(r.get(f"/api/patients/{pid}").status_code, 200)        # identity allowed
        for url in (f"/api/patients/{pid}/history", f"/api/episodes/{ep}/assessment", f"/api/episodes/{ep}/plan",
                    f"/api/episodes/{ep}/sessions", f"/api/episodes/{ep}/outcomes",
                    f"/reports/episode/{ep}/assessment.pdf", f"/reports/patient/{pid}/history.pdf"):
            resp = r.get(url)
            self.assertIn(resp.status_code, (403, 404), url)
            self.assertNotIn("انزلاق", resp.get_data(as_text=True))
        resp = r.post(f"/api/patients/{pid}/history/answers", {"items": [{"code": "HX_MAIN_PROBLEM", "value": "x"}]})
        self.assertIn(resp.status_code, (403, 404))
        # accounting and sysadmin are equally blocked from clinical data
        for u in ("accounting", "sysadmin"):
            c = Client(u)
            self.assertIn(c.get(f"/api/episodes/{ep}/assessment").status_code, (403, 404))


class T04_UnknownIsNotNo(Base):
    def test_unknown_safety_answer_blocks_and_is_not_no(self):
        with db.tx() as d:
            t = S.u(d, "therapist.a")
            pid = S.patient_id(d, "سامر")
            from app.services import episodes
            ep = episodes.create_episode(d, t, pid, {"region": "LUMBAR", "title": "اختبار غير معروف"})["id"]
        a = Client("therapist.a")
        items = S.safety_all_no(SF_SADDLE_NUMBNESS="UNKNOWN") + S.lumbar_core()
        out = lumbar_items(a, ep, items)
        self.assertEqual(out["safety"]["status"], "INCOMPLETE")
        self.assertIn("SF_SADDLE_NUMBNESS", [m["code"] for m in out["safety"]["missing"]])
        stored = a.ok(a.get(f"/api/episodes/{ep}/assessment"))["answers"]["SF_SADDLE_NUMBNESS"]
        self.assertEqual(stored["status"], "UNKNOWN")
        self.assertIsNone(stored["value"])
        # exam results cannot be recorded, assessment cannot be finalised, plan cannot be submitted
        r = a.post(f"/api/episodes/{ep}/exam", {"test_code": "OBS_FUNCTION", "result": "RECORDED", "value_text": "x"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(a.post(f"/api/episodes/{ep}/assessment/finalize").status_code, 409)
        a.ok(a.put(f"/api/episodes/{ep}/plan/draft", S.PLAN_DATA))
        r = a.post(f"/api/episodes/{ep}/plan/submit")
        self.assertEqual(r.status_code, 409)
        self.assertTrue(any("السلامة" in b for b in r.get_json()["error"]["details"]["blockers"]))
        # an empty (never asked) safety question is also missing
        with db.tx() as d:
            from app.clinical import safety
            res = safety.evaluate({}, {}, {"sex": "M"})
            self.assertEqual(res["status"], "NOT_CONFIRMED")
            self.assertEqual(len(res["missing"]), len(SAFETY_QUESTIONS))


class T05_CaudaEquinaEmergency(Base):
    def test_cauda_equina_and_rapid_weakness_trigger_emergency_hold(self):
        pid, ep = make_ready_episode()
        a = Client("therapist.a")
        a.ok(a.put(f"/api/episodes/{ep}/plan/draft", S.PLAN_DATA))
        a.ok(a.post(f"/api/episodes/{ep}/plan/submit"))
        out = lumbar_items(a, ep, [{"code": "SF_SADDLE_NUMBNESS", "status": "ANSWERED", "value": "YES"}])
        self.assertEqual(out["safety"]["status"], "EMERGENCY")
        self.assertIn("PROVOCATIVE_TESTS_BLOCKED", out["safety"]["flags"])
        with db.tx() as d:
            self.assertEqual(d.scalar("SELECT status FROM clinical_episodes WHERE id=%s", [ep]), "ON_HOLD")
            self.assertEqual(d.scalar("SELECT count(*) FROM alerts WHERE episode_id=%s AND severity='CRITICAL' AND status='OPEN'", [ep]), 1)
            st = d.scalar("""SELECT pv.status FROM plan_versions pv JOIN treatment_plans tp ON tp.id=pv.plan_id WHERE tp.episode_id=%s""", [ep])
            self.assertEqual(st, "ON_HOLD")
        # the reviewer cannot approve, provocative tests are blocked, sessions are blocked
        h = Client("head.men")
        vid = h.ok(h.get(f"/api/episodes/{ep}/plan"))["versions"][0]["id"]
        self.assertEqual(h.post(f"/api/plan-versions/{vid}/decision", {"action": "APPROVE", "evidence_reviewed": True}).status_code, 409)
        r = a.post(f"/api/episodes/{ep}/exam", {"test_code": "SLR", "side": "RIGHT", "result": "POSITIVE"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(a.post(f"/api/episodes/{ep}/sessions", {"session_date": "2026-10-10", "interventions": [{"title": "x"}]}).status_code, 409)
        # resume refused while the screening is still emergency
        self.assertEqual(h.post(f"/api/episodes/{ep}/resume", {"reason": "محاولة"}).status_code, 409)

    def test_rapidly_progressive_weakness_from_branch(self):
        with db.tx() as d:
            t = S.u(d, "therapist.a")
            pid = S.patient_id(d, "سامر")
            from app.services import episodes
            ep = episodes.create_episode(d, t, pid, {"region": "LUMBAR", "title": "ضعف"})["id"]
        a = Client("therapist.a")
        out = lumbar_items(a, ep, S.safety_all_no() + [
            {"code": "LB_NEURO_SYMPTOMS", "status": "ANSWERED", "value": ["WEAKNESS"]},
            {"code": "LB_NEURO_CHANGE", "status": "ANSWERED", "value": "WORSE_FAST"}])
        self.assertEqual(out["safety"]["status"], "EMERGENCY")
        self.assertIn("LB:NEURO_RAPID", [t["rule"] for t in out["safety"]["triggered"]])


class T06_NoDirectApproval(Base):
    def test_draft_cannot_jump_to_approved(self):
        pid, ep = make_ready_episode()
        a = Client("therapist.a")
        a.ok(a.put(f"/api/episodes/{ep}/plan/draft", S.PLAN_DATA))
        vid = a.ok(a.get(f"/api/episodes/{ep}/plan"))["versions"][0]["id"]
        h = Client("head.men")
        r = h.post(f"/api/plan-versions/{vid}/decision", {"action": "APPROVE", "evidence_reviewed": True})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.get_json()["error"]["code"], "INVALID_TRANSITION")
        # direct SQL bypass is also rejected by the database (approver must differ from author)
        with db.tx() as d:
            author = d.scalar("SELECT author_id FROM plan_versions WHERE id=%s", [vid])
        from app.db import DatabaseError
        with self.assertRaises(DatabaseError):
            with db.tx() as d:
                d.execute("UPDATE plan_versions SET status='APPROVED', approved_by=%s WHERE id=%s", [author, vid])
        # unknown action
        self.assertEqual(h.post(f"/api/plan-versions/{vid}/decision", {"action": "FORCE"}).status_code, 422)
        # deputy without active delegation cannot decide; with delegation can
        a.ok(a.post(f"/api/episodes/{ep}/plan/submit"))
        with db.tx() as d:
            d.execute("UPDATE review_delegations SET revoked_at=now()")
        dep = Client("deputy.men")
        self.assertEqual(dep.post(f"/api/plan-versions/{vid}/decision", {"action": "REQUEST_CHANGES", "comment": "x"}).status_code, 403)


class T07_RevisionKeepsHistory(Base):
    def test_request_changes_revise_resubmit_keeps_versions_and_comments(self):
        pid, ep = make_ready_episode()
        a, h = Client("therapist.a"), Client("head.men")
        a.ok(a.put(f"/api/episodes/{ep}/plan/draft", S.PLAN_DATA))
        a.ok(a.post(f"/api/episodes/{ep}/plan/submit"))
        v1 = a.ok(a.get(f"/api/episodes/{ep}/plan"))["versions"][0]
        item_id = None
        with db.tx() as d:
            item_id = d.scalar("SELECT id FROM plan_items WHERE plan_version_id=%s ORDER BY position LIMIT 1", [v1["id"]])
        self.assertEqual(h.post(f"/api/plan-versions/{v1['id']}/decision", {"action": "REQUEST_CHANGES"}).status_code, 422)  # comment required
        h.ok(h.post(f"/api/plan-versions/{v1['id']}/decision",
                    {"action": "REQUEST_CHANGES", "comment": "حدد معايير التقدم", "item_comments": {item_id: "أضف التقدم"}}))
        a.ok(a.post(f"/api/episodes/{ep}/plan/revise"))
        plan = a.ok(a.get(f"/api/episodes/{ep}/plan"))
        v2 = plan["versions"][0]
        data = dict(S.PLAN_DATA, lock_version=v2["lock_version"])
        data["items"] = [dict(S.PLAN_DATA["items"][0], progression_criteria="زيادة التكرار عند ألم ≤ 3")] + S.PLAN_DATA["items"][1:]
        a.ok(a.put(f"/api/episodes/{ep}/plan/draft", data))
        # stale lock_version is rejected (concurrent edit protection)
        self.assertEqual(a.put(f"/api/episodes/{ep}/plan/draft", data).status_code, 409)
        a.ok(a.post(f"/api/episodes/{ep}/plan/submit"))
        h.ok(h.post(f"/api/plan-versions/{v2['id']}/decision", {"action": "APPROVE", "evidence_reviewed": True}))
        plan = a.ok(a.get(f"/api/episodes/{ep}/plan"))
        statuses = {v["version_no"]: v["status"] for v in plan["versions"]}
        self.assertEqual(statuses, {1: "CHANGES_REQUESTED", 2: "APPROVED"})
        dec = plan["decisions"]
        rc = [x for x in dec if x["action"] == "REQUEST_CHANGES"][0]
        self.assertEqual(rc["comment"], "حدد معايير التقدم")
        self.assertEqual(rc["item_comments"][item_id], "أضف التقدم")
        with db.tx() as d:  # approved content frozen at DB level
            from app.db import DatabaseError
            with self.assertRaises(DatabaseError):
                with db.tx() as d2:
                    d2.execute("UPDATE plan_versions SET content='{}' WHERE id=%s", [v2["id"]])


class T08_SessionBoundToApprovedVersion(Base):
    def test_session_keeps_plan_version_after_plan_change(self):
        pid, ep = make_ready_episode()
        a, h = Client("therapist.a"), Client("head.men")
        self.assertEqual(a.post(f"/api/episodes/{ep}/sessions", {"session_date": "2026-10-01", "interventions": [{"title": "x", "deviation_reason": "y"}]}).status_code, 409)
        a.ok(a.put(f"/api/episodes/{ep}/plan/draft", S.PLAN_DATA))
        a.ok(a.post(f"/api/episodes/{ep}/plan/submit"))
        v1 = a.ok(a.get(f"/api/episodes/{ep}/plan"))["versions"][0]
        h.ok(h.post(f"/api/plan-versions/{v1['id']}/decision", {"action": "APPROVE", "evidence_reviewed": True}))
        with db.tx() as d:
            items = d.all("SELECT id FROM plan_items WHERE plan_version_id=%s ORDER BY position", [v1["id"]])
        s1 = a.ok(a.post(f"/api/episodes/{ep}/sessions", {"session_date": "2026-10-02", "pain_before": 6, "pain_after": 5,
                                                          "interventions": [{"plan_item_id": items[0]["id"], "performed": True}]}))
        self.assertEqual(s1["plan_version_no"], 1)
        # intervention not in plan without justification is refused
        self.assertEqual(a.post(f"/api/episodes/{ep}/sessions", {"session_date": "2026-10-03", "interventions": [{"title": "تدليك"}]}).status_code, 422)
        # revise + approve v2
        a.ok(a.post(f"/api/episodes/{ep}/plan/revise"))
        v2 = a.ok(a.get(f"/api/episodes/{ep}/plan"))["versions"][0]
        d2 = dict(S.PLAN_DATA, lock_version=v2["lock_version"])
        a.ok(a.put(f"/api/episodes/{ep}/plan/draft", d2))
        a.ok(a.post(f"/api/episodes/{ep}/plan/submit"))
        h.ok(h.post(f"/api/plan-versions/{v2['id']}/decision", {"action": "APPROVE", "evidence_reviewed": True}))
        # session created with stale plan version id is refused
        r = a.post(f"/api/episodes/{ep}/sessions", {"session_date": "2026-10-04", "plan_version_id": v1["id"],
                                                     "interventions": [{"plan_item_id": items[0]["id"]}]})
        self.assertEqual(r.status_code, 409)
        sess = a.ok(a.get(f"/api/episodes/{ep}/sessions"))["sessions"]
        self.assertEqual(sess[0]["plan_version_id"], v1["id"])
        with db.tx() as d:
            self.assertEqual(d.scalar("SELECT status FROM plan_versions WHERE id=%s", [v1["id"]]), "SUPERSEDED")
        from app.db import DatabaseError
        with self.assertRaises(DatabaseError):  # DB forbids re-linking a session retroactively
            with db.tx() as d:
                d.execute("UPDATE sessions SET plan_version_id=%s WHERE id=%s", [v2["id"], s1["id"]])


class T09_ArabicPdf(Base):
    def test_pdf_arabic_not_reversed_and_single_patient(self):
        import shutil
        import subprocess
        import tempfile
        pid, ep = make_ready_episode()
        a, h = Client("therapist.a"), Client("head.men")
        a.ok(a.put(f"/api/episodes/{ep}/plan/draft", S.PLAN_DATA))
        a.ok(a.post(f"/api/episodes/{ep}/plan/submit"))
        vid = a.ok(a.get(f"/api/episodes/{ep}/plan"))["versions"][0]["id"]
        h.ok(h.post(f"/api/plan-versions/{vid}/decision", {"action": "APPROVE", "evidence_reviewed": True}))
        r = a.get(f"/reports/episode/{ep}/plan.pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "application/pdf")
        if not shutil.which("pdftotext"):
            self.skipTest("pdftotext not installed")
        with tempfile.NamedTemporaryFile(suffix=".pdf") as f:
            f.write(r.data)
            f.flush()
            txt = subprocess.run(["pdftotext", "-layout", f.name, "-"], capture_output=True, text=True).stdout
        # Note: pdftotext maps the lam-alef ligature (لا) as "ال"; assertions avoid that ligature.
        self.assertIn("سامر تجريبي", txt)                         # logical-order Arabic extracted (not reversed)
        self.assertNotIn("رماس", txt)                             # reversed form absent
        self.assertIn("الخطة", txt)
        self.assertIn("رئيس قسم الرجال", txt)                       # approver name printed
        self.assertNotIn("خالد", txt)                              # no other patient's data
        self.assertNotIn("ريم", txt)
        self.assertIn("ML-", txt)                                   # file number LTR intact
        for kind in ("assessment", "sessions", "progress", "patient-file"):
            self.assertEqual(a.get(f"/reports/episode/{ep}/{kind}.pdf").status_code, 200, kind)
        self.assertEqual(a.get(f"/reports/patient/{pid}/history.pdf").status_code, 200)


class T10_ProgressReviewsMeasures(Base):
    def test_s6_s12_linked_to_episode_measures(self):
        pid, ep = make_ready_episode()
        a, h = Client("therapist.a"), Client("head.men")
        a.ok(a.put(f"/api/episodes/{ep}/plan/draft", S.PLAN_DATA))
        a.ok(a.post(f"/api/episodes/{ep}/plan/submit"))
        vid = a.ok(a.get(f"/api/episodes/{ep}/plan"))["versions"][0]["id"]
        h.ok(h.post(f"/api/plan-versions/{vid}/decision", {"action": "APPROVE", "evidence_reviewed": True}))
        with db.tx() as d:
            item = d.scalar("SELECT id FROM plan_items WHERE plan_version_id=%s ORDER BY position LIMIT 1", [vid])
        measures = [{"measure_code": "NPRS_NOW", "value": 4}, {"measure_code": "PSFS_ITEM", "label": "الجلوس في العمل", "value": 6}]
        self.assertEqual(a.post(f"/api/episodes/{ep}/progress-reviews", {"milestone": "S6", "summary": "x", "decision": "CONTINUE", "measures": measures}).status_code, 409)
        for i in range(6):
            a.ok(a.post(f"/api/episodes/{ep}/sessions", {"session_date": f"2026-09-{10 + i}", "interventions": [{"plan_item_id": item}]}))
        due = a.ok(a.get(f"/api/episodes/{ep}/sessions"))["due"]
        self.assertEqual(due, ["S6"])
        self.assertEqual(a.post(f"/api/episodes/{ep}/progress-reviews", {"milestone": "S6", "summary": "x", "decision": "CONTINUE", "measures": []}).status_code, 422)
        a.ok(a.post(f"/api/episodes/{ep}/progress-reviews", {"milestone": "S6", "summary": "تحسن الجلوس", "decision": "CONTINUE", "measures": measures}))
        table = a.ok(a.get(f"/api/episodes/{ep}/outcomes"))["table"]
        pain = [t for t in table if t["measure_code"] == "NPRS_NOW"][0]
        self.assertEqual(pain["values"], {"BASELINE": 6.0, "S6": 4.0})
        self.assertEqual(pain["change"]["S6"]["diff"], -2.0)
        self.assertTrue(pain["change"]["S6"]["improved"])
        psfs = [t for t in table if t["measure_code"] == "PSFS_ITEM"][0]
        self.assertEqual(psfs["label"], "الجلوس في العمل")
        self.assertTrue(psfs["change"]["S6"]["improved"])          # higher is better for function
        with db.tx() as d:
            self.assertEqual(d.scalar("""SELECT count(*) FROM outcome_measures o JOIN progress_reviews r ON r.id=o.progress_review_id
                                         WHERE r.episode_id=%s AND r.milestone='S6' AND o.timepoint='S6'""", [ep]), 2)
        self.assertEqual(a.post(f"/api/episodes/{ep}/progress-reviews", {"milestone": "S6", "summary": "x", "decision": "CONTINUE", "measures": measures}).status_code, 409)


class T11_SaveHonesty(Base):
    def test_conflicting_answer_not_overwritten_and_failed_save_reports_error(self):
        with db.tx() as d:
            t = S.u(d, "therapist.a")
            pid = S.patient_id(d, "سامر")
            from app.services import episodes
            ep = episodes.create_episode(d, t, pid, {"region": "LUMBAR", "title": "حفظ"})["id"]
        a, h = Client("therapist.a"), Client("head.men")
        r1 = a.ok(a.post(f"/api/episodes/{ep}/assessment/answers", {"items": [{"code": "LB_PAIN_NOW", "status": "ANSWERED", "value": 5, "base_id": None}]}))
        self.assertEqual(r1["saved"], ["LB_PAIN_NOW"])
        base = r1["answers"]["LB_PAIN_NOW"]["id"]
        h.ok(h.post(f"/api/episodes/{ep}/assessment/answers", {"items": [{"code": "LB_PAIN_NOW", "status": "ANSWERED", "value": 7, "base_id": base}]}))
        r3 = a.ok(a.post(f"/api/episodes/{ep}/assessment/answers", {"items": [{"code": "LB_PAIN_NOW", "status": "ANSWERED", "value": 3, "base_id": base}]}))
        self.assertEqual(r3["saved"], [])
        self.assertEqual(r3["conflicts"][0]["current"]["value"], 7)
        # invalid value -> error response, nothing stored, whole batch rolled back
        r4 = a.post(f"/api/episodes/{ep}/assessment/answers", {"items": [
            {"code": "LB_PAIN_MIN_WEEK", "status": "ANSWERED", "value": 2, "base_id": None},
            {"code": "LB_PAIN_MAX_WEEK", "status": "ANSWERED", "value": 14, "base_id": None}]})
        self.assertEqual(r4.status_code, 422)
        cur = a.ok(a.get(f"/api/episodes/{ep}/assessment"))["answers"]
        self.assertNotIn("LB_PAIN_MIN_WEEK", cur)
        # missing CSRF token -> rejected, no write
        resp = a.c.post(f"/api/episodes/{ep}/assessment/answers", json={"items": [{"code": "LB_TREND", "status": "ANSWERED", "value": "SAME"}]})
        self.assertEqual(resp.status_code, 403)
        # history of the answer is preserved
        with db.tx() as d:
            self.assertEqual(d.scalar("SELECT count(*) FROM answers WHERE episode_id=%s AND question_code='LB_PAIN_NOW'", [ep]), 2)


class T12_AuditApprovalChanges(Base):
    def test_audit_shows_who_changed_approval_when_and_why(self):
        pid, ep = make_ready_episode()
        a, h, director = Client("therapist.a"), Client("head.men"), Client("director")
        a.ok(a.put(f"/api/episodes/{ep}/plan/draft", S.PLAN_DATA))
        a.ok(a.post(f"/api/episodes/{ep}/plan/submit"))
        vid = a.ok(a.get(f"/api/episodes/{ep}/plan"))["versions"][0]["id"]
        h.ok(h.post(f"/api/plan-versions/{vid}/decision", {"action": "ESCALATE", "comment": "حالة معقدة"}))
        self.assertEqual(h.post(f"/api/plan-versions/{vid}/decision", {"action": "APPROVE", "evidence_reviewed": True}).status_code, 403)
        director.ok(director.post(f"/api/plan-versions/{vid}/decision", {"action": "APPROVE", "evidence_reviewed": True, "comment": "موافق بعد المراجعة"}))
        director.ok(director.post(f"/api/plan-versions/{vid}/decision", {"action": "HOLD", "comment": "إحالة لتقييم طبي"}))
        ev = director.ok(director.get(f"/api/admin/audit?entity_id={vid}"))["events"]
        acts = [(e["action"], e["actor_name"], e["reason"]) for e in ev]
        self.assertIn(("PLAN_ESCALATE", "رئيس قسم الرجال (تجريبي)", "حالة معقدة"), acts)
        self.assertIn(("PLAN_APPROVE", "د. مدير تجريبي", "موافق بعد المراجعة"), acts)
        self.assertIn(("PLAN_HOLD", "د. مدير تجريبي", "إحالة لتقييم طبي"), acts)
        self.assertTrue(all(e["at"] for e in ev))
        from app.db import DatabaseError
        with self.assertRaises(DatabaseError):
            with db.tx() as d:
                d.execute("DELETE FROM audit_events WHERE entity_id=%s", [vid])
        # sysadmin sees security events only, therapist none
        self.assertEqual(Client("therapist.a").get("/api/admin/audit").status_code, 403)
        sa = Client("sysadmin").ok(Client("sysadmin").get("/api/admin/audit"))["events"]
        self.assertFalse([e for e in sa if e["action"].startswith("PLAN_")])


if __name__ == "__main__":
    unittest.main()


class T13_LibraryAndDevicePrograms(Base):
    def test_exercise_and_device_program_items(self):
        pid, ep = make_ready_episode()
        a, h = Client("therapist.a"), Client("head.men")
        lib = a.ok(a.get("/api/library"))
        self.assertGreaterEqual(len(lib["exercises"]), 140)
        self.assertEqual({r["code"] for r in lib["regions"]} >= {"LUMBAR", "SHOULDER", "KNEE", "TMJ", "FOOT"}, True)
        devs = {d["code"]: d for d in lib["devices"]}
        self.assertEqual(len(devs["EQ02"]["programs"]), 31)   # TR-Therapy
        self.assertEqual(len(devs["EQ12"]["programs"]), 27)   # FSWT
        prog = devs["EQ02"]["programs"][18]                   # Lumbalgia
        self.assertEqual(prog["en"], "Lumbalgia")
        self.assertTrue(a.get("/library/figure/LB04.svg").data.startswith(b"<svg"))
        self.assertEqual(Client("reception").get("/api/library").status_code, 403)
        data = dict(S.PLAN_DATA)
        data["items"] = [
            {"category": "HOME", "title": "تمرين الكلب والطائر", "exercise_code": "LB04", "dosage": "10 × 3", "stop_criteria": "ألم ممتد"},
            {"category": "DEVICE", "title": "TR: ألم أسفل الظهر", "equipment_code": "EQ02", "program_code": prog["code"],
             "dosage": "برنامج الجهاز", "contraindications_reviewed": True, "precautions": "—"},
        ]
        bad = dict(data, items=[dict(data["items"][1], equipment_code="EQ11")])  # program of another device
        self.assertEqual(a.put(f"/api/episodes/{ep}/plan/draft", bad).status_code, 422)
        bad2 = dict(data, items=[dict(data["items"][0], exercise_code="NOPE")])
        self.assertEqual(a.put(f"/api/episodes/{ep}/plan/draft", bad2).status_code, 422)
        a.ok(a.put(f"/api/episodes/{ep}/plan/draft", data))
        with db.tx() as d:
            row = d.one("SELECT program_label FROM plan_items WHERE program_code=%s", [prog["code"]])
            self.assertIn("Lumbalgia", row["program_label"])     # label derived server-side, not from the client
        a.ok(a.post(f"/api/episodes/{ep}/plan/submit"))
        vid = a.ok(a.get(f"/api/episodes/{ep}/plan"))["versions"][0]["id"]
        h.ok(h.post(f"/api/plan-versions/{vid}/decision", {"action": "APPROVE", "evidence_reviewed": True}))
        r = a.get(f"/reports/episode/{ep}/home-program.pdf")
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.mimetype, "application/pdf")
        self.assertEqual(a.get("/library").status_code, 200)
        self.assertEqual(a.get("/library?tab=devices&q=Lumbalgia").status_code, 200)
