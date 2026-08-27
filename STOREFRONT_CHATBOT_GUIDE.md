# Vendly storefront chatbot — build-from-scratch guide

This document explains the customer storefront chatbot in a way that another developer or agent can reproduce and maintain it. It is written for the active project at `D:/Documents/orderflow/vendly-lk-web`.

## 1. What the chatbot does

The public storefront is reached with a seller short link such as `/s/L23OOWs`. It loads only that seller's active catalogue. A visitor can:

1. Ask about a product, category, feature, review or seller rating.
2. Ask questions that span the catalogue — "which is cheaper", "anything under 3000", "which has the longest warranty".
3. Ask how the shop works — returns, exchanges, cash on delivery, opening hours — answered from seller-written policy text.
4. Ask the delivery fee for their district before committing to anything.
5. See product photos, descriptions, stock and variants.
6. Build a multi-item cart, either by clicking **Add** or by saying so ("mata GM2 pro dekak ona").
7. Submit name, one or two phone numbers, address, district, nearest city and an optional note.
8. Review subtotal, the real delivery fee and total, then confirm.
9. Receive an order number, receipt, status messages and later order history.
10. Sign in as a customer or continue as a guest. Signed-in history is restored on the next visit.
11. Do all of the above in **English, Sinhala or Tamil**, including romanised Sinhala and sentences that mix languages.

The chatbot must never invent products, stock, prices or shop policies. Every answer is grounded in the seller-scoped API response or the seller's own policy text. AI is used for language identification, intent classification, natural-language answers and translation; deterministic application code owns cart contents, customer validation, delivery pricing, totals and order creation.

**The dividing line that matters:** the model decides *what the customer meant*. Application code decides *what happens*. No model output is ever trusted as an identifier, a price or a quantity — products are re-resolved against the seller's catalogue, quantities are clamped, and every total is recalculated server-side.

## 2. Source of truth (complete source)

The production source is intentionally kept in normal modules rather than duplicated in this guide. Open these files for the complete source code:

- Frontend page and all chatbot JSX/state: `frontend/src/pages/StorefrontPage.jsx`
- Frontend storefront/chatbot styles: `frontend/src/pages/StorefrontPage.css`
- Frontend API functions: `frontend/src/services/publicService.js`
- Shared HTTP client/auth headers: `frontend/src/services/apiClient.js`
- Backend public routes: `backend/app/api/public.py`
- Backend chatbot/order logic: `backend/app/services/public_chat_service.py`
- **Every AI call and prompt**: `backend/app/services/ai_service.py`
- **Delivery pricing, districts and courier selection**: `backend/app/services/courier_service.py`
- **Public payload shape (what the browser and the model are allowed to see)**: `backend/app/services/public_catalog_service.py`
- **Sri Lankan district list shared by both dashboards**: `frontend/src/data/districts.js`
- Seller policy text editor: `frontend/src/components/SettingsModal.jsx`
- Courier per-district pricing form: `frontend/src/components/AddCourierModal.jsx`
- Seller inbox and human handoff: `backend/app/services/message_service.py`
- Status-to-chat notifications: `backend/app/services/chat_event_service.py`

When changing behavior, update these canonical files and use this guide as the explanation. This avoids two copies of a 2,500-line page drifting apart.

## 3. Project setup

```powershell
cd D:\Documents\orderflow\vendly-lk-web

# frontend
cd frontend
npm install
npm run dev

# backend, in another terminal
cd D:\Documents\orderflow\vendly-lk-web\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py
```

For local Firebase emulators, run from the project directory:

```powershell
firebase emulators:start --import .\emulator-data
```

The frontend API URL belongs in `frontend/.env` (for example `VITE_API_BASE_URL=http://127.0.0.1:5000/api/v1`). Never commit `.env` files or API keys.

## 4. Request flow

```text
browser /s/:storeCode
      │
      ├─ GET /public/stores/:storeCode ──> seller + active products
      ├─ POST /public/chat/sessions ─────> session id + session token
      ├─ POST /public/chat/sessions/:id/messages
      │       └─ backend validates session, reads products, calls AI, returns messages/actions/cart
      ├─ POST /public/chat/sessions/:id/orders ──> validates and writes order + order items
      └─ GET /public/chat/sessions/:id/messages ──> restore conversation
```

The session token is sent in `X-Chat-Session-Token`. It is separate from the seller dashboard auth token. A customer may claim a guest session after signing in; the backend then associates it with the customer id.

## 5. Frontend API layer

`frontend/src/services/publicService.js` keeps fetch details out of JSX. The essential implementation is:

```js
import { apiRequest } from "./apiClient";

export function getPublicStore(storeCode) {
  return apiRequest(`/public/stores/${storeCode}`, {
    requiresAuthentication: false,
  });
}

export function createPublicChatSession({ storeCode, productCode }) {
  return apiRequest("/public/chat/sessions", {
    method: "POST",
    body: { storeCode, productCode },
    requiresAuthentication: "optional",
  });
}

export function sendPublicChatMessage(sessionId, sessionToken, message, orderDraft = {}) {
  return apiRequest(`/public/chat/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "X-Chat-Session-Token": sessionToken },
    body: { message, ...orderDraft },
    requiresAuthentication: false,
  });
}

