import { assertEquals } from "https://deno.land/std@0.208.0/assert/mod.ts";
import { createPart, initDb, type PartStatus, type PartType } from "../db.ts";
import { makeHandler } from "../main.ts";
import { VERSION } from "../version.ts";

function makeApp() {
  const db = initDb(":memory:");
  return { db, handler: makeHandler(db) };
}

Deno.test("GET /api/health returns status, version, name", async () => {
  const { handler } = makeApp();
  const res = await handler(new Request("http://localhost/api/health"));
  assertEquals(res.status, 200);
  assertEquals(res.headers.get("Content-Type"), "application/json; charset=utf-8");
  const body = await res.json();
  assertEquals(body.status, "ok");
  assertEquals(body.name, "fpv-inventory");
  assertEquals(body.version, VERSION);
});

Deno.test("GET /api/nope returns 404 JSON error, not HTML", async () => {
  const { handler } = makeApp();
  const res = await handler(new Request("http://localhost/api/nope"));
  assertEquals(res.status, 404);
  assertEquals(res.headers.get("Content-Type"), "application/json; charset=utf-8");
  const body = await res.json();
  assertEquals(typeof body.error, "string");
});

Deno.test("GET /api (no trailing slash) returns 404 JSON error, not HTML", async () => {
  const { handler } = makeApp();
  const res = await handler(new Request("http://localhost/api"));
  assertEquals(res.status, 404);
  assertEquals(res.headers.get("Content-Type"), "application/json; charset=utf-8");
  const body = await res.json();
  assertEquals(typeof body.error, "string");
});

Deno.test("GET / still serves HTML (unaffected by API layer)", async () => {
  const { handler } = makeApp();
  const res = await handler(new Request("http://localhost/"));
  assertEquals(res.status, 200);
  assertEquals(res.headers.get("Content-Type"), "text/html; charset=utf-8");
});

// ─── GET /api/parts ───────────────────────────────────────────────────────────

Deno.test("GET /api/parts returns [] for an empty DB", async () => {
  const { handler } = makeApp();
  const res = await handler(new Request("http://localhost/api/parts"));
  assertEquals(res.status, 200);
  assertEquals(res.headers.get("Content-Type"), "application/json; charset=utf-8");
  assertEquals(await res.json(), []);
});

Deno.test("GET /api/parts returns all parts", async () => {
  const { db, handler } = makeApp();
  createPart(db, { name: "Motor A", quantity: 4, status: "unused", type: "motor" });
  createPart(db, { name: "Frame X", quantity: 1, status: "unused", type: "frame" });
  const res = await handler(new Request("http://localhost/api/parts"));
  const body = await res.json();
  assertEquals(body.length, 2);
});

Deno.test("GET /api/parts filters by type", async () => {
  const { db, handler } = makeApp();
  createPart(db, { name: "Motor A", quantity: 4, status: "unused", type: "motor" });
  createPart(db, { name: "Frame X", quantity: 1, status: "unused", type: "frame" });
  const res = await handler(new Request("http://localhost/api/parts?type=motor"));
  const body = await res.json();
  assertEquals(body.length, 1);
  assertEquals(body[0].name, "Motor A");
});

Deno.test("GET /api/parts with an invalid type returns [] not an error", async () => {
  const { db, handler } = makeApp();
  createPart(db, { name: "Motor A", quantity: 4, status: "unused", type: "motor" });
  const res = await handler(new Request("http://localhost/api/parts?type=not-a-real-type"));
  assertEquals(res.status, 200);
  assertEquals(await res.json(), []);
});

Deno.test("GET /api/parts?type=<invalid> returns [] even if the DB contains that literal value", async () => {
  const { db, handler } = makeApp();
  // Legacy/corrupt data: main.ts's form handlers cast arbitrary strings to PartType
  // without validation, so a row like this can exist in the wild.
  createPart(db, {
    name: "Weird Part",
    quantity: 1,
    status: "unused",
    type: "not-a-real-type" as PartType,
  });
  const res = await handler(new Request("http://localhost/api/parts?type=not-a-real-type"));
  assertEquals(await res.json(), []);
});

Deno.test("GET /api/parts?status=<invalid> returns [] even if the DB contains that literal value", async () => {
  const { db, handler } = makeApp();
  createPart(db, { name: "Weird Part", quantity: 1, status: "not-a-real-status" as PartStatus });
  const res = await handler(new Request("http://localhost/api/parts?status=not-a-real-status"));
  assertEquals(await res.json(), []);
});

