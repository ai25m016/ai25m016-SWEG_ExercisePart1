#!/usr/bin/env bash
set -eu

# Usage:
#   ./scripts/run_tests.sh backend          # Backend-Tests ohne Docker
#   ./scripts/run_tests.sh backend-docker   # Backend-Tests im Docker-Image
#   ./scripts/run_tests.sh frontend         # Frontend-E2E ohne Docker
#   ./scripts/run_tests.sh frontend-docker  # Frontend-E2E mit Docker-Image
#   ./scripts/run_tests.sh all              # alles nacheinander
#   ./scripts/run_tests.sh none             # nichts tun

SCOPE="${1:-all}"  # default: all

# UV-Command finden (uv oder py -m uv oder python -m uv)
if command -v uv >/dev/null 2>&1; then
  UV="uv"
elif command -v py >/dev/null 2>&1; then
  UV="py -m uv"
elif command -v python >/dev/null 2>&1; then
  UV="python -m uv"
else
  echo "Fehler: 'uv' wurde nicht gefunden."
  echo "Bitte installiere Python + uv oder füge sie zum PATH hinzu."
  exit 1
fi

case "$SCOPE" in
  backend)
    echo "== Backend-Tests (ohne Docker) =="

    cd backend
    $UV sync --all-extras --dev
    $UV run pytest -q
    ;;

  backend-docker)
    echo "== Backend-Tests (im Docker-Container) =="

    docker build \
      -f backend/Dockerfile \
      -t simple-social-backend:test \
      .

    docker run --rm simple-social-backend:test \
      uv run pytest -q
    ;;

  frontend)
    echo "== Frontend-E2E-Tests (ohne Docker) =="

    BACKEND_PID=""
    FRONTEND_PID=""

    cleanup() {
      if [[ -n "${FRONTEND_PID:-}" ]]; then
        echo "→ Stoppe Frontend-HTTP-Server (PID $FRONTEND_PID)..."
        kill "$FRONTEND_PID" 2>/dev/null || true
      fi
      if [[ -n "${BACKEND_PID:-}" ]]; then
        echo "→ Stoppe Backend (PID $BACKEND_PID)..."
        kill "$BACKEND_PID" 2>/dev/null || true
      fi
    }
    trap cleanup EXIT

    # Backend starten
    (
      cd backend
      $UV sync --all-extras --dev
      $UV run social-api &
      echo $! > ../.backend.pid
    )
    BACKEND_PID="$(cat .backend.pid)"
    rm -f .backend.pid

    echo "Warte auf Backend (http://127.0.0.1:8000/docs)..."
    for i in {1..30}; do
      if curl -sSf http://127.0.0.1:8000/docs >/dev/null 2>&1; then
        echo "Backend ist bereit."
        break
      fi
      echo "Backend noch nicht bereit, Versuch $i..."
      sleep 1
    done

    # Statisches Frontend auf Port 5500 starten
    (
      cd frontend
      python -m http.server 5500 &
      echo $! > ../.frontend.pid
    )
    FRONTEND_PID="$(cat .frontend.pid)"
    rm -f .frontend.pid

    echo "Warte auf Frontend (http://127.0.0.1:5500)..."
    sleep 2

    # Playwright-Tests ausführen
    (
      cd frontend
      npx playwright test
    )
    ;;

  frontend-docker)
    echo "== Frontend-E2E-Tests (mit Docker-Image) =="

    BACKEND_PID=""
    FRONTEND_CONTAINER_NAME="simple-social-frontend-under-test"

    cleanup() {
      if docker ps -a --format '{{.Names}}' | grep -q "^${FRONTEND_CONTAINER_NAME}\$"; then
        echo "→ Stoppe Frontend-Container '${FRONTEND_CONTAINER_NAME}'..."
        docker stop "${FRONTEND_CONTAINER_NAME}" >/dev/null 2>&1 || true
      fi
      if [[ -n "${BACKEND_PID:-}" ]]; then
        echo "→ Stoppe Backend (PID $BACKEND_PID)..."
        kill "$BACKEND_PID" 2>/dev/null || true
      fi
    }
    trap cleanup EXIT

    # Backend starten
    (
      cd backend
      $UV sync --all-extras --dev
      $UV run social-api &
      echo $! > ../.backend.pid
    )
    BACKEND_PID="$(cat .backend.pid)"
    rm -f .backend.pid

    echo "Warte auf Backend (http://127.0.0.1:8000/docs)..."
    for i in {1..30}; do
      if curl -sSf http://127.0.0.1:8000/docs >/dev/null 2>&1; then
        echo "Backend ist bereit."
        break
      fi
      echo "Backend noch nicht bereit, Versuch $i..."
      sleep 1
    done

    # Frontend-Dockerimage bauen
    echo "Baue Frontend-Dockerimage..."
    docker build \
      -f frontend/Dockerfile \
      -t simple-social-frontend:test \
      ./frontend

    # Container starten (nginx auf Port 80 → Host-Port 5500)
    echo "Starte Frontend-Container auf Port 5500..."
    docker run -d --rm -p 5500:80 --name "${FRONTEND_CONTAINER_NAME}" simple-social-frontend:test

    echo "Warte auf Frontend (http://127.0.0.1:5500)..."
    for i in {1..30}; do
      if curl -sSf http://127.0.0.1:5500 >/dev/null 2>&1; then
        echo "Frontend ist bereit."
        break
      fi
      echo "Frontend noch nicht bereit, Versuch $i..."
      sleep 1
    done

    # Playwright-Tests ausführen
    (
      cd frontend
      npx playwright test
    )
    ;;

  all)
    echo "== Backend-Tests (ohne Docker) =="
    "$0" backend

    echo
    echo "== Frontend-E2E-Tests (ohne Docker) =="
    "$0" frontend

    echo
    echo "== Backend-Tests (mit Docker) =="
    "$0" backend-docker

    echo
    echo "== Frontend-E2E-Tests (mit Docker) =="
    "$0" frontend-docker
    ;;

  none)
    echo "Tests übersprungen (SCOPE=none)"
    ;;

  *)
    echo "Unbekannter Test-Scope: '$SCOPE'"
    echo "Erwartet: backend | backend-docker | frontend | frontend-docker | all | none"
    exit 1
    ;;
esac
