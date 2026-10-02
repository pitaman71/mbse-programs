/**
 * Parses Python source text into Python trees, delegating to tree-sitter-python (through web-tree-sitter).
 *
 * tree-sitter-python builds a concrete syntax tree; `Converter` rewrites it into Python kinds, one tree-sitter node
 * type at a time. tree-sitter-python 0.25 cannot parse three constructs of Python 3.13 and later. When the text does
 * not parse, a pre-pass (`prepare`) rewrites them, keeping every other character where it was: it moves `lazy` after
 * the `import` or `from` it qualifies, and removes the `**` of a dict comprehension that unpacks and the defaults of
 * type parameters. The converter puts them back where they were.
 *
 * Positions are counted in characters (code points), never UTF-16 units, so that every implementation reports the same
 * line and column.
 */

import type { Node as TS, Parser as TSParser } from "web-tree-sitter";

import { ParseError } from "../Framework/Errors.js";
import { type SyntaxNode, walk } from "../Framework/Syntax.js";
import { parser } from "../Framework/_TreeSitter.js";
import * as S from "./Syntax.js";

const PARSER = await parser("tree-sitter-python/tree-sitter-python.wasm");

const EXTRAS = new Set(["comment", "line_continuation"]);
const PYTHON2 = new Set(["exec_statement"]);
const CLAUSES = new Set(["elif_clause", "else_clause", "except_clause", "finally_clause", "case_clause"]);
/** Python's binary operators, by precedence, the loosest first. tree-sitter-python 0.25 groups `^` and `&` as one
 * level, so the converter regroups chains of binary operators by these. */
const LEVELS: readonly (readonly string[])[] = [
  ["|"], ["^"], ["&"], ["<<", ">>"], ["+", "-"], ["*", "@", "/", "//", "%"], ["**"],
];
const DEPTH: Record<string, number> = { "(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1 };

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

  error(message: string, offset: number): ParseError {
    const before = this.characters.slice(0, offset);
    const line = before.filter((ch) => ch === "\n").length + 1;
    return new ParseError(message, line, offset - (before.lastIndexOf("\n") + 1) + 1);
  }
}

// --- The pre-pass: what tree-sitter-python cannot parse ---

/** What the pre-pass rewrote, by the character offset where the construct starts: lazy imports, set comprehensions
 * that are dict comprehensions that unpack, and type parameters' defaults (the offset and text of each default). */
class Prepared {
  readonly lazy = new Set<number>();
  readonly unpacking = new Set<number>();
  readonly defaults = new Map<number, [number, string]>();
}

type Token = [number, number, string];

const all = (ts: TS): TS[] => ts.children.filter((c): c is TS => c !== null);

/** The tokens of a tree, as UTF-16 spans and their text: each leaf, but each string whole, without comments. */
function tokens(text: string, root: TS): Token[] {
  const out: Token[] = [];
  const stack = [root];
  while (stack.length > 0) {
    const ts = stack.pop() as TS;
    if (EXTRAS.has(ts.type)) continue;
    if (ts.childCount === 0 || ts.type === "string") {
      out.push([ts.startIndex, ts.endIndex, text.slice(ts.startIndex, ts.endIndex)]);
      continue;
    }
    stack.push(...all(ts).reverse());
  }
  return out;
}

/** The index of the bracket that closes the one at `found[i]`, or of the last token if none does. */
function closing(found: Token[], i: number): number {
  let depth = 0;
  for (let j = i; j < found.length; j++) {
    const word = (found[j] as Token)[2];
    if (word === "(" || word === "[" || word === "{") {
      depth++;
    } else if (word === ")" || word === "]" || word === "}") {
      depth--;
      if (depth === 0) return j;
    }
  }
  return found.length - 1;
}

/** The text with the constructs tree-sitter-python cannot parse rewritten, and what was rewritten. */
function prepare(text: string, root: TS, source: Source): [string, Prepared] {
  const found = new Prepared();
  const units = text.split("");
  const list = tokens(text, root);
  const blank = (start: number, end: number): void => {
    for (let p = start; p < end; p++) if (units[p] !== "\n") units[p] = " ";
  };
  list.forEach(([start, , word], i) => {
    const following = i + 1 < list.length ? (list[i + 1] as Token)[2] : "";
    const lineStart = text.lastIndexOf("\n", start - 1) + 1;
    if (word === "lazy" && (following === "import" || following === "from") && text.slice(lineStart, start).trim() === "") {
      // `lazy import` becomes `import    `, which keeps the statement where it starts
      const after = list[i + 1] as Token;
      units.splice(start, after[1] - start, ...following.padEnd(after[1] - start).split(""));
      found.lazy.add(source.offset(start));
    } else if (word === "{" && following === "**") {
      const close = closing(list, i);
      let depth = 0;
      let comprehension = false;
      for (const [, , inner] of list.slice(i + 1, close)) {
        depth += DEPTH[inner] ?? 0;
        if (depth === 0 && inner === ":") return;
        comprehension ||= depth === 0 && inner === "for";
      }
      if (comprehension) {
        blank((list[i + 1] as Token)[0], (list[i + 1] as Token)[1]);
        found.unpacking.add(source.offset(start));
      }
    } else if (word === "[" && i >= 2 && ["def", "class", "type"].includes((list[i - 2] as Token)[2])) {
      const close = closing(list, i);
      let depth = 0;
      let parameter: number | null = null;
      let equals: number | null = null;
      for (let j = i + 1; j <= close; j++) {
        const [s, , inner] = list[j] as Token;
        if (depth === 0 && (inner === "," || inner === "]")) {
          if (equals !== null && equals + 1 < j) {
            const from = (list[equals + 1] as Token)[0];
            found.defaults.set(source.offset(parameter as number), [source.offset(from), text.slice(from, s)]);
            blank((list[equals] as Token)[0], s);
          }
          parameter = null;
          equals = null;
          continue;
        }
        if (parameter === null) parameter = s;
        if (depth === 0 && inner === "=") equals = j;
        depth += DEPTH[inner] ?? 0;
      }
    }
  });
  return [units.join(""), found];
}

// --- The converter ---

type Method = (self: Converter, ts: TS) => any;

/** Rewrites a tree-sitter-python tree into Python nodes, recording where each node starts in `positions`. `shift` and
 * `origin` place a tree parsed from a part of the text: its offsets are `shift` past those of the part, and its errors
 * are located in `origin`. */
class Converter {
  readonly positions = new Map<SyntaxNode, number>();
  static STATEMENTS: Record<string, Method> = {};
  static EXPRESSIONS: Record<string, Method> = {};
  static PATTERNS: Record<string, Method> = {};
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

