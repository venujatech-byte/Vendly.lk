import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { registerHooks } from "node:module";
import { afterEach, beforeEach, test } from "node:test";
import { transformWithOxc } from "vite";

import { cachedRequest, invalidateReadCache } from "./readCache.js";

// Execute the actual provider with offline Firebase/services and hook state controlled by the test.
let listener;
let listenerError;
let cleanup;
let states;
let accountLoader;
let profileLoader;
let businessWrites;
let provider;
const auth = { currentUser: null };
const mocks = {
  auth,
  useEffect: (effect) => { cleanup = effect(); },
  useRef: (value) => ({ current: value }),
  useState: (initial) => {
    const index = states.length;
    states.push(initial);
    return [initial, (value) => { states[index] = value; }];
  },
  onAuthStateChanged: (_auth, success, error) => {
    listener = success;
    listenerError = error;
    return () => {};
  },
  getCurrentAccount: () => accountLoader(),
  getSellerProfile: (user) => profileLoader(user),
  clearPendingSellerProfile: () => {},
  createBusiness: () => { businessWrites += 1; },
};
globalThis.__vendlyCacheAuthMocks = mocks;
const providerUrl = new URL("../context/AuthContext.jsx", import.meta.url);
const transformed = await transformWithOxc(await readFile(providerUrl, "utf8"), providerUrl.pathname);
const modules = {
  react: ["useEffect", "useRef", "useState"],
  "firebase/auth": ["onAuthStateChanged"],
  "../firebase/firebase": ["auth"],
  "../services/accountService": ["getCurrentAccount"],
  "../services/businessService": ["createBusiness"],
  "../services/sellerService": ["clearPendingSellerProfile", "getSellerProfile"],
};
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (context.parentURL === providerUrl.href) {
      if (modules[specifier]) return { url: `cache-auth-test:${specifier}`, shortCircuit: true };
      if (specifier === "../services/readCache") return { url: new URL("./readCache.js", import.meta.url).href, shortCircuit: true };
      if (specifier === "./authContextValue") return { url: new URL("../context/authContextValue.js", import.meta.url).href, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url === providerUrl.href) return { format: "module", source: transformed.code, shortCircuit: true };
    if (url.startsWith("cache-auth-test:")) {
      return {
        format: "module", shortCircuit: true,
        source: modules[url.slice("cache-auth-test:".length)].map((name) =>
          `export const ${name} = globalThis.__vendlyCacheAuthMocks[${JSON.stringify(name)}];`
        ).join("\n"),
      };
    }
    return nextLoad(url, context);
  },
});
const { AuthProvider } = await import(providerUrl.href);
hook.deregister();

// Deferred responses reproduce a previous account finishing after the new session has loaded.
function deferred() {
  let resolve;
  let reject;
  const promise = new Promise((accept, fail) => { resolve = accept; reject = fail; });
  return { promise, resolve, reject };
}

function changeUser(user) {
  auth.currentUser = user;
  return listener(user);
}

beforeEach(() => {
  invalidateReadCache("");
  states = [];
  auth.currentUser = null;
  accountLoader = async () => ({ business: { id: "shop" }, membership: { role: "staff" } });
  profileLoader = async () => null;
  businessWrites = 0;
  provider = AuthProvider({ children: null });
});

afterEach(() => cleanup());

test("an owner-to-staff switch clears completed and pending cached reads", async () => {
  await changeUser({ uid: "owner" });
  await cachedRequest("customers:shop:", () => "owner customers");
  const old = deferred();
  const request = cachedRequest("products:shop:", () => old.promise);
  await changeUser({ uid: "staff" });
  assert.equal(await cachedRequest("customers:shop:", () => "staff customers"), "staff customers");
  assert.equal(await cachedRequest("products:shop:", () => "staff products"), "staff products");
  old.resolve("owner products");
  await request;
  assert.equal(await cachedRequest("products:shop:", () => assert.fail("old account repopulated cache")), "staff products");
});

