"""HTTP-level test client: logs in through the real API (cookie session + CSRF header)."""
from tests import support  # noqa: F401  (sets ML_ENV=test before app import)
from app import create_app

_app = None


def app():
    global _app
    if _app is None:
        _app = create_app()
        _app.testing = True
    return _app


class Client:
    def __init__(self, username, password="Motion-Demo-2026"):
        self.c = app().test_client()
        self.username = username
        r = self.c.post("/api/auth/login", json={"username": username, "password": password})
        assert r.status_code == 200, (username, r.status_code, r.get_json())
        self.csrf = self.c.get("/api/auth/me").get_json()["csrf_token"]

    def _h(self):
        return {"X-CSRF-Token": self.csrf}

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, json=None, **kw):
        return self.c.post(url, json=json if json is not None else {}, headers=self._h(), **kw)

    def put(self, url, json=None):
        return self.c.put(url, json=json or {}, headers=self._h())

    def patch(self, url, json=None):
        return self.c.patch(url, json=json or {}, headers=self._h())

    def ok(self, resp, code=(200, 201)):
        assert resp.status_code in (code if isinstance(code, tuple) else (code,)), (resp.status_code, resp.get_json())
        return resp.get_json()
