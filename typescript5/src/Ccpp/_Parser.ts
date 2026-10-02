/**
 * Parses C and C++ source text into Ccpp trees, delegating to tree-sitter-cpp (through web-tree-sitter).
 *
 * tree-sitter-cpp builds a concrete syntax tree; `Converter` rewrites it into Ccpp kinds, one tree-sitter node type at
 * a time. A token-level pre-pass (`premodules`) handles what tree-sitter-cpp 0.23 cannot parse: module and import
 * declarations, `export` and `extern template`. It removes them from the text, keeping every other character where it
 * was, and the converter puts them back where they were.
 *
 * Positions are counted in characters (code points), never UTF-16 units, so that every implementation reports the same
 * line and column.
 */

import type { Node as TS, Parser as TSParser } from "web-tree-sitter";

import { ParseError } from "../Framework/Errors.js";
import type { SyntaxNode } from "../Framework/Syntax.js";
import { parser } from "../Framework/_TreeSitter.js";
import * as S from "./Syntax.js";

const PARSER = await parser("tree-sitter-cpp/tree-sitter-cpp.wasm");

const ALTERNATIVES: Record<string, string> = {
  and: "&&", or: "||", not: "!", compl: "~", bitand: "&", bitor: "|", xor: "^", and_eq: "&=", or_eq: "|=",
  xor_eq: "^=", not_eq: "!=",
};
const PRIMITIVES = new Set<string>(S.PRIMITIVE_KEYWORDS);
const CV_KEYWORDS = new Set<string>(S.CV_KEYWORDS);
const CASTS = new Set(["static_cast", "dynamic_cast", "const_cast", "reinterpret_cast"]);
const NAMES = new Set(["identifier", "field_identifier", "type_identifier", "namespace_identifier", "statement_identifier"]);
const ATTRIBUTES = new Set(["attribute_declaration", "attribute_specifier", "ms_declspec_modifier", "alignas_qualifier"]);
const SPECIFIERS = new Set(["storage_class_specifier", "type_qualifier", "explicit_function_specifier", "virtual"]);

function op(token: string): string {
  return ALTERNATIVES[token] ?? token;
}

type Lifted = { requires: SyntaxNode[]; virt_specifiers: S.VirtSpecifier[] };
const lifted = (): Lifted => ({ requires: [], virt_specifiers: [] });

// --- Source text ---

/** The text being parsed, as given and as tree-sitter parses it (`cleaned`), with conversions from tree-sitter's UTF-16
 * offsets to character offsets, and from character offsets to lines and columns. The cleaned text has the same UTF-16
 * units as the text, but for those the pre-pass replaced. */
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

// --- The pre-pass: what tree-sitter-cpp cannot parse ---

/** What the pre-pass removed from the text: module and import declarations to insert among the top-level items, by
 * offset (in characters); and the offsets (in UTF-16 units) of declarations that `export` or `extern template`
 * introduced, and of blocks `export` introduced. */
class Premodules {
  readonly declarations: [number, SyntaxNode][] = [];
  readonly exported = new Set<number>();
  readonly exportBlocks = new Set<number>();
  readonly externTemplates = new Set<number>();
}

const isAlnum = (ch: string) => /^[\p{L}\p{N}]$/u.test(ch);
const charAt = (text: string, i: number) => String.fromCodePoint(text.codePointAt(i) as number);

/** The spans of the tokens of `text` that matter to the pre-pass, skipping comments and directives: each identifier,
 * number, literal, header name after `import`, and punctuation character. */
function tokens(text: string): [number, number][] {
  const out: [number, number][] = [];
  const n = text.length;
  let i = 0;
  let lineStart = true;
  while (i < n) {
    const ch = charAt(text, i);
    if (ch === "\n") {
      lineStart = true;
      i++;
      continue;
    }
    if (" \t\r\f\v".includes(ch)) {
      i++;
      continue;
    }
    if (ch === "#" && lineStart) { // a directive: skip to the end of its line, following continuations
      while (i < n && text[i] !== "\n") i += text[i] === "\\" && i + 1 < n ? 2 : 1;
      continue;
    }
    lineStart = false;
    if (text.startsWith("//", i)) {
      while (i < n && text[i] !== "\n") i++;
      continue;
    }
    if (text.startsWith("/*", i)) {
      const end = text.indexOf("*/", i + 2);
      i = end < 0 ? n : end + 2;
      continue;
    }
    if (isAlnum(ch) || ch === "_") {
      let j = i;
      while (j < n && (isAlnum(charAt(text, j)) || "_'".includes(text[j] as string))) j += charAt(text, j).length;
      if (j < n && "'\"".includes(text[j] as string)
        && ["L", "u", "U", "u8", "R", "LR", "uR", "UR", "u8R"].includes(text.slice(i, j))) {
        out.push([i, literal(text, i, j)]);
        i = (out[out.length - 1] as [number, number])[1];
        continue;
      }
      out.push([i, j]);
      i = j;
      continue;
    }
    if ("'\"".includes(ch)) {
      out.push([i, literal(text, i, i)]);
      i = (out[out.length - 1] as [number, number])[1];
      continue;
    }
    const previous = out[out.length - 1];
    if (ch === "<" && previous !== undefined && text.slice(previous[0], previous[1]) === "import") {
      const end = text.indexOf(">", i);
      out.push([i, end < 0 ? n : end + 1]);
      i = (out[out.length - 1] as [number, number])[1];
      continue;
    }
    out.push([i, i + ch.length]);
    i += ch.length;
  }
  return out;
}

/** The end of the character or string literal starting at `start`, whose quote is at `quote`. */
function literal(text: string, start: number, quote: number): number {
  const n = text.length;
  if (text[quote] === '"' && quote > start && text[quote - 1] === "R") {
    const open = text.indexOf("(", quote);
    const delimiter = text.slice(quote + 1, open);
    const end = open >= 0 ? text.indexOf(")" + delimiter + '"', open) : -1;
    return end < 0 ? n : end + delimiter.length + 2;
  }
  const q = text[quote];
  let i = quote + 1;
  while (i < n && text[i] !== q && text[i] !== "\n") i += text[i] === "\\" ? 2 : 1;
  return i + 1;
}

/** The text with module and import declarations, `export` and the `extern` of `extern template` replaced by spaces,
 * and what was removed. */
function premodules(text: string, source: Source): [string, Premodules] {
  const found = new Premodules();
  const spans = tokens(text);
  const units = text.split(""); // UTF-16 units, blanked one for one so that tree-sitter's offsets stay the text's
  const word = (k: number) => (k < spans.length ? text.slice(...(spans[k] as [number, number])) : "");
  const blank = (start: number, end: number) => {
    for (let p = start; p < end; p++) if (units[p] !== "\n") units[p] = " ";
  };
  let depth = 0;
  let k = 0;
  let startOfStatement = true;
  while (k < spans.length) {
    const w = word(k);
    const span = spans[k] as [number, number];
    if (startOfStatement && ["export", "module", "import", "extern"].includes(w)) {
      const exported = w === "export";
      const j = exported ? k + 1 : k;
      const head = word(j);
      if ((head === "module" || head === "import") && depth === 0
        && !["=", "(", "::", ".", "->", "["].includes(word(j + 1))) {
        let end = j;
        while (end < spans.length && word(end) !== ";") end++;
        if (end === spans.length) {
          throw source.error("expected ';'", source.offset((spans[spans.length - 1] as [number, number])[1]));
        }
        found.declarations.push([source.offset(span[0]), module(text, spans, j, end, exported, source)]);
        blank(span[0], (spans[end] as [number, number])[1]);
        k = end + 1;
        startOfStatement = true;
        continue;
      }
      if (exported && head) {
        blank(...span);
        (head === "{" ? found.exportBlocks : found.exported).add((spans[j] as [number, number])[0]);
        k++;
        continue;
      }
      if (w === "extern" && head === "extern" && word(k + 1) === "template") {
        blank(...span);
        found.externTemplates.add((spans[k + 1] as [number, number])[0]);
        k++;
        continue;
      }
    }
    startOfStatement = [";", "{", "}"].includes(w);
    depth += w === "{" ? 1 : w === "}" ? -1 : 0;
    k++;
  }
  return [units.join(""), found];
}

/** The module or import declaration whose tokens are `spans[k:end]`, from its keyword to before its `;`. */
function module(text: string, spans: [number, number][], k: number, end: number, exported: boolean,
  source: Source): SyntaxNode {
  const words = spans.slice(k + 1, end).map(([s, e]) => text.slice(s, e));
  const keyword = text.slice(...(spans[k] as [number, number]));
  const at = source.offset((spans[k] as [number, number])[0]);
  if (words.includes("[")) throw source.error(`attributes of ${keyword} declarations are not supported`, at);
  const fail = () => source.error(`expected a module name after ${keyword}`, at);
  const dotted = (parts: string[]): string => { // `a.b.c`: identifiers separated by dots
    if (parts.length % 2 === 0 || parts.some((p, i) => (i % 2 === 1 ? p !== "." : !identifier(p)))) throw fail();
    return parts.join("");
  };
  const named = (parts: string[]): [string | null, string | null] => { // `name`, `name:partition` or `:partition`
    const colon = parts.includes(":") ? parts.indexOf(":") : parts.length;
    return [colon > 0 ? dotted(parts.slice(0, colon)) : null,
      colon < parts.length ? dotted(parts.slice(colon + 1)) : null];
  };
  if (keyword === "module") {
    if (words.length === 0 && !exported) return new S.GlobalModuleFragment();
    if (words.length === 2 && words[0] === ":" && words[1] === "private" && !exported) {
      return new S.PrivateModuleFragment();
    }
    const [name, partition] = named(words);
    if (name === null) throw fail();
    return new S.ModuleDeclaration({ export: exported, name, partition });
  }
  if (words.length === 1 && "<\"".includes((words[0] as string)[0] as string)) {
    const header = words[0] as string;
    return new S.ImportDeclaration({ export: exported, header: header.slice(1, -1), system: header[0] === "<" });
  }
  if (words.length === 0) throw fail();
  const [name, partition] = named(words);
  return new S.ImportDeclaration({ export: exported, name, partition });
}

