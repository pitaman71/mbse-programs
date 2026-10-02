/**
 * Syntax: the abstract syntax of C and C++, as one tree language (Ccpp), organized as the standard's grammar is.
 *
 * The kinds cover the union of C++26 and C23: every construct of either language is a tree of these kinds, and each
 * kind and feature records the standards that have it (`SINCE`, `FEATURES`), which `Ccpp17`, `Ccpp20` and later
 * standards check. Common GNU and Microsoft extensions that real code depends on are kinds too, marked `EXTENSION`.
 *
 * The tree is abstract where the grammar only spells and concrete where a transpiler needs to see what was written:
 *
 * - Precedence levels collapse: every binary operator is a `BinaryExpression`. Parentheses written in the source stay,
 *   as `ParenthesizedExpression`, and printing adds those a hand-built tree needs.
 * - Equivalent spellings are normalized: alternative tokens (`and`, `bitor`) and digraphs become the primary tokens,
 *   and `defined X` becomes `defined(X)`. Keywords with distinct spellings (`_Alignof`, `alignof`) keep them.
 * - Names are syntax nodes (category `Name`) wherever they occur, so one traversal finds every use and declaration of a
 *   name. Expressions refer to them through `IdExpression`, types through `NamedTypeSpecifier`, declarators through
 *   `IdDeclarator`.
 * - Specifiers stay in source order, one syntax node per keyword, as decl-specifier-seq lists them.
 * - Declarators nest inside out, as the grammar defines them: `int *a[3]` declares `a` with
 *   `ArrayDeclarator(declarator=PointerDeclarator(declarator=IdDeclarator(a)))`... read from the name outwards.
 * - Literals keep their spelling: digits, separators and suffixes for numbers, and the characters between the quotes,
 *   escapes included, for characters and strings.
 * - Comments are kept where declarations, statements, members and enumerators are listed; elsewhere they are dropped.
 *   Preprocessor directives are kept where they are listed too, with conditional branches as trees.
 *
 * Property names avoid both languages' reserved words: an `if` has a `consequence` and an `alternative`.
 */

import { Repr } from "@mbse/schemas/Framework";

import {
  type AttributeSpec, type Availability, type ChildSpec, choice, type Features, flag, Language, many, one, optional,
  optionalChoice, optionalText, type Properties, SyntaxNode, text,
} from "../Framework/Syntax.js";
import type * as Self from "./Syntax.js";

const { repr } = Repr;

export const CPP = "C++";
export const C = "C";

/** C++ from `year` on; not C. */
export function cpp(year: number): Availability {
  return { [CPP]: year };
}

/** C from `year` on; not C++. */
export function c(year: number): Availability {
  return { [C]: year };
}

/** C++ from `cppYear` on and C from `cYear` on; a [first, last] span for a feature a later standard removed. */
export function both(cppYear: number | readonly [number, number], cYear: number): Availability {
  return { [CPP]: cppYear, [C]: cYear };
}

// --- Choices ---

export const ENCODINGS = ["L", "u8", "u", "U"] as const;
export type Encoding = (typeof ENCODINGS)[number];
export const OVERLOADABLE_OPERATORS = [
  "new", "delete", "new[]", "delete[]", "co_await", "()", "[]", "->", "->*", "~", "!", "+", "-", "*", "/", "%", "^",
  "&", "|", "=", "+=", "-=", "*=", "/=", "%=", "^=", "&=", "|=", "==", "!=", "<", ">", "<=", ">=", "<=>", "&&", "||",
  "<<", ">>", "<<=", ">>=", "++", "--", ","
] as const;
export type OverloadableOperator = (typeof OVERLOADABLE_OPERATORS)[number];
export const UNARY_OPERATORS = ["+", "-", "!", "~", "*", "&", "++", "--"] as const;
export type UnaryOperator = (typeof UNARY_OPERATORS)[number];
export const POSTFIX_OPERATORS = ["++", "--"] as const;
export type PostfixOperator = (typeof POSTFIX_OPERATORS)[number];
export const BINARY_OPERATORS = [
  ".*", "->*", "*", "/", "%", "+", "-", "<<", ">>", "<=>", "<", ">", "<=", ">=", "==", "!=", "&", "^", "|", "&&",
  "||", ","
] as const;
export type BinaryOperator = (typeof BINARY_OPERATORS)[number];
export const ASSIGNMENT_OPERATORS = ["=", "*=", "/=", "%=", "+=", "-=", ">>=", "<<=", "&=", "^=", "|="] as const;
export type AssignmentOperator = (typeof ASSIGNMENT_OPERATORS)[number];
export const FOLD_OPERATORS = [
  "+", "-", "*", "/", "%", "^", "&", "|", "<<", ">>", "+=", "-=", "*=", "/=", "%=", "^=", "&=", "|=", "<<=", ">>=",
  "=", "==", "!=", "<", ">", "<=", ">=", "&&", "||", ",", ".*", "->*"
] as const;
export type FoldOperator = (typeof FOLD_OPERATORS)[number];
export const CAST_OPERATORS = ["static_cast", "dynamic_cast", "const_cast", "reinterpret_cast"] as const;
export type CastOperator = (typeof CAST_OPERATORS)[number];
export const ALIGNOF_KEYWORDS = ["alignof", "_Alignof", "__alignof__", "__alignof", "_alignof"] as const;
export type AlignofKeyword = (typeof ALIGNOF_KEYWORDS)[number];
export const DECL_KEYWORDS = [
  "static", "extern", "thread_local", "_Thread_local", "mutable", "register", "inline", "virtual", "_Noreturn",
  "friend", "typedef", "constexpr", "consteval", "constinit", "__inline", "__inline__", "__forceinline", "__thread",
  "__extension__", "noreturn"
] as const;
export type DeclKeyword = (typeof DECL_KEYWORDS)[number];
export const CV_KEYWORDS = [
  "const", "volatile", "restrict", "_Atomic", "__restrict", "__restrict__", "_Nonnull"
] as const;
export type CvKeyword = (typeof CV_KEYWORDS)[number];
export const PRIMITIVE_KEYWORDS = [
  "void", "char", "char8_t", "char16_t", "char32_t", "wchar_t", "bool", "_Bool", "short", "int", "long", "signed",
  "unsigned", "float", "double", "_Complex", "_Imaginary", "_Decimal32", "_Decimal64", "_Decimal128", "_Float16",
  "_Float32", "_Float64", "_Float128", "_Float32x", "_Float64x", "_Float128x", "__int128", "__float128"
] as const;
export type PrimitiveKeyword = (typeof PRIMITIVE_KEYWORDS)[number];
export const TYPEOF_KEYWORDS = ["typeof", "typeof_unqual", "__typeof__", "__typeof"] as const;
export type TypeofKeyword = (typeof TYPEOF_KEYWORDS)[number];
export const CLASS_KEYS = ["class", "struct", "union"] as const;
export type ClassKey = (typeof CLASS_KEYS)[number];
export const ENUM_KEYS = ["enum", "enum class", "enum struct"] as const;
export type EnumKey = (typeof ENUM_KEYS)[number];
export const ACCESSES = ["public", "protected", "private"] as const;
export type Access = (typeof ACCESSES)[number];
export const ASM_KEYWORDS = ["asm", "__asm__", "__asm"] as const;
export type AsmKeyword = (typeof ASM_KEYWORDS)[number];
export const INCLUDE_KEYWORDS = ["include", "include_next", "import"] as const;
export type IncludeKeyword = (typeof INCLUDE_KEYWORDS)[number];

// --- Categories ---

/** A name: what declarations declare and what expressions, types and declarators refer to ([expr.prim.id]). */
export abstract class Name extends SyntaxNode {}

/** An expression ([expr]); also a braced initializer list where one may stand for an expression. */
export abstract class Expression extends SyntaxNode {}

/** A literal ([lex.literal]). */
export abstract class Literal extends Expression {}

/**
 * A statement ([stmt]). Declarations are not statements here: blocks list them directly, and substatements may be
 * declarations, as C++'s declaration statements are.
 */
export abstract class Statement extends SyntaxNode {}

/** A declaration ([dcl]), a member declaration ([class.mem]) or a module declaration ([module]). */
export abstract class Declaration extends SyntaxNode {}

/** A decl-specifier or type-specifier ([dcl.spec]): one keyword, a type name, or a class or enum definition. */
export abstract class Specifier extends SyntaxNode {}

/** A declarator ([dcl.decl]), named or abstract: the part of a declaration that declares one name and its type. */
export abstract class Declarator extends SyntaxNode {}

/** A function parameter ([dcl.fct]), or the ellipsis of a variadic function. */
export abstract class Parameter extends SyntaxNode {}

/** A template parameter that is a type or a template ([temp.param]). Constants are `ParameterDeclaration`s. */
export abstract class TemplateParameter extends SyntaxNode {}

/** An initializer ([dcl.init]): `= value` or `(arguments)`; a braced list is an `InitializerList`. */
export abstract class Initializer extends SyntaxNode {}

/** A lambda capture ([expr.prim.lambda.capture]). */
export abstract class Capture extends SyntaxNode {}

/** A requirement in a requires-expression ([expr.prim.req]). */
export abstract class Requirement extends SyntaxNode {}

/** A designator in a designated initializer ([dcl.init.general], C [6.7.10]). */
export abstract class Designator extends SyntaxNode {}

/** An attribute specifier ([dcl.attr]): `[[...]]`, `alignas(...)`, or an extension's attribute syntax. */
export abstract class AttributeSpecifier extends SyntaxNode {}

/** An exception specification ([except.spec]): `noexcept(...)` or a dynamic `throw(...)`. */
export abstract class ExceptionSpecification extends SyntaxNode {}

/** A function contract specifier ([dcl.contract.func]): a precondition or a postcondition. */
export abstract class ContractSpecifier extends SyntaxNode {}

/** A preprocessing directive ([cpp]), where declarations, statements, members or enumerators are listed. */
export abstract class Directive extends SyntaxNode {}

// === Lexical conventions [lex] ===

const CommentSpec = {
  block: flag(),
  text: text(),
  trailing: flag(),
};
export interface Comment extends Properties<typeof CommentSpec> {}
/**
 * `// text` or, with `block`, `/* text *\/`. `text` excludes the delimiters. A `trailing` comment ends the line of
 * the item before it.
 */
export class Comment extends SyntaxNode {
  static override SPEC = CommentSpec;
}

// === Basics [basic] ===

const TranslationUnitSpec = {
  items: many(() => [Declaration, Statement, Directive, Comment]),
};
export interface TranslationUnit extends Properties<typeof TranslationUnitSpec> {}
/** A source file after its directives are kept as trees rather than performed ([basic.link]). */
export class TranslationUnit extends SyntaxNode {
  static override SPEC = TranslationUnitSpec;
}

// === Expressions [expr] ===

// --- Names [expr.prim.id], [over.oper], [class.conv.fct], [over.literal], [temp.names] ---

const IdentifierSpec = {
  spelling: text(),
};
export interface Identifier extends Properties<typeof IdentifierSpec> {}
/**
 * An identifier ([lex.name]): letters, digits, `_` and `$`, not starting with a digit. Characters beyond ASCII
 * are taken to be letters.
 */
export class Identifier extends Name {
  static override SPEC = IdentifierSpec;
  override check(): string[] {
    const spelling = this.spelling;
    if (typeof spelling !== "string" || spelling === "") return [];
    const points = [...spelling];
    if ("0123456789".includes(points[0] as string) || !points.every((ch) => ch.charCodeAt(0) > 0x7f || /[A-Za-z0-9_$]/.test(ch))) {
      return [`${repr(spelling)} is not an identifier`];
    }
    return [];
  }
}

const OperatorNameSpec = {
  operator: choice(...OVERLOADABLE_OPERATORS),
};
export interface OperatorName extends Properties<typeof OperatorNameSpec> {}
/** `operator op`, naming an operator function ([over.oper]). */
export class OperatorName extends Name {
  static override SPEC = OperatorNameSpec;
  static override SINCE: Availability | null = cpp(1998);
  static override FEATURES: Features = { operator: [["<=>", cpp(2020)], ["co_await", cpp(2020)]] };
}

