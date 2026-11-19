import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { beforeEach, test } from "node:test";

import { invalidateReadCache } from "./readCache.js";

// Use the actual loader, cache and inventory mapping; replace only its authenticated HTTP boundary.
let respond;
const calls = [];
const versionCalls = [];
let respondVersion;
globalThis.__vendlyProductPageRequest = async (path, options) => {
  // Keep document-data requests separate from the cheap authorized revision checks.
  if (path.endsWith("/inventory/version")) {
    versionCalls.push(path);
    return respondVersion();
  }
  calls.push({ path, options });
  return respond(new URL(path, "https://synthetic.example"), options);
};
const moduleUrl = new URL("./productService.js", import.meta.url);
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (context.parentURL === moduleUrl.href) {
      if (specifier === "./apiClient") return { url: "product-pagination-test:api", shortCircuit: true };
      if (specifier === "./readCache") return { url: new URL("./readCache.js", import.meta.url).href, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url === "product-pagination-test:api") return {
      format: "module", shortCircuit: true,
      source: "export const apiRequest = globalThis.__vendlyProductPageRequest; export const apiFileRequest = () => { throw new Error('Unexpected file request'); };",
    };
    return nextLoad(url, context);
  },
});
const { getProducts, createProduct, updateProduct, updateProductStatus, uploadVariantImage, generateProductDescription } = await import(moduleUrl.href);
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

test("complete pages retain category/status filters, server order and inventory mapping", async () => {
  const first = Array.from({ length: 200 }, (_, index) => ({ id: `product-${index}`, name: `Product ${index}` }));
  first[0] = { ...first[0], costPriceMinor: 12345, sellingPriceMinor: 23456, weightGrams: 750,
    availableStock: 3, variantSummaries: [{ id: "variant-a", sku: "SKU-A", barcode: "BAR-A", stockAvailable: 3 }] };
  respond = (url) => {
    assert.equal(url.pathname, "/businesses/shop-a/products");
    assert.equal(url.searchParams.get("categoryId"), "cat & one");
    assert.equal(url.searchParams.get("status"), "active");
    return url.searchParams.has("after")
      ? { products: [{ id: "beyond-200", name: "Later product" }], hasMore: false }
      : { products: first, hasMore: true, nextCursor: "cursor-1" };
  };
  const products = await getProducts("shop-a", { categoryId: "cat & one", status: "active" });
  assert.equal(products.length, 201);
  assert.equal(products[0].id, "product-0");
  assert.equal(products.at(-1).id, "beyond-200");
  assert.equal(products[0].costPrice, 123.45);
  assert.equal(products[0].sellingPrice, 234.56);
  assert.equal(products[0].weightKg, 0.75);
  assert.equal(products[0].sizes[0].id, "variant-a");
  assert.equal(products[0].sizes[0].stockAvailable, 3);
  assert.equal(calls.length, 2);
});

test("the complete filtered load is shared and cached for existing consumers", async () => {
  const entered = deferred();
  const later = deferred();
  respond = (url) => {
    if (url.searchParams.has("after")) { entered.resolve(); return later.promise; }
    return { products: [{ id: "a" }], hasMore: true, nextCursor: "cursor-1" };
  };
  const first = getProducts("shop-a", { status: "active" });
  await entered.promise;
  const second = getProducts("shop-a", { status: "active" });
  assert.equal(calls.length, 2);
  later.resolve({ products: [{ id: "b" }], hasMore: false });
  const results = await Promise.all([first, second]);
  assert.equal(results[0], results[1]);
  assert.equal(results[0].length, 2);
  assert.equal(await getProducts("shop-a", { status: "active" }), results[0]);
  assert.equal(calls.length, 2);
});

test("later-page failures reject without caching a partial inventory and allow retry", async () => {
  respond = (url) => {
    if (url.searchParams.has("after")) throw new Error("Access revoked");
    return { products: [{ id: "partial" }], hasMore: true, nextCursor: "cursor-1" };
  };
  await assert.rejects(getProducts("shop-a"), /Access revoked/);
  respond = () => ({ products: [{ id: "recovered" }], hasMore: false });
  assert.deepEqual((await getProducts("shop-a")).map(({ id }) => id), ["recovered"]);
  assert.equal(calls.length, 3);
});