  made<N extends SyntaxNode>(ts: TS, node: N): N {
    if (!this.positions.has(node)) this.positions.set(node, this.at(ts));
    return node;
  }

  madeAt<N extends SyntaxNode>(unit: number, node: N): N {
    if (!this.positions.has(node)) this.positions.set(node, this.shift + this.source.offset(unit));
    return node;
  }

  /** The children of `ts`, without comments and line continuations. */
  kids(ts: TS): TS[] {
    return all(ts).filter((c) => !EXTRAS.has(c.type));
  }

  named(ts: TS): TS[] {
    return all(ts).filter((c) => c.isNamed && !EXTRAS.has(c.type));
  }

  field(ts: TS, name: string): TS | null {
    return ts.childForFieldName(name);
  }

  fields(ts: TS, name: string): TS[] {
    return all(ts).filter((_c, i) => ts.fieldNameForChild(i) === name);
  }

  has(ts: TS, token: string): boolean {
    return all(ts).some((c) => !c.isNamed && c.type === token);
  }

  /** A field the grammar requires, which tree-sitter always writes: it reports a missing one as an error. */
  require(ts: TS, name: string): TS {
    return ts.childForFieldName(name) as TS;
  }

  identifier(ts: TS): S.Identifier {
    return this.made(ts, new S.Identifier({ spelling: this.text(ts) }));
  }

  name(ts: TS): S.Name {
    return this.made(ts, new S.Name({ id: this.identifier(ts) }));
  }

  // Errors

  /** Throws for the first syntax error in `ts`, in source order, and for Python 2's statements. */
  check(ts: TS): void {
    const stack = [ts];
    while (stack.length > 0) {
      const node = stack.pop() as TS;
      if (node.type === "ERROR") throw this.error(node, "syntax error");
      if (node.isMissing) throw this.error(node, `expected ${node.type}`);
      if (PYTHON2.has(node.type)) throw this.error(node, `unsupported syntax: ${node.type}, which is Python 2`);
      stack.push(...all(node).reverse());
    }
  }

  // Statements

  module(ts: TS): S.Module {
    this.check(ts);
    return this.made(ts, new S.Module({ body: this.statements(all(ts)) }));
  }

  /** The statements and comments among `nodes`. A comment is trailing on the line where the node before it ends; for
   * the first, that is `header`, the clause whose block the statements are. */
  statements(nodes: TS[], header: TS | null = null): S.Statement[] {
    const out: S.Statement[] = [];
    let previous = header;
    for (const ts of nodes) {
      if (ts.type === "comment") {
        const comment = this.made(ts, new S.Comment({ text: this.text(ts).slice(1).replace(/\r+$/, "") }));
        comment.trailing = previous !== null && previous.endPosition.row === ts.startPosition.row;
        out.push(comment);
      } else if (ts.isNamed && ts.type !== "line_continuation") {
        out.push(this.statement(ts));
      } else {
        continue;
      }
      previous = ts;
    }
    return out;
  }

  /** The statements of the block `ts` of `clause`, with the comments tree-sitter lists beside the block: in the clause
   * between its header and the block, and after the block until the next clause. */
  block(ts: TS, clause: TS): S.Statement[] {
    const colons = all(clause).filter((c) => c.type === ":" && c.startIndex < ts.startIndex);
    const header = colons.reduce((a, b) => (b.startIndex > a.startIndex ? b : a));
    const before = all(clause).filter((c) => c.type === "comment" && header.startIndex < c.startIndex
      && c.startIndex < ts.startIndex);
    const after = this.after(ts);
    if (CLAUSES.has(clause.type)) after.push(...this.after(clause));
    return this.statements([...before, ...all(ts), ...after], header);
  }

  /** The comments that follow `ts` among its siblings, up to the next sibling that is not one. */
  after(ts: TS): TS[] {
    const out: TS[] = [];
    let sibling = ts.nextSibling;
    while (sibling !== null && sibling.type === "comment") {
      out.push(sibling);
      sibling = sibling.nextSibling;
    }
    return out;
  }

  statement(ts: TS): S.Statement {
    return this.made(ts, (Converter.STATEMENTS[ts.type] as Method)(this, ts)); // check() has thrown for any other
  }

  expressionStatement(ts: TS): S.Statement {
    const kids = this.named(ts);
    if (kids.length > 1 || this.has(ts, ",")) {
      return new S.Expr({ value: this.made(ts, new S.Tuple({ elts: kids.map((k) => this.expression(k)) })) });
    }
    const inner = kids[0] as TS;
    if (inner.type === "assignment") {
      const annotation = this.field(inner, "type");
      let right = this.field(inner, "right");
      if (annotation !== null) {
        return new S.AnnAssign({ target: this.target(this.require(inner, "left")), annotation: this.type(annotation),
          value: right === null ? null : this.expression(right) });
      }
      const targets = [this.target(this.require(inner, "left"))];
      while ((right as TS).type === "assignment") {
        targets.push(this.target(this.require(right as TS, "left")));
        right = this.require(right as TS, "right");
      }
      return new S.Assign({ targets, value: this.expression(right as TS) });
    }
    if (inner.type === "augmented_assignment") {
      return new S.AugAssign({ target: this.target(this.require(inner, "left")),
        op: this.text(this.require(inner, "operator")).slice(0, -1) as S.BinaryOperator,
        value: this.expression(this.require(inner, "right")) });
    }
    return new S.Expr({ value: this.expression(inner) });
  }

  returnStatement(ts: TS): S.Return {
    const kids = this.named(ts);
    return new S.Return({ value: kids.length > 0 ? this.expression(kids[0] as TS) : null });
  }

  deleteStatement(ts: TS): S.Delete {
    const target = this.named(ts)[0] as TS;
    const targets = target.type === "expression_list" ? this.named(target) : [target];
    return new S.Delete({ targets: targets.map((t) => this.target(t)) });
  }

  raiseStatement(ts: TS): S.Raise {
    const cause = this.field(ts, "cause");
    const kids = this.named(ts).filter((k) => cause === null || k.id !== cause.id);
    return new S.Raise({ exc: kids.length > 0 ? this.expression(kids[0] as TS) : null,
      cause: cause === null ? null : this.expression(cause) });
  }

  assertStatement(ts: TS): S.Assert {
    const kids = this.named(ts);
    return new S.Assert({ test: this.expression(kids[0] as TS),
      msg: kids.length > 1 ? this.expression(kids[1] as TS) : null });
  }

  dotted(ts: TS): S.DottedName {
    return this.made(ts, new S.DottedName({ names: this.named(ts).map((k) => this.identifier(k)) }));
  }