function identifier(word: string): boolean {
  return !"0123456789".includes(word[0] as string)
    && [...word].every((ch) => (ch.codePointAt(0) as number) > 0x7f || /[A-Za-z0-9_$]/.test(ch));
}

// --- The converter ---

type Method = (self: Converter, ts: TS) => any;

/** Rewrites a tree-sitter-cpp tree into Ccpp nodes, recording where each node starts in `positions`. */
class Converter {
  readonly positions = new Map<SyntaxNode, number>();
  static EXPRESSIONS: Record<string, Method> = {};
  static STATEMENTS: Record<string, Method> = {};
  static DECLARATIONS: Record<string, Method> = {};

  constructor(private readonly source: Source, private readonly pre: Premodules) {}

  // Helpers

  at(ts: TS): number {
    return this.source.offset(ts.startIndex);
  }

  text(ts: TS): string {
    return this.source.cleaned.slice(ts.startIndex, ts.endIndex);
  }

  error(ts: TS, message: string): ParseError {
    return this.source.error(message, this.at(ts));
  }

  unsupported(ts: TS): ParseError {
    return this.error(ts, `unsupported syntax: ${ts.type}`);
  }

  made<N extends SyntaxNode>(ts: TS, node: N): N {
    if (!this.positions.has(node)) this.positions.set(node, this.at(ts));
    return node;
  }

  static all(ts: TS): TS[] {
    return ts.children.filter((c): c is TS => c !== null);
  }

  /** The children of `ts`, without comments. */
  kids(ts: TS): TS[] {
    return Converter.all(ts).filter((c) => c.type !== "comment");
  }

  named(ts: TS): TS[] {
    return Converter.all(ts).filter((c) => c.isNamed && c.type !== "comment");
  }

  field(ts: TS, name: string): TS | null {
    return ts.childForFieldName(name);
  }

  fields(ts: TS, name: string): TS[] {
    return Converter.all(ts).filter((_c, i) => ts.fieldNameForChild(i) === name);
  }

  has(ts: TS, token: string): boolean {
    return Converter.all(ts).some((c) => !c.isNamed && c.type === token);
  }

  /** A field the grammar requires, which tree-sitter always writes: it reports a missing one as an error. */
  require(ts: TS, name: string): TS {
    return ts.childForFieldName(name) as TS;
  }

  // Errors

  /** Throws for the first syntax error in `ts`, in source order. */
  check(ts: TS): void {
    const stack = [ts];
    while (stack.length > 0) {
      const node = stack.pop() as TS;
      if (node.type === "ERROR") throw this.error(node, "syntax error");
      if (node.isMissing && node.parent?.type !== "template_instantiation") {
        throw this.error(node, `expected ${node.type}`);
      }
      if (node.hasError) stack.push(...Converter.all(node).reverse());
    }
  }

  // Lists of items

  unit(ts: TS): S.TranslationUnit {
    this.check(ts);
    const items = this.items(Converter.all(ts), true);
    for (const [offset, declaration] of this.pre.declarations) this.positions.set(declaration, offset);
    const merged: [number, SyntaxNode][] = [...items.map((item): [number, SyntaxNode] => [this.positions.get(item) as number, item]),
      ...this.pre.declarations];
    merged.sort((a, b) => a[0] - b[0]);
    return this.made(ts, new S.TranslationUnit({ items: merged.map(([, item]) => item) }));
  }

  /** The items of a list of declarations, statements, members or enumerators. With `declarations`, `;` alone is an
   * empty declaration rather than an empty statement. */
  items(all: TS[], declarations: boolean, enumerators = false): any[] {
    const out: any[] = [];
    const nodes = all.filter((n) => n.isNamed);
    let i = 0;
    while (i < nodes.length) {
      const ts = nodes[i] as TS;
      i++;
      if (ts.type === "comment") {
        const comment = this.comment(ts);
        comment.trailing = i > 1 && (nodes[i - 2] as TS).endPosition.row === ts.startPosition.row;
        out.push(comment);
      } else if (ts.type === "case_statement") {
        const [made, next] = this.case(nodes, i - 1);
        out.push(...made);
        i = next;
      } else if (ts.type === "enumerator" && enumerators) {
        out.push(this.enumerator(ts));
      } else if (ts.type === "access_specifier") {
        out.push(this.made(ts, new S.AccessSpecifier({ access: this.text(ts) })));
      } else if (ts.type.startsWith("preproc_")) {
        out.push(this.directive(ts, declarations, enumerators));
      } else if (ts.type === "expression_statement" && declarations && this.named(ts).length === 0) {
        out.push(this.made(ts, new S.EmptyDeclaration()));
      } else if (ts.type === "attributed_statement" && declarations
        && this.named(this.named(ts).at(-1) as TS).length === 0) {
        // `[[attributes]];`, which tree-sitter reads as an empty statement with attributes
        out.push(this.made(ts, new S.AttributeDeclaration({
          attributes: this.named(ts).slice(0, -1).map((a) => this.attribute(a)) })));
      } else {
        out.push(this.item(ts));
      }
    }
    return out;
  }

  /** A declaration or statement, exported if `export` introduced it. */
  item(ts: TS): SyntaxNode {
    let made: SyntaxNode;
    if (ts.type === "compound_statement" && this.pre.exportBlocks.has(ts.startIndex)) {
      made = new S.ExportDeclaration({ braced: true, items: this.items(Converter.all(ts), true) });
    } else {
      made = this.declarationOrStatement(ts);
      if (this.pre.exported.has(ts.startIndex)) made = new S.ExportDeclaration({ items: [made] });
    }
    return this.made(ts, made);
  }

  /** The case or default label `nodes[i]`, and the index of the node after what it took: tree-sitter lists the
   * statements after a label as its children; here it labels the first, and the others follow it. A label without
   * statements labels the next label. */
  case(nodes: TS[], i: number): [SyntaxNode[], number] {
    const ts = nodes[i] as TS;
    i++;
    const value = this.field(ts, "value");
    const body = Converter.all(ts).filter((c) => c.isNamed && c.type !== "comment" && (value === null || c.id !== value.id));
    const comments = Converter.all(ts).filter((c) => c.type === "comment").map((c) => this.comment(c));
    let statement: SyntaxNode | null = null;
    let rest: SyntaxNode[] = [];
    if (body.length > 0) {
      statement = this.statement(body[0] as TS);
      rest = body.slice(1).map((c) => this.statement(c));
    } else if (i < nodes.length && (nodes[i] as TS).type === "case_statement") {
      const [nested, next] = this.case(nodes, i);
      i = next;
      statement = nested[0] as SyntaxNode;
      rest = nested.slice(1);
    }
    const label = value === null ? new S.DefaultStatement({ statement })
      : new S.CaseStatement({ value: this.expression(value), statement });
    return [[this.made(ts, label), ...comments, ...rest], i];
  }

  comment(ts: TS): S.Comment {
    const spelling = this.text(ts);
    if (spelling.startsWith("/*")) return this.made(ts, new S.Comment({ block: true, text: spelling.slice(2, -2) }));
    return this.made(ts, new S.Comment({ text: spelling.slice(2).replace(/\r+$/, "") }));
  }

  declarationOrStatement(ts: TS): any {
    const method = Converter.DECLARATIONS[ts.type];
    return method !== undefined ? method(this, ts) : this.statement(ts);
  }

  // Directives

  directive(ts: TS, declarations: boolean, enumerators: boolean): SyntaxNode {
    const kind = ts.type;
    if (kind === "preproc_include") {
      const directive = this.text(this.kids(ts)[0] as TS).slice(1).trim();
      const path = this.require(ts, "path");
      if (path.type === "system_lib_string") {
        return this.made(ts, new S.IncludeDirective({ directive, path: this.text(path).slice(1, -1), system: true }));
      }
      if (path.type === "string_literal") {
        return this.made(ts, new S.IncludeDirective({ directive, path: this.text(path).slice(1, -1) }));
      }
      return this.made(ts, new S.IncludeDirective({ directive, macro: this.expression(path) }));
    }
    if (kind === "preproc_def" || kind === "preproc_function_def") {
      const value = this.field(ts, "value");
      const replacement = value !== null ? this.text(value).trim() : "";
      const made = new S.DefineDirective({ name: this.identifier(this.require(ts, "name")),
        replacement: replacement || null });
      const parameters = this.field(ts, "parameters");
      if (parameters !== null) {
        made.function_like = true;
        made.parameters = this.named(parameters).map((p) => this.identifier(p));
        made.variadic = this.has(parameters, "...");
      }
      return this.made(ts, made);
    }
    if (kind === "preproc_call") {
      const directive = this.text(this.require(ts, "directive")).slice(1).trim();
      const argument = this.field(ts, "argument");
      const text = argument !== null ? this.text(argument).trim() : "";
      return this.made(ts, new S.OtherDirective({ directive, text: text || null }));
    }
    const excluded = new Set(["condition", "name", "alternative"].flatMap((n) => this.fields(ts, n).map((c) => c.id)));
    const items = this.items(Converter.all(ts).filter((c) => c.isNamed && !excluded.has(c.id)), declarations,
      enumerators);
    const alternative = this.field(ts, "alternative");
    const tail = alternative !== null ? this.directive(alternative, declarations, enumerators) : null;
    if (kind === "preproc_else") return this.made(ts, new S.ElseDirective({ items }));
    if (kind === "preproc_if" || kind === "preproc_elif") {
      const condition = this.expression(this.require(ts, "condition"));
      const made = new (kind === "preproc_if" ? S.IfDirective : S.ElifDirective)({ condition, items, alternative: tail });
      return this.made(ts, made);
    }
    const negated = this.text(this.kids(ts)[0] as TS).trimEnd().endsWith("ndef");
    const name = this.identifier(this.require(ts, "name"));
    const made = new (kind === "preproc_ifdef" ? S.IfdefDirective : S.ElifdefDirective)(
      { negated, name, items, alternative: tail });
    return this.made(ts, made);
  }

