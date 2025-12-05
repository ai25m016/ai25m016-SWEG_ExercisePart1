#!/usr/bin/env bash
set -eu

# Usage:
#   ./scripts/test_persistence.sh docker-compose.orch.local.yml         # Backend Persistenz-Test (docker-compose.orch.local.yml)
#   ./scripts/test_persistence.sh docker-compose.orch.yml               # Backend Persistenz-Test (docker-compose.orch.yml)


COMPOSE_FILE="${1:-docker-compose.orch.yml}"

echo "== Persistenz-Test mit ${COMPOSE_FILE} =="

MARKER="persist-test-$(date +%s)"

cleanup() {
  echo "→ Aufräumen (Stack + Volumes löschen)..."
  docker compose -f "$COMPOSE_FILE" down -v >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "→ Starte Stack (db + backend)..."
docker compose -f "$COMPOSE_FILE" up -d --build db backend

echo "→ Warte auf Backend (http://127.0.0.1:8000/docs)..."
for i in {1..40}; do
  if curl -sSf http://127.0.0.1:8000/docs >/dev/null 2>&1; then
    echo "   Backend ist bereit."
    break
  fi
  echo "   Backend noch nicht bereit, Versuch $i..."
  sleep 2
done

echo "→ Lege Test-Post mit Marker '${MARKER}' an..."
curl -sSf -X POST "http://127.0.0.1:8000/posts" \
  -H "Content-Type: application/json" \
  -d "{\"image\": \"persist.png\", \"text\": \"${MARKER}\", \"user\": \"persist_user\"}" >/dev/null

echo "→ Stoppe Stack (ohne -v, Volume bleibt bestehen)..."
docker compose -f "$COMPOSE_FILE" down

echo "→ Starte Stack erneut (db + backend)..."
docker compose -f "$COMPOSE_FILE" up -d db backend

echo "→ Warte erneut auf Backend..."
for i in {1..40}; do
  if curl -sSf http://127.0.0.1:8000/docs >/dev/null 2>&1; then
    echo "   Backend ist bereit."
    break
  fi
  echo "   Backend noch nicht bereit, Versuch $i..."
  sleep 2
done

echo "→ Prüfe, ob der Post nach Neustart noch vorhanden ist..."
if curl -sS "http://127.0.0.1:8000/posts" | grep -q "${MARKER}"; then
  echo "✅ Persistenz OK – Post mit Marker '${MARKER}' wurde nach Neustart gefunden."
  exit 0
else
  echo "❌ Persistenz FEHLER – Post mit Marker '${MARKER}' wurde nach Neustart NICHT gefunden."
  exit 1
fi
