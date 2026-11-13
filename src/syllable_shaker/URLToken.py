"""Canonical, bounded Base64-JSON tokens. Obfuscation, not authentication."""

import base64
import binascii
import json
import re


def encode_payload(version, payload):
    if not isinstance(payload, list):
        raise ValueError("URL token payload must be an array.")
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")
    if not 2 <= len(encoded) <= 512:
        raise ValueError("URL token payload is too large.")
    return version + "." + encoded


def decode_payload(version, token):
    pattern = re.escape(version) + r"\.[A-Za-z0-9_-]{2,512}"
    if not isinstance(token, str) or not re.fullmatch(pattern, token):
        raise ValueError("Invalid URL token.")
    try:
        encoded = token[len(version) + 1:]
        raw = base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, list) or encode_payload(version, payload) != token:
            raise ValueError("Noncanonical URL token.")
    except (binascii.Error, UnicodeError, ValueError, TypeError) as error:
        raise ValueError("Invalid URL token.") from error
    return payload
