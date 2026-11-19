import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { beforeEach, test } from "node:test";

import { invalidateReadCache } from "./readCache.js";

// Exercise the real customer loader and cache offline; replace only authenticated HTTP requests.
let respond;
const calls = [];
globalThis.__vendlyCustomerPageRequest = async (path, options) => {
  calls.push({ path, options });
  return respond(new URL(path, "https://synthetic.example"), options);
};
const moduleUrl = new URL("./customerService.js", import.meta.url);
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (context.parentURL === moduleUrl.href) {
      if (specifier === "./apiClient") return { url: "customer-pagination-test:api", shortCircuit: true };
      if (specifier === "./readCache") return { url: new URL("./readCache.js", import.meta.url).href, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url === "customer-pagination-test:api") return {
      format: "module", shortCircuit: true,
      source: "export const apiRequest = globalThis.__vendlyCustomerPageRequest;",
    };
    return nextLoad(url, context);
  },
});
const { getCustomers, updateCustomer, downloadCustomersCsv } = await import(moduleUrl.href);
hook.deregister();

function deferred() {
  let resolve;
  const promise = new Promise((accept) => { resolve = accept; });
  return { promise, resolve };
}

beforeEach(() => { invalidateReadCache(""); calls.length = 0; });

test("all scan pages load before name sorting, including empty matching pages", async () => {
  const first = Array.from({ length: 200 }, (_, index) => ({ id: `customer-${index}`, name: `Name ${String(199 - index).padStart(3, "0")}` }));
  respond = (url) => {
    assert.equal(url.pathname, "/businesses/shop-a/customers");
    assert.equal(url.searchParams.get("search"), "old & new");
    const cursor = url.searchParams.get("after");
    if (!cursor) return { customers: first, hasMore: true, nextCursor: "cursor-1" };
    if (cursor === "cursor-1") return { customers: [], hasMore: true, nextCursor: "cursor-2" };
    assert.equal(cursor, "cursor-2");
    return { customers: [{ id: "beyond-200", name: "AAA later match" }], hasMore: false };
  };
  const customers = await getCustomers("shop-a", "old & new");
  assert.equal(customers.length, 201);
  assert.equal(customers[0].id, "beyond-200");
  assert.equal(customers[1].name, "Name 000");
  assert.equal(calls.length, 3);
});

test("default name ordering matches Firestore Unicode order and preserves equal-name ID ties", async () => {
  const names = ["😀", "A", "é", "ආ", "\uE000", "a", "A", "", null];
  respond = () => ({ customers: names.map((name, index) => ({ id: String(index), name })), hasMore: false });
  assert.deepEqual((await getCustomers("shop-a")).map(({ id }) => id), ["8", "7", "1", "6", "5", "2", "3", "4", "0"]);
});

test("concurrent consumers share the complete load and cache only the finished list", async () => {
  const entered = deferred();
  const later = deferred();
  respond = (url) => {
    if (url.searchParams.has("after")) { entered.resolve(); return later.promise; }
    return { customers: [{ id: "a", name: "A" }], hasMore: true, nextCursor: "cursor-1" };
  };
  const first = getCustomers("shop-a");
  await entered.promise;
  const second = getCustomers("shop-a");
  assert.equal(calls.length, 2);
  later.resolve({ customers: [{ id: "b", name: "B" }], hasMore: false });
  const results = await Promise.all([first, second]);
  assert.equal(results[0], results[1]);
  assert.equal(results[0].length, 2);
  assert.equal(await getCustomers("shop-a"), results[0]);
  assert.equal(calls.length, 2);
});

test("a later-page error rejects without caching a partial list and allows a full retry", async () => {
  respond = (url) => {
    if (url.searchParams.has("after")) throw new Error("Access revoked");
    return { customers: [{ id: "partial", name: "Partial" }], hasMore: true, nextCursor: "cursor-1" };
  };
  await assert.rejects(getCustomers("shop-a"), /Access revoked/);
  respond = () => ({ customers: [{ id: "fresh", name: "Fresh" }], hasMore: false });
  assert.deepEqual((await getCustomers("shop-a")).map(({ id }) => id), ["fresh"]);
  assert.equal(calls.length, 3);
});

