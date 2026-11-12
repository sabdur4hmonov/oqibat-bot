FROM python:3.12-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONUTF8=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --retries 10 --timeout 120 -r requirements.txt \
    && groupadd --gid 10001 oqibat \
    && useradd --uid 10001 --gid 10001 --create-home oqibat

COPY --chown=10001:10001 bot/ ./bot/
COPY --chown=10001:10001 data/ ./data/
COPY --chown=10001:10001 assets/ ./assets/
COPY --chown=10001:10001 alembic/ ./alembic/
COPY --chown=10001:10001 scripts/ ./scripts/
COPY --chown=10001:10001 alembic.ini ./alembic.ini

USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=6s --start-period=120s --retries=3 CMD ["python", "scripts/healthcheck.py"]
CMD ["python", "-m", "bot"]
