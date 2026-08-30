# Vendly.lk Mobile-Friendly Implementation Guide

This guide explains how the current Vendly seller dashboard and storefront adapt from desktop screens to mobile phones. It is written for a beginner and focuses on the responsive changes already implemented in this project.

The mobile work changes presentation and small interface states only. It does not change Firestore documents, backend calculations, order data, or API responses.

## 1. Files involved

| File | Mobile responsibility |
|---|---|
| `frontend/src/mobile.css` | Shared mobile layout: header, bottom navigation, page spacing, buttons, cards, and modal behavior |
| `frontend/src/components/OrderFilters.jsx` | Opens and closes the Orders filters on mobile |
| `frontend/src/components/OrderFilters.css` | Hides the Orders filter form behind a mobile toggle |
| `frontend/src/components/OrderTable.jsx` | Adds a class that identifies the Orders table only |
| `frontend/src/components/OrderTable.css` | Shows only important Order columns on small screens |
| `frontend/src/components/OrderDetails.jsx` | Supplies the extra details shown after an order is expanded |
| `frontend/src/components/OrderDetails.css` | Stacks expanded order details vertically on mobile |
| `frontend/src/components/InventoryFilters.jsx` | Opens and closes Inventory filters on mobile |
| `frontend/src/components/InventoryFilters.css` | Hides the Inventory filter form until requested |
| `frontend/src/components/InventoryTable.css` | Keeps only Product, SKU/barcode, and Stock in the compact row |
| `frontend/src/components/CategoryTable.css` | Gives Categories a separate compact table layout |
| `frontend/src/pages/CouriersPage.jsx` | Stores which courier is expanded |
| `frontend/src/pages/ManagementPage.css` | Makes the courier summary compact and reveals details below it |
| `frontend/src/pages/OrdersPage.css` | Makes Orders action buttons small and two per row |
| `frontend/src/pages/InventoryPage.css` | Makes Inventory action buttons small and two per row |
| `frontend/src/components/Header.css` | Fits Settings and other header menus inside the phone viewport |
| `frontend/src/components/StaffSettings.css` | Stacks staff forms and cards into one column |
| `frontend/src/pages/StorefrontPage.css` | Reduces storefront/chatbot typography and spacing |

## 2. Responsive breakpoints

A breakpoint is a screen width at which the CSS changes the layout.

| Breakpoint | Main use |
|---|---|
| `760px` | Main dashboard mobile layout, bottom navigation, action buttons, couriers, and header dropdowns |
| `700px` | Compact tables, expanded details, categories, and staff settings |
| `640px` | Storefront and chatbot phone layout |
| `620px` | Collapsible Orders and Inventory filters |
| `420px` | Extra-small phone refinements |
| `380px` | Very narrow storefront screens |

The basic CSS pattern is:

```css
/* Normal desktop styles */
.example {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
}

/* These styles apply only when the viewport is 760px or narrower. */
@media (max-width: 760px) {
  .example {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
```

`max-width: 760px` means “apply these rules when the browser is no wider than 760 pixels.” Desktop CSS remains the default, and the rules inside the media query override only what needs to change.

## 3. Shared dashboard adaptation

The shared rules are in `frontend/src/mobile.css`.

On a desktop, Vendly has:

- A vertical sidebar on the left
- A full header across the top
- Wide content areas and tables
- Action buttons placed in a single horizontal row

On a phone, the same application changes to:

- A fixed bottom navigation bar
- A smaller top header
- Full-width content with reduced padding
- Horizontally scrollable stat cards
- Smaller action buttons arranged two per row
- Modal dialogs displayed like bottom sheets

The fixed bottom navigation sits over the page, so the main content needs extra bottom padding. Without it, the final table row or button could be hidden behind the navigation.

Conceptually:

```css
@media (max-width: 760px) {
  .sidebar {
    position: fixed;
    right: 0;
    bottom: 0;
    left: 0;
  }

  .dashboard__content {
    padding-bottom: 90px;
  }
}
```

## 4. Mobile action buttons

Orders and Inventory can have several page actions. Placing every button on one mobile row makes them too narrow or creates horizontal overflow.

The mobile version uses a two-column grid:

