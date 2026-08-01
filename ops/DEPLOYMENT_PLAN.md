# Deployment Plan — From Laptop to Real Hosting

Everything built so far has run on `localhost` on your own machine — fine for
building and demoing, not deployable to a real client today. This is the
plan to fix that, sized for ~10 clients without over-building. It's
infrastructure, not a product change — no code, schema, or feature-scope
changes to LeadGuard itself; the app runs exactly as it does today, just on
a real always-on host instead of your laptop.

## The shape of it

One small always-on server, running all ten clients as separate lightweight
processes (same single-tenant architecture already built — one SQLite file
and one FastAPI process per client, nothing rearchitected), with a reverse
proxy in front routing by subdomain.

```
                         ┌─────────────────────────────┐
  client1.leadguard.app ─┤                              ├─ backend on :8001
  client2.leadguard.app ─┤   Caddy (reverse proxy +     ├─ backend on :8002
  client3.leadguard.app ─┤   automatic HTTPS)           ├─ backend on :8003
        ...              │                              │       ...
                         └─────────────────────────────┘
                              one small VPS, always on
```

## Components

### 1. A server
One small VPS (virtual private server) that's on 24/7, independent of your
laptop. Recommendation: **DigitalOcean's cheapest droplet** (~$6-12/month
for 1-2GB RAM) — friendlier docs and support than most alternatives if
you're not deep into server ops already. **Hetzner** is materially cheaper
for similar specs if you're comfortable with a slightly less polished
control panel — worth it once you're confident in the setup. Either easily
runs 10+ of these lightweight FastAPI/SQLite instances at once; this
workload is small.

### 2. A domain
Buy one domain for the product if you don't already have one (~$10-15/year)
— e.g. `leadguard.app`. Set up **one wildcard DNS record**
(`*.leadguard.app` → the server's IP) so every future client subdomain
works automatically, with zero new DNS entry needed per client.

### 3. Reverse proxy — Caddy
Caddy over nginx for this specifically because it handles HTTPS
certificates automatically (via Let's Encrypt) with no manual cert
management — meaningful since you'll be adding a new subdomain regularly.
Config is a short block per client:

```
client1.leadguard.app {
    reverse_proxy localhost:8001
}
client2.leadguard.app {
    reverse_proxy localhost:8002
}
```

### 4. Process management — systemd
Every instance so far has been started by hand (`uvicorn ... &` in a
terminal) — that dies the moment the terminal closes or the server
reboots. A systemd service per client instance fixes both: auto-starts on
server boot, auto-restarts if the process crashes, no manual commands. One
templated unit file, parameterized by port and data directory, covers all
clients without writing ten near-identical files by hand.

### 5. The "new client" provisioning script
Ties the above together into the single command the earlier "cutting setup
time down" conversation was aiming at. Given a client name, subdomain, and
port, it should:
1. Create the client's data directory.
2. Write its systemd unit file and start the service.
3. Append its Caddyfile block and reload Caddy.
4. Append a row to `ops/CLIENT_DIRECTORY.md` (the private one — still
   never published, per its own warning).

Turns "spin up a new instance" from a handful of manual steps into one
script invocation.

### 6. Deploying code updates
All clients share the same codebase, just different data/port. A code
change (like today's Pipeline feature) needs: pull the new code once on the
server, then restart every client's systemd service to pick it up. A short
script (`git pull && systemctl restart leadguard-*`) covers this — no
per-client manual SSH work.

### 7. Backups
Each client's entire data is a single SQLite file. A nightly cron job
copying every client's data directory to off-server storage (a cheap
S3-compatible bucket, or even a scheduled copy to your own machine) is
enough at this scale. Worth setting up before real client data exists, not
after — a single-server failure with no backup loses every client's leads
and conversations at once.

### 8. Uptime monitoring
Closes the "how do I know if an instance goes down" gap from the earlier
ops discussion, cheaply: a free-tier service (UptimeRobot or similar)
pinging each client's `/api/health` endpoint every few minutes, alerting
you by email/SMS if one stops responding — no custom monitoring code
needed.

## Cost, all-in for 10 clients

- VPS: ~$6-12/month (one server, not per client)
- Domain: ~$10-15/year
- Uptime monitoring: free tier is sufficient at this scale
- **Total: under $20/month** for all ten clients combined — small relative
  to $99/month × 10 clients in revenue, but a real new recurring cost line
  that should be folded into the pro forma rather than left implicit.

## What this doesn't require

No schema changes, no product feature changes, no rebuild of anything
already built this session — the Pipeline board, Team Access, rot
thresholds, all of it runs on this host exactly as it runs on `localhost`
today. This is purely where the code runs, not what it does.

## Recommended order of operations

1. Buy the domain (if you don't already have one for this).
2. Provision one small VPS (DigitalOcean or Hetzner).
3. Install Caddy; point the wildcard DNS record at the server.
4. Set up the systemd template unit.
5. Write the new-client provisioning script.
6. Set up the backup cron job and uptime monitoring.
7. Migrate the existing LMTLSS and Evolve demo instances onto it as the
   first real test — proves the whole pipeline before a real client is on
   the line.

I can write the actual Caddyfile, systemd unit template, and provisioning
script whenever you're ready to execute this — those are just files. The
domain purchase and server provisioning are real-money, real-account
actions only you can take; let me know once you've got a server and domain
in hand and I'll wire up everything from there.
