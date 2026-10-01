/**
 * Parses TypeScript and JavaScript source text into TypeScript trees, delegating to tree-sitter-typescript (through
 * web-tree-sitter).
 *
 * tree-sitter-typescript builds a concrete syntax tree, with its `typescript` grammar or, for JSX, its `tsx` grammar;
 * `Converter` rewrites it into TypeScript kinds, one tree-sitter node type at a time. tree-sitter-typescript 0.23
 * cannot parse a few constructs of TypeScript 4.7 and later. When the text does not parse, a pre-pass (`prepare`)
 * removes them, keeping every other character where it was: the `accessor` keyword, the variance annotations `in` and
 * `out` of type parameters, the `defer` of `import defer`, and the `type` of `export type *`. The converter puts them
 * back where they were.
 *
 * Positions are counted in characters (code points), never UTF-16 units, so that every implementation reports the same
 * line and column.
 */

import type { Node as TS, Parser as TSParser } from "web-tree-sitter";

import { ParseError } from "../Framework/Errors.js";
import type { Node } from "../Framework/Syntax.js";
import { parser } from "../Framework/_TreeSitter.js";
import * as S from "./Syntax.js";

const PARSERS = {
  false: await parser("tree-sitter-typescript/tree-sitter-typescript.wasm"),
  true: await parser("tree-sitter-typescript/tree-sitter-tsx.wasm"),
};

const EXTRAS = new Set(["comment", "html_comment"]);
const KEYWORD_TYPES: Record<string, new () => Node> = {
  any: S.TSAnyKeyword, unknown: S.TSUnknownKeyword, number: S.TSNumberKeyword, bigint: S.TSBigIntKeyword,
  boolean: S.TSBooleanKeyword, string: S.TSStringKeyword, symbol: S.TSSymbolKeyword, object: S.TSObjectKeyword,
  never: S.TSNeverKeyword, void: S.TSVoidKeyword, undefined: S.TSUndefinedKeyword, null: S.TSNullKeyword,
  intrinsic: S.TSIntrinsicKeyword,
};
/** Operators that bind less than `as` and `satisfies`, which bind as the relational operators do. */
const LOOSER_THAN_AS = new Set(["==", "!=", "===", "!==", "&", "^", "|", "&&", "||", "??"]);
/** How tightly each binary operator binds. */
const BINDS: Record<string, number> = {
  "??": 1, "||": 1, "&&": 2, "|": 3, "^": 4, "&": 5, "==": 6, "!=": 6, "===": 6, "!==": 6, "<": 7, "<=": 7, ">": 7,
  ">=": 7, in: 7, instanceof: 7, "<<": 8, ">>": 8, ">>>": 8, "+": 9, "-": 9, "*": 10, "/": 10, "%": 10, "**": 11,
};
const LOGICAL = new Set(["&&", "||", "??"]);

// --- Source text ---

/** The text being parsed, as given and as tree-sitter parses it (`cleaned`), with conversions from tree-sitter's UTF-16
 * offsets to character offsets, and from character offsets to lines and columns. The cleaned text has the same UTF-16
 * units as the text, but for those the pre-pass rewrote. */
export class Source {
  private readonly points: number[] | null = null;
  private readonly characters: string[];

  constructor(readonly text: string, readonly cleaned: string = text) {
    this.characters = [...text];
    if (this.characters.length !== text.length) {
      this.points = [];
      let at = 0;
      for (const ch of this.characters) {
        for (let u = 0; u < ch.length; u++) this.points.push(at);
        at++;
      }
      this.points.push(at);
    }
  }

  offset(unit: number): number {
    return this.points === null ? unit : this.points[unit] as number;
  }

  /** The text between two character offsets. */
  slice(start: number, end: number): string {
    return this.characters.slice(start, end).join("");
  }

  error(message: string, offset: number): ParseError {
    const before = this.characters.slice(0, offset);
    const line = before.filter((ch) => ch === "\n").length + 1;
    return new ParseError(message, line, offset - (before.lastIndexOf("\n") + 1) + 1);
  }
}

// --- The pre-pass: what tree-sitter-typescript cannot parse ---

/** What the pre-pass rewrote, by character offset: `accessor`s (by the offset of what follows), `in` and `out`
 * annotations (by the type parameter's name), `import defer` and `export type *` (by the statement), names
 * tree-sitter-typescript reads as keywords, `using` in `for (... of ...)`, and `import(...)` in types. */
class Prepared {
  readonly accessors = new Set<number>();
  readonly variance = new Map<number, Set<string>>();
  readonly deferred = new Set<number>();
  readonly typeExports = new Set<number>();
  readonly imports = new Set<number>();
  readonly names = new Map<number, string>();
  readonly usings = new Map<number, string>();
}

type Token = [number, number, string];

const all = (ts: TS): TS[] => ts.children.filter((c): c is TS => c !== null);

/** The tokens of a tree, as UTF-16 spans and their text: each leaf, but each string whole, without comments. */
function tokens(text: string, root: TS): Token[] {
  const out: Token[] = [];
  const stack = [root];
  while (stack.length > 0) {
    const ts = stack.pop() as TS;
    if (EXTRAS.has(ts.type) || ts.isMissing) continue; // what error recovery put in is not in the text
    if (ts.childCount === 0 || ["string", "template_string", "regex"].includes(ts.type)) {
      out.push([ts.startIndex, ts.endIndex, text.slice(ts.startIndex, ts.endIndex)]);
      continue;
    }
    stack.push(...all(ts).reverse());
  }
  return out;
}

/** Whether a token starts as a name does: with a letter, `_` or `$`. */
function startsName(word: string): boolean {
  return /^[\p{L}_$]/u.test(word);
}

/** The text with the constructs tree-sitter-typescript cannot parse removed, and what was removed. */
function prepare(text: string, root: TS, source: Source): [string, Prepared] {
  const found = new Prepared();
  const units = text.split("");
  const blank = (start: number, end: number): void => {
    for (let p = start; p < end; p++) units[p] = " ";
  };
  const list = tokens(text, root);
  list.forEach(([start, end, word], i) => {
    const before = i > 0 ? (list[i - 1] as Token)[2] : "";
    const after = i + 1 < list.length ? (list[i + 1] as Token)[2] : "";
    if (word === "accessor" && !["", "(", ":", "=", ";", "?", "!", "<", ",", ")", "}"].includes(after)) {
      blank(start, end);
      found.accessors.add(source.offset((list[i + 1] as Token)[0])); // where the member starts, or its name
    } else if (word === "accessor" && ["{", ";", "}"].includes(before)) {
      units[start] = "_"; // a member named `accessor`
      found.names.set(source.offset(start), word);
    } else if ((word === "in" || word === "out") && ["<", ",", "in", "const"].includes(before) && startsName(after)
      && after !== "in" && after !== "of") {
      const name = list.slice(i + 1).find((t) => t[2] !== "in" && t[2] !== "out") as Token;
      blank(start, end);
      const at = source.offset(name[0]);
      if (!found.variance.has(at)) found.variance.set(at, new Set());
      found.variance.get(at)?.add(word);
    } else if (word === "defer" && before === "import" && (after === "*" || after === "{")) {
      blank(start, end);
      found.deferred.add(source.offset((list[i - 1] as Token)[0]));
    } else if (word === "type" && before === "export" && after === "*") {
      blank(start, end);
      found.typeExports.add(source.offset((list[i - 1] as Token)[0]));
    } else if (word === "abstract" && [":", "?", "("].includes(after) && [";", "{", ",", "readonly"].includes(before)) {
      units[start] = "_"; // a member named `abstract`
      found.names.set(source.offset(start), word);
    } else if (word === "using" && (before === "(" || before === "await") && i + 2 < list.length
      && (list[i + 2] as Token)[2] === "of" && (before === "(" || (list[i - 2] as Token)[2] === "(")) {
      // `for (using x of y)` becomes `for (const x of y)`, as long
      units.splice(start, end - start, ..."const".split(""));
      let keyword = "using";
      if (before === "await") {
        blank((list[i - 1] as Token)[0], (list[i - 1] as Token)[1]);
        keyword = "await using";
      }
      found.usings.set(source.offset(start), keyword);
    } else if (word === "using" && (!startsName(after)
      || ["in", "of", "instanceof", "as", "satisfies"].includes(after))) {
      units[start] = "_"; // a name `using`: the keyword is followed by the name it binds
      found.names.set(source.offset(start), word);
    } else if (word === "import" && after === "(" && before !== "." && before !== "") {
      // `import("m")`, which tree-sitter-typescript cannot qualify with type arguments as a type, becomes a name as
      // long, `_______m_`... the converter reads the call back from the text
      const close = list.findIndex((t, j) => j > i && t[2] === ")");
      if (close >= 0) {
        // one name, though the call spans lines: positions are offsets, which stay
        for (let p = start; p < (list[close] as Token)[1]; p++) units[p] = "_";
        found.imports.add(source.offset(start));
      }
    }
  });
  return [units.join(""), found];
}

// --- The converter ---

type Method = (self: Converter, ts: TS) => any;

/** Rewrites a tree-sitter-typescript tree into TypeScript nodes, recording where each node starts in `positions`.
 * `shift` and `origin` place a tree parsed from a part of the text: its offsets are `shift` past those of the part,
 * and its errors are located in `origin`. */
class Converter {
  readonly positions = new Map<Node, number>();
  static STATEMENTS: Record<string, Method> = {};
  static EXPRESSIONS: Record<string, Method> = {};
  static TYPES: Record<string, Method> = {};
  private readonly origin: Source;

  constructor(private readonly source: Source, private readonly pre: Prepared, private readonly shift = 0,
    origin: Source | null = null) {
    this.origin = origin ?? source;
  }

  // Helpers

  at(ts: TS): number {
    return this.shift + this.source.offset(ts.startIndex);
  }

  text(ts: TS): string {
    return this.source.cleaned.slice(ts.startIndex, ts.endIndex);
  }

  /** The text between two UTF-16 offsets. */
  between(start: number, end: number): string {
    return this.source.cleaned.slice(start, end);
  }

  error(ts: TS, message: string): ParseError {
    return this.origin.error(message, this.at(ts));
  }

  unsupported(ts: TS): ParseError {
    return this.error(ts, `unsupported syntax: ${ts.type}`);
  }

  made<N extends Node>(ts: TS, node: N): N {
    if (!this.positions.has(node)) this.positions.set(node, this.at(ts));
    return node;
  }

  madeAt<N extends Node>(unit: number, node: N): N {
    if (!this.positions.has(node)) this.positions.set(node, this.shift + this.source.offset(unit));
    return node;
  }

  kids(ts: TS): TS[] {
    return all(ts).filter((c) => !EXTRAS.has(c.type));
  }

  named(ts: TS): TS[] {
    return all(ts).filter((c) => c.isNamed && !EXTRAS.has(c.type));
  }

  /** The child in the field `name`, found among the children: tree-sitter's own lookup can return a nested node's
   * (`typeof a.b.c`). */
  field(ts: TS, name: string): TS | null {
    return this.fields(ts, name)[0] ?? null;
  }

