"""Arabic PDF reports: HTML templates rendered by headless Chromium (correct Arabic shaping & bidi)."""
from __future__ import annotations

import datetime as dt
import threading

from flask import Blueprint, Response, g, render_template, request

from .. import config, db, rbac
from ..audit import audit
from ..clinical import engine
from ..errors import AppError, NotFound, Unauthorized
from ..services import assessment as asvc, catalog, plans as psvc, questionnaire as qsvc, sessions as ssvc

bp = Blueprint("reports", __name__, url_prefix="/reports")
_lock = threading.Lock()


def _user():
    if not g.get("user"):
        raise Unauthorized("يجب تسجيل الدخول")
    return g.user


def html_to_pdf(html: str, title: str) -> bytes:
    if config.PDF_ENGINE != "chromium":
        raise AppError("توليد PDF غير مفعّل على هذا الخادم. استخدم معاينة HTML ثم «طباعة» من المتصفح.", status=501)
    from playwright.sync_api import sync_playwright

    footer = ('<div style="font-family:\'DejaVu Sans\',sans-serif;font-size:8px;width:100%;padding:0 12mm;color:#555;'
              'display:flex;justify-content:space-between;direction:rtl"><span>Motion Life — وثيقة سريرية سرية</span>'
              '<span>صفحة <span class="pageNumber"></span> من <span class="totalPages"></span></span></div>')
    with _lock:
        with sync_playwright() as p:
            browser = p.chromium.launch(args=["--no-sandbox"] if (config.ENV != "production" or config.CHROMIUM_NO_SANDBOX) else [])
            try:
                page = browser.new_page()
                page.set_content(html, wait_until="load")
                page.evaluate("document.fonts.ready")
                return page.pdf(format="A4", print_background=True, display_header_footer=True,
                                header_template="<div></div>", footer_template=footer,
                                margin={"top": "12mm", "bottom": "16mm", "left": "12mm", "right": "12mm"})
            finally:
                browser.close()


