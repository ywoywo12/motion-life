"""Role-based access control. Single source of truth for permissions.

Every service function calls these helpers *before* touching data. Patient lists are
filtered in SQL with `patient_scope_sql`, never in the UI.
"""
from __future__ import annotations

from .errors import Forbidden, NotFound

DIRECTOR = "DIRECTOR"
DEPT_HEAD = "DEPT_HEAD"
DEPUTY_HEAD = "DEPUTY_HEAD"
THERAPIST = "THERAPIST"
RECEPTION = "RECEPTION"
ACCOUNTING = "ACCOUNTING"
SYSADMIN = "SYSADMIN"

ROLE_NAMES = {
    DIRECTOR: "المدير العام/السريري",
    DEPT_HEAD: "رئيس القسم",
    DEPUTY_HEAD: "نائب رئيس القسم",
    THERAPIST: "معالج",
    RECEPTION: "استقبال",
    ACCOUNTING: "محاسبة",
    SYSADMIN: "مسؤول النظام",
}

CLINICAL_ROLES = {DIRECTOR, DEPT_HEAD, DEPUTY_HEAD, THERAPIST}
SUPERVISORS = {DIRECTOR, DEPT_HEAD, DEPUTY_HEAD}

PERMISSIONS = {
    "patient.identity.read": "قراءة بيانات الهوية والتواصل",
    "patient.identity.write": "تسجيل وتعديل بيانات الهوية",
    "patient.assign": "تخصيص معالج ونقل القسم",
    "clinical.read": "قراءة السجل السريري",
    "clinical.write": "إدخال التاريخ الطبي والفحص",
    "plan.author": "إنشاء وتعديل مسودات الخطط",
    "plan.review": "مراجعة واعتماد الخطط (ضمن النطاق والتفويض)",
    "plan.review.escalated": "البت في الخطط المصعّدة",
    "session.write": "تسجيل الجلسات وإعادة التقييم",
    "billing.read": "قراءة الباقات والدفعات",
    "billing.write": "تسجيل الباقات والدفعات",
    "report.clinical": "طباعة التقارير السريرية",
    "admin.users": "إدارة الحسابات",
    "admin.delegations": "إدارة تفويضات المراجعة",
    "admin.catalogs.propose": "اقتراح مسودات الكتالوج",
    "admin.catalogs.publish": "نشر الكتالوج",
    "audit.read.clinical": "قراءة سجل التدقيق الكامل",
    "audit.read.security": "قراءة أحداث الأمان",
}

ROLE_PERMISSIONS = {
    DIRECTOR: set(PERMISSIONS),
    DEPT_HEAD: {"patient.identity.read", "patient.identity.write", "patient.assign", "clinical.read", "clinical.write",
                "plan.author", "plan.review", "session.write", "report.clinical", "admin.delegations",
                "admin.catalogs.propose"},
    DEPUTY_HEAD: {"patient.identity.read", "patient.identity.write", "clinical.read", "clinical.write", "plan.author",
                  "plan.review", "session.write", "report.clinical"},
    THERAPIST: {"patient.identity.read", "clinical.read", "clinical.write", "plan.author", "session.write",
                "report.clinical"},
    RECEPTION: {"patient.identity.read", "patient.identity.write"},
    ACCOUNTING: {"patient.identity.read", "billing.read", "billing.write"},
    SYSADMIN: {"admin.users", "audit.read.security"},
}


def has_perm(user, perm: str) -> bool:
    return bool(user) and perm in ROLE_PERMISSIONS.get(user["role_code"], set())


def require_perm(user, perm: str):
    if not has_perm(user, perm):
        raise Forbidden("لا تملك صلاحية لهذا الإجراء")


# ───────────── patient scope ─────────────

def patient_scope_sql(user, alias="p", level="identity"):
    """Returns (sql_condition, params) restricting patients visible to `user`.

    level = 'identity' | 'clinical'
    """
    role = user["role_code"]
    if level == "clinical" and role not in CLINICAL_ROLES:
        return "FALSE", []
    if role == DIRECTOR:
        return "TRUE", []
    if role in (RECEPTION, ACCOUNTING):
        return ("TRUE", []) if level == "identity" else ("FALSE", [])
    if role in (DEPT_HEAD, DEPUTY_HEAD):
        deps = [str(d) for d in user.get("departments", [])]
        if not deps:
            return "FALSE", []
        return f"{alias}.department_id = ANY(%s::uuid[])", ["{" + ",".join(deps) + "}"]
    if role == THERAPIST:
        return (f"EXISTS (SELECT 1 FROM patient_assignments pa WHERE pa.patient_id = {alias}.id "
                f"AND pa.therapist_id = %s AND pa.ended_at IS NULL)"), [user["id"]]
    return "FALSE", []


def load_patient_scoped(db, user, patient_id, level="identity"):
    """Load a patient row if `user` may see it at `level`; otherwise NotFound (no disclosure)."""
    if level == "clinical":
        if not has_perm(user, "clinical.read"):
            raise NotFound()
    elif not has_perm(user, "patient.identity.read"):
        raise NotFound()
    cond, params = patient_scope_sql(user, "p", level)
    try:
        row = db.one(f"SELECT p.* FROM patients p WHERE p.id = %s::uuid AND ({cond})", [str(patient_id)] + params)
    except Exception as e:  # invalid uuid etc.
        if "invalid input syntax for type uuid" in str(e):
            raise NotFound()
        raise
    if not row:
        raise NotFound()
    return row


def load_episode_scoped(db, user, episode_id):
    try:
        ep = db.one("SELECT * FROM clinical_episodes WHERE id=%s::uuid", [str(episode_id)])
    except Exception as e:
        if "invalid input syntax for type uuid" in str(e):
            raise NotFound()
        raise
    if not ep:
        raise NotFound()
    patient = load_patient_scoped(db, user, ep["patient_id"], "clinical")
    return ep, patient


def can_review_department(user, department_id) -> bool:
    role = user["role_code"]
    if role == DIRECTOR:
        return True
    if role == DEPT_HEAD:
        return department_id in user.get("departments", [])
    if role == DEPUTY_HEAD:
        return department_id in user.get("delegated_departments", []) and department_id in user.get("departments", [])
    return False


def is_supervisor_of(user, patient) -> bool:
    role = user["role_code"]
    if role == DIRECTOR:
        return True
    return role in (DEPT_HEAD, DEPUTY_HEAD) and patient["department_id"] in user.get("departments", [])
