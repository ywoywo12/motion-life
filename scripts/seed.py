"""Seed reference data and SYNTHETIC demo data.

python -m scripts.seed            -> reference data + demo accounts + synthetic patients
python -m scripts.seed --reference-only   (production: roles, departments, questionnaires, catalogs)

Demo accounts are flagged is_test_account and refused when ML_ENV=production.
All demo patients are fictional (is_synthetic = true).
"""
import hashlib
import json
import sys

from app import config, db, rbac
from app.clinical import catalog_seed, definitions
from app.security import hash_password

DEMO_PASSWORD = "Motion-Demo-2026"

DEMO_USERS = [
    # username, full name, role, departments
    ("director", "د. مدير تجريبي", rbac.DIRECTOR, ["MEN", "WOMEN"]),
    ("head.men", "رئيس قسم الرجال (تجريبي)", rbac.DEPT_HEAD, ["MEN"]),
    ("head.women", "رئيسة قسم النساء (تجريبي)", rbac.DEPT_HEAD, ["WOMEN"]),
    ("deputy.men", "نائب رئيس قسم الرجال (تجريبي)", rbac.DEPUTY_HEAD, ["MEN"]),
    ("therapist.a", "المعالج أ (تجريبي)", rbac.THERAPIST, ["MEN"]),
    ("therapist.b", "المعالج ب (تجريبي)", rbac.THERAPIST, ["MEN"]),
    ("therapist.w", "المعالجة و (تجريبي)", rbac.THERAPIST, ["WOMEN"]),
    ("reception", "موظف الاستقبال (تجريبي)", rbac.RECEPTION, []),
    ("accounting", "المحاسبة (تجريبي)", rbac.ACCOUNTING, []),
    ("sysadmin", "مسؤول النظام (تجريبي)", rbac.SYSADMIN, []),
]


