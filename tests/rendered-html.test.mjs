import assert from "node:assert/strict";
import test from "node:test";

test("renders the complete NextUp PNW experience", async () => {
  const workerUrl = new URL("../dist/server/index.js", import.meta.url);
  workerUrl.searchParams.set("test", `${process.pid}-${Date.now()}`);
  const { default: worker } = await import(workerUrl.href);
  const response = await worker.fetch(new Request("http://localhost/", { headers: { accept: "text/html" } }), { ASSETS: { fetch: async () => new Response("Not found", { status: 404 }) } }, { waitUntil() {}, passThroughOnException() {} });
  assert.equal(response.status, 200);
  const body = await response.text();
  assert.match(body, /<title>NextUp PNW/);
  assert.match(body, /Stop finding out/);
  assert.match(body, /Frontier Cascadia/);
  assert.match(body, /Medicine &amp; Health/);
  assert.match(body, /WCC Seattle Law Fair/);
  assert.match(body, /40(?:<!-- -->)? researched listings/);
  assert.match(body, /Submit an opportunity/);
  assert.doesNotMatch(body, /codex-preview/);
});
