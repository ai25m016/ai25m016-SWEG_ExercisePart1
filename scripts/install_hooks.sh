#!/bin/sh
set -e

REPO_ROOT="$(git rev-parse --show-toplevel)"
HOOKS_SRC="$REPO_ROOT/hooks"
GIT_DIR="$(git rev-parse --git-dir)"
HOOKS_DST="$GIT_DIR/hooks"

echo "Installing Git hooks from $HOOKS_SRC to $HOOKS_DST"

mkdir -p "$HOOKS_DST"

for hook in commit-msg pre-push; do
  if [ -f "$HOOKS_SRC/$hook" ]; then
    cp "$HOOKS_SRC/$hook" "$HOOKS_DST/$hook"
    chmod +x "$HOOKS_DST/$hook"
    echo "  -> installed $hook"
  fi
done

echo "✅ Hooks installiert."
