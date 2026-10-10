"""Patients: registration, duplicate detection, scoped search, assignments, department transfer."""
from __future__ import annotations

import datetime as dt

from .. import rbac
from ..audit import audit
from ..errors import Conflict, Forbidden, NotFound, ValidationError
from .. import validation as v

IDENTITY_FIELDS = ("id", "file_no", "serial_no", "archive_shelf", "archive_cabinet", "full_name", "birth_date", "sex",
                   "phone", "occupation", "height_cm", "weight_kg", "referring_doctor", "department_id", "is_synthetic",
                   "created_at", "updated_at", "version")
BASIC_FIELDS = ("id", "file_no", "full_name", "sex", "birth_date", "phone", "department_id", "is_synthetic")


def _dep_for_sex(d, sex):
    return d.scalar("SELECT id FROM departments WHERE code=%s", ["MEN" if sex == "M" else "WOMEN"])


def _parse(data, partial=False):
    out = {
        "full_name": v.s(data, "full_name", "الاسم الكامل", required=not partial, max_len=200),
        "birth_date": v.date(data, "birth_date", "تاريخ الميلاد"),
        "sex": v.choice(data, "sex", "الجنس", ("M", "F"), required=not partial),
        "phone": v.s(data, "phone", "رقم الهاتف", max_len=30, pattern=r"[0-9+\-\s()٠-٩]{6,30}"),
        "occupation": v.s(data, "occupation", "المهنة", max_len=120),
        "height_cm": v.num(data, "height_cm", "الطول", lo=40, hi=250),
        "weight_kg": v.num(data, "weight_kg", "الوزن", lo=2, hi=400),
        "referring_doctor": v.s(data, "referring_doctor", "الطبيب المحوِّل", max_len=150),
        "serial_no": v.s(data, "serial_no", "رقم التسلسل", max_len=40),
        "archive_shelf": v.s(data, "archive_shelf", "الرف", max_len=40),
        "archive_cabinet": v.s(data, "archive_cabinet", "الخزانة/الدرج", max_len=40),
    }
    if out["full_name"] and len(out["full_name"]) < 2:
        raise ValidationError("الاسم قصير جداً")
    return out


def find_duplicates(d, full_name, birth_date, phone, exclude_id=None):
    nn = v.normalize_name(full_name or "")
    ph = v.normalize_phone(phone)
    rows = d.all(
        """SELECT id, file_no, full_name, birth_date FROM patients
           WHERE (id <> %s::uuid OR %s::uuid IS NULL)
             AND ((name_normalized = %s AND (birth_date = %s::date OR %s::date IS NULL OR birth_date IS NULL))
                  OR (phone_normalized IS NOT NULL AND phone_normalized = %s))
           LIMIT 10""",
        [exclude_id, exclude_id, nn, birth_date, birth_date, ph])
    return [{"id": r["id"], "file_no": r["file_no"], "full_name": r["full_name"],
             "birth_date": r["birth_date"].isoformat() if r["birth_date"] else None} for r in rows]


