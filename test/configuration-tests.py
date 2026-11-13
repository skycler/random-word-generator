import base64
import json

import pytest

from syllable_shaker import app, routes
from syllable_shaker.Configuration import Configuration
from syllable_shaker.WordState import WordState
from syllable_shaker.WordToken import encode_word


def configuration_token(payload):
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode()
    return "c2." + base64.urlsafe_b64encode(raw).decode().rstrip("=")


def test_configuration_token_uses_a_compact_array():
    configuration = Configuration.from_values({"fadeout": 250, "capitalize": "yes"})
    token = configuration.to_token()
    raw = json.loads(base64.urlsafe_b64decode(token[3:] + "=" * (-len(token[3:]) % 4)))
    assert raw == [3, 0, 250, 1]
    assert token.startswith("c2.")
    assert len(token) == 18


def test_configuration_round_trip_preserves_preferences_without_word_or_score():
    view = WordState.from_values({
        "token": encode_word("nalimo"), "syllables": "4", "complexity": "complex",
        "fadeout": "1.25", "capitalize": "yes", "score": "9:8",
    }, seconds=True)
    configuration = view.configuration
    token = configuration.to_token()
    assert Configuration.from_token(token) == configuration
    payload = json.loads(base64.urlsafe_b64decode(token[3:] + "=" * (-len(token[3:]) % 4)))
    assert payload == [4, 2, 1250, 1]
    assert view.retry().configuration.to_token() == token


def test_setup_token_does_not_generate_a_word(monkeypatch):
    monkeypatch.setattr(routes, "generator", None)
    configuration = Configuration.from_values({"syllables": "4", "complexity": "complex"})
    response = app.test_client().get("/setup/" + configuration.to_token())
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert 'step="1" value="4"' in html
    assert 'value="complex" selected' in html


@pytest.mark.parametrize("token", [None, "", "c1.e30", "c2.", "c2.e30", "c3.e30", "c2._w", "c2.YR", "c2." + "a" * 513])
def test_malformed_and_old_configuration_tokens_are_rejected(token):
    with pytest.raises(ValueError, match="Invalid configuration token"):
        Configuration.from_token(token)


@pytest.mark.parametrize("position,value", [
    (0, 1), (0, 5), (0, True), (0, "3"),
    (1, 3), (1, -1), (1, True), (1, "simple"),
    (2, -1), (2, 10001), (2, float("nan")), (2, True), (2, 0.0),
    (3, True), (3, 2), (3, -1), (3, "yes"),
])
def test_invalid_configuration_tokens_return_400(position, value):
    payload = [3, 0, 0, 0]
    payload[position] = value
    response = app.test_client().get("/setup/" + configuration_token(payload))
    assert response.status_code == 400
    assert "Invalid configuration token" in response.get_data(as_text=True)


def test_configuration_arrays_require_exactly_four_values():
    for payload in ([3, 0, 0], [3, 0, 0, 0, "extra"]):
        with pytest.raises(ValueError, match="Invalid configuration token"):
            Configuration.from_token(configuration_token(payload))


def test_view_and_configuration_tokens_are_not_interchangeable():
    view = WordState.from_values({"token": encode_word("nalimo")})
    client = app.test_client()
    assert client.get("/setup/" + view.to_token()).status_code == 400
    assert client.get("/word/" + view.configuration.to_token()).status_code == 400
    assert client.get("/qr/" + view.configuration.to_token()).status_code == 400
