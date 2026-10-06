/**
 * Python: between mbse-expressions' Python dialect and the Python language's syntax trees, both ways, tree to tree.
 *
 * From terms to syntax nodes: `expression(term)` is the Python expression a term of the dialect writes, `module(term)`
 * the module of its imports and then the expression, and `function_(name, parameters, term)` the function that returns
 * it, its imports first: a constraint as code. Every term of the dialect has a counterpart, and the expression prints
 * as the dialect renders it, but for the parentheses the printer chooses. A constant is the literal `repr` writes, a
 * negative number a negation, and a float that is not finite `float('nan')` or `float('inf')`.
 *
 * From syntax nodes to terms: `term(expression)` and `term_of_module(module)`, which reads a module of imports, then
 * one expression (comments are skipped), as the dialect's `parse` reads source in Python. They throw `TranspileError`
 * at the first syntax node the dialect cannot hold, with its path: a keyword argument, a slice, a lambda other than `(lambda name: body)(value)` (a let), a generator of more than one `for`, and
 * any other kind of expression. `and` and `or` of more than two operands nest to the left, and a chained comparison
 * (`a < b < c`) is `and` of comparisons that share their middle operands. Literals are decoded as
 * Python decodes them: ints, floats, strings and bytes (with their prefixes, escapes and adjacent literals joined), and
 * `True` and `False`; `None`, `...`, imaginary numbers and `\N{...}` escapes have no counterpart. With the Python
 * standards' parsers, this reads Python source into the dialect, which the dialect alone does only in Python.
 */

import { Domains, Expressions as E } from "@mbse/expressions/Dialects/Python";
import { Errors, Repr } from "@mbse/schemas/Framework";

import { TranspileError } from "../Framework/Errors.js";
import { type Builder, Parents, type SyntaxNode } from "../Framework/Syntax.js";
import * as P from "../Python/Syntax.js";

const Py = P.LANGUAGE.Builders;
type Term = any; // a term of the Python dialect, read through its kind and properties

// --- From terms to syntax nodes ---

/** The Python expression `term` writes. A term with imports is a module (`module`) or a function (`function_`). */
export function expression(term: Term): SyntaxNode {
  return syntax(term).create();
}

/** The module that writes `term`: its imports, then the expression as a statement. */
export function module(term: Term): P.Module {
  const [imports, body] = importsOf(term);
  return Py.Module().body([...imports, Py.Expr().value(syntax(body))]).create();
}

/** `def name(parameters): return term`, with the term's imports first in its body. */
export function function_(name: string, parameters: string[], term: Term): P.FunctionDef {
  const [imports, body] = importsOf(term);
  const args = Py.Arguments().args(parameters.map((parameter) => Py.Arg().arg(parameter)));
  return Py.FunctionDef().name(name).args(args).body([...imports, Py.Return().value(syntax(body))]).create();
}

const kindOf = (term: Term): string => term.kind().KIND;

/** The import statements that enclose `term`, outermost first, and the expression within them. */
function importsOf(term: Term): [SyntaxNode[], Term] {
  const imports: SyntaxNode[] = [];
  while (kindOf(term) === "import" || kindOf(term) === "importfrom") {
    const names = kindOf(term) === "import" ? term.module.split(".") : [term.name];
    const alias = Py.Alias().name(Py.DottedName().names(names)).asname(term.alias);
    if (kindOf(term) === "import") {
      imports.push(Py.Import().add_names(alias).create());
    } else {
      const moduleName = Py.DottedName().names(term.module.split("."));
      imports.push(Py.ImportFrom().module(moduleName).add_names(alias).create());
    }
    term = term.body;
  }
  return [imports, term];
}

