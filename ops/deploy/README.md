# Deploy files

Companion files for `../DEPLOYMENT_PLAN.md`. These are ready to use once you have a
server and domain — nothing here needs code changes to LeadGuard itself.

| File | Purpose |
|---|---|
| `Caddyfile` | Reverse-proxy config — one block per client subdomain, automatic HTTPS. |
| `leadguard@.service` | systemd template unit — one running instance per client. |
| `leadguard.env.example` | Per-client env file the systemd unit reads (port + data dir). |
| `provision_client.sh` | Run on the server to spin up one new client: data dir, systemd service, Caddy block. |
| `backup.sh` | Nightly cron job — tars up every client's SQLite data to a backup directory. |

## First-time server setup (once you have a VPS + domain)

1. Install Caddy and systemd are already on most VPS images; install Caddy via its
   official repo if not present.
2. `sudo useradd -r -s /bin/false leadguard` — dedicated service user, no login shell.
3. `sudo mkdir -p /opt/leadguard /etc/leadguard` and deploy the app code to
   `/opt/leadguard` (git clone + `python -m venv backend/venv` + install requirements).
4. Copy `leadguard@.service` to `/etc/systemd/system/` and run `sudo systemctl daemon-reload`.
5. Copy `Caddyfile` to `/etc/caddy/Caddyfile`, point your domain's wildcard DNS record
   (`*.yourdomain.com`) at the server's IP.
6. Put the shared secrets (`ANTHROPIC_API_KEY`, `PRODUCT_NAME`, `AGENCY_NOTIFY_*`) in
   `/opt/leadguard/backend/.env` — same file every client instance reads.
7. For each existing client (LMTLSS, Evolve): `./provision_client.sh <id> <subdomain> <port>`.
8. Add `backup.sh` to root's crontab (see the comment at the top of that file).
9. Point an uptime monitor (e.g. UptimeRobot, free tier) at each
   `https://<subdomain>/api/health`.

## Deploying a code update

On the server, from `/opt/leadguard`:

```bash
git pull
sudo systemctl restart 'leadguard@*'
```
