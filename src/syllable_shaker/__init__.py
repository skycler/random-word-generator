import os
from flask import Flask
from .WordGenerator import WordGenerator

path = os.path.dirname(__file__)

app = Flask(
    __name__,
    template_folder=os.path.join(path, 'templates'),
    static_folder=os.path.join(path, 'static'),
)
generator = WordGenerator()

from syllable_shaker import routes, errors