  alias(ts: TS): S.Alias {
    if (ts.type === "aliased_import") {
      return this.made(ts, new S.Alias({ name: this.dotted(this.require(ts, "name")),
        asname: this.identifier(this.require(ts, "alias")) }));
    }
    return this.made(ts, new S.Alias({ name: this.dotted(ts) }));
  }

  importStatement(ts: TS): S.Import {
    return new S.Import({ is_lazy: this.pre.lazy.has(this.at(ts)), names: this.fields(ts, "name").map((n) => this.alias(n)) });
  }

  importFromStatement(ts: TS): S.ImportFrom {
    const made = new S.ImportFrom({ is_lazy: this.pre.lazy.has(this.at(ts)) });
    const module = this.require(ts, "module_name");
    if (module.type === "relative_import") {
      made.level = BigInt([...this.text(this.named(module)[0] as TS)].filter((ch) => ch === ".").length);
      const names = this.named(module).slice(1);
      made.module = names.length > 0 ? this.dotted(names[0] as TS) : null;
    } else {
      made.module = this.dotted(module);
    }
    const wildcard = all(ts).filter((c) => c.type === "wildcard_import");
    made.names = wildcard.length > 0 ? [this.made(wildcard[0] as TS, new S.Alias())]
      : this.fields(ts, "name").map((n) => this.alias(n));
    return made;
  }

  futureImportStatement(ts: TS): S.ImportFrom {
    const future = all(ts).find((c) => c.type === "__future__") as TS;
    const module = this.made(future, new S.DottedName({
      names: [this.made(future, new S.Identifier({ spelling: "__future__" }))] }));
    return new S.ImportFrom({ module, names: this.fields(ts, "name").map((n) => this.alias(n)) });
  }

  typeAliasStatement(ts: TS): S.Statement {
    const left = this.named(this.require(ts, "left"))[0] as TS;
    if (left.type !== "identifier" && left.type !== "generic_type") return this.reread(ts);
    const made = new S.TypeAlias({ value: this.type(this.require(ts, "right")) });
    if (left.type === "generic_type") {
      const [name, parameters] = this.named(left) as [TS, TS];
      made.name = this.name(name);
      made.type_params = this.typeParameters(parameters);
    } else {
      made.name = this.name(left);
    }
    return made;
  }

  /** An assignment to an expression that starts with the name `type`, as `type(t).name = value`, which
   * tree-sitter-python reads as a type alias: it is parsed again with `Type` for `type`, which is then put back. */
  reread(ts: TS): S.Statement {
    const source = new Source("Type" + this.text(ts).slice(4));
    const tree = PARSER.parse(source.text) as NonNullable<ReturnType<TSParser["parse"]>>;
    const converter = new Converter(source, new Prepared(), this.at(ts), this.origin);
    converter.check(tree.rootNode);
    const statement = converter.statement(converter.named(tree.rootNode)[0] as TS);
    tree.delete();
    ([...walk(statement)].find((n) => n instanceof S.Identifier) as S.Identifier).spelling = "type";
    for (const [node, at] of converter.positions) this.positions.set(node, at);
    return statement;
  }

  /** `print >> file, value`, which is Python 3 too: a tuple of a shift and the values. tree-sitter-python reads it as
   * Python 2's print statement, which without `>>` is not Python 3. */
  printStatement(ts: TS): S.Expr {
    const chevron = all(ts).find((c) => c.type === "chevron");
    if (chevron === undefined) throw this.error(ts, "unsupported syntax: print_statement, which is Python 2");
    const keyword = all(ts)[0] as TS;
    const shift = this.made(keyword, new S.BinOp({
      left: this.made(keyword, new S.Name({ id: this.made(keyword, new S.Identifier({ spelling: "print" })) })),
      op: ">>", right: this.expression(this.named(chevron)[0] as TS) }));
    const values = this.fields(ts, "argument").map((a) => this.expression(a));
    return new S.Expr({ value: values.length > 0 ? this.made(ts, new S.Tuple({ elts: [shift, ...values] })) : shift });
  }

  // Compound statements

  ifStatement(ts: TS): S.If {
    const made = new S.If({ test: this.expression(this.require(ts, "condition")),
      body: this.block(this.require(ts, "consequence"), ts) });
    let last = made;
    for (const clause of this.fields(ts, "alternative")) {
      if (clause.type === "elif_clause") {
        const elif = this.made(clause, new S.If({ test: this.expression(this.require(clause, "condition")),
          body: this.block(this.require(clause, "consequence"), clause) }));
        last.orelse = [elif];
        last = elif;
      } else {
        last.orelse = this.block(this.require(clause, "body"), clause);
      }
    }
    return made;
  }

  orelse(ts: TS): S.Statement[] {
    const clause = this.field(ts, "alternative");
    return clause === null ? [] : this.block(this.require(clause, "body"), clause);
  }

  whileStatement(ts: TS): S.While {
    return new S.While({ test: this.expression(this.require(ts, "condition")),
      body: this.block(this.require(ts, "body"), ts), orelse: this.orelse(ts) });
  }

  forStatement(ts: TS): S.For | S.AsyncFor {
    const kind = this.has(ts, "async") ? S.AsyncFor : S.For;
    return new kind({ target: this.target(this.require(ts, "left")), iter: this.expression(this.require(ts, "right")),
      body: this.block(this.require(ts, "body"), ts), orelse: this.orelse(ts) });
  }

  tryStatement(ts: TS): S.Try | S.TryStar {
    const handlers: S.ExceptHandler[] = [];
    let orelse: S.Statement[] = [];
    let finalbody: S.Statement[] = [];
    let star = false;
    for (const clause of this.named(ts).slice(1)) {
      if (clause.type === "except_clause") {
        star ||= this.has(clause, "*");
        handlers.push(this.handler(clause));
      } else if (clause.type === "else_clause") {
        orelse = this.block(this.require(clause, "body"), clause);
      } else {
        finalbody = this.block(this.named(clause)[0] as TS, clause);
      }
    }
    const kind = star ? S.TryStar : S.Try;
    return new kind({ body: this.block(this.require(ts, "body"), ts), handlers, orelse, finalbody });
  }

  handler(ts: TS): S.ExceptHandler {
    const made = this.made(ts, new S.ExceptHandler({ body: this.block(this.named(ts).at(-1) as TS, ts) }));
    let values = this.fields(ts, "value");
    if (values.length === 1 && (values[0] as TS).type === "as_pattern") {
      made.name = this.identifier(this.named(this.require(values[0] as TS, "alias"))[0] as TS);
      values = [this.named(values[0] as TS)[0] as TS];
    }
    if (values.length > 1) {
      made.type = this.made(values[0] as TS, new S.Tuple({ elts: values.map((v) => this.expression(v)) }));
    } else if (values.length > 0) {
      made.type = this.expression(values[0] as TS);
    }
    return made;
  }

