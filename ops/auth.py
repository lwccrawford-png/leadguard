"""Minimal session-cookie auth for launcher_server.py — stdlib only, no new
dependencies. Not meant to be a general-purpose auth system: a handful of named
logins (Larry, Natalia, a couple of VAs) protecting one internal tool.

User store: ops/auth_users.json (gitignored — real credentials, never committed).
Session secret: ops/.auth_secret (gitignored, auto-generated on first run).

Password hashing: PBKDF2-HMAC-SHA256, stdlib via hashlib.pbkdf2_hmac.
Session cookie: "username|expiry|hmac-signature", verified with hmac.compare_digest
to avoid timing attacks. Not a JWT/itsdangerous-style library — deliberately simple
and auditable for a low-user-count internal tool.
"""
import base64
import hashlib
import hmac
import json
import os
import pathlib
import secrets
import time
from typing import Optional

BASE_DIR = pathlib.Path(__file__).parent
USERS_PATH = BASE_DIR / "auth_users.json"
SECRET_PATH = BASE_DIR / ".auth_secret"
SESSION_COOKIE = "eiq_session"
SESSION_LIFETIME_SECONDS = 14 * 24 * 60 * 60  # 14 days


def _get_secret() -> bytes:
    if SECRET_PATH.exists():
        return SECRET_PATH.read_bytes()
    secret = secrets.token_bytes(32)
    SECRET_PATH.write_bytes(secret)
    os.chmod(SECRET_PATH, 0o600)
    return secret


def _load_users() -> dict:
    if not USERS_PATH.exists():
        return {}
    return json.loads(USERS_PATH.read_text())


def _save_users(users: dict) -> None:
    USERS_PATH.write_text(json.dumps(users, indent=2))
    os.chmod(USERS_PATH, 0o600)


def hash_password(password: str, salt: bytes = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return base64.b64encode(salt).decode() + "$" + base64.b64encode(digest).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_b64, digest_b64 = stored.split("$", 1)
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except (ValueError, TypeError):
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 200_000)
    return hmac.compare_digest(actual, expected)


def add_user(username: str, password: str) -> None:
    users = _load_users()
    users[username.strip().lower()] = hash_password(password)
    _save_users(users)


def remove_user(username: str) -> bool:
    users = _load_users()
    removed = users.pop(username.strip().lower(), None) is not None
    if removed:
        _save_users(users)
    return removed


def list_usernames() -> list:
    return sorted(_load_users().keys())


def check_login(username: str, password: str) -> bool:
    users = _load_users()
    stored = users.get(username.strip().lower())
    if not stored:
        return False
    return verify_password(password, stored)


def make_session_cookie(username: str) -> str:
    expiry = int(time.time()) + SESSION_LIFETIME_SECONDS
    payload = f"{username}|{expiry}"
    sig = hmac.new(_get_secret(), payload.encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"{payload}|{sig}".encode()).decode()


def verify_session_cookie(cookie_value: str) -> Optional[str]:
    """Return the username if the cookie is valid and unexpired, else None."""
    if not cookie_value:
        return None
    try:
        decoded = base64.urlsafe_b64decode(cookie_value.encode()).decode()
        username, expiry_str, sig = decoded.split("|", 2)
        expiry = int(expiry_str)
    except (ValueError, TypeError):
        return None
    if time.time() > expiry:
        return None
    expected_sig = hmac.new(_get_secret(), f"{username}|{expiry}".encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected_sig):
        return None
    return username


if __name__ == "__main__":
    import sys

    if len(sys.argv) == 4 and sys.argv[1] == "add-user":
        add_user(sys.argv[2], sys.argv[3])
        print(f"Added/updated user: {sys.argv[2]}")
    elif len(sys.argv) == 3 and sys.argv[1] == "remove-user":
        ok = remove_user(sys.argv[2])
        print("Removed." if ok else "No such user.")
    elif len(sys.argv) == 2 and sys.argv[1] == "list-users":
        for u in list_usernames():
            print(u)
    else:
        print("Usage:")
        print("  python3 auth.py add-user <username> <password>")
        print("  python3 auth.py remove-user <username>")
        print("  python3 auth.py list-users")
