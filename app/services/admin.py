"""Users, delegations, catalogs and audit log (admin)."""
from __future__ import annotations

from .. import rbac
from ..audit import audit
from ..errors import Conflict, Forbidden, NotFound, ValidationError
from .. import security, validation as v
from . import catalog


def list_users(d, user):
    if not (rbac.has_perm(user, "admin.users") or rbac.has_perm(user, "admin.delegations")):
        raise Forbidden("لا تملك صلاحية")
    rows = d.all("""SELECT u.id, u.username, u.full_name, u.role_code, u.is_active, u.is_test_account, u.locked_until, u.created_at,
                           u.version,
                           (SELECT string_agg(dp.name, '، ') FROM memberships m JOIN departments dp ON dp.id=m.department_id
                             WHERE m.user_id=u.id) AS departments,
                           (SELECT array_to_json(array_agg(m.department_id)) FROM memberships m WHERE m.user_id=u.id) AS department_ids
                    FROM users u ORDER BY u.role_code, u.full_name""")
    return rows


def _check_role_change_allowed(user, target_role, target_user=None):
    if target_user and target_user["id"] == user["id"]:
        raise Forbidden("لا يمكن تعديل دور أو حالة حسابك بنفسك", code="SELF_ROLE_CHANGE")
    if user["role_code"] == rbac.SYSADMIN and (target_role == rbac.DIRECTOR or (target_user and target_user["role_code"] == rbac.DIRECTOR)):
        raise Forbidden("إنشاء/تعديل حساب المدير يتطلب المدير")


def create_user(d, user, data):
    rbac.require_perm(user, "admin.users")
    role = v.choice(data, "role_code", "الدور", tuple(rbac.ROLE_NAMES), required=True)
    _check_role_change_allowed(user, role)
    username = (v.s(data, "username", "اسم المستخدم", required=True, max_len=40, pattern=r"[a-z0-9._-]{3,40}") or "").lower()
    pw = data.get("password") or ""
    security.validate_new_password(pw)
    if d.scalar("SELECT count(*) FROM users WHERE username=%s", [username]):
        raise Conflict("اسم المستخدم مستخدم مسبقاً")
    uid = d.scalar("""INSERT INTO users(username, full_name, role_code, password_hash, must_change_password)
                      VALUES (%s,%s,%s,%s,true) RETURNING id""",
                   [username, v.s(data, "full_name", "الاسم", required=True, max_len=120), role, security.hash_password(pw)])
    for dep in data.get("department_ids") or []:
        d.execute("INSERT INTO memberships(user_id, department_id) VALUES (%s,%s::uuid) ON CONFLICT DO NOTHING", [uid, v.uid(dep)])
    audit(d, user, "USER_CREATE", "user", uid, category="ADMIN", details={"role": role, "username": username})
    return uid


def update_user(d, user, user_id, data):
    rbac.require_perm(user, "admin.users")
    target = d.one("SELECT * FROM users WHERE id=%s::uuid", [v.uid(user_id)])
    if not target:
        raise NotFound()
    role = v.choice(data, "role_code", "الدور", tuple(rbac.ROLE_NAMES)) or target["role_code"]
    _check_role_change_allowed(user, role, target)
    expected = v.int_version(data)
    active = v.boolean(data, "is_active", target["is_active"])
    row = d.one("""UPDATE users SET role_code=%s, is_active=%s, full_name=COALESCE(%s, full_name), updated_at=now(), version=version+1,
                          deactivated_at = CASE WHEN %s THEN NULL ELSE COALESCE(deactivated_at, now()) END
                   WHERE id=%s AND version=%s RETURNING *""",
                [role, active, v.s(data, "full_name", "الاسم", max_len=120), active, target["id"], expected])
    if not row:
        raise Conflict("تغيّر الحساب بواسطة مستخدم آخر", code="STALE_VERSION")
    if "department_ids" in data:
        d.execute("DELETE FROM memberships WHERE user_id=%s", [target["id"]])
        for dep in data.get("department_ids") or []:
            d.execute("INSERT INTO memberships(user_id, department_id) VALUES (%s,%s::uuid)", [target["id"], v.uid(dep)])
    if not active or role != target["role_code"]:
        security.revoke_all_sessions(d, target["id"])
    audit(d, user, "USER_UPDATE", "user", target["id"], category="ADMIN",
          details={"role": [target["role_code"], role], "active": [target["is_active"], active]},
          reason=v.s(data, "reason", "السبب", max_len=300))
    return row


