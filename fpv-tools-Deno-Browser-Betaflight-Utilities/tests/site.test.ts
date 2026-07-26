import { assert, assertEquals } from "https://deno.land/std@0.208.0/assert/mod.ts";

const ROOT = new URL("../", import.meta.url);

async function readText(path: string): Promise<string> {
  return await Deno.readTextFile(new URL(path, ROOT));
}

async function exists(path: string): Promise<boolean> {
  try {
    await Deno.stat(new URL(path, ROOT));
    return true;
  } catch {
    return false;
  }
}

const PAGES = [
  { path: "index.html", root: "./", home: true },
  { path: "cli-merge/index.html", root: "../", home: false },
  { path: "rate-profile/index.html", root: "../", home: false },
  { path: "igow/index.html", root: "../", home: false },
  { path: "prop-motor-sizer/index.html", root: "../", home: false },
];

for (const page of PAGES) {
  Deno.test(`${page.path} - uses the shared fpv-header component`, async () => {
    const html = await readText(page.path);
    assert(html.includes("<fpv-header"), "missing <fpv-header> element");
    assert(
      html.includes(`src="${page.root}assets/site-header.js"`),
      "missing site-header.js script tag with correct relative root",
    );
    assert(
      html.includes(`href="${page.root}assets/site-header.css"`),
      "missing site-header.css link with correct relative root",
    );
    assert(
      html.includes(`root="${page.root}"`),
      "fpv-header root attribute doesn't match page depth",
    );
  });

  Deno.test(`${page.path} - back-to-home behavior matches page role`, async () => {
    const html = await readText(page.path);
    const tag = html.match(/<fpv-header\b[^>]*>/)?.[0] ?? "";
    // Strip quoted attribute values first so "home" appearing inside e.g.
    // heading="Welcome home" isn't mistaken for the boolean `home` attribute.
    const tagWithoutValues = tag.replace(/"[^"]*"/g, "");
    const isHome = /\bhome\b/.test(tagWithoutValues);
    assertEquals(isHome, page.home);
  });
}

Deno.test("manifest.json - is valid and has installable PWA fields", async () => {
  const manifest = JSON.parse(await readText("manifest.json"));
  assertEquals(manifest.display, "standalone");
  assert(typeof manifest.name === "string" && manifest.name.length > 0);
  assert(Array.isArray(manifest.icons) && manifest.icons.length > 0);

  for (const icon of manifest.icons) {
    assert(await exists(icon.src), `manifest icon missing on disk: ${icon.src}`);
  }
});

Deno.test("sw.js - precaches only files that exist on disk", async () => {
  const sw = await readText("sw.js");
  const match = sw.match(/const PRECACHE_URLS = \[([\s\S]*?)\];/);
  assert(match, "couldn't find PRECACHE_URLS array in sw.js");

  const urls = [...match[1].matchAll(/"([^"]+)"/g)].map((m) => m[1]);
  assert(urls.length > 0, "PRECACHE_URLS is empty");

  for (const url of urls) {
    const path = url === "./" ? "." : url.replace(/^\.\//, "");
    assert(await exists(path), `precached URL missing on disk: ${url}`);
  }
});
