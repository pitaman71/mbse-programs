/**
 * Prints Python trees as Python source text, in one fixed layout.
 *
 * The layout: four spaces per level, one statement per line, `elif` for an `orelse` that is one `If`, and, as PEP 8
 * has it, two blank lines around top-level function and class definitions and one around nested ones. Parentheses
 * written in the tree are printed; those a tree built by hand needs are added, by the precedence of Python's grammar,
 * which also decides where an assignment expression (`:=`), a `yield` or a lambda must be parenthesized. The printer
 * assumes a valid tree: versions validate before they print.
 */

import type { Node } from "../Framework/Syntax.js";
import * as S from "./Syntax.js";

const INDENT = "    ";

// Precedence: higher binds tighter. An operand is parenthesized when its precedence is below what its place needs.
const YIELD = -1, TUPLE = 0, NAMED = 1, EXPR = 2, OR = 3, AND = 4, NOT = 5, CMP = 6, BOR = 7, BXOR = 8, BAND = 9,
  SHIFT = 10, SUM = 11, TERM = 12, FACTOR = 13, POWER = 14, AWAIT = 15, PRIMARY = 16, ATOM = 17;
const BINARY: Record<string, number> = {
  "|": BOR, "^": BXOR, "&": BAND, "<<": SHIFT, ">>": SHIFT, "+": SUM, "-": SUM, "*": TERM, "@": TERM, "/": TERM,
  "//": TERM, "%": TERM, "**": POWER,
};
const PRECEDENCE = new Map<Function, number>([
  [S.Yield, YIELD], [S.YieldFrom, YIELD], [S.NamedExpr, NAMED], [S.Lambda, EXPR], [S.IfExp, EXPR], [S.Compare, CMP],
  [S.Await, AWAIT], [S.Attribute, PRIMARY], [S.Subscript, PRIMARY], [S.Call, PRIMARY], [S.Starred, PRIMARY],
]);

function precedence(node: any): number {
  if (node instanceof S.BinOp) return BINARY[node.op as string] as number;
  if (node instanceof S.UnaryOp) return node.op === "not" ? NOT : FACTOR;
  if (node instanceof S.BoolOp) return node.op === "and" ? AND : OR;
  if (node instanceof S.Tuple) return node.elts.length > 0 ? TUPLE : ATOM;
  return PRECEDENCE.get(node.constructor) ?? ATOM;
}

/** The code of an expression's text: without comments, and without whitespace outside its strings. */
function code(text: string): string {
  const out: string[] = [];
  let i = 0;
  let quote: string | null = null;
  while (i < text.length) {
    const ch = text[i] as string;
    if (quote !== null) {
      if (ch === "\\") {
        out.push(text.slice(i, i + 2));
        i += 2;
        continue;
      }
      if (text.startsWith(quote, i)) {
        out.push(quote);
        i += quote.length;
        quote = null;
        continue;
      }
      out.push(ch);
    } else if (ch === "#") {
      while (i < text.length && text[i] !== "\n") i++;
      continue;
    } else if (ch === "'" || ch === "\"") {
      const three = text.slice(i, i + 3);
      quote = three === "'''" || three === "\"\"\"" ? three : ch;
      out.push(quote);
      i += quote.length;
      continue;
    } else if (!" \t\n\r\f\v".includes(ch)) {
      out.push(ch);
    }
    i++;
  }
  return out.join("");
}

function definition(node: Node): boolean {
  return node instanceof S.FunctionDef || node instanceof S.AsyncFunctionDef || node instanceof S.ClassDef;
}

const is = <T>(kinds: Function[], node: unknown): node is T => kinds.some((k) => node instanceof k);

type Text = (self: Printer, node: any) => string;
type Lines = (self: Printer, node: any, level: number) => string[];

/** Prints a module as a file, and any other node as the text it stands for: a statement as its lines, an expression, a
 * pattern or a part (an `Arg`, a `Keyword`, an `Alias`, ...) as its text. */
