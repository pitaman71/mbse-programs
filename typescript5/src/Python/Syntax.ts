/**
 * Syntax: the abstract syntax of Python 3, as one tree language, organized as the language reference is.
 *
 * The kinds follow Python's own abstract syntax, the `ast` module, through Python 3.15: the same kinds with the same
 * names and fields where `ast` has them (capitalized where `ast`'s are lowercase: `Arg`, `Keyword`, `Alias`,
 * `WithItem`, `MatchCase`, `Comprehension`), with fields in source order. Each kind and feature records the version
 * that introduced it (`SINCE`, `FEATURES`), which `Python312`, `Python314` and other versions check.
 *
 * Where `ast` drops what a transpiler needs to see or a printer needs to write it back, the tree is concrete:
 *
 * - Names are nodes (`Identifier`) wherever `ast` has an identifier string, so one traversal finds every use and
 *   declaration of a name. A module's dotted name is a `DottedName`.
 * - Literals keep their spelling: `Constant.spelling` is the literal as written (`0x_FF`, `1e3j`, `rb'\d'`, a
 *   triple-quoted string with its newlines). f-strings and t-strings keep their prefix and quotes, the text between
 *   their replacement fields as written, and the text of each field's expression.
 * - Parentheses written around an expression stay, as `Parenthesized`; adjacent string literals stay, as
 *   `ConcatenatedString`. Printing adds the parentheses a hand-built tree needs.
 * - Comments are kept where statements are listed, as `Comment` statements; elsewhere they are dropped.
 * - Lists hold no empty places: a dict's `**mapping` is a `DictItem` without a key, a parameter's default is on its
 *   `Arg`, a comparison is a `Compare` of `Comparison`s, and `from m import *` imports an `Alias` without a name.
 *
 * Not represented: the expression context (`ctx`: load, store or delete), which follows from where an expression is;
 * `AnnAssign.simple`, which follows from its target; type comments, which are comments; and Python 2's syntax.
 */

import { Repr } from "@mbse/schemas/Framework";

import {
  article, type AttributeSpec, type Availability, type ChildSpec, choice, type Features, type Fields, flag, Language,
  many, Node, one, optional, optionalChoice, optionalInteger, optionalText, text,
} from "../Framework/Syntax.js";

const { repr } = Repr;

export const PY = "Python";

/** Python 3.`minor` on. Versions are numbered `100 * major + minor`: 3.12 is 312. */
export function py(minor: number): Availability {
  return { [PY]: 300 + minor };
}

/** Python's keywords, which are not identifiers; its soft keywords are. */
const KEYWORDS: readonly string[] = [
  "False", "None", "True", "and", "as", "assert", "async", "await", "break", "class", "continue", "def", "del",
  "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in", "is", "lambda", "nonlocal",
  "not", "or", "pass", "raise", "return", "try", "while", "with", "yield"
];

/** A problem if the list `field` of `node` is empty. */
function needs(node: Node, field: string, what: string): string[] {
  return (node.field(field) as unknown[]).length > 0 ? [] : [`${article(node.kind().KIND)} needs ${what}`];
}

/** Problems with the blocks in `fields` of `node`: the first must hold a statement other than a comment, and the
 * others, if they hold anything, too. */
function suite(node: Node, ...fields: string[]): string[] {
  const problems: string[] = [];
  fields.forEach((field, i) => {
    const body = node.field(field) as Node[];
    if ((i === 0 || body.length > 0) && body.every((s) => s instanceof Comment)) {
      problems.push(`${article(node.kind().KIND)} needs a statement in its ${field}`);
    }
  });
  return problems;
}

function prefixProblems(node: JoinedStr | TemplateStr, letter: string): string[] {
  const prefix: unknown = node.prefix;
  if (typeof prefix !== "string") return [];
  const sorted = [...prefix.toLowerCase()].sort().join("");
  if (sorted !== letter && sorted !== [letter, "r"].sort().join("")) {
    return [`${node.kind().KIND}.prefix cannot be ${repr(prefix)}`];
  }
  return [];
}

function unpacked(node: ListComp | SetComp | GeneratorExp): [string, Availability][] {
  return node.elt instanceof Starred ? [[`${node.kind().KIND} of unpacked elements`, py(15)]] : [];
}

function tryProblems(node: Try | TryStar): string[] {
  const problems = suite(node, "body", "orelse", "finalbody");
  if (node.handlers.length === 0 && node.finalbody.length === 0) {
    problems.push(`${article(node.kind().KIND)} needs a handler or a finalbody`);
  } else if (node.orelse.length > 0 && node.handlers.length === 0) {
    problems.push(`${article(node.kind().KIND)} with an orelse needs a handler`);
  }
  return problems;
}

/** PEP 614: before Python 3.9, a decorator is a dotted name, optionally called. */
function decorators(node: FunctionDef | AsyncFunctionDef | ClassDef): [string, Availability][] {
  const dotted = (e: unknown): boolean => e instanceof Name || (e instanceof Attribute && dotted(e.value));
  const relaxed = node.decorator_list.some((d) => !dotted(d instanceof Call ? d.func : d));
  return relaxed ? [[`${node.kind().KIND} with a decorator that is not a dotted name`, py(9)]] : [];
}

// --- Choices ---

