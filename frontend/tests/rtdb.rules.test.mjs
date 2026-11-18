// Test the actual private rules against a demo-only local RTDB emulator.
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import process from "node:process";
import { after, before, test } from "node:test";
import { initializeApp, deleteApp } from "firebase/app";
import { subscribeNotificationFeeds } from "../src/services/realtimeNotifications.js";
import { connectDatabaseEmulator, get, getDatabase, goOffline, onValue, ref, set } from "firebase/database";

// Refuse real hosts/projects so fixture seeding cannot overwrite live data.
const host = process.env.FIREBASE_DATABASE_EMULATOR_HOST;
assert.match(host || "", /^127\.0\.0\.1:\d+$/, "Set FIREBASE_DATABASE_EMULATOR_HOST to a local emulator.");
const namespace = "demo-vendly-rules";
const [hostname, port] = host.split(":");
const apps = [];

async function admin(path, value) {
  const response = await fetch(`http://${host}/${path}.json?ns=${namespace}`, {
    method: "PUT",
    headers: { Authorization: "Bearer owner", "Content-Type": "application/json" },
    body: JSON.stringify(value),
    signal: AbortSignal.timeout(10000),
  });
  assert.equal(response.status, 200, `Emulator setup failed: ${response.status}`);
}

function client(uid, provider = "password", verified = true) {
  // Use installed Firebase SDK mock tokens; no new testing library or real Auth account.
  const app = initializeApp({ projectId: namespace, databaseURL: `https://${namespace}.firebaseio.com` }, `rules-${apps.length}`);
  const database = getDatabase(app);
  const options = uid ? { mockUserToken: { sub: uid, email_verified: verified, firebase: { sign_in_provider: provider } } } : undefined;
  connectDatabaseEmulator(database, hostname, Number(port), options);
  apps.push({ app, database });
  return database;
}

before(async () => {
  // Load the repository's exact rules and seed only fake customer/business records.
  const rules = JSON.parse(await readFile(new URL("../../database.rules.json", import.meta.url), "utf8"));
  await admin(".settings/rules", rules);
  await admin("", {
    _access: {
      members: {
        "biz-a": {
          seller: { chats: true, notifications: { orders: true, customers: true, management: true } },
          viewer: { chats: false, notifications: { orders: true, customers: false, management: false } },
          inactive: { chats: false, notifications: { orders: false, customers: false, management: false } },
          blocked: { chats: false, notifications: { orders: false, customers: false, management: false }, pending: true },
        },
        "biz-b": { "other-seller": { chats: true, notifications: { orders: true, customers: true, management: true } } },
      },
      chats: {
        "chat-a": { businessId: "biz-a", customerUid: "guest-a" },
        "chat-b": { businessId: "biz-b", customerUid: "guest-b" },
      },
    },
    chatMessages: {
      "chat-a": { first: { role: "customer", message: "Private A", createdAt: "2026-01-01" } },
      "chat-b": { first: { role: "customer", message: "Private B", createdAt: "2026-01-01" } },
      "unmapped-chat": { first: { message: "No ownership metadata" } },
    },
    businesses: {
      "biz-a": {
        notifications: { first: { message: "Legacy private A" } },
        notificationFeeds: {
          orders: { first: { title: "Order A", type: "new-order", createdAt: 1 } },
          customers: { chat: { title: "Private customer A", type: "chat-needs-attention", createdAt: 2 } },
          management: { system: { title: "Private system A", type: "ai-status", createdAt: 3 } },
        },
      },
      "biz-b": { notifications: { first: { message: "Legacy private B" } }, notificationFeeds: { orders: { first: { title: "Order B" } } } },
    },
    businessChatActivity: { "biz-a": { sessionId: "chat-a" }, "biz-b": { sessionId: "chat-b" } },
    customerOrderUpdates: { "store-a": {
      "guest-a": { "order-a": { fulfilmentStatus: "shipped" } },
      "guest-b": { "order-b": { fulfilmentStatus: "confirmed" } },
      "legacy-customer-id": { "order-a": { fulfilmentStatus: "shipped" } },
      "legacy-order-id": { orderId: "order-a", fulfilmentStatus: "shipped" },
    } },
  });
});

after(async () => {
  // Close every emulator connection, including listeners canceled by revocation.
  await Promise.all(apps.map(async ({ app, database }) => { goOffline(database); await deleteApp(app); }));
});

test("unauthenticated callers cannot read any private path", { timeout: 10000 }, async () => {
  const db = client();
  for (const path of ["chatMessages/chat-a", "businesses/biz-a/notifications", "businesses/biz-a/notificationFeeds/orders", "businessChatActivity/biz-a", "customerOrderUpdates/store-a/guest-a"]) {
    await assert.rejects(get(ref(db, path)), /permission[ _]denied/i);
  }
});

