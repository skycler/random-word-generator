import random
from html.parser import HTMLParser
from urllib.parse import urlsplit

import pytest

from syllable_shaker import app, routes
from syllable_shaker.WordGenerator import WordGenerator
from syllable_shaker.WordState import WordState
from syllable_shaker.WordToken import decode_word, encode_word


class Page(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.forms = []
        self.links = []
        self.inputs = []
        self.options = []
        self.word = ""
        self._in_word = False
        self._in_link = False
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "form":
            self.forms.append(
                {"action": attrs["action"], "method": attrs.get("method", "get"), "data": {}}
            )
        elif tag == "input":
            self.inputs.append(attrs)
            if self.forms and attrs.get("type") == "hidden":
                self.forms[-1]["data"][attrs["name"]] = attrs["value"]
        elif tag == "option":
            self.options.append(attrs)
        elif tag == "h1" and attrs.get("id") == "myWord":
            self._in_word = True
        elif tag == "a":
            self.links.append({"href": attrs["href"], "text": "", "label": attrs.get("aria-label")})
            self._in_link = True

    def handle_endtag(self, tag):
        if tag == "h1":
            self._in_word = False
        elif tag == "a":
            self._in_link = False

    def handle_data(self, data):
        if self._in_word:
            self.word += data
        if self._in_link:
            self.links[-1]["text"] += data


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(routes, "generator", WordGenerator(rng=random.Random(42)))
    return app.test_client()


def start(client, **preferences):
    data = {"syllables": "3", "complexity": "simple", "fadeout": "0.25", "capitalize": "on"}
    data.update(preferences)
    response = client.post("/", data=data)
    assert response.status_code == 303
    assert urlsplit(response.location).path.startswith("/word/")
    return response.location


def state(url):
    return WordState.from_token(token(url))


def score(url):
    return state(url).score


def token(url):
    return urlsplit(url).path.rsplit("/", 1)[1]


def test_view_url_obfuscates_all_settings_without_query_parameters(client):
    location = start(client, syllables="4", complexity="complex")
    assert urlsplit(location).query == ""
    assert "complex" not in location
    assert "syllables" not in location


def test_setup_redirects_to_obfuscated_stable_uppercase_word(client, monkeypatch):
    location = start(client)
    assert score(location) == "0:0"
    assert state(location).fadeout == 250.0

    def unexpected_generation(*args):
        pytest.fail("Viewing or refreshing a word must not generate a new one")

    monkeypatch.setattr(routes.generator, "generate", unexpected_generation)
    pages = [client.get(location) for _ in range(3)]
    assert all(page.status_code == 200 for page in pages)
    assert len({page.data for page in pages}) == 1
    word = Page(pages[0].get_data(as_text=True)).word
    assert word and word == word.upper()
    assert decode_word(state(location).token) == word.lower()
    assert word.lower() not in location.lower()
    forms = Page(pages[0].get_data(as_text=True)).forms
    assert all(form["data"] == {"state": token(location)} for form in forms)
    assert all(word.lower() not in form["data"].values() for form in forms)


def test_word_actions_are_post_redirect_get_and_preserve_state(client):
    location = start(client, syllables="4", complexity="complex")
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
    assert state(repeated.location).token == state(location).token
    assert Page(client.get(repeated.location).get_data(as_text=True)).word == page.word

    repeated_page = Page(client.get(repeated.location).get_data(as_text=True))
    advance = repeated_page.forms[1]
    next_word = client.post(advance["action"], data=advance["data"])
    assert next_word.status_code == 303
    assert score(next_word.location) == "1:1"
    next_state = state(next_word.location)
    assert next_state.syllables == 4
    assert next_state.complexity == "complex"
    assert next_state.capitalize == "yes"
    assert next_state.fadeout == 250.0
    assert urlsplit(next_word.location).query == ""
    assert client.get(next_word.location).status_code == 200
    assert client.get(location).get_data(as_text=True) == original_html


def test_qr_encodes_absolute_obfuscated_stable_word_url(client, monkeypatch):
    addresses = []
    original = routes.make_qr_code

    def capture_qr(address):
        addresses.append(address)
        return original(address)

    monkeypatch.setattr(routes, "make_qr_code", capture_qr)
    response = client.post(
        "/", data={"syllables": "3", "complexity": "medium", "fadeout": "0", "qr": "on"}
    )
    assert response.status_code == 303
    assert urlsplit(response.location).path.startswith("/qr/")

    def unexpected_generation(*args):
        pytest.fail("Viewing or refreshing a QR code must not generate a new word")

    monkeypatch.setattr(routes.generator, "generate", unexpected_generation)
    images = [client.get(response.location) for _ in range(2)]
    assert all(image.status_code == 200 and image.mimetype == "image/png" for image in images)
    assert images[0].data == images[1].data
    assert addresses[0] == addresses[1]
    address = addresses[0]
    assert address.startswith("http://localhost/word/")
    assert "//word" not in address
    assert score(address) == "0:0"
    assert token(address) == token(response.location)
    word = Page(client.get(address).get_data(as_text=True)).word
    assert state(address).word() == word
    assert urlsplit(address).query == ""
    assert word not in address


@pytest.mark.parametrize(
    "preferences",
    [
        {"syllables": ""},
        {"syllables": "1"},
        {"syllables": "5"},
        {"syllables": "2.5"},
        {"syllables": "2:2-3:1"},
        {"complexity": ""},
        {"complexity": "invalid"},
        {"fadeout": "nan"},
        {"fadeout": "-1"},
        {"fadeout": "11"},
    ],
)
def test_invalid_setup_returns_400(client, preferences):
    data = {"syllables": "3", "complexity": "simple", "fadeout": "0"}
    data.update(preferences)
    assert client.post("/", data=data).status_code == 400


def test_missing_setup_returns_400(client):
    assert client.post("/", data={}).status_code == 400


@pytest.mark.parametrize("bad_token", ["2.0", "invalid", "bmFsaW1v=", "YR", "_w", "a" * 100])
def test_invalid_tokens_return_400_in_views_and_retry(client, bad_token):
    assert client.get("/word/" + bad_token).status_code == 400
    assert client.get("/qr/" + bad_token).status_code == 400
    assert client.post("/repeat", data={"state": bad_token}).status_code == 400


def test_invalid_action_state_returns_400(client):
    for action in ("/next", "/repeat"):
        assert client.post(action, data={}).status_code == 400
        assert client.post(action, data={"state": "v1.e30"}).status_code == 400
        assert client.post(action, data={"state": "bmFsaW1v"}).status_code == 400


def test_token_reconstruction_does_not_depend_on_the_generator_or_settings(client, monkeypatch):
    monkeypatch.setattr(routes, "generator", None)
    for complexity in ("simple", "medium", "complex"):
        view = WordState.from_values(
            {"token": encode_word("mälin"), "syllables": "4", "complexity": complexity}
        )
        page = client.get("/word/" + view.to_token())
        assert page.status_code == 200
        assert Page(page.get_data(as_text=True)).word == "mälin"
    view = WordState.from_values({"token": encode_word("mälin"), "capitalize": "yes"})
    uppercase = client.get("/word/" + view.to_token())
    assert Page(uppercase.get_data(as_text=True)).word == "MÄLIN"
    retry = Page(uppercase.get_data(as_text=True)).forms[0]
    repeated = client.post(retry["action"], data=retry["data"])
    assert repeated.status_code == 303
    assert state(repeated.location).token == encode_word("mälin")


@pytest.mark.parametrize("path", ["/word/bmFsaW1v", "/qr/bmFsaW1v"])
def test_word_only_links_are_not_supported(client, path):
    response = client.get(
        path, query_string={"syllables": "4", "complexity": "medium", "score": "2:3"}
    )
    assert response.status_code == 400
    assert "Location" not in response.headers


def test_query_parameters_cannot_override_an_encoded_view(client):
    location = start(client)
    response = client.get(location + "?complexity=complex&score=99:99&fadeout=9999")
    assert response.status_code == 303
    assert response.location == location
    assert state(response.location).complexity == "simple"
    assert state(response.location).score == "0:0"
    assert state(response.location).fadeout == 250.0


@pytest.mark.parametrize(
    "path",
    [
        "/next/2:2-3:1/0:-1",
        "/repeat/2.0/2:1/0:0",
        "/code/2:1/0:-1/0/no",
    ],
)
def test_retired_list_based_routes_are_not_supported(client, path):
    assert client.get(path).status_code == 404


def test_setup_has_syllable_and_complexity_controls(client):
    html = client.get("/").get_data(as_text=True)
    assert 'name="syllables" min="2" max="4" step="1" value="3"' in html
    assert 'name="complexity"' in html
    assert 'value="simple" selected' in html
    assert 'name="config"' not in html
    assert 'step="0.25" value="0"' in html
    location = start(client, capitalize="", fadeout="0")
    word = Page(client.get(location).get_data(as_text=True)).word
    assert word == word.lower()
    assert state(location).fadeout == 0.0


@pytest.mark.parametrize("path", ["/", "word", "/word/YR", "/does-not-exist"])
def test_home_link_returns_to_setup_from_every_html_screen(client, path):
    path = start(client) if path == "word" else path
    page = Page(client.get(path).get_data(as_text=True))
    home_links = [link for link in page.links if link["label"] == "Syllable Shaker home"]
    assert len(home_links) == 1
    assert "s." in home_links[0]["text"]
    assert "Syllable Shaker" in home_links[0]["text"]
    response = client.get(home_links[0]["href"])
    assert response.status_code == 200
    assert 'name="syllables"' in response.get_data(as_text=True)
    assert Page(response.get_data(as_text=True)).word == ""


@pytest.mark.parametrize(
    "preferences",
    [
        {"syllables": "4", "complexity": "complex", "fadeout": "1.25", "capitalize": "on"},
        {"syllables": "2", "complexity": "medium", "fadeout": "0.75", "capitalize": ""},
    ],
)
def test_home_prefills_current_preferences_but_starts_a_fresh_session(client, preferences):
    location = start(client, **preferences)
    page = Page(client.get(location).get_data(as_text=True))
    original_home = next(link for link in page.links if link["label"] == "Syllable Shaker home")
    retry = page.forms[0]
    repeated = client.post(retry["action"], data=retry["data"])
    assert score(repeated.location) == "1:0"
    page = Page(client.get(repeated.location).get_data(as_text=True))
    home = next(link for link in page.links if link["label"] == "Syllable Shaker home")
    assert home["href"] == original_home["href"]
    assert urlsplit(home["href"]).query == ""
    setup = client.get(home["href"])
    assert setup.status_code == 200
    form = Page(setup.get_data(as_text=True))
    fields = {field["name"]: field for field in form.inputs if "name" in field}
    selected = next(option for option in form.options if "selected" in option)
    assert fields["syllables"]["value"] == preferences["syllables"]
    assert fields["fadeout"]["value"] == preferences["fadeout"]
    assert selected["value"] == preferences["complexity"]
    assert ("checked" in fields["capitalize"]) == bool(preferences["capitalize"])
    assert form.word == ""
    # Clicking Home again while on setup must retain the same configuration.
    setup_home = next(link for link in form.links if link["label"] == "Syllable Shaker home")
    assert setup_home["href"] == home["href"]
    restarted = client.post(
        form.forms[0]["action"],
        data={
            "syllables": fields["syllables"]["value"],
            "complexity": selected["value"],
            "fadeout": fields["fadeout"]["value"],
            "capitalize": preferences["capitalize"],
        },
    )
    assert restarted.status_code == 303
    assert score(restarted.location) == "0:0"
    assert state(restarted.location).configuration == state(location).configuration


def test_static_assets_and_external_dom_ready_timer(client):
    css = client.get("/static/app.css")
    script = client.get("/static/word.js")
    assert css.status_code == script.status_code == 200
    assert css.mimetype == "text/css"
    html = client.get(start(client)).get_data(as_text=True)
    assert 'data-fadeout="250.0"' in html
    assert "/static/word.js" in html
    assert "defer" in html
    assert "jquery" not in html.lower()
    assert "<style>" not in html
    assert "<script>" not in html