  // Names

  identifier(ts: TS): S.Identifier {
    return this.made(ts, new S.Identifier({ spelling: this.text(ts) }));
  }

  name(ts: TS): any {
    const kind = ts.type;
    if (NAMES.has(kind) || kind === "primitive_type") return this.identifier(ts);
    if (kind === "template_type" || kind === "template_function" || kind === "template_method") {
      return this.made(ts, new S.TemplateId({ name: this.name(this.require(ts, "name")),
        arguments: this.templateArguments(this.require(ts, "arguments")) }));
    }
    if (kind === "dependent_name") {
      const made = this.name(this.named(ts)[0] as TS);
      made.template_keyword = true;
      return made;
    }
    if (kind === "qualified_identifier") return this.qualified(ts);
    if (kind === "destructor_name") return this.made(ts, new S.DestructorName({ type: this.name(this.named(ts)[0] as TS) }));
    return this.operatorName(ts); // the last kind of name tree-sitter writes outside declarators
  }

  operatorName(ts: TS): SyntaxNode {
    const parts = this.kids(ts).slice(1).map((c) => this.text(c));
    if (parts[0] === '""') return this.made(ts, new S.LiteralOperatorName({ suffix: parts[1] }));
    return this.made(ts, new S.OperatorName({ operator: op(parts.join("")) }));
  }

  qualified(ts: TS): S.QualifiedName {
    const [global_scope, qualifiers, last] = this.qualifiedParts(ts);
    return this.made(ts, new S.QualifiedName({ global_scope, qualifiers, name: this.name(last) }));
  }

  scope(ts: TS): SyntaxNode {
    if (ts.type === "decltype") return this.specifiers(ts)[0] as SyntaxNode;
    return this.name(ts);
  }

  templateArguments(ts: TS): SyntaxNode[] {
    return this.named(ts).map((c) => (c.type === "type_descriptor" ? this.typeId(c) : this.expression(c)));
  }

  // Literals

  number(ts: TS): SyntaxNode {
    const spelling = this.text(ts);
    const lower = spelling.toLowerCase();
    const floating = lower.startsWith("0x") ? lower.includes("p") || lower.includes(".")
      : !lower.startsWith("0b") && (lower.includes(".") || lower.includes("e"));
    return this.made(ts, new (floating ? S.FloatingLiteral : S.IntegerLiteral)({ spelling }));
  }

  quoted(ts: TS): SyntaxNode {
    const spelling = this.text(ts);
    if (ts.type === "raw_string_literal") {
      const quote = spelling.indexOf('"');
      const open = spelling.indexOf("(", quote);
      const delimiter = spelling.slice(quote + 1, open);
      return this.made(ts, new S.RawStringLiteral({ prefix: spelling.slice(0, quote - 1) || null,
        delimiter: delimiter || null, text: spelling.slice(open + 1, spelling.length - delimiter.length - 2) }));
    }
    const quote = spelling.indexOf(ts.type === "char_literal" ? "'" : '"');
    const kind = ts.type === "char_literal" ? S.CharacterLiteral : S.StringLiteral;
    return this.made(ts, new kind({ prefix: spelling.slice(0, quote) || null, text: spelling.slice(quote + 1, -1) }));
  }

  // Expressions

  expression(ts: TS): any {
    const method = Converter.EXPRESSIONS[ts.type];
    if (method === undefined) throw this.unsupported(ts);
    return this.made(ts, method(this, ts));
  }

  expressions(ts: TS): SyntaxNode[] {
    return this.named(ts).map((c) => this.expression(c));
  }

  idExpression(ts: TS): SyntaxNode {
    return new S.IdExpression({ name: this.name(ts) });
  }

  null(ts: TS): SyntaxNode {
    if (this.text(ts) === "nullptr") return new S.NullptrLiteral();
    return new S.IdExpression({ name: this.identifier(ts) });
  }

  parenthesized(ts: TS): SyntaxNode {
    const inner = this.named(ts)[0] as TS;
    if (inner.type === "compound_statement") return new S.StatementExpression({ body: this.statement(inner) });
    return new S.ParenthesizedExpression({ expression: this.expression(inner) });
  }

  binary(ts: TS): SyntaxNode {
    return new S.BinaryExpression({ left: this.expression(this.require(ts, "left")),
      operator: op(this.text(this.require(ts, "operator"))), right: this.expression(this.require(ts, "right")) });
  }

  /** `a, b, c`, which tree-sitter nests to the right; the comma operator groups to the left. */
  comma(ts: TS): SyntaxNode {
    const operands = [this.require(ts, "left")];
    let right = this.require(ts, "right");
    while (right.type === "comma_expression") {
      operands.push(this.require(right, "left"));
      right = this.require(right, "right");
    }
    let made = this.expression(operands[0] as TS);
    for (const operand of [...operands.slice(1), right]) {
      made = this.made(operand, new S.BinaryExpression({ left: made, operator: ",", right: this.expression(operand) }));
    }
    return made;
  }

  assignment(ts: TS): SyntaxNode {
    return new S.AssignmentExpression({ left: this.expression(this.require(ts, "left")),
      operator: op(this.text(this.require(ts, "operator"))), right: this.expression(this.require(ts, "right")) });
  }

  conditional(ts: TS): SyntaxNode {
    const consequence = this.field(ts, "consequence");
    return new S.ConditionalExpression({ condition: this.expression(this.require(ts, "condition")),
      consequence: consequence !== null ? this.expression(consequence) : null,
      alternative: this.expression(this.require(ts, "alternative")) });
  }

  unary(ts: TS): SyntaxNode {
    return new S.UnaryExpression({ operator: op(this.text(this.require(ts, "operator"))),
      operand: this.expression(this.require(ts, "argument")) });
  }

  update(ts: TS): SyntaxNode {
    const operator = this.text(this.require(ts, "operator"));
    const operand = this.expression(this.require(ts, "argument"));
    if (["++", "--"].includes((this.kids(ts)[0] as TS).type)) return new S.UnaryExpression({ operator, operand });
    return new S.PostfixExpression({ operand, operator });
  }

  cast(ts: TS): SyntaxNode {
    return new S.CastExpression({ type: this.typeId(this.require(ts, "type")),
      operand: this.expression(this.require(ts, "value")) });
  }

  call(ts: TS): SyntaxNode {
    const fn = this.require(ts, "function");
    const args = this.require(ts, "arguments");
    if (fn.type === "primitive_type") {
      return new S.FunctionalCastExpression({ type: this.specifiers(fn)[0],
        initializer: this.made(args, new S.ParenthesizedInitializer({ arguments: this.expressions(args) })) });
    }
    if (fn.type === "identifier" && ["typeid", "noexcept"].includes(this.text(fn))) {
      // tree-sitter reads these operators as calls; their operand is an expression here
      const operands = this.named(args);
      if (operands.length !== 1) throw this.error(args, `${this.text(fn)} takes one operand`);
      const kind = this.text(fn) === "typeid" ? S.TypeidExpression : S.NoexceptExpression;
      return new kind({ operand: this.expression(operands[0] as TS) });
    }
    if (fn.type === "template_function") {
      const name = this.text(this.require(fn, "name"));
      const types = this.named(this.require(fn, "arguments"));
      if (CASTS.has(name) && types.length === 1 && (types[0] as TS).type === "type_descriptor") {
        const operands = this.named(args);
        if (operands.length !== 1) throw this.error(args, `${name} takes one operand`);
        return new S.NamedCastExpression({ operator: name, type: this.typeId(types[0] as TS),
          operand: this.expression(operands[0] as TS) });
      }
    }
    return new S.CallExpression({ function: this.expression(fn), arguments: this.expressions(args) });
  }

  fieldExpression(ts: TS): SyntaxNode {
    const operator = this.text(this.require(ts, "operator"));
    const member = this.require(ts, "field");
    if (operator === ".*") {
      return new S.BinaryExpression({ left: this.expression(this.require(ts, "argument")), operator: ".*",
        right: this.expression(member) });
    }
    const keyword = member.type === "dependent_name"; // `object.template name<...>`: the keyword is the access's
    return new S.MemberExpression({ object: this.expression(this.require(ts, "argument")), operator,
      template_keyword: keyword, member: this.name(keyword ? this.named(member)[0] as TS : member) });
  }

  subscript(ts: TS): SyntaxNode {
    return new S.SubscriptExpression({ object: this.expression(this.require(ts, "argument")),
      indices: this.expressions(this.require(ts, "indices")) });
  }

  sizeof(ts: TS): SyntaxNode {
    const type = this.field(ts, "type");
    if (type !== null) return new S.SizeofExpression({ operand: this.typeId(type) });
    const value = this.require(ts, "value");
    if (this.has(ts, "...")) return new S.SizeofPackExpression({ pack: this.identifier(value) });
    return new S.SizeofExpression({ operand: this.expression(value) });
  }

  alignof(ts: TS): SyntaxNode {
    return new S.AlignofExpression({ keyword: this.text(this.kids(ts)[0] as TS),
      operand: this.typeId(this.require(ts, "type")) });
  }

  new(ts: TS): SyntaxNode {
    const type = this.require(ts, "type");
    let declarator: SyntaxNode | null = null;
    for (let node = this.field(ts, "declarator"); node !== null;
      node = this.named(node).find((c) => c.type === "new_declarator") ?? null) {
      declarator = this.made(node, new S.ArrayDeclarator({ declarator,
        size: this.expression(this.require(node, "length")) }));
    }
    const placement = this.field(ts, "placement");
    const args = this.field(ts, "arguments");
    let initializer: SyntaxNode | null = null;
    if (args !== null && args.type === "argument_list") {
      initializer = this.made(args, new S.ParenthesizedInitializer({ arguments: this.expressions(args) }));
    } else if (args !== null) {
      initializer = this.expression(args);
    }
    return new S.NewExpression({ global_scope: this.has(ts, "::"),
      placement: placement !== null ? this.expressions(placement) : [],
      type: this.made(type, new S.TypeId({ specifiers: this.specifiers(type), declarator })), initializer });
  }

