import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

test("renders the complete NextUp PNW experience", async () => {
  const opportunities = JSON.parse(await readFile(new URL("../data/opportunities.json", import.meta.url), "utf8"));
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  const response = await worker.fetch(new Request("http://localhost/", { headers: { accept: "text/html" } }), { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } }, { waitUntil() {}, passThroughOnException() {} });
  assert.equal(response.status, 200);
  const body = await response.text();
  assert.match(body, /<title>NextUp PNW/);
  assert.match(body, /What(?:’|&#x27;|')s next across the Pacific Northwest/);
  assert.match(body, /Washington, Oregon, Idaho, and British Columbia/);
  assert.match(body, /Medicine &amp; Health/);
  assert.match(body, new RegExp(`<strong>${opportunities.length}</strong><span>active listings</span>`));
  assert.match(body, /Send an official link/);
  assert.match(body, /View official listing/);
  assert.doesNotMatch(body, /hero-panel/);
  assert.doesNotMatch(body, /opportunity-grid/);
  assert.doesNotMatch(body, /codex-preview/);
});