test("anonymous customers read only their own chat and order updates", { timeout: 10000 }, async () => {
  const db = client("guest-a", "anonymous");
  assert.equal((await get(ref(db, "chatMessages/chat-a"))).exists(), true);
  assert.equal((await get(ref(db, "customerOrderUpdates/store-a/guest-a"))).exists(), true);
  for (const path of ["chatMessages/chat-b", "chatMessages/unmapped-chat", "customerOrderUpdates/store-a/guest-b", "customerOrderUpdates/store-a/legacy-customer-id", "customerOrderUpdates/store-a/legacy-order-id", "businesses/biz-a/notifications"]) {
    await assert.rejects(get(ref(db, path)), /permission[ _]denied/i);
  }
});

test("authorized staff read their tenant's chats, inbox signal and notifications", { timeout: 10000 }, async () => {
  const db = client("seller");
  for (const path of ["chatMessages/chat-a", "businessChatActivity/biz-a", "businesses/biz-a/notificationFeeds/orders", "businesses/biz-a/notificationFeeds/customers", "businesses/biz-a/notificationFeeds/management"]) {
    assert.equal((await get(ref(db, path))).exists(), true);
  }
  for (const path of ["chatMessages/chat-b", "businessChatActivity/biz-b", "businesses/biz-b/notifications", "businesses/biz-b/notificationFeeds/orders", "businesses/biz-a/notifications", "customerOrderUpdates/store-a/guest-a"]) {
    await assert.rejects(get(ref(db, path)), /permission[ _]denied/i);
  }
});

test("a member without customer read permission cannot read chats or activity", { timeout: 10000 }, async () => {
  const db = client("viewer");
  assert.equal((await get(ref(db, "businesses/biz-a/notificationFeeds/orders"))).exists(), true);
  await assert.rejects(get(ref(db, "businesses/biz-a/notificationFeeds/customers")), /permission[ _]denied/i);
  await assert.rejects(get(ref(db, "businesses/biz-a/notificationFeeds/management")), /permission[ _]denied/i);
  await assert.rejects(get(ref(db, "businesses/biz-a/notifications")), /permission[ _]denied/i);
  await assert.rejects(get(ref(db, "chatMessages/chat-a")), /permission[ _]denied/i);
  await assert.rejects(get(ref(db, "businessChatActivity/biz-a")), /permission[ _]denied/i);
});

test("inactive, removed and temporarily blocked staff cannot read business records", { timeout: 10000 }, async () => {
  for (const uid of ["inactive", "removed", "blocked"]) {
    const db = client(uid);
    await assert.rejects(get(ref(db, "businesses/biz-a/notifications")), /permission[ _]denied/i);
    await assert.rejects(get(ref(db, "businesses/biz-a/notificationFeeds/orders")), /permission[ _]denied/i);
    await assert.rejects(get(ref(db, "chatMessages/chat-a")), /permission[ _]denied/i);
  }
});

test("unverified password users cannot use otherwise valid ownership", { timeout: 10000 }, async () => {
  await assert.rejects(get(ref(client("guest-a", "password", false), "chatMessages/chat-a")), /permission[ _]denied/i);
});

test("clients cannot inspect or forge authorization metadata or write messages", { timeout: 10000 }, async () => {
  const db = client("seller");
  await assert.rejects(get(ref(db, "_access")), /permission[ _]denied/i);
  await assert.rejects(get(ref(db, "chatMessages")), /permission[ _]denied/i);
  await assert.rejects(set(ref(db, "_access/members/biz-b/seller"), { chats: true }), /permission[ _]denied/i);
  await assert.rejects(set(ref(db, "chatMessages/chat-a/forged"), { message: "forged" }), /permission[ _]denied/i);
});

test("deleting an account denies its remaining token across owned records", { timeout: 10000 }, async () => {
  await admin("_access/disabledUsers/guest-a", true);
  try {
    const db = client("guest-a", "anonymous");
    await assert.rejects(get(ref(db, "chatMessages/chat-a")), /permission[ _]denied/i);
    await assert.rejects(get(ref(db, "customerOrderUpdates/store-a/guest-a")), /permission[ _]denied/i);
  } finally {
    await admin("_access/disabledUsers/guest-a", null);
  }
});

test("revoking a membership cancels an already-open realtime listener", { timeout: 10000 }, async () => {
  const db = client("seller");
  let firstRead;
  let revoked;
  const first = new Promise((resolve) => { firstRead = resolve; });
  const cancellation = new Promise((resolve) => { revoked = resolve; });
  const unsubscribe = onValue(ref(db, "chatMessages/chat-a"), firstRead, revoked);
  try {
    await first;
    await admin("_access/members/biz-a/seller/chats", false);
    assert.match((await cancellation).code, /permission[ _]denied/i);
  } finally {
    unsubscribe();
    await admin("_access/members/biz-a/seller/chats", true);
  }
});

