/**
 * iNav JavaScript-like expression → Logic Conditions transpiler.
 *
 * Compiles a small expression language into iNav Logic Condition slots, the
 * same idea as the Configurator's javascript-programming tab. Each binary
 * operation becomes one LC (operandA OP operandB); intermediate results feed
 * later LCs via the LC operand type. Statements:
 *
 *   gvar[0] = rc[6] > 1600           // sets global variable 0 when aux is high
 *   gvar[1] = (gvar[0] * 10) + 5
 *   rc[5] > 1500 && gvar[2] < 20     // a bare boolean result LC
 *
 * Supported: numbers, gvar[N], rc[N], parentheses, unary !, and the operators
 * + - * / %  > < >= <= == !=  && ||  (>=, <=, != are composed with NOT).
 * Output is reviewed in the Logic Conditions editor before it is written, so
 * the transpiler never talks to the FC directly.
 *
 * @module lib/inav/lc-transpiler
 */

import type { INavLogicCondition } from "@/lib/protocol/msp/msp-decoders-inav";

const MAX_LOGIC_CONDITIONS = 64;

// logicOperation_e codes (iNav firmware, verified).
const OP = {
  EQUAL: 1,
  GREATER_THAN: 2,
  LOWER_THAN: 3,
  AND: 7,
  OR: 8,
  NOT: 12,
  ADD: 14,
  SUB: 15,
  MUL: 16,
  DIV: 17,
  GVAR_SET: 18,
  MODULUS: 40,
} as const;

// logicOperandType_e codes.
const OPERAND = {
  VALUE: 0,
  RC_CHANNEL: 1,
  LC: 4,
  GVAR: 5,
} as const;

type Operand = { type: number; value: number };

// ── AST ───────────────────────────────────────────────────────

type Node =
  | { kind: "num"; value: number }
  | { kind: "gvar"; index: number }
  | { kind: "rc"; index: number }
  | { kind: "unary"; op: "!"; operand: Node }
  | { kind: "binary"; op: string; left: Node; right: Node };

type Statement =
  | { kind: "assign"; gvar: number; expr: Node }
  | { kind: "expr"; expr: Node };

// ── Lexer ─────────────────────────────────────────────────────

type Token = { t: string; v?: string; n?: number; pos: number };

function tokenize(line: string): Token[] {
  const tokens: Token[] = [];
  let i = 0;
  const two = ["&&", "||", "==", "!=", ">=", "<="];
  while (i < line.length) {
    const c = line[i];
    if (/\s/.test(c)) {
      i++;
      continue;
    }
    if (/[0-9.]/.test(c)) {
      let j = i;
      while (j < line.length && /[0-9.]/.test(line[j])) j++;
      const num = Number(line.slice(i, j));
      if (Number.isNaN(num)) throw new Error(`Invalid number at column ${i + 1}`);
      tokens.push({ t: "num", n: num, pos: i });
      i = j;
      continue;
    }
    if (/[a-zA-Z]/.test(c)) {
      let j = i;
      while (j < line.length && /[a-zA-Z]/.test(line[j])) j++;
      tokens.push({ t: "ident", v: line.slice(i, j), pos: i });
      i = j;
      continue;
    }
    const pair = line.slice(i, i + 2);
    if (two.includes(pair)) {
      tokens.push({ t: pair, pos: i });
      i += 2;
      continue;
    }
    if ("+-*/%<>=()[]!".includes(c)) {
      tokens.push({ t: c, pos: i });
      i++;
      continue;
    }
    throw new Error(`Unexpected character '${c}' at column ${i + 1}`);
  }
  return tokens;
}

// ── Parser (precedence climbing) ──────────────────────────────

class Parser {
  private pos = 0;
  constructor(private tokens: Token[]) {}

  private peek(): Token | undefined {
    return this.tokens[this.pos];
  }
  private next(): Token {
    const t = this.tokens[this.pos++];
    if (!t) throw new Error("Unexpected end of expression");
    return t;
  }
  private expect(t: string): Token {
    const tok = this.next();
    if (tok.t !== t) throw new Error(`Expected '${t}' at column ${tok.pos + 1}`);
    return tok;
  }
  atEnd(): boolean {
    return this.pos >= this.tokens.length;
  }

  parseStatement(): Statement {
    // gvar[N] = expr  |  bare expr
    const t = this.peek();
    if (t?.t === "ident" && t.v === "gvar") {
      const save = this.pos;
      this.next(); // gvar
      if (this.peek()?.t === "[") {
        this.next();
        const idx = this.expect("num").n ?? 0;
        this.expect("]");
        if (this.peek()?.t === "=") {
          this.next();
          const expr = this.parseExpr();
          return { kind: "assign", gvar: idx, expr };
        }
      }
      this.pos = save; // not an assignment — parse as a bare expression
    }
    return { kind: "expr", expr: this.parseExpr() };
  }

  private parseExpr(): Node {
    return this.parseBinary(0);
  }

  // Precedence levels (low → high).
  private static readonly LEVELS: string[][] = [
    ["||"],
    ["&&"],
    ["==", "!="],
    [">", "<", ">=", "<="],
    ["+", "-"],
    ["*", "/", "%"],
  ];

  private parseBinary(level: number): Node {
    if (level >= Parser.LEVELS.length) return this.parseUnary();
    let left = this.parseBinary(level + 1);
    while (this.peek() && Parser.LEVELS[level].includes(this.peek()!.t)) {
      const op = this.next().t;
      const right = this.parseBinary(level + 1);
      left = { kind: "binary", op, left, right };
    }
    return left;
  }