/** The builder of the syntax node that writes `term`. */
function syntax(term: Term): Builder {
  switch (kindOf(term)) {
    case "constant":
      return constant(term.value);
    case "name":
      return Py.Name().id(term.name);
    case "attribute":
      return Py.Attribute().value(syntax(term.value)).attr(term.attr);
    case "subscript":
      return Py.Subscript().value(syntax(term.value)).slice(constant(term.key));
    case "index":
      return Py.Subscript().value(syntax(term.value)).slice(syntax(term.index));
    case "call":
      return Py.Call().func(syntax(term.function)).args(term.arguments.map(syntax));
    case "compare": {
      const comparison = Py.Comparison().op(term.operator).comparator(syntax(term.right));
      return Py.Compare().left(syntax(term.left)).add_comparisons(comparison);
    }
    case "boolop": { // `a and b and c`, nested to the left, is one BoolOp
      let left = term.left;
      const values = [syntax(term.right)];
      while (kindOf(left) === "boolop" && left.operator === term.operator) {
        values.unshift(syntax(left.right));
        left = left.left;
      }
      return Py.BoolOp().op(term.operator).values([syntax(left), ...values]);
    }
    case "binop":
      return Py.BinOp().left(syntax(term.left)).op(term.operator).right(syntax(term.right));
    case "unaryop":
      return Py.UnaryOp().op(term.operator).operand(syntax(term.operand));
    case "ifexp":
      return Py.IfExp().test(syntax(term.test)).body(syntax(term.body)).orelse(syntax(term.orelse));
    case "generator": {
      const clause = Py.Comprehension().target(Py.Name().id(term.name)).iter(syntax(term.iterable))
        .ifs(term.conditions.map(syntax));
      return Py.GeneratorExp().elt(syntax(term.element)).add_generators(clause);
    }
    case "let": { // `(lambda name: body)(value)`
      const parameters = Py.Arguments().add_args(Py.Arg().arg(term.name));
      return Py.Call().func(Py.Lambda().args(parameters).body(syntax(term.body))).add_args(syntax(term.value));
    }
    default:
      throw new TranspileError("an import can only enclose the whole expression", "");
  }
}

/** The builder of the literal of a native value: a negation for a negative number, and `float(...)` for a float that
 * is not finite. */
function constant(value: unknown): Builder {
  if (typeof value === "number" && !Number.isFinite(value)) {
    const call = Py.Call().func(Py.Name().id("float"))
      .add_args(Py.Constant().spelling(Repr.repr(Number.isNaN(value) ? "nan" : "inf")));
    return value < 0 ? Py.UnaryOp().op("-").operand(call) : call;
  }
  const text = Repr.repr(value);
  if (text.startsWith("-")) return Py.UnaryOp().op("-").operand(constant(-(value as number)));
  return Py.Constant().spelling(text);
}

// --- From syntax nodes to terms ---

/** The term of the dialect that the Python expression writes. */
export function term(expression: SyntaxNode): Term {
  return new Reader(expression).term(expression);
}

/** The term a module writes: import statements, then one expression; comments are skipped. */
export function term_of_module(module: P.Module): Term {
  const reader = new Reader(module);
  const statements = module.body.filter((s) => !(s instanceof P.Comment));
  const last = statements[statements.length - 1];
  if (!(last instanceof P.Expr)) throw new TranspileError("the module must end with an expression", "");
  let result = reader.term(last.value as SyntaxNode);
  for (const statement of statements.slice(0, -1).reverse()) {
    if (statement instanceof P.Import && !statement.is_lazy) {
      for (const alias of [...statement.names].reverse()) {
        result = E.import_(dotted(alias.name as P.DottedName), result, spelling(alias.asname));
      }
    } else if (statement instanceof P.ImportFrom && !statement.is_lazy && !statement.level
      && statement.module !== null) {
      for (const alias of [...statement.names].reverse()) {
        if (alias.name === null) throw reader.error(statement, "import * binds names that cannot be known");
        result = E.importfrom(dotted(statement.module), dotted(alias.name), result, spelling(alias.asname));
      }
    } else {
      throw reader.error(statement, "only imports may precede the expression");
    }
  }
  return result;
}

/** `node` without the parentheses written around it. */
function bare(node: SyntaxNode): SyntaxNode {
  while (node instanceof P.Parenthesized) node = node.value as SyntaxNode;
  return node;
}

function dotted(name: P.DottedName): string {
  return name.names.map((identifier) => identifier.spelling as string).join(".");
}

function spelling(identifier: P.Identifier | null): string | null {
  return identifier === null ? null : identifier.spelling as string;
}