Deno.test("GET /api/parts filters by status", async () => {
  const { db, handler } = makeApp();
  createPart(db, { name: "Motor A", quantity: 4, status: "unused" });
  createPart(db, { name: "Motor B", quantity: 4, status: "broken" });
  const res = await handler(new Request("http://localhost/api/parts?status=broken"));
  const body = await res.json();
  assertEquals(body.length, 1);
  assertEquals(body[0].name, "Motor B");
});

Deno.test("GET /api/parts?parent_id=0 returns only top-level parts", async () => {
  const { db, handler } = makeApp();
  const quadId = createPart(db, { name: "Quad", quantity: 1, status: "in-use" });
  createPart(db, { name: "Motor", quantity: 4, status: "in-use", parent_id: quadId });
  const res = await handler(new Request("http://localhost/api/parts?parent_id=0"));
  const body = await res.json();
  assertEquals(body.length, 1);
  assertEquals(body[0].name, "Quad");
});

Deno.test("GET /api/parts?parent_id=<garbage> ignores the malformed filter instead of matching a partial number", async () => {
  const { db, handler } = makeApp();
  const quadId = createPart(db, { name: "Quad", quantity: 1, status: "in-use" });
  createPart(db, { name: "Motor", quantity: 4, status: "in-use", parent_id: quadId });
  createPart(db, { name: "Loose Prop", quantity: 10, status: "unused" });
  // "12abc" must not be parsed as parent_id=12 (parseInt would stop at the first non-digit)
  const res = await handler(new Request(`http://localhost/api/parts?parent_id=${quadId}abc`));
  const body = await res.json();
  assertEquals(body.length, 3);
});

Deno.test("GET /api/parts?parent_id=-1 rejects negative ids instead of filtering by them", async () => {
  const { db, handler } = makeApp();
  const quadId = createPart(db, { name: "Quad", quantity: 1, status: "in-use" });
  createPart(db, { name: "Motor", quantity: 4, status: "in-use", parent_id: quadId });
  // Real ids are never negative; -1 must be ignored as malformed, not applied as a (perpetually empty) filter
  const res = await handler(new Request("http://localhost/api/parts?parent_id=-1"));
  const body = await res.json();
  assertEquals(body.length, 2);
});

Deno.test("GET /api/parts?parent_id=<id> returns children of that part", async () => {
  const { db, handler } = makeApp();
  const quadId = createPart(db, { name: "Quad", quantity: 1, status: "in-use" });
  createPart(db, { name: "Motor", quantity: 4, status: "in-use", parent_id: quadId });
  const res = await handler(new Request(`http://localhost/api/parts?parent_id=${quadId}`));
  const body = await res.json();
  assertEquals(body.length, 1);
  assertEquals(body[0].name, "Motor");
});

Deno.test("GET /api/parts?q= matches case-insensitive substring of name", async () => {
  const { db, handler } = makeApp();
  createPart(db, { name: "0702 Motor", quantity: 4, status: "unused" });
  createPart(db, { name: "Frame X", quantity: 1, status: "unused" });
  const res = await handler(new Request("http://localhost/api/parts?q=MOTOR"));
  const body = await res.json();
  assertEquals(body.length, 1);
  assertEquals(body[0].name, "0702 Motor");
});

Deno.test("GET /api/parts combines type and q filters", async () => {
  const { db, handler } = makeApp();
  createPart(db, { name: "0702 Motor", quantity: 4, status: "unused", type: "motor" });
  createPart(db, { name: "Frame Motor Mount", quantity: 1, status: "unused", type: "frame" });
  const res = await handler(new Request("http://localhost/api/parts?type=motor&q=0702"));
  const body = await res.json();
  assertEquals(body.length, 1);
  assertEquals(body[0].name, "0702 Motor");
});

// ─── GET /api/parts/:id ───────────────────────────────────────────────────────

Deno.test("GET /api/parts/:id returns part with history", async () => {
  const { db, handler } = makeApp();
  const id = createPart(db, { name: "0702 Motor", quantity: 4, status: "unused", type: "motor" });
  const res = await handler(new Request(`http://localhost/api/parts/${id}`));
  assertEquals(res.status, 200);
  const body = await res.json();
  assertEquals(body.id, id);
  assertEquals(body.name, "0702 Motor");
  assertEquals(Array.isArray(body.history), true);
  assertEquals(body.history.length, 1);
  assertEquals(body.history[0].action, "created");
});

Deno.test("GET /api/parts/:id returns 404 JSON error when missing", async () => {
  const { handler } = makeApp();
  const res = await handler(new Request("http://localhost/api/parts/999999"));
  assertEquals(res.status, 404);
  assertEquals(res.headers.get("Content-Type"), "application/json; charset=utf-8");
  const body = await res.json();
  assertEquals(body.error, "Part not found");
});