def create_patient(d, user, data, allow_duplicate=False):
    rbac.require_perm(user, "patient.identity.write")
    f = _parse(data)
    dups = find_duplicates(d, f["full_name"], f["birth_date"], f["phone"])
    if dups and not allow_duplicate:
        raise Conflict("يوجد مريض مشابه مسجل مسبقاً. تحقق قبل إنشاء ملف جديد.", code="DUPLICATE_SUSPECTED",
                       details={"candidates": dups})
    if dups and allow_duplicate and not data.get("is_synthetic"):
        reason = v.s(data, "duplicate_reason", "سبب إنشاء ملف رغم التشابه", required=True, max_len=300)
    else:
        reason = None
    dep = _dep_for_sex(d, f["sex"])
    if data.get("department_id"):
        dep_req = v.uid(data["department_id"], "القسم")
        if user["role_code"] in (rbac.DEPT_HEAD, rbac.DEPUTY_HEAD) and dep_req not in user["departments"]:
            raise Forbidden("لا يمكنك تسجيل مريض في قسم آخر")
        dep = dep_req
    seq = d.scalar("SELECT nextval('patient_file_seq')")
    file_no = "ML-%d-%05d" % (dt.date.today().year, seq)
    row = d.one(
        """INSERT INTO patients(file_no, serial_no, archive_shelf, archive_cabinet, full_name, name_normalized, birth_date, sex,
                                phone, phone_normalized, occupation, height_cm, weight_kg, referring_doctor, department_id,
                                is_synthetic, created_by)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
        [file_no, f["serial_no"], f["archive_shelf"], f["archive_cabinet"], f["full_name"], v.normalize_name(f["full_name"]),
         f["birth_date"], f["sex"], f["phone"], v.normalize_phone(f["phone"]), f["occupation"], f["height_cm"], f["weight_kg"],
         f["referring_doctor"], dep, bool(data.get("is_synthetic")), user["id"]])
    ec = data.get("emergency_contact") or {}
    if ec.get("name"):
        d.execute("INSERT INTO patient_contacts(patient_id, name, relation, phone) VALUES (%s,%s,%s,%s)",
                  [row["id"], v.s(ec, "name", "اسم شخص الطوارئ", max_len=120),
                   v.s(ec, "relation", "صلة القرابة", max_len=60),
                   v.s(ec, "phone", "هاتف شخص الطوارئ", max_len=30)])
    audit(d, user, "PATIENT_CREATE", "patient", row["id"], patient_id=row["id"], reason=reason,
          details={"file_no": file_no, "duplicate_override": bool(dups)})
    return row


def update_patient(d, user, patient_id, data):
    rbac.require_perm(user, "patient.identity.write")
    p = rbac.load_patient_scoped(d, user, patient_id, "identity")
    expected = v.int_version(data)
    f = _parse(data)
    changes = {k: val for k, val in f.items() if k in data}
    if "sex" in changes and changes["sex"] != p["sex"] and user["role_code"] == rbac.RECEPTION:
        pass  # allowed; department stays until a supervisor transfers explicitly
    if not changes:
        return p
    sets, params = [], []
    for k, val in changes.items():
        sets.append(f"{k}=%s")
        params.append(val)
    if "full_name" in changes:
        sets.append("name_normalized=%s")
        params.append(v.normalize_name(changes["full_name"]))
    if "phone" in changes:
        sets.append("phone_normalized=%s")
        params.append(v.normalize_phone(changes["phone"]))
    row = d.one(f"UPDATE patients SET {', '.join(sets)}, updated_at=now(), version=version+1 WHERE id=%s AND version=%s RETURNING *",
                params + [p["id"], expected])
    if not row:
        raise Conflict("عدّل مستخدم آخر هذا الملف بعد فتحك له. أعد التحميل ثم طبّق تعديلك.", code="STALE_VERSION")
    before = {k: (str(p[k]) if p[k] is not None else None) for k in changes}
    audit(d, user, "PATIENT_UPDATE", "patient", p["id"], patient_id=p["id"],
          details={"fields": sorted(changes), "before": before})
    return row


def search(d, user, q=None, department_id=None, limit=50, offset=0):
    rbac.require_perm(user, "patient.identity.read")
    cond, params = rbac.patient_scope_sql(user, "p", "identity")
    where = [f"({cond})"]
    if q:
        q = v.clean_text(q, 100) or ""
        nq = v.normalize_name(q)
        ph = v.normalize_phone(q)
        where.append("(p.name_normalized LIKE %s OR p.file_no ILIKE %s OR (%s::text IS NOT NULL AND p.phone_normalized LIKE %s))")
        params += ["%" + nq + "%", "%" + q + "%", ph, "%" + (ph or "") + "%"]
    if department_id:
        where.append("p.department_id = %s::uuid")
        params.append(v.uid(department_id))
    limit = max(1, min(int(limit), 200))
    rows = d.all(
        f"""SELECT p.id, p.file_no, p.full_name, p.sex, p.birth_date, p.phone, p.department_id, p.is_synthetic, dep.name AS department_name,
                   (SELECT string_agg(u.full_name, '، ') FROM patient_assignments pa JOIN users u ON u.id=pa.therapist_id
                     WHERE pa.patient_id=p.id AND pa.ended_at IS NULL) AS therapists
            FROM patients p JOIN departments dep ON dep.id = p.department_id
            WHERE {' AND '.join(where)} ORDER BY p.created_at DESC LIMIT {limit} OFFSET {int(offset)}""", params)
    if not rbac.has_perm(user, "clinical.read") and user["role_code"] == rbac.ACCOUNTING:
        rows = [{k: r[k] for k in ("id", "file_no", "full_name", "department_name", "is_synthetic")} for r in rows]
    return rows


def get_identity(d, user, patient_id):
    p = rbac.load_patient_scoped(d, user, patient_id, "identity")
    out = {k: p[k] for k in IDENTITY_FIELDS}
    if user["role_code"] == rbac.ACCOUNTING:
        out = {k: p[k] for k in ("id", "file_no", "full_name", "department_id", "is_synthetic", "version")}
    else:
        out["contacts"] = d.all("SELECT id, name, relation, phone, is_emergency FROM patient_contacts WHERE patient_id=%s", [p["id"]])
    out["department"] = d.one("SELECT id, code, name FROM departments WHERE id=%s", [p["department_id"]])
    out["therapists"] = d.all(
        """SELECT u.id, u.full_name, pa.assigned_at FROM patient_assignments pa JOIN users u ON u.id = pa.therapist_id
           WHERE pa.patient_id=%s AND pa.ended_at IS NULL""", [p["id"]])
    audit(d, user, "PATIENT_VIEW_IDENTITY", "patient", p["id"], patient_id=p["id"], category="ACCESS")
    return out


def assign_therapist(d, user, patient_id, therapist_id, reason=None):
    rbac.require_perm(user, "patient.assign")
    p = rbac.load_patient_scoped(d, user, patient_id, "identity")
    if user["role_code"] != rbac.DIRECTOR and p["department_id"] not in user["departments"]:
        raise Forbidden("لا يمكنك تخصيص معالج لمريض خارج قسمك")
    t = d.one("SELECT id, role_code, is_active FROM users WHERE id=%s::uuid", [v.uid(therapist_id, "المعالج")])
    if not t or t["role_code"] not in (rbac.THERAPIST, rbac.DEPT_HEAD, rbac.DEPUTY_HEAD) or not t["is_active"]:
        raise ValidationError("المستخدم المختار ليس معالجاً فعّالاً")
    in_dep = d.scalar("SELECT count(*) FROM memberships WHERE user_id=%s AND department_id=%s", [t["id"], p["department_id"]])
    if not in_dep:
        raise ValidationError("المعالج ليس عضواً في قسم المريض")
    exists = d.scalar("SELECT count(*) FROM patient_assignments WHERE patient_id=%s AND therapist_id=%s AND ended_at IS NULL",
                      [p["id"], t["id"]])
    if exists:
        return
    d.execute("INSERT INTO patient_assignments(patient_id, therapist_id, assigned_by, reason) VALUES (%s,%s,%s,%s)",
              [p["id"], t["id"], user["id"], v.clean_text(reason, 300)])
    audit(d, user, "ASSIGN_THERAPIST", "patient", p["id"], patient_id=p["id"], reason=reason, details={"therapist_id": t["id"]})


def unassign_therapist(d, user, patient_id, therapist_id, reason):
    rbac.require_perm(user, "patient.assign")
    p = rbac.load_patient_scoped(d, user, patient_id, "identity")
    if user["role_code"] != rbac.DIRECTOR and p["department_id"] not in user["departments"]:
        raise Forbidden("لا يمكنك تعديل تخصيص مريض خارج قسمك")
    reason = v.s({"r": reason}, "r", "السبب", required=True)
    n = d.execute("UPDATE patient_assignments SET ended_at=now(), ended_by=%s, reason=%s WHERE patient_id=%s AND therapist_id=%s::uuid AND ended_at IS NULL",
                  [user["id"], reason, p["id"], v.uid(therapist_id)]).rowcount
    if not n:
        raise NotFound("لا يوجد تخصيص نشط")
    audit(d, user, "UNASSIGN_THERAPIST", "patient", p["id"], patient_id=p["id"], reason=reason, details={"therapist_id": therapist_id})


def transfer_department(d, user, patient_id, to_department_id, reason):
    rbac.require_perm(user, "patient.assign")
    p = rbac.load_patient_scoped(d, user, patient_id, "identity")
    to_dep = v.uid(to_department_id, "القسم")
    reason = v.s({"r": reason}, "r", "سبب النقل", required=True)
    if to_dep == p["department_id"]:
        raise ValidationError("المريض في هذا القسم أصلاً")
    if user["role_code"] != rbac.DIRECTOR and p["department_id"] not in user["departments"]:
        raise Forbidden("لا يمكنك نقل مريض من قسم لا تديره")
    if not d.scalar("SELECT count(*) FROM departments WHERE id=%s", [to_dep]):
        raise ValidationError("القسم غير موجود")
    d.execute("INSERT INTO department_transfers(patient_id, from_department_id, to_department_id, reason, transferred_by) VALUES (%s,%s,%s,%s,%s)",
              [p["id"], p["department_id"], to_dep, reason, user["id"]])
    d.execute("UPDATE patients SET department_id=%s, updated_at=now(), version=version+1 WHERE id=%s", [to_dep, p["id"]])
    # assignments of therapists outside the new department end automatically (documented)
    d.execute("""UPDATE patient_assignments pa SET ended_at=now(), ended_by=%s, reason='انتهى تلقائياً بنقل القسم'
                 WHERE pa.patient_id=%s AND pa.ended_at IS NULL
                   AND NOT EXISTS (SELECT 1 FROM memberships m WHERE m.user_id = pa.therapist_id AND m.department_id = %s)""",
              [user["id"], p["id"], to_dep])
    audit(d, user, "DEPARTMENT_TRANSFER", "patient", p["id"], patient_id=p["id"], reason=reason,
          details={"from": p["department_id"], "to": to_dep})
