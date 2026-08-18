#!/usr/bin/env python3
"""Provision a new EvolveIQ client instance on this production server.

Turns "stand up a new client" from a handful of manual systemctl/Caddy/SSH
steps into one command. Ties together everything set up by hand for LMTLSS
and Evolve: a per-client systemd service (via the evolveiq-client@ template),
a Caddy subdomain reverse-proxying to it, and a row in the local client
registry so future tooling can enumerate what's running.

Usage:
  python3 provision_client.py --id acme-hvac --name "Acme HVAC" --subdomain acme
  python3 provision_client.py --id acme-hvac --name "Acme HVAC"   # subdomain defaults to id

Run as root on the server itself (needs systemctl/caddy/chown).
"""
import argparse
import json
import pathlib
import re
import subprocess
import sys

CLIENTS_DIR = pathlib.Path("/opt/evolveiq/clients")
CADDY_SITES_DIR = pathlib.Path("/etc/caddy/sites")
# Must match ops/launcher_server.py's CLIENTS_PATH exactly (OPS_DIR / "clients.json",
# i.e. inside the git-managed app dir) — NOT /opt/evolveiq/clients.json, a stale path
# from an earlier schema that the launcher stopped reading from. Writing to the wrong
# file meant every client provisioned by this script silently never showed up in the
# admin dashboard (discovered 2026-08-18, re-registering Evolve Credit Repair).
REGISTRY_PATH = pathlib.Path("/opt/evolveiq/app/ops/clients.json")
DOMAIN = "justaskevolveiq.com"
PORT_RANGE_START = 8000
PORT_RANGE_END = 8999


def load_registry():
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return []


def save_registry(registry):
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2) + "\n")


def next_free_port(registry):
    used = {c["port"] for c in registry}
    port = PORT_RANGE_START
    while port in used and port <= PORT_RANGE_END:
        port += 1
    if port > PORT_RANGE_END:
        raise SystemExit("No free ports left in range — widen PORT_RANGE_END or retire an old client")
    return port


def slugify(value: str) -> str:
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", value.strip().lower())).strip("-")


def run(cmd, **kwargs):
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", required=True, help="Unique client id, e.g. acme-hvac (lowercase, hyphenated)")
    parser.add_argument("--name", required=True, help="Human-readable business name, e.g. 'Acme HVAC'")
    parser.add_argument("--subdomain", default=None, help="Defaults to --id if omitted")
    parser.add_argument("--port", type=int, default=None, help="Defaults to next free port if omitted")
    parser.add_argument("--accent-color", default="#4f46e5", help="Hex color for the dashboard/widget accent")
    args = parser.parse_args()

    client_id = slugify(args.id)
    subdomain = slugify(args.subdomain or client_id)

    if client_id != args.id:
        print(f"Note: client id normalized to '{client_id}'")

    env_path = CLIENTS_DIR / f"{client_id}.env"
    if env_path.exists():
        raise SystemExit(f"Client '{client_id}' already exists ({env_path}) — pick a different --id, or remove it first")

    registry = load_registry()
    if any(c["id"] == client_id for c in registry):
        raise SystemExit(f"Client '{client_id}' already in the registry — pick a different --id")

    port = args.port or next_free_port(registry)
    if any(c["port"] == port for c in registry):
        raise SystemExit(f"Port {port} is already in use by another client")

    data_dir = CLIENTS_DIR / client_id / "data"
    print(f"\nProvisioning '{args.name}' (id={client_id}, subdomain={subdomain}.{DOMAIN}, port={port})\n")

    # 1. Data directory + per-instance env file
    data_dir.mkdir(parents=True, exist_ok=True)
    env_path.write_text(f"PORT={port}\nLEADGUARD_DATA_DIR={data_dir}\n")
    run(["chown", "-R", "evolveiq:evolveiq", str(CLIENTS_DIR / client_id), str(env_path)])
    run(["chmod", "700", str(CLIENTS_DIR / client_id)])
    run(["chmod", "600", str(env_path)])

    # 2. systemd service (template already installed at
    #    /etc/systemd/system/evolveiq-client@.service — this just instantiates it)
    service = f"evolveiq-client@{client_id}.service"
    run(["systemctl", "enable", service])
    run(["systemctl", "start", service])

    # 3. Caddy subdomain
    caddy_site = CADDY_SITES_DIR / f"{client_id}.caddy"
    caddy_site.write_text(f"{subdomain}.{DOMAIN} {{\n\treverse_proxy 127.0.0.1:{port}\n}}\n")
    run(["caddy", "validate", "--config", "/etc/caddy/Caddyfile"])
    run(["systemctl", "reload", "caddy"])

    # 4. Registry — shape must match what ops/launcher_server.py's load_clients()
    # actually expects (data_dir/accent_color/type/tier/features), not the older
    # subdomain/industry shape. tier/features start unset; set via the launcher's
    # tier dropdown after provisioning, same as every other client.
    registry.append({
        "id": client_id,
        "name": args.name,
        "port": port,
        "data_dir": str(data_dir),
        "accent_color": args.accent_color,
        "widget_demo": None,
        "sales_demo": None,
        "type": "client",
        "tier": None,
        "features": {},
    })
    save_registry(registry)

    print(f"\nDone. Live at:")
    print(f"  Dashboard: https://{subdomain}.{DOMAIN}/dashboard/")
    print(f"  Widget:    https://{subdomain}.{DOMAIN}/widget/widget.js")
    print(f"\nSet tier, industry, and the rest of the business details via the")
    print(f"admin dashboard (team.{DOMAIN}) — nothing here configures those.")
    print(f"(HTTPS cert issues automatically on first real request — may take a few seconds.)")


if __name__ == "__main__":
    if sys.platform != "linux":
        print("Warning: this is meant to run on the server itself, not locally.", file=sys.stderr)
    main()
