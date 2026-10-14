#!/usr/bin/env bash
# Runs on the server as the deploy user, called by deploy/deploy.sh after the code is checked out.
set -euo pipefail
umask 002

ROOT=/srv/purseshop
BACKEND=$ROOT/app/backend
cd "$BACKEND"

if [ ! -f .env ]; then
  echo "==> Creating .env (staging defaults: no indexing, SMS printed to the log, manual payments)"
  key=$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')
  cat > .env <<EOF
DJANGO_SECRET_KEY=$key
DJANGO_ALLOWED_HOSTS=$DOMAIN,localhost
PUBLIC_URL=https://$DOMAIN
SITE_NOINDEX=True
VITE_MANIFEST=$ROOT/www/.vite/manifest.json
SMS_BACKEND=console
PAYMENT_PROVIDER=manual
EOF
  chmod 640 .env
  echo "    Edit $BACKEND/.env for Kavenegar, cartbecart and the real domain (see .env.example)."
fi

echo "==> Python dependencies"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt

if [ -f db.sqlite3 ]; then
  echo "==> Backing up the database"
  mkdir -p "$ROOT/backups"
  .venv/bin/python - <<EOF
import sqlite3, datetime
target = "$ROOT/backups/db-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + ".sqlite3"
with sqlite3.connect(target) as dst:
    sqlite3.connect("db.sqlite3").backup(dst)
print("   ", target)
EOF
  ls -1t "$ROOT"/backups/db-*.sqlite3 | tail -n +31 | xargs -r rm --
  chmod 640 "$ROOT"/backups/db-*.sqlite3
fi

echo "==> Migrations, cache table, static files, roles, starting content"
.venv/bin/python manage.py migrate --noinput
.venv/bin/python manage.py createcachetable
.venv/bin/python manage.py collectstatic --noinput --verbosity 0
.venv/bin/python manage.py setup_roles
.venv/bin/python manage.py seed_store
chmod 660 db.sqlite3
# Transfer screenshots: the service writes them, nobody else reads them.
install -d -m 2770 private

echo "==> Restarting gunicorn"
sudo /usr/bin/systemctl restart purseshop
sudo /usr/bin/systemctl start purseshop-tick.timer
sleep 2
sudo /usr/bin/systemctl is-active purseshop
