from flask import redirect, render_template, request, send_file, url_for
from werkzeug.exceptions import BadRequest

from syllable_shaker import app, generator
from .WordState import WordState
from .utils import make_qr_code


def read_state(values, *, seconds=False):
    try:
        return WordState.from_values(values, seconds=seconds)
    except ValueError as error:
        raise BadRequest(str(error)) from error


def transition(state, *, retry=False):
    try:
        return state.retry(generator) if retry else state.advance(generator)
    except ValueError as error:
        raise BadRequest(str(error)) from error


def word_url(state, *, external=False):
    return url_for("show_word", **state.as_values(), _external=external)


def redirect_to_word(state, *, qr=False):
    location = url_for("show_qr", **state.as_values()) if qr else word_url(state)
    return redirect(location, code=303)


def qr_response(state):
    try:
        state.word(generator)
    except ValueError as error:
        raise BadRequest(str(error)) from error
    return send_file(make_qr_code(word_url(state, external=True)), mimetype="image/png")


@app.route("/", methods=["POST", "GET"])
@app.route("/index", methods=["POST", "GET"])
def index():
    if request.method == "GET":
        return render_template("index.html")

    state = read_state({
        "config": request.form.get("config"),
        "fadeout": request.form.get("fadeout"),
        "score": "0:-1",
        "capitalize": "yes" if request.form.get("capitalize") else "no",
    }, seconds=True)
    state = transition(state)
    # The QR code identifies the same stable initial view as ordinary setup.
    return redirect_to_word(state, qr=bool(request.form.get("qr")))


@app.get("/word/<code>")
def show_word(code):
    state = read_state({**request.args, "code": code})
    try:
        word = state.word(generator)
    except ValueError as error:
        raise BadRequest(str(error)) from error
    return render_template("word.html", state=state, word=word)


@app.get("/qr/<code>")
def show_qr(code):
    return qr_response(read_state({**request.args, "code": code}))


@app.post("/next")
def next_word():
    return redirect_to_word(transition(read_state(request.form)))


@app.post("/repeat")
def same_word():
    return redirect_to_word(transition(read_state(request.form), retry=True))


# Compatibility adapters for existing bookmarks and printed QR codes. New UI
# actions only use POST; old action URLs redirect to a stable view on arrival.
@app.get("/next/<config>/<score>")
@app.get("/next/<config>/<score>/<fadeout>")
@app.get("/next/<config>/<score>/<fadeout>/<capitalize>")
def legacy_next_word(config, score, fadeout=0.0, capitalize="no"):
    state = read_state({"config": config, "score": score, "fadeout": fadeout, "capitalize": capitalize})
    return redirect_to_word(transition(state))


@app.get("/repeat/<code>/<config>/<score>")
@app.get("/repeat/<code>/<config>/<score>/<fadeout>")
@app.get("/repeat/<code>/<config>/<score>/<fadeout>/<capitalize>")
def legacy_same_word(code, config, score, fadeout=0.0, capitalize="no"):
    state = read_state({"code": code, "config": config, "score": score, "fadeout": fadeout, "capitalize": capitalize})
    return redirect_to_word(transition(state, retry=True))


@app.get("/code/<config>/<score>/<fadeout>/<capitalize>")
def make_code(config, score, fadeout, capitalize):
    state = read_state({"config": config, "score": score, "fadeout": fadeout, "capitalize": capitalize})
    return qr_response(transition(state))
