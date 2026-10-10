"""JSON API. Every endpoint authenticates, then delegates to services that enforce RBAC and rules."""
from __future__ import annotations

from flask import Blueprint, Response, g, jsonify, make_response, request

from .. import config, db, security
from ..errors import Unauthorized, ValidationError
from ..services import (admin, assessment, attachments, billing, dashboard, episodes, patients, plans, questionnaire,
                        sessions)

bp = Blueprint("api", __name__, url_prefix="/api")


def _user():
    if not g.get("user"):
        raise Unauthorized("يجب تسجيل الدخول")
    return g.user


def _json():
    data = request.get_json(silent=True)
    if data is None:
        if request.mimetype == "application/json":
            raise ValidationError("JSON غير صالح")
        data = {}
    if not isinstance(data, dict):
        raise ValidationError("صيغة الطلب غير صالحة")
    return data


def ok(payload=None, status=200):
    return jsonify(payload if payload is not None else {"ok": True}), status


# ───────── auth ─────────
@bp.post("/auth/login")
def login():
    data = _json()
    with db.tx() as d:
        tok, csrf, user = security.login(d, str(data.get("username", ""))[:60], str(data.get("password", ""))[:200],
                                         g.client_ip, request.headers.get("User-Agent"))
    if not tok:  # failure was recorded and committed above (brute-force counters)
        raise Unauthorized(security.LOGIN_FAIL_MSG)
    resp = make_response(jsonify({"ok": True, "user": {"full_name": user["full_name"], "role": user["role_code"]},
                                  "must_change_password": user["must_change_password"]}))
    resp.set_cookie("ml_session", tok, httponly=True, samesite="Strict", secure=config.COOKIE_SECURE,
                    max_age=config.SESSION_TTL_HOURS * 3600, path="/")
    return resp


@bp.post("/auth/logout")
def logout():
    user = _user()
    with db.tx() as d:
        security.logout(d, g.session["id"], user)
    resp = make_response(ok())
    resp.delete_cookie("ml_session", path="/")
    return resp


@bp.get("/auth/me")
def me():
    user = _user()
    return ok({"user": {k: user[k] for k in ("id", "username", "full_name", "role_code")}, "csrf_token": g.session["csrf_token"]})


@bp.post("/auth/password")
def change_password():
    user = _user()
    data = _json()
    with db.tx() as d:
        admin.change_own_password(d, user, data.get("current"), data.get("new"))
    return ok()


@bp.get("/dashboard")
def api_dashboard():
    with db.tx() as d:
        return ok(dashboard.dashboard(d, _user()))


# ───────── patients ─────────
@bp.get("/patients")
def list_patients():
    with db.tx() as d:
        return ok({"patients": patients.search(d, _user(), request.args.get("q"), request.args.get("department_id"))})


@bp.post("/patients")
def create_patient():
    data = _json()
    with db.tx() as d:
        row = patients.create_patient(d, _user(), data, allow_duplicate=bool(data.get("confirm_duplicate")))
    return ok({"id": row["id"], "file_no": row["file_no"]}, 201)


@bp.get("/patients/<pid>")
def get_patient(pid):
    with db.tx() as d:
        return ok(patients.get_identity(d, _user(), pid))


@bp.patch("/patients/<pid>")
def update_patient(pid):
    with db.tx() as d:
        row = patients.update_patient(d, _user(), pid, _json())
    return ok({"version": row["version"]})


@bp.post("/patients/<pid>/assignments")
def assign(pid):
    data = _json()
    with db.tx() as d:
        patients.assign_therapist(d, _user(), pid, data.get("therapist_id"), data.get("reason"))
    return ok()


@bp.post("/patients/<pid>/assignments/<tid>/end")
def unassign(pid, tid):
    with db.tx() as d:
        patients.unassign_therapist(d, _user(), pid, tid, _json().get("reason"))
    return ok()


@bp.post("/patients/<pid>/transfer")
def transfer(pid):
    data = _json()
    with db.tx() as d:
        patients.transfer_department(d, _user(), pid, data.get("department_id"), data.get("reason"))
    return ok()


# ───────── medical history ─────────
@bp.get("/patients/<pid>/history")
def get_history(pid):
    from .. import rbac
    from ..services import catalog
    user = _user()
    with db.tx() as d:
        p = rbac.load_patient_scoped(d, user, pid, "clinical")
        return ok({"answers": questionnaire.get_answers(d, p["id"]), "entries": questionnaire.list_entries(d, p["id"]),
                   "questionnaire_version": catalog.questionnaire(d, "MEDICAL_HISTORY")["version"]})


@bp.post("/patients/<pid>/history/answers")
def save_history(pid):
    data = _json()
    with db.tx() as d:
        out = assessment.save_history_answers(d, _user(), pid, data.get("items") or [])
    return ok(out)


