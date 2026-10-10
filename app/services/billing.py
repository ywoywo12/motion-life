"""Accounting placeholder (paper file: agreed sessions, total, up to 4 installments). No clinical data exposed."""
from __future__ import annotations

from decimal import Decimal

from .. import rbac
from ..audit import audit
from ..errors import Conflict, NotFound, ValidationError
from .. import validation as v


def _episode_for_billing(d, user, episode_id):
    ep = d.one("SELECT id, patient_id, title, status FROM clinical_episodes WHERE id=%s::uuid", [v.uid(episode_id)])
    if not ep:
        raise NotFound()
    rbac.load_patient_scoped(d, user, ep["patient_id"], "identity")
    return ep


def get_billing(d, user, episode_id):
    rbac.require_perm(user, "billing.read")
    ep = _episode_for_billing(d, user, episode_id)
    pkg = d.one("SELECT * FROM billing_packages WHERE episode_id=%s", [ep["id"]])
    pays = d.all("SELECT * FROM payments WHERE package_id=%s ORDER BY installment_no", [pkg["id"]]) if pkg else []
    paid = sum((p["amount"] for p in pays), Decimal(0)) if pays else Decimal(0)
    sessions_done = d.scalar("SELECT count(*) FROM sessions WHERE episode_id=%s", [ep["id"]])
    return {"episode": {"id": ep["id"], "title": ep["title"]}, "package": pkg, "payments": pays, "paid": paid,
            "remaining": (Decimal(pkg["total_amount"]) - paid) if pkg else None, "sessions_done": sessions_done}


def set_package(d, user, episode_id, data):
    rbac.require_perm(user, "billing.write")
    ep = _episode_for_billing(d, user, episode_id)
    if d.scalar("SELECT count(*) FROM billing_packages WHERE episode_id=%s", [ep["id"]]):
        raise Conflict("الباقة مسجلة مسبقاً")
    pid = d.scalar("""INSERT INTO billing_packages(episode_id, sessions_agreed, total_amount, currency, created_by)
                      VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                   [ep["id"], v.num(data, "sessions_agreed", "عدد الجلسات المتفق عليها", required=True, lo=1, hi=100, integer=True),
                    v.num(data, "total_amount", "المبلغ الإجمالي", required=True, lo=0, hi=1e12),
                    v.choice(data, "currency", "العملة", ("SYP", "USD")) or "SYP", user["id"]])
    audit(d, user, "BILLING_PACKAGE", "billing_package", pid, patient_id=ep["patient_id"], category="ADMIN")
    return pid


def add_payment(d, user, episode_id, data):
    rbac.require_perm(user, "billing.write")
    ep = _episode_for_billing(d, user, episode_id)
    pkg = d.one("SELECT * FROM billing_packages WHERE episode_id=%s", [ep["id"]])
    if not pkg:
        raise ValidationError("سجّل الباقة أولاً")
    n = (d.scalar("SELECT COALESCE(max(installment_no),0) FROM payments WHERE package_id=%s", [pkg["id"]]) or 0) + 1
    if n > 4:
        raise ValidationError("الملف الورقي يدعم أربع دفعات كحد أقصى")
    amount = Decimal(str(v.num(data, "amount", "المبلغ", required=True, lo=0.01, hi=1e12)))
    paid = d.scalar("SELECT COALESCE(sum(amount),0) FROM payments WHERE package_id=%s", [pkg["id"]])
    if Decimal(paid) + amount > Decimal(pkg["total_amount"]):
        raise ValidationError("المبلغ يتجاوز المتبقي")
    pid = d.scalar("""INSERT INTO payments(package_id, installment_no, amount, paid_on, recorded_by) VALUES (%s,%s,%s,%s,%s) RETURNING id""",
                   [pkg["id"], n, amount, v.date(data, "paid_on", "تاريخ الدفعة", required=True), user["id"]])
    audit(d, user, "PAYMENT_ADD", "payment", pid, patient_id=ep["patient_id"], category="ADMIN", details={"installment": n})
    return pid


def billing_list(d, user):
    rbac.require_perm(user, "billing.read")
    return d.all("""SELECT e.id AS episode_id, e.title, p.full_name, p.file_no, b.sessions_agreed, b.total_amount, b.currency,
                           (SELECT COALESCE(sum(amount),0) FROM payments x WHERE x.package_id=b.id) AS paid,
                           (SELECT count(*) FROM sessions s WHERE s.episode_id=e.id) AS sessions_done
                    FROM clinical_episodes e JOIN patients p ON p.id=e.patient_id
                    LEFT JOIN billing_packages b ON b.episode_id=e.id ORDER BY e.created_at DESC LIMIT 200""")
