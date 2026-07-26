import { readFileSync } from 'node:fs';
import { serve } from '@hono/node-server';
import { serveStatic } from '@hono/node-server/serve-static';
import { Hono } from 'hono';
import sessions from './api/sessions.js';
import progress from './api/progress.js';
import tricks from './api/tricks.js';
import equipment from './api/equipment.js';
import denver from './api/denver.js';
import exportimport from './api/exportimport.js';
import plans from './api/plans.js';

const { version: APP_VERSION } = JSON.parse(
  readFileSync(new URL('../package.json', import.meta.url), 'utf-8')
);

const app = new Hono();

// API routes
app.route('/api/sessions', sessions);
app.route('/api/progress', progress);
app.route('/api/tricks', tricks);
app.route('/api/equipment', equipment);
app.route('/api/denver', denver);
app.route('/api/data', exportimport);
app.route('/api/plans', plans);

// Health check
app.get('/api/health', (c) => c.json({ status: 'ok', version: APP_VERSION }));

// Static files
app.use('/*', serveStatic({ root: './public' }));

const port = parseInt(process.env.PORT || '3000', 10);
console.log(`flowchart listening on http://localhost:${port}`);
serve({ fetch: app.fetch, port });
