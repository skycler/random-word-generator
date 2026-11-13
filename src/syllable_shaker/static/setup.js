"use strict";

function setupQrOverlay() {
    const form = document.getElementById("setup-form");
    const dialog = document.getElementById("qr-dialog");
    const image = document.getElementById("qr-image");
    const copyButton = document.getElementById("qr-copy");
    const status = document.getElementById("qr-status");
    // Without these features the form still works: the button just opens the PNG.
    if (!form || !dialog || !image || typeof dialog.showModal !== "function"
        || typeof fetch !== "function") return;

    let pending = false;
    let bypass = false;
    let objectUrl = null;
    let currentBlob = null;
    let statusTimer = null;
    let pressedBackdrop = false;

    // Copying images needs the async clipboard API (secure contexts only).
    const canCopy = Boolean(copyButton && status && typeof ClipboardItem === "function"
        && typeof navigator !== "undefined" && navigator.clipboard
        && typeof navigator.clipboard.write === "function");
    if (canCopy) copyButton.hidden = false;

    function say(message, isError = false) {
        clearTimeout(statusTimer);
        status.textContent = message;
        if (isError) status.setAttribute("data-error", "");
        else status.removeAttribute("data-error");
        if (message) statusTimer = setTimeout(() => say(""), 2500);
    }

    function clearImage() {
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        objectUrl = null;
        currentBlob = null;
        image.removeAttribute("src");
        if (status) say("");
    }

    function submitNormally(submitter) {
        // Let the browser and server handle it, including validation errors.
        bypass = true;
        try {
            form.requestSubmit(submitter);
        } finally {
            bypass = false;
        }
    }

    form.addEventListener("submit", async (event) => {
        const submitter = event.submitter;
        if (bypass || !submitter || submitter.value !== "qr") return;
        event.preventDefault();
        if (pending) return;

        pending = true;
        // aria-busy rather than disabled, so the button keeps focus for the dialog to restore.
        submitter.setAttribute("aria-busy", "true");
        try {
            const body = new URLSearchParams(new FormData(form));
            body.set("action", "qr");
            // Not form.action: the buttons are named "action", which shadows that property.
            const response = await fetch(form.getAttribute("action"), { method: "POST", body });
            const type = response.headers.get("Content-Type") || "";
            if (!response.ok || !type.startsWith("image/png")) {
                submitNormally(submitter);
                return;
            }
            const blob = await response.blob();
            clearImage();
            currentBlob = blob;
            objectUrl = URL.createObjectURL(blob);
            image.src = objectUrl;
            dialog.showModal();
        } catch {
            submitNormally(submitter);
        } finally {
            pending = false;
            submitter.removeAttribute("aria-busy");
        }
    });

    if (canCopy) {
        copyButton.addEventListener("click", async () => {
            if (!currentBlob) return;
            try {
                // The image alone: no link or text goes on the clipboard.
                const png = currentBlob.type === "image/png"
                    ? currentBlob : currentBlob.slice(0, currentBlob.size, "image/png");
                await navigator.clipboard.write([new ClipboardItem({ "image/png": png })]);
                say("QR code copied");
            } catch {
                say("Couldn't copy. Try again.", true);
            }
        });
    }

    dialog.addEventListener("close", clearImage);
    // Only a press and release that both land on the backdrop count as a dismissal.
    dialog.addEventListener("pointerdown", (event) => {
        pressedBackdrop = event.target === dialog;
    });
    dialog.addEventListener("click", (event) => {
        if (pressedBackdrop && event.target === dialog) dialog.close();
        pressedBackdrop = false;
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setupQrOverlay, { once: true });
} else {
    setupQrOverlay();
}
