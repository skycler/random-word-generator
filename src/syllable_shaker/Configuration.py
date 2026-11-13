"""Reusable setup preferences, independent of a word or its score."""

from dataclasses import dataclass
from math import isfinite

from .URLToken import decode_payload, encode_payload
from .WordGenerator import GenerationSettings


# Fixed protocol codes: 0 = simple, 1 = medium, 2 = complex.
_COMPLEXITIES = ("simple", "medium", "complex")


@dataclass(frozen=True)
class Configuration:
    syllables: int = 3
    complexity: str = "simple"
    fadeout: float = 0.0  # Milliseconds; the setup form displays seconds.
    capitalize: str = "no"

    @classmethod
    def from_values(cls, values, *, seconds=False):
        settings = GenerationSettings.from_values(values)
        try:
            fadeout = float(values.get("fadeout", 0)) * (1000 if seconds else 1)
        except (TypeError, ValueError) as error:
            raise ValueError("Invalid visibility duration; use 0 to 10 seconds.") from error
        if not isfinite(fadeout) or not 0 <= fadeout <= 10000:
            raise ValueError("Invalid visibility duration; use 0 to 10 seconds.")

        capitalize = values.get("capitalize", "no")
        if capitalize not in ("yes", "no"):
            raise ValueError("Invalid upper-case preference.")
        return cls(settings.syllables, settings.complexity, fadeout, capitalize)

    def to_array(self):
        """[syllables, complexity code, milliseconds, uppercase flag]."""
        milliseconds = int(self.fadeout) if float(self.fadeout).is_integer() else self.fadeout
        return [self.syllables, _COMPLEXITIES.index(self.complexity), milliseconds, int(self.capitalize == "yes")]

    @classmethod
    def from_array(cls, payload):
        if not isinstance(payload, list) or len(payload) != 4:
            raise ValueError("Invalid configuration array.")
        syllables, complexity, fadeout, capitalize = payload
        if (type(syllables) is not int or type(complexity) is not int
                or not 0 <= complexity < len(_COMPLEXITIES)
                or type(fadeout) not in (int, float)
                or type(capitalize) is not int or capitalize not in (0, 1)):
            raise ValueError("Invalid configuration array.")
        return cls.from_values({
            "syllables": syllables, "complexity": _COMPLEXITIES[complexity],
            "fadeout": fadeout, "capitalize": "yes" if capitalize else "no",
        })

    def to_token(self):
        return encode_payload("c2", self.to_array())

    @classmethod
    def from_token(cls, token):
        try:
            configuration = cls.from_array(decode_payload("c2", token))
            if configuration.to_token() != token:
                raise ValueError("Noncanonical configuration token.")
        except (ValueError, TypeError) as error:
            raise ValueError("Invalid configuration token.") from error
        return configuration
