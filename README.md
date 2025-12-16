# 🌐 Simple Social – Fullstack Demo

FastAPI + Frontend + Docker + Playwright + GitHub Actions + Orchestrierung

Ein modernes Fullstack-Projekt zur Demonstration von REST-API-Entwicklung, Containerisierung, automatisierten Tests, Multi-Service-Orchestrierung und CI/CD-Pipelines.

## 🚀 Features

### 🧠 Backend (FastAPI)
- SQLModel + SQLite
- CRUD-Endpunkte
- Seed-Script (social-seed)
- Automatische OpenAPI-Dokumentation
→ /docs, /redoc

### 🎨 Frontend
- Einfaches HTML/JS-Frontend
- End-to-End Tests mit Playwright

### 🧪 Testing
- Backend Tests (pytest)
- Frontend E2E Tests (Playwright)
- Docker-basierte Test-Pipelines
- Server-Orchestration Tests (Backend + Frontend + DB)

🐳 Docker & Orchestrierung
- Backend-Image
- Frontend-Image
- Lokale Entwicklung (Backend + Frontend)
- Vollständige Orchestrierung (Backend + Frontend + Postgres)
- Persistente Volumes

### ⚙️ GitHub Actions
- 8 vollständige CI/CD Workflows:
  - Backend Tests (ohne Docker)
  - Backend Tests (Docker)
  - Backend Release Image
  - Frontend Tests (ohne Docker)
  - Frontend Tests (Docker)
  - Frontend Release Image
  - Branch + Issue Validation
  - Issue → Branch Automation

### 🔐 Git Hooks
- Commit Message Validator
- Branch Name Validator
- Integration mit Test-Skripten

## 🛠️ Installation
### 🔧 Backend installieren
```
py -m uv sync
```

### 🎭 Frontend installieren
```
cd frontend
npm install
npx playwright install
```

## 🧩 Lokaler Betrieb
### 🧩 RabbitMQ starten (Docker)
```
docker run --rm -it --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```
#### 📍 Web UI: 
- http://localhost:15672 (guest/guest)

### 🧩 Image-Resizer starten (lokal per Python)
```
.\.venv\Scripts\activate
social-resizer
```


### 🧩 Backend starten
```
cd backend
$env:RABBITMQ_HOST="127.0.0.1"
$env:IMAGE_RESIZE_QUEUE="image_resize"
py -m uv run social-api
```

### 📍 API läuft:
- http://localhost:8000
- http://localhost:8000/docs
- http://localhost:8000/redoc


## 🧪 Backend testen
```
cd backend
py -m uv run pytest -q
```

## 🎭 Frontend E2E Tests
```
cd frontend
npx playwright test
```


## 🐳 Betrieb mit Docker


### 🐳 Docker Compose lokales Image

### 🐳 Docker Compose Github Image



### 🧪 Backend testen
```
cd backend
py -m uv run pytest -q
```

### 🎭 Frontend E2E Tests
```
cd frontend
npx playwright test
```


Startet:
| Service  | Port |
| -------- | ---  |
| Backend  | 8000 |
| Frontend | 5500 |







Services:
| Service  | Port | Beschreibung          |
| -------- | ---- | --------------------- |
| Backend  | 8000 | FastAPI               |
| Frontend | 5500 | Nginx Static Frontend |
| Postgres | 5432 | Persistente Datenbank (`social_db_data`)|




## 🧪 Orchestrierte Tests (Backend + Frontend + DB)

Alle Testskripte befinden sich unter `scripts/run_tests.sh`.

### Backend in Orchestrierung testen
```
./scripts/run_tests.sh backend-orch
```

### Frontend in Orchestrierung testen
```
./scripts/run_tests.sh frontend-orch
```

### Alle Tests (lokal, Docker, Orchestrierung)
```
./scripts/run_tests.sh all
```

Dies führt in Reihenfolge aus:
1. Backend lokal
2. Frontend lokal
3. Backend im Docker-Image
4. Frontend im Docker-Image
5. Backend orchestration
6. Frontend orchestration

