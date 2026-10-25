# One image, one process: the API and the Discord bot. Configuration comes only from environment
# variables; the database lives on a volume mounted at /data. Behind Caddy (deploy/), which
# terminates TLS and forwards the client address.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.28 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencies first so code changes do not reinstall them.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

# /data is owned by the app user before it becomes a volume, so a fresh named volume inherits that
# ownership and the process never needs root.
RUN useradd --system --uid 10001 --user-group --no-create-home crewbie \
    && mkdir /data && chown crewbie:crewbie /data

ENV CREWBIE_ENV=prod \
    CREWBIE_HOST=0.0.0.0 \
    CREWBIE_PORT=8000 \
    CREWBIE_TRUST_PROXY=true \
    CREWBIE_DATABASE_URL=sqlite:////data/crewbie.db

VOLUME /data
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,sys,urllib.request as u; port=os.environ.get('PORT') or os.environ.get('CREWBIE_PORT','8000'); sys.exit(0 if u.urlopen(f'http://127.0.0.1:{port}/healthz', timeout=4).status == 200 else 1)"

USER crewbie
CMD ["python", "-m", "crewbie"]
