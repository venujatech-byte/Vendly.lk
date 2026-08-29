"""A human reply must reach the customer in the customer's language.

A seller pauses the AI precisely when a question is hard. Handing that customer
a sudden English reply after ten Sinhala messages is where the language
guarantee used to break, and it happens at the worst possible moment.
"""

from app.services import message_service


class FakeMessageDocument:
    def __init__(self, store):
        self.store = store

    def set(self, data):
        self.store.update(data)

    def get(self):
        return FakeSnapshot(self.store, exists=True)


class FakeSnapshot:
    def __init__(self, data, exists=True):
        self.id = "message-1"
        self._data = data
        self.exists = exists

    def to_dict(self):
        return self._data


class FakeSessionReference:
    def __init__(self, session, written):
        self.session = session
        self.written = written

    def get(self):
        return FakeSnapshot(self.session)

    def set(self, data, merge=False):
        self.session.update(data)

    def collection(self, _name):
        return self

    def document(self, _name=None):
        return FakeMessageDocument(self.written)


class FakeDatabase:
    def __init__(self, session, written):
        self.reference = FakeSessionReference(session, written)

    def collection(self, _name):
        return self

    def document(self, _name):
        return self.reference


def send(monkeypatch, language, seller_text, translator=None):
    session = {"businessId": "biz", "language": language}
    written = {}
    monkeypatch.setattr(
        message_service,
        "translate_chat_message",
        translator or (lambda text, lang: f"[{lang}] {text}" if lang != "en" else text),
    )
    message_service.send_seller_message(
        FakeDatabase(session, written),
        "biz",
        "session-1",
        "seller-uid",
        {"message": seller_text},
    )
    return session, written


def test_a_seller_reply_reaches_a_sinhala_customer_in_sinhala(monkeypatch):
    session, written = send(monkeypatch, "si", "We will ship it tomorrow.")

    assert written["message"] == "[si] We will ship it tomorrow."
    # The seller's own words are kept so their inbox shows what they typed.
    assert written["sellerMessage"] == "We will ship it tomorrow."
    assert written["metadata"]["translated"] is True
    assert written["metadata"]["language"] == "si"


def test_the_customer_facing_text_is_what_the_conversation_summary_shows(monkeypatch):
    session, _written = send(monkeypatch, "ta", "Your order is packed.")

    # The storefront reads lastMessage, so it must be the translated form.
    assert session["lastMessage"] == "[ta] Your order is packed."
    assert session["lastMessageRole"] == "seller"


def test_an_english_conversation_is_left_untouched(monkeypatch):
    _session, written = send(monkeypatch, "en", "We will ship it tomorrow.")

    assert written["message"] == "We will ship it tomorrow."
    assert written["metadata"]["translated"] is False


def test_a_seller_already_writing_the_customer_language_is_not_flagged(monkeypatch):
    # A Sri Lankan seller often types Sinhala themselves. Translating that is a
    # near no-op and must not be reported as a translation.
    _session, written = send(
        monkeypatch,
        "si",
        "හෙට යවනවා",
        translator=lambda text, _language: text,
    )

    assert written["message"] == "හෙට යවනවා"
    assert written["sellerMessage"] == "හෙට යවනවා"
    assert written["metadata"]["translated"] is False


def test_a_session_with_no_language_defaults_to_english(monkeypatch):
    session = {"businessId": "biz"}
    written = {}
    monkeypatch.setattr(
        message_service,
        "translate_chat_message",
        lambda text, language: text if language == "en" else "TRANSLATED",
    )
    message_service.send_seller_message(
        FakeDatabase(session, written), "biz", "s", "uid", {"message": "Hello"},
    )

    assert written["message"] == "Hello"
