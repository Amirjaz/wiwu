#!/usr/bin/env bash
# Deploys the committed main branch to the server. From the repo root (Git Bash on Windows works):
#   DOMAIN=<host> bash deploy/deploy.sh
# The code goes to a bare repo on the server over SSH (no GitHub access needed there); the
# frontend is built here, since the server has no Node (and npm is unreliable from Iran).
set -euo pipefail

SERVER=${SERVER:-amir@185.231.180.92}
DOMAIN=${DOMAIN:?set DOMAIN, the site host name (only used on the first deploy, for .env)}
ROOT=/srv/purseshop

cd "$(git rev-parse --show-toplevel)"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "Uncommitted changes; commit them first so the server runs exactly what is in git." >&2
  exit 1
fi
[ "$(git rev-parse --abbrev-ref HEAD)" = main ] || { echo "Deploy from main." >&2; exit 1; }

echo "==> Building the frontend"
(
  cd frontend
  if [ ! -f node_modules/.package-lock.json ] || [ package-lock.json -nt node_modules/.package-lock.json ]; then
    npm ci --no-audit --no-fund
  fi
  npm run build
)

echo "==> Pushing code to $SERVER"
ssh "$SERVER" "umask 002; [ -d $ROOT/repo.git ] || git init --quiet --bare $ROOT/repo.git; mkdir -p $ROOT/app"
git push --quiet "$SERVER:$ROOT/repo.git" +HEAD:refs/heads/main
ssh "$SERVER" "umask 002; git --git-dir=$ROOT/repo.git --work-tree=$ROOT/app checkout --quiet -f main"

echo "==> Uploading the frontend build"
tar -C frontend/dist -czf - . | ssh "$SERVER" "set -e; umask 002; cd $ROOT
  rm -rf www.new && mkdir www.new && tar -xzf - -C www.new
  if [ -d www ]; then mv www www.old; fi
  mv www.new www && rm -rf www.old"

echo "==> Backend"
ssh "$SERVER" "DOMAIN=$DOMAIN bash $ROOT/app/deploy/remote-deploy.sh"