def _respond(tpl, filename, ctx, patient_id, kind):
    user = g.user
    html = render_template("reports/" + tpl, user=user, now=dt.datetime.now(dt.timezone.utc),
                           center_phone=config.CENTER_PHONE, center_address=config.CENTER_ADDRESS, **ctx)
    with db.tx() as d:
        audit(d, user, "REPORT_EXPORT", "report", kind, patient_id=patient_id, category="ACCESS",
              details={"kind": kind, "format": request.args.get("format", "pdf")})
    if request.args.get("format") == "html":
        resp = Response(html, mimetype="text/html")
        resp.headers["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
        return resp
    pdf = html_to_pdf(html, filename)
    from urllib.parse import quote
    return Response(pdf, mimetype="application/pdf", headers={
        "Content-Disposition": f"inline; filename*=UTF-8''{quote(filename)}", "Cache-Control": "no-store"})


def _history_ctx(d, user, p):
    qn = catalog.questionnaire(d, "MEDICAL_HISTORY")
    answers = qsvc.answers_plain(d, p["id"])
    vis = engine.visible_codes(qn["questions"], answers, {"sex": p["sex"]})
    return {"qn": qn, "answers": answers, "visible": vis, "entries": qsvc.list_entries(d, p["id"]),
            "review": qsvc.last_review(d, p["id"])}


@bp.get("/patient/<pid>/history.pdf")
def history(pid):
    user = _user()
    rbac.require_perm(user, "report.clinical")
    with db.tx() as d:
        p = rbac.load_patient_scoped(d, user, pid, "clinical")
        ctx = _history_ctx(d, user, p)
    return _respond("history.html", f"{p['file_no']}-history.pdf", dict(ctx, p=p, title="استبيان التاريخ الطبي والتقييم الأولي"),
                    p["id"], "history")


def _episode(d, user, eid):
    rbac.require_perm(user, "report.clinical")
    return rbac.load_episode_scoped(d, user, eid)


@bp.get("/episode/<eid>/assessment.pdf")
def assessment_report(eid):
    user = _user()
    with db.tx() as d:
        ep, p = _episode(d, user, eid)
        a = d.one("SELECT * FROM assessments WHERE episode_id=%s", [ep["id"]])
        vn = request.args.get("version")
        q = "SELECT av.*, u.full_name AS created_by_name FROM assessment_versions av JOIN users u ON u.id=av.created_by WHERE av.assessment_id=%s"
        av = d.one(q + (" AND av.version_no=%s" if vn else " ORDER BY av.version_no DESC LIMIT 1"),
                   [a["id"], int(vn)] if vn else [a["id"]])
        if not av:
            raise NotFound("لا يوجد إصدار تقييم منتهٍ بعد")
        qn = catalog.questionnaire(d, "LUMBAR_ASSESSMENT")
        snap = av["snapshot"]
        vis = engine.visible_codes(qn["questions"], snap["answers"], {"sex": p["sex"]})
        ctx = {"p": p, "ep": ep, "av": av, "snap": snap, "qn": qn, "visible": vis, "tests": catalog.tests(d),
               "outcome_catalog": catalog.outcomes(d), "title": "التقييم السريري — أسفل الظهر",
               "referrals": d.all("SELECT r.*, u.full_name AS decided_by_name FROM referrals r JOIN users u ON u.id=r.decided_by WHERE r.episode_id=%s", [ep["id"]])}
    return _respond("assessment.html", f"{p['file_no']}-assessment-v{av['version_no']}.pdf", ctx, p["id"], "assessment")


@bp.get("/episode/<eid>/plan.pdf")
def plan_report(eid):
    user = _user()
    with db.tx() as d:
        ep, p = _episode(d, user, eid)
        plan = d.one("SELECT * FROM treatment_plans WHERE episode_id=%s", [ep["id"]])
        if not plan:
            raise NotFound("لا توجد خطة")
        vn = request.args.get("version")
        if vn:
            pv = d.one("SELECT * FROM plan_versions WHERE plan_id=%s AND version_no=%s", [plan["id"], int(vn)])
        else:
            pv = d.one("SELECT * FROM plan_versions WHERE plan_id=%s AND status='APPROVED'", [plan["id"]])
        if not pv:
            raise NotFound("لا يوجد إصدار معتمد للطباعة")
        approver = d.one("SELECT full_name, role_code FROM users WHERE id=%s", [pv["approved_by"]]) if pv["approved_by"] else None
        author = d.one("SELECT full_name FROM users WHERE id=%s", [pv["author_id"]])
        from ..clinical import figures
        exs = catalog.exercises(d)
        its = psvc.items(d, pv["id"])
        for it in its:
            e = exs.get(it["exercise_code"] or "")
            it["svg"] = figures.svg(e["pose"], e["hl"], 70) if e else None
        ctx = {"p": p, "ep": ep, "pv": pv, "items": its, "approver": approver, "author": author,
               "decisions": psvc.decisions(d, [pv["id"]]), "equipment": catalog.equipment(d), "goals": asvc.list_goals(d, ep["id"]),
               "av": d.one("SELECT version_no FROM assessment_versions WHERE id=%s", [pv["assessment_version_id"]]) if pv["assessment_version_id"] else None,
               "title": "الخطة العلاجية"}
    return _respond("plan.html", f"{p['file_no']}-plan-v{pv['version_no']}.pdf", ctx, p["id"], "plan")


@bp.get("/episode/<eid>/home-program.pdf")
def home_program(eid):
    """Patient handout: exercises of the APPROVED plan with illustrations and the clinician-set dose."""
    from ..clinical import figures
    user = _user()
    with db.tx() as d:
        ep, p = _episode(d, user, eid)
        pv = psvc.approved_version(d, ep["id"])
        if not pv:
            raise NotFound("لا توجد خطة معتمدة")
        exs = catalog.exercises(d)
        items = [it for it in psvc.items(d, pv["id"]) if it["category"] in ("HOME", "GYM", "EDUCATION")]
        for it in items:
            e = exs.get(it["exercise_code"] or "")
            it["svg"] = figures.svg(e["pose"], e["hl"], 150) if e else None
        approver = d.one("SELECT full_name FROM users WHERE id=%s", [pv["approved_by"]])
        ctx = {"p": p, "ep": ep, "pv": pv, "items": items, "approver": approver, "title": "برنامج التمارين"}
    return _respond("home_program.html", f"{p['file_no']}-home-program.pdf", ctx, p["id"], "home_program")


@bp.get("/episode/<eid>/sessions.pdf")
def sessions_report(eid):
    user = _user()
    with db.tx() as d:
        ep, p = _episode(d, user, eid)
        ss = ssvc.list_sessions(d, ep["id"])
        ctx = {"p": p, "ep": ep, "sessions": ss, "reviews": ssvc.list_reviews(d, ep["id"]),
               "approved": psvc.approved_version(d, ep["id"]), "title": "متابعة الجلسات"}
    return _respond("sessions.html", f"{p['file_no']}-sessions.pdf", ctx, p["id"], "sessions")


@bp.get("/episode/<eid>/progress.pdf")
def progress_report(eid):
    user = _user()
    with db.tx() as d:
        ep, p = _episode(d, user, eid)
        ctx = {"p": p, "ep": ep, "table": ssvc.outcome_table(d, ep["id"]), "reviews": ssvc.list_reviews(d, ep["id"]),
               "goals": asvc.list_goals(d, ep["id"]), "title": "الملخص الدوري وتطور القياسات",
               "session_count": d.scalar("SELECT count(*) FROM sessions WHERE episode_id=%s", [ep["id"]])}
    return _respond("progress.html", f"{p['file_no']}-progress.pdf", ctx, p["id"], "progress")


@bp.get("/episode/<eid>/patient-file.pdf")
def patient_file(eid):
    """Two-page layout mirroring the paper 'Patient File' (v7)."""
    user = _user()
    with db.tx() as d:
        ep, p = _episode(d, user, eid)
        hist = _history_ctx(d, user, p)
        lumbar = qsvc.answers_plain(d, p["id"], ep["id"])
        a = d.one("SELECT * FROM assessments WHERE episode_id=%s", [ep["id"]])
        ctx = {"p": p, "ep": ep, "h": hist, "lumbar": lumbar, "lq": catalog.questionnaire(d, "LUMBAR_ASSESSMENT"),
               "exam": asvc.current_exam_results(d, a["id"]), "tests": catalog.tests(d),
               "approved": psvc.approved_version(d, ep["id"]), "sessions": ssvc.list_sessions(d, ep["id"]),
               "reviews": ssvc.list_reviews(d, ep["id"]), "title": "ملف المريض والتقييم السريري",
               "assessor": d.one("""SELECT u.full_name, av.created_at FROM assessment_versions av JOIN users u ON u.id=av.created_by
                                    WHERE av.assessment_id=%s ORDER BY av.version_no DESC LIMIT 1""", [a["id"]])}
        if ctx["approved"]:
            ctx["items"] = psvc.items(d, ctx["approved"]["id"])
    return _respond("patient_file.html", f"{p['file_no']}-patient-file.pdf", ctx, p["id"], "patient_file")
