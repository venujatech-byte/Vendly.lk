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
# The fixture stubs message saving out; the conversation-window tests need the
# real one, which writes through the fake Firestore reference.
REAL_SAVE_CHAT_MESSAGE = public_chat_service.save_chat_message


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
            "brand": "Lenovo",
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


class FakeBusinessDatabase:
    """Answers the one business-document read the deposit branch performs."""

    def __init__(self, bank):
        self.bank = bank

    def collection(self, _name):
        return self

    def document(self, _name):
        return self

    def get(self):
        return FakeBusinessSnapshot(self.bank)


class FakeBusinessSnapshot:
    exists = True

    def __init__(self, bank):
        self.bank = bank

    def to_dict(self):
        return {"bankDetails": self.bank}


class Chat:
    """Drives a conversation, carrying session state between turns."""

    def __init__(self, session, intent_holder):
        self.session = session
        self.intent_holder = intent_holder
        self.bank = {}

    def say(self, message, intent=None, **fields):
        self.intent_holder["value"] = (
            {"intent": intent, "language": "en", **fields} if intent else {}
        )
        return answer_public_message(
            FakeBusinessDatabase(self.bank),
            "session-1",
            "token",
            {"message": message},
        )

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
        "generate_comparison_answer": lambda *a, **k: None,
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


def test_ordering_by_brand_alone_lists_that_brand(chat):
    # "I want to order Lenovo" resolves no single product and no category, so
    # it reached the brand fallback - which read `requested_brand` a hundred
    # lines before it was assigned. Live, that was a 500, not a wrong answer.
    reply = chat.say("I want to order Lenovo", intent="start_order",
                     productQuery="Lenovo")

    assert "Lenovo" in reply["message"]
    assert [item["id"] for item in reply["products"]] == ["buds"]


def test_show_my_cart_lists_what_is_in_it(chat):
    chat.say("mata GM2 pro ekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")

    # "show my cart" names no product, so it was resolved as one, matched
    # nothing, and the customer was asked which product they meant - while
    # holding a cart the bot could simply have read out.
    reply = chat.say("show my cart", intent="show_cart")

    assert "GM2" in reply["message"]
    assert "2 x" in reply["message"]
    assert "did not catch" not in reply["message"]


def test_an_empty_cart_says_so_rather_than_asking_which_product(chat):
    reply = chat.say("what is in my cart", intent="show_cart")

    assert "empty" in reply["message"].lower()


