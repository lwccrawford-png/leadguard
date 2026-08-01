#!/usr/bin/env bash
# Spin up one new client instance on the LeadGuard host. Run this ON THE SERVER
# (not your laptop) — it touches systemd and Caddy, both server-only concerns.
#
# Usage: ./provision_client.sh <client_id> <subdomain> <port>
#   ./provision_client.sh acme_plumbing acme-plumbing.yourdomain.com 8003
#
# What it does:
#   1. Creates /opt/leadguard/data/<client_id>
#   2. Writes /etc/leadguard/<client_id>.env
#   3. Enables + starts leadguard@<client_id>.service
#   4. Appends a reverse-proxy block to /etc/caddy/Caddyfile and reloads Caddy
#
# What it does NOT do: add a row to ops/CLIENT_DIRECTORY.md — that file is
# deliberately kept out of git (real client names/URLs, never to be published)
# and lives only on your laptop. Add the row there yourself after this runs.

set -euo pipefail

CLIENT_ID="${1:?Usage: provision_client.sh <client_id> <subdomain> <port>}"
SUBDOMAIN="${2:?Usage: provision_client.sh <client_id> <subdomain> <port>}"
PORT="${3:?Usage: provision_client.sh <client_id> <subdomain> <port>}"

DATA_DIR="/opt/leadguard/data/${CLIENT_ID}"
ENV_FILE="/etc/leadguard/${CLIENT_ID}.env"
CADDYFILE="/etc/caddy/Caddyfile"

if [[ -f "$ENV_FILE" ]]; then
  echo "Error: ${ENV_FILE} already exists — ${CLIENT_ID} looks already provisioned." >&2
  exit 1
fi

if ss -ltn "( sport = :${PORT} )" | grep -q LISTEN; then
  echo "Error: port ${PORT} is already in use." >&2
  exit 1
fi

echo "Creating data directory ${DATA_DIR}..."
sudo mkdir -p "$DATA_DIR"
sudo chown leadguard:leadguard "$DATA_DIR"

echo "Writing ${ENV_FILE}..."
sudo tee "$ENV_FILE" > /dev/null <<EOF
PORT=${PORT}
LEADGUARD_DATA_DIR=${DATA_DIR}
EOF

echo "Enabling and starting leadguard@${CLIENT_ID}.service..."
sudo systemctl enable --now "leadguard@${CLIENT_ID}.service"

echo "Appending Caddy block for ${SUBDOMAIN}..."
sudo tee -a "$CADDYFILE" > /dev/null <<EOF

${SUBDOMAIN} {
    reverse_proxy localhost:${PORT}
}
EOF
sudo systemctl reload caddy

echo ""
echo "Done. ${CLIENT_ID} is live at https://${SUBDOMAIN} (port ${PORT})."
echo "Reminder: add a row for it to ops/CLIENT_DIRECTORY.md on your laptop — that file"
echo "stays local-only and isn't touched by this script."
