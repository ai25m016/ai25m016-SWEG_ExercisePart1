# Simple Social – Mini Social REST API

Eine kompakte Beispielanwendung mit FastAPI, SQLModel, SQLite, Tests und GitHub Actions.
Ziel: Drei Posts speichern und den neuesten Post per API abrufen.

---

## ✅ Features
🚀 Features

- CRUD-ähnliche API (Create + Get latest)
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
py -m uv run social-api
```

Server läuft dann unter:

* Swagger UI: http://127.0.0.1:8000/docs
* ReDoc: http://127.0.0.1:8000/redoc
* OpenAPI Spec: http://127.0.0.1:8000/openapi.json


## 📡 API Endpoints
### POST /posts

Erstellt einen neuen Post.

#### Beispiel-JSON:
```
{
  "image": "images/cat.png",
  "text": "Süße Katze!",
  "user": "alice"
}
```

#### Beispiel-Call via curl:
```
curl -X POST http://127.0.0.1:8000/posts \
  -H "Content-Type: application/json" \
  -d "{\"image\":\"images/cat.png\", \"text\":\"Süße Katze!\", \"user\":\"alice\"}"
```
### GET /posts/latest

Gibt den zuletzt gespeicherten Post zurück.
```
curl http://127.0.0.1:8000/posts/latest
```

## 🌱 Seed Script

Demo-Daten in die Datenbank schreiben:
```
m uv run social-seed
```
Es werden drei Beispiel-Posts eingefügt.

## 🧪 Tests ausführen
```
py -m uv run pytest -q
```

- Erzeugt temporäre SQLite-Testdatenbank

- Löscht alle Testdaten nach Laufende

- Keine Konflikte mit deiner echten social.db

## 🗂️ Projektstruktur
```
simple_social/
│
├── src/simple_social/
│   ├── api.py          # FastAPI Endpoints
│   ├── db.py           # SQLModel DB-Anbindung
│   ├── models.py       # Post SQLModel Klasse
│   ├── cli.py          # Seed-Script
│   └── __init__.py
│
├── tests/
│   ├── test_api.py     # API Tests
│   └── conftest.py
│
├── pyproject.toml      # Dependencies & Script entrypoints
└── README.md
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