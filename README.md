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

## Local development

```sh
python -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m flask --app src/main.py run --port 8008
```

Open http://localhost:8008. Port 8008 avoids the macOS AirPlay conflict on port 5000.

## Tests

```sh
PYTHONPATH=src .venv/bin/python -m pytest test -q
node --test test/word-timer-tests.cjs
```

The timer tests use Node's built-in test runner (Node 18+) and require no npm dependencies. Node is only needed for those tests, not to run the app.

## CI and deployment

`.github/workflows/tests.yml` runs both test suites on pushes and pull requests targeting `main`, using Python 3.10 and Node.js 22. It can also be run manually from GitHub Actions.

Railway's production source is configured to **Wait for CI** before deploying `main`. Keep that setting enabled so failed checks prevent deployment. The workflow itself does not deploy or need Railway credentials.