test("unchanged read permissions keep the existing listener open during an edit", { timeout: 10000 }, async () => {
  const db = client("seller");
  let firstRead;
  let changed;
  let rejected;
  const first = new Promise((resolve) => { firstRead = resolve; });
  const next = new Promise((resolve, reject) => { changed = resolve; rejected = reject; });
  const unsubscribe = onValue(ref(db, "chatMessages/chat-a"), (snapshot) => {
    firstRead();
    if (snapshot.child("after-edit").exists()) changed(snapshot);
  }, rejected);
  try {
    await first;
    await admin("_access/members/biz-a/seller/pending", true);
    await admin("chatMessages/chat-a/after-edit", { message: "Still connected", createdAt: "2026-01-02" });
    assert.equal((await next).child("after-edit/message").val(), "Still connected");
  } finally {
    unsubscribe();
    await admin("_access/members/biz-a/seller/pending", null);
    await admin("chatMessages/chat-a/after-edit", null);
  }
});

test("members can read only their own notification flags and cannot forge grants", { timeout: 10000 }, async () => {
  const db = client("viewer");
  assert.deepEqual((await get(ref(db, "_access/members/biz-a/viewer/notifications"))).val(), {
    orders: true, customers: false, management: false,
  });
  for (const path of ["_access/members/biz-a", "_access/members/biz-a/viewer", "_access/members/biz-a/seller/notifications"]) {
    await assert.rejects(get(ref(db, path)), /permission[ _]denied/i);
  }
  await assert.rejects(set(ref(db, "_access/members/biz-a/viewer/notifications/management"), true), /permission[ _]denied/i);
  await assert.rejects(set(ref(db, "businesses/biz-a/notificationFeeds/orders/forged"), { title: "Forged" }), /permission[ _]denied/i);
});

test("legacy broad grants and unknown scope names cannot expose payloads", { timeout: 10000 }, async () => {
  await admin("_access/members/biz-a/legacy", { notifications: true });
  await admin("_access/members/biz-a/seller/notifications/unrecognized", true);
  await admin("businesses/biz-a/notificationFeeds/unrecognized", { private: { message: "Private" } });
  try {
    const legacy = client("legacy");
    await assert.rejects(get(ref(legacy, "businesses/biz-a/notifications")), /permission[ _]denied/i);
    await assert.rejects(get(ref(legacy, "businesses/biz-a/notificationFeeds/orders")), /permission[ _]denied/i);
    await assert.rejects(get(ref(client("seller"), "businesses/biz-a/notificationFeeds/unrecognized")), /permission[ _]denied/i);
  } finally {
    await admin("_access/members/biz-a/legacy", null);
    await admin("_access/members/biz-a/seller/notifications/unrecognized", null);
    await admin("businesses/biz-a/notificationFeeds/unrecognized", null);
  }
});

test("production subscriptions follow grants and revocations without reopening unchanged feeds", { timeout: 15000 }, async () => {
  const db = client("viewer");
  let firstOrder, customerGranted, orderRevoked, customerUpdated, orderRestored;
  const first = new Promise((resolve) => { firstOrder = resolve; });
  const granted = new Promise((resolve) => { customerGranted = resolve; });
  const revoked = new Promise((resolve) => { orderRevoked = resolve; });
  const updated = new Promise((resolve) => { customerUpdated = resolve; });
  const restored = new Promise((resolve) => { orderRestored = resolve; });
  const orderEvents = [];
  const errors = [];
  let revoking = false;
  const unsubscribe = subscribeNotificationFeeds(db, "biz-a", "viewer", {
    onPermissions(scopes) {
      assert.equal(scopes.includes("management"), false);
      if (revoking && !scopes.includes("orders")) orderRevoked();
    },
    onFeed(scope, records) {
      if (scope === "orders") {
        orderEvents.push(records);
        firstOrder();
        if (records.some((record) => record.id === "after-revoke")) orderRestored();
      }
      if (scope === "customers") {
        customerGranted();
        if (records.some((record) => record.id === "after-revoke")) customerUpdated();
      }
    },
    onError: (error) => errors.push(error),
  });
  try {
    await first;
    await admin("_access/members/biz-a/viewer/notifications/customers", true);
    await granted;
    assert.equal(orderEvents.length, 1, "An unchanged order grant must keep its listener open.");
    revoking = true;
    await admin("_access/members/biz-a/viewer/notifications/orders", false);
    await revoked;
    const previousOrderEvents = orderEvents.length;
    await admin("businesses/biz-a/notificationFeeds/orders/after-revoke", { title: "Hidden while revoked", type: "new-order" });
    await admin("businesses/biz-a/notificationFeeds/customers/after-revoke", { title: "Allowed chat", type: "chat-needs-attention" });
    await updated;
    assert.equal(orderEvents.length, previousOrderEvents);
    revoking = false;
    await admin("_access/members/biz-a/viewer/notifications/orders", true);
    await restored;
    assert.equal(errors.length, 0);
  } finally {
    unsubscribe();
    await admin("_access/members/biz-a/viewer/notifications", { orders: true, customers: false, management: false });
    await admin("businesses/biz-a/notificationFeeds/orders/after-revoke", null);
    await admin("businesses/biz-a/notificationFeeds/customers/after-revoke", null);
  }
});