  fields(ts: TS, name: string): TS[] {
    return ts.children.filter((c, i): c is TS => c !== null && ts.fieldNameForChild(i) === name);
  }

  has(ts: TS, token: string): boolean {
    return all(ts).some((c) => !c.isNamed && c.type === token);
  }

  /** A field the grammar requires, which tree-sitter always writes. */
  require(ts: TS, name: string): TS {
    return this.field(ts, name) as TS;
  }

  /** The modifier keywords and marks among `ts`'s children before its field `field`. */
  tokensBefore(ts: TS, field: string): Set<string> {
    const stop = this.require(ts, field).startIndex;
    const out = new Set<string>();
    for (const c of all(ts)) {
      const modifier = c.type === "accessibility_modifier" || c.type === "override_modifier";
      if (c.startIndex < stop && (!c.isNamed || modifier)) {
        out.add(c.isNamed ? this.text(c) : c.type);
      }
    }
    return out;
  }

  /** A name's spelling, which the pre-pass may have changed: a name tree-sitter-typescript reads as a keyword. */
  spelling(ts: TS): string {
    return this.pre.names.get(this.at(ts)) ?? this.text(ts);
  }

  identifier(ts: TS): S.Identifier {
    return this.made(ts, new S.Identifier({ name: this.spelling(ts) }));
  }

  /** Whether `ts` is the name the pre-pass put in place of `import(...)`. */
  placeholder(ts: TS): boolean {
    return this.pre.imports.has(this.at(ts));
  }

  literal(ts: TS): S.Literal {
    return this.made(ts, new S.Literal({ raw: this.text(ts) }));
  }

  // Errors

  /** Throws for the first syntax error in `ts`, in source order. */
  check(ts: TS): void {
    const stack = [ts];
    while (stack.length > 0) {
      const node = stack.pop() as TS;
      if (node.type === "ERROR" && !this.globalBlock(node)) throw this.error(node, "syntax error");
      if (node.isMissing && !(node.parent !== null && this.globalBlock(node.parent))) {
        throw this.error(node, `expected ${node.type}`);
      }
      stack.push(...all(node).reverse());
    }
  }

  /** Whether `ts` is the `global` of `global { ... }` in a module, which tree-sitter-typescript reads as an error
   * followed by a block. */
  globalBlock(ts: TS): boolean {
    const kids = all(ts).filter((c) => !c.isMissing);
    const following = ts.nextSibling;
    return (ts.type === "ERROR" || ts.type === "expression_statement") && kids.length === 1
      && (kids[0] as TS).type === "identifier" && this.text(kids[0] as TS) === "global" && following !== null
      && following.type === "statement_block" && ts.parent !== null && ts.parent.type === "statement_block";
  }

  // Lists of statements and members, with their comments

  /** The items among `nodes`, up to a closing brace, converted, and the comments between them: a comment is trailing on
   * the line where the item before it ends, or `header` for the first. */
  listed(nodes: TS[], convert: (ts: TS) => any, header: TS | null = null): any[] {
    const out: any[] = [];
    let previous = header;
    let skip: number | null = null;
    for (let ts of nodes) {
      if (skip !== null && ts.id === skip) {
        previous = ts;
        continue;
      }
      const last = out[out.length - 1];
      if (ts.type === "comment") {
        out.push(this.comment(ts, previous));
      } else if (ts.type === "empty_statement" && last instanceof S.TSModuleDeclaration && last.body === null
        && previous !== null && previous.type !== "comment") {
        // the `;` that ends `declare module "a";`, which tree-sitter-typescript reads as a statement
      } else if ((ts.type === "ERROR" || ts.type === "expression_statement") && this.globalBlock(ts)) {
        const block = ts.nextSibling as TS;
        const made = new S.TSModuleDeclaration({ moduleKind: "global",
          id: this.made(ts, new S.Identifier({ name: "global" })), body: this.moduleBlock(block) });
        out.push(this.made(ts, made));
        skip = block.id;
      } else if (ts.isNamed && ts.type !== "html_comment") {
        out.push(convert(ts));
        for (const comment of this.strays(ts)) {
          out.push(this.comment(comment, comment.previousSibling));
          ts = comment;
        }
      } else if (ts.type === "}") {
        break;
      } else {
        continue;
      }
      previous = ts;
    }
    return out;
  }

  /** The comments after `ts` that tree-sitter-typescript puts after the closing brace of the block that ends it:
   * `m() {} // c`. */
  strays(ts: TS): TS[] {
    let out: TS[] = [];
    let node = ts;
    while (node.childCount > 0) {
      const kids = all(node);
      let i = kids.length;
      while ((kids[i - 1] as TS).type === "comment") i--; // a node holds more than comments
      if (i < kids.length && (kids[i - 1] as TS).type === "}") out = [...kids.slice(i), ...out]; // inner ones first
      node = kids[i - 1] as TS;
    }
    return out;
  }

  comment(ts: TS, previous: TS | null): S.Comment {
    const text = this.text(ts);
    const block = text.startsWith("/*");
    const made = new S.Comment({ block, text: block ? text.slice(2, -2) : text.slice(2) });
    // in the text as written
    made.trailing = previous !== null && !this.source.text.slice(previous.endIndex, ts.startIndex).includes("\n");
    return this.made(ts, made);
  }

  program(ts: TS): S.Program {
    this.check(ts);
    const made = new S.Program();
    let nodes = all(ts);
    if (nodes.length > 0 && (nodes[0] as TS).type === "hash_bang_line") {
      made.hashbang = this.text(nodes[0] as TS).slice(2);
      nodes = nodes.slice(1);
    }
    made.body = this.listed(nodes, (n) => this.statement(n));
    return this.made(ts, made);
  }

  block(ts: TS): S.BlockStatement {
    return this.made(ts, new S.BlockStatement({ body: this.listed(all(ts), (n) => this.statement(n), all(ts)[0]) }));
  }

  // Statements

  statement(ts: TS): any {
    return this.made(ts, (Converter.STATEMENTS[ts.type] as Method)(this, ts)); // the grammar has no other statement
  }

  expressionStatement(ts: TS): any {
    const inner = this.named(ts)[0] as TS;
    if (inner.type === "internal_module") return this.module(inner, "namespace"); // read as an expression
    const using = this.using(inner);
    if (using !== null) return using;
    return new S.ExpressionStatement({ expression: this.expression(inner) });
  }

  /** `using x = f()` or `await using x = f()`, which tree-sitter-typescript reads as an assignment with a `using`
   * token, perhaps awaited; null for any other expression. */
  using(ts: TS): S.VariableDeclaration | null {
    let keyword = "using";
    if (ts.type === "await_expression") {
      keyword = "await using";
      ts = this.named(ts)[0] as TS;
    }
    if (ts.type !== "assignment_expression" || !this.has(ts, "using")) return null;
    const left = this.require(ts, "left");
    const declarator = this.made(left, new S.VariableDeclarator({ id: this.binding(left),
      init: this.expression(this.require(ts, "right")) }));
    return new S.VariableDeclaration({ declarationKind: keyword as S.DeclarationKind, declarations: [declarator] });
  }

  declarators(ts: TS): S.VariableDeclarator[] {
    return this.named(ts).filter((d) => d.type === "variable_declarator").map((d) => this.declarator(d));
  }

  declarator(ts: TS): S.VariableDeclarator {
    const made = new S.VariableDeclarator({ id: this.binding(this.require(ts, "name")) });
    made.definite = this.has(ts, "!");
    const annotation = this.field(ts, "type");
    if (annotation !== null) (made.id as any).typeAnnotation = this.annotation(annotation);
    const value = this.field(ts, "value");
    made.init = value === null ? null : this.expression(value);
    return this.made(ts, made);
  }

  lexicalDeclaration(ts: TS): S.VariableDeclaration {
    return new S.VariableDeclaration({ declarationKind: this.text(this.require(ts, "kind")) as S.DeclarationKind,
      declarations: this.declarators(ts) });
  }

  variableDeclaration(ts: TS): S.VariableDeclaration {
    return new S.VariableDeclaration({ declarationKind: "var", declarations: this.declarators(ts) });
  }

  returnStatement(ts: TS): S.ReturnStatement {
    const kids = this.named(ts);
    return new S.ReturnStatement({ argument: kids.length > 0 ? this.expression(kids[0] as TS) : null });
  }

  throwStatement(ts: TS): S.ThrowStatement {
    return new S.ThrowStatement({ argument: this.expression(this.named(ts)[0] as TS) });
  }

  ifStatement(ts: TS): S.IfStatement {
    const made = new S.IfStatement({ test: this.condition(this.require(ts, "condition")),
      consequent: this.statement(this.require(ts, "consequence")) });
    const alternative = this.field(ts, "alternative");
    if (alternative !== null) made.alternate = this.statement(this.named(alternative)[0] as TS);
    return made;
  }

  /** The expression in the parentheses a statement's syntax has: `if (test)`, `while (test)`. */
  condition(ts: TS): any {
    return this.expression(this.named(ts)[0] as TS);
  }

  whileStatement(ts: TS): S.WhileStatement {
    return new S.WhileStatement({ test: this.condition(this.require(ts, "condition")),
      body: this.statement(this.require(ts, "body")) });
  }

  doStatement(ts: TS): S.DoWhileStatement {
    return new S.DoWhileStatement({ body: this.statement(this.require(ts, "body")),
      test: this.condition(this.require(ts, "condition")) });
  }

  withStatement(ts: TS): S.WithStatement {
    return new S.WithStatement({ object: this.condition(this.require(ts, "object")),
      body: this.statement(this.require(ts, "body")) });
  }

  forStatement(ts: TS): S.ForStatement {
    const made = new S.ForStatement({ body: this.statement(this.require(ts, "body")) });
    const init = this.require(ts, "initializer");
    if (init.type === "lexical_declaration" || init.type === "variable_declaration") {
      made.init = this.made(init, (Converter.STATEMENTS[init.type] as Method)(this, init));
    } else if (init.type !== "empty_statement") {
      made.init = this.expression(init);
    }
    const conditions = this.fields(ts, "condition").filter((c) => c.type !== ";" && c.type !== "empty_statement");
    made.test = conditions.length > 0 ? this.expression(conditions[0] as TS) : null;
    const increment = this.field(ts, "increment");
    made.update = increment === null ? null : this.expression(increment);
    return made;
  }

  forInStatement(ts: TS): any {
    const left = this.require(ts, "left");
    const kind = this.field(ts, "kind");
    let target: any;
    if (kind !== null) {
      const declarator = this.made(left, new S.VariableDeclarator({ id: this.binding(left) }));
      const value = this.field(ts, "value");
      if (value !== null) declarator.init = this.expression(value);
      const keyword = this.pre.usings.get(this.at(kind)) ?? this.text(kind);
      target = this.made(kind, new S.VariableDeclaration({ declarationKind: keyword as S.DeclarationKind,
        declarations: [declarator] }));
    } else {
      target = this.target(left);
    }
    const right = this.expression(this.require(ts, "right"));
    const body = this.statement(this.require(ts, "body"));
    if (this.text(this.require(ts, "operator")) === "in") return new S.ForInStatement({ left: target, right, body });
    return new S.ForOfStatement({ isAwait: (this.kids(ts)[1] as TS).type === "await", left: target, right, body });
  }

