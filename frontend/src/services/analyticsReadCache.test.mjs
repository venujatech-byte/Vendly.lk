import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { registerHooks } from "node:module";
import { beforeEach, test } from "node:test";

import { invalidateReadCache } from "./readCache.js";

// Run the existing analytics cache/save client offline against a small HTTP state model.
let version;
let target;
let rejectSave;
let sourceRevision;
let units;
let versionReply;
let overviewReply;
const versionCalls = [];
const reportCalls = [];
globalThis.__vendlyAnalyticsCacheRequest = async (path, options) => {
  const url = new URL(path, "https://synthetic.example");
  if (url.pathname.endsWith("/analytics/version")) {
    assert.equal(url.searchParams.get("includeRevision"), "1");
    versionCalls.push(path);
    return versionReply();
  }
  if (path.endsWith("/analytics/monthly-target")) {
    assert.equal(options.method, "PATCH");
    if (rejectSave) throw new Error("Target save rejected");
    target = options.body.monthlyTargetMinor;
    version += 1;
    return { monthlyTargetMinor: target };
  }
  assert.ok(path.endsWith("/analytics/overview"));
  reportCalls.push(path);
  return overviewReply();
};
const moduleUrl = new URL("./analyticsService.js", import.meta.url);
const hook = registerHooks({
  resolve(specifier, context, nextResolve) {
    if (context.parentURL === moduleUrl.href) {
      if (specifier === "./apiClient") return { url: "analytics-cache-test:api", shortCircuit: true };
      if (specifier === "./readCache") return { url: new URL("./readCache.js", import.meta.url).href, shortCircuit: true };
    }
    return nextResolve(specifier, context);
  },
  load(url, context, nextLoad) {
    if (url === "analytics-cache-test:api") return {
      format: "module", shortCircuit: true,
      source: "export const apiRequest = globalThis.__vendlyAnalyticsCacheRequest; export const apiFileRequest = () => { throw new Error('Unexpected file request'); };",
    };
    return nextLoad(url, context);
  },
});
const { getAnalyticsOverview, saveMonthlyRevenueTarget } = await import(moduleUrl.href);
hook.deregister();

beforeEach(() => {
  invalidateReadCache("");
  version = 3;
  target = 10000;
  rejectSave = false;
  reportCalls.length = 0;
  versionCalls.length = 0;
  sourceRevision = "source-1";
  units = 10;
  versionReply = () => ({ analyticsVersion: version, analyticsRevision: createHash("sha256").update(`${version}:${sourceRevision}`).digest("hex") });
  overviewReply = () => ({ analytics: { salesForecast: { summary: { monthlyTargetMinor: target, activeTargetMinor: target } }, inventory: { totalUnits: units } } });
});

test("the existing save-then-refresh flow replaces the old target before the cache TTL expires", async () => {
  const original = await getAnalyticsOverview("shop-a");
  assert.equal(await getAnalyticsOverview("shop-a"), original);
  await saveMonthlyRevenueTarget("shop-a", 500000);
  const updated = await getAnalyticsOverview("shop-a");
  assert.equal(updated.salesForecast.summary.monthlyTargetMinor, 500000);
  assert.equal(updated.salesForecast.summary.activeTargetMinor, 500000);
  assert.notEqual(updated, original);
  assert.equal(await getAnalyticsOverview("shop-a"), updated);
  assert.equal(reportCalls.length, 2);
});

test("a failed target save leaves the original report cache reusable", async () => {
  const original = await getAnalyticsOverview("shop-a");
  rejectSave = true;
  await assert.rejects(saveMonthlyRevenueTarget("shop-a", 500000), /Target save rejected/);
  assert.equal(await getAnalyticsOverview("shop-a"), original);
  assert.equal(original.salesForecast.summary.monthlyTargetMinor, 10000);
  assert.equal(reportCalls.length, 1);
});

test("another app changing the shared target/version refreshes the next web report request", async () => {
  await getAnalyticsOverview("shop-a");
  target = 750000;
  version += 1;
  assert.equal((await getAnalyticsOverview("shop-a")).salesForecast.summary.monthlyTargetMinor, 750000);
  assert.equal(reportCalls.length, 2);
});


// Shared source markers invalidate analytics even when a service writer bypasses the older route counter.
test("source changes refresh analytics without an increment to the legacy counter", async () => {
  await getAnalyticsOverview("shop-a");
  sourceRevision = "mobile-stock-change";
  units = 8;
  assert.equal((await getAnalyticsOverview("shop-a")).inventory.totalUnits, 8);
  assert.equal(version, 3);
  assert.equal(reportCalls.length, 2);
});

test("unchanged sources reuse the report while retaining its existing thirty-minute expiry", async (t) => {
  let now = 1000;
  t.mock.method(Date, "now", () => now);
  const original = await getAnalyticsOverview("shop-a");
  now += 29 * 60 * 1000;
  assert.equal(await getAnalyticsOverview("shop-a"), original);
  now += 2 * 60 * 1000;
  assert.notEqual(await getAnalyticsOverview("shop-a"), original);
  assert.equal(reportCalls.length, 2);
  assert.equal(versionCalls.length, 3);
});

test("identical revisions cannot share analytics across businesses", async () => {
  const first = await getAnalyticsOverview("shop-a");
  const second = await getAnalyticsOverview("shop-b");
  assert.notEqual(first, second);
  assert.equal(await getAnalyticsOverview("shop-a"), first);
  assert.equal(reportCalls.length, 2);
});

test("failed permission/revision checks never return a cached financial report", async () => {
  await getAnalyticsOverview("shop-a");
  versionReply = () => { throw new Error("Read access revoked"); };
  await assert.rejects(getAnalyticsOverview("shop-a"), /Read access revoked/);
  for (const analyticsRevision of [null, "", "x".repeat(64), 4]) {
    versionReply = () => ({ analyticsRevision });
    await assert.rejects(getAnalyticsOverview("shop-a"), /freshness could not be verified/);
  }
  assert.equal(reportCalls.length, 1);
});

function deferred() {
  let resolve;
  const promise = new Promise((accept) => { resolve = accept; });
  return { promise, resolve };
}

test("a version reply after logout cannot start an old-session report load", async () => {
  const reply = deferred();
  const metadata = versionReply();
  versionReply = () => reply.promise;
  const old = getAnalyticsOverview("shop-a");
  invalidateReadCache("");
  reply.resolve(metadata);
  await assert.rejects(old, { name: "AbortError" });
  assert.equal(reportCalls.length, 0);
});

test("an old-session report response cannot repopulate cache or be returned after logout", async () => {
  const entered = deferred();
  const reply = deferred();
  const defaultReply = overviewReply;
  overviewReply = () => { entered.resolve(); return reply.promise; };
  const old = getAnalyticsOverview("shop-a");
  await entered.promise;
  invalidateReadCache("");
  overviewReply = defaultReply;
  const current = await getAnalyticsOverview("shop-a");
  reply.resolve(defaultReply());
  await assert.rejects(old, { name: "AbortError" });
  assert.equal(await getAnalyticsOverview("shop-a"), current);
  assert.equal(reportCalls.length, 2);
});
