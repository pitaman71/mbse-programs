/**
 * Syntax: the abstract syntax of Verilog and SystemVerilog, as one tree language (Verilog), organized as IEEE 1800's
 * grammar is.
 *
 * The kinds cover SystemVerilog (IEEE 1800-2023)'s design subset and its classes: design units, ports and parameters,
 * data types, declarations, continuous assignments, procedural blocks and statements, generate constructs,
 * instantiation, functions and tasks, classes with their properties, methods and objects, immediate assertions and
 * compiler directives. Verilog (IEEE 1364) is a family of its own whose standards have fewer of them: each kind and
 * feature records where it exists in both families (`SINCE`, `FEATURES`), which `Verilog2005`, `SystemVerilog2017`,
 * `SystemVerilog2023` and `VerilogStandard(year, family)` check. Constraints, properties and sequences, and covergroups
 * are not kinds yet.
 *
 * The tree is abstract where the grammar only spells and concrete where a transpiler needs to see what was written:
 *
 * - Precedence levels collapse: every binary operator is a `BinaryExpression`. Parentheses written in the source stay,
 *   as `ParenthesizedExpression`, and printing adds those a hand-built tree needs.
 * - Names are syntax nodes (category `Name`) wherever they occur, so one traversal finds every use and declaration of a
 *   name. Expressions refer to them through `NameExpression`; a hierarchical name is `MemberExpression`s.
 * - Literals keep their spelling: size, base and digits with their underscores (`8'b0000_0100`), and the characters
 *   between a string's quotes, escapes included.
 * - Equivalent spellings are normalized: `@*` is `@(*)`, events joined by `,` are joined by `or`, and an event control
 *   of one name is parenthesized.
 * - Comments and compiler directives are kept where items and statements are listed; conditional compilation is a tree
 *   of its branches there.
 *
 * Property names avoid Python's and TypeScript's reserved words: an `if` has a `consequence` and an `alternative`.
 */

import { Repr } from "@mbse/schemas/Framework";

import {
  type AttributeSpec, type Availability, type ChildSpec, choice, type Features, flag, Language, many, one, optional,
  optionalChoice, optionalInteger, optionalText, type Properties, SyntaxNode, text,
} from "../Framework/Syntax.js";
import type * as Self from "./Syntax.js";

const { repr } = Repr;

export const VERILOG = "Verilog";
export const SV = "SystemVerilog";

/** SystemVerilog from `year` on; not Verilog. */
export function sv(year = 2005): Availability {
  return { [SV]: year };
}

/** Verilog from `year` on, and every SystemVerilog. */
export function verilog(year: number): Availability {
  return { [VERILOG]: year, [SV]: 2005 };
}

// --- Choices ---

export const DIRECTIONS = ["input", "output", "inout", "ref"] as const;
export type Direction = (typeof DIRECTIONS)[number];
export const NET_TYPES = [
  "wire", "tri", "tri0", "tri1", "triand", "trior", "trireg", "wand", "wor", "supply0", "supply1", "uwire",
  "interconnect"
] as const;
export type NetType = (typeof NET_TYPES)[number];
export const SIGNINGS = ["signed", "unsigned"] as const;
export type Signing = (typeof SIGNINGS)[number];
export const LIFETIMES = ["static", "automatic"] as const;
export type Lifetime = (typeof LIFETIMES)[number];
export const VECTOR_KEYWORDS = ["bit", "logic", "reg"] as const;
export type VectorKeyword = (typeof VECTOR_KEYWORDS)[number];
export const ATOM_KEYWORDS = ["byte", "shortint", "int", "longint", "integer", "time"] as const;
export type AtomKeyword = (typeof ATOM_KEYWORDS)[number];
export const REAL_KEYWORDS = ["shortreal", "real", "realtime"] as const;
export type RealKeyword = (typeof REAL_KEYWORDS)[number];
export const SIMPLE_KEYWORDS = ["string", "chandle", "event", "void"] as const;
export type SimpleKeyword = (typeof SIMPLE_KEYWORDS)[number];
export const ALWAYS_KEYWORDS = ["always", "always_comb", "always_ff", "always_latch"] as const;
export type AlwaysKeyword = (typeof ALWAYS_KEYWORDS)[number];
export const CASE_KEYWORDS = ["case", "casez", "casex"] as const;
export type CaseKeyword = (typeof CASE_KEYWORDS)[number];
export const QUALIFIERS = ["unique", "unique0", "priority"] as const;
export type Qualifier = (typeof QUALIFIERS)[number];
export const JOIN_KEYWORDS = ["join", "join_any", "join_none"] as const;
export type JoinKeyword = (typeof JOIN_KEYWORDS)[number];
export const EDGES = ["posedge", "negedge", "edge"] as const;
export type Edge = (typeof EDGES)[number];
export const ASSERTION_KEYWORDS = ["assert", "assume", "cover"] as const;
export type AssertionKeyword = (typeof ASSERTION_KEYWORDS)[number];
export const DEFERRALS = ["#0", "final"] as const;
export type Deferral = (typeof DEFERRALS)[number];
export const PARAMETER_KEYWORDS = ["parameter", "localparam"] as const;
export type ParameterKeyword = (typeof PARAMETER_KEYWORDS)[number];
export const UNARY_OPERATORS = ["+", "-", "!", "~", "&", "~&", "|", "~|", "^", "~^", "^~"] as const;
export type UnaryOperator = (typeof UNARY_OPERATORS)[number];
export const INCREMENT_OPERATORS = ["++", "--"] as const;
export type IncrementOperator = (typeof INCREMENT_OPERATORS)[number];
export const BINARY_OPERATORS = [
  "**", "*", "/", "%", "+", "-", "<<", ">>", "<<<", ">>>", "<", "<=", ">", ">=", "==", "!=", "===", "!==", "==?",
  "!=?", "&", "^", "^~", "~^", "|", "&&", "||", "->", "<->"
] as const;
export type BinaryOperator = (typeof BINARY_OPERATORS)[number];
export const ASSIGNMENT_OPERATORS = [
  "=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=", "<<<=", ">>>="
] as const;
export type AssignmentOperator = (typeof ASSIGNMENT_OPERATORS)[number];
export const STATEMENT_ASSIGNMENTS = [
  "=", "<=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=", "<<<=", ">>>="
] as const;
export type StatementAssignment = (typeof STATEMENT_ASSIGNMENTS)[number];
export const SELECT_OPERATORS = [":", "+:", "-:"] as const;
export type SelectOperator = (typeof SELECT_OPERATORS)[number];
export const UNBASED_VALUES = ["0", "1", "x", "z", "X", "Z"] as const;
export type UnbasedValue = (typeof UNBASED_VALUES)[number];
export const MODULE_KEYWORDS = ["module", "macromodule"] as const;
export type ModuleKeyword = (typeof MODULE_KEYWORDS)[number];
export const VISIBILITYS = ["local", "protected"] as const;
export type Visibility = (typeof VISIBILITYS)[number];
export const RANDOM_QUALIFIERS = ["rand", "randc"] as const;
export type RandomQualifier = (typeof RANDOM_QUALIFIERS)[number];
export const FORWARD_KEYWORDS = ["enum", "struct", "union", "class", "interface class"] as const;
export type ForwardKeyword = (typeof FORWARD_KEYWORDS)[number];
export const DEFAULT_NETTYPES = [
  "wire", "tri", "tri0", "tri1", "triand", "trior", "trireg", "wand", "wor", "uwire", "none"
] as const;
export type DefaultNettype = (typeof DEFAULT_NETTYPES)[number];

// --- Categories ---

/** A name: what declarations declare and what expressions and types refer to (A.9.3). */
export abstract class Name extends SyntaxNode {}

/** An expression (11, A.8). */
export abstract class Expression extends SyntaxNode {}

/** A literal number or string (5.7, 5.9). */
export abstract class Literal extends Expression {}

/** A data type (6, A.2.2.1), or the implicit type of a declaration that gives only a signing or dimensions. */
export abstract class DataType extends SyntaxNode {}

/** A packed or unpacked dimension (7.4, A.2.5). */
export abstract class Dimension extends SyntaxNode {}

/**
 * What source text, a design unit, a package or a generate block lists: design units, declarations, assignments,
 * procedural blocks, generate constructs and instantiations (A.1).
 */
export abstract class Item extends SyntaxNode {}

/**
 * A port in a design unit's header: an ANSI port declaration, an interface port, or a non-ANSI port's name
 * (23.2).
 */
export abstract class Port extends SyntaxNode {}

/** A procedural statement (12, A.6.4). */
export abstract class Statement extends SyntaxNode {}

/** A delay or event control (9.4, A.6.5). */
export abstract class TimingControl extends SyntaxNode {}

/**
 * A named or wildcard connection of a port, a parameter or an argument (23.3.2, 13.5.4); ordered ones are
 * expressions.
 */
export abstract class Connection extends SyntaxNode {}

/** A range of values, in a set (`inside`, a case item) (11.4.13). */
export abstract class Range extends SyntaxNode {}

/** A compiler directive (22), where items or statements are listed. */
export abstract class Directive extends SyntaxNode {}

// === Lexical conventions (5) ===

const CommentSpec = {
  block: flag(),
  text: text(),
  trailing: flag(),
};
export interface Comment extends Properties<typeof CommentSpec> {}
/**
 * `// text` or, with `block`, `/* text *\/`. `text` excludes the delimiters. A `trailing` comment ends the line of
 * the item before it (5.4).
 */
