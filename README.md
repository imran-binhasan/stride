# A3Zen — Product Suite

Welcome to **A3Zen**. This repository hosts the core products and platforms engineered by A3Zen.

---

## Products

### 🚀 Stride (Project Management & Workforce Intelligence SaaS)
**Stride** is an all-in-one agile project management and workforce intelligence platform merging Linear/ClickUp-grade agile issue tracking, real-time collaboration, Gantt Critical Path calculations, and desktop activity/screenshot monitoring.

#### Directory Layout
```
a3zen/
└── stride/
    ├── backend/     # Python 3.12+ / FastAPI / Async SQLAlchemy 2.0 / Redis / Pytest (~92% coverage)
    ├── frontend/    # React / Next.js / Tailwind CSS / Kanban & Gantt Web App
    ├── desktop/     # Tauri 2.0 (Rust Core + React UI) Lightweight Desktop Companion Tracker
    └── docs/        # SRS, 5-Gate AI Loop Engineering, and System Architecture specifications
```

---

## Quickstart (Backend API)

```bash
cd stride/backend
uv sync --extra dev
uv run uvicorn src.main:app --reload --port 8000
```
* **Interactive API Swagger Docs:** `http://localhost:8000/docs`
* **Run Test Suite:** `uv run pytest -v`