test("repeated and missing cursors fail instead of looping or silently truncating the cache", async () => {
  respond = () => ({ customers: [], hasMore: true, nextCursor: "repeated" });
  await assert.rejects(getCustomers("shop-a"), /Customers could not be loaded/);
  assert.equal(calls.length, 2);
  respond = () => ({ customers: [], hasMore: true });
  await assert.rejects(getCustomers("shop-a"), /Customers could not be loaded/);
  assert.equal(calls.length, 3);
});

test("overlapping pages deduplicate identities while retaining the latest customer fields", async () => {
  respond = (url) => url.searchParams.has("after")
    ? { customers: [{ id: "same", name: "Renamed" }, { id: "new", name: "A new customer" }], hasMore: false }
    : { customers: [{ id: "same", name: "Original" }], hasMore: true, nextCursor: "cursor-1" };
  const customers = await getCustomers("shop-a");
  assert.deepEqual(customers.map(({ id }) => id), ["new", "same"]);
  assert.equal(customers[1].name, "Renamed");
});

test("a customer edit invalidates the completed list before the next read", async () => {
  respond = (_url, options) => options?.method === "PATCH"
    ? { customer: { id: "a", name: "Updated" } }
    : { customers: [{ id: "a", name: "Original" }], hasMore: false };
  assert.equal((await getCustomers("shop-a"))[0].name, "Original");
  await updateCustomer("shop-a", "a", { name: "Updated" });
  respond = () => ({ customers: [{ id: "a", name: "Updated" }], hasMore: false });
  assert.equal((await getCustomers("shop-a"))[0].name, "Updated");
  assert.equal(calls.length, 3);
});

test("invalidated old pages cannot replace a newer account's cached result", async () => {
  const entered = deferred();
  const later = deferred();
  respond = (url) => {
    if (url.searchParams.has("after")) { entered.resolve(); return later.promise; }
    return { customers: [{ id: "old", name: "Old session" }], hasMore: true, nextCursor: "cursor-1" };
  };
  const oldLoad = getCustomers("shop-a");
  await entered.promise;
  invalidateReadCache("");
  respond = () => ({ customers: [{ id: "current", name: "Current session" }], hasMore: false });
  await getCustomers("shop-a");
  later.resolve({ customers: [{ id: "old-2", name: "Old second page" }], hasMore: false });
  await oldLoad;
  assert.deepEqual((await getCustomers("shop-a")).map(({ id }) => id), ["current"]);
  assert.equal(calls.length, 3);
});

test("search and unfiltered list TTLs remain unchanged", async (t) => {
  let now = 1000;
  t.mock.method(Date, "now", () => now);
  respond = () => ({ customers: [], hasMore: false });
  await getCustomers("shop-a");
  await getCustomers("shop-a", "query");
  now += 16000;
  await getCustomers("shop-a");
  await getCustomers("shop-a", "query");
  assert.equal(calls.length, 3);
});

test("CSV export includes customers from every API page", async (t) => {
  respond = (url) => url.searchParams.has("after")
    ? { customers: [{ id: "later", name: "Later customer" }], hasMore: false }
    : { customers: Array.from({ length: 200 }, (_, index) => ({ id: String(index), name: `Customer ${index}` })), hasMore: true, nextCursor: "cursor-1" };
  let exported;
  t.mock.method(URL, "createObjectURL", (blob) => { exported = blob; return "blob:synthetic-export"; });
  t.mock.method(URL, "revokeObjectURL", () => {});
  const original = globalThis.document;
  globalThis.document = { body: { appendChild() {} }, createElement: () => ({ click() {}, remove() {} }) };
  t.after(() => { if (original === undefined) delete globalThis.document; else globalThis.document = original; });
  downloadCustomersCsv(await getCustomers("shop-a"));
  const csv = await exported.text();
  assert.equal(csv.split("\r\n").length, 202);
  assert.ok(csv.includes('"Later customer"'));
});