export const BINARY_OPERATORS = ["+", "-", "*", "@", "/", "//", "%", "**", "<<", ">>", "|", "^", "&"] as const;
export type BinaryOperator = (typeof BINARY_OPERATORS)[number];
export const UNARY_OPERATORS = ["not", "-", "+", "~"] as const;
export type UnaryOperator = (typeof UNARY_OPERATORS)[number];
export const BOOLEAN_OPERATORS = ["and", "or"] as const;
export type BooleanOperator = (typeof BOOLEAN_OPERATORS)[number];
export const COMPARISON_OPERATORS = ["==", "!=", "<", "<=", ">", ">=", "is", "is not", "in", "not in"] as const;
export type ComparisonOperator = (typeof COMPARISON_OPERATORS)[number];
export const QUOTES = ["'", "\"", "'''", "\"\"\""] as const;
export type Quote = (typeof QUOTES)[number];
export const CONVERSIONS = ["s", "r", "a"] as const;
export type Conversion = (typeof CONVERSIONS)[number];
export const SINGLETONS = ["None", "True", "False"] as const;
export type Singleton = (typeof SINGLETONS)[number];
export const DELIMITERS = ["[]", "()"] as const;
export type Delimiter = (typeof DELIMITERS)[number];

// --- Categories ---

/** A statement (simple statements, §7; compound statements, §8), or a comment where statements are listed. */
export abstract class Statement extends Node {}

/** An expression (§6). */
export abstract class Expression extends Node {}

/** A pattern of a `case` clause (§8.6.4). */
export abstract class Pattern extends Node {}

/** A type parameter of a generic function, class or type alias (§8.11). */
export abstract class TypeParameter extends Node {}

// === Lexical analysis (§2) ===

const CommentSpec = {
  text: text(),
  trailing: flag(),
};
export interface Comment extends Fields<typeof CommentSpec> {}
/**
 * `# text`, where statements are listed. `text` excludes the `#`. A `trailing` comment ends the line of the
 * statement or clause header before it.
 */
export class Comment extends Statement {
  static override SPEC = CommentSpec;
}

const IdentifierSpec = {
  spelling: text(),
};
export interface Identifier extends Fields<typeof IdentifierSpec> {}
/**
 * An identifier (§2.3): a letter or `_`, then letters, digits and `_`, as Unicode defines them, other than a
 * keyword. Soft keywords (`match`, `case`, `type`, `_`, `lazy`) are identifiers.
 */
export class Identifier extends Node {
  static override SPEC = IdentifierSpec;
  override check(): string[] {
    const spelling = this.spelling;
    if (typeof spelling !== "string") return [];
    if (!/^[\p{XID_Start}_]\p{XID_Continue}*$/u.test(spelling)) return [`${repr(spelling)} is not an identifier`];
    if (KEYWORDS.includes(spelling)) return [`${repr(spelling)} is a keyword`];
    return [];
  }
}

const DottedNameSpec = {
  names: many(() => [Identifier]),
};
export interface DottedName extends Fields<typeof DottedNameSpec> {}
/** `name.name...`, a module's name in an import (§7.11). */
export class DottedName extends Node {
  static override SPEC = DottedNameSpec;
  override check(): string[] {
    return needs(this, "names", "a name");
  }
}

// === Expressions (§6) ===

// --- Atoms (§6.2) ---

const NameSpec = {
  id: one(() => [Identifier]),
};
export interface Name extends Fields<typeof NameSpec> {}
/** A name used as an expression (§6.2.1): read, assigned or deleted. */
export class Name extends Expression {
  static override SPEC = NameSpec;
}

const ConstantSpec = {
  spelling: text(),
};
export interface Constant extends Fields<typeof ConstantSpec> {}
/**
 * A literal (§2.6) as written: a number, a string or bytes literal with its prefix and quotes, `None`, `True`,
 * `False` or `...`.
 */
export class Constant extends Expression {
  static override SPEC = ConstantSpec;
}

const ConcatenatedStringSpec = {
  values: many(() => [Constant, JoinedStr, TemplateStr]),
};
export interface ConcatenatedString extends Fields<typeof ConcatenatedStringSpec> {}
/** Adjacent string literals, which make one string (§2.6.2): `'a' "b"`, `'a' f'{b}'`. */
export class ConcatenatedString extends Expression {
  static override SPEC = ConcatenatedStringSpec;
  override check(): string[] {
    return this.values.length > 1 ? [] : ["a ConcatenatedString needs two strings"];
  }
}

const StringTextSpec = {
  spelling: text(),
};
export interface StringText extends Fields<typeof StringTextSpec> {}
/**
 * Text of an f-string, a t-string or a format spec between replacement fields, as written: escapes and doubled
 * braces (`{{`) included.
 */
export class StringText extends Node {
  static override SPEC = StringTextSpec;
}

const FormatSpecSpec: {
  values: ChildSpec<StringText | FormattedValue, true, true>;
} = {
  values: many(() => [StringText, FormattedValue]),
};
export interface FormatSpec extends Fields<typeof FormatSpecSpec> {}
/** `:spec` after a replacement field's expression, which may hold replacement fields itself. */
export class FormatSpec extends Node {
  static override SPEC = FormatSpecSpec;
}

const FormattedValueSpec: {
  value: ChildSpec<Expression, false, false>;
  text: AttributeSpec<string, true>;
  debug: AttributeSpec<boolean, false>;
  conversion: AttributeSpec<Conversion, true>;
  format_spec: ChildSpec<FormatSpec, false, true>;
} = {
  value: one(() => [Expression]),
  text: optionalText(),
  debug: flag(),
  conversion: optionalChoice(...CONVERSIONS),
  format_spec: optional(() => [FormatSpec]),
};
export interface FormattedValue extends Fields<typeof FormattedValueSpec> {}
/**
 * `{value=!conversion:format_spec}` in an f-string (§2.6.3). `text` is the field as written from after `{` to
 * its conversion, format spec or `}`: the expression with its whitespace, and with `debug` (`{x = }`) the `=` and
 * the whitespace after it, which a self-documenting field writes into the string. Printing writes `text` while it
 * still spells `value`, and `value` otherwise.
 */
export class FormattedValue extends Node {
  static override SPEC = FormattedValueSpec;
  static override FEATURES: Features = { debug: [[true, py(8)]] };
}

