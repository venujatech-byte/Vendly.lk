import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { registerHooks } from "node:module";
import { beforeEach, test } from "node:test";

// Execute the actual deletion flow with offline SDK/network boundaries.
const auth = { currentUser: null };
let calls;
let respond;
let refresh;
let reauthenticate;
const mocks = {
  auth, googleProvider: {},
  EmailAuthProvider: { credential: (email, password) => ({ email, password }) },
  reauthenticateWithCredential: async () => { calls.push("reauthenticate"); return reauthenticate(); },
  reauthenticateWithPopup: async () => { calls.push("popup"); return reauthenticate(); },
  getIdToken: async (user, force) => { calls.push(["token", user.uid, force]); return refresh(); },
  deleteUser: async () => { throw new Error("Client-side Auth deletion must not run"); },
  signOut: async () => { calls.push("signOut"); auth.currentUser = null; },
  apiRequest: async (path, options) => { calls.push(["request", path, options]); return respond(); },
};
globalThis.__vendlyDeletionMocks = mocks;
const moduleUrl = new URL("./authService.js", import.meta.url);
const source = await readFile(moduleUrl, "utf8");
const sdkExports = source.match(/import\s*\{([^}]+)\}\s*from\s*["']firebase\/auth["']/)[1]
  .split(",").map((name) => name.trim()).filter(Boolean);
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (context.parentURL === moduleUrl.href) {
      const boundary = {
        "firebase/auth": "sdk", "../firebase/firebase": "config", "./apiClient": "api",
      }[specifier];
      if (boundary) return { url: `account-deletion-test:${boundary}`, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url.startsWith("account-deletion-test:")) {
      const names = url.endsWith("sdk") ? sdkExports : url.endsWith("config") ? ["auth", "googleProvider"] : ["apiRequest"];
      return { format: "module", shortCircuit: true, source: names.map((name) =>
        `export const ${name} = globalThis.__vendlyDeletionMocks[${JSON.stringify(name)}];`
      ).join("\n") };
    }
    return nextLoad(url, context);
  },
});
const { deleteCurrentUserAccount } = await import(moduleUrl.href);
hook.deregister();

beforeEach(() => {
  auth.currentUser = { uid: "customer-a", email: "customer@example.test", providerData: [{ providerId: "password" }] };
  calls = [];
  respond = async () => ({ deleted: true });
  refresh = async () => "synthetic-fresh-token";
  reauthenticate = async () => {};
});

test("deletion reauthenticates, refreshes the exact account token, then trusts backend completion", async () => {
  await deleteCurrentUserAccount("synthetic-password");
  assert.deepEqual(calls, ["reauthenticate", ["token", "customer-a", true], ["request", "/me", {
    method: "DELETE", headers: { Authorization: "Bearer synthetic-fresh-token" }, requiresAuthentication: false,
  }], "signOut"]);
});

for (const code of ["business_owner_deletion_blocked", "account_deletion_failed", "recent_login_required"]) {
  test(`${code} stops deletion and preserves the signed-in account`, async () => {
    const failure = Object.assign(new Error("Synthetic backend rejection"), { code });
    respond = async () => { throw failure; };
    await assert.rejects(deleteCurrentUserAccount("synthetic-password"), (error) => error === failure);
    assert.equal(auth.currentUser.uid, "customer-a");
    assert.ok(!calls.includes("signOut"));
  });
}

test("failed reauthentication never calls cleanup or signs out", async () => {
  reauthenticate = async () => { throw new Error("Synthetic wrong password"); };
  await assert.rejects(deleteCurrentUserAccount("synthetic-password"), /Synthetic wrong password/);
  assert.deepEqual(calls, ["reauthenticate"]);
});

test("a failed token refresh never calls cleanup", async () => {
  refresh = async () => { throw new Error("Synthetic token failure"); };
  await assert.rejects(deleteCurrentUserAccount("synthetic-password"), /Synthetic token failure/);
  assert.equal(calls.length, 2);
});

test("a signed-out browser cannot request deletion", async () => {
  auth.currentUser = null;
  await assert.rejects(deleteCurrentUserAccount(), /Please sign in again/);
  assert.deepEqual(calls, []);
});

test("switching accounts before cleanup cannot delete the newly signed-in account", async () => {
  refresh = async () => { auth.currentUser = { uid: "customer-b" }; return "synthetic-old-account-token"; };
  await assert.rejects(deleteCurrentUserAccount("synthetic-password"), /account changed/);
  assert.equal(calls.length, 2);
  assert.equal(auth.currentUser.uid, "customer-b");
});

test("switching accounts during cleanup does not sign out the new account", async () => {
  respond = async () => { auth.currentUser = { uid: "customer-b" }; return { deleted: true }; };
  await deleteCurrentUserAccount("synthetic-password");
  assert.equal(auth.currentUser.uid, "customer-b");
  assert.ok(!calls.includes("signOut"));
});

test("Google accounts retain their existing popup reauthentication path", async () => {
  auth.currentUser.providerData = [{ providerId: "google.com" }];
  await deleteCurrentUserAccount();
  assert.equal(calls[0], "popup");
  assert.equal(calls.at(-1), "signOut");
});
