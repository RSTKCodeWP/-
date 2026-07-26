/**
 * Lightweight Lua syntax highlighter — zero dependencies.
 * Returns React elements with Tailwind color classes.
 */
import { type ReactNode } from 'react';

const LUA_KEYWORDS = new Set([
  'and', 'break', 'do', 'else', 'elseif', 'end', 'false', 'for',
  'function', 'goto', 'if', 'in', 'local', 'nil', 'not', 'or',
  'repeat', 'return', 'then', 'true', 'until', 'while',
]);

// Ordered by match priority — first match wins per position
const TOKEN_REGEX =
  /--\[\[[\s\S]*?\]\]|--[^\n]*|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'|\[\[[\s\S]*?\]\]|0[xX][0-9a-fA-F]+|\b\d+\.?\d*(?:[eE][+-]?\d+)?\b|[a-zA-Z_]\w*/g;

interface Token {
  text: string;
  className: string;
}

function classifyToken(text: string): string {
  // Comments
  if (text.startsWith('--')) return 'text-content-tertiary italic';
  // Strings
  if (text.startsWith('"') || text.startsWith("'") || text.startsWith('[[')) return 'text-amber-400';
  // Numbers
  if (/^(?:0[xX])?[\d]/.test(text)) return 'text-blue-400';
  // Keywords
  if (LUA_KEYWORDS.has(text)) {
    if (text === 'true' || text === 'false' || text === 'nil') return 'text-orange-400';
    return 'text-purple-400';
  }
  // Identifiers — default
  return '';
}

/**
 * Highlight Lua source code and return React elements.
 */
export function highlightLua(code: string): ReactNode[] {
  const elements: ReactNode[] = [];
  let lastIndex = 0;
  let key = 0;

  // We need to detect function calls (identifier immediately before '(')
  // by scanning the matches and peeking at the character after
  const matches = Array.from(code.matchAll(TOKEN_REGEX));

  for (const match of matches) {
    const start = match.index!;
    const text = match[0]!;

    // Push any plain text between tokens
    if (start > lastIndex) {
      elements.push(<span key={key++}>{code.slice(lastIndex, start)}</span>);
    }

    let cls = classifyToken(text);

    // If it's an unclassified identifier, check if it's a function call
    if (!cls && /^[a-zA-Z_]/.test(text)) {
      // Look ahead past whitespace for '(' or ':'
      const after = code.slice(start + text.length);
      if (/^\s*[:(]/.test(after)) {
        cls = 'text-sky-400';
      }
    }

    if (cls) {
      elements.push(<span key={key++} className={cls}>{text}</span>);
    } else {
      elements.push(<span key={key++}>{text}</span>);
    }

    lastIndex = start + text.length;
  }

  // Trailing plain text
  if (lastIndex < code.length) {
    elements.push(<span key={key++}>{code.slice(lastIndex)}</span>);
  }

  return elements;
}