  switchStatement(ts: TS): S.SwitchStatement {
    const cases: S.SwitchCase[] = [];
    for (const kase of all(this.require(ts, "body")).filter((c) => c.isNamed)) {
      if (kase.type === "comment") { // after a case, which tree-sitter-typescript ends where its last statement does
        cases.at(-1)?.consequent.push(this.comment(kase, kase.previousSibling));
        continue;
      }
      const value = this.field(kase, "value");
      const head = (value ?? all(kase)[0]) as TS;
      const made = new S.SwitchCase({ test: value === null ? null : this.expression(value) });
      const colon = all(kase).find((c) => c.type === ":") as TS;
      const body = all(kase).filter((c) => c.startIndex > head.endIndex && c.startIndex > colon.startIndex);
      made.consequent = this.listed(body, (n) => this.statement(n), colon);
      cases.push(this.made(kase, made));
    }
    return new S.SwitchStatement({ discriminant: this.condition(this.require(ts, "value")), cases });
  }

  tryStatement(ts: TS): S.TryStatement {
    const made = new S.TryStatement({ block: this.block(this.require(ts, "body")) });
    const handler = this.field(ts, "handler");
    if (handler !== null) {
      const clause = new S.CatchClause({ body: this.block(this.require(handler, "body")) });
      const parameter = this.field(handler, "parameter");
      if (parameter !== null) {
        clause.param = this.binding(parameter);
        const annotation = this.field(handler, "type");
        if (annotation !== null) (clause.param as any).typeAnnotation = this.annotation(annotation);
      }
      made.handler = this.made(handler, clause);
    }
    const finalizer = this.field(ts, "finalizer");
    if (finalizer !== null) made.finalizer = this.block(this.require(finalizer, "body"));
    return made;
  }

  labeledStatement(ts: TS): S.LabeledStatement {
    return new S.LabeledStatement({ label: this.identifier(this.require(ts, "label")),
      body: this.statement(this.require(ts, "body")) });
  }

  // Functions and classes

  functionDeclaration(ts: TS): S.FunctionDeclaration {
    const made = new S.FunctionDeclaration({ isAsync: this.has(ts, "async"), generator: this.has(ts, "*"),
      id: this.identifier(this.require(ts, "name")), body: this.block(this.require(ts, "body")) });
    this.signature(ts, made);
    return made;
  }

  /** The type parameters, parameters and return type of a function, method or signature. */
  signature(ts: TS, made: any): void {
    const parameters = this.field(ts, "type_parameters");
    if (parameters !== null) made.typeParameters = this.typeParameters(parameters);
    made.params = this.parameters(this.require(ts, "parameters"));
    const returns = this.field(ts, "return_type")
      ?? (ts.type === "construct_signature" ? this.field(ts, "type") : null);
    if (returns !== null) made.returnType = this.annotation(returns);
  }

  functionSignature(ts: TS): S.TSDeclareFunction {
    const made = new S.TSDeclareFunction({ isAsync: this.has(ts, "async"), generator: this.has(ts, "*"),
      id: this.identifier(this.require(ts, "name")) });
    this.signature(ts, made);
    return made;
  }

  parameters(ts: TS): any[] {
    return this.named(ts).map((p) => this.parameter(p));
  }

  /** A `required_parameter` or `optional_parameter`: a binding, perhaps with `?`, a type and a default, or a parameter
   * property. */
  parameter(ts: TS): any {
    const pattern = this.require(ts, "pattern"); // a parameter's, which `name` only is in a tuple type
    const binding: any = pattern.type === "this" ? this.made(pattern, new S.Identifier({ name: "this" }))
      : this.binding(pattern);
    const annotation = this.field(ts, "type");
    if (annotation !== null) binding.typeAnnotation = this.annotation(annotation);
    if (ts.type === "optional_parameter") binding.optional = true;
    const decorators = this.fields(ts, "decorator").map((d) => this.decorator(d));
    const value = this.field(ts, "value");
    let result: any = binding;
    if (value !== null) {
      result = this.made(ts, new S.AssignmentPattern({ left: binding, right: this.expression(value) }));
    }
    const modifiers = this.tokensBefore(ts, "pattern");
    const accessibility = [...modifiers].find((m) => ["public", "private", "protected"].includes(m)) ?? null;
    if (accessibility !== null || modifiers.has("readonly") || modifiers.has("override")) {
      return this.made(ts, new S.TSParameterProperty({ decorators,
        accessibility: accessibility as S.Accessibility | null,
        override: modifiers.has("override"), readonly: modifiers.has("readonly"), parameter: result }));
    }
    result.decorators = decorators;
    return result;
  }

  classDeclaration(ts: TS): S.ClassDeclaration {
    const made = new S.ClassDeclaration({ abstract: ts.type === "abstract_class_declaration" });
    this.classParts(ts, made);
    return made;
  }

  classParts(ts: TS, made: S.ClassDeclaration | S.ClassExpression): void {
    made.decorators = this.fields(ts, "decorator").map((d) => this.decorator(d));
    const name = this.field(ts, "name");
    made.id = name === null ? null : this.identifier(name);
    const parameters = this.field(ts, "type_parameters");
    if (parameters !== null) made.typeParameters = this.typeParameters(parameters);
    const heritage = this.named(ts).find((c) => c.type === "class_heritage");
    if (heritage !== undefined) {
      for (const clause of this.named(heritage)) {
        if (clause.type === "extends_clause") {
          made.superClass = this.expression(this.require(clause, "value"));
          const args = this.field(clause, "type_arguments");
          if (args !== null) made.superTypeArguments = this.typeArguments(args);
        } else {
          made.implements = this.named(clause).map((t) => this.made(t, new S.TSClassImplements(this.heritage(t))));
        }
      }
    }
    const body = this.require(ts, "body");
    made.body = this.made(body, new S.ClassBody({ body: this.members(body) }));
  }

  /** A class body's members and comments; decorators before a member, which tree-sitter-typescript lists beside it,
   * are its own. */
  members(body: TS): any[] {
    const pending: S.Decorator[] = [];
    const member = (ts: TS): any => {
      if (ts.type === "decorator") {
        pending.push(this.decorator(ts));
        return null;
      }
      const made = this.member(ts);
      if (pending.length > 0 && made.kind().BY_NAME.has("decorators")) {
        made.decorators = [...pending, ...made.decorators];
      }
      pending.length = 0;
      return made;
    };
    return this.listed(all(body), member, all(body)[0]).filter((m) => m !== null);
  }

  /** The expression and type arguments of a type in `implements` or `extends`. */
  heritage(ts: TS): { expression: any; typeArguments?: S.TSTypeParameterInstantiation } {
    if (ts.type === "generic_type") {
      return { expression: this.typeNameExpression(this.require(ts, "name")),
        typeArguments: this.typeArguments(this.require(ts, "type_arguments")) };
    }
    return { expression: this.typeNameExpression(ts) };
  }

  /** A type's name, as the expression `implements` and `extends` take: `a.b.C`. */
  typeNameExpression(ts: TS): any {
    if (ts.type === "nested_type_identifier") {
      return this.made(ts, new S.MemberExpression({ object: this.typeNameExpression(this.require(ts, "module")),
        property: this.identifier(this.require(ts, "name")) }));
    }
    if (ts.type === "nested_identifier") {
      return this.made(ts, new S.MemberExpression({ object: this.typeNameExpression(this.require(ts, "object")),
        property: this.identifier(this.require(ts, "property")) }));
    }
    return this.identifier(ts);
  }

  decorator(ts: TS): S.Decorator {
    return this.made(ts, new S.Decorator({ expression: this.expression(this.named(ts)[0] as TS) }));
  }

  /** A member's key, and whether it is computed. */
  key(ts: TS): [any, boolean] {
    if (ts.type === "computed_property_name") return [this.expression(this.named(ts)[0] as TS), true];
    if (ts.type === "private_property_identifier") {
      return [this.made(ts, new S.PrivateIdentifier({ name: this.text(ts).slice(1) })), false];
    }
    if (ts.type === "string" || ts.type === "number") return [this.literal(ts), false];
    return [this.identifier(ts), false];
  }

  /** A class member. */
  member(ts: TS): any {
    if (ts.type === "class_static_block") {
      const body = this.require(ts, "body");
      return this.made(ts, new S.StaticBlock({ body: this.listed(all(body), (n) => this.statement(n), all(body)[0]) }));
    }
    if (ts.type === "index_signature") return this.indexSignature(ts);
    if (ts.type === "public_field_definition") return this.fieldDefinition(ts);
    return this.method(ts); // a method_definition, method_signature or abstract_method_signature
  }

  modifiers(ts: TS, made: any, modifiers: Set<string>): void {
    made.decorators = this.fields(ts, "decorator").map((d) => this.decorator(d));
    made.accessibility = [...modifiers].find((m) => ["public", "private", "protected"].includes(m)) ?? null;
    made.static = modifiers.has("static");
    made.override = modifiers.has("override");
  }

  fieldDefinition(ts: TS): any {
    const modifiers = this.tokensBefore(ts, "name");
    const from = this.at(ts);
    const to = this.at(this.require(ts, "name"));
    const accessor = modifiers.has("accessor") || [...this.pre.accessors].some((o) => from <= o && o <= to);
    const abstract = modifiers.has("abstract");
    const kind = accessor ? (abstract ? S.TSAbstractAccessorProperty : S.AccessorProperty)
      : (abstract ? S.TSAbstractPropertyDefinition : S.PropertyDefinition);
    const made: any = new kind();
    this.modifiers(ts, made, modifiers);
    made.declare = modifiers.has("declare");
    made.readonly = modifiers.has("readonly");
    [made.key, made.computed] = this.key(this.require(ts, "name"));
    made.optional = this.has(ts, "?");
    made.definite = this.has(ts, "!");
    const annotation = this.field(ts, "type");
    if (annotation !== null) made.typeAnnotation = this.annotation(annotation);
    const value = this.field(ts, "value");
    made.value = value === null ? null : this.expression(value);
    return this.made(ts, made);
  }

  method(ts: TS): any {
    const modifiers = this.tokensBefore(ts, "name");
    const name = this.require(ts, "name");
    const abstract = ts.type === "abstract_method_signature" || modifiers.has("abstract");
    const made: any = abstract ? new S.TSAbstractMethodDefinition() : new S.MethodDefinition();
    this.modifiers(ts, made, modifiers);
    [made.key, made.computed] = this.key(name);
    made.methodKind = modifiers.has("get") ? "get" : modifiers.has("set") ? "set" : "method";
    if (made.methodKind === "method" && !made.static && !made.computed
      && ["constructor", "'constructor'", '"constructor"'].includes(this.text(name))) {
      made.methodKind = "constructor";
    }
    made.optional = all(ts).some((c) => c.type === "?" && c.startIndex > name.startIndex);
    const body = this.field(ts, "body");
    const value: any = body !== null ? new S.FunctionExpression({ body: this.block(body) })
      : new S.TSEmptyBodyFunctionExpression();
    value.isAsync = modifiers.has("async");
    value.generator = modifiers.has("*");
    this.signature(ts, value);
    made.value = this.made(this.require(ts, "parameters"), value);
    return this.made(ts, made);
  }

