# Slim image for hosted deployment (Fly.io / Render / Cloudflare-via-Workers-proxy).
FROM python:3.12-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --prefix=/install .

# ---- runtime ---- #
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HEVY_MCP_HOST=0.0.0.0 \
    HEVY_MCP_PORT=8000

COPY --from=builder /install /usr/local
WORKDIR /app

# Non-root for safety.
RUN useradd -m -u 1001 hevy
USER hevy

EXPOSE 8000
ENTRYPOINT ["hevy-mcp", "--http"]