const ConversionNameSpec = {
  type: one(() => [TypeId]),
};
export interface ConversionName extends Properties<typeof ConversionNameSpec> {}
/** `operator type`, naming a conversion function ([class.conv.fct]). */
export class ConversionName extends Name {
  static override SPEC = ConversionNameSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const LiteralOperatorNameSpec = {
  suffix: text(),
};
export interface LiteralOperatorName extends Properties<typeof LiteralOperatorNameSpec> {}
/** `operator""suffix`, naming a literal operator ([over.literal]). */
export class LiteralOperatorName extends Name {
  static override SPEC = LiteralOperatorNameSpec;
  static override SINCE: Availability | null = cpp(2011);
}

const DestructorNameSpec = {
  type: one(() => [Identifier, TemplateId, DecltypeSpecifier]),
};
export interface DestructorName extends Properties<typeof DestructorNameSpec> {}
/** `~type`, naming a destructor ([class.dtor]). */
export class DestructorName extends Name {
  static override SPEC = DestructorNameSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const TemplateIdSpec = {
  template_keyword: flag(),
  name: one(() => [Identifier, OperatorName, LiteralOperatorName]),
  arguments: many(() => [Expression, TypeId]),
};
export interface TemplateId extends Properties<typeof TemplateIdSpec> {}
/** `name<arguments>`, or `template name<arguments>` with `template_keyword` ([temp.names]). */
export class TemplateId extends Name {
  static override SPEC = TemplateIdSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const QualifiedNameSpec = {
  global_scope: flag(),
  qualifiers: many(() => [Identifier, TemplateId, DecltypeSpecifier, PackIndexingSpecifier, SpliceSpecifier]),
  name: one(() => [Name]),
};
export interface QualifiedName extends Properties<typeof QualifiedNameSpec> {}
/**
 * `q1::q2::name`, or `::q1::name` with `global_scope` ([expr.prim.id.qual]). Each qualifier names a namespace,
 * class or enumeration.
 */
export class QualifiedName extends Name {
  static override SPEC = QualifiedNameSpec;
  static override SINCE: Availability | null = cpp(1998);
}

// --- Literals [lex.literal] ---

const IntegerLiteralSpec = {
  spelling: text(),
};
export interface IntegerLiteral extends Properties<typeof IntegerLiteralSpec> {}
/** An integer literal, spelled as written: prefix, digits, separators and suffix ([lex.icon]). */
export class IntegerLiteral extends Literal {
  static override SPEC = IntegerLiteralSpec;
}

const FloatingLiteralSpec = {
  spelling: text(),
};
export interface FloatingLiteral extends Properties<typeof FloatingLiteralSpec> {}
/** A floating-point literal, spelled as written ([lex.fcon]). */
export class FloatingLiteral extends Literal {
  static override SPEC = FloatingLiteralSpec;
}

const CharacterLiteralSpec = {
  prefix: optionalChoice(...ENCODINGS),
  text: text(),
};
export interface CharacterLiteral extends Properties<typeof CharacterLiteralSpec> {}
/** `'text'`, with an optional encoding prefix ([lex.ccon]). `text` is spelled as written, escapes included. */
export class CharacterLiteral extends Literal {
  static override SPEC = CharacterLiteralSpec;
  static override FEATURES: Features = {
    prefix: [["u8", both(2017, 2023)], ["u", both(2011, 2011)], ["U", both(2011, 2011)]],
  };
}

const StringLiteralSpec = {
  prefix: optionalChoice(...ENCODINGS),
  text: text(),
};
export interface StringLiteral extends Properties<typeof StringLiteralSpec> {}
/** `"text"`, with an optional encoding prefix ([lex.string]). `text` is spelled as written, escapes included. */
export class StringLiteral extends Literal {
  static override SPEC = StringLiteralSpec;
  static override FEATURES: Features = {
    prefix: [["u8", both(2011, 2011)], ["u", both(2011, 2011)], ["U", both(2011, 2011)]],
  };
}

const RawStringLiteralSpec = {
  prefix: optionalChoice(...ENCODINGS),
  delimiter: optionalText(),
  text: text(),
};
export interface RawStringLiteral extends Properties<typeof RawStringLiteralSpec> {}
/** `R"delimiter(text)delimiter"`, with an optional encoding prefix ([lex.string]). */
export class RawStringLiteral extends Literal {
  static override SPEC = RawStringLiteralSpec;
  static override SINCE: Availability | null = cpp(2011);
}

const UserDefinedLiteralSpec = {
  literal: one(() => [IntegerLiteral, FloatingLiteral, CharacterLiteral, StringLiteral, RawStringLiteral]),
  suffix: text(),
};
export interface UserDefinedLiteral extends Properties<typeof UserDefinedLiteralSpec> {}
/** A literal followed by a user-defined suffix, such as `10_km` ([lex.ext]). */
export class UserDefinedLiteral extends Literal {
  static override SPEC = UserDefinedLiteralSpec;
  static override SINCE: Availability | null = cpp(2011);
}

const ConcatenatedStringSpec = {
  parts: many(() => [StringLiteral, RawStringLiteral, UserDefinedLiteral, IdExpression]),
};
export interface ConcatenatedString extends Properties<typeof ConcatenatedStringSpec> {}
/**
 * Adjacent string literals, concatenated ([lex.string]). Macros expanding to strings, such as `PRId64`, are
 * `IdExpression`s among them.
 */
export class ConcatenatedString extends Literal {
  static override SPEC = ConcatenatedStringSpec;
}

const BooleanLiteralSpec = {
  value: flag(),
};
export interface BooleanLiteral extends Properties<typeof BooleanLiteralSpec> {}
/** `true`, or `false` unless `value` ([lex.bool]). */
export class BooleanLiteral extends Literal {
  static override SPEC = BooleanLiteralSpec;
  static override SINCE: Availability | null = both(1998, 2023);
}

/** `nullptr` ([lex.nullptr]). */
export class NullptrLiteral extends Literal {
  static override SINCE: Availability | null = both(2011, 2023);
}

// --- Primary expressions [expr.prim] ---

/** `this` ([expr.prim.this]). */
export class ThisExpression extends Expression {
  static override SINCE: Availability | null = cpp(1998);
}

const ParenthesizedExpressionSpec = {
  expression: one(() => [Expression]),
};
export interface ParenthesizedExpression extends Properties<typeof ParenthesizedExpressionSpec> {}
/** `(expression)` ([expr.prim.paren]). */
export class ParenthesizedExpression extends Expression {
  static override SPEC = ParenthesizedExpressionSpec;
}

const IdExpressionSpec = {
  name: one(() => [Name]),
};
export interface IdExpression extends Properties<typeof IdExpressionSpec> {}
/** A name used as an expression ([expr.prim.id]). */
export class IdExpression extends Expression {
  static override SPEC = IdExpressionSpec;
}

const LambdaExpressionSpec = {
  captures: many(() => [Capture]),
  template_parameters: many(() => [TemplateParameter, Parameter]),
  template_requires: optional(() => [Expression]),
  attributes: many(() => [AttributeSpecifier]),
  declarator: optional(() => [LambdaDeclarator]),
  body: one(() => [CompoundStatement]),
};
export interface LambdaExpression extends Properties<typeof LambdaExpressionSpec> {}
/**
 * `[captures] <template_parameters> requires template_requires attributes declarator body`
 * ([expr.prim.lambda]). Without a declarator, the lambda has no parameter list: `[] { ... }`.
 */
export class LambdaExpression extends Expression {
  static override SPEC = LambdaExpressionSpec;
  static override SINCE: Availability | null = cpp(2011);
  static override FEATURES: Features = { template_parameters: [[true, cpp(2020)]], attributes: [[true, cpp(2023)]] };
}

const LambdaDeclaratorSpec = {
  parameters: many(() => [Parameter]),
  specifiers: many(() => [DeclSpecifier]),
  exception: optional(() => [ExceptionSpecification]),
  attributes: many(() => [AttributeSpecifier]),
  trailing_return: optional(() => [TypeId]),
  requires: optional(() => [Expression]),
  contracts: many(() => [ContractSpecifier]),
};
export interface LambdaDeclarator extends Properties<typeof LambdaDeclaratorSpec> {}
/** `(parameters) specifiers exception attributes -> trailing_return requires contracts` ([expr.prim.lambda]). */
export class LambdaDeclarator extends SyntaxNode {
  static override SPEC = LambdaDeclaratorSpec;
  static override SINCE: Availability | null = cpp(2011);
  static override FEATURES: Features = { requires: [[true, cpp(2020)]], contracts: [[true, cpp(2026)]] };
}

const DefaultCaptureSpec = {
  mode: choice("=", "&"),
};
export interface DefaultCapture extends Properties<typeof DefaultCaptureSpec> {}
/** `=` or `&`: capture what the body uses, by copy or by reference ([expr.prim.lambda.capture]). */
export class DefaultCapture extends Capture {
  static override SPEC = DefaultCaptureSpec;
  static override SINCE: Availability | null = cpp(2011);
}

const SimpleCaptureSpec = {
  by_reference: flag(),
  name: one(() => [Identifier]),
  pack: flag(),
};
export interface SimpleCapture extends Properties<typeof SimpleCaptureSpec> {}
/** `name`, `&name`, `name...` or `&name...` ([expr.prim.lambda.capture]). */
export class SimpleCapture extends Capture {
  static override SPEC = SimpleCaptureSpec;
  static override SINCE: Availability | null = cpp(2011);
}

const ThisCaptureSpec = {
  copy: flag(),
};
export interface ThisCapture extends Properties<typeof ThisCaptureSpec> {}
/** `this`, or `*this` with `copy` ([expr.prim.lambda.capture]). */
export class ThisCapture extends Capture {
  static override SPEC = ThisCaptureSpec;
  static override SINCE: Availability | null = cpp(2011);
  static override FEATURES: Features = { copy: [[true, cpp(2017)]] };
}

const InitCaptureSpec = {
  by_reference: flag(),
  pack: flag(),
  name: one(() => [Identifier]),
  initializer: one(() => [Initializer, InitializerList]),
};
export interface InitCapture extends Properties<typeof InitCaptureSpec> {}
/**
 * `name initializer`, `&name initializer`, `...name initializer` or `&...name initializer`
 * ([expr.prim.lambda.capture]).
 */
export class InitCapture extends Capture {
  static override SPEC = InitCaptureSpec;
  static override SINCE: Availability | null = cpp(2014);
  static override FEATURES: Features = { pack: [[true, cpp(2020)]] };
}

const FoldExpressionSpec = {
  left: optional(() => [Expression]),
  operator: choice(...FOLD_OPERATORS),
  right: optional(() => [Expression]),
};
export interface FoldExpression extends Properties<typeof FoldExpressionSpec> {}
/** `(left op ...)`, `(... op right)` or `(left op ... op right)` ([expr.prim.fold]). */
export class FoldExpression extends Expression {
  static override SPEC = FoldExpressionSpec;
  static override SINCE: Availability | null = cpp(2017);
}

const RequiresExpressionSpec = {
  parameters: many(() => [Parameter]),
  requirements: many(() => [Requirement]),
};
export interface RequiresExpression extends Properties<typeof RequiresExpressionSpec> {}
/** `requires (parameters) { requirements }` ([expr.prim.req]). Without parameters, `requires { ... }`. */
export class RequiresExpression extends Expression {
  static override SPEC = RequiresExpressionSpec;
  static override SINCE: Availability | null = cpp(2020);
}

const SimpleRequirementSpec = {
  expression: one(() => [Expression]),
};
export interface SimpleRequirement extends Properties<typeof SimpleRequirementSpec> {}
/** `expression;` ([expr.prim.req.simple]). */
export class SimpleRequirement extends Requirement {
  static override SPEC = SimpleRequirementSpec;
  static override SINCE: Availability | null = cpp(2020);
}

const TypeRequirementSpec = {
  name: one(() => [Name]),
};
export interface TypeRequirement extends Properties<typeof TypeRequirementSpec> {}
/** `typename name;` ([expr.prim.req.type]). */
export class TypeRequirement extends Requirement {
  static override SPEC = TypeRequirementSpec;
  static override SINCE: Availability | null = cpp(2020);
}

const CompoundRequirementSpec = {
  expression: one(() => [Expression]),
  noexcept: flag(),
  return_type: optional(() => [Name]),
};
export interface CompoundRequirement extends Properties<typeof CompoundRequirementSpec> {}
/** `{ expression } noexcept -> return_type;` ([expr.prim.req.compound]). `return_type` is a type constraint. */
export class CompoundRequirement extends Requirement {
  static override SPEC = CompoundRequirementSpec;
  static override SINCE: Availability | null = cpp(2020);
}

const NestedRequirementSpec = {
  constraint: one(() => [Expression]),
};
export interface NestedRequirement extends Properties<typeof NestedRequirementSpec> {}
/** `requires constraint;` ([expr.prim.req.nested]). */
export class NestedRequirement extends Requirement {
  static override SPEC = NestedRequirementSpec;
  static override SINCE: Availability | null = cpp(2020);
}

const PackIndexingExpressionSpec = {
  pack: one(() => [Name]),
  index: one(() => [Expression]),
};
export interface PackIndexingExpression extends Properties<typeof PackIndexingExpressionSpec> {}
/** `pack...[index]` ([expr.prim.pack.index]). */
export class PackIndexingExpression extends Expression {
  static override SPEC = PackIndexingExpressionSpec;
  static override SINCE: Availability | null = cpp(2026);
}

const ReflectExpressionSpec = {
  operand: optional(() => [Name, TypeId, Expression]),
};
export interface ReflectExpression extends Properties<typeof ReflectExpressionSpec> {}
/** `^^operand`, reflecting a name, type, namespace or expression; `^^::` without an operand ([expr.reflect]). */
export class ReflectExpression extends Expression {
  static override SPEC = ReflectExpressionSpec;
  static override SINCE: Availability | null = cpp(2026);
}

const SpliceExpressionSpec = {
  template_keyword: flag(),
  reflection: one(() => [Expression]),
  arguments: many(() => [Expression, TypeId]),
};
export interface SpliceExpression extends Properties<typeof SpliceExpressionSpec> {}
/** `[: reflection :]`, or `template [: reflection :] <arguments>` ([expr.prim.splice]). */
export class SpliceExpression extends Expression {
  static override SPEC = SpliceExpressionSpec;
  static override SINCE: Availability | null = cpp(2026);
}

// --- Postfix expressions [expr.post] ---

const SubscriptExpressionSpec = {
  object: one(() => [Expression]),
  indices: many(() => [Expression]),
};
export interface SubscriptExpression extends Properties<typeof SubscriptExpressionSpec> {}
/** `object[indices]` ([expr.sub]); several indices since C++23. */
export class SubscriptExpression extends Expression {
  static override SPEC = SubscriptExpressionSpec;
  override features(): [string, Availability][] {
    return this.indices.length > 1 ? [["SubscriptExpression with several indices", cpp(2023)]] : [];
  }
}

const CallExpressionSpec = {
  function: one(() => [Expression]),
  arguments: many(() => [Expression, TypeId]),
};
export interface CallExpression extends Properties<typeof CallExpressionSpec> {}
/** `function(arguments)` ([expr.call]). A macro's arguments may be types, as in `offsetof(S, m)`. */
export class CallExpression extends Expression {
  static override SPEC = CallExpressionSpec;
}

const FunctionalCastExpressionSpec = {
  type: one(() => [Specifier]),
  initializer: one(() => [ParenthesizedInitializer, InitializerList]),
};
export interface FunctionalCastExpression extends Properties<typeof FunctionalCastExpressionSpec> {}
/** `type(arguments)` or `type{items}`: explicit type conversion in functional notation ([expr.type.conv]). */
export class FunctionalCastExpression extends Expression {
  static override SPEC = FunctionalCastExpressionSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const MemberExpressionSpec = {
  object: one(() => [Expression]),
  operator: choice(".", "->"),
  template_keyword: flag(),
  member: one(() => [Name]),
};
export interface MemberExpression extends Properties<typeof MemberExpressionSpec> {}
/** `object.member` or `object->member`, with `template_keyword` `object.template member` ([expr.ref]). */
export class MemberExpression extends Expression {
  static override SPEC = MemberExpressionSpec;
}

const PostfixExpressionSpec = {
  operand: one(() => [Expression]),
  operator: choice(...POSTFIX_OPERATORS),
};
export interface PostfixExpression extends Properties<typeof PostfixExpressionSpec> {}
/** `operand++` or `operand--` ([expr.post.incr]). */
export class PostfixExpression extends Expression {
  static override SPEC = PostfixExpressionSpec;
}

const NamedCastExpressionSpec = {
  operator: choice(...CAST_OPERATORS),
  type: one(() => [TypeId]),
  operand: one(() => [Expression]),
};
export interface NamedCastExpression extends Properties<typeof NamedCastExpressionSpec> {}
/** `static_cast<type>(operand)` and its siblings ([expr.static.cast] and following). */
export class NamedCastExpression extends Expression {
  static override SPEC = NamedCastExpressionSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const TypeidExpressionSpec = {
  operand: one(() => [Expression, TypeId]),
};
export interface TypeidExpression extends Properties<typeof TypeidExpressionSpec> {}
/** `typeid(operand)` ([expr.typeid]). */
export class TypeidExpression extends Expression {
  static override SPEC = TypeidExpressionSpec;
  static override SINCE: Availability | null = cpp(1998);
}

// --- Unary expressions [expr.unary] ---

const UnaryExpressionSpec = {
  operator: choice(...UNARY_OPERATORS),
  operand: one(() => [Expression]),
};
export interface UnaryExpression extends Properties<typeof UnaryExpressionSpec> {}
/** `op operand` for the prefix operators ([expr.unary.op], [expr.pre.incr]). */
export class UnaryExpression extends Expression {
  static override SPEC = UnaryExpressionSpec;
}

const AwaitExpressionSpec = {
  operand: one(() => [Expression]),
};
export interface AwaitExpression extends Properties<typeof AwaitExpressionSpec> {}
/** `co_await operand` ([expr.await]). */
export class AwaitExpression extends Expression {
  static override SPEC = AwaitExpressionSpec;
  static override SINCE: Availability | null = cpp(2020);
}

const SizeofExpressionSpec = {
  operand: one(() => [Expression, TypeId]),
};
export interface SizeofExpression extends Properties<typeof SizeofExpressionSpec> {}
/** `sizeof operand` or `sizeof(type)` ([expr.sizeof]). */
export class SizeofExpression extends Expression {
  static override SPEC = SizeofExpressionSpec;
}

const SizeofPackExpressionSpec = {
  pack: one(() => [Identifier]),
};
export interface SizeofPackExpression extends Properties<typeof SizeofPackExpressionSpec> {}
/** `sizeof...(pack)` ([expr.sizeof]). */
export class SizeofPackExpression extends Expression {
  static override SPEC = SizeofPackExpressionSpec;
  static override SINCE: Availability | null = cpp(2011);
}

const AlignofExpressionSpec = {
  keyword: choice(...ALIGNOF_KEYWORDS),
  operand: one(() => [TypeId, Expression]),
};
export interface AlignofExpression extends Properties<typeof AlignofExpressionSpec> {}
/** `alignof(operand)`, or one of its other spellings ([expr.alignof], C [6.5.4.5]). */
export class AlignofExpression extends Expression {
  static override SPEC = AlignofExpressionSpec;
  static override SINCE: Availability | null = both(2011, 2011);
  static override FEATURES: Features = { keyword: [["alignof", both(2011, 2023)], ["_Alignof", c(2011)]] };
}

const NoexceptExpressionSpec = {
  operand: one(() => [Expression]),
};
export interface NoexceptExpression extends Properties<typeof NoexceptExpressionSpec> {}
/** `noexcept(operand)` ([expr.unary.noexcept]). */
export class NoexceptExpression extends Expression {
  static override SPEC = NoexceptExpressionSpec;
  static override SINCE: Availability | null = cpp(2011);
}

const NewExpressionSpec = {
  global_scope: flag(),
  placement: many(() => [Expression]),
  parenthesized_type: flag(),
  type: one(() => [TypeId]),
  initializer: optional(() => [ParenthesizedInitializer, InitializerList]),
};
export interface NewExpression extends Properties<typeof NewExpressionSpec> {}
/** `::new (placement) type initializer` ([expr.new]); with `parenthesized_type`, `new (type)`. */
export class NewExpression extends Expression {
  static override SPEC = NewExpressionSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const DeleteExpressionSpec = {
  global_scope: flag(),
  array: flag(),
  operand: one(() => [Expression]),
};
export interface DeleteExpression extends Properties<typeof DeleteExpressionSpec> {}
/** `::delete operand` or `::delete[] operand` ([expr.delete]). */
export class DeleteExpression extends Expression {
  static override SPEC = DeleteExpressionSpec;
  static override SINCE: Availability | null = cpp(1998);
}

// --- Other expressions [expr.cast] to [expr.comma] ---

const CastExpressionSpec = {
  type: one(() => [TypeId]),
  operand: one(() => [Expression]),
};
export interface CastExpression extends Properties<typeof CastExpressionSpec> {}
/** `(type) operand` ([expr.cast]). */
export class CastExpression extends Expression {
  static override SPEC = CastExpressionSpec;
}

const BinaryExpressionSpec = {
  left: one(() => [Expression]),
  operator: choice(...BINARY_OPERATORS),
  right: one(() => [Expression]),
};
export interface BinaryExpression extends Properties<typeof BinaryExpressionSpec> {}
/** `left op right` for every binary operator but assignment ([expr.mptr.oper] to [expr.comma]). */
export class BinaryExpression extends Expression {
  static override SPEC = BinaryExpressionSpec;
  static override FEATURES: Features = { operator: [["<=>", cpp(2020)], [".*", cpp(1998)], ["->*", cpp(1998)]] };
}

const ConditionalExpressionSpec = {
  condition: one(() => [Expression]),
  consequence: optional(() => [Expression]),
  alternative: one(() => [Expression]),
};
export interface ConditionalExpression extends Properties<typeof ConditionalExpressionSpec> {}
/** `condition ? consequence : alternative` ([expr.cond]); without a consequence, the GNU `condition ?: alternative`. */
export class ConditionalExpression extends Expression {
  static override SPEC = ConditionalExpressionSpec;
}

const AssignmentExpressionSpec = {
  left: one(() => [Expression]),
  operator: choice(...ASSIGNMENT_OPERATORS),
  right: one(() => [Expression]),
};
export interface AssignmentExpression extends Properties<typeof AssignmentExpressionSpec> {}
/** `left op right` for the assignment operators ([expr.assign]). */
export class AssignmentExpression extends Expression {
  static override SPEC = AssignmentExpressionSpec;
}

const ThrowExpressionSpec = {
  operand: optional(() => [Expression]),
};
export interface ThrowExpression extends Properties<typeof ThrowExpressionSpec> {}
/** `throw operand`, or `throw` to rethrow ([expr.throw]). */
export class ThrowExpression extends Expression {
  static override SPEC = ThrowExpressionSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const YieldExpressionSpec = {
  operand: one(() => [Expression]),
};
export interface YieldExpression extends Properties<typeof YieldExpressionSpec> {}
/** `co_yield operand` ([expr.yield]). */
export class YieldExpression extends Expression {
  static override SPEC = YieldExpressionSpec;
  static override SINCE: Availability | null = cpp(2020);
}

const PackExpansionSpec = {
  pattern: one(() => [Expression, TypeId]),
};
export interface PackExpansion extends Properties<typeof PackExpansionSpec> {}
/** `pattern...`, expanding a pack in a list of expressions or types ([temp.variadic]). */
export class PackExpansion extends Expression {
  static override SPEC = PackExpansionSpec;
  static override SINCE: Availability | null = cpp(2011);
}

const InitializerListSpec: {
  items: ChildSpec<Expression | DesignatedInitializer, true, true>;
  trailing_comma: AttributeSpec<boolean, false>;
} = {
  items: many(() => [Expression, DesignatedInitializer]),
  trailing_comma: flag(),
};
export interface InitializerList extends Properties<typeof InitializerListSpec> {}
/** `{items}`, with `trailing_comma` `{items,}` ([dcl.init.list]). */
export class InitializerList extends Expression {
  static override SPEC = InitializerListSpec;
}

const DesignatedInitializerSpec: {
  designators: ChildSpec<Designator, true, true>;
  initializer: ChildSpec<EqualInitializer | InitializerList, false, false>;
} = {
  designators: many(() => [Designator]),
  initializer: one(() => [EqualInitializer, InitializerList]),
};
export interface DesignatedInitializer extends Properties<typeof DesignatedInitializerSpec> {}
/** `designators initializer`, such as `.x = 1`, `.x{1}` or C's `[2].y = 3` ([dcl.init.general], C [6.7.10]). */
export class DesignatedInitializer extends SyntaxNode {
  static override SPEC = DesignatedInitializerSpec;
  static override SINCE: Availability | null = both(2020, 1999);
  override features(): [string, Availability][] {
    const nested = this.designators.length > 1 || this.designators.some((d) => !(d instanceof FieldDesignator));
    return nested ? [["DesignatedInitializer with array or nested designators", c(1999)]] : [];
  }
}

const FieldDesignatorSpec = {
  name: one(() => [Identifier]),
};
export interface FieldDesignator extends Properties<typeof FieldDesignatorSpec> {}
/** `.name`. */
export class FieldDesignator extends Designator {
  static override SPEC = FieldDesignatorSpec;
}

const IndexDesignatorSpec = {
  index: one(() => [Expression]),
  last: optional(() => [Expression]),
};
export interface IndexDesignator extends Properties<typeof IndexDesignatorSpec> {}
/** `[index]`, or the GNU `[index ... last]`. */
export class IndexDesignator extends Designator {
  static override SPEC = IndexDesignatorSpec;
  static override SINCE: Availability | null = c(1999);
}

const CompoundLiteralExpressionSpec = {
  type: one(() => [TypeId]),
  initializer: one(() => [InitializerList]),
};
export interface CompoundLiteralExpression extends Properties<typeof CompoundLiteralExpressionSpec> {}
/** `(type){items}`: an unnamed object (C [6.5.3.6]). */
export class CompoundLiteralExpression extends Expression {
  static override SPEC = CompoundLiteralExpressionSpec;
  static override SINCE: Availability | null = c(1999);
}

const GenericSelectionSpec = {
  controlling: one(() => [Expression, TypeId]),
  associations: many(() => [GenericAssociation]),
};
export interface GenericSelection extends Properties<typeof GenericSelectionSpec> {}
/** `_Generic(controlling, associations)` (C [6.5.2.1]). */
export class GenericSelection extends Expression {
  static override SPEC = GenericSelectionSpec;
  static override SINCE: Availability | null = c(2011);
}

const GenericAssociationSpec = {
  type: optional(() => [TypeId]),
  value: one(() => [Expression]),
};
export interface GenericAssociation extends Properties<typeof GenericAssociationSpec> {}
/** `type: value`, or `default: value` without a type (C [6.5.2.1]). */
export class GenericAssociation extends SyntaxNode {
  static override SPEC = GenericAssociationSpec;
  static override SINCE: Availability | null = c(2011);
}

const StatementExpressionSpec = {
  body: one(() => [CompoundStatement]),
};
export interface StatementExpression extends Properties<typeof StatementExpressionSpec> {}
/** `({ items })`, a GNU statement expression whose value is its last statement's. */
export class StatementExpression extends Expression {
  static override SPEC = StatementExpressionSpec;
  static override EXTENSION = true;
}

const ExtensionExpressionSpec = {
  operand: one(() => [Expression]),
};
export interface ExtensionExpression extends Properties<typeof ExtensionExpressionSpec> {}
/** `__extension__ operand`, a GNU marker silencing warnings about extensions. */
export class ExtensionExpression extends Expression {
  static override SPEC = ExtensionExpressionSpec;
  static override EXTENSION = true;
}

const DefinedExpressionSpec = {
  name: one(() => [Identifier]),
};
export interface DefinedExpression extends Properties<typeof DefinedExpressionSpec> {}
/** `defined(name)`, in a preprocessing condition ([cpp.cond]). */
export class DefinedExpression extends Expression {
  static override SPEC = DefinedExpressionSpec;
}

// === Statements [stmt] ===

const LabeledStatementSpec = {
  label: one(() => [Identifier]),
  statement: optional(() => [Statement, Declaration]),
};
export interface LabeledStatement extends Properties<typeof LabeledStatementSpec> {}
/** `label: statement` ([stmt.label]); without a statement, a label ending a block (C++23, C23). */
export class LabeledStatement extends Statement {
  static override SPEC = LabeledStatementSpec;
  override features(): [string, Availability][] {
    return this.statement === null ? [["LabeledStatement without a statement", both(2023, 2023)]] : [];
  }
}

const CaseStatementSpec = {
  value: one(() => [Expression]),
  last: optional(() => [Expression]),
  statement: optional(() => [Statement, Declaration]),
};
export interface CaseStatement extends Properties<typeof CaseStatementSpec> {}
/** `case value: statement`, or the GNU range `case value ... last: statement` ([stmt.label]). */
export class CaseStatement extends Statement {
  static override SPEC = CaseStatementSpec;
  override features(): [string, Availability][] {
    return this.statement === null ? [["CaseStatement without a statement", both(2023, 2023)]] : [];
  }
}

const DefaultStatementSpec = {
  statement: optional(() => [Statement, Declaration]),
};
export interface DefaultStatement extends Properties<typeof DefaultStatementSpec> {}
/** `default: statement` ([stmt.label]). */
export class DefaultStatement extends Statement {
  static override SPEC = DefaultStatementSpec;
  override features(): [string, Availability][] {
    return this.statement === null ? [["DefaultStatement without a statement", both(2023, 2023)]] : [];
  }
}

const ExpressionStatementSpec = {
  expression: optional(() => [Expression]),
};
export interface ExpressionStatement extends Properties<typeof ExpressionStatementSpec> {}
/** `expression;`, or `;` without an expression ([stmt.expr]). */
export class ExpressionStatement extends Statement {
  static override SPEC = ExpressionStatementSpec;
}

const CompoundStatementSpec = {
  items: many(() => [Statement, Declaration, Directive, Comment]),
};
export interface CompoundStatement extends Properties<typeof CompoundStatementSpec> {}
/** `{ items }` ([stmt.block]). */
export class CompoundStatement extends Statement {
  static override SPEC = CompoundStatementSpec;
}

const IfStatementSpec = {
  constexpr: flag(),
  consteval: flag(),
  negated: flag(),
  initializer: optional(() => [Statement, Declaration]),
  condition: optional(() => [Expression, Declaration]),
  consequence: one(() => [Statement, Declaration]),
  alternative: optional(() => [Statement, Declaration]),
};
export interface IfStatement extends Properties<typeof IfStatementSpec> {}
/**
 * `if constexpr (initializer condition) consequence else alternative` ([stmt.if]), or `if !consteval
 * consequence else alternative` with `consteval` (and `negated`), which has no condition.
 */
export class IfStatement extends Statement {
  static override SPEC = IfStatementSpec;
  static override FEATURES: Features = {
    constexpr: [[true, cpp(2017)]],
    consteval: [[true, cpp(2023)]],
    initializer: [[true, cpp(2017)]],
  };
}

const SwitchStatementSpec = {
  initializer: optional(() => [Statement, Declaration]),
  condition: one(() => [Expression, Declaration]),
  body: one(() => [Statement, Declaration]),
};
export interface SwitchStatement extends Properties<typeof SwitchStatementSpec> {}
/** `switch (initializer condition) body` ([stmt.switch]). */
export class SwitchStatement extends Statement {
  static override SPEC = SwitchStatementSpec;
  static override FEATURES: Features = { initializer: [[true, cpp(2017)]] };
}

const WhileStatementSpec = {
  condition: one(() => [Expression, Declaration]),
  body: one(() => [Statement, Declaration]),
};
export interface WhileStatement extends Properties<typeof WhileStatementSpec> {}
/** `while (condition) body` ([stmt.while]). */
export class WhileStatement extends Statement {
  static override SPEC = WhileStatementSpec;
}

const DoStatementSpec = {
  body: one(() => [Statement, Declaration]),
  condition: one(() => [Expression]),
};
export interface DoStatement extends Properties<typeof DoStatementSpec> {}
/** `do body while (condition);` ([stmt.do]). */
export class DoStatement extends Statement {
  static override SPEC = DoStatementSpec;
}

const ForStatementSpec = {
  initializer: optional(() => [Statement, Declaration]),
  condition: optional(() => [Expression, Declaration]),
  increment: optional(() => [Expression]),
  body: one(() => [Statement, Declaration]),
};
export interface ForStatement extends Properties<typeof ForStatementSpec> {}
/**
 * `for (initializer condition; increment) body` ([stmt.for]). The initializer ends with its own `;`; without
 * one, the statement is `for (; condition; increment)`.
 */
export class ForStatement extends Statement {
  static override SPEC = ForStatementSpec;
}

const RangeForStatementSpec = {
  template_keyword: flag(),
  initializer: optional(() => [Statement, Declaration]),
  declaration: one(() => [Declaration]),
  range: one(() => [Expression]),
  body: one(() => [Statement, Declaration]),
};
export interface RangeForStatement extends Properties<typeof RangeForStatementSpec> {}
/**
 * `for (initializer declaration : range) body` ([stmt.ranged]), or with `template_keyword` the expansion
 * statement `template for (...)` ([stmt.expand]).
 */
export class RangeForStatement extends Statement {
  static override SPEC = RangeForStatementSpec;
  static override SINCE: Availability | null = cpp(2011);
  static override FEATURES: Features = { initializer: [[true, cpp(2020)]], template_keyword: [[true, cpp(2026)]] };
}

/** `break;` ([stmt.break]). */
export class BreakStatement extends Statement {}

/** `continue;` ([stmt.cont]). */
export class ContinueStatement extends Statement {}

const ReturnStatementSpec = {
  value: optional(() => [Expression]),
};
export interface ReturnStatement extends Properties<typeof ReturnStatementSpec> {}
/** `return value;` ([stmt.return]). */
export class ReturnStatement extends Statement {
  static override SPEC = ReturnStatementSpec;
}

const CoReturnStatementSpec = {
  value: optional(() => [Expression]),
};
export interface CoReturnStatement extends Properties<typeof CoReturnStatementSpec> {}
/** `co_return value;` ([stmt.return.coroutine]). */
export class CoReturnStatement extends Statement {
  static override SPEC = CoReturnStatementSpec;
  static override SINCE: Availability | null = cpp(2020);
}

const GotoStatementSpec = {
  label: one(() => [Identifier]),
};
export interface GotoStatement extends Properties<typeof GotoStatementSpec> {}
/** `goto label;` ([stmt.goto]). */
export class GotoStatement extends Statement {
  static override SPEC = GotoStatementSpec;
}

const TryStatementSpec = {
  body: one(() => [CompoundStatement]),
  handlers: many(() => [Handler]),
};
export interface TryStatement extends Properties<typeof TryStatementSpec> {}
/** `try body handlers` ([except.pre]); also a function-try-block, as a function definition's body. */
export class TryStatement extends Statement {
  static override SPEC = TryStatementSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const HandlerSpec = {
  parameter: one(() => [Parameter]),
  body: one(() => [CompoundStatement]),
};
export interface Handler extends Properties<typeof HandlerSpec> {}
/** `catch (parameter) body`; `catch (...)` when the parameter is an `EllipsisParameter` ([except.pre]). */
export class Handler extends SyntaxNode {
  static override SPEC = HandlerSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const AttributedStatementSpec = {
  attributes: many(() => [AttributeSpecifier]),
  statement: one(() => [Statement]),
};
export interface AttributedStatement extends Properties<typeof AttributedStatementSpec> {}
/** `attributes statement` ([stmt.pre]). */
export class AttributedStatement extends Statement {
  static override SPEC = AttributedStatementSpec;
}

const ContractAssertStatementSpec = {
  attributes: many(() => [AttributeSpecifier]),
  predicate: one(() => [Expression]),
};
export interface ContractAssertStatement extends Properties<typeof ContractAssertStatementSpec> {}
/** `contract_assert attributes (predicate);` ([stmt.contract.assert]). */
export class ContractAssertStatement extends Statement {
  static override SPEC = ContractAssertStatementSpec;
  static override SINCE: Availability | null = cpp(2026);
}

// === Declarations [dcl] ===

const SimpleDeclarationSpec = {
  attributes: many(() => [AttributeSpecifier]),
  specifiers: many(() => [Specifier, AttributeSpecifier]),
  declarators: many(() => [InitDeclarator]),
};
export interface SimpleDeclaration extends Properties<typeof SimpleDeclarationSpec> {}
/**
 * `attributes specifiers declarators;` ([dcl.pre]): variables, functions, types, typedefs, friends and members.
 * Without `;` where it is a condition or a for-range declaration.
 */
export class SimpleDeclaration extends Declaration {
  static override SPEC = SimpleDeclarationSpec;
}

const InitDeclaratorSpec = {
  declarator: optional(() => [Declarator]),
  virt_specifiers: many(() => [VirtSpecifier]),
  pure: flag(),
  bitfield: optional(() => [Expression]),
  initializer: optional(() => [Initializer, InitializerList]),
  requires: optional(() => [Expression]),
  contracts: many(() => [ContractSpecifier]),
};
export interface InitDeclarator extends Properties<typeof InitDeclaratorSpec> {}
/**
 * One declarator of a declaration with what follows it ([dcl.decl], [class.mem]): `declarator virt_specifiers
 * = 0` (with `pure`), `declarator : bitfield initializer`, `declarator initializer`, or `declarator requires
 * contracts`. Without a declarator, an unnamed bit-field.
 */
export class InitDeclarator extends SyntaxNode {
  static override SPEC = InitDeclaratorSpec;
  static override FEATURES: Features = {
    requires: [[true, cpp(2020)]],
    contracts: [[true, cpp(2026)]],
    virt_specifiers: [[true, cpp(2011)]],
    pure: [[true, cpp(1998)]],
  };
}

const FunctionDefinitionSpec = {
  attributes: many(() => [AttributeSpecifier]),
  specifiers: many(() => [Specifier, AttributeSpecifier]),
  declarator: one(() => [Declarator]),
  virt_specifiers: many(() => [VirtSpecifier]),
  requires: optional(() => [Expression]),
  contracts: many(() => [ContractSpecifier]),
  initializers: many(() => [MemberInitializer]),
  body: one(() => [CompoundStatement, TryStatement, DefaultedBody, DeletedBody]),
};
export interface FunctionDefinition extends Properties<typeof FunctionDefinitionSpec> {}
/**
 * `attributes specifiers declarator virt_specifiers requires contracts : initializers body` ([dcl.fct.def]).
 * The body is a block, a function-try-block, `= default;` or `= delete;`.
 */
export class FunctionDefinition extends Declaration {
  static override SPEC = FunctionDefinitionSpec;
  static override FEATURES: Features = {
    requires: [[true, cpp(2020)]],
    contracts: [[true, cpp(2026)]],
    virt_specifiers: [[true, cpp(2011)]],
    initializers: [[true, cpp(1998)]],
  };
}

/** `= default;` ([dcl.fct.def.default]). */
export class DefaultedBody extends SyntaxNode {
  static override SINCE: Availability | null = cpp(2011);
}

const DeletedBodySpec = {
  reason: optional(() => [Expression]),
};
export interface DeletedBody extends Properties<typeof DeletedBodySpec> {}
/** `= delete;`, or `= delete(reason);` ([dcl.fct.def.delete]). */
export class DeletedBody extends SyntaxNode {
  static override SPEC = DeletedBodySpec;
  static override SINCE: Availability | null = cpp(2011);
  static override FEATURES: Features = { reason: [[true, cpp(2026)]] };
}

const MemberInitializerSpec = {
  member: one(() => [Name]),
  initializer: one(() => [ParenthesizedInitializer, InitializerList]),
  pack: flag(),
};
export interface MemberInitializer extends Properties<typeof MemberInitializerSpec> {}
/**
 * `member(arguments)` or `member{items}` in a constructor's initializer list, with `pack` `member(...)...`
 * ([class.base.init]).
 */
export class MemberInitializer extends SyntaxNode {
  static override SPEC = MemberInitializerSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const VirtSpecifierSpec = {
  keyword: choice("override", "final"),
};
export interface VirtSpecifier extends Properties<typeof VirtSpecifierSpec> {}
/** `override` or `final` ([class.mem]). */
export class VirtSpecifier extends SyntaxNode {
  static override SPEC = VirtSpecifierSpec;
  static override SINCE: Availability | null = cpp(2011);
}

// --- Specifiers [dcl.spec] ---

const DeclSpecifierSpec = {
  keyword: choice(...DECL_KEYWORDS),
};
export interface DeclSpecifier extends Properties<typeof DeclSpecifierSpec> {}
/**
 * A keyword specifier: storage class, function specifier, `friend`, `typedef`, `constexpr`, `consteval`,
 * `constinit` or `inline` ([dcl.stc] to [dcl.constinit]).
 */
export class DeclSpecifier extends Specifier {
  static override SPEC = DeclSpecifierSpec;
  static override FEATURES: Features = {
    keyword: [
      ["thread_local", both(2011, 2023)],
      ["_Thread_local", c(2011)],
      ["mutable", cpp(1998)],
      ["register", both([1998, 2017], 1989)],
      ["inline", both(1998, 1999)],
      ["virtual", cpp(1998)],
      ["_Noreturn", c(2011)],
      ["friend", cpp(1998)],
      ["constexpr", both(2011, 2023)],
      ["consteval", cpp(2020)],
      ["constinit", cpp(2020)],
    ],
  };
}

const ExplicitSpecifierSpec = {
  condition: optional(() => [Expression]),
};
export interface ExplicitSpecifier extends Properties<typeof ExplicitSpecifierSpec> {}
/** `explicit`, or `explicit(condition)` ([dcl.fct.spec]). */
export class ExplicitSpecifier extends Specifier {
  static override SPEC = ExplicitSpecifierSpec;
  static override SINCE: Availability | null = cpp(1998);
  static override FEATURES: Features = { condition: [[true, cpp(2020)]] };
}

const CvQualifierSpec = {
  keyword: choice(...CV_KEYWORDS),
};
export interface CvQualifier extends Properties<typeof CvQualifierSpec> {}
/** `const`, `volatile`, C's `restrict` and `_Atomic`, and their extensions ([dcl.type.cv], C [6.7.4]). */
export class CvQualifier extends Specifier {
  static override SPEC = CvQualifierSpec;
  static override FEATURES: Features = { keyword: [["restrict", c(1999)], ["_Atomic", c(2011)]] };
}

const PrimitiveTypeSpecifierSpec = {
  keyword: choice(...PRIMITIVE_KEYWORDS),
};
export interface PrimitiveTypeSpecifier extends Properties<typeof PrimitiveTypeSpecifierSpec> {}
/** A fundamental type keyword: `int`, `unsigned`, `double`... ([dcl.type.simple]). `unsigned long` is two. */
export class PrimitiveTypeSpecifier extends Specifier {
  static override SPEC = PrimitiveTypeSpecifierSpec;
  static override FEATURES: Features = {
    keyword: [
      ["char8_t", cpp(2020)],
      ["char16_t", cpp(2011)],
      ["char32_t", cpp(2011)],
      ["wchar_t", cpp(1998)],
      ["bool", both(1998, 2023)],
      ["_Bool", c(1999)],
      ["_Complex", c(1999)],
      ["_Imaginary", c(1999)],
      ["_Decimal32", c(2023)],
      ["_Decimal64", c(2023)],
      ["_Decimal128", c(2023)],
    ],
  };
}

const NamedTypeSpecifierSpec = {
  name: one(() => [Name]),
};
export interface NamedTypeSpecifier extends Properties<typeof NamedTypeSpecifierSpec> {}
/** A type named by a class, enumeration, typedef or template name ([dcl.type.simple]). */
export class NamedTypeSpecifier extends Specifier {
  static override SPEC = NamedTypeSpecifierSpec;
}

const TypenameSpecifierSpec = {
  name: one(() => [Name]),
};
export interface TypenameSpecifier extends Properties<typeof TypenameSpecifierSpec> {}
/** `typename name`, naming a type in a dependent scope ([temp.res]). */
export class TypenameSpecifier extends Specifier {
  static override SPEC = TypenameSpecifierSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const ClassSpecifierSpec = {
  key: choice(...CLASS_KEYS),
  attributes: many(() => [AttributeSpecifier]),
  name: optional(() => [Name]),
  final: flag(),
  bases: many(() => [BaseSpecifier]),
  body: optional(() => [MemberList]),
};
export interface ClassSpecifier extends Properties<typeof ClassSpecifierSpec> {}
/**
 * `key attributes name final : bases { members }` ([class.pre]); without a body, the elaborated type specifier
 * `key attributes name` ([dcl.type.elab]).
 */
export class ClassSpecifier extends Specifier {
  static override SPEC = ClassSpecifierSpec;
  static override FEATURES: Features = { final: [[true, cpp(2011)]], bases: [[true, cpp(1998)]] };
}

const MemberListSpec = {
  items: many(() => [Declaration, Directive, Comment]),
};
export interface MemberList extends Properties<typeof MemberListSpec> {}
/** `{ items }`: a class's member specification ([class.mem]). */
export class MemberList extends SyntaxNode {
  static override SPEC = MemberListSpec;
}

const EnumSpecifierSpec = {
  key: choice(...ENUM_KEYS),
  attributes: many(() => [AttributeSpecifier]),
  name: optional(() => [Name]),
  base: optional(() => [TypeId]),
  body: optional(() => [EnumeratorList]),
};
export interface EnumSpecifier extends Properties<typeof EnumSpecifierSpec> {}
/**
 * `key attributes name : base { enumerators }` ([dcl.enum]); without a body, an opaque enumeration declaration
 * or an elaborated type specifier.
 */
export class EnumSpecifier extends Specifier {
  static override SPEC = EnumSpecifierSpec;
  static override FEATURES: Features = {
    key: [["enum class", cpp(2011)], ["enum struct", cpp(2011)]],
    base: [[true, both(2011, 2023)]],
  };
}

const EnumeratorListSpec = {
  enumerators: many(() => [Enumerator, Directive, Comment]),
  trailing_comma: flag(),
};
export interface EnumeratorList extends Properties<typeof EnumeratorListSpec> {}
/** `{ enumerators }`, with `trailing_comma` `{ enumerators, }` ([dcl.enum]). */
export class EnumeratorList extends SyntaxNode {
  static override SPEC = EnumeratorListSpec;
}

const EnumeratorSpec = {
  name: one(() => [Identifier]),
  attributes: many(() => [AttributeSpecifier]),
  value: optional(() => [Expression]),
};
export interface Enumerator extends Properties<typeof EnumeratorSpec> {}
/** `name attributes = value` ([dcl.enum]). */
export class Enumerator extends SyntaxNode {
  static override SPEC = EnumeratorSpec;
}

const DecltypeSpecifierSpec = {
  expression: one(() => [Expression]),
};
export interface DecltypeSpecifier extends Properties<typeof DecltypeSpecifierSpec> {}
/** `decltype(expression)` ([dcl.type.decltype]). */
export class DecltypeSpecifier extends Specifier {
  static override SPEC = DecltypeSpecifierSpec;
  static override SINCE: Availability | null = cpp(2011);
}

const PlaceholderTypeSpecifierSpec = {
  constraint: optional(() => [Name]),
  decltype: flag(),
};
export interface PlaceholderTypeSpecifier extends Properties<typeof PlaceholderTypeSpecifierSpec> {}
/** `auto`, `decltype(auto)` with `decltype`, each optionally constrained: `C<T> auto` ([dcl.spec.auto]). */
export class PlaceholderTypeSpecifier extends Specifier {
  static override SPEC = PlaceholderTypeSpecifierSpec;
  static override SINCE: Availability | null = both(2011, 2023);
  static override FEATURES: Features = { decltype: [[true, cpp(2014)]], constraint: [[true, cpp(2020)]] };
}

const TypeofSpecifierSpec = {
  keyword: choice(...TYPEOF_KEYWORDS),
  operand: one(() => [Expression, TypeId]),
};
export interface TypeofSpecifier extends Properties<typeof TypeofSpecifierSpec> {}
/** `typeof(operand)` or `typeof_unqual(operand)` (C [6.7.3.6]), and the GNU `__typeof__`. */
export class TypeofSpecifier extends Specifier {
  static override SPEC = TypeofSpecifierSpec;
  static override SINCE: Availability | null = c(2023);
  override availability(): Availability | null {
    return this.keyword === "__typeof__" || this.keyword === "__typeof" ? null : TypeofSpecifier.SINCE;
  }
}

const AtomicTypeSpecifierSpec = {
  type: one(() => [TypeId]),
};
export interface AtomicTypeSpecifier extends Properties<typeof AtomicTypeSpecifierSpec> {}
/** `_Atomic(type)` (C [6.7.3.5]). */
export class AtomicTypeSpecifier extends Specifier {
  static override SPEC = AtomicTypeSpecifierSpec;
  static override SINCE: Availability | null = c(2011);
}

const BitIntSpecifierSpec = {
  width: one(() => [Expression]),
};
export interface BitIntSpecifier extends Properties<typeof BitIntSpecifierSpec> {}
/** `_BitInt(width)` (C [6.7.3]). */
export class BitIntSpecifier extends Specifier {
  static override SPEC = BitIntSpecifierSpec;
  static override SINCE: Availability | null = c(2023);
}

const PackIndexingSpecifierSpec = {
  pack: one(() => [Name]),
  index: one(() => [Expression]),
};
export interface PackIndexingSpecifier extends Properties<typeof PackIndexingSpecifierSpec> {}
/** `pack...[index]`, a type of a pack ([dcl.type.pack.index]). */
export class PackIndexingSpecifier extends Specifier {
  static override SPEC = PackIndexingSpecifierSpec;
  static override SINCE: Availability | null = cpp(2026);
}

const SpliceSpecifierSpec = {
  typename_keyword: flag(),
  template_keyword: flag(),
  reflection: one(() => [Expression]),
  arguments: many(() => [Expression, TypeId]),
};
export interface SpliceSpecifier extends Properties<typeof SpliceSpecifierSpec> {}
/** `typename [: reflection :]`, or `template [: reflection :] <arguments>` ([dcl.type.splice]). */
export class SpliceSpecifier extends Specifier {
  static override SPEC = SpliceSpecifierSpec;
  static override SINCE: Availability | null = cpp(2026);
}

// --- Declarators [dcl.decl] ---

const IdDeclaratorSpec = {
  name: one(() => [Name]),
  attributes: many(() => [AttributeSpecifier]),
};
export interface IdDeclarator extends Properties<typeof IdDeclaratorSpec> {}
/** `name attributes`: the declarator-id, innermost in every named declarator ([dcl.decl]). */
export class IdDeclarator extends Declarator {
  static override SPEC = IdDeclaratorSpec;
}

const PackDeclaratorSpec = {
  declarator: optional(() => [Declarator]),
};
export interface PackDeclarator extends Properties<typeof PackDeclaratorSpec> {}
/** `...declarator`, declaring a pack; abstract (`...` alone) without a declarator ([dcl.fct]). */
export class PackDeclarator extends Declarator {
  static override SPEC = PackDeclaratorSpec;
  static override SINCE: Availability | null = cpp(2011);
}

const PointerDeclaratorSpec = {
  scope: optional(() => [Name]),
  attributes: many(() => [AttributeSpecifier]),
  qualifiers: many(() => [CvQualifier]),
  declarator: optional(() => [Declarator]),
};
export interface PointerDeclarator extends Properties<typeof PointerDeclaratorSpec> {}
/** `* attributes qualifiers declarator`, or `scope::* ...` for a pointer to member ([dcl.ptr], [dcl.mptr]). */
export class PointerDeclarator extends Declarator {
  static override SPEC = PointerDeclaratorSpec;
  static override FEATURES: Features = { scope: [[true, cpp(1998)]] };
}

const ReferenceDeclaratorSpec = {
  rvalue: flag(),
  attributes: many(() => [AttributeSpecifier]),
  declarator: optional(() => [Declarator]),
};
export interface ReferenceDeclarator extends Properties<typeof ReferenceDeclaratorSpec> {}
/** `& attributes declarator`, or `&& ...` with `rvalue` ([dcl.ref]). */
export class ReferenceDeclarator extends Declarator {
  static override SPEC = ReferenceDeclaratorSpec;
  static override SINCE: Availability | null = cpp(1998);
  static override FEATURES: Features = { rvalue: [[true, cpp(2011)]] };
}

const ArrayDeclaratorSpec = {
  declarator: optional(() => [Declarator]),
  static: flag(),
  qualifiers: many(() => [CvQualifier]),
  size: optional(() => [Expression]),
  star: flag(),
  attributes: many(() => [AttributeSpecifier]),
};
export interface ArrayDeclarator extends Properties<typeof ArrayDeclaratorSpec> {}
/** `declarator[static qualifiers size] attributes`, or C's `[*]` with `star` ([dcl.array], C [6.7.7.3]). */
export class ArrayDeclarator extends Declarator {
  static override SPEC = ArrayDeclaratorSpec;
  static override FEATURES: Features = {
    static: [[true, c(1999)]],
    qualifiers: [[true, c(1999)]],
    star: [[true, c(1999)]],
  };
}

const FunctionDeclaratorSpec = {
  declarator: optional(() => [Declarator]),
  parameters: many(() => [Parameter]),
  qualifiers: many(() => [CvQualifier]),
  ref_qualifier: optionalChoice("&", "&&"),
  exception: optional(() => [ExceptionSpecification]),
  attributes: many(() => [AttributeSpecifier]),
  trailing_return: optional(() => [TypeId]),
};
export interface FunctionDeclarator extends Properties<typeof FunctionDeclaratorSpec> {}
/** `declarator(parameters) qualifiers ref_qualifier exception attributes -> trailing_return` ([dcl.fct]). */
export class FunctionDeclarator extends Declarator {
  static override SPEC = FunctionDeclaratorSpec;
  static override FEATURES: Features = {
    qualifiers: [[true, cpp(1998)]],
    ref_qualifier: [[true, cpp(2011)]],
    trailing_return: [[true, cpp(2011)]],
  };
}

const ParenthesizedDeclaratorSpec = {
  declarator: one(() => [Declarator]),
};
export interface ParenthesizedDeclarator extends Properties<typeof ParenthesizedDeclaratorSpec> {}
/** `(declarator)` ([dcl.decl]). */
export class ParenthesizedDeclarator extends Declarator {
  static override SPEC = ParenthesizedDeclaratorSpec;
}

const StructuredBindingDeclaratorSpec = {
  bindings: many(() => [IdDeclarator, PackDeclarator]),
};
export interface StructuredBindingDeclarator extends Properties<typeof StructuredBindingDeclaratorSpec> {}
/** `[bindings]` ([dcl.struct.bind]): each binding is a name with attributes, or a pack of one. */
export class StructuredBindingDeclarator extends Declarator {
  static override SPEC = StructuredBindingDeclaratorSpec;
  static override SINCE: Availability | null = cpp(2017);
  override features(): [string, Availability][] {
    const found: [string, Availability][] = [];
    if (this.bindings.some((b) => b instanceof PackDeclarator)) {
      found.push(["StructuredBindingDeclarator with a pack", cpp(2026)]);
    }
    if (this.bindings.some((b) => b instanceof IdDeclarator && b.attributes.length > 0)) {
      found.push(["StructuredBindingDeclarator with attributes", cpp(2026)]);
    }
    return found;
  }
}

const TypeIdSpec = {
  specifiers: many(() => [Specifier, AttributeSpecifier]),
  declarator: optional(() => [Declarator]),
};
export interface TypeId extends Properties<typeof TypeIdSpec> {}
/** `specifiers declarator`: a type, named by specifiers and an abstract declarator ([dcl.name]). */
export class TypeId extends SyntaxNode {
  static override SPEC = TypeIdSpec;
}

const ParameterDeclarationSpec = {
  attributes: many(() => [AttributeSpecifier]),
  this_keyword: flag(),
  specifiers: many(() => [Specifier, AttributeSpecifier]),
  declarator: optional(() => [Declarator]),
  default: optional(() => [Expression]),
};
export interface ParameterDeclaration extends Properties<typeof ParameterDeclarationSpec> {}
/**
 * `attributes this specifiers declarator = default` ([dcl.fct]); with `this_keyword`, an explicit object
 * parameter. Also a constant template parameter.
 */
export class ParameterDeclaration extends Parameter {
  static override SPEC = ParameterDeclarationSpec;
  static override FEATURES: Features = { this_keyword: [[true, cpp(2023)]] };
}

/** `...`: the variable arguments of a variadic function, or the parameter of `catch (...)` ([dcl.fct]). */
export class EllipsisParameter extends Parameter {}

// --- Initializers [dcl.init] ---

const EqualInitializerSpec = {
  value: one(() => [Expression]),
};
export interface EqualInitializer extends Properties<typeof EqualInitializerSpec> {}
/** `= value` ([dcl.init]). */
export class EqualInitializer extends Initializer {
  static override SPEC = EqualInitializerSpec;
}

const ParenthesizedInitializerSpec = {
  arguments: many(() => [Expression]),
};
export interface ParenthesizedInitializer extends Properties<typeof ParenthesizedInitializerSpec> {}
/** `(arguments)` ([dcl.init]). */
export class ParenthesizedInitializer extends Initializer {
  static override SPEC = ParenthesizedInitializerSpec;
  static override SINCE: Availability | null = cpp(1998);
}

// --- Exception specifications [except.spec] ---

const NoexceptSpecifierSpec = {
  condition: optional(() => [Expression]),
};
export interface NoexceptSpecifier extends Properties<typeof NoexceptSpecifierSpec> {}
/** `noexcept`, or `noexcept(condition)` ([except.spec]). */
export class NoexceptSpecifier extends ExceptionSpecification {
  static override SPEC = NoexceptSpecifierSpec;
  static override SINCE: Availability | null = cpp(2011);
}

const ThrowSpecifierSpec = {
  types: many(() => [TypeId, PackExpansion]),
};
export interface ThrowSpecifier extends Properties<typeof ThrowSpecifierSpec> {}
/**
 * `throw(types)`: a dynamic exception specification, removed in C++17; `throw()` lasted until C++20
 * ([except.spec] in C++14).
 */
export class ThrowSpecifier extends ExceptionSpecification {
  static override SPEC = ThrowSpecifierSpec;
  static override SINCE: Availability | null = cpp(1998);
  override features(): [string, Availability][] {
    if (this.types.length > 0) return [["ThrowSpecifier with types", { [CPP]: [1998, 2017] }]];
    return [["ThrowSpecifier", { [CPP]: [1998, 2020] }]];
  }
}

// --- Contract specifiers [dcl.contract] ---

const PreconditionSpecifierSpec = {
  attributes: many(() => [AttributeSpecifier]),
  predicate: one(() => [Expression]),
};
export interface PreconditionSpecifier extends Properties<typeof PreconditionSpecifierSpec> {}
/** `pre attributes (predicate)` ([dcl.contract.func]). */
export class PreconditionSpecifier extends ContractSpecifier {
  static override SPEC = PreconditionSpecifierSpec;
  static override SINCE: Availability | null = cpp(2026);
}

const PostconditionSpecifierSpec = {
  attributes: many(() => [AttributeSpecifier]),
  result: optional(() => [Identifier]),
  predicate: one(() => [Expression]),
};
export interface PostconditionSpecifier extends Properties<typeof PostconditionSpecifierSpec> {}
/** `post attributes (result: predicate)` ([dcl.contract.func]). */
export class PostconditionSpecifier extends ContractSpecifier {
  static override SPEC = PostconditionSpecifierSpec;
  static override SINCE: Availability | null = cpp(2026);
}

// --- Namespaces [basic.namespace] ---

const NamespaceDefinitionSpec = {
  inline: flag(),
  attributes: many(() => [AttributeSpecifier]),
  names: many(() => [NamespaceName]),
  items: many(() => [Declaration, Directive, Comment]),
};
export interface NamespaceDefinition extends Properties<typeof NamespaceDefinitionSpec> {}
/**
 * `inline namespace attributes names { items }` ([namespace.def]); unnamed without names, nested with several
 * (`namespace a::inline b`).
 */
export class NamespaceDefinition extends Declaration {
  static override SPEC = NamespaceDefinitionSpec;
  static override SINCE: Availability | null = cpp(1998);
  static override FEATURES: Features = { inline: [[true, cpp(2011)]], attributes: [[true, cpp(2017)]] };
  override features(): [string, Availability][] {
    const found: [string, Availability][] = [];
    if (this.names.length > 1) {
      found.push(["NamespaceDefinition with nested names", cpp(2017)]);
      if (this.names.some((n) => n.inline)) found.push(["NamespaceDefinition with inline nested names", cpp(2020)]);
    }
    return found;
  }
}

const NamespaceNameSpec = {
  inline: flag(),
  name: one(() => [Identifier]),
};
export interface NamespaceName extends Properties<typeof NamespaceNameSpec> {}
/** One name of a namespace definition, `inline name` with `inline` ([namespace.def]). */
export class NamespaceName extends SyntaxNode {
  static override SPEC = NamespaceNameSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const NamespaceAliasDefinitionSpec = {
  name: one(() => [Identifier]),
  target: one(() => [Name]),
};
export interface NamespaceAliasDefinition extends Properties<typeof NamespaceAliasDefinitionSpec> {}
/** `namespace name = target;` ([namespace.alias]). */
export class NamespaceAliasDefinition extends Declaration {
  static override SPEC = NamespaceAliasDefinitionSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const UsingDirectiveSpec = {
  attributes: many(() => [AttributeSpecifier]),
  name: one(() => [Name]),
};
export interface UsingDirective extends Properties<typeof UsingDirectiveSpec> {}
/** `attributes using namespace name;` ([namespace.udir]). */
export class UsingDirective extends Declaration {
  static override SPEC = UsingDirectiveSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const UsingDeclarationSpec = {
  declarators: many(() => [UsingDeclarator]),
};
export interface UsingDeclaration extends Properties<typeof UsingDeclarationSpec> {}
/** `using declarators;` ([namespace.udecl]). */
export class UsingDeclaration extends Declaration {
  static override SPEC = UsingDeclarationSpec;
  static override SINCE: Availability | null = cpp(1998);
  override features(): [string, Availability][] {
    return this.declarators.length > 1 ? [["UsingDeclaration with several declarators", cpp(2017)]] : [];
  }
}

const UsingDeclaratorSpec = {
  typename_keyword: flag(),
  name: one(() => [Name]),
  pack: flag(),
};
export interface UsingDeclarator extends Properties<typeof UsingDeclaratorSpec> {}
/** `typename name...` ([namespace.udecl]). */
export class UsingDeclarator extends SyntaxNode {
  static override SPEC = UsingDeclaratorSpec;
  static override SINCE: Availability | null = cpp(1998);
  static override FEATURES: Features = { pack: [[true, cpp(2017)]] };
}

const UsingEnumDeclarationSpec = {
  type: one(() => [Name]),
};
export interface UsingEnumDeclaration extends Properties<typeof UsingEnumDeclarationSpec> {}
/** `using enum type;` ([enum.udecl]). */
export class UsingEnumDeclaration extends Declaration {
  static override SPEC = UsingEnumDeclarationSpec;
  static override SINCE: Availability | null = cpp(2020);
}

const AliasDeclarationSpec = {
  name: one(() => [Identifier]),
  attributes: many(() => [AttributeSpecifier]),
  type: one(() => [TypeId]),
};
export interface AliasDeclaration extends Properties<typeof AliasDeclarationSpec> {}
/** `using name attributes = type;` ([dcl.typedef]). */
export class AliasDeclaration extends Declaration {
  static override SPEC = AliasDeclarationSpec;
  static override SINCE: Availability | null = cpp(2011);
}

const StaticAssertDeclarationSpec = {
  keyword: choice("static_assert", "_Static_assert"),
  condition: one(() => [Expression]),
  message: optional(() => [Expression]),
};
export interface StaticAssertDeclaration extends Properties<typeof StaticAssertDeclarationSpec> {}
/** `static_assert(condition, message);` ([dcl.pre], C [6.7.12]). */
export class StaticAssertDeclaration extends Declaration {
  static override SPEC = StaticAssertDeclarationSpec;
  static override SINCE: Availability | null = both(2011, 2011);
  static override FEATURES: Features = { keyword: [["static_assert", both(2011, 2023)], ["_Static_assert", c(2011)]] };
  override features(): [string, Availability][] {
    return this.message === null ? [["StaticAssertDeclaration without a message", both(2017, 2023)]] : [];
  }
}

const AttributeDeclarationSpec = {
  attributes: many(() => [AttributeSpecifier]),
};
export interface AttributeDeclaration extends Properties<typeof AttributeDeclarationSpec> {}
/** `attributes;` ([dcl.pre]). */
export class AttributeDeclaration extends Declaration {
  static override SPEC = AttributeDeclarationSpec;
  static override SINCE: Availability | null = both(2011, 2023);
}

/** `;` ([dcl.pre]). */
export class EmptyDeclaration extends Declaration {}

const LinkageSpecificationSpec = {
  language: text(),
  braced: flag(),
  items: many(() => [Declaration, Directive, Comment]),
};
export interface LinkageSpecification extends Properties<typeof LinkageSpecificationSpec> {}
/** `extern "language" { items }`, or without `braced` `extern "language" item` ([dcl.link]). */
export class LinkageSpecification extends Declaration {
  static override SPEC = LinkageSpecificationSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const AsmDeclarationSpec = {
  attributes: many(() => [AttributeSpecifier]),
  keyword: choice(...ASM_KEYWORDS),
  volatile: flag(),
  inline: flag(),
  goto: flag(),
  template: one(() => [Expression]),
  outputs: many(() => [AsmOperand]),
  inputs: many(() => [AsmOperand]),
  clobbers: many(() => [Expression]),
  labels: many(() => [Identifier]),
};
export interface AsmDeclaration extends Properties<typeof AsmDeclarationSpec> {}
/**
 * `asm volatile inline goto (template : outputs : inputs : clobbers : labels);` ([dcl.asm]). Operands and the
 * sections after the template are GNU extensions.
 */
export class AsmDeclaration extends Declaration {
  static override SPEC = AsmDeclarationSpec;
}

const AsmOperandSpec = {
  name: optional(() => [Identifier]),
  constraint: one(() => [Expression]),
  value: one(() => [Expression]),
};
export interface AsmOperand extends Properties<typeof AsmOperandSpec> {}
/** `[name] constraint (value)` (GNU). */
export class AsmOperand extends SyntaxNode {
  static override SPEC = AsmOperandSpec;
  static override EXTENSION = true;
}

// --- Attributes [dcl.attr] ---

const StandardAttributeSpecifierSpec = {
  using_namespace: optionalText(),
  attributes: many(() => [Attribute, Annotation]),
};
export interface StandardAttributeSpecifier extends Properties<typeof StandardAttributeSpecifierSpec> {}
/** `[[using namespace: attributes]]` ([dcl.attr.grammar]). */
export class StandardAttributeSpecifier extends AttributeSpecifier {
  static override SPEC = StandardAttributeSpecifierSpec;
  static override SINCE: Availability | null = both(2011, 2023);
  static override FEATURES: Features = { using_namespace: [[true, cpp(2017)]] };
}

const AttributeSpec = {
  namespace: optionalText(),
  name: text(),
  arguments: many(() => [Expression, TypeId]),
  pack: flag(),
};
export interface Attribute extends Properties<typeof AttributeSpec> {}
/**
 * `namespace::name(arguments)`, or `name...` with `pack` ([dcl.attr.grammar]). The arguments of an attribute are
 * balanced tokens in the grammar; here they are expressions.
 */
export class Attribute extends SyntaxNode {
  static override SPEC = AttributeSpec;
}

const AnnotationSpec = {
  value: one(() => [Expression]),
  pack: flag(),
};
export interface Annotation extends Properties<typeof AnnotationSpec> {}
/** `=value`, or `=value...` with `pack`: an annotation for reflection ([dcl.attr.annotation]). */
export class Annotation extends SyntaxNode {
  static override SPEC = AnnotationSpec;
  static override SINCE: Availability | null = cpp(2026);
}

const AlignasSpecifierSpec = {
  keyword: choice("alignas", "_Alignas"),
  operand: one(() => [Expression, TypeId]),
  pack: flag(),
};
export interface AlignasSpecifier extends Properties<typeof AlignasSpecifierSpec> {}
/** `alignas(operand)`, `alignas(operand...)` with `pack`, or C's `_Alignas(operand)` ([dcl.align]). */
export class AlignasSpecifier extends AttributeSpecifier {
  static override SPEC = AlignasSpecifierSpec;
  static override SINCE: Availability | null = both(2011, 2011);
  static override FEATURES: Features = { keyword: [["alignas", both(2011, 2023)], ["_Alignas", c(2011)]] };
}

const GnuAttributeSpecifierSpec = {
  keyword: choice("__attribute__", "__attribute"),
  attributes: many(() => [Attribute]),
};
export interface GnuAttributeSpecifier extends Properties<typeof GnuAttributeSpecifierSpec> {}
/** `__attribute__((attributes))` (GNU). */
export class GnuAttributeSpecifier extends AttributeSpecifier {
  static override SPEC = GnuAttributeSpecifierSpec;
  static override EXTENSION = true;
}

const DeclspecSpecifierSpec = {
  attributes: many(() => [Attribute]),
};
export interface DeclspecSpecifier extends Properties<typeof DeclspecSpecifierSpec> {}
/** `__declspec(attributes)` (Microsoft). */
export class DeclspecSpecifier extends AttributeSpecifier {
  static override SPEC = DeclspecSpecifierSpec;
  static override EXTENSION = true;
}

// === Modules [module] ===

const ModuleDeclarationSpec = {
  export: flag(),
  name: text(),
  partition: optionalText(),
  attributes: many(() => [AttributeSpecifier]),
};
export interface ModuleDeclaration extends Properties<typeof ModuleDeclarationSpec> {}
/** `export module name:partition attributes;` ([module.unit]). Names are dotted, such as `std.core`. */
export class ModuleDeclaration extends Declaration {
  static override SPEC = ModuleDeclarationSpec;
  static override SINCE: Availability | null = cpp(2020);
}

/** `module;`, opening the global module fragment ([module.global.frag]). */
export class GlobalModuleFragment extends Declaration {
  static override SINCE: Availability | null = cpp(2020);
}

/** `module :private;`, opening the private module fragment ([module.private.frag]). */
export class PrivateModuleFragment extends Declaration {
  static override SINCE: Availability | null = cpp(2020);
}

const ImportDeclarationSpec = {
  export: flag(),
  name: optionalText(),
  partition: optionalText(),
  header: optionalText(),
  system: flag(),
  attributes: many(() => [AttributeSpecifier]),
};
export interface ImportDeclaration extends Properties<typeof ImportDeclarationSpec> {}
/**
 * `export import name:partition attributes;`, or `import <header>;` with `system` and `import "header";`
 * ([module.import]).
 */
export class ImportDeclaration extends Declaration {
  static override SPEC = ImportDeclarationSpec;
  static override SINCE: Availability | null = cpp(2020);
}

const ExportDeclarationSpec = {
  braced: flag(),
  items: many(() => [Declaration, Directive, Comment]),
};
export interface ExportDeclaration extends Properties<typeof ExportDeclarationSpec> {}
/** `export { items }`, or without `braced` `export item` ([module.interface]). */
export class ExportDeclaration extends Declaration {
  static override SPEC = ExportDeclarationSpec;
  static override SINCE: Availability | null = cpp(2020);
}

// === Classes [class] ===

const AccessSpecifierSpec = {
  access: choice(...ACCESSES),
};
export interface AccessSpecifier extends Properties<typeof AccessSpecifierSpec> {}
/** `public:`, `protected:` or `private:` among a class's members ([class.access.spec]). */
export class AccessSpecifier extends Declaration {
  static override SPEC = AccessSpecifierSpec;
  static override SINCE: Availability | null = cpp(1998);
}

const BaseSpecifierSpec = {
  attributes: many(() => [AttributeSpecifier]),
  virtual: flag(),
  access: optionalChoice(...ACCESSES),
  type: one(() => [Name, DecltypeSpecifier, PackIndexingSpecifier, SpliceSpecifier]),
  pack: flag(),
};
export interface BaseSpecifier extends Properties<typeof BaseSpecifierSpec> {}
/** `attributes virtual access type...` ([class.derived]). `virtual` is written before the access. */
export class BaseSpecifier extends SyntaxNode {
  static override SPEC = BaseSpecifierSpec;
  static override SINCE: Availability | null = cpp(1998);
  static override FEATURES: Features = { pack: [[true, cpp(2011)]], attributes: [[true, cpp(2011)]] };
}

const FriendTypeDeclarationSpec = {
  types: many(() => [TypeId, PackExpansion]),
};
export interface FriendTypeDeclaration extends Properties<typeof FriendTypeDeclarationSpec> {}
/** `friend types;`: befriending several types, or packs of them ([class.friend]). */
export class FriendTypeDeclaration extends Declaration {
  static override SPEC = FriendTypeDeclarationSpec;
  static override SINCE: Availability | null = cpp(2026);
}

// === Templates [temp] ===

const TemplateDeclarationSpec = {
  parameters: many(() => [TemplateParameter, Parameter]),
  requires: optional(() => [Expression]),
  declaration: one(() => [Declaration]),
};
export interface TemplateDeclaration extends Properties<typeof TemplateDeclarationSpec> {}
/** `template <parameters> requires declaration` ([temp.pre]); an explicit specialization without parameters. */
export class TemplateDeclaration extends Declaration {
  static override SPEC = TemplateDeclarationSpec;
  static override SINCE: Availability | null = cpp(1998);
  static override FEATURES: Features = { requires: [[true, cpp(2020)]] };
}

const TypeParameterSpec = {
  key: optionalChoice("class", "typename"),
  constraint: optional(() => [Name]),
  pack: flag(),
  name: optional(() => [Identifier]),
  default: optional(() => [TypeId]),
};
export interface TypeParameter extends Properties<typeof TypeParameterSpec> {}
/**
 * `key ...name = default` with `key` `class` or `typename`, or the constrained `constraint ...name = default`
 * ([temp.param]).
 */
export class TypeParameter extends TemplateParameter {
  static override SPEC = TypeParameterSpec;
  static override SINCE: Availability | null = cpp(1998);
  static override FEATURES: Features = { pack: [[true, cpp(2011)]], constraint: [[true, cpp(2020)]] };
}

const TemplateTemplateParameterSpec = {
  parameters: many(() => [TemplateParameter, Parameter]),
  requires: optional(() => [Expression]),
  key: choice("class", "typename", "concept", "auto"),
  pack: flag(),
  name: optional(() => [Identifier]),
  default: optional(() => [Name]),
};
export interface TemplateTemplateParameter extends Properties<typeof TemplateTemplateParameterSpec> {}
/**
 * `template <parameters> requires key ...name = default` ([temp.param]); `key` is `class` or `typename`, or for
 * a concept or variable template `concept` or `auto`.
 */
export class TemplateTemplateParameter extends TemplateParameter {
  static override SPEC = TemplateTemplateParameterSpec;
  static override SINCE: Availability | null = cpp(1998);
  static override FEATURES: Features = {
    pack: [[true, cpp(2011)]],
    requires: [[true, cpp(2020)]],
    key: [["typename", cpp(2017)], ["concept", cpp(2026)], ["auto", cpp(2026)]],
  };
}

const ConceptDefinitionSpec = {
  name: one(() => [Identifier]),
  attributes: many(() => [AttributeSpecifier]),
  constraint: one(() => [Expression]),
};
export interface ConceptDefinition extends Properties<typeof ConceptDefinitionSpec> {}
/** `concept name attributes = constraint;` ([temp.concept]). */
export class ConceptDefinition extends Declaration {
  static override SPEC = ConceptDefinitionSpec;
  static override SINCE: Availability | null = cpp(2020);
}

const ExplicitInstantiationSpec = {
  extern: flag(),
  declaration: one(() => [Declaration]),
};
export interface ExplicitInstantiation extends Properties<typeof ExplicitInstantiationSpec> {}
/** `template declaration`, or with `extern` `extern template declaration` ([temp.explicit]). */
export class ExplicitInstantiation extends Declaration {
  static override SPEC = ExplicitInstantiationSpec;
  static override SINCE: Availability | null = cpp(1998);
  static override FEATURES: Features = { extern: [[true, cpp(2011)]] };
}

// === Preprocessing directives [cpp] ===

const IncludeDirectiveSpec = {
  directive: choice(...INCLUDE_KEYWORDS),
  path: optionalText(),
  system: flag(),
  macro: optional(() => [Expression]),
};
export interface IncludeDirective extends Properties<typeof IncludeDirectiveSpec> {}
/**
 * `#include <path>` with `system`, `#include "path"`, or `#include macro` ([cpp.include]); also `#include_next`
 * and `#import`, which are extensions.
 */
export class IncludeDirective extends Directive {
  static override SPEC = IncludeDirectiveSpec;
}

const DefineDirectiveSpec = {
  name: one(() => [Identifier]),
  function_like: flag(),
  parameters: many(() => [Identifier]),
  variadic: flag(),
  replacement: optionalText(),
};
export interface DefineDirective extends Properties<typeof DefineDirectiveSpec> {}
/**
 * `#define name replacement`, or with `function_like` `#define name(parameters, ...) replacement` ([cpp.replace]).
 * The replacement is the text of its tokens, which are not a tree until the macro is used.
 */
export class DefineDirective extends Directive {
  static override SPEC = DefineDirectiveSpec;
}

const IfDirectiveSpec = {
  condition: one(() => [Expression]),
  items: many(() => [SyntaxNode]),
  alternative: optional(() => [ElifDirective, ElifdefDirective, ElseDirective]),
};
export interface IfDirective extends Properties<typeof IfDirectiveSpec> {}
/** `#if condition items alternative #endif` ([cpp.cond]). */
export class IfDirective extends Directive {
  static override SPEC = IfDirectiveSpec;
}

const IfdefDirectiveSpec = {
  negated: flag(),
  name: one(() => [Identifier]),
  items: many(() => [SyntaxNode]),
  alternative: optional(() => [ElifDirective, ElifdefDirective, ElseDirective]),
};
export interface IfdefDirective extends Properties<typeof IfdefDirectiveSpec> {}
/** `#ifdef name items alternative #endif`, or `#ifndef` with `negated` ([cpp.cond]). */
export class IfdefDirective extends Directive {
  static override SPEC = IfdefDirectiveSpec;
}

const ElifDirectiveSpec: {
  condition: ChildSpec<Expression, false, false>;
  items: ChildSpec<SyntaxNode, true, true>;
  alternative: ChildSpec<ElifDirective | ElifdefDirective | ElseDirective, false, true>;
} = {
  condition: one(() => [Expression]),
  items: many(() => [SyntaxNode]),
  alternative: optional(() => [ElifDirective, ElifdefDirective, ElseDirective]),
};
export interface ElifDirective extends Properties<typeof ElifDirectiveSpec> {}
/** `#elif condition items alternative` ([cpp.cond]). */
export class ElifDirective extends Directive {
  static override SPEC = ElifDirectiveSpec;
}

const ElifdefDirectiveSpec: {
  negated: AttributeSpec<boolean, false>;
  name: ChildSpec<Identifier, false, false>;
  items: ChildSpec<SyntaxNode, true, true>;
  alternative: ChildSpec<ElifDirective | ElifdefDirective | ElseDirective, false, true>;
} = {
  negated: flag(),
  name: one(() => [Identifier]),
  items: many(() => [SyntaxNode]),
  alternative: optional(() => [ElifDirective, ElifdefDirective, ElseDirective]),
};
export interface ElifdefDirective extends Properties<typeof ElifdefDirectiveSpec> {}
/** `#elifdef name items alternative`, or `#elifndef` with `negated` ([cpp.cond]). */
export class ElifdefDirective extends Directive {
  static override SPEC = ElifdefDirectiveSpec;
  static override SINCE: Availability | null = both(2023, 2023);
}

const ElseDirectiveSpec = {
  items: many(() => [SyntaxNode]),
};
export interface ElseDirective extends Properties<typeof ElseDirectiveSpec> {}
/** `#else items` ([cpp.cond]). */
export class ElseDirective extends Directive {
  static override SPEC = ElseDirectiveSpec;
}

const OtherDirectiveSpec = {
  directive: optionalText(),
  text: optionalText(),
};
export interface OtherDirective extends Properties<typeof OtherDirectiveSpec> {}
/**
 * `#directive text` for every other directive: `#undef`, `#pragma`, `#error`, `#warning`, `#line`, `#embed`,
 * `#ident` and the null directive `#` without a name ([cpp.pre]).
 */
export class OtherDirective extends Directive {
  static override SPEC = OtherDirectiveSpec;
  override features(): [string, Availability][] {
    const since = ({ warning: both(2023, 2023), embed: both(2026, 2023) } as Record<string, Availability>)[this.directive ?? ""];
    return since === undefined ? [] : [[`#${this.directive}`, since]];
  }
}

// --- Helpers ---

/** The innermost declarator of `declarator`, which names what it declares, and the declarator binding that name most
 * closely, parentheses aside: a `FunctionDeclarator` there declares a function (`int *f()`), and anything else an
 * object (`int (*f)()`). The innermost is null for an abstract declarator. */
export function binding(declarator: Declarator | null): [IdDeclarator | StructuredBindingDeclarator | null, Declarator | null] {
  let binder: Declarator | null = null;
  let current: Declarator | null = declarator;
  while (current !== null && !(current instanceof IdDeclarator) && !(current instanceof StructuredBindingDeclarator)) {
    if (!(current instanceof ParenthesizedDeclarator)) binder = current;
    current = current.get("declarator") as Declarator | null;
  }
  return [current, binder];
}

// --- The language ---

export const KINDS: readonly (typeof SyntaxNode)[] = [
  Comment, TranslationUnit, Identifier, OperatorName, ConversionName, LiteralOperatorName, DestructorName, TemplateId,
  QualifiedName, IntegerLiteral, FloatingLiteral, CharacterLiteral, StringLiteral, RawStringLiteral,
  UserDefinedLiteral, ConcatenatedString, BooleanLiteral, NullptrLiteral, ThisExpression, ParenthesizedExpression,
  IdExpression, LambdaExpression, LambdaDeclarator, DefaultCapture, SimpleCapture, ThisCapture, InitCapture,
  FoldExpression, RequiresExpression, SimpleRequirement, TypeRequirement, CompoundRequirement, NestedRequirement,
  PackIndexingExpression, ReflectExpression, SpliceExpression, SubscriptExpression, CallExpression,
  FunctionalCastExpression, MemberExpression, PostfixExpression, NamedCastExpression, TypeidExpression,
  UnaryExpression, AwaitExpression, SizeofExpression, SizeofPackExpression, AlignofExpression, NoexceptExpression,
  NewExpression, DeleteExpression, CastExpression, BinaryExpression, ConditionalExpression, AssignmentExpression,
  ThrowExpression, YieldExpression, PackExpansion, InitializerList, DesignatedInitializer, FieldDesignator,
  IndexDesignator, CompoundLiteralExpression, GenericSelection, GenericAssociation, StatementExpression,
  ExtensionExpression, DefinedExpression, LabeledStatement, CaseStatement, DefaultStatement, ExpressionStatement,
  CompoundStatement, IfStatement, SwitchStatement, WhileStatement, DoStatement, ForStatement, RangeForStatement,
  BreakStatement, ContinueStatement, ReturnStatement, CoReturnStatement, GotoStatement, TryStatement, Handler,
  AttributedStatement, ContractAssertStatement, SimpleDeclaration, InitDeclarator, FunctionDefinition, DefaultedBody,
  DeletedBody, MemberInitializer, VirtSpecifier, DeclSpecifier, ExplicitSpecifier, CvQualifier,
  PrimitiveTypeSpecifier, NamedTypeSpecifier, TypenameSpecifier, ClassSpecifier, MemberList, EnumSpecifier,
  EnumeratorList, Enumerator, DecltypeSpecifier, PlaceholderTypeSpecifier, TypeofSpecifier, AtomicTypeSpecifier,
  BitIntSpecifier, PackIndexingSpecifier, SpliceSpecifier, IdDeclarator, PackDeclarator, PointerDeclarator,
  ReferenceDeclarator, ArrayDeclarator, FunctionDeclarator, ParenthesizedDeclarator, StructuredBindingDeclarator,
  TypeId, ParameterDeclaration, EllipsisParameter, EqualInitializer, ParenthesizedInitializer, NoexceptSpecifier,
  ThrowSpecifier, PreconditionSpecifier, PostconditionSpecifier, NamespaceDefinition, NamespaceName,
  NamespaceAliasDefinition, UsingDirective, UsingDeclaration, UsingDeclarator, UsingEnumDeclaration, AliasDeclaration,
  StaticAssertDeclaration, AttributeDeclaration, EmptyDeclaration, LinkageSpecification, AsmDeclaration, AsmOperand,
  StandardAttributeSpecifier, Attribute, Annotation, AlignasSpecifier, GnuAttributeSpecifier, DeclspecSpecifier,
  ModuleDeclaration, GlobalModuleFragment, PrivateModuleFragment, ImportDeclaration, ExportDeclaration,
  AccessSpecifier, BaseSpecifier, FriendTypeDeclaration, TemplateDeclaration, TypeParameter,
  TemplateTemplateParameter, ConceptDefinition, ExplicitInstantiation, IncludeDirective, DefineDirective, IfDirective,
  IfdefDirective, ElifDirective, ElifdefDirective, ElseDirective, OtherDirective,
];

/** The language, whose `Builders` are typed from this module's kinds. */
export const LANGUAGE: Language<typeof Self> = new Language("Ccpp", KINDS, { base: { [CPP]: 1998, [C]: 1989 } });
