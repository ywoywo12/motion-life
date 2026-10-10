"""Attachments: stored outside the web root, served only through an authorised route (no public URLs)."""
from __future__ import annotations

import hashlib
import secrets

from .. import config, rbac
from ..audit import audit
from ..errors import NotFound, ValidationError
from .. import validation as v

ALLOWED = {"application/pdf": b"%PDF", "image/png": b"\x89PNG", "image/jpeg": b"\xff\xd8\xff"}
KINDS = {"IMAGING_REPORT": "تقرير صور طبية", "SURGICAL_REPORT": "تقرير عملية", "REFERRAL_LETTER": "رسالة إحالة", "OTHER": "أخرى"}


def upload(d, user, patient_id, kind, filename, mime, data: bytes, episode_id=None):
    rbac.require_perm(user, "clinical.write")
    p = rbac.load_patient_scoped(d, user, patient_id, "clinical")
    kind = v.choice({"k": kind}, "k", "نوع المرفق", tuple(KINDS), required=True)
    if mime not in ALLOWED or not data.startswith(ALLOWED[mime]):
        raise ValidationError("نوع الملف غير مسموح (PDF أو PNG أو JPEG فقط)، أو محتواه لا يطابق نوعه")
    if len(data) > config.MAX_UPLOAD_MB * 1024 * 1024:
        raise ValidationError("الملف كبير جداً")
    name = (v.clean_text(filename, 150) or "file").replace("/", "_").replace("\\", "_")
    key = secrets.token_hex(20)
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    (config.UPLOAD_DIR / key).write_bytes(data)
    if episode_id:
        ep = d.one("SELECT id FROM clinical_episodes WHERE id=%s::uuid AND patient_id=%s", [v.uid(episode_id), p["id"]])
        if not ep:
            raise NotFound()
    aid = d.scalar("""INSERT INTO attachments(patient_id, episode_id, kind, filename, mime, size_bytes, sha256, storage_key, uploaded_by)
                      VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                   [p["id"], episode_id, kind, name, mime, len(data), hashlib.sha256(data).hexdigest(), key, user["id"]])
    audit(d, user, "ATTACHMENT_UPLOAD", "attachment", aid, patient_id=p["id"], details={"kind": kind, "size": len(data)})
    return aid


def list_for_patient(d, patient_id):
    return d.all("""SELECT a.id, a.kind, a.filename, a.mime, a.size_bytes, a.uploaded_at, u.full_name AS uploaded_by_name
                    FROM attachments a JOIN users u ON u.id=a.uploaded_by WHERE a.patient_id=%s AND a.removed_at IS NULL
                    ORDER BY a.uploaded_at DESC""", [patient_id])


def fetch(d, user, attachment_id):
    a = d.one("SELECT * FROM attachments WHERE id=%s::uuid AND removed_at IS NULL", [v.uid(attachment_id)])
    if not a:
        raise NotFound()
    rbac.load_patient_scoped(d, user, a["patient_id"], "clinical")
    path = config.UPLOAD_DIR / a["storage_key"]
    if not path.exists():
        raise NotFound("الملف غير موجود في التخزين")
    audit(d, user, "ATTACHMENT_VIEW", "attachment", a["id"], patient_id=a["patient_id"], category="ACCESS")
    return a, path.read_bytes()
