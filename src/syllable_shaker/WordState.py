"""URL-carried state for stable word views and explicit scoring transitions."""

from dataclasses import asdict, dataclass, replace

from .Configuration import Configuration
from .ScoreManager import ScoreManager
from .URLToken import decode_payload, encode_payload
from .WordToken import decode_word, encode_word


@dataclass(frozen=True)
class WordState:
    syllables: int
    complexity: str
    score: str
    fadeout: float  # Milliseconds; only the setup form uses seconds.
    capitalize: str
    token: str | None = None

    @classmethod
    def from_values(cls, values, *, seconds=False):
        configuration = Configuration.from_values(values, seconds=seconds)
        try:
            score = ScoreManager(values.get("score", "0:0")).GetScore()
            if len(score) > 64:
                raise ValueError("Score is too long.")
        except Exception as error:
            raise ValueError("Invalid score.") from error

        return cls(**asdict(configuration), score=score, token=values.get("token"))

    @property
    def configuration(self):
        return Configuration(self.syllables, self.complexity, self.fadeout, self.capitalize)

    def to_token(self):
        """[word, syllables, complexity code, failures, successes, ms, uppercase]."""
        count, complexity, fadeout, capitalize = self.configuration.to_array()
        scores = ScoreManager(self.score)
        payload = [
            decode_word(self.token),
            count,
            complexity,
            scores.Fails,
            scores.Success,
            fadeout,
            capitalize,
        ]
        return encode_payload("v2", payload)

    @classmethod
    def from_token(cls, token):
        try:
            payload = decode_payload("v2", token)
            if len(payload) != 7:
                raise ValueError("Invalid view array.")
            word, syllables, complexity, failures, successes, fadeout, capitalize = payload
            if type(failures) is not int or type(successes) is not int:
                raise ValueError("Invalid score values.")
            configuration = Configuration.from_array([syllables, complexity, fadeout, capitalize])
            state = cls.from_values(
                {
                    **asdict(configuration),
                    "token": encode_word(word),
                    "score": f"{failures}:{successes}",
                }
            )
            if state.to_token() != token:
                raise ValueError("Noncanonical view token.")
        except (ValueError, TypeError) as error:
            raise ValueError("Invalid view token.") from error
        return state

    def advance(self, generator):
        result = generator.generate(self.syllables, self.complexity)
        scores = ScoreManager(self.score)
        scores.Succeeded()
        return replace(self, token=encode_word(result.text), score=scores.GetScore())

    def retry(self):
        self.word()  # Reject missing or invalid tokens before transitioning.
        scores = ScoreManager(self.score)
        scores.Failed()
        return replace(self, score=scores.GetScore())

    def word(self):
        word = decode_word(self.token)
        return word.upper() if self.capitalize == "yes" else word
