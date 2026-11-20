import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { beforeEach, test } from "node:test";

import { invalidateReadCache } from "./readCache.js";

// Run the actual order loader/mapping offline; replace only its HTTP boundary.
let respond;
const calls = [];
const versionCalls = [];
let respondVersion;
globalThis.__vendlyOrderPageRequest = async (path, options) => {
  if (path.endsWith("/orders/cache/version")) {
    versionCalls.push({ path, options });
    return respondVersion(options);
  }
  calls.push({ path, options });
  return respond(new URL(path, "https://synthetic.example"), options);
};
const moduleUrl = new URL("./orderService.js", import.meta.url);
const operationUrl = new URL("./operationService.js", import.meta.url);
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if ([moduleUrl.href, operationUrl.href].includes(context.parentURL)) {
      if (specifier === "./apiClient") return { url: "order-pagination-test:api", shortCircuit: true };
      if (specifier === "./orderService") return { url: moduleUrl.href, shortCircuit: true };
      if (specifier === "./readCache") return { url: new URL("./readCache.js", import.meta.url).href, shortCircuit: true };
      if (specifier === "./orderNotes") return { url: new URL("./orderNotes.js", import.meta.url).href, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url === "order-pagination-test:api") return {
      format: "module", shortCircuit: true,
      source: "export const apiRequest = globalThis.__vendlyOrderPageRequest; export const apiFileRequest = () => { throw new Error('Unexpected file request'); };",
    };
    return nextLoad(url, context);
  },
});
const { getOrders, createOrder, recordOrderPayment, getPaymentReceiptLinks, updateOrderStatus, removeOrder, updateOrder } = await import(moduleUrl.href);
const { generateOrderWaybill, reportFraudOrder, reportCourierIssue } = await import(operationUrl.href);
hook.deregister();

function deferred() {
  let resolve;
  const promise = new Promise((accept) => { resolve = accept; });
  return { promise, resolve };
}

beforeEach(() => {
  invalidateReadCache("");
  calls.length = 0;
  versionCalls.length = 0;
  respondVersion = () => ({ revision: "revision-1" });
});

test("receipt previews and opens request fresh links outside the order cache", async () => {
  // The second request must reach the API again so it can recheck access and expiry.
  const { signal } = new AbortController();
  respond = (url) => {
    assert.equal(url.pathname, "/businesses/shop-a/orders/order-a/payment-receipts/links");
    return { links: { receipt: `https://example.test/link-${calls.length}` } };
  };
  assert.equal((await getPaymentReceiptLinks("shop-a", "order-a", signal)).receipt, "https://example.test/link-1");
  assert.equal((await getPaymentReceiptLinks("shop-a", "order-a")).receipt, "https://example.test/link-2");
  assert.equal(calls[0].options.signal, signal);
  assert.deepEqual(versionCalls, []);
});

test("fetches all pages including empty search pages and retains every filter", async () => {
  const first = Array.from({ length: 200 }, (_, index) => ({ id: `recent-${index}`, totalAmountMinor: 100 }));
  respond = (url) => {
    const cursor = url.searchParams.get("after");
    if (!cursor) return { orders: first, hasMore: true, nextCursor: "cursor-1" };
    if (cursor === "cursor-1") return { orders: [], hasMore: true, nextCursor: "cursor-2" };
    assert.equal(cursor, "cursor-2");
    return { orders: [{ id: "older-than-200", totalAmountMinor: 200 }], hasMore: false, nextCursor: null };
  };
  const filters = { search: "old & new", status: "confirmed", dateFrom: "2025-01-01", dateTo: "2026-01-01", courierId: "courier-1" };
  const orders = await getOrders("shop-a", filters);
  assert.equal(orders.length, 201);
  assert.equal(orders.at(-1).id, "older-than-200");
  assert.equal(orders.reduce((total, order) => total + order.totalAmountMinor, 0), 20200);
  assert.equal(calls.length, 3);
  for (const { path } of calls) {
    const url = new URL(path, "https://synthetic.example");
    assert.equal(url.pathname, "/businesses/shop-a/orders");
    for (const [key, value] of Object.entries(filters)) assert.equal(url.searchParams.get(key), value);
  }
});