const InterpolationSpec = {
  value: one(() => [Expression]),
  text: optionalText(),
  debug: flag(),
  conversion: optionalChoice(...CONVERSIONS),
  format_spec: optional(() => [FormatSpec]),
};
export interface Interpolation extends Fields<typeof InterpolationSpec> {}
/**
 * `{value=!conversion:format_spec}` in a t-string (§2.6.4), as `FormattedValue`; `text` is also what the
 * template records as the expression.
 */
export class Interpolation extends Node {
  static override SPEC = InterpolationSpec;
  static override SINCE: Availability | null = py(14);
}

const JoinedStrSpec = {
  prefix: text(),
  quote: choice(...QUOTES),
  values: many(() => [StringText, FormattedValue]),
};
export interface JoinedStr extends Fields<typeof JoinedStrSpec> {}
/**
 * An f-string (§2.6.3): `prefix` (`f`, `rf`, `Fr`, ...), then `quote`, the text and replacement fields, and the
 * quote again.
 */
export class JoinedStr extends Expression {
  static override SPEC = JoinedStrSpec;
  static override SINCE: Availability | null = py(6);
  override check(): string[] {
    return prefixProblems(this, "f");
  }
}

const TemplateStrSpec = {
  prefix: text(),
  quote: choice(...QUOTES),
  values: many(() => [StringText, Interpolation]),
};
export interface TemplateStr extends Fields<typeof TemplateStrSpec> {}
/** A t-string (§2.6.4), written as an f-string with `t` for `f`. */
export class TemplateStr extends Expression {
  static override SPEC = TemplateStrSpec;
  static override SINCE: Availability | null = py(14);
  override check(): string[] {
    return prefixProblems(this, "t");
  }
}

const ParenthesizedSpec = {
  value: one(() => [Expression]),
};
export interface Parenthesized extends Fields<typeof ParenthesizedSpec> {}
/** `(value)`: parentheses written in the source (§6.2.3). A parenthesized tuple is a `Parenthesized` `Tuple`. */
export class Parenthesized extends Expression {
  static override SPEC = ParenthesizedSpec;
}

const TupleSpec = {
  elts: many(() => [Expression]),
};
export interface Tuple extends Fields<typeof TupleSpec> {}
/** `elt, elt` (§6.15); `()` when empty. Parentheses written around it are a `Parenthesized`. */
export class Tuple extends Expression {
  static override SPEC = TupleSpec;
}

const ListSpec = {
  elts: many(() => [Expression]),
};
export interface List extends Fields<typeof ListSpec> {}
/** `[elt, elt]` (§6.2.5). */
export class List extends Expression {
  static override SPEC = ListSpec;
}

const SetSpec = {
  elts: many(() => [Expression]),
};
export interface Set extends Fields<typeof SetSpec> {}
/** `{elt, elt}` (§6.2.6). */
export class Set extends Expression {
  static override SPEC = SetSpec;
  override check(): string[] {
    return needs(this, "elts", "an element"); // `{}` is a dict
  }
}

const DictItemSpec = {
  key: optional(() => [Expression]),
  value: one(() => [Expression]),
};
export interface DictItem extends Fields<typeof DictItemSpec> {}
/** `key: value` in a dict display, or `**value` without a key. */
export class DictItem extends Node {
  static override SPEC = DictItemSpec;
}

const DictSpec = {
  items: many(() => [DictItem]),
};
export interface Dict extends Fields<typeof DictSpec> {}
/** `{key: value, **mapping}` (§6.2.7). */
export class Dict extends Expression {
  static override SPEC = DictSpec;
}

const ComprehensionSpec = {
  is_async: flag(),
  target: one(() => [Expression]),
  iter: one(() => [Expression]),
  ifs: many(() => [Expression]),
};
export interface Comprehension extends Fields<typeof ComprehensionSpec> {}
/** `for target in iter if condition...` in a comprehension, or `async for` with `is_async` (§6.2.4). */
export class Comprehension extends Node {
  static override SPEC = ComprehensionSpec;
  static override FEATURES: Features = { is_async: [[true, py(6)]] };
}

const ListCompSpec = {
  elt: one(() => [Expression]),
  generators: many(() => [Comprehension]),
};
export interface ListComp extends Fields<typeof ListCompSpec> {}
/** `[elt for ...]` (§6.2.4, §6.2.5); `[*elt for ...]` unpacks. */
export class ListComp extends Expression {
  static override SPEC = ListCompSpec;
  override check(): string[] {
    return needs(this, "generators", "a for clause");
  }

  override features(): [string, Availability][] {
    return unpacked(this);
  }
}

const SetCompSpec = {
  elt: one(() => [Expression]),
  generators: many(() => [Comprehension]),
};
export interface SetComp extends Fields<typeof SetCompSpec> {}
/** `{elt for ...}` (§6.2.4, §6.2.6). */
export class SetComp extends Expression {
  static override SPEC = SetCompSpec;
  override check(): string[] {
    return needs(this, "generators", "a for clause");
  }

  override features(): [string, Availability][] {
    return unpacked(this);
  }
}

const DictCompSpec = {
  key: one(() => [Expression]),
  value: optional(() => [Expression]),
  generators: many(() => [Comprehension]),
};
export interface DictComp extends Fields<typeof DictCompSpec> {}
/** `{key: value for ...}` (§6.2.4, §6.2.7); without `value`, `{**key for ...}`. */
export class DictComp extends Expression {
  static override SPEC = DictCompSpec;
  override check(): string[] {
    return needs(this, "generators", "a for clause");
  }

  override features(): [string, Availability][] {
    return this.value === null ? [["DictComp of unpacked mappings", py(15)]] : [];
  }
}

