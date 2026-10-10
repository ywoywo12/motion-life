"""Role-based dashboard (work queues)."""
from __future__ import annotations

from .. import rbac
from . import plans as psvc


def dashboard(d, user):
    out = {"role": user["role_code"], "role_name": rbac.ROLE_NAMES[user["role_code"]], "cards": {}}
    role = user["role_code"]
    if role in rbac.CLINICAL_ROLES:
        cond, params = rbac.patient_scope_sql(user, "p", "clinical")
        out["cards"]["new_patients"] = d.all(
            f"""SELECT p.id, p.full_name, p.file_no, p.created_at FROM patients p
                WHERE ({cond}) AND NOT EXISTS (SELECT 1 FROM clinical_episodes e WHERE e.patient_id=p.id)
                ORDER BY p.created_at DESC LIMIT 20""", params)
        out["cards"]["assessments_in_progress"] = d.all(
            f"""SELECT e.id AS episode_id, e.title, p.full_name, p.file_no, s.status AS safety_status, a.status
                FROM clinical_episodes e JOIN patients p ON p.id=e.patient_id JOIN assessments a ON a.episode_id=e.id
                LEFT JOIN safety_screenings s ON s.episode_id=e.id AND s.is_current
                WHERE ({cond}) AND e.status <> 'CLOSED' AND a.status='IN_PROGRESS' ORDER BY a.updated_at DESC LIMIT 20""", params)
        out["cards"]["my_drafts"] = d.all(
            f"""SELECT e.id AS episode_id, e.title, p.full_name, pv.version_no, pv.status FROM plan_versions pv
                JOIN treatment_plans tp ON tp.id=pv.plan_id JOIN clinical_episodes e ON e.id=tp.episode_id
                JOIN patients p ON p.id=e.patient_id
                WHERE ({cond}) AND pv.author_id=%s AND pv.status IN ('DRAFT','CHANGES_REQUESTED','ON_HOLD')
                  AND pv.version_no = (SELECT max(version_no) FROM plan_versions x WHERE x.plan_id=pv.plan_id)
                ORDER BY pv.updated_at DESC""", params + [user["id"]])
        out["cards"]["alerts"] = d.all(
            f"""SELECT al.id, al.severity, al.message, al.created_at, e.id AS episode_id, p.full_name FROM alerts al
                JOIN clinical_episodes e ON e.id=al.episode_id JOIN patients p ON p.id=al.patient_id
                WHERE ({cond}) AND al.status='OPEN'
                ORDER BY CASE al.severity WHEN 'CRITICAL' THEN 0 WHEN 'HIGH' THEN 1 WHEN 'MEDIUM' THEN 2 ELSE 3 END, al.created_at DESC
                LIMIT 30""", params)
        out["cards"]["due_reviews"] = d.all(
            f"""SELECT e.id AS episode_id, e.title, p.full_name, c.n AS sessions,
                       CASE WHEN c.n >= 12 AND NOT EXISTS (SELECT 1 FROM progress_reviews r WHERE r.episode_id=e.id AND r.milestone='S12') THEN 'S12'
                            ELSE 'S6' END AS milestone
                FROM clinical_episodes e JOIN patients p ON p.id=e.patient_id
                JOIN LATERAL (SELECT count(*) AS n FROM sessions s WHERE s.episode_id=e.id) c ON true
                WHERE ({cond}) AND e.status='OPEN' AND (
                  (c.n >= 6 AND NOT EXISTS (SELECT 1 FROM progress_reviews r WHERE r.episode_id=e.id AND r.milestone='S6')) OR
                  (c.n >= 12 AND NOT EXISTS (SELECT 1 FROM progress_reviews r WHERE r.episode_id=e.id AND r.milestone='S12')))""", params)
        out["cards"]["today_sessions"] = d.all(
            f"""SELECT s.session_no, s.session_date, e.id AS episode_id, p.full_name, u.full_name AS therapist FROM sessions s
                JOIN clinical_episodes e ON e.id=s.episode_id JOIN patients p ON p.id=e.patient_id JOIN users u ON u.id=s.therapist_id
                WHERE ({cond}) AND s.session_date = CURRENT_DATE ORDER BY s.created_at DESC""", params)
        out["cards"]["active_treatment"] = d.all(
            f"""SELECT e.id AS episode_id, e.title, p.full_name, pv.version_no,
                       (SELECT count(*) FROM sessions s WHERE s.episode_id=e.id) AS sessions,
                       (pv.content->>'sessions_planned') AS planned
                FROM plan_versions pv JOIN treatment_plans tp ON tp.id=pv.plan_id JOIN clinical_episodes e ON e.id=tp.episode_id
                JOIN patients p ON p.id=e.patient_id
                WHERE ({cond}) AND pv.status='APPROVED' AND e.status='OPEN' ORDER BY p.full_name LIMIT 50""", params)
    if rbac.has_perm(user, "plan.review"):
        out["cards"]["review_queue"] = psvc.review_queue(d, user)
    if role == rbac.RECEPTION:
        out["cards"]["recent_patients"] = d.all("SELECT id, full_name, file_no, created_at FROM patients ORDER BY created_at DESC LIMIT 15")
    return out
