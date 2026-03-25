"""
Tests for app/auth.py
Covers: local IP detection, password hashing, session tokens
"""
import time
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.auth import (
    is_local_address,
    hash_password, verify_password,
    create_token, verify_token,
    generate_secret_key,
)


# ─────────────────────────────────────────────
# is_local_address
# ─────────────────────────────────────────────

class TestIsLocalAddress:

    def test_loopback_ipv4(self):
        assert is_local_address("127.0.0.1") is True

    def test_loopback_ipv4_other(self):
        assert is_local_address("127.0.0.2") is True

    def test_private_10(self):
        assert is_local_address("10.0.0.1") is True
        assert is_local_address("10.100.102.9") is True
        assert is_local_address("10.255.255.255") is True

    def test_private_192_168(self):
        assert is_local_address("192.168.0.1") is True
        assert is_local_address("192.168.1.100") is True

    def test_private_172_16(self):
        assert is_local_address("172.16.0.1") is True
        assert is_local_address("172.31.255.255") is True

    def test_loopback_ipv6(self):
        assert is_local_address("::1") is True

    def test_public_ip_is_not_local(self):
        assert is_local_address("8.8.8.8") is False
        assert is_local_address("1.1.1.1") is False
        assert is_local_address("203.0.113.1") is False

    def test_172_outside_private_range(self):
        # 172.32.x.x is NOT in the 172.16.0.0/12 range
        assert is_local_address("172.32.0.1") is False

    def test_invalid_ip_returns_false(self):
        assert is_local_address("not-an-ip") is False
        assert is_local_address("") is False


# ─────────────────────────────────────────────
# hash_password / verify_password
# ─────────────────────────────────────────────

class TestPasswordHashing:

    def test_hash_returns_hash_and_salt(self):
        pw_hash, salt = hash_password("secret123")
        assert pw_hash
        assert salt
        assert len(salt) == 32   # token_hex(16) = 32 hex chars

    def test_same_password_different_salts(self):
        h1, s1 = hash_password("secret123")
        h2, s2 = hash_password("secret123")
        assert s1 != s2
        assert h1 != h2   # different salts → different hashes

    def test_verify_correct_password(self):
        pw_hash, salt = hash_password("mypassword")
        assert verify_password("mypassword", pw_hash, salt) is True

    def test_verify_wrong_password(self):
        pw_hash, salt = hash_password("mypassword")
        assert verify_password("wrongpassword", pw_hash, salt) is False

    def test_verify_empty_password_fails(self):
        pw_hash, salt = hash_password("mypassword")
        assert verify_password("", pw_hash, salt) is False

    def test_hash_with_explicit_salt(self):
        pw_hash, salt = hash_password("secret", salt="abc123defsalt00")
        assert salt == "abc123defsalt00"
        assert verify_password("secret", pw_hash, "abc123defsalt00") is True

    def test_unicode_password(self):
        pw_hash, salt = hash_password("pässwörd!🔒")
        assert verify_password("pässwörd!🔒", pw_hash, salt) is True
        assert verify_password("passwordwrong", pw_hash, salt) is False


# ─────────────────────────────────────────────
# create_token / verify_token
# ─────────────────────────────────────────────

class TestSessionTokens:

    SECRET = "testsecretkey1234567890abcdef"

    def test_valid_token_returns_payload(self):
        token = create_token("admin", False, self.SECRET)
        payload = verify_token(token, self.SECRET)
        assert payload is not None
        assert payload["u"] == "admin"

    def test_remember_me_token_has_longer_expiry(self):
        t_short = create_token("user", False, self.SECRET)
        t_long  = create_token("user", True,  self.SECRET)
        p_short = verify_token(t_short, self.SECRET)
        p_long  = verify_token(t_long,  self.SECRET)
        assert p_long["exp"] > p_short["exp"]

    def test_wrong_secret_returns_none(self):
        token = create_token("admin", False, self.SECRET)
        assert verify_token(token, "wrongsecret") is None

    def test_tampered_payload_returns_none(self):
        token = create_token("admin", False, self.SECRET)
        # Flip a character in the payload portion
        parts = token.split(".")
        parts[0] = parts[0][:-1] + ("A" if parts[0][-1] != "A" else "B")
        tampered = ".".join(parts)
        assert verify_token(tampered, self.SECRET) is None

    def test_expired_token_returns_none(self):
        # Create a token with a past expiry by monkeypatching time
        import app.auth as auth_module
        original_time = time.time

        # Create a token that expires 2 seconds in the future, then advance time
        token = create_token("admin", False, self.SECRET)
        payload = verify_token(token, self.SECRET)

        # Directly forge an expired token
        import json, base64, hmac, hashlib
        data = json.dumps({"u": "admin", "exp": int(time.time()) - 1})
        p = base64.urlsafe_b64encode(data.encode()).decode().rstrip("=")
        sig = hmac.new(self.SECRET.encode(), p.encode(), hashlib.sha256).hexdigest()
        expired_token = f"{p}.{sig}"
        assert verify_token(expired_token, self.SECRET) is None

    def test_malformed_token_returns_none(self):
        assert verify_token("notavalidtoken", self.SECRET) is None
        assert verify_token("", self.SECRET) is None
        assert verify_token("a.b.c.d", self.SECRET) is None

    def test_generate_secret_key_is_unique(self):
        k1 = generate_secret_key()
        k2 = generate_secret_key()
        assert k1 != k2
        assert len(k1) == 64   # token_hex(32) = 64 hex chars
