import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { registerHooks } from "node:module";
import { test } from "node:test";

// Stub Firebase at the module boundary; exercise the actual registration implementation offline.
const calls = [];
let linkError = null;
let loginEmailVerified = false;
const auth = { currentUser: null };
globalThis.__vendlyRegistrationMocks = {
  auth,
  googleProvider: {},
  EmailAuthProvider: { credential: (email, password) => ({ email, password }) },
  createUserWithEmailAndPassword: async (...args) => {
    calls.push(["create", ...args]);
    return { user: { uid: "new-account" } };
  },
  linkWithCredential: async (user, credential) => {
    calls.push(["link", user.uid, credential]);
    if (linkError) throw linkError;
    return { user: { uid: user.uid, isAnonymous: false } };
  },
  updateProfile: async (...args) => calls.push(["profile", ...args]),
  sendEmailVerification: async (...args) => calls.push(["verify", ...args]),
  signOut: async () => { calls.push(["signOut"]); auth.currentUser = null; },
  signInWithEmailAndPassword: async () => {
    calls.push(["signIn"]);
    auth.currentUser = { uid: "existing-account", emailVerified: loginEmailVerified };
    return { user: auth.currentUser };
  },
  reload: async () => calls.push(["reload"]),
  updateCurrentUser: async (_auth, user) => { calls.push(["restore"]); auth.currentUser = user; },
  apiRequest: async (...args) => calls.push(["request", ...args]),
};
const authUrl = new URL("./authService.js", import.meta.url);
const publicUrl = new URL("./publicService.js", import.meta.url);
const source = await readFile(authUrl, "utf8");
const sdkExports = source.match(/import\s*\{([^}]+)\}\s*from\s*["']firebase\/auth["']/)[1]
  .split(",").map((name) => name.trim()).filter(Boolean);
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (context.parentURL === authUrl.href || context.parentURL === publicUrl.href) {
      if (specifier === "firebase/auth") return { url: "registration-test:sdk", shortCircuit: true };
      if (specifier === "../firebase/firebase") return { url: "registration-test:config", shortCircuit: true };
      if (specifier === "./apiClient") return { url: "registration-test:api", shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url.startsWith("registration-test:")) {
      const names = url.endsWith("sdk") ? sdkExports : url.endsWith("config") ? ["auth", "googleProvider"] : ["apiRequest"];
      return {
        format: "module", shortCircuit: true,
        source: names.map((name) => `export const ${name} = globalThis.__vendlyRegistrationMocks[${JSON.stringify(name)}];`).join("\n"),
      };
    }
    return nextLoad(url, context);
  },
});
const { registerWithEmail, loginWithEmail } = await import(authUrl.href);
const { claimGuestCustomerOrders } = await import(publicUrl.href);
hook.deregister();

// Upgrading a guest must retain the UID that already owns its orders.
test("customer registration upgrades an anonymous identity in place", async () => {
  calls.length = 0;
  auth.currentUser = { uid: "guest-account", isAnonymous: true };
  const user = await registerWithEmail("Customer", "customer@example.test", "synthetic-password", { linkGuestAccount: true });
  assert.equal(user.uid, "guest-account");
  assert.deepEqual(calls.map(([name]) => name), ["link", "profile", "verify", "signOut"]);
});

// The existing seller registration path must continue creating a new account.
test("default registration retains existing behavior", async () => {
  calls.length = 0;
  auth.currentUser = { uid: "guest-account", isAnonymous: true };
  const user = await registerWithEmail("Seller", "seller@example.test", "synthetic-password");
  assert.equal(user.uid, "new-account");
  assert.deepEqual(calls.map(([name]) => name), ["create", "profile", "verify", "signOut"]);
});

// Failed linking must not silently create another UID and disconnect the existing order history.
test("failed guest upgrade preserves the original identity", async () => {
  calls.length = 0;
  auth.currentUser = { uid: "guest-account", isAnonymous: true };
  linkError = new Error("Synthetic credential conflict");
  await assert.rejects(registerWithEmail("Customer", "customer@example.test", "synthetic-password", { linkGuestAccount: true }), /credential conflict/);
  assert.deepEqual(calls.map(([name]) => name), ["link"]);
  assert.equal(auth.currentUser.uid, "guest-account");
  linkError = null;
});


// A concurrent sign-in in another tab must not change which account receives the guest orders.
test("history linking sends both explicit ownership proofs", async () => {
  calls.length = 0;
  await claimGuestCustomerOrders("store", "synthetic-guest-token", "synthetic-destination-token");
  assert.deepEqual(calls, [["request", "/public/stores/store/customer/claim-guest-orders", {
    method: "POST",
    headers: { Authorization: "Bearer synthetic-destination-token" },
    body: { guestIdToken: "synthetic-guest-token" },
    requiresAuthentication: false,
  }]]);
});


// An unverified destination account must not strand orders under a discarded anonymous login.
test("failed customer sign-in restores the guest identity", async () => {
  calls.length = 0;
  auth.currentUser = { uid: "guest-account", isAnonymous: true };
  loginEmailVerified = false;
  await assert.rejects(loginWithEmail("customer@example.test", "synthetic-password", { preserveGuestOnFailure: true }), /not been verified/);
  assert.equal(auth.currentUser.uid, "guest-account");
  assert.deepEqual(calls.map(([name]) => name), ["signIn", "reload", "signOut", "restore"]);
});

// Seller sign-in retains its existing rejection and sign-out behavior for unverified accounts.
test("default sign-in does not restore an earlier guest", async () => {
  calls.length = 0;
  auth.currentUser = { uid: "guest-account", isAnonymous: true };
  await assert.rejects(loginWithEmail("seller@example.test", "synthetic-password"), /not been verified/);
  assert.equal(auth.currentUser, null);
  assert.deepEqual(calls.map(([name]) => name), ["signIn", "reload", "signOut"]);
});

// Successful customer sign-in returns the verified destination used by the history-link request.
test("verified customer sign-in keeps the signed-in account", async () => {
  calls.length = 0;
  auth.currentUser = { uid: "guest-account", isAnonymous: true };
  loginEmailVerified = true;
  const user = await loginWithEmail("customer@example.test", "synthetic-password", { preserveGuestOnFailure: true });
  assert.equal(user.uid, "existing-account");
  assert.deepEqual(calls.map(([name]) => name), ["signIn", "reload"]);
});
