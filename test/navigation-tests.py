from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

import pytest

from syllable_shaker import app, routes
from syllable_shaker.WordGenerator import WordGenerator


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.word = ""
        self._in_word = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.forms.append({"action": attrs["action"], "method": attrs.get("method", "get"), "data": {}})
        elif tag == "input" and self.forms and attrs.get("type") == "hidden":
            self.forms[-1]["data"][attrs["name"]] = attrs["value"]
        elif tag == "h1" and attrs.get("id") == "myWord":
            self._in_word = True

    def handle_endtag(self, tag):
        if tag == "h1":
            self._in_word = False

    def handle_data(self, data):
        if self._in_word:
            self.word += data


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes, "generator", WordGenerator.FromList(["an", "be", "der"]))
    return app.test_client()


def start(client, **preferences):
    data = {"config": "2:2-3:1", "fadeout": "0.25", "capitalize": "on"}
    data.update(preferences)
    response = client.post("/", data=data)
    assert response.status_code == 303
    assert urlsplit(response.location).path.startswith("/word/")
    return response.location


def score(url):
    return parse_qs(urlsplit(url).query)["score"][0]


def test_setup_redirects_to_stable_uppercase_word(client, monkeypatch):
    location = start(client)
    assert score(location) == "0:0"
    assert parse_qs(urlsplit(location).query)["fadeout"] == ["250.0"]

    def unexpected_generation(*args):
        pytest.fail("Viewing or refreshing a word must not generate a new one")

    monkeypatch.setattr(routes.generator, "MakeWord", unexpected_generation)
    pages = [client.get(location) for _ in range(3)]
    assert all(page.status_code == 200 for page in pages)
    assert len({page.data for page in pages}) == 1
    word = Page(pages[0].get_data(as_text=True)).word
    assert word and word == word.upper()


def test_word_actions_are_post_redirect_get_and_preserve_state(client):
    location = start(client)
    original_html = client.get(location).get_data(as_text=True)
    page = Page(original_html)
    retry, advance = page.forms
    assert retry["method"] == advance["method"] == "post"
    assert retry["action"] == "/repeat"
    assert advance["action"] == "/next"
    assert client.get("/next").status_code == 405
    assert client.get("/repeat").status_code == 405

    repeated = client.post(retry["action"], data=retry["data"])
    assert repeated.status_code == 303
    assert score(repeated.location) == "1:0"
    assert urlsplit(repeated.location).path == urlsplit(location).path
    assert Page(client.get(repeated.location).get_data(as_text=True)).word == page.word

    repeated_page = Page(client.get(repeated.location).get_data(as_text=True))
    advance = repeated_page.forms[1]
    next_word = client.post(advance["action"], data=advance["data"])
    assert next_word.status_code == 303
    assert score(next_word.location) == "1:1"
    params = parse_qs(urlsplit(next_word.location).query)
    assert params["config"] == ["2:2-3:1"]
    assert params["capitalize"] == ["yes"]
    assert params["fadeout"] == ["250.0"]
    assert client.get(next_word.location).status_code == 200
    # Going back to an earlier URL restores its exact word and score.
    assert client.get(location).get_data(as_text=True) == original_html
    assert score(location) == "0:0"


@pytest.mark.parametrize("path, expected_score", [
    ("/next/2:2-3:1/0:-1", "0:0"),
    ("/next/2:2-3:1/1:2/250/yes", "1:3"),
    ("/repeat/2.0-3.0/2:1-3:1/1:2/250/yes", "2:2"),
])
def test_legacy_links_redirect_to_stable_views(client, path, expected_score):
    response = client.get(path)
    assert response.status_code == 303
    assert urlsplit(response.location).path.startswith("/word/")
    assert score(response.location) == expected_score
    assert client.get(response.location).status_code == 200


