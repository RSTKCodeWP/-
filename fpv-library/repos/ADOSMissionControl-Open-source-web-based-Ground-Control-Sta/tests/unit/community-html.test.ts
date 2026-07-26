import { describe, expect, it } from "vitest";

import { sanitizeChangelogHtml } from "@/lib/community-html";

describe("sanitizeChangelogHtml", () => {
  it("removes scripts, event handlers, and unsafe hrefs", () => {
    const html = sanitizeChangelogHtml(
      '<p onclick="alert(1)">Hi</p><script>alert(1)</script><a href="javascript:alert(1)">bad</a>',
    );

    expect(html).toContain("<p>Hi</p>");
    expect(html).not.toContain("script");
    expect(html).not.toContain("onclick");
    expect(html).not.toContain("javascript:");
  });

  it("keeps safe changelog links with external-link guards", () => {
    const html = sanitizeChangelogHtml('<a href="https://example.com">read</a>');

    expect(html).toContain('href="https://example.com"');
    expect(html).toContain('rel="noopener noreferrer"');
    expect(html).toContain('target="_blank"');
  });
});
