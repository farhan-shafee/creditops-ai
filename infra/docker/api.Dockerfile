FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 PYTHONPATH=/app/apps/api:/app/apps/mcp
ENV PUBLIC_DEMO=true EMBEDDINGS_ENABLED=false TELEMETRY_MODE=persisted CREDITOPS_ENV_FILE="" REPLAY_DIR=/app/data/showcase
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY alembic.ini ./
COPY apps/api ./apps/api
COPY apps/mcp ./apps/mcp
COPY data ./data
COPY artifacts/eval ./artifacts/eval
COPY artifacts/robustness ./artifacts/robustness
COPY scripts ./scripts
RUN python -m pip install --no-cache-dir -c requirements.lock pip \
    && python -m pip install --no-cache-dir -c requirements.lock . \
    && python -c "import importlib.metadata as m; assert m.version('pip') == '26.2.2'" \
    && useradd --create-home --uid 10001 creditops \
    && chown -R creditops:creditops /app
USER creditops
EXPOSE 8000
CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn creditops.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