const GeneratorExpSpec = {
  elt: one(() => [Expression]),
  generators: many(() => [Comprehension]),
};
export interface GeneratorExp extends Fields<typeof GeneratorExpSpec> {}
/** `(elt for ...)` (§6.2.8); the parentheses are its own, and a call's sole argument shares the call's. */
export class GeneratorExp extends Expression {
  static override SPEC = GeneratorExpSpec;
  override check(): string[] {
    return needs(this, "generators", "a for clause");
  }

  override features(): [string, Availability][] {
    return unpacked(this);
  }
}

const YieldSpec = {
  value: optional(() => [Expression]),
};
export interface Yield extends Fields<typeof YieldSpec> {}
/** `yield value` (§6.2.9). */
export class Yield extends Expression {
  static override SPEC = YieldSpec;
}

const YieldFromSpec = {
  value: one(() => [Expression]),
};
export interface YieldFrom extends Fields<typeof YieldFromSpec> {}
/** `yield from value` (§6.2.9). */
export class YieldFrom extends Expression {
  static override SPEC = YieldFromSpec;
}

// --- Primaries (§6.3) ---

const AttributeSpec = {
  value: one(() => [Expression]),
  attr: one(() => [Identifier]),
};
export interface Attribute extends Fields<typeof AttributeSpec> {}
/** `value.attr` (§6.3.1). */
export class Attribute extends Expression {
  static override SPEC = AttributeSpec;
}

const SubscriptSpec = {
  value: one(() => [Expression]),
  slice: one(() => [Expression]),
};
export interface Subscript extends Fields<typeof SubscriptSpec> {}
/** `value[slice]` (§6.3.2); several indices are a `Tuple`. */
export class Subscript extends Expression {
  static override SPEC = SubscriptSpec;
  override features(): [string, Availability][] {
    const elts = this.slice instanceof Tuple ? this.slice.elts : [this.slice];
    return elts.some((e) => e instanceof Starred) ? [["Subscript with an unpacked index", py(11)]] : [];
  }
}

const SliceSpec = {
  lower: optional(() => [Expression]),
  upper: optional(() => [Expression]),
  step: optional(() => [Expression]),
};
export interface Slice extends Fields<typeof SliceSpec> {}
/** `lower:upper:step`, an index of a subscript (§6.3.3). */
export class Slice extends Expression {
  static override SPEC = SliceSpec;
}

const KeywordSpec = {
  arg: optional(() => [Identifier]),
  value: one(() => [Expression]),
};
export interface Keyword extends Fields<typeof KeywordSpec> {}
/** `arg=value` in a call or a class's bases, or `**value` without `arg` (§6.3.4). */
export class Keyword extends Node {
  static override SPEC = KeywordSpec;
}

const CallSpec = {
  func: one(() => [Expression]),
  args: many(() => [Expression]),
  keywords: many(() => [Keyword]),
};
export interface Call extends Fields<typeof CallSpec> {}
/**
 * `func(args, keywords)` (§6.3.4). As in `ast`, positional arguments (also `*iterable`) come before keyword
 * arguments (also `**mapping`), which is the order in which they are evaluated.
 */
export class Call extends Expression {
  static override SPEC = CallSpec;
}

const StarredSpec = {
  value: one(() => [Expression]),
};
export interface Starred extends Fields<typeof StarredSpec> {}
/** `*value`: unpacked in a display, a call, a subscript or an assignment target (§6.3.4, §7.2). */
export class Starred extends Expression {
  static override SPEC = StarredSpec;
}

const AwaitSpec = {
  value: one(() => [Expression]),
};
export interface Await extends Fields<typeof AwaitSpec> {}
/** `await value` (§6.4). */
export class Await extends Expression {
  static override SPEC = AwaitSpec;
  static override SINCE: Availability | null = py(5);
}

// --- Operators (§6.5–§6.13) ---

const UnaryOpSpec = {
  op: choice(...UNARY_OPERATORS),
  operand: one(() => [Expression]),
};
export interface UnaryOp extends Fields<typeof UnaryOpSpec> {}
/** `op operand`: `-x`, `+x`, `~x` (§6.6) or `not x` (§6.11). */
export class UnaryOp extends Expression {
  static override SPEC = UnaryOpSpec;
}

const BinOpSpec = {
  left: one(() => [Expression]),
  op: choice(...BINARY_OPERATORS),
  right: one(() => [Expression]),
};
export interface BinOp extends Fields<typeof BinOpSpec> {}
/** `left op right` (§6.5, §6.7–§6.9). */
export class BinOp extends Expression {
  static override SPEC = BinOpSpec;
  static override FEATURES: Features = { op: [["@", py(5)]] };
}

const ComparisonSpec = {
  op: choice(...COMPARISON_OPERATORS),
  comparator: one(() => [Expression]),
};
export interface Comparison extends Fields<typeof ComparisonSpec> {}
/** `op comparator`, one link of a comparison chain. */
export class Comparison extends Node {
  static override SPEC = ComparisonSpec;
}

const CompareSpec = {
  left: one(() => [Expression]),
  comparisons: many(() => [Comparison]),
};
export interface Compare extends Fields<typeof CompareSpec> {}
/** `left op comparator op comparator...` (§6.10). */
export class Compare extends Expression {
  static override SPEC = CompareSpec;
  override check(): string[] {
    return needs(this, "comparisons", "a comparison");
  }
}

const BoolOpSpec = {
  op: choice(...BOOLEAN_OPERATORS),
  values: many(() => [Expression]),
};
export interface BoolOp extends Fields<typeof BoolOpSpec> {}
/** `value and value...` or `value or value...` (§6.11). */
export class BoolOp extends Expression {
  static override SPEC = BoolOpSpec;
  override check(): string[] {
    return this.values.length > 1 ? [] : ["a BoolOp needs two values"];
  }
}

