import sanitizeHtml from "sanitize-html";

const ALLOWED_CHANGELOG_TAGS = [
  "a",
  "blockquote",
  "br",
  "code",
  "em",
  "li",
  "ol",
  "p",
  "pre",
  "strong",
  "ul",
];

export function sanitizeChangelogHtml(html: string): string {
  return sanitizeHtml(html, {
    allowedTags: ALLOWED_CHANGELOG_TAGS,
    allowedAttributes: {
      a: ["href", "name", "target", "rel"],
      code: ["class"],
      pre: ["class"],
    },
    allowedSchemes: ["http", "https", "mailto"],
    transformTags: {
      a: sanitizeHtml.simpleTransform("a", {
        rel: "noopener noreferrer",
        target: "_blank",
      }),
    },
  });
}