  indexSignature(ts: TS): any {
    if (this.named(ts).some((c) => c.type === "mapped_type_clause")) throw this.unsupported(ts);
    const modifiers = this.tokensBefore(ts, "type");
    const parameter = this.identifier(this.require(ts, "name"));
    const index = this.require(ts, "index_type");
    parameter.typeAnnotation = this.made(index, new S.TSTypeAnnotation({ typeAnnotation: this.type(index) }));
    const made = new S.TSIndexSignature({ parameters: [parameter], readonly: modifiers.has("readonly"),
      static: modifiers.has("static"), typeAnnotation: this.annotation(this.require(ts, "type")) });
    made.accessibility = ([...modifiers].find((m) => ["public", "private", "protected"].includes(m)) ?? null) as
      S.Accessibility | null;
    return this.made(ts, made);
  }

  // Modules

  importStatement(ts: TS): any {
    const require = this.named(ts).find((c) => c.type === "import_require_clause");
    const kind = (this.kids(ts)[1] as TS).type === "type" ? "type" : "value";
    if (require !== undefined) {
      const reference = this.made(require, new S.TSExternalModuleReference({
        expression: this.literal(this.require(require, "source")) }));
      return new S.TSImportEqualsDeclaration({ importKind: kind, id: this.identifier(this.named(require)[0] as TS),
        moduleReference: reference });
    }
    const made = new S.ImportDeclaration({ source: this.literal(this.require(ts, "source")) });
    made.importKind = kind;
    if (this.pre.deferred.has(this.at(ts))) made.phase = "defer";
    const clause = this.named(ts).find((c) => c.type === "import_clause");
    if (clause !== undefined) {
      for (const part of this.named(clause)) {
        if (part.type === "identifier") {
          made.specifiers.push(this.made(part, new S.ImportDefaultSpecifier({ local: this.identifier(part) })));
        } else if (part.type === "namespace_import") {
          made.specifiers.push(this.made(part, new S.ImportNamespaceSpecifier({
            local: this.identifier(this.named(part)[0] as TS) })));
        } else {
          made.specifiers.push(...this.named(part).map((s) => this.importSpecifier(s)));
        }
      }
    }
    const attributes = this.named(ts).find((c) => c.type === "import_attribute");
    if (attributes !== undefined) made.attributes = this.attributes(attributes);
    return made;
  }

  attributes(ts: TS): S.ImportAttribute[] {
    return this.named(this.named(ts)[0] as TS).map((pair) => {
      const key = this.require(pair, "key");
      return this.made(pair, new S.ImportAttribute({
        key: key.type === "string" ? this.literal(key) : this.identifier(key),
        value: this.literal(this.require(pair, "value")) }));
    });
  }

  importSpecifier(ts: TS): S.ImportSpecifier {
    const name = this.require(ts, "name");
    const imported = name.type === "string" ? this.literal(name) : this.identifier(name);
    const alias = this.field(ts, "alias");
    const local = alias !== null ? this.identifier(alias)
      : this.made(name, new S.Identifier({ name: this.spelling(name) }));
    const kind = (this.kids(ts)[0] as TS).type === "type" ? "type" : "value";
    return this.made(ts, new S.ImportSpecifier({ importKind: kind, imported, local }));
  }

  importAlias(ts: TS): S.TSImportEqualsDeclaration {
    const [name, reference] = this.named(ts) as [TS, TS];
    return new S.TSImportEqualsDeclaration({ importKind: "value", id: this.identifier(name),
      moduleReference: this.entityName(reference) });
  }

  /** `a.b.c` as a type's or a namespace's name: an `Identifier` or a `TSQualifiedName`. */
  entityName(ts: TS): any {
    if (ts.type === "nested_identifier" || ts.type === "member_expression") {
      return this.made(ts, new S.TSQualifiedName({ left: this.entityName(this.require(ts, "object")),
        right: this.identifier(this.require(ts, "property")) }));
    }
    if (ts.type === "nested_type_identifier") {
      return this.made(ts, new S.TSQualifiedName({ left: this.entityName(this.require(ts, "module")),
        right: this.identifier(this.require(ts, "name")) }));
    }
    if (ts.type === "this") return this.made(ts, new S.ThisExpression());
    return this.identifier(ts);
  }

  exportStatement(ts: TS): any {
    const kids = this.kids(ts);
    const decorators = this.fields(ts, "decorator").map((d) => this.decorator(d));
    const second = (kids[1] as TS).type;
    if (second === "=") return new S.TSExportAssignment({ expression: this.expression(this.named(ts).at(-1) as TS) });
    if (second === "as") {
      return new S.TSNamespaceExportDeclaration({ id: this.identifier(this.named(ts).at(-1) as TS) });
    }
    const declaration = this.field(ts, "declaration");
    const value = this.field(ts, "value");
    if (this.has(ts, "default")) {
      const target = declaration ?? this.require(ts, "value");
      let converted: any;
      if (["function_expression", "generator_function", "class"].includes(target.type) && value !== null) {
        converted = this.defaultDeclaration(target);
      } else if (declaration !== null) {
        converted = this.statement(declaration);
      } else {
        converted = this.expression(target);
      }
      if (decorators.length > 0 && converted instanceof S.ClassDeclaration) {
        converted.decorators = [...decorators, ...converted.decorators];
      }
      return new S.ExportDefaultDeclaration({ declaration: converted });
    }
    const source = this.field(ts, "source");
    if (this.has(ts, "*") || all(ts).some((c) => c.type === "namespace_export")) {
      const made = new S.ExportAllDeclaration({ source: this.literal(source as TS) });
      made.exportKind = this.pre.typeExports.has(this.at(ts)) || second === "type" ? "type" : "value";
      const namespace = this.named(ts).find((c) => c.type === "namespace_export");
      if (namespace !== undefined) {
        const exported = this.named(namespace)[0] as TS;
        made.exported = exported.type === "string" ? this.literal(exported) : this.identifier(exported);
      }
      return made; // tree-sitter-typescript reads no attributes here
    }
    const made = new S.ExportNamedDeclaration();
    if (declaration !== null) {
      const converted = this.statement(declaration);
      if (decorators.length > 0 && converted instanceof S.ClassDeclaration) {
        converted.decorators = [...decorators, ...converted.decorators];
      }
      made.declaration = converted;
      made.exportKind = converted instanceof S.TSInterfaceDeclaration || converted instanceof S.TSTypeAliasDeclaration
        || converted.declare === true ? "type" : "value";
      return made;
    }
    made.exportKind = second === "type" ? "type" : "value";
    const clause = this.named(ts).find((c) => c.type === "export_clause") as TS;
    made.specifiers = this.named(clause).map((s) => this.exportSpecifier(s));
    if (source !== null) made.source = this.literal(source);
    return made; // tree-sitter-typescript reads no attributes here
  }

  /** `export default function ...` or `export default class ...`, which are declarations, unnamed: a named one is a
   * declaration to tree-sitter-typescript too. */
  defaultDeclaration(ts: TS): any {
    if (ts.type === "class") {
      const made = new S.ClassDeclaration();
      this.classParts(ts, made);
      return this.made(ts, made);
    }
    const made = new S.FunctionDeclaration({ isAsync: this.has(ts, "async"),
      generator: ts.type === "generator_function", body: this.block(this.require(ts, "body")) });
    this.signature(ts, made);
    return this.made(ts, made);
  }

  exportSpecifier(ts: TS): S.ExportSpecifier {
    const name = this.require(ts, "name");
    const local = name.type === "string" ? this.literal(name) : this.identifier(name);
    const alias = this.field(ts, "alias");
    let exported: any;
    if (alias === null) {
      exported = this.made(name, name.type === "string" ? new S.Literal({ raw: this.text(name) })
        : new S.Identifier({ name: this.spelling(name) }));
    } else {
      exported = alias.type === "string" ? this.literal(alias) : this.identifier(alias);
    }
    const kind = (this.kids(ts)[0] as TS).type === "type" ? "type" : "value";
    return this.made(ts, new S.ExportSpecifier({ exportKind: kind, local, exported }));
  }

  /** `declare ...`, or `declare global { ... }`. */
  ambientDeclaration(ts: TS): any {
    const inner = this.named(ts)[0] as TS;
    if (inner.type === "statement_block") {
      const made = new S.TSModuleDeclaration({ declare: true, moduleKind: "global",
        id: this.made(all(ts)[1] as TS, new S.Identifier({ name: "global" })) });
      made.body = this.moduleBlock(inner);
      return made;
    }
    const made = this.statement(inner);
    made.declare = true;
    return made;
  }

  moduleBlock(ts: TS): S.TSModuleBlock {
    return this.made(ts, new S.TSModuleBlock({ body: this.listed(all(ts), (n) => this.statement(n), all(ts)[0]) }));
  }

  module(ts: TS, kind: string | null = null): S.TSModuleDeclaration {
    const name = this.require(ts, "name");
    const keyword = kind ?? (ts.type === "internal_module" ? "namespace" : "module");
    const made = new S.TSModuleDeclaration({ moduleKind: keyword as S.ModuleKind,
      id: name.type === "string" ? this.literal(name) : this.entityName(name) });
    const body = this.field(ts, "body");
    made.body = body === null ? null : this.moduleBlock(body);
    return this.made(ts, made);
  }

  typeAliasDeclaration(ts: TS): S.TSTypeAliasDeclaration {
    const value = this.require(ts, "value");
    const made = new S.TSTypeAliasDeclaration({ id: this.identifier(this.require(ts, "name")),
      typeAnnotation: value.type === "type_identifier" && this.text(value) === "intrinsic"
        ? this.made(value, new S.TSIntrinsicKeyword()) : this.type(value) });
    const parameters = this.field(ts, "type_parameters");
    if (parameters !== null) made.typeParameters = this.typeParameters(parameters);
    return made;
  }

  interfaceDeclaration(ts: TS): S.TSInterfaceDeclaration {
    const made = new S.TSInterfaceDeclaration({ id: this.identifier(this.require(ts, "name")) });
    const parameters = this.field(ts, "type_parameters");
    if (parameters !== null) made.typeParameters = this.typeParameters(parameters);
    const clause = this.named(ts).find((c) => c.type === "extends_type_clause");
    if (clause !== undefined) {
      made.extends = this.named(clause).map((t) => this.made(t, new S.TSInterfaceHeritage(this.heritage(t))));
    }
    const body = this.require(ts, "body");
    made.body = this.made(body, new S.TSInterfaceBody({
      body: this.listed(all(body), (n) => this.typeMember(n), all(body)[0]) }));
    return made;
  }

  enumDeclaration(ts: TS): S.TSEnumDeclaration {
    const body = this.require(ts, "body");
    const made = new S.TSEnumDeclaration({ const: this.has(ts, "const"),
      id: this.identifier(this.require(ts, "name")) });
    made.body = this.made(body, new S.TSEnumBody({
      members: this.listed(all(body), (n) => this.enumMember(n), all(body)[0]) }));
    return made;
  }