test("mapping and server order are retained before the existing browser sort runs", async () => {
  respond = () => ({ orders: [
    { id: "newer", fulfilmentStatus: "needs-confirmation", customerSnapshot: { name: "Customer" }, totalAmountMinor: 12345 },
    { id: "older", fulfilmentStatus: "delivered", totalAmountMinor: 200 },
  ], hasMore: false });
  const orders = await getOrders("shop-a");
  assert.deepEqual(orders.map(({ id }) => id), ["newer", "older"]);
  assert.equal(orders[0].status, "pending");
  assert.equal(orders[0].customerName, "Customer");
  assert.equal(orders[0].totalAmountMinor, 12345);
  assert.equal(orders[1].fulfilmentStatus, "delivered");
});

test("a later-page authorization/error response rejects instead of publishing a partial list", async () => {
  respond = (url) => {
    if (url.searchParams.has("after")) throw new Error("Access revoked");
    return { orders: [{ id: "first" }], hasMore: true, nextCursor: "cursor-1" };
  };
  await assert.rejects(getOrders("shop-a"), /Access revoked/);
  assert.equal(calls.length, 2);
});

test("overlapping pages cannot duplicate orders and the latest copy retains its fields", async () => {
  respond = (url) => url.searchParams.has("after")
    ? { orders: [{ id: "same", totalAmountMinor: 200 }, { id: "older" }], hasMore: false }
    : { orders: [{ id: "same", totalAmountMinor: 100 }], hasMore: true, nextCursor: "cursor-1" };
  const orders = await getOrders("shop-a");
  assert.deepEqual(orders.map(({ id }) => id), ["same", "older"]);
  assert.equal(orders[0].totalAmountMinor, 200);
});

test("repeated cursors fail instead of causing an endless request loop", async () => {
  respond = () => ({ orders: [], hasMore: true, nextCursor: "same-cursor" });
  await assert.rejects(getOrders("shop-a"), /Orders could not be loaded/);
  assert.equal(calls.length, 2);
});

test("a missing continuation cursor fails instead of silently truncating results", async () => {
  respond = () => ({ orders: [], hasMore: true });
  await assert.rejects(getOrders("shop-a"), /Orders could not be loaded/);
  assert.equal(calls.length, 1);
});

test("an already-aborted load never sends an API request", async () => {
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(getOrders("shop-a", {}, { signal: controller.signal }), { name: "AbortError" });
  assert.equal(calls.length, 0);
});

test("changed filters or tenants can cancel a load before it requests another page", async () => {
  const controller = new AbortController();
  respond = (_url, options) => {
    assert.equal(options.signal, controller.signal);
    controller.abort();
    return { orders: [{ id: "stale" }], hasMore: true, nextCursor: "cursor-1" };
  };
  await assert.rejects(getOrders("shop-a", {}, { signal: controller.signal }), { name: "AbortError" });
  assert.equal(calls.length, 1);
});


// Reuse completed data only after the authenticated revision check, across all unchanged filters.
test("unchanged order lists survive elapsed time and filter caches remain isolated", async (t) => {
  let now = 1000;
  t.mock.method(Date, "now", () => now);
  respond = (url) => ({ orders: [{ id: url.searchParams.get("search") || "all" }], hasMore: false });
  const all = await getOrders("shop-a");
  const searched = await getOrders("shop-a", { search: "query" });
  now += 24 * 60 * 60 * 1000;
  assert.equal(await getOrders("shop-a"), all);
  assert.equal(await getOrders("shop-a", { search: "query" }), searched);
  assert.equal(calls.length, 2);
  assert.equal(versionCalls.length, 4);
});

test("changed mobile revisions refresh matching lists without evicting another tenant", async () => {
  respond = () => ({ orders: [{ id: "old" }], hasMore: false });
  await getOrders("shop-a");
  await getOrders("shop-b");
  respondVersion = () => ({ revision: "mobile-change" });
  respond = () => ({ orders: [{ id: "mobile" }], hasMore: false });
  assert.equal((await getOrders("shop-a"))[0].id, "mobile");
  respondVersion = () => ({ revision: "revision-1" });
  assert.equal((await getOrders("shop-b"))[0].id, "old");
  assert.equal(calls.length, 3);
});

