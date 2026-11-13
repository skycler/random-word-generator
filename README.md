![master](https://github.com/basegpu/random-word-generator/actions/workflows/main.yml/badge.svg)

# random-word-generator
Based on a list of syllables, randomly generated words are displayed. Implemented as flask webapp.

## Navigation and rendering

The app uses Flask/Jinja server-rendered pages, with no client-side router or server-side session store.

- Setup and the next/retry actions use **POST → 303 redirect → GET**.
- `/word/<code>?config=...&score=...&fadeout=...&capitalize=...` identifies an exact word and score. Refreshing, bookmarking, or sharing it does not generate a new word or update the score.
- `/qr/<code>` with the same query parameters returns a QR image pointing to that stable word URL. Scans share the initial word; subsequent actions carry each browser's state independently.
- `WordState` owns input normalization, word reconstruction, scoring transitions, and the values used by URLs and hidden form inputs. Scores are client-carried state, not an authoritative server-side record.
- Existing `/next/...`, `/repeat/...`, and `/code/...` links remain compatibility adapters. Old action URLs still perform their original transition on arrival; the new UI uses only POST actions and stable GET views.
- `static/app.css` supplies the shared styles. `static/word.js` starts the visibility timer after DOM parsing and restarts it when a page is restored from the browser's back/forward cache. Navigation works without JavaScript, but timed hiding requires it.

Visibility durations are validated as finite values between 0 and 10 seconds. Setup uses seconds; URLs and hidden form inputs use milliseconds.

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