export class Printer {
  static SIMPLE = new Map<Function, Text>();
  static STATEMENTS = new Map<Function, Lines>();
  static TEXTS = new Map<Function, Text>();
  static PATTERNS = new Map<Function, Text>();

  print(node: Node): string {
    if (node instanceof S.Module) return this.block(node.body, 0, true).map((line) => line + "\n").join("");
    if (is([S.Statement, S.ExceptHandler, S.MatchCase], node)) return this.statement(node, 0).join("\n");
    return this.text(node);
  }

  // Statements

  /** The lines of a list of statements at `level`, with blank lines around definitions: two at the top level, one
   * elsewhere. Comments directly before a definition stay with it. */
  block(statements: any[], level: number, top = false): string[] {
    const lines: string[] = [];
    const blank = top ? 2 : 1;
    let afterDefinition = false;
    statements.forEach((statement, i) => {
      if (statement instanceof S.Comment && statement.trailing && lines.length > 0) {
        lines[lines.length - 1] += `  #${statement.text}`;
        return;
      }
      const starts = (definition(statement) && !Printer.led(statements, i))
        || (statement instanceof S.Comment && Printer.leads(statements, i));
      if (lines.length > 0 && (afterDefinition || starts)) lines.push(...Array<string>(blank).fill(""));
      lines.push(...this.statement(statement, level));
      afterDefinition = definition(statement);
    });
    return lines;
  }

  /** Whether the comment `statements[i]` starts the comments directly before a definition. */
  static leads(statements: Node[], i: number): boolean {
    let j = i;
    while (j < statements.length && statements[j] instanceof S.Comment) j++;
    const previous = statements[i - 1];
    return j < statements.length && definition(statements[j] as Node)
      && (i === 0 || !(previous instanceof S.Comment) || previous.trailing);
  }

  /** Whether `statements[i]` follows a comment that leads it: blank lines go before that comment. */
  static led(statements: Node[], i: number): boolean {
    const previous = statements[i - 1];
    return i > 0 && previous instanceof S.Comment && !previous.trailing;
  }

  /** `header:` and the indented body, a leading trailing comment on the header's line. */
  suite(header: string, body: any[], level: number): string[] {
    const lines = [INDENT.repeat(level) + header + ":"];
    const first = body[0];
    if (first instanceof S.Comment && first.trailing) {
      lines[0] += `  #${first.text}`;
      body = body.slice(1);
    }
    return [...lines, ...this.block(body, level + 1)];
  }

  statement(node: any, level: number): string[] {
    const method = Printer.STATEMENTS.get(node.constructor);
    if (method !== undefined) return method(this, node, level);
    return [INDENT.repeat(level) + (Printer.SIMPLE.get(node.constructor) as Text)(this, node)];
  }

  orelse(orelse: any[], level: number): string[] {
    if (orelse.length === 0) return [];
    const only = orelse[0];
    if (orelse.length === 1 && only instanceof S.If) {
      return [...this.suite(`elif ${this.e(only.test, NAMED)}`, only.body, level),
        ...this.orelse(only.orelse, level)];
    }
    return this.suite("else", orelse, level);
  }

  handler(node: any, level: number, star = false): string[] {
    let header = star ? "except*" : "except";
    if (node.type !== null) header += ` ${this.e(node.type, node.name === null ? TUPLE : EXPR)}`;
    if (node.name !== null) header += ` as ${this.text(node.name)}`;
    return this.suite(header, node.body, level);
  }

  case(node: any, level: number): string[] {
    const guard = node.guard === null ? "" : ` if ${this.e(node.guard, NAMED)}`;
    return this.suite(`case ${this.p(node.pattern, true)}${guard}`, node.body, level);
  }

  decorators(node: S.FunctionDef | S.AsyncFunctionDef | S.ClassDef, level: number): string[] {
    return node.decorator_list.map((d) => `${INDENT.repeat(level)}@${this.e(d, NAMED)}`);
  }

