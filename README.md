[![Tests](https://github.com/skycler/random-word-generator/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/skycler/random-word-generator/actions/workflows/tests.yml)

# Syllable Shaker

A small Flask app that generates German-readable, invented words to practice with. Pick 2–4 syllables and a complexity, then step through words and keep score. A QR code lets you open the same word on another device.

## How it works

**Words** are built from weighted onset + vowel + coda syllables, with rules that avoid awkward joins (see `src/syllable_shaker/WordGenerator.py`). Complexity controls the patterns: *simple* is open syllables, *medium* adds endings, *complex* adds clusters like `sch` and diphthongs like `ei`. Output is meant to read naturally, not to be real German, and there's no dictionary filter.

**State lives in the URL.** There are no sessions or database. Each word page (`/word/v2.<token>`) carries its word, settings and score in a short token, so refreshing or sharing a link never changes the word or score. Actions (next, try again, create QR) are POST requests that redirect to the new page.

The token is Base64-encoded JSON. It hides the word from a casual glance, but it is **obfuscation, not encryption**: anyone can decode or edit it, so scores are not trustworthy.

## Development

Requires [uv](https://docs.astral.sh/uv/getting-started/installation/) 0.13.8 or newer. uv installs the pinned Python (3.15) for you. Node.js 24 is only needed for the JavaScript tests.

```sh
uv sync --locked
uv run --locked flask --app syllable_shaker run --debug --port 8008
```

Open http://localhost:8008 (port 8008 avoids the macOS AirPlay conflict on 5000).

```sh
uv run --locked ruff check .            # lint (format with: ruff format .)
uv run --locked pytest                  # Python tests, 90% coverage required
node --test tests/*.test.cjs            # JavaScript tests
```

`pyproject.toml` holds all project and tool configuration. Add dependencies with `uv add <package>` (or `--dev`) and commit the updated `uv.lock`.

## Docker

```sh
docker compose up --build app                       # http://localhost:8008
docker compose --profile dev up --build debug       # hot reload, http://localhost:8009
docker compose --profile test run --build --rm tests
```

The production image runs as a non-root user under Gunicorn and uses `PORT` (default 8000).

## CI and deployment

GitHub Actions (`.github/workflows/tests.yml`) runs lint, tests, a package build, and a smoke test of the production image on every push and pull request to `main`. Each run's summary page shows test results and coverage at a glance, including which tests failed. Dependabot proposes dependency updates weekly.

Production runs on Railway, which deploys `main` only after CI passes (its **Wait for CI** setting must stay enabled).
