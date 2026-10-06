/**
 * Verilog: between mbse-expressions' SystemVerilog dialect and the Verilog language's syntax trees, both ways, tree to
 * tree.
 *
 * From terms to syntax nodes: `expression(term)` is the SystemVerilog expression a term of the dialect writes, and a
 * constraint becomes SystemVerilog as `function_(name, ports, term)`, a function that returns it, `constraint(name,
 * term)`, a `constraint` block that holds it, or `assertion(term)`, an immediate assertion of it. Every term of the
 * dialect has a counterpart, and the expression prints as the dialect renders it. A constant is an unsized decimal, a
 * real or a string literal, a negative number a negation, and a real that is not finite `0.0 / 0.0` or `1.0 / 0.0`; a
 * vector is a sized literal in its base, as the dialect writes it.
 *
 * From syntax nodes to terms: `term(expression)`, and `term_of_function`, `term_of_constraint` and `term_of_assertion`
 * for what the writers make. They throw `TranspileError` at the first syntax node the dialect cannot hold, with its
 * path: an unbased or an unsized based literal, a part-select with `+:` or `-:`, a tolerance range, a cast to a type
 * the dialect does not name, an iteration that is not a reduction over one iterator, a scoped name, attributes, and
 * any other kind of expression. A replication of several items repeats their concatenation. Literals are decoded as
 * IEEE 1800 reads them: a sized literal's digits are its bits, extended or truncated to its size, and a string's
 * escapes are decoded.
 */

import { Domains, Expressions as E, Text } from "@mbse/expressions/Dialects/SystemVerilog";
import { Errors, Repr } from "@mbse/schemas/Framework";

import { TranspileError } from "../Framework/Errors.js";
import { Parents, type SyntaxNode } from "../Framework/Syntax.js";
import * as S from "../Verilog/Syntax.js";

type Term = any; // a term of the SystemVerilog dialect, read through its kind and properties

const VECTORS = ["bit", "logic", "reg"];
const ATOMS = ["byte", "shortint", "int", "longint", "integer", "time"];

// --- From terms to syntax nodes ---

const kindOf = (term: Term): string => term.kind().KIND;
const identifier = (spelling: string): S.Identifier => new S.Identifier({ spelling });

/** The SystemVerilog expression `term` writes. */
export function expression(term: Term): S.Expression {
  switch (kindOf(term)) {
    case "constant":
      return constant(term.value);
    case "vector":
      return new S.IntegerLiteral({ spelling: Text.ToText(term) }); // as the dialect writes it, in its base
    case "identifier":
      return name(term.name);
    case "unary":
      return new S.UnaryExpression({ operator: term.operator, operand: expression(term.operand) });
    case "binary":
      return new S.BinaryExpression({ left: expression(term.left), operator: term.operator, right: expression(term.right) });
    case "conditional":
      return new S.ConditionalExpression({ condition: expression(term.condition), consequence: expression(term.consequent),
        alternative: expression(term.alternative) });
    case "concatenation":
      return new S.Concatenation({ items: term.parts.map(expression) });
    case "replication":
      return new S.Replication({ count: expression(term.count), items: [expression(term.value)] });
    case "select":
      return new S.IndexExpression({ value: expression(term.value), index: expression(term.index) });
    case "range":
      return new S.RangeSelect({ value: expression(term.value), left: expression(term.msb), operator: ":",
        right: expression(term.lsb) });
    case "inside":
      return new S.InsideExpression({ value: expression(term.value), set: term.items.map((item: Term) =>
        kindOf(item) === "span" ? new S.ValueRange({ left: expression(item.low), right: expression(item.high) })
          : expression(item)) });
    case "cast":
      return new S.CastExpression({ type: castType(term), value: expression(term.operand) });
    case "member":
      return new S.MemberExpression({ value: expression(term.object), member: identifier(term.name) });
    case "call": {
      const args = term.arguments.map(expression);
      if (term.function.startsWith("$")) return new S.SystemCall({ name: term.function, arguments: args });
      return new S.CallExpression({ callee: name(term.function), arguments: args });
    }
    case "method":
      return new S.CallExpression({ callee: new S.MemberExpression({ value: expression(term.array),
        member: identifier(term.name) }) });
    case "iterate": { // `array.method(name) with (body)`
      const call = new S.CallExpression({ callee: new S.MemberExpression({ value: expression(term.array),
        member: identifier(term.method) }), arguments: [name(term.name)] });
      return new S.ArrayMethodWithExpression({ call, expression: expression(term.body) });
    }
    default:
      throw new TranspileError(`a ${kindOf(term)} is not an expression`, ""); // a span, outside `inside`
  }
}