export class Comment extends SyntaxNode {
  static override SPEC = CommentSpec;
}

const IdentifierSpec = {
  spelling: text(),
};
export interface Identifier extends Properties<typeof IdentifierSpec> {}
/**
 * A simple identifier, letters, digits, `_` and `$` not starting with a digit or `$`, or an escaped one: `\` and
 * printable characters up to white space, which the spelling ends with no space (5.6).
 */
export class Identifier extends Name {
  static override SPEC = IdentifierSpec;
  override check(): string[] {
    const spelling = this.spelling;
    if (typeof spelling !== "string" || spelling === "") return [];
    if (spelling[0] === "\\") {
      if (spelling.length > 1 && [...spelling.slice(1)].every((ch) => ch >= "!" && ch <= "~")) return [];
    } else if (!"0123456789$".includes(spelling[0] as string) && /^[A-Za-z0-9_$]+$/.test(spelling)) {
      return [];
    }
    return [`${repr(spelling)} is not an identifier`];
  }
}

const ScopedNameSpec = {
  scope: one(() => [Identifier, ParameterizedName]),
  name: one(() => [Name]),
};
export interface ScopedName extends Properties<typeof ScopedNameSpec> {}
/**
 * `scope::name`: a name in a package or a class, whose scope may be a parameterized class (26.3, 8.23). A name
 * of several scopes nests to the right: `p::c::x` is `p::(c::x)`.
 */
export class ScopedName extends Name {
  static override SPEC = ScopedNameSpec;
  static override SINCE: Availability | null = sv();
}

const ParameterizedNameSpec = {
  name: one(() => [Identifier]),
  parameters: many(() => [Expression, DataType, Connection]),
};
export interface ParameterizedName extends Properties<typeof ParameterizedNameSpec> {}
/**
 * `name #(parameters)`: a parameterized class, as a type or as a scope (8.25). Parameters are ordered expressions
 * or types, or `NamedConnection`s.
 */
export class ParameterizedName extends Name {
  static override SPEC = ParameterizedNameSpec;
  static override SINCE: Availability | null = sv();
}

// === Source text (A.1) ===

const SourceTextSpec = {
  items: many(() => [Item, Directive, Comment]),
};
export interface SourceText extends Properties<typeof SourceTextSpec> {}
/** A source file: design units, declarations, directives and comments (3.12, A.1.2). */
export class SourceText extends SyntaxNode {
  static override SPEC = SourceTextSpec;
}

const ModuleDeclarationSpec = {
  keyword: choice(...MODULE_KEYWORDS),
  lifetime: optionalChoice(...LIFETIMES),
  name: one(() => [Identifier]),
  imports: many(() => [ImportDeclaration]),
  parameters: many(() => [ParameterDeclaration, TypeParameterDeclaration]),
  ports: many(() => [Port]),
  items: many(() => [Item, Directive, Comment]),
  labeled: flag(),
};
export interface ModuleDeclaration extends Properties<typeof ModuleDeclarationSpec> {}
/**
 * `module name #(parameters) (ports); items endmodule` (23.2). Parameters in the header are listed even when
 * empty; ports are `AnsiPort`s or `InterfacePort`s, or for a non-ANSI header `PortReference`s, which `PortDeclaration`
 * items declare. `labeled` repeats the name after `endmodule`.
 */
export class ModuleDeclaration extends Item {
  static override SPEC = ModuleDeclarationSpec;
  static override FEATURES: Features = {
    lifetime: [[true, verilog(2001)]],
    imports: [[true, sv(2009)]],
    labeled: [[true, sv()]],
  };
}

const InterfaceDeclarationSpec = {
  lifetime: optionalChoice(...LIFETIMES),
  name: one(() => [Identifier]),
  imports: many(() => [ImportDeclaration]),
  parameters: many(() => [ParameterDeclaration, TypeParameterDeclaration]),
  ports: many(() => [Port]),
  items: many(() => [Item, Directive, Comment]),
  labeled: flag(),
};
export interface InterfaceDeclaration extends Properties<typeof InterfaceDeclarationSpec> {}
/** `interface name #(parameters) (ports); items endinterface` (25.3). */
export class InterfaceDeclaration extends Item {
  static override SPEC = InterfaceDeclarationSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { imports: [[true, sv(2009)]] };
}

const ProgramDeclarationSpec = {
  lifetime: optionalChoice(...LIFETIMES),
  name: one(() => [Identifier]),
  imports: many(() => [ImportDeclaration]),
  parameters: many(() => [ParameterDeclaration, TypeParameterDeclaration]),
  ports: many(() => [Port]),
  items: many(() => [Item, Directive, Comment]),
  labeled: flag(),
};
export interface ProgramDeclaration extends Properties<typeof ProgramDeclarationSpec> {}
/** `program name #(parameters) (ports); items endprogram` (24.3). */
export class ProgramDeclaration extends Item {
  static override SPEC = ProgramDeclarationSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { imports: [[true, sv(2009)]] };
}

const PackageDeclarationSpec = {
  lifetime: optionalChoice(...LIFETIMES),
  name: one(() => [Identifier]),
  items: many(() => [Item, Directive, Comment]),
  labeled: flag(),
};
export interface PackageDeclaration extends Properties<typeof PackageDeclarationSpec> {}
/** `package name; items endpackage` (26.2). */
export class PackageDeclaration extends Item {
  static override SPEC = PackageDeclarationSpec;
  static override SINCE: Availability | null = sv();
}

// === Ports (23.2) ===

const AnsiPortSpec = {
  direction: optionalChoice(...DIRECTIONS),
  net_type: optionalChoice(...NET_TYPES),
  var: flag(),
  type: optional(() => [DataType]),
  name: one(() => [Identifier]),
  dimensions: many(() => [Dimension]),
  value: optional(() => [Expression]),
};
export interface AnsiPort extends Properties<typeof AnsiPortSpec> {}
/**
 * A port declared in an ANSI header: `direction net_type var type name dimensions = default` (23.2.2.2). Without
 * a direction, a type or a net type, a port inherits them from the port before it.
 */
export class AnsiPort extends Port {
  static override SPEC = AnsiPortSpec;
  static override SINCE: Availability | null = verilog(2001);
  static override FEATURES: Features = { var: [[true, sv()]], value: [[true, sv()]], direction: [["ref", sv()]] };
}

const InterfacePortSpec = {
  interface: optional(() => [Identifier]),
  modport: optional(() => [Identifier]),
  name: one(() => [Identifier]),
  dimensions: many(() => [Dimension]),
};
export interface InterfacePort extends Properties<typeof InterfacePortSpec> {}
/**
 * `interface_name.modport name` or `interface.modport name`, a port of an interface type (25.3.3). Without an
 * `interface`, the port is generic (`interface`).
 */
export class InterfacePort extends Port {
  static override SPEC = InterfacePortSpec;
  static override SINCE: Availability | null = sv();
}

const PortReferenceSpec = {
  name: one(() => [Identifier]),
};
export interface PortReference extends Properties<typeof PortReferenceSpec> {}
/** A non-ANSI header's port, named in the header and declared by a `PortDeclaration` item (23.2.2.1). */
export class PortReference extends Port {
  static override SPEC = PortReferenceSpec;
}

const PortDeclarationSpec = {
  direction: choice(...DIRECTIONS),
  net_type: optionalChoice(...NET_TYPES),
  var: flag(),
  type: optional(() => [DataType]),
  declarators: many(() => [VariableDeclarator]),
};
export interface PortDeclaration extends Properties<typeof PortDeclarationSpec> {}
/**
 * `direction net_type var type names;`, declaring non-ANSI ports in the body, or Verilog-1995 task and function
 * ports (23.2.2.1).
 */
export class PortDeclaration extends Item {
  static override SPEC = PortDeclarationSpec;
  static override FEATURES: Features = { var: [[true, sv()]], direction: [["ref", sv()]] };
}

// === Parameters (6.20) ===

const ParameterDeclarationSpec = {
  keyword: optionalChoice(...PARAMETER_KEYWORDS),
  type: optional(() => [DataType]),
  assignments: many(() => [ParamAssignment]),
};
export interface ParameterDeclaration extends Properties<typeof ParameterDeclarationSpec> {}
/**
 * `parameter type name = value, ...;` or `localparam ...` (6.20.1). In a header's parameter list, each is one
 * entry, which may give no keyword (it is then a `parameter`, or the keyword of the entry before it) and, as a
 * `parameter`, no value.
 */
export class ParameterDeclaration extends Item {
  static override SPEC = ParameterDeclarationSpec;
  static override FEATURES: Features = { keyword: [["localparam", verilog(2001)]] };
}

const ParamAssignmentSpec = {
  name: one(() => [Identifier]),
  dimensions: many(() => [Dimension]),
  value: optional(() => [Expression]),
};
export interface ParamAssignment extends Properties<typeof ParamAssignmentSpec> {}
/** `name dimensions = value` in a parameter declaration (A.2.4). */
export class ParamAssignment extends SyntaxNode {
  static override SPEC = ParamAssignmentSpec;
}

