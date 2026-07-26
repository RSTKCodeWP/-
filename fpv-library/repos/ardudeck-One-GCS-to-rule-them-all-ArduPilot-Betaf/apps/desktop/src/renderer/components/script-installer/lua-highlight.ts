/**
 * Minimal Lua syntax highlighter.
 *
 * Regex-based tokenizer - no parser - so it's small (no library dep) and
 * fast enough to highlight the full ArduDeck script (a few hundred lines)
 * on every render. Single-pass over the whole source so multi-line tokens
 * (block strings/comments) are handled correctly.
 *
 * Output is a flat array of {kind, text} - the renderer maps each kind to
 * a Tailwind text color. Rendering pre-line is left to the caller.
 */

export type TokenKind =
  | 'comment'
  | 'string'
  | 'number'
  | 'keyword'
  | 'builtin'
  | 'identifier'
  | 'operator'
  | 'whitespace'
  | 'plain';

export interface Token {
  kind: TokenKind;
  text: string;
}

const KEYWORDS = new Set([
  'and', 'break', 'do', 'else', 'elseif', 'end', 'false', 'for', 'function',
  'goto', 'if', 'in', 'local', 'nil', 'not', 'or', 'repeat', 'return', 'then',
  'true', 'until', 'while',
]);

const BUILTINS = new Set([
  'string', 'table', 'math', 'io', 'os', 'ipairs', 'pairs', 'print', 'type',
  'tonumber', 'tostring', 'pcall', 'xpcall', 'error', 'assert', 'select',
  'setmetatable', 'getmetatable', 'rawequal', 'rawget', 'rawset', 'next',
  'unpack', 'require',
  // ArduPilot Lua API namespaces
  'ahrs', 'gcs', 'mavlink', 'vehicle', 'gps', 'battery', 'param', 'serial',
  'arming', 'mission', 'rc', 'SRV_Channels', 'Location', 'Vector3f',
  'millis', 'micros',
]);

/**
 * Tokenize Lua source. Walks the whole string once with a fixed set of
 * patterns evaluated in priority order at each position.
 */
export function tokenizeLua(source: string): Token[] {
  const out: Token[] = [];
  let i = 0;
  const n = source.length;

  while (i < n) {
    const ch = source[i]!;
    const next = source[i + 1];

    // Block comment: --[[ ... ]] (greedy match to ]])
    if (ch === '-' && next === '-' && source[i + 2] === '[' && source[i + 3] === '[') {
      const end = source.indexOf(']]', i + 4);
      const stop = end < 0 ? n : end + 2;
      out.push({ kind: 'comment', text: source.slice(i, stop) });
      i = stop;
      continue;
    }

    // Line comment: -- ... \n
    if (ch === '-' && next === '-') {
      let j = i + 2;
      while (j < n && source[j] !== '\n') j++;
      out.push({ kind: 'comment', text: source.slice(i, j) });
      i = j;
      continue;
    }

    // Block string: [[ ... ]]
    if (ch === '[' && next === '[') {
      const end = source.indexOf(']]', i + 2);
      const stop = end < 0 ? n : end + 2;
      out.push({ kind: 'string', text: source.slice(i, stop) });
      i = stop;
      continue;
    }

    // Single-quoted or double-quoted string with escape handling
    if (ch === '"' || ch === "'") {
      const quote = ch;
      let j = i + 1;
      while (j < n && source[j] !== quote) {
        if (source[j] === '\\' && j + 1 < n) j += 2;
        else if (source[j] === '\n') break;
        else j++;
      }
      const stop = j < n && source[j] === quote ? j + 1 : j;
      out.push({ kind: 'string', text: source.slice(i, stop) });
      i = stop;
      continue;
    }

    // Number: 0x... or decimal/float
    if (isDigit(ch) || (ch === '.' && next !== undefined && isDigit(next))) {
      let j = i;
      if (ch === '0' && (next === 'x' || next === 'X')) {
        j += 2;
        while (j < n && /[0-9a-fA-F]/.test(source[j]!)) j++;
      } else {
        while (j < n && isDigit(source[j]!)) j++;
        if (source[j] === '.') {
          j++;
          while (j < n && isDigit(source[j]!)) j++;
        }
        if (source[j] === 'e' || source[j] === 'E') {
          j++;
          if (source[j] === '+' || source[j] === '-') j++;
          while (j < n && isDigit(source[j]!)) j++;
        }
      }
      out.push({ kind: 'number', text: source.slice(i, j) });
      i = j;
      continue;
    }

    // Identifier / keyword / builtin
    if (isIdentStart(ch)) {
      let j = i + 1;
      while (j < n && isIdentCont(source[j]!)) j++;
      const text = source.slice(i, j);
      const kind: TokenKind = KEYWORDS.has(text) ? 'keyword'
        : BUILTINS.has(text) ? 'builtin'
        : 'identifier';
      out.push({ kind, text });
      i = j;
      continue;
    }

    // Whitespace (incl newlines) - we keep them as their own tokens so the
    // renderer can split per-line cleanly.
    if (ch === ' ' || ch === '\t' || ch === '\n' || ch === '\r') {
      let j = i + 1;
      while (j < n && (source[j] === ' ' || source[j] === '\t' || source[j] === '\n' || source[j] === '\r')) j++;
      out.push({ kind: 'whitespace', text: source.slice(i, j) });
      i = j;
      continue;
    }

    // Operator / punctuation - single char fallback
    out.push({ kind: 'operator', text: ch });
    i++;
  }

  return out;
}

/**
 * Group tokens by line so the caller can render line-by-line with line numbers.
 * Tokens that span newlines (e.g. block comments, whitespace) get split.
 */
export function tokensByLine(tokens: Token[]): Token[][] {
  const lines: Token[][] = [[]];
  for (const tok of tokens) {
    const parts = tok.text.split('\n');
    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]!;
      if (part.length > 0) {
        lines[lines.length - 1]!.push({ kind: tok.kind, text: part });
      }
      if (i < parts.length - 1) {
        lines.push([]);
      }
    }
  }
  return lines;
}

/**
 * Tailwind classes for each kind. The `light:` variants give readable contrast
 * on the light theme - dark theme keeps the brighter pastel palette.
 */
export const TOKEN_CLASS: Record<TokenKind, string> = {
  comment:    'text-gray-500 italic',
  string:     'text-emerald-600 dark:text-emerald-300',
  number:     'text-orange-600 dark:text-orange-300',
  keyword:    'text-violet-700 dark:text-violet-300 font-medium',
  builtin:    'text-cyan-700 dark:text-cyan-300',
  identifier: 'text-content',
  operator:   'text-content-secondary',
  whitespace: '',
  plain:      'text-content',
};

function isDigit(ch: string): boolean {
  return ch >= '0' && ch <= '9';
}
function isIdentStart(ch: string): boolean {
  return (ch >= 'a' && ch <= 'z') || (ch >= 'A' && ch <= 'Z') || ch === '_';
}
function isIdentCont(ch: string): boolean {
  return isIdentStart(ch) || isDigit(ch);
}
