import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time
from typing import Any

from .config import settings


def _encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def _decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    iterations = 210_000
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return f"pbkdf2_sha256${iterations}${_encode(salt)}${_encode(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, iteration_text, salt_text, digest_text = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            _decode(salt_text),
            int(iteration_text),
        )
        return hmac.compare_digest(digest, _decode(digest_text))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, role: str) -> str:
    header = {"alg": "HS256", "typ": "OKDRIVER"}
    payload = {
        "sub": subject,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.token_ttl_minutes * 60,
        "jti": secrets.token_hex(8),
    }
    encoded_header = _encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = _encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(settings.secret_key.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{_encode(signature)}"


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected = hmac.new(
            settings.secret_key.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()
        if not hmac.compare_digest(expected, _decode(encoded_signature)):
            return None
        payload = json.loads(_decode(encoded_payload))
        if int(payload.get("exp", 0)) <= int(time.time()):
            return None
        return payload
    except (ValueError, TypeError, json.JSONDecodeError, binascii.Error):
        return None
