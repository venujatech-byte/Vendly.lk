import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { beforeEach, test } from "node:test";

import { invalidateReadCache } from "./readCache.js";

// Exercise real search/cache code offline, replacing only the authenticated HTTP boundary.
let respond;
let respondVersion;
const calls = [];
const versionCalls = [];
globalThis.__vendlySearchCacheRequest = async (path, options) => {
  const url = new URL(path, "https://synthetic.example");
  if (url.pathname.endsWith("/search/cache/version")) {
    versionCalls.push({ path, options });
    return respondVersion(url, options);
  }
  calls.push({ path, options });
  return respond(url, options);
};
const moduleUrl = new URL("./searchService.js", import.meta.url);
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (context.parentURL === moduleUrl.href) {
      if (specifier === "./apiClient") return { url: "search-cache-test:api", shortCircuit: true };
      if (specifier === "./readCache") return { url: new URL("./readCache.js", import.meta.url).href, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url === "search-cache-test:api") return {
      format: "module", shortCircuit: true,
      source: "export const apiRequest = globalThis.__vendlySearchCacheRequest;",
    };
    return nextLoad(url, context);
  },
});
const { searchBusiness } = await import(moduleUrl.href);
hook.deregister();

const fullScope = "orders,products,customers";
function results(scope, id) {
  return Object.fromEntries(["orders", "products", "customers"].map((module) => [module, scope.split(",").includes(module) ? [{ id }] : []]));
}
function deferred() {
  let resolve;
  const promise = new Promise((accept) => { resolve = accept; });
  return { promise, resolve };
}

beforeEach(() => {
  invalidateReadCache("");
  calls.length = 0;
  versionCalls.length = 0;
  respondVersion = () => ({ revision: "a".repeat(64), scope: fullScope });
  respond = (url) => ({ scope: fullScope, results: results(fullScope, url.searchParams.get("q")) });
});

test("repeated queries reuse results beyond a day but always recheck permissions and freshness", async (t) => {
  let now = 1000;
  t.mock.method(Date, "now", () => now);
  const original = await searchBusiness("shop-a", "query");
  now += 24 * 60 * 60 * 1000;
  assert.equal(await searchBusiness("shop-a", "query"), original);
  assert.equal(calls.length, 1);
  assert.equal(versionCalls.length, 2);
});

test("mobile data changes reload cached queries while preserving other tenant results", async () => {
  await searchBusiness("shop-a", "query");
  const other = await searchBusiness("shop-b", "query");
  respondVersion = (url) => ({ revision: (url.pathname.includes("shop-a") ? "b" : "a").repeat(64), scope: fullScope });
  respond = () => ({ scope: fullScope, results: results(fullScope, "mobile") });
  assert.equal((await searchBusiness("shop-a", "query")).orders[0].id, "mobile");
  assert.equal(await searchBusiness("shop-b", "query"), other);
  assert.equal(calls.length, 3);
});

test("permission reduction discards broader results even if business data did not change", async () => {
  await searchBusiness("shop-a", "query");
  respondVersion = () => ({ revision: "b".repeat(64), scope: "orders" });
  respond = () => ({ scope: "orders", results: results("orders", "allowed") });
  const restricted = await searchBusiness("shop-a", "query");
  assert.deepEqual(restricted.products, []);
  assert.equal(restricted.orders[0].id, "allowed");
  assert.equal(calls.length, 2);
});

test("permissions changing between validation and data cannot cache broader results under a narrow scope", async () => {
  respondVersion = () => ({ revision: "a".repeat(64), scope: "orders" });
  // The user briefly gains inventory/customer access before the data request, then loses it again.
  const expanded = await searchBusiness("shop-a", "query");
  assert.equal(expanded.products.length, 1);
  respond = () => ({ scope: "orders", results: results("orders", "restricted-again") });
  const restricted = await searchBusiness("shop-a", "query");
  assert.deepEqual(restricted.products, []);
  assert.equal(restricted.orders[0].id, "restricted-again");
  assert.equal(calls.length, 2);
  assert.equal(await searchBusiness("shop-a", "query"), restricted);
});

test("legacy responses without scope remain usable but cannot populate the search cache", async () => {
  respond = () => ({ results: results(fullScope, "legacy") });
  await searchBusiness("shop-a", "query");
  await searchBusiness("shop-a", "query");
  assert.equal(calls.length, 2);
});