  enumMember(ts: TS): S.TSEnumMember {
    if (ts.type === "enum_assignment") {
      const [key, computed] = this.key(this.require(ts, "name"));
      return this.made(ts, new S.TSEnumMember({ computed, id: key,
        initializer: this.expression(this.require(ts, "value")) }));
    }
    const [key, computed] = this.key(ts);
    return this.made(ts, new S.TSEnumMember({ computed, id: key }));
  }

  // Bindings and patterns

  /** What a declaration or a parameter binds: a name or a destructuring pattern. */
  binding(ts: TS): any {
    if (ts.type === "identifier" || ts.type === "undefined") return this.identifier(ts);
    return this.target(ts);
  }

  /** An assignment's or a binding's target, which tree-sitter-typescript writes as a pattern. */
  target(ts: TS): any {
    if (ts.type === "array_pattern") {
      return this.made(ts, new S.ArrayPattern({ elements: this.elements(ts, (n) => this.target(n)) }));
    }
    if (ts.type === "object_pattern") {
      return this.made(ts, new S.ObjectPattern({ properties: this.named(ts).map((p) => this.patternProperty(p)) }));
    }
    if (ts.type === "assignment_pattern") {
      return this.made(ts, new S.AssignmentPattern({ left: this.target(this.require(ts, "left")),
        right: this.expression(this.require(ts, "right")) }));
    }
    if (ts.type === "rest_pattern") {
      return this.made(ts, new S.RestElement({ argument: this.target(this.named(ts)[0] as TS) }));
    }
    if (ts.type === "identifier" || ts.type === "undefined") return this.identifier(ts);
    return this.expression(ts);
  }

  patternProperty(ts: TS): any {
    if (ts.type === "rest_pattern") {
      return this.made(ts, new S.RestElement({ argument: this.target(this.named(ts)[0] as TS) }));
    }
    if (ts.type === "shorthand_property_identifier_pattern") {
      return this.made(ts, new S.Property({ propertyKind: "init", key: this.identifier(ts), shorthand: true,
        value: this.made(ts, new S.Identifier({ name: this.spelling(ts) })) }));
    }
    if (ts.type === "object_assignment_pattern") { // `{ a = 1 }`, whose left is always a shorthand name
      const left = this.require(ts, "left");
      const value = this.made(ts, new S.AssignmentPattern({ left: this.identifier(left),
        right: this.expression(this.require(ts, "right")) }));
      return this.made(ts, new S.Property({ propertyKind: "init",
        key: this.made(left, new S.Identifier({ name: this.text(left) })), shorthand: true, value }));
    }
    const [key, computed] = this.key(this.require(ts, "key"));
    return this.made(ts, new S.Property({ propertyKind: "init", key, computed,
      value: this.target(this.require(ts, "value")) }));
  }

  /** The elements of an array or an array pattern, with an `Elision` for each hole. */
  elements(ts: TS, convert: (ts: TS) => any): any[] {
    const out: any[] = [];
    let pending = true; // a comma now leaves a hole
    for (const c of this.kids(ts).slice(1, -1)) {
      if (c.type === ",") {
        if (pending) out.push(this.made(c, new S.Elision()));
        pending = true;
      } else {
        out.push(convert(c));
        pending = false;
      }
    }
    return out;
  }

  // Expressions

  expression(ts: TS): any {
    return this.made(ts, (Converter.EXPRESSIONS[ts.type] as Method)(this, ts)); // the grammar has no other expression
  }

  parenthesized(ts: TS): S.ParenthesizedExpression {
    if (this.field(ts, "type") !== null) throw this.unsupported(ts);
    return new S.ParenthesizedExpression({ expression: this.expression(this.named(ts)[0] as TS) });
  }

  sequence(ts: TS): S.SequenceExpression {
    return new S.SequenceExpression({ expressions: this.named(ts).map((k) => this.expression(k)) });
  }

  element(ts: TS): any {
    if (ts.type === "spread_element") {
      return this.made(ts, new S.SpreadElement({ argument: this.expression(this.named(ts)[0] as TS) }));
    }
    return this.expression(ts);
  }

  object(ts: TS): S.ObjectExpression {
    const properties: any[] = [];
    for (const p of this.named(ts)) {
      if (p.type === "spread_element") {
        properties.push(this.element(p));
      } else if (p.type === "shorthand_property_identifier") {
        properties.push(this.made(p, new S.Property({ propertyKind: "init", key: this.identifier(p), shorthand: true,
          value: this.made(p, new S.Identifier({ name: this.spelling(p) })) })));
      } else if (p.type === "pair") {
        const [key, computed] = this.key(this.require(p, "key"));
        properties.push(this.made(p, new S.Property({ propertyKind: "init", key, computed,
          value: this.expression(this.require(p, "value")) })));
      } else {
        properties.push(this.objectMethod(p)); // a method_definition
      }
    }
    return new S.ObjectExpression({ properties });
  }

  objectMethod(ts: TS): S.Property {
    const modifiers = this.tokensBefore(ts, "name");
    const [key, computed] = this.key(this.require(ts, "name"));
    const value = new S.FunctionExpression({ isAsync: modifiers.has("async"), generator: modifiers.has("*"),
      body: this.block(this.require(ts, "body")) });
    this.signature(ts, value);
    const kind = modifiers.has("get") ? "get" : modifiers.has("set") ? "set" : "init";
    return this.made(ts, new S.Property({ propertyKind: kind, key, computed, method: kind === "init",
      value: this.made(this.require(ts, "parameters"), value) }));
  }

  functionExpression(ts: TS): S.FunctionExpression {
    const made = new S.FunctionExpression({ isAsync: this.has(ts, "async"),
      generator: ts.type === "generator_function" || this.has(ts, "*"), body: this.block(this.require(ts, "body")) });
    const name = this.field(ts, "name");
    made.id = name === null ? null : this.identifier(name);
    this.signature(ts, made);
    return made;
  }

  arrowFunction(ts: TS): S.ArrowFunctionExpression {
    const made = new S.ArrowFunctionExpression({ isAsync: this.has(ts, "async") });
    const parameter = this.field(ts, "parameter");
    if (parameter !== null) made.params = [this.identifier(parameter)];
    else this.signature(ts, made);
    const body = this.require(ts, "body");
    made.body = body.type === "statement_block" ? this.block(body) : this.expression(body);
    return made;
  }

  classExpression(ts: TS): S.ClassExpression {
    const made = new S.ClassExpression();
    this.classParts(ts, made);
    return made;
  }

  template(ts: TS): S.TemplateLiteral {
    const [quasis, expressions] = this.templateParts(ts, "template_substitution", (n) => this.expression(n));
    return new S.TemplateLiteral({ quasis, expressions });
  }

  /** The texts of a template and what is substituted between them. */
  templateParts(ts: TS, holder: string, convert: (ts: TS) => any): [S.TemplateElement[], any[]] {
    const quasis: S.TemplateElement[] = [];
    const values: any[] = [];
    let at = ts.startIndex + 1;
    for (const part of this.named(ts)) {
      if (part.type !== holder) continue;
      quasis.push(this.madeAt(at, new S.TemplateElement({ raw: this.between(at, part.startIndex) })));
      values.push(convert(this.named(part)[0] as TS));
      at = part.endIndex;
    }
    quasis.push(this.madeAt(at, new S.TemplateElement({ raw: this.between(at, ts.endIndex - 1), tail: true })));
    return [quasis, values];
  }

  memberExpression(ts: TS): any {
    const typed = this.typedMember(ts);
    if (typed !== null) return typed;
    const [made, optional] = this.chain(ts);
    return optional ? new S.ChainExpression({ expression: this.made(ts, made) }) : made;
  }

  /** `x as A.B.C`, which tree-sitter-typescript reads as `(x as A.B).C`: a member of an `as` or `satisfies`
   * expression without parentheses, whose names belong to its type. null for any other member. */
  typedMember(ts: TS): any {
    const names: TS[] = [];
    let node = ts;
    while (node.type === "member_expression" && this.field(node, "optional_chain") === null) {
      names.unshift(this.require(node, "property"));
      node = this.require(node, "object");
    }
    if ((node.type !== "as_expression" && node.type !== "satisfies_expression") || this.named(node).length !== 2) {
      return null;
    }
    const [expression, type] = this.named(node) as [TS, TS];
    let last = type; // in `x as A | B.C.D`, the names continue the last type of the union
    while (last.type === "union_type" || last.type === "intersection_type") last = this.named(last).at(-1) as TS;
    if (last.type !== "type_identifier" && last.type !== "nested_type_identifier") return null;
    const converted = this.type(type);
    let reference = converted;
    while (reference instanceof S.TSUnionType || reference instanceof S.TSIntersectionType) {
      reference = reference.types.at(-1);
    }
    let name = reference.typeName;
    for (const n of names) name = this.made(last, new S.TSQualifiedName({ left: name, right: this.identifier(n) }));
    reference.typeName = name;
    const kind = node.type === "as_expression" ? S.TSAsExpression : S.TSSatisfiesExpression;
    return new kind({ expression: this.expression(expression), typeAnnotation: converted });
  }

  /** A member, a call or a non-null assertion, and whether an optional link (`?.`) is in its chain. */
  chain(ts: TS): [any, boolean] {
    if (ts.type === "member_expression") {
      const [target, optional] = this.chain(this.require(ts, "object"));
      const link = this.field(ts, "optional_chain") !== null;
      const [key] = this.key(this.require(ts, "property"));
      const made = new S.MemberExpression({ object: target, optional: link, property: key });
      return [this.made(ts, made), optional || link];
    }
    if (ts.type === "subscript_expression") {
      const [target, optional] = this.chain(this.require(ts, "object"));
      const link = this.field(ts, "optional_chain") !== null;
      const index = this.require(ts, "index");
      return [this.made(ts, new S.MemberExpression({ object: target, optional: link, computed: true,
        property: this.expression(index) })), optional || link];
    }
    if (ts.type === "call_expression" && this.require(ts, "arguments").type !== "template_string"
      && this.require(ts, "function").type !== "import") {
      const [target, optional] = this.chain(this.require(ts, "function"));
      const link = this.has(ts, "?.") || all(ts).some((c) => c.type === "optional_chain");
      const made = new S.CallExpression({ callee: target, optional: link,
        arguments: this.named(this.require(ts, "arguments")).map((a) => this.element(a)) });
      const args = this.field(ts, "type_arguments");
      if (args !== null) made.typeArguments = this.typeArguments(args);
      return [this.made(ts, made), optional || link];
    }
    if (ts.type === "non_null_expression") {
      const inner = this.named(ts)[0] as TS;
      if (inner.type === "binary_expression") return [this.nonNullLast(this.expression(inner)), false];
      const [target, optional] = this.chain(inner);
      return [this.made(ts, new S.TSNonNullExpression({ expression: target })), optional];
    }
    return [this.expression(ts), false];
  }

