from flask import redirect, render_template, request, send_file, url_for
from werkzeug.exceptions import BadRequest

from syllable_shaker import app, generator

from .Configuration import Configuration
from .utils import make_qr_code
from .WordState import WordState


def read_state(values, *, seconds=False):
    try:
        return WordState.from_values(values, seconds=seconds)
    except ValueError as error:
        raise BadRequest(str(error)) from error


def read_view_state(token):
    try:
        return WordState.from_token(token)
    except ValueError as error:
        raise BadRequest(str(error)) from error


def transition(state, *, retry=False):
    try:
        return state.retry() if retry else state.advance(generator)
    except ValueError as error:
        raise BadRequest(str(error)) from error


def word_url(state, *, external=False):
    return url_for("show_word", token=state.to_token(), _external=external)


def redirect_to_word(state, *, qr=False):
    location = url_for("show_qr", token=state.to_token()) if qr else word_url(state)
    return redirect(location, code=303)


def qr_response(state):
    try:
        state.word()
    except ValueError as error:
        raise BadRequest(str(error)) from error
    return send_file(make_qr_code(word_url(state, external=True)), mimetype="image/png")


@app.get("/setup/<configuration_token>")
@app.route("/", methods=["POST", "GET"])
@app.route("/index", methods=["POST", "GET"])
def index(configuration_token=None):
    if request.method == "GET":
        try:
            configuration = (
                Configuration.from_token(configuration_token)
                if configuration_token
                else Configuration()
            )
        except ValueError as error:
            raise BadRequest(str(error)) from error
        return render_template("index.html", configuration=configuration)

    action = request.form.get("action", "word")
    if action not in ("word", "qr"):
        raise BadRequest("Unknown action.")

    state = read_state(
        {
            "syllables": request.form.get("syllables"),
            "complexity": request.form.get("complexity"),
            "fadeout": request.form.get("fadeout"),
            "score": "0:-1",
            "capitalize": "yes" if request.form.get("capitalize") else "no",
        },
        seconds=True,
    )
    state = transition(state)
    # The QR code identifies the same stable initial view as ordinary setup.
    return redirect_to_word(state, qr=action == "qr")


@app.get("/word/<token>")
def show_word(token):
    state = read_view_state(token)
    if request.args:
        return redirect_to_word(state)
    return render_template(
        "word.html", state=state, word=state.word(), configuration=state.configuration
    )


@app.get("/qr/<token>")
def show_qr(token):
    state = read_view_state(token)
    if request.args:
        return redirect_to_word(state, qr=True)
    return qr_response(state)


@app.post("/next")
def next_word():
    return redirect_to_word(transition(read_view_state(request.form.get("state"))))


@app.post("/repeat")
def same_word():
    return redirect_to_word(transition(read_view_state(request.form.get("state")), retry=True))
