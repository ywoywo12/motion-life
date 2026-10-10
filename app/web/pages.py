"""Server-rendered pages (GET only). All mutations go through /api with CSRF protection."""
from __future__ import annotations

from flask import Blueprint, g, redirect, render_template, request

from .. import db, rbac
from ..clinical import engine
from ..errors import Forbidden, NotFound, Unauthorized
from ..services import (admin, assessment, attachments, billing, catalog, dashboard, episodes, patients, plans,
                        questionnaire, sessions)

bp = Blueprint("pages", __name__)


def _user():
    if not g.get("user"):
        raise Unauthorized("يجب تسجيل الدخول")
    return g.user


def render(tpl, **kw):
    return render_template(tpl, user=g.get("user"), csrf=g.session["csrf_token"] if g.get("session") else "", **kw)


@bp.get("/")
def index():
    return redirect("/dashboard" if g.get("user") else "/login")


@bp.get("/login")
def login():
    if g.get("user"):
        return redirect("/dashboard")
    nxt = request.args.get("next", "/dashboard")
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = "/dashboard"
    return render_template("login.html", next=nxt, user=None, csrf="")


@bp.get("/dashboard")
def dash():
    with db.tx() as d:
        data = dashboard.dashboard(d, _user())
    return render("dashboard.html", data=data)


@bp.get("/account")
def account():
    _user()
    return render("account.html")


@bp.get("/patients")
def patients_page():
    user = _user()
    rbac.require_perm(user, "patient.identity.read")
    q = request.args.get("q", "")
    with db.tx() as d:
        rows = patients.search(d, user, q or None)
        deps = d.all("SELECT id, code, name FROM departments ORDER BY code")
    return render("patients.html", rows=rows, q=q, deps=deps)


@bp.get("/patients/<pid>")
def patient_page(pid):
    user = _user()
    with db.tx() as d:
        ident = patients.get_identity(d, user, pid)
        clinical = rbac.has_perm(user, "clinical.read")
        ctx = {"p": ident, "clinical": False}
        if clinical:
            try:
                rbac.load_patient_scoped(d, user, pid, "clinical")
                ctx["clinical"] = True
            except NotFound:
                pass
        if ctx["clinical"]:
            ctx["episodes"] = episodes.list_for_patient(d, ident["id"])
            ctx["alerts"] = d.all("SELECT * FROM alerts WHERE patient_id=%s AND status <> 'RESOLVED' ORDER BY created_at DESC", [ident["id"]])
            ctx["attachments"] = attachments.list_for_patient(d, ident["id"])
            ctx["history_review"] = questionnaire.last_review(d, ident["id"])
            h = questionnaire.answers_plain(d, ident["id"])
            qn = catalog.questionnaire(d, "MEDICAL_HISTORY")
            ctx["history_summary"] = _history_summary(qn, h)
            ctx["entries"] = questionnaire.list_entries(d, ident["id"])
            ctx["outcomes"] = {e["id"]: sessions.outcome_table(d, e["id"]) for e in ctx["episodes"]}
        if rbac.has_perm(user, "patient.assign"):
            ctx["therapist_options"] = d.all(
                """SELECT u.id, u.full_name FROM users u JOIN memberships m ON m.user_id=u.id
                   WHERE m.department_id=%s AND u.is_active AND u.role_code IN ('THERAPIST','DEPT_HEAD','DEPUTY_HEAD')
                   ORDER BY u.full_name""", [ident["department_id"]])
            ctx["deps"] = d.all("SELECT id, name FROM departments ORDER BY code")
        if rbac.has_perm(user, "billing.read"):
            ctx["billing_episodes"] = d.all("SELECT id, title, created_at FROM clinical_episodes WHERE patient_id=%s ORDER BY created_at DESC",
                                            [ident["id"]])
    return render("patient.html", **ctx)


def _history_summary(qn, h):
    by = qn["by_code"]

    def pick(*codes):
        out = []
        for c in codes:
            a = h.get(c)
            if a and a["status"] == "ANSWERED":
                out.append((by[c]["text"], engine.display_value(by[c], a)))
        return out

    conds = [by[c]["text"] for c in by if c.startswith("HX_COND_") and h.get(c, {}).get("value") == "YES"]
    return {
        "complaint": pick("HX_MAIN_PROBLEM"),
        "conditions": conds,
        "meds": pick("HX_MED_CLASSES", "HX_ALLERGIES"),
        "implants": pick("HX_IMPLANTS"),
        "function": pick("HX_WALK_NOW", "HX_ADL_HELP", "HX_HARDEST_ACTIVITY"),
        "goal": pick("HX_MAIN_GOAL"),
        "patient_flags": [by[c]["text"] for c in by if c.startswith("HX_SF_") and h.get(c, {}).get("value") == "YES"],
    }