  typeParams(params: Node[]): string {
    return params.length > 0 ? `[${params.map((p) => this.text(p)).join(", ")}]` : "";
  }

  // Expressions

  /** `node`'s text, parenthesized if it binds less than its place needs. */
  e(node: any, needed: number): string {
    const text = this.text(node);
    return precedence(node) < needed ? `(${text})` : text;
  }

  /** A statement's value, which may be a tuple and, at `YIELD`, a `yield`, but not an assignment expression. */
  value(node: any, needed = YIELD): string {
    return node instanceof S.NamedExpr ? `(${this.text(node)})` : this.e(node, needed);
  }

  text(node: any): string {
    return (Printer.TEXTS.get(node.constructor) as Text)(this, node);
  }

  field(node: S.FormattedValue | S.Interpolation): string {
    let value = this.e(node.value, YIELD);
    if (node.value instanceof S.Lambda || node.value instanceof S.NamedExpr) value = `(${value})`; // their colons
    let text = node.text;
    if (text !== null && code(text) !== code(value) + (node.debug ? "=" : "")) text = null; // it no longer spells it
    if (text === null) text = (value.startsWith("{") ? " " + value : value) + (node.debug ? "=" : "");
    const conversion = node.conversion === null ? "" : `!${node.conversion}`;
    const spec = node.format_spec === null ? "" : ":" + node.format_spec.values.map((v) => this.text(v)).join("");
    return "{" + text + conversion + spec + "}";
  }

  comprehensions(generators: any[]): string {
    return generators.map((g) => " " + this.text(g)).join("");
  }

  // Patterns

  /** A pattern's text. An open sequence, `case a, b:`, is written only where `openSequence` allows it. */
  p(node: any, openSequence = false): string {
    if (node instanceof S.MatchSequence && node.delimiters === null && !openSequence) {
      return node.patterns.length > 0 ? `(${this.sequence(node)})` : "()";
    }
    return (Printer.PATTERNS.get(node.constructor) as Text)(this, node);
  }

  sequence(node: S.MatchSequence): string {
    return node.patterns.map((p) => this.p(p)).join(", ") + (node.patterns.length === 1 ? "," : "");
  }
}

const e = (self: Printer, node: any, needed: number): string => self.e(node, needed);
const joined: Text = (self, node: S.JoinedStr | S.TemplateStr) =>
  `${node.prefix}${node.quote}${node.values.map((v) => self.text(v)).join("")}${node.quote}`;
const loop: Lines = (self, node: S.For | S.AsyncFor, level) => {
  const keyword = node instanceof S.AsyncFor ? "async for" : "for";
  const header = `${keyword} ${e(self, node.target, TUPLE)} in ${self.value(node.iter, TUPLE)}`;
  return [...self.suite(header, node.body, level), ...(node.orelse.length > 0 ? self.suite("else", node.orelse, level) : [])];
};
const tryLines: Lines = (self, node: S.Try | S.TryStar, level) => {
  const lines = self.suite("try", node.body, level);
  for (const handler of node.handlers) lines.push(...self.handler(handler, level, node instanceof S.TryStar));
  if (node.orelse.length > 0) lines.push(...self.suite("else", node.orelse, level));
  if (node.finalbody.length > 0) lines.push(...self.suite("finally", node.finalbody, level));
  return lines;
};
const withLines: Lines = (self, node: S.With | S.AsyncWith, level) => {
  const keyword = node instanceof S.AsyncWith ? "async with" : "with";
  return self.suite(`${keyword} ${node.items.map((i) => self.text(i)).join(", ")}`, node.body, level);
};
const functionLines: Lines = (self, node: S.FunctionDef | S.AsyncFunctionDef, level) => {
  const keyword = node instanceof S.AsyncFunctionDef ? "async def" : "def";
  const returns = node.returns === null ? "" : ` -> ${e(self, node.returns, EXPR)}`;
  const name = self.text(node.name) + self.typeParams(node.type_params);
  return [...self.decorators(node, level), ...self.suite(`${keyword} ${name}(${self.text(node.args)})${returns}`, node.body, level)];
};
const typeVar: Text = (self, node: S.TypeVar | S.ParamSpec | S.TypeVarTuple) => {
  let text = (node instanceof S.ParamSpec ? "**" : node instanceof S.TypeVarTuple ? "*" : "") + self.text(node.name);
  if (node instanceof S.TypeVar && node.bound !== null) text += `: ${e(self, node.bound, EXPR)}`;
  if (node.default_value !== null) text += ` = ${e(self, node.default_value, EXPR)}`;
  return text;
};
const elements = (self: Printer, elts: any[]): string => elts.map((x) => e(self, x, NAMED)).join(", ");