def test_qr_encodes_absolute_stable_word_url(client, monkeypatch):
    addresses = []
    original = routes.make_qr_code

    def capture_qr(address):
        addresses.append(address)
        return original(address)

    monkeypatch.setattr(routes, "make_qr_code", capture_qr)
    response = client.post("/", data={"config": "2:2-3:1", "fadeout": "0", "qr": "on"})
    assert response.status_code == 303
    assert urlsplit(response.location).path.startswith("/qr/")

    def unexpected_generation(*args):
        pytest.fail("Viewing or refreshing a QR code must not generate a new word")

    monkeypatch.setattr(routes.generator, "MakeWord", unexpected_generation)
    images = [client.get(response.location) for _ in range(2)]
    assert all(image.status_code == 200 and image.mimetype == "image/png" for image in images)
    assert images[0].data == images[1].data
    assert addresses[0] == addresses[1]
    address = addresses[0]
    assert address.startswith("http://localhost/word/")
    assert "//word" not in address
    assert score(address) == "0:0"
    assert client.get(address).status_code == 200


@pytest.mark.parametrize("fadeout", ["invalid", "nan", "inf", "-1", "10001", "0);alert(1)"])
def test_invalid_timer_in_view_returns_400(client, fadeout):
    response = client.get("/word/2.0", query_string={"config": "2:1", "score": "0:0", "fadeout": fadeout})
    assert response.status_code == 400
    assert "Invalid visibility duration" in response.get_data(as_text=True)


@pytest.mark.parametrize("data", [
    {},
    {"config": "invalid", "fadeout": "0"},
    {"config": "2:1", "fadeout": "nan"},
    {"config": "2:1", "fadeout": "-1"},
    {"config": "2:1", "fadeout": "11"},
])
def test_invalid_setup_returns_400(client, data):
    assert client.post("/", data=data).status_code == 400


def test_invalid_word_and_actions_return_400(client):
    params = {"config": "2:1", "score": "0:0", "fadeout": "0", "capitalize": "no"}
    assert client.get("/word/invalid", query_string=params).status_code == 400
    assert client.get("/word/2.0", query_string={**params, "score": "invalid"}).status_code == 400
    assert client.get("/word/2.0", query_string={**params, "capitalize": "invalid"}).status_code == 400
    assert client.post("/repeat", data=params).status_code == 400
    assert client.post("/next", data={**params, "config": "invalid"}).status_code == 400
    assert client.get("/qr/invalid", query_string=params).status_code == 400


def test_legacy_qr_endpoint_encodes_a_stable_view(client, monkeypatch):
    addresses = []
    original = routes.make_qr_code

    def capture_qr(address):
        addresses.append(address)
        return original(address)

    monkeypatch.setattr(routes, "make_qr_code", capture_qr)
    response = client.get("/code/2:1/0:-1/0/no")
    assert response.status_code == 200
    assert response.mimetype == "image/png"
    address, = addresses
    assert urlsplit(address).path.startswith("/word/")
    assert score(address) == "0:0"


def test_setup_defaults_remain_unchanged(client):
    html = client.get("/").get_data(as_text=True)
    assert 'name="config" value="2:2-3:1"' in html
    assert 'step="0.25" value="0"' in html
    location = start(client, capitalize="", fadeout="0")
    word = Page(client.get(location).get_data(as_text=True)).word
    assert word == word.lower()
    assert parse_qs(urlsplit(location).query)["fadeout"] == ["0.0"]


def test_static_assets_and_external_dom_ready_timer(client):
    css = client.get("/static/app.css")
    script = client.get("/static/word.js")
    assert css.status_code == script.status_code == 200
    assert css.mimetype == "text/css"
    assert "DOMContentLoaded" in script.get_data(as_text=True)
    html = client.get(start(client)).get_data(as_text=True)
    assert 'data-fadeout="250.0"' in html
    assert '/static/word.js' in html
    assert 'defer' in html
    assert 'jquery' not in html.lower()
    assert '<style>' not in html
    assert '<script>' not in html