  delete(ts: TS): SyntaxNode {
    return new S.DeleteExpression({ global_scope: this.has(ts, "::"), array: this.has(ts, "["),
      operand: this.expression(this.named(ts)[0] as TS) });
  }

  fold(ts: TS): SyntaxNode {
    const left = this.require(ts, "left");
    const right = this.require(ts, "right");
    return new S.FoldExpression({ left: left.isNamed ? this.expression(left) : null,
      operator: op(this.text(this.require(ts, "operator"))), right: right.isNamed ? this.expression(right) : null });
  }

  packExpansion(ts: TS): SyntaxNode {
    const pattern = this.require(ts, "pattern");
    return new S.PackExpansion({ pattern: pattern.type === "type_descriptor" ? this.typeId(pattern)
      : this.expression(pattern) });
  }

  concatenated(ts: TS): SyntaxNode {
    return new S.ConcatenatedString({ parts: this.named(ts).map((c) => this.expression(c)) });
  }

  userDefined(ts: TS): SyntaxNode {
    const [literal, suffix] = this.named(ts) as [TS, TS];
    return new S.UserDefinedLiteral({ literal: this.expression(literal), suffix: this.text(suffix) });
  }

  initializerList(ts: TS): SyntaxNode {
    const kids = this.kids(ts);
    return new S.InitializerList({
      items: this.named(ts).map((c) => (c.type === "initializer_pair" ? this.designated(c) : this.expression(c))),
      trailing_comma: kids.length > 2 && (kids[kids.length - 2] as TS).type === "," });
  }

  designated(ts: TS): SyntaxNode {
    const designators: SyntaxNode[] = [];
    for (const d of this.fields(ts, "designator")) {
      if (d.type === "field_designator" || d.type === "field_identifier") {
        const name = d.type === "field_designator" ? this.named(d)[0] as TS : d;
        designators.push(this.made(d, new S.FieldDesignator({ name: this.identifier(name) })));
      } else if (d.type === "subscript_designator") {
        designators.push(this.made(d, new S.IndexDesignator({ index: this.expression(this.named(d)[0] as TS) })));
      } else {
        designators.push(this.made(d, new S.IndexDesignator({ index: this.expression(this.require(d, "start")),
          last: this.expression(this.require(d, "end")) })));
      }
    }
    const value = this.require(ts, "value");
    const initializer = this.made(value, new S.EqualInitializer({ value: this.expression(value) }));
    return this.made(ts, new S.DesignatedInitializer({ designators, initializer }));
  }

  compoundLiteral(ts: TS): SyntaxNode {
    const type = this.require(ts, "type");
    const value = this.expression(this.require(ts, "value"));
    if (type.type === "type_descriptor") return new S.CompoundLiteralExpression({ type: this.typeId(type), initializer: value });
    return new S.FunctionalCastExpression({ type: this.specifiers(type)[0], initializer: value });
  }

  generic(ts: TS): SyntaxNode {
    const parts = this.named(ts);
    const first = parts[0] as TS;
    const made = new S.GenericSelection({ controlling: this.expression(first) }); // tree-sitter reads no type there
    for (let i = 1; i < parts.length; i += 2) { // type, value: `default` is a type named default to tree-sitter
      const association = parts[i] as TS;
      made.associations.push(this.made(association, new S.GenericAssociation({
        type: this.text(association) !== "default" ? this.typeId(association) : null,
        value: this.expression(parts[i + 1] as TS) })));
    }
    return made;
  }

  offsetof(ts: TS): SyntaxNode {
    const keyword = this.kids(ts)[0] as TS;
    return new S.CallExpression({ function: this.made(keyword, new S.IdExpression({ name: this.identifier(keyword) })),
      arguments: [this.typeId(this.require(ts, "type")), this.idExpression(this.require(ts, "member"))] });
  }

  lambda(ts: TS): SyntaxNode {
    const made = new S.LambdaExpression({ body: this.statement(this.require(ts, "body")) });
    const kids = this.kids(this.require(ts, "captures"));
    let i = 1;
    while (i < kids.length - 1) {
      const c = kids[i] as TS;
      i++;
      if (c.type === ",") continue;
      if (c.type === "lambda_default_capture") {
        made.captures.push(this.made(c, new S.DefaultCapture({ mode: this.text(c) })));
      } else if (c.type === "&") {
        const target = kids[i] as TS;
        i++;
        if (target.type === "parameter_pack_expansion") {
          made.captures.push(this.made(c, new S.SimpleCapture({ by_reference: true,
            name: this.identifier(this.require(target, "pattern")), pack: true })));
        } else {
          made.captures.push(this.made(c, new S.SimpleCapture({ by_reference: true, name: this.identifier(target) })));
        }
      } else if (c.type === "*") {
        made.captures.push(this.made(c, new S.ThisCapture({ copy: true })));
        i++;
      } else if (c.type === "this") {
        made.captures.push(this.made(c, new S.ThisCapture()));
      } else if (c.type === "lambda_capture_initializer") {
        made.captures.push(this.initCapture(c));
      } else if (c.type === "parameter_pack_expansion") {
        made.captures.push(this.made(c, new S.SimpleCapture({ name: this.identifier(this.require(c, "pattern")),
          pack: true })));
      } else if (c.type === "identifier") {
        made.captures.push(this.made(c, new S.SimpleCapture({ name: this.identifier(c) })));
      } else {
        throw this.unsupported(c);
      }
    }
    const parameters = this.field(ts, "template_parameters");
    if (parameters !== null) made.template_parameters = this.templateParameters(parameters);
    const constraint = this.field(ts, "constraint");
    if (constraint !== null) made.template_requires = this.requiresClause(constraint);
    const declarator = this.field(ts, "declarator");
    if (declarator !== null) made.declarator = this.lambdaDeclarator(declarator);
    return made;
  }

  initCapture(ts: TS): SyntaxNode {
    const value = this.require(ts, "right");
    const initializer = this.made(value, new S.EqualInitializer({ value: this.expression(value) }));
    return this.made(ts, new S.InitCapture({ by_reference: this.has(ts, "&"), pack: this.has(ts, "..."),
      name: this.identifier(this.require(ts, "left")), initializer }));
  }

  lambdaDeclarator(ts: TS): S.LambdaDeclarator {
    const made = new S.LambdaDeclarator({ parameters: this.parameters(this.require(ts, "parameters")) });
    for (const c of this.named(ts)) {
      if (c.type === "parameter_list") continue;
      if (c.type === "type_qualifier") made.specifiers.push(this.made(c, new S.DeclSpecifier({ keyword: this.text(c) as S.DeclKeyword })));
      else if (c.type === "noexcept" || c.type === "throw_specifier") made.exception = this.exception(c);
      else if (c.type === "trailing_return_type") made.trailing_return = this.typeId(this.named(c)[0] as TS);
      else if (c.type === "requires_clause") made.requires = this.requiresClause(c);
      else if (ATTRIBUTES.has(c.type)) made.attributes.push(this.attribute(c));
      else throw this.unsupported(c);
    }
    return this.made(ts, made);
  }

  requiresExpression(ts: TS): SyntaxNode {
    const parameters = this.field(ts, "parameters");
    const made = new S.RequiresExpression({ parameters: parameters !== null ? this.parameters(parameters) : [] });
    for (const r of this.named(this.require(ts, "requirements"))) {
      // tree-sitter reads `;` after some requirements as empty ones
      if (r.type !== "simple_requirement" || this.named(r).length > 0) made.requirements.push(this.requirement(r));
    }
    return made;
  }

  requirement(ts: TS): SyntaxNode {
    if (ts.type === "simple_requirement") {
      const inner = this.named(ts)[0] as TS;
      if (inner.type === "requires_clause") { // `requires constraint;`
        return this.made(ts, new S.NestedRequirement({ constraint: this.requiresClause(inner) }));
      }
      return this.made(ts, new S.SimpleRequirement({ expression: this.expression(inner) }));
    }
    if (ts.type === "type_requirement") return this.made(ts, new S.TypeRequirement({ name: this.name(this.named(ts)[0] as TS) }));
    const parts = this.named(ts);
    const made = new S.CompoundRequirement({ expression: this.expression(parts[0] as TS), noexcept: this.has(ts, "noexcept") });
    for (const p of parts.slice(1)) made.return_type = this.name(this.require(this.named(p)[0] as TS, "type"));
    return this.made(ts, made);
  }

  requiresClause(ts: TS): SyntaxNode {
    return this.constraint(this.fields(ts, "constraint"));
  }

  /** A constraint expression from tree-sitter's constraint fields, which hold parentheses as tokens. */
  constraint(parts: TS[]): SyntaxNode {
    const ts = parts[0] as TS;
    if (ts.type === "(") {
      return this.made(ts, new S.ParenthesizedExpression({ expression: this.constraint(parts.slice(1, -1)) }));
    }
    if (ts.type === "constraint_conjunction" || ts.type === "constraint_disjunction") {
      return this.made(ts, new S.BinaryExpression({ left: this.constraint(this.fields(ts, "left")),
        operator: op(this.text(this.require(ts, "operator"))), right: this.constraint(this.fields(ts, "right")) }));
    }
    if (ts.type === "template_type" || ts.type === "type_identifier") {
      return this.made(ts, new S.IdExpression({ name: this.name(ts) }));
    }
    return this.expression(ts);
  }

  // Types

  /** A type_descriptor: specifiers in source order, and its abstract declarator. */
  typeId(ts: TS): S.TypeId {
    const declarator = this.field(ts, "declarator");
    return this.made(ts, new S.TypeId({ specifiers: this.specifiersOf(ts),
      declarator: declarator !== null ? this.declarator(declarator) : null }));
  }