const NamedExprSpec = {
  target: one(() => [Name]),
  value: one(() => [Expression]),
};
export interface NamedExpr extends Fields<typeof NamedExprSpec> {}
/** `target := value` (§6.12). */
export class NamedExpr extends Expression {
  static override SPEC = NamedExprSpec;
  static override SINCE: Availability | null = py(8);
}

const IfExpSpec = {
  body: one(() => [Expression]),
  test: one(() => [Expression]),
  orelse: one(() => [Expression]),
};
export interface IfExp extends Fields<typeof IfExpSpec> {}
/** `body if test else orelse` (§6.13). */
export class IfExp extends Expression {
  static override SPEC = IfExpSpec;
}

const ArgSpec = {
  arg: one(() => [Identifier]),
  annotation: optional(() => [Expression]),
  default_value: optional(() => [Expression]),
};
export interface Arg extends Fields<typeof ArgSpec> {}
/** A parameter: `arg: annotation = default_value` (§8.7). A lambda's parameters have no annotations. */
export class Arg extends Node {
  static override SPEC = ArgSpec;
}

const ArgumentsSpec = {
  posonlyargs: many(() => [Arg]),
  args: many(() => [Arg]),
  vararg: optional(() => [Arg]),
  kwonlyargs: many(() => [Arg]),
  kwarg: optional(() => [Arg]),
};
export interface Arguments extends Fields<typeof ArgumentsSpec> {}
/**
 * A parameter list (§8.7): `posonlyargs, /, args, *vararg, kwonlyargs, **kwarg`. A bare `*` comes before
 * keyword-only parameters when there is no `vararg`.
 */
export class Arguments extends Node {
  static override SPEC = ArgumentsSpec;
  static override FEATURES: Features = { posonlyargs: [[true, py(8)]] };
}

const LambdaSpec = {
  args: one(() => [Arguments]),
  body: one(() => [Expression]),
};
export interface Lambda extends Fields<typeof LambdaSpec> {}
/** `lambda args: body` (§6.14). */
export class Lambda extends Expression {
  static override SPEC = LambdaSpec;
  override check(): string[] {
    const args = this.args;
    if (!(args instanceof Arguments)) return [];
    const parameters = [...args.posonlyargs, ...args.args, args.vararg, ...args.kwonlyargs, args.kwarg];
    const annotated = parameters.some((a) => a instanceof Arg && a.annotation !== null);
    return annotated ? ["a Lambda's parameters have no annotations"] : [];
  }
}

// === Simple statements (§7) ===

const ExprSpec = {
  value: one(() => [Expression]),
};
export interface Expr extends Fields<typeof ExprSpec> {}
/** An expression statement (§7.1). */
export class Expr extends Statement {
  static override SPEC = ExprSpec;
}

const AssignSpec = {
  targets: many(() => [Expression]),
  value: one(() => [Expression]),
};
export interface Assign extends Fields<typeof AssignSpec> {}
/** `target = target = value` (§7.2). */
export class Assign extends Statement {
  static override SPEC = AssignSpec;
  override check(): string[] {
    return needs(this, "targets", "a target");
  }
}

const AugAssignSpec = {
  target: one(() => [Expression]),
  op: choice(...BINARY_OPERATORS),
  value: one(() => [Expression]),
};
export interface AugAssign extends Fields<typeof AugAssignSpec> {}
/** `target op= value` (§7.2.1); `op` is the binary operator, as `+` for `+=`. */
export class AugAssign extends Statement {
  static override SPEC = AugAssignSpec;
  static override FEATURES: Features = { op: [["@", py(5)]] };
}

const AnnAssignSpec = {
  target: one(() => [Expression]),
  annotation: one(() => [Expression]),
  value: optional(() => [Expression]),
};
export interface AnnAssign extends Fields<typeof AnnAssignSpec> {}
/** `target: annotation = value` (§7.2.2). */
export class AnnAssign extends Statement {
  static override SPEC = AnnAssignSpec;
  static override SINCE: Availability | null = py(6);
}

const AssertSpec = {
  test: one(() => [Expression]),
  msg: optional(() => [Expression]),
};
export interface Assert extends Fields<typeof AssertSpec> {}
/** `assert test, msg` (§7.3). */
export class Assert extends Statement {
  static override SPEC = AssertSpec;
}

/** `pass` (§7.4). */
export class Pass extends Statement {}

const DeleteSpec = {
  targets: many(() => [Expression]),
};
export interface Delete extends Fields<typeof DeleteSpec> {}
/** `del target, target` (§7.5). */
export class Delete extends Statement {
  static override SPEC = DeleteSpec;
  override check(): string[] {
    return needs(this, "targets", "a target");
  }
}

const ReturnSpec = {
  value: optional(() => [Expression]),
};
export interface Return extends Fields<typeof ReturnSpec> {}
/** `return value` (§7.6). */
export class Return extends Statement {
  static override SPEC = ReturnSpec;
}

const RaiseSpec = {
  exc: optional(() => [Expression]),
  cause: optional(() => [Expression]),
};
export interface Raise extends Fields<typeof RaiseSpec> {}
/** `raise exc from cause` (§7.8). */
export class Raise extends Statement {
  static override SPEC = RaiseSpec;
  override check(): string[] {
    return this.cause !== null && this.exc === null ? ["a Raise with a cause needs an exc"] : [];
  }
}

/** `break` (§7.9). */
export class Break extends Statement {}

/** `continue` (§7.10). */
export class Continue extends Statement {}

const AliasSpec = {
  name: optional(() => [DottedName]),
  asname: optional(() => [Identifier]),
};
export interface Alias extends Fields<typeof AliasSpec> {}
/** `name as asname` in an import; without `name`, the `*` of `from module import *` (§7.11). */
export class Alias extends Node {
  static override SPEC = AliasSpec;
}

