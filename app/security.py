"""Passwords, login throttling and server-side sessions."""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

from . import config
from .audit import audit
from .errors import Unauthorized, ValidationError

_SCRYPT = dict(n=2**14, r=8, p=1, dklen=32)


def hash_password(pw: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(pw.encode(), salt=salt, maxmem=64 * 1024 * 1024, **_SCRYPT)
    return "scrypt$%d$%d$%d$%s$%s" % (
        _SCRYPT["n"], _SCRYPT["r"], _SCRYPT["p"],
        base64.b64encode(salt).decode(), base64.b64encode(dk).decode(),
    )


def verify_password(pw: str, stored: str) -> bool:
    try:
        algo, n, r, p, salt, dk = stored.split("$")
        if algo != "scrypt":
            return False
        calc = hashlib.scrypt(pw.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p),
                              dklen=len(base64.b64decode(dk)), maxmem=64 * 1024 * 1024)
        return hmac.compare_digest(calc, base64.b64decode(dk))
    except Exception:
        return False


_DUMMY_HASH = None


def _dummy_hash():
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_hex(8))
    return _DUMMY_HASH


def validate_new_password(pw: str):
    if len(pw) < 10 or pw.lower() == pw or not any(ch.isdigit() for ch in pw):
        raise ValidationError("كلمة المرور يجب أن تكون 10 أحرف على الأقل وتحتوي حرفاً كبيراً ورقماً")


def _token_hash(tok: str) -> str:
    return hashlib.sha256((config.SECRET_KEY + ":" + tok).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc)


LOGIN_FAIL_MSG = "اسم المستخدم أو كلمة المرور غير صحيحة، أو الحساب مقفل مؤقتاً"


def login(db, username: str, password: str, ip: str | None, user_agent: str | None):
    """Returns (session_token, csrf_token, user), or (None, None, None) on failure (attempt is recorded)."""
    username = (username or "").strip().lower()
    t0 = time.monotonic()
    # IP-level throttle
    ip_fails = db.scalar(
        "SELECT count(*) FROM login_attempts WHERE ip=%s AND NOT success AND at > now() - make_interval(mins => %s)",
        [ip, config.LOGIN_LOCK_MINUTES],
    )
    user = db.one("SELECT * FROM users WHERE username=%s", [username])
    ok = False
    reason = "bad_credentials"
    if ip_fails >= config.LOGIN_MAX_ATTEMPTS * 4:
        reason = "ip_throttled"
        verify_password(password, _dummy_hash())
    elif user is None:
        verify_password(password, _dummy_hash())  # constant-ish timing
    elif not user["is_active"]:
        verify_password(password, _dummy_hash())
        reason = "inactive"
    elif user["locked_until"] and user["locked_until"] > now():
        verify_password(password, _dummy_hash())
        reason = "locked"
    elif verify_password(password, user["password_hash"]):
        ok = True
    db.execute("INSERT INTO login_attempts(username, ip, success) VALUES (%s,%s,%s)", [username[:60], ip, ok])
    if not ok:
        if user is not None and reason == "bad_credentials":
            fails = user["failed_attempts"] + 1
            lock = None
            if fails >= config.LOGIN_MAX_ATTEMPTS:
                lock = now() + timedelta(minutes=config.LOGIN_LOCK_MINUTES)
                fails = 0
            db.execute("UPDATE users SET failed_attempts=%s, locked_until=COALESCE(%s, locked_until) WHERE id=%s",
                       [fails, lock, user["id"]])
        audit(db, None, "LOGIN_FAILED", "user", user["id"] if user else None, category="SECURITY",
              details={"username": username[:60], "reason": reason}, ip=ip)
        # small uniform delay to blunt online guessing
        elapsed = time.monotonic() - t0
        if elapsed < 0.3:
            time.sleep(0.3 - elapsed)
        return None, None, None  # caller commits the attempt record, then raises Unauthorized
    db.execute("UPDATE users SET failed_attempts=0, locked_until=NULL WHERE id=%s", [user["id"]])
    tok = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(24)
    db.execute(
        "INSERT INTO auth_sessions(token_hash, csrf_token, user_id, expires_at, ip, user_agent) VALUES (%s,%s,%s,%s,%s,%s)",
        [_token_hash(tok), csrf, user["id"], now() + timedelta(hours=config.SESSION_TTL_HOURS), ip, (user_agent or "")[:200]],
    )
    audit(db, user, "LOGIN", "user", user["id"], category="SECURITY", ip=ip)
    return tok, csrf, user


def resolve_session(db, token: str | None):
    """Returns (user_row, session_row) or (None, None)."""
    if not token or len(token) > 200:
        return None, None
    s = db.one(
        """SELECT s.*, u.username, u.full_name, u.role_code, u.is_active, u.must_change_password
           FROM auth_sessions s JOIN users u ON u.id = s.user_id
           WHERE s.token_hash=%s AND s.revoked_at IS NULL AND s.expires_at > now()
             AND s.last_seen_at > now() - make_interval(mins => %s)""",
        [_token_hash(token), config.SESSION_IDLE_MINUTES],
    )
    if not s or not s["is_active"]:
        return None, None
    db.execute("UPDATE auth_sessions SET last_seen_at=now() WHERE id=%s AND last_seen_at < now() - interval '30 seconds'", [s["id"]])
    user = load_user(db, s["user_id"])
    return user, s


def load_user(db, user_id):
    u = db.one("SELECT id, username, full_name, role_code, is_active, must_change_password, is_test_account FROM users WHERE id=%s", [user_id])
    if not u:
        return None
    u["departments"] = [r["department_id"] for r in db.all("SELECT department_id FROM memberships WHERE user_id=%s", [user_id])]
    u["delegated_departments"] = [
        r["department_id"] for r in db.all(
            """SELECT d.department_id FROM review_delegations d JOIN users g ON g.id = d.delegator_id
               WHERE d.delegate_id=%s AND d.revoked_at IS NULL AND (d.expires_at IS NULL OR d.expires_at > now())
                 AND g.is_active""", [user_id])
    ]
    return u


def logout(db, session_id, user):
    db.execute("UPDATE auth_sessions SET revoked_at=now() WHERE id=%s", [session_id])
    audit(db, user, "LOGOUT", "user", user["id"], category="SECURITY")


def revoke_all_sessions(db, user_id):
    db.execute("UPDATE auth_sessions SET revoked_at=now() WHERE user_id=%s AND revoked_at IS NULL", [user_id])


def require_user(user):
    if not user:
        raise Unauthorized("يجب تسجيل الدخول")
    return user
