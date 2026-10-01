/**
 * Syntax: the abstract syntax of TypeScript and JavaScript, as one tree language.
 *
 * The kinds follow typescript-estree (TSESTree), the ESTree of TypeScript that ESLint and its tools read: the same
 * kinds with the same names and fields, in source order, but for fields whose names are keywords of Python or clash
 * with the framework's tag `kind`: `kind` is `declarationKind`, `methodKind`, `propertyKind` or `moduleKind`, and
 * `async`, `await`, `in` and `out` are `isAsync`, `isAwait`, `isIn` and `isOut`. Each kind and feature records where
 * it exists in two families (`SINCE`, `FEATURES`): ECMAScript, by edition year (ES2015 is 2015), and TypeScript, by
 * version (`100 * major + minor`: 5.9 is 509). Type syntax is TypeScript's alone; proposals that TypeScript implements
 * before an ECMAScript edition has them (decorators, `accessor`, `using`, `import defer`) are TypeScript's too. JSX is
 * an extension, outside every edition and version, which the standards made with `jsx` accept.
 *
 * Where TSESTree drops what a transpiler needs to see or a printer needs to write it back, the tree is concrete:
 *
 * - Literals keep their spelling: `Literal.raw` is the literal as written (`0x_FF`, `1_000n`, `'a\n'`, `/a/v`), and a
 *   template's parts are their raw text.
 * - Parentheses written in the source stay, as `ParenthesizedExpression` and `TSParenthesizedType`. Printing adds
 *   those a hand-built tree needs.
 * - Comments are kept where statements, class members, interface members and enum members are listed, as `Comment`;
 *   elsewhere they are dropped. A hashbang line is `Program.hashbang`.
 * - Lists hold no empty places: an array's hole (`[a, , b]`) is an `Elision`.
 *
 * Not represented: what follows from the rest (`ExpressionStatement.directive`, `ArrowFunctionExpression.expression`,
 * `Program.sourceType`, `TSModuleDeclaration.global`), what TSESTree keeps only for compatibility (`assertions`,
 * `TSEnumDeclaration.members`, `TSMappedType.typeParameter`, `TSImportType.argument`), and the modifier keywords
 * (`TSAbstractKeyword`, ...), which the parser never writes.
 */

import { Repr } from "@mbse/schemas/Framework";

import {
  article, type AttributeSpec, type Availability, type ChildSpec, choice, type Features, type Fields, flag, Language,
  many, Node, one, optional, optionalChoice, optionalText, text,
} from "../Framework/Syntax.js";

const { repr } = Repr;

export const ES = "ECMAScript";
export const TS = "TypeScript";

/** ECMAScript from the edition `year` on, and TypeScript from the version `ts` on. */
export function es(year: number, ts: number): Availability {
  return { [ES]: year, [TS]: ts };
}

/** TypeScript from `version` on (`100 * major + minor`); not ECMAScript. */
export function ts(version: number): Availability {
  return { [TS]: version };
}

/** A problem if the list `field` of `node` is empty. */
function needs(node: Node, field: string, what: string): string[] {
  return (node.field(field) as unknown[]).length > 0 ? [] : [`${article(node.kind().KIND)} needs ${what}`];
}

/** A problem if `name` is not an identifier, `$` counting as a letter. */
function identifierProblems(name: unknown): string[] {
  if (typeof name !== "string") return [];
  const valid = /^[\p{XID_Start}_]\p{XID_Continue}*$/u.test(name.replaceAll("$", "_"));
  return valid ? [] : [`${repr(name)} is not an identifier`];
}

// --- Choices ---

export const DECLARATION_KINDS = ["var", "let", "const", "using", "await using"] as const;
export type DeclarationKind = (typeof DECLARATION_KINDS)[number];
export const METHOD_KINDS = ["constructor", "method", "get", "set"] as const;
export type MethodKind = (typeof METHOD_KINDS)[number];
export const PROPERTY_KINDS = ["init", "get", "set"] as const;
export type PropertyKind = (typeof PROPERTY_KINDS)[number];
export const MODULE_KINDS = ["global", "module", "namespace"] as const;
export type ModuleKind = (typeof MODULE_KINDS)[number];
export const IMPORT_EXPORT_KINDS = ["type", "value"] as const;
export type ImportExportKind = (typeof IMPORT_EXPORT_KINDS)[number];
export const ACCESSIBILITYS = ["private", "protected", "public"] as const;
export type Accessibility = (typeof ACCESSIBILITYS)[number];
export const ASSIGNMENT_OPERATORS = [
  "=", "+=", "-=", "*=", "/=", "%=", "**=", "<<=", ">>=", ">>>=", "&=", "|=", "^=", "&&=", "||=", "??="
] as const;
export type AssignmentOperator = (typeof ASSIGNMENT_OPERATORS)[number];
export const BINARY_OPERATORS = [
  "==", "!=", "===", "!==", "<", "<=", ">", ">=", "<<", ">>", ">>>", "+", "-", "*", "/", "%", "**", "|", "^", "&",
  "in", "instanceof"
] as const;
export type BinaryOperator = (typeof BINARY_OPERATORS)[number];
export const LOGICAL_OPERATORS = ["&&", "||", "??"] as const;
export type LogicalOperator = (typeof LOGICAL_OPERATORS)[number];
export const UNARY_OPERATORS = ["-", "+", "!", "~", "typeof", "void", "delete"] as const;
export type UnaryOperator = (typeof UNARY_OPERATORS)[number];
export const UPDATE_OPERATORS = ["++", "--"] as const;
export type UpdateOperator = (typeof UPDATE_OPERATORS)[number];
export const TYPE_OPERATORS = ["keyof", "readonly", "unique"] as const;
export type TypeOperator = (typeof TYPE_OPERATORS)[number];
export const MAPPED_OPTIONALS = ["?", "+?", "-?"] as const;
export type MappedOptional = (typeof MAPPED_OPTIONALS)[number];
export const MAPPED_READONLYS = ["readonly", "+readonly", "-readonly"] as const;
export type MappedReadonly = (typeof MAPPED_READONLYS)[number];
export const PHASES = ["defer"] as const;
export type Phase = (typeof PHASES)[number];

// --- Categories ---

/** A statement or a declaration, where statements are listed; also a comment there. */
export abstract class Statement extends Node {}

/** An expression. */
export abstract class Expression extends Node {}

/** A destructuring pattern: what an assignment, a declaration or a parameter binds. */
export abstract class Pattern extends Node {}

/** A type. */
export abstract class TypeNode extends Node {}

/** A member of a class body. */
export abstract class ClassElement extends Node {}

/** A member of an interface or an object type. */
export abstract class TypeElement extends Node {}

// === Program, comments and names ===

const CommentSpec = {
  block: flag(),
  text: text(),
  trailing: flag(),
};
export interface Comment extends Fields<typeof CommentSpec> {}
/**
 * `// text`, or with `block` `/* text *\/`. `text` excludes the delimiters. A `trailing` comment ends the line of
 * the item before it.
 */
export class Comment extends Statement {
  static override SPEC = CommentSpec;
}

const ProgramSpec = {
  hashbang: optionalText(),
  body: many(() => [Statement]),
};
export interface Program extends Fields<typeof ProgramSpec> {}
/** A source file: `hashbang`, the text of a first line `#!...` without the `#!`, then its statements. */
export class Program extends Node {
  static override SPEC = ProgramSpec;
}

const IdentifierSpec = {
  decorators: many(() => [Decorator]),
  name: text(),
  optional: flag(),
  typeAnnotation: optional(() => [TSTypeAnnotation]),
};
export interface Identifier extends Fields<typeof IdentifierSpec> {}
/**
 * A name: a variable's, a property's, a label's or a type's. As a parameter or a binding, it may carry decorators,
 * `?` and a type annotation.
 */
export class Identifier extends Expression {
  static override SPEC = IdentifierSpec;
  static override FEATURES: Features = { optional: [[true, ts(100)]] };
  override check(): string[] {
    return identifierProblems(this.name);
  }
}

const PrivateIdentifierSpec = {
  name: text(),
};
export interface PrivateIdentifier extends Fields<typeof PrivateIdentifierSpec> {}
/** `#name`, a class's private member; `name` excludes the `#`. */
export class PrivateIdentifier extends Expression {
  static override SPEC = PrivateIdentifierSpec;
  static override SINCE: Availability | null = es(2022, 308);
  override check(): string[] {
    return identifierProblems(this.name);
  }
}

// === Literals and primary expressions ===

const LiteralSpec = {
  raw: text(),
};
export interface Literal extends Fields<typeof LiteralSpec> {}
/** A string, number, bigint, regular expression, boolean or `null` literal, as written. */
export class Literal extends Expression {
  static override SPEC = LiteralSpec;
  override check(): string[] {
    return this.raw !== "" ? [] : ["a Literal needs a raw"];
  }

  override features(): [string, Availability][] {
    const raw: unknown = this.raw;
    if (typeof raw !== "string") return [];
    if (/^[0-9]/.test(raw) && raw.endsWith("n")) return [["bigint Literal", es(2020, 302)]];
    if (raw.includes("_") && /^[0-9.]/.test(raw)) return [["Literal with numeric separators", es(2021, 207)]];
    return [];
  }
}

const TemplateElementSpec = {
  raw: text(),
  tail: flag(),
};
export interface TemplateElement extends Fields<typeof TemplateElementSpec> {}
/** Text of a template literal between its substitutions, as written; `tail` for the last. */
export class TemplateElement extends Node {
  static override SPEC = TemplateElementSpec;
}

const TemplateLiteralSpec = {
  quasis: many(() => [TemplateElement]),
  expressions: many(() => [Expression]),
};
export interface TemplateLiteral extends Fields<typeof TemplateLiteralSpec> {}
/** `` `quasi${expression}quasi` ``: the texts and the substitutions between them. */
export class TemplateLiteral extends Expression {
  static override SPEC = TemplateLiteralSpec;
  override check(): string[] {
    if (this.quasis.length === this.expressions.length + 1) return [];
    return ["a TemplateLiteral needs one more quasi than expressions"];
  }
}

const TaggedTemplateExpressionSpec = {
  tag: one(() => [Expression]),
  typeArguments: optional(() => [TSTypeParameterInstantiation]),
  quasi: one(() => [TemplateLiteral]),
};
export interface TaggedTemplateExpression extends Fields<typeof TaggedTemplateExpressionSpec> {}
/** `` tag<typeArguments>`...` ``. */
export class TaggedTemplateExpression extends Expression {
  static override SPEC = TaggedTemplateExpressionSpec;
}

/** `this`. */
export class ThisExpression extends Expression {}