const ImportSpec = {
  is_lazy: flag(),
  names: many(() => [Alias]),
};
export interface Import extends Fields<typeof ImportSpec> {}
/** `import name as asname, ...`, or with `is_lazy` `lazy import ...` (§7.11). */
export class Import extends Statement {
  static override SPEC = ImportSpec;
  static override FEATURES: Features = { is_lazy: [[true, py(15)]] };
  override check(): string[] {
    return needs(this, "names", "a name");
  }
}

const ImportFromSpec = {
  is_lazy: flag(),
  level: optionalInteger(),
  module: optional(() => [DottedName]),
  names: many(() => [Alias]),
};
export interface ImportFrom extends Fields<typeof ImportFromSpec> {}
/**
 * `from module import names`, or with `is_lazy` `lazy from ...` (§7.11). `level` counts the dots of a relative
 * import (`from ..module`); None for an absolute one.
 */
export class ImportFrom extends Statement {
  static override SPEC = ImportFromSpec;
  static override FEATURES: Features = { is_lazy: [[true, py(15)]] };
  override check(): string[] {
    const problems = needs(this, "names", "a name");
    if (this.module === null && !this.level) problems.push("an ImportFrom needs a module or a level");
    return problems;
  }
}

const GlobalSpec = {
  names: many(() => [Identifier]),
};
export interface Global extends Fields<typeof GlobalSpec> {}
/** `global name, name` (§7.12). */
export class Global extends Statement {
  static override SPEC = GlobalSpec;
  override check(): string[] {
    return needs(this, "names", "a name");
  }
}

const NonlocalSpec = {
  names: many(() => [Identifier]),
};
export interface Nonlocal extends Fields<typeof NonlocalSpec> {}
/** `nonlocal name, name` (§7.13). */
export class Nonlocal extends Statement {
  static override SPEC = NonlocalSpec;
  override check(): string[] {
    return needs(this, "names", "a name");
  }
}

const TypeAliasSpec = {
  name: one(() => [Name]),
  type_params: many(() => [TypeParameter]),
  value: one(() => [Expression]),
};
export interface TypeAlias extends Fields<typeof TypeAliasSpec> {}
/** `type name[type_params] = value` (§7.14). */
export class TypeAlias extends Statement {
  static override SPEC = TypeAliasSpec;
  static override SINCE: Availability | null = py(12);
}

// === Compound statements (§8) ===

const IfSpec = {
  test: one(() => [Expression]),
  body: many(() => [Statement]),
  orelse: many(() => [Statement]),
};
export interface If extends Fields<typeof IfSpec> {}
/** `if test: body else: orelse` (§8.1). An `orelse` that is one `If` is printed as `elif`. */
export class If extends Statement {
  static override SPEC = IfSpec;
  override check(): string[] {
    return suite(this, "body", "orelse");
  }
}

const WhileSpec = {
  test: one(() => [Expression]),
  body: many(() => [Statement]),
  orelse: many(() => [Statement]),
};
export interface While extends Fields<typeof WhileSpec> {}
/** `while test: body else: orelse` (§8.2). */
export class While extends Statement {
  static override SPEC = WhileSpec;
  override check(): string[] {
    return suite(this, "body", "orelse");
  }
}

const ForSpec = {
  target: one(() => [Expression]),
  iter: one(() => [Expression]),
  body: many(() => [Statement]),
  orelse: many(() => [Statement]),
};
export interface For extends Fields<typeof ForSpec> {}
/** `for target in iter: body else: orelse` (§8.3). */
export class For extends Statement {
  static override SPEC = ForSpec;
  override check(): string[] {
    return suite(this, "body", "orelse");
  }
}

const AsyncForSpec = {
  target: one(() => [Expression]),
  iter: one(() => [Expression]),
  body: many(() => [Statement]),
  orelse: many(() => [Statement]),
};
export interface AsyncFor extends Fields<typeof AsyncForSpec> {}
/** `async for target in iter: body else: orelse` (§8.9.2). */
export class AsyncFor extends Statement {
  static override SPEC = AsyncForSpec;
  static override SINCE: Availability | null = py(5);
  override check(): string[] {
    return suite(this, "body", "orelse");
  }
}

const ExceptHandlerSpec = {
  type: optional(() => [Expression]),
  name: optional(() => [Identifier]),
  body: many(() => [Statement]),
};
export interface ExceptHandler extends Fields<typeof ExceptHandlerSpec> {}
/** `except type as name: body` (§8.4). Several types are a `Tuple`, unparenthesized since Python 3.14. */
export class ExceptHandler extends Node {
  static override SPEC = ExceptHandlerSpec;
  override check(): string[] {
    return suite(this, "body");
  }

  override features(): [string, Availability][] {
    return this.type instanceof Tuple ? [["ExceptHandler with unparenthesized types", py(14)]] : [];
  }
}

const TrySpec = {
  body: many(() => [Statement]),
  handlers: many(() => [ExceptHandler]),
  orelse: many(() => [Statement]),
  finalbody: many(() => [Statement]),
};
export interface Try extends Fields<typeof TrySpec> {}
/** `try: body except...: handlers else: orelse finally: finalbody` (§8.4). */
export class Try extends Statement {
  static override SPEC = TrySpec;
  override check(): string[] {
    return tryProblems(this);
  }
}

const TryStarSpec = {
  body: many(() => [Statement]),
  handlers: many(() => [ExceptHandler]),
  orelse: many(() => [Statement]),
  finalbody: many(() => [Statement]),
};
export interface TryStar extends Fields<typeof TryStarSpec> {}
/** `try` with `except*` handlers, which match exception groups (§8.4.2). */
export class TryStar extends Statement {
  static override SPEC = TryStarSpec;
  static override SINCE: Availability | null = py(11);
  override check(): string[] {
    return tryProblems(this);
  }
}