export function createPublicChatOrder(sessionId, sessionToken, order) {
  return apiRequest(`/public/chat/sessions/${sessionId}/orders`, {
    method: "POST",
    headers: { "X-Chat-Session-Token": sessionToken },
    body: order,
    requiresAuthentication: false,
  });
}
```

`apiRequest` parses JSON, adds the optional Firebase bearer token when available, throws a useful error for non-2xx responses, and uses the configured base URL. Keep all URL construction in service modules.

## 6. Storefront state and session restoration

The page owns presentation state, while the backend owns truth. The important state shape is:

```js
const [business, setBusiness] = useState(null);
const [products, setProducts] = useState([]);
const [session, setSession] = useState(null); // { id, token }
const [messages, setMessages] = useState([]);
const [cart, setCart] = useState([]);          // { productId, variantId, name, price, quantity, imageUrl }
const [customer, setCustomer] = useState({
  name: "", phone: "", secondPhone: "", address: "", district: "", city: "", note: "",
});
```

On load, call `getPublicStore`, then restore `vendly_public_session` from `localStorage`. Validate the saved session with `getPublicChatMessages`; if invalid, remove it and create a new session. For an authenticated customer, call `getCustomerOrders` and `getCustomerChats` after Firebase `onAuthStateChanged` resolves—this prevents the login race where the setup/login screen appears until a manual refresh.

Persist only non-sensitive identifiers:

```js
localStorage.setItem("vendly_public_session", JSON.stringify({
  id: response.sessionId,
  token: response.sessionToken,
}));
```

Never store passwords, raw Firebase credentials or payment data in local storage.

## 7. Sending a message and rendering actions

The page sends the text plus a normalized snapshot of the cart. The response contains assistant messages and optional UI actions. Do not parse HTML from the model.

```js
async function requestChatMessage(text) {
  const draft = {
    cart: cart.map((line) => ({
      productId: line.productId,
      variantId: line.variantId || null,
      quantity: line.quantity,
    })),
    customer,
  };

  setMessages((old) => [...old, { role: "user", text }]);
  const result = await sendPublicChatMessage(session.id, session.token, text, draft);
  setMessages((old) => [...old, ...(result.messages || [])]);
  if (result.cart) setCart(result.cart);
  if (result.customer) setCustomer((old) => ({ ...old, ...result.customer }));
}
```

Actions are plain objects, for example `{ type: "show-catalog", products }`, `{ type: "show-product", product }`, `{ type: "show-reviews", reviews }`, `{ type: "confirm-order", summary }`, or `{ type: "start-order" }`. `ChatbotView` switches on `action.type` and renders a small component. This makes the AI replaceable: the UI contract stays stable even if the model changes.

## 7a. Suggestion chips

Every reply carries a `suggestions` array of **ids**, chosen by `chat_suggestions()` from the action, the state, whether the cart has items and whether an order exists. They render under the newest bot reply only — older chips would stack up and keep offering actions that no longer apply.

Ids rather than text, because the storefront already has the localised labels: `CHAT_SUGGESTIONS` in `storefrontText.js` maps each id to a label key and to the **English command** that is actually sent. So the chips cost no AI call, translate instantly, and still match the deterministic keyword ladder when the provider is down.

What they offer tracks the conversation: the numbers `1 / 2 / 3` while a quantity is being asked for, "confirm" and "change" at the confirmation step, the two amounts after bank details, order actions once an order exists, and "that's everything" as soon as the cart has items.

**Nothing is offered mid-checkout.** A chip cannot answer "what is your name" and would only sit in the way of typing it. The exceptions are the genuinely optional steps — second phone and delivery note — where "skip" is a real answer.

Adding a suggestion means adding it in both places; there is a check for that in the notes below §19.

**A warning about the CSS.** The composer's chips shared selector lists with the input bar — `.storefront-chat-quick-actions, .storefront-chat-input { … }`. Removing the chips with a regex over the selector name deleted those whole rules, taking the input bar's glass styling and its dark-mode background with it. If you strip a class from this stylesheet, check for grouped selectors first and keep the surviving half; and remember the rule has to go back in its **original position**, because re-adding it after the `.storefront--dark` overrides makes the light background win in dark mode.

## 8. Browsing versus ordering (important business rule)

The first greeting should ask what the customer wants to know. Do not put products in the cart merely because they were displayed. In browsing mode cards show `View product details`; clicking it sends a product-information request. In ordering mode cards show `Add`, and only that click adds a line to the cart. Every card also carries a **cart icon in its top-right corner**, and the product detail panel carries **Add to cart** beside **Order this product** — so a customer who has decided can add without first switching the bot into ordering mode. The icon turns into a tick once the item is in the cart. All of them route through the same `addFromChat`, which is what enforces the stock ceiling.

```js
function addFromChat(product, variant) {
  setCart((old) => addOrIncreaseLine(old, {
    productId: product.id,
    variantId: variant?.id || null,
    name: product.name,
    price: variant?.price ?? product.price,
    quantity: 1,
    imageUrl: variant?.imageUrl || product.imageUrl,
  }));
  appendAssistant(`${product.name} was added to your cart. Do you want to add any other item?`);
}
```

`addOrIncreaseLine` merges the same product/variant and caps quantity at available stock. The cart summary on the right (or below on mobile) is derived from `cart`, never separately edited by the model.

**The chat can also add items.** "I want 2 of the GM2 Pro" — in any of the three languages — adds them without a click, which is the whole point for someone typing Sinhala on a phone or using voice. The rules are unchanged in substance:

- Only an explicit order intent adds anything. A question about a product (`do you have GM2 pro?`) never does.
- A multi-variant product with no size named **asks** which size. Guessing puts the wrong item in a real order.
- The quantity is capped at available stock and the customer is told when it was reduced.
- The model supplies a *name and a number*, never an identifier. The product is re-resolved with `find_matching_products` and the quantity clamped to 0–99.

**A stated quantity is a total, not an addition.** `mata 3k ona` means "I want 3", so a cart holding 1 becomes 3 — not 4. `set_variant_quantity(..., mode)` defaults to `"total"` and only accumulates when the classifier reports `quantityMode: "add"`, which it does for `thawa dekak` / "2 more" / "another one". Getting this backwards silently overcharges the customer, so the prompt tells the model to choose `"total"` whenever it is unsure.

**A quantity is always confirmed before anything is added.** When the customer names a product without a number — `mata GM2 pro ona` — the bot replies with the product, its unit price and "How many would you like to order?", holding the choice in `pendingVariantId` with state `awaiting-item-quantity`. Assuming one silently is how someone ends up with a quantity they never asked for. When they *do* state a number, that step is skipped: they already answered it.

`quantity_from_message()` reads a standalone number and otherwise defers to the classifier. The number must not be embedded in a word: a bare `\d+` matched the "2" in "GM2 pro" and read a product name as a quantity. Suffixed Sinhala forms (`3k`, `2ak`) deliberately fall through to the classifier rather than being guessed from digits.

The `set_quantity` intent handles corrections and removals — "make it 2", `thawa 3k neme okkoma 3k` ("not 3 more, 3 in total"), `meka epa` ("remove it", quantity 0). It runs **before** the order branch so a correction is never read as a fresh product choice. When the message names no product it applies to the only cart line; with several lines it asks which one, because editing the wrong item is worse than asking.

Server-side additions come back in `cartSummary`, and `requestChatMessage` reconciles local state from it. Without that reconciliation the added line is invisible **and** the next message uploads the stale local cart over the top of it.

### Narrowing instead of dumping the catalogue

"Show products" no longer returns every product. Above `BROWSABLE_CATALOGUE_SIZE` (6) the bot asks **what kind of product** the customer wants and offers the category names, returned in a `categories` field and rendered as one-tap chips. A full dump makes the customer do the filtering and buries the conversation on a phone.

Below that size it still shows everything — with a handful of products there is nothing to narrow and the extra question is pure friction. The same narrowing covers the unmatched fallback, which used to answer "I did not understand" with the entire catalogue.

**Category names are matched as whole words.** `find_category_request` used to substring-match against the squashed message, and stripping "es" from "Shoes" leaves the stub "sho" — which sits inside "show", so "show products" resolved to the Shoes category. Singular and plural forms of the customer's own words are compared against the category aliases instead.

## 9. Product cards and product information

`ChatCatalogCard` receives `mode`, `product`, `onAdd`, `onDetails`, and variant data. Use `object-fit: contain` when the seller image must be shown completely; use a fixed aspect-ratio wrapper so cards do not jump when images have different dimensions.

```css
.storefront-chat-catalog-card__image {
  aspect-ratio: 4 / 3;
  overflow: hidden;
  border-radius: 12px;
  background: #eef4fb;
}
.storefront-chat-catalog-card__image img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}
```

When a customer asks for details, return the selected product's description, every configured specification, warranty, price, stock/variants, review cards and review photos. If a fact is absent, the backend may use its approved information lookup; it must not invent a specification.

## 10. Customer details and confirmation

When the customer says they want to order, switch to ordering mode and ask for missing details one or two at a time:

```text
Please choose the product(s) and quantity first. What name should we use for delivery?
What is your primary phone number? A second number is optional.
Please provide your address, district and nearest city.
Do you have any delivery note (optional)?
```

Accept one phone number, but validate Sri Lankan formats on the server. Validate required name, address, district and city — the district must resolve to one of the 25 (§14c) or the fee is wrong.

The final summary must contain **real numbers**, not a promise. It shows item lines, subtotal, the delivery fee for the district and cart weight, the courier, and the total. An earlier version said "the delivery fee will be calculated from the district and total weight" and then asked the customer to confirm — nobody confirms an unknown total. Only the customer's explicit confirmation calls the order endpoint.

```js
const orderPayload = {
  customerName: customer.name,
  phone: customer.phone,
  secondPhone: customer.secondPhone || null,
  deliveryAddress: customer.address,
  district: customer.district,
  nearestCity: customer.city,
  note: customer.note || null,
  items: cart.map(({ productId, variantId, quantity }) => ({ productId, variantId, quantity })),
};
await createPublicChatOrder(session.id, session.token, orderPayload);
```

The backend recalculates prices, stock, delivery and total. Never trust totals supplied by the browser.

## 11. Backend public endpoints

Implemented in `backend/app/api/public.py` and `backend/app/api/reviews.py`:

```text
GET  /api/v1/public/stores/{storeCode}
GET  /api/v1/public/products/{productCode}
POST /api/v1/public/chat/sessions
GET  /api/v1/public/chat/sessions/{sessionId}/messages
POST /api/v1/public/chat/sessions/{sessionId}/messages
POST /api/v1/public/chat/sessions/{sessionId}/orders
POST /api/v1/public/chat/sessions/{sessionId}/claim
GET  /api/v1/public/stores/{storeCode}/customer/orders
GET  /api/v1/public/stores/{storeCode}/customer/chats
POST /api/v1/public/stores/{storeCode}/reviews
```

Each route should: validate path/body data, authorize the session token, scope every query by `business_id`, perform the service operation, and return a stable JSON shape. Keep SQL/Firestore access in services, not route functions.

## 12. Backend chatbot service

`public_chat_service.py` is the single place for conversation rules. `answer_public_message` runs a fixed sequence of checks; the order matters and is load-bearing:

```text
1.  authorise session, save the customer message
2.  if AI is paused by the seller -> hand off, return early
3.  load catalogue + reconcile cart
4.  classify intent + language (ONE AI call, browsing-like states only)
5.  delivery-fee question            -> quote, remember the district
6.  order-status question            -> order info
7.  completed session                -> order info, or "another order"
8.  collecting-* states              -> read the message literally as data
9.  awaiting-confirmation            -> create the order, or re-collect
10. "that is everything"             -> start collecting details
11. start_order / catalogue / category / alternatives / reviews / product
12. ambiguous product match          -> ask which one
13. catalogue-wide or policy question-> grounded AI answer
14. otherwise                        -> notify the seller, generic prompt
```

Two ordering rules that will bite if changed:

- **Step 5 must precede step 6.** `ORDER_ENQUIRY_WORDS` contains `delivery`, so "what is the delivery fee" would otherwise be answered as a tracking question.
- **Step 4 must skip the `collecting-*` states.** In those states the message *is* the data — a name, a phone number, an address. Classifying "Nimal Perera" as an intent is both wasteful and wrong. `INTENT_CLASSIFIED_STATES` enforces this, and a test asserts the classifier is never called while collecting details.

Every deterministic branch returns through the nested `respond()` helper, which is the single place that translates the reply, persists state, cart, draft and language, and shapes the JSON. Anything bypassing `respond()` must localise its own message — currently only order confirmation does.

### Keyword ladder vs. AI classifier

Both run. `intent_is(...)` is OR-ed into each keyword check, never substituted for it:

```python
wants_to_order = any(
    phrase in lowered_message for phrase in ORDER_INTENT_PHRASES
) or intent_is("start_order")
```

The phrase lists (`ORDER_INTENT_PHRASES`, `CATALOG_PHRASES`, `ALTERNATIVE_PHRASES`, …) carry English, Sinhala, Tamil and romanised Sinhala wording. They exist so that **a provider outage degrades the bot instead of breaking it**. Do not delete them when tidying up.

## 13. Conversation state machine

The stored `state` field takes exactly these values:

```text
browsing ──delivery-fee or delivery-time question────> quoting-district
quoting-district ──district recognised─────────────> browsing (district saved to draft)
quoting-district ──not a district──────────────────> browsing (handled as a normal message)

browsing ──"that is everything" with a cart────────> collecting-name
browsing ──"I want N of X"─────────────────────────> browsing (item added to cart)

browsing ──names a multi-variant product──────────> awaiting-variant
awaiting-variant ──a variant name─────────────────> awaiting-item-quantity
awaiting-variant ──a variant name + a number──────> browsing (item added)
awaiting-variant ──moves on to something else─────> browsing (handled normally)

browsing ──names a product, no quantity────────────> awaiting-item-quantity
awaiting-item-quantity ──a number─────────────────> browsing (item added)
awaiting-item-quantity ──names another product────> that product's quantity
awaiting-item-quantity ──anything else────────────> browsing (handled normally)

browsing ──a budget, with a category on screen────> clarifying-scope
clarifying-scope ──names a category───────────────> browsing (answered, scoped)
clarifying-scope ──"any product"──────────────────> browsing (answered, whole shop)

collecting-name ──> collecting-phone ──> collecting-secondary-phone
                ──> collecting-address ──> collecting-district ──> collecting-nearest-city
                ──> collecting-delivery-note ──> awaiting-confirmation

awaiting-confirmation ──confirm───────────────────> completed (order created)
awaiting-confirmation ──change────────────────────> collecting-name (draft cleared)
completed ──status question───────────────────────> completed (order info)
completed ──"cancel my order"─────────────────────> confirming-cancel
confirming-cancel ──"yes cancel"──────────────────> completed (cancelled, stock released)
confirming-cancel ──anything else─────────────────> completed (order untouched)
completed ──"another order"───────────────────────> browsing (history kept, new draft)

browsing ──names an order number, no order linked─> verifying-order
verifying-order ──phone matches the order────────> completed (order linked + shown)
verifying-order ──wrong phone, under 5 attempts──> verifying-order (same generic reply)
verifying-order ──5th wrong phone────────────────> browsing (told to contact the seller)
```

`awaiting-variant`, `awaiting-item-quantity` and `clarifying-scope` are all handled **before** product and category resolution. A one-word reply like "shoes" or "2" would otherwise be claimed as a product or a catalogue number — the same rule the `collecting-*` states follow.

`collecting-address` **skips `collecting-district`** when a district was already captured during a delivery quote. Do not remove that: asking again for something the customer just told you is the fastest way to lose them.

After order creation, keep the same session open. Append an order-created message and do not reset to the initial greeting. A status question queries the customer's orders and returns the matching order number/status.

## 14. Firestore data model

The backend can use the Firebase Admin SDK while the browser uses Firebase Auth. A practical collection layout is:

```text
businesses/{businessId}
  shortCode, name, logoUrl, publicPhone, publicEmail, currency, status
  storefrontFaq            <- seller's free-text policies; the ONLY source the
                              bot may answer returns/COD/hours questions from
  storeLocation            <- {isOnlineOnly, addressLine, city, district,
                              openingHours, mapUrl}; public
  bankDetails              <- {bankName, branch, accountName, accountNumber,
                              instructions}; NOT public, read only when a
                              customer asks how to pay