const TypeParameterDeclarationSpec = {
  keyword: optionalChoice(...PARAMETER_KEYWORDS),
  assignments: many(() => [TypeAssignment]),
};
export interface TypeParameterDeclaration extends Properties<typeof TypeParameterDeclarationSpec> {}
/**
 * `parameter type name = type, ...` or `localparam type ...`, or in a header's parameter list `type name = type`
 * without a keyword (6.20.3).
 */
export class TypeParameterDeclaration extends Item {
  static override SPEC = TypeParameterDeclarationSpec;
  static override SINCE: Availability | null = sv();
}

const TypeAssignmentSpec = {
  name: one(() => [Identifier]),
  type: optional(() => [DataType]),
};
export interface TypeAssignment extends Properties<typeof TypeAssignmentSpec> {}
/** `name = type` in a type parameter declaration (A.2.4). */
export class TypeAssignment extends SyntaxNode {
  static override SPEC = TypeAssignmentSpec;
}

// === Data types (6) ===

const IntegerVectorTypeSpec = {
  keyword: choice(...VECTOR_KEYWORDS),
  signing: optionalChoice(...SIGNINGS),
  dimensions: many(() => [Dimension]),
};
export interface IntegerVectorType extends Properties<typeof IntegerVectorTypeSpec> {}
/** `bit`, `logic` or `reg`, with a signing and packed dimensions (6.11). */
export class IntegerVectorType extends DataType {
  static override SPEC = IntegerVectorTypeSpec;
  static override FEATURES: Features = {
    keyword: [["bit", sv()], ["logic", sv()]],
    signing: [["signed", verilog(2001)], ["unsigned", sv()]],
  };
}

const IntegerAtomTypeSpec = {
  keyword: choice(...ATOM_KEYWORDS),
  signing: optionalChoice(...SIGNINGS),
};
export interface IntegerAtomType extends Properties<typeof IntegerAtomTypeSpec> {}
/** `byte`, `shortint`, `int`, `longint`, `integer` or `time`, with a signing (6.11). */
export class IntegerAtomType extends DataType {
  static override SPEC = IntegerAtomTypeSpec;
  static override FEATURES: Features = {
    keyword: [["byte", sv()], ["shortint", sv()], ["int", sv()], ["longint", sv()]],
    signing: [[true, sv()]],
  };
}

const NonIntegerTypeSpec = {
  keyword: choice(...REAL_KEYWORDS),
};
export interface NonIntegerType extends Properties<typeof NonIntegerTypeSpec> {}
/** `shortreal`, `real` or `realtime` (6.12). */
export class NonIntegerType extends DataType {
  static override SPEC = NonIntegerTypeSpec;
  static override FEATURES: Features = { keyword: [["shortreal", sv()]] };
}

const KeywordTypeSpec = {
  keyword: choice(...SIMPLE_KEYWORDS),
};
export interface KeywordType extends Properties<typeof KeywordTypeSpec> {}
/** `string`, `chandle`, `event` or `void` (6.16, 6.14, 6.17, 6.13). */
export class KeywordType extends DataType {
  static override SPEC = KeywordTypeSpec;
  static override FEATURES: Features = { keyword: [["string", sv()], ["chandle", sv()], ["void", sv()]] };
}

const NamedTypeSpec = {
  name: one(() => [Name]),
  dimensions: many(() => [Dimension]),
};
export interface NamedType extends Properties<typeof NamedTypeSpec> {}
/** A type by its name: a typedef, a type parameter or an interface's type, with packed dimensions (6.18). */
export class NamedType extends DataType {
  static override SPEC = NamedTypeSpec;
  static override SINCE: Availability | null = sv();
}

const VirtualInterfaceTypeSpec = {
  interface_keyword: flag(),
  interface: one(() => [Identifier]),
  parameters: many(() => [Expression, DataType, Connection]),
  modport: optional(() => [Identifier]),
};
export interface VirtualInterfaceType extends Properties<typeof VirtualInterfaceTypeSpec> {}
/**
 * `virtual interface name #(parameters).modport`, a variable's type that refers to an interface instance
 * (25.9). `interface_keyword` writes the optional `interface`.
 */
export class VirtualInterfaceType extends DataType {
  static override SPEC = VirtualInterfaceTypeSpec;
  static override SINCE: Availability | null = sv();
}

const ImplicitTypeSpec = {
  signing: optionalChoice(...SIGNINGS),
  dimensions: many(() => [Dimension]),
};
export interface ImplicitType extends Properties<typeof ImplicitTypeSpec> {}
/**
 * The type a declaration gives by a signing and packed dimensions alone, such as `input [7:0] a` (6.10); also
 * the `signed` or `unsigned` of a cast.
 */
export class ImplicitType extends DataType {
  static override SPEC = ImplicitTypeSpec;
  static override FEATURES: Features = { signing: [["signed", verilog(2001)], ["unsigned", sv()]] };
}

const StructTypeSpec = {
  keyword: choice("struct", "union"),
  packed: flag(),
  signing: optionalChoice(...SIGNINGS),
  members: many(() => [StructMember]),
  dimensions: many(() => [Dimension]),
};
export interface StructType extends Properties<typeof StructTypeSpec> {}
/** `struct packed signed { members }` or `union ...`, with packed dimensions (7.2, 7.3). */
export class StructType extends DataType {
  static override SPEC = StructTypeSpec;
  static override SINCE: Availability | null = sv();
}

const StructMemberSpec = {
  type: one(() => [DataType]),
  declarators: many(() => [VariableDeclarator]),
};
export interface StructMember extends Properties<typeof StructMemberSpec> {}
/** `type declarators;` in a structure or union (7.2). */
export class StructMember extends SyntaxNode {
  static override SPEC = StructMemberSpec;
}

const EnumTypeSpec = {
  base: optional(() => [DataType]),
  members: many(() => [EnumMember]),
  dimensions: many(() => [Dimension]),
};
export interface EnumType extends Properties<typeof EnumTypeSpec> {}
/** `enum base { members }`, with packed dimensions (6.19). */
export class EnumType extends DataType {
  static override SPEC = EnumTypeSpec;
  static override SINCE: Availability | null = sv();
}

const EnumMemberSpec = {
  name: one(() => [Identifier]),
  value: optional(() => [Expression]),
};
export interface EnumMember extends Properties<typeof EnumMemberSpec> {}
/** `name = value` in an enumeration (6.19). */
export class EnumMember extends SyntaxNode {
  static override SPEC = EnumMemberSpec;
}

// --- Dimensions (7.4) ---

const RangeDimensionSpec = {
  left: one(() => [Expression]),
  right: one(() => [Expression]),
};
export interface RangeDimension extends Properties<typeof RangeDimensionSpec> {}
/** `[left:right]` (7.4.1). */
export class RangeDimension extends Dimension {
  static override SPEC = RangeDimensionSpec;
}

const SizeDimensionSpec = {
  size: one(() => [Expression]),
};
export interface SizeDimension extends Properties<typeof SizeDimensionSpec> {}
/** `[size]`, an unpacked dimension of `size` elements from 0 (7.4.2). */
export class SizeDimension extends Dimension {
  static override SPEC = SizeDimensionSpec;
  static override SINCE: Availability | null = sv();
}

const UnsizedDimensionSpec = {};
export interface UnsizedDimension extends Properties<typeof UnsizedDimensionSpec> {}
/** `[]`, a dynamic array's (7.5). */
export class UnsizedDimension extends Dimension {
  static override SPEC = UnsizedDimensionSpec;
  static override SINCE: Availability | null = sv();
}

const AssociativeDimensionSpec = {
  type: optional(() => [DataType]),
};
export interface AssociativeDimension extends Properties<typeof AssociativeDimensionSpec> {}
/** `[type]` or `[*]`, an associative array's index (7.8). */
export class AssociativeDimension extends Dimension {
  static override SPEC = AssociativeDimensionSpec;
  static override SINCE: Availability | null = sv();
}

const QueueDimensionSpec = {
  bound: optional(() => [Expression]),
};
export interface QueueDimension extends Properties<typeof QueueDimensionSpec> {}
/** `[$]` or `[$:bound]` (7.10). */
export class QueueDimension extends Dimension {
  static override SPEC = QueueDimensionSpec;
  static override SINCE: Availability | null = sv();
}

// === Declarations (A.2) ===

const NetDeclarationSpec = {
  net_type: choice(...NET_TYPES),
  type: optional(() => [DataType]),
  delay: optional(() => [DelayControl]),
  declarators: many(() => [VariableDeclarator]),
};
export interface NetDeclaration extends Properties<typeof NetDeclarationSpec> {}
/** `net_type type #delay declarators;` (6.7). */
export class NetDeclaration extends Item {
  static override SPEC = NetDeclarationSpec;
  static override FEATURES: Features = { net_type: [["uwire", verilog(2005)], ["interconnect", sv(2012)]] };
}

const VariableDeclarationSpec = {
  visibility: optionalChoice(...VISIBILITYS),
  random: optionalChoice(...RANDOM_QUALIFIERS),
  const: flag(),
  var: flag(),
  lifetime: optionalChoice(...LIFETIMES),
  type: optional(() => [DataType]),
  declarators: many(() => [VariableDeclarator]),
};
export interface VariableDeclaration extends Properties<typeof VariableDeclarationSpec> {}
/**
 * `visibility random const var lifetime type declarators;` (6.8); in a class, a property, which may be `local`
 * or `protected` and `rand` or `randc`, and is `static` by its `lifetime` (8.5, 18.4).
 */