/** `super`, called or with a member. */
export class Super extends Expression {}

const ParenthesizedExpressionSpec = {
  expression: one(() => [Expression, Pattern]),
};
export interface ParenthesizedExpression extends Fields<typeof ParenthesizedExpressionSpec> {}
/** `(expression)`: parentheses written in the source. */
export class ParenthesizedExpression extends Expression {
  static override SPEC = ParenthesizedExpressionSpec;
}

/** A hole in an array, as in `[a, , b]`. */
export class Elision extends Node {}

const SpreadElementSpec = {
  argument: one(() => [Expression]),
};
export interface SpreadElement extends Fields<typeof SpreadElementSpec> {}
/** `...argument` in an array, a call or an object. */
export class SpreadElement extends Node {
  static override SPEC = SpreadElementSpec;
}

const ArrayExpressionSpec = {
  elements: many(() => [Expression, SpreadElement, Elision]),
};
export interface ArrayExpression extends Fields<typeof ArrayExpressionSpec> {}
/** `[elements]`. */
export class ArrayExpression extends Expression {
  static override SPEC = ArrayExpressionSpec;
}

const PropertySpec = {
  propertyKind: choice(...PROPERTY_KINDS),
  computed: flag(),
  key: one(() => [Expression]),
  optional: flag(),
  method: flag(),
  shorthand: flag(),
  value: one(() => [Expression, Pattern, TSEmptyBodyFunctionExpression]),
};
export interface Property extends Fields<typeof PropertySpec> {}
/**
 * `key: value` in an object or an object pattern; a method (`method`), an accessor (`propertyKind` 'get' or
 * 'set'), or the shorthand `key` (`shorthand`).
 */
export class Property extends Node {
  static override SPEC = PropertySpec;
  static override FEATURES: Features = { optional: [[true, ts(100)]] };
}

const ObjectExpressionSpec = {
  properties: many(() => [Property, SpreadElement]),
};
export interface ObjectExpression extends Fields<typeof ObjectExpressionSpec> {}
/** `{properties}`. */
export class ObjectExpression extends Expression {
  static override SPEC = ObjectExpressionSpec;
}

const FunctionExpressionSpec = {
  isAsync: flag(),
  generator: flag(),
  id: optional(() => [Identifier]),
  typeParameters: optional(() => [TSTypeParameterDeclaration]),
  params: many(() => [Identifier, Pattern, TSParameterProperty]),
  returnType: optional(() => [TSTypeAnnotation]),
  body: one(() => [BlockStatement]),
};
export interface FunctionExpression extends Fields<typeof FunctionExpressionSpec> {}
/** `async function* id<typeParameters>(params): returnType { body }`. */
export class FunctionExpression extends Expression {
  static override SPEC = FunctionExpressionSpec;
}

const ArrowFunctionExpressionSpec = {
  isAsync: flag(),
  typeParameters: optional(() => [TSTypeParameterDeclaration]),
  params: many(() => [Identifier, Pattern]),
  returnType: optional(() => [TSTypeAnnotation]),
  body: one(() => [BlockStatement, Expression]),
};
export interface ArrowFunctionExpression extends Fields<typeof ArrowFunctionExpressionSpec> {}
/** `async <typeParameters>(params): returnType => body`; a body that is an expression is its value. */
export class ArrowFunctionExpression extends Expression {
  static override SPEC = ArrowFunctionExpressionSpec;
  static override SINCE: Availability | null = es(2015, 100);
}

const ClassExpressionSpec = {
  decorators: many(() => [Decorator]),
  id: optional(() => [Identifier]),
  typeParameters: optional(() => [TSTypeParameterDeclaration]),
  superClass: optional(() => [Expression]),
  superTypeArguments: optional(() => [TSTypeParameterInstantiation]),
  implements: many(() => [TSClassImplements]),
  body: one(() => [ClassBody]),
};
export interface ClassExpression extends Fields<typeof ClassExpressionSpec> {}
/** `class id<typeParameters> extends superClass<superTypeArguments> implements ... { body }`, as an expression. */
export class ClassExpression extends Expression {
  static override SPEC = ClassExpressionSpec;
  static override SINCE: Availability | null = es(2015, 106);
}

const MetaPropertySpec = {
  meta: one(() => [Identifier]),
  property: one(() => [Identifier]),
};
export interface MetaProperty extends Fields<typeof MetaPropertySpec> {}
/** `new.target` or `import.meta`. */
export class MetaProperty extends Expression {
  static override SPEC = MetaPropertySpec;
  override features(): [string, Availability][] {
    const meta = this.meta instanceof Identifier ? this.meta.name : null;
    return meta === "import" ? [["import.meta", es(2020, 209)]] : [];
  }
}

// === Operations ===

const MemberExpressionSpec = {
  object: one(() => [Expression]),
  optional: flag(),
  computed: flag(),
  property: one(() => [Expression]),
};
export interface MemberExpression extends Fields<typeof MemberExpressionSpec> {}
/** `object.property`, `object[property]` (`computed`), or with `optional` `object?.property`. */
export class MemberExpression extends Expression {
  static override SPEC = MemberExpressionSpec;
  override features(): [string, Availability][] {
    return this.optional ? [["MemberExpression with ?.", es(2020, 307)]] : [];
  }
}

const CallExpressionSpec = {
  callee: one(() => [Expression]),
  optional: flag(),
  typeArguments: optional(() => [TSTypeParameterInstantiation]),
  arguments: many(() => [Expression, SpreadElement]),
};
export interface CallExpression extends Fields<typeof CallExpressionSpec> {}
/** `callee<typeArguments>(arguments)`, or with `optional` `callee?.(arguments)`. */
export class CallExpression extends Expression {
  static override SPEC = CallExpressionSpec;
  override features(): [string, Availability][] {
    return this.optional ? [["CallExpression with ?.", es(2020, 307)]] : [];
  }
}

const ChainExpressionSpec = {
  expression: one(() => [Expression]),
};
export interface ChainExpression extends Fields<typeof ChainExpressionSpec> {}
/** An optional chain, `a?.b.c()`, whose members and calls short-circuit together. */
export class ChainExpression extends Expression {
  static override SPEC = ChainExpressionSpec;
  static override SINCE: Availability | null = es(2020, 307);
}

const NewExpressionSpec = {
  callee: one(() => [Expression]),
  typeArguments: optional(() => [TSTypeParameterInstantiation]),
  arguments: many(() => [Expression, SpreadElement]),
};
export interface NewExpression extends Fields<typeof NewExpressionSpec> {}
/** `new callee<typeArguments>(arguments)`. */
export class NewExpression extends Expression {
  static override SPEC = NewExpressionSpec;
}

const ImportExpressionSpec = {
  phase: optionalChoice(...PHASES),
  source: one(() => [Expression]),
  options: optional(() => [Expression]),
};
export interface ImportExpression extends Fields<typeof ImportExpressionSpec> {}
/** `import(source, options)`, or with `phase` `import.defer(source)`. */
export class ImportExpression extends Expression {
  static override SPEC = ImportExpressionSpec;
  static override SINCE: Availability | null = es(2020, 204);
  static override FEATURES: Features = { phase: [["defer", ts(509)]], options: [[true, es(2025, 503)]] };
}

const UpdateExpressionSpec = {
  operator: choice(...UPDATE_OPERATORS),
  prefix: flag(),
  argument: one(() => [Expression]),
};
export interface UpdateExpression extends Fields<typeof UpdateExpressionSpec> {}
/** `++argument` (`prefix`) or `argument--`. */
export class UpdateExpression extends Expression {
  static override SPEC = UpdateExpressionSpec;
}

const UnaryExpressionSpec = {
  operator: choice(...UNARY_OPERATORS),
  argument: one(() => [Expression]),
};
export interface UnaryExpression extends Fields<typeof UnaryExpressionSpec> {}
/** `operator argument`: `-x`, `!x`, `typeof x`, `void x`, `delete x`. */
export class UnaryExpression extends Expression {
  static override SPEC = UnaryExpressionSpec;
}

const AwaitExpressionSpec = {
  argument: one(() => [Expression]),
};
export interface AwaitExpression extends Fields<typeof AwaitExpressionSpec> {}
/** `await argument`. */
export class AwaitExpression extends Expression {
  static override SPEC = AwaitExpressionSpec;
  static override SINCE: Availability | null = es(2017, 107);
}

const BinaryExpressionSpec = {
  left: one(() => [Expression]),
  operator: choice(...BINARY_OPERATORS),
  right: one(() => [Expression]),
};
export interface BinaryExpression extends Fields<typeof BinaryExpressionSpec> {}
/** `left operator right`; `left` is a `PrivateIdentifier` in `#x in object`. */
export class BinaryExpression extends Expression {
  static override SPEC = BinaryExpressionSpec;
  static override FEATURES: Features = { operator: [["**", es(2016, 107)]] };
  override features(): [string, Availability][] {
    return this.left instanceof PrivateIdentifier ? [["BinaryExpression of #name in", es(2022, 405)]] : [];
  }
}

const LogicalExpressionSpec = {
  left: one(() => [Expression]),
  operator: choice(...LOGICAL_OPERATORS),
  right: one(() => [Expression]),
};
export interface LogicalExpression extends Fields<typeof LogicalExpressionSpec> {}
/** `left && right`, `left || right` or `left ?? right`. */
export class LogicalExpression extends Expression {
  static override SPEC = LogicalExpressionSpec;
  static override FEATURES: Features = { operator: [["??", es(2020, 307)]] };
}

const ConditionalExpressionSpec = {
  test: one(() => [Expression]),
  consequent: one(() => [Expression]),
  alternate: one(() => [Expression]),
};
export interface ConditionalExpression extends Fields<typeof ConditionalExpressionSpec> {}
/** `test ? consequent : alternate`. */
export class ConditionalExpression extends Expression {
  static override SPEC = ConditionalExpressionSpec;
}

const AssignmentExpressionSpec = {
  left: one(() => [Expression, Pattern]),
  operator: choice(...ASSIGNMENT_OPERATORS),
  right: one(() => [Expression]),
};
export interface AssignmentExpression extends Fields<typeof AssignmentExpressionSpec> {}
/** `left operator right`. */
export class AssignmentExpression extends Expression {
  static override SPEC = AssignmentExpressionSpec;
  static override FEATURES: Features = {
    operator: [["**=", es(2016, 107)], ["&&=", es(2021, 400)], ["||=", es(2021, 400)], ["??=", es(2021, 400)]],
  };
}