/** `function automatic type name(input port_type port, ...); return term; endfunction`: a constraint as a function of
 * its ports, each a [type, name] of the dialect's types. */
export function function_(name: string, ports: [string, string][], term: Term, type = "logic"): S.FunctionDeclaration {
  return new S.FunctionDeclaration({ lifetime: "automatic", type: keywordType(type), name: identifier(name),
    ports: ports.map(([t, n]) => new S.TfPort({ direction: "input", type: keywordType(t), name: identifier(n) })),
    body: [new S.ReturnStatement({ value: expression(term) })] });
}

/** `constraint name { term; }`: a `constraint` block, within which randomization generates values. */
export function constraint(name: string, term: Term): S.ConstraintDeclaration {
  return new S.ConstraintDeclaration({ name: identifier(name),
    items: [new S.ExpressionConstraint({ expression: expression(term) })] });
}

/** `assert (term) else $error("message");`: a constraint checked where the statement runs; without a message, the
 * simulator reports its failure. */
export function assertion(term: Term, message: string | null = null): S.ImmediateAssertion {
  const out = new S.ImmediateAssertion({ keyword: "assert", expression: expression(term) });
  if (message !== null) {
    out.fail_action = new S.ExpressionStatement({ expression: new S.SystemCall({ name: "$error",
      arguments: [constant(message)] }) });
  }
  return out;
}

/** A name, or a dotted name's members; `this` is the keyword. */
function name(dotted: string): S.Expression {
  const [first, ...rest] = dotted.split(".") as [string, ...string[]];
  let out: S.Expression = first === "this" ? new S.ThisExpression({})
    : new S.NameExpression({ name: identifier(first) });
  for (const member of rest) out = new S.MemberExpression({ value: out, member: identifier(member) });
  return out;
}

/** A built-in type of the dialect, by its keyword. */
function keywordType(keyword: string): S.DataType {
  if (VECTORS.includes(keyword)) return new S.IntegerVectorType({ keyword });
  if (ATOMS.includes(keyword)) return new S.IntegerAtomType({ keyword });
  return new S.NonIntegerType({ keyword }); // real, shortreal
}

/** What a cast names: a width, a signedness or a built-in type. */
function castType(term: Term): S.DataType | S.Expression {
  if (term.width !== null) return new S.IntegerLiteral({ spelling: String(term.width) });
  if (term.type === "signed" || term.type === "unsigned") return new S.ImplicitType({ signing: term.type });
  return keywordType(term.type);
}

/** The literal of a native value: a negation for a negative number, and `0.0 / 0.0` or `1.0 / 0.0` for a real that is
 * not finite. */
function constant(value: unknown): S.Expression {
  if (typeof value === "string") {
    const escapes: Record<string, string> = { "\\": "\\\\", "\"": "\\\"", "\n": "\\n", "\t": "\\t" };
    return new S.StringLiteral({ text: [...value].map((c) => escapes[c] ?? c).join("") });
  }
  if (typeof value === "number" && !Number.isFinite(value)) {
    const top = Number.isNaN(value) ? 0 : value > 0 ? 1 : -1;
    return new S.BinaryExpression({ left: constant(top), operator: "/", right: new S.RealLiteral({ spelling: "0.0" }) });
  }
  const text = typeof value === "number" ? Repr.repr(value) : String(value);
  if (text.startsWith("-")) return new S.UnaryExpression({ operator: "-", operand: constant(-(value as number)) });
  return typeof value === "number" ? new S.RealLiteral({ spelling: text }) : new S.IntegerLiteral({ spelling: text });
}