test("denied or malformed revision checks never return cached private results", async () => {
  await searchBusiness("shop-a", "query");
  respondVersion = () => { throw new Error("Access revoked"); };
  await assert.rejects(searchBusiness("shop-a", "query"), /Access revoked/);
  for (const version of [
    { revision: null, scope: fullScope }, { revision: "", scope: fullScope },
    { revision: "x".repeat(64), scope: fullScope }, { revision: "a".repeat(64) },
    { revision: "a".repeat(64), scope: "x".repeat(81) },
  ]) {
    respondVersion = () => version;
    await assert.rejects(searchBusiness("shop-a", "query"), /freshness could not be verified/);
  }
  assert.equal(calls.length, 1);
});

test("members without searchable modules get empty results without a second request", async () => {
  respondVersion = () => ({ revision: "b".repeat(64), scope: "" });
  assert.deepEqual(await searchBusiness("shop-a", "query"), { orders: [], products: [], customers: [] });
  assert.equal(calls.length, 0);
  assert.equal(versionCalls.length, 1);
});

test("raw Unicode, markup and phone queries reach the server without browser normalization", async () => {
  const query = "ශ්‍රී & +94 77 / <b>x</b>";
  await searchBusiness("shop-a", query);
  assert.equal(new URL(calls[0].path, "https://synthetic.example").searchParams.get("q"), query);
});

test("an aborted request never starts validation or returns cached data", async () => {
  await searchBusiness("shop-a", "query");
  const controller = new AbortController();
  controller.abort();
  await assert.rejects(searchBusiness("shop-a", "query", controller.signal), { name: "AbortError" });
  assert.equal(versionCalls.length, 1);
});

test("logout during a version check prevents old-session data requests", async () => {
  const version = deferred();
  respondVersion = () => version.promise;
  const old = searchBusiness("shop-a", "query");
  invalidateReadCache("");
  version.resolve({ revision: "a".repeat(64), scope: fullScope });
  await assert.rejects(old, { name: "AbortError" });
  assert.equal(calls.length, 0);
});

test("one cancelled consumer cannot cancel another consumer or replace its result", async () => {
  const entered = deferred();
  const later = deferred();
  const controller = new AbortController();
  respond = (_url, options) => {
    if (options.signal === controller.signal) { entered.resolve(); return later.promise; }
    return { scope: fullScope, results: results(fullScope, "fresh") };
  };
  const old = searchBusiness("shop-a", "query", controller.signal);
  await entered.promise;
  const current = await searchBusiness("shop-a", "query");
  controller.abort();
  later.resolve({ scope: fullScope, results: results(fullScope, "old") });
  await assert.rejects(old, { name: "AbortError" });
  assert.equal(await searchBusiness("shop-a", "query"), current);
  assert.equal(calls.length, 2);
});

test("late pre-logout data cannot repopulate the cache", async () => {
  const entered = deferred();
  const later = deferred();
  respond = () => { entered.resolve(); return later.promise; };
  const old = searchBusiness("shop-a", "query");
  await entered.promise;
  invalidateReadCache("");
  respond = () => ({ scope: fullScope, results: results(fullScope, "current") });
  const current = await searchBusiness("shop-a", "query");
  later.resolve({ scope: fullScope, results: results(fullScope, "old") });
  await assert.rejects(old, { name: "AbortError" });
  assert.equal(await searchBusiness("shop-a", "query"), current);
  assert.equal(calls.length, 2);
});

test("the 50-query bound evicts oldest results without disturbing another business", async () => {
  const other = await searchBusiness("shop-b", "other");
  for (let index = 0; index <= 50; index += 1) await searchBusiness("shop-a", `query-${index}`);
  await searchBusiness("shop-a", "query-50");
  assert.equal(await searchBusiness("shop-b", "other"), other);
  assert.equal(calls.length, 52);
  await searchBusiness("shop-a", "query-0");
  assert.equal(calls.length, 53);
});

test("a failed search after a revision change cannot fall back to old results or cache its error", async () => {
  await searchBusiness("shop-a", "query");
  respondVersion = () => ({ revision: "b".repeat(64), scope: fullScope });
  respond = () => { throw new Error("Search request failed"); };
  await assert.rejects(searchBusiness("shop-a", "query"), /Search request failed/);
  respond = () => ({ scope: fullScope, results: results(fullScope, "retried") });
  const retried = await searchBusiness("shop-a", "query");
  assert.equal(retried.orders[0].id, "retried");
  assert.equal(await searchBusiness("shop-a", "query"), retried);
  assert.equal(calls.length, 3);
});