export class VariableDeclaration extends Item {
  static override SPEC = VariableDeclarationSpec;
  static override FEATURES: Features = {
    const: [[true, sv()]],
    var: [[true, sv()]],
    lifetime: [[true, sv()]],
    visibility: [[true, sv()]],
    random: [[true, sv()]],
  };
}

const VariableDeclaratorSpec = {
  name: one(() => [Identifier]),
  dimensions: many(() => [Dimension]),
  value: optional(() => [Expression]),
};
export interface VariableDeclarator extends Properties<typeof VariableDeclaratorSpec> {}
/** `name dimensions = value` in a net, variable, port or member declaration (A.2.3). */
export class VariableDeclarator extends SyntaxNode {
  static override SPEC = VariableDeclaratorSpec;
}

const ForwardTypedefDeclarationSpec = {
  keyword: optionalChoice(...FORWARD_KEYWORDS),
  name: one(() => [Identifier]),
};
export interface ForwardTypedefDeclaration extends Properties<typeof ForwardTypedefDeclarationSpec> {}
/** `typedef keyword name;`, which declares a type before its definition (6.18). */
export class ForwardTypedefDeclaration extends Item {
  static override SPEC = ForwardTypedefDeclarationSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { keyword: [["interface class", sv(2012)]] };
}

const TypedefDeclarationSpec = {
  type: one(() => [DataType]),
  name: one(() => [Identifier]),
  dimensions: many(() => [Dimension]),
};
export interface TypedefDeclaration extends Properties<typeof TypedefDeclarationSpec> {}
/** `typedef type name dimensions;` (6.18). */
export class TypedefDeclaration extends Item {
  static override SPEC = TypedefDeclarationSpec;
  static override SINCE: Availability | null = sv();
}

const GenvarDeclarationSpec = {
  names: many(() => [Identifier]),
};
export interface GenvarDeclaration extends Properties<typeof GenvarDeclarationSpec> {}
/** `genvar names;` (27.4). */
export class GenvarDeclaration extends Item {
  static override SPEC = GenvarDeclarationSpec;
  static override SINCE: Availability | null = verilog(2001);
}

const ImportDeclarationSpec = {
  items: many(() => [ImportItem]),
};
export interface ImportDeclaration extends Properties<typeof ImportDeclarationSpec> {}
/** `import package::name, package::*;` (26.3). */
export class ImportDeclaration extends Item {
  static override SPEC = ImportDeclarationSpec;
  static override SINCE: Availability | null = sv();
}

const ImportItemSpec = {
  package: one(() => [Identifier]),
  name: optional(() => [Identifier]),
};
export interface ImportItem extends Properties<typeof ImportItemSpec> {}
/** `package::name`, or `package::*` without a `name` (26.3). */
export class ImportItem extends SyntaxNode {
  static override SPEC = ImportItemSpec;
}

const ModportDeclarationSpec = {
  items: many(() => [ModportItem]),
};
export interface ModportDeclaration extends Properties<typeof ModportDeclarationSpec> {}
/** `modport items;` in an interface (25.5). */
export class ModportDeclaration extends Item {
  static override SPEC = ModportDeclarationSpec;
  static override SINCE: Availability | null = sv();
}

const ModportItemSpec = {
  name: one(() => [Identifier]),
  ports: many(() => [ModportPort]),
};
export interface ModportItem extends Properties<typeof ModportItemSpec> {}
/** `name (ports)` in a modport declaration (25.5). */
export class ModportItem extends SyntaxNode {
  static override SPEC = ModportItemSpec;
}

const ModportPortSpec = {
  direction: choice(...DIRECTIONS),
  name: one(() => [Identifier]),
};
export interface ModportPort extends Properties<typeof ModportPortSpec> {}
/** `direction name` in a modport (25.5). */
export class ModportPort extends SyntaxNode {
  static override SPEC = ModportPortSpec;
}

const ContinuousAssignSpec = {
  delay: optional(() => [DelayControl]),
  assignments: many(() => [AssignmentExpression]),
};
export interface ContinuousAssign extends Properties<typeof ContinuousAssignSpec> {}
/** `assign #delay target = value, ...;` (10.3). */
export class ContinuousAssign extends Item {
  static override SPEC = ContinuousAssignSpec;
}

const AlwaysConstructSpec = {
  keyword: choice(...ALWAYS_KEYWORDS),
  body: one(() => [Statement]),
};
export interface AlwaysConstruct extends Properties<typeof AlwaysConstructSpec> {}
/** `always body`, `always_comb`, `always_ff` or `always_latch` (9.2.2). */
export class AlwaysConstruct extends Item {
  static override SPEC = AlwaysConstructSpec;
  static override FEATURES: Features = {
    keyword: [["always_comb", sv()], ["always_ff", sv()], ["always_latch", sv()]],
  };
}

const InitialConstructSpec = {
  body: one(() => [Statement]),
};
export interface InitialConstruct extends Properties<typeof InitialConstructSpec> {}
/** `initial body` (9.2.1). */
export class InitialConstruct extends Item {
  static override SPEC = InitialConstructSpec;
}

const FinalConstructSpec = {
  body: one(() => [Statement]),
};
export interface FinalConstruct extends Properties<typeof FinalConstructSpec> {}
/** `final body` (9.2.3). */
export class FinalConstruct extends Item {
  static override SPEC = FinalConstructSpec;
  static override SINCE: Availability | null = sv();
}

const FunctionDeclarationSpec = {
  extern: flag(),
  pure: flag(),
  virtual: flag(),
  visibility: optionalChoice(...VISIBILITYS),
  static: flag(),
  lifetime: optionalChoice(...LIFETIMES),
  type: optional(() => [DataType]),
  name: one(() => [Name]),
  ports: many(() => [TfPort]),
  body: many(() => [Item, Statement, Directive, Comment]),
  labeled: flag(),
};
export interface FunctionDeclaration extends Properties<typeof FunctionDeclarationSpec> {}
/**
 * `function lifetime type name(ports); body endfunction` (13.4). The body lists declarations and statements in
 * order. Without ports in parentheses, Verilog-1995 style, `PortDeclaration`s in the body declare them.
 * In a class, a method may be `local` or `protected`, `static`, `virtual`, and a prototype without a body:
 * `extern`, defined outside the class, or `pure virtual` (8.10, 8.20, 8.24). A constructor is named `new`.
 */
export class FunctionDeclaration extends Item {
  static override SPEC = FunctionDeclarationSpec;
  static override FEATURES: Features = {
    lifetime: [[true, verilog(2001)]],
    labeled: [[true, sv()]],
    extern: [[true, sv()]],
    pure: [[true, sv()]],
    virtual: [[true, sv()]],
    visibility: [[true, sv()]],
    static: [[true, sv()]],
  };
  override check(): string[] {
    return methodProblems(this);
  }
}

const TaskDeclarationSpec = {
  extern: flag(),
  pure: flag(),
  virtual: flag(),
  visibility: optionalChoice(...VISIBILITYS),
  static: flag(),
  lifetime: optionalChoice(...LIFETIMES),
  name: one(() => [Name]),
  ports: many(() => [TfPort]),
  body: many(() => [Item, Statement, Directive, Comment]),
  labeled: flag(),
};
export interface TaskDeclaration extends Properties<typeof TaskDeclarationSpec> {}
/**
 * `task lifetime name(ports); body endtask` (13.3). In a class, a method may be `local` or `protected`, `static`,
 * `virtual`, and a prototype without a body: `extern`, defined outside the class, or `pure virtual` (8.10, 8.20, 8.24).
 * A constructor is named `new`.
 */
export class TaskDeclaration extends Item {
  static override SPEC = TaskDeclarationSpec;
  static override FEATURES: Features = {
    lifetime: [[true, verilog(2001)]],
    labeled: [[true, sv()]],
    extern: [[true, sv()]],
    pure: [[true, sv()]],
    virtual: [[true, sv()]],
    visibility: [[true, sv()]],
    static: [[true, sv()]],
  };
  override check(): string[] {
    return methodProblems(this);
  }
}

const TfPortSpec = {
  direction: optionalChoice(...DIRECTIONS),
  var: flag(),
  type: optional(() => [DataType]),
  name: one(() => [Identifier]),
  dimensions: many(() => [Dimension]),
  value: optional(() => [Expression]),
};
export interface TfPort extends Properties<typeof TfPortSpec> {}
/**
 * `direction var type name dimensions = default`, a task's or function's port in parentheses (13.3). Without a
 * direction or a type, a port inherits them from the one before it.
 */
export class TfPort extends SyntaxNode {
  static override SPEC = TfPortSpec;
  static override SINCE: Availability | null = verilog(2001);
  static override FEATURES: Features = { var: [[true, sv()]], value: [[true, sv()]], direction: [["ref", sv()]] };
}

// --- Classes (8) ---

const ClassDeclarationSpec = {
  virtual: flag(),
  interface: flag(),
  name: one(() => [Identifier]),
  parameters: many(() => [ParameterDeclaration, TypeParameterDeclaration]),
  base: optional(() => [NamedType]),
  arguments: many(() => [Expression, Connection]),
  interfaces: many(() => [NamedType]),
  items: many(() => [Item, Directive, Comment]),
  labeled: flag(),
};
export interface ClassDeclaration extends Properties<typeof ClassDeclarationSpec> {}
/**
 * `virtual class name #(parameters) extends base(arguments) implements interfaces; items endclass`, or
 * `interface class name #(parameters) extends interfaces; items endclass` (8.3, 8.26). Its items are properties,
 * methods, parameters, types and classes. `labeled` repeats the name after `endclass`.
 */
