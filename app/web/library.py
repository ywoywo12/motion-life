"""Exercise library and device programs: browsing page, JSON for the plan picker, SVG illustrations."""
from __future__ import annotations

from flask import Blueprint, Response, g, jsonify, render_template, request

from .. import db, rbac
from ..clinical import exercises as X, figures
from ..errors import NotFound, Unauthorized
from ..services import catalog

bp = Blueprint("library", __name__)


def _user():
    if not g.get("user"):
        raise Unauthorized("يجب تسجيل الدخول")
    rbac.require_perm(g.user, "clinical.read")
    return g.user


def library_data(d):
    exs = sorted(catalog.exercises(d).values(), key=lambda e: e["code"])
    devs = sorted(catalog.equipment(d).values(), key=lambda e: e["code"])
    return {
        "regions": [{"code": c, "ar": a} for c, a in X.REGIONS],
        "types": [{"code": c, "ar": a} for c, a in X.TYPES],
        "exercises": [{k: e.get(k) for k in ("code", "region", "region_ar", "type", "type_ar", "name_ar", "name_en", "steps",
                                             "dosage", "caution")} for e in exs],
        "devices": [{"code": e["code"], "name": e["name"], "name_ar": e.get("name_ar", ""), "category_ar": e.get("category_ar", ""),
                     "source": e.get("source"), "status_note": e.get("status_note"), "info": e.get("info"),
                     "programs": e.get("programs") or []} for e in devs],
    }


@bp.get("/api/library")
def api_library():
    _user()
    with db.tx() as d:
        return jsonify(library_data(d))


@bp.get("/library/figure/<code>.svg")
def figure(code):
    _user()
    with db.tx() as d:
        e = catalog.exercises(d).get(code[:20])
    if not e:
        raise NotFound()
    size = 240 if request.args.get("size") == "l" else 120
    resp = Response(figures.svg(e["pose"], e["hl"], size), mimetype="image/svg+xml")
    resp.headers["Cache-Control"] = "private, max-age=86400"
    return resp


@bp.get("/library")
def page():
    user = _user()
    with db.tx() as d:
        data = library_data(d)
    return render_template("library.html", user=user, csrf=g.session["csrf_token"], data=data,
                           region=request.args.get("region", ""), typ=request.args.get("type", ""), q=request.args.get("q", ""))