def test_the_cart_question_survives_the_ai_being_down(chat):
    chat.say("mata GM2 pro ekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=1, quantityMode="total")

    # No intent at all is what a rate-limited provider returns. The phrase
    # match has to carry it, or the feature dies exactly when the shop is busy.
    reply = chat.say("show my cart", intent=None)

    assert "GM2" in reply["message"]


def test_a_stated_quantity_replaces_rather_than_accumulates(chat):
    chat.say("mata GM2 pro ekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=1, quantityMode="total")
    chat.say("meken mata 3k ona", intent="start_order",
             productQuery="GM2 pro", quantity=3, quantityMode="total")

    # "I want 3" is a total. Adding made this 4 and overcharged the customer.
    assert chat.cart == [{"variantId": "v-buds", "quantity": 3}]


def test_a_multi_variant_product_asks_which_variant(chat):
    chat.say("I want Runner Shoes", intent="start_order",
             productQuery="Runner Shoes", quantity=1, quantityMode="total")

    # Guessing a variant puts the wrong item in a real order.
    assert chat.cart == []
    assert chat.state == "awaiting-variant"


def test_a_bare_variant_name_answers_the_variant_question(chat):
    chat.say("I want Runner Shoes", intent="start_order",
             productQuery="Runner Shoes", quantity=1, quantityMode="total")

    # The bug: "XL" on its own carries no sizeQuery, so the reply was read as
    # a new product, resolved to nothing, and the same question was asked
    # again - the customer could answer correctly and never get to order.
    reply = chat.say("XL", intent="unknown")

    assert chat.state == "awaiting-item-quantity"
    assert "how many" in reply["message"].lower()

    chat.say("1", intent="set_quantity", quantity=1)

    assert chat.cart == [{"variantId": "v-xl", "quantity": 1}]


def test_a_variant_answered_with_its_quantity_skips_the_extra_question(chat):
    chat.say("I want Runner Shoes", intent="start_order",
             productQuery="Runner Shoes", quantity=0, quantityMode="total")
    chat.say("XL", intent="start_order", quantity=1, quantityMode="total")

    assert chat.cart == [{"variantId": "v-xl", "quantity": 1}]


def test_changing_your_mind_escapes_the_variant_question(chat):
    chat.say("I want Runner Shoes", intent="start_order",
             productQuery="Runner Shoes", quantity=1, quantityMode="total")
    chat.say("actually show me the catalogue", intent="show_catalog")

    # Re-asking forever traps anyone who did not want that product after all.
    assert chat.state != "awaiting-variant"


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
    chat.say("skip")

    assert chat.state == "choosing-payment"

    reply = chat.say("cash on delivery")

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


def test_a_returning_guest_must_prove_the_phone_before_seeing_an_order(chat, monkeypatch):
    lookups = []

    def fake_lookup(_db, _business, order_number, phone):
        lookups.append((order_number, phone))
        return (
            {"id": "o1", "orderNumber": "VD-000012", "fulfilmentStatus": "packed",
             "totalAmountMinor": 945000}
            if phone.strip() == "0771234567"
            else None
        )

    monkeypatch.setattr(public_chat_service, "find_order_by_number", fake_lookup)

    reply = chat.say("VD-000012 kohomada?")
    # The number alone reveals nothing about the order.
    assert chat.state == "verifying-order"
    assert "VD-000012" in reply["message"]
    assert "mobile number" in reply["message"]
    assert lookups == []

    reply = chat.say("0771234567")
    assert chat.state == "completed"
    assert "VD-000012" in reply["message"]
    assert "packed" in reply["message"]


def test_a_wrong_phone_reveals_nothing_and_does_not_link_the_order(chat, monkeypatch):
    monkeypatch.setattr(public_chat_service, "find_order_by_number", lambda *a: None)

    chat.say("where is VD-000012")
    reply = chat.say("0770000000")

    assert chat.state == "verifying-order"
    assert chat.session.get("orderId") in (None, "")
    # The same wording must cover "wrong phone" and "no such order", or the
    # reply becomes a way to discover which order numbers exist.
    assert "could not match" in reply["message"]


def test_a_missing_order_gives_the_same_answer_as_a_wrong_phone(chat, monkeypatch):
    monkeypatch.setattr(public_chat_service, "find_order_by_number", lambda *a: None)

    chat.say("VD-999999 status?")
    missing = chat.say("0771234567")["message"]

    chat.session["state"] = "browsing"
    chat.session["pendingOrderNumber"] = ""
    chat.session["orderVerificationAttempts"] = 0
    chat.say("VD-000012 status?")
    wrong_phone = chat.say("0770000000")["message"]

    assert missing.replace("VD-999999", "X") == wrong_phone.replace("VD-000012", "X")


def test_phone_guessing_is_capped(chat, monkeypatch):
    monkeypatch.setattr(public_chat_service, "find_order_by_number", lambda *a: None)

    chat.say("VD-000012 status?")
    for _attempt in range(4):
        reply = chat.say("0770000000")
        assert chat.state == "verifying-order"

    reply = chat.say("0770000000")

    # Five wrong phones ends it rather than allowing an endless guessing loop.
    assert chat.state == "browsing"
    assert "contact the seller" in reply["message"]
    assert chat.session["orderVerificationAttempts"] == 0


def test_an_order_number_does_not_hijack_a_session_that_owns_an_order(chat, monkeypatch):
    def fail(*_a):
        raise AssertionError("must not re-verify an order already linked")

    monkeypatch.setattr(public_chat_service, "find_order_by_number", fail)
    monkeypatch.setattr(
        public_chat_service,
        "latest_order_for_session",
        lambda *a: {"id": "o-existing", "orderNumber": "VD-000001",
                    "fulfilmentStatus": "shipped", "totalAmountMinor": 100000},
    )
    chat.session["orderId"] = "o-existing"

    reply = chat.say("VD-000001 kohomada?")

    assert "VD-000001" in reply["message"]
    assert chat.state == "completed"


def big_catalogue():
    """More products than a customer will happily scroll on a phone."""
    return [
        {
            "id": f"p{index}",
            "name": f"Product {index}",
            "categoryName": ["Earbuds", "Shoes", "Watches"][index % 3],
            "sellingPriceMinor": 100000 + index,
            "weightGrams": 200,
            "availableStock": 5,
            "media": [],
            "variants": [{"id": f"v{index}", "size": "", "availableStock": 5,
                          "sellingPriceMinor": 100000 + index, "weightGrams": 200}],
        }
        for index in range(12)
    ]


def test_show_products_asks_what_they_need_instead_of_dumping_everything(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": big_catalogue()},
    )

    reply = chat.say("show products", intent="show_catalog")

    # Twelve product cards makes the customer do the filtering and buries the
    # conversation on a phone.
    assert reply["action"] == "show-categories"
    assert reply["products"] == []
    assert reply["categories"] == ["Earbuds", "Shoes", "Watches"]
    assert "What kind of product" in reply["message"]


def test_a_small_shop_still_shows_everything(chat):
    # With two products there is nothing to narrow; asking would be friction.
    reply = chat.say("show products", intent="show_catalog")

    assert reply["action"] == "show-catalog"
    assert len(reply["products"]) == 2
    assert reply["categories"] == []


def test_naming_a_category_narrows_to_that_category(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": big_catalogue()},
    )

    chat.say("show products", intent="show_catalog")
    reply = chat.say("Shoes", intent="show_category", categoryQuery="Shoes")

    assert reply["action"] == "show-category"
    assert {p["categoryName"] for p in reply["products"]} == {"Shoes"}


def test_an_unrecognised_request_offers_categories_not_the_whole_catalogue(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": big_catalogue()},
    )

    reply = chat.say("hmm something nice", intent="unknown")

    assert reply["action"] == "show-categories"
    assert reply["products"] == []
    assert reply["categories"] == ["Earbuds", "Shoes", "Watches"]


def cancellable_chat(chat, monkeypatch, status="confirmed"):
    """A session that already owns an order, with status writes captured."""
    calls = []
    chat.session["orderId"] = "o1"
    monkeypatch.setattr(
        public_chat_service,
        "latest_order_for_session",
        lambda *a: {"id": "o1", "orderNumber": "VD-000012",
                    "fulfilmentStatus": status, "totalAmountMinor": 945000},
    )
    monkeypatch.setattr(
        public_chat_service,
        "update_order_status",
        lambda _db, _biz, order_id, uid, payload: calls.append((order_id, payload)),
    )
    return calls


def test_cancelling_needs_an_explicit_confirmation(chat, monkeypatch):
    calls = cancellable_chat(chat, monkeypatch)

    reply = chat.say("cancel my order")

    # Releasing stock and voiding an order cannot happen on one ambiguous line.
    assert chat.state == "confirming-cancel"
    assert calls == []
    assert "cannot be undone" in reply["message"]

    chat.say("yes cancel")

    assert calls == [("o1", {"status": "cancelled",
                             "note": "Cancelled by the customer in the storefront chat."})]


def test_declining_at_the_confirmation_leaves_the_order_alone(chat, monkeypatch):
    calls = cancellable_chat(chat, monkeypatch)

    chat.say("cancel my order")
    reply = chat.say("actually no, leave it")

    assert calls == []
    assert "has not been cancelled" in reply["message"]
    assert chat.state == "completed"


def test_a_shipped_order_is_not_cancellable_and_the_seller_is_told(chat, monkeypatch):
    calls = cancellable_chat(chat, monkeypatch, status="shipped")
    told = []
    monkeypatch.setattr(
        public_chat_service,
        "notify_seller_attention",
        lambda *a, **k: told.append(a[-1]),
    )

    reply = chat.say("cancel my order")

    # The parcel is physically moving; only the seller can stop it.
    assert calls == []
    assert chat.state == "completed"
    assert "already shipped" in reply["message"]
    assert told


def test_a_cancellation_always_notifies_the_seller(chat, monkeypatch):
    cancellable_chat(chat, monkeypatch)
    told = []
    monkeypatch.setattr(
        public_chat_service,
        "notify_seller_attention",
        lambda *a, **k: told.append(a[-1]),
    )

    chat.say("cancel my order")
    reply = chat.say("yes cancel")

    # The seller has stock to put back and may want to follow up.
    assert told
    assert "back in stock" in reply["message"]


def test_a_race_with_dispatch_fails_safely(chat, monkeypatch):
    from app.core.errors import ApiError

    cancellable_chat(chat, monkeypatch)
    monkeypatch.setattr(
        public_chat_service,
        "update_order_status",
        lambda *a: (_ for _ in ()).throw(
            ApiError("invalid_status_transition", "no", 409),
        ),
    )
    told = []
    monkeypatch.setattr(
        public_chat_service, "notify_seller_attention", lambda *a, **k: told.append(a),
    )

    chat.say("cancel my order")
    reply = chat.say("yes cancel")

    # Dispatched between the question and the answer: report it, do not crash.
    assert "already moved on" in reply["message"]
    assert told


def test_a_session_with_no_order_cannot_cancel_anything(chat, monkeypatch):
    def fail(*_a):
        raise AssertionError("must not touch order status without an order")

    monkeypatch.setattr(public_chat_service, "update_order_status", fail)

    reply = chat.say("cancel my order")

    # Falls through to normal handling rather than acting on someone's order.
    assert chat.state != "confirming-cancel"
    assert "cannot be undone" not in reply["message"]


def test_a_packed_order_is_escalated_rather_than_self_cancelled(chat, monkeypatch):
    calls = cancellable_chat(chat, monkeypatch, status="packed")
    told = []
    monkeypatch.setattr(
        public_chat_service,
        "notify_seller_attention",
        lambda *a, **k: told.append(a[-1]),
    )

    reply = chat.say("cancel my order")

    # The seller's own rules permit packed -> cancelled, but by then they have
    # picked, boxed and often labelled it. Undoing that work is their call.
    assert calls == []
    assert "already packed" in reply["message"]
    assert told


def test_a_confirmed_order_is_still_cancellable_by_the_customer(chat, monkeypatch):
    calls = cancellable_chat(chat, monkeypatch, status="confirmed")

    chat.say("cancel my order")
    chat.say("yes cancel")

    assert [order_id for order_id, _payload in calls] == ["o1"]


def test_the_customer_cancel_window_is_narrower_than_the_sellers():
    from app.services.order_service import STATUS_TRANSITIONS
    from app.services.public_chat_service import CUSTOMER_CANCELLABLE_STATUSES

    seller_can_cancel = {
        status
        for status, allowed in STATUS_TRANSITIONS.items()
        if "cancelled" in allowed
    }

    # Every status the customer may cancel from must be one the seller allows,
    # so the chat can never drive an invalid transition.
    assert CUSTOMER_CANCELLABLE_STATUSES <= seller_can_cancel
    assert "packed" in seller_can_cancel
    assert "packed" not in CUSTOMER_CANCELLABLE_STATUSES


def test_cancelling_with_items_in_the_cart_clears_the_draft_not_a_past_order(chat, monkeypatch):
    def fail(*_a):
        raise AssertionError("must not touch a placed order while a draft is open")

    monkeypatch.setattr(public_chat_service, "update_order_status", fail)
    monkeypatch.setattr(
        public_chat_service,
        "latest_order_for_session",
        lambda *a: {"id": "o1", "orderNumber": "VD-000013",
                    "fulfilmentStatus": "delivered", "totalAmountMinor": 100000},
    )
    # A customer who has ordered before keeps orderId on the session forever.
    chat.session["orderId"] = "o1"
    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")

    reply = chat.say("I want 55 if not available cancel my order")

    # They meant "do not place this one", not "undo VD-000013".
    assert chat.cart == []
    assert chat.state == "browsing"
    assert "VD-000013" not in reply["message"]
    assert "cleared" in reply["message"]
    assert "earlier order is not affected" in reply["message"]


def test_cancelling_mid_checkout_clears_the_draft(chat, monkeypatch):
    monkeypatch.setattr(public_chat_service, "latest_order_for_session", lambda *a: None)
    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    chat.say("that's all", intent="finished_selecting")
    assert chat.state == "collecting-name"

    chat.say("cancel my order")

    assert chat.cart == []
    assert chat.session["customerDraft"] == {}
    assert chat.state == "browsing"


def test_cancelling_with_no_draft_still_targets_the_placed_order(chat, monkeypatch):
    calls = cancellable_chat(chat, monkeypatch, status="confirmed")

    reply = chat.say("cancel my order")

    assert chat.state == "confirming-cancel"
    assert "VD-000012" in reply["message"]
    chat.say("yes cancel")
    assert [order_id for order_id, _payload in calls] == ["o1"]


BANK = {
    "bankName": "Commercial Bank",
    "branch": "Nugegoda",
    "accountName": "VS Tech Store",
    "accountNumber": "8001234567",
}


def test_asking_to_pay_by_transfer_sends_the_account_and_records_the_intent(chat):
    chat.bank = BANK

    reply = chat.say("can I do a bank transfer?")

    assert "8001234567" in reply["message"]
    assert "Commercial Bank" in reply["message"]
    # Recorded so the order carries it and the seller watches for the money.
    assert chat.session["customerDraft"]["paymentMethod"] == "deposit"


def test_a_seller_with_no_bank_details_says_cash_on_delivery_only(chat):
    chat.bank = {}

    reply = chat.say("can I do a bank transfer?")

    # Never send a half-empty account block.
    assert "cash on delivery only" in reply["message"]
    assert chat.session["customerDraft"].get("paymentMethod") is None


def test_the_recorded_payment_method_reaches_the_order(chat, monkeypatch):
    created = []
    monkeypatch.setattr(
        public_chat_service,
        "create_public_chat_order",
        lambda _db, _sid, _tok, payload: created.append(payload)
        or {"id": "o1", "orderNumber": "VD-000014", "subtotalMinor": 900000,
            "deliveryFeeMinor": 45000, "totalAmountMinor": 945000},
    )
    chat.bank = BANK

    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    chat.say("can I do a bank transfer?")
    chat.say("that's all", intent="finished_selecting")
    chat.say("Nimal Perera")
    chat.say("0771234567")
    chat.say("skip")
    chat.say("No. 45 Park Road")
    chat.say("Colombo")
    chat.say("Nugegoda")
    chat.say("skip")
    # The direct answer is what counts now: the customer is asked outright
    # before the summary, and that answer outranks anything inferred from an
    # earlier question about bank transfers.
    chat.say("half bank transfer")
    chat.say("confirm order")

    assert created and created[0]["paymentMethod"] == "deposit"


def test_a_plain_order_is_still_cash_on_delivery(chat, monkeypatch):
    created = []
    monkeypatch.setattr(
        public_chat_service,
        "create_public_chat_order",
        lambda _db, _sid, _tok, payload: created.append(payload)
        or {"id": "o1", "orderNumber": "VD-000015", "subtotalMinor": 900000,
            "deliveryFeeMinor": 45000, "totalAmountMinor": 945000},
    )

    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    chat.say("that's all", intent="finished_selecting")
    chat.say("Nimal Perera")
    chat.say("0771234567")
    chat.say("skip")
    chat.say("No. 45 Park Road")
    chat.say("Colombo")
    chat.say("Nugegoda")
    chat.say("skip")
    chat.say("cash on delivery")
    chat.say("confirm order")

    assert created and created[0]["paymentMethod"] == "cod"


def test_the_stated_deposit_amount_is_captured_and_sent_to_the_order(chat, monkeypatch):
    created = []
    monkeypatch.setattr(
        public_chat_service,
        "create_public_chat_order",
        lambda _db, _sid, _tok, payload: created.append(payload)
        or {"id": "o1", "orderNumber": "VD-000016", "subtotalMinor": 900000,
            "deliveryFeeMinor": 45000, "totalAmountMinor": 945000},
    )
    chat.bank = BANK
    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    chat.say("can I do a bank transfer?")

    reply = chat.say("just half")

    assert chat.session["customerDraft"]["depositChoice"] == "part"
    assert "balance on delivery" in reply["message"]

    for line in ["that's all", "Nimal", "0771234567", "skip", "No. 45 Park Road",
                 "Colombo", "Nugegoda", "skip", "half bank transfer",
                 "confirm order"]:
        chat.say(line, intent="finished_selecting" if line == "that's all" else None)

    assert created[0]["depositChoice"] == "part"
    assert created[0]["paymentMethod"] == "deposit"


def test_a_full_transfer_is_captured_as_full(chat):
    chat.bank = BANK
    chat.say("can I do a bank transfer?")

    reply = chat.say("I will send the full amount")

    assert chat.session["customerDraft"]["depositChoice"] == "full"
    assert "the full amount" in reply["message"]


def test_the_amount_question_is_only_asked_once(chat):
    chat.bank = BANK
    chat.say("can I do a bank transfer?")
    chat.say("full")

    # A later unrelated message must not be re-read as an amount.
    reply = chat.say("do you have GM2 pro?", intent="product_question")

    assert chat.session["customerDraft"]["depositChoice"] == "full"
    assert "Noted" not in reply["message"]


def test_suggestions_follow_the_conversation(chat):
    # Nothing chosen yet.
    reply = chat.say("hello", intent="greeting")
    assert "show-products" in reply["suggestions"]
    assert "checkout" not in reply["suggestions"]

    # Being asked how many: offer the numbers, nothing else.
    reply = chat.say("mata GM2 pro ona", intent="start_order",
                     productQuery="GM2 pro", quantity=0, quantityMode="total")
    assert reply["suggestions"] == ["qty-1", "qty-2", "qty-3"]

    # With items in the cart, finishing becomes the useful next step.
    reply = chat.say("2", intent="set_quantity", quantity=2, quantityMode="total")
    assert "checkout" in reply["suggestions"]


def test_no_suggestions_while_typing_a_name_or_address(chat):
    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    reply = chat.say("that's all", intent="finished_selecting")

    # A chip cannot answer "what is your name", and would sit in the way.
    assert reply["suggestions"] == []

    chat.say("Nimal Perera")
    reply = chat.say("0771234567")

    # The optional steps are the exception: "skip" is a real answer.
    assert reply["suggestions"] == ["skip"]


def test_the_confirmation_step_offers_both_ways_out(chat):
    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    for line in ["that's all", "Nimal", "0771234567", "skip",
                 "No. 45 Park Road", "Colombo", "Nugegoda"]:
        chat.say(line, intent="finished_selecting" if line == "that's all" else None)
    reply = chat.say("skip")

    # Payment is asked between the delivery note and the summary.
    assert reply["suggestions"] == ["pay-cod", "pay-bank-full", "pay-bank-half"]

    reply = chat.say("cash on delivery")

    assert reply["suggestions"] == ["confirm-order", "change-order"]


def test_bank_details_offer_the_two_amounts(chat):
    chat.bank = BANK
    reply = chat.say("can I do a bank transfer?")

    assert reply["suggestions"] == ["pay-full", "pay-part"]


def test_a_completed_order_offers_order_actions(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "latest_order_for_session",
        lambda *a: {"id": "o1", "orderNumber": "VD-000012",
                    "fulfilmentStatus": "packed", "totalAmountMinor": 945000},
    )
    chat.session["orderId"] = "o1"
    chat.session["state"] = "completed"
    chat.session["status"] = "completed"

    reply = chat.say("where is my order")

    assert reply["suggestions"] == ["order-status", "another-order", "cancel-order"]


def test_answering_the_district_keeps_an_english_chat_in_english(chat):
    # Reproduces the reported bug: an English conversation, "what is the
    # delivery fee", then "Gampaha" - and every later reply came back Sinhala.
    chat.say("what is the delivery fee", intent="delivery_quote")
    assert chat.state == "quoting-district"

    reply = chat.say("Gampaha", intent="delivery_quote", language="si")

    assert reply["language"] == "en"
    assert chat.session["language"] == "en"


def test_the_district_reply_is_not_sent_to_the_classifier(chat, monkeypatch):
    calls = []
    monkeypatch.setattr(public_chat_service, "storefront_intent", REAL_STOREFRONT_INTENT)
    monkeypatch.setattr(
        public_chat_service,
        "generate_storefront_intent",
        lambda message, *a: calls.append(message) or None,
    )

    chat.session["state"] = "quoting-district"
    chat.say("Gampaha")

    # A district name is data. Classifying it made the model guess a language
    # from a place name, and it costs a provider call for nothing.
    assert calls == []


def test_asking_where_the_shop_is_answers_from_the_store_location(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {
            "business": {
                "name": "VS Tech Store",
                "storefrontFaq": "",
                "storeLocation": {
                    "isOnlineOnly": False,
                    "addressLine": "No. 45 Galle Road",
                    "city": "Nugegoda",
                    "district": "Colombo",
                },
            },
            "products": catalogue(),
        },
    )

    reply = chat.say("do you have a physical shop?")

    assert reply["action"] == "show-store-location"
    assert "No. 45 Galle Road" in reply["message"]


def test_an_online_only_seller_tells_the_customer_not_to_travel(chat):
    # The fixture's business has no storeLocation configured.
    reply = chat.say("where are you located?")

    assert "online store" in reply["message"]


def test_naming_a_product_shows_it_rather_than_starting_an_order(chat):
    # The classifier reads a bare product name as start_order, which sent the
    # customer to "how many would you like?" before they had seen the price,
    # the photos or the reviews.
    reply = chat.say("GM2 Pro Earbuds", intent="start_order",
                     productQuery="GM2 Pro Earbuds", quantity=0, quantityMode="total")

    assert chat.state == "browsing"
    assert chat.cart == []
    assert reply["action"] == "show-product"
    # A full overview carries the photos, the reviews and the similar strip.
    assert reply["product"]["id"] == "buds"
    assert reply["products"]
    assert "order-this" in reply["suggestions"]


def test_naming_a_product_with_a_quantity_still_orders(chat):
    reply = chat.say("2 GM2 Pro Earbuds", intent="start_order",
                     productQuery="GM2 Pro Earbuds", quantity=2, quantityMode="total")

    # Extra words beyond the name mean they really are ordering.
    assert chat.cart == [{"variantId": "v-buds", "quantity": 2}]
    assert reply["action"] == "start-order"


def test_an_ambiguous_budget_asks_which_scope(chat, monkeypatch):
    asked = []
    monkeypatch.setattr(
        public_chat_service,
        "generate_catalogue_answer",
        lambda question, scope, *a: asked.append((question, [p["id"] for p in scope]))
        or "The Runner Shoes at LKR 9,000.00 fit that budget.",
    )
    chat.session["lastCategoryShown"] = "Shoes"

    reply = chat.say("show me below Rs 2000")

    # Guessing the scope is wrong half the time, so it asks first.
    assert chat.state == "clarifying-scope"
    assert "Shoes" in reply["message"]
    assert asked == []

    chat.say("shoes")

    # The original budget question is carried into the scoped answer.
    question, scope = asked[0]
    assert "below Rs 2000" in question
    assert scope == ["shoes"]
    assert chat.state == "browsing"


def test_choosing_any_product_widens_the_search(chat, monkeypatch):
    scopes = []
    monkeypatch.setattr(
        public_chat_service,
        "generate_catalogue_answer",
        lambda question, scope, *a: scopes.append([p["id"] for p in scope]) or "Nothing under that.",
    )
    chat.session["lastCategoryShown"] = "Shoes"

    chat.say("show me below Rs 2000")
    chat.say("any product")

    assert scopes[0] == ["buds", "shoes"]


def test_a_budget_with_no_category_in_view_does_not_ask(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "generate_catalogue_answer",
        lambda *a: "Nothing under that price.",
    )

    reply = chat.say("show me below Rs 2000")

    # Nothing to disambiguate against, so answering directly is right.
    assert chat.state == "browsing"
    assert "Just to be sure" not in reply["message"]


def test_comparing_the_products_on_screen_uses_only_those(chat, monkeypatch):
    scopes = []
    monkeypatch.setattr(
        public_chat_service,
        "generate_catalogue_answer",
        lambda question, scope, *a: scopes.append([p["id"] for p in scope])
        or "The Runner Shoes wins on build quality.",
    )
    # Two products were just listed.
    chat.session["lastShownProductIds"] = ["shoes"]
    chat.session["lastCategoryShown"] = "Shoes"

    chat.say("what is best among these two", intent="product_question")

    # Scoped to what is on screen, not the whole catalogue or the category.
    assert scopes and scopes[0] == ["shoes"]


def test_an_english_question_switches_a_sinhala_chat_back(chat):
    chat.session["language"] = "si"

    reply = chat.say(
        "what is best among these two I meant technically",
        intent="product_question",
        language="en",
    )

    # A settled language used to short-circuit before the detected language was
    # consulted, so Sinhala was a one-way trap.
    assert reply["language"] == "en"


def test_best_among_them_compares_the_products_on_screen(chat, monkeypatch):
    scopes = []
    monkeypatch.setattr(
        public_chat_service,
        "generate_catalogue_answer",
        lambda question, scope, *a: scopes.append([p["id"] for p in scope])
        or "The Runner Shoes wins on build quality.",
    )
    # Two products listed, and an unrelated product remembered from earlier.
    chat.session["lastShownProductIds"] = ["buds", "shoes"]
    chat.session["selectedProductId"] = "buds"

    # The single-product path must not claim this message. Asserting only on
    # the scope cannot tell the two apart, because the end-of-sequence
    # fallthrough scopes to the same products.
    product_answers = []
    monkeypatch.setattr(
        public_chat_service,
        "generate_product_answer",
        lambda *a, **k: product_answers.append(a[1]) or "About one product.",
    )

    reply = chat.say("what is best among them", intent="product_question")

    assert product_answers == [], "the remembered product claimed the comparison"
    assert scopes and scopes[0] == ["buds", "shoes"]
    assert "wins on build quality" in reply["message"]


def test_a_comparison_needs_more_than_one_product_on_screen(chat, monkeypatch):
    scopes = []
    monkeypatch.setattr(
        public_chat_service,
        "generate_catalogue_answer",
        lambda question, scope, *a: scopes.append([p["id"] for p in scope]) or "Only one option.",
    )
    chat.session["lastShownProductIds"] = ["buds"]
    chat.session["lastCategoryShown"] = "Earbuds"

    chat.say("what is best among them", intent="product_question")

    # One product is not a comparison, so it falls through to the ordinary
    # answer path scoped to the category rather than to a list of one.
    assert scopes and scopes[0] == ["buds"]


def test_checking_the_cart_mid_checkout_does_not_restart_it(chat):
    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    chat.say("that is everything", intent="finished_selecting")

    assert chat.state == "collecting-name"

    reply = chat.say("show my cart", intent="show_cart")

    # Reading the cart back is not a step in the conversation. Sending them to
    # browsing dropped a customer half way through checkout, who was then
    # asked for their name again from the top.
    assert chat.state == "collecting-name"
    assert "GM2" in reply["message"]


def open_order(status="needs-confirmation"):
    return {
        "id": "order-1",
        "orderNumber": "VD-000041",
        "fulfilmentStatus": status,
        "itemCount": 2,
        "totalAmountMinor": 500000,
    }


def test_an_unconfirmed_order_is_offered_the_new_items(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "latest_order_for_session",
        lambda *a: open_order(),
    )
    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    reply = chat.say("that is everything", intent="finished_selecting")

    # Two orders minutes apart usually mean one delivery. Asking beats both
    # deciding for them and silently charging two delivery fees.
    assert chat.state == "choosing-order-merge"
    assert "VD-000041" in reply["message"]


def test_a_confirmed_order_is_not_offered(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "latest_order_for_session",
        lambda *a: open_order("preparing"),
    )
    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    chat.say("that is everything", intent="finished_selecting")

    # Once the seller is packing it, the parcel no longer matches the record.
    assert chat.state == "collecting-name"


def test_choosing_to_merge_adds_the_items_and_reprices(chat, monkeypatch):
    added = {}

    def fake_add(_db, _business, order_id, _uid, items):
        added["orderId"] = order_id
        added["items"] = items
        return {**open_order(), "itemCount": 4, "totalAmountMinor": 950000}

    monkeypatch.setattr(
        public_chat_service, "latest_order_for_session", lambda *a: open_order(),
    )
    monkeypatch.setattr(public_chat_service, "add_items_to_order", fake_add)
    monkeypatch.setattr(
        public_chat_service, "order_information_message", lambda _order: "Order info.",
    )

    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    chat.say("that is everything", intent="finished_selecting")
    reply = chat.say("add to my order", intent="confirm_order")

    assert added["orderId"] == "order-1"
    assert added["items"] == [{"variantId": "v-buds", "quantity": 2}]
    # The cart must be emptied, or the next message re-uploads it and the same
    # items are added to the order a second time.
    assert chat.cart == []
    assert chat.state == "completed"
    assert "VD-000041" in reply["message"]


def test_choosing_a_separate_order_continues_to_checkout(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service, "latest_order_for_session", lambda *a: open_order(),
    )
    monkeypatch.setattr(
        public_chat_service,
        "add_items_to_order",
        lambda *a: pytest.fail("a separate order must not touch the old one"),
    )

    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    chat.say("that is everything", intent="finished_selecting")
    reply = chat.say("separate order", intent="new_order")

    assert chat.state == "collecting-name"
    assert "full name" in reply["message"].lower()


def test_stock_lost_between_the_offer_and_the_choice_falls_back(chat, monkeypatch):
    from app.core.errors import ApiError

    def sold_out(*_arguments):
        raise ApiError("insufficient_stock", "Only 1 unit(s) are available.", 409)

    monkeypatch.setattr(
        public_chat_service, "latest_order_for_session", lambda *a: open_order(),
    )
    monkeypatch.setattr(public_chat_service, "add_items_to_order", sold_out)

    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    chat.say("that is everything", intent="finished_selecting")
    reply = chat.say("add to my order", intent="confirm_order")

    # Losing the cart because a merge failed would be the worst outcome: the
    # customer has to start again from an empty basket.
    assert chat.state == "collecting-name"
    assert "available" in reply["message"]


def test_an_unclear_reply_asks_again_rather_than_guessing(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service, "latest_order_for_session", lambda *a: open_order(),
    )
    chat.say("mata GM2 pro dekak ona", intent="start_order",
             productQuery="GM2 pro", quantity=2, quantityMode="total")
    chat.say("that is everything", intent="finished_selecting")
    chat.say("hmm", intent="unknown")

    # Guessing either way is expensive: a wrong merge changes an order the
    # customer did not want changed, a wrong split charges a second delivery.
    assert chat.state == "choosing-order-merge"


def test_a_new_order_asks_what_they_need_on_a_large_catalogue(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": big_catalogue()},
    )
    chat.session["state"] = "completed"
    chat.session["status"] = "completed"

    reply = chat.say("I want to order again", intent="new_order")

    # Same rule as any other catalogue request. Dumping twelve products makes
    # the customer do the filtering, and it buries the conversation on a phone.
    assert reply["action"] == "show-categories"
    assert reply["products"] == []
    assert reply["categories"]


def show_both(chat):
    """Put two products on screen, the way a category listing would."""
    chat.session["lastShownProductIds"] = ["buds", "shoes"]


def test_compare_returns_a_table_and_no_verdict(chat, monkeypatch):
    calls = {}
    monkeypatch.setattr(
        public_chat_service,
        "generate_comparison_answer",
        lambda products, language: calls.setdefault(
            "products", [item["id"] for item in products],
        ) and None or "| Spec | A | B |\n|---|---|---|\n| Price | 1 | 2 |",
    )
    monkeypatch.setattr(
        public_chat_service,
        "generate_catalogue_answer",
        lambda *a, **k: pytest.fail("a comparison must not ask for a verdict"),
    )
    show_both(chat)

    reply = chat.say("compare these", intent="product_question")

    # "Compare" and "which is best" want opposite answers. Sharing a branch
    # answered a comparison request with a recommendation, hiding the very
    # differences that were asked for.
    assert calls["products"] == ["buds", "shoes"]
    assert "| Spec |" in reply["message"]
    assert [item["id"] for item in reply["products"]] == ["buds", "shoes"]


def test_the_best_product_path_is_untouched(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "generate_catalogue_answer",
        lambda *a, **k: "The GM2 Pro Earbuds are the better buy. [ANSWERED]",
    )
    monkeypatch.setattr(
        public_chat_service,
        "generate_comparison_answer",
        lambda *a, **k: pytest.fail("a recommendation must not become a table"),
    )
    show_both(chat)

    reply = chat.say("what is best from these", intent="product_question")

    assert "better buy" in reply["message"]


def test_a_comparison_falls_back_to_stored_facts_when_the_ai_is_down(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service, "generate_comparison_answer", lambda *a, **k: None,
    )
    show_both(chat)

    reply = chat.say("compare these two", intent="product_question")

    # Rate limited is the normal case on the free tier. A table from stored
    # fields is worse than the model reading the descriptions, but it is an
    # answer.
    assert "|" in reply["message"]
    assert "Price" in reply["message"]


def test_a_named_category_is_compared_without_anything_on_screen(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": big_catalogue()},
    )
    monkeypatch.setattr(
        public_chat_service,
        "generate_comparison_answer",
        lambda products, language: "| Spec |\n|---|\n"
        + f"| {len(products)} compared |",
    )

    # "Compare the earbuds" carries its own scope, so it must not depend on
    # what happened to be listed before it - here, nothing was.
    reply = chat.say("compare the earbuds", intent="product_question")

    assert "compared |" in reply["message"]
    assert len(reply["products"]) > 1
    assert all(item["categoryName"] == "Earbuds" for item in reply["products"])


def test_comparing_one_product_asks_what_to_compare_it_with(chat):
    chat.session["lastShownProductIds"] = ["buds"]

    reply = chat.say("compare this", intent="product_question")

    # A one-column table is not a comparison.
    assert "at least two" in reply["message"]


def test_vs_is_read_as_a_comparison(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "generate_comparison_answer",
        lambda *a, **k: "| Spec | A | B |",
    )
    show_both(chat)

    reply = chat.say("GM2 Pro Earbuds vs Runner Shoes", intent="product_question")

    assert "| Spec |" in reply["message"]


def watch_catalogue():
    return [
        {"id": "t800", "name": "T800 Ultra Smart Watch", "categoryName": "Smart watch",
         "description": "Bluetooth calling, IP67 water resistant.",
         "sellingPriceMinor": 130000, "weightGrams": 100, "availableStock": 48,
         "media": [], "variants": [{"id": "v-t800", "size": "", "availableStock": 48,
                                    "sellingPriceMinor": 130000, "weightGrams": 100}]},
        {"id": "zeblace", "name": "Zeblace Gts 3 Smart Watch", "categoryName": "Smart watch",
         "description": "AMOLED display, 30 days battery.",
         "sellingPriceMinor": 500000, "weightGrams": 100, "availableStock": 40,
         "media": [], "variants": [{"id": "v-zeb", "size": "", "availableStock": 40,
                                    "sellingPriceMinor": 500000, "weightGrams": 100}]},
    ]


def test_a_feature_request_filters_the_category_without_calling_the_ai(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": watch_catalogue()},
    )
    monkeypatch.setattr(
        public_chat_service,
        "generate_catalogue_answer",
        lambda *a, **k: pytest.fail("the descriptions answer this without a call"),
    )

    reply = chat.say("send me smart watches with water resistant",
                     intent="show_category", categoryQuery="Smart watch")

    # Only the watch whose description mentions it. Listing both would read as
    # though the Zeblace is water resistant too.
    assert [item["id"] for item in reply["products"]] == ["t800"]
    assert "water resistant" in reply["message"]


def test_a_feature_nobody_has_is_said_plainly(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": watch_catalogue()},
    )

    reply = chat.say("send me smart watches with satellite gps",
                     intent="show_category", categoryQuery="Smart watch")

    # The AI is stubbed to None here, standing in for a rate limited provider.
    # A plain "we do not have it" plus alternatives beats both a wrong yes and
    # a dead end.
    assert "do not have any" in reply["message"]
    assert reply["products"], "an outright no with nothing beside it ends the chat"


def test_the_ai_is_consulted_before_denying_a_feature(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": watch_catalogue()},
    )
    monkeypatch.setattr(
        public_chat_service,
        "generate_catalogue_answer",
        lambda *a, **k: "The Zeblace Gts 3 Smart Watch has an always-on "
                        "screen. [ANSWERED]",
    )

    reply = chat.say("send me smart watches with always on display",
                     intent="show_category", categoryQuery="Smart watch")

    # A seller may describe a feature in words the matcher does not know, so
    # the model gets a look before the customer is told it does not exist.
    assert "always-on" in reply["message"]
    assert [item["id"] for item in reply["products"]] == ["zeblace"]


def test_a_plain_category_request_still_lists_the_category(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": watch_catalogue()},
    )

    reply = chat.say("show me smart watches", intent="show_category",
                     categoryQuery="Smart watch")

    assert len(reply["products"]) == 2


def test_a_group_of_products_offers_to_compare_them(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": big_catalogue()},
    )

    reply = chat.say("show me earbuds", intent="show_category",
                     categoryQuery="Earbuds")

    # Comparing is the next thing a customer wants from a list and the hardest
    # thing to phrase by typing.
    assert len(reply["products"]) > 1
    assert "compare-these" in reply["suggestions"]


def test_a_single_product_does_not_offer_a_comparison(chat):
    reply = chat.say("tell me about GM2 pro", intent="product_question",
                     productQuery="GM2 pro")

    assert "compare-these" not in reply["suggestions"]


def test_the_compare_chip_sends_a_message_the_bot_acts_on(chat, monkeypatch):
    # The chip is only useful if its wording reaches the comparison branch.
    # "compare these" is what the storefront sends for this id.
    monkeypatch.setattr(
        public_chat_service,
        "generate_comparison_answer",
        lambda *a, **k: "| Spec | A | B |",
    )
    chat.session["lastShownProductIds"] = ["buds", "shoes"]

    reply = chat.say("compare these", intent="product_question")

    assert "| Spec |" in reply["message"]


def sim_watches():
    return [
        {"id": "t800", "name": "T800 Ultra Smart Watch", "categoryName": "Smart watch",
         "description": "Bluetooth calling, IP67 water resistant. No SIM slot.",
         "sellingPriceMinor": 130000, "weightGrams": 100, "availableStock": 48,
         "media": [], "variants": [{"id": "v-t800", "size": "", "availableStock": 48,
                                    "sellingPriceMinor": 130000, "weightGrams": 100}]},
        {"id": "zeblace", "name": "Zeblace Gts 3 Smart Watch", "categoryName": "Smart watch",
         "description": "AMOLED display, 30 days battery.",
         "sellingPriceMinor": 500000, "weightGrams": 100, "availableStock": 40,
         "media": [], "variants": [{"id": "v-zeb", "size": "", "availableStock": 40,
                                    "sellingPriceMinor": 500000, "weightGrams": 100}]},
    ]


def test_a_sinhala_feature_question_is_not_answered_with_products_lacking_it(
    chat, monkeypatch,
):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": sim_watches()},
    )

    reply = chat.say("sim danna puluwan smart watch nadda",
                     intent="product_question", productQuery="smart watch")

    # Both watches matched on "smart watch" and the bot asked which one was
    # meant - about two products that neither take a SIM. The Sinhala request
    # words were also being read as features, so nothing could ever match.
    assert "do not have any" in reply["message"]
    assert "which one" not in reply["message"].lower()


def test_the_alternatives_are_still_offered_when_the_feature_is_missing(
    chat, monkeypatch,
):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": sim_watches()},
    )

    reply = chat.say("sim danna puluwan ewa evanna", intent="product_question",
                     productQuery="smart watch")

    # "We do not have it" with nothing beside it ends the conversation, and
    # the customer came here to buy something.
    assert len(reply["products"]) > 0