Printer.SIMPLE = new Map<Function, Text>([
  [S.Comment, (_self, node: S.Comment) => `#${node.text}`],
  [S.Expr, (self, node: S.Expr) => self.value(node.value)],
  [S.Assign, (self, node: S.Assign) => [...node.targets.map((t) => e(self, t, TUPLE)), self.value(node.value)].join(" = ")],
  [S.AugAssign, (self, node: S.AugAssign) => `${e(self, node.target, TUPLE)} ${node.op}= ${self.value(node.value)}`],
  [S.AnnAssign, (self, node: S.AnnAssign) => `${e(self, node.target, PRIMARY)}: ${e(self, node.annotation, EXPR)}`
    + (node.value === null ? "" : ` = ${self.value(node.value)}`)],
  [S.Assert, (self, node: S.Assert) => `assert ${e(self, node.test, EXPR)}`
    + (node.msg === null ? "" : `, ${e(self, node.msg, EXPR)}`)],
  [S.Pass, () => "pass"], [S.Break, () => "break"], [S.Continue, () => "continue"],
  [S.Delete, (self, node: S.Delete) => "del " + node.targets.map((t) => e(self, t, BOR)).join(", ")],
  [S.Return, (self, node: S.Return) => node.value === null ? "return" : `return ${self.value(node.value, TUPLE)}`],
  [S.Raise, (self, node: S.Raise) => "raise" + (node.exc === null ? "" : ` ${e(self, node.exc, EXPR)}`)
    + (node.cause === null ? "" : ` from ${e(self, node.cause, EXPR)}`)],
  [S.Import, (self, node: S.Import) => (node.is_lazy ? "lazy " : "") + "import "
    + node.names.map((a) => self.text(a)).join(", ")],
  [S.ImportFrom, (self, node: S.ImportFrom) => {
    const module = ".".repeat(Number(node.level ?? 0n)) + (node.module === null ? "" : self.text(node.module));
    return `${node.is_lazy ? "lazy " : ""}from ${module} import ${node.names.map((a) => self.text(a)).join(", ")}`;
  }],
  [S.TypeAlias, (self, node: S.TypeAlias) =>
    `type ${self.text(node.name)}${self.typeParams(node.type_params)} = ${e(self, node.value, EXPR)}`],
  [S.Global, (self, node: S.Global) => "global " + node.names.map((n) => self.text(n)).join(", ")],
  [S.Nonlocal, (self, node: S.Nonlocal) => "nonlocal " + node.names.map((n) => self.text(n)).join(", ")],
]);

