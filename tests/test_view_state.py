import base64
import json

import pytest

from syllable_shaker import app
from syllable_shaker.WordState import WordState
from syllable_shaker.WordToken import encode_word


def payload_token(payload):
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    return "v2." + base64.urlsafe_b64encode(raw).decode().rstrip("=")


@pytest.fixture
def payload():
    return ["mälin", 4, 2, 2, 3, 250, 1]


def test_view_token_uses_a_compact_array():
    state = WordState.from_values(
        {"token": encode_word("nalimo"), "fadeout": 250, "capitalize": "yes"}
    )
    token = state.to_token()
    raw = json.loads(base64.urlsafe_b64decode(token[3:] + "=" * (-len(token[3:]) % 4)))
    assert raw == ["nalimo", 3, 0, 0, 0, 250, 1]
    assert token.startswith("v2.")
    assert len(token) == 35


def test_view_token_preserves_the_word_and_every_setting(payload):
    token = payload_token(payload)
    state = WordState.from_token(token)
    assert state.word() == "MÄLIN"
    assert state.syllables == 4
    assert state.complexity == "complex"
    assert state.score == "2:3"
    assert state.fadeout == 250.0
    assert state.capitalize == "yes"
    assert state.to_token() == token
    assert "mälin" not in token
    assert "complex" not in token


def test_retry_changes_the_state_token_but_not_the_word(payload):
    original = WordState.from_token(payload_token(payload))
    repeated = original.retry()
    assert repeated.word() == original.word()
    assert repeated.score == "3:3"
    assert repeated.to_token() != original.to_token()
    assert WordState.from_token(repeated.to_token()) == repeated


@pytest.mark.parametrize(
    "token",
    [
        None,
        "",
        "v1.e30",
        "v2.",
        "v3.e30",
        "v2.!bad",
        "v2.YR",
        "v2._w",
        "v2.bmFsaW1v",
        "v2." + "a" * 513,
        "v2.W10",
        "v2.bnVsbA",
        "v2.e30",
    ],
)
def test_malformed_and_old_view_tokens_are_rejected(token):
    with pytest.raises(ValueError, match="Invalid view token"):
        WordState.from_token(token)


@pytest.mark.parametrize(
    "position,value",
    [
        (0, "<script>alert(1)</script>"),
        (0, "two words"),
        (0, ""),
        (1, 5),
        (1, True),
        (1, "3"),
        (2, 3),
        (2, -1),
        (2, True),
        (2, "simple"),
        (3, "invalid"),
        (3, True),
        (3, 0.0),
        (4, True),
        (4, 10**100),
        (5, -1),
        (5, 11000),
        (5, float("nan")),
        (5, float("inf")),
        (5, True),
        (5, "250"),
        (5, 250.0),
        (6, True),
        (6, 2),
        (6, -1),
        (6, "yes"),
    ],
)
def test_invalid_embedded_state_returns_400_in_views_and_actions(payload, position, value):
    payload[position] = value
    token = payload_token(payload)
    client = app.test_client()
    assert client.get("/word/" + token).status_code == 400
    assert client.get("/qr/" + token).status_code == 400
    assert client.post("/next", data={"state": token}).status_code == 400
    assert client.post("/repeat", data={"state": token}).status_code == 400


def test_wrong_array_lengths_and_noncanonical_encodings_are_rejected(payload):
    for malformed in (payload[:-1], payload + ["extra"]):
        with pytest.raises(ValueError, match="Invalid view token"):
            WordState.from_token(payload_token(malformed))
    token = payload_token(payload)
    with pytest.raises(ValueError, match="Invalid view token"):
        WordState.from_token(token + "=")
    spaced = "v2." + base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    with pytest.raises(ValueError, match="Invalid view token"):
        WordState.from_token(spaced)


def test_fractional_milliseconds_are_not_rounded(payload):
    payload[5] = 125.5
    state = WordState.from_token(payload_token(payload))
    assert state.fadeout == 125.5
    assert state.to_token() == payload_token(payload)


def test_old_object_tokens_are_rejected_without_migration_redirects():
    old = {
        "word": "nalimo",
        "syllables": 3,
        "complexity": "simple",
        "score": "0:0",
        "fadeout": 0.0,
        "capitalize": "no",
    }
    encoded = (
        base64.urlsafe_b64encode(json.dumps(old, sort_keys=True, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )
    client = app.test_client()
    for path in ("/word/v1.", "/qr/v1."):
        response = client.get(path + encoded)
        assert response.status_code == 400
        assert "Location" not in response.headers
    old.pop("word")
    old.pop("score")
    encoded = (
        base64.urlsafe_b64encode(json.dumps(old, sort_keys=True, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )
    response = client.get("/setup/c1." + encoded)
    assert response.status_code == 400
    assert "Location" not in response.headers


def test_largest_supported_word_and_score_fit_within_token_limit():
    state = WordState.from_values({"token": encode_word("ä" * 32), "score": "0:" + "9" * 62})
    assert WordState.from_token(state.to_token()) == state
