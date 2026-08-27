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

## 8. Browsing versus ordering (important business rule)

The first greeting should ask what the customer wants to know. Do not put products in the cart merely because they were displayed. In browsing mode cards show `View product details`; clicking it sends a product-information request. In ordering mode cards show `Add`, and only that click adds a line to the cart.

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
browsing ──delivery-fee question, no district known──> quoting-district
quoting-district ──district recognised─────────────> browsing (district saved to draft)
quoting-district ──not a district──────────────────> browsing (handled as a normal message)

browsing ──"that is everything" with a cart────────> collecting-name
browsing ──"I want N of X"─────────────────────────> browsing (item added to cart)

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

`collecting-address` **skips `collecting-district`** when a district was already captured during a delivery quote. Do not remove that: asking again for something the customer just told you is the fastest way to lose them.

After order creation, keep the same session open. Append an order-created message and do not reset to the initial greeting. A status question queries the customer's orders and returns the matching order number/status.

## 14. Firestore data model

The backend can use the Firebase Admin SDK while the browser uses Firebase Auth. A practical collection layout is:

```text
businesses/{businessId}
  shortCode, name, logoUrl, publicPhone, publicEmail, currency, status
  storefrontFaq            <- seller's free-text policies; the ONLY source the
                              bot may answer returns/COD/hours questions from
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
  language                 <- "en" | "si" | "ta", set from the first message and
                              then kept; drives every reply and the mic locale
  selectedProductId, orderId, aiPaused, unreadBySeller, createdAt, updatedAt, expiresAt
publicChatSessions/{sessionId}/messages/{messageId}
  role, message, metadata{action, productId, state, language}, createdAt
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
4. Latin text on an English session — ask the AI.

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

Automated: `cd backend && .venv/Scripts/python.exe -m pytest -q` (153 tests), `cd frontend && npm run build`, and `node frontend/src/data/storefrontText.test.mjs`.

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
