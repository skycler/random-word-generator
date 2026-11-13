[![Tests](https://github.com/skycler/random-word-generator/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/skycler/random-word-generator/actions/workflows/tests.yml)

# Syllable Shaker

A Flask web app generating German-readable, neutral-sounding invented words.

## Word generation

Words are constructed from weighted **onsets + vowel nuclei + codas**, not selected from a syllable CSV. Choose 2–4 syllables and a complexity level:

| Complexity | Patterns |
|---|---|
| Simple | Open consonant–vowel syllables, using `a e i o u` and common consonants |
| Medium | Adds occasional endings in `n m l r`, and occasional vowel-initial starts |
| Complex | Adds selected clusters (including `sch`) and diphthongs (`ei`, `au`), plus more final endings |

Internal syllables are mostly open; endings are more common at the end of a word. Cross-syllable rules reject vowel collisions, doubled consonants, adjacent identical syllables, ambiguous `n` + `g` joins, and excessive consonant runs. `sch` is treated as one sound. Each syllable has at most 64 sampling attempts, so generation cannot loop indefinitely.

`WordGenerator.generate()` returns a `GeneratedWord` with its syllable segmentation and joined `text`. The inventories and weights live in `src/syllable_shaker/WordGenerator.py`. A random source can be injected for reproducible tests; normal generation uses an independent `SystemRandom` source.

The goal is straightforward German-style reading, not perfect phonetic transcription. Ordinary spelling does not fully specify vowel length or stress. Some outputs may coincide with real words; there is no dictionary filter.

## Navigation and word tokens

The app uses Flask/Jinja server-rendered pages, with no client-side router or server-side session store.

- Setup and the next/retry actions use **POST → 303 redirect → GET**.
- `/word/v2.<token>` identifies an exact word, score, and set of preferences, with **no query parameters**. Refreshing, bookmarking, or sharing it does not generate a new word or update the score.
- The token is **unpadded URL-safe Base64 of a compact UTF-8 JSON array**: `[word, syllables, complexity, failures, successes, milliseconds, uppercase]`. Complexity codes are `0` = simple, `1` = medium, `2` = complex; uppercase is `0` or `1`. Whole milliseconds are stored as integers, while fractional values are preserved. The `v2.` prefix identifies the serialization format. This hides the word and settings from a casual glance at the address bar; it is **obfuscation, not encryption or a signature**. Anyone can decode and edit it.
- `URLToken` supplies bounded, canonical Base64-JSON-array encoding for both view and setup URLs. `WordState` validates view fields; `Configuration` validates preferences; `WordToken` validates decoded words. Invalid tokens return HTTP 400. Decoding does not depend on inventories or generation rules, so changing the generator does not change existing token contents.
- Uppercase is applied only when displaying the decoded word. Next/retry forms carry one hidden `state` token, not separate settings or the literal word. Retry preserves the word but produces a new view token recording the updated score.
- `/qr/v2.<token>` returns a QR image pointing to the stable word URL with that same state token. Scans share the initial word; subsequent actions carry each browser's state independently.
- Word-only links and previous object-based `v1`/`c1` tokens are not supported; there are no migration redirects. Query parameters on a state-token URL cannot override its contents and are stripped by redirect.
- `WordState` owns input normalization, serialization, and scoring transitions. Scores are client-carried state, not an authoritative server-side record.
- The top-left icon and title form a keyboard-accessible Home link. From a word view, it opens `/setup/c2.<token>` with the same syllable count, complexity, visibility duration, and uppercase preference prefilled. Its compact array is `[syllables, complexity, milliseconds, uppercase]`, containing neither word nor score. Starting from setup creates a fresh session at `0:0`; clicking Home again on setup preserves its configuration.
- `static/app.css` supplies the shared styles. `static/word.js` starts the visibility timer after DOM parsing and restarts it when a page is restored from the browser's back/forward cache. Navigation works without JavaScript, but timed hiding requires it.

The old character-length configuration, list-index word codes, and legacy `/next/...`, `/repeat/...`, and `/code/...` routes have intentionally been removed. Old bookmarks and printed QR codes using those formats, or word-only tokens, are not supported.

Visibility durations are validated as finite values between 0 and 10 seconds. Setup uses seconds; encoded view state stores milliseconds.

## Toolchain and local development

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) **0.13.8 or newer** and Node.js 24 (only needed for JavaScript tests). Upgrade an existing standalone uv installation with `uv self update`. Python 3.14 is selected by the tracked `.python-version`; uv can install it automatically.

`pyproject.toml` is the source of truth for package metadata, dependencies, development tools, pytest, coverage, and Ruff. Commit `uv.lock` when dependencies change; local development, CI, and Docker use the same locked versions from PyPI.

```sh
uv sync --locked
uv run --locked flask --app syllable_shaker run --debug --port 8008
```

Open http://localhost:8008. Port 8008 avoids the macOS AirPlay conflict on port 5000. The package is installed in editable mode for development; no `PYTHONPATH` setup is needed.

To add or update dependencies:

```sh
uv add <package>
uv add --dev <tool>
uv lock --upgrade
uv sync --locked
```

## Checks and tests

Tests live in `tests/test_*.py` and use pytest's standard discovery. JavaScript timer tests use Node's built-in runner with no npm dependencies.

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest -q
node --test tests/*.test.cjs
```

Apply formatting with `uv run --locked ruff format .`. For branch coverage:

```sh
uv run --locked pytest --cov=syllable_shaker --cov-report=term-missing
```

Coverage runs require at least 90% coverage, configured in `pyproject.toml`.

## Packaging and Docker

```sh
uv build
```

The uv build backend creates a source distribution and wheel in `dist/`, including the package's HTML templates, CSS, and JavaScript. Package metadata starts at version `0.1.0` in `pyproject.toml`.

The multi-stage Dockerfile uses Python 3.14 on Debian Trixie and pinned uv. Production installs only runtime dependencies and the non-editable package, runs as a non-root user, and starts `syllable_shaker:app` with Gunicorn. `PORT` defaults to 8000 and honors Railway's supplied value.

```sh
docker compose up --build app                     # http://localhost:8008
docker compose --profile dev up --build debug     # hot reload at http://localhost:8009
docker compose --profile test run --build --rm tests
```

The Docker test target runs Python tests; run JavaScript tests separately with Node or in CI. Python test reports are written to `.reports/` when using Compose. `.dockerignore` excludes Git metadata, local environments, secrets, caches, and build artifacts.

## CI and deployment

`.github/workflows/tests.yml` runs on pushes and pull requests targeting `main`, and can also be run manually. CI uses uv's locked dependencies, Python 3.14, and Node.js 24. It checks Ruff lint/formatting, runs Python tests with coverage and JavaScript timer tests, builds distributions, and builds/smoke-tests the non-root production image and its packaged assets.

GitHub Actions are pinned to commit SHAs. Dependabot checks uv dependencies, Actions, and Docker images weekly.

Railway's production source is configured to **Wait for CI** before deploying `main`. Keep that setting enabled so failed checks prevent deployment. The workflow itself does not deploy or need Railway credentials.