businesses/{businessId}/products/{productId}
  name, description, aiDescription, categoryId, categoryName, brand, colourName,
  sellingPriceMinor, compareAtPriceMinor, costPriceMinor, weightGrams,
  warrantyPeriodMonths, productSize, availableStock, stockStatus, media, status,
  variantSummaries[]       <- denormalised copy read by the public catalogue
businesses/{businessId}/productVariants/{variantId}
  productId, size, sku, barcode, sellingPriceMinor, costPriceMinor, weightGrams,
  stockOnHand, stockReserved, stockAvailable, stockStatus, status
businesses/{businessId}/couriers/{courierId}
  name, code, extraKgPriceMinor, averageDeliveryDays, status,
  firstKgPriceMinor        <- DERIVED: the modal (most common) district price,
                              also the fallback for an unconfigured district
  districtFirstKgPricesMinor  <- {districtSlug: minorUnits} for all 25 districts
  successRate, returnRate, districtIssueCounts, waybillPrefix/Start/End
businesses/{businessId}/reviews/{reviewId}
  productId, customerId, rating, text, imageUrls, approved, createdAt
publicChatSessions/{sessionId}
  businessId, customerUid|null, tokenHash, status, state, cart, customerDraft,
  orderId, aiPaused, unreadBySeller, createdAt, updatedAt, expiresAt
  language                 <- "en" | "si" | "ta", set from the first message and
                              then kept; drives every reply and the mic locale

  -- conversational memory. Every one of these is a FALLBACK for a message that
  -- says nothing itself; none may override what the customer just typed. Four
  -- separate bugs came from one of them winning against the current message.
  selectedProductId        <- the product a follow-up question is about
  lastCategoryShown        <- scopes "what is the best one?" to what is on screen
  lastShownProductIds      <- the exact items listed, for "best among these two"

  -- parked questions. Each belongs to one state and is cleared on the way out.
  selectedProductId        <- awaiting-variant: also the product awaiting a choice
  pendingVariantId         <- awaiting-item-quantity: the item awaiting a count
  pendingBudgetQuestion    <- clarifying-scope: the budget question to re-answer
  pendingOrderNumber       <- verifying-order: the order awaiting a phone check
  orderVerificationAttempts<- verifying-order: capped by MAX_ORDER_VERIFICATION_ATTEMPTS

  customerDraft.paymentMethod / .depositChoice
                           <- "deposit" plus "full"/"part"; recorded as intent,
                              never as money received
publicChatSessions/{sessionId}/messages/{messageId}
  role, message, metadata{action, productId, state, language, imageUrl, kind},
  sellerMessage            <- what the seller typed, when `message` is its
                              translation into the customer's language
  createdAt
businesses/{businessId}/orders/{orderId}
  orderNumber, customerId, customerName, phone, secondPhone, address, district, city,
  items, subtotal, deliveryFee, discount, taxAmount, totalAmount, status, waybillNumber, createdAt
businesses/{businessId}/orders/{orderId}/events/{eventId}
  status, message, createdAt
globalFraudCustomers/{customerKey}
  phoneHash, riskLevel, returnCount, businesses, updatedAt
