# Vendly storefront chatbot — build-from-scratch guide

This document explains the customer storefront chatbot in a way that another developer or agent can reproduce and maintain it. It is written for the active project at `D:/Documents/orderflow/vendly-lk-web`.

## 1. What the chatbot does

The public storefront is reached with a seller short link such as `/s/L23OOWs`. It loads only that seller's active catalogue. A visitor can:

1. Ask about a product, category, feature, review or seller rating.
2. See product photos, descriptions, stock and variants.
3. Start an order only after deciding to buy.
4. Build a multi-item cart with quantity controls.
5. Submit name, one or two phone numbers, address, district, nearest city and an optional note.
6. Review subtotal, delivery fee, discount and total, then confirm.
7. Receive an order number, receipt, status messages and later order history.
8. Sign in as a customer or continue as a guest. Signed-in history is restored on the next visit.

The chatbot must never invent products or stock. Every product answer is based on the seller-scoped API response. AI is used for natural-language intent extraction and concise replies; deterministic application code validates cart, customer data, totals and order creation.

## 2. Source of truth (complete source)

The production source is intentionally kept in normal modules rather than duplicated in this guide. Open these files for the complete source code:

- Frontend page and all chatbot JSX/state: `frontend/src/pages/StorefrontPage.jsx`
- Frontend storefront/chatbot styles: `frontend/src/pages/StorefrontPage.css`
- Frontend API functions: `frontend/src/services/publicService.js`
- Shared HTTP client/auth headers: `frontend/src/services/apiClient.js`
- Backend public routes: `backend/app/api/public.py`
- Backend chatbot/order logic: `backend/app/services/public_chat_service.py`
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

Accept one phone number, but validate Sri Lankan formats on the server. Validate required name, address, district and city. Show a final summary containing item lines, subtotal, delivery fee, discount, tax (if configured), total and payment method. Only the customer’s explicit confirmation calls the order endpoint.

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

`public_chat_service.py` is the single place for conversation rules:

```python
def answer_public_message(session, text, cart, customer):
    intent = classify_intent(text)  # model or deterministic fallback
    if intent == "order_status":
        return order_status_reply(session, text)
    if intent == "show_reviews":
        return reviews_action(session.business_id, text)
    if intent == "show_product":
        return product_details_action(session.business_id, text)
    if intent == "start_order":
        return start_order_action(cart)
    return safe_catalog_question_reply(session.business_id, text)
```

The actual service also contains `create_public_chat_session`, `authorize_public_chat_session`, `get_public_chat_messages`, `save_chat_message`, `claim_public_chat_session`, `normalize_chat_cart`, `summarize_chat_cart`, `answer_public_message` and `create_public_chat_order`. Read that file before changing the state machine; it prevents an order-status question from accidentally restarting a new order.

## 13. Conversation state machine

```text
DISCOVERY ──product/category question──> PRODUCT_INFO
DISCOVERY ──“want to order”────────────> SELECTING_ITEMS
PRODUCT_INFO ──another product─────────> DISCOVERY
SELECTING_ITEMS ──Add/quantity─────────> CART_REVIEW
CART_REVIEW ──customer details─────────> COLLECTING_DETAILS
COLLECTING_DETAILS ──all valid─────────> AWAITING_CONFIRMATION
AWAITING_CONFIRMATION ──yes────────────> ORDER_CREATED
ORDER_CREATED ──status question────────> ORDER_INFO
ORDER_CREATED ──“another order”───────> SELECTING_ITEMS (keep history, new draft)
```

After order creation, keep the same session open. Append an order-created system message and do not reset the conversation to the initial greeting. A status question must query the customer’s orders and return the matching order number/status.

## 14. Firestore data model

The backend can use the Firebase Admin SDK while the browser uses Firebase Auth. A practical collection layout is:

```text
businesses/{businessId}
  storeCode, name, logoUrl, phone, email, deliverySettings
businesses/{businessId}/products/{productId}
  name, description, categoryId, price, costPrice, stock, weight, imageUrls, isActive
businesses/{businessId}/products/{productId}/variants/{variantId}
  label, sku, barcode, price, stock, imageUrl
businesses/{businessId}/reviews/{reviewId}
  productId, customerId, rating, text, imageUrls, approved, createdAt
publicChatSessions/{sessionId}
  businessId, customerId|null, tokenHash, status, cart, customer, createdAt, updatedAt
publicChatSessions/{sessionId}/messages/{messageId}
  role, text, actions, createdAt, source
businesses/{businessId}/orders/{orderId}
  orderNumber, customerId, customerName, phone, secondPhone, address, district, city,
  items, subtotal, deliveryFee, discount, taxAmount, totalAmount, status, waybillNumber, createdAt
businesses/{businessId}/orders/{orderId}/events/{eventId}
  status, message, createdAt
globalFraudCustomers/{customerKey}
  phoneHash, riskLevel, returnCount, businesses, updatedAt
```

Use a transaction when creating an order: re-read each product/variant, reject insufficient stock, decrement stock, allocate order number/waybill, write order and order items, then write a chat event. Security rules must deny clients direct writes to stock, totals, fraud records and orders; only trusted backend code writes them.

## 15. Seller replies and live updates

Seller dashboard messages are stored in the same session/message model. `message_service.py` lets a seller pause AI and send a human reply. The storefront polls messages (currently about every five seconds) and merges only unseen ids. For production, replace polling with Firestore `onSnapshot` or Server-Sent Events, while retaining the same message shape.

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

1. Open a seller link and verify only that seller’s active products load.
2. Ask for a category, then a product feature, then reviews with images.
3. Verify browsing cards do not alter the cart.
4. Say “I want to order”; add two different products and change both quantities.
5. Submit one phone number, then two; test invalid phone/address messages.
6. Confirm totals, create the order, download/view the receipt and verify stock decrement.
7. Ask for order status after creation; ensure the same chat continues and no new order starts.
8. Log in, refresh, and verify chat history and orders restore; also test guest mode.
9. Pause AI, send a seller reply, update order status, and verify live messages appear.
10. Test mobile widths, keyboard navigation, mic denial, expired sessions and offline retry.

## 20. Change guide for future agents

Start by reading `StorefrontPage.jsx`, `publicService.js`, `public.py` and `public_chat_service.py`. Preserve the response contract (`messages`, `actions`, `cart`, `customer`, `order`) when adding a feature. Put business rules in backend services, API calls in service modules, and visual changes in `StorefrontPage.css`. After every change run `npm run build` and the backend tests, then manually test one guest and one signed-in conversation.

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
