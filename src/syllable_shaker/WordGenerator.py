"""Weighted syllable construction for German-readable invented words."""

from dataclasses import dataclass
import random


@dataclass(frozen=True)
class GenerationSettings:
    syllables: int = 3
    complexity: str = "simple"

    def __post_init__(self):
        if type(self.syllables) is not int or not 2 <= self.syllables <= 4:
            raise ValueError("Syllable count must be a whole number from 2 to 4.")
        if self.complexity not in ("simple", "medium", "complex"):
            raise ValueError("Unknown complexity; choose simple, medium, or complex.")

    @classmethod
    def from_values(cls, values):
        raw_count = values.get("syllables", 3)
        try:
            if type(raw_count) not in (str, int):
                raise ValueError("Not an integer")
            count = int(raw_count)
        except (TypeError, ValueError) as error:
            raise ValueError("Syllable count must be a whole number from 2 to 4.") from error
        return cls(count, values.get("complexity", "simple"))


@dataclass(frozen=True)
class GeneratedWord:
    syllables: tuple[str, ...]

    @property
    def text(self):
        return "".join(self.syllables)


class WordGenerator:
    # Spellings with straightforward German readings; deliberately no c/v/q/x/y.
    _onsets = (("b", 2), ("d", 2), ("f", 2), ("g", 1), ("k", 3), ("l", 5),
               ("m", 5), ("n", 5), ("p", 2), ("r", 3), ("s", 2), ("t", 4))
    _vowels = (("a", 5), ("e", 3), ("i", 4), ("o", 4), ("u", 3))
    _clusters = tuple((part, 1) for part in
                      ("bl", "br", "dr", "fl", "fr", "gl", "gr", "kl", "kr", "pl", "pr", "tr", "sch"))
    _diphthongs = (("ei", 1), ("au", 1))
    _internal_codas = (("", 16), ("n", 2), ("m", 1), ("l", 1), ("r", 1))
    _final_codas = (("", 5), ("n", 3), ("m", 1), ("l", 2), ("r", 2))
    _complex_codas = (("s", 1), ("t", 1), ("k", 1), ("f", 1))

    # A small, explicit set of readable cross-syllable consonant joins.
    # No doubled consonants, n+g, or coda followed by a two-sound cluster.
    _joins = {
        "n": ("d", "t", "k", "s", "sch"),
        "m": ("b", "p"),
        "l": ("b", "d", "f", "g", "k", "m", "n", "p", "s", "t", "sch"),
        "r": ("b", "d", "f", "g", "k", "l", "m", "n", "p", "s", "t", "sch"),
    }

    def __init__(self, *, rng=None):
        self._rng = rng if rng is not None else random.SystemRandom()

    def _choose(self, inventory):
        parts, weights = zip(*inventory)
        return self._rng.choices(parts, weights=weights, k=1)[0]

    def generate(self, syllables=3, complexity="simple"):
        settings = GenerationSettings(syllables, complexity)
        onsets = self._onsets + (self._clusters if settings.complexity == "complex" else ())
        vowels = self._vowels + (self._diphthongs if settings.complexity == "complex" else ())
        parts = []
        for position in range(settings.syllables):
            if settings.complexity == "simple":
                codas = (("", 1),)
                starts = onsets
            else:
                # Vowel-initial syllables are only allowed at the start of a word.
                starts = onsets + ((("", 3),) if position == 0 else ())
                codas = self._final_codas if position == settings.syllables - 1 else self._internal_codas
                if settings.complexity == "complex" and position == settings.syllables - 1:
                    codas += self._complex_codas

            for _ in range(64):
                onset = self._choose(starts)
                candidate = onset + self._choose(vowels) + self._choose(codas)
                previous = parts[-1] if parts else ""
                if previous and previous[-1] not in "aeiou" and onset not in self._joins[previous[-1]]:
                    continue
                if candidate == previous:
                    continue
                parts.append(candidate)
                break
            else:
                # Bound the work even when a supplied random source is pathological.
                raise RuntimeError("Unable to construct a readable syllable join.")

        return GeneratedWord(tuple(parts))
