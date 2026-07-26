import { assertEquals } from "https://deno.land/std@0.208.0/assert/mod.ts";
import handler from "../main.ts";

Deno.test("GET / returns HTML with template content", async () => {
  const req = new Request("http://localhost/");
  const res = await handler(req);

  assertEquals(res.status, 200);
  assertEquals(res.headers.get("Content-Type"), "text/html; charset=utf-8");

  const html = await res.text();
  assertEquals(html.includes("Val.town Template"), true);
});

Deno.test("GET /api/hello returns JSON", async () => {
  const req = new Request("http://localhost/api/hello");
  const res = await handler(req);

  assertEquals(res.status, 200);

  const json = await res.json();
  assertEquals(json.message, "Hello from Val.town!");
  assertEquals(typeof json.timestamp, "string");
});

Deno.test("GET /unknown returns 404", async () => {
  const req = new Request("http://localhost/unknown");
  const res = await handler(req);

  assertEquals(res.status, 404);
});
