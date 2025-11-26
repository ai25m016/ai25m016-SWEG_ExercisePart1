# Simple Social – Mini Social REST API

Eine kompakte Beispielanwendung mit FastAPI, SQLModel, SQLite, Tests und GitHub Actions.
Ziel: Drei Posts speichern und den neuesten Post per API abrufen.

---

## ✅ Features
🚀 Features

- CRUD API (Create + Get latest)
- FastAPI + SQLModel + SQLite
- Seed-Script (social-seed) zum Befüllen der DB
- Tests mit pytest
- GitHub Actions Workflow für Pull-Request-Tests
- Automatisch generierte Swagger-UI & ReDoc
- Reproduzierbare Python-Umgebung mit uv

---

## 📦 Installation

### Projekt-Abhängigkeiten installieren:
```
py -m uv sync
```

## ▶️ API starten

```
cd backend
py -m uv run social-api
```

Server läuft dann unter:

* Swagger UI: http://127.0.0.1:8000/docs
* ReDoc: http://127.0.0.1:8000/redoc
* OpenAPI Spec: http://127.0.0.1:8000/openapi.json

## Frontend starten

```
python -m http.server 5500
```

* Frontend Weboberfläche: http://127.0.0.1:5500

## 🌱 Seed Script

Demo-Daten in die Datenbank schreiben:
```
m uv run social-seed
```
Es werden drei Beispiel-Posts eingefügt.

## 🧪 Tests ausführen
### Backend
```
py -m uv run pytest -q
```

- Erzeugt temporäre SQLite-Testdatenbank

- Löscht alle Testdaten nach Laufende

- Keine Konflikte mit deiner echten social.db

### Frontend
```
npx playwright test
```

- Führt alle Playwright tests aus, die im Projekt gefunden werden

- Führt die Tests in einem headless Browser aus

## 🗂️ Projektstruktur
```
simple_social/
.
├── backend
│   ├── main.py
│   ├── pyproject.toml
│   ├── social.db
│   ├── src
│   │   └── simple_social_backend
│   ├── tests
│   │   └── test_api.py
│   └── uv.lock
├── frontend
│   ├── index.html
│   ├── node_modules
│   │   ├── @playwright
│   │   ├── playwright
│   │   └── playwright-core
│   ├── package-lock.json
│   ├── package.json
│   ├── test-results
│   └── tests
│       └── posts.spec.js
├── hooks
│   └── commit-msg
├── README.md
└── scripts
    └── install_hooks.sh
```

## 🤖 GitHub Actions

Tests werden automatisch ausgeführt, sobald ein Pull Request erstellt wird.

Workflow: ```.github/workflows/tests.yml```

Er macht:

1. Code auschecken

2. Python installieren

3. uv installieren

4. Dependencies synchronisieren

5. ```pytest``` ausführen

## 🧠 Technologien

* FastAPI

* SQLModel

* SQLite

* Pytest

* uv (Package/Env Manager)

* Uvicorn

* GitHub Actions

## 🔧 Nützliche Entwicklertools

Python-Shell im Projektkontext:
```
py -m uv run python
```

Neu synchronisieren (alles neu installieren):
```
py -m uv sync --clean
```

# Git Hooks

Dieses Repository verwendet einen Git-Hook, um sicherzustellen, dass Commit-Messages zu Feature-/Bugfix-/Hotfix-/Release-Branches immer die passende Issue-Nummer enthalten.

### Branch-Namenskonvention

Der Hook greift nur auf Branches, die diesem Schema folgen:

- `feature/<ISSUE>-beschreibung`
- `bugfix/<ISSUE>-beschreibung`
- `hotfix/<ISSUE>-beschreibung`
- `release/<ISSUE>-beschreibung`

Beispiele:

- `feature/12-neue-login-maske`
- `bugfix/34-nullpointer-beim-start`
- `hotfix/7-falscher-text-im-banner`
- `release/5-version-1-2-0`

Die Issue-Nummer ist immer die Zahl direkt nach dem `/`, also z. B. `12` in `feature/12-neue-login-maske`.

### Commit-Message-Konvention

Wenn du auf einem dieser Branches committest, **muss** die erste Zeile der Commit-Message die Issue-Nummer in der Form `#<ISSUE>` enthalten.

Beispiel für eine gültige Commit-Message auf Branch `feature/12-neue-login-maske`:

