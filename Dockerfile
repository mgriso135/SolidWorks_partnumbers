FROM node:22-alpine AS frontend

WORKDIR /src/frontend
COPY frontend/ ./
RUN rm -rf node_modules dist *.tsbuildinfo \
    && npm ci --include=dev \
    && npm run build

FROM python:3.13-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app/backend

COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./
COPY --from=frontend /src/frontend/dist /app/frontend/dist

RUN useradd --create-home --uid 10001 partcode \
    && chown -R partcode:partcode /app
USER partcode

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"]

CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