test("missing and repeated cursors fail instead of silently truncating or looping", async () => {
  respond = () => ({ products: [], hasMore: true, nextCursor: "repeated" });
  await assert.rejects(getProducts("shop-a"), /Products could not be loaded/);
  assert.equal(calls.length, 2);
  respond = () => ({ products: [], hasMore: true });
  await assert.rejects(getProducts("shop-a"), /Products could not be loaded/);
  assert.equal(calls.length, 3);
});

test("overlapping pages retain only the latest copy without changing ID order", async () => {
  respond = (url) => url.searchParams.has("after")
    ? { products: [{ id: "same", availableStock: 2 }, { id: "later" }], hasMore: false }
    : { products: [{ id: "same", availableStock: 1 }], hasMore: true, nextCursor: "cursor-1" };
  const products = await getProducts("shop-a");
  assert.deepEqual(products.map(({ id }) => id), ["same", "later"]);
  assert.equal(products[0].stock, 2);
});

test("product creation still invalidates every cached category/status list", async () => {
  respond = (_url, options) => options?.method === "POST"
    ? { product: { id: "b", availableStock: 2 } }
    : { products: [{ id: "a", availableStock: 1 }], hasMore: false };
  await getProducts("shop-a", { categoryId: "cat-a" });
  await getProducts("shop-a", { status: "active" });
  await createProduct("shop-a", { name: "New product" });
  respond = () => ({ products: [{ id: "a", availableStock: 1 }, { id: "b", availableStock: 2 }], hasMore: false });
  assert.deepEqual((await getProducts("shop-a", { categoryId: "cat-a" })).map(({ id }) => id), ["a", "b"]);
  assert.deepEqual((await getProducts("shop-a", { status: "active" })).map(({ id }) => id), ["a", "b"]);
  assert.equal(calls.length, 5);
});

test("a previous session's late pages cannot repopulate the new session's cache", async () => {
  const entered = deferred();
  const later = deferred();
  respond = (url) => {
    if (url.searchParams.has("after")) { entered.resolve(); return later.promise; }
    return { products: [{ id: "old" }], hasMore: true, nextCursor: "cursor-1" };
  };
  const old = getProducts("shop-a");
  await entered.promise;
  invalidateReadCache("");
  respond = () => ({ products: [{ id: "current" }], hasMore: false });
  await getProducts("shop-a");
  later.resolve({ products: [{ id: "old-later" }], hasMore: false });
  await old;
  assert.deepEqual((await getProducts("shop-a")).map(({ id }) => id), ["current"]);
  assert.equal(calls.length, 3);
});

test("unchanged inventory remains cached past the old expiry while each use validates the revision", async (t) => {
  let now = 1000;
  t.mock.method(Date, "now", () => now);
  respond = () => ({ products: [], hasMore: false });
  await getProducts("shop-a");
  now += 59000;
  await getProducts("shop-a");
  assert.equal(calls.length, 1);
  now += 1001;
  await getProducts("shop-a");
  now += 24 * 60 * 60 * 1000;
  await getProducts("shop-a");
  assert.equal(calls.length, 1);
  assert.equal(versionCalls.length, 4);
});

test("a revision changed by another client reloads data and discards previous revision caches", async () => {
  respond = () => ({ products: [{ id: "a", name: "Original" }], hasMore: false });
  await getProducts("shop-a", { status: "active" });
  await getProducts("shop-a", { categoryId: "cat-a" });
  respondVersion = () => ({ revision: "revision-2" });
  respond = () => ({ products: [{ id: "a", name: "Changed by mobile" }], hasMore: false });
  assert.equal((await getProducts("shop-a", { status: "active" }))[0].name, "Changed by mobile");
  assert.equal((await getProducts("shop-a", { categoryId: "cat-a" }))[0].name, "Changed by mobile");
  assert.equal(calls.length, 4);
});

