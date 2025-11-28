#!/usr/bin/env bash
set -e

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

  all)
    echo "== Backend-Tests (ohne Docker) =="
    "$0" backend

    echo
    echo "== Backend-Tests (mit Docker) =="
    "$0" backend-docker
    ;;

  none)
    echo "Tests übersprungen (SCOPE=none)"
    ;;

  *)
    echo "Unbekannter Test-Scope: '$SCOPE'"
    echo "Erwartet: backend | backend-docker | all | none"
    exit 1
    ;;
esac
