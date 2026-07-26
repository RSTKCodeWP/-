import { DB } from "https://deno.land/x/sqlite@v3.9.1/mod.ts";
import {
  createPart,
  getPart,
  getPartHistory,
  initDb,
  listParts,
  movePart,
  type Part,
  type PartStatus,
  type PartType,
  updatePart,
} from "./db.ts";
import { handleApi } from "./api.ts";

const PHOTOS_DIR = Deno.env.get("PHOTOS_DIR") ?? "./photos";
const DB_PATH = Deno.env.get("DB_PATH") ?? "./fpv-inventory.db";

const STATUS_LABELS: Record<PartStatus, string> = {
  "unused": "Unused",
  "in-use": "In Use",
  "broken": "Broken",
  "retired": "Retired",
  "lost": "Lost",
};

const STATUS_COLORS: Record<PartStatus, string> = {
  "unused": "#6c757d",
  "in-use": "#198754",
  "broken": "#dc3545",
  "retired": "#6f42c1",
  "lost": "#fd7e14",
};

const TYPE_LABELS: Record<PartType, string> = {
  "motor": "Motor",
  "fc": "FC",
  "esc": "ESC",
  "vtx": "VTX",
  "frame": "Frame",
  "camera": "Camera",
  "antenna": "Antenna",
  "battery": "Battery",
  "craft": "Craft",
  "gear": "Gear",
  "other": "Other",
};

function html(strings: TemplateStringsArray, ...values: unknown[]): string {
  return strings.reduce(
    (acc, str, i) => acc + str + (i < values.length ? String(values[i]) : ""),
    "",
  );
}