/** Reads the syntax nodes of one tree into terms, locating errors by their path in it. */
class Reader {
  private readonly parents: Parents;

  constructor(root: SyntaxNode) {
    this.parents = new Parents(root);
  }

  error(node: SyntaxNode, message: string): TranspileError {
    return new TranspileError(message, this.parents.path(node));
  }

  term(node: SyntaxNode): Term {
    node = bare(node);
    if (node instanceof P.Constant || node instanceof P.ConcatenatedString) {
      return E.constant(this.literal(node) as any);
    }
    if (node instanceof P.Name) return E.name((node.id as P.Identifier).spelling as string);
    if (node instanceof P.Attribute) {
      return E.attribute(this.term(node.value as SyntaxNode), (node.attr as P.Identifier).spelling as string);
    }
    if (node instanceof P.Subscript) {
      const index = bare(node.slice as SyntaxNode);
      if (index instanceof P.Slice || index instanceof P.Tuple) throw this.error(index, "slices are not supported");
      if (index instanceof P.Constant) {
        const key = this.literal(index);
        if (typeof key === "string") return E.subscript(this.term(node.value as SyntaxNode), key);
      }
      return E.index(this.term(node.value as SyntaxNode), this.term(node.slice as SyntaxNode));
    }
    if (node instanceof P.GeneratorExp) {
      const clause = node.generators[0] as P.Comprehension;
      if (node.generators.length !== 1 || clause.is_async || !(clause.target instanceof P.Name)) {
        throw this.error(node, "a generator has one for, over a name");
      }
      return E.generator((clause.target.id as P.Identifier).spelling as string, this.term(clause.iter as SyntaxNode),
        this.term(node.elt as SyntaxNode), ...clause.ifs.map((c) => this.term(c)));
    }
    if (node instanceof P.Call) return this.call(node);
    if (node instanceof P.Compare) { // a chain a < b < c is a < b and b < c, the middle operand shared
      let left = this.term(node.left as SyntaxNode);
      let result: Term | null = null;
      for (const comparison of node.comparisons) {
        this.operator(comparison, comparison.op as string, Domains.COMPARE);
        const right = this.term(comparison.comparator as SyntaxNode);
        const compare = E.compare(comparison.op as string, left, right);
        result = result === null ? compare : E.boolop("and", result, compare);
        left = right;
      }
      return result as Term;
    }
    if (node instanceof P.BoolOp) {
      let result = this.term(node.values[0] as SyntaxNode);
      for (const value of node.values.slice(1)) result = E.boolop(node.op as string, result, this.term(value));
      return result;
    }
    if (node instanceof P.BinOp) {
      this.operator(node, node.op as string, Domains.BINOP);
      return E.binop(node.op as string, this.term(node.left as SyntaxNode), this.term(node.right as SyntaxNode));
    }
    if (node instanceof P.UnaryOp) return E.unaryop(node.op as string, this.term(node.operand as SyntaxNode));
    if (node instanceof P.IfExp) {
      return E.ifexp(this.term(node.test as SyntaxNode), this.term(node.body as SyntaxNode),
        this.term(node.orelse as SyntaxNode));
    }
    throw this.error(node, `${node.kind().KIND} has no counterpart in the Python dialect`);
  }

  private operator(node: SyntaxNode, operator: string, vocabulary: ReadonlyMap<string, unknown>): void {
    if (!vocabulary.has(operator)) {
      throw this.error(node, `the operator '${operator}' has no counterpart in the Python dialect`);
    }
  }

  private call(node: P.Call): Term {
    if (node.keywords.length > 0) {
      throw this.error(node.keywords[0] as SyntaxNode, "keyword arguments are not supported");
    }
    const fn = bare(node.func as SyntaxNode);
    if (fn instanceof P.Lambda) {
      const parameters = fn.args as P.Arguments;
      const only = parameters.args[0];
      if (parameters.args.length !== 1 || node.args.length !== 1 || parameters.posonlyargs.length > 0
        || parameters.vararg !== null || parameters.kwonlyargs.length > 0 || parameters.kwarg !== null
        || (only as P.Arg).default_value !== null) {
        throw this.error(node, "a let binds one name");
      }
      return E.let_(((only as P.Arg).arg as P.Identifier).spelling as string, this.term(node.args[0] as SyntaxNode),
        this.term(fn.body as SyntaxNode));
    }
    return E.call(this.term(node.func as SyntaxNode), ...node.args.map((argument) => this.term(argument)));
  }

