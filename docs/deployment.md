# النشر والنسخ الاحتياطي والاستعادة

## 1. الخادم (Hostinger VPS أو أي Ubuntu 24.04)

| البند | الإعداد |
|---|---|
| المستخدم | مستخدم نظام مخصص `motionlife` بلا صلاحيات root |
| المسار | `/opt/motionlife` |
| الملفات المرفوعة | `UPLOAD_DIR=/var/lib/motionlife/uploads` (خارج مجلد الويب) |
| PostgreSQL | يستمع على `localhost` فقط. مستخدم `ml_app` مالك القاعدة، بكلمة مرور قوية |
| Nginx | `proxy_pass http://127.0.0.1:8000`، مع `proxy_set_header X-Real-IP $remote_addr` و`client_max_body_size 12m` |
| HTTPS | `certbot --nginx` |
| `.env` | `ML_ENV=production`، `COOKIE_SECURE=1`، `PUBLIC_ORIGIN=https://<النطاق>`، و`SECRET_KEY` من `python3 -c "import secrets;print(secrets.token_urlsafe(48))"` |

خدمة systemd (`/etc/systemd/system/motionlife.service`):

```ini
[Service]
User=motionlife
WorkingDirectory=/opt/motionlife
EnvironmentFile=/opt/motionlife/.env
ExecStart=/opt/motionlife/venv/bin/gunicorn -w 3 --threads 4 -b 127.0.0.1:8000 wsgi:app
Restart=always
```

إن فشل Chromium بسبب الـ sandbox عند تشغيله كمستخدم غير root داخل حاوية، ثبّت الاعتماديات بـ `playwright install --with-deps chromium`. بديل ذلك: `PDF_ENGINE=none` (معاينة HTML وطباعة من المتصفح عبر `?format=html`).

## 2. الحساب الأول للمدير (دون حسابات تجريبية)

```bash
python3 - <<'PY'
from app import db
from app.security import hash_password
with db.tx() as d:
    uid = d.scalar("INSERT INTO users(username, full_name, role_code, password_hash, must_change_password) VALUES (%s,%s,'DIRECTOR',%s,true) RETURNING id",
                   ["admin.director", "الاسم الحقيقي", hash_password("كلمة-مرور-مؤقتة-قوية-123")])
    for dep in d.all("SELECT id FROM departments"):
        d.execute("INSERT INTO memberships VALUES (%s,%s)", [uid, dep["id"]])
PY
```

بعدها يُنشئ المدير بقية الحسابات من الواجهة.

## 3. ترحيل قاعدة البيانات عند التحديث

1. أوقف الخدمة، أو ضعها في وضع صيانة.
2. خذ نسخة احتياطية.
3. `python -m scripts.migrate`: يطبّق فقط ملفات `migrations/*.sql` الجديدة، كل ملف في معاملة.
4. `python -m scripts.seed --reference-only`: ينشر إصداراً **جديداً** من الاستبيانات أو الكتالوجات إن تغيّر محتواها. الإصدارات القديمة لا تُمس، والإجابات تبقى مرتبطة بنص السؤال الذي أُجيب عليه.
5. شغّل الخدمة.

## 4. النسخ الاحتياطي

```bash
# يومياً 02:30 (crontab للمستخدم motionlife)
30 2 * * * cd /opt/motionlife && set -a && . ./.env && set +a && BACKUP_DIR=/var/backups/motionlife UPLOAD_DIR=$UPLOAD_DIR ./scripts/backup.sh >> /var/log/motionlife-backup.log 2>&1
```

ما ينتجه السكربت:
- `motionlife-<UTC>.dump`: تنسيق pg_dump custom.
- `uploads-<UTC>.tar.gz`.
- `SHA256SUMS-<UTC>`.

ويتحقق من قابلية قراءة النسخة (`pg_restore --list`)، ويحذف ما هو أقدم من `KEEP_DAYS` (افتراضياً 30).

**إلزامي:** انسخ المجلد يومياً خارج الخادم ومشفّراً، مثلاً بـ `gpg --symmetric` أو `restic` أو `rclone crypt`. نسخة على الخادم نفسه لا تحمي من فقدانه.

## 5. الاستعادة (اختبار شهري)

```bash
createdb -O ml_app motionlife_restore_check
TARGET_DATABASE_URL=postgresql://ml_app:...@localhost/motionlife_restore_check \
  ./scripts/restore.sh /var/backups/motionlife/motionlife-XXXX.dump /var/backups/motionlife/uploads-XXXX.tar.gz /tmp/uploads_check
```

ما يفعله السكربت:
1. يتحقق من checksum.
2. يرفض الكتابة على قاعدة غير فارغة (إلا بـ `FORCE=1`).
3. يستعيد القاعدة.
4. يطبع أعداد الصفوف للمقارنة.

**للاستعادة الفعلية بعد كارثة:** استعد إلى قاعدة جديدة، وتحقق منها، ثم غيّر `DATABASE_URL` وأعد تشغيل الخدمة.

**ما تم فعلاً في بيئة البناء:** نُفّذت دورة نسخ ثم استعادة كاملة إلى قاعدة منفصلة، وتطابقت الأعداد:
- المرضى: 3.
- الإجابات: 82.
- أحداث التدقيق: 69.

## 6. المراقبة والسجلات

- سجل gunicorn لا يتضمن أجسام الطلبات. الأخطاء تُسجَّل برقم مرجعي دون بيانات مرضى.
- لا خدمات تحليلات أو تسجيل جلسات خارجية.
- راقب: مساحة القرص، نجاح النسخ الاحتياطي، وأحداث `LOGIN_FAILED` في سجل التدقيق.
