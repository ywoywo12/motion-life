"""Motion Life Clinical System — Flask application factory."""
from __future__ import annotations

import logging
import secrets
import uuid

from flask import Flask, g, jsonify, render_template, request

from . import config, db
from .errors import AppError, Forbidden, Unauthorized

log = logging.getLogger("motionlife")


def create_app():
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.update(SECRET_KEY=config.SECRET_KEY, MAX_CONTENT_LENGTH=config.MAX_UPLOAD_MB * 1024 * 1024 + 65536,
                      JSON_AS_ASCII=False, TEMPLATES_AUTO_RELOAD=not config.IS_PROD)
    from .web import filters
    filters.register(app)
    if config.TRUST_PROXY:
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    @app.before_request
    def _auth():
        g.client_ip = (request.headers.get("X-Real-IP") if config.IS_PROD and request.headers.get("X-Real-IP") and not config.TRUST_PROXY
                       else request.remote_addr)
        g.user = g.session = None
        g.csp_nonce = secrets.token_urlsafe(12)
        if request.path.startswith("/static/"):
            return
        from . import security
        tok = request.cookies.get("ml_session")
        if tok:
            with db.tx() as d:
                g.user, g.session = security.resolve_session(d, tok)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            _check_origin()
            if request.path != "/api/auth/login":
                if not g.session:
                    raise Unauthorized("انتهت الجلسة أو لم تسجّل الدخول")
                sent = request.headers.get("X-CSRF-Token") or request.form.get("csrf_token")
                if not sent or not secrets.compare_digest(sent, g.session["csrf_token"]):
                    raise Forbidden("رمز الحماية (CSRF) غير صالح. أعد تحميل الصفحة.", code="CSRF")

    @app.after_request
    def _headers(resp):
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        resp.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
        if config.COOKIE_SECURE:
            resp.headers["Strict-Transport-Security"] = "max-age=31536000"
        if not request.path.startswith("/static/"):
            resp.headers["Cache-Control"] = "no-store"
        return resp

    @app.errorhandler(AppError)
    def _app_error(e: AppError):
        payload = {"error": {"code": e.code, "message": e.message, "details": e.details}}
        if _wants_json():
            return jsonify(payload), e.status
        if isinstance(e, Unauthorized):
            from flask import redirect
            return redirect("/login?next=" + request.path)
        return render_template("error.html", error=e), e.status

    @app.errorhandler(404)
    def _404(e):
        if _wants_json():
            return jsonify({"error": {"code": "NOT_FOUND", "message": "غير موجود"}}), 404
        return render_template("error.html", error=AppError("الصفحة غير موجودة", status=404)), 404

    @app.errorhandler(413)
    def _413(e):
        return jsonify({"error": {"code": "TOO_LARGE", "message": f"الملف أكبر من {config.MAX_UPLOAD_MB} ميغابايت"}}), 413

    @app.errorhandler(Exception)
    def _500(e):
        from werkzeug.exceptions import HTTPException
        if isinstance(e, HTTPException):
            return e
        ref = uuid.uuid4().hex[:10]
        # never log request bodies (may contain PHI); log the exception type/location with a reference
        log.exception("unhandled error ref=%s path=%s", ref, request.path)
        msg = f"حدث خطأ غير متوقع. لم يتم حفظ العملية. رقم المرجع: {ref}"
        if _wants_json():
            return jsonify({"error": {"code": "INTERNAL", "message": msg}}), 500
        return render_template("error.html", error=AppError(msg, status=500)), 500

    from .web import api, library, pages, reports
    app.register_blueprint(library.bp)
    app.register_blueprint(api.bp)
    app.register_blueprint(pages.bp)
    app.register_blueprint(reports.bp)
    return app


def _wants_json():
    return request.path.startswith("/api/") or request.accept_mimetypes.best == "application/json"


def _check_origin():
    origin = request.headers.get("Origin")
    if not origin:
        return
    allowed = {request.host_url.rstrip("/")}
    if config.PUBLIC_ORIGIN:
        allowed.add(config.PUBLIC_ORIGIN.rstrip("/"))
    if origin.rstrip("/") not in allowed:
        raise Forbidden("طلب من مصدر غير موثوق", code="BAD_ORIGIN")