```

Use a transaction when creating an order: re-read each product/variant, reject insufficient stock, decrement stock, allocate order number/waybill, write order and order items, then write a chat event. Security rules must deny clients direct writes to stock, totals, fraud records and orders; only trusted backend code writes them.

### Cancelling an order

Cancellation is the last routine reason to phone a seller, and it is common in cash-on-delivery retail. The chat handles it by calling the seller's own `update_order_status`, so the transaction, the transition rules and the stock release are the existing tested ones — nothing about cancellation is reimplemented here.

Four guards, each with a test that fails when it is removed:

1. **The order must be on this session.** Only a conversation that placed the order or passed the phone check in `verifying-order` can reach it.
2. **An explicit confirmation is required.** "Cancel my order" asks first; anything other than a clear yes leaves the order untouched. Releasing stock and voiding an order must not happen on one ambiguous line — and note that `is_cancel_order_request("cancel")` is deliberately `False`, because a bare "cancel" is as likely to mean "cancel that last thing you said".
3. **Only `needs-confirmation` and `confirmed`** (`CUSTOMER_CANCELLABLE_STATUSES`). This is deliberately narrower than the seller's own `STATUS_TRANSITIONS`, which also permit `packed -> cancelled`: by the time an order is packed the seller has picked, boxed and often labelled it, so undoing that work is their decision. Packed and later are escalated to the seller instead. A test asserts the customer's window stays a strict subset of the seller's, so the chat can never drive an invalid transition.
4. **The seller is always told**, on success and on refusal. They have stock to put back and may want to follow up, so this is never a silent change.

An `ApiError` from the status update — most likely dispatch happening between the question and the answer — is caught, reported plainly and escalated rather than surfacing a raw transition error.

**If you want to be more permissive,** add `packed` to `CUSTOMER_CANCELLABLE_STATUSES` to let customers cancel right up to dispatch. The seller's transition rules already allow it, so nothing else needs to change.

### Tracking an order with no session link

A guest who ordered, closed the tab and came back later has neither `orderId` on the session nor a `customerUid`, so `latest_order_for_session` finds nothing and they have to phone the seller. Naming the number — `VD-000012 kohomada?` — starts a phone check instead.

Three properties hold this together, and all three have tests that fail when removed:

1. **The phone on the order must match.** An order number is short and sequential, so it is guessable; `find_order_by_number` compares against `customerSnapshot.normalizedPhone`, the same check `review_service` makes. This one line is all that stands between a guessed number and a stranger's delivery address.
2. **One reply covers both failures.** "No such order" and "wrong phone" return identical wording, so the bot cannot be used to discover which order numbers exist.
3. **Guessing is capped** at `MAX_ORDER_VERIFICATION_ATTEMPTS` per session.

An invalid phone is rejected before any query runs, so a malformed reply cannot even cause a read.

Note that a **named order number is a status enquiry on its own**. `ORDER_ENQUIRY_WORDS` contains none of "VD-000001 kohomada?", so requiring a keyword as well sent that message to the generic fallback.

## 14a. The AI layer

Every provider call goes through **one** function, `request_ai_text()` in `ai_service.py`. Do not add a second call path; the error handling below only exists there.

| Function | When it runs | Failure behaviour |
|---|---|---|
| `generate_storefront_intent` | once per steering message | falls back to keyword ladder |
| `generate_product_answer` | product questions | falls back to the seller's description |
| `generate_catalogue_answer` | catalogue-wide + policy questions | falls through to seller handoff |
| `translate_chat_message` | every deterministic reply when language ≠ en | returns the English original |
| `detect_chat_language` | only if the intent call did not report a language | keeps the current language |

Configuration lives in `.env`: `AI_PROVIDER`, `AI_API_KEY`, `AI_MODEL`, `AI_API_BASE_URL`, `AI_TIMEOUT_SECONDS`. `AI_PROVIDER=none` disables AI entirely and the bot still works deterministically.

### Three operational traps, all of which have already bitten this project

1. **Models get retired.** `llama-3.3-70b-versatile` was decommissioned by Groq; every call 404'd, was swallowed, and the chat silently answered in English for an unknown period. A 4xx now logs `AI DISABLED - provider X rejected model Y`. **If replies suddenly go English-only, grep the logs for that string first.** List live models with:

   ```bash
   curl -s https://api.groq.com/openai/v1/models -H "Authorization: Bearer $AI_API_KEY"
   ```

2. **Reasoning models spend the token budget before writing anything.** `openai/gpt-oss-120b` used 43 of 62 completion tokens on reasoning for a trivial prompt. A 200-token cap returned empty content and classification silently failed. Budgets are now 1200–1500. If you switch models and intents start coming back `None`, raise `max_tokens` before suspecting the prompt.

3. **Rate limits are not configuration errors.** Groq's free tier is 8000 TPM. A 429 logs `AI RATE LIMITED` and says it recovers on its own — deliberately worded differently from `AI DISABLED` so nobody edits a model name that was never wrong.

### Grounding rules

- The model never sees another seller's data. Prompts are built from the already-scoped `get_public_store` response.
- Product, category and district names returned by the model are **queries, not identifiers** — they are re-resolved against the catalogue with `find_matching_products` / `find_district_in_text`.
- Quantities are clamped to 0–99 at the parse boundary.
- Every reply ends with `[ANSWERED]` or `[NO_DATA]`, stripped before display. This is a **forced choice** — when only the "no data" marker was offered, the model appended it to answers it had fully answered and paged the seller for nothing. `[NO_DATA]` is what triggers `notify_seller_attention`, and it works in any language, unlike matching English phrases like "I don't know".

## 14b. Language handling

The customer's language is decided once per message by `conversation_language()`, cheapest check first:

1. Explicit request ("reply in english", "සිංහලෙන්", "தமிழில்") — wins outright.
2. Sinhala or Tamil **script** present — certain, free, no AI call.
3. A language already settled on the session — **kept**.
4. Fewer than `MINIMUM_WORDS_TO_SWITCH_LANGUAGE` Latin words — **kept**.
5. Latin text on an English session — ask the AI.

Step 4 exists because of a real bug. An English customer asked for the delivery fee, answered the district with `Gampaha`, and every reply after that came back in Sinhala: the classifier saw a bare Sri Lankan place name and guessed `si`. A short Latin reply is almost always an *answer* — a district, a name, a phone number, "yes" — and carries no language to detect, so it must never switch a settled conversation. Script still switches however short it is, because script is proof rather than a guess.

`quoting-district` was also removed from `INTENT_CLASSIFIED_STATES` for the same reason: the expected reply there is data, exactly like the `collecting-*` states, so classifying it both guessed a language and cost a provider call for nothing.

Step 4 is the only one that needs a model: `mata bag ekak ona` is Sinhala in Latin letters and no character range can tell it from English. Step 3 matters just as much — a phone number or `No. 45 Park Road` carries no language signal, and re-detecting it would switch a Sinhala customer back to English mid-order.

**Tokenising Sinhala and Tamil.** Use `word_characters()`, never `\w` or `[a-z0-9]`:

- `[a-z0-9]+` deletes those scripts entirely — the original bug that made every non-English message match nothing.
- `\w+` is *worse*: it silently drops Unicode combining marks (categories `Mn`/`Mc`), which is what Sinhala and Tamil vowel signs are. `නැහැ` came back as two unrelated fragments and `யாழ்ப்பாணம்` lost 5 of its 11 characters.

`word_characters()` keeps categories `L`, `M` and `N`, so every script survives intact.

**The greeting is the one message with no language to detect.** It is written before the customer has said anything, so `create_public_chat_session` takes an optional `language` from the browser — the storefront sends whatever the visitor settled on last time, read from `vendly-storefront-voice-language`. A returning Sinhala customer is greeted in Sinhala; a first-time visitor with no stored preference gets a short trilingual line rather than an English wall. `savedChatLanguage()` returns `""` rather than `"en"` for exactly this reason: the backend has to tell "never chose" apart from "chose English".

**Translation** happens in `respond()`. The prompt must keep proper nouns in Latin script — an early version transliterated Jaffna to `ජාප්පනය` (which reads "Japan"; Jaffna is `යාපනය`), and a customer echoing that back would fail the district lookup and misprice delivery. Quoted commands like `'skip'` and `'confirm order'` also stay English, because the recognisers match on them — though `is_optional_phone_skip` and `CONFIRMATION_PHRASES` also accept Sinhala and Tamil answers, since people reply in their own words regardless.

The response carries `language`, and the storefront syncs the mic and text-to-speech locale to it.

**The interface follows too.** The bot used to answer in Sinhala while the quick-reply chips underneath still read "Show products" and "I want to order". `frontend/src/data/storefrontText.js` holds those fixed labels in all three languages, keyed off the same `language` the reply carries. It is a static table on purpose: the bot's replies are generated text and need the model, but this chrome is a closed set of short strings, so a table is cheaper, instant, and still correct when the provider is down. `storefrontText()` merges over English, so a missing key renders English rather than blank.

It covers the **entire** customer surface: the catalogue page and its search, the chat panel, product action buttons, the voice overlay, the live order draft, the cart drawer, the checkout form and its placeholders, the order receipt, the contact page, and the review pages. A grep over `StorefrontPage.jsx` for hardcoded English in JSX text and placeholder positions comes back clean; run it again after adding UI:

```bash
grep -nE 'placeholder="[A-Z]|<h[123]>[A-Z][a-z]|<p>[A-Z][a-z]|<span>[A-Z][a-z]|<small>[A-Z][a-z]' frontend/src/pages/StorefrontPage.jsx | grep -v 'storefrontText\|{text\.'
```

**The failure mode to watch:** a component that calls `storefrontText(chatLanguage)` without receiving `chatLanguage` as a prop gets `undefined`, falls back to English, and renders perfectly — no error, no warning. `CatalogView` did exactly that. When adding a localised component, check the prop is threaded all the way from `StorefrontPage`. The checkout form matters most — it is where an order is won or abandoned, and a Sinhala conversation that ends at an English form is where a customer gives up and phones the seller instead.

The chip **labels** are localised but the message each chip sends stays English, so the deterministic keyword ladder matches it even with no AI. The remembered language rides on the existing `vendly-storefront-voice-language` key, so a returning customer does not get English labels back until their next reply arrives.

## 14c. Delivery pricing

```text
fee = districtFirstKgPricesMinor[district] + (ceil((weight - 1000) / 1000) x extraKgPriceMinor)
```

- The first-kilogram price is **per district**; the extra-kilogram price is one value shared by all districts.
- `firstKgPriceMinor` is **derived** as the modal district price (`Counter(...).most_common(1)`), not typed by the seller. It is what the courier table shows and the fallback for any district not in the map.
- `SRI_LANKA_DISTRICTS` in `courier_service.py` is the single source of truth, mirrored in `frontend/src/data/districts.js`. `DISTRICT_ALIASES` resolves Sinhala, Tamil and misspellings (`kaluthara`, `yapanaya`, `யாழ்ப்பாணம்`) to one slug.
- The storefront district field is a `<select>` and the chat rejects unrecognised districts. Free text there would silently fall back to the modal price and misprice the order.
- The chatbot quotes and assigns the **cheapest** courier for the district (`cheapest_courier_quote`), with delivery quality only breaking a price tie. The seller dashboard's own `recommend_couriers` ranking is unchanged and still weighs success rate first — there is a test pinning that difference.

**How long delivery takes is answered too.** Sellers configure `averageDeliveryDays` per courier and it is snapshotted onto every order, but it was never shown to a customer — so the most common pre-purchase question after price had no answer. `is_delivery_time_question` routes "how long will it take", `kochchara kalak yanawada` and "when will it arrive" into the same district-and-courier resolution as the fee, and the quote now ends with "Koombiyo usually delivers to Colombo in about 3 working days."

Order status says the same thing from the courier snapshot frozen at checkout, so it stays right even if the seller later changes the courier's estimate — but **not** for a delivered, returned or cancelled order, where promising a future delivery is worse than saying nothing.

Weights and prices must come from the **variant**, not the product: `create_order` bills `variant.sellingPriceMinor` and `variant.weightGrams`. Using the product's values showed one subtotal and charged another.

### Shop location

`businesses/{id}.storeLocation` is set in Settings → General: either an address a customer can walk into, or an explicit `isOnlineOnly`. Unlike `bankDetails` this **is** part of `public_business` — a shop address exists to be found.

`is_location_question` covers "where are you", "do you have a shop", "can I come there", `kohedha` and the Sinhala and Tamil equivalents. An online-only seller gets a plain *"there is no shop to visit, everything is delivered by courier"* rather than silence, because a customer planning to travel needs a straight answer either way — and an unanswered question is what sends them to the phone.

An unconfigured or empty location is treated as online-only. That is the safe default: better a correct general answer than a half-empty address block.

### Deposits and bank transfer

`businesses/{id}.bankDetails` is set in Settings → General and is deliberately **not** part of `public_business`: an account number should reach someone who asked how to pay, not every anonymous storefront visitor, so the chat reads the business document directly on that one path.

Asking about a transfer sends the account block and records `paymentMethod: "deposit"` on the draft. The next reply is read for "half" or "full" — `deposit_choice` checks the part-payment phrases **first**, so "not the full amount" resolves to `part`. Note the list contains "only the delivery" but never a bare "delivery fee", which is the wording of a price question and would be misread as an amount.

**No money is ever recorded as received.** `create_order` sets `paidAmountMinor = total` for method `"paid"`, so the chatbot must never use it — the order stays `unpaid`, and the stated amount goes on the private note in words. Converting "half" into a number is the seller's call once the transfer actually lands. Deposit rows are amber in the order table (fraud red still wins) so the seller knows to check for the money before packing.

### Images in chat

`POST /public/chat/sessions/{id}/images` takes a base64 data URL, the same shape reviews already use, and `upload_chat_data_url` shares the review uploader so there is one Cloudinary path with one set of type and size limits — only the folder differs. It is rate limited to **10 per minute**, far tighter than text, because each call costs storage and an outbound request.

The image is saved as a customer message with the URL in `metadata.imageUrl` and always notifies the seller: a bank slip is something a person has to look at. Both the storefront and the seller inbox render it — showing only the caption would hide the thing that matters.

## 14d. Store policies

`businesses/{id}.storefrontFaq` is free text the seller writes in Settings → General. It is deliberately *not* a set of named fields (returns / COD / hours): fixed fields can only answer questions someone anticipated, and a textarea costs one input instead of a repeatable editor.

It is passed to `generate_catalogue_answer` as a separate grounded block. When it does not cover the question, the model returns `[NO_DATA]` and the seller is notified — it must never invent a policy on a shop's behalf.

## 15. Seller replies and live updates

Seller dashboard messages are stored in the same session/message model. `message_service.py` lets a seller pause AI and send a human reply.

**A human reply is translated into the customer's language.** The seller pauses AI precisely when a question is hard, and handing that customer a sudden English reply after ten Sinhala messages is where the language guarantee used to break — at the worst possible moment. `send_seller_message` translates whatever the seller typed into `session.language`: already writing Sinhala makes it a near no-op, typing English in a hurry still reaches the customer in their own language.

The message document keeps both. `message` is what the customer reads and what `lastMessage` shows; `sellerMessage` is what the seller typed, so their own inbox shows their words back rather than a translation they cannot check. `metadata.translated` drives the small "Sent in Sinhala: …" line under the bubble, so the seller can always see what was delivered in their name. The storefront polls messages (currently about every five seconds) and merges only unseen ids. For production, replace polling with Firestore `onSnapshot` or Server-Sent Events, while retaining the same message shape.

Order status updates call `chat_event_service.py`, which appends a customer-visible message such as “Order VD-000004 is packed and ready for dispatch.” The storefront listener/poller displays it without a browser refresh.

## 16. Voice input and text-to-speech

The browser Web Speech APIs are optional enhancements:

```js
function stopVoiceInput() {
  recognitionRef.current?.stop();
  window.speechSynthesis?.cancel(); // stop an ongoing spoken reply
}

