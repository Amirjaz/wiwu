#!/usr/bin/env bash
# Deploys the committed main branch to the server. From the repo root (Git Bash on Windows works):
#   DOMAIN=<host> bash deploy/deploy.sh
# The code goes to a bare repo on the server over SSH (no GitHub access needed there); the
# frontend is built here, since the server has no Node (and npm is unreliable from Iran).
set -euo pipefail

SERVER=${SERVER:-amir@37.32.25.183}  # the shop's own server since 2026-10-24 (the shared Nisatech one before)
# The site's host name: written into the server's backend/.env on the first deploy, checked against
# it on later ones, and used for the HTTPS check at the end.
DOMAIN=${DOMAIN:?set DOMAIN, the site host name, e.g. DOMAIN=penolinshop.com}
ROOT=/srv/purseshop

cd "$(git rev-parse --show-toplevel)"
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "Uncommitted changes; commit them first so the server runs exactly what is in git." >&2
  exit 1
fi
[ "$(git rev-parse --abbrev-ref HEAD)" = main ] || { echo "Deploy from main." >&2; exit 1; }

# A new domain means editing .env on the server first (README, Deploying): otherwise SMS links and
# the sitemap would keep the old address, and Django would turn the new one away.
if ssh "$SERVER" "[ -f $ROOT/app/backend/.env ] && ! grep -qx 'PUBLIC_URL=https://$DOMAIN' $ROOT/app/backend/.env"; then
  echo "The server's backend/.env has a PUBLIC_URL other than https://$DOMAIN; fix one of them first." >&2
  exit 1
fi

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