test("a failed permission/revision check never serves previously cached inventory", async () => {
  respond = () => ({ products: [{ id: "a", name: "Private" }], hasMore: false });
  await getProducts("shop-a");
  respondVersion = () => { throw new Error("Access revoked"); };
  await assert.rejects(getProducts("shop-a"), /Access revoked/);
  assert.equal(calls.length, 1);
});

test("logout during a revision check cannot recreate old-session data after the cache was cleared", async () => {
  const pending = deferred();
  respondVersion = () => pending.promise;
  const load = getProducts("shop-a");
  invalidateReadCache("");
  pending.resolve({ revision: "old-session" });
  await assert.rejects(load, { name: "AbortError" });
  assert.equal(calls.length, 0);
});

test("invalid revision responses fail instead of creating a permanently reusable unknown cache", async () => {
  respondVersion = () => ({});
  await assert.rejects(getProducts("shop-a"), /freshness could not be verified/);
  assert.equal(calls.length, 0);
});

// Every mutation affecting product summaries must invalidate all of this business's filter caches.
for (const [name, mutate] of [
  ["product edits", () => updateProduct("shop-a", "a", { name: "Updated product" })],
  ["status changes", () => updateProductStatus("shop-a", "a", "archived")],
  ["variant image uploads", () => uploadVariantImage("shop-a", "a", "variant-a", new Blob(["synthetic image"]))],
]) {
  test(`${name} discard stale cached product lists after success`, async () => {
    respond = (_url, options) => options?.method
      ? { product: { id: "a", name: "Updated product" } }
      : { products: [{ id: "a", name: "Original product" }], hasMore: false };
    await getProducts("shop-a", { categoryId: "cat-a" });
    await getProducts("shop-a", { status: "active" });
    await getProducts("shop-b");
    await mutate();
    respond = () => ({ products: [{ id: "a", name: "Updated product" }], hasMore: false });
    assert.equal((await getProducts("shop-a", { categoryId: "cat-a" }))[0].name, "Updated product");
    assert.equal((await getProducts("shop-a", { status: "active" }))[0].name, "Updated product");
    assert.equal((await getProducts("shop-b"))[0].name, "Original product");
    assert.equal(calls.length, 6);
  });
}

test("failed edits preserve the existing cache without triggering unnecessary reloads", async () => {
  respond = (_url, options) => {
    if (options?.method === "PATCH") throw new Error("Synthetic edit failure");
    return { products: [{ id: "a", name: "Original product" }], hasMore: false };
  };
  await getProducts("shop-a");
  await assert.rejects(updateProduct("shop-a", "a", { name: "Rejected edit" }), /Synthetic edit failure/);
  assert.equal((await getProducts("shop-a"))[0].name, "Original product");
  assert.equal(calls.length, 2);
});

test("a late pre-edit page cannot repopulate the cache after a successful edit", async () => {
  const entered = deferred();
  const later = deferred();
  respond = (url, options) => {
    if (options?.method === "PATCH") return { product: { id: "a", name: "Updated" } };
    if (url.searchParams.has("after")) { entered.resolve(); return later.promise; }
    return { products: [{ id: "a", name: "Old" }], hasMore: true, nextCursor: "cursor-1" };
  };
  const oldLoad = getProducts("shop-a");
  await entered.promise;
  await updateProduct("shop-a", "a", { name: "Updated" });
  respond = () => ({ products: [{ id: "a", name: "Updated" }], hasMore: false });
  const freshLoad = getProducts("shop-a");
  later.resolve({ products: [{ id: "older-page", name: "Old" }], hasMore: false });
  await Promise.all([oldLoad, freshLoad]);
  assert.deepEqual((await getProducts("shop-a")).map(({ name }) => name), ["Updated"]);
  assert.equal(calls.length, 4);
});

test("generating an unsaved AI description does not invalidate unchanged inventory", async () => {
  respond = (_url, options) => options?.method === "POST"
    ? { productInfo: { description: "Synthetic generated description" } }
    : { products: [{ id: "a", name: "Original" }], hasMore: false };
  await getProducts("shop-a");
  await generateProductDescription("shop-a", { name: "Draft product" });
  await getProducts("shop-a");
  assert.equal(calls.length, 2);
});