  withStatement(ts: TS): S.With | S.AsyncWith {
    const items: S.WithItem[] = [];
    for (const item of this.named(this.named(ts)[0] as TS)) {
      let value = this.require(item, "value");
      if (value.type === "parenthesized_expression" && (this.named(value)[0] as TS).type === "as_pattern") {
        value = this.named(value)[0] as TS; // `with (manager() as target):`, one item in parentheses
      }
      let made: S.WithItem;
      if (value.type === "as_pattern") {
        const target = this.named(this.require(value, "alias"))[0] as TS;
        made = new S.WithItem({ context_expr: this.expression(this.named(value)[0] as TS), optional_vars: this.target(target) });
      } else {
        made = new S.WithItem({ context_expr: this.expression(value) });
      }
      items.push(this.made(item, made));
    }
    const kind = this.has(ts, "async") ? S.AsyncWith : S.With;
    return new kind({ items, body: this.block(this.require(ts, "body"), ts) });
  }

  matchStatement(ts: TS): S.Match {
    const subjects = this.fields(ts, "subject");
    const subject = subjects.length > 1 || this.has(ts, ",")
      ? this.made(subjects[0] as TS, new S.Tuple({ elts: subjects.map((s) => this.expression(s)) }))
      : this.expression(subjects[0] as TS);
    const cases: S.MatchCase[] = [];
    for (const clause of this.fields(this.require(ts, "body"), "alternative")) {
      const patterns = this.named(clause).filter((c) => c.type === "case_pattern");
      const pattern = patterns.length > 1 || this.has(clause, ",")
        ? this.made(clause, new S.MatchSequence({ patterns: patterns.map((p) => this.pattern(p)) }))
        : this.pattern(patterns[0] as TS);
      const guard = this.field(clause, "guard");
      cases.push(this.made(clause, new S.MatchCase({ pattern,
        guard: guard === null ? null : this.expression(this.named(guard)[0] as TS),
        body: this.block(this.require(clause, "consequence"), clause) })));
    }
    return new S.Match({ subject, cases });
  }

  functionDefinition(ts: TS): S.FunctionDef | S.AsyncFunctionDef {
    const kind = this.has(ts, "async") ? S.AsyncFunctionDef : S.FunctionDef;
    const parameters = this.field(ts, "type_parameters");
    const returns = this.field(ts, "return_type");
    return new kind({ name: this.identifier(this.require(ts, "name")),
      type_params: parameters === null ? [] : this.typeParameters(parameters),
      args: this.arguments(this.require(ts, "parameters")),
      returns: returns === null ? null : this.type(returns),
      body: this.block(this.require(ts, "body"), ts) });
  }

  classDefinition(ts: TS): S.ClassDef {
    const parameters = this.field(ts, "type_parameters");
    const made = new S.ClassDef({ name: this.identifier(this.require(ts, "name")),
      type_params: parameters === null ? [] : this.typeParameters(parameters),
      body: this.block(this.require(ts, "body"), ts) });
    const superclasses = this.field(ts, "superclasses");
    if (superclasses !== null) [made.bases, made.keywords] = this.callArguments(superclasses);
    return made;
  }

  decoratedDefinition(ts: TS): S.Statement {
    const made = this.statement(this.require(ts, "definition")) as S.FunctionDef;
    made.decorator_list = this.named(ts).filter((d) => d.type === "decorator")
      .map((d) => this.expression(this.named(d)[0] as TS));
    return made;
  }

  // Parameters

  /** A function's or lambda's parameter list. */
  arguments(ts: TS): S.Arguments {
    const made = this.made(ts, new S.Arguments());
    let keywordOnly = false;
    for (const p of this.named(ts)) {
      if (p.type === "positional_separator") {
        made.posonlyargs = made.args;
        made.args = [];
      } else if (p.type === "keyword_separator") {
        keywordOnly = true;
      } else if (p.type === "list_splat_pattern" || p.type === "dictionary_splat_pattern"
        || (p.type === "typed_parameter" && (this.named(p)[0] as TS).type !== "identifier")) {
        const splat = p.type !== "typed_parameter" ? p : this.named(p)[0] as TS;
        const annotation = this.field(p, "type");
        const arg = this.made(p, new S.Arg({ arg: this.identifier(this.named(splat)[0] as TS),
          annotation: annotation === null ? null : this.type(annotation) }));
        if (splat.type === "list_splat_pattern") {
          made.vararg = arg;
          keywordOnly = true;
        } else {
          made.kwarg = arg;
        }
      } else {
        (keywordOnly ? made.kwonlyargs : made.args).push(this.parameter(p));
      }
    }
    return made;
  }

  parameter(ts: TS): S.Arg {
    if (ts.type === "identifier") return this.made(ts, new S.Arg({ arg: this.identifier(ts) }));
    if (ts.type === "typed_parameter") {
      return this.made(ts, new S.Arg({ arg: this.identifier(this.named(ts)[0] as TS),
        annotation: this.type(this.require(ts, "type")) }));
    }
    if (ts.type !== "default_parameter" && ts.type !== "typed_default_parameter") throw this.unsupported(ts);
    const name = this.require(ts, "name");
    if (name.type !== "identifier") throw this.unsupported(name);
    const annotation = this.field(ts, "type");
    return this.made(ts, new S.Arg({ arg: this.identifier(name),
      annotation: annotation === null ? null : this.type(annotation),
      default_value: this.expression(this.require(ts, "value")) }));
  }

  typeParameters(ts: TS): S.TypeParameter[] {
    const out: S.TypeParameter[] = [];
    for (const t of this.named(ts)) {
      const inner = this.named(t)[0] as TS;
      let made: S.TypeVar | S.ParamSpec | S.TypeVarTuple;
      if (inner.type === "constrained_type") {
        const [name, bound] = this.named(inner) as [TS, TS];
        made = new S.TypeVar({ name: this.identifier(this.named(name)[0] as TS), bound: this.type(bound) });
      } else if (inner.type === "splat_type") {
        const kind = this.has(inner, "**") ? S.ParamSpec : S.TypeVarTuple;
        made = new kind({ name: this.identifier(this.named(inner)[0] as TS) });
      } else if (inner.type === "identifier") {
        made = new S.TypeVar({ name: this.identifier(inner) });
      } else {
        throw this.unsupported(inner);
      }
      const found = this.pre.defaults.get(this.at(t));
      if (found !== undefined) made.default_value = this.part(...found);
      out.push(this.made(t, made));
    }
    return out;
  }

