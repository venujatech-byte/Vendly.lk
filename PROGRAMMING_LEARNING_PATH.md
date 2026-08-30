# Programming Learning Path for Vendly

Learn in this order. You do not need to master every language before building;
learn one small concept, apply it to Vendly, then continue.

## 1. JavaScript fundamentals

Learn variables, strings, arrays, objects, functions, conditions, loops,
modules, promises and `async/await`.

```js
const item = { name: "Watch", price: 2000, quantity: 2 };
const lineTotal = item.price * item.quantity;

async function loadProducts() {
  const response = await fetch("/api/v1/products");
  if (!response.ok) throw new Error("Could not load products");
  return response.json();
}
```

Practice: calculate a cart subtotal, filter products by category and handle a
failed API request.

## 2. HTML and CSS

Learn semantic elements, forms, labels, CSS box model, flexbox, grid,
responsive media queries, variables and focus states.

```html
<label for="phone">Phone number</label>
<input id="phone" name="phone" type="tel" required />
```

```css
.card { display: grid; gap: 12px; padding: 20px; border-radius: 14px; }
@media (max-width: 700px) { .card { grid-template-columns: 1fr; } }
```

Practice: recreate one Vendly stat card and make it work on a phone width.

## 3. React fundamentals

Learn components, props, state, events, conditional rendering, lists, keys,
controlled inputs, effects and custom hooks.

```jsx
function Quantity({ value, onChange }) {
  return (
    <button type="button" onClick={() => onChange(value + 1)}>
      Quantity: {value}
    </button>
  );
}
```

```jsx
const [isOpen, setIsOpen] = useState(false);
{isOpen && <ProductDetails />}
```

Practice: build a product card, then a cart that can add, remove and update
quantity. Keep one responsibility per component.

## 4. Firebase Authentication

Learn sign-up, sign-in, Google popup, email verification, logout, auth state
listeners and ID tokens. The frontend identifies the user; Flask enforces
permissions.

```jsx
useEffect(() => onAuthStateChanged(auth, setUser), []);
```

Practice: show a login page when no user exists and a dashboard when a user is
authenticated.

## 5. Python fundamentals

Learn types, dictionaries, lists, functions, exceptions, modules, virtual
environments and JSON.

```python
def total_price(lines):
    return sum(line["price"] * line["quantity"] for line in lines)
```

Practice: write delivery-fee and phone-validation functions with pytest.

## 6. Flask REST APIs

Learn routes, request JSON, response status codes, decorators, CORS,
configuration and application structure.

```python
@app.get("/api/v1/health")
def health():
    return {"ok": True}
```

```python
@app.post("/api/v1/products")
def create_product():
    data = request.get_json()
    return jsonify(data), 201
```

Practice: create, list, update and delete a product using Postman or curl.

## 7. Firestore data modelling

Learn collections, documents, subcollections, queries, indexes, transactions,
security rules and server timestamps. Model records by business ID so each
seller is isolated.

```python
ref = db.collection("businesses").document(business_id) \
        .collection("products").document()
ref.set({"name": "Watch", "sellingPrice": 2000})
```

Practice: create a product, add a size variant, adjust stock and record an
inventory transaction.

## 8. API integration and debugging

Learn HTTP methods, headers, JSON, authentication, status codes and browser
network tools. For each request ask: what did the browser send, what did Flask
receive, what did Firestore return?

```js
try {
  await api(`/businesses/${businessId}/products`);
} catch (error) {
  setError(error.message);
}
```

## 9. Build Vendly feature by feature

1. Authentication and business setup.
2. Categories and products.
3. Size variants and inventory transactions.
4. Customers and multi-item orders.
5. Delivery fee and courier assignment.
6. Status updates, waybills and exports.
7. Chatbot catalogue, cart, confirmation and checkout.
8. Notifications, reviews, analytics and staff permissions.

For every feature: design the Firestore document, write the Flask endpoint,
test it independently, connect one React component, then add loading/error
states. Commit after each working feature.

## 10. Essential habits

- Read the browser console and Network tab before changing code.
- Keep secrets in environment files and keep them out of Git.
- Validate input on both sides, but trust only the backend validation.
- Use descriptive names and small functions.
- Do not duplicate business calculations in React and Flask.
- Write a small test when a bug is fixed.

For the chatbot checkout, practise state machines: each user answer moves from one named state to the next. Learn Python validation functions, React controlled inputs, and Firestore document updates together. The optional second phone and delivery note are good examples of optional fields with a `skip` branch.
# Current advanced topics to learn next

After the basic JavaScript, React, Python, Flask and Firestore sections, study these topics in this order:

1. **Asynchronous application bootstrap** — wait for Firebase authentication and the seller-account request before routing or rendering protected data.
2. **Derived read models** — calculate analytics and ledger rows in backend services without mutating operational order and inventory documents.
3. **Financial vocabulary** — distinguish revenue, COGS, gross profit, contribution margin and net profit.
4. **Server-side filtering and exports** — use the same validated query parameters for the table and Excel download.
5. **Accessible motion preferences** — disabling animation must preserve content visibility and respect reduced-motion users.
6. **Analytics data quality** — understand why missing cost, weight, district, courier or payment data produces unreliable reports.

Small practice example:

```js
// Rendering is allowed only after both independent checks finish.
const canRenderDashboard = !isAuthLoading && !isAccountLoading;
```

```python
# A read model derives a value; it does not overwrite the source order.
gross_profit = product_revenue - cost_of_goods_sold
```