// --- From syntax nodes to terms ---

/** The term of the dialect that the SystemVerilog expression writes. */
export function term(node: SyntaxNode): Term {
  return new Reader(node).term(node);
}

/** The term a function returns: its body, but for comments, is one `return`. */
export function term_of_function(fn: S.FunctionDeclaration): Term {
  const reader = new Reader(fn);
  const statements = fn.body.filter((s) => !(s instanceof S.Comment));
  const only = statements[0];
  if (statements.length !== 1 || !(only instanceof S.ReturnStatement) || only.value === null) {
    throw new TranspileError("the function's body must be one return of a value", "");
  }
  return reader.term(only.value as SyntaxNode);
}

/** The term a constraint holds: its items, but for comments, are one expression, not `soft`. */
export function term_of_constraint(declaration: S.ConstraintDeclaration): Term {
  const reader = new Reader(declaration);
  const items = declaration.items.filter((i) => !(i instanceof S.Comment));
  const only = items[0];
  if (items.length !== 1 || !(only instanceof S.ExpressionConstraint) || only.soft) {
    throw new TranspileError("the constraint must hold one expression, not soft", "");
  }
  return reader.term(only.expression as SyntaxNode);
}

/** The term an immediate assertion checks. */
export function term_of_assertion(statement: S.ImmediateAssertion): Term {
  return new Reader(statement).term(statement.expression as SyntaxNode);
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
    while (node instanceof S.ParenthesizedExpression) node = node.expression as SyntaxNode;
    const attributes = (node as any).attributes as unknown[] | undefined;
    if (attributes !== undefined && attributes.length > 0) {
      throw this.error(node, "attributes have no counterpart in the SystemVerilog dialect");
    }
    if (node instanceof S.IntegerLiteral || node instanceof S.RealLiteral || node instanceof S.StringLiteral) {
      try {
        return decode(node);
      } catch (error) { // decode throws only ValueError
        throw this.error(node, (error as Error).message);
      }
    }
    if (node instanceof S.NameExpression && node.name instanceof S.Identifier) {
      return E.identifier(node.name.spelling as string);
    }
    if (node instanceof S.ThisExpression) return E.identifier("this"); // the object a constraint is about, as in a class's method
    if (node instanceof S.UnaryExpression) {
      this.operator(node, node.operator as string, Domains.UNARY);
      return E.unary(node.operator as string, this.term(node.operand as SyntaxNode));
    }
    if (node instanceof S.BinaryExpression) {
      this.operator(node, node.operator as string, Domains.BINARY);
      return E.binary(node.operator as string, this.term(node.left as SyntaxNode), this.term(node.right as SyntaxNode));
    }
    if (node instanceof S.ConditionalExpression) {
      return E.conditional(this.term(node.condition as SyntaxNode), this.term(node.consequence as SyntaxNode),
        this.term(node.alternative as SyntaxNode));
    }
    if (node instanceof S.Concatenation) return E.concatenation(...node.items.map((i) => this.term(i)));
    if (node instanceof S.Replication) {
      const items = node.items.map((i) => this.term(i));
      return E.replication(this.term(node.count as SyntaxNode), items.length === 1 ? items[0] : E.concatenation(...items));
    }
    if (node instanceof S.IndexExpression) {
      return E.select(this.term(node.value as SyntaxNode), this.term(node.index as SyntaxNode));
    }
    if (node instanceof S.RangeSelect) {
      if (node.operator !== ":") {
        throw this.error(node, `a part-select with ${node.operator} has no counterpart in the dialect`);
      }
      return E.range_(this.term(node.value as SyntaxNode), this.term(node.left as SyntaxNode),
        this.term(node.right as SyntaxNode));
    }
    if (node instanceof S.InsideExpression) {
      return E.inside(this.term(node.value as SyntaxNode), ...node.set.map((i) => this.item(i as SyntaxNode)));
    }
    if (node instanceof S.CastExpression) return E.cast(this.cast(node), this.term(node.value as SyntaxNode));
    if (node instanceof S.MemberExpression) {
      return E.member(this.term(node.value as SyntaxNode), (node.member as S.Identifier).spelling as string);
    }
    if (node instanceof S.SystemCall) {
      return E.call(node.name as string, ...node.arguments.map((a) => this.argument(a as SyntaxNode)));
    }
    if (node instanceof S.CallExpression) return this.call(node);
    if (node instanceof S.ArrayMethodWithExpression) return this.iteration(node);
    throw this.error(node, `${node.kind().KIND} has no counterpart in the SystemVerilog dialect`);
  }

  private operator(node: SyntaxNode, operator: string, vocabulary: ReadonlyMap<string, unknown>): void {
    if (!vocabulary.has(operator)) {
      throw this.error(node, `the operator '${operator}' has no counterpart in the SystemVerilog dialect`);
    }
  }

  /** An item of `inside`: a value, or a span `[low:high]`. */
  private item(node: SyntaxNode): Term {
    if (node instanceof S.ValueRange) {
      if (node.operator !== null) throw this.error(node, "a tolerance range has no counterpart in the dialect");
      return E.span(this.term(node.left as SyntaxNode), this.term(node.right as SyntaxNode));
    }
    return this.term(node);
  }

  /** What a cast names: a built-in type's keyword, a signedness (not `const`), or a width. */
  private cast(node: S.CastExpression): string | bigint {
    const kind = node.type as SyntaxNode;
    if (kind instanceof S.IntegerVectorType || kind instanceof S.IntegerAtomType || kind instanceof S.NonIntegerType) {
      const plain = kind instanceof S.NonIntegerType
        || (kind.signing === null && !(kind instanceof S.IntegerVectorType && kind.dimensions.length > 0));
      if (plain && E.CASTS.includes(kind.keyword as string)) return kind.keyword as string;
    }
    if (kind instanceof S.ImplicitType && (kind.signing === "signed" || kind.signing === "unsigned")
      && kind.dimensions.length === 0) {
      return kind.signing;
    }
    if (kind instanceof S.IntegerLiteral && /^[0-9]+$/.test(kind.spelling as string)) return BigInt(kind.spelling as string);
    throw this.error(kind, "a cast names a built-in type, a signedness or a width");
  }

  private argument(node: SyntaxNode): Term {
    if (node instanceof S.DataType || node instanceof S.EmptyArgument) throw this.error(node, "an argument is an expression");
    return this.term(node);
  }

  private call(node: S.CallExpression): Term {
    const callee = node.callee as SyntaxNode;
    if (callee instanceof S.MemberExpression && E.METHODS.includes((callee.member as S.Identifier).spelling as string)
      && node.arguments.length === 0) {
      return E.method(this.term(callee.value as SyntaxNode), (callee.member as S.Identifier).spelling as string);
    }
    return E.call(this.function(callee), ...node.arguments.map((a) => this.argument(a as SyntaxNode)));
  }

  /** `array.method(name) with (body)`, of a reduction. */
  private iteration(node: S.ArrayMethodWithExpression): Term {
    const call = node.call as SyntaxNode;
    const callee = call instanceof S.CallExpression ? call.callee as SyntaxNode : null;
    const args = call instanceof S.CallExpression ? call.arguments : [];
    const iterator = args[0];
    if (!(callee instanceof S.MemberExpression) || !E.REDUCTIONS.includes((callee.member as S.Identifier).spelling as string)
      || args.length !== 1 || !(iterator instanceof S.NameExpression) || !(iterator.name instanceof S.Identifier)) {
      throw this.error(node, `an iteration is a reduction (${E.REDUCTIONS.join(", ")}) of one iterator`);
    }
    return E.iterate(this.term(callee.value as SyntaxNode), (callee.member as S.Identifier).spelling as string,
      iterator.name.spelling as string, this.term(node.expression as SyntaxNode));
  }

  /** A function's name, or a dotted name's. */
  private function(node: SyntaxNode): string {
    if (node instanceof S.MemberExpression) {
      return `${this.function(node.value as SyntaxNode)}.${(node.member as S.Identifier).spelling}`;
    }
    if (node instanceof S.NameExpression && node.name instanceof S.Identifier) return node.name.spelling as string;
    if (node instanceof S.ThisExpression) return "this";
    throw this.error(node, "a function is called by its name");
  }
}

