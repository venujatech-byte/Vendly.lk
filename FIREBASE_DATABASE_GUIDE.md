# Vendly Firebase Database Guide

This guide builds Vendly's Firebase layer from an empty Firebase project. The
frontend uses Firebase Authentication for sign-in. The Flask API uses the
Firebase Admin SDK for trusted Firestore writes, stock changes, totals and
permissions. Keep these responsibilities separate.

## 1. Create the Firebase project

1. Open Firebase Console and create a project named `vendly-lk-web`.
2. Enable Authentication → Sign-in method → Email/Password and Google.
3. Create a Firestore database in production mode and choose a nearby region.
4. Create a Web App under Project settings.
5. Copy the web configuration into `frontend/.env.local`:

```env
VITE_FIREBASE_API_KEY=...
VITE_FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=your-project
VITE_FIREBASE_STORAGE_BUCKET=your-project.firebasestorage.app
VITE_FIREBASE_MESSAGING_SENDER_ID=...
VITE_FIREBASE_APP_ID=...
```

Only `VITE_*` web configuration belongs in the browser. It is not a secret.
Never put a service-account JSON key or private API key in `VITE_*` variables.

## 2. Frontend Firebase setup

Install the SDK inside `frontend`:

```powershell
cd D:\Documents\orderflow\vendly-lk-web\frontend
npm install firebase
```

Create one initialization module:

```js
// src/firebase/firebase.js
import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider } from "firebase/auth";

const app = initializeApp({
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
  storageBucket: import.meta.env.VITE_FIREBASE_STORAGE_BUCKET,
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID,
  appId: import.meta.env.VITE_FIREBASE_APP_ID,
});

export const auth = getAuth(app);
export const googleProvider = new GoogleAuthProvider();
```

Email registration and Google sign-in are small service functions:

```js
import { createUserWithEmailAndPassword, signInWithPopup } from "firebase/auth";
import { auth, googleProvider } from "../firebase/firebase";

export const register = (email, password) =>
  createUserWithEmailAndPassword(auth, email, password);

export const signInWithGoogle = () => signInWithPopup(auth, googleProvider);
```

After sign-in, send the ID token to Flask. Firebase's client SDK must not be
used to bypass backend permission checks.

```js
const token = await auth.currentUser.getIdToken();
await fetch(`${API_URL}/api/v1/me`, {
  headers: { Authorization: `Bearer ${token}` },
});
```

## 3. Firestore structure

Use the business as the tenant boundary. A seller never reads another
business's subcollection.

```text
users/{uid}
businesses/{businessId}
businesses/{businessId}/members/{uid}
businesses/{businessId}/categories/{categoryId}
businesses/{businessId}/products/{productId}
businesses/{businessId}/products/{productId}/variants/{variantId}
businesses/{businessId}/inventoryTransactions/{transactionId}
businesses/{businessId}/customers/{customerId}
businesses/{businessId}/orders/{orderId}
businesses/{businessId}/orders/{orderId}/items/{itemId}
businesses/{businessId}/couriers/{courierId}
businesses/{businessId}/notifications/{notificationId}
```

Example product document:

```js
{
  name: "Daisy Running Shoes",
  colourName: "Pink",
  categoryId: "footwear",
  skuPrefix: "DFS-PNK",
  description: "Lightweight running shoes...",
  sellingPrice: 1899,
  costPrice: 1200,
  weightKg: 0.45,
  hasSizes: true,
  primaryMediaPath: "products/productId/main.jpg",
  totalStock: 15,
  availableStock: 15,
  createdAt: serverTimestamp(),
}
```

Each size is a variant with its own SKU, barcode and stock. A stock change
must also create an inventory transaction so it can be audited.

## 4. Rules and indexes

Use Firebase rules as a second safety layer. The Flask Admin SDK bypasses
Firestore rules, so Flask must always verify membership itself.

```text
match /businesses/{businessId}/{document=**} {
  allow read, write: if isMember(businessId);
}

function isMember(businessId) {
  return request.auth != null &&
    exists(/databases/$(database)/documents/businesses/$(businessId)/members/$(request.auth.uid));
}
```

Create indexes only when Firestore reports that a compound query needs one.
Typical indexes combine `status`, `createdAt`, `categoryId` or `courierId`.

## 5. Local verification checklist

```powershell
firebase login
firebase use your-project-id
firebase deploy --only firestore:rules,firestore:indexes
```

Check that a user can see their own business, cannot read another business,
and that a checkout made through Flask creates one order with multiple items.
Use the Firebase Emulator Suite later for safe local tests.

## 6. Production rules

- Do not commit `.env.local`, service-account JSON, or `backend/.env`.
- Validate prices and stock again on the server; never trust browser totals.
- Use a Firestore transaction when reserving stock and creating an order.
- Keep customer phone numbers and addresses private and restrict staff roles.
- Cloudinary or another object store should hold media; Firestore stores URLs.

## Chatbot customer and delivery fields

The public chat session stores an in-progress `customerDraft` map. Keep it on the session document so the customer can continue after navigation or a temporary network retry:

```text
publicChatSessions/{sessionId}
  customerDraft.name
  customerDraft.phoneNumber
  customerDraft.secondaryPhoneNumber   // optional; empty string is valid
  customerDraft.address.line1
  customerDraft.address.city           // nearest city
  customerDraft.address.district
  customerDraft.address.line2
  customerDraft.address.postalCode
  customerDraft.deliveryNote            // optional
```

After confirmation, copy the same fields into the customer document and the order snapshot. `secondaryPhoneNumber` may be empty, but `phoneNumber`, `address.line1`, `address.city`, and `address.district` are required. Firestore security rules must allow a customer to update only their own public session and must prevent a public client from changing calculated totals, stock, seller ownership, or order status.