const WithItemSpec = {
  context_expr: one(() => [Expression]),
  optional_vars: optional(() => [Expression]),
};
export interface WithItem extends Fields<typeof WithItemSpec> {}
/** `context_expr as optional_vars` (§8.5). */
export class WithItem extends Node {
  static override SPEC = WithItemSpec;
}

const WithSpec = {
  items: many(() => [WithItem]),
  body: many(() => [Statement]),
};
export interface With extends Fields<typeof WithSpec> {}
/** `with items: body` (§8.5). */
export class With extends Statement {
  static override SPEC = WithSpec;
  override check(): string[] {
    return [...needs(this, "items", "an item"), ...suite(this, "body")];
  }
}

const AsyncWithSpec = {
  items: many(() => [WithItem]),
  body: many(() => [Statement]),
};
export interface AsyncWith extends Fields<typeof AsyncWithSpec> {}
/** `async with items: body` (§8.9.3). */
export class AsyncWith extends Statement {
  static override SPEC = AsyncWithSpec;
  static override SINCE: Availability | null = py(5);
  override check(): string[] {
    return [...needs(this, "items", "an item"), ...suite(this, "body")];
  }
}

const MatchCaseSpec = {
  pattern: one(() => [Pattern]),
  guard: optional(() => [Expression]),
  body: many(() => [Statement]),
};
export interface MatchCase extends Fields<typeof MatchCaseSpec> {}
/** `case pattern if guard: body` (§8.6). */
export class MatchCase extends Node {
  static override SPEC = MatchCaseSpec;
  static override SINCE: Availability | null = py(10);
  override check(): string[] {
    return suite(this, "body");
  }
}

const MatchSpec = {
  subject: one(() => [Expression]),
  cases: many(() => [MatchCase]),
};
export interface Match extends Fields<typeof MatchSpec> {}
/** `match subject: cases` (§8.6). */
export class Match extends Statement {
  static override SPEC = MatchSpec;
  static override SINCE: Availability | null = py(10);
  override check(): string[] {
    return needs(this, "cases", "a case");
  }
}

const FunctionDefSpec = {
  decorator_list: many(() => [Expression]),
  name: one(() => [Identifier]),
  type_params: many(() => [TypeParameter]),
  args: one(() => [Arguments]),
  returns: optional(() => [Expression]),
  body: many(() => [Statement]),
};
export interface FunctionDef extends Fields<typeof FunctionDefSpec> {}
/** `@decorator def name[type_params](args) -> returns: body` (§8.7). */
export class FunctionDef extends Statement {
  static override SPEC = FunctionDefSpec;
  static override FEATURES: Features = { type_params: [[true, py(12)]] };
  override check(): string[] {
    return suite(this, "body");
  }

  override features(): [string, Availability][] {
    return decorators(this);
  }
}

const AsyncFunctionDefSpec = {
  decorator_list: many(() => [Expression]),
  name: one(() => [Identifier]),
  type_params: many(() => [TypeParameter]),
  args: one(() => [Arguments]),
  returns: optional(() => [Expression]),
  body: many(() => [Statement]),
};
export interface AsyncFunctionDef extends Fields<typeof AsyncFunctionDefSpec> {}
/** `async def`, otherwise as `FunctionDef` (§8.9.1). */
export class AsyncFunctionDef extends Statement {
  static override SPEC = AsyncFunctionDefSpec;
  static override SINCE: Availability | null = py(5);
  static override FEATURES: Features = { type_params: [[true, py(12)]] };
  override check(): string[] {
    return suite(this, "body");
  }

  override features(): [string, Availability][] {
    return decorators(this);
  }
}

const ClassDefSpec = {
  decorator_list: many(() => [Expression]),
  name: one(() => [Identifier]),
  type_params: many(() => [TypeParameter]),
  bases: many(() => [Expression]),
  keywords: many(() => [Keyword]),
  body: many(() => [Statement]),
};
export interface ClassDef extends Fields<typeof ClassDefSpec> {}
/** `@decorator class name[type_params](bases, keywords): body` (§8.8). */
export class ClassDef extends Statement {
  static override SPEC = ClassDefSpec;
  static override FEATURES: Features = { type_params: [[true, py(12)]] };
  override check(): string[] {
    return suite(this, "body");
  }

  override features(): [string, Availability][] {
    return decorators(this);
  }
}

// --- Patterns (§8.6.4) ---

const MatchValueSpec = {
  value: one(() => [Expression]),
};
export interface MatchValue extends Fields<typeof MatchValueSpec> {}
/** A value pattern: a literal, or a dotted name (§8.6.4.3, §8.6.4.8). */
export class MatchValue extends Pattern {
  static override SPEC = MatchValueSpec;
  static override SINCE: Availability | null = py(10);
}

const MatchSingletonSpec = {
  value: choice(...SINGLETONS),
};
export interface MatchSingleton extends Fields<typeof MatchSingletonSpec> {}
/** `None`, `True` or `False`, compared by identity (§8.6.4.3). */
export class MatchSingleton extends Pattern {
  static override SPEC = MatchSingletonSpec;
  static override SINCE: Availability | null = py(10);
}

const MatchSequenceSpec = {
  delimiters: optionalChoice(...DELIMITERS),
  patterns: many(() => [Pattern]),
};
export interface MatchSequence extends Fields<typeof MatchSequenceSpec> {}
/** `[p, p]`, `(p, p)`, or `p, p` without `delimiters` (§8.6.4.9). */
export class MatchSequence extends Pattern {
  static override SPEC = MatchSequenceSpec;
  static override SINCE: Availability | null = py(10);
}