function speakAssistantReply(text) {
  if (!window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}
```

Mic permissions require HTTPS (or localhost). Always provide a text input fallback. Pressing the mic or long-pressing the assistant button should cancel current TTS before starting recognition.

## 17. Layout and responsive styling

Desktop uses a storefront shell with a narrow seller sidebar, chat panel and cart/draft panel. On mobile, the sidebar becomes bottom navigation; the chat messages have a fixed flex height and their own `overflow-y: auto`; the page itself must not scroll because the message list is the scroll region.

```css
.storefront-chat-panel {
  display: flex;
  min-height: 0;
  flex-direction: column;
}
.storefront-chat-messages {
  flex: 1 1 auto;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
}
@media (max-width: 700px) {
  .storefront-layout { display: block; }
  .storefront-chat-panel { height: calc(100dvh - 170px); }
  .storefront-cart-panel { max-height: 42dvh; overflow-y: auto; }
}
```

Use `min-width: 0` on grid/flex children, `aspect-ratio` for images, and `object-fit: contain` where the complete seller image is important. Keep font sizes modest on phones and never position the input behind bottom navigation or the safe-area inset.

## 18. Error handling and security checklist

- Show a friendly retry message for network/AI failures; do not expose stack traces.
- Treat expired/invalid session tokens as a new guest session, not as a fatal page error.
- Scope every product, review, order and message query to the short-link business.
- Rate-limit chat and review endpoints; cap message length and uploaded image size.
- Sanitize text before rendering; React text nodes are safer than `dangerouslySetInnerHTML`.
- Validate phone, address and required fields server-side.
- Recalculate all prices and delivery fees on the server.
- Never send AI provider keys to the browser.
- Configure CORS with the actual frontend origins, including LAN development origins only when needed.

## 19. Test plan

Automated, all three must pass:

```bash
cd backend && .venv/Scripts/python.exe -m pytest -q
```

```bash
cd frontend && npm run build
```

```bash
node frontend/src/data/storefrontText.test.mjs && node frontend/src/data/messageBlocks.test.mjs
```

257 backend tests at the time of writing.

`tests/test_chat_conversation.py` is the one that matters most when changing the chat. Every other test covers an extracted pure helper; that file drives real conversations through `answer_public_message`, so it catches the failures unit tests cannot see — a branch that stops being reachable, an early return that shadows a later one, a `respond()` that persists the wrong state. Only the real boundaries are faked (Firestore, the AI provider, the other services); the step ordering under test is production code.

Two notes for extending it. `ai_status()` is evaluated as an *argument* to `sync_ai_failure_notification`, so it runs even when that call is patched out and must be patched too. And the intent state gate lives *inside* `storefront_intent` — patching that function removes the thing under test, so patch `generate_storefront_intent` beneath it instead.

Manual, in this order:

1. Open a seller link and verify only that seller's active products load.
2. Ask for a category, then a product feature, then reviews with images.
3. Verify browsing cards do not alter the cart.
4. Say "I want to order"; add two different products and change both quantities.
5. Submit one phone number, then two; test invalid phone/address messages.
6. Confirm totals, create the order, download/view the receipt and verify stock decrement.
7. Ask for order status after creation; ensure the same chat continues and no new order starts.
8. Log in, refresh, and verify chat history and orders restore; also test guest mode.
9. Pause AI, send a seller reply, update order status, and verify live messages appear.
10. Test mobile widths, keyboard navigation, mic denial, expired sessions and offline retry.

Language and intent, which the unit tests cannot cover because they need a live model:

11. Ask in Sinhala script; every following reply must stay Sinhala, including checkout prompts and the order confirmation.
12. Ask in **romanised** Sinhala (`mata bag ekak ona`) — this is the case only the AI can catch.
13. Mix languages (`මට black bag එකක් order කරන්න ඕන`) and confirm the product still resolves.
14. Mid-order, send only a phone number and an address; the language must **not** flip back to English.
15. Say `me vage thava ewa thiyenawada` and confirm similar products are suggested, not a generic prompt.
16. Ask a delivery fee before choosing anything, then check out — the district must not be asked for twice.
17. Order to a district priced differently from the common price; the quote, the confirmation and the invoice must all agree.
18. Ask a policy question the seller **did not** write about; the bot must decline rather than invent, and the seller must be notified.
19. Say "give me 10" when 2 are in stock; the cart must cap at 2 and say so.
20. Set `AI_PROVIDER=none` and re-run 1–10. Everything must still work in English.

Step 20 is the one people skip. It is the regression test for the whole fallback ladder.

## 20. Change guide for future agents

Start by reading `public_chat_service.py` (the state machine, §12), `ai_service.py` (every prompt, §14a), then `StorefrontPage.jsx`. **§22 is the backlog** — start there rather than inventing work.

Preserve the response contract (`message`, `language`, `action`, `state`, `product`, `products`, `reviews`, `cart`, `cartSummary`, `customerDraft`, `order`) when adding a feature. Put business rules in backend services, API calls in service modules, and visual changes in `StorefrontPage.css`. After every change run `npm run build` and the backend tests, then manually test one guest and one signed-in conversation — and at least one in Sinhala.

This separation keeps the storefront chatbot understandable: React displays state, the service layer talks to the API, the backend validates and persists data, and Firestore remains the shared source of truth for web and mobile clients.

## 21. Voice assistant updates: click, hold, glow and TTS cancellation

The storefront mic follows the same interaction model as the Business Assistant.

- A normal click toggles listening on or off.
- Holding the mic for about 280 ms starts voice recognition and shows the visual listening state.
- Interim speech is displayed in the overlay, but only final speech is submitted to the chatbot.
- Releasing a hold stops recognition and suppresses the follow-up click, preventing an accidental second action.
- Starting or stopping the mic cancels current text-to-speech so the browser does not transcribe the assistant's own voice.
- Unmounting the page aborts recognition, clears the hold timer and cancels TTS.

The implementation is in `D:\Documents\orderflow\vendly-lk-web\frontend\src\pages\StorefrontPage.jsx`. The important state and refs are:

```jsx
const [isListening, setIsListening] = useState(false);
const [isHoldingVoiceButton, setIsHoldingVoiceButton] = useState(false);
const [voiceTranscript, setVoiceTranscript] = useState("");
const recognitionRef = useRef(null);
const voiceHoldTimerRef = useRef(null);
const skipNextVoiceClickRef = useRef(false);
const voiceStopRequestedRef = useRef(false);
```

Clean up browser resources when the component is removed:

```jsx
useEffect(() => () => {
  window.clearTimeout(voiceHoldTimerRef.current);
  recognitionRef.current?.abort();
  window.speechSynthesis?.cancel();
}, []);
```

Recognition uses interim results for the overlay. The final phrase goes through the existing `requestChatMessage` function, so voice orders use exactly the same backend/session flow as typed messages:

```jsx
recognition.interimResults = true;
recognition.onresult = (event) => {
  let transcript = "";
  let finalTranscript = "";

  for (let index = event.resultIndex; index < event.results.length; index += 1) {
    const phrase = event.results[index]?.[0]?.transcript || "";
    transcript += phrase;
    if (event.results[index].isFinal) finalTranscript += phrase;
  }

  setVoiceTranscript(transcript.trim());
  if (finalTranscript.trim()) {
    setMessageText(finalTranscript.trim());
    requestChatMessage(finalTranscript.trim());
  }
};
```

The hold gesture is deliberately implemented with pointer events so it works with both mouse and touch screens:

```jsx
function startHeldVoiceCommand(event) {
  if (event.button !== undefined && event.button !== 0) return;

  skipNextVoiceClickRef.current = false;
  window.clearTimeout(voiceHoldTimerRef.current);
  voiceHoldTimerRef.current = window.setTimeout(() => {
    skipNextVoiceClickRef.current = true;
    setIsHoldingVoiceButton(true);
    startVoiceInput();
  }, 280);
}

function finishHeldVoiceCommand() {
  window.clearTimeout(voiceHoldTimerRef.current);
  if (!skipNextVoiceClickRef.current) return;

  setIsHoldingVoiceButton(false);
  stopVoiceInput();
}

function handleVoiceButtonClick() {
  if (skipNextVoiceClickRef.current) {
    skipNextVoiceClickRef.current = false;
    return;
  }
  onToggleListening();
}
```

The mic button connects those handlers and exposes an accessible pressed state:

```jsx
<button
  className={`storefront-chat-input__voice ${
    isListening || isHoldingVoiceButton ? "is-listening" : ""
  }`}
  type="button"
  onClick={handleVoiceButtonClick}
  onPointerDown={startHeldVoiceCommand}
  onPointerUp={finishHeldVoiceCommand}
  onPointerLeave={cancelHeldVoiceCommand}
  onPointerCancel={cancelHeldVoiceCommand}
  aria-pressed={isListening || isHoldingVoiceButton}
  title="Click to toggle. Press and hold to speak."
>
  {isListening ? <MicOff size={18} /> : <Mic size={18} />}
</button>
```

The full-screen glow is rendered only while listening/holding, and does not intercept clicks:

```jsx
{(isListening || isHoldingVoiceButton) && (
  <div className="storefront-voice-overlay" aria-live="polite">
    <div className="storefront-voice-overlay__orb"><Mic /></div>
    <p className="storefront-voice-overlay__label">Listening…</p>
    <p className="storefront-voice-overlay__transcript">
      {voiceTranscript || "Speak your message"}
    </p>
    <p className="storefront-voice-overlay__hint">Release to finish</p>
  </div>
)}
```

The matching visual effects are in `D:\Documents\orderflow\vendly-lk-web\frontend\src\pages\StorefrontPage.css`:

```css
.storefront-chat-input__voice.is-listening {
  color: #fff;
  border-color: #2f80ed;
  background: radial-gradient(circle at 32% 25%, #b9efff 0 5%, #55b9ff 23%, #287be5 58%, #5e35c8 100%);
  box-shadow: 0 0 0 5px rgba(71, 171, 255, .16), 0 0 26px rgba(83, 131, 255, .7);
  animation: storefrontVoiceOrb 1.1s ease-in-out infinite alternate;
}

.storefront-chat-input__voice.is-listening::before,
.storefront-chat-input__voice.is-listening::after {
  position: absolute;
  z-index: -1;
  inset: -7px;
  border: 2px solid rgba(89, 187, 255, .58);
  border-radius: inherit;
  content: "";
  animation: storefrontVoiceRing 1.45s ease-out infinite;
}
```

For another agent to reproduce this safely, do not create a second chatbot voice API. Reuse `startVoiceInput`, `stopVoiceInput` and `requestChatMessage`; the update is only interaction state, cleanup, and presentation. Test short click, long press, pointer cancellation, microphone denial, unsupported browsers, Sinhala/English recognition, and TTS cancellation on desktop and mobile.

---

## 22. Roadmap — pick up here in a new session

Everything above is **built and tested**. This section is the backlog, ordered by value. Each item is written to be actionable without the conversation that produced it.

Before starting any of these, run `pytest -q` and `npm run build` to confirm a clean baseline, and check the logs for `AI DISABLED` / `AI RATE LIMITED` (see §14a) — a dead model looks exactly like a broken feature.

### Known limits of what exists

| Limit | Where | When it starts to matter |
|---|---|---|
| Whole catalogue goes into the prompt | `generate_catalogue_answer` | ~200 products: cost rises and the model gets worse at picking |
| One classifier call per steering message | `storefront_intent` | high traffic on an 8000 TPM tier |
| Translation cache is a plain dict, cleared wholesale at 1000 entries | `ai_service._TRANSLATION_CACHE` | multi-process deploys — each worker caches separately |
| Opening greeting is always English | `create_public_chat_session` | no message exists yet to detect from |
| Reviews are fetched only for overview requests | `answer_public_message` | if customers start asking about reviews conversationally |

### 1. Catalogue shortlisting (do this first if the seller has many products)

**Problem:** `generate_catalogue_answer` sends every product. Fine at ~40, wasteful and less accurate at 200+.

**Approach:** filter before prompting — by category when the intent named one, by price band when the question mentions a number, otherwise the 40 nearest by name tokens. Keep the full list only when it fits a token budget. Do **not** reach for embeddings until a real catalogue makes the cheap filter fail; that is a vector store and a sync job for a problem you may not have.

**Touches:** `ai_service.generate_catalogue_answer`, `public_chat_service` fallthrough.

### 2. Stock changes mid-conversation — DONE

**Problem:** a cart item can sell out between adding and confirming. `create_order` rejects it inside the transaction and the customer sees a raw error at the final step — the worst possible moment for "order without contacting the seller".

**Built as:** `reconcile_cart_stock()` runs on every message, before anything else is answered. A sold-out line used to be filtered out of the cart *silently*; a partly-depleted one survived to the order transaction and failed there with a raw SKU error at the moment of confirmation. Both are now reported, and `describe_missing_variant()` reads the variant document directly to name an item that has dropped out of the public catalogue. `STOCK_CONFLICT_CODES` catches the remaining race between the summary and the transaction and re-offers the corrected cart instead of surfacing the raw error.

### 3. Order-status detail — DONE

**Problem:** `is_order_enquiry` matches broad words. "How long is delivery?" during browsing can still route to order status when a past order exists, because it is not a *fee* question and falls to step 6.

**Built as:** `keyword_status_enquiry` — the broad keyword list is trusted only once an order exists in the conversation (`state == "completed"`, `status == "completed"` or a stored `orderId`) or the customer names an order/waybill number. The classifier's `order_status` verdict is trusted anywhere, since it reads the whole sentence.

### 4. Seller-facing AI health — DONE

**Problem:** `AI DISABLED` only reaches the server log. A seller whose bot has quietly gone English-only has no way to know.

**Built as:** `record_ai_failure()` / `ai_status()` in `ai_service.py` capture the last failure and its kind (`configuration` / `rate_limit` / `unavailable`); a successful call clears it, so a stale warning cannot linger. `sync_ai_failure_notification()` in `operations_service.py` turns that into a seller notification in the existing bell, written from `answer_public_message` — the only place that knows both that a provider call was just attempted and which business it was for.

The notification uses a **fixed document id** (`ai-status`), so a provider failing on every message leaves one notification rather than hundreds, and `_SYNCED_AI_FAILURES` skips the write entirely once a failure has been recorded. Recovery deletes it.

The in-memory failure state is process-local on purpose — a dead model fails on every worker within seconds, so any one of them has the answer; move it to Firestore only if that stops holding. Note it is **traffic-driven**: nothing probes the provider on its own, so a broken model on a quiet storefront stays unreported until the next customer message.

### 5. Proactive upsell and abandoned drafts

**Problem:** a customer who builds a cart and stops is never followed up.

**Approach:** sessions already carry `cart`, `customerDraft`, `language` and `updatedAt`. A scheduled job could message stale active sessions in their own language. **Check consent and messaging rules before building this** — an unsolicited follow-up is a very different thing from answering a question, and it is the seller's reputation at stake.

### 6. Voice quality on real phones

**Problem:** `si-LK` and `ta-LK` recognition quality varies by browser and device, and has only been tested via typed input.

**Approach:** test on real Android and iOS hardware before promising voice ordering. If browser recognition is too weak, the Groq Whisper model already configured as `GROQ_TRANSCRIPTION_MODEL` is the fallback — record audio and transcribe server-side.

### Rules to keep when extending any of this

1. **The keyword ladder stays.** It is the outage fallback, not dead code. Test with `AI_PROVIDER=none`.
2. **Model output is never an identifier.** Re-resolve names against the seller's catalogue.
3. **Money and stock are recalculated server-side**, always, from the variant.
4. **New deterministic replies go through `respond()`** or they will not be translated.
5. **Never classify intent in a `collecting-*` state.** The message is data there.
6. **One provider call path** — `request_ai_text`. Adding a second loses the 4xx/429 handling.
7. **Leave a runnable check** behind non-trivial logic; see `test_delivery.py` and `test_public_catalog.py` for the house style.

---

## 23. Issues found in real use

**All 24 below are fixed.** They are kept rather than deleted because several were caused by the fix before them, and the causes are what stop them being reintroduced.

**Start here in a new session.** Run the three commands in §19 first — everything should be green. Then read §22 for the remaining roadmap and the note at the end of this section for what is still unverified.

Four themes run through these, and they are the ones to check any new change against:

1. **Memory must never override the current message.** `selectedProductId`, `lastCategoryShown` and `lastShownProductIds` all exist for continuity, and each one caused a bug by winning against something the customer had just said. See 23.3, 23.16, 23.17, 23.21.
2. **Token overlap is evidence, not proof.** Product names contain ordinary words — charge, power, fast, pro. Any matcher built on them needs a floor. See 23.16.
3. **What is rendered must agree with what was said.** Cards attached by default contradicted the reply above them. See 23.10.
4. **A state waiting for an answer must read that answer first.** Otherwise a one-word reply gets claimed by product or category resolution. See 23.20, and the `collecting-*` rule in §12.

Found by the seller testing a full catalogue (power banks, smart watches, earbuds, routers, laptops). Ordered by impact. Each says what was seen, the likely cause, and where to look.

### 23.1 A category word dumps the whole catalogue — FIXED

**Seen:** "I want to order a powerbank" → *"Which product would you like to order?"* plus every product in the store. Once, after a backend restart, it correctly resolved a single power bank; adding a space ("power bank" vs "powerbank") pushed the whole category again.

**Cause:** `find_matching_products` matches product *names* by token overlap. "powerbank" is a category, not a name, and `message_tokens` drops nothing useful — so nothing matches and `wants_to_order` falls through to the "which product?" branch with `products` attached. `find_category_request` is not consulted on the order path, and it needs an exact-ish category name anyway.

**Fix direction:** on the order path, when no product resolves, try the category before giving up — and match categories on singular/plural and spacing variants ("powerbank" / "power bank" / "power banks"). Show only that category's items. `public_chat_service.find_category_request`, and the `wants_to_order` branch.

### 23.2 Catalogue cards in order mode have no way to see details — FIXED

**Seen:** cards show only **+ Add**. A customer has to commit before they can read anything about the product.

**Fix direction:** `ChatCatalogCard` — show **View product details** alongside **Add** in order mode, not instead of it. `StorefrontPage.jsx`.

### 23.3 "What is the best one?" answers about an unrelated product — FIXED

**Seen:** after browsing smart watches, "what is best one" replied about a *Huawei 4G router*.

**Cause:** the question names no product, so it falls through to `generate_catalogue_answer`, which sees the entire catalogue and picks whatever it considers premium. Nothing narrows it to what the customer was just looking at.

**Fix direction:** carry the last shown category/product set into the catalogue answer and prefer it. The session already has `selectedProductId`; a `lastCategoryShown` would cover the rest.

### 23.4 "Best smart watch" lists all of them instead of recommending one — FIXED

**Seen:** "I meant best smart watch" → *"Here are all available products in Smart watch."*

**Cause:** `find_category_request` matched, and the category branch returns the whole category. A superlative ("best", "cheapest", "top") should reach the AI answer, which can actually choose and justify one.

**Fix direction:** detect a superlative and route to `generate_catalogue_answer` scoped to that category rather than to the category listing.

### 23.5 Product detail images are too large, description is a wall of text — FIXED

**Seen:** the gallery dominates the reply; the description is a raw spec dump with emoji and no structure.

**Fix direction:** cap the gallery height in `.chat-product-details__gallery`; render the description with line breaks preserved and a "read more" fold past ~4 lines.

### 23.6 Product photo and "similar items" render twice — FIXED

**Seen:** asking a follow-up detail about a product repeats the whole product block and the similar-products grid again beneath the new answer.

**Cause:** every `show-product` reply now carries `response_products` (added so similar items always appear), and the frontend renders the full `ChatProductDetails` block plus the related grid for each such message. Two product questions in a row therefore render the same product twice.

**Fix direction:** render the product block and related grid only on the newest `show-product` message, the same rule the suggestion chips already use.

### 23.7 "You may also like" is single-category and too big — FIXED

**Seen:** the related strip is a large two-column grid from one category.

**Fix direction:** make it a compact single-row horizontal scroller with small thumbnails; draw from more than one category so it is genuinely a cross-sell.

### How they were fixed

- **23.1** `find_category_request` gained `require_cue=False` for the ordering path, plus **n-gram matching** so a category stored as one token ("Powerbanks") matches two typed words ("power bank"). Whole-word matching is preserved — substring matching is what previously made "show" resolve to "Shoes".
- **23.3** `respond()` now records `lastCategoryShown` on the session, and a catalogue-wide question with no product named is scoped to it first.
- **23.4** `wants_a_recommendation` routes superlatives ("best", "which one", "cheapest") to `generate_catalogue_answer` scoped to the category, so one product is picked and justified instead of the shelf being listed.
- **23.2/23.5/23.6/23.7** frontend only: a details button beside **Add**, a capped gallery, `white-space: pre-line` on descriptions, the product block rendered only on the newest reply, and the related strip as one compact scrolling row drawing from more than one category.

### 23.8 A spec question repeated the whole product card — FIXED

**Seen:** "does it have ANC?" answered correctly, then redrew the gallery, the reviews block and the similar-products strip beneath it.

**Cause:** every product reply used the `show-product` action, which the storefront renders as the full card. Limiting it to the newest message did not help, because the spec answer *is* the newest message.

**Fixed as:** a full overview keeps `show-product` and earns the card; a follow-up question returns the new `product-answer` action — text and chips only, no gallery, no reviews, no related strip. "Show similar" is one chip away when they want it.

### 23.9 Single-image products rendered badly — FIXED

**Seen:** products with one photo showed a large empty box with the image cut off; small photos appeared tiny inside a big card.

**Cause:** two separate things. The gallery used `repeat(auto-fit, minmax(120px, 1fr))`, so a lone image stretched to the full width and its `aspect-ratio: 1/1` made it ~500px tall — which the `max-height: 190px; overflow: hidden` added for 23.5 then clipped, hiding the image and showing the empty top. Separately, catalogue thumbnails used `object-fit: scale-down`, which never enlarges, so a low-resolution photo stayed tiny.

**Fixed as:** the gallery caps its **cells** (`minmax(110px, 148px)` with `justify-content: start`) instead of clipping the container, and thumbnails use `object-fit: contain`.

### 23.10 Recommendation cards contradicted the answer — FIXED

**Seen:** "what is cheapest and best here" while browsing power banks. The text was correct — it named the WIWU P-08B and the ASPOR A337 — but the cards underneath showed a Xiaomi power bank, some Baseus earbuds and a T800 smart watch.

**Cause:** both the catalogue-answer fallthrough and the category-recommendation branch attached `products[:4]` / `scoped[:4]` — the first few items of the catalogue, chosen without reference to what the answer actually said.

**Fixed as:** `products_named_in(answer, products)` returns the catalogue items the reply mentions, in catalogue order, and those become the cards. It falls back to the scoped category, then the catalogue, when the answer names nothing (for example "we do not stock laptops"). A recommendation and the cards beneath it now agree.

**Rule for anything similar:** when a reply talks about specific products, the cards must be derived from the reply, not from the catalogue. Attaching a default slice silently contradicts the words above it.

### 23.11 Brand requests fell through to the category picker — FIXED

**Seen:** "show me lenovo products" and "show me baseus products" both returned *"What kind of product are you looking for?"* with the category chips. The brand was ignored.

**Cause:** products carry a `brand` field, but nothing ever matched on it. A brand name is not a product name and not a category, so every such message reached the picker.

**Fixed as:** `find_brand_request` / `brand_products`, checked before the category picker on the browse path and alongside the category fallback on the ordering path. It reuses the same whole-word and n-gram alias matching as categories, so "asp" does not match "ASPOR". The two alias builders — `message_word_alias_set` and `message_phrase_aliases` — were extracted from `find_category_request` so both features share one implementation.

### 23.12 Naming a product returned text with no card — FIXED

**Seen:** "lenovo gm2 pro" answered with price and specs as plain text, no product card.

**Cause:** the 23.8 fix routes non-overview questions to `product-answer` (no card), and `is_product_overview_request` only recognised "tell me about", "product details" and catalogue numbers. A bare product name matched none of them.

**Fixed as:** naming a product **in this message** (`explicitly_selected_product`) now counts as an overview request. The distinction that matters is *naming a product* — show it — versus *asking a feature about the product already on screen* — just answer.

### 23.13 Naming a product jumped straight to "how many?" — FIXED

**Seen:** typing "lenovo gm2 pro" replied *"LKR 2,500.00 each. How many would you like to order?"* — no photos, no specs, no reviews, no similar items. The customer was asked to commit before seeing anything.

**Cause:** the classifier reads a bare product name as `start_order`, so `wants_to_order` was true and the ordering branch ran.

**Fixed as:** `message_is_only_a_product_name` — when the message's word tokens are a subset of the product's name and no quantity was given, it is a request to *see* the product, so the ordering branch is skipped and the full card is returned. A stated quantity always wins: `message_tokens` drops one- and two-character words, so "2 GM2 Pro" looked like a bare name until the quantity was checked separately.

**What "full info" means here:** a `show-product` overview carries the photos (`product`), the reviews (`response_reviews` + `review_summary`) and the similar-items strip (`response_products`). A `product-answer` follow-up carries none of them — see 23.8.

Related: the newest-message gate added for 23.6 was removed. Once 23.8 stopped follow-ups carrying a card, nothing could duplicate, and the gate was making the product card vanish from history as soon as the customer asked anything else.

### 23.14 An unanswerable question was a dead end — FIXED

**Seen:** "is it waterproof" → *"We don't have information about waterproof capability for the Monster MQT52."* and nothing else. The seller was notified silently; the customer was left with no next step.

**Fixed as:** `seller_contact_message` appends a handoff — *"One of our agents will contact you shortly about this. If you are in a hurry you can call 0771234567 or message us on WhatsApp: https://wa.me/94771234567."* It runs wherever `notify_seller_attention` fires: the `[NO_DATA]` product answer and the generic fallthrough.

The WhatsApp link is **derived** from the published phone via `normalize_sri_lankan_phone`, so any format the seller typed resolves to the same `wa.me` link and there is no second field to keep in step. A seller with no published number still gets the "we will contact you" half, without a broken link.

When the model answered in the customer's language the handoff is translated separately, because that reply bypasses `respond()`'s translation with `is_translated=True`.

### 23.15 "More info" gave the wrong product and no card — FIXED

**Seen:** after a recommendation named the ASPOR **A337**, "more info" replied about the **A336** as plain text — no photos, no reviews, no description card.

**Two causes.** `is_product_overview_request` did not recognise "more info", so it went to `product-answer` (no card by design, see 23.8). And the recommendation branch never set `selectedProductId`, so the follow-up resolved against whatever had been selected earlier.

**Fixed as:** "more info", "more detail", "full details", "specs" and the Sinhala/Tamil equivalents added to the overview phrases; and when a recommendation or catalogue answer names exactly one product, that product becomes the selected one, so the next question is about it.

### 23.16 A feature question returned another product's spec sheet — FIXED

**Seen:** "how long does it take to charge" returned the full spec dump for the *Xiaomi* power bank while the conversation was about the ASPOR.

**Cause:** `find_matching_products` scores by token overlap, and "charge" is a word in "Fast **Charge** Power Bank". A single shared word selected the wrong product, and 23.12 then read that as "the customer named a product", so it returned the whole card.

**Fixed as:** a single-word overlap only identifies a product when the message is essentially just that word (two tokens or fewer). Longer questions need at least two matching words. "earbuds" still resolves; "how long does it take to charge" resolves to nothing and falls through to the remembered product, which is what the customer was actually asking about.

**The general rule:** token overlap is evidence, not proof. Product names contain ordinary words — charge, power, fast, pro, ultra — and any matcher built on them needs a floor.

### 23.17 "Send me smartwatches" said the shop has none — FIXED

**Seen:** after asking about an ASPOR power bank, "send me smartwatches" and "send me smart watches" both replied *"Sorry, we don't have any smartwatches listed right now"* — with a Smart watch category present. Then "send me smartwatch" ordered the **ASPOR power bank**.

**Three causes, all the same theme: memory outranked what was just said.**

1. `find_category_request`'s cue words are show/list/all/have — "send" is not among them, so the category branch never ran.
2. It therefore fell through to `generate_catalogue_answer`, which 23.3 scopes to `lastCategoryShown` — still **Power banks**. The model saw only power banks and truthfully said there were no smart watches.
3. The singular form reached the ordering branch, where `selected_product` was still the remembered ASPOR, so it asked how many of *that*.

**Fixed as:** a category named in the current message is resolved before anything else and outranks both the remembered product and `lastCategoryShown`. Phrase aliases are singularised too, so "smart watches" → "smartwatches" → "smartwatch" matches a category stored as "Smart watch".

**The rule:** conversational memory is a fallback for when the message says nothing, never an override for when it does. Every scoping mechanism added for continuity — `selectedProductId`, `lastCategoryShown` — needs the same escape hatch.

### 23.18 Feature questions were answered without reading descriptions — FIXED

**Seen:** "are there any alternatives which has sim support" listed Smart watch alternatives without checking whether any of them actually supports a SIM.

**Cause:** `catalogue_entry` — the row shape every cross-product answer sees — carried name, category, brand, price, warranty and stock, but **no description**. The model had nothing to check a feature against, so it either guessed or listed the category regardless. Only the single-product path (`product_facts`) ever saw a description.

**Fixed as:** `catalogue_entry` now includes the description (whitespace-collapsed, trimmed to 400 characters), plus colour and size. The catalogue prompt was given an explicit instruction: check each description before answering a feature question, and if none of them has it, **say so plainly and do not list products that do not match** — naming products under a question they fail to answer reads as though they qualify.

**Why trimmed rather than whole:** the rows are sent for every product in scope, so full descriptions would blow the prompt out on a large catalogue. 400 characters covers the spec lines sellers actually write; if feature answers start missing details, raise it before reaching for anything cleverer.

### 23.19 A price filter returned the category picker — FIXED

**Seen:** after "show me smart watches", asking "show me below Rs 2000" returned *"What kind of product are you looking for?"* with the category chips.

**Cause:** the message starts with "show me", which is a catalogue cue, so `wants_catalog` claimed it before anything looked at the number.

**Fixed as:** `has_price_constraint` spots "below Rs 2000", "under 5000", "up to 3000", "less than 1500" and the Sinhala equivalents, and routes to a scoped catalogue answer instead of the picker. A bare quantity ("I want 2 of them") is not a budget.

### 23.20 Ambiguous scope now asks instead of guessing

**The customer's point:** looking at smart watches and asking "below Rs 2000" could mean *those* watches or *any* product. Guessing is wrong half the time.

**Built as:** when a budget arrives with a category in view and none named in the message, the bot asks — *"Just to be sure — are you asking about Smart watch in that price range, or any product in the shop?"* — stores the original question in `pendingBudgetQuestion`, and enters `clarifying-scope`. The reply chooses the scope, the stored question is answered against it, and the pending question is cleared.

**Placement matters:** the handler runs **before** product and category resolution. Left later, a one-word reply like "shoes" resolved as a *product* and returned that product's card instead of answering the budget question. This is the same rule as the `collecting-*` states — when a state is waiting for a specific answer, that answer must be read before anything else tries to interpret it.

This is the pattern to reuse for any future ambiguity: ask, park the original question, resolve on the next turn.

### 23.21 Sinhala was a one-way trap — FIXED

**Seen:** a conversation that had switched to Sinhala kept replying in Sinhala to plainly English questions.

**Cause:** `conversation_language` returned the settled language *before* it ever looked at the classifier's verdict. English could become Sinhala, but never the reverse.

**Fixed as:** the detected language is consulted first, in both directions. The word-count floor and the script check still apply, so short answers and Sinhala script behave as before.

### 23.22 Sinhala replies read as machine output — FIXED

**The customer's point:** a Sinhala reply that translates *items* to `අයිතම` is harder to read than the mixed wording Sri Lankans actually text.

**Fixed as:** `language_instruction` now tells the model to keep common product, tech and commerce words in English — items, delivery, order, battery, warranty, Bluetooth, charging, stock, size — and warns that heavy translation reads as machine output.

### 23.23 "Which of these two is better?" was not understood — FIXED

**Seen:** two products listed, then "what is best among these two I meant technically" → *"I don't understand which product you meant. What kind of item are you looking for?"*

**Cause:** only `lastCategoryShown` was remembered, never which products were actually on screen, so a question about "these" had nothing to resolve against.

**Fixed as:** `respond()` records `lastShownProductIds`, and `refers_to_shown_products` ("these", "those", "both", `මේවා`) scopes the answer to exactly those items. The catalogue prompt was also told how to answer a comparison: compare the specifications and name one with a reason drawn from them, and **if the descriptions do not separate them, lay the differences out as a short markdown table rather than picking arbitrarily** and let the customer choose.

### 23.24 Comparison tables rendered as raw pipes — FIXED

**Seen:** a "which is better" reply came back as `| Spec | ASPOR A337 | ... |` with the `|---|---|` separator visible — the model's markdown table rendered as text.

**Fixed as:** `frontend/src/data/messageBlocks.js` parses a reply into text and table blocks, and `MessageBody` renders the tables as real `<table>` elements. No markdown library: this is the only markdown shape the bot emits, and a parser for it is smaller than a dependency.

The table scrolls sideways with the **spec column pinned**, so on a phone the row labels stay visible while the values move. First column of each row is a `<th scope="row">`, a lone `-` becomes an em dash, and the header row is sticky.

`messageBlocks.test.mjs` (plain `node`) checks that the separator row never becomes a data row, that plain replies stay plain, and that a stray pipe in prose is not mistaken for a table.

### 23.25 "What is best among them" answered about one product — FIXED

**Seen:** two routers listed, then "what is best among them" — answered about a single product instead of comparing the two.

**Cause:** 23.23 added the on-screen scoping, but only inside the catalogue-answer fallthrough near the end of the sequence. A remembered `selectedProductId` claimed the message long before that and routed it to the single-product path.

**Fixed as:** an explicit branch — when the message refers to what is on screen *and* asks for a recommendation, and more than one product is listed, the comparison is answered against exactly those products, **before** single-product resolution runs. When the answer names one winner it becomes the selected product, so "more info" follows on correctly.

This is the fourth time a memory field claimed a message meant for something else (see the themes at the top of this section). When adding a branch that needs the current message, check where in `answer_public_message` it actually runs — placing it after product resolution is usually too late.

### 23.26 Comparisons died when the AI was rate limited — FIXED

**Seen:** "what is best among them" kept failing in real use after 23.25, while a direct probe of the same code path worked.

**Cause:** the provider was over its tokens-per-minute limit. `generate_catalogue_answer` returns `None` on a 429 (see §14a), and the comparison branch simply fell through — so the customer got no answer at all.

**Fixed as:** `comparison_table` builds a spec table from stored facts with **no AI call** — price, warranty, availability, brand — and names the lowest priced. Rows where every product would show "-" are dropped, and fewer than two products is not a comparison. The model is still preferred; this is what runs when it is unavailable.

**A method note.** I twice "fixed" this by moving code, and twice the tests passed either way. The tests could not tell the two paths apart because the end-of-sequence fallthrough produced the same scope — asserting on the scope alone proved nothing. What settled it was probing the live function with each branch stubbed to a distinct marker. **When a fix cannot be shown to fail without it, the diagnosis is still a guess.**

### Note on ordering

23.1, 23.3 and 23.4 are the same underlying gap — **the conversation has no memory of what the customer was just looking at**, so every question is answered against the whole catalogue. Fixing that once addresses all three; the rest are presentation.

### 23.27 A variant could be answered correctly and still not order — FIXED

**Seen:** "Which size of T800 Ultra would you like? Available: Black, Orange."
The customer replied "orange". The bot answered with a sentence about the
orange one, then asked the same question again. The order never progressed.

**Cause:** the ask set `next_state="browsing"` and recorded nothing about the
question it had just asked. So "orange" arrived as an ordinary browsing
message. `choose_variant` reads the classifier's `sizeQuery`, which is empty
for a bare word carrying no order intent, and the message itself was then
resolved as a product name — matching nothing. The loop was structural: every
correct answer took the same path as the first.

**Fix:** a real `awaiting-variant` state, handled before product and category
resolution like the other one-word-reply states. `match_variant_in_message`
matches the reply against the seller's own variant labels directly, whole-word,
without needing the model. A variant plus a number ("two orange") skips
straight to the cart; anything that is clearly a change of subject drops back
to browsing rather than asking forever.

Two wording fixes went with it. The field is `size`, but sellers put colours in
it, so the customer-facing question now asks which **option**, and cart lines
read `T800 Ultra (Orange)` rather than `(size Orange)`.

The storefront renders the options as **cards with their own images and stock
counts**. Typing "orange" still works — the state handles both — but clicking
cannot be misheard, which is the whole point for a customer ordering in Sinhala.

**Method note:** the test for this asserts a state (`awaiting-variant`) that
did not exist before the fix, so it cannot pass against the old code. The
previous test asserted the opposite (`state == "browsing"`) and had to be
rewritten — the old behaviour was pinned by a test that described the bug.

### 23.28 Catalogue photos were cropped, and a card was a dead end — FIXED

**Seen:** a power bank photo with its top and bottom cut off, on a card whose
only actions were *Add to Cart* and *ask the chatbot*.

**Cause:** `object-fit: cover` on the card image. Cover fills the frame by
cropping whatever does not fit, which is right for banners and wrong for
products - sellers upload whatever their phone took, in every aspect ratio, and
the part cropped away is the product. Now `contain` with padding, so the whole
item is visible whatever its shape and the frame stays a consistent grid.

**Second half:** clicking a card did nothing. The catalogue showed a truncated
description and a review *count*, and the only route to the full picture was
asking the chatbot - which is exactly the phone call this product exists to
avoid. Cards now open a **detail popup**: full gallery with thumbnails, price
and any compare-at price, star rating averaged from the reviews themselves,
a spec grid (brand, category, warranty, size, weight, stock), the complete
description, variant chips, add-to-cart, and every approved review.

Reviews load on open from the existing `/public/products/<code>/reviews`
endpoint; a product with none renders the empty state rather than an error.
The average is computed from the loaded reviews because the catalogue payload
carries `approvedReviewCount` but no average - one round trip, not two.

**Note on the localisation self-check:** it asserts every Sinhala and Tamil
string differs from English, which caught `specBrand: "Brand"`. That one is
deliberate - the rule is to keep terms Sri Lankan customers say in English.
The four such keys are allowlisted by name in `storefrontText.test.mjs`, not
excused by loosening the assertion.

### 23.29 The corner cart button filled the card, and added silently — FIXED

**Seen:** the round cart icon rendered as a full-width blue bar across the top
of every card, and clicking it dropped one unit straight into the cart.

**Cause of the width:** CSS specificity, not source order. `.card > button` is
one class plus one type selector, which outranks a lone `.card__cart` class no
matter how late it appears in the file. Placing the override after the rule it
was meant to beat achieved nothing. Matching the same child combinator is what
actually wins.

Worth remembering: "put it later in the file" only settles ties between
selectors of *equal* specificity.

**Cause of the silent add:** the button called `addFromChat`, which adds one
and posts its own local confirmation. One is a guess, and guessing a quantity
is the same mistake §23 has already recorded twice. Both cart buttons now send
`I want to order <name>` through the normal chat route, so the bot asks the
variant when there is one and then how many - the same questions every other
path to the cart asks.

### 23.30 "Show my cart" asked which product they meant — FIXED

**Seen:** "show my cart" answered with "I did not catch which product you
meant" and a category list, while the cart had items in it.

**Cause:** there was no cart intent. The message named no product, so it fell
through to product resolution, matched nothing, and hit the generic fallback -
the bot was holding the answer the whole time.

**Fix:** a `show_cart` intent, plus `CART_PHRASES` so the phrase alone works
when the provider is rate limited, handled **before** product resolution.
`cart_contents_message` lists each line with its size, quantity and line total,
then the items subtotal, and says plainly that delivery is added once the
district is known. An empty cart says so and invites a search rather than
reporting a failure.

Three tests cover it, including one with no intent at all - the rate-limited
case. All three fail with the branch removed.

### 23.31 Ordering by brand name crashed the endpoint — FIXED

**Seen:** a live 500 on `POST /public/chat/sessions/<id>/messages`.
`UnboundLocalError: cannot access local variable 'requested_brand'`.

**Cause:** `requested_brand` was read inside the ordering block and assigned
about a hundred lines *below* it. Python binds a name at assignment, so the
read only worked when the ordering block had already returned — which it does
on almost every path. Reaching that line needed all three at once: an order
intent, no single product resolved, and no matching category. "I want to order
Lenovo" is exactly that shape, and it took the endpoint down rather than
answering wrongly.

**Fix:** resolve it once, above its first use, and delete the later
assignment. Nothing between the two positions changes the message it reads,
so the move is behaviour-preserving for every other path.

**Worth noting:** this was latent before any of this session's work — a
function long enough that a name could be used a hundred lines before it is
defined is the actual finding. The 3,600-line `answer_public_message` is on
the roadmap to be split; this is the second bug (with §23.27) caused by
distance between related lines rather than by the logic itself.

The test drives the real crashing shape and reproduces the exact
`UnboundLocalError` with the assignment moved back.

### 23.32 A brand name returned a text list and no cards — FIXED

**Seen:** typing a brand listed the items as prose with no product cards, and
adding ordinary words - "show me lenovo", "send me lenovo" - stopped it being
recognised as a brand at all.

**Diagnosis note:** the first probe showed every phrasing working perfectly,
because the fake catalogue had `brand: "Lenovo"` filled in. The bug only
appears with the field **empty**, which is how real sellers leave it - it is
optional in the product form. Setting it to `""` reproduced both symptoms at
once. A fake that is tidier than production hides the bug it was built to find.

**Cause 1 - no brand recorded.** `find_brand_request` read the `brand` field
only, so "Lenovo" - present in every product *name* - was invisible. The
request fell through to name matching, which returned several products, and
the answer came from the AI as prose instead of the brand branch's cards.

**Cause 2 - cue words.** Name matching requires two overlapping tokens unless
the message is two tokens or fewer (§23 records why: "charge" was matching
"Fast Charge Power Bank"). "show me lenovo" is three tokens with one overlap,
so it matched nothing and dumped the whole catalogue.

**Fix:** `implied_brands` reads brands off the product names. A leading word
counts only when **two or more** products share it and their **second words
differ** - real brands are followed by different model names, while "Fast
Charge Power Bank" and "Fast Charge Cable" share a descriptive phrase. Without
that guard "is delivery fast?" answered with a product list. A short
`NEVER_A_BRAND` set covers generic openers ("product", "item") that pass the
structural test but are what a customer types to browse.

`brand_products` had to change with it: matching the field alone recognised the
brand and then returned nothing, which is worse than not recognising it - a
confident answer with an empty list.

Since cue words no longer matter, all seven phrasings tested reach the brand
branch with cards, with the brand field empty.