Printer.STATEMENTS = new Map<Function, Lines>([
  [S.If, (self, node: S.If, level) => [...self.suite(`if ${e(self, node.test, NAMED)}`, node.body, level),
    ...self.orelse(node.orelse, level)]],
  [S.While, (self, node: S.While, level) => [...self.suite(`while ${e(self, node.test, NAMED)}`, node.body, level),
    ...(node.orelse.length > 0 ? self.suite("else", node.orelse, level) : [])]],
  [S.For, loop], [S.AsyncFor, loop], [S.Try, tryLines], [S.TryStar, tryLines], [S.With, withLines],
  [S.AsyncWith, withLines],
  [S.Match, (self, node: S.Match, level) => [`${INDENT.repeat(level)}match ${e(self, node.subject, TUPLE)}:`,
    ...node.cases.flatMap((c) => self.case(c, level + 1))]],
  [S.FunctionDef, functionLines], [S.AsyncFunctionDef, functionLines],
  [S.ClassDef, (self, node: S.ClassDef, level) => {
    const args = [...node.bases.map((b) => e(self, b, NAMED)), ...node.keywords.map((k) => self.text(k))];
    let header = `class ${self.text(node.name)}${self.typeParams(node.type_params)}`;
    if (args.length > 0) header += `(${args.join(", ")})`;
    return [...self.decorators(node, level), ...self.suite(header, node.body, level)];
  }],
  [S.ExceptHandler, (self, node: S.ExceptHandler, level) => self.handler(node, level)],
  [S.MatchCase, (self, node: S.MatchCase, level) => self.case(node, level)],
]);