@bp.get("/patients/<pid>/history")
def history_page(pid):
    user = _user()
    with db.tx() as d:
        p = rbac.load_patient_scoped(d, user, pid, "clinical")
        qn = catalog.questionnaire(d, "MEDICAL_HISTORY")
        answers = questionnaire.get_answers(d, p["id"])
        entries = questionnaire.list_entries(d, p["id"])
        review = questionnaire.last_review(d, p["id"])
        eps = d.all("SELECT id, title FROM clinical_episodes WHERE patient_id=%s AND status <> 'CLOSED'", [p["id"]])
        safety_rows = d.all("""SELECT e.title, s.status FROM clinical_episodes e JOIN safety_screenings s ON s.episode_id=e.id AND s.is_current
                               WHERE e.patient_id=%s AND e.status <> 'CLOSED'""", [p["id"]])
    return render("history.html", p=p, qn=qn, answers=answers, entries=entries, review=review, episodes=eps,
                  visible=sorted(engine.visible_codes(qn["questions"], answers, {"sex": p["sex"]})), safety_rows=safety_rows,
                  save_url=f"/api/patients/{p['id']}/history/answers")


@bp.get("/episodes/<eid>/assessment")
def assessment_page(eid):
    user = _user()
    with db.tx() as d:
        view = assessment.assessment_view(d, user, eid)
    return render("assessment.html", v=view, ep=view["episode"], p=view["patient"],
                  save_url=f"/api/episodes/{eid}/assessment/answers")


@bp.get("/episodes/<eid>/plan")
def plan_page(eid):
    user = _user()
    with db.tx() as d:
        view = plans.plan_view(d, user, eid)
    return render("plan.html", v=view, ep=view["episode"], p=view["patient"])


@bp.get("/reviews")
def reviews_page():
    user = _user()
    with db.tx() as d:
        q = plans.review_queue(d, user)
    return render("reviews.html", queue=q)


@bp.get("/reviews/<vid>")
def review_page(vid):
    user = _user()
    with db.tx() as d:
        r = plans.review_view(d, user, vid)
    return render("review.html", r=r, ep=r["episode"], p=r["patient"], v=r["view"])


@bp.get("/episodes/<eid>/sessions")
def sessions_page(eid):
    user = _user()
    with db.tx() as d:
        v = sessions.sessions_view(d, user, eid)
        baseline = [o for o in assessment.list_outcomes(d, eid) if o["timepoint"] == "BASELINE"]
    return render("sessions.html", v=v, ep=v["episode"], p=v["patient"], baseline=baseline)


@bp.get("/episodes/<eid>/outcomes")
def outcomes_page(eid):
    user = _user()
    with db.tx() as d:
        ep, p = rbac.load_episode_scoped(d, user, eid)
        table = sessions.outcome_table(d, eid)
        reviews = sessions.list_reviews(d, eid)
        goals = assessment.list_goals(d, eid)
    return render("outcomes.html", ep=ep, p=p, table=table, reviews=reviews, goals=goals)


@bp.get("/episodes/<eid>/billing")
def billing_page(eid):
    user = _user()
    with db.tx() as d:
        b = billing.get_billing(d, user, eid)
        pt = d.one("SELECT p.id, p.full_name, p.file_no FROM clinical_episodes e JOIN patients p ON p.id=e.patient_id WHERE e.id=%s", [b["episode"]["id"]])
    return render("billing.html", b=b, p=pt)


@bp.get("/billing")
def billing_list():
    user = _user()
    with db.tx() as d:
        rows = billing.billing_list(d, user)
    return render("billing_list.html", rows=rows)


@bp.get("/reports")
def reports_page():
    user = _user()
    if not (rbac.has_perm(user, "report.clinical") or rbac.has_perm(user, "billing.read")):
        raise Forbidden("لا تملك صلاحية التقارير")
    with db.tx() as d:
        cond, params = rbac.patient_scope_sql(user, "p", "clinical")
        rows = d.all(f"""SELECT p.id AS patient_id, p.full_name, p.file_no, e.id AS episode_id, e.title, e.status,
                                (SELECT pv.version_no FROM plan_versions pv JOIN treatment_plans tp ON tp.id=pv.plan_id
                                  WHERE tp.episode_id=e.id AND pv.status='APPROVED') AS approved_version,
                                (SELECT count(*) FROM sessions s WHERE s.episode_id=e.id) AS sessions
                         FROM patients p LEFT JOIN clinical_episodes e ON e.patient_id=p.id
                         WHERE ({cond}) ORDER BY p.full_name, e.created_at DESC LIMIT 300""", params)
    return render("reports.html", rows=rows)


@bp.get("/admin/users")
def admin_users():
    user = _user()
    with db.tx() as d:
        users = admin.list_users(d, user)
        delegs = admin.list_delegations(d, user) if rbac.has_perm(user, "admin.delegations") else []
        deps = d.all("SELECT id, name FROM departments ORDER BY code")
    return render("admin_users.html", users=users, delegs=delegs, deps=deps)


@bp.get("/admin/catalogs")
def admin_catalogs():
    user = _user()
    with db.tx() as d:
        rows = admin.list_catalog(d, user)
        protos = d.all("SELECT * FROM protocol_versions ORDER BY code, version")
    return render("admin_catalogs.html", rows=rows, protos=protos)


@bp.get("/admin/audit")
def admin_audit():
    user = _user()
    with db.tx() as d:
        events = admin.audit_log(d, user, patient_id=request.args.get("patient_id") or None,
                                 action=request.args.get("action") or None, limit=300)
    return render("admin_audit.html", events=events)
