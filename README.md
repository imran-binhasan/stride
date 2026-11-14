# Stride

A3Zen’s project and time-management application: a FastAPI backend, React/Vite web app, and a separate Tauri desktop companion.

The **core team workflow is implemented and locally validated**. See [scope, validation, and remaining deployment checks](docs/CORE_WORKFLOW_STATUS.md). The full enterprise specification and native tracker are separate work.

## Run locally

Backend:

```bash
cd backend
uv sync --extra dev
uv run --extra dev uvicorn src.main:app --reload --port 8000
```

Without a `.env`, the API defaults to SQLite. Development Redis fallback requires the development dependencies above. Use [backend/.env.example](backend/.env.example) for Postgres, storage, and integration configuration.

Web app, in another terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`. Register an organization, then create a project in Workspace settings. API documentation is at `http://localhost:8000/docs` when debug mode is enabled.

## Checks

```bash
cd backend
uv run --extra dev pytest
uv run --extra dev ruff check src tests
```

```bash
cd frontend
npm run build
npm test
```

## Deployment and specifications

The [Compose stack](backend/docker-compose.yml) provisions Postgres, Redis, private object storage, migrations, and the API. Set the required secrets in `.env` before running it. The object-storage public endpoint must be reachable from the browser.

- [Core workflow status](docs/CORE_WORKFLOW_STATUS.md)
- [Full product specification](docs/SRS.md)
- [Architecture](docs/ARCHITECTURE.md)
