"""Stateless word obfuscation, independent of generation rules. Not encryption."""

import base64
import binascii
import re


_WORD = re.compile(r"[a-zäöüß]{1,32}")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{2,86}")


def encode_word(word):
    if not isinstance(word, str) or not _WORD.fullmatch(word):
        raise ValueError("Invalid word; use at most 32 lower-case German letters.")
    return base64.urlsafe_b64encode(word.encode("utf-8")).decode("ascii").rstrip("=")


def decode_word(token):
    if not isinstance(token, str) or not _TOKEN.fullmatch(token):
        raise ValueError("Invalid word token.")
    try:
        padding = "=" * (-len(token) % 4)
        word = base64.b64decode(token + padding, altchars=b"-_", validate=True).decode("utf-8")
        # Reject noncanonical encodings, arbitrary bytes, and HTML/script payloads.
        if encode_word(word) != token:
            raise ValueError("Noncanonical word token.")
    except (binascii.Error, UnicodeError, ValueError) as error:
        raise ValueError("Invalid word token.") from error
    return word