```css
@media (max-width: 760px) {
  .page-actions {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 8px;
  }

  .page-actions button {
    min-height: 34px;
    padding: 6px 10px;
    font-size: 0.76rem;
  }
}
```

`minmax(0, 1fr)` is important. It allows both columns to shrink without long button text forcing the page wider than the screen.

Page-specific overrides exist in both `OrdersPage.css` and `InventoryPage.css`. This is necessary because page CSS can load after `mobile.css` and win the CSS cascade. A later rule with equal specificity can replace an earlier rule.

## 5. Collapsible mobile filters

Desktop users have enough space to see every filter. On a phone, showing all fields immediately pushes the table far down the page. Orders and Inventory therefore use a Show filters/Hide filters button.

### React state

Both filter components use a Boolean state:

```jsx
const [areMobileFiltersOpen, setAreMobileFiltersOpen] = useState(false);
```

- `false` means closed.
- `true` means open.

The button reverses the current value:

```jsx
<button
  type="button"
  onClick={() => setAreMobileFiltersOpen((current) => !current)}
  aria-expanded={areMobileFiltersOpen}
>
  {areMobileFiltersOpen ? "Hide filters" : "Show filters"}
</button>
```

The form receives an extra class when it is open:

```jsx
<form className={`filters__form ${areMobileFiltersOpen ? "is-open" : ""}`}>
  {/* Filter fields */}
</form>
```

### CSS behavior

```css
/* Desktop: the toggle is unnecessary. */
.filters__mobile-toggle {
  display: none;
}

@media (max-width: 620px) {
  .filters__mobile-toggle {
    display: flex;
  }

  .filters__form {
    display: none;
  }

  .filters__form.is-open {
    display: grid;
  }
}
```

Applying or resetting filters also closes the panel. This returns the user to the results immediately instead of leaving a tall filter form open.

`aria-expanded` tells screen readers whether the controlled section is currently open.

## 6. Orders table on mobile

The desktop Orders table contains more information than a phone can display. The mobile summary row keeps only:

- Expand arrow
- Order number
- Customer name
- Ordered-item photos/count

The other fields become available after the user expands the order.

### Why the table has a modifier class

Several tables use the general `.orders-table` class. Applying mobile column rules to that shared class previously affected the Categories table too.

The Orders table is now identified as:

```jsx
<table className="orders-table orders-table--orders">
```

The responsive rules are scoped to `.orders-table--orders`, for example:

```css
@media (max-width: 700px) {
  .orders-table--orders th:nth-child(6),
  .orders-table--orders td:nth-child(6) {
    display: none;
  }
}
```

This is called a component modifier class. It prevents one table's styles from accidentally changing another table.

### Expanded order details

`OrderDetails.jsx` contains a mobile-only summary section with information removed from the compact row, such as:

- Courier
- Status
- Order date/time

It is hidden on desktop and shown below `700px`. The complete detail layout changes from several columns to one stacked column, so the user can scroll vertically instead of horizontally.

No order information is deleted. It is only moved from the summary row into the expandable details area.

## 7. Inventory table on mobile

The Inventory table uses the same compact-summary idea. At `700px` and below, the normal row primarily shows:

- Expand arrow
- Product image and name
- SKU/barcode
- Available stock

Price, category, weight, status, and actions remain available through the expanded product section.

The expanded content stacks into one column on a phone. Product description, photos, variants, stock information, reviews, and actions therefore remain usable without forcing the whole page to become wider than the viewport.

## 8. Categories table fix

Categories require a different mobile summary from Orders. At `700px` and below, the Categories table keeps:

- Expand arrow
- Category name
- Short description
- Number of products
- Total stock

Status and action controls are hidden from the summary and can be placed in the expanded content.

Long text is shortened with an ellipsis:

```css
.category-table__description {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
```

This is what produces text such as `Electro...` instead of allowing it to overlap the next column.

The earlier category bug happened because generic `.orders-table` mobile selectors also matched the Categories table. Scoping the Orders selectors to `.orders-table--orders` solved it.

## 9. Couriers page on mobile

The courier desktop table has delivery prices, rates, delivery time, status, and actions. A phone summary only keeps the most important identity fields.

`CouriersPage.jsx` tracks the open courier:

```jsx
const [expandedCourierId, setExpandedCourierId] = useState(null);
```

Clicking the chevron either opens that courier or closes it:

```jsx
setExpandedCourierId((currentId) =>
  currentId === courier.id ? null : courier.id
);
```

When open, the mobile details section displays:

- First-kilogram fee
- Extra-kilogram fee
- Success rate
- Return rate
- Estimated delivery time

This is an accordion pattern: a small summary is always visible, and the full record is displayed only when requested.

## 10. Settings and staff permissions

Header menus were too wide and partly outside the phone viewport. On mobile, the Settings dropdown is positioned relative to the viewport rather than the small settings icon:

```css
@media (max-width: 760px) {
  .header__settings-dropdown {
    position: fixed;
    top: 62px;
    right: 10px;
    left: 10px;
    width: auto;
    max-height: 72dvh;
    overflow-y: auto;
  }
}
```

Why these values matter:

- `position: fixed` anchors the panel to the browser viewport.
- `left: 10px` and `right: 10px` keep equal safe space on both sides.
- `width: auto` allows those left/right values to determine the width.
- `72dvh` limits the height using the dynamic mobile viewport.
- `overflow-y: auto` makes the inside scroll if it is taller than the available area.

`StaffSettings.css` then changes the internal multi-column form and member rows into a single column. Long email addresses use truncation so they cannot push the panel wider.

## 11. Storefront and chatbot typography

The customer storefront uses `640px` as its main phone breakpoint and `380px` for very narrow devices.

Mobile rules reduce:

- Chat message font size and padding
- Assistant/user avatar size
- Product-card titles and descriptions
- Quantity-control size
- Quick-action button text
- Message-input text
- Live order draft text

The purpose is not simply to make everything tiny. The hierarchy is preserved:

- Product name remains stronger than its description.
- Price and stock remain easy to scan.
- Buttons stay large enough to tap.
- Secondary text becomes smaller first.

When adding more chatbot content, avoid fixed pixel widths. Prefer:

```css
.chat-card {
  width: 100%;
  max-width: 360px;
}
```

instead of:

```css
.chat-card {
  width: 360px;
}
```

The first version can shrink on a 320px phone; the second can overflow.

## 12. Mobile modal dialogs

Desktop modals are centered floating windows. On mobile, `mobile.css` changes them into bottom sheets:

- They sit at the bottom of the screen.
- Their width fills the available viewport.
- Their height is limited to the visible phone area.
- Their contents scroll internally when needed.
- Footer buttons remain easier to reach.

This pattern is better for Add Order, Add Product, profile, confirmation, and stock adjustment dialogs because a centered desktop-sized modal can extend beyond a phone screen.

## 13. CSS cascade and why some rules are repeated

CSS applies the winning declaration based on:

1. Importance (`!important`)
2. Selector specificity
3. Source order when specificity is equal

The page components are lazy-loaded. Their CSS may be inserted after the global `mobile.css`. Therefore a desktop rule in a page CSS file can unexpectedly override an earlier mobile rule.

The safest solution used here is to put critical page-specific mobile rules at the bottom of that page's own stylesheet:

```css
/* OrdersPage.css */
@media (max-width: 760px) {
  .orders-page .page-actions {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
```

Use `!important` only as a last resort. A correctly scoped selector is easier to maintain.

## 14. How to make a new page mobile-friendly

Follow this sequence:

1. Build and verify the desktop page first.
2. Give the page a unique parent class, such as `.customers-page`.
3. Add mobile rules at the bottom of its stylesheet.
4. Reduce outer padding and gaps.
5. Arrange action buttons in a one- or two-column grid.
6. Hide only secondary table columns.
7. Put hidden information into an expandable detail section.
8. Make filter panels collapsible if they contain several fields.
9. Use `width: 100%` with a reasonable `max-width` for cards and dialogs.
10. Check that fixed navigation does not cover the final content.
11. Add `aria-expanded` to expandable buttons.
12. Test long names, emails, addresses, and large numbers.

Example page-scoped media query:

```css
@media (max-width: 700px) {
  .customers-page__table {
    font-size: 0.78rem;
  }

  .customers-page__secondary-column {
    display: none;
  }

  .customers-page__expanded-details {
    display: grid;
    grid-template-columns: 1fr;
  }
}
```

## 15. Common mobile bugs to avoid

### A shared selector changes the wrong table

Bad:

```css
.orders-table td:nth-child(5) {
  display: none;
}
```

Better:

```css
.orders-table--orders td:nth-child(5) {
  display: none;
}
```

### The expanded row disappears

A selector such as `tbody td:nth-child(...)` may also target cells inside a details row. Exclude that row:

```css
tbody tr:not(.orders-table__details-row) > td:nth-child(6) {
  display: none;
}
```

The direct-child symbol `>` prevents the rule from reaching nested detail tables.

### The page scrolls sideways

Check for:

- Fixed widths wider than the viewport
- Grid columns without `minmax(0, 1fr)`
- Long unbroken email addresses or IDs
- Images missing `max-width: 100%`
- Elements using `width: 100vw` inside padded parents

### A dropdown is cut off

Use a viewport-fixed mobile dropdown with safe left/right gaps and a `max-height`.

### The bottom navigation covers content

Add bottom padding to the page content that is at least as tall as the fixed navigation.

### A global mobile rule does not work

Inspect whether a later component stylesheet is overriding it. Add a page-scoped mobile rule at the bottom of that component stylesheet.

## 16. Accessibility and touch behavior

Responsive design must remain usable, not only visually smaller.

- Use real `<button>` elements for clickable controls.
- Add `aria-expanded` to filter and accordion toggles.
- Keep a visible keyboard focus state.
- Do not depend only on color to communicate status.
- Keep important tap targets approximately 34–44px high.
- Do not remove information permanently; move secondary data into expanded details.
- Respect `prefers-reduced-motion` for users who disable animations.

## 17. Testing the mobile version

Start the frontend from the frontend folder:

```powershell
cd D:\Documents\orderflow\vendly-lk-web\frontend
npm run dev
```

Then open the browser developer tools and test these widths:

- `360 × 800` — small Android phone
- `390 × 844` — common modern phone
- `412 × 915` — larger Android phone
- `768 × 1024` — tablet boundary
- A normal desktop width such as `1440 × 900`

Test each workflow:

1. Open and close Orders filters.
2. Apply and reset filters.
3. Expand an order and verify all hidden details appear.
4. Expand an inventory product and a category.
5. Expand a courier.
6. Open Settings and scroll the staff panel.
7. Open Add Order and Add Product modals.
8. Use the storefront chat, product cards, quantity controls, and cart.
9. Confirm that the bottom navigation does not cover content.
10. Rotate the phone and test landscape orientation.

Run the code checks after editing:

```powershell
npm run lint
npm run build
```

The current mobile changes passed both commands when this guide was created.

## 18. Summary of the adaptation strategy

Vendly does not create a separate mobile application page. React renders the same data and components, while CSS media queries rearrange and simplify their presentation.

For small interaction changes—such as opening filters, expanding an order, or expanding a courier—React state records whether the section is open. For visual changes—such as smaller text, two-column buttons, hidden summary columns, and stacked details—CSS media queries perform the adaptation.

The overall pattern is:

```text
Same React data and business logic
              |
              +-- Desktop width -> full navigation, filters, and table columns
              |
              +-- Mobile width  -> bottom navigation, collapsible filters,
                                   compact rows, and expandable details
```

This keeps one maintainable codebase while giving desktop and mobile users layouts suited to their screen sizes.

## Chatbot contact form on mobile

Keep each contact question as a normal chat message and input. The second phone field is optional; the customer can type `skip`. Use full-width controls for the street address, district, nearest city, and delivery note. Show the collected draft in the fixed order-summary panel and allow scrolling inside the chat panel so the checkout controls remain reachable on small screens.

## 19. Animation preferences must preserve content

Vendly stores the seller's animation preference on the document root. Entrance animations may begin with `opacity: 0` and a translated position, but disabling animation must immediately restore every element to its normal visible state.

```css
html[data-animations="off"] .page-animate,
html[data-animations="off"] .sidebar__link,
html[data-animations="off"] .courier-fee-map,
html[data-animations="off"] .courier-fee-map__visual-card {
  opacity: 1 !important;
  transform: none !important;
  animation: none !important;
  transition: none !important;
}
```

This matters on mobile because the sidebar becomes bottom navigation. If only the animation is removed while its hidden starting state remains, navigation icons or the courier map disappear. Test every page once with animations enabled and once with them disabled.
