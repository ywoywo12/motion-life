"""Append-only audit trail (table protected by a DB trigger)."""
from __future__ import annotations


def _current_ip():
    try:
        from flask import g, has_request_context

        if has_request_context():
            return getattr(g, "client_ip", None)
    except Exception:
        pass
    return None


def audit(db, user, action: str, entity_type: str, entity_id=None, *, patient_id=None, reason=None,
          details=None, category="CLINICAL", ip=None):
    db.execute(
        """INSERT INTO audit_events(actor_id, actor_role, action, entity_type, entity_id, patient_id, reason, details, ip, category)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        [
            user["id"] if user else None,
            user["role_code"] if user else None,
            action, entity_type, str(entity_id) if entity_id else None,
            patient_id, reason, details or {}, ip or _current_ip(), category,
        ],
    )
