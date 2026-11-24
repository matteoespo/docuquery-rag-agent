FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install uv

# Install exactly the versions in uv.lock (no dev deps). Dependencies are a
# separate layer so code changes don't reinstall them.
COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-dev --no-install-project

COPY backend ./backend

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/backend
# Run from /app: settings paths (data/chroma_db, data/pdfs) are relative to
# the working directory and docker-compose mounts ./data at /app/data.
EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