  /** The expression `text`, at `offset` of the text, which the pre-pass removed. */
  part(offset: number, text: string): S.Expression {
    const source = new Source(`(${text})`);
    const tree = PARSER.parse(source.text) as NonNullable<ReturnType<TSParser["parse"]>>;
    const converter = new Converter(source, new Prepared(), offset - 1, this.origin);
    converter.check(tree.rootNode);
    const statement = converter.named(tree.rootNode)[0] as TS;
    const value = converter.expression(converter.named(converter.named(statement)[0] as TS)[0] as TS);
    tree.delete();
    for (const [node, at] of converter.positions) this.positions.set(node, at);
    return value;
  }

  // Annotations: tree-sitter-python's type grammar

  /** An annotation, or the value of a type alias: tree-sitter's `type`, which holds an expression or a construct of
   * its type grammar. */
  type(ts: TS): S.Expression {
    const inner = ts.type === "type" ? this.named(ts)[0] as TS : ts;
    if (inner.type === "generic_type") {
      const [name, parameters] = this.named(inner) as [TS, TS];
      const elts = this.named(parameters).map((t) => this.type(t));
      const index = elts.length === 1 ? elts[0] as S.Expression : this.made(parameters, new S.Tuple({ elts }));
      return this.made(inner, new S.Subscript({ value: this.expression(name), slice: index }));
    }
    if (inner.type === "union_type") {
      // `a | b | c` groups to the left, which tree-sitter-python's type grammar writes to the right
      const members: TS[] = [];
      const flatten = (start: TS): void => {
        const node = start.type === "type" ? this.named(start)[0] as TS : start;
        if (node.type === "union_type") {
          this.named(node).forEach(flatten);
        } else if (node.type === "binary_operator" && this.text(this.require(node, "operator")) === "|") {
          flatten(this.require(node, "left"));
          flatten(this.require(node, "right"));
        } else {
          members.push(node);
        }
      };
      flatten(inner);
      let union = this.type(members[0] as TS);
      for (const member of members.slice(1)) {
        union = this.made(members[0] as TS, new S.BinOp({ left: union, op: "|", right: this.type(member) }));
      }
      return union;
    }
    if (inner.type === "splat_type") return this.made(inner, new S.Starred({ value: this.name(this.named(inner)[0] as TS) }));
    return this.expression(inner);
  }

  // Assignment targets: tree-sitter-python's patterns

  target(ts: TS): S.Expression {
    if (ts.type === "pattern_list") return this.made(ts, new S.Tuple({ elts: this.named(ts).map((k) => this.target(k)) }));
    if (ts.type === "tuple_pattern") {
      const elts = this.named(ts).map((k) => this.target(k));
      if (elts.length === 0) return this.made(ts, new S.Tuple());
      if (this.has(ts, ",")) return this.made(ts, new S.Parenthesized({ value: this.made(ts, new S.Tuple({ elts })) }));
      return this.made(ts, new S.Parenthesized({ value: elts[0] as S.Expression }));
    }
    if (ts.type === "list_pattern") return this.made(ts, new S.List({ elts: this.named(ts).map((k) => this.target(k)) }));
    if (ts.type === "list_splat_pattern") {
      return this.made(ts, new S.Starred({ value: this.target(this.named(ts)[0] as TS) }));
    }
    return this.expression(ts);
  }

  // Expressions

  expression(ts: TS): S.Expression {
    const method = Converter.EXPRESSIONS[ts.type];
    if (method === undefined) throw this.unsupported(ts);
    return this.made(ts, method(this, ts));
  }

  string(ts: TS): S.Expression {
    const start = this.named(ts)[0] as TS;
    const opening = this.text(start);
    const quoteAt = [...opening].findIndex((ch) => ch === "'" || ch === "\"");
    const prefix = opening.slice(0, quoteAt);
    const quote = opening.slice(quoteAt) as S.Quote;
    if (![..."fFtT"].some((ch) => prefix.includes(ch))) return new S.Constant({ spelling: this.text(ts) });
    const template = prefix.includes("t") || prefix.includes("T");
    const fields = this.named(ts).filter((c) => c.type === "interpolation");
    // the text ends at the closing quote: tree-sitter-python counts the backslashes before it in a raw string as part
    // of its end, as in `fr'\\'`
    const values = this.pieces(start.endIndex, ts.endIndex - quote.length, fields, template);
    return template ? new S.TemplateStr({ prefix, quote, values: values as (S.StringText | S.Interpolation)[] })
      : new S.JoinedStr({ prefix, quote, values: values as (S.StringText | S.FormattedValue)[] });
  }

  /** The text and replacement fields between two UTF-16 offsets of an f-string, t-string or format spec. */
  pieces(start: number, end: number, fields: TS[], template: boolean): SyntaxNode[] {
    const out: SyntaxNode[] = [];
    let at = start;
    for (const field of fields) {
      if (field.startIndex > at) out.push(this.madeAt(at, new S.StringText({ spelling: this.between(at, field.startIndex) })));
      out.push(this.replacement(field, template));
      at = field.endIndex;
    }
    if (end > at) out.push(this.madeAt(at, new S.StringText({ spelling: this.between(at, end) })));
    return out;
  }

  /** A replacement field: an interpolation of a t-string, or else a formatted value. */
  replacement(ts: TS, template: boolean): S.FormattedValue | S.Interpolation {
    const made = template ? new S.Interpolation() : new S.FormattedValue();
    const expression = this.require(ts, "expression");
    const conversion = this.field(ts, "type_conversion");
    const spec = this.field(ts, "format_specifier");
    const children = all(ts);
    const closing = children.at(-1) as TS;
    const end = (conversion ?? spec ?? closing).startIndex;
    made.debug = this.has(ts, "=");
    if (expression.type === "named_expression" && spec === null) {
      // `{x:=10}` formats `x` with the spec `=10`, which tree-sitter-python reads as an assignment expression
      const name = this.require(expression, "name");
      made.text = this.between((children[0] as TS).endIndex, name.endIndex);
      made.value = this.name(name);
      const colon = all(expression).find((c) => c.type === ":=") as TS;
      made.format_spec = this.made(colon, new S.FormatSpec({ values: [this.madeAt(colon.startIndex + 1,
        new S.StringText({ spelling: this.between(colon.startIndex + 1, closing.startIndex) }))] }));
      return this.made(ts, made);
    }
    made.text = this.between((children[0] as TS).endIndex, end);
    made.value = this.expression(expression);
    if (conversion !== null) made.conversion = this.text(conversion).slice(1) as S.Conversion;
    if (spec !== null) {
      const fields = this.named(spec).filter((c) => c.type === "format_expression");
      const colon = all(spec)[0] as TS;
      made.format_spec = this.made(spec, new S.FormatSpec({
        values: this.pieces(colon.endIndex, spec.endIndex, fields, false) as (S.StringText | S.FormattedValue)[] }));
    }
    return this.made(ts, made);
  }

