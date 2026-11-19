import assert from "node:assert/strict";
import { registerHooks } from "node:module";
import { beforeEach, test } from "node:test";

import { invalidateReadCache } from "./readCache.js";

// Run the existing analytics cache/save client offline against a small HTTP state model.
let version;
let target;
let rejectSave;
const reportCalls = [];
globalThis.__vendlyAnalyticsCacheRequest = async (path, options) => {
  if (path.endsWith("/analytics/version")) return { analyticsVersion: version };
  if (path.endsWith("/analytics/monthly-target")) {
    assert.equal(options.method, "PATCH");
    if (rejectSave) throw new Error("Target save rejected");
    target = options.body.monthlyTargetMinor;
    version += 1;
    return { monthlyTargetMinor: target };
  }
  assert.ok(path.endsWith("/analytics/overview"));
  reportCalls.push(path);
  return { analytics: { salesForecast: { summary: { monthlyTargetMinor: target, activeTargetMinor: target } } } };
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