export class ClassDeclaration extends Item {
  static override SPEC = ClassDeclarationSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { interface: [[true, sv(2012)]], interfaces: [[true, sv(2012)]] };
  override check(): string[] {
    if (this.interface === true && (this.virtual === true || this.base !== null || this.arguments.length > 0)) {
      return ["an interface ClassDeclaration has no virtual, base or arguments"];
    }
    if (this.arguments.length > 0 && this.base === null) return ["a ClassDeclaration with arguments has a base"];
    return [];
  }
}

// --- Generate constructs (27) ---

const GenerateRegionSpec = {
  items: many(() => [Item, Directive, Comment]),
};
export interface GenerateRegion extends Properties<typeof GenerateRegionSpec> {}
/** `generate items endgenerate` (27.3). */
export class GenerateRegion extends Item {
  static override SPEC = GenerateRegionSpec;
  static override SINCE: Availability | null = verilog(2001);
}

const GenerateForSpec = {
  genvar: flag(),
  name: one(() => [Identifier]),
  start: one(() => [Expression]),
  condition: one(() => [Expression]),
  step: one(() => [Expression]),
  body: one(() => [Item]),
};
export interface GenerateFor extends Properties<typeof GenerateForSpec> {}
/** `for (genvar name = start; condition; step) body` (27.4). */
export class GenerateFor extends Item {
  static override SPEC = GenerateForSpec;
  static override SINCE: Availability | null = verilog(2001);
  static override FEATURES: Features = { genvar: [[true, verilog(2005)]] };
}

const GenerateIfSpec = {
  condition: one(() => [Expression]),
  consequence: one(() => [Item]),
  alternative: optional(() => [Item]),
};
export interface GenerateIf extends Properties<typeof GenerateIfSpec> {}
/** `if (condition) consequence else alternative` among items (27.5). */
export class GenerateIf extends Item {
  static override SPEC = GenerateIfSpec;
  static override SINCE: Availability | null = verilog(2001);
}

const GenerateCaseSpec = {
  expression: one(() => [Expression]),
  items: many(() => [CaseItem]),
};
export interface GenerateCase extends Properties<typeof GenerateCaseSpec> {}
/** `case (expression) items endcase` among items (27.5). */
export class GenerateCase extends Item {
  static override SPEC = GenerateCaseSpec;
  static override SINCE: Availability | null = verilog(2001);
}

const GenerateBlockSpec = {
  name: optional(() => [Identifier]),
  items: many(() => [Item, Directive, Comment]),
  labeled: flag(),
};
export interface GenerateBlock extends Properties<typeof GenerateBlockSpec> {}
/** `begin : name items end : name` in a generate construct (27.3). `labeled` repeats the name after `end`. */
export class GenerateBlock extends Item {
  static override SPEC = GenerateBlockSpec;
  static override SINCE: Availability | null = verilog(2001);
  static override FEATURES: Features = { labeled: [[true, sv()]] };
}

// --- Instantiation (23.3) ---

const ModuleInstantiationSpec = {
  module: one(() => [Identifier]),
  parameters: many(() => [Expression, DataType, Connection]),
  instances: many(() => [Instance]),
};
export interface ModuleInstantiation extends Properties<typeof ModuleInstantiationSpec> {}
/**
 * `module #(parameters) instance (connections), ...;`, of a module, an interface or a program (23.3).
 * Parameters and connections are ordered expressions or `NamedConnection`s.
 */
export class ModuleInstantiation extends Item {
  static override SPEC = ModuleInstantiationSpec;
}

const InstanceSpec = {
  name: one(() => [Identifier]),
  dimensions: many(() => [Dimension]),
  connections: many(() => [Expression, Connection]),
};
export interface Instance extends Properties<typeof InstanceSpec> {}
/** `name dimensions (connections)` in an instantiation (23.3.2). */
export class Instance extends SyntaxNode {
  static override SPEC = InstanceSpec;
}

const NamedConnectionSpec = {
  name: one(() => [Identifier]),
  value: optional(() => [Expression, DataType]),
  implicit: flag(),
};
export interface NamedConnection extends Properties<typeof NamedConnectionSpec> {}
/**
 * `.name(value)`; `.name()` without a value leaves it unconnected, and an `implicit` `.name` connects it to
 * what has its name (23.3.2.2, 23.3.2.3). In a call, a named argument.
 */
export class NamedConnection extends Connection {
  static override SPEC = NamedConnectionSpec;
  static override FEATURES: Features = { implicit: [[true, sv()]] };
}

const WildcardConnectionSpec = {};
export interface WildcardConnection extends Properties<typeof WildcardConnectionSpec> {}
/** `.*`, connecting every port to what has its name (23.3.2.4). */
export class WildcardConnection extends Connection {
  static override SPEC = WildcardConnectionSpec;
  static override SINCE: Availability | null = sv();
}

// === Statements (12) ===

const AssignmentStatementSpec = {
  target: one(() => [Expression]),
  operator: choice(...STATEMENT_ASSIGNMENTS),
  timing: optional(() => [TimingControl]),
  value: one(() => [Expression]),
};
export interface AssignmentStatement extends Properties<typeof AssignmentStatementSpec> {}
/**
 * `target = timing value;`: blocking (`=`), nonblocking (`<=`) or an assignment operator (`+=`), with an
 * intra-assignment delay or event control (10.4, 11.4.1).
 */
export class AssignmentStatement extends Statement {
  static override SPEC = AssignmentStatementSpec;
  static override FEATURES: Features = {
    operator: [
      ["+=", sv()], ["-=", sv()], ["*=", sv()], ["/=", sv()], ["%=", sv()], ["&=", sv()], ["|=", sv()], ["^=", sv()],
      ["<<=", sv()], [">>=", sv()], ["<<<=", sv()], [">>>=", sv()]
    ],
  };
}

const ExpressionStatementSpec = {
  expression: one(() => [Expression]),
};
export interface ExpressionStatement extends Properties<typeof ExpressionStatementSpec> {}
/** `expression;`: a call, or an increment or decrement (12.3). */
export class ExpressionStatement extends Statement {
  static override SPEC = ExpressionStatementSpec;
}

const NullStatementSpec = {};
export interface NullStatement extends Properties<typeof NullStatementSpec> {}
/** `;` (12.3). */
export class NullStatement extends Statement {
  static override SPEC = NullStatementSpec;
}

const SeqBlockSpec = {
  name: optional(() => [Identifier]),
  items: many(() => [Item, Statement, Directive, Comment]),
  labeled: flag(),
};
export interface SeqBlock extends Properties<typeof SeqBlockSpec> {}
/** `begin : name items end : name`, declarations then statements (9.3.1). `labeled` repeats the name after `end`. */
export class SeqBlock extends Statement {
  static override SPEC = SeqBlockSpec;
  static override FEATURES: Features = { labeled: [[true, sv()]] };
}

const ParBlockSpec = {
  name: optional(() => [Identifier]),
  items: many(() => [Item, Statement, Directive, Comment]),
  join: choice(...JOIN_KEYWORDS),
  labeled: flag(),
};
export interface ParBlock extends Properties<typeof ParBlockSpec> {}
/** `fork : name items join` or `join_any` or `join_none` (9.3.2). */
export class ParBlock extends Statement {
  static override SPEC = ParBlockSpec;
  static override FEATURES: Features = { join: [["join_any", sv()], ["join_none", sv()]], labeled: [[true, sv()]] };
}

const IfStatementSpec = {
  qualifier: optionalChoice(...QUALIFIERS),
  condition: one(() => [Expression]),
  consequence: one(() => [Statement]),
  alternative: optional(() => [Statement]),
};
export interface IfStatement extends Properties<typeof IfStatementSpec> {}
/** `qualifier if (condition) consequence else alternative` (12.4). */
export class IfStatement extends Statement {
  static override SPEC = IfStatementSpec;
  static override FEATURES: Features = { qualifier: [["unique", sv()], ["priority", sv()], ["unique0", sv(2009)]] };
}

const CaseStatementSpec = {
  qualifier: optionalChoice(...QUALIFIERS),
  keyword: choice(...CASE_KEYWORDS),
  expression: one(() => [Expression]),
  inside: flag(),
  items: many(() => [CaseItem]),
};
export interface CaseStatement extends Properties<typeof CaseStatementSpec> {}
/** `qualifier case (expression) inside items endcase`, or `casez` or `casex` (12.5). */
export class CaseStatement extends Statement {
  static override SPEC = CaseStatementSpec;
  static override FEATURES: Features = {
    qualifier: [["unique", sv()], ["priority", sv()], ["unique0", sv(2009)]],
    inside: [[true, sv()]],
  };
}

const CaseItemSpec = {
  expressions: many(() => [Expression, Range]),
  body: one(() => [Statement, Item]),
};
export interface CaseItem extends Properties<typeof CaseItemSpec> {}
/**
 * `expressions: body`, or `default: body` without expressions, in a case statement or a case generate construct
 * (12.5).
 */
