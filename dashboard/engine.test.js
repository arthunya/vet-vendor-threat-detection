// Node tests for the dashboard risk engine (dashboard/engine.js).
// Run: node --test dashboard/engine.test.js
const test = require("node:test");
const assert = require("node:assert");
require("./engine.js");
const E = globalThis.VET_ENGINE;
const data = require("../data_build/vet_db.json");
const PREP = E.prepSanctions(data.sanctions);
const screen = (entity) => E.screen(PREP, entity, {});

test("E1 exact match on a designated name forces CRITICAL", () => {
  const r = screen({ name: "Huawei Technologies Co., Ltd.", jurisdiction: "CN", ownerJurisdiction: "CN" });
  assert.strictEqual(r.tier, "CRITICAL");
  assert.strictEqual(r.override, true);
});

test("E2 affiliate-style name variant is routed to human review", () => {
  const r = screen({ name: "Huawei Technologies (Thailand) Ltd", jurisdiction: "TH", ownerJurisdiction: "CN" });
  assert.ok(r.signals.sanctions.score >= 0.85);
  assert.ok(["MEDIUM", "HIGH", "CRITICAL"].includes(r.tier));
});

test("E3 clean listed US company scores LOW", () => {
  const r = screen({ name: "Apple Inc.", jurisdiction: "US", registryId: true, cik: "0000320193" });
  assert.strictEqual(r.tier, "LOW");
});

test("E4 buyback negative equity alone does not escalate the tier", () => {
  const r = screen({ name: "Domino's Pizza, Inc.", jurisdiction: "US", registryId: true, cik: "0001286681" });
  assert.strictEqual(r.signals.financial.score, 0.8);
  assert.strictEqual(r.tier, "LOW");
});

test("E5 missing financial coverage returns null, never a fabricated score", () => {
  const r = screen({ name: "Example Private Vendor LLC", jurisdiction: "US", registryId: true });
  assert.strictEqual(r.signals.financial.score, null);
});

test("E6 missing jurisdiction data is excluded, not assumed to be US", () => {
  const r = screen({ name: "Example Private Vendor LLC", jurisdiction: "", ownerJurisdiction: "" });
  assert.strictEqual(r.signals.geographic.score, null);
});

test("E7 FATF call-for-action jurisdiction raises geographic risk", () => {
  const g = E.geoRisk("IR", "");
  assert.strictEqual(g.score, 0.9);
});

test("E8 dual-use category with sanctioned-jurisdiction exposure is flagged", () => {
  const i = E.industry("334413", "HK", "RU");
  assert.strictEqual(i.score, 0.7);
});

test("E9 no registry identity plus very recent incorporation raises opacity", () => {
  const o = E.opacity(false, 2026, 2026);
  assert.strictEqual(o.score, 0.9);
});

test("E10 no designated name matches any of the 1,261 real companies", () => {
  const hits = data.companies.filter(c =>
    E.screen(PREP, { name: c.name, jurisdiction: "US", registryId: c.registryId, founded: c.founded, cik: c.cik }, { quickReject: true }).tier !== "LOW");
  assert.deepStrictEqual(hits.map(c => c.name), []);
});
