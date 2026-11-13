const assert = require("node:assert/strict");
const { readFileSync } = require("node:fs");
const { resolve } = require("node:path");
const { test } = require("node:test");
const { runInNewContext } = require("node:vm");

const source = readFileSync(resolve(__dirname, "../src/syllable_shaker/static/setup.js"), "utf8");

function emitter() {
    const listeners = new Map();
    return {
        addEventListener(name, callback) { listeners.set(name, callback); },
        emit(name, event = {}) { const callback = listeners.get(name); return callback && callback(event); },
    };
}

function button(value) {
    const attributes = new Map();
    return {
        value,
        setAttribute(name, content) { attributes.set(name, content); },
        removeAttribute(name) { attributes.delete(name); },
        busy: () => attributes.get("aria-busy") === "true",
    };
}

const PNG = { type: "image/png", size: 9, slice() { throw new Error("not needed for a PNG"); } };

function element() {
    const attributes = new Map();
    return Object.assign(emitter(), {
        hidden: true,
        textContent: "",
        setAttribute(name, value) { attributes.set(name, value); },
        removeAttribute(name) { attributes.delete(name); },
        hasAttribute: (name) => attributes.has(name),
    });
}

function response({ ok = true, type = "image/png", blob = PNG } = {}) {
    return {
        ok,
        headers: { get: (name) => (name === "Content-Type" ? type : null) },
        blob: async () => blob,
    };
}