export class CaseItem extends SyntaxNode {
  static override SPEC = CaseItemSpec;
}

const ForStatementSpec = {
  initializers: many(() => [VariableDeclaration, AssignmentExpression]),
  condition: optional(() => [Expression]),
  steps: many(() => [Expression]),
  body: one(() => [Statement]),
};
export interface ForStatement extends Properties<typeof ForStatementSpec> {}
/** `for (initializers; condition; steps) body` (12.7.1). */
export class ForStatement extends Statement {
  static override SPEC = ForStatementSpec;
  override features(): [string, Availability][] {
    if (this.initializers.some((i) => i instanceof VariableDeclaration) || this.initializers.length > 1) {
      return [["ForStatement.initializers declarations", sv()]];
    }
    return [];
  }
}

const WhileStatementSpec = {
  condition: one(() => [Expression]),
  body: one(() => [Statement]),
};
export interface WhileStatement extends Properties<typeof WhileStatementSpec> {}
/** `while (condition) body` (12.7.4). */
export class WhileStatement extends Statement {
  static override SPEC = WhileStatementSpec;
}

const DoWhileStatementSpec = {
  body: one(() => [Statement]),
  condition: one(() => [Expression]),
};
export interface DoWhileStatement extends Properties<typeof DoWhileStatementSpec> {}
/** `do body while (condition);` (12.7.5). */
export class DoWhileStatement extends Statement {
  static override SPEC = DoWhileStatementSpec;
  static override SINCE: Availability | null = sv();
}

const RepeatStatementSpec = {
  count: one(() => [Expression]),
  body: one(() => [Statement]),
};
export interface RepeatStatement extends Properties<typeof RepeatStatementSpec> {}
/** `repeat (count) body` (12.7.2). */
export class RepeatStatement extends Statement {
  static override SPEC = RepeatStatementSpec;
}

const ForeverStatementSpec = {
  body: one(() => [Statement]),
};
export interface ForeverStatement extends Properties<typeof ForeverStatementSpec> {}
/** `forever body` (12.7.2). */
export class ForeverStatement extends Statement {
  static override SPEC = ForeverStatementSpec;
}

const ForeachStatementSpec = {
  array: one(() => [Expression]),
  variables: many(() => [Identifier]),
  body: one(() => [Statement]),
};
export interface ForeachStatement extends Properties<typeof ForeachStatementSpec> {}
/** `foreach (array[variables]) body` (12.7.3). */
export class ForeachStatement extends Statement {
  static override SPEC = ForeachStatementSpec;
  static override SINCE: Availability | null = sv();
}

const BreakStatementSpec = {};
export interface BreakStatement extends Properties<typeof BreakStatementSpec> {}
/** `break;` (12.8). */
export class BreakStatement extends Statement {
  static override SPEC = BreakStatementSpec;
  static override SINCE: Availability | null = sv();
}

const ContinueStatementSpec = {};
export interface ContinueStatement extends Properties<typeof ContinueStatementSpec> {}
/** `continue;` (12.8). */
export class ContinueStatement extends Statement {
  static override SPEC = ContinueStatementSpec;
  static override SINCE: Availability | null = sv();
}

const ReturnStatementSpec = {
  value: optional(() => [Expression]),
};
export interface ReturnStatement extends Properties<typeof ReturnStatementSpec> {}
/** `return value;` (12.8). */
export class ReturnStatement extends Statement {
  static override SPEC = ReturnStatementSpec;
  static override SINCE: Availability | null = sv();
}

const TimedStatementSpec = {
  timing: one(() => [TimingControl]),
  body: optional(() => [Statement]),
};
export interface TimedStatement extends Properties<typeof TimedStatementSpec> {}
/** `timing body`, a statement after a delay or an event control; without a body, `timing;` (9.4). */
export class TimedStatement extends Statement {
  static override SPEC = TimedStatementSpec;
}

const WaitStatementSpec = {
  condition: one(() => [Expression]),
  body: optional(() => [Statement]),
};
export interface WaitStatement extends Properties<typeof WaitStatementSpec> {}
/** `wait (condition) body`; without a body, `wait (condition);` (9.4.3). */
export class WaitStatement extends Statement {
  static override SPEC = WaitStatementSpec;
}

const EventTriggerSpec = {
  nonblocking: flag(),
  event: one(() => [Expression]),
};
export interface EventTrigger extends Properties<typeof EventTriggerSpec> {}
/** `-> event;`, or `->> event;` when `nonblocking` (15.5.1). */
export class EventTrigger extends Statement {
  static override SPEC = EventTriggerSpec;
  static override FEATURES: Features = { nonblocking: [[true, sv()]] };
}

const DisableStatementSpec = {
  target: optional(() => [Expression]),
};
export interface DisableStatement extends Properties<typeof DisableStatementSpec> {}
/** `disable target;`, or `disable fork;` without a target (9.6.2, 9.6.3). */
export class DisableStatement extends Statement {
  static override SPEC = DisableStatementSpec;
  override features(): [string, Availability][] {
    return this.target === null ? [["DisableStatement fork", sv()]] : [];
  }
}

const ImmediateAssertionSpec = {
  keyword: choice(...ASSERTION_KEYWORDS),
  deferral: optionalChoice(...DEFERRALS),
  expression: one(() => [Expression]),
  pass_action: optional(() => [Statement]),
  fail_action: optional(() => [Statement]),
};
export interface ImmediateAssertion extends Properties<typeof ImmediateAssertionSpec> {}
/**
 * `assert (expression) pass else fail`, or `assume` or `cover`, deferred with `#0` or `final` (16.3, 16.4).
 * `cover` has no `fail`.
 */
export class ImmediateAssertion extends Statement {
  static override SPEC = ImmediateAssertionSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { deferral: [["#0", sv(2009)], ["final", sv(2012)]] };
}

// === Timing controls (9.4) ===

const DelayControlSpec = {
  value: one(() => [Expression]),
};
export interface DelayControl extends Properties<typeof DelayControlSpec> {}
/** `#value`: a number, a time literal, a name or a parenthesized expression (9.4.1). */
export class DelayControl extends TimingControl {
  static override SPEC = DelayControlSpec;
}

const EventControlSpec = {
  events: many(() => [EventExpression]),
};
export interface EventControl extends Properties<typeof EventControlSpec> {}
/** `@(events)`, joined by `or`, or `@(*)` without events (9.4.2). */
export class EventControl extends TimingControl {
  static override SPEC = EventControlSpec;
  override features(): [string, Availability][] {
    return this.events.length === 0 ? [["EventControl *", verilog(2001)]] : [];
  }
}

const EventExpressionSpec = {
  edge: optionalChoice(...EDGES),
  expression: one(() => [Expression]),
  condition: optional(() => [Expression]),
};
export interface EventExpression extends Properties<typeof EventExpressionSpec> {}
/** `edge expression iff condition` (9.4.2). */
export class EventExpression extends SyntaxNode {
  static override SPEC = EventExpressionSpec;
  static override FEATURES: Features = { edge: [["edge", sv()]], condition: [[true, sv()]] };
}

// === Expressions (11) ===

const NameExpressionSpec = {
  name: one(() => [Name]),
};
export interface NameExpression extends Properties<typeof NameExpressionSpec> {}
/** A name used as a value (A.8.4). */
export class NameExpression extends Expression {
  static override SPEC = NameExpressionSpec;
}

const MemberExpressionSpec = {
  value: one(() => [Expression]),
  member: one(() => [Identifier]),
};
export interface MemberExpression extends Properties<typeof MemberExpressionSpec> {}
/** `value.member`: a structure's member, an interface's signal, or a step of a hierarchical name (7.2, 23.6). */
export class MemberExpression extends Expression {
  static override SPEC = MemberExpressionSpec;
}

const IndexExpressionSpec = {
  value: one(() => [Expression]),
  index: one(() => [Expression]),
};
export interface IndexExpression extends Properties<typeof IndexExpressionSpec> {}
/** `value[index]`: a bit select or an array element (11.5.1). */
export class IndexExpression extends Expression {
  static override SPEC = IndexExpressionSpec;
}

const RangeSelectSpec = {
  value: one(() => [Expression]),
  left: one(() => [Expression]),
  operator: choice(...SELECT_OPERATORS),
  right: one(() => [Expression]),
};
export interface RangeSelect extends Properties<typeof RangeSelectSpec> {}
/** `value[left:right]`, or an indexed part select `value[base+:width]` or `value[base-:width]` (11.5.1). */
export class RangeSelect extends Expression {
  static override SPEC = RangeSelectSpec;
  static override FEATURES: Features = { operator: [["+:", verilog(2001)], ["-:", verilog(2001)]] };
}

const IntegerLiteralSpec = {
  spelling: text(),
};
export interface IntegerLiteral extends Properties<typeof IntegerLiteralSpec> {}
/** An integer, spelled as written: size, signing, base and digits, with underscores, `x`, `z` and `?` (5.7.1). */
export class IntegerLiteral extends Literal {
  static override SPEC = IntegerLiteralSpec;
}

const RealLiteralSpec = {
  spelling: text(),
};
export interface RealLiteral extends Properties<typeof RealLiteralSpec> {}
/** A real number, spelled as written (5.7.2). */
export class RealLiteral extends Literal {
  static override SPEC = RealLiteralSpec;
}