  /** The native value a literal writes, as Python decodes it. */
  literal(node: SyntaxNode): unknown {
    if (node instanceof P.ConcatenatedString) {
      const parts = node.values.map((part) => (part instanceof P.Constant ? this.literal(part) : this.term(part)));
      const binary = parts.map((part) => part instanceof Uint8Array);
      if (binary.some((b) => b !== binary[0])) throw this.error(node, "bytes and strings cannot be joined");
      if (!binary[0]) return parts.join("");
      return new Uint8Array(parts.flatMap((part) => [...(part as Uint8Array)]));
    }
    try {
      return decode((node as P.Constant).spelling as string);
    } catch (error) { // decode throws only ValueError
      throw this.error(node, (error as Error).message);
    }
  }
}

// --- Python's literals ---

const ESCAPES: Record<string, string> = {
  "\\": "\\", "'": "'", "\"": "\"", a: "\x07", b: "\b", f: "\f", n: "\n", r: "\r", t: "\t", v: "\v",
};

/** The native value of a Python literal's spelling; ValueError for one the dialect cannot hold. */
export function decode(spelling: string): boolean | bigint | number | string | Uint8Array {
  if (spelling === "True" || spelling === "False") return spelling === "True";
  if ("jJ".includes(spelling[spelling.length - 1] as string) || spelling === "None" || spelling === "...") {
    throw new Errors.ValueError("only native constants are supported");
  }
  if (/^(0[xX][0-9a-fA-F_]+|0[oO][0-7_]+|0[bB][01_]+|[0-9][0-9_]*)$/.test(spelling)) {
    return BigInt(spelling.replaceAll("_", ""));
  }
  if ("0123456789.".includes(spelling[0] as string)) return Number(spelling.replaceAll("_", ""));
  const prefix = (/^[a-zA-Z]*/.exec(spelling) as RegExpExecArray)[0].toLowerCase();
  const three = spelling.slice(prefix.length, prefix.length + 3);
  const quote = three === "\"\"\"" || three === "'''" ? three : spelling[prefix.length] as string;
  const body = spelling.slice(prefix.length + quote.length, -quote.length);
  const binary = prefix.includes("b");
  const text = prefix.includes("r") ? body : unescape(body, binary);
  return binary ? Uint8Array.from(text, (c) => c.charCodeAt(0)) : text;
}

/** The characters a literal's body writes, its escapes decoded; for bytes, each character is a byte. */
function unescape(body: string, binary: boolean): string {
  let out = "";
  let i = 0;
  while (i < body.length) {
    const c = body[i] as string;
    if (c !== "\\") {
      out += c;
      i += 1;
      continue;
    }
    const e = body[i + 1] as string;
    if (e === "\n") {
      i += 2;
    } else if (e in ESCAPES) {
      out += ESCAPES[e];
      i += 2;
    } else if ("01234567".includes(e)) {
      const digits = (/^[0-7]{1,3}/.exec(body.slice(i + 1)) as RegExpExecArray)[0];
      const code = parseInt(digits, 8);
      out += String.fromCodePoint(binary ? code & 0xff : code);
      i += 1 + digits.length;
    } else if (e === "x" || (!binary && (e === "u" || e === "U"))) {
      const size = ({ x: 2, u: 4, U: 8 } as Record<string, number>)[e] as number;
      const code = parseInt(body.slice(i + 2, i + 2 + size), 16);
      if (code > 0x10ffff) throw new Errors.ValueError("an escape beyond U+10FFFF");
      out += String.fromCodePoint(code);
      i += 2 + size;
    } else if (e === "N" && !binary) {
      throw new Errors.ValueError("a \\N{...} escape is not supported");
    } else { // an unknown escape keeps its backslash
      out += c;
      i += 1;
    }
  }
  return out;
}