const MatchMappingSpec = {
  keys: many(() => [Expression]),
  patterns: many(() => [Pattern]),
  rest: optional(() => [Identifier]),
};
export interface MatchMapping extends Fields<typeof MatchMappingSpec> {}
/** `{key: pattern, **rest}` (§8.6.4.10); `keys` and `patterns` pair up. */
export class MatchMapping extends Pattern {
  static override SPEC = MatchMappingSpec;
  static override SINCE: Availability | null = py(10);
  override check(): string[] {
    return this.keys.length === this.patterns.length ? [] : ["a MatchMapping needs a pattern for each key"];
  }
}

const MatchClassSpec = {
  cls: one(() => [Expression]),
  patterns: many(() => [Pattern]),
  kwd_attrs: many(() => [Identifier]),
  kwd_patterns: many(() => [Pattern]),
};
export interface MatchClass extends Fields<typeof MatchClassSpec> {}
/** `cls(pattern, kwd_attr=kwd_pattern)` (§8.6.4.11); `kwd_attrs` and `kwd_patterns` pair up. */
export class MatchClass extends Pattern {
  static override SPEC = MatchClassSpec;
  static override SINCE: Availability | null = py(10);
  override check(): string[] {
    return this.kwd_attrs.length === this.kwd_patterns.length ? [] : ["a MatchClass needs a pattern for each keyword"];
  }
}

const MatchStarSpec = {
  name: optional(() => [Identifier]),
};
export interface MatchStar extends Fields<typeof MatchStarSpec> {}
/** `*name` in a sequence pattern, or `*_` without `name` (§8.6.4.9). */
export class MatchStar extends Pattern {
  static override SPEC = MatchStarSpec;
  static override SINCE: Availability | null = py(10);
}

const MatchAsSpec = {
  pattern: optional(() => [Pattern]),
  name: optional(() => [Identifier]),
};
export interface MatchAs extends Fields<typeof MatchAsSpec> {}
/** `pattern as name` (§8.6.4.5); a capture `name` without `pattern`; the wildcard `_` without either. */
export class MatchAs extends Pattern {
  static override SPEC = MatchAsSpec;
  static override SINCE: Availability | null = py(10);
}

const MatchOrSpec = {
  patterns: many(() => [Pattern]),
};
export interface MatchOr extends Fields<typeof MatchOrSpec> {}
/** `pattern | pattern` (§8.6.4.4). */
export class MatchOr extends Pattern {
  static override SPEC = MatchOrSpec;
  static override SINCE: Availability | null = py(10);
  override check(): string[] {
    return this.patterns.length > 1 ? [] : ["a MatchOr needs two patterns"];
  }
}

// --- Type parameters (§8.11) ---

const TypeVarSpec = {
  name: one(() => [Identifier]),
  bound: optional(() => [Expression]),
  default_value: optional(() => [Expression]),
};
export interface TypeVar extends Fields<typeof TypeVarSpec> {}
/** `name: bound = default_value` (§8.11.1). */
export class TypeVar extends TypeParameter {
  static override SPEC = TypeVarSpec;
  static override SINCE: Availability | null = py(12);
  static override FEATURES: Features = { default_value: [[true, py(13)]] };
}

const ParamSpecSpec = {
  name: one(() => [Identifier]),
  default_value: optional(() => [Expression]),
};
export interface ParamSpec extends Fields<typeof ParamSpecSpec> {}
/** `**name = default_value` (§8.11.1). */
export class ParamSpec extends TypeParameter {
  static override SPEC = ParamSpecSpec;
  static override SINCE: Availability | null = py(12);
  static override FEATURES: Features = { default_value: [[true, py(13)]] };
}

const TypeVarTupleSpec = {
  name: one(() => [Identifier]),
  default_value: optional(() => [Expression]),
};
export interface TypeVarTuple extends Fields<typeof TypeVarTupleSpec> {}
/** `*name = default_value` (§8.11.1). */
export class TypeVarTuple extends TypeParameter {
  static override SPEC = TypeVarTupleSpec;
  static override SINCE: Availability | null = py(12);
  static override FEATURES: Features = { default_value: [[true, py(13)]] };
}

// === Top-level components (§9) ===

const ModuleSpec = {
  body: many(() => [Statement]),
};
export interface Module extends Fields<typeof ModuleSpec> {}
/** A source file: its statements (§9.2). */
export class Module extends Node {
  static override SPEC = ModuleSpec;
}

// --- The language ---

export const KINDS: readonly (typeof Node)[] = [
  Comment, Identifier, DottedName, Name, Constant, ConcatenatedString, StringText, FormatSpec, FormattedValue,
  Interpolation, JoinedStr, TemplateStr, Parenthesized, Tuple, List, Set, DictItem, Dict, Comprehension, ListComp,
  SetComp, DictComp, GeneratorExp, Yield, YieldFrom, Attribute, Subscript, Slice, Keyword, Call, Starred, Await,
  UnaryOp, BinOp, Comparison, Compare, BoolOp, NamedExpr, IfExp, Arg, Arguments, Lambda, Expr, Assign, AugAssign,
  AnnAssign, Assert, Pass, Delete, Return, Raise, Break, Continue, Alias, Import, ImportFrom, Global, Nonlocal,
  TypeAlias, If, While, For, AsyncFor, ExceptHandler, Try, TryStar, WithItem, With, AsyncWith, MatchCase, Match,
  FunctionDef, AsyncFunctionDef, ClassDef, MatchValue, MatchSingleton, MatchSequence, MatchMapping, MatchClass,
  MatchStar, MatchAs, MatchOr, TypeVar, ParamSpec, TypeVarTuple, Module,
];

export const LANGUAGE = new Language("Python", KINDS, { base: py(0) });