def power_banks():
    def bank(identifier, name, description, price):
        return {
            "id": identifier, "name": name, "categoryName": "PowerBanks",
            "description": description, "sellingPriceMinor": price,
            "weightGrams": 300, "availableStock": 20, "media": [],
            "variants": [{"id": f"v-{identifier}", "size": "",
                          "availableStock": 20, "sellingPriceMinor": price,
                          "weightGrams": 300}],
        }

    return [
        bank("wiwu", "WIWU Essen Power Bank", "10000mAh, 18W fast charging.", 399000),
        bank("xiaomi", "Xiaomi Power Bank", "20000mAh, 18W fast charge, dual USB.", 699000),
        bank("aspor", "ASPOR A337 Power Bank", "20000mAh with built-in cables.", 550000),
    ]


def test_a_feature_survives_an_order_intent(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": power_banks()},
    )

    reply = chat.say("send me 20000mah power banks", intent="start_order",
                     categoryQuery="PowerBanks")

    # The ordering branch asked "which PowerBanks would you like to order?"
    # and listed all three, ignoring the capacity entirely. A feature is a
    # filter whatever the customer intends to do with the result.
    assert [item["id"] for item in reply["products"]] == ["xiaomi", "aspor"]


def test_a_feature_survives_a_plain_listing_request(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": power_banks()},
    )

    reply = chat.say("show me 10000mah power banks", intent="show_category",
                     categoryQuery="PowerBanks")

    assert [item["id"] for item in reply["products"]] == ["wiwu"]