test("sign-out and unverified sign-in discard the previous account cache", async () => {
  await cachedRequest("customers:shop:", () => "owner");
  await changeUser(null);
  assert.equal(await cachedRequest("customers:shop:", () => "after logout"), "after logout");
  await changeUser({ uid: "unverified", providerData: [{ providerId: "password" }], emailVerified: false });
  assert.equal(await cachedRequest("customers:shop:", () => "after unverified login"), "after unverified login");
  assert.equal(states[0], null);
});

test("authentication errors clear the previous account cache", async (t) => {
  t.mock.method(console, "error", () => {});
  await cachedRequest("customers:shop:", () => "owner");
  listenerError(new Error("synthetic auth failure"));
  assert.equal(await cachedRequest("customers:shop:", () => "after failure"), "after failure");
});

test("a previous account response cannot replace the new account profile", async () => {
  const old = deferred();
  accountLoader = () => old.promise;
  const ownerLoad = changeUser({ uid: "owner" });
  await Promise.resolve();
  const staffAccount = { business: { id: "shop" }, membership: { role: "staff" } };
  accountLoader = async () => staffAccount;
  await changeUser({ uid: "staff" });
  old.resolve({ business: { id: "shop" }, membership: { role: "owner" } });
  await ownerLoad;
  assert.equal(states[0].uid, "staff");
  assert.equal(states[2], staffAccount);
});

test("a late previous-account failure cannot clear the current account", async () => {
  const old = deferred();
  accountLoader = () => old.promise;
  const ownerLoad = changeUser({ uid: "owner" });
  await Promise.resolve();
  const staffAccount = { business: { id: "shop" }, membership: { role: "staff" } };
  accountLoader = async () => staffAccount;
  await changeUser({ uid: "staff" });
  old.reject(new Error("previous account failed"));
  await ownerLoad;
  assert.equal(states[2], staffAccount);
  assert.equal(states[3], null);
});

test("a delayed legacy profile cannot trigger onboarding after sign-out", async () => {
  const old = deferred();
  profileLoader = () => old.promise;
  const ownerLoad = changeUser({ uid: "owner" });
  await changeUser(null);
  old.resolve({ businessName: "Previous business" });
  await ownerLoad;
  assert.equal(businessWrites, 0);
  assert.equal(states[0], null);
  assert.equal(states[2], null);
});

test("a current profile failure cannot leave the prior business attached", async (t) => {
  t.mock.method(console, "error", () => {});
  await changeUser({ uid: "owner" });
  profileLoader = async () => { throw new Error("new profile failed"); };
  await changeUser({ uid: "staff" });
  assert.equal(states[0].uid, "staff");
  assert.equal(states[1], null);
  assert.equal(states[2], null);
});

test("legacy onboarding still creates the business for the current signed-in account", async () => {
  profileLoader = async () => ({ ownerName: "Owner", businessName: "Shop" });
  const currentAccount = { business: { id: "shop" }, membership: { role: "owner" } };
  let calls = 0;
  accountLoader = async () => ++calls === 1 ? { profile: {}, business: null } : currentAccount;
  await changeUser({ uid: "owner" });
  assert.equal(businessWrites, 1);
  assert.equal(states[2], currentAccount);
  assert.equal(states[5], false);
});

test("late account completion cannot stop the loading state of a newer session", async () => {
  const owner = deferred();
  const staff = deferred();
  accountLoader = () => owner.promise;
  const ownerLoad = changeUser({ uid: "owner" });
  await Promise.resolve();
  accountLoader = () => staff.promise;
  const staffLoad = changeUser({ uid: "staff" });
  await Promise.resolve();
  owner.resolve({ business: { id: "shop" }, membership: { role: "owner" } });
  await ownerLoad;
  assert.equal(states[5], true);
  assert.equal(states[2], null);
  staff.resolve({ business: { id: "shop" }, membership: { role: "staff" } });
  await staffLoad;
  assert.equal(states[5], false);
});

test("a membership refresh clears reads cached under the previous permissions", async () => {
  await changeUser({ uid: "staff" });
  await cachedRequest("customers:shop:", () => "previous permissions");
  await provider.props.value.refreshSellerProfile();
  assert.equal(await cachedRequest("customers:shop:", () => "current permissions"), "current permissions");
});
