"use strict";

function startWordTimer() {
    const word = document.getElementById("myWord");
    if (!word) return;

    const delay = Number(word.dataset.fadeout);
    if (!Number.isFinite(delay) || delay <= 0 || delay > 10000) return;

    const originalWord = word.textContent;
    let timer;

    function restartTimer() {
        window.clearTimeout(timer);
        word.hidden = false;
        word.textContent = originalWord;
        timer = window.setTimeout(() => {
            // Keep the word stage in the layout, but remove the word itself.
            word.hidden = true;
            word.textContent = "";
        }, delay);
    }

    restartTimer();
    window.addEventListener("pageshow", (event) => {
        // Back/forward caching restores the DOM, including its hidden state.
        if (event.persisted) restartTimer();
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", startWordTimer, { once: true });
} else {
    startWordTimer();
}