  private parseUnary(): Node {
    if (this.peek()?.t === "!") {
      this.next();
      return { kind: "unary", op: "!", operand: this.parseUnary() };
    }
    return this.parsePrimary();
  }

  private parsePrimary(): Node {
    const t = this.next();
    if (t.t === "num") return { kind: "num", value: t.n ?? 0 };
    if (t.t === "(") {
      const e = this.parseExpr();
      this.expect(")");
      return e;
    }
    if (t.t === "ident" && (t.v === "gvar" || t.v === "rc")) {
      this.expect("[");
      const idx = this.expect("num").n ?? 0;
      this.expect("]");
      return t.v === "gvar" ? { kind: "gvar", index: idx } : { kind: "rc", index: idx };
    }
    throw new Error(`Unexpected token at column ${t.pos + 1}`);
  }
}

// ── Code generator ────────────────────────────────────────────

function emptyLc(): INavLogicCondition {
  return { enabled: false, activatorId: -1, operation: 0, operandAType: 0, operandAValue: 0, operandBType: 0, operandBValue: 0, flags: 0 };
}

class CodeGen {
  conditions: INavLogicCondition[] = [];

  private alloc(operation: number, a: Operand, b: Operand): Operand {
    if (this.conditions.length >= MAX_LOGIC_CONDITIONS) {
      throw new Error(`Program needs more than ${MAX_LOGIC_CONDITIONS} logic conditions`);
    }
    const idx = this.conditions.length;
    this.conditions.push({
      enabled: true,
      activatorId: -1,
      operation,
      operandAType: a.type,
      operandAValue: a.value,
      operandBType: b.type,
      operandBValue: b.value,
      flags: 0,
    });
    return { type: OPERAND.LC, value: idx };
  }

  compileNode(node: Node): Operand {
    switch (node.kind) {
      case "num":
        return { type: OPERAND.VALUE, value: Math.trunc(node.value) };
      case "gvar":
        return { type: OPERAND.GVAR, value: node.index };
      case "rc":
        return { type: OPERAND.RC_CHANNEL, value: node.index };
      case "unary": // !x  →  NOT(x)
        return this.alloc(OP.NOT, this.compileNode(node.operand), { type: OPERAND.VALUE, value: 0 });
      case "binary": {
        const a = this.compileNode(node.left);
        const b = this.compileNode(node.right);
        switch (node.op) {
          case "+": return this.alloc(OP.ADD, a, b);
          case "-": return this.alloc(OP.SUB, a, b);
          case "*": return this.alloc(OP.MUL, a, b);
          case "/": return this.alloc(OP.DIV, a, b);
          case "%": return this.alloc(OP.MODULUS, a, b);
          case ">": return this.alloc(OP.GREATER_THAN, a, b);
          case "<": return this.alloc(OP.LOWER_THAN, a, b);
          case "==": return this.alloc(OP.EQUAL, a, b);
          case "&&": return this.alloc(OP.AND, a, b);
          case "||": return this.alloc(OP.OR, a, b);
          case ">=": return this.not(this.alloc(OP.LOWER_THAN, a, b)); // a>=b ≡ !(a<b)
          case "<=": return this.not(this.alloc(OP.GREATER_THAN, a, b)); // a<=b ≡ !(a>b)
          case "!=": return this.not(this.alloc(OP.EQUAL, a, b)); // a!=b ≡ !(a==b)
          default:
            throw new Error(`Unsupported operator '${node.op}'`);
        }
      }
    }
  }

  private not(op: Operand): Operand {
    return this.alloc(OP.NOT, op, { type: OPERAND.VALUE, value: 0 });
  }

  compileStatement(stmt: Statement): void {
    if (stmt.kind === "assign") {
      const value = this.compileNode(stmt.expr);
      // GVAR_SET: operandA = gvar index (VALUE), operandB = value to store.
      this.alloc(OP.GVAR_SET, { type: OPERAND.VALUE, value: stmt.gvar }, value);
    } else {
      this.compileNode(stmt.expr);
    }
  }
}

// ── Public API ────────────────────────────────────────────────

export interface CompiledProgram {
  conditions: INavLogicCondition[];
  error?: string;
  errorLine?: number;
}

/**
 * Compile a program (one statement per non-empty line; `//` line comments
 * allowed) into Logic Condition slots, filling unused slots with disabled
 * conditions up to MAX_LOGIC_CONDITIONS.
 */
export function compileToLogicConditions(source: string): CompiledProgram {
  const gen = new CodeGen();
  const lines = source.split("\n");
  try {
    for (let ln = 0; ln < lines.length; ln++) {
      const raw = lines[ln].replace(/\/\/.*$/, "").trim();
      if (!raw) continue;
      const tokens = tokenize(raw);
      const parser = new Parser(tokens);
      const stmt = parser.parseStatement();
      if (!parser.atEnd()) throw new Error("Unexpected trailing tokens");
      gen.compileStatement(stmt);
    }
  } catch (e) {
    return { conditions: [], error: e instanceof Error ? e.message : String(e) };
  }
  const conditions = gen.conditions.slice();
  while (conditions.length < MAX_LOGIC_CONDITIONS) conditions.push(emptyLc());
  return { conditions };
}
