# Production/trial image. Uses the built-in libpq adapter (the path tested in development).
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 ML_ENV=production
RUN apt-get update && apt-get install -y --no-install-recommends libpq5 postgresql-client fonts-noto-core fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
RUN pip install --no-cache-dir Flask==3.1.3 Jinja2==3.1.6 Werkzeug==3.1.8 playwright==1.56.0 "gunicorn>=22,<24" \
    && playwright install --with-deps chromium
COPY . .
RUN chmod +x scripts/start.sh && mkdir -p /app/var/uploads
EXPOSE 8000
CMD ["scripts/start.sh"]