Damit wird garantiert, dass das System **immer** konsistent funktioniert.

## 🌱 Seed Script

Testdaten einfügen:
```
py -m uv run social-seed
```

Erzeugt drei Beispiel-Posts.


# 📁 Projektstruktur
```
simple_social/
├── backend/
│   ├── src/simple_social_backend/
│   ├── tests/test_api.py
│   ├── main.py
│   ├── social.db
│   ├── pyproject.toml
│   └── uv.lock
│
├── frontend/
│   ├── index.html
│   ├── tests/posts.spec.js
│   ├── package.json
│   └── node_modules/
│
├── .github/workflows/
│   ├── backend-tests.yml
│   ├── backend-docker.yml
│   ├── backend-release.yml
│   ├── backend-orch.yml
│   ├── frontend-tests.yml
│   ├── frontend-docker.yml
│   ├── frontend-release.yml
│   ├── frontend-orch.yml
│   ├── validate-branch-issue.yml
│   └── create-issue-branch.yml
│
├── hooks/commit-msg
├── scripts/install_hooks.sh
├── .env
├── docker-compose.local.yml
├── docker-compose.orch.local.yml
├── docker-compose.orch.yml
├── docker-compose.yml
└── README.md
```

## 🤖 GitHub Actions – Übersicht
### 🧪 Backend Tests (no Docker)

→ `backend-tests.yml`
Läuft bei Push + PR auf:
`feature/*`, `bugfix/*`, `hotfix/*`, `docs/*`, `release/*`, `develop`, `main`

### 🐳🧪 Backend Tests (Docker)
→ `backend-docker.yml`
- Baut Image
- Führt pytest im Container aus
- Optional: push von Docker Images

### 🚀 Backend Release
→ `backend-release.yml`
- läuft nur bei Tags:
  - `vX.Y.Z`
  - `vX.Y.Z-rcN`

- pushed nach GHCR:
  - `simple-social-backend:<tag>`
  - `:latest` bei final Release


### 🎭 Frontend Tests (no Docker)
→ `frontend-tests.yml`

### 🎭🐳 Frontend Tests (Docker)
→ `frontend-docker.yml`

### 🚀 Frontend Release
→ `frontend-release.yml`

Pusht Image nach GHCR.

### 🕵️ Branch & Commit Validator
→ `validate-branch-and-issue.yml`

Prüft:
- Branch Format
- Commit Message enthält Issue-Nummer
- Keine Pflicht für Releases


### 🧵 Issue → Branch Automation
→ `create-issue-branch.yml`
Erzeugt automatisch:
```
feature/<ISSUE>-kürzer-titel
```


🧭 Branch-Namenskonventionen

|    Typ  |          Muster	             |      Beispiel         |
| :------ | :--------------------------: | --------------------: |
| Feature | feature/<ISSUE>-beschreibung | feature/12-login-form |
| Bugfix  | bugfix/<ISSUE>-beschreibung  | bugfix/7-null-bug     |
| Hotfix  | hotfix/<ISSUE>-beschreibung  | hotfix/3-prod-crash   |
| Docs    | docs/<ISSUE>-beschreibung    | docs/5-update-readme  |
| Release | release/X.Y.Z(-rcN)          | release/3.0.0-rc1     |

❗ Releases dürfen keine Issue-Nummer enthalten.



## ✍️ Commit-Message-Regeln
### Auf feature/bugfix/hotfix/docs:
✔ Erste Zeile MUSS die Issue-Nummer enthalten:
```
Login-Button hinzugefügt (#12)
```
### Auf release/X.Y.Z:

✔ Keine Issue-Pflicht:
```
Release 3.0.0 vorbereitet
```
### 🔧 Git Hooks

Setup:
```
./scripts/install_hooks.sh
```
### 🔧 Git Hooks

Konfiguration:
```
git config --local hook.tests backend
git config --local hook.tests backend-docker
git config --local hook.tests backend-orch
git config --local hook.tests frontend
git config --local hook.tests frontend-docker
git config --local hook.tests frontend-orch
git config --local hook.tests all
git config --local hook.tests none
```