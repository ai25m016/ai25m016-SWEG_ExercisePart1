#!/usr/bin/env bash
set -e

echo "== Git Clean-History Setup =="

# 1) git pull soll standardmäßig rebasen
git config --global pull.rebase true
echo "Set: git pull => rebase (pull.rebase=true)"

# 2) Nur Fast-Forward-Merges, wenn möglich (keine unnötigen Merge-Commits)
git config --global merge.ff only
echo "Set: merge.ff=only (nur Fast-Forward)"

# 3) Alias: 'git up' = git pull --rebase --autostash
git config --global alias.up "pull --rebase --autostash"
echo "Alias: git up"

# 4) Alias: 'git rbdev' = auf origin/develop rebasen
git config --global alias.rbdev "!git fetch origin && git rebase origin/develop"
echo "Alias: git rbdev"

echo
echo "Fertige Einstellungen:"
git config --global --get pull.rebase
git config --global --get merge.ff
git config --global --get alias.up
git config --global --get alias.rbdev

echo
echo "Done. Dein Git ist jetzt auf Rebase/Fast-Forward + Aliases eingestellt. 🙂"