def test_a_question_about_one_product_is_not_treated_as_a_filter(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": power_banks()},
    )
    monkeypatch.setattr(
        public_chat_service,
        "generate_product_answer",
        lambda *a, **k: "The Xiaomi Power Bank is 20000mAh. [ANSWERED]",
    )

    reply = chat.say("is the Xiaomi Power Bank 20000mah?",
                     intent="product_question", productQuery="Xiaomi Power Bank")

    # Naming one product is a question about it, not a filter over a group.
    assert reply["action"] in {"show-product", "product-answer"}


def test_a_product_overview_does_not_repeat_what_the_card_shows(chat):
    reply = chat.say("tell me about GM2 pro", intent="product_question",
                     productQuery="GM2 pro")

    # The card carries name, price, warranty, stock and description in a
    # readable layout. Printing them in the message too showed everything
    # twice and pushed the card off a phone screen.
    assert reply["product"]["id"] == "buds"
    assert "Price: LKR" not in reply["message"]
    assert "Black wireless earbuds" not in reply["message"]
    # The card needs the facts it is now responsible for showing.
    assert reply["product"]["sellingPriceMinor"] == 450000


def test_the_conversation_window_accumulates_both_sides(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service, "save_chat_message", REAL_SAVE_CHAT_MESSAGE,
    )
    chat.say("hello", intent="greeting")
    chat.say("show me earbuds", intent="show_category", categoryQuery="Earbuds")

    turns = chat.session["recentTurns"]
    roles = [turn["role"] for turn in turns]

    # Both halves, oldest first. Without the assistant's turns the model cannot
    # tell what "the second one" refers to.
    assert "customer" in roles and "assistant" in roles
    assert turns[0]["text"] == "hello"


