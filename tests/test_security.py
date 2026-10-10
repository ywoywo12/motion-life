"""Security and misuse cases: brute force, CSRF/origin, XSS in notes, sessions, role changes, pages per role."""
import unittest

from tests import support as S
from tests.http import Client, app
from app import db


class Security(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        S.reset_db()

    def test_login_lockout_and_generic_message(self):
        c = app().test_client()
        for _ in range(5):
            r = c.post("/api/auth/login", json={"username": "therapist.b", "password": "wrong"})
            self.assertEqual(r.status_code, 401)
        r = c.post("/api/auth/login", json={"username": "therapist.b", "password": "Motion-Demo-2026"})
        self.assertEqual(r.status_code, 401)  # locked even with the right password
        r2 = c.post("/api/auth/login", json={"username": "nobody", "password": "x"})
        self.assertEqual(r.get_json()["error"]["message"], r2.get_json()["error"]["message"])  # no user enumeration
        with db.tx() as d:
            self.assertGreaterEqual(d.scalar("SELECT count(*) FROM audit_events WHERE action='LOGIN_FAILED'"), 6)
            d.execute("UPDATE users SET locked_until=NULL, failed_attempts=0 WHERE username='therapist.b'")
            d.execute("DELETE FROM login_attempts")

    def test_unauthenticated_and_csrf(self):
        c = app().test_client()
        self.assertEqual(c.get("/api/patients").status_code, 401)
        self.assertEqual(c.get("/dashboard").status_code, 302)
        a = Client("reception")
        r = a.c.post("/api/patients", json={"full_name": "س", "sex": "M"})
        self.assertEqual(r.status_code, 403)
        r = a.c.post("/api/patients", json={"full_name": "س", "sex": "M"}, headers={"X-CSRF-Token": a.csrf, "Origin": "https://evil.example"})
        self.assertEqual(r.status_code, 403)

    def test_xss_in_notes_is_escaped(self):
        rec = Client("reception")
        payload = '<script>alert(1)</script><img src=x onerror=alert(2)>'
        res = rec.ok(rec.post("/api/patients", {"full_name": "اختبار " + payload, "sex": "M", "phone": "0911111111"}))
        page = rec.get(f"/patients/{res['id']}").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;", page)
        self.assertIn("script-src 'self'", rec.get("/dashboard").headers["Content-Security-Policy"])

    def test_duplicate_detection(self):
        rec = Client("reception")
        r = rec.post("/api/patients", {"full_name": "سامر تجريبي الاول", "birth_date": "1980-04-12", "sex": "M"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.get_json()["error"]["code"], "DUPLICATE_SUSPECTED")
        r = rec.post("/api/patients", {"full_name": "شخص آخر", "sex": "M", "phone": "+963 900 000 001"})
        self.assertEqual(r.status_code, 409)  # same normalised phone

    def test_no_self_role_change_and_deactivation_kills_sessions(self):
        sa = Client("sysadmin")
        with db.tx() as d:
            me = d.one("SELECT id, version FROM users WHERE username='sysadmin'")
            dr = d.one("SELECT id, version FROM users WHERE username='director'")
            tb = d.one("SELECT id, version FROM users WHERE username='therapist.b'")
        self.assertEqual(sa.patch(f"/api/admin/users/{me['id']}", {"role_code": "DIRECTOR", "version": me["version"]}).status_code, 403)
        self.assertEqual(sa.patch(f"/api/admin/users/{dr['id']}", {"is_active": False, "version": dr["version"]}).status_code, 403)
        t = Client("therapist.b")
        self.assertEqual(t.get("/api/dashboard").status_code, 200)
        sa.ok(sa.patch(f"/api/admin/users/{tb['id']}", {"is_active": False, "version": tb["version"], "reason": "اختبار"}))
        self.assertEqual(t.get("/api/dashboard").status_code, 401)
        with db.tx() as d:
            d.execute("UPDATE users SET is_active=true WHERE id=%s", [tb["id"]])
        # therapist cannot reach admin endpoints
        self.assertEqual(Client("therapist.a").get("/api/admin/users").status_code, 403)

    def test_invalid_ids_do_not_leak(self):
        a = Client("therapist.a")
        for url in ("/api/patients/not-a-uuid", "/api/episodes/123/assessment", "/patients/xyz"):
            self.assertEqual(a.get(url).status_code, 404, url)

    def test_pages_render_per_role(self):
        with db.tx() as d:
            pid = S.patient_id(d, "سامر")
            from app.services import episodes
            ep = episodes.create_episode(d, S.u(d, "therapist.a"), pid, {"region": "LUMBAR", "title": "صفحات"})["id"]
        expectations = {
            "therapist.a": {f"/patients/{pid}": 200, f"/patients/{pid}/history": 200, f"/episodes/{ep}/assessment": 200,
                            f"/episodes/{ep}/plan": 200, f"/episodes/{ep}/sessions": 200, f"/episodes/{ep}/outcomes": 200,
                            "/reviews": 403, "/admin/users": 403, "/reports": 200, "/dashboard": 200, "/patients": 200},
            "head.men": {"/reviews": 200, "/admin/users": 200, "/admin/catalogs": 200, f"/episodes/{ep}/assessment": 200},
            "director": {"/admin/audit": 200, "/admin/catalogs": 200, "/reviews": 200},
            "reception": {f"/patients/{pid}": 200, f"/patients/{pid}/history": 404, f"/episodes/{ep}/assessment": 404, "/reports": 403},
            "accounting": {f"/episodes/{ep}/billing": 200, "/billing": 200, f"/episodes/{ep}/assessment": 404},
            "sysadmin": {"/admin/users": 200, "/admin/audit": 200, "/patients": 403, f"/patients/{pid}": 404},
            "head.women": {f"/patients/{pid}": 404},
        }
        for user, pages in expectations.items():
            c = Client(user)
            for url, code in pages.items():
                self.assertEqual(c.get(url).status_code, code, f"{user} {url}")


if __name__ == "__main__":
    unittest.main()
