# syntax=docker/dockerfile:1
# Pin the multi-platform manifests used by the verified build.
FROM node:22-bookworm-slim@sha256:e9f565d32859f0cbfb52125eafe8be39390f24dac302dc3cdf566e8ba3ab21ee AS frontend-deps
WORKDIR /src/frontend
ENV CI=true
# Bootstrap the repository's pinned pnpm without an implicit Corepack download.
# npm and pnpm retain their normal TLS and package-integrity verification.
RUN --mount=type=cache,id=voxprep-npm,target=/root/.npm,sharing=locked \
    npm install --global pnpm@11.25.0 --ignore-scripts --no-audit --no-fund \
      --fetch-retries=5 --fetch-timeout=120000
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN node -e 'if (require("./package.json").packageManager !== "pnpm@11.25.0") throw new Error("Update the Docker pnpm pin to match package.json")'
RUN --mount=type=cache,id=voxprep-pnpm,target=/pnpm/store,sharing=locked \
    pnpm install --frozen-lockfile --prefer-offline --store-dir=/pnpm/store \
      --network-concurrency=4 --fetch-retries=5 --fetch-timeout=120000 \
      --fetch-retry-mintimeout=10000 --fetch-retry-maxtimeout=60000

FROM frontend-deps AS frontend
COPY frontend/ ./
RUN pnpm build

FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS python-deps
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_DEFAULT_TIMEOUT=120 PIP_RETRIES=5
COPY requirements.lock ./requirements.lock
RUN --mount=type=cache,id=voxprep-pip,target=/root/.cache/pip,sharing=locked \
    pip install --prefer-binary -r requirements.lock

FROM python-deps AS runtime
# Run the source package directly; no unpinned build backend is downloaded.
ENV PYTHONPATH=/app/backend
COPY backend/ ./backend/
COPY knowledge/ ./knowledge/
COPY evaluation/results/ ./evaluation/results/
COPY --from=frontend /src/frontend/dist ./frontend/dist/
RUN useradd --create-home voxprep && mkdir data && chown -R voxprep:voxprep /app
USER voxprep
EXPOSE 8000
CMD ["sh", "-c", "alembic -c backend/alembic.ini upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]
