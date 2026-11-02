FROM node:22-bookworm-slim AS frontend
WORKDIR /src/frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN corepack pnpm install --frozen-lockfile
COPY frontend/ ./
RUN corepack pnpm build

FROM python:3.12-slim AS runtime
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY backend/ ./backend/
COPY requirements.lock ./requirements.lock
RUN pip install --no-cache-dir -r requirements.lock && pip install --no-cache-dir --no-deps ./backend
COPY knowledge/ ./knowledge/
COPY evaluation/results/ ./evaluation/results/
COPY --from=frontend /src/frontend/dist ./frontend/dist/
RUN useradd --create-home voxprep && mkdir data && chown -R voxprep:voxprep /app
USER voxprep
EXPOSE 8000
CMD ["sh", "-c", "alembic -c backend/alembic.ini upgrade head && uvicorn backend.app.main:app --host 0.0.0.0 --port 8000"]