const SequenceExpressionSpec = {
  expressions: many(() => [Expression]),
};
export interface SequenceExpression extends Fields<typeof SequenceExpressionSpec> {}
/** `expression, expression`. */
export class SequenceExpression extends Expression {
  static override SPEC = SequenceExpressionSpec;
  override check(): string[] {
    return this.expressions.length > 1 ? [] : ["a SequenceExpression needs two expressions"];
  }
}

const YieldExpressionSpec = {
  delegate: flag(),
  argument: optional(() => [Expression]),
};
export interface YieldExpression extends Fields<typeof YieldExpressionSpec> {}
/** `yield argument`, or with `delegate` `yield* argument`. */
export class YieldExpression extends Expression {
  static override SPEC = YieldExpressionSpec;
  static override SINCE: Availability | null = es(2015, 106);
}

// --- TypeScript's expressions ---

const TSAsExpressionSpec = {
  expression: one(() => [Expression]),
  typeAnnotation: one(() => [TypeNode]),
};
export interface TSAsExpression extends Fields<typeof TSAsExpressionSpec> {}
/** `expression as typeAnnotation`. */
export class TSAsExpression extends Expression {
  static override SPEC = TSAsExpressionSpec;
  static override SINCE: Availability | null = ts(106);
}

const TSSatisfiesExpressionSpec = {
  expression: one(() => [Expression]),
  typeAnnotation: one(() => [TypeNode]),
};
export interface TSSatisfiesExpression extends Fields<typeof TSSatisfiesExpressionSpec> {}
/** `expression satisfies typeAnnotation`. */
export class TSSatisfiesExpression extends Expression {
  static override SPEC = TSSatisfiesExpressionSpec;
  static override SINCE: Availability | null = ts(409);
}

