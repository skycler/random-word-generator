from flask import render_template

from syllable_shaker import app


@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", message=error.description), 400


@app.errorhandler(500)
def internal_error(error):
    return render_template("error.html", message="An unexpected error has occurred"), 500


@app.errorhandler(404)
def not_found_error(error):
    return render_template("error.html", message="non-valid url"), 404
