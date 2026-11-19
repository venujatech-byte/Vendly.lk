import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { beforeEach, test } from "node:test";

// Run the actual order loader/mapping offline; replace only its HTTP boundary.
let respond;
const calls = [];
globalThis.__vendlyOrderPageRequest = async (path, options) => {
  calls.push({ path, options });
  return respond(new URL(path, "https://synthetic.example"), options);
};
const moduleUrl = new URL("./orderService.js", import.meta.url);
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (context.parentURL === moduleUrl.href) {
      if (specifier === "./apiClient") return { url: "order-pagination-test:api", shortCircuit: true };
      if (specifier === "./orderNotes") return { url: new URL("./orderNotes.js", import.meta.url).href, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url === "order-pagination-test:api") return {
      format: "module", shortCircuit: true,
      source: "export const apiRequest = globalThis.__vendlyOrderPageRequest;",
    };
    return nextLoad(url, context);
  },
});
const { getOrders } = await import(moduleUrl.href);
hook.deregister();

beforeEach(() => { calls.length = 0; });

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
