import pytest

from syllable_shaker.WordToken import decode_word, encode_word


@pytest.mark.parametrize("word", ["nalimo", "mälin", "straße"])
def test_word_tokens_round_trip_without_exposing_the_literal_word(word):
    token = encode_word(word)
    assert word not in token
    assert "=" not in token
    assert decode_word(token) == word


@pytest.mark.parametrize("token", [
    None, "", "a", "!!", "2.0", "bmFsaW1v=", "YR", "_w", "a" * 100,
])
def test_invalid_and_noncanonical_tokens_are_rejected(token):
    with pytest.raises(ValueError, match="Invalid word token"):
        decode_word(token)


@pytest.mark.parametrize("word", ["<script>alert(1)</script>", "two words", "123", "NALIMO", "", "a" * 33])
def test_valid_base64_cannot_smuggle_invalid_word_payloads(word):
    import base64

    token = base64.urlsafe_b64encode(word.encode()).decode().rstrip("=")
    with pytest.raises(ValueError, match="Invalid word token"):
        decode_word(token)


def test_tokens_are_canonical_and_support_the_maximum_word_length():
    assert encode_word("nalimo") == "bmFsaW1v"
    assert decode_word("YQ") == "a"
    word = "ä" * 32
    assert decode_word(encode_word(word)) == word