test("authorization errors and invalid revisions do not return cached order contacts or money", async () => {
  respond = () => ({ orders: [{ id: "private" }], hasMore: false });
  await getOrders("shop-a");
  respondVersion = () => { throw new Error("Access revoked"); };
  await assert.rejects(getOrders("shop-a"), /Access revoked/);
  for (const revision of [null, "", 5, "x".repeat(129)]) {
    respondVersion = () => ({ revision });
    await assert.rejects(getOrders("shop-a"), /freshness could not be verified/);
  }
  assert.equal(calls.length, 1);
});

test("logout while checking a revision prevents any old-session order load", async () => {
  const version = deferred();
  respondVersion = () => version.promise;
  const old = getOrders("shop-a");
  invalidateReadCache("");
  version.resolve({ revision: "revision-1" });
  await assert.rejects(old, { name: "AbortError" });
  assert.equal(calls.length, 0);
});

test("independent consumers do not inherit a cancelled order request", async () => {
  const entered = deferred();
  const later = deferred();
  const controller = new AbortController();
  respond = (_url, options) => {
    if (options.signal === controller.signal) { entered.resolve(); return later.promise; }
    return { orders: [{ id: "current" }], hasMore: false };
  };
  const old = getOrders("shop-a", {}, { signal: controller.signal });
  await entered.promise;
  const fresh = await getOrders("shop-a");
  controller.abort();
  later.resolve({ orders: [{ id: "old" }], hasMore: true, nextCursor: "unused" });
  await assert.rejects(old, { name: "AbortError" });
  assert.equal(await getOrders("shop-a"), fresh);
  assert.equal(fresh[0].id, "current");
  assert.equal(calls.length, 2);
});

test("cancelling during revision validation prevents page requests and passes the signal through", async () => {
  const controller = new AbortController();
  respondVersion = (options) => {
    assert.equal(options.signal, controller.signal);
    controller.abort();
    return { revision: "revision-1" };
  };
  await assert.rejects(getOrders("shop-a", {}, { signal: controller.signal }), { name: "AbortError" });
  assert.equal(calls.length, 0);
});

for (const [name, mutate] of [
  ["create", () => createOrder("shop-a", {})],
  ["payment", () => recordOrderPayment("shop-a", "a", {})],
  ["status", () => updateOrderStatus("shop-a", "a", "confirmed")],
  ["remove", () => removeOrder("shop-a", "a")],
  ["edit", () => updateOrder("shop-a", "a", {})],
  ["waybill", () => generateOrderWaybill("shop-a", "a")],
  ["fraud report", () => reportFraudOrder("shop-a", "a", "fake-details")],
  ["courier issue", () => reportCourierIssue("shop-a", "a", "lost")],
]) {
  test(`successful ${name} invalidates order lists; rejected writes retain cached data`, async () => {
    respond = (_url, options) => {
      if (options?.method) throw new Error("Rejected change");
      return { orders: [{ id: "a", customerSnapshot: { name: "Original" } }], hasMore: false };
    };
    const original = await getOrders("shop-a");
    await assert.rejects(mutate(), /Rejected change/);
    assert.equal(await getOrders("shop-a"), original);
    respond = (_url, options) => options?.method ? { order: {}, fraudReport: {}, courierIssue: {} }
      : { orders: [{ id: "a", customerSnapshot: { name: "Changed" } }], hasMore: false };
    await mutate();
    assert.equal((await getOrders("shop-a"))[0].customerName, "Changed");
    assert.equal(calls.length, 4);
  });
}

test("late invalidated order pages cannot overwrite a new session cache", async () => {
  const entered = deferred();
  const later = deferred();
  respond = (url) => {
    if (url.searchParams.has("after")) { entered.resolve(); return later.promise; }
    return { orders: [{ id: "old" }], hasMore: true, nextCursor: "cursor-1" };
  };
  const old = getOrders("shop-a");
  await entered.promise;
  invalidateReadCache("");
  respond = () => ({ orders: [{ id: "current" }], hasMore: false });
  const current = await getOrders("shop-a");
  later.resolve({ orders: [{ id: "old-2" }], hasMore: false });
  await old;
  assert.equal(await getOrders("shop-a"), current);
  assert.equal(calls.length, 3);
});
