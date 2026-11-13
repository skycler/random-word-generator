const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const { test } = require("node:test");
const { runInNewContext } = require("node:vm");

const source = readFileSync(resolve(__dirname, "../src/syllable_shaker/static/word.js"), "utf8");

function page({ delay = "250", readyState = "complete", missingWord = false } = {}) {
    const word = { dataset: { fadeout: delay }, hidden: false, textContent: "ander" };
    const documentEvents = new Map();
    const windowEvents = new Map();
    const timers = new Map();
    let nextTimer = 0;
    const document = {
        readyState,
        getElementById(id) {
            assert.equal(id, "myWord");
            return missingWord ? null : word;
        },
        addEventListener(name, callback) { documentEvents.set(name, callback); },
    };
    const window = {
        setTimeout(callback, delay) {
            timers.set(++nextTimer, { callback, delay });
            return nextTimer;
        },
        clearTimeout(id) { timers.delete(id); },
        addEventListener(name, callback) { windowEvents.set(name, callback); },
    };
    runInNewContext(source, { document, window });
    return {
        word, timers,
        ready() { documentEvents.get("DOMContentLoaded")(); },
        restore() { windowEvents.get("pageshow")({ persisted: true }); },
        expire() {
            assert.equal(timers.size, 1);
            const [id, timer] = timers.entries().next().value;
            timers.delete(id);
            timer.callback();
        },
    };
}

test("waits for the DOM, then hides and clears only the word after the configured delay", () => {
    const view = page({ readyState: "loading" });
    assert.equal(view.timers.size, 0);
    view.ready();
    assert.equal(view.timers.size, 1);
    assert.equal([...view.timers.values()][0].delay, 250);
    assert.equal(view.word.hidden, false);
    assert.equal(view.word.textContent, "ander");
    view.expire();
    assert.equal(view.word.hidden, true);
    assert.equal(view.word.textContent, "");
});

test("starts immediately when a deferred script runs after DOM parsing", () => {
    const view = page({ readyState: "interactive", delay: "10000" });
    assert.equal(view.timers.size, 1);
    assert.equal([...view.timers.values()][0].delay, 10000);
});

for (const delay of ["0", "", "-1", "NaN", "Infinity", "invalid", "10001"]) {
    test(`does not hide the word for disabled or invalid delay: ${JSON.stringify(delay)}`, () => {
        const view = page({ delay });
        assert.equal(view.timers.size, 0);
        assert.equal(view.word.hidden, false);
        assert.equal(view.word.textContent, "ander");
    });
}

test("does nothing if there is no word element", () => {
    assert.equal(page({ missingWord: true }).timers.size, 0);
});

test("back/forward cache restoration restores the word and restarts its timer", () => {
    const view = page();
    view.expire();
    assert.equal(view.word.hidden, true);
    view.restore();
    assert.equal(view.word.hidden, false);
    assert.equal(view.word.textContent, "ander");
    assert.equal(view.timers.size, 1);
    view.restore();
    assert.equal(view.timers.size, 1, "Restoration must replace, not duplicate, the timer");
    view.expire();
    assert.equal(view.word.hidden, true);
});