def test_repeated_answers_are_not_collapsed(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service, "save_chat_message", REAL_SAVE_CHAT_MESSAGE,
    )
    # "skip", "2" and "yes" repeat constantly in a checkout. An append that
    # deduplicates would quietly drop them and leave a history that never
    # happened.
    for _ in range(3):
        chat.say("skip")

    texts = [turn["text"] for turn in chat.session["recentTurns"]]

    assert texts.count("skip") == 3


def test_the_window_stays_small(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service, "save_chat_message", REAL_SAVE_CHAT_MESSAGE,
    )
    for index in range(12):
        chat.say(f"message {index}")

    # Long enough for a browse, a few questions and a follow-up; short enough
    # that an old topic cannot outweigh the current one, and it caps the tokens
    # spent on history for every single call.
    assert len(chat.session["recentTurns"]) <= 12


def test_the_model_is_given_the_turns_before_the_current_message(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service, "save_chat_message", REAL_SAVE_CHAT_MESSAGE,
    )
    # The real wrapper, so the spy below is actually reached.
    monkeypatch.setattr(
        public_chat_service, "storefront_intent", REAL_STOREFRONT_INTENT,
    )
    seen = {}
    monkeypatch.setattr(
        public_chat_service,
        "generate_storefront_intent",
        lambda message, names, categories, state, history=None: seen.update(
            {"message": message, "history": list(history or [])},
        ) or {"intent": "product_question", "language": "en"},
    )

    chat.say("show me earbuds", intent="show_category", categoryQuery="Earbuds")
    chat.say("is the second one waterproof?")

    # The current message is passed separately; including it in the history too
    # would read as though the customer asked it twice.
    assert seen["message"] == "is the second one waterproof?"
    assert all(turn["text"] != seen["message"] for turn in seen["history"])
    assert any("earbuds" in turn["text"] for turn in seen["history"])