function page({
    fetchImpl, showModal = true, missing = [], readyState = "complete",
    clipboard = true, writeImpl = async () => {},
} = {}) {
    const fields = [["syllables", "3"], ["complexity", "simple"], ["action", "word"]];
    const log = { fetches: [], created: [], revoked: [], shown: 0, closed: 0, native: [], written: [], items: [] };
    const timers = new Map();
    let nextTimer = 0;
    let bypassSeen = [];

    const form = Object.assign(emitter(), {
        // Real browsers expose the controls named "action" here, shadowing the URL.
        action: { toString: () => "[object RadioNodeList]" },
        getAttribute: (name) => (name === "action" ? "/index" : null),
        requestSubmit(submitter) {
            // Real browsers dispatch submit synchronously, then navigate unless prevented.
            const event = { submitter, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
            const result = form.emit("submit", event);
            bypassSeen.push(event.defaultPrevented);
            if (!event.defaultPrevented) log.native.push(submitter);
            return result;
        },
    });
    const dialog = Object.assign(emitter(), {
        close() { log.closed++; dialog.emit("close"); },
    });
    if (showModal) dialog.showModal = () => { log.shown++; };
    const image = {
        src: undefined,
        removeAttribute(name) { if (name === "src") this.src = undefined; },
    };
    const copyButton = element();
    const status = element();
    const elements = {
        "setup-form": form, "qr-dialog": dialog, "qr-image": image,
        "qr-copy": copyButton, "qr-status": status,
    };
    for (const id of missing) delete elements[id];

    const documentEvents = new Map();
    const document = {
        readyState,
        getElementById: (id) => elements[id] ?? null,
        addEventListener(name, callback) { documentEvents.set(name, callback); },
    };
    class FakeFormData {
        constructor(target) { this.target = target; }
        [Symbol.iterator]() { return fields[Symbol.iterator](); }
    }
    class FakeClipboardItem {
        constructor(data) { this.data = data; log.items.push(data); }
    }
    const context = {
        document, URLSearchParams, FormData: FakeFormData,
        setTimeout(callback, delay) { timers.set(++nextTimer, { callback, delay }); return nextTimer; },
        clearTimeout(id) { timers.delete(id); },
        ...(clipboard ? {
            ClipboardItem: FakeClipboardItem,
            navigator: { clipboard: { write: async (items) => { log.written.push(items); return writeImpl(items); } } },
        } : {}),
        URL: {
            createObjectURL(blob) { log.created.push(blob); return "blob:" + log.created.length; },
            revokeObjectURL(url) { log.revoked.push(url); },
        },
        fetch: fetchImpl && (async (url, options) => { log.fetches.push({ url, options }); return fetchImpl(url, options); }),
    };
    runInNewContext(source, context);

    return {
        form, dialog, image, log, documentEvents, copyButton, status, timers,
        expireStatus() {
            assert.equal(timers.size, 1, "exactly one pending status timer");
            const [id, timer] = timers.entries().next().value;
            timers.delete(id);
            timer.callback();
            return timer.delay;
        },
        click: () => copyButton.emit("click"),
        async submit(submitter) {
            const event = { submitter, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
            await form.emit("submit", event);
            return event;
        },
        bypassSeen: () => bypassSeen,
    };
}

test("Create QR code fetches the image and opens the modal without navigating", async () => {
    const view = page({ fetchImpl: async () => response() });
    const qr = button("qr");
    const event = await view.submit(qr);

    assert.equal(event.defaultPrevented, true);
    assert.equal(view.log.fetches.length, 1);
    const { url, options } = view.log.fetches[0];
    assert.equal(url, "/index");
    assert.equal(options.method, "POST");
    // The button's own value is forced, since FormData excludes the submitter.
    const sent = new URLSearchParams(options.body);
    assert.equal(sent.get("action"), "qr");
    assert.equal(sent.get("syllables"), "3");
    assert.equal(sent.get("complexity"), "simple");
    assert.deepEqual(view.log.created, [PNG]);
    assert.equal(view.image.src, "blob:1");
    assert.equal(view.log.shown, 1);
    assert.equal(qr.busy(), false);
    assert.deepEqual(view.log.native, []);
});

test("the Go! button is left to normal form submission", async () => {
    const view = page({ fetchImpl: async () => response() });
    for (const submitter of [button("word"), undefined, button("")]) {
        const event = await view.submit(submitter);
        assert.equal(event.defaultPrevented, false);
    }
    assert.equal(view.log.fetches.length, 0);
});

test("the button shows a busy state while the request is pending", async () => {
    let release;
    const view = page({ fetchImpl: () => new Promise((resolve) => { release = () => resolve(response()); }) });
    const qr = button("qr");
    const submission = view.submit(qr);
    assert.equal(qr.busy(), true);
    release();
    await submission;
    assert.equal(qr.busy(), false);
});

test("repeated clicks while a request is pending are ignored", async () => {
    let release;
    const view = page({ fetchImpl: () => new Promise((resolve) => { release = () => resolve(response()); }) });
    const first = view.submit(button("qr"));
    const second = await view.submit(button("qr"));
    assert.equal(second.defaultPrevented, true);
    assert.equal(view.log.fetches.length, 1);
    release();
    await first;
    assert.equal(view.log.shown, 1);
});

for (const [name, fetchImpl] of [
    ["a server error", async () => response({ ok: false, type: "text/html" })],
    ["a non-image response", async () => response({ type: "text/html; charset=utf-8" })],
    ["a network failure", async () => { throw new TypeError("offline"); }],
]) {
    test(`falls back to a normal submission after ${name}`, async () => {
        const view = page({ fetchImpl });
        const qr = button("qr");
        await view.submit(qr);

        assert.equal(view.log.shown, 0);
        assert.equal(view.image.src, undefined);
        // The retried submission must not be intercepted again, or it would loop.
        assert.deepEqual(view.log.native, [qr]);
        assert.deepEqual(view.bypassSeen(), [false]);
        assert.equal(view.log.fetches.length, 1);
        assert.equal(qr.busy(), false);
        // Intercepting works again afterwards.
        const next = await view.submit(button("qr"));
        assert.equal(next.defaultPrevented, true);
    });
}

test("closing the dialog releases the image and its object URL", async () => {
    const view = page({ fetchImpl: async () => response() });
    await view.submit(button("qr"));
    view.dialog.emit("close");
    assert.deepEqual(view.log.revoked, ["blob:1"]);
    assert.equal(view.image.src, undefined);
    view.dialog.emit("close");
    assert.deepEqual(view.log.revoked, ["blob:1"], "must not revoke twice");
});

test("a second QR code replaces and releases the first", async () => {
    const view = page({ fetchImpl: async () => response() });
    await view.submit(button("qr"));
    await view.submit(button("qr"));
    assert.deepEqual(view.log.revoked, ["blob:1"]);
    assert.equal(view.image.src, "blob:2");
});

test("clicking the backdrop closes, but clicks inside do not", async () => {
    const view = page({ fetchImpl: async () => response() });
    const inside = {};
    view.dialog.emit("pointerdown", { target: inside });
    view.dialog.emit("click", { target: inside });
    assert.equal(view.log.closed, 0);

    view.dialog.emit("pointerdown", { target: view.dialog });
    view.dialog.emit("click", { target: view.dialog });
    assert.equal(view.log.closed, 1);
});

test("a drag that starts inside and ends on the backdrop does not close", () => {
    const view = page({ fetchImpl: async () => response() });
    view.dialog.emit("pointerdown", { target: {} });
    view.dialog.emit("click", { target: view.dialog });
    assert.equal(view.log.closed, 0);
});

test("a stale backdrop press does not close on a later click", () => {
    const view = page({ fetchImpl: async () => response() });
    view.dialog.emit("pointerdown", { target: view.dialog });
    view.dialog.emit("click", { target: view.dialog });
    view.dialog.emit("click", { target: view.dialog });
    assert.equal(view.log.closed, 1);
});

test("does nothing, leaving normal submission, without dialog or fetch support", async () => {
    for (const options of [
        { showModal: false, fetchImpl: async () => response() },
        { fetchImpl: undefined },
        { missing: ["qr-dialog"], fetchImpl: async () => response() },
        { missing: ["qr-image"], fetchImpl: async () => response() },
        { missing: ["setup-form"], fetchImpl: async () => response() },
    ]) {
        const view = page(options);
        const event = await view.submit(button("qr"));
        assert.equal(event.defaultPrevented, false, JSON.stringify(Object.keys(options)));
        assert.equal(view.log.fetches.length, 0);
    }
});

test("waits for the DOM before wiring the form", () => {
    const view = page({ readyState: "loading", fetchImpl: async () => response() });
    assert.equal(view.documentEvents.size, 1);
});

test("the copy button stays hidden where images cannot be copied", () => {
    for (const options of [
        { clipboard: false },
        { missing: ["qr-copy"] },
        { missing: ["qr-status"] },
    ]) {
        const view = page({ fetchImpl: async () => response(), ...options });
        assert.equal(view.copyButton.hidden, true, JSON.stringify(Object.keys(options)));
    }
    assert.equal(page({ fetchImpl: async () => response() }).copyButton.hidden, false);
});

test("copy puts only the PNG image on the clipboard", async () => {
    const view = page({ fetchImpl: async () => response() });
    await view.submit(button("qr"));
    await view.click();

    assert.equal(view.log.written.length, 1);
    assert.equal(view.log.written[0].length, 1, "a single clipboard item");
    // Exactly one flavour, so no link or text can come along with it.
    assert.deepEqual(view.log.items.map((data) => Object.keys(data)), [["image/png"]]);
    assert.equal(view.log.items[0]["image/png"], PNG);
    assert.equal(view.status.textContent, "QR code copied");
    assert.equal(view.status.hasAttribute("data-error"), false);
});

test("the copied confirmation disappears after a moment", async () => {
    const view = page({ fetchImpl: async () => response() });
    await view.submit(button("qr"));
    await view.click();
    assert.equal(view.expireStatus(), 2500);
    assert.equal(view.status.textContent, "");
});

test("copying twice keeps a single status timer", async () => {
    const view = page({ fetchImpl: async () => response() });
    await view.submit(button("qr"));
    await view.click();
    await view.click();
    assert.equal(view.timers.size, 1);
    assert.equal(view.log.written.length, 2);
});

test("a clipboard failure shows an error, and a retry on the same dialog recovers", async () => {
    let attempts = 0;
    const view = page({
        fetchImpl: async () => response(),
        writeImpl: async () => {
            if (++attempts === 1) throw new DOMException("denied", "NotAllowedError");
        },
    });
    await view.submit(button("qr"));
    await view.click();
    assert.equal(view.status.textContent, "Couldn't copy. Try again.");
    assert.equal(view.status.hasAttribute("data-error"), true);

    await view.click();
    assert.equal(view.status.textContent, "QR code copied");
    assert.equal(view.status.hasAttribute("data-error"), false);
    assert.equal(view.timers.size, 1);
});

test("a PNG delivered with a different blob type is relabelled before copying", async () => {
    const sliced = [];
    const odd = {
        type: "image/png; charset=binary", size: 9,
        slice(start, end, type) { sliced.push([start, end, type]); return { type, size: 9 }; },
    };
    const view = page({ fetchImpl: async () => response({ blob: odd }) });
    await view.submit(button("qr"));
    await view.click();
    assert.deepEqual(sliced, [[0, 9, "image/png"]]);
    assert.equal(view.log.items[0]["image/png"].type, "image/png");
});

test("copy does nothing when there is no QR code, or after the dialog closes", async () => {
    const view = page({ fetchImpl: async () => response() });
    await view.click();
    assert.equal(view.log.written.length, 0);

    await view.submit(button("qr"));
    view.dialog.emit("close");
    await view.click();
    assert.equal(view.log.written.length, 0);
    assert.equal(view.status.textContent, "");
});

test("closing the dialog clears any copy status and its timer", async () => {
    const view = page({ fetchImpl: async () => response() });
    await view.submit(button("qr"));
    await view.click();
    view.dialog.emit("close");
    assert.equal(view.status.textContent, "");
    assert.equal(view.timers.size, 0);
});