const TimeLiteralSpec = {
  spelling: text(),
};
export interface TimeLiteral extends Properties<typeof TimeLiteralSpec> {}
/** A time, such as `10ns`, spelled as written (5.8). */
export class TimeLiteral extends Literal {
  static override SPEC = TimeLiteralSpec;
  static override SINCE: Availability | null = sv();
}

const UnbasedUnsizedLiteralSpec = {
  value: choice(...UNBASED_VALUES),
};
export interface UnbasedUnsizedLiteral extends Properties<typeof UnbasedUnsizedLiteralSpec> {}
/** `'0`, `'1`, `'x` or `'z`: every bit of its context's width (5.7.1). */
export class UnbasedUnsizedLiteral extends Literal {
  static override SPEC = UnbasedUnsizedLiteralSpec;
  static override SINCE: Availability | null = sv();
}

const StringLiteralSpec = {
  text: text(),
  triple: flag(),
};
export interface StringLiteral extends Properties<typeof StringLiteralSpec> {}
/** `"text"`, or with `triple` `"""text"""`, spelled as written, escapes and line breaks included (5.9). */
export class StringLiteral extends Literal {
  static override SPEC = StringLiteralSpec;
  static override FEATURES: Features = { triple: [[true, sv(2023)]] };
}

const UnaryExpressionSpec = {
  operator: choice(...UNARY_OPERATORS),
  operand: one(() => [Expression]),
};
export interface UnaryExpression extends Properties<typeof UnaryExpressionSpec> {}
/** `operator operand`, including the reductions `&`, `~&`, `|`, `~|`, `^`, `~^` (11.4). */
export class UnaryExpression extends Expression {
  static override SPEC = UnaryExpressionSpec;
}

const IncrementExpressionSpec = {
  operator: choice(...INCREMENT_OPERATORS),
  postfix: flag(),
  operand: one(() => [Expression]),
};
export interface IncrementExpression extends Properties<typeof IncrementExpressionSpec> {}
/** `++operand`, `--operand`, or with `postfix` `operand++`, `operand--` (11.4.2). */
export class IncrementExpression extends Expression {
  static override SPEC = IncrementExpressionSpec;
  static override SINCE: Availability | null = sv();
}

const BinaryExpressionSpec = {
  left: one(() => [Expression]),
  operator: choice(...BINARY_OPERATORS),
  right: one(() => [Expression]),
};
export interface BinaryExpression extends Properties<typeof BinaryExpressionSpec> {}
/** `left operator right` (11.4). */
export class BinaryExpression extends Expression {
  static override SPEC = BinaryExpressionSpec;
  static override FEATURES: Features = {
    operator: [
      ["**", verilog(2001)], ["<<<", verilog(2001)], [">>>", verilog(2001)], ["==?", sv()], ["!=?", sv()],
      ["->", sv(2009)], ["<->", sv(2009)]
    ],
  };
}

const AssignmentExpressionSpec = {
  target: one(() => [Expression]),
  operator: choice(...ASSIGNMENT_OPERATORS),
  value: one(() => [Expression]),
};
export interface AssignmentExpression extends Properties<typeof AssignmentExpressionSpec> {}
/**
 * `target operator value`: in a continuous assignment, a `for` loop's initializers and steps, or parenthesized as
 * an expression (10.3, 11.4.1).
 */
export class AssignmentExpression extends Expression {
  static override SPEC = AssignmentExpressionSpec;
  static override FEATURES: Features = {
    operator: [
      ["+=", sv()], ["-=", sv()], ["*=", sv()], ["/=", sv()], ["%=", sv()], ["&=", sv()], ["|=", sv()], ["^=", sv()],
      ["<<=", sv()], [">>=", sv()], ["<<<=", sv()], [">>>=", sv()]
    ],
  };
}

const ConditionalExpressionSpec = {
  condition: one(() => [Expression]),
  consequence: one(() => [Expression]),
  alternative: one(() => [Expression]),
};
export interface ConditionalExpression extends Properties<typeof ConditionalExpressionSpec> {}
/** `condition ? consequence : alternative` (11.4.11). */
export class ConditionalExpression extends Expression {
  static override SPEC = ConditionalExpressionSpec;
}

const InsideExpressionSpec = {
  value: one(() => [Expression]),
  set: many(() => [Expression, Range]),
};
export interface InsideExpression extends Properties<typeof InsideExpressionSpec> {}
/** `value inside {set}` (11.4.13). */
export class InsideExpression extends Expression {
  static override SPEC = InsideExpressionSpec;
  static override SINCE: Availability | null = sv();
}

const ValueRangeSpec = {
  left: one(() => [Expression]),
  right: one(() => [Expression]),
};
export interface ValueRange extends Properties<typeof ValueRangeSpec> {}
/** `[left:right]` in a set (11.4.13). */
export class ValueRange extends Range {
  static override SPEC = ValueRangeSpec;
  static override SINCE: Availability | null = sv();
}

const ConcatenationSpec = {
  items: many(() => [Expression]),
};
export interface Concatenation extends Properties<typeof ConcatenationSpec> {}
/** `{items}` (11.4.12). */
export class Concatenation extends Expression {
  static override SPEC = ConcatenationSpec;
}

const ReplicationSpec = {
  count: one(() => [Expression]),
  items: many(() => [Expression]),
};
export interface Replication extends Properties<typeof ReplicationSpec> {}
/** `{count{items}}` (11.4.12.1). */
export class Replication extends Expression {
  static override SPEC = ReplicationSpec;
}

const AssignmentPatternSpec = {
  type: optional(() => [DataType]),
  items: many(() => [Expression, PatternItem]),
};
export interface AssignmentPattern extends Properties<typeof AssignmentPatternSpec> {}
/** `type'{items}` or `'{items}`: positional values, or `key: value` items (10.9). */
export class AssignmentPattern extends Expression {
  static override SPEC = AssignmentPatternSpec;
  static override SINCE: Availability | null = sv();
}

const PatternItemSpec = {
  key: optional(() => [Expression, DataType]),
  value: one(() => [Expression]),
};
export interface PatternItem extends Properties<typeof PatternItemSpec> {}
/** `key: value` in an assignment pattern, or `default: value` without a key (10.9.1). */
export class PatternItem extends SyntaxNode {
  static override SPEC = PatternItemSpec;
}

const NullLiteralSpec = {};
export interface NullLiteral extends Properties<typeof NullLiteralSpec> {}
/** `null`, the handle of no object (8.4). */
export class NullLiteral extends Literal {
  static override SPEC = NullLiteralSpec;
  static override SINCE: Availability | null = sv();
}

const ThisExpressionSpec = {};
export interface ThisExpression extends Properties<typeof ThisExpressionSpec> {}
/** `this`, the object a method runs on (8.11). */
export class ThisExpression extends Expression {
  static override SPEC = ThisExpressionSpec;
  static override SINCE: Availability | null = sv();
}

const SuperExpressionSpec = {};
export interface SuperExpression extends Properties<typeof SuperExpressionSpec> {}
/** `super`, the object a method runs on as its base class (8.15). */
export class SuperExpression extends Expression {
  static override SPEC = SuperExpressionSpec;
  static override SINCE: Availability | null = sv();
}

const NewExpressionSpec = {
  scope: optional(() => [Name, SuperExpression]),
  arguments: many(() => [Expression, Connection]),
};
export interface NewExpression extends Properties<typeof NewExpressionSpec> {}
/**
 * `new(arguments)`: a new object of the class the place it is assigned to has, or with `scope` of that class
 * (`c#(8)::new`) or the base class's constructor (`super.new`) (8.7, 8.15). `new` without arguments is written
 * without parentheses.
 */
export class NewExpression extends Expression {
  static override SPEC = NewExpressionSpec;
  static override SINCE: Availability | null = sv();
}

const NewCopyExpressionSpec = {
  value: one(() => [Expression]),
};
export interface NewCopyExpression extends Properties<typeof NewCopyExpressionSpec> {}
/** `new value`: a shallow copy of an object (8.12). */
export class NewCopyExpression extends Expression {
  static override SPEC = NewCopyExpressionSpec;
  static override SINCE: Availability | null = sv();
}

const NewArrayExpressionSpec = {
  size: one(() => [Expression]),
  value: optional(() => [Expression]),
};
export interface NewArrayExpression extends Properties<typeof NewArrayExpressionSpec> {}
/** `new[size](value)`: a dynamic array of `size` elements, copying `value`'s first ones (7.5.1). */
export class NewArrayExpression extends Expression {
  static override SPEC = NewArrayExpressionSpec;
  static override SINCE: Availability | null = sv();
}

const CallExpressionSpec = {
  callee: one(() => [Expression]),
  arguments: many(() => [Expression, Connection]),
};
export interface CallExpression extends Properties<typeof CallExpressionSpec> {}
/**
 * `callee(arguments)`: a function or method call (13.5); arguments are ordered expressions or named
 * `NamedConnection`s.
 */
export class CallExpression extends Expression {
  static override SPEC = CallExpressionSpec;
}

const SystemCallSpec = {
  name: text(),
  arguments: many(() => [Expression, DataType]),
};
export interface SystemCall extends Properties<typeof SystemCallSpec> {}
/**
 * `$name(arguments)`: a system task or function call, such as `$display` or `$clog2` (20). An argument may be a
 * data type, as `$bits` takes.
 */