Printer.TEXTS = new Map<Function, Text>([
  [S.Identifier, (_self, node: S.Identifier) => node.spelling as string],
  [S.DottedName, (self, node: S.DottedName) => node.names.map((n) => self.text(n)).join(".")],
  [S.Name, (self, node: S.Name) => self.text(node.id)],
  [S.Constant, (_self, node: S.Constant) => node.spelling as string],
  [S.ConcatenatedString, (self, node: S.ConcatenatedString) => node.values.map((v) => self.text(v)).join(" ")],
  [S.JoinedStr, joined], [S.TemplateStr, joined],
  [S.StringText, (_self, node: S.StringText) => node.spelling as string],
  [S.FormattedValue, (self, node: S.FormattedValue) => self.field(node)],
  [S.Interpolation, (self, node: S.Interpolation) => self.field(node)],
  [S.FormatSpec, (self, node: S.FormatSpec) => ":" + node.values.map((v) => self.text(v)).join("")],
  [S.Parenthesized, (self, node: S.Parenthesized) => {
    const value = node.value;
    if (value instanceof S.Tuple && value.elts.length > 0) {
      return `(${elements(self, value.elts)}${value.elts.length === 1 ? "," : ""})`;
    }
    return `(${e(self, value, YIELD)})`;
  }],
  [S.Tuple, (self, node: S.Tuple) => {
    if (node.elts.length === 0) return "()";
    if (node.elts.length === 1) return e(self, node.elts[0] as Node, EXPR) + ",";
    return node.elts.map((x) => e(self, x, EXPR)).join(", ");
  }],
  [S.List, (self, node: S.List) => `[${elements(self, node.elts)}]`],
  [S.Set, (self, node: S.Set) => `{${elements(self, node.elts)}}`],
  [S.DictItem, (self, node: S.DictItem) => node.key === null ? `**${e(self, node.value, BOR)}`
    : `${e(self, node.key, EXPR)}: ${e(self, node.value, EXPR)}`],
  [S.Dict, (self, node: S.Dict) => `{${node.items.map((i) => self.text(i)).join(", ")}}`],
  [S.Comprehension, (self, node: S.Comprehension) =>
    `${node.is_async ? "async " : ""}for ${e(self, node.target, TUPLE)} in ${e(self, node.iter, OR)}`
    + node.ifs.map((i) => ` if ${e(self, i, OR)}`).join("")],
  [S.ListComp, (self, node: S.ListComp) => `[${e(self, node.elt, NAMED)}${self.comprehensions(node.generators)}]`],
  [S.SetComp, (self, node: S.SetComp) => `{${e(self, node.elt, NAMED)}${self.comprehensions(node.generators)}}`],
  [S.DictComp, (self, node: S.DictComp) => {
    const item = node.value === null ? `**${e(self, node.key, BOR)}` : `${e(self, node.key, EXPR)}: ${e(self, node.value, EXPR)}`;
    return `{${item}${self.comprehensions(node.generators)}}`;
  }],
  [S.GeneratorExp, (self, node: S.GeneratorExp) => `(${e(self, node.elt, NAMED)}${self.comprehensions(node.generators)})`],
  [S.Yield, (self, node: S.Yield) => node.value === null ? "yield" : `yield ${e(self, node.value, TUPLE)}`],
  [S.YieldFrom, (self, node: S.YieldFrom) => `yield from ${e(self, node.value, EXPR)}`],
  [S.Attribute, (self, node: S.Attribute) => {
    let value = e(self, node.value, PRIMARY);
    if (node.value instanceof S.Constant && /^[0-9]+$/.test(value.replaceAll("_", ""))) value = `(${value})`; // `1.real`
    return `${value}.${self.text(node.attr)}`;
  }],
  [S.Subscript, (self, node: S.Subscript) => {
    const index = node.slice;
    const inner = index instanceof S.Tuple && index.elts.length > 0
      ? elements(self, index.elts) + (index.elts.length === 1 ? "," : "") : e(self, index, NAMED);
    return `${e(self, node.value, PRIMARY)}[${inner}]`;
  }],
  [S.Slice, (self, node: S.Slice) => {
    const text = [node.lower, node.upper].map((p) => p === null ? "" : e(self, p, EXPR)).join(":");
    return node.step === null ? text : `${text}:${e(self, node.step, EXPR)}`;
  }],
  [S.Keyword, (self, node: S.Keyword) => node.arg === null ? `**${e(self, node.value, EXPR)}`
    : `${self.text(node.arg)}=${e(self, node.value, EXPR)}`],
  [S.Call, (self, node: S.Call) => {
    const only = node.args[0];
    if (node.args.length === 1 && node.keywords.length === 0 && only instanceof S.GeneratorExp) {
      return `${e(self, node.func, PRIMARY)}(${e(self, only.elt, NAMED)}${self.comprehensions(only.generators)})`;
    }
    const args = [...node.args.map((a) => e(self, a, NAMED)), ...node.keywords.map((k) => self.text(k))];
    return `${e(self, node.func, PRIMARY)}(${args.join(", ")})`;
  }],
  [S.Starred, (self, node: S.Starred) => `*${e(self, node.value, BOR)}`],
  [S.Await, (self, node: S.Await) => `await ${e(self, node.value, PRIMARY)}`],
  [S.UnaryOp, (self, node: S.UnaryOp) => node.op === "not" ? `not ${e(self, node.operand, NOT)}`
    : `${node.op}${e(self, node.operand, FACTOR)}`],
  [S.BinOp, (self, node: S.BinOp) => {
    if (node.op === "**") return `${e(self, node.left, AWAIT)} ** ${e(self, node.right, FACTOR)}`;
    const level = BINARY[node.op as string] as number;
    return `${e(self, node.left, level)} ${node.op} ${e(self, node.right, level + 1)}`;
  }],
  [S.Compare, (self, node: S.Compare) => e(self, node.left, BOR)
    + node.comparisons.map((c) => ` ${c.op} ${e(self, c.comparator, BOR)}`).join("")],
  [S.Comparison, (self, node: S.Comparison) => `${node.op} ${e(self, node.comparator, BOR)}`],
  [S.BoolOp, (self, node: S.BoolOp) => node.values.map((v) => e(self, v, node.op === "and" ? NOT : AND)).join(` ${node.op} `)],
  [S.IfExp, (self, node: S.IfExp) => `${e(self, node.body, OR)} if ${e(self, node.test, OR)} else ${e(self, node.orelse, EXPR)}`],
  [S.Lambda, (self, node: S.Lambda) => {
    const args = self.text(node.args);
    return `lambda${args ? " " : ""}${args}: ${e(self, node.body, EXPR)}`;
  }],
  [S.NamedExpr, (self, node: S.NamedExpr) => `${self.text(node.target)} := ${e(self, node.value, EXPR)}`],
  [S.Arg, (self, node: S.Arg) => {
    let text = self.text(node.arg);
    if (node.annotation !== null) text += `: ${e(self, node.annotation, EXPR)}`;
    if (node.default_value !== null) {
      text += node.annotation !== null ? ` = ${e(self, node.default_value, EXPR)}` : `=${e(self, node.default_value, EXPR)}`;
    }
    return text;
  }],
  [S.Arguments, (self, node: S.Arguments) => {
    const parts = node.posonlyargs.map((a) => self.text(a));
    if (node.posonlyargs.length > 0) parts.push("/");
    parts.push(...node.args.map((a) => self.text(a)));
    if (node.vararg !== null) parts.push("*" + self.text(node.vararg));
    else if (node.kwonlyargs.length > 0) parts.push("*");
    parts.push(...node.kwonlyargs.map((a) => self.text(a)));
    if (node.kwarg !== null) parts.push("**" + self.text(node.kwarg));
    return parts.join(", ");
  }],
  [S.Alias, (self, node: S.Alias) => node.name === null ? "*"
    : self.text(node.name) + (node.asname === null ? "" : ` as ${self.text(node.asname)}`)],
  [S.WithItem, (self, node: S.WithItem) => {
    const text = e(self, node.context_expr, EXPR);
    return node.optional_vars === null ? text : `${text} as ${e(self, node.optional_vars, PRIMARY)}`;
  }],
  [S.TypeVar, typeVar], [S.ParamSpec, typeVar], [S.TypeVarTuple, typeVar],
]);

