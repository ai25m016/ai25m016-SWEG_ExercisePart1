# 🌐 Simple Social – Fullstack Demo

FastAPI + Frontend + Docker Compose + Playwright + GitHub Actions

Ein modernes Fullstack-Projekt zur Demonstration von REST-API-Entwicklung, Containerisierung, automatisierten Tests, Multi-Service-Orchestrierung und CI/CD.

## 🚀 Features

### 🧠 Backend (FastAPI)
- SQLModel + **Postgres (SQLite ist deaktiviert)**
- CRUD-Endpunkte
- Seed-Script (`social-seed`)
- OpenAPI-Doku: `/docs`, `/redoc`
- Queue-Integration (RabbitMQ) für:
  - Image-Resizing (Worker)
  - Text-Generation (Worker)
- Sentiment-Analyse via HTTP-Service

### 🎨 Frontend
- Einfaches HTML/JS-Frontend (Nginx Container)
- End-to-End Tests mit Playwright

### 🧪 Testing
- Backend Tests (pytest) mit Markern:
  - `api`, `persistence`, `resizer`, `textgen`, `sentiment`
- Frontend E2E Tests (Playwright)
- Docker-basierte E2E/Orchestrierungs-Tests (über Compose)

## 🛠️ Installation (lokale Entwicklung ohne Docker)
Hinweis: Das Backend braucht immer eine Postgres-DB. Am einfachsten ist Docker Compose (siehe Quickstart).

### Backend Dependencies (uv)
```
cd backend
python -m pip install -U pip
pip install uv
uv sync --all-extras --dev
```



### Frontend Dependencies
```
cd frontend
npm install
npx playwright install
```


### ✅ Quickstart (empfohlen): Alles mit Docker Compose starten
Start im Repo-Root:
```
docker compose -f docker-compose.local.yml up -d --build
```
Stop:
```
docker compose -f docker-compose.local.yml down
```
Stop inkl. Volumes/Daten löschen:
```
docker compose -f docker-compose.local.yml down -v
```


Danach laufen typischerweise:
- Backend: http://localhost:8000 (Docs: http://localhost:8000/docs)
- Frontend: http://localhost:5500
- Postgres: localhost:5432
- RabbitMQ: localhost:5672 (UI: http://localhost:15672)
- Sentiment Service: http://localhost:8001


## 🌱 Seed Script

Seed in die laufende DB (z. B. wenn Compose läuft):
```
cd backend
uv run social-seed
```


## 🧪 Backend Tests (pytest)

Empfehlung: Backend-Tests ausführen, nachdem Docker verfügbar ist (die Tests starten Postgres/Services je nach Marker).
```
cd backend
uv run pytest -m api -q
uv run pytest -m persistence -q -s
uv run pytest -m resizer -q -s
uv run pytest -m textgen -q -s
uv run pytest -m sentiment -q -s
```
Hinweis:
- `api` nutzt TestClient + Docker-Postgres (kein SQLite).
- `resizer`/`persistence` starten benötigte Services via Compose.


## 🎭 Frontend E2E Tests (Playwright)
```
cd frontend
npx playwright test
```


## 🤖 GitHub Actions – was wirklich im Repo ist
Workflows unter `.github/workflows/`:
- `backend-tests.yml` (Jobs: api, persistence, resizer, textgen, sentiment)
- `backend-release.yml`
- `frontend-release.yml`
- `validate-branch-issue.yml`
- `create-issue-branch.yml`

## 🔐 Git Hooks

Vorhanden im Repo:
- `hooks/commit-msg`
- `hooks/pre-push`

Setup:
```
./scripts/install_hooks.sh
```

## 📁 Projektstruktur (gekürzt)
- `backend/` (FastAPI + pytest + uv)
- `frontend/` (Static + Playwright)
- `image_resizer/` (Worker)
- `ml_worker/` (Worker)
- `sentiment_analysis/` (Service)
- `docker-compose.local.yml` (lokaler Build-Stack)
- `docker-compose.yml` (GHCR Images + Tags)
- .github/workflows/ (CI)