@bp.post("/patients/<pid>/history/entries")
def add_entry(pid):
    from .. import rbac
    user = _user()
    with db.tx() as d:
        p = rbac.load_patient_scoped(d, user, pid, "clinical")
        eid = questionnaire.add_entry(d, user, p, _json())
    return ok({"id": eid}, 201)


@bp.post("/patients/<pid>/history/entries/<eid>/remove")
def remove_entry(pid, eid):
    from .. import rbac
    user = _user()
    with db.tx() as d:
        p = rbac.load_patient_scoped(d, user, pid, "clinical")
        questionnaire.remove_entry(d, user, p, eid, _json().get("reason"))
    return ok()


@bp.post("/patients/<pid>/history/review")
def review_history(pid):
    from .. import rbac
    user = _user()
    with db.tx() as d:
        p = rbac.load_patient_scoped(d, user, pid, "clinical")
        questionnaire.confirm_review(d, user, p, _json().get("note"))
    return ok()


@bp.get("/patients/<pid>/answers/<code>/history")
def answer_hist(pid, code):
    from .. import rbac
    user = _user()
    with db.tx() as d:
        p = rbac.load_patient_scoped(d, user, pid, "clinical")
        return ok({"history": questionnaire.answer_history(d, user, p, code[:60], request.args.get("episode_id"))})


# ───────── episodes & assessment ─────────
@bp.post("/patients/<pid>/episodes")
def create_episode(pid):
    with db.tx() as d:
        ep = episodes.create_episode(d, _user(), pid, _json())
    return ok({"id": ep["id"]}, 201)


@bp.post("/episodes/<eid>/resume")
def resume(eid):
    with db.tx() as d:
        episodes.resume_episode(d, _user(), eid, _json().get("reason"))
    return ok()


@bp.post("/episodes/<eid>/close")
def close(eid):
    with db.tx() as d:
        episodes.close_episode(d, _user(), eid, _json().get("reason"))
    return ok()


@bp.get("/episodes/<eid>/assessment")
def get_assessment(eid):
    with db.tx() as d:
        v = assessment.assessment_view(d, _user(), eid)
    return ok({k: v[k] for k in ("answers", "safety", "exam_results", "goals", "outcomes", "blockers", "recommended", "alerts",
                                 "versions", "referrals")} | {"episode": v["episode"]})


@bp.post("/episodes/<eid>/assessment/answers")
def save_lumbar(eid):
    with db.tx() as d:
        out = assessment.save_lumbar_answers(d, _user(), eid, _json().get("items") or [])
    return ok(out)


@bp.post("/episodes/<eid>/exam")
def exam(eid):
    with db.tx() as d:
        rid = assessment.record_exam_result(d, _user(), eid, _json())
    return ok({"id": rid}, 201)


@bp.post("/episodes/<eid>/goals")
def goal(eid):
    with db.tx() as d:
        g_ = assessment.add_goal(d, _user(), eid, _json())
    return ok({"id": g_["id"]}, 201)


@bp.post("/episodes/<eid>/goals/<gid>/status")
def goal_status(eid, gid):
    data = _json()
    with db.tx() as d:
        assessment.update_goal_status(d, _user(), eid, gid, data.get("status"), data.get("reason"))
    return ok()


@bp.post("/episodes/<eid>/outcomes")
def outcome(eid):
    with db.tx() as d:
        oid = assessment.record_outcome(d, _user(), eid, _json())
    return ok({"id": oid}, 201)


@bp.post("/episodes/<eid>/assessment/finalize")
def finalize(eid):
    with db.tx() as d:
        out = assessment.finalize(d, _user(), eid, _json().get("note"))
    return ok(out)


@bp.post("/episodes/<eid>/referrals")
def referral(eid):
    with db.tx() as d:
        rid = assessment.record_referral(d, _user(), eid, _json())
    return ok({"id": rid}, 201)


@bp.post("/alerts/<aid>/ack")
def ack(aid):
    with db.tx() as d:
        assessment.acknowledge_alert(d, _user(), aid, _json().get("note"))
    return ok()


# ───────── plans & reviews ─────────
@bp.get("/episodes/<eid>/plan")
def get_plan(eid):
    with db.tx() as d:
        v = plans.plan_view(d, _user(), eid)
    return ok({"versions": v["versions"], "decisions": v["decisions"], "blockers": v["blockers"]})


@bp.put("/episodes/<eid>/plan/draft")
def save_draft(eid):
    with db.tx() as d:
        row = plans.save_draft(d, _user(), eid, _json())
    return ok({"id": row["id"], "lock_version": row["lock_version"], "version_no": row["version_no"]})


