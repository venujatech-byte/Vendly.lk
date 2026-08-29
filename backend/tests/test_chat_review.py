"""The post-delivery review flow: rating, text, photos, seller rating.

The flow spends four turns in `collecting-review-*` states with a draft on the
session, and only writes to `reviews` at the end. A wrong transition or a lost
draft would submit the wrong thing, or nothing, so the whole walk is driven
here rather than each helper being poked in isolation.
"""

import pytest

from app.services import public_chat_service
from app.services.public_chat_service import (
    answer_public_message,
    parse_star_rating,
    wants_to_skip,
)


class FakeOrderSnapshot:
    exists = True
    id = "order-1"

    def to_dict(self):
        return {
            "orderNumber": "VD-000004",
            "fulfilmentStatus": "delivered",
            "customerSnapshot": {"normalizedPhone": "+94771234567"},
            "items": [{"productId": "buds", "productName": "GM2 Pro Earbuds"}],
        }


class FakeReference:
    def __init__(self, session):
        self.session = session

    def update(self, changes):
        self.session.update(changes)

    def set(self, changes, merge=False):
        self.session.update(changes)

    def collection(self, _name):
        return self

    def document(self, _name=None):
        return self


class FakeSnapshot:
    id = "session-1"

    def __init__(self, session):
        self.session = session
        self.reference = FakeReference(session)


class FakeDatabase:
    """Every document read in this flow is the one order under review."""

    def collection(self, _name):
        return self

    def document(self, _name=None):
        return self

    def get(self):
        return FakeOrderSnapshot()


@pytest.fixture
def chat(monkeypatch):
    session = {
        "businessId": "biz",
        "state": "collecting-review-rating",
        "cart": [],
        "customerDraft": {},
        "language": "en",
        "reviewDraft": {"orderId": "order-1", "productId": "buds", "media": []},
    }
    snapshot = FakeSnapshot(session)
    written = []

    patches = {
        "authorize_public_chat_session": lambda *a, **k: (snapshot, session),
        "save_chat_message": lambda *a, **k: None,
        "session_catalog": lambda *a: {
            "business": {"name": "VS Tech", "storefrontFaq": ""},
            "products": [],
        },
        "storefront_intent": lambda *a: {},
        "sync_ai_failure_notification": lambda *a: None,
        "ai_status": lambda: {"failure": None},
        "translate_chat_message": lambda text, _language: text,
        "detect_chat_language": lambda _message: None,
        "notify_seller_attention": lambda *a, **k: None,
        "latest_order_for_session": lambda *a: None,
        "write_order_review": lambda _db, _biz, _order, review, _config=None: (
            written.append(review)
        ),
    }
    for name, replacement in patches.items():
        monkeypatch.setattr(public_chat_service, name, replacement)

    def say(message):
        return answer_public_message(FakeDatabase(), "session-1", "token",
                                     {"message": message})

    return say, session, written


def test_a_rating_walks_through_to_both_reviews(chat):
    say, session, written = chat

    say("5")
    assert session["state"] == "collecting-review-text"

    say("Sound is great and it arrived fast.")
    assert session["state"] == "collecting-review-photo"

    # A photo is optional. Any text here means "finished adding them", which is
    # what submits the product review.
    say("done")
    assert session["state"] == "collecting-review-seller-rating"
    assert written[0]["productId"] == "buds"
    assert written[0]["rating"] == 5
    assert "arrived fast" in written[0]["reviewText"]

    say("4")
    # The seller review carries no product, which is what makes it a seller
    # review rather than a second product one.
    assert written[1]["productId"] == ""
    assert written[1]["rating"] == 4
    assert session["state"] == "completed"
    assert not session["reviewDraft"]


def test_skipping_leaves_the_flow_without_writing_anything(chat):
    say, session, written = chat

    say("skip")

    assert session["state"] == "completed"
    assert written == []


def test_a_photo_sent_while_reviewing_joins_the_draft(chat, monkeypatch):
    say, session, _written = chat
    session["state"] = "collecting-review-photo"
    monkeypatch.setattr(
        public_chat_service,
        "upload_chat_data_url",
        lambda *a, **k: {"url": "https://cdn/photo.jpg"},
    )

    # The uploader reads Cloudinary credentials off the app config, so this
    # one call needs a context; the uploader itself is faked above.
    from app import create_app

    with create_app().app_context():
        reply = public_chat_service.attach_public_chat_image(
            FakeDatabase(), "session-1", "token",
            {"image": "data:image/png;base64,x"},
        )

    # It belongs to the review, not to the seller's attention queue.
    assert session["reviewDraft"]["media"] == ["https://cdn/photo.jpg"]
    assert "review" in reply["message"]


def test_ratings_are_read_from_however_the_customer_writes_them():
    assert parse_star_rating("5") == 5
    assert parse_star_rating("4/5") == 4
    assert parse_star_rating("⭐⭐⭐") == 3
    assert parse_star_rating("it was good") == 4
    assert parse_star_rating("no idea") is None
    assert wants_to_skip("skip") and not wants_to_skip("good")