def seed_reference(d):
    for code, name in rbac.ROLE_NAMES.items():
        d.execute("INSERT INTO roles(code,name) VALUES (%s,%s) ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name", [code, name])
    for code, desc in rbac.PERMISSIONS.items():
        d.execute("INSERT INTO permissions(code,description) VALUES (%s,%s) ON CONFLICT (code) DO UPDATE SET description=EXCLUDED.description",
                  [code, desc])
    d.execute("DELETE FROM role_permissions")
    for role, perms in rbac.ROLE_PERMISSIONS.items():
        for p in sorted(perms):
            d.execute("INSERT INTO role_permissions VALUES (%s,%s)", [role, p])
    for code, name in (("MEN", "قسم الرجال"), ("WOMEN", "قسم النساء")):
        d.execute("INSERT INTO departments(code,name) VALUES (%s,%s) ON CONFLICT (code) DO NOTHING", [code, name])

    for qcode, spec in definitions.QUESTIONNAIRES.items():
        qid = d.scalar("INSERT INTO questionnaires(code,name) VALUES (%s,%s) ON CONFLICT (code) DO UPDATE SET name=EXCLUDED.name RETURNING id",
                       [qcode, spec["name"]])
        payload = {"sections": [{"code": c, "title": t} for c, t in spec["sections"]], "scope": spec["scope"]}
        qs = []
        order = {c: i for i, (c, _) in enumerate(spec["sections"])}
        for pos, q in enumerate(sorted(spec["questions"], key=lambda q: order[q["section"]])):
            qs.append((q["code"], q["section"], pos, {k: v for k, v in q.items() if k not in ("code", "section")}))
        h = hashlib.sha256(json.dumps([payload, qs], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        cur = d.one("SELECT id, version, content_hash FROM questionnaire_versions WHERE questionnaire_id=%s AND status='PUBLISHED' ORDER BY version DESC LIMIT 1", [qid])
        if cur and cur["content_hash"] == h:
            continue
        nextv = (d.scalar("SELECT max(version) FROM questionnaire_versions WHERE questionnaire_id=%s", [qid]) or 0) + 1
        if cur:
            d.execute("UPDATE questionnaire_versions SET status='RETIRED' WHERE id=%s", [cur["id"]])
        vid = d.scalar("""INSERT INTO questionnaire_versions(questionnaire_id, version, status, definition, content_hash, published_at)
                          VALUES (%s,%s,'PUBLISHED',%s,%s,now()) RETURNING id""", [qid, nextv, payload, h])
        for code, section, pos, defin in qs:
            d.execute("INSERT INTO question_definitions(questionnaire_version_id, code, section, position, definition) VALUES (%s,%s,%s,%s,%s)",
                      [vid, code, section, pos, defin])
        print(f"published questionnaire {qcode} v{nextv}")

    for kind, code, data in catalog_seed.catalog_rows():
        cur = d.one("SELECT id, data FROM catalogs WHERE kind=%s AND code=%s AND status='PUBLISHED'", [kind, code])
        if cur and cur["data"] == json.loads(json.dumps(data, ensure_ascii=False)):
            continue
        nextv = (d.scalar("SELECT max(version) FROM catalogs WHERE kind=%s AND code=%s", [kind, code]) or 0) + 1
        if cur:
            d.execute("UPDATE catalogs SET status='RETIRED' WHERE id=%s", [cur["id"]])
        d.execute("""INSERT INTO catalogs(kind, code, version, status, data, review_note, published_at)
                     VALUES (%s,%s,%s,'PUBLISHED',%s,%s,now())""", [kind, code, nextv, data, catalog_seed.REVIEW_NOTE])


def seed_demo(d):
    if config.IS_PROD and not config.ALLOW_DEMO:
        raise SystemExit("refusing to create demo accounts in production (set ALLOW_DEMO=1 only for a trial deployment)")
    deps = {r["code"]: r["id"] for r in d.all("SELECT code, id FROM departments")}
    pw = hash_password(DEMO_PASSWORD)
    ids = {}
    for username, name, role, dcodes in DEMO_USERS:
        uid = d.scalar("""INSERT INTO users(username, full_name, role_code, password_hash, is_test_account)
                          VALUES (%s,%s,%s,%s,true)
                          ON CONFLICT (username) DO UPDATE SET full_name=EXCLUDED.full_name RETURNING id""",
                       [username, name, role, pw])
        ids[username] = uid
        for dc in dcodes:
            d.execute("INSERT INTO memberships(user_id, department_id) VALUES (%s,%s) ON CONFLICT DO NOTHING", [uid, deps[dc]])
    if not d.scalar("SELECT count(*) FROM review_delegations WHERE delegate_id=%s AND revoked_at IS NULL", [ids["deputy.men"]]):
        d.execute("""INSERT INTO review_delegations(delegator_id, delegate_id, department_id, reason)
                     VALUES (%s,%s,%s,'تفويض تجريبي لنائب رئيس قسم الرجال')""", [ids["head.men"], ids["deputy.men"], deps["MEN"]])
    if d.scalar("SELECT count(*) FROM patients") == 0:
        from app.services import patients as ps
        from app.security import load_user
        rec = load_user(d, ids["reception"])
        head_m = load_user(d, ids["head.men"])
        head_w = load_user(d, ids["head.women"])
        demo = [
            ("سامر تجريبي الأول", "1980-04-12", "M", "0900000001", "مهندس", "therapist.a", head_m),
            ("خالد تجريبي الثاني", "1958-09-01", "M", "0900000002", "متقاعد", "therapist.b", head_m),
            ("ريم تجريبية الثالثة", "1991-02-20", "F", "0900000003", "معلمة", "therapist.w", head_w),
        ]
        for name, bd, sex, phone, occ, ther, head in demo:
            p = ps.create_patient(d, rec, {"full_name": name, "birth_date": bd, "sex": sex, "phone": phone,
                                           "occupation": occ, "is_synthetic": True}, allow_duplicate=True)
            ps.assign_therapist(d, head, p["id"], ids[ther], "تخصيص تجريبي")
    print("demo users created; password for all demo accounts:", DEMO_PASSWORD)


if __name__ == "__main__":
    with db.tx() as d:
        seed_reference(d)
        if "--reference-only" not in sys.argv:
            seed_demo(d)
    print("seed done")