  /** The specifiers of a declaration-like node, in source order. Attributes before the first specifier go to
   * `attributes` when given. */
  specifiersOf(ts: TS, attributes: SyntaxNode[] | null = null): SyntaxNode[] {
    const out: SyntaxNode[] = [];
    const type = this.field(ts, "type");
    Converter.all(ts).forEach((c, i) => {
      if (type !== null && c.id === type.id) out.push(...this.specifiers(c));
      else if (ATTRIBUTES.has(c.type) && ts.fieldNameForChild(i) === null) {
        (attributes !== null && out.length === 0 ? attributes : out).push(this.attribute(c));
      } else if (SPECIFIERS.has(c.type) || c.type === "typedef" || c.type === "__extension__") out.push(...this.specifiers(c));
      else if (c.type === "ms_call_modifier") throw this.unsupported(c);
    });
    return out;
  }

  /** The specifiers one tree-sitter node spells. */
  specifiers(ts: TS): any[] {
    const kind = ts.type;
    const spelling = this.text(ts);
    if (kind === "primitive_type" || (kind === "type_identifier" && PRIMITIVES.has(spelling))) {
      if (PRIMITIVES.has(spelling)) return [this.made(ts, new S.PrimitiveTypeSpecifier({ keyword: spelling }))];
      return [this.made(ts, new S.NamedTypeSpecifier({ name: this.identifier(ts) }))];
    }
    if (kind === "sized_type_specifier") {
      return this.kids(ts).flatMap((c) => (c.isNamed ? this.specifiers(c)
        : [this.made(c, new S.PrimitiveTypeSpecifier({ keyword: c.type }))]));
    }
    if (kind === "type_identifier" || kind === "qualified_identifier" || kind === "template_type") {
      return [this.made(ts, new S.NamedTypeSpecifier({ name: this.name(ts) }))];
    }
    if (kind === "dependent_type") {
      return [this.made(ts, new S.TypenameSpecifier({ name: this.specifiers(this.named(ts)[0] as TS)[0].name }))];
    }
    if (kind === "placeholder_type_specifier") {
      const constraint = this.field(ts, "constraint");
      return [this.made(ts, new S.PlaceholderTypeSpecifier({ constraint: constraint !== null ? this.name(constraint) : null,
        decltype: this.named(ts).some((c) => c.type === "decltype") }))];
    }
    if (kind === "decltype") {
      return [this.made(ts, new S.DecltypeSpecifier({ expression: this.expression(this.named(ts)[0] as TS) }))];
    }
    if (["class_specifier", "struct_specifier", "union_specifier"].includes(kind)) return [this.classSpecifier(ts)];
    if (kind === "enum_specifier") return [this.enumSpecifier(ts)];
    if (kind === "storage_class_specifier" || ["virtual", "typedef", "__extension__"].includes(kind)) {
      return [this.made(ts, new S.DeclSpecifier({ keyword: spelling }))];
    }
    if (kind === "type_qualifier") {
      const inner = this.named(ts);
      if (inner.length > 0) return [this.attribute(inner[0] as TS)];
      if (CV_KEYWORDS.has(spelling)) return [this.made(ts, new S.CvQualifier({ keyword: spelling }))];
      return [this.made(ts, new S.DeclSpecifier({ keyword: spelling }))];
    }
    const condition = this.named(ts); // explicit_function_specifier, the last kind of specifier
    return [this.made(ts, new S.ExplicitSpecifier({ condition: condition.length > 0 ? this.expression(condition[0] as TS) : null }))];
  }

  classSpecifier(ts: TS): SyntaxNode {
    const made = new S.ClassSpecifier({ key: this.text(this.kids(ts)[0] as TS) });
    const name = this.field(ts, "name");
    if (name !== null) made.name = this.name(name);
    for (const c of this.named(ts)) {
      if (ATTRIBUTES.has(c.type)) made.attributes.push(this.attribute(c));
      else if (c.type === "virtual_specifier") made.final = true;
      else if (c.type === "base_class_clause") made.bases = this.bases(c);
    }
    const body = this.field(ts, "body");
    if (body !== null) made.body = this.made(body, new S.MemberList({ items: this.items(Converter.all(body), true) }));
    return this.made(ts, made);
  }

  bases(ts: TS): S.BaseSpecifier[] {
    const out: S.BaseSpecifier[] = [];
    let current: S.BaseSpecifier | null = null;
    for (const c of this.kids(ts).slice(1)) {
      current ??= this.made(c, new S.BaseSpecifier());
      if (c.type === ",") {
        out.push(current);
        current = null;
      } else if (c.type === "virtual") current.virtual = true;
      else if (c.type === "access_specifier") current.access = this.text(c) as S.Access;
      else if (c.type === "...") current.pack = true;
      else if (ATTRIBUTES.has(c.type)) current.attributes.push(this.attribute(c));
      else current.type = this.name(c);
    }
    out.push(current as S.BaseSpecifier);
    return out;
  }

  enumSpecifier(ts: TS): SyntaxNode {
    const kids = this.kids(ts);
    const second = kids[1];
    const key = second !== undefined && (second.type === "class" || second.type === "struct") ? `enum ${second.type}` : "enum";
    const made = new S.EnumSpecifier({ key });
    const name = this.field(ts, "name");
    const base = this.field(ts, "base");
    const body = this.field(ts, "body");
    made.attributes = this.named(ts).filter((c) => ATTRIBUTES.has(c.type)).map((c) => this.attribute(c));
    if (name !== null) made.name = this.name(name);
    if (base !== null) made.base = this.made(base, new S.TypeId({ specifiers: this.specifiers(base) }));
    if (body !== null) {
      const items = this.kids(body);
      made.body = this.made(body, new S.EnumeratorList({ enumerators: this.items(Converter.all(body), false, true),
        trailing_comma: items.length > 2 && (items[items.length - 2] as TS).type === "," }));
    }
    return this.made(ts, made);
  }

  enumerator(ts: TS): SyntaxNode {
    const value = this.field(ts, "value");
    return this.made(ts, new S.Enumerator({ name: this.identifier(this.require(ts, "name")),
      value: value !== null ? this.expression(value) : null }));
  }

  // Attributes

  attribute(ts: TS): any {
    const kind = ts.type;
    if (kind === "attribute_declaration") {
      return this.made(ts, new S.StandardAttributeSpecifier({ attributes: this.named(ts).map((a) => this.standardAttribute(a)) }));
    }
    if (kind === "attribute_specifier") {
      const made = new S.GnuAttributeSpecifier({ keyword: this.text(this.kids(ts)[0] as TS) });
      for (const a of this.named(this.named(ts)[0] as TS)) {
        if (a.type === "call_expression") {
          made.attributes.push(this.made(a, new S.Attribute({ name: this.text(this.require(a, "function")),
            arguments: this.expressions(this.require(a, "arguments")) })));
        } else {
          made.attributes.push(this.made(a, new S.Attribute({ name: this.text(a) })));
        }
      }
      return this.made(ts, made);
    }
    if (kind === "ms_declspec_modifier") {
      return this.made(ts, new S.DeclspecSpecifier({ attributes: this.named(ts).map((a) => this.made(a, new S.Attribute({ name: this.text(a) }))) }));
    }
    const operand = this.named(ts)[0] as TS;
    return this.made(ts, new S.AlignasSpecifier({ keyword: this.text(this.kids(ts)[0] as TS),
      operand: operand.type === "type_descriptor" ? this.typeId(operand) : this.expression(operand) }));
  }

  standardAttribute(ts: TS): SyntaxNode {
    const prefix = this.field(ts, "prefix");
    const args = this.named(ts).find((c) => c.type === "argument_list");
    return this.made(ts, new S.Attribute({ namespace: prefix !== null ? this.text(prefix) : null,
      name: this.text(this.require(ts, "name")), arguments: args !== undefined ? this.expressions(args) : [] }));
  }

  // Declarators

  /** A declarator, named or abstract. A function declarator's trailing requires-clause and virt-specifiers belong to
   * the declaration, so they go to `lift`. */
  declarator(ts: TS, lift: Lifted | null = null): any {
    const kind = ts.type;
    if (kind === "qualified_identifier") {
      const [global_scope, qualifiers, last] = this.qualifiedParts(ts);
      if (last.type === "pointer_type_declarator") return this.memberPointer(ts, global_scope, qualifiers, last, lift);
      if (last.type === "operator_cast") return this.conversion(last, lift, ts, global_scope, qualifiers);
    }
    if (NAMES.has(kind) || ["qualified_identifier", "template_function", "template_method", "destructor_name",
      "operator_name", "primitive_type"].includes(kind)) {
      return this.made(ts, new S.IdDeclarator({ name: this.name(ts) }));
    }
    if (["pointer_declarator", "abstract_pointer_declarator", "pointer_type_declarator"].includes(kind)) {
      const inner = this.field(ts, "declarator");
      const made = new S.PointerDeclarator({ declarator: inner !== null ? this.declarator(inner, lift) : null });
      for (const c of this.named(ts)) {
        if (c.type === "type_qualifier") made.qualifiers.push(this.made(c, new S.CvQualifier({ keyword: this.text(c) as S.CvKeyword })));
        else if (inner === null || c.id !== inner.id) throw this.unsupported(c);
      }
      return this.made(ts, made);
    }
    if (kind === "reference_declarator" || kind === "abstract_reference_declarator") {
      const inner = this.named(ts);
      return this.made(ts, new S.ReferenceDeclarator({ rvalue: this.has(ts, "&&"),
        declarator: inner.length > 0 ? this.declarator(inner[0] as TS, lift) : null }));
    }
    if (kind === "array_declarator" || kind === "abstract_array_declarator") {
      const inner = this.field(ts, "declarator");
      const size = this.field(ts, "size");
      const made = new S.ArrayDeclarator({ declarator: inner !== null ? this.declarator(inner, lift) : null,
        static: this.has(ts, "static") });
      if (size !== null) {
        if (size.type === "*") made.star = true;
        else made.size = this.expression(size);
      }
      made.qualifiers = this.named(ts).filter((c) => c.type === "type_qualifier")
        .map((c) => this.made(c, new S.CvQualifier({ keyword: this.text(c) as S.CvKeyword })));
      return this.made(ts, made);
    }
    if (kind === "function_declarator" || kind === "abstract_function_declarator") return this.functionDeclarator(ts, lift);
    if (kind === "parenthesized_declarator" || kind === "abstract_parenthesized_declarator") {
      const inner = this.named(ts);
      if (inner.length !== 1) throw this.unsupported(inner[0] as TS); // a calling convention, as in `(__cdecl *f)`
      return this.made(ts, new S.ParenthesizedDeclarator({ declarator: this.declarator(inner[0] as TS, lift) }));
    }
    if (kind === "attributed_declarator") {
      const parts = this.named(ts);
      const made = this.declarator(parts[0] as TS, lift);
      made.attributes.push(...parts.slice(1).map((a) => this.attribute(a)));
      return made;
    }
    if (kind === "structured_binding_declarator") {
      return this.made(ts, new S.StructuredBindingDeclarator({
        bindings: this.named(ts).map((c) => this.made(c, new S.IdDeclarator({ name: this.identifier(c) }))) }));
    }
    if (kind === "variadic_declarator") {
      const inner = this.named(ts);
      return this.made(ts, new S.PackDeclarator({ declarator: inner.length > 0
        ? this.made(inner[0] as TS, new S.IdDeclarator({ name: this.identifier(inner[0] as TS) })) : null }));
    }
    return this.conversion(ts, lift); // operator_cast, the last kind of declarator
  }