  tuple(ts: TS): S.Expression {
    const elts = this.named(ts).map((k) => this.expression(k));
    if (elts.length === 0) return new S.Tuple();
    return new S.Parenthesized({ value: this.made(ts, new S.Tuple({ elts })) });
  }

  dictionary(ts: TS): S.Dict {
    const items = this.named(ts).map((k) => this.made(k, k.type === "pair"
      ? new S.DictItem({ key: this.expression(this.require(k, "key")), value: this.expression(this.require(k, "value")) })
      : new S.DictItem({ value: this.expression(this.named(k)[0] as TS) })));
    return new S.Dict({ items });
  }

  generators(ts: TS): S.Comprehension[] {
    const out: S.Comprehension[] = [];
    for (const clause of this.named(ts).slice(1)) {
      if (clause.type === "for_in_clause") {
        const right = this.fields(clause, "right").filter((k) => k.isNamed);
        const iter = right.length === 1 ? this.expression(right[0] as TS)
          : this.made(right[0] as TS, new S.Tuple({ elts: right.map((r) => this.expression(r)) }));
        out.push(this.made(clause, new S.Comprehension({ is_async: this.has(clause, "async"),
          target: this.target(this.require(clause, "left")), iter })));
      } else {
        (out.at(-1) as S.Comprehension).ifs.push(this.expression(this.named(clause)[0] as TS));
      }
    }
    return out;
  }

  setComprehension(ts: TS): S.SetComp | S.DictComp {
    if (this.pre.unpacking.has(this.at(ts))) {
      return new S.DictComp({ key: this.expression(this.require(ts, "body")), generators: this.generators(ts) });
    }
    return new S.SetComp({ elt: this.expression(this.require(ts, "body")), generators: this.generators(ts) });
  }

  dictionaryComprehension(ts: TS): S.DictComp {
    const pair = this.require(ts, "body");
    return new S.DictComp({ key: this.expression(this.require(pair, "key")),
      value: this.expression(this.require(pair, "value")), generators: this.generators(ts) });
  }

  yield(ts: TS): S.Yield | S.YieldFrom {
    const kids = this.named(ts);
    if (this.has(ts, "from")) return new S.YieldFrom({ value: this.expression(kids[0] as TS) });
    return new S.Yield({ value: kids.length > 0 ? this.expression(kids[0] as TS) : null });
  }

  subscript(ts: TS): S.Subscript {
    const indices = this.fields(ts, "subscript");
    const elts = indices.map((i) => this.expression(i));
    const index = elts.length === 1 && !this.has(ts, ",") ? elts[0] as S.Expression
      : this.made(indices[0] as TS, new S.Tuple({ elts }));
    return new S.Subscript({ value: this.expression(this.require(ts, "value")), slice: index });
  }

  slice(ts: TS): S.Slice {
    const parts: (S.Expression | null)[] = [null, null, null];
    let colons = 0;
    for (const c of this.kids(ts)) {
      if (c.type === ":") colons++;
      else parts[colons] = this.expression(c);
    }
    return new S.Slice({ lower: parts[0], upper: parts[1], step: parts[2] });
  }

  callArguments(ts: TS): [S.Expression[], S.Keyword[]] {
    const args: S.Expression[] = [];
    const keywords: S.Keyword[] = [];
    for (const k of this.named(ts)) {
      if (k.type === "keyword_argument") {
        keywords.push(this.made(k, new S.Keyword({ arg: this.identifier(this.require(k, "name")),
          value: this.expression(this.require(k, "value")) })));
      } else if (k.type === "dictionary_splat") {
        keywords.push(this.made(k, new S.Keyword({ value: this.expression(this.named(k)[0] as TS) })));
      } else {
        args.push(this.expression(k));
      }
    }
    return [args, keywords];
  }

  call(ts: TS): S.Call {
    const args = this.require(ts, "arguments");
    const made = new S.Call({ func: this.expression(this.require(ts, "function")) });
    if (args.type === "generator_expression") made.args = [this.expression(args)];
    else [made.args, made.keywords] = this.callArguments(args);
    return made;
  }

  await(ts: TS): S.Expression {
    const value = this.named(ts)[0] as TS;
    if (value.type === "binary_operator" && this.text(this.require(value, "operator")) === "**") {
      // `await x ** y` is `(await x) ** y`, which tree-sitter-python reads as `await (x ** y)`
      const left = this.made(ts, new S.Await({ value: this.expression(this.require(value, "left")) }));
      return new S.BinOp({ left, op: "**", right: this.expression(this.require(value, "right")) });
    }
    return new S.Await({ value: this.expression(value) });
  }

  /** A chain of binary operators, regrouped by Python's precedence. */
  binaryOperator(ts: TS): S.Expression {
    const operands: TS[] = [];
    const operators: string[] = [];
    const flatten = (node: TS): void => {
      if (node.type === "binary_operator") {
        flatten(this.require(node, "left"));
        operators.push(this.text(this.require(node, "operator")));
        flatten(this.require(node, "right"));
      } else {
        operands.push(node);
      }
    };
    flatten(ts);
    const values = operands.map((o) => this.expression(o));
    /** The operands `low` to `high`, with the operators between them, at precedence `level` or above. */
    const build = (low: number, high: number, level: number): S.Expression => {
      if (low === high) return values[low] as S.Expression;
      const group = LEVELS[level] as readonly string[];
      const splits: number[] = [];
      for (let k = low; k < high; k++) if (group.includes(operators[k] as string)) splits.push(k);
      if (splits.length === 0) return build(low, high, level + 1);
      const power = group[0] === "**";
      const k = (power ? splits[0] : splits.at(-1)) as number; // `**` groups to the right, the others to the left
      const made = new S.BinOp({ left: build(low, k, power ? level + 1 : level), op: operators[k] as S.BinaryOperator,
        right: build(k + 1, high, power ? level : level + 1) });
      return this.made(operands[low] as TS, made);
    };
    return build(0, values.length - 1, 0);
  }

  booleanOperator(ts: TS): S.BoolOp {
    const op = this.text(this.require(ts, "operator")) as S.BooleanOperator;
    const values: S.Expression[] = [];
    for (const side of [this.require(ts, "left"), this.require(ts, "right")]) {
      if (side.type === "boolean_operator" && this.text(this.require(side, "operator")) === op) {
        values.push(...this.made(side, this.booleanOperator(side)).values);
      } else {
        values.push(this.expression(side));
      }
    }
    return new S.BoolOp({ op, values });
  }