export class SystemCall extends Expression {
  static override SPEC = SystemCallSpec;
  override check(): string[] {
    const name = this.name;
    if (typeof name !== "string" || name === "") return [];
    if (name[0] !== "$" || !/^\$[A-Za-z0-9_$]+$/.test(name)) {
      return [`${repr(name)} is not a system task or function name`];
    }
    return [];
  }
}

const CastExpressionSpec = {
  type: one(() => [DataType, Expression]),
  value: one(() => [Expression]),
};
export interface CastExpression extends Properties<typeof CastExpressionSpec> {}
/** `type'(value)`: a cast to a type, a width (`8'(x)`) or a signing (`signed'(x)`, an `ImplicitType`) (6.24.1). */
export class CastExpression extends Expression {
  static override SPEC = CastExpressionSpec;
  static override SINCE: Availability | null = sv();
}

const ParenthesizedExpressionSpec = {
  expression: one(() => [Expression]),
};
export interface ParenthesizedExpression extends Properties<typeof ParenthesizedExpressionSpec> {}
/** `(expression)` (A.8.4). */
export class ParenthesizedExpression extends Expression {
  static override SPEC = ParenthesizedExpressionSpec;
}

const MacroUsageSpec = {
  name: one(() => [Identifier]),
  arguments: optionalText(),
};
export interface MacroUsage extends Properties<typeof MacroUsageSpec> {}
/**
 * `` `name `` or `` `name(arguments) ``, a text macro used as a value (22.5.1). `arguments` keeps the text between
 * the parentheses.
 */
export class MacroUsage extends Expression {
  static override SPEC = MacroUsageSpec;
}

const DollarExpressionSpec = {};
export interface DollarExpression extends Properties<typeof DollarExpressionSpec> {}
/** `$`, the last element of a queue or an unbounded range (7.10.1). */
export class DollarExpression extends Expression {
  static override SPEC = DollarExpressionSpec;
  static override SINCE: Availability | null = sv();
}

// === Compiler directives (22) ===

const IncludeDirectiveSpec = {
  path: text(),
  system: flag(),
};
export interface IncludeDirective extends Properties<typeof IncludeDirectiveSpec> {}
/** `` `include "path" ``, or `` `include <path> `` when `system` (22.4). */
export class IncludeDirective extends Directive {
  static override SPEC = IncludeDirectiveSpec;
  static override FEATURES: Features = { system: [[true, sv(2009)]] };
}

const DefineDirectiveSpec = {
  name: one(() => [Identifier]),
  function_like: flag(),
  parameters: many(() => [Identifier]),
  body: text(),
};
export interface DefineDirective extends Properties<typeof DefineDirectiveSpec> {}
/**
 * `` `define name body ``, or with `function_like` `` `define name(parameters) body `` (22.5.1). `body` keeps its
 * text, line continuations included.
 */
export class DefineDirective extends Directive {
  static override SPEC = DefineDirectiveSpec;
}

const UndefDirectiveSpec = {
  name: one(() => [Identifier]),
};
export interface UndefDirective extends Properties<typeof UndefDirectiveSpec> {}
/** `` `undef name `` (22.5.2). */
export class UndefDirective extends Directive {
  static override SPEC = UndefDirectiveSpec;
}

const TimescaleDirectiveSpec = {
  unit: text(),
  precision: text(),
};
export interface TimescaleDirective extends Properties<typeof TimescaleDirectiveSpec> {}
/** `` `timescale unit / precision ``, each a magnitude and a unit, such as `1ns` (22.7). */
export class TimescaleDirective extends Directive {
  static override SPEC = TimescaleDirectiveSpec;
}

const DefaultNettypeDirectiveSpec = {
  net_type: choice(...DEFAULT_NETTYPES),
};
export interface DefaultNettypeDirective extends Properties<typeof DefaultNettypeDirectiveSpec> {}
/** `` `default_nettype net_type ``, or `none` (22.8). */
export class DefaultNettypeDirective extends Directive {
  static override SPEC = DefaultNettypeDirectiveSpec;
  static override FEATURES: Features = { net_type: [["none", verilog(2001)], ["uwire", verilog(2005)]] };
}

const IfdefDirectiveSpec = {
  negated: flag(),
  name: one(() => [Identifier]),
  items: many(() => [Item, Statement, Directive, Comment]),
  branches: many(() => [ElsifDirective]),
  alternative: many(() => [Item, Statement, Directive, Comment]),
  has_else: flag(),
};
export interface IfdefDirective extends Properties<typeof IfdefDirectiveSpec> {}
/**
 * `` `ifdef name items `elsif name items `else items `endif ``, or `` `ifndef `` when `negated`, as a tree of its
 * branches (22.6). Branches hold what their place lists: items, or statements. A branch the reading did not take
 * ends with its text as written, a `DisabledText`.
 */
export class IfdefDirective extends Directive {
  static override SPEC = IfdefDirectiveSpec;
}

const ElsifDirectiveSpec = {
  name: one(() => [Identifier]),
  items: many(() => [Item, Statement, Directive, Comment]),
};
export interface ElsifDirective extends Properties<typeof ElsifDirectiveSpec> {}
/** `` `elsif name items ``, a branch of an `IfdefDirective` (22.6). */
export class ElsifDirective extends Directive {
  static override SPEC = ElsifDirectiveSpec;
  static override SINCE: Availability | null = verilog(2001);
}

const DisabledTextSpec = {
  text: text(),
};
export interface DisabledText extends Properties<typeof DisabledTextSpec> {}
/**
 * The text of a conditional branch the preprocessor skipped, as written: it is not parsed, since which branch is
 * taken depends on the macros defined (22.6).
 */
export class DisabledText extends Directive {
  static override SPEC = DisabledTextSpec;
}

const OtherDirectiveSpec = {
  text: text(),
};
export interface OtherDirective extends Properties<typeof OtherDirectiveSpec> {}
/** Any other directive, as written: `` `resetall ``, `` `celldefine ``, `` `line ``, ... (22). */
export class OtherDirective extends Directive {
  static override SPEC = OtherDirectiveSpec;
}

/** A `pure` method is `virtual`, and a prototype (`extern` or `pure`) has no body. */
function methodProblems(method: FunctionDeclaration | TaskDeclaration): string[] {
  const kind = method.kind().KIND;
  if (method.pure === true && method.virtual !== true) return [`a pure ${kind} is virtual`];
  if ((method.extern === true || method.pure === true) && (method.body.length > 0 || method.labeled === true)) {
    return [`an extern or pure ${kind} has no body`];
  }
  return [];
}

// --- The language ---

export const KINDS = [
  Comment, Identifier, ScopedName, ParameterizedName, SourceText, ModuleDeclaration, InterfaceDeclaration,
  ProgramDeclaration, PackageDeclaration, AnsiPort, InterfacePort, PortReference, PortDeclaration,
  ParameterDeclaration, ParamAssignment, TypeParameterDeclaration, TypeAssignment, IntegerVectorType, IntegerAtomType,
  NonIntegerType, KeywordType, NamedType, VirtualInterfaceType, ImplicitType, StructType, StructMember, EnumType,
  EnumMember, RangeDimension, SizeDimension, UnsizedDimension, AssociativeDimension, QueueDimension, NetDeclaration,
  VariableDeclaration, VariableDeclarator, ForwardTypedefDeclaration, TypedefDeclaration, GenvarDeclaration,
  ImportDeclaration, ImportItem, ModportDeclaration, ModportItem, ModportPort, ContinuousAssign, AlwaysConstruct,
  InitialConstruct, FinalConstruct, FunctionDeclaration, TaskDeclaration, TfPort, ClassDeclaration, GenerateRegion,
  GenerateFor, GenerateIf, GenerateCase, GenerateBlock, ModuleInstantiation, Instance, NamedConnection,
  WildcardConnection, AssignmentStatement, ExpressionStatement, NullStatement, SeqBlock, ParBlock, IfStatement,
  CaseStatement, CaseItem, ForStatement, WhileStatement, DoWhileStatement, RepeatStatement, ForeverStatement,
  ForeachStatement, BreakStatement, ContinueStatement, ReturnStatement, TimedStatement, WaitStatement, EventTrigger,
  DisableStatement, ImmediateAssertion, DelayControl, EventControl, EventExpression, NameExpression, MemberExpression,
  IndexExpression, RangeSelect, IntegerLiteral, RealLiteral, TimeLiteral, UnbasedUnsizedLiteral, StringLiteral,
  UnaryExpression, IncrementExpression, BinaryExpression, AssignmentExpression, ConditionalExpression,
  InsideExpression, ValueRange, Concatenation, Replication, AssignmentPattern, PatternItem, CallExpression,
  SystemCall, CastExpression, ParenthesizedExpression, MacroUsage, DollarExpression, NullLiteral, ThisExpression,
  SuperExpression, NewExpression, NewCopyExpression, NewArrayExpression, IncludeDirective, DefineDirective,
  UndefDirective, TimescaleDirective, DefaultNettypeDirective, IfdefDirective, ElsifDirective, DisabledText,
  OtherDirective,
];

/** The language, whose `Builders` are typed from this module's kinds. */
export const LANGUAGE: Language<typeof Self> = new Language("Verilog", KINDS, {
  base: { [VERILOG]: 1995, [SV]: 2005 },
});