@bp.post("/episodes/<eid>/plan/submit")
def submit(eid):
    with db.tx() as d:
        row = plans.submit(d, _user(), eid)
    return ok({"status": row["status"]})


@bp.post("/episodes/<eid>/plan/revise")
def revise(eid):
    with db.tx() as d:
        row = plans.revise(d, _user(), eid)
    return ok({"id": row["id"], "version_no": row["version_no"]}, 201)


@bp.get("/reviews")
def reviews():
    with db.tx() as d:
        return ok({"queue": plans.review_queue(d, _user())})


@bp.post("/plan-versions/<vid>/decision")
def decide(vid):
    data = _json()
    with db.tx() as d:
        row = plans.decide(d, _user(), vid, str(data.get("action", "")), data)
    return ok({"status": row["status"]})


# ───────── sessions ─────────
@bp.get("/episodes/<eid>/sessions")
def list_sessions(eid):
    with db.tx() as d:
        v = sessions.sessions_view(d, _user(), eid)
    return ok({"sessions": v["sessions"], "due": v["due"], "approved_version_id": v["approved"]["id"] if v["approved"] else None})


@bp.post("/episodes/<eid>/sessions")
def create_session(eid):
    with db.tx() as d:
        out = sessions.create_session(d, _user(), eid, _json())
    return ok(out, 201)


@bp.post("/episodes/<eid>/progress-reviews")
def progress(eid):
    with db.tx() as d:
        rid = sessions.create_progress_review(d, _user(), eid, _json())
    return ok({"id": rid}, 201)


@bp.get("/episodes/<eid>/outcomes")
def outcomes(eid):
    from .. import rbac
    user = _user()
    with db.tx() as d:
        rbac.load_episode_scoped(d, user, eid)
        return ok({"table": sessions.outcome_table(d, eid)})


# ───────── attachments ─────────
@bp.post("/patients/<pid>/attachments")
def upload(pid):
    f = request.files.get("file")
    if not f:
        raise ValidationError("اختر ملفاً")
    data = f.read()
    with db.tx() as d:
        aid = attachments.upload(d, _user(), pid, request.form.get("kind"), f.filename, f.mimetype, data,
                                 request.form.get("episode_id") or None)
    return ok({"id": aid}, 201)


@bp.get("/attachments/<aid>")
def download(aid):
    with db.tx() as d:
        a, data = attachments.fetch(d, _user(), aid)
    from urllib.parse import quote
    return Response(data, mimetype=a["mime"], headers={
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(a['filename'])}", "Cache-Control": "no-store"})


# ───────── billing ─────────
@bp.get("/episodes/<eid>/billing")
def get_billing(eid):
    with db.tx() as d:
        return ok(billing.get_billing(d, _user(), eid))


@bp.post("/episodes/<eid>/billing/package")
def package(eid):
    with db.tx() as d:
        return ok({"id": billing.set_package(d, _user(), eid, _json())}, 201)


@bp.post("/episodes/<eid>/billing/payments")
def payment(eid):
    with db.tx() as d:
        return ok({"id": billing.add_payment(d, _user(), eid, _json())}, 201)


# ───────── admin ─────────
@bp.get("/admin/users")
def users():
    with db.tx() as d:
        return ok({"users": admin.list_users(d, _user())})


@bp.post("/admin/users")
def create_user():
    with db.tx() as d:
        return ok({"id": admin.create_user(d, _user(), _json())}, 201)


@bp.patch("/admin/users/<uid>")
def update_user(uid):
    with db.tx() as d:
        row = admin.update_user(d, _user(), uid, _json())
    return ok({"version": row["version"]})


@bp.post("/admin/users/<uid>/password")
def reset_pw(uid):
    with db.tx() as d:
        admin.reset_password(d, _user(), uid, _json().get("password") or "")
    return ok()


@bp.post("/admin/delegations")
def grant():
    with db.tx() as d:
        return ok({"id": admin.grant_delegation(d, _user(), _json())}, 201)


@bp.post("/admin/delegations/<did>/revoke")
def revoke(did):
    with db.tx() as d:
        admin.revoke_delegation(d, _user(), did, _json().get("reason"))
    return ok()


@bp.post("/admin/catalogs/<kind>/<code>/propose")
def propose(kind, code):
    with db.tx() as d:
        return ok({"id": admin.propose_catalog_change(d, _user(), kind, code, _json())}, 201)


@bp.post("/admin/catalogs/<cid>/publish")
def publish(cid):
    with db.tx() as d:
        admin.publish_catalog(d, _user(), cid)
    return ok()


@bp.get("/admin/audit")
def audit_log():
    with db.tx() as d:
        return ok({"events": admin.audit_log(d, _user(), patient_id=request.args.get("patient_id"),
                                             entity_id=request.args.get("entity_id"), action=request.args.get("action"))})