function escape(s: unknown): string {
  return String(s ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function statusBadge(status: PartStatus): string {
  const color = STATUS_COLORS[status] ?? "#6c757d";
  const label = STATUS_LABELS[status] ?? status;
  return `<span class="badge" style="background:${color}">${escape(label)}</span>`;
}

function typeBadge(type: PartType | null): string {
  if (!type) return "";
  const label = TYPE_LABELS[type] ?? type;
  return `<span class="type-badge">${escape(label)}</span>`;
}

const ALL_TYPES = [
  "motor",
  "fc",
  "esc",
  "vtx",
  "frame",
  "camera",
  "antenna",
  "battery",
  "craft",
  "other",
] as PartType[];

function typeOptions(selected: PartType | null): string {
  return `<option value="">— any type —</option>` +
    ALL_TYPES.map((t) =>
      `<option value="${t}"${t === selected ? " selected" : ""}>${TYPE_LABELS[t]}</option>`
    ).join("");
}

function layout(title: string, body: string): string {
  return html`
    <!DOCTYPE html>
    <html lang="en">
      <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>${escape(title)} — FPV Inventory</title>
        <style>
        *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
        body {
          font-family: system-ui, -apple-system, sans-serif;
          background: #0d1117;
          color: #e6edf3;
          min-height: 100vh;
          padding: 0 0 80px;
        }
        a { color: #58a6ff; text-decoration: none; }
        a:hover { text-decoration: underline; }
        header {
          background: #161b22;
          border-bottom: 1px solid #30363d;
          padding: 12px 16px;
          display: flex;
          align-items: center;
          gap: 12px;
        }
        header h1 { font-size: 1.1rem; font-weight: 600; }
        header h1 a { color: #e6edf3; }
        .container { max-width: 860px; margin: 0 auto; padding: 20px 16px; }
        .card {
          background: #161b22;
          border: 1px solid #30363d;
          border-radius: 8px;
          padding: 16px;
          margin-bottom: 16px;
        }
        .card h2 { font-size: 1rem; margin-bottom: 12px; color: #8b949e; text-transform: uppercase; font-size: .75rem; letter-spacing: .04em; }
        .btn {
          display: inline-block;
          padding: 6px 14px;
          border-radius: 6px;
          border: 1px solid #30363d;
          background: #21262d;
          color: #e6edf3;
          font-size: .875rem;
          cursor: pointer;
          text-decoration: none;
        }
        .btn:hover { background: #30363d; text-decoration: none; }
        .btn-primary { background: #238636; border-color: #2ea043; color: #fff; }
        .btn-primary:hover { background: #2ea043; }
        .btn-danger { background: #b91c1c; border-color: #ef4444; color: #fff; }
        .btn-sm { padding: 3px 10px; font-size: .8rem; }
        input, select, textarea {
          background: #0d1117;
          border: 1px solid #30363d;
          border-radius: 6px;
          color: #e6edf3;
          padding: 6px 10px;
          font-size: .9rem;
          width: 100%;
        }
        input:focus, select:focus, textarea:focus {
          outline: none;
          border-color: #58a6ff;
        }
        label { font-size: .875rem; color: #8b949e; display: block; margin-bottom: 4px; }
        .field { margin-bottom: 12px; }
        .badge {
          display: inline-block;
          padding: 2px 8px;
          border-radius: 12px;
          font-size: .75rem;
          color: #fff;
          font-weight: 600;
        }
        .part-row {
          display: flex;
          align-items: center;
          gap: 10px;
          padding: 10px 0;
          border-bottom: 1px solid #21262d;
        }
        .part-row:last-child { border-bottom: none; }
        .part-name { flex: 1; font-weight: 500; }
        .part-meta { font-size: .8rem; color: #8b949e; }
        .history-item {
          padding: 8px 0;
          border-bottom: 1px solid #21262d;
          font-size: .85rem;
          color: #8b949e;
        }
        .history-item:last-child { border-bottom: none; }
        .history-action { color: #e6edf3; font-weight: 500; }
        .breadcrumb { font-size: .85rem; margin-bottom: 16px; color: #8b949e; }
        .breadcrumb a { color: #58a6ff; }
        .quick-add { display: flex; gap: 8px; flex-wrap: wrap; align-items: flex-end; }
        .quick-add .field { margin-bottom: 0; flex: 1; min-width: 120px; }
        .photo-preview { max-width: 100%; max-height: 240px; border-radius: 6px; margin-top: 8px; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
        @media (max-width: 600px) {
          .grid-2 { grid-template-columns: 1fr; }
          .quick-add { flex-direction: column; }
        }
        .empty { color: #8b949e; font-size: .9rem; padding: 12px 0; }
        .detail-field { margin-bottom: 8px; font-size: .9rem; }
        .detail-field .label { color: #8b949e; font-size: .8rem; display: block; margin-bottom: 2px; }
        .part-qty { background: #21262d; border-radius: 4px; padding: 1px 6px; font-size: .8rem; min-width: 28px; text-align: center; }
        .type-badge { background: #1f3a5f; color: #79c0ff; border-radius: 4px; padding: 1px 7px; font-size: .75rem; font-weight: 500; }
      </style>
      </head>
      <body>
        <header>
          <h1><a href="/">🚁 FPV Inventory</a></h1>
        </header>
        <div class="container">
        ${body}
      </div>
      </body>
    </html>
  `;
}

function fullAddForm(parentId?: number): string {
  const parentInput = parentId != null
    ? `<input type="hidden" name="parent_id" value="${parentId}">`
    : `
      <div class="field">
        <label>Parent Assembly (optional)</label>
        <select name="parent_id">
          <option value="">(none — spare parts)</option>
        </select>
      </div>`;
  const title = parentId != null ? `Add Component to Assembly` : `Add Part`;
  const backLink = parentId != null ? `/parts/${parentId}` : "/";
  return layout(
    title,
    `
    <div class="breadcrumb"><a href="${backLink}">← Back</a></div>
    <div class="card">
      <h2>${escape(title)}</h2>
      <form method="POST" action="/parts/new">
        ${parentInput}
        <div class="field">
          <label>Name *</label>
          <input name="name" required placeholder="e.g. 0702 Motor, Quad Alpha…" autofocus>
        </div>
        <div class="grid-2">
          <div class="field">
            <label>Type</label>
            <select name="type">
              <option value="">—</option>
              ${ALL_TYPES.map((t) => `<option value="${t}">${TYPE_LABELS[t]}</option>`).join("")}
            </select>
          </div>
          <div class="field">
            <label>Status</label>
            <select name="status">
              <option value="unused">Unused</option>
              <option value="in-use">In Use</option>
              <option value="broken">Broken</option>
              <option value="retired">Retired</option>
              <option value="lost">Lost</option>
            </select>
          </div>
        </div>
        <div class="field">
          <label>Quantity</label>
          <input name="quantity" type="number" value="1" min="1" style="max-width:120px">
        </div>
        <div class="field">
          <label>Notes</label>
          <textarea name="notes" rows="3" placeholder="e.g. burned in, running on 4S only"></textarea>
        </div>
        <div class="field">
          <label>Specs <span style="color:#6e7681;font-weight:400">(raw spec block from product listing)</span></label>
          <textarea name="specs" rows="4" style="font-family:monospace;font-size:.82rem" placeholder="e.g. KV: 2400&#10;Weight: 31.5g&#10;Max Power: 1100W"></textarea>
        </div>
        <div style="display:flex;gap:8px;align-items:center">
          <button type="submit" class="btn btn-primary">Save Part</button>
          <a href="${backLink}" class="btn">Cancel</a>
        </div>
      </form>
    </div>
  `,
  );
}

function quickAddForm(parentId?: number): string {
  const parentInput = parentId != null
    ? `<input type="hidden" name="parent_id" value="${parentId}">`
    : "";
  return `
<div class="card">
  <h2>Quick Add</h2>
  <form method="POST" action="/parts">
    ${parentInput}
    <div class="quick-add">
      <div class="field" style="flex:2;min-width:180px">
        <label>Name *</label>
        <input name="name" required placeholder="e.g. 0702 Motor, Quad Alpha…">
      </div>
      <div class="field">
        <label>Qty</label>
        <input name="quantity" type="number" value="1" min="1" style="max-width:80px">
      </div>
      <div class="field">
        <label>Type</label>
        <select name="type">
          <option value="">—</option>
          ${ALL_TYPES.map((t) => `<option value="${t}">${TYPE_LABELS[t]}</option>`).join("")}
        </select>
      </div>
      <div class="field">
        <label>Status</label>
        <select name="status">
          <option value="unused">Unused</option>
          <option value="in-use">In Use</option>
          <option value="broken">Broken</option>
          <option value="retired">Retired</option>
          <option value="lost">Lost</option>
        </select>
      </div>
      <div class="field" style="flex:none">
        <label>&nbsp;</label>
        <button type="submit" class="btn btn-primary">Add</button>
      </div>
      <div class="field" style="flex:none">
        <label>&nbsp;</label>
        <a href="/parts/new${
    parentId != null ? `?parent_id=${parentId}` : ""
  }" class="btn btn-sm" style="white-space:nowrap">Full details…</a>
      </div>
    </div>
  </form>
</div>`;
}

function partRow(part: Part): string {
  const qty = part.quantity > 1 ? `<span class="part-qty">${part.quantity}</span>` : "";
  const notes = part.notes
    ? `<span class="part-meta" style="margin-left:4px">— ${escape(part.notes)}</span>`
    : "";
  return `
<div class="part-row">
  <span class="part-name">
    <a href="/parts/${part.id}">${escape(part.name)}</a>
    ${qty}
    ${typeBadge(part.type)}
    ${notes}
  </span>
  ${statusBadge(part.status)}
</div>`;
}

function homePage(db: DB, typeFilter?: PartType): string {
  const parts = listParts(db, { parent_id: null, type: typeFilter });
  const rows = parts.length > 0
    ? parts.map(partRow).join("")
    : `<p class="empty">No parts yet — add something above.</p>`;

  const filterBar = `
<form method="GET" action="/" style="margin-bottom:12px;display:flex;gap:8px;align-items:center;flex-wrap:wrap">
  <label style="margin:0;color:#8b949e;font-size:.875rem">Filter by type:</label>
  <select name="type" onchange="this.form.submit()" style="width:auto">
    ${typeOptions(typeFilter ?? null)}
  </select>
  ${typeFilter ? `<a href="/" class="btn btn-sm">Clear</a>` : ""}
</form>`;

  return layout(
    "Inventory",
    `
    ${quickAddForm()}
    <div class="card">
      <h2>Parts &amp; Assemblies</h2>
      ${filterBar}
      ${rows}
    </div>
  `,
  );
}

async function buildBreadcrumb(db: DB, partId: number): Promise<string> {
  const crumbs: { id: number; name: string }[] = [];
  let current = getPart(db, partId);
  while (current) {
    crumbs.unshift({ id: current.id, name: current.name });
    current = current.parent_id != null ? getPart(db, current.parent_id) : null;
  }
  const links = crumbs.map((c, i) =>
    i === crumbs.length - 1 ? escape(c.name) : `<a href="/parts/${c.id}">${escape(c.name)}</a>`
  );
  return `<div class="breadcrumb"><a href="/">Home</a> › ${links.join(" › ")}</div>`;
}

function historyDescription(entry: ReturnType<typeof getPartHistory>[0]): string {
  switch (entry.action) {
    case "created":
      return entry.to_parent_id ? `Added to assembly #${entry.to_parent_id}` : "Added to inventory";
    case "updated":
      return entry.old_status !== entry.new_status
        ? `Status changed: ${entry.old_status} → ${entry.new_status}`
        : entry.quantity_delta && entry.quantity_delta !== 0
        ? `Quantity changed by ${entry.quantity_delta > 0 ? "+" : ""}${entry.quantity_delta}`
        : "Details updated";
    case "moved":
      return entry.to_parent_id
        ? `Moved from #${entry.from_parent_id ?? "spare parts"} to assembly #${entry.to_parent_id}${
          entry.notes ? ` — ${escape(entry.notes)}` : ""
        }`
        : `Removed from assembly #${entry.from_parent_id}${
          entry.notes ? ` — ${escape(entry.notes)}` : ""
        }`;
    default:
      return escape(entry.action);
  }
}

async function partDetailPage(db: DB, id: number): Promise<string | null> {
  const part = getPart(db, id);
  if (!part) return null;

  const children = listParts(db, { parent_id: id });
  const history = getPartHistory(db, id);
  const allParts = listParts(db).filter((p) => p.id !== id);
  const breadcrumb = await buildBreadcrumb(db, id);

  const photoSection = part.photo_path
    ? `<img src="/photos/${escape(part.photo_path)}" alt="photo" class="photo-preview">`
    : "";

  const childrenHtml = children.length > 0
    ? children.map(partRow).join("")
    : `<p class="empty">No components — use quick add below.</p>`;

  const historyHtml = history.map((h) => `
    <div class="history-item">
      <span class="history-action">${escape(h.action)}</span>
      — ${historyDescription(h)}
      <span style="float:right;font-size:.75rem">${
    h.created_at.replace("T", " ").slice(0, 16)
  }</span>
    </div>
  `).join("");

  const parentOptions = allParts
    .map((p) => `<option value="${p.id}">${escape(p.name)}</option>`)
    .join("");

  const currentParentId = part.parent_id;

  return layout(
    part.name,
    `
    ${breadcrumb}

    <div class="grid-2">
      <div class="card">
        <h2>Part Details</h2>
        ${photoSection}
        <div class="detail-field">
          <span class="label">Name</span>
          <strong>${escape(part.name)}</strong>
        </div>
        <div class="detail-field">
          <span class="label">Status</span>
          ${statusBadge(part.status)}
        </div>
        <div class="detail-field">
          <span class="label">Type</span>
          ${part.type ? typeBadge(part.type) : '<span style="color:#8b949e">—</span>'}
        </div>
        <div class="detail-field">
          <span class="label">Quantity</span>
          ${escape(part.quantity)}
        </div>
        ${
      part.notes
        ? `<div class="detail-field"><span class="label">Notes</span>${escape(part.notes)}</div>`
        : ""
    }
        ${
      part.specs
        ? `<div class="detail-field"><span class="label">Specs</span><pre style="font-size:.8rem;background:#0d1117;padding:8px;border-radius:4px;overflow-x:auto;white-space:pre-wrap;color:#79c0ff">${
          escape(part.specs)
        }</pre></div>`
        : ""
    }
        ${
      part.parent_id != null
        ? `<div class="detail-field"><span class="label">Assembly</span><a href="/parts/${part.parent_id}">${
          escape(getPart(db, part.parent_id)?.name ?? `#${part.parent_id}`)
        }</a></div>`
        : ""
    }

        <hr style="border-color:#30363d;margin:12px 0">

        <form method="POST" action="/parts/${id}/update">
          <div class="field">
            <label>Status</label>
            <select name="status">
              ${
      (["unused", "in-use", "broken", "retired", "lost"] as PartStatus[])
        .map((s) =>
          `<option value="${s}"${s === part.status ? " selected" : ""}>${STATUS_LABELS[s]}</option>`
        )
        .join("")
    }
            </select>
          </div>
          <div class="field">
            <label>Type</label>
            <select name="type">
              ${typeOptions(part.type)}
            </select>
          </div>
          <div class="field">
            <label>Quantity</label>
            <input name="quantity" type="number" min="0" value="${escape(part.quantity)}">
          </div>
          <div class="field">
            <label>Notes</label>
            <textarea name="notes" rows="2">${escape(part.notes ?? "")}</textarea>
          </div>
          <div class="field">
            <label>Specs <span style="color:#6e7681;font-weight:400">(raw spec block from product listing)</span></label>
            <textarea name="specs" rows="4" style="font-family:monospace;font-size:.82rem" placeholder="e.g. KV: 2400&#10;Weight: 31.5g&#10;Max Power: 1100W">${
      escape(part.specs ?? "")
    }</textarea>
          </div>
          <button type="submit" class="btn btn-primary btn-sm">Save changes</button>
        </form>

        <hr style="border-color:#30363d;margin:12px 0">

        <form method="POST" action="/parts/${id}/move" style="margin-top:4px">
          <div class="field">
            <label>Move to assembly (or spare parts)</label>
            <select name="new_parent_id">
              <option value=""${
      currentParentId == null ? " selected" : ""
    }>(spare parts / top-level)</option>
              ${parentOptions}
            </select>
          </div>
          <div class="field">
            <label>Reason (optional)</label>
            <input name="notes" placeholder="e.g. Salvaged from crash">
          </div>
          <button type="submit" class="btn btn-sm">Move</button>
        </form>

        <hr style="border-color:#30363d;margin:12px 0">

        <form method="POST" action="/parts/${id}/photo" enctype="multipart/form-data">
          <div class="field">
            <label>Upload photo</label>
            <input type="file" name="photo" accept="image/*">
          </div>
          <button type="submit" class="btn btn-sm">Upload</button>
        </form>
      </div>

      <div>
        <div class="card">
          <h2>History</h2>
          ${historyHtml || '<p class="empty">No history.</p>'}
        </div>
      </div>
    </div>

    <div class="card">
      <h2>Components of ${escape(part.name)}</h2>
      ${childrenHtml}
    </div>

    ${quickAddForm(id)}
  `,
  );
}

export function makeHandler(db: DB) {
  return async function handler(req: Request): Promise<Response> {
    const url = new URL(req.url);
    const path = url.pathname;

    // JSON API — owns everything under /api/, returns null for other paths
    const apiRes = handleApi(db, req, url);
    if (apiRes) return apiRes;

    // GET /
    if (path === "/" && req.method === "GET") {
      const typeParam = url.searchParams.get("type") as PartType | null;
      return new Response(homePage(db, typeParam ?? undefined), {
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    }

    // POST /parts — create
    if (path === "/parts" && req.method === "POST") {
      const form = await req.formData();
      const name = form.get("name")?.toString().trim();
      if (!name) {
        return new Response("Name is required", { status: 400 });
      }
      const quantity = parseInt(form.get("quantity")?.toString() ?? "1", 10) || 1;
      const status = (form.get("status")?.toString() ?? "unused") as PartStatus;
      const typeStr = form.get("type")?.toString() || undefined;
      const type = typeStr ? typeStr as PartType : undefined;
      const notes = form.get("notes")?.toString().trim() || undefined;
      const parentIdStr = form.get("parent_id")?.toString();
      const parsedParentId = parentIdStr ? parseInt(parentIdStr, 10) : null;
      const parent_id = (parsedParentId != null && !isNaN(parsedParentId)) ? parsedParentId : null;

      try {
        createPart(db, { name, quantity, status, type, notes, parent_id });
      } catch (err) {
        console.error("Failed to create part:", err);
        return new Response("Failed to create part", { status: 500 });
      }

      const redirect = parent_id != null ? `/parts/${parent_id}` : "/";
      return new Response(null, { status: 303, headers: { Location: redirect } });
    }

    // GET /parts/new — full add form
    if (path === "/parts/new" && req.method === "GET") {
      const parentIdStr = url.searchParams.get("parent_id");
      const parentId = parentIdStr ? parseInt(parentIdStr, 10) : undefined;
      return new Response(fullAddForm(parentId), {
        headers: { "Content-Type": "text/html; charset=utf-8" },
      });
    }

    // POST /parts/new — create from full form (redirects to new part detail)
    if (path === "/parts/new" && req.method === "POST") {
      const form = await req.formData();
      const name = form.get("name")?.toString().trim();
      if (!name) {
        return new Response("Name is required", { status: 400 });
      }
      const quantity = parseInt(form.get("quantity")?.toString() ?? "1", 10) || 1;
      const status = (form.get("status")?.toString() ?? "unused") as PartStatus;
      const typeStr = form.get("type")?.toString() || undefined;
      const type = typeStr ? typeStr as PartType : undefined;
      const notes = form.get("notes")?.toString().trim() || undefined;
      const specs = form.get("specs")?.toString().trim() || undefined;
      const parentIdStr = form.get("parent_id")?.toString();
      const parsedParentId = parentIdStr ? parseInt(parentIdStr, 10) : null;
      const parent_id = (parsedParentId != null && !isNaN(parsedParentId)) ? parsedParentId : null;

      let newId: number;
      try {
        newId = createPart(db, { name, quantity, status, type, notes, specs, parent_id });
      } catch (err) {
        console.error("Failed to create part:", err);
        return new Response("Failed to create part", { status: 500 });
      }
      return new Response(null, { status: 303, headers: { Location: `/parts/${newId}` } });
    }

    // GET /parts/:id
    const detailMatch = path.match(/^\/parts\/(\d+)$/);
    if (detailMatch && req.method === "GET") {
      const id = parseInt(detailMatch[1], 10);
      const page = await partDetailPage(db, id);
      if (!page) return new Response("Not Found", { status: 404 });
      return new Response(page, { headers: { "Content-Type": "text/html; charset=utf-8" } });
    }

    // POST /parts/:id/update
    const updateMatch = path.match(/^\/parts\/(\d+)\/update$/);
    if (updateMatch && req.method === "POST") {
      const id = parseInt(updateMatch[1], 10);
      const part = getPart(db, id);
      if (!part) return new Response("Not Found", { status: 404 });
      const form = await req.formData();
      const status = form.get("status")?.toString() as PartStatus | undefined;
      const typeStr = form.get("type")?.toString();
      const type = typeStr !== undefined ? (typeStr || null) as PartType | null : undefined;
      const notes = form.get("notes")?.toString();
      const specs = form.get("specs")?.toString();
      const quantityStr = form.get("quantity")?.toString();
      const quantity = quantityStr != null ? parseInt(quantityStr, 10) : undefined;
      try {
        updatePart(db, id, { status, type, notes, specs, quantity });
      } catch (err) {
        console.error("Failed to update part:", err);
        return new Response("Failed to update part", { status: 500 });
      }
      return new Response(null, { status: 303, headers: { Location: `/parts/${id}` } });
    }

    // POST /parts/:id/move
    const moveMatch = path.match(/^\/parts\/(\d+)\/move$/);
    if (moveMatch && req.method === "POST") {
      const id = parseInt(moveMatch[1], 10);
      const part = getPart(db, id);
      if (!part) return new Response("Not Found", { status: 404 });
      const form = await req.formData();
      const newParentIdStr = form.get("new_parent_id")?.toString();
      const newParentId = newParentIdStr ? parseInt(newParentIdStr, 10) : null;
      const notes = form.get("notes")?.toString() || undefined;
      try {
        movePart(db, id, newParentId, notes);
      } catch (err) {
        console.error("Failed to move part:", err);
        return new Response("Failed to move part", { status: 500 });
      }
      const redirect = newParentId != null ? `/parts/${newParentId}` : "/";
      return new Response(null, { status: 303, headers: { Location: redirect } });
    }

    // POST /parts/:id/photo
    const photoUploadMatch = path.match(/^\/parts\/(\d+)\/photo$/);
    if (photoUploadMatch && req.method === "POST") {
      const id = parseInt(photoUploadMatch[1], 10);
      const part = getPart(db, id);
      if (!part) return new Response("Not Found", { status: 404 });
      const form = await req.formData();
      const file = form.get("photo");
      if (!file || !(file instanceof File) || file.size === 0) {
        return new Response("No file provided", { status: 400 });
      }
      const ext = file.name.split(".").pop() ?? "jpg";
      const filename = `${id}-${Date.now()}.${ext}`;
      await Deno.mkdir(PHOTOS_DIR, { recursive: true });
      const bytes = new Uint8Array(await file.arrayBuffer());
      await Deno.writeFile(`${PHOTOS_DIR}/${filename}`, bytes);
      updatePart(db, id, { photo_path: filename });
      return new Response(null, { status: 303, headers: { Location: `/parts/${id}` } });
    }

    // GET /photos/:filename
    const photoMatch = path.match(/^\/photos\/([a-zA-Z0-9_\-\.]+)$/);
    if (photoMatch && req.method === "GET") {
      const filename = photoMatch[1];
      try {
        const bytes = await Deno.readFile(`${PHOTOS_DIR}/${filename}`);
        const ext = filename.split(".").pop()?.toLowerCase() ?? "jpg";
        const contentType = ext === "png"
          ? "image/png"
          : ext === "gif"
          ? "image/gif"
          : "image/jpeg";
        return new Response(bytes, { headers: { "Content-Type": contentType } });
      } catch {
        return new Response("Not Found", { status: 404 });
      }
    }

    return new Response("Not Found", { status: 404 });
  };
}

function withLogging(
  handler: (req: Request) => Promise<Response>,
): (req: Request) => Promise<Response> {
  return async (req: Request) => {
    const start = Date.now();
    const { method } = req;
    const path = new URL(req.url).pathname;
    try {
      const res = await handler(req);
      console.log(`${method} ${path} → ${res.status} (${Date.now() - start}ms)`);
      return res;
    } catch (err) {
      console.error(`${method} ${path} → ERROR`, err);
      return new Response("Internal Server Error", { status: 500 });
    }
  };
}

// When run directly (not imported), start the server
if (import.meta.main) {
  const db = initDb(DB_PATH);
  const port = parseInt(Deno.env.get("PORT") ?? "8000", 10);

  const server = Deno.serve(
    {
      port,
      onListen: ({ port, hostname }) => {
        console.log(`FPV Inventory running on http://${hostname}:${port}`);
      },
    },
    withLogging(makeHandler(db)),
  );

  const shutdown = async () => {
    console.log("Shutting down gracefully...");
    await server.shutdown();
    db.close();
    console.log("Shutdown complete.");
  };

  Deno.addSignalListener("SIGTERM", shutdown);
  Deno.addSignalListener("SIGINT", shutdown);
}
