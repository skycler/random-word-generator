import random
import re

import pytest

from syllable_shaker.WordGenerator import WordGenerator


@pytest.mark.parametrize("count", [2, 3, 4])
def test_simple_words_have_the_requested_number_of_open_syllables(count):
    generator = WordGenerator(rng=random.Random(42))
    for _ in range(100):
        result = generator.generate(syllables=count, complexity="simple")
        assert len(result.syllables) == count
        assert result.text == "".join(result.syllables)
        assert all(
            re.fullmatch(r"[bdfgklmnprst][aeiou]", syllable) for syllable in result.syllables
        )


@pytest.mark.parametrize("complexity", ["simple", "medium", "complex"])
def test_words_respect_syllable_boundaries_and_readable_sound_patterns(complexity):
    generator = WordGenerator(rng=random.Random(123))
    words = [generator.generate(syllables=4, complexity=complexity) for _ in range(500)]
    for result in words:
        assert len(result.syllables) == 4
        assert re.fullmatch(r"[a-z]+", result.text)
        # sch is one sound, even though it is spelled with three letters.
        assert not re.search(r"[^aeiou]{3}", result.text.replace("sch", "S"))
        assert not re.search(r"(.)\1", result.text)
        assert "ng" not in result.text  # Avoid merging n + g into a different sound.
        for previous, current in zip(result.syllables, result.syllables[1:]):
            assert not (previous[-1] in "aeiou" and current[0] in "aeiou")
        assert all(
            re.fullmatch(r"(?:sch|[bdfgklmnprst]{1,2})?(?:ei|au|[aeiou])[nmlrstkf]?", syllable)
            for syllable in result.syllables
        )

    if complexity != "simple":
        assert any(syllable[-1] not in "aeiou" for word in words for syllable in word.syllables)
    if complexity == "complex":
        assert any(
            re.match(r"sch|[bdfgklmnprst]{2}", syllable)
            for word in words
            for syllable in word.syllables
        )
        assert any("ei" in word.text or "au" in word.text for word in words)
    else:
        assert not any("ei" in word.text or "au" in word.text for word in words)


@pytest.mark.parametrize("count", [0, 1, 5, -1, "3", 2.5, None, True])
def test_invalid_syllable_counts_are_rejected(count):
    with pytest.raises(ValueError, match="Syllable count"):
        WordGenerator().generate(syllables=count)


@pytest.mark.parametrize("complexity", ["", "hard", "SIMPLE", None])
def test_unknown_complexity_is_rejected(complexity):
    with pytest.raises(ValueError, match="complexity"):
        WordGenerator().generate(complexity=complexity)


def test_generation_is_repeatable_with_an_injected_random_source():
    first = WordGenerator(rng=random.Random(7))
    second = WordGenerator(rng=random.Random(7))
    assert [first.generate(3, "complex") for _ in range(50)] == [
        second.generate(3, "complex") for _ in range(50)
    ]


def test_default_generation_does_not_reseed_or_consume_global_random_state():
    before = random.getstate()
    WordGenerator().generate()
    assert random.getstate() == before


def test_pathological_random_source_cannot_cause_unbounded_generation():
    class AlwaysFirstChoice:
        calls = 0

        def choices(self, population, **kwargs):
            self.calls += 1
            return [population[0]]

    rng = AlwaysFirstChoice()
    with pytest.raises(RuntimeError, match="readable syllable join"):
        WordGenerator(rng=rng).generate()
    assert rng.calls < 1000
