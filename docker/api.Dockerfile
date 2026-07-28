# =============================================================================
# LuoBlog Studio — API Dockerfile (multi-stage)
# =============================================================================

# --- Development Stage ---
FROM python:3.11-slim AS development

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System dependencies for PDF parsing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY apps/api/pyproject.toml .
RUN pip install --upgrade pip && \
    pip install -e ".[dev]"

COPY apps/api/src ./src
COPY agents /agents

EXPOSE 8000
CMD ["uvicorn", "src.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--reload"]


# --- Production Stage ---
FROM python:3.11-slim AS production

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

COPY apps/api/pyproject.toml .
RUN pip install --upgrade pip && pip install -e "."

COPY apps/api/src ./src
COPY agents /agents

EXPOSE 8000
CMD ["uvicorn", "src.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