  /** A qualified_identifier, which tree-sitter nests: whether it starts with `::`, its qualifiers, and its last name's
   * node. */
  qualifiedParts(ts: TS): [boolean, SyntaxNode[], TS] {
    const qualifiers: SyntaxNode[] = [];
    let node = ts;
    while (node.type === "qualified_identifier") {
      const scope = this.field(node, "scope");
      if (scope !== null) qualifiers.push(this.scope(scope));
      node = this.fields(node, "name").find((n) => n.isNamed) as TS;
    }
    return [this.field(ts, "scope") === null, qualifiers, node];
  }

  /** `C::* declarator`, which tree-sitter writes as a qualified name ending in a pointer declarator. */
  memberPointer(ts: TS, global_scope: boolean, qualifiers: SyntaxNode[], last: TS, lift: Lifted | null): SyntaxNode {
    const made = this.declarator(last, lift);
    const scope = qualifiers.pop() as SyntaxNode;
    made.scope = qualifiers.length > 0 || global_scope
      ? this.made(ts, new S.QualifiedName({ global_scope, qualifiers, name: scope })) : scope;
    return made;
  }

  functionDeclarator(ts: TS, lift: Lifted | null): S.FunctionDeclarator {
    const inner = this.field(ts, "declarator");
    const made = new S.FunctionDeclarator({ declarator: inner !== null ? this.declarator(inner, lift) : null,
      parameters: this.parameters(this.require(ts, "parameters")) });
    for (const c of this.named(ts)) {
      if (c.type === "parameter_list" || (inner !== null && c.id === inner.id)) continue;
      if (c.type === "type_qualifier") made.qualifiers.push(this.made(c, new S.CvQualifier({ keyword: this.text(c) as S.CvKeyword })));
      else if (c.type === "ref_qualifier") made.ref_qualifier = this.text(c) as "&" | "&&";
      else if (c.type === "noexcept" || c.type === "throw_specifier") made.exception = this.exception(c);
      else if (c.type === "trailing_return_type") made.trailing_return = this.typeId(this.named(c)[0] as TS);
      else if (ATTRIBUTES.has(c.type)) made.attributes.push(this.attribute(c));
      else if (c.type === "requires_clause" && lift !== null) lift.requires.push(this.requiresClause(c));
      else if (c.type === "virtual_specifier" && lift !== null) {
        lift.virt_specifiers.push(this.made(c, new S.VirtSpecifier({ keyword: this.text(c) as "override" | "final" })));
      } else throw this.unsupported(c);
    }
    return this.made(ts, made);
  }

  /** `operator type declarator`, or a qualified `A::operator type declarator`: tree-sitter nests the function
   * declarator inside the conversion type's pointers; the conversion type is `type` and those pointers, and the
   * function declarator declares it. */
  conversion(ts: TS, lift: Lifted | null, qualified: TS | null = null, global_scope = false,
    qualifiers: SyntaxNode[] = []): SyntaxNode {
    const wrappers: TS[] = [];
    let node = this.require(ts, "declarator");
    while (node.type === "abstract_pointer_declarator" || node.type === "abstract_reference_declarator") {
      wrappers.push(node);
      node = this.named(node).at(-1) as TS;
    }
    let typeDeclarator: SyntaxNode | null = null;
    for (const w of wrappers.reverse()) {
      typeDeclarator = w.type === "abstract_pointer_declarator"
        ? this.made(w, new S.PointerDeclarator({ declarator: typeDeclarator,
          qualifiers: this.named(w).filter((c) => c.type === "type_qualifier")
            .map((c) => this.made(c, new S.CvQualifier({ keyword: this.text(c) as S.CvKeyword }))) }))
        : this.made(w, new S.ReferenceDeclarator({ rvalue: this.has(w, "&&"), declarator: typeDeclarator }));
    }
    let conversion: SyntaxNode = this.made(ts, new S.ConversionName({ type: this.made(ts, new S.TypeId({
      specifiers: this.specifiersOf(ts), declarator: typeDeclarator })) }));
    const made = this.functionDeclarator(node, lift);
    if (qualified !== null) {
      conversion = this.made(qualified, new S.QualifiedName({ global_scope, qualifiers, name: conversion }));
    }
    made.declarator = this.made(ts, new S.IdDeclarator({ name: conversion }));
    return made;
  }

  exception(ts: TS): SyntaxNode {
    if (ts.type === "noexcept") {
      const condition = this.named(ts);
      return this.made(ts, new S.NoexceptSpecifier({ condition: condition.length > 0 ? this.expression(condition[0] as TS) : null }));
    }
    return this.made(ts, new S.ThrowSpecifier({ types: this.named(ts).map((c) => this.typeId(c)) }));
  }

  // Parameters

  parameters(ts: TS): SyntaxNode[] {
    const out: SyntaxNode[] = [];
    for (const c of this.kids(ts)) {
      if (c.type === "...") out.push(this.made(c, new S.EllipsisParameter()));
      else if (c.isNamed) out.push(this.parameter(c));
    }
    return out;
  }

  parameter(ts: TS): SyntaxNode {
    const made = new S.ParameterDeclaration();
    made.specifiers = this.specifiersOf(ts, made.attributes);
    const declarator = this.field(ts, "declarator");
    if (declarator !== null) made.declarator = this.declarator(declarator);
    const fallback = this.field(ts, "default_value");
    if (fallback !== null) made.default = this.expression(fallback);
    return this.made(ts, made);
  }

  templateParameters(ts: TS): SyntaxNode[] {
    return this.named(ts).map((c) => {
      const kind = c.type;
      if (["type_parameter_declaration", "variadic_type_parameter_declaration", "optional_type_parameter_declaration"].includes(kind)) {
        return this.typeParameter(c);
      }
      if (kind === "template_template_parameter_declaration") {
        const inner = this.typeParameter(this.named(c).at(-1) as TS);
        return this.made(c, new S.TemplateTemplateParameter({
          parameters: this.templateParameters(this.require(c, "parameters")), key: inner.key, pack: inner.pack,
          name: inner.name, default: inner.default !== null ? (inner.default.specifiers[0] as S.NamedTypeSpecifier).name : null }));
      }
      return this.parameter(c);
    });
  }

  typeParameter(ts: TS): S.TypeParameter {
    const made = new S.TypeParameter({ key: this.text(this.kids(ts)[0] as TS), pack: this.has(ts, "...") });
    const name = this.field(ts, "name") ?? this.named(ts).find((c) => c.type === "type_identifier") ?? null;
    if (name !== null) made.name = this.identifier(name);
    const fallback = this.field(ts, "default_type");
    if (fallback !== null) made.default = this.made(fallback, new S.TypeId({ specifiers: this.specifiers(fallback) }));
    return this.made(ts, made);
  }

  // Statements

  statement(ts: TS): any {
    const method = Converter.STATEMENTS[ts.type];
    if (method === undefined) {
      const declaration = Converter.DECLARATIONS[ts.type];
      if (declaration !== undefined) return declaration(this, ts);
      throw this.unsupported(ts);
    }
    return this.made(ts, method(this, ts));
  }

  compound(ts: TS): SyntaxNode {
    return new S.CompoundStatement({ items: this.items(Converter.all(ts), false) });
  }

  expressionStatement(ts: TS): SyntaxNode {
    const inner = this.named(ts);
    if (inner.length === 0) return new S.ExpressionStatement();
    if ((inner[0] as TS).type === "gnu_asm_expression") return this.asm(inner[0] as TS);
    return new S.ExpressionStatement({ expression: this.expression(inner[0] as TS) });
  }