  comparisonOperator(ts: TS): S.Compare {
    const operands = all(ts).filter((c, i) => c.isNamed && !EXTRAS.has(c.type) && ts.fieldNameForChild(i) !== "operators");
    const operators = this.fields(ts, "operators");
    const comparisons = operators.map((op, i) => {
      const spelling = this.text(op).split(/\s+/).filter((w) => w !== "").join(" ");
      if (spelling === "<>") throw this.error(op, "unsupported syntax: <>, which is Python 2");
      return this.made(op, new S.Comparison({ op: spelling as S.ComparisonOperator,
        comparator: this.expression(operands[i + 1] as TS) }));
    });
    return new S.Compare({ left: this.expression(operands[0] as TS), comparisons });
  }

  conditionalExpression(ts: TS): S.Expression {
    const [body, test, orelse] = this.named(ts) as [TS, TS, TS];
    if (body.type === "named_expression") {
      // `x := a if b else c` is `x := (a if b else c)`, which tree-sitter-python reads as `(x := a) if b else c`
      const value = this.made(ts, new S.IfExp({ body: this.expression(this.require(body, "value")),
        test: this.expression(test), orelse: this.expression(orelse) }));
      return new S.NamedExpr({ target: this.name(this.require(body, "name")), value });
    }
    return new S.IfExp({ body: this.expression(body), test: this.expression(test), orelse: this.expression(orelse) });
  }

  lambda(ts: TS): S.Lambda {
    const parameters = this.field(ts, "parameters");
    return new S.Lambda({ args: parameters !== null ? this.arguments(parameters) : this.made(ts, new S.Arguments()),
      body: this.expression(this.require(ts, "body")) });
  }

  // Patterns

  /** A pattern: a `case_pattern`, or what one holds. */
  pattern(ts: TS): S.Pattern {
    if (ts.type === "_") return this.made(ts, new S.MatchAs());
    if (ts.type === "case_pattern") {
      const kids = this.kids(ts);
      if ((kids[0] as TS).type === "-") return this.made(ts, new S.MatchValue({ value: this.signed(kids) }));
      return this.pattern(kids[0] as TS);
    }
    const method = Converter.PATTERNS[ts.type];
    if (method !== undefined) return this.made(ts, method(this, ts));
    if (ts.type === "none" || ts.type === "true" || ts.type === "false") {
      return this.made(ts, new S.MatchSingleton({ value: this.text(ts) as S.Singleton }));
    }
    return this.made(ts, new S.MatchValue({ value: this.expression(ts) }));
  }

  /** A negative number, `-1`, which tree-sitter-python writes as two tokens. */
  signed(kids: TS[]): S.Expression {
    return this.made(kids[0] as TS, new S.UnaryOp({ op: "-", operand: this.expression(kids[1] as TS) }));
  }

  unionPattern(ts: TS): S.MatchOr {
    const patterns: S.Pattern[] = [];
    const kids = this.kids(ts).filter((k) => k.type !== "|");
    for (let i = 0; i < kids.length; i++) {
      const k = kids[i] as TS;
      if (k.type === "-") { // tree-sitter lists `-1` as two alternatives' worth of children
        patterns.push(this.made(k, new S.MatchValue({ value: this.signed(kids.slice(i, i + 2)) })));
        i++;
      } else {
        patterns.push(this.pattern(k));
      }
    }
    return new S.MatchOr({ patterns });
  }

  tuplePattern(ts: TS): S.Pattern {
    const patterns = this.named(ts).map((k) => this.pattern(k));
    if (patterns.length === 1 && !this.has(ts, ",")) return patterns[0] as S.Pattern; // a group: `(pattern)`
    return new S.MatchSequence({ delimiters: "()", patterns });
  }

  dottedPattern(ts: TS): S.Pattern {
    const names = this.named(ts);
    if (names.length === 1) return new S.MatchAs({ name: this.identifier(names[0] as TS) });
    return new S.MatchValue({ value: this.dottedExpression(ts) });
  }

  dottedExpression(ts: TS): S.Expression {
    const names = this.named(ts);
    let value: S.Expression = this.name(names[0] as TS);
    for (const name of names.slice(1)) {
      value = this.made(ts, new S.Attribute({ value, attr: this.identifier(name) }));
    }
    return value;
  }

  dictPattern(ts: TS): S.MatchMapping {
    const made = new S.MatchMapping();
    const children = all(ts);
    const kids = children.map((c, i): [TS, string | null] => [c, ts.fieldNameForChild(i)])
      .filter(([c]) => !EXTRAS.has(c.type));
    for (let i = 0; i < kids.length; i++) {
      const [k, field] = kids[i] as [TS, string | null];
      if (k.type === "splat_pattern") {
        made.rest = this.identifier(this.named(k)[0] as TS);
      } else if (field === "key") {
        if (k.type === "-") {
          i++;
          made.keys.push(this.signed([k, (kids[i] as [TS, string | null])[0]]));
        } else {
          made.keys.push(this.patternValue(k));
        }
      } else if (k.type === "case_pattern") {
        made.patterns.push(this.pattern(k));
      }
    }
    return made;
  }

  /** A literal or dotted name in a pattern, as an expression. */
  patternValue(ts: TS): S.Expression {
    if (ts.type === "dotted_name") return this.dottedExpression(ts);
    if (ts.type === "complex_pattern") return this.complex(ts);
    return this.expression(ts);
  }

  complex(ts: TS): S.Expression {
    let kids = this.kids(ts);
    let left: S.Expression;
    if ((kids[0] as TS).type === "-") {
      left = this.made(kids[0] as TS, new S.UnaryOp({ op: "-", operand: this.expression(kids[1] as TS) }));
      kids = kids.slice(2);
    } else {
      left = this.expression(kids[0] as TS);
      kids = kids.slice(1);
    }
    return this.made(ts, new S.BinOp({ left, op: (kids[0] as TS).type as S.BinaryOperator,
      right: this.expression(kids[1] as TS) }));
  }

  classPattern(ts: TS): S.MatchClass {
    const names = this.named(ts);
    const made = new S.MatchClass({ cls: this.dottedExpression(names[0] as TS) });
    for (const k of names.slice(1)) {
      const inner = this.kids(k)[0] as TS;
      if (inner.type === "as_pattern" && (this.kids(this.named(inner)[0] as TS)[0] as TS).type === "keyword_pattern") {
        // `name=pattern as alias`, which tree-sitter-python reads as `(name=pattern) as alias`
        const keyword = this.kids(this.named(inner)[0] as TS)[0] as TS;
        const alias = this.named(inner).at(-1) as TS;
        const [name, , ...value] = this.kids(keyword) as [TS, TS, ...TS[]];
        made.kwd_attrs.push(this.identifier(name));
        made.kwd_patterns.push(this.made(keyword, new S.MatchAs({ pattern: this.keywordValue(value),
          name: this.identifier(alias) })));
      } else if (inner.type === "keyword_pattern") {
        const [name, , ...value] = this.kids(inner) as [TS, TS, ...TS[]];
        made.kwd_attrs.push(this.identifier(name));
        made.kwd_patterns.push(this.made(inner, this.keywordValue(value)));
      } else {
        made.patterns.push(this.pattern(k));
      }
    }
    return made;
  }