def test_a_partly_named_category_resolves_without_asking(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": [
                        {**item, "categoryName": "Routers and modems"}
                        for item in big_catalogue()[:4]
                    ]},
    )

    reply = chat.say("do you have routers", intent="unknown")

    # A seller writes "Routers and modems"; a customer types "routers".
    # Requiring every word meant the customer had to guess the seller's exact
    # wording or get nothing at all.
    assert reply["products"], reply["message"]
    assert "did not catch" not in reply["message"]


def test_a_model_code_alone_offers_that_product(chat):
    reply = chat.say("do you have the gm2", intent="unknown")

    # A code mixing letters and digits identifies one product even when the
    # rest of the name is wrong or missing.
    assert "Did you mean" in reply["message"]
    assert "GM2" in reply["message"]


def test_an_ambiguous_word_still_offers_the_category_list(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "session_catalog",
        lambda *a: {"business": {"name": "VS Tech", "storefrontFaq": ""},
                    "products": big_catalogue()},
    )

    reply = chat.say("qwertyuiop", intent="unknown")

    # Nothing to guess at. Inventing a suggestion would be worse than asking.
    assert "Did you mean" not in reply["message"]
    assert reply["categories"]


def test_a_delivery_time_question_is_not_answered_with_a_price(chat, monkeypatch):
    monkeypatch.setattr(
        public_chat_service,
        "recommend_couriers",
        lambda _db, _biz, weight, _district: [
            {
                "courier": {"id": "c1", "name": "Royal Express",
                            "averageDeliveryDays": 3, "extraKgPriceMinor": 10000,
                            "districtFirstKgPricesMinor": {"gampaha": 45000}},
                "deliveryFeeMinor": 45000,
                "score": 90.0,
            },
        ],
    )
    reply = chat.say("delivery time eka kohomada", intent="delivery_quote")

    # Asking "how long does it take" and being told "I will check the fee",
    # twice, reads as not listening - the question was never registered.
    assert "how long delivery takes" in reply["message"]
    assert "delivery fee for that district" not in reply["message"]

    reply = chat.say("Gampaha")

    # And the answer leads with the days rather than burying them under a
    # price breakdown the customer did not ask for.
    assert reply["message"].index("days") < reply["message"].index("LKR")


def test_a_delivery_fee_question_still_leads_with_the_price(chat):
    reply = chat.say("delivery fee kiyada", intent="delivery_quote")

    assert "delivery fee for that district" in reply["message"]

    reply = chat.say("Gampaha")

    assert reply["message"].startswith("Delivery to Gampaha")