  asm(ts: TS): SyntaxNode {
    const made = new S.AsmDeclaration({ keyword: this.text(this.kids(ts)[0] as TS),
      template: this.expression(this.require(ts, "assembly_code")) });
    for (const q of this.named(ts)) {
      if (q.type === "gnu_asm_qualifier") (made as unknown as Record<string, unknown>)[this.text(q).replace(/^_+|_+$/g, "")] = true;
    }
    const operands = (name: string) => {
      const found = this.field(ts, name);
      return (found !== null ? this.fields(found, "operand") : []).map((o) => {
        const symbol = this.field(o, "symbol");
        return this.made(o, new S.AsmOperand({ name: symbol !== null ? this.identifier(symbol) : null,
          constraint: this.expression(this.require(o, "constraint")), value: this.expression(this.require(o, "value")) }));
      });
    };
    made.outputs = operands("output_operands");
    made.inputs = operands("input_operands");
    const clobbers = this.field(ts, "clobbers");
    const labels = this.field(ts, "goto_labels");
    made.clobbers = clobbers !== null ? this.named(clobbers).map((c) => this.expression(c)) : [];
    made.labels = labels !== null ? this.named(labels).map((c) => this.identifier(c)) : [];
    return this.made(ts, made);
  }

  /** Fills `made`'s initializer and condition from a condition_clause. */
  condition<N extends SyntaxNode>(ts: TS, made: N): N {
    const fields = made as unknown as Record<string, unknown>;
    const initializer = this.field(ts, "initializer");
    if (initializer !== null) fields["initializer"] = this.declarationOrStatement(this.named(initializer)[0] as TS);
    const value = this.require(ts, "value");
    fields["condition"] = value.type === "declaration" ? this.declarationOrStatement(value) : this.expression(value);
    return made;
  }

  if(ts: TS): SyntaxNode {
    const made = new S.IfStatement({ constexpr: this.has(ts, "constexpr"),
      consequence: this.statement(this.require(ts, "consequence")) });
    this.condition(this.require(ts, "condition"), made);
    const alternative = this.field(ts, "alternative");
    if (alternative !== null) made.alternative = this.statement(this.named(alternative)[0] as TS);
    return made;
  }

  switch(ts: TS): SyntaxNode {
    return this.condition(this.require(ts, "condition"), new S.SwitchStatement({ body: this.statement(this.require(ts, "body")) }));
  }

  while(ts: TS): SyntaxNode {
    return this.condition(this.require(ts, "condition"), new S.WhileStatement({ body: this.statement(this.require(ts, "body")) }));
  }

  do(ts: TS): SyntaxNode {
    return new S.DoStatement({ body: this.statement(this.require(ts, "body")),
      condition: this.expression(this.named(this.require(ts, "condition"))[0] as TS) });
  }

  for(ts: TS): SyntaxNode {
    const made = new S.ForStatement({ body: this.statement(this.require(ts, "body")) });
    const initializer = this.field(ts, "initializer");
    const condition = this.field(ts, "condition");
    const update = this.field(ts, "update");
    if (initializer !== null) {
      made.initializer = initializer.type === "declaration" ? this.simpleDeclaration(initializer)
        : this.made(initializer, new S.ExpressionStatement({ expression: this.expression(initializer) }));
    }
    if (condition !== null) made.condition = this.expression(condition);
    if (update !== null) made.increment = this.expression(update);
    return made;
  }

  rangeFor(ts: TS): SyntaxNode {
    const declaration = new S.SimpleDeclaration();
    declaration.specifiers = this.specifiersOf(ts, declaration.attributes);
    declaration.declarators = [this.made(ts, new S.InitDeclarator({ declarator: this.declarator(this.require(ts, "declarator")) }))];
    const made = new S.RangeForStatement({ declaration: this.made(ts, declaration),
      range: this.expression(this.require(ts, "right")), body: this.statement(this.require(ts, "body")) });
    const initializer = this.field(ts, "initializer");
    if (initializer !== null) made.initializer = this.declarationOrStatement(this.named(initializer)[0] as TS);
    return made;
  }

  return(ts: TS): SyntaxNode {
    const value = this.named(ts);
    return new S.ReturnStatement({ value: value.length > 0 ? this.expression(value[0] as TS) : null });
  }

  coReturn(ts: TS): SyntaxNode {
    const value = this.named(ts);
    return new S.CoReturnStatement({ value: value.length > 0 ? this.expression(value[0] as TS) : null });
  }

  coYield(ts: TS): SyntaxNode {
    return new S.ExpressionStatement({ expression: this.made(ts, new S.YieldExpression({
      operand: this.expression(this.named(ts)[0] as TS) })) });
  }

  throw(ts: TS): SyntaxNode {
    const value = this.named(ts);
    return new S.ExpressionStatement({ expression: this.made(ts, new S.ThrowExpression({
      operand: value.length > 0 ? this.expression(value[0] as TS) : null })) });
  }

  goto(ts: TS): SyntaxNode {
    return new S.GotoStatement({ label: this.identifier(this.require(ts, "label")) });
  }

  labeled(ts: TS): SyntaxNode {
    const label = this.require(ts, "label");
    const body = this.named(ts).filter((c) => c.id !== label.id);
    // tree-sitter parses no label that ends a block
    return new S.LabeledStatement({ label: this.identifier(label), statement: this.statement(body[0] as TS) });
  }

  try(ts: TS): S.TryStatement {
    const made = new S.TryStatement({ body: this.statement(this.require(ts, "body")) });
    for (const c of this.named(ts)) {
      if (c.type !== "catch_clause") continue;
      const parameters = this.parameters(this.require(c, "parameters"));
      made.handlers.push(this.made(c, new S.Handler({ parameter: parameters[0],
        body: this.statement(this.require(c, "body")) })));
    }
    return made;
  }

  attributed(ts: TS): SyntaxNode {
    const parts = this.named(ts);
    return new S.AttributedStatement({ attributes: parts.slice(0, -1).map((a) => this.attribute(a)),
      statement: this.statement(parts.at(-1) as TS) });
  }

  // Declarations

  simpleDeclaration(ts: TS): S.SimpleDeclaration {
    const made = new S.SimpleDeclaration();
    made.specifiers = this.specifiersOf(ts, made.attributes);
    const kids = Converter.all(ts);
    let current: S.InitDeclarator | null = null;
    const lift = lifted();
    kids.forEach((c, i) => {
      const name = ts.fieldNameForChild(i);
      if (name === "declarator") {
        current = this.initDeclarator(c, lift);
        made.declarators.push(current);
      } else if (name === "default_value" || name === "value") {
        const declarator = current as unknown as S.InitDeclarator;
        declarator.initializer = this.initializer(c, i > 0 && (kids[i - 1] as TS).type === "=", declarator);
      } else if (c.type === "bitfield_clause") { // tree-sitter-cpp parses no unnamed bit-field
        (current as unknown as S.InitDeclarator).bitfield = this.expression(this.named(c)[0] as TS);
      }
    });
    return made;
  }

  initDeclarator(ts: TS, lift: Lifted): S.InitDeclarator {
    if (ts.type === "gnu_asm_expression") throw this.unsupported(ts);
    let made: S.InitDeclarator;
    if (ts.type !== "init_declarator") {
      made = new S.InitDeclarator({ declarator: this.declarator(ts, lift) });
    } else {
      made = new S.InitDeclarator({ declarator: this.declarator(this.require(ts, "declarator"), lift) });
      made.initializer = this.initializer(this.require(ts, "value"), this.has(ts, "="), made);
    }
    made.requires = lift.requires.pop() ?? null;
    made.virt_specifiers = lift.virt_specifiers;
    lift.virt_specifiers = [];
    return this.made(ts, made);
  }

  initializer(ts: TS, equals: boolean, declarator: S.InitDeclarator): any {
    if (ts.type === "argument_list") return this.made(ts, new S.ParenthesizedInitializer({ arguments: this.expressions(ts) }));
    const value = this.expression(ts);
    if (!equals) return value;
    if (value instanceof S.IntegerLiteral && value.spelling === "0"
      && S.binding(declarator.declarator)[1] instanceof S.FunctionDeclarator) {
      declarator.pure = true; // `= 0` after a function declarator is the pure-specifier
      return null;
    }
    return this.made(ts, new S.EqualInitializer({ value }));
  }

  functionDefinition(ts: TS): SyntaxNode {
    const lift = lifted();
    const attributes: SyntaxNode[] = [];
    const specifiers = this.specifiersOf(ts, attributes);
    const declarator = this.declarator(this.require(ts, "declarator"), lift);
    const clauses = new Map(this.named(ts).map((c) => [c.type, c]));
    // a function-try-block with member initializers is a child that is not the body
    const body = this.field(ts, "body") ?? clauses.get("try_statement") ?? null;
    if (clauses.has("pure_virtual_clause")) {
      return this.made(ts, new S.SimpleDeclaration({ attributes, specifiers, declarators: [this.made(ts,
        new S.InitDeclarator({ declarator, pure: true, virt_specifiers: lift.virt_specifiers,
          requires: lift.requires[0] ?? null }))] }));
    }
    const made = new S.FunctionDefinition({ attributes, specifiers, declarator, virt_specifiers: lift.virt_specifiers,
      requires: lift.requires[0] ?? null });
    const initializers = clauses.get("field_initializer_list");
    if (initializers !== undefined) made.initializers = this.memberInitializers(initializers);
    if (body !== null && body.type === "try_statement") {
      made.body = this.made(body, this.try(body));
      const inner = this.named(body).find((c) => c.type === "field_initializer_list");
      if (inner !== undefined) made.initializers = this.memberInitializers(inner);
    } else if (body !== null) {
      made.body = this.statement(body);
    } else if (clauses.has("default_method_clause")) {
      made.body = this.made(clauses.get("default_method_clause") as TS, new S.DefaultedBody());
    } else { // tree-sitter requires a body or one of these clauses
      made.body = this.made(clauses.get("delete_method_clause") as TS, new S.DeletedBody());
    }
    return this.made(ts, made);
  }

  memberInitializers(ts: TS): S.MemberInitializer[] {
    return this.named(ts).map((c) => {
      const parts = this.named(c);
      const value = parts.at(-1) as TS;
      const initializer = value.type === "argument_list"
        ? this.made(value, new S.ParenthesizedInitializer({ arguments: this.expressions(value) })) : this.expression(value);
      return this.made(c, new S.MemberInitializer({ member: this.name(parts[0] as TS), initializer, pack: this.has(c, "...") }));
    });
  }

