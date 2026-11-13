"""URL-carried word state and the transitions that produce the next view."""

from dataclasses import asdict, dataclass, replace
from math import isfinite

from .ScoreManager import ScoreManager
from .WordGenerator import DecodeConfig


@dataclass(frozen=True)
class WordState:
    config: str
    score: str
    fadeout: float  # Milliseconds; only the setup form uses seconds.
    capitalize: str
    code: str | None = None

    @classmethod
    def from_values(cls, values, *, seconds=False):
        config = values.get("config")
        try:
            DecodeConfig(config)
        except (AttributeError, TypeError, ValueError) as error:
            raise ValueError("Invalid configuration.") from error

        try:
            score = ScoreManager(values.get("score", "0:0")).GetScore()
        except Exception as error:
            raise ValueError("Invalid score.") from error

        try:
            fadeout = float(values.get("fadeout", 0)) * (1000 if seconds else 1)
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid visibility duration; use 0 to 10 seconds.") from error
        if not isfinite(fadeout) or not 0 <= fadeout <= 10000:
            raise ValueError("Invalid visibility duration; use 0 to 10 seconds.")

        capitalize = values.get("capitalize", "no")
        if capitalize not in ("yes", "no"):
            raise ValueError("Invalid upper-case preference.")

        return cls(config, score, fadeout, capitalize, values.get("code"))

    def as_values(self):
        """One representation for both URL parameters and hidden form inputs."""
        return asdict(self)

    def advance(self, generator):
        try:
            _, code = generator.MakeWord(self.config, self.capitalize)
        except Exception as error:
            raise ValueError("Unable to generate a word from this configuration.") from error
        scores = ScoreManager(self.score)
        scores.Succeeded()
        return replace(self, code=code, score=scores.GetScore())

    def retry(self, generator):
        self.word(generator)  # Reject missing or invalid codes before transitioning.
        scores = ScoreManager(self.score)
        scores.Failed()
        return replace(self, score=scores.GetScore())

    def word(self, generator):
        try:
            return generator.MakeWordFromCode(self.code, self.capitalize)
        except Exception as error:
            raise ValueError("Invalid word code.") from error