  /** `node` with its last operand asserted non-null: `a ?? b!` is `a ?? (b!)`, which tree-sitter-typescript reads as
   * `(a ?? b)!`. */
  nonNullLast(node: any): any {
    if (node instanceof S.BinaryExpression || node instanceof S.LogicalExpression) {
      node.right = this.nonNullLast(node.right);
      return node;
    }
    const made = new S.TSNonNullExpression({ expression: node });
    this.positions.set(made, this.positions.get(node) as number);
    return made;
  }

  link(ts: TS): any {
    const [chained, optional] = this.chain(ts);
    const made = this.made(ts, chained);
    return optional ? new S.ChainExpression({ expression: made }) : made;
  }

  call(ts: TS): any {
    const fn = this.require(ts, "function");
    const args = this.require(ts, "arguments");
    if (args.type === "template_string") {
      // tree-sitter-typescript reads `f<T>`x`` as comparisons: a tagged template has no type arguments
      return new S.TaggedTemplateExpression({ tag: this.expression(fn), quasi: this.expression(args) });
    }
    if (fn.type === "import") {
      const values = this.named(args).map((a) => this.expression(a));
      return new S.ImportExpression({ source: values[0], options: values.length > 1 ? values[1] : null });
    }
    const [made, optional] = this.chain(ts);
    return optional ? new S.ChainExpression({ expression: this.made(ts, made) }) : made;
  }

  newExpression(ts: TS): S.NewExpression {
    const made = new S.NewExpression({ callee: this.expression(this.require(ts, "constructor")) });
    const args = this.field(ts, "arguments");
    if (args !== null) made.arguments = this.named(args).map((a) => this.element(a));
    const typeArguments = this.field(ts, "type_arguments");
    if (typeArguments !== null) made.typeArguments = this.typeArguments(typeArguments);
    return made;
  }

  metaProperty(ts: TS): S.MetaProperty {
    const [meta, property] = this.text(ts).replaceAll(" ", "").split(".") as [string, string];
    const kids = this.kids(ts);
    return new S.MetaProperty({ meta: this.made(kids[0] as TS, new S.Identifier({ name: meta })),
      property: this.made(kids.at(-1) as TS, new S.Identifier({ name: property })) });
  }

  update(ts: TS): S.UpdateExpression {
    const operator = this.require(ts, "operator");
    const argument = this.require(ts, "argument");
    return new S.UpdateExpression({ operator: this.text(operator) as S.UpdateOperator,
      prefix: operator.startIndex < argument.startIndex, argument: this.expression(argument) });
  }

  unary(ts: TS): S.UnaryExpression {
    return new S.UnaryExpression({ operator: this.text(this.require(ts, "operator")) as S.UnaryOperator,
      argument: this.expression(this.require(ts, "argument")) });
  }

  binary(ts: TS): any {
    const operator = this.text(this.require(ts, "operator"));
    const left = this.require(ts, "left");
    const converted = left.type === "private_property_identifier"
      ? this.made(left, new S.PrivateIdentifier({ name: this.text(left).slice(1) })) : this.expression(left);
    const right = this.expression(this.require(ts, "right"));
    if (left.type === "as_expression" || left.type === "satisfies_expression") {
      return this.binaryLast(converted, operator, right);
    }
    return operate(converted, operator, right);
  }

  /** `left operator right`, where `left` was an `as` or `satisfies` expression that `typedLast` moved onto its last
   * operand: `a || b as T && c` is `a || (b as T && c)`, which tree-sitter-typescript reads as `((a || b) as T) && c`.
   * The operator applies to that last operand when it binds tighter than `left`'s. */
  binaryLast(left: any, operator: string, right: any): any {
    if ((left instanceof S.BinaryExpression || left instanceof S.LogicalExpression)
      && (BINDS[left.operator as string] as number) < (BINDS[operator] as number)) {
      left.right = this.binaryLast(left.right, operator, right);
      return left;
    }
    const made = operate(left, operator, right);
    this.positions.set(made, this.positions.get(left) as number); // where its left operand starts
    return made;
  }

  assignment(ts: TS): S.AssignmentExpression {
    const operator = this.field(ts, "operator");
    return new S.AssignmentExpression({ left: this.target(this.require(ts, "left")),
      operator: (operator === null ? "=" : this.text(operator)) as S.AssignmentOperator,
      right: this.expression(this.require(ts, "right")) });
  }

  ternary(ts: TS): S.ConditionalExpression {
    return new S.ConditionalExpression({ test: this.expression(this.require(ts, "condition")),
      consequent: this.expression(this.require(ts, "consequence")),
      alternate: this.expression(this.require(ts, "alternative")) });
  }

  yieldExpression(ts: TS): S.YieldExpression {
    const kids = this.named(ts);
    return new S.YieldExpression({ delegate: this.has(ts, "*"),
      argument: kids.length > 0 ? this.expression(kids[0] as TS) : null });
  }

  /** `node` with `as type` (or `satisfies type`) applied to its last operand when that binds tighter than its
   * operator: `a ?? b as T` is `a ?? (b as T)`, which tree-sitter-typescript reads as `(a ?? b) as T`. */
  typedLast(node: any, kind: typeof S.TSAsExpression | typeof S.TSSatisfiesExpression, type: any): any {
    if ((node instanceof S.BinaryExpression || node instanceof S.LogicalExpression)
      && LOOSER_THAN_AS.has(node.operator as string)) {
      node.right = this.typedLast(node.right, kind, type);
      return node;
    }
    const made = new kind({ expression: node, typeAnnotation: type });
    this.positions.set(made, this.positions.get(node) as number);
    return made;
  }

  /** `expression as type` or `expression satisfies type`. */
  typed(ts: TS, kind: typeof S.TSAsExpression | typeof S.TSSatisfiesExpression): any {
    const kids = this.named(ts);
    const expression = kids[0] as TS;
    let converted: any;
    if (kids.length === 1 || (kids[1] as TS).type === "const") { // `as const`
      const constant = all(ts).find((c) => c.type === "const") as TS;
      converted = this.made(constant, new S.TSTypeReference({
        typeName: this.made(constant, new S.Identifier({ name: "const" })) }));
    } else {
      converted = this.type(kids[1] as TS);
    }
    const inner = this.expression(expression);
    if (expression.type === "binary_expression") return this.typedLast(inner, kind, converted);
    return new kind({ expression: inner, typeAnnotation: converted });
  }

  typeAssertion(ts: TS): S.TSTypeAssertion {
    const [args, expression] = this.named(ts) as [TS, TS];
    return new S.TSTypeAssertion({ typeAnnotation: this.type(this.named(args)[0] as TS),
      expression: this.expression(expression) });
  }

  instantiation(ts: TS): S.TSInstantiationExpression {
    return new S.TSInstantiationExpression({ expression: this.expression(this.named(ts)[0] as TS),
      typeArguments: this.typeArguments(this.require(ts, "type_arguments")) });
  }

  // Types

  /** A `type_annotation` (`: type`), or a return type: `: x is T`, `: asserts x`. */
  annotation(ts: TS): S.TSTypeAnnotation {
    if (ts.type === "type_predicate_annotation" || ts.type === "asserts_annotation") {
      return this.made(ts, new S.TSTypeAnnotation({ typeAnnotation: this.predicate(this.named(ts)[0] as TS) }));
    }
    return this.made(ts, new S.TSTypeAnnotation({ typeAnnotation: this.type(this.named(ts)[0] as TS) }));
  }

  predicate(ts: TS): S.TSTypePredicate {
    if (ts.type === "asserts") {
      const inner = this.named(ts)[0] as TS;
      if (inner.type === "type_predicate") {
        const made = this.predicate(inner);
        made.asserts = true;
        return this.made(ts, made);
      }
      return this.made(ts, new S.TSTypePredicate({ asserts: true, parameterName: this.predicateName(inner) }));
    }
    const name = this.require(ts, "name");
    const type = this.require(ts, "type");
    return this.made(ts, new S.TSTypePredicate({ parameterName: this.predicateName(name),
      typeAnnotation: this.made(type, new S.TSTypeAnnotation({ typeAnnotation: this.type(type) })) }));
  }

  predicateName(ts: TS): any {
    return ts.type === "this" ? this.made(ts, new S.TSThisType()) : this.identifier(ts);
  }

  type(ts: TS): any {
    const method = Converter.TYPES[ts.type];
    if (method === undefined) throw this.unsupported(ts);
    return this.made(ts, method(this, ts));
  }

  predefined(ts: TS): any {
    const text = this.text(ts).split(/\s+/).filter((w) => w !== "").join(" ");
    if (text === "unique symbol") {
      return new S.TSTypeOperator({ operator: "unique", typeAnnotation: this.made(all(ts).at(-1) as TS,
        new S.TSSymbolKeyword()) });
    }
    return new (KEYWORD_TYPES[text] as new () => Node)();
  }

  typeReference(ts: TS): any {
    const keyword = KEYWORD_TYPES[this.text(ts)];
    if (keyword !== undefined && this.text(ts) !== "intrinsic") return new keyword(); // `bigint` is read as a name
    return this.importOrReference(ts);
  }

  generic(ts: TS): any {
    const name = this.require(ts, "name");
    const args = this.require(ts, "type_arguments");
    return this.importType(name, args) ?? new S.TSTypeReference({ typeName: this.entityName(name),
      typeArguments: this.typeArguments(args) });
  }

  typeArguments(ts: TS): S.TSTypeParameterInstantiation {
    return this.made(ts, new S.TSTypeParameterInstantiation({ params: this.named(ts).map((t) => this.type(t)) }));
  }

  typeParameters(ts: TS): S.TSTypeParameterDeclaration {
    const params = this.named(ts).map((p) => this.typeParameter(p));
    return this.made(ts, new S.TSTypeParameterDeclaration({ params }));
  }

  typeParameter(ts: TS): S.TSTypeParameter {
    const name = this.require(ts, "name");
    const variance = this.pre.variance.get(this.at(name)) ?? new Set<string>();
    const made = new S.TSTypeParameter({ const: this.has(ts, "const"), isIn: variance.has("in") || this.has(ts, "in"),
      isOut: variance.has("out") || all(ts).some((c) => c.type === "out"), name: this.identifier(name) });
    const constraint = this.field(ts, "constraint");
    if (constraint !== null) made.constraint = this.type(this.named(constraint)[0] as TS);
    const fallback = this.field(ts, "value");
    if (fallback !== null) made.default = this.type(this.named(fallback)[0] as TS);
    return this.made(ts, made);
  }

  /** A union or an intersection, whose nested ones of the same kind flatten. */
  flat(ts: TS, kind: typeof S.TSUnionType | typeof S.TSIntersectionType): any {
    const types: any[] = [];
    for (const t of this.named(ts)) {
      if (t.type === ts.type) {
        types.push(...this.made(t, this.flat(t, kind)).types);
        continue;
      }
      const converted = this.type(t);
      if (t.type === "readonly_type" && converted.constructor === kind) types.push(...converted.types); // a union
      else types.push(converted);
    }
    return new kind({ types });
  }