  templateDeclaration(ts: TS): SyntaxNode {
    const parameters = this.require(ts, "parameters");
    const made = new S.TemplateDeclaration({ parameters: this.templateParameters(parameters) });
    for (const c of this.named(ts)) {
      if (c.id === parameters.id) continue;
      if (c.type === "requires_clause") made.requires = this.requiresClause(c);
      else made.declaration = this.declarationOrStatement(c);
    }
    return made;
  }

  templateInstantiation(ts: TS): SyntaxNode {
    const declaration = new S.SimpleDeclaration();
    declaration.specifiers = this.specifiersOf(ts, declaration.attributes);
    const declarator = this.require(ts, "declarator");
    if (!declarator.isMissing) declaration.declarators = [this.initDeclarator(declarator, lifted())];
    return new S.ExplicitInstantiation({ extern: this.pre.externTemplates.has(ts.startIndex),
      declaration: this.made(ts, declaration) });
  }

  typeSpecifierDeclaration(ts: TS): SyntaxNode {
    return new S.SimpleDeclaration({ specifiers: this.specifiers(ts) });
  }

  friend(ts: TS): SyntaxNode {
    const friend = this.made(this.kids(ts)[0] as TS, new S.DeclSpecifier({ keyword: "friend" }));
    const inner = this.named(ts);
    const first = inner[0] as TS;
    if (first.type === "declaration" || first.type === "function_definition") {
      const made = this.declarationOrStatement(first);
      made.specifiers.unshift(friend);
      return made;
    }
    const key = this.kids(ts).find((c) => ["class", "struct", "union"].includes(c.type))?.type ?? null;
    const specifier = key !== null ? this.made(first, new S.ClassSpecifier({ key, name: this.name(first) }))
      : this.specifiers(first)[0];
    return new S.SimpleDeclaration({ specifiers: [friend, specifier] });
  }

  alias(ts: TS): SyntaxNode {
    return new S.AliasDeclaration({ name: this.identifier(this.require(ts, "name")),
      attributes: this.named(ts).filter((c) => ATTRIBUTES.has(c.type)).map((c) => this.attribute(c)),
      type: this.typeId(this.require(ts, "type")) });
  }

  using(ts: TS): SyntaxNode {
    const target = this.name(this.named(ts)[0] as TS);
    if (this.has(ts, "namespace")) return new S.UsingDirective({ name: target });
    if (this.has(ts, "enum")) return new S.UsingEnumDeclaration({ type: target });
    return new S.UsingDeclaration({ declarators: [this.made(ts, new S.UsingDeclarator({
      typename_keyword: this.has(ts, "typename"), name: target }))] });
  }

  namespace(ts: TS): SyntaxNode {
    const made = new S.NamespaceDefinition({ inline: this.has(ts, "inline"),
      attributes: this.named(ts).filter((c) => ATTRIBUTES.has(c.type)).map((c) => this.attribute(c)) });
    const name = this.field(ts, "name");
    made.names = name !== null ? this.namespaceNames(name).map(([inline, n]) =>
      this.made(n, new S.NamespaceName({ inline, name: this.identifier(n) }))) : [];
    made.items = this.items(Converter.all(this.require(ts, "body")), true);
    return made;
  }

  /** The names of a namespace_identifier or nested_namespace_specifier, which tree-sitter nests, each with whether
   * `inline` precedes it. */
  namespaceNames(ts: TS): [boolean, TS][] {
    if (ts.type === "namespace_identifier") return [[false, ts]];
    const out: [boolean, TS][] = [];
    let inline = false;
    for (const c of this.kids(ts)) {
      if (c.type === "inline") {
        inline = true;
      } else if (c.isNamed) {
        const found = this.namespaceNames(c);
        const [first, ...rest] = found as [[boolean, TS], ...[boolean, TS][]];
        out.push([inline || first[0], first[1]], ...rest);
        inline = false;
      }
    }
    return out;
  }

  namespaceAlias(ts: TS): SyntaxNode {
    const name = this.require(ts, "name");
    const target = this.named(ts).find((c) => c.id !== name.id) as TS;
    let resolved: SyntaxNode;
    if (target.type === "nested_namespace_specifier") {
      const parts = this.namespaceNames(target).map(([, n]) => this.identifier(n));
      resolved = this.made(target, new S.QualifiedName({ qualifiers: parts.slice(0, -1), name: parts.at(-1),
        global_scope: (this.kids(target)[0] as TS).type === "::" }));
    } else {
      resolved = this.identifier(target);
    }
    return new S.NamespaceAliasDefinition({ name: this.identifier(name), target: resolved });
  }

  staticAssert(ts: TS): SyntaxNode {
    const message = this.field(ts, "message");
    return new S.StaticAssertDeclaration({ keyword: this.text(this.kids(ts)[0] as TS),
      condition: this.expression(this.require(ts, "condition")), message: message !== null ? this.expression(message) : null });
  }

  linkage(ts: TS): SyntaxNode {
    const body = this.require(ts, "body");
    const language = this.text(this.require(ts, "value")).slice(1, -1);
    if (body.type === "declaration_list") {
      return new S.LinkageSpecification({ language, braced: true, items: this.items(Converter.all(body), true) });
    }
    return new S.LinkageSpecification({ language, items: [this.declarationOrStatement(body)] });
  }

  concept(ts: TS): SyntaxNode {
    const name = this.require(ts, "name");
    return new S.ConceptDefinition({ name: this.identifier(name),
      constraint: this.expression(this.named(ts).find((c) => c.id !== name.id) as TS) });
  }
}

const C = Converter.prototype;
const bind = (method: (this: Converter, ts: TS) => any): Method => (self, ts) => method.call(self, ts);

Converter.EXPRESSIONS = {
  ...Object.fromEntries([...NAMES, "qualified_identifier", "template_function", "template_method", "dependent_name",
    "destructor_name", "operator_name"].map((n) => [n, bind(C.idExpression)])),
  number_literal: bind(C.number), char_literal: bind(C.quoted), string_literal: bind(C.quoted),
  raw_string_literal: bind(C.quoted), concatenated_string: bind(C.concatenated), user_defined_literal: bind(C.userDefined),
  true: () => new S.BooleanLiteral({ value: true }), false: () => new S.BooleanLiteral(), null: bind(C.null),
  this: () => new S.ThisExpression(), parenthesized_expression: bind(C.parenthesized), comma_expression: bind(C.comma),
  binary_expression: bind(C.binary), assignment_expression: bind(C.assignment),
  conditional_expression: bind(C.conditional), unary_expression: bind(C.unary), pointer_expression: bind(C.unary),
  update_expression: bind(C.update), cast_expression: bind(C.cast), call_expression: bind(C.call),
  field_expression: bind(C.fieldExpression), subscript_expression: bind(C.subscript), sizeof_expression: bind(C.sizeof),
  alignof_expression: bind(C.alignof), new_expression: bind(C.new), delete_expression: bind(C.delete),
  fold_expression: bind(C.fold), parameter_pack_expansion: bind(C.packExpansion),
  initializer_list: bind(C.initializerList), compound_literal_expression: bind(C.compoundLiteral),
  generic_expression: bind(C.generic), offsetof_expression: bind(C.offsetof), lambda_expression: bind(C.lambda),
  requires_expression: bind(C.requiresExpression), requires_clause: bind(C.requiresClause),
  co_await_expression: (self, ts) => new S.AwaitExpression({ operand: self.expression(self.require(ts, "argument")) }),
  extension_expression: (self, ts) => new S.ExtensionExpression({ operand: self.expression(self.named(ts)[0] as TS) }),
  preproc_defined: (self, ts) => new S.DefinedExpression({ name: self.identifier(self.named(ts)[0] as TS) }),
};

Converter.STATEMENTS = {
  compound_statement: bind(C.compound), expression_statement: bind(C.expressionStatement), if_statement: bind(C.if),
  switch_statement: bind(C.switch), while_statement: bind(C.while), do_statement: bind(C.do),
  for_statement: bind(C.for), for_range_loop: bind(C.rangeFor), return_statement: bind(C.return),
  co_return_statement: bind(C.coReturn), co_yield_statement: bind(C.coYield), throw_statement: bind(C.throw),
  break_statement: () => new S.BreakStatement(), continue_statement: () => new S.ContinueStatement(),
  goto_statement: bind(C.goto), labeled_statement: bind(C.labeled), try_statement: bind(C.try),
  attributed_statement: bind(C.attributed),
};

Converter.DECLARATIONS = {
  declaration: bind(C.simpleDeclaration), field_declaration: bind(C.simpleDeclaration),
  type_definition: bind(C.simpleDeclaration), function_definition: bind(C.functionDefinition),
  template_declaration: bind(C.templateDeclaration), template_instantiation: bind(C.templateInstantiation),
  friend_declaration: bind(C.friend), alias_declaration: bind(C.alias), using_declaration: bind(C.using),
  namespace_definition: bind(C.namespace), namespace_alias_definition: bind(C.namespaceAlias),
  static_assert_declaration: bind(C.staticAssert), linkage_specification: bind(C.linkage), concept_definition: bind(C.concept),
  ...Object.fromEntries(["class_specifier", "struct_specifier", "union_specifier", "enum_specifier"]
    .map((n) => [n, bind(C.typeSpecifierDeclaration)])),
};

/** The tree of `text`, the offset where each of its nodes starts, and the source, for locating problems. Throws
 * `ParseError` for text tree-sitter-cpp cannot parse. */
export function parse(text: string): [S.TranslationUnit, Map<SyntaxNode, number>, Source] {
  const plain = new Source(text);
  const [cleaned, pre] = premodules(text, plain);
  const source = new Source(text, cleaned);
  const tree = PARSER.parse(cleaned) as NonNullable<ReturnType<TSParser["parse"]>>;
  const converter = new Converter(source, pre);
  const unit = converter.unit(tree.rootNode);
  tree.delete();
  return [unit, converter.positions, source];
}
