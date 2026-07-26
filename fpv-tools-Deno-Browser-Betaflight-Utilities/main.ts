/**
 * Main entry point for your Val.town val
 *
 * This is a template - replace with your actual implementation.
 * Follow TDD: Write tests first, then implement features.
 */

export default async function handler(req: Request): Promise<Response> {
  const url = new URL(req.url);

  // Example: Simple routing
  if (url.pathname === "/") {
    return new Response(
      `
      <!DOCTYPE html>
      <html lang="en">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Val.town Template</title>
        <style>
          body {
            font-family: system-ui, -apple-system, sans-serif;
            max-width: 600px;
            margin: 40px auto;
            padding: 0 20px;
            line-height: 1.6;
          }
          h1 { color: #333; }
          code {
            background: #f4f4f4;
            padding: 2px 6px;
            border-radius: 3px;
          }
        </style>
      </head>
      <body>
        <h1>🚀 Val.town Template</h1>
        <p>This is a template val. Replace this with your actual implementation.</p>
        <h2>Next Steps:</h2>
        <ol>
          <li>Read <code>claude.md</code> for development guidelines</li>
          <li>Write your first test in <code>tests/</code></li>
          <li>Implement your feature</li>
          <li>Commit both separately</li>
          <li>Deploy with <code>val deploy main.ts</code></li>
        </ol>
        <p><strong>Remember:</strong> Test first. No React. Mobile-responsive. Commit often.</p>
      </body>
      </html>
      `,
      {
        headers: { "Content-Type": "text/html; charset=utf-8" },
      }
    );
  }

  // Example: JSON API endpoint
  if (url.pathname === "/api/hello") {
    return Response.json({
      message: "Hello from Val.town!",
      timestamp: new Date().toISOString(),
    });
  }

  // 404
  return new Response("Not Found", { status: 404 });
}