  /** The pattern of a keyword pattern, which tree-sitter does not wrap in a `case_pattern`. */
  keywordValue(kids: TS[]): S.Pattern {
    if ((kids[0] as TS).type === "-") return this.made(kids[0] as TS, new S.MatchValue({ value: this.signed(kids) }));
    return this.pattern(kids[0] as TS);
  }
}

const C = Converter.prototype;
const bind = (method: (this: Converter, ts: TS) => any): Method => (self, ts) => method.call(self, ts);
const elements = (self: Converter, ts: TS): S.Expression[] => self.named(ts).map((k) => self.expression(k));

Converter.STATEMENTS = {
  expression_statement: bind(C.expressionStatement), return_statement: bind(C.returnStatement),
  delete_statement: bind(C.deleteStatement), raise_statement: bind(C.raiseStatement),
  assert_statement: bind(C.assertStatement), pass_statement: () => new S.Pass(), break_statement: () => new S.Break(),
  continue_statement: () => new S.Continue(),
  global_statement: (self, ts) => new S.Global({ names: self.named(ts).map((k) => self.identifier(k)) }),
  nonlocal_statement: (self, ts) => new S.Nonlocal({ names: self.named(ts).map((k) => self.identifier(k)) }),
  import_statement: bind(C.importStatement), import_from_statement: bind(C.importFromStatement),
  future_import_statement: bind(C.futureImportStatement), type_alias_statement: bind(C.typeAliasStatement),
  print_statement: bind(C.printStatement),
  if_statement: bind(C.ifStatement), while_statement: bind(C.whileStatement), for_statement: bind(C.forStatement),
  try_statement: bind(C.tryStatement), with_statement: bind(C.withStatement), match_statement: bind(C.matchStatement),
  function_definition: bind(C.functionDefinition), class_definition: bind(C.classDefinition),
  decorated_definition: bind(C.decoratedDefinition),
};

const constant: Method = (self, ts) => new S.Constant({ spelling: self.text(ts) });

Converter.EXPRESSIONS = {
  identifier: (self, ts) => new S.Name({ id: self.identifier(ts) }), integer: constant, float: constant, true: constant,
  false: constant, none: constant, ellipsis: constant, string: bind(C.string),
  concatenated_string: (self, ts) => new S.ConcatenatedString({
    values: elements(self, ts) as (S.Constant | S.JoinedStr | S.TemplateStr)[] }),
  parenthesized_expression: (self, ts) => new S.Parenthesized({ value: self.expression(self.named(ts)[0] as TS) }),
  tuple: bind(C.tuple), expression_list: (self, ts) => new S.Tuple({ elts: elements(self, ts) }),
  pattern_list: (self, ts) => new S.Tuple({ elts: elements(self, ts) }),
  list: (self, ts) => new S.List({ elts: elements(self, ts) }), set: (self, ts) => new S.Set({ elts: elements(self, ts) }),
  dictionary: bind(C.dictionary),
  list_comprehension: (self, ts) => new S.ListComp({ elt: self.expression(self.require(ts, "body")),
    generators: self.generators(ts) }),
  set_comprehension: bind(C.setComprehension), dictionary_comprehension: bind(C.dictionaryComprehension),
  generator_expression: (self, ts) => new S.GeneratorExp({ elt: self.expression(self.require(ts, "body")),
    generators: self.generators(ts) }),
  yield: bind(C.yield),
  attribute: (self, ts) => new S.Attribute({ value: self.expression(self.require(ts, "object")),
    attr: self.identifier(self.require(ts, "attribute")) }),
  subscript: bind(C.subscript), slice: bind(C.slice), call: bind(C.call),
  list_splat: (self, ts) => new S.Starred({ value: self.expression(self.named(ts)[0] as TS) }),
  list_splat_pattern: (self, ts) => new S.Starred({ value: self.expression(self.named(ts)[0] as TS) }),
  await: bind(C.await),
  unary_operator: (self, ts) => new S.UnaryOp({ op: self.text(self.require(ts, "operator")) as S.UnaryOperator,
    operand: self.expression(self.require(ts, "argument")) }),
  not_operator: (self, ts) => new S.UnaryOp({ op: "not", operand: self.expression(self.require(ts, "argument")) }),
  binary_operator: bind(C.binaryOperator), boolean_operator: bind(C.booleanOperator),
  comparison_operator: bind(C.comparisonOperator), conditional_expression: bind(C.conditionalExpression),
  named_expression: (self, ts) => new S.NamedExpr({ target: self.name(self.require(ts, "name")),
    value: self.expression(self.require(ts, "value")) }),
  lambda: bind(C.lambda),
};

Converter.PATTERNS = {
  as_pattern: (self, ts) => {
    const [pattern, name] = self.named(ts) as [TS, TS];
    return new S.MatchAs({ pattern: self.pattern(pattern), name: self.identifier(name) });
  },
  union_pattern: bind(C.unionPattern),
  list_pattern: (self, ts) => new S.MatchSequence({ delimiters: "[]", patterns: self.named(ts).map((k) => self.pattern(k)) }),
  tuple_pattern: bind(C.tuplePattern),
  splat_pattern: (self, ts) => {
    const names = self.named(ts);
    return new S.MatchStar({ name: names.length > 0 ? self.identifier(names[0] as TS) : null });
  },
  dotted_name: bind(C.dottedPattern), dict_pattern: bind(C.dictPattern), class_pattern: bind(C.classPattern),
  complex_pattern: (self, ts) => new S.MatchValue({ value: self.complex(ts) }),
};

/** The tree of `text`, the offset where each of its nodes starts, and the source, for locating problems. Throws
 * `ParseError` for text tree-sitter-python cannot parse. */
export function parse(text: string): [S.Module, Map<SyntaxNode, number>, Source] {
  let source = new Source(text);
  let tree = PARSER.parse(text) as NonNullable<ReturnType<TSParser["parse"]>>;
  let prepared = new Prepared();
  if (tree.rootNode.hasError) {
    const [cleaned, found] = prepare(text, tree.rootNode, source);
    tree.delete();
    prepared = found;
    source = new Source(text, cleaned);
    tree = PARSER.parse(cleaned) as NonNullable<ReturnType<TSParser["parse"]>>;
  }
  const converter = new Converter(source, prepared);
  const module = converter.module(tree.rootNode);
  tree.delete();
  return [module, converter.positions, source];
}
