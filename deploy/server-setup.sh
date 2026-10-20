#!/usr/bin/env bash
# One-time root setup for the purse store on the Nisatech server (Ubuntu 24.04), next to
# nisatech.org, nisatak.com and contech.
#   scp -r deploy amir@185.231.180.92:purseshop-deploy
#   ssh -t amir@185.231.180.92 'sudo DOMAIN=<host> STAGING=1 bash purseshop-deploy/server-setup.sh'
# DOMAIN: the site's host name (staging: a nisatech.org subdomain; later the client's .ir).
# STAGING=1 puts the whole site behind a password (asked for here) except the payment webhook.
# CERT=1 gets the site a Let's Encrypt certificate (once; certbot.timer renews it) so it answers HTTPS
# itself, for when Arvan's proxy is off or connects over HTTPS. Re-runs keep HTTPS on once it exists.
# Safe to re-run (do, after changing anything under deploy/nginx or deploy/systemd).
set -euo pipefail

DEPLOY_USER=${DEPLOY_USER:-amir}
DOMAIN=${DOMAIN:?set DOMAIN, e.g. DOMAIN=shop.nisatech.org}
STAGING=${STAGING:-0}
ROOT=/srv/purseshop
HERE=$(cd "$(dirname "$0")" && pwd)

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo."; exit 1; }

echo "==> Service user 'purseshop' and $ROOT"
id purseshop &>/dev/null || useradd --system --no-create-home --home-dir "$ROOT" --shell /usr/sbin/nologin purseshop
usermod -aG purseshop "$DEPLOY_USER"
# setgid: everything created inside stays in group purseshop, so the deploy user and the service share it.
install -d -o purseshop -g purseshop -m 2775 "$ROOT"

echo "==> systemd units (gunicorn + the minute timer)"
install -m 644 "$HERE/systemd/purseshop.service" /etc/systemd/system/purseshop.service
install -m 644 "$HERE/systemd/purseshop-tick.service" /etc/systemd/system/purseshop-tick.service
install -m 644 "$HERE/systemd/purseshop-tick.timer" /etc/systemd/system/purseshop-tick.timer
systemctl daemon-reload
systemctl enable purseshop purseshop-tick.timer  # started by the first deploy, once the code is in place

echo "==> Staging password"
ACCESS=/etc/nginx/snippets/purseshop-access.conf
install -d /etc/nginx/snippets
if [ "$STAGING" = 1 ]; then
  if [ ! -f /etc/nginx/purseshop.htpasswd ]; then
    read -rp "   staging user name: " name
    read -rsp "   staging password: " pass; echo
    printf '%s:%s\n' "$name" "$(openssl passwd -apr1 "$pass")" > /etc/nginx/purseshop.htpasswd
    chmod 640 /etc/nginx/purseshop.htpasswd
    chgrp www-data /etc/nginx/purseshop.htpasswd
  fi
  printf 'auth_basic "staging";\nauth_basic_user_file /etc/nginx/purseshop.htpasswd;\n' > "$ACCESS"
else
  : > "$ACCESS"
fi

echo "==> nginx site for $DOMAIN"
# HTTPS lines for the site's server block, once it has a certificate (empty until then).
TLS=/etc/nginx/snippets/purseshop-tls.conf
LIVE=/etc/letsencrypt/live/$DOMAIN
write_tls() {
  if [ -f "$LIVE/fullchain.pem" ]; then
    printf '%s\n' 'listen 443 ssl;' 'listen [::]:443 ssl;' \
      "ssl_certificate $LIVE/fullchain.pem;" "ssl_certificate_key $LIVE/privkey.pem;" \
      'include /etc/letsencrypt/options-ssl-nginx.conf;' 'ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;' > "$TLS"
  else
    : > "$TLS"
  fi
}
write_tls
sed "s/__DOMAIN__/$DOMAIN/" "$HERE/nginx/purseshop.conf" > /etc/nginx/sites-available/purseshop
ln -sf /etc/nginx/sites-available/purseshop /etc/nginx/sites-enabled/purseshop
# A broken site would also block reloads for the other sites: take it out again.
if ! nginx -t; then
  rm -f /etc/nginx/sites-enabled/purseshop
  echo "nginx rejected the purseshop site; it was not enabled." >&2
  exit 1
fi
systemctl reload nginx

if [ "${CERT:-0}" = 1 ] && [ ! -f "$LIVE/fullchain.pem" ]; then
  echo "==> Let's Encrypt certificate for $DOMAIN"
  # Checked over plain HTTP on the site above; the reload hook puts each renewal in use.
  certbot certonly --nginx -d "$DOMAIN" --non-interactive --agree-tos --deploy-hook 'systemctl reload nginx'
  write_tls
  if ! nginx -t; then
    : > "$TLS"
    echo "nginx rejected the HTTPS lines; the site stays on HTTP only." >&2
    exit 1
  fi
  systemctl reload nginx
fi

echo "==> Let $DEPLOY_USER restart the service without a password (and nothing else)"
SUDOERS=/etc/sudoers.d/purseshop-deploy
printf '%s ALL=(root) NOPASSWD: /usr/bin/systemctl restart purseshop, /usr/bin/systemctl is-active purseshop, /usr/bin/systemctl start purseshop-tick.timer\n' "$DEPLOY_USER" > "$SUDOERS.tmp"
visudo -cf "$SUDOERS.tmp"
install -m 440 "$SUDOERS.tmp" "$SUDOERS"
rm -f "$SUDOERS.tmp"

echo "Done. $DEPLOY_USER must open a new SSH session to pick up the purseshop group."
echo "Then from the repo: DOMAIN=$DOMAIN bash deploy/deploy.sh"
