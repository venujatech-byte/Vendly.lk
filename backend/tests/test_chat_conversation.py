"""End-to-end tests for the storefront conversation state machine.

Every other test in this suite exercises an extracted pure helper. Nothing
covered `answer_public_message` itself, which is where the fourteen ordered
steps, the early returns and the state transitions actually live. A branch that
never gets reached, an early return that shadows a later one, or a `respond()`
that persists the wrong state would all pass the unit tests untouched.

Only real boundaries are faked: Firestore, the AI provider, and the other
services. The ordering under test is the production code.
"""

import pytest

from app.services import public_chat_service
from app.services.public_chat_service import answer_public_message

# The state gate lives inside storefront_intent, so testing it needs the real
# implementation with only the AI boundary underneath faked.
REAL_STOREFRONT_INTENT = public_chat_service.storefront_intent


class FakeReference:
    """Applies writes back to the session dict, the way Firestore would."""

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
    def __init__(self, session):
        self.id = "session-1"
        self.session = session
        self.reference = FakeReference(session)


def catalogue():
    return [
        {
            "id": "buds",
            "name": "GM2 Pro Earbuds",
            "categoryName": "Earbuds",
            "sellingPriceMinor": 450000,
            "weightGrams": 300,
            "availableStock": 5,
            "description": "Black wireless earbuds.",
            "media": [],
            "variants": [
                {"id": "v-buds", "size": "", "availableStock": 5,
                 "sellingPriceMinor": 450000, "weightGrams": 300},
            ],
        },
        {
            "id": "shoes",
            "name": "Runner Shoes",
            "categoryName": "Shoes",
            "sellingPriceMinor": 900000,
            "weightGrams": 800,
            "availableStock": 3,
            "description": "Running shoes.",
            "media": [],
            "variants": [
                {"id": "v-s", "size": "S", "availableStock": 2,
                 "sellingPriceMinor": 900000, "weightGrams": 800},
                {"id": "v-xl", "size": "XL", "availableStock": 1,
                 "sellingPriceMinor": 950000, "weightGrams": 850},
            ],
        },
    ]


class Chat:
    """Drives a conversation, carrying session state between turns."""

    def __init__(self, session, intent_holder):
        self.session = session
        self.intent_holder = intent_holder

    def say(self, message, intent=None, **fields):
        self.intent_holder["value"] = (
            {"intent": intent, "language": "en", **fields} if intent else {}
        )
        return answer_public_message(None, "session-1", "token", {"message": message})

    @property
    def state(self):
        return self.session.get("state")

    @property
    def cart(self):
        return self.session.get("cart", [])


@pytest.fixture
def chat(monkeypatch):
    session = {
        "businessId": "biz",
        "state": "browsing",
        "status": "active",
        "cart": [],
        "customerDraft": {},
        "language": "en",
        "aiPaused": False,
    }
    snapshot = FakeSnapshot(session)
    intent_holder = {"value": {}}
    products = catalogue()

    patches = {
        "authorize_public_chat_session": lambda *a, **k: (snapshot, session),
        "save_chat_message": lambda *a, **k: None,
        "session_catalog": lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                                       "products": products},
        "storefront_intent": lambda *a: intent_holder["value"],
        "sync_ai_failure_notification": lambda *a: None,
        # Evaluated as an argument to the call above, so it runs even when that
        # call is patched out - and it reads current_app.
        "ai_status": lambda: {"failure": None},
        "translate_chat_message": lambda text, _language: text,
        "detect_chat_language": lambda _message: None,
        "generate_product_answer": lambda *a, **k: None,
        "generate_catalogue_answer": lambda *a, **k: None,
        "notify_seller_attention": lambda *a, **k: None,
        "latest_order_for_session": lambda *a: None,
        "describe_missing_variant": lambda *a: "Runner Shoes (size XL)",
        "list_public_product_reviews": lambda *a: [],
        "list_public_seller_reviews": lambda *a: [],
        "recommend_couriers": lambda _db, _biz, weight, _district: [
            {
                "courier": {"id": "c1", "name": "Koombiyo", "extraKgPriceMinor": 10000,
                            "districtFirstKgPricesMinor": {"colombo": 45000}},
                "deliveryFeeMinor": 45000,
                "score": 90.0,
            },
        ],
    }
    for name, replacement in patches.items():
        monkeypatch.setattr(public_chat_service, name, replacement)

    return Chat(session, intent_holder)


def test_a_product_question_does_not_touch_the_cart(chat):
    chat.say("do you have GM2 pro?", intent="product_question", productQuery="GM2 pro")

    # Asking about a product must never order it.
    assert chat.cart == []
    assert chat.state == "browsing"


