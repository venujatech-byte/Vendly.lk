import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { beforeEach, test } from "node:test";
import { setImmediate } from "node:timers";

// Exercise the real hook offline, preserving its ref across simulated renders.
let reference;
let renew;
let renewals;
let saved;
globalThis.__vendlyChatRecovery = {
  useRef: (initial) => (reference ??= { current: initial }),
  resumePublicChatSession: (id) => { renewals.push(id); return renew(id); },
};
const moduleUrl = new URL("../hooks/useChatSessionRecovery.js", import.meta.url);
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (context.parentURL === moduleUrl.href && ["react", "../services/publicService"].includes(specifier)) {
      return { url: `chat-recovery-test:${specifier}`, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url.startsWith("chat-recovery-test:")) {
      const name = url.endsWith("react") ? "useRef" : "resumePublicChatSession";
      return { format: "module", shortCircuit: true, source: `export const ${name} = globalThis.__vendlyChatRecovery.${name};` };
    }
    return nextLoad(url, context);
  },
});
const { useChatSessionRecovery } = await import(moduleUrl.href);
hook.deregister();

const session = { sessionId: "chat-a", sessionToken: "synthetic-old" };
const renewed = { ...session, sessionToken: "synthetic-new" };
const user = { uid: "customer-a", isAnonymous: false };
const expiry = () => Object.assign(new Error("Synthetic expired chat"), { code: "chat_session_expired" });
const render = (currentSession = session, currentUser = user, key = "store-a") =>
  useChatSessionRecovery(currentSession, currentUser, key, (value) => saved.push(value));

beforeEach(() => {
  reference = undefined;
  renewals = [];
  saved = [];
  renew = async () => renewed;
});

test("a working session makes one request without renewal", async () => {
  let calls = 0;
  const response = await render()(session, async (active) => {
    calls += 1;
    assert.equal(active, session);
    return "success";
  });
  assert.equal(response, "success");
  assert.equal(calls, 1);
  assert.deepEqual(renewals, []);
  assert.deepEqual(saved, []);
});

test("expiry renews the same chat and retries once with its new credentials", async () => {
  const tokens = [];
  const response = await render()(session, async (active) => {
    tokens.push(active.sessionToken);
    if (active === session) throw expiry();
    return "sent";
  });
  assert.equal(response, "sent");
  assert.deepEqual(tokens, [session.sessionToken, renewed.sessionToken]);
  assert.deepEqual(renewals, [session.sessionId]);
  assert.deepEqual(saved, [renewed]);
});

test("simultaneous claim and message failures share one renewal and one saved token", async () => {
  let finish;
  renew = () => new Promise((resolve) => { finish = resolve; });
  const run = render();
  const request = async (active) => { if (active === session) throw expiry(); return active.sessionToken; };
  const first = run(session, request);
  const second = run(session, request);
  await new Promise(setImmediate);
  assert.equal(renewals.length, 1);
  finish(renewed);
  assert.deepEqual(await Promise.all([first, second]), [renewed.sessionToken, renewed.sessionToken]);
  render(renewed);
  assert.equal(await run(session, request), renewed.sessionToken);
  assert.deepEqual(renewals, [session.sessionId]);
  assert.deepEqual(saved, [renewed]);
});

test("a second expiry is returned without looping or replaying again", async () => {
  let attempts = 0;
  await assert.rejects(render()(session, async () => { attempts += 1; throw expiry(); }), { code: "chat_session_expired" });
  assert.equal(attempts, 2);
  assert.equal(renewals.length, 1);
});

for (const currentUser of [null, { uid: "guest-a", isAnonymous: true }]) {
  test(`expiry cannot renew for ${currentUser ? "an anonymous account" : "a signed-out browser"}`, async () => {
    const error = expiry();
    await assert.rejects(render(session, currentUser)(session, async () => { throw error; }), (actual) => actual === error);
    assert.deepEqual(renewals, []);
    assert.deepEqual(saved, []);
  });
}

for (const code of ["invalid_chat_session", "forbidden", "api_request_failed"]) {
  test(`${code} is never retried because it is not explicit expiry`, async () => {
    let attempts = 0;
    const error = Object.assign(new Error("Synthetic failure"), { code });
    await assert.rejects(render()(session, async () => { attempts += 1; throw error; }), (actual) => actual === error);
    assert.equal(attempts, 1);
    assert.deepEqual(renewals, []);
  });
}

for (const change of ["account", "route", "conversation", "manual-token", "logout-and-return"]) {
  test(`a pending renewal cannot replace the session after a ${change} change`, async () => {
    let finish;
    renew = () => new Promise((resolve) => { finish = resolve; });
    let attempts = 0;
    const pending = render()(session, async () => { attempts += 1; throw expiry(); });
    await new Promise(setImmediate);
    if (change === "account") render(session, { uid: "customer-b", isAnonymous: false });
    if (change === "route") render(session, user, "store-b");
    if (change === "conversation") render({ ...session, sessionId: "chat-b" });
    if (change === "manual-token") render({ ...session, sessionToken: "synthetic-manual" });
    if (change === "logout-and-return") { render(session, null); render(); }
    finish(renewed);
    await assert.rejects(pending, { code: "chat_session_expired" });
    assert.equal(attempts, 1);
    assert.deepEqual(saved, []);
  });
}

test("server ownership denial is preserved and a later renewal failure is not cached", async () => {
  const error = Object.assign(new Error("Synthetic ownership denial"), { code: "forbidden" });
  renew = async () => { throw error; };
  const run = render();
  const request = async (active) => { if (active === session) throw expiry(); return "sent"; };
  await assert.rejects(run(session, request), (actual) => actual === error);
  assert.deepEqual(saved, []);
  renew = async () => renewed;
  assert.equal(await run(session, request), "sent");
  assert.equal(renewals.length, 2);
});