def reset_password(d, user, user_id, new_password):
    rbac.require_perm(user, "admin.users")
    target = d.one("SELECT * FROM users WHERE id=%s::uuid", [v.uid(user_id)])
    if not target:
        raise NotFound()
    _check_role_change_allowed(user, target["role_code"], target)
    security.validate_new_password(new_password)
    d.execute("UPDATE users SET password_hash=%s, must_change_password=true, failed_attempts=0, locked_until=NULL WHERE id=%s",
              [security.hash_password(new_password), target["id"]])
    security.revoke_all_sessions(d, target["id"])
    audit(d, user, "PASSWORD_RESET_BY_ADMIN", "user", target["id"], category="SECURITY")


def change_own_password(d, user, current, new):
    row = d.one("SELECT password_hash FROM users WHERE id=%s", [user["id"]])
    if not security.verify_password(current or "", row["password_hash"]):
        raise ValidationError("كلمة المرور الحالية غير صحيحة")
    security.validate_new_password(new or "")
    d.execute("UPDATE users SET password_hash=%s, must_change_password=false WHERE id=%s", [security.hash_password(new), user["id"]])
    audit(d, user, "PASSWORD_CHANGE", "user", user["id"], category="SECURITY")


# ───────── delegations ─────────

def list_delegations(d, user):
    rbac.require_perm(user, "admin.delegations")
    return d.all("""SELECT rd.*, a.full_name AS delegator_name, b.full_name AS delegate_name, dp.name AS department_name
                    FROM review_delegations rd JOIN users a ON a.id=rd.delegator_id JOIN users b ON b.id=rd.delegate_id
                    JOIN departments dp ON dp.id=rd.department_id ORDER BY rd.granted_at DESC""")