def test_ordering_asks_the_quantity_before_adding_anything(chat):
    reply = chat.say("mata GM2 pro ona", intent="start_order",
                     productQuery="GM2 pro", quantity=0, quantityMode="total")

    assert chat.state == "awaiting-item-quantity"
    assert chat.cart == []
    assert "How many" in reply["message"]

    reply = chat.say("2", intent="set_quantity", quantity=2, quantityMode="total")

    assert chat.cart == [{"variantId": "v-buds", "quantity": 2}]
    assert chat.state == "browsing"


def test_a_stated_quantity_skips_the_question(chat):
    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")

    # They already answered it; asking again is friction.
    assert chat.state == "browsing"
    assert chat.cart == [{"variantId": "v-buds", "quantity": 2}]


def test_a_stated_quantity_replaces_rather_than_accumulates(chat):
    chat.say("mata GM2 pro ekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=1, quantityMode="total")
    chat.say("meken mata 3k ona", intent="start_order",
             productQuery="GM2 pro", quantity=3, quantityMode="total")

    # "I want 3" is a total. Adding made this 4 and overcharged the customer.
    assert chat.cart == [{"variantId": "v-buds", "quantity": 3}]


def test_a_multi_size_product_asks_which_size(chat):
    chat.say("I want Runner Shoes", intent="start_order",
             productQuery="Runner Shoes", quantity=1, quantityMode="total")

    # Guessing a size puts the wrong item in a real order.
    assert chat.cart == []
    assert chat.state == "browsing"


def test_a_named_size_is_accepted_and_capped_at_stock(chat):
    chat.say("I want 5 Runner Shoes size XL", intent="start_order",
             productQuery="Runner Shoes", sizeQuery="XL", quantity=5,
             quantityMode="total")

    # Only one XL exists.
    assert chat.cart == [{"variantId": "v-xl", "quantity": 1}]


def test_a_delivery_question_asks_for_the_district_then_quotes_it(chat):
    reply = chat.say("delivery fee kiyada?", intent="delivery_quote")

    assert chat.state == "quoting-district"
    assert "district" in reply["message"].lower()

    reply = chat.say("Colombo")

    assert chat.state == "browsing"
    assert "Colombo" in reply["message"]
    # The district is remembered so checkout does not ask for it again.
    assert chat.session["customerDraft"]["address"]["district"] == "Colombo"


def test_checkout_skips_the_district_it_already_captured(chat):
    chat.say("delivery fee kiyada?", intent="delivery_quote")
    chat.say("Colombo")
    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    chat.say("that's all", intent="finished_selecting")

    assert chat.state == "collecting-name"

    chat.say("Nimal Perera")
    assert chat.state == "collecting-phone"
    chat.say("0771234567")
    assert chat.state == "collecting-secondary-phone"
    chat.say("skip")
    assert chat.state == "collecting-address"
    reply = chat.say("No. 45 Park Road")

    # Colombo was captured during the quote, so the district step is skipped.
    assert chat.state == "collecting-nearest-city"
    assert "Colombo" in reply["message"]


def test_a_full_order_reaches_confirmation_with_a_real_total(chat, monkeypatch):
    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    chat.say("that's all", intent="finished_selecting")
    chat.say("Nimal Perera")
    chat.say("0771234567")
    chat.say("skip")
    chat.say("No. 45 Park Road")
    chat.say("Colombo")
    chat.say("Nugegoda")
    reply = chat.say("skip")

    assert chat.state == "awaiting-confirmation"
    # Items 2 x 4,500 = 9,000, delivery 450, total 9,450. A summary that says
    # "will be calculated" is one nobody can confirm.
    assert "9,000.00" in reply["message"]
    assert "450.00" in reply["message"]
    assert "9,450.00" in reply["message"]


def test_a_name_is_never_classified_as_an_intent(chat, monkeypatch):
    calls = []

    monkeypatch.setattr(public_chat_service, "storefront_intent", REAL_STOREFRONT_INTENT)
    monkeypatch.setattr(
        public_chat_service,
        "generate_storefront_intent",
        lambda message, *a: calls.append(message) or None,
    )

    chat.say("show me products")
    assert calls == ["show me products"]

    chat.session["state"] = "collecting-name"
    chat.say("Ruwan Silva")

    # In collecting-* states the message IS the data. Classifying "Ruwan Silva"
    # is both wasteful and wrong, and it costs a provider call per keystroke of
    # the checkout flow.
    assert "Ruwan Silva" not in calls


def test_a_sold_out_item_is_reported_before_anything_else(chat):
    chat.session["cart"] = [{"variantId": "v-gone", "quantity": 1}]
    reply = chat.say("do you have GM2 pro?", intent="product_question")

    # A changed order outranks the question they just asked, and the line must
    # not vanish silently.
    assert "sold out" in reply["message"].lower()
    assert chat.cart == []


def test_a_paused_ai_hands_over_without_answering(chat):
    chat.session["aiPaused"] = True
    reply = chat.say("hello?")

    assert reply["action"] == "waiting-for-seller"
    assert reply["message"] == ""
