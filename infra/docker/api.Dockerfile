FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PORT=8000 PYTHONPATH=/app/apps/api:/app/apps/mcp
WORKDIR /app
COPY pyproject.toml requirements.lock ./
COPY alembic.ini ./
COPY apps/api ./apps/api
COPY apps/mcp ./apps/mcp
COPY data ./data
COPY artifacts ./artifacts
COPY scripts ./scripts
RUN pip install --no-cache-dir -c requirements.lock . && useradd --create-home --uid 10001 creditops && chown -R creditops:creditops /app
USER creditops
EXPOSE 8000
CMD ["sh", "-c", "python -m alembic upgrade head && exec python -m uvicorn creditops.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