  literalType(ts: TS): any {
    const inner = this.named(ts)[0] as TS;
    if (inner.type === "unary_expression") return new S.TSLiteralType({ literal: this.expression(inner) });
    if (inner.type === "null") return new S.TSNullKeyword();
    if (inner.type === "undefined") return new S.TSUndefinedKeyword();
    return new S.TSLiteralType({ literal: this.literal(inner) });
  }

  functionType(ts: TS): S.TSFunctionType {
    const made = new S.TSFunctionType();
    const parameters = this.field(ts, "type_parameters");
    if (parameters !== null) made.typeParameters = this.typeParameters(parameters);
    made.params = this.parameters(this.require(ts, "parameters"));
    const returns = this.require(ts, "return_type");
    made.returnType = this.made(returns, new S.TSTypeAnnotation({
      typeAnnotation: returns.type === "type_predicate" || returns.type === "asserts" ? this.predicate(returns)
        : this.type(returns) }));
    return made;
  }

  constructorType(ts: TS): S.TSConstructorType {
    const made = new S.TSConstructorType({ abstract: this.has(ts, "abstract") });
    const parameters = this.field(ts, "type_parameters");
    if (parameters !== null) made.typeParameters = this.typeParameters(parameters);
    made.params = this.parameters(this.require(ts, "parameters"));
    const returns = this.require(ts, "type");
    made.returnType = this.made(returns, new S.TSTypeAnnotation({ typeAnnotation: this.type(returns) }));
    return made;
  }

  tupleType(ts: TS): S.TSTupleType {
    const out: any[] = [];
    for (const element of this.named(ts)) {
      if (element.type === "required_parameter" || element.type === "optional_parameter") {
        const name = this.require(element, "name");
        const annotation = this.named(this.require(element, "type"))[0] as TS;
        if (name.type === "rest_pattern") {
          const member = new S.TSNamedTupleMember({ label: this.identifier(this.named(name)[0] as TS),
            elementType: this.type(annotation) });
          out.push(this.made(element, new S.TSRestType({ typeAnnotation: this.made(element, member) })));
          continue;
        }
        out.push(this.made(element, new S.TSNamedTupleMember({ label: this.identifier(name),
          optional: element.type === "optional_parameter", elementType: this.type(annotation) })));
      } else {
        out.push(this.type(element));
      }
    }
    return new S.TSTupleType({ elementTypes: out });
  }

  objectType(ts: TS): any {
    const members = this.named(ts);
    if (members.length === 1 && (members[0] as TS).type === "index_signature"
      && this.named(members[0] as TS).some((c) => c.type === "mapped_type_clause")) {
      return this.mapped(members[0] as TS);
    }
    return new S.TSTypeLiteral({ members: this.listed(all(ts), (n) => this.typeMember(n), all(ts)[0]) });
  }

  mapped(ts: TS): S.TSMappedType {
    const clause = this.named(ts).find((c) => c.type === "mapped_type_clause") as TS;
    const made = new S.TSMappedType({ key: this.identifier(this.require(clause, "name")),
      constraint: this.type(this.require(clause, "type")) });
    const alias = this.field(clause, "alias");
    if (alias !== null) made.nameType = this.type(alias);
    const sign = this.field(ts, "sign");
    if (this.kids(ts).some((c) => c.type === "readonly")) {
      made.readonly = ((sign !== null && sign.startIndex < clause.startIndex ? this.text(sign) : "") + "readonly") as
        S.MappedReadonly;
    }
    const annotation = this.require(ts, "type");
    if (annotation.type === "adding_type_annotation") made.optional = "+?";
    else if (annotation.type === "omitting_type_annotation") made.optional = "-?";
    else if (annotation.type === "opting_type_annotation") made.optional = "?";
    made.typeAnnotation = this.type(this.named(annotation)[0] as TS); // tree-sitter-typescript reads none without one
    return made;
  }

  typeMember(ts: TS): any {
    if (ts.type === "property_signature") {
      const modifiers = this.tokensBefore(ts, "name");
      const [key, computed] = this.key(this.require(ts, "name"));
      const made = new S.TSPropertySignature({ readonly: modifiers.has("readonly"), static: modifiers.has("static"),
        key,
        computed, optional: this.has(ts, "?") });
      const annotation = this.field(ts, "type");
      if (annotation !== null) made.typeAnnotation = this.annotation(annotation);
      return this.made(ts, made);
    }
    if (ts.type === "method_signature") {
      const modifiers = this.tokensBefore(ts, "name");
      const [key, computed] = this.key(this.require(ts, "name"));
      const made = new S.TSMethodSignature({
        methodKind: modifiers.has("get") ? "get" : modifiers.has("set") ? "set" : "method", key, computed,
        optional: this.has(ts, "?") });
      this.signature(ts, made);
      return this.made(ts, made);
    }
    if (ts.type === "call_signature") {
      const made = new S.TSCallSignatureDeclaration();
      this.signature(ts, made);
      return this.made(ts, made);
    }
    if (ts.type === "construct_signature") {
      const made = new S.TSConstructSignatureDeclaration();
      this.signature(ts, made);
      return this.made(ts, made);
    }
    return this.indexSignature(ts);
  }

  typeQuery(ts: TS): S.TSTypeQuery {
    const inner = this.named(ts)[0] as TS;
    if (inner.type === "instantiation_expression") {
      const name = this.named(inner)[0] as TS;
      return new S.TSTypeQuery({ exprName: this.importType(name) ?? this.entityName(name),
        typeArguments: this.typeArguments(this.require(inner, "type_arguments")) });
    }
    return new S.TSTypeQuery({ exprName: this.importType(inner) ?? this.entityName(inner) });
  }

  /** The import at the root of the dotted name `ts`, `import('m').a.b`, and the names after it; null if it has none.
   * The import is a call, or the name the pre-pass put in its place. */
  importRoot(ts: TS): [TS, TS[]] | null {
    const names: TS[] = [];
    let node = ts;
    while (["member_expression", "nested_identifier", "nested_type_identifier"].includes(node.type)) {
      if (node.type === "nested_type_identifier") {
        names.unshift(this.require(node, "name"));
        node = this.require(node, "module");
      } else {
        names.unshift(this.require(node, "property"));
        node = this.require(node, "object");
      }
    }
    if (node.type === "call_expression" && this.require(node, "function").type === "import") return [node, names];
    if ((node.type === "identifier" || node.type === "type_identifier") && this.placeholder(node)) {
      return [node, names];
    }
    return null;
  }

  /** `import('m').a.b<arguments>` as a type; null if `ts` is not rooted at an import. */
  importType(ts: TS, args: TS | null = null): S.TSImportType | null {
    const root = this.importRoot(ts);
    if (root === null) return null;
    const [call, names] = root;
    const made = new S.TSImportType(this.importCall(call));
    let qualifier: any = null;
    for (const name of names) {
      const right = this.identifier(name);
      qualifier = qualifier === null ? right : this.made(name, new S.TSQualifiedName({ left: qualifier, right }));
    }
    made.qualifier = qualifier;
    if (args !== null) made.typeArguments = this.typeArguments(args);
    return this.made(ts, made);
  }

  /** The source and options of `import(source, options)`: a call, or the name the pre-pass put in its place, whose
   * text is parsed again. */
  importCall(ts: TS): { source: any; options: any } {
    if (ts.type === "call_expression") {
      const args = this.named(this.require(ts, "arguments"));
      return { source: this.expression(args[0] as TS),
        options: args.length > 1 ? this.expression(args[1] as TS) : null };
    }
    const start = this.at(ts);
    const source = new Source(this.origin.slice(start, this.shift + this.source.offset(ts.endIndex)));
    const tree = PARSERS.false.parse(source.text) as NonNullable<ReturnType<TSParser["parse"]>>;
    const converter = new Converter(source, new Prepared(), start, this.origin);
    converter.check(tree.rootNode);
    const call = converter.named(converter.named(tree.rootNode)[0] as TS)[0] as TS;
    const parts = converter.importCall(call);
    tree.delete();
    for (const [node, at] of converter.positions) this.positions.set(node, at);
    return parts;
  }

  /** A type that is `import('m').a.b`, or a type reference. */
  importOrReference(ts: TS): any {
    return this.importType(ts) ?? new S.TSTypeReference({ typeName: this.entityName(ts) });
  }

  templateType(ts: TS): S.TSTemplateLiteralType {
    const [quasis, types] = this.templateParts(ts, "template_type", (n) => this.type(n));
    return new S.TSTemplateLiteralType({ quasis, types });
  }

  infer(ts: TS): S.TSInferType {
    const kids = this.named(ts);
    const parameter = new S.TSTypeParameter({ name: this.identifier(kids[0] as TS) });
    if (kids.length > 1) parameter.constraint = this.type(kids[1] as TS);
    return new S.TSInferType({ typeParameter: this.made(kids[0] as TS, parameter) });
  }

  lookup(ts: TS): S.TSIndexedAccessType {
    const [objectType, indexType] = this.named(ts) as [TS, TS];
    return new S.TSIndexedAccessType({ objectType: this.type(objectType), indexType: this.type(indexType) });
  }

  /** `readonly T`, which binds tighter than `|` and `&`: tree-sitter-typescript reads `readonly A[] | B` as
   * `readonly (A[] | B)`. */
  readonly(ts: TS): any {
    const inner = this.named(ts)[0] as TS;
    if (inner.type === "union_type" || inner.type === "intersection_type") return this.readonlyFirst(inner, ts);
    return new S.TSTypeOperator({ operator: "readonly", typeAnnotation: this.type(inner) });
  }

  /** The union or intersection `ts`, with its first member made readonly. */
  readonlyFirst(ts: TS, at: TS): any {
    const members = this.named(ts);
    const kind = ts.type === "union_type" ? S.TSUnionType : S.TSIntersectionType;
    let types: any[];
    if ((members[0] as TS).type === ts.type) {
      types = this.readonlyFirst(members[0] as TS, at).types;
    } else {
      const first = new S.TSTypeOperator({ operator: "readonly", typeAnnotation: this.type(members[0] as TS) });
      types = [this.made(at, first)];
    }
    types.push(...members.slice(1).map((m) => this.type(m))); // a union groups to the left: only its first may be one
    return this.made(at, new kind({ types }));
  }

  // JSX

  jsxElement(ts: TS): any {
    if (ts.type === "jsx_self_closing_element") {
      const opening = this.made(ts, new S.JSXOpeningElement({ selfClosing: true }));
      this.jsxTag(ts, opening);
      return new S.JSXElement({ openingElement: opening });
    }
    const openTag = this.require(ts, "open_tag");
    const closeTag = this.require(ts, "close_tag");
    const children = this.jsxChildren(openTag, closeTag, this.named(ts).filter((c) => c.id !== openTag.id
      && c.id !== closeTag.id && c.type !== "jsx_text" && c.type !== "html_character_reference"));
    if (this.field(openTag, "name") === null) {
      return new S.JSXFragment({ openingFragment: this.made(openTag, new S.JSXOpeningFragment()), children,
        closingFragment: this.made(closeTag, new S.JSXClosingFragment()) });
    }
    const opening = this.made(openTag, new S.JSXOpeningElement());
    this.jsxTag(openTag, opening);
    const closing = this.made(closeTag, new S.JSXClosingElement({
      name: this.jsxName(this.require(closeTag, "name")) }));
    return new S.JSXElement({ openingElement: opening, children, closingElement: closing });
  }

