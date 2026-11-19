import assert from "node:assert/strict";
import { beforeEach, test } from "node:test";

import { cachedRequest, getReadCacheSession, invalidateReadCache, limitReadCache } from "./readCache.js";

// Control completion order without timers or network requests.
function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((accept, fail) => { resolve = accept; reject = fail; });
  return { promise, resolve, reject };
}

beforeEach(() => invalidateReadCache(""));

test("revision invalidation preserves current filters and other businesses but removes obsolete cached/pending loads", async () => {
  const old = deferred();
  await cachedRequest("products:shop:old:active", () => "old", Infinity);
  const late = cachedRequest("products:shop:old:category", () => old.promise, Infinity);
  await cachedRequest("products:shop:new:active", () => "current", Infinity);
  await cachedRequest("products:other:old:active", () => "other", Infinity);
  invalidateReadCache("products:shop:", "products:shop:new:");
  assert.equal(await cachedRequest("products:shop:new:active", () => assert.fail("current revision evicted")), "current");
  assert.equal(await cachedRequest("products:other:old:active", () => assert.fail("other business evicted")), "other");
  old.resolve("late old data");
  await late;
  assert.equal(await cachedRequest("products:shop:old:category", () => "reloaded"), "reloaded");
});

test("only full session clears advance the async cache session generation", () => {
  const initial = getReadCacheSession();
  invalidateReadCache("products:shop:");
  assert.equal(getReadCacheSession(), initial);
  invalidateReadCache("");
  assert.equal(getReadCacheSession(), initial + 1);
});

test("cache reuses successful values and deduplicates pending reads", async () => {
  const response = deferred();
  let calls = 0;
  const loader = () => { calls += 1; return response.promise; };
  const first = cachedRequest("customers:shop:", loader);
  assert.equal(cachedRequest("customers:shop:", loader), first);
  response.resolve(["customer"]);
  assert.deepEqual(await first, ["customer"]);
  assert.deepEqual(await cachedRequest("customers:shop:", loader), ["customer"]);
  assert.equal(calls, 1);
});

test("expired values reload while unexpired entries remain reusable", async (t) => {
  let now = 1000;
  t.mock.method(Date, "now", () => now);
  await cachedRequest("analytics:shop:1", () => "old", 10);
  await cachedRequest("products:shop:", () => "products", 100);
  now += 11;
  assert.equal(await cachedRequest("analytics:shop:1", () => "new"), "new");
  assert.equal(await cachedRequest("products:shop:", () => assert.fail("unexpired entry reloaded")), "products");
});

test("a request for a different version also prunes abandoned expired keys", async (t) => {
  let now = 1000;
  t.mock.method(Date, "now", () => now);
  const deleted = [];
  const originalDelete = Map.prototype.delete;
  t.mock.method(Map.prototype, "delete", function (key) {
    if (key === "analytics:shop:old") deleted.push(key);
    return originalDelete.call(this, key);
  });
  await cachedRequest("analytics:shop:old", () => "old", 10);
  deleted.length = 0;
  now += 11;
  await cachedRequest("analytics:shop:new", () => "new");
  assert.deepEqual(deleted, ["analytics:shop:old"]);
});

test("prefix invalidation discards matching cached values and preserves other tenants", async () => {
  await cachedRequest("customers:shop-a:", () => "old");
  await cachedRequest("customers:shop-b:", () => "other shop");
  invalidateReadCache("customers:shop-a:");
  assert.equal(await cachedRequest("customers:shop-a:", () => "updated"), "updated");
  assert.equal(await cachedRequest("customers:shop-b:", () => assert.fail("other shop invalidated")), "other shop");
});

test("a late success after invalidation cannot replace newer cached data", async () => {
  const old = deferred();
  const first = cachedRequest("products:shop:", () => old.promise);
  invalidateReadCache("products:shop:");
  assert.equal(await cachedRequest("products:shop:", () => "updated"), "updated");
  old.resolve("stale");
  await first;
  assert.equal(await cachedRequest("products:shop:", () => assert.fail("new data overwritten")), "updated");
});

test("a late success cannot detach the replacement request while it is pending", async () => {
  const old = deferred();
  const fresh = deferred();
  const first = cachedRequest("customers:shop:", () => old.promise);
  invalidateReadCache("customers:shop:");
  const second = cachedRequest("customers:shop:", () => fresh.promise);
  old.resolve("stale");
  await first;
  assert.equal(cachedRequest("customers:shop:", () => assert.fail("replacement detached")), second);
  fresh.resolve("new");
  assert.equal(await second, "new");
});

test("a late failure cannot detach the replacement request", async () => {
  const old = deferred();
  const fresh = deferred();
  const first = cachedRequest("analytics:shop:1", () => old.promise);
  const rejected = assert.rejects(first, /old request failed/);
  invalidateReadCache("analytics:shop:");
  const second = cachedRequest("analytics:shop:1", () => fresh.promise);
  old.reject(new Error("old request failed"));
  await rejected;
  assert.equal(cachedRequest("analytics:shop:1", () => assert.fail("replacement detached")), second);
  fresh.resolve("new");
  await second;
});

test("a failed current request can be retried without caching its error", async () => {
  await assert.rejects(cachedRequest("products:shop:", () => { throw new Error("failed"); }), /failed/);
  assert.equal(await cachedRequest("products:shop:", () => "retried"), "retried");
});

test("clearing the session detaches all pending keys without disturbing subsequent loads", async () => {
  const old = deferred();
  const first = cachedRequest("customers:shop:", () => old.promise);
  await cachedRequest("products:shop:", () => "old products");
  invalidateReadCache("");
  assert.equal(await cachedRequest("customers:shop:", () => "staff customers"), "staff customers");
  assert.equal(await cachedRequest("products:shop:", () => "staff products"), "staff products");
  old.resolve("owner customers");
  await first;
  assert.equal(await cachedRequest("customers:shop:", () => assert.fail("old session returned")), "staff customers");
});


// Search retention must not evict product caches, another tenant's results or independent pending work.
test("query retention discards oldest completed entries only within its business prefix", async () => {
  await cachedRequest("search:shop-a:old", () => "old", Infinity);
  await cachedRequest("search:shop-b:other", () => "other", Infinity);
  await cachedRequest("products:shop-a:revision", () => "products", Infinity);
  await cachedRequest("search:shop-a:current", () => "current", Infinity);
  const late = deferred();
  const pending = cachedRequest("search:shop-a:pending", () => late.promise, Infinity);
  limitReadCache("search:shop-a:", 1);
  assert.equal(await cachedRequest("search:shop-a:current", () => assert.fail("current result evicted")), "current");
  assert.equal(await cachedRequest("search:shop-b:other", () => assert.fail("other tenant evicted")), "other");
  assert.equal(await cachedRequest("products:shop-a:revision", () => assert.fail("product cache evicted")), "products");
  assert.equal(cachedRequest("search:shop-a:pending", () => assert.fail("pending request detached")), pending);
  late.resolve("late");
  await pending;
  assert.equal(await cachedRequest("search:shop-a:old", () => "reloaded"), "reloaded");
});