def grant_delegation(d, user, data):
    rbac.require_perm(user, "admin.delegations")
    delegate = d.one("SELECT * FROM users WHERE id=%s::uuid", [v.uid(data.get("delegate_id"), "المفوَّض")])
    dep = v.uid(data.get("department_id"), "القسم")
    if not delegate or delegate["role_code"] != rbac.DEPUTY_HEAD or not delegate["is_active"]:
        raise ValidationError("التفويض بالمراجعة يُمنح لنائب رئيس قسم فعّال فقط")
    if delegate["id"] == user["id"]:
        raise Forbidden("لا يمكن تفويض نفسك")
    if user["role_code"] != rbac.DIRECTOR and dep not in user["departments"]:
        raise Forbidden("لا يمكنك التفويض في قسم لا تديره")
    if not d.scalar("SELECT count(*) FROM memberships WHERE user_id=%s AND department_id=%s", [delegate["id"], dep]):
        raise ValidationError("المفوَّض ليس عضواً في القسم")
    rid = d.scalar("""INSERT INTO review_delegations(delegator_id, delegate_id, department_id, reason, expires_at)
                      VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                   [user["id"], delegate["id"], dep, v.s(data, "reason", "سبب التفويض", required=True, max_len=300),
                    v.date(data, "expires_at", "تاريخ الانتهاء", not_future=False)])
    audit(d, user, "DELEGATION_GRANT", "delegation", rid, category="ADMIN", details={"delegate": delegate["id"], "department": dep})
    return rid


def revoke_delegation(d, user, delegation_id, reason):
    rbac.require_perm(user, "admin.delegations")
    rd = d.one("SELECT * FROM review_delegations WHERE id=%s::uuid AND revoked_at IS NULL", [v.uid(delegation_id)])
    if not rd:
        raise NotFound()
    if user["role_code"] != rbac.DIRECTOR and rd["department_id"] not in user["departments"]:
        raise Forbidden("لا يمكنك إلغاء تفويض خارج قسمك")
    d.execute("UPDATE review_delegations SET revoked_at=now(), revoked_by=%s WHERE id=%s", [user["id"], rd["id"]])
    audit(d, user, "DELEGATION_REVOKE", "delegation", rd["id"], category="ADMIN", reason=reason)


# ───────── catalogs ─────────

def list_catalog(d, user):
    if not (rbac.has_perm(user, "admin.catalogs.propose") or rbac.has_perm(user, "admin.catalogs.publish")):
        raise Forbidden("لا تملك صلاحية")
    return d.all("""SELECT c.id, c.kind, c.code, c.version, c.status, c.data, c.review_note, c.created_at, c.published_at,
                           u.full_name AS created_by_name, pu.full_name AS published_by_name
                    FROM catalogs c LEFT JOIN users u ON u.id=c.created_by LEFT JOIN users pu ON pu.id=c.published_by
                    WHERE c.status IN ('PUBLISHED','DRAFT') ORDER BY c.kind, c.code, c.version""")


EDITABLE = {"EQUIPMENT": ("name", "status_note", "info"),
            "TEST": ("name_ar", "indication", "safety", "position", "steps", "positive", "limits"),
            "OUTCOME": ("name_ar", "note", "enabled")}


def propose_catalog_change(d, user, kind, code, changes):
    rbac.require_perm(user, "admin.catalogs.propose")
    cur = d.one("SELECT * FROM catalogs WHERE kind=%s AND code=%s AND status='PUBLISHED'", [kind, code])
    if not cur:
        raise NotFound()
    if d.scalar("SELECT count(*) FROM catalogs WHERE kind=%s AND code=%s AND status='DRAFT'", [kind, code]):
        raise Conflict("توجد مسودة قيد المراجعة لهذا البند")
    data = dict(cur["data"])
    for k in EDITABLE.get(kind, ()):
        if k in changes:
            data[k] = v.boolean(changes, k) if k == "enabled" else v.clean_text(changes[k], 2000)
    nv = d.scalar("SELECT max(version) FROM catalogs WHERE kind=%s AND code=%s", [kind, code]) + 1
    cid = d.scalar("""INSERT INTO catalogs(kind, code, version, status, data, review_note, created_by)
                      VALUES (%s,%s,%s,'DRAFT',%s,%s,%s) RETURNING id""",
                   [kind, code, nv, data, v.clean_text(changes.get("review_note"), 500), user["id"]])
    audit(d, user, "CATALOG_PROPOSE", "catalog", cid, category="ADMIN", details={"kind": kind, "code": code, "version": nv})
    return cid


def publish_catalog(d, user, catalog_id):
    rbac.require_perm(user, "admin.catalogs.publish")
    dr = d.one("SELECT * FROM catalogs WHERE id=%s::uuid AND status='DRAFT'", [v.uid(catalog_id)])
    if not dr:
        raise NotFound()
    if dr["created_by"] == user["id"]:
        raise Forbidden("ينشر المسودة مراجع غير كاتبها")
    d.execute("UPDATE catalogs SET status='RETIRED' WHERE kind=%s AND code=%s AND status='PUBLISHED'", [dr["kind"], dr["code"]])
    d.execute("UPDATE catalogs SET status='PUBLISHED', published_by=%s, published_at=now(), review_note=%s WHERE id=%s",
              [user["id"], "نُشر بعد مراجعة " + user["full_name"], dr["id"]])
    catalog.clear_cache()
    audit(d, user, "CATALOG_PUBLISH", "catalog", dr["id"], category="ADMIN", details={"kind": dr["kind"], "code": dr["code"]})


# ───────── audit ─────────

def audit_log(d, user, *, patient_id=None, entity_id=None, action=None, limit=200):
    if rbac.has_perm(user, "audit.read.clinical"):
        where, params = ["TRUE"], []
    elif rbac.has_perm(user, "audit.read.security"):
        where, params = ["a.category IN ('SECURITY','ADMIN')"], []
    else:
        raise Forbidden("لا تملك صلاحية")
    if patient_id:
        where.append("a.patient_id=%s::uuid")
        params.append(v.uid(patient_id))
    if entity_id:
        where.append("a.entity_id=%s")
        params.append(str(entity_id)[:60])
    if action:
        where.append("a.action=%s")
        params.append(str(action)[:60])
    rows = d.all(f"""SELECT a.id, a.at, a.action, a.entity_type, a.entity_id, a.patient_id, a.reason, a.details, a.category, a.ip,
                            a.actor_role, u.full_name AS actor_name, p.file_no
                     FROM audit_events a LEFT JOIN users u ON u.id=a.actor_id LEFT JOIN patients p ON p.id=a.patient_id
                     WHERE {' AND '.join(where)} ORDER BY a.id DESC LIMIT {int(min(limit, 1000))}""", params)
    if not rbac.has_perm(user, "audit.read.clinical"):
        for r in rows:
            r["details"] = {k: val for k, val in (r["details"] or {}).items() if k in ("username", "reason", "role", "active")}
    return rows