  jsxTag(ts: TS, made: S.JSXOpeningElement): void {
    made.name = this.jsxName(this.require(ts, "name"));
    const args = this.field(ts, "type_arguments");
    if (args !== null) made.typeArguments = this.typeArguments(args);
    for (const attribute of this.fields(ts, "attribute")) {
      if (attribute.type === "jsx_expression") {
        made.attributes.push(this.made(attribute, new S.JSXSpreadAttribute({
          argument: this.expression(this.named(this.named(attribute)[0] as TS)[0] as TS) })));
        continue;
      }
      const [name, ...value] = this.named(attribute) as [TS, ...TS[]];
      const converted = new S.JSXAttribute({ name: this.jsxName(name) });
      if (value.length > 0) {
        const inner = value[0] as TS;
        converted.value = inner.type === "string" ? this.literal(inner) : this.jsxChild(inner);
      }
      made.attributes.push(this.made(attribute, converted));
    }
  }

  jsxName(ts: TS): any {
    if (ts.type === "member_expression") {
      return this.made(ts, new S.JSXMemberExpression({ object: this.jsxName(this.require(ts, "object")),
        property: this.jsxName(this.require(ts, "property")) }));
    }
    if (ts.type === "jsx_namespace_name") {
      const [namespace, name] = this.named(ts) as [TS, TS];
      return this.made(ts, new S.JSXNamespacedName({ namespace: this.jsxName(namespace), name: this.jsxName(name) }));
    }
    return this.made(ts, new S.JSXIdentifier({ name: this.text(ts) }));
  }

  /** An element's children: its elements and expressions, and the text between them, as written. Text is whatever lies
   * between the others: tree-sitter-typescript leaves out the text that is only whitespace, and splits the rest at
   * character references (`&amp;`). */
  jsxChildren(openTag: TS, closeTag: TS, nodes: TS[]): any[] {
    const out: any[] = [];
    let at = openTag.endIndex;
    for (const ts of [...nodes, closeTag]) {
      if (ts.startIndex > at) out.push(this.madeAt(at, new S.JSXText({ raw: this.between(at, ts.startIndex) })));
      if (ts.id !== closeTag.id) out.push(this.jsxChild(ts));
      at = ts.endIndex;
    }
    return out;
  }

  /** An element's child or an attribute's value, but text, which `jsxChildren` reads. */
  jsxChild(ts: TS): any {
    if (ts.type === "jsx_expression") {
      const inner = this.named(ts);
      if (inner.length === 0) {
        return this.made(ts, new S.JSXExpressionContainer({ expression: this.made(ts, new S.JSXEmptyExpression()) }));
      }
      if ((inner[0] as TS).type === "spread_element") {
        const spread = this.expression(this.named(inner[0] as TS)[0] as TS);
        return this.made(ts, new S.JSXSpreadChild({ expression: spread }));
      }
      return this.made(ts, new S.JSXExpressionContainer({ expression: this.expression(inner[0] as TS) }));
    }
    return this.expression(ts);
  }
}

/** `left operator right`, a logical or a binary expression. */
function operate(left: any, operator: string, right: any): any {
  if (LOGICAL.has(operator)) return new S.LogicalExpression({ left, operator: operator as S.LogicalOperator, right });
  return new S.BinaryExpression({ left, operator: operator as S.BinaryOperator, right });
}

const C = Converter.prototype;
const bind = (method: (this: Converter, ts: TS) => any): Method => (self, ts) => method.call(self, ts);
const jump = (kind: typeof S.BreakStatement | typeof S.ContinueStatement): Method => (self, ts) => {
  const label = self.field(ts, "label");
  return new kind({ label: label === null ? null : self.identifier(label) });
};

Converter.STATEMENTS = {
  expression_statement: bind(C.expressionStatement), lexical_declaration: bind(C.lexicalDeclaration),
  variable_declaration: bind(C.variableDeclaration), return_statement: bind(C.returnStatement),
  throw_statement: bind(C.throwStatement), if_statement: bind(C.ifStatement), while_statement: bind(C.whileStatement),
  do_statement: bind(C.doStatement), with_statement: bind(C.withStatement), for_statement: bind(C.forStatement),
  for_in_statement: bind(C.forInStatement), switch_statement: bind(C.switchStatement),
  try_statement: bind(C.tryStatement), labeled_statement: bind(C.labeledStatement),
  break_statement: jump(S.BreakStatement), continue_statement: jump(S.ContinueStatement),
  empty_statement: () => new S.EmptyStatement(), debugger_statement: () => new S.DebuggerStatement(),
  statement_block: bind(C.block), function_declaration: bind(C.functionDeclaration),
  generator_function_declaration: bind(C.functionDeclaration), function_signature: bind(C.functionSignature),
  class_declaration: bind(C.classDeclaration), abstract_class_declaration: bind(C.classDeclaration),
  import_statement: bind(C.importStatement), import_alias: bind(C.importAlias),
  export_statement: bind(C.exportStatement),
  ambient_declaration: bind(C.ambientDeclaration), module: (self, ts) => self.module(ts),
  internal_module: (self, ts) => self.module(ts), type_alias_declaration: bind(C.typeAliasDeclaration),
  interface_declaration: bind(C.interfaceDeclaration), enum_declaration: bind(C.enumDeclaration),
};

Converter.EXPRESSIONS = {
  identifier: (self, ts) => self.placeholder(ts) ? new S.ImportExpression(self.importCall(ts))
    : new S.Identifier({ name: self.spelling(ts) }),
  undefined: () => new S.Identifier({ name: "undefined" }),
  number: (self, ts) => new S.Literal({ raw: self.text(ts) }),
  string: (self, ts) => new S.Literal({ raw: self.text(ts) }),
  true: () => new S.Literal({ raw: "true" }), false: () => new S.Literal({ raw: "false" }),
  null: () => new S.Literal({ raw: "null" }), regex: (self, ts) => new S.Literal({ raw: self.text(ts) }),
  this: () => new S.ThisExpression(), super: () => new S.Super(),
  parenthesized_expression: bind(C.parenthesized), sequence_expression: bind(C.sequence),
  array: (self, ts) => new S.ArrayExpression({ elements: self.elements(ts, (n) => self.element(n)) }),
  object: bind(C.object), function_expression: bind(C.functionExpression),
  generator_function: bind(C.functionExpression),
  arrow_function: bind(C.arrowFunction), class: bind(C.classExpression), template_string: bind(C.template),
  member_expression: bind(C.memberExpression), subscript_expression: bind(C.memberExpression),
  call_expression: bind(C.call),
  non_null_expression: bind(C.link), new_expression: bind(C.newExpression), meta_property: bind(C.metaProperty),
  update_expression: bind(C.update), unary_expression: bind(C.unary),
  await_expression: (self, ts) => new S.AwaitExpression({ argument: self.expression(self.named(ts)[0] as TS) }),
  binary_expression: bind(C.binary), assignment_expression: bind(C.assignment),
  augmented_assignment_expression: bind(C.assignment), ternary_expression: bind(C.ternary),
  yield_expression: bind(C.yieldExpression), as_expression: (self, ts) => self.typed(ts, S.TSAsExpression),
  satisfies_expression: (self, ts) => self.typed(ts, S.TSSatisfiesExpression), type_assertion: bind(C.typeAssertion),
  instantiation_expression: bind(C.instantiation),
  array_pattern: (self, ts) => new S.ArrayPattern({ elements: self.elements(ts, (n) => self.target(n)) }),
  object_pattern: (self, ts) => new S.ObjectPattern({ properties: self.named(ts).map((p) => self.patternProperty(p)) }),
  jsx_element: bind(C.jsxElement), jsx_self_closing_element: bind(C.jsxElement),
  internal_module: (self, ts) => self.module(ts, "namespace"),
};

Converter.TYPES = {
  predefined_type: bind(C.predefined), type_identifier: bind(C.typeReference), identifier: bind(C.typeReference),
  nested_type_identifier: bind(C.importOrReference), generic_type: bind(C.generic),
  member_expression: bind(C.importOrReference), this_type: () => new S.TSThisType(),
  parenthesized_type: (self, ts) => new S.TSParenthesizedType({ typeAnnotation: self.type(self.named(ts)[0] as TS) }),
  literal_type: bind(C.literalType),
  array_type: (self, ts) => new S.TSArrayType({ elementType: self.type(self.named(ts)[0] as TS) }),
  tuple_type: bind(C.tupleType), union_type: (self, ts) => self.flat(ts, S.TSUnionType),
  intersection_type: (self, ts) => self.flat(ts, S.TSIntersectionType), function_type: bind(C.functionType),
  constructor_type: bind(C.constructorType), object_type: bind(C.objectType),
  index_type_query: (self, ts) => new S.TSTypeOperator({ operator: "keyof",
    typeAnnotation: self.type(self.named(ts)[0] as TS) }),
  readonly_type: bind(C.readonly), lookup_type: bind(C.lookup), type_query: bind(C.typeQuery),
  template_literal_type: bind(C.templateType),
  conditional_type: (self, ts) => new S.TSConditionalType({ checkType: self.type(self.require(ts, "left")),
    extendsType: self.type(self.require(ts, "right")), trueType: self.type(self.require(ts, "consequence")),
    falseType: self.type(self.require(ts, "alternative")) }),
  infer_type: bind(C.infer),
  optional_type: (self, ts) => new S.TSOptionalType({ typeAnnotation: self.type(self.named(ts)[0] as TS) }),
  rest_type: (self, ts) => new S.TSRestType({ typeAnnotation: self.type(self.named(ts)[0] as TS) }),
  type_predicate: bind(C.predicate), asserts: bind(C.predicate), call_expression: bind(C.importOrReference),
  const: (self, ts) => new S.TSTypeReference({ typeName: self.made(ts, new S.Identifier({ name: "const" })) }),
  template_type: (self, ts) => self.type(self.named(ts)[0] as TS),
};

/** The tree of `text`, with the `tsx` grammar if `jsx`, the offset where each of its nodes starts, and the source, for
 * locating problems. Throws `ParseError` for text tree-sitter-typescript cannot parse. */
export function parse(text: string, jsx = false): [S.Program, Map<Node, number>, Source] {
  const grammar = jsx ? PARSERS.true : PARSERS.false;
  let source = new Source(text);
  let tree = grammar.parse(text) as NonNullable<ReturnType<TSParser["parse"]>>;
  let prepared = new Prepared();
  if (tree.rootNode.hasError) {
    const [cleaned, found] = prepare(text, tree.rootNode, source);
    tree.delete();
    prepared = found;
    source = new Source(text, cleaned);
    tree = grammar.parse(cleaned) as NonNullable<ReturnType<TSParser["parse"]>>;
  }
  const converter = new Converter(source, prepared);
  const program = converter.program(tree.rootNode);
  tree.delete();
  return [program, converter.positions, source];
}
