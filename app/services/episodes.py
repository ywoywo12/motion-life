"""Clinical episodes (one per problem), hold/resume/close."""
from __future__ import annotations

from .. import rbac
from ..audit import audit
from ..errors import Forbidden, RuleBlocked, ValidationError
from .. import validation as v


def create_episode(d, user, patient_id, data):
    rbac.require_perm(user, "clinical.write")
    p = rbac.load_patient_scoped(d, user, patient_id, "clinical")
    region = v.choice(data, "region", "المنطقة", ("LUMBAR",), required=True)
    title = v.s(data, "title", "عنوان المشكلة", required=True, max_len=200)
    ep = d.one("INSERT INTO clinical_episodes(patient_id, region, title, created_by) VALUES (%s,%s,%s,%s) RETURNING *",
               [p["id"], region, title, user["id"]])
    d.execute("INSERT INTO assessments(episode_id, created_by) VALUES (%s,%s)", [ep["id"], user["id"]])
    d.execute("""INSERT INTO safety_screenings(episode_id, status, rules_version, computed_by)
                 VALUES (%s,'NOT_CONFIRMED','initial',%s)""", [ep["id"], user["id"]])
    audit(d, user, "EPISODE_CREATE", "episode", ep["id"], patient_id=p["id"], details={"region": region})
    return ep


def list_for_patient(d, patient_id):
    return d.all(
        """SELECT e.*, s.status AS safety_status, a.status AS assessment_status, a.current_version AS assessment_version,
                  (SELECT pv.status FROM plan_versions pv JOIN treatment_plans tp ON tp.id=pv.plan_id
                    WHERE tp.episode_id=e.id ORDER BY pv.version_no DESC LIMIT 1) AS latest_plan_status,
                  (SELECT count(*) FROM sessions se WHERE se.episode_id=e.id) AS session_count
           FROM clinical_episodes e
           LEFT JOIN safety_screenings s ON s.episode_id=e.id AND s.is_current
           LEFT JOIN assessments a ON a.episode_id=e.id
           WHERE e.patient_id=%s ORDER BY e.created_at DESC""", [patient_id])


def resume_episode(d, user, episode_id, reason):
    """Lift an ON_HOLD (e.g. after emergency referral was resolved). Supervisors only, documented."""
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    if not rbac.is_supervisor_of(user, p):
        raise Forbidden("رفع التعليق يتطلب رئيس القسم أو المدير")
    reason = v.s({"r": reason}, "r", "سبب رفع التعليق والمعطيات الطبية الجديدة", required=True, max_len=1000)
    if ep["status"] != "ON_HOLD":
        raise ValidationError("الحلقة ليست معلّقة")
    cur = d.one("SELECT status FROM safety_screenings WHERE episode_id=%s AND is_current", [ep["id"]])
    if cur and cur["status"] == "EMERGENCY":
        raise RuleBlocked("فرز السلامة الحالي ما زال إسعافياً. حدّث إجابات السلامة بعد التقييم الطبي (مع ملاحظة المصدر) قبل رفع التعليق.")
    d.execute("UPDATE clinical_episodes SET status='OPEN', hold_reason=NULL, version=version+1 WHERE id=%s", [ep["id"]])
    audit(d, user, "EPISODE_RESUME", "episode", ep["id"], patient_id=p["id"], reason=reason)


def close_episode(d, user, episode_id, reason):
    ep, p = rbac.load_episode_scoped(d, user, episode_id)
    rbac.require_perm(user, "session.write")
    reason = v.s({"r": reason}, "r", "سبب الإغلاق", required=True)
    d.execute("UPDATE clinical_episodes SET status='CLOSED', closed_at=now(), version=version+1 WHERE id=%s", [ep["id"]])
    d.execute("""UPDATE plan_versions SET status='CLOSED', updated_at=now() WHERE plan_id IN (SELECT id FROM treatment_plans WHERE episode_id=%s)
                 AND status='APPROVED'""", [ep["id"]])
    audit(d, user, "EPISODE_CLOSE", "episode", ep["id"], patient_id=p["id"], reason=reason)
