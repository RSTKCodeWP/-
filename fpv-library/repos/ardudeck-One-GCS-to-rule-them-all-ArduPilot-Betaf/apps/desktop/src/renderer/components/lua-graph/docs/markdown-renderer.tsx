/**
 * Lightweight markdown-to-React renderer - zero dependencies.
 * Supports: headers, paragraphs, fenced code blocks (with Lua highlighting),
 * tables, ordered/unordered lists, blockquotes, horizontal rules,
 * bold, italic, inline code, and links.
 */
import { type ReactNode } from 'react';
import { highlightLua } from '../lua-highlighter';

// ── Inline parsing ──────────────────────────────────────────────

function parseInline(text: string, keyBase: number): ReactNode[] {
  const elements: ReactNode[] = [];
  let key = keyBase;

  // Regex matches inline patterns in priority order:
  // 1. inline code  2. bold  3. italic  4. links
  const re = /`([^`]+)`|\*\*(.+?)\*\*|\*(.+?)\*|\[([^\]]+)\]\(([^)]+)\)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = re.exec(text)) !== null) {
    // Push plain text before match
    if (match.index > lastIndex) {
      elements.push(<span key={key++}>{text.slice(lastIndex, match.index)}</span>);
    }

    if (match[1] !== undefined) {
      // Inline code
      elements.push(
        <code key={key++} className="px-1.5 py-0.5 rounded bg-surface-raised text-amber-400 text-[12px] font-mono">
          {match[1]}
        </code>,
      );
    } else if (match[2] !== undefined) {
      // Bold
      elements.push(<strong key={key++} className="text-content font-semibold">{match[2]}</strong>);
    } else if (match[3] !== undefined) {
      // Italic
      elements.push(<em key={key++} className="text-content italic">{match[3]}</em>);
    } else if (match[4] !== undefined && match[5] !== undefined) {
      // Link
      elements.push(
        <a key={key++} href={match[5]} target="_blank" rel="noopener noreferrer"
          className="text-blue-400 hover:text-blue-300 underline underline-offset-2">
          {match[4]}
        </a>,
      );
    }
    lastIndex = match.index + match[0]!.length;
  }

  // Trailing text
  if (lastIndex < text.length) {
    elements.push(<span key={key++}>{text.slice(lastIndex)}</span>);
  }

  return elements;
}

// ── Table parsing ───────────────────────────────────────────────

function parseTable(lines: string[], startKey: number): ReactNode {
  if (lines.length < 2) return null;

  const parseRow = (line: string): string[] =>
    line.split('|').map((c) => c.trim()).filter((c) => c.length > 0);

  const headers = parseRow(lines[0]!);
  // lines[1] is the separator row - skip it
  const rows = lines.slice(2).map(parseRow);

  return (
    <div key={startKey} className="my-3 rounded-lg border border-subtle overflow-hidden">
      <table className="w-full text-[12px]">
        <thead>
          <tr className="bg-surface">
            {headers.map((h, i) => (
              <th key={i} className="px-3 py-2 text-left text-content-secondary font-medium border-b border-subtle">
                {parseInline(h, startKey + 1000 + i * 100)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, ri) => (
            <tr key={ri} className="border-b border-subtle last:border-b-0">
              {row.map((cell, ci) => (
                <td key={ci} className="px-3 py-1.5 text-content-secondary">
                  {parseInline(cell, startKey + 2000 + ri * 100 + ci)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ── Block parsing ───────────────────────────────────────────────

export function renderMarkdown(markdown: string): ReactNode[] {
  const lines = markdown.split('\n');
  const elements: ReactNode[] = [];
  let key = 0;
  let i = 0;

  while (i < lines.length) {
    const line = lines[i]!;

    // ── Fenced code blocks ────────────────────────────────────
    if (line.startsWith('```')) {
      const lang = line.slice(3).trim();
      const codeLines: string[] = [];
      i++;
      while (i < lines.length && !lines[i]!.startsWith('```')) {
        codeLines.push(lines[i]!);
        i++;
      }
      i++; // skip closing ```

      const code = codeLines.join('\n');
      const isLua = lang === 'lua';

      elements.push(
        <div key={key++} className="my-3 rounded-lg bg-surface-base border border-subtle overflow-hidden">
          {lang && (
            <div className="px-3 py-1 text-[10px] text-content-tertiary border-b border-subtle font-mono">
              {lang}
            </div>
          )}
          <pre className="px-4 py-3 text-[12px] leading-relaxed font-mono text-content overflow-x-auto">
            <code>{isLua ? highlightLua(code) : code}</code>
          </pre>
        </div>,
      );
      continue;
    }

    // ── Headers ──────────────────────────────────────────────
    if (line.startsWith('### ')) {
      elements.push(
        <h3 key={key++} className="text-[13px] font-semibold text-content mt-5 mb-2">
          {parseInline(line.slice(4), key * 100)}
        </h3>,
      );
      i++;
      continue;
    }
    if (line.startsWith('## ')) {
      elements.push(
        <h2 key={key++} className="text-[15px] font-bold text-content mt-6 mb-3 pb-2 border-b border-subtle">
          {parseInline(line.slice(3), key * 100)}
        </h2>,
      );
      i++;
      continue;
    }
    if (line.startsWith('# ')) {
      elements.push(
        <h1 key={key++} className="text-lg font-bold text-content mt-4 mb-3">
          {parseInline(line.slice(2), key * 100)}
        </h1>,
      );
      i++;
      continue;
    }

    // ── Horizontal rule ──────────────────────────────────────
    if (/^---+$/.test(line.trim())) {
      elements.push(<hr key={key++} className="my-4 border-subtle" />);
      i++;
      continue;
    }

    // ── Table ────────────────────────────────────────────────
    if (line.includes('|') && lines[i + 1]?.includes('---')) {
      const tableLines: string[] = [];
      while (i < lines.length && lines[i]!.includes('|')) {
        tableLines.push(lines[i]!);
        i++;
      }
      elements.push(parseTable(tableLines, key++ * 10000));
      continue;
    }

    // ── Blockquote ───────────────────────────────────────────
    if (line.startsWith('> ')) {
      const quoteLines: string[] = [];
      while (i < lines.length && lines[i]!.startsWith('> ')) {
        quoteLines.push(lines[i]!.slice(2));
        i++;
      }
      elements.push(
        <blockquote key={key++} className="my-3 pl-4 border-l-2 border-blue-500/40 text-content-secondary text-[12px] leading-relaxed">
          {quoteLines.map((ql, qi) => (
            <p key={qi}>{parseInline(ql, key * 100 + qi)}</p>
          ))}
        </blockquote>,
      );
      continue;
    }

    // ── Unordered list ───────────────────────────────────────
    if (line.startsWith('- ')) {
      const items: string[] = [];
      while (i < lines.length && lines[i]!.startsWith('- ')) {
        items.push(lines[i]!.slice(2));
        i++;
      }
      elements.push(
        <ul key={key++} className="my-2 pl-4 space-y-1">
          {items.map((item, ii) => (
            <li key={ii} className="text-[12px] text-content-secondary leading-relaxed list-disc">
              {parseInline(item, key * 100 + ii)}
            </li>
          ))}
        </ul>,
      );
      continue;
    }

    // ── Ordered list ─────────────────────────────────────────
    if (/^\d+\.\s/.test(line)) {
      const items: string[] = [];
      while (i < lines.length && /^\d+\.\s/.test(lines[i]!)) {
        items.push(lines[i]!.replace(/^\d+\.\s/, ''));
        i++;
      }
      elements.push(
        <ol key={key++} className="my-2 pl-4 space-y-1">
          {items.map((item, ii) => (
            <li key={ii} className="text-[12px] text-content-secondary leading-relaxed list-decimal">
              {parseInline(item, key * 100 + ii)}
            </li>
          ))}
        </ol>,
      );
      continue;
    }

    // ── Empty line ───────────────────────────────────────────
    if (line.trim() === '') {
      i++;
      continue;
    }

    // ── Paragraph (default) ──────────────────────────────────
    elements.push(
      <p key={key++} className="text-[12px] text-content-secondary leading-relaxed my-2">
        {parseInline(line, key * 100)}
      </p>,
    );
    i++;
  }

  return elements;
}
