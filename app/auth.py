"""
Authentication helpers for CinePlete.

Implements Radarr-style auth:
  - None                     → open access
  - Forms                    → login required for everyone
  - DisabledForLocalAddresses → login required only from the internet
                                (10.x / 172.16.x / 192.168.x / 127.x are free)

Tokens are HMAC-SHA256 signed payloads — no external JWT lib required.
Passwords are PBKDF2-HMAC-SHA256 with 260 000 iterations (OWASP 2023).
"""

import base64
import hashlib
import hmac
import ipaddress
import json
import secrets
import time

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ITERATIONS   = 260_000
COOKIE_NAME  = "cp_session"
_LOCAL_NETS  = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
]


# ---------------------------------------------------------------------------
# IP helpers
# ---------------------------------------------------------------------------

def is_local_address(ip_str: str) -> bool:
    """Return True if the IP is in a private / loopback range."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return any(ip in net for net in _LOCAL_NETS)
    except ValueError:
        return False


def get_client_ip(request) -> str:
    """Extract real client IP, respecting X-Forwarded-For for reverse proxies."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "127.0.0.1"


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------

def hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    """
    Hash *password* with PBKDF2-HMAC-SHA256.
    Returns (b64-encoded hash, hex salt).  If *salt* is None, a fresh one is
    generated.
    """
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), ITERATIONS
    )
    return base64.b64encode(dk).decode(), salt


def verify_password(password: str, stored_hash: str, salt: str) -> bool:
    computed, _ = hash_password(password, salt)
    return secrets.compare_digest(computed, stored_hash)


# ---------------------------------------------------------------------------
# Session tokens (HMAC-signed, no external dep)
# ---------------------------------------------------------------------------

def _sign(payload: str, secret: str) -> str:
    return hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()


def create_token(username: str, remember_me: bool, secret: str) -> str:
    exp = int(time.time()) + (30 * 86_400 if remember_me else 86_400)
    data = json.dumps({"u": username, "exp": exp})
    payload = base64.urlsafe_b64encode(data.encode()).decode().rstrip("=")
    return f"{payload}.{_sign(payload, secret)}"


def verify_token(token: str, secret: str) -> dict | None:
    """Return decoded payload dict, or None if invalid / expired."""
    try:
        payload, sig = token.rsplit(".", 1)
        if not secrets.compare_digest(_sign(payload, secret), sig):
            return None
        # Re-add padding stripped during creation
        padding = 4 - len(payload) % 4
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * padding))
        if data["exp"] < time.time():
            return None
        return data
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Secret key helpers
# ---------------------------------------------------------------------------

def generate_secret_key() -> str:
    return secrets.token_hex(32)
