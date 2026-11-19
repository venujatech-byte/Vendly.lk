import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { beforeEach, test } from "node:test";

import { invalidateReadCache } from "./readCache.js";

// Use the actual loader, cache and inventory mapping; replace only its authenticated HTTP boundary.
let respond;
const calls = [];
globalThis.__vendlyProductPageRequest = async (path, options) => {
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
const { getProducts, createProduct } = await import(moduleUrl.href);
hook.deregister();

function deferred() {
  let resolve;
  const promise = new Promise((accept) => { resolve = accept; });
  return { promise, resolve };
}

beforeEach(() => { invalidateReadCache(""); calls.length = 0; });

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

test("the existing 60-second product cache TTL is retained", async (t) => {
  let now = 1000;
  t.mock.method(Date, "now", () => now);
  respond = () => ({ products: [], hasMore: false });
  await getProducts("shop-a");
  now += 59000;
  await getProducts("shop-a");
  assert.equal(calls.length, 1);
  now += 1001;
  await getProducts("shop-a");
  assert.equal(calls.length, 2);
});
