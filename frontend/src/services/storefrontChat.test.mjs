import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { test } from "node:test";

import { chatSessionStorageKey, chatCartFromSummary } from "./storefrontChat.js";

// Product links share registered-customer storage only within the same verified store/account.
test("registered customers reuse one store key across product links", () => {
  const user = { uid: "customer-a", isAnonymous: false };
  const store = chatSessionStorageKey("store-a", "", user, "business-a");
  assert.equal(store, chatSessionStorageKey(undefined, "product-a", user, "business-a"));
  assert.equal(store, chatSessionStorageKey("store-a", "product-b", user, "business-a"));
  assert.notEqual(store, chatSessionStorageKey("store-b", "product-a", user, "business-b"));
  assert.notEqual(store, chatSessionStorageKey("store-a", "", { uid: "customer-b" }, "business-a"));
});

test("guest and legacy keys retain their existing identities", () => {
  const guest = { uid: "guest-a", isAnonymous: true };
  assert.equal(chatSessionStorageKey("store-a", "product-a", guest, "business-a"), "vendly-chat-session:product:product-a:guest-a");
  assert.equal(chatSessionStorageKey("store-a", "", null, "business-a"), "vendly-chat-session:store:store-a:guest");
  assert.equal(chatSessionStorageKey("store-a", "product-a", { uid: "customer-a" }), "vendly-chat-session:product:product-a:customer-a");
});

test("restored carts retain prices, images and the existing stock fallback behavior", () => {
  const summary = [{ variantId: "variant-a", productName: "Synthetic item", unitPriceMinor: 1250, quantity: 2 }];
  const current = [{ variantId: "variant-a", imageUrl: "synthetic-image", availableStock: 6 }];
  const products = [{ variants: [{ id: "variant-a", availableStock: 9 }] }];
  const restored = chatCartFromSummary(summary, current, products)[0];
  assert.equal(restored.sellingPriceMinor, 1250);
  assert.equal(restored.quantity, 2);
  assert.equal(restored.imageUrl, "synthetic-image");
  assert.equal(restored.availableStock, 9);
  assert.equal(chatCartFromSummary(summary, current, [])[0].availableStock, 6);
  assert.equal(chatCartFromSummary(summary, [], [])[0].availableStock, 2);
  assert.deepEqual(chatCartFromSummary([], current, products), []);
});

// Exercise the real public API helpers while replacing only network transport.
const calls = [];
globalThis.__vendlySharedChatRequest = async (path, options) => { calls.push({ path, options }); return {}; };
const moduleUrl = new URL("./publicService.js", import.meta.url);
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (context.parentURL === moduleUrl.href && specifier === "./apiClient") {
      return { url: "shared-chat-test:api", shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url === "shared-chat-test:api") return {
      format: "module", shortCircuit: true, source: "export const apiRequest = globalThis.__vendlySharedChatRequest;",
    };
    return nextLoad(url, context);
  },
});
const { getPublicChatMessages, sendPublicChatImage } = await import(moduleUrl.href);
hook.deregister();

test("history and uploads send available Firebase proof without requiring guest sign-in", async () => {
  await getPublicChatMessages("chat-a", "synthetic-token", { before: "older", limit: 10 });
  await sendPublicChatImage("chat-a", "synthetic-token", "synthetic-image", "Synthetic caption");
  for (const { options } of calls) {
    assert.equal(options.requiresAuthentication, "optional");
    assert.equal(options.headers["X-Chat-Session-Token"], "synthetic-token");
  }
  assert.match(calls[0].path, /before=older/);
  assert.deepEqual(calls[1].options.body, { image: "synthetic-image", caption: "Synthetic caption" });
});
