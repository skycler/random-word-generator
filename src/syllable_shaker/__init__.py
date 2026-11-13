from flask import Flask

from .WordGenerator import WordGenerator

app = Flask(__name__)
generator = WordGenerator()

# Register routes and error handlers only after the shared app exists.
from . import errors, routes  # noqa: E402, F401