// --- SystemVerilog's literals ---

const DIGITS: Record<string, number> = { b: 1, o: 3, h: 4 };
const ESCAPES: Record<string, string> = { n: "\n", t: "\t", "\\": "\\", "\"": "\"", v: "\v", f: "\f", a: "\x07" };

/** The term of a literal: a constant, or a sized literal's vector; ValueError for one the dialect cannot hold. */
export function decode(literal: S.IntegerLiteral | S.RealLiteral | S.StringLiteral): Term {
  if (literal instanceof S.StringLiteral) return E.constant(unescape(literal.text as string));
  const spelling = (literal.spelling as string).replaceAll("_", "");
  if (literal instanceof S.RealLiteral) return E.constant(Number(spelling));
  if (!spelling.includes("'")) return E.constant(BigInt(spelling));
  const match = /^([0-9]+)'([sS]?)([bBoOdDhH])([0-9a-fA-FxXzZ?]+)$/.exec(spelling);
  if (match === null) throw new Errors.ValueError("an unsized based literal has no counterpart in the dialect");
  const [, sizeText, signed, baseText, digits] = match as unknown as [string, string, string, string, string];
  const size = Number(sizeText);
  const base = baseText.toLowerCase();
  const unknown = (d: string): string => d.toLowerCase().replace("?", "z");
  let bits: string;
  if (base === "d") {
    bits = "xz?".includes(digits.toLowerCase()) ? unknown(digits).repeat(size) : BigInt(digits).toString(2);
  } else {
    const width = DIGITS[base] as number;
    bits = [...digits].map((d) => ("xz?".includes(d.toLowerCase()) ? unknown(d).repeat(width)
      : parseInt(d, 16).toString(2).padStart(width, "0"))).join("");
  }
  const fill = "xz".includes(bits[0] as string) ? bits[0] as string : "0";
  bits = (fill.repeat(size) + bits).slice(-size); // extended or truncated to its size
  return E.vector(bits, signed ? true : null, base);
}

/** The characters a string literal writes, its escapes decoded (5.9.1). */
function unescape(text: string): string {
  let out = "";
  let i = 0;
  while (i < text.length) {
    const c = text[i] as string;
    if (c !== "\\" || i + 1 === text.length) {
      out += c;
      i += 1;
      continue;
    }
    const e = text[i + 1] as string;
    const hex = /^[0-9a-fA-F]{1,2}/.exec(text.slice(i + 2));
    if (e in ESCAPES) {
      out += ESCAPES[e];
      i += 2;
    } else if ("01234567".includes(e)) {
      const digits = (/^[0-7]{1,3}/.exec(text.slice(i + 1)) as RegExpExecArray)[0];
      out += String.fromCharCode(parseInt(digits, 8));
      i += 1 + digits.length;
    } else if (e === "x" && hex !== null) {
      out += String.fromCharCode(parseInt(hex[0], 16));
      i += 2 + hex[0].length;
    } else if (e === "\n") { // a line continued
      i += 2;
    } else { // an unknown escape is the character itself
      out += e;
      i += 2;
    }
  }
  return out;
}
