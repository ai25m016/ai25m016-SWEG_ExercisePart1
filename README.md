# 🌐 Simple Social – Fullstack Demo

FastAPI + Frontend + Docker Compose + Playwright + GitHub Actions

Ein modernes Fullstack-Projekt zur Demonstration von REST-API-Entwicklung, Containerisierung, automatisierten Tests, Multi-Service-Orchestrierung und CI/CD.

## 🚀 Features

### 🧠 Backend (FastAPI)
- SQLModel + **Postgres**
- CRUD-Endpunkte
- Seed-Script (`social-seed`)
- OpenAPI-Doku: `/docs`, `/redoc`
- Queue-Integration (RabbitMQ) für:
  - Image-Resizing (Worker)
  - Text-Generation (Worker)
- Sentiment-Analyse via RabbitMQ RPC

### 🎨 Frontend
- Einfaches HTML/JS-Frontend (Nginx Container)
- End-to-End Tests mit Playwright

### 🧪 Testing
- Backend Tests (pytest) mit Markern:
  - `api`, `persistence`, `resizer`, `textgen`, `sentiment`
- Frontend E2E Tests (Playwright)
- Docker-basierte Integrationstests (Compose)

## 🛠️ Installation
Hinweis: Das Backend braucht immer eine Postgres-DB.
Für Quickstart & Integrationstests wird Docker benötigt.

### Backend Dependencies
```
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -U pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
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
docker compose up -d --build
```
Stop:
```
docker compose down
```
Stop inkl. Volumes/Daten löschen:
```
docker compose down -v
```


Danach laufen typischerweise:
- Backend: http://localhost:8000 (Docs: http://localhost:8000/docs)
- Frontend: http://localhost:5500
- Postgres: localhost:5432
- RabbitMQ: localhost:5672 (UI: http://localhost:15672)
- Sentiment Service: http://localhost:8001


## 🧪 Backend Tests (pytest)

Empfehlung: Backend-Tests ausführen, nachdem Docker verfügbar ist (die Tests starten Postgres/Services je nach Marker).
```
pytest -m api -q
pytest -m persistence -q
pytest -m resizer -q
pytest -m textgen -q
pytest -m sentiment -q
```

## 🎭 Frontend E2E Tests (Playwright)
```
cd frontend
npx playwright test
```


## 🤖 GitHub Actions – was wirklich im Repo ist
Workflows unter `.github/workflows/`:
- `backend-tests.yml` (Matrix: suite = api|persistence|resizer|textgen|sentiment)
- `release-image.yml`
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
- `text_gen/` (Worker)
- `sentiment_analysis/` (Service)
- `docker-compose.yml` (lokaler Build-Stack)
- `docker-compose.github.yml` (GHCR Images + Tags)
- .github/workflows/ (CI)