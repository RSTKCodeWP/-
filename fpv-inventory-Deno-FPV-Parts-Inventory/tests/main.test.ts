import { assertEquals, assertStringIncludes } from "https://deno.land/std@0.208.0/assert/mod.ts";
import { makeHandler } from "../main.ts";
import { initDb } from "../db.ts";

Deno.test("GET / returns HTML with FPV Inventory title", async () => {
  const db = initDb(":memory:");
  const handler = makeHandler(db);
  const req = new Request("http://localhost/");
  const res = await handler(req);

  assertEquals(res.status, 200);
  assertEquals(res.headers.get("Content-Type"), "text/html; charset=utf-8");

  const html = await res.text();
  assertStringIncludes(html, "FPV Inventory");
});

Deno.test("GET /unknown returns 404", async () => {
  const db = initDb(":memory:");
  const handler = makeHandler(db);
  const req = new Request("http://localhost/unknown");
  const res = await handler(req);

  assertEquals(res.status, 404);
});