const TSTypeAssertionSpec = {
  typeAnnotation: one(() => [TypeNode]),
  expression: one(() => [Expression]),
};
export interface TSTypeAssertion extends Fields<typeof TSTypeAssertionSpec> {}
/** `<typeAnnotation>expression`, which `.tsx` files do not have. */
export class TSTypeAssertion extends Expression {
  static override SPEC = TSTypeAssertionSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSNonNullExpressionSpec = {
  expression: one(() => [Expression]),
};
export interface TSNonNullExpression extends Fields<typeof TSNonNullExpressionSpec> {}
/** `expression!`. */
export class TSNonNullExpression extends Expression {
  static override SPEC = TSNonNullExpressionSpec;
  static override SINCE: Availability | null = ts(200);
}

const TSInstantiationExpressionSpec = {
  expression: one(() => [Expression]),
  typeArguments: one(() => [TSTypeParameterInstantiation]),
};
export interface TSInstantiationExpression extends Fields<typeof TSInstantiationExpressionSpec> {}
/** `expression<typeArguments>`, without a call. */
export class TSInstantiationExpression extends Expression {
  static override SPEC = TSInstantiationExpressionSpec;
  static override SINCE: Availability | null = ts(407);
}

// === Patterns ===

const ArrayPatternSpec = {
  decorators: many(() => [Decorator]),
  elements: many(() => [Pattern, Expression, Elision]),
  optional: flag(),
  typeAnnotation: optional(() => [TSTypeAnnotation]),
};
export interface ArrayPattern extends Fields<typeof ArrayPatternSpec> {}
/** `[elements]: typeAnnotation`, destructuring. */
export class ArrayPattern extends Pattern {
  static override SPEC = ArrayPatternSpec;
  static override SINCE: Availability | null = es(2015, 105);
  static override FEATURES: Features = { optional: [[true, ts(100)]] };
}

const ObjectPatternSpec = {
  decorators: many(() => [Decorator]),
  properties: many(() => [Property, RestElement]),
  optional: flag(),
  typeAnnotation: optional(() => [TSTypeAnnotation]),
};
export interface ObjectPattern extends Fields<typeof ObjectPatternSpec> {}
/** `{properties}: typeAnnotation`, destructuring. */
export class ObjectPattern extends Pattern {
  static override SPEC = ObjectPatternSpec;
  static override SINCE: Availability | null = es(2015, 105);
  static override FEATURES: Features = { optional: [[true, ts(100)]] };
}

const AssignmentPatternSpec = {
  decorators: many(() => [Decorator]),
  left: one(() => [Identifier, Pattern, Expression]),
  optional: flag(),
  typeAnnotation: optional(() => [TSTypeAnnotation]),
  right: one(() => [Expression]),
};
export interface AssignmentPattern extends Fields<typeof AssignmentPatternSpec> {}
/** `left = right`: a binding with a default. */
export class AssignmentPattern extends Pattern {
  static override SPEC = AssignmentPatternSpec;
  static override SINCE: Availability | null = es(2015, 105);
  static override FEATURES: Features = { optional: [[true, ts(100)]] };
}

const RestElementSpec = {
  decorators: many(() => [Decorator]),
  argument: one(() => [Identifier, Pattern, Expression]),
  optional: flag(),
  typeAnnotation: optional(() => [TSTypeAnnotation]),
  value: optional(() => [AssignmentPattern]),
};
export interface RestElement extends Fields<typeof RestElementSpec> {}
/** `...argument: typeAnnotation`, the rest of an array, an object or a parameter list. */
export class RestElement extends Pattern {
  static override SPEC = RestElementSpec;
  static override SINCE: Availability | null = es(2015, 105);
  static override FEATURES: Features = { optional: [[true, ts(100)]] };
}

// === Statements ===

const ExpressionStatementSpec = {
  expression: one(() => [Expression]),
};
export interface ExpressionStatement extends Fields<typeof ExpressionStatementSpec> {}
/** `expression;`; also a directive, `'use strict';`. */
export class ExpressionStatement extends Statement {
  static override SPEC = ExpressionStatementSpec;
}

const BlockStatementSpec = {
  body: many(() => [Statement]),
};
export interface BlockStatement extends Fields<typeof BlockStatementSpec> {}
/** `{ body }`. */
export class BlockStatement extends Statement {
  static override SPEC = BlockStatementSpec;
}

/** `;`. */
export class EmptyStatement extends Statement {}

/** `debugger;`. */
export class DebuggerStatement extends Statement {}

const WithStatementSpec = {
  object: one(() => [Expression]),
  body: one(() => [Statement]),
};
export interface WithStatement extends Fields<typeof WithStatementSpec> {}
/** `with (object) body`, which strict code does not have. */
export class WithStatement extends Statement {
  static override SPEC = WithStatementSpec;
}

const ReturnStatementSpec = {
  argument: optional(() => [Expression]),
};
export interface ReturnStatement extends Fields<typeof ReturnStatementSpec> {}
/** `return argument;`. */
export class ReturnStatement extends Statement {
  static override SPEC = ReturnStatementSpec;
}

const LabeledStatementSpec = {
  label: one(() => [Identifier]),
  body: one(() => [Statement]),
};
export interface LabeledStatement extends Fields<typeof LabeledStatementSpec> {}
/** `label: body`. */
export class LabeledStatement extends Statement {
  static override SPEC = LabeledStatementSpec;
}

const BreakStatementSpec = {
  label: optional(() => [Identifier]),
};
export interface BreakStatement extends Fields<typeof BreakStatementSpec> {}
/** `break label;`. */
export class BreakStatement extends Statement {
  static override SPEC = BreakStatementSpec;
}

const ContinueStatementSpec = {
  label: optional(() => [Identifier]),
};
export interface ContinueStatement extends Fields<typeof ContinueStatementSpec> {}
/** `continue label;`. */
export class ContinueStatement extends Statement {
  static override SPEC = ContinueStatementSpec;
}

const IfStatementSpec = {
  test: one(() => [Expression]),
  consequent: one(() => [Statement]),
  alternate: optional(() => [Statement]),
};
export interface IfStatement extends Fields<typeof IfStatementSpec> {}
/** `if (test) consequent else alternate`. */
export class IfStatement extends Statement {
  static override SPEC = IfStatementSpec;
  override check(): string[] {
    if (this.alternate === null) return [];
    let last: unknown = this.consequent;
    while (
      last instanceof IfStatement || last instanceof WhileStatement || last instanceof ForStatement ||
      last instanceof ForInStatement || last instanceof ForOfStatement || last instanceof LabeledStatement ||
      last instanceof WithStatement
    ) {
      if (last instanceof IfStatement) {
        if (last.alternate === null) return ["an if without else ends the consequent, and would take the else"];
        last = last.alternate;
      } else {
        last = last.body;
      }
    }
    return [];
  }
}

const SwitchCaseSpec = {
  test: optional(() => [Expression]),
  consequent: many(() => [Statement]),
};
export interface SwitchCase extends Fields<typeof SwitchCaseSpec> {}
/** `case test: consequent`, or `default: consequent` without `test`. */
export class SwitchCase extends Node {
  static override SPEC = SwitchCaseSpec;
}

const SwitchStatementSpec = {
  discriminant: one(() => [Expression]),
  cases: many(() => [SwitchCase]),
};
export interface SwitchStatement extends Fields<typeof SwitchStatementSpec> {}
/** `switch (discriminant) { cases }`. */
export class SwitchStatement extends Statement {
  static override SPEC = SwitchStatementSpec;
}

const ThrowStatementSpec = {
  argument: one(() => [Expression]),
};
export interface ThrowStatement extends Fields<typeof ThrowStatementSpec> {}
/** `throw argument;`. */
export class ThrowStatement extends Statement {
  static override SPEC = ThrowStatementSpec;
}

const CatchClauseSpec = {
  param: optional(() => [Identifier, Pattern]),
  body: one(() => [BlockStatement]),
};
export interface CatchClause extends Fields<typeof CatchClauseSpec> {}
/** `catch (param) body`, or `catch body` without `param`. */
export class CatchClause extends Node {
  static override SPEC = CatchClauseSpec;
  override features(): [string, Availability][] {
    return this.param === null ? [["CatchClause without a param", es(2019, 205)]] : [];
  }
}

const TryStatementSpec = {
  block: one(() => [BlockStatement]),
  handler: optional(() => [CatchClause]),
  finalizer: optional(() => [BlockStatement]),
};
export interface TryStatement extends Fields<typeof TryStatementSpec> {}
/** `try block catch... handler finally finalizer`. */
export class TryStatement extends Statement {
  static override SPEC = TryStatementSpec;
  override check(): string[] {
    return this.handler !== null || this.finalizer !== null ? [] : ["a TryStatement needs a handler or a finalizer"];
  }
}

const WhileStatementSpec = {
  test: one(() => [Expression]),
  body: one(() => [Statement]),
};
export interface WhileStatement extends Fields<typeof WhileStatementSpec> {}
/** `while (test) body`. */
export class WhileStatement extends Statement {
  static override SPEC = WhileStatementSpec;
}

const DoWhileStatementSpec = {
  body: one(() => [Statement]),
  test: one(() => [Expression]),
};
export interface DoWhileStatement extends Fields<typeof DoWhileStatementSpec> {}
/** `do body while (test);`. */
export class DoWhileStatement extends Statement {
  static override SPEC = DoWhileStatementSpec;
}

const ForStatementSpec = {
  init: optional(() => [VariableDeclaration, Expression]),
  test: optional(() => [Expression]),
  update: optional(() => [Expression]),
  body: one(() => [Statement]),
};
export interface ForStatement extends Fields<typeof ForStatementSpec> {}
/** `for (init; test; update) body`. */
export class ForStatement extends Statement {
  static override SPEC = ForStatementSpec;
}

const ForInStatementSpec = {
  left: one(() => [VariableDeclaration, Expression, Pattern]),
  right: one(() => [Expression]),
  body: one(() => [Statement]),
};
export interface ForInStatement extends Fields<typeof ForInStatementSpec> {}
/** `for (left in right) body`. */
export class ForInStatement extends Statement {
  static override SPEC = ForInStatementSpec;
}

const ForOfStatementSpec = {
  isAwait: flag(),
  left: one(() => [VariableDeclaration, Expression, Pattern]),
  right: one(() => [Expression]),
  body: one(() => [Statement]),
};
export interface ForOfStatement extends Fields<typeof ForOfStatementSpec> {}
/** `for (left of right) body`, or with `isAwait` `for await (...)`. */
export class ForOfStatement extends Statement {
  static override SPEC = ForOfStatementSpec;
  static override SINCE: Availability | null = es(2015, 105);
  static override FEATURES: Features = { isAwait: [[true, es(2018, 203)]] };
}

const VariableDeclaratorSpec = {
  id: one(() => [Identifier, Pattern]),
  definite: flag(),
  init: optional(() => [Expression]),
};
export interface VariableDeclarator extends Fields<typeof VariableDeclaratorSpec> {}
/** `id: type = init`, or with `definite` `id!: type`. */
export class VariableDeclarator extends Node {
  static override SPEC = VariableDeclaratorSpec;
  static override FEATURES: Features = { definite: [[true, ts(207)]] };
  override check(): string[] {
    if (this.definite && !(this.id instanceof Identifier && this.id.typeAnnotation !== null)) {
      return ["definite needs a name with a type annotation"];
    }
    return [];
  }
}

const VariableDeclarationSpec = {
  declare: flag(),
  declarationKind: choice(...DECLARATION_KINDS),
  declarations: many(() => [VariableDeclarator]),
};
export interface VariableDeclaration extends Fields<typeof VariableDeclarationSpec> {}
/** `declare kind declarations;`, `kind` being `var`, `let`, `const`, `using` or `await using`. */
export class VariableDeclaration extends Statement {
  static override SPEC = VariableDeclarationSpec;
  static override FEATURES: Features = {
    declarationKind: [["let", es(2015, 105)], ["const", es(2015, 105)], ["using", ts(502)], ["await using", ts(502)]],
    declare: [[true, ts(100)]],
  };
  override check(): string[] {
    return needs(this, "declarations", "a declarator");
  }
}

const FunctionDeclarationSpec = {
  isAsync: flag(),
  generator: flag(),
  id: optional(() => [Identifier]),
  typeParameters: optional(() => [TSTypeParameterDeclaration]),
  params: many(() => [Identifier, Pattern, TSParameterProperty]),
  returnType: optional(() => [TSTypeAnnotation]),
  body: one(() => [BlockStatement]),
};
export interface FunctionDeclaration extends Fields<typeof FunctionDeclarationSpec> {}
/** `async function* id<typeParameters>(params): returnType { body }`. */
export class FunctionDeclaration extends Statement {
  static override SPEC = FunctionDeclarationSpec;
  static override FEATURES: Features = {
    isAsync: [[true, es(2017, 107)]],
    generator: [[true, es(2015, 106)]],
    typeParameters: [[true, ts(100)]],
    returnType: [[true, ts(100)]],
  };
}

const TSDeclareFunctionSpec = {
  declare: flag(),
  isAsync: flag(),
  generator: flag(),
  id: optional(() => [Identifier]),
  typeParameters: optional(() => [TSTypeParameterDeclaration]),
  params: many(() => [Identifier, Pattern, TSParameterProperty]),
  returnType: optional(() => [TSTypeAnnotation]),
};
export interface TSDeclareFunction extends Fields<typeof TSDeclareFunctionSpec> {}
/** `declare function id<typeParameters>(params): returnType;`, or an overload's signature, without a body. */
export class TSDeclareFunction extends Statement {
  static override SPEC = TSDeclareFunctionSpec;
  static override SINCE: Availability | null = ts(100);
}

const DecoratorSpec = {
  expression: one(() => [Expression]),
};
export interface Decorator extends Fields<typeof DecoratorSpec> {}
/** `@expression`. */
export class Decorator extends Node {
  static override SPEC = DecoratorSpec;
  static override SINCE: Availability | null = ts(105);
}

const ClassBodySpec = {
  body: many(() => [ClassElement, TSIndexSignature, Comment]),
};
export interface ClassBody extends Fields<typeof ClassBodySpec> {}
/** `{ body }`: a class's members. */
export class ClassBody extends Node {
  static override SPEC = ClassBodySpec;
}

const ClassDeclarationSpec = {
  decorators: many(() => [Decorator]),
  declare: flag(),
  abstract: flag(),
  id: optional(() => [Identifier]),
  typeParameters: optional(() => [TSTypeParameterDeclaration]),
  superClass: optional(() => [Expression]),
  superTypeArguments: optional(() => [TSTypeParameterInstantiation]),
  implements: many(() => [TSClassImplements]),
  body: one(() => [ClassBody]),
};
export interface ClassDeclaration extends Fields<typeof ClassDeclarationSpec> {}
/**
 * `@decorators abstract class id<typeParameters> extends superClass<superTypeArguments> implements ... { body }`;
 * without `id`, the default export's.
 */
export class ClassDeclaration extends Statement {
  static override SPEC = ClassDeclarationSpec;
  static override SINCE: Availability | null = es(2015, 100);
  static override FEATURES: Features = {
    abstract: [[true, ts(106)]],
    declare: [[true, ts(100)]],
    implements: [[true, ts(100)]],
  };
}

const StaticBlockSpec = {
  body: many(() => [Statement]),
};
export interface StaticBlock extends Fields<typeof StaticBlockSpec> {}
/** `static { body }`. */
export class StaticBlock extends ClassElement {
  static override SPEC = StaticBlockSpec;
  static override SINCE: Availability | null = es(2022, 404);
}

const MethodDefinitionSpec = {
  decorators: many(() => [Decorator]),
  accessibility: optionalChoice(...ACCESSIBILITYS),
  static: flag(),
  override: flag(),
  methodKind: choice(...METHOD_KINDS),
  computed: flag(),
  key: one(() => [Expression]),
  optional: flag(),
  value: one(() => [FunctionExpression, TSEmptyBodyFunctionExpression]),
};
export interface MethodDefinition extends Fields<typeof MethodDefinitionSpec> {}
/**
 * A class's method: `@decorators accessibility static override kind key?<...>(...) { ... }`; `methodKind` is
 * 'constructor', 'method', 'get' or 'set'.
 */
export class MethodDefinition extends ClassElement {
  static override SPEC = MethodDefinitionSpec;
  static override FEATURES: Features = {
    override: [[true, ts(403)]],
    accessibility: [[true, ts(100)]],
    optional: [[true, ts(200)]],
  };
}

const TSAbstractMethodDefinitionSpec = {
  decorators: many(() => [Decorator]),
  accessibility: optionalChoice(...ACCESSIBILITYS),
  static: flag(),
  override: flag(),
  methodKind: choice(...METHOD_KINDS),
  computed: flag(),
  key: one(() => [Expression]),
  optional: flag(),
  value: one(() => [FunctionExpression, TSEmptyBodyFunctionExpression]),
};
export interface TSAbstractMethodDefinition extends Fields<typeof TSAbstractMethodDefinitionSpec> {}
/** An `abstract` method, without a body. */
export class TSAbstractMethodDefinition extends ClassElement {
  static override SPEC = TSAbstractMethodDefinitionSpec;
  static override SINCE: Availability | null = ts(106);
}

const TSEmptyBodyFunctionExpressionSpec = {
  isAsync: flag(),
  generator: flag(),
  typeParameters: optional(() => [TSTypeParameterDeclaration]),
  params: many(() => [Identifier, Pattern, TSParameterProperty]),
  returnType: optional(() => [TSTypeAnnotation]),
};
export interface TSEmptyBodyFunctionExpression extends Fields<typeof TSEmptyBodyFunctionExpressionSpec> {}
/** The signature of a method without a body: an overload's, an abstract one's, or a declared class's. */
export class TSEmptyBodyFunctionExpression extends Node {
  static override SPEC = TSEmptyBodyFunctionExpressionSpec;
  static override SINCE: Availability | null = ts(100);
}

const PropertyDefinitionSpec = {
  decorators: many(() => [Decorator]),
  declare: flag(),
  accessibility: optionalChoice(...ACCESSIBILITYS),
  static: flag(),
  override: flag(),
  readonly: flag(),
  computed: flag(),
  key: one(() => [Expression]),
  optional: flag(),
  definite: flag(),
  typeAnnotation: optional(() => [TSTypeAnnotation]),
  value: optional(() => [Expression]),
};
export interface PropertyDefinition extends Fields<typeof PropertyDefinitionSpec> {}
/** A class's field: `@decorators declare accessibility static override readonly key?!: type = value;`. */
export class PropertyDefinition extends ClassElement {
  static override SPEC = PropertyDefinitionSpec;
  static override SINCE: Availability | null = es(2022, 100);
  static override FEATURES: Features = {
    declare: [[true, ts(307)]],
    accessibility: [[true, ts(100)]],
    readonly: [[true, ts(200)]],
    override: [[true, ts(403)]],
    optional: [[true, ts(200)]],
    definite: [[true, ts(207)]],
    typeAnnotation: [[true, ts(100)]],
  };
}

const TSAbstractPropertyDefinitionSpec = {
  decorators: many(() => [Decorator]),
  declare: flag(),
  accessibility: optionalChoice(...ACCESSIBILITYS),
  static: flag(),
  override: flag(),
  readonly: flag(),
  computed: flag(),
  key: one(() => [Expression]),
  optional: flag(),
  definite: flag(),
  typeAnnotation: optional(() => [TSTypeAnnotation]),
  value: optional(() => [Expression]),
};
export interface TSAbstractPropertyDefinition extends Fields<typeof TSAbstractPropertyDefinitionSpec> {}
/** An `abstract` field, without a value. */
export class TSAbstractPropertyDefinition extends ClassElement {
  static override SPEC = TSAbstractPropertyDefinitionSpec;
  static override SINCE: Availability | null = ts(200);
}

const AccessorPropertySpec = {
  decorators: many(() => [Decorator]),
  declare: flag(),
  accessibility: optionalChoice(...ACCESSIBILITYS),
  static: flag(),
  override: flag(),
  readonly: flag(),
  computed: flag(),
  key: one(() => [Expression]),
  optional: flag(),
  definite: flag(),
  typeAnnotation: optional(() => [TSTypeAnnotation]),
  value: optional(() => [Expression]),
};
export interface AccessorProperty extends Fields<typeof AccessorPropertySpec> {}
/** `accessor key: type = value;`, a field with a getter and a setter. */
export class AccessorProperty extends ClassElement {
  static override SPEC = AccessorPropertySpec;
  static override SINCE: Availability | null = ts(409);
}

const TSAbstractAccessorPropertySpec = {
  decorators: many(() => [Decorator]),
  declare: flag(),
  accessibility: optionalChoice(...ACCESSIBILITYS),
  static: flag(),
  override: flag(),
  readonly: flag(),
  computed: flag(),
  key: one(() => [Expression]),
  optional: flag(),
  definite: flag(),
  typeAnnotation: optional(() => [TSTypeAnnotation]),
  value: optional(() => [Expression]),
};
export interface TSAbstractAccessorProperty extends Fields<typeof TSAbstractAccessorPropertySpec> {}
/** `abstract accessor key: type;`. */
export class TSAbstractAccessorProperty extends ClassElement {
  static override SPEC = TSAbstractAccessorPropertySpec;
  static override SINCE: Availability | null = ts(409);
}

const TSParameterPropertySpec = {
  decorators: many(() => [Decorator]),
  accessibility: optionalChoice(...ACCESSIBILITYS),
  static: flag(),
  override: flag(),
  readonly: flag(),
  parameter: one(() => [Identifier, AssignmentPattern]),
};
export interface TSParameterProperty extends Fields<typeof TSParameterPropertySpec> {}
/** A constructor's parameter that declares a field: `accessibility static override readonly parameter`. */
export class TSParameterProperty extends Node {
  static override SPEC = TSParameterPropertySpec;
  static override SINCE: Availability | null = ts(100);
}

// === Modules ===

const ImportAttributeSpec = {
  key: one(() => [Identifier, Literal]),
  value: one(() => [Literal]),
};
export interface ImportAttribute extends Fields<typeof ImportAttributeSpec> {}
/** `key: value` in `with { ... }`. */
export class ImportAttribute extends Node {
  static override SPEC = ImportAttributeSpec;
}

const ImportSpecifierSpec = {
  importKind: choice(...IMPORT_EXPORT_KINDS),
  imported: one(() => [Identifier, Literal]),
  local: one(() => [Identifier]),
};
export interface ImportSpecifier extends Fields<typeof ImportSpecifierSpec> {}
/** `imported as local`, or with `importKind` 'type' `type imported as local`. */
export class ImportSpecifier extends Node {
  static override SPEC = ImportSpecifierSpec;
  static override FEATURES: Features = { importKind: [["type", ts(405)]] };
}

const ImportDefaultSpecifierSpec = {
  local: one(() => [Identifier]),
};
export interface ImportDefaultSpecifier extends Fields<typeof ImportDefaultSpecifierSpec> {}
/** `local`, the default export's binding. */
export class ImportDefaultSpecifier extends Node {
  static override SPEC = ImportDefaultSpecifierSpec;
}

const ImportNamespaceSpecifierSpec = {
  local: one(() => [Identifier]),
};
export interface ImportNamespaceSpecifier extends Fields<typeof ImportNamespaceSpecifierSpec> {}
/** `* as local`. */
export class ImportNamespaceSpecifier extends Node {
  static override SPEC = ImportNamespaceSpecifierSpec;
}

const ImportDeclarationSpec = {
  importKind: choice(...IMPORT_EXPORT_KINDS),
  phase: optionalChoice(...PHASES),
  specifiers: many(() => [ImportDefaultSpecifier, ImportNamespaceSpecifier, ImportSpecifier]),
  source: one(() => [Literal]),
  attributes: many(() => [ImportAttribute]),
};
export interface ImportDeclaration extends Fields<typeof ImportDeclarationSpec> {}
/** `import type defer specifiers from source with { attributes };`, or `import source;` without specifiers. */
export class ImportDeclaration extends Statement {
  static override SPEC = ImportDeclarationSpec;
  static override SINCE: Availability | null = es(2015, 105);
  static override FEATURES: Features = {
    importKind: [["type", ts(308)]],
    phase: [["defer", ts(509)]],
    attributes: [[true, es(2025, 503)]],
  };
}

const ExportSpecifierSpec = {
  exportKind: choice(...IMPORT_EXPORT_KINDS),
  local: one(() => [Identifier, Literal]),
  exported: one(() => [Identifier, Literal]),
};
export interface ExportSpecifier extends Fields<typeof ExportSpecifierSpec> {}
/** `local as exported`, or with `exportKind` 'type' `type local as exported`. */
export class ExportSpecifier extends Node {
  static override SPEC = ExportSpecifierSpec;
  static override FEATURES: Features = { exportKind: [["type", ts(405)]] };
}

const ExportNamedDeclarationSpec = {
  exportKind: choice(...IMPORT_EXPORT_KINDS),
  declaration: optional(() => [Statement]),
  specifiers: many(() => [ExportSpecifier]),
  source: optional(() => [Literal]),
  attributes: many(() => [ImportAttribute]),
};
export interface ExportNamedDeclaration extends Fields<typeof ExportNamedDeclarationSpec> {}
/** `export declaration`, or `export type { specifiers } from source with { attributes };`. */
export class ExportNamedDeclaration extends Statement {
  static override SPEC = ExportNamedDeclarationSpec;
  static override SINCE: Availability | null = es(2015, 105);
  static override FEATURES: Features = { exportKind: [["type", ts(308)]], attributes: [[true, es(2025, 503)]] };
}

const ExportDefaultDeclarationSpec = {
  declaration: one(() => [Statement, Expression]),
};
export interface ExportDefaultDeclaration extends Fields<typeof ExportDefaultDeclarationSpec> {}
/** `export default declaration`. */
export class ExportDefaultDeclaration extends Statement {
  static override SPEC = ExportDefaultDeclarationSpec;
  static override SINCE: Availability | null = es(2015, 105);
}

const ExportAllDeclarationSpec = {
  exportKind: choice(...IMPORT_EXPORT_KINDS),
  exported: optional(() => [Identifier, Literal]),
  source: one(() => [Literal]),
  attributes: many(() => [ImportAttribute]),
};
export interface ExportAllDeclaration extends Fields<typeof ExportAllDeclarationSpec> {}
/** `export type * as exported from source with { attributes };`. */
export class ExportAllDeclaration extends Statement {
  static override SPEC = ExportAllDeclarationSpec;
  static override SINCE: Availability | null = es(2015, 105);
  static override FEATURES: Features = {
    exportKind: [["type", ts(500)]],
    exported: [[true, es(2020, 308)]],
    attributes: [[true, es(2025, 503)]],
  };
}

const TSImportEqualsDeclarationSpec = {
  importKind: choice(...IMPORT_EXPORT_KINDS),
  id: one(() => [Identifier]),
  moduleReference: one(() => [Identifier, TSQualifiedName, TSExternalModuleReference]),
};
export interface TSImportEqualsDeclaration extends Fields<typeof TSImportEqualsDeclarationSpec> {}
/** `import type id = moduleReference;`. */
export class TSImportEqualsDeclaration extends Statement {
  static override SPEC = TSImportEqualsDeclarationSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSExternalModuleReferenceSpec = {
  expression: one(() => [Literal]),
};
export interface TSExternalModuleReference extends Fields<typeof TSExternalModuleReferenceSpec> {}
/** `require(expression)`, in `import x = require('m')`. */
export class TSExternalModuleReference extends Node {
  static override SPEC = TSExternalModuleReferenceSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSExportAssignmentSpec = {
  expression: one(() => [Expression]),
};
export interface TSExportAssignment extends Fields<typeof TSExportAssignmentSpec> {}
/** `export = expression;`. */
export class TSExportAssignment extends Statement {
  static override SPEC = TSExportAssignmentSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSNamespaceExportDeclarationSpec = {
  id: one(() => [Identifier]),
};
export interface TSNamespaceExportDeclaration extends Fields<typeof TSNamespaceExportDeclarationSpec> {}
/** `export as namespace id;`. */
export class TSNamespaceExportDeclaration extends Statement {
  static override SPEC = TSNamespaceExportDeclarationSpec;
  static override SINCE: Availability | null = ts(200);
}

// === TypeScript's declarations ===

const TSTypeAnnotationSpec = {
  typeAnnotation: one(() => [TypeNode]),
};
export interface TSTypeAnnotation extends Fields<typeof TSTypeAnnotationSpec> {}
/** `: typeAnnotation`, after a binding, a parameter, a field or a signature. */
export class TSTypeAnnotation extends Node {
  static override SPEC = TSTypeAnnotationSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSTypeParameterSpec = {
  const: flag(),
  isIn: flag(),
  isOut: flag(),
  name: one(() => [Identifier]),
  constraint: optional(() => [TypeNode]),
  default: optional(() => [TypeNode]),
};
export interface TSTypeParameter extends Fields<typeof TSTypeParameterSpec> {}
/** `const in out name extends constraint = default`. */
export class TSTypeParameter extends Node {
  static override SPEC = TSTypeParameterSpec;
  static override SINCE: Availability | null = ts(100);
  static override FEATURES: Features = {
    const: [[true, ts(500)]],
    isIn: [[true, ts(407)]],
    isOut: [[true, ts(407)]],
    default: [[true, ts(203)]],
  };
}

const TSTypeParameterDeclarationSpec = {
  params: many(() => [TSTypeParameter]),
};
export interface TSTypeParameterDeclaration extends Fields<typeof TSTypeParameterDeclarationSpec> {}
/** `<params>`, a declaration's type parameters. */
export class TSTypeParameterDeclaration extends Node {
  static override SPEC = TSTypeParameterDeclarationSpec;
  static override SINCE: Availability | null = ts(100);
  override check(): string[] {
    return needs(this, "params", "a type parameter");
  }
}

const TSTypeParameterInstantiationSpec = {
  params: many(() => [TypeNode]),
};
export interface TSTypeParameterInstantiation extends Fields<typeof TSTypeParameterInstantiationSpec> {}
/** `<params>`, type arguments. */
export class TSTypeParameterInstantiation extends Node {
  static override SPEC = TSTypeParameterInstantiationSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSTypeAliasDeclarationSpec = {
  declare: flag(),
  id: one(() => [Identifier]),
  typeParameters: optional(() => [TSTypeParameterDeclaration]),
  typeAnnotation: one(() => [TypeNode]),
};
export interface TSTypeAliasDeclaration extends Fields<typeof TSTypeAliasDeclarationSpec> {}
/** `declare type id<typeParameters> = typeAnnotation;`. */
export class TSTypeAliasDeclaration extends Statement {
  static override SPEC = TSTypeAliasDeclarationSpec;
  static override SINCE: Availability | null = ts(104);
}

const TSInterfaceHeritageSpec = {
  expression: one(() => [Expression]),
  typeArguments: optional(() => [TSTypeParameterInstantiation]),
};
export interface TSInterfaceHeritage extends Fields<typeof TSInterfaceHeritageSpec> {}
/** `expression<typeArguments>`, which an interface extends. */
export class TSInterfaceHeritage extends Node {
  static override SPEC = TSInterfaceHeritageSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSClassImplementsSpec = {
  expression: one(() => [Expression]),
  typeArguments: optional(() => [TSTypeParameterInstantiation]),
};
export interface TSClassImplements extends Fields<typeof TSClassImplementsSpec> {}
/** `expression<typeArguments>`, which a class implements. */
export class TSClassImplements extends Node {
  static override SPEC = TSClassImplementsSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSInterfaceBodySpec = {
  body: many(() => [TypeElement, Comment]),
};
export interface TSInterfaceBody extends Fields<typeof TSInterfaceBodySpec> {}
/** `{ body }`: an interface's members. */
export class TSInterfaceBody extends Node {
  static override SPEC = TSInterfaceBodySpec;
  static override SINCE: Availability | null = ts(100);
}

const TSInterfaceDeclarationSpec = {
  declare: flag(),
  id: one(() => [Identifier]),
  typeParameters: optional(() => [TSTypeParameterDeclaration]),
  extends: many(() => [TSInterfaceHeritage]),
  body: one(() => [TSInterfaceBody]),
};
export interface TSInterfaceDeclaration extends Fields<typeof TSInterfaceDeclarationSpec> {}
/** `declare interface id<typeParameters> extends ... { body }`. */
export class TSInterfaceDeclaration extends Statement {
  static override SPEC = TSInterfaceDeclarationSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSEnumMemberSpec = {
  computed: flag(),
  id: one(() => [Expression]),
  initializer: optional(() => [Expression]),
};
export interface TSEnumMember extends Fields<typeof TSEnumMemberSpec> {}
/** `id = initializer`; `computed` for `[id]`. */
export class TSEnumMember extends Node {
  static override SPEC = TSEnumMemberSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSEnumBodySpec = {
  members: many(() => [TSEnumMember, Comment]),
};
export interface TSEnumBody extends Fields<typeof TSEnumBodySpec> {}
/** `{ members }`. */
export class TSEnumBody extends Node {
  static override SPEC = TSEnumBodySpec;
  static override SINCE: Availability | null = ts(100);
}

const TSEnumDeclarationSpec = {
  declare: flag(),
  const: flag(),
  id: one(() => [Identifier]),
  body: one(() => [TSEnumBody]),
};
export interface TSEnumDeclaration extends Fields<typeof TSEnumDeclarationSpec> {}
/** `declare const enum id { body }`. */
export class TSEnumDeclaration extends Statement {
  static override SPEC = TSEnumDeclarationSpec;
  static override SINCE: Availability | null = ts(100);
  static override FEATURES: Features = { const: [[true, ts(104)]] };
}

const TSModuleBlockSpec = {
  body: many(() => [Statement]),
};
export interface TSModuleBlock extends Fields<typeof TSModuleBlockSpec> {}
/** `{ body }`: a namespace's or module's statements. */
export class TSModuleBlock extends Node {
  static override SPEC = TSModuleBlockSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSModuleDeclarationSpec = {
  declare: flag(),
  moduleKind: choice(...MODULE_KINDS),
  id: one(() => [Identifier, Literal, TSQualifiedName]),
  body: optional(() => [TSModuleBlock]),
};
export interface TSModuleDeclaration extends Fields<typeof TSModuleDeclarationSpec> {}
/**
 * `declare namespace id { body }`, `declare module 'id' { body }` or `declare global { body }`; `moduleKind` is
 * 'namespace', 'module' or 'global'. A declared module may have no body.
 */
export class TSModuleDeclaration extends Statement {
  static override SPEC = TSModuleDeclarationSpec;
  static override SINCE: Availability | null = ts(100);
  static override FEATURES: Features = { moduleKind: [["namespace", ts(105)], ["global", ts(108)]] };
}

// --- Signatures and members ---

const TSPropertySignatureSpec = {
  accessibility: optionalChoice(...ACCESSIBILITYS),
  static: flag(),
  readonly: flag(),
  computed: flag(),
  key: one(() => [Expression]),
  optional: flag(),
  typeAnnotation: optional(() => [TSTypeAnnotation]),
};
export interface TSPropertySignature extends Fields<typeof TSPropertySignatureSpec> {}
/** `readonly key?: typeAnnotation;`, in an interface or an object type. */
export class TSPropertySignature extends TypeElement {
  static override SPEC = TSPropertySignatureSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSMethodSignatureSpec = {
  accessibility: optionalChoice(...ACCESSIBILITYS),
  static: flag(),
  readonly: flag(),
  methodKind: choice(...METHOD_KINDS),
  computed: flag(),
  key: one(() => [Expression]),
  optional: flag(),
  typeParameters: optional(() => [TSTypeParameterDeclaration]),
  params: many(() => [Identifier, Pattern, TSParameterProperty]),
  returnType: optional(() => [TSTypeAnnotation]),
};
export interface TSMethodSignature extends Fields<typeof TSMethodSignatureSpec> {}
/** `get key?<typeParameters>(params): returnType;`; `methodKind` is 'method', 'get' or 'set'. */
export class TSMethodSignature extends TypeElement {
  static override SPEC = TSMethodSignatureSpec;
  static override SINCE: Availability | null = ts(100);
  static override FEATURES: Features = { methodKind: [["get", ts(403)], ["set", ts(403)]] };
}

const TSCallSignatureDeclarationSpec = {
  typeParameters: optional(() => [TSTypeParameterDeclaration]),
  params: many(() => [Identifier, Pattern, TSParameterProperty]),
  returnType: optional(() => [TSTypeAnnotation]),
};
export interface TSCallSignatureDeclaration extends Fields<typeof TSCallSignatureDeclarationSpec> {}
/** `<typeParameters>(params): returnType;`. */
export class TSCallSignatureDeclaration extends TypeElement {
  static override SPEC = TSCallSignatureDeclarationSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSConstructSignatureDeclarationSpec = {
  typeParameters: optional(() => [TSTypeParameterDeclaration]),
  params: many(() => [Identifier, Pattern, TSParameterProperty]),
  returnType: optional(() => [TSTypeAnnotation]),
};
export interface TSConstructSignatureDeclaration extends Fields<typeof TSConstructSignatureDeclarationSpec> {}
/** `new <typeParameters>(params): returnType;`. */
export class TSConstructSignatureDeclaration extends TypeElement {
  static override SPEC = TSConstructSignatureDeclarationSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSIndexSignatureSpec = {
  accessibility: optionalChoice(...ACCESSIBILITYS),
  static: flag(),
  readonly: flag(),
  parameters: many(() => [Identifier, Pattern, TSParameterProperty]),
  typeAnnotation: optional(() => [TSTypeAnnotation]),
};
export interface TSIndexSignature extends Fields<typeof TSIndexSignatureSpec> {}
/** `static readonly [parameters]: typeAnnotation;`, in an interface, an object type or a class. */
export class TSIndexSignature extends TypeElement {
  static override SPEC = TSIndexSignatureSpec;
  static override SINCE: Availability | null = ts(100);
  static override FEATURES: Features = { static: [[true, ts(403)]] };
}

// === Types ===

/** `any`. */
export class TSAnyKeyword extends TypeNode {
  static override SINCE: Availability | null = ts(100);
}

/** `unknown`. */
export class TSUnknownKeyword extends TypeNode {
  static override SINCE: Availability | null = ts(300);
}

/** `number`. */
export class TSNumberKeyword extends TypeNode {
  static override SINCE: Availability | null = ts(100);
}

/** `bigint`. */
export class TSBigIntKeyword extends TypeNode {
  static override SINCE: Availability | null = ts(302);
}

/** `boolean`. */
export class TSBooleanKeyword extends TypeNode {
  static override SINCE: Availability | null = ts(100);
}

/** `string`. */
export class TSStringKeyword extends TypeNode {
  static override SINCE: Availability | null = ts(100);
}

/** `symbol`. */
export class TSSymbolKeyword extends TypeNode {
  static override SINCE: Availability | null = ts(100);
}

/** `object`. */
export class TSObjectKeyword extends TypeNode {
  static override SINCE: Availability | null = ts(202);
}

/** `never`. */
export class TSNeverKeyword extends TypeNode {
  static override SINCE: Availability | null = ts(200);
}

/** `void`. */
export class TSVoidKeyword extends TypeNode {
  static override SINCE: Availability | null = ts(100);
}

/** `undefined`. */
export class TSUndefinedKeyword extends TypeNode {
  static override SINCE: Availability | null = ts(200);
}

/** `null`. */
export class TSNullKeyword extends TypeNode {
  static override SINCE: Availability | null = ts(200);
}

/** `intrinsic`, the body of the compiler's own type aliases. */
export class TSIntrinsicKeyword extends TypeNode {
  static override SINCE: Availability | null = ts(401);
}

/** `this`, as a type. */
export class TSThisType extends TypeNode {
  static override SINCE: Availability | null = ts(107);
}

const TSQualifiedNameSpec: {
  left: ChildSpec<Identifier | ThisExpression | TSQualifiedName, false, false>;
  right: ChildSpec<Identifier, false, false>;
} = {
  left: one(() => [Identifier, ThisExpression, TSQualifiedName]),
  right: one(() => [Identifier]),
};
export interface TSQualifiedName extends Fields<typeof TSQualifiedNameSpec> {}
/** `left.right`, a name in a namespace. */
export class TSQualifiedName extends TypeNode {
  static override SPEC = TSQualifiedNameSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSTypeReferenceSpec = {
  typeName: one(() => [Identifier, ThisExpression, TSQualifiedName]),
  typeArguments: optional(() => [TSTypeParameterInstantiation]),
};
export interface TSTypeReference extends Fields<typeof TSTypeReferenceSpec> {}
/** `typeName<typeArguments>`. */
export class TSTypeReference extends TypeNode {
  static override SPEC = TSTypeReferenceSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSParenthesizedTypeSpec = {
  typeAnnotation: one(() => [TypeNode]),
};
export interface TSParenthesizedType extends Fields<typeof TSParenthesizedTypeSpec> {}
/** `(typeAnnotation)`: parentheses written in the source. */
export class TSParenthesizedType extends TypeNode {
  static override SPEC = TSParenthesizedTypeSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSLiteralTypeSpec = {
  literal: one(() => [Literal, UnaryExpression, TemplateLiteral]),
};
export interface TSLiteralType extends Fields<typeof TSLiteralTypeSpec> {}
/** A literal as a type: a string, number, bigint or boolean literal, a negated number, or a template literal. */
export class TSLiteralType extends TypeNode {
  static override SPEC = TSLiteralTypeSpec;
  static override SINCE: Availability | null = ts(108);
}

const TSTemplateLiteralTypeSpec = {
  quasis: many(() => [TemplateElement]),
  types: many(() => [TypeNode]),
};
export interface TSTemplateLiteralType extends Fields<typeof TSTemplateLiteralTypeSpec> {}
/** `` `quasi${type}quasi` ``, a template literal type. */
export class TSTemplateLiteralType extends TypeNode {
  static override SPEC = TSTemplateLiteralTypeSpec;
  static override SINCE: Availability | null = ts(401);
  override check(): string[] {
    if (this.quasis.length === this.types.length + 1) return [];
    return ["a TSTemplateLiteralType needs one more quasi than types"];
  }
}

const TSArrayTypeSpec = {
  elementType: one(() => [TypeNode]),
};
export interface TSArrayType extends Fields<typeof TSArrayTypeSpec> {}
/** `elementType[]`. */
export class TSArrayType extends TypeNode {
  static override SPEC = TSArrayTypeSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSTupleTypeSpec = {
  elementTypes: many(() => [TypeNode]),
};
export interface TSTupleType extends Fields<typeof TSTupleTypeSpec> {}
/** `[elementTypes]`. */
export class TSTupleType extends TypeNode {
  static override SPEC = TSTupleTypeSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSNamedTupleMemberSpec = {
  label: one(() => [Identifier]),
  optional: flag(),
  elementType: one(() => [TypeNode]),
};
export interface TSNamedTupleMember extends Fields<typeof TSNamedTupleMemberSpec> {}
/** `label?: elementType`, in a tuple. */
export class TSNamedTupleMember extends TypeNode {
  static override SPEC = TSNamedTupleMemberSpec;
  static override SINCE: Availability | null = ts(400);
}

const TSOptionalTypeSpec = {
  typeAnnotation: one(() => [TypeNode]),
};
export interface TSOptionalType extends Fields<typeof TSOptionalTypeSpec> {}
/** `typeAnnotation?`, in a tuple. */
export class TSOptionalType extends TypeNode {
  static override SPEC = TSOptionalTypeSpec;
  static override SINCE: Availability | null = ts(300);
}

const TSRestTypeSpec = {
  typeAnnotation: one(() => [TypeNode]),
};
export interface TSRestType extends Fields<typeof TSRestTypeSpec> {}
/** `...typeAnnotation`, in a tuple. */
export class TSRestType extends TypeNode {
  static override SPEC = TSRestTypeSpec;
  static override SINCE: Availability | null = ts(300);
}

const TSUnionTypeSpec = {
  types: many(() => [TypeNode]),
};
export interface TSUnionType extends Fields<typeof TSUnionTypeSpec> {}
/** `type | type`. */
export class TSUnionType extends TypeNode {
  static override SPEC = TSUnionTypeSpec;
  static override SINCE: Availability | null = ts(104);
  override check(): string[] {
    return this.types.length > 1 ? [] : ["a TSUnionType needs two types"];
  }
}

const TSIntersectionTypeSpec = {
  types: many(() => [TypeNode]),
};
export interface TSIntersectionType extends Fields<typeof TSIntersectionTypeSpec> {}
/** `type & type`. */
export class TSIntersectionType extends TypeNode {
  static override SPEC = TSIntersectionTypeSpec;
  static override SINCE: Availability | null = ts(106);
  override check(): string[] {
    return this.types.length > 1 ? [] : ["a TSIntersectionType needs two types"];
  }
}

const TSFunctionTypeSpec = {
  typeParameters: optional(() => [TSTypeParameterDeclaration]),
  params: many(() => [Identifier, Pattern, TSParameterProperty]),
  returnType: optional(() => [TSTypeAnnotation]),
};
export interface TSFunctionType extends Fields<typeof TSFunctionTypeSpec> {}
/** `<typeParameters>(params) => returnType`. */
export class TSFunctionType extends TypeNode {
  static override SPEC = TSFunctionTypeSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSConstructorTypeSpec = {
  abstract: flag(),
  typeParameters: optional(() => [TSTypeParameterDeclaration]),
  params: many(() => [Identifier, Pattern, TSParameterProperty]),
  returnType: optional(() => [TSTypeAnnotation]),
};
export interface TSConstructorType extends Fields<typeof TSConstructorTypeSpec> {}
/** `abstract new <typeParameters>(params) => returnType`. */
export class TSConstructorType extends TypeNode {
  static override SPEC = TSConstructorTypeSpec;
  static override SINCE: Availability | null = ts(100);
  static override FEATURES: Features = { abstract: [[true, ts(402)]] };
}

const TSTypeLiteralSpec = {
  members: many(() => [TypeElement, Comment]),
};
export interface TSTypeLiteral extends Fields<typeof TSTypeLiteralSpec> {}
/** `{ members }`, an object type. */
export class TSTypeLiteral extends TypeNode {
  static override SPEC = TSTypeLiteralSpec;
  static override SINCE: Availability | null = ts(100);
}

const TSMappedTypeSpec = {
  readonly: optionalChoice(...MAPPED_READONLYS),
  key: one(() => [Identifier]),
  constraint: one(() => [TypeNode]),
  nameType: optional(() => [TypeNode]),
  optional: optionalChoice(...MAPPED_OPTIONALS),
  typeAnnotation: optional(() => [TypeNode]),
};
export interface TSMappedType extends Fields<typeof TSMappedTypeSpec> {}
/** `{ readonly [key in constraint as nameType]?: typeAnnotation }`. */
export class TSMappedType extends TypeNode {
  static override SPEC = TSMappedTypeSpec;
  static override SINCE: Availability | null = ts(201);
  static override FEATURES: Features = {
    nameType: [[true, ts(401)]],
    optional: [["+?", ts(208)], ["-?", ts(208)]],
    readonly: [["+readonly", ts(208)], ["-readonly", ts(208)]],
  };
}

const TSIndexedAccessTypeSpec = {
  objectType: one(() => [TypeNode]),
  indexType: one(() => [TypeNode]),
};
export interface TSIndexedAccessType extends Fields<typeof TSIndexedAccessTypeSpec> {}
/** `objectType[indexType]`. */
export class TSIndexedAccessType extends TypeNode {
  static override SPEC = TSIndexedAccessTypeSpec;
  static override SINCE: Availability | null = ts(201);
}

const TSTypeOperatorSpec = {
  operator: choice(...TYPE_OPERATORS),
  typeAnnotation: optional(() => [TypeNode]),
};
export interface TSTypeOperator extends Fields<typeof TSTypeOperatorSpec> {}
/** `keyof typeAnnotation`, `readonly typeAnnotation` or `unique symbol`. */
export class TSTypeOperator extends TypeNode {
  static override SPEC = TSTypeOperatorSpec;
  static override SINCE: Availability | null = ts(201);
  static override FEATURES: Features = { operator: [["readonly", ts(304)], ["unique", ts(207)]] };
}

const TSTypeQuerySpec = {
  exprName: one(() => [Identifier, ThisExpression, TSQualifiedName, TSImportType]),
  typeArguments: optional(() => [TSTypeParameterInstantiation]),
};
export interface TSTypeQuery extends Fields<typeof TSTypeQuerySpec> {}
/** `typeof exprName<typeArguments>`. */
export class TSTypeQuery extends TypeNode {
  static override SPEC = TSTypeQuerySpec;
  static override SINCE: Availability | null = ts(100);
}

const TSImportTypeSpec = {
  source: one(() => [Literal]),
  options: optional(() => [ObjectExpression]),
  qualifier: optional(() => [Identifier, ThisExpression, TSQualifiedName]),
  typeArguments: optional(() => [TSTypeParameterInstantiation]),
};
export interface TSImportType extends Fields<typeof TSImportTypeSpec> {}
/** `import(source, options).qualifier<typeArguments>`. */
export class TSImportType extends TypeNode {
  static override SPEC = TSImportTypeSpec;
  static override SINCE: Availability | null = ts(209);
}

const TSConditionalTypeSpec = {
  checkType: one(() => [TypeNode]),
  extendsType: one(() => [TypeNode]),
  trueType: one(() => [TypeNode]),
  falseType: one(() => [TypeNode]),
};
export interface TSConditionalType extends Fields<typeof TSConditionalTypeSpec> {}
/** `checkType extends extendsType ? trueType : falseType`. */
export class TSConditionalType extends TypeNode {
  static override SPEC = TSConditionalTypeSpec;
  static override SINCE: Availability | null = ts(208);
}

const TSInferTypeSpec = {
  typeParameter: one(() => [TSTypeParameter]),
};
export interface TSInferType extends Fields<typeof TSInferTypeSpec> {}
/** `infer typeParameter`, in a conditional type's `extends`. */
export class TSInferType extends TypeNode {
  static override SPEC = TSInferTypeSpec;
  static override SINCE: Availability | null = ts(208);
}

const TSTypePredicateSpec = {
  asserts: flag(),
  parameterName: one(() => [Identifier, TSThisType]),
  typeAnnotation: optional(() => [TSTypeAnnotation]),
};
export interface TSTypePredicate extends Fields<typeof TSTypePredicateSpec> {}
/** `asserts parameterName is typeAnnotation`, a function's return type. */
export class TSTypePredicate extends TypeNode {
  static override SPEC = TSTypePredicateSpec;
  static override SINCE: Availability | null = ts(106);
  static override FEATURES: Features = { asserts: [[true, ts(307)]] };
}

// === JSX, an extension that the standards made with `jsx` accept ===

const JSXIdentifierSpec = {
  name: text(),
};
export interface JSXIdentifier extends Fields<typeof JSXIdentifierSpec> {}
/** A JSX name, which may hold `-`. */
export class JSXIdentifier extends Node {
  static override SPEC = JSXIdentifierSpec;
  static override EXTENSION = true;
}

const JSXNamespacedNameSpec = {
  namespace: one(() => [JSXIdentifier]),
  name: one(() => [JSXIdentifier]),
};
export interface JSXNamespacedName extends Fields<typeof JSXNamespacedNameSpec> {}
/** `namespace:name`. */
export class JSXNamespacedName extends Node {
  static override SPEC = JSXNamespacedNameSpec;
  static override EXTENSION = true;
}

const JSXMemberExpressionSpec: {
  object: ChildSpec<JSXIdentifier | JSXMemberExpression, false, false>;
  property: ChildSpec<JSXIdentifier, false, false>;
} = {
  object: one(() => [JSXIdentifier, JSXMemberExpression]),
  property: one(() => [JSXIdentifier]),
};
export interface JSXMemberExpression extends Fields<typeof JSXMemberExpressionSpec> {}
/** `object.property`, a tag's name. */
export class JSXMemberExpression extends Node {
  static override SPEC = JSXMemberExpressionSpec;
  static override EXTENSION = true;
}

/** Nothing, in `{}` or `{/* comment *\/}`. */
export class JSXEmptyExpression extends Node {
  static override EXTENSION = true;
}

const JSXExpressionContainerSpec = {
  expression: one(() => [Expression, JSXEmptyExpression]),
};
export interface JSXExpressionContainer extends Fields<typeof JSXExpressionContainerSpec> {}
/** `{expression}`. */
export class JSXExpressionContainer extends Node {
  static override SPEC = JSXExpressionContainerSpec;
  static override EXTENSION = true;
}

const JSXSpreadChildSpec = {
  expression: one(() => [Expression, JSXEmptyExpression]),
};
export interface JSXSpreadChild extends Fields<typeof JSXSpreadChildSpec> {}
/** `{...expression}`, a child. */
export class JSXSpreadChild extends Node {
  static override SPEC = JSXSpreadChildSpec;
  static override EXTENSION = true;
}

const JSXTextSpec = {
  raw: text(),
};
export interface JSXText extends Fields<typeof JSXTextSpec> {}
/** Text between tags, as written. */
export class JSXText extends Node {
  static override SPEC = JSXTextSpec;
  static override EXTENSION = true;
}

const JSXAttributeSpec: {
  name: ChildSpec<JSXIdentifier | JSXNamespacedName, false, false>;
  value: ChildSpec<Literal | JSXExpressionContainer | JSXElement | JSXFragment, false, true>;
} = {
  name: one(() => [JSXIdentifier, JSXNamespacedName]),
  value: optional(() => [Literal, JSXExpressionContainer, JSXElement, JSXFragment]),
};
export interface JSXAttribute extends Fields<typeof JSXAttributeSpec> {}
/** `name=value`, or `name` without a value. */
export class JSXAttribute extends Node {
  static override SPEC = JSXAttributeSpec;
  static override EXTENSION = true;
}

const JSXSpreadAttributeSpec = {
  argument: one(() => [Expression]),
};
export interface JSXSpreadAttribute extends Fields<typeof JSXSpreadAttributeSpec> {}
/** `{...argument}`, an attribute. */
export class JSXSpreadAttribute extends Node {
  static override SPEC = JSXSpreadAttributeSpec;
  static override EXTENSION = true;
}

const JSXOpeningElementSpec: {
  name: ChildSpec<JSXIdentifier | JSXMemberExpression | JSXNamespacedName, false, false>;
  typeArguments: ChildSpec<TSTypeParameterInstantiation, false, true>;
  attributes: ChildSpec<JSXAttribute | JSXSpreadAttribute, true, true>;
  selfClosing: AttributeSpec<boolean, false>;
} = {
  name: one(() => [JSXIdentifier, JSXMemberExpression, JSXNamespacedName]),
  typeArguments: optional(() => [TSTypeParameterInstantiation]),
  attributes: many(() => [JSXAttribute, JSXSpreadAttribute]),
  selfClosing: flag(),
};
export interface JSXOpeningElement extends Fields<typeof JSXOpeningElementSpec> {}
/** `<name<typeArguments> attributes>`, or with `selfClosing` `<name ... />`. */
export class JSXOpeningElement extends Node {
  static override SPEC = JSXOpeningElementSpec;
  static override EXTENSION = true;
}

const JSXClosingElementSpec = {
  name: one(() => [JSXIdentifier, JSXMemberExpression, JSXNamespacedName]),
};
export interface JSXClosingElement extends Fields<typeof JSXClosingElementSpec> {}
/** `</name>`. */
export class JSXClosingElement extends Node {
  static override SPEC = JSXClosingElementSpec;
  static override EXTENSION = true;
}

const JSXElementSpec: {
  openingElement: ChildSpec<JSXOpeningElement, false, false>;
  children: ChildSpec<JSXText | JSXExpressionContainer | JSXSpreadChild | JSXElement | JSXFragment, true, true>;
  closingElement: ChildSpec<JSXClosingElement, false, true>;
} = {
  openingElement: one(() => [JSXOpeningElement]),
  children: many(() => [JSXText, JSXExpressionContainer, JSXSpreadChild, JSXElement, JSXFragment]),
  closingElement: optional(() => [JSXClosingElement]),
};
export interface JSXElement extends Fields<typeof JSXElementSpec> {}
/** `<name ...>children</name>`. */
export class JSXElement extends Expression {
  static override SPEC = JSXElementSpec;
  static override EXTENSION = true;
}

/** `<>`. */
export class JSXOpeningFragment extends Node {
  static override EXTENSION = true;
}

/** `</>`. */
export class JSXClosingFragment extends Node {
  static override EXTENSION = true;
}

const JSXFragmentSpec: {
  openingFragment: ChildSpec<JSXOpeningFragment, false, false>;
  children: ChildSpec<JSXText | JSXExpressionContainer | JSXSpreadChild | JSXElement | JSXFragment, true, true>;
  closingFragment: ChildSpec<JSXClosingFragment, false, false>;
} = {
  openingFragment: one(() => [JSXOpeningFragment]),
  children: many(() => [JSXText, JSXExpressionContainer, JSXSpreadChild, JSXElement, JSXFragment]),
  closingFragment: one(() => [JSXClosingFragment]),
};
export interface JSXFragment extends Fields<typeof JSXFragmentSpec> {}
/** `<>children</>`. */
export class JSXFragment extends Expression {
  static override SPEC = JSXFragmentSpec;
  static override EXTENSION = true;
}

// --- The language ---

export const KINDS: readonly (typeof Node)[] = [
  Comment, Program, Identifier, PrivateIdentifier, Literal, TemplateElement, TemplateLiteral,
  TaggedTemplateExpression, ThisExpression, Super, ParenthesizedExpression, Elision, SpreadElement, ArrayExpression,
  Property, ObjectExpression, FunctionExpression, ArrowFunctionExpression, ClassExpression, MetaProperty,
  MemberExpression, CallExpression, ChainExpression, NewExpression, ImportExpression, UpdateExpression,
  UnaryExpression, AwaitExpression, BinaryExpression, LogicalExpression, ConditionalExpression, AssignmentExpression,
  SequenceExpression, YieldExpression, TSAsExpression, TSSatisfiesExpression, TSTypeAssertion, TSNonNullExpression,
  TSInstantiationExpression, ArrayPattern, ObjectPattern, AssignmentPattern, RestElement, ExpressionStatement,
  BlockStatement, EmptyStatement, DebuggerStatement, WithStatement, ReturnStatement, LabeledStatement, BreakStatement,
  ContinueStatement, IfStatement, SwitchCase, SwitchStatement, ThrowStatement, CatchClause, TryStatement,
  WhileStatement, DoWhileStatement, ForStatement, ForInStatement, ForOfStatement, VariableDeclarator,
  VariableDeclaration, FunctionDeclaration, TSDeclareFunction, Decorator, ClassBody, ClassDeclaration, StaticBlock,
  MethodDefinition, TSAbstractMethodDefinition, TSEmptyBodyFunctionExpression, PropertyDefinition,
  TSAbstractPropertyDefinition, AccessorProperty, TSAbstractAccessorProperty, TSParameterProperty, ImportAttribute,
  ImportSpecifier, ImportDefaultSpecifier, ImportNamespaceSpecifier, ImportDeclaration, ExportSpecifier,
  ExportNamedDeclaration, ExportDefaultDeclaration, ExportAllDeclaration, TSImportEqualsDeclaration,
  TSExternalModuleReference, TSExportAssignment, TSNamespaceExportDeclaration, TSTypeAnnotation, TSTypeParameter,
  TSTypeParameterDeclaration, TSTypeParameterInstantiation, TSTypeAliasDeclaration, TSInterfaceHeritage,
  TSClassImplements, TSInterfaceBody, TSInterfaceDeclaration, TSEnumMember, TSEnumBody, TSEnumDeclaration,
  TSModuleBlock, TSModuleDeclaration, TSPropertySignature, TSMethodSignature, TSCallSignatureDeclaration,
  TSConstructSignatureDeclaration, TSIndexSignature, TSAnyKeyword, TSUnknownKeyword, TSNumberKeyword, TSBigIntKeyword,
  TSBooleanKeyword, TSStringKeyword, TSSymbolKeyword, TSObjectKeyword, TSNeverKeyword, TSVoidKeyword,
  TSUndefinedKeyword, TSNullKeyword, TSIntrinsicKeyword, TSThisType, TSQualifiedName, TSTypeReference,
  TSParenthesizedType, TSLiteralType, TSTemplateLiteralType, TSArrayType, TSTupleType, TSNamedTupleMember,
  TSOptionalType, TSRestType, TSUnionType, TSIntersectionType, TSFunctionType, TSConstructorType, TSTypeLiteral,
  TSMappedType, TSIndexedAccessType, TSTypeOperator, TSTypeQuery, TSImportType, TSConditionalType, TSInferType,
  TSTypePredicate, JSXIdentifier, JSXNamespacedName, JSXMemberExpression, JSXEmptyExpression, JSXExpressionContainer,
  JSXSpreadChild, JSXText, JSXAttribute, JSXSpreadAttribute, JSXOpeningElement, JSXClosingElement, JSXElement,
  JSXOpeningFragment, JSXClosingFragment, JSXFragment,
];

export const LANGUAGE = new Language("TypeScript", KINDS, { base: es(2015, 100) });
