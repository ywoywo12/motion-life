#!/usr/bin/env sh
# Container start: apply migrations, publish reference data, (trial only) demo data, then serve.
set -e
python -m scripts.migrate
if [ "$ALLOW_DEMO" = "1" ]; then
  python -m scripts.seed
  python -m scripts.demo_data || true
else
  python -m scripts.seed --reference-only
fi
exec gunicorn -w "${WEB_WORKERS:-2}" --threads 4 --timeout 120 -b "0.0.0.0:${PORT:-8000}" wsgi:app
