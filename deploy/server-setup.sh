#!/usr/bin/env bash
# One-time root setup for the purse store on its own server (Arvan cloud in Tehran, Ubuntu 24.04,
# 37.32.25.183 since 2026-10-24; before that the shared Nisatech server, 185.231.180.92). A bare server
# needs nginx, certbot, python3-certbot-nginx and python3-venv, swap, and the deploy user with the
# deployer's SSH key first (README -> Deploying, *A new server*). Then, as root:
#   scp -r deploy root@37.32.25.183:purseshop-deploy
#   ssh root@37.32.25.183 'DOMAIN=<host> REDIRECT="<names>" PANEL="<names>" CERT=1 bash purseshop-deploy/server-setup.sh'
# DOMAIN: the site's host name (penolinshop.com since 2026-10-24; shop.nisatech.org before).
# REDIRECT: other names (space-separated) that send visitors to DOMAIN, keeping the path: its www and
# any address the shop used to have, e.g. REDIRECT="www.penolinshop.com shop.nisatech.org".
# PANEL: names that open the staff panel, DOMAIN/panel/, keeping the rest of the path (Amir, 2026-10-24:
# PANEL="panel.penolinshop.com"; panel.penolinshop.com/orders opens penolinshop.com/panel/orders).
# STAGING=1 puts the whole site behind a password (asked for here) except the payment webhook.
# CERT=1 gets DOMAIN and each REDIRECT and PANEL name its own Let's Encrypt certificate (once; certbot.timer renews
# them) so they answer HTTPS themselves, for when Arvan's proxy is off or connects over HTTPS. Re-runs
# keep HTTPS on once a name has one.
# Safe to re-run (do, after changing anything under deploy/nginx or deploy/systemd). Pass the same
# REDIRECT and PANEL every time: a name left out stops redirecting.
set -euo pipefail

DEPLOY_USER=${DEPLOY_USER:-amir}
DOMAIN=${DOMAIN:?set DOMAIN, e.g. DOMAIN=penolinshop.com}
REDIRECT=${REDIRECT:-}
PANEL=${PANEL:-}
STAGING=${STAGING:-0}
ROOT=/srv/purseshop
HERE=$(cd "$(dirname "$0")" && pwd)

[ "$(id -u)" -eq 0 ] || { echo "Run with sudo."; exit 1; }
for name in $REDIRECT $PANEL; do
  [ "$name" != "$DOMAIN" ] || { echo "REDIRECT and PANEL must not include DOMAIN ($DOMAIN)." >&2; exit 1; }
done
for name in $PANEL; do
  case " $REDIRECT " in *" $name "*) echo "$name is in both REDIRECT and PANEL." >&2; exit 1 ;; esac
done

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

echo "==> nginx site for $DOMAIN${REDIRECT:+ (and $REDIRECT, sent to it)}${PANEL:+ (and $PANEL, sent to its panel)}"
# HTTPS lines for a server block, once its name has a certificate (empty until then): the shop's block
# includes purseshop-tls.conf, each REDIRECT or PANEL name's block purseshop-tls-<name>.conf.
tls_file() {
  if [ "$1" = "$DOMAIN" ]; then echo /etc/nginx/snippets/purseshop-tls.conf
  else echo "/etc/nginx/snippets/purseshop-tls-$1.conf"; fi
}
write_tls() {  # $1: a host name
  local live=/etc/letsencrypt/live/$1
  if [ -f "$live/fullchain.pem" ]; then
    printf '%s\n' 'listen 443 ssl;' 'listen [::]:443 ssl;' \
      "ssl_certificate $live/fullchain.pem;" "ssl_certificate_key $live/privkey.pem;" \
      'include /etc/letsencrypt/options-ssl-nginx.conf;' 'ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;' > "$(tls_file "$1")"
  else
    : > "$(tls_file "$1")"
  fi
}
for name in $DOMAIN $REDIRECT $PANEL; do write_tls "$name"; done
{
  sed "s/__DOMAIN__/$DOMAIN/" "$HERE/nginx/purseshop.conf"
  for name in $REDIRECT; do
    echo
    sed -e "s|__NAME__|$name|g" -e "s|__TARGET__|$DOMAIN|g" "$HERE/nginx/purseshop-redirect.conf"
  done
  for name in $PANEL; do
    echo
    sed -e "s|__NAME__|$name|g" -e "s|__TARGET__|$DOMAIN/panel|g" "$HERE/nginx/purseshop-redirect.conf"
  done
} > /etc/nginx/sites-available/purseshop
ln -sf /etc/nginx/sites-available/purseshop /etc/nginx/sites-enabled/purseshop
# A broken site would also block reloads for the other sites: take it out again.
if ! nginx -t; then
  rm -f /etc/nginx/sites-enabled/purseshop
  echo "nginx rejected the purseshop site; it was not enabled." >&2
  exit 1
fi
systemctl reload nginx

if [ "${CERT:-0}" = 1 ]; then
  for name in $DOMAIN $REDIRECT $PANEL; do
    if [ -f "/etc/letsencrypt/live/$name/fullchain.pem" ]; then continue; fi
    echo "==> Let's Encrypt certificate for $name"
    # Checked over plain HTTP on the blocks above; the reload hook puts each renewal in use.
    certbot certonly --nginx -d "$name" --non-interactive --agree-tos --deploy-hook 'systemctl reload nginx'
    write_tls "$name"
    if ! nginx -t; then
      : > "$(tls_file "$name")"
      echo "nginx rejected the HTTPS lines for $name; it stays on HTTP only." >&2
      exit 1
    fi
    systemctl reload nginx
  done
fi

echo "==> Let $DEPLOY_USER restart the service without a password (and nothing else)"
SUDOERS=/etc/sudoers.d/purseshop-deploy
printf '%s ALL=(root) NOPASSWD: /usr/bin/systemctl restart purseshop, /usr/bin/systemctl is-active purseshop, /usr/bin/systemctl start purseshop-tick.timer\n' "$DEPLOY_USER" > "$SUDOERS.tmp"
visudo -cf "$SUDOERS.tmp"
install -m 440 "$SUDOERS.tmp" "$SUDOERS"
rm -f "$SUDOERS.tmp"

echo "Done. $DEPLOY_USER must open a new SSH session to pick up the purseshop group."
echo "Then from the repo: DOMAIN=$DOMAIN bash deploy/deploy.sh"