Printer.PATTERNS = new Map<Function, Text>([
  [S.MatchValue, (self, node: S.MatchValue) => self.text(node.value)],
  [S.MatchSingleton, (_self, node: S.MatchSingleton) => node.value as string],
  [S.MatchSequence, (self, node: S.MatchSequence) => {
    if (node.delimiters === "[]") return `[${node.patterns.map((p) => self.p(p)).join(", ")}]`;
    if (node.delimiters === "()" || node.patterns.length === 0) return `(${self.sequence(node)})`;
    return self.sequence(node);
  }],
  [S.MatchMapping, (self, node: S.MatchMapping) => {
    const items = node.keys.map((k, i) => `${self.text(k)}: ${self.p(node.patterns[i] as Node)}`);
    if (node.rest !== null) items.push(`**${self.text(node.rest)}`);
    return `{${items.join(", ")}}`;
  }],
  [S.MatchClass, (self, node: S.MatchClass) => {
    const args = [...node.patterns.map((p) => self.p(p)),
      ...node.kwd_attrs.map((a, i) => `${self.text(a)}=${self.p(node.kwd_patterns[i] as Node)}`)];
    return `${e(self, node.cls, PRIMARY)}(${args.join(", ")})`;
  }],
  [S.MatchStar, (self, node: S.MatchStar) => "*" + (node.name === null ? "_" : self.text(node.name))],
  [S.MatchAs, (self, node: S.MatchAs) => {
    if (node.pattern === null) return node.name === null ? "_" : self.text(node.name);
    let pattern = self.p(node.pattern);
    if (node.pattern instanceof S.MatchAs && node.pattern.pattern !== null) pattern = `(${pattern})`;
    return `${pattern} as ${node.name === null ? "_" : self.text(node.name)}`;
  }],
  [S.MatchOr, (self, node: S.MatchOr) => node.patterns.map((p) => {
    const text = self.p(p);
    return p instanceof S.MatchOr || (p instanceof S.MatchAs && p.pattern !== null) ? `(${text})` : text;
  }).join(" | ")],
]);

for (const kind of Printer.PATTERNS.keys()) Printer.TEXTS.set(kind, (self, node) => self.p(node));
