# ═══════════════════════════════════════════════════════════════════
#  QMS Enterprise — Railway Production Dockerfile
#  Single container: Flask serves API + static frontend
#  Railway injects PORT at runtime via environment variable
# ═══════════════════════════════════════════════════════════════════
FROM python:3.12-slim

# ── System dependencies ─────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpq-dev \
        gcc \
        curl \
    && rm -rf /var/lib/apt/lists/*

# ── Working directory ───────────────────────────────────────────
WORKDIR /app

# ── Python dependencies (cached layer) ─────────────────────────
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# ── Copy application source ─────────────────────────────────────
COPY backend/ /app/backend/
COPY frontend/ /app/frontend/

# ── Non-root user for security ──────────────────────────────────
RUN useradd -m -u 1000 appuser \
    && mkdir -p /tmp/ai_models \
    && chown -R appuser:appuser /app /tmp/ai_models
USER appuser

# ── Environment defaults ────────────────────────────────────────
ENV FLASK_ENV=production \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app/backend \
    MODEL_DIR=/tmp/ai_models \
    PORT=8000

EXPOSE 8000

# ── Working dir for gunicorn ────────────────────────────────────
WORKDIR /app/backend

# ── Start command — shell form so $PORT expands at runtime ──────
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "wsgi:application"]
