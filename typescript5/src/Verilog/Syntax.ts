/**
 * Syntax: the abstract syntax of Verilog and SystemVerilog, as one tree language (Verilog), organized as IEEE 1800's
 * grammar is.
 *
 * The kinds cover SystemVerilog (IEEE 1800-2023)'s design subset and its classes: design units, ports and parameters,
 * data types, declarations, continuous assignments, procedural blocks and statements, generate constructs,
 * instantiation, functions and tasks, classes with their properties, methods and objects, constraints and
 * randomization, immediate and concurrent assertions with their properties and sequences, clocking blocks, covergroups
 * and compiler directives. Verilog (IEEE 1364) is a family of its own whose standards have fewer of them: each kind and
 * feature records where it exists in both families (`SINCE`, `FEATURES`), which `Verilog2005`, `SystemVerilog2017`,
 * `SystemVerilog2023` and `VerilogStandard(year, family)` check.
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
  type AttributeSpec as PropertyAttribute, type Availability, type ChildSpec, choice, type Features, flag, Language, many,
  one, optional, optionalChoice, optionalInteger, optionalText, type Properties, SyntaxNode, text,
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
export const SIMPLE_KEYWORDS = ["string", "chandle", "event", "void", "sequence", "property", "untyped"] as const;
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
export const DIST_OPERATORS = [":=", ":/"] as const;
export type DistOperator = (typeof DIST_OPERATORS)[number];
export const CONCURRENT_KEYWORDS = ["assert", "assume", "cover", "restrict"] as const;
export type ConcurrentKeyword = (typeof CONCURRENT_KEYWORDS)[number];
export const REPETITION_OPERATORS = ["*", "->", "="] as const;
export type RepetitionOperator = (typeof REPETITION_OPERATORS)[number];
export const SEQUENCE_OPERATORS = ["and", "or", "intersect", "within", "throughout"] as const;
export type SequenceOperator = (typeof SEQUENCE_OPERATORS)[number];
export const IMPLICATION_OPERATORS = ["|->", "|=>", "#-#", "#=#"] as const;
export type ImplicationOperator = (typeof IMPLICATION_OPERATORS)[number];
export const PROPERTY_OPERATORS = [
  "and", "or", "iff", "implies", "until", "s_until", "until_with", "s_until_with"
] as const;
export type PropertyOperator = (typeof PROPERTY_OPERATORS)[number];
export const UNARY_PROPERTY_OPERATORS = [
  "not", "nexttime", "s_nexttime", "always", "s_always", "eventually", "s_eventually"
] as const;
export type UnaryPropertyOperator = (typeof UNARY_PROPERTY_OPERATORS)[number];
export const STRENGTH_KEYWORDS = ["strong", "weak"] as const;
export type StrengthKeyword = (typeof STRENGTH_KEYWORDS)[number];
export const ABORT_KEYWORDS = ["accept_on", "reject_on", "sync_accept_on", "sync_reject_on"] as const;
export type AbortKeyword = (typeof ABORT_KEYWORDS)[number];
export const PORT_DIRECTIONS = ["input", "output", "inout"] as const;
export type PortDirection = (typeof PORT_DIRECTIONS)[number];
export const CLOCKING_DIRECTIONS = ["input", "output", "inout", "input output"] as const;
export type ClockingDirection = (typeof CLOCKING_DIRECTIONS)[number];
export const CLOCKING_SCOPES = ["default", "global"] as const;
export type ClockingScope = (typeof CLOCKING_SCOPES)[number];
export const STREAM_OPERATORS = [">>", "<<"] as const;
export type StreamOperator = (typeof STREAM_OPERATORS)[number];
export const TOLERANCE_OPERATORS = ["+/-", "+%-"] as const;
export type ToleranceOperator = (typeof TOLERANCE_OPERATORS)[number];
export const BINS_KEYWORDS = ["bins", "illegal_bins", "ignore_bins"] as const;
export type BinsKeyword = (typeof BINS_KEYWORDS)[number];
export const BINS_SELECT_OPERATORS = ["&&", "||"] as const;
export type BinsSelectOperator = (typeof BINS_SELECT_OPERATORS)[number];
export const PROTOTYPE_QUALIFIERS = ["extern", "pure"] as const;
export type PrototypeQualifier = (typeof PROTOTYPE_QUALIFIERS)[number];
export const FORWARD_KEYWORDS = ["enum", "struct", "union", "class", "interface class"] as const;
export type ForwardKeyword = (typeof FORWARD_KEYWORDS)[number];
export const STRENGTHS = [
  "supply0", "strong0", "pull0", "weak0", "highz0", "supply1", "strong1", "pull1", "weak1", "highz1"
] as const;
export type Strength = (typeof STRENGTHS)[number];
export const CHARGE_SIZES = ["small", "medium", "large"] as const;
export type ChargeSize = (typeof CHARGE_SIZES)[number];
export const NET_EXPANSIONS = ["vectored", "scalared"] as const;
export type NetExpansion = (typeof NET_EXPANSIONS)[number];
export const TIME_UNIT_KEYWORDS = ["timeunit", "timeprecision"] as const;
export type TimeUnitKeyword = (typeof TIME_UNIT_KEYWORDS)[number];
export const IMPORT_EXPORTS = ["import", "export"] as const;
export type ImportExport = (typeof IMPORT_EXPORTS)[number];
export const OVERRIDE_SPECIFIERS = ["initial", "extends"] as const;
export type OverrideSpecifier = (typeof OVERRIDE_SPECIFIERS)[number];
export const FORCE_KEYWORDS = ["force", "assign"] as const;
export type ForceKeyword = (typeof FORCE_KEYWORDS)[number];
export const RELEASE_KEYWORDS = ["release", "deassign"] as const;
export type ReleaseKeyword = (typeof RELEASE_KEYWORDS)[number];
export const ELABORATION_TASK_NAMES = ["$fatal", "$error", "$warning", "$info"] as const;
export type ElaborationTaskName = (typeof ELABORATION_TASK_NAMES)[number];
export const DPI_SPECS = ["DPI-C", "DPI"] as const;
export type DpiSpec = (typeof DPI_SPECS)[number];
export const DPI_PROPERTYS = ["context", "pure"] as const;
export type DpiProperty = (typeof DPI_PROPERTYS)[number];
export const SUBROUTINE_KEYWORDS = ["function", "task"] as const;
export type SubroutineKeyword = (typeof SUBROUTINE_KEYWORDS)[number];
export const UNION_QUALIFIERS = ["tagged", "soft"] as const;
export type UnionQualifier = (typeof UNION_QUALIFIERS)[number];
export const GATE_KEYWORDS = [
  "and", "nand", "or", "nor", "xor", "xnor", "buf", "not", "bufif0", "bufif1", "notif0", "notif1", "nmos", "pmos",
  "rnmos", "rpmos", "cmos", "rcmos", "tran", "rtran", "tranif0", "tranif1", "rtranif0", "rtranif1", "pullup",
  "pulldown"
] as const;
export type GateKeyword = (typeof GATE_KEYWORDS)[number];
export const UDP_DIRECTIONS = ["output", "input"] as const;
export type UdpDirection = (typeof UDP_DIRECTIONS)[number];
export const PATH_OPERATORS = ["=>", "*>"] as const;
export type PathOperator = (typeof PATH_OPERATORS)[number];
export const POLARITYS = ["+", "-"] as const;
export type Polarity = (typeof POLARITYS)[number];
export const DATA_POLARITYS = ["+:", "-:", ":"] as const;
export type DataPolarity = (typeof DATA_POLARITYS)[number];
export const TIMING_CHECK_NAMES = [
  "$setup", "$hold", "$setuphold", "$recovery", "$removal", "$recrem", "$skew", "$timeskew", "$fullskew", "$period",
  "$width", "$nochange"
] as const;
export type TimingCheckName = (typeof TIMING_CHECK_NAMES)[number];
export const BLOCK_EVENT_KEYWORDS = ["begin", "end"] as const;
export type BlockEventKeyword = (typeof BLOCK_EVENT_KEYWORDS)[number];
export const CONFIG_RULE_KEYWORDS = ["default", "instance", "cell"] as const;
export type ConfigRuleKeyword = (typeof CONFIG_RULE_KEYWORDS)[number];
export const PULSE_STYLES = ["pulsestyle_onevent", "pulsestyle_ondetect", "showcancelled", "noshowcancelled"] as const;
export type PulseStyle = (typeof PULSE_STYLES)[number];
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

/** A constraint on random variables, in a constraint block (18.5, A.1.10). */
export abstract class Constraint extends SyntaxNode {}

/**
 * A property: what a concurrent assertion checks (16.12, A.2.10). A sequence, and an expression, is a property
 * too: a position that holds a property holds a `Property` or an `Expression`.
 */
export abstract class Property extends SyntaxNode {}

/**
 * A sequence: a pattern of values over clock ticks (16.7, A.2.10). An expression is a sequence of one tick too: a
 * position that holds a sequence holds a `Sequence` or an `Expression`.
 */
export abstract class Sequence extends Property {}

/**
 * A select expression: which combinations of a cross's bins a bin of the cross holds (19.6.1). A cross's name, or
 * an expression, is one too: a position that holds a select holds a `BinsSelect` or an `Expression`.
 */
export abstract class BinsSelect extends SyntaxNode {}

/** What a `randsequence` production's rule lists: productions to generate, code, and their choices (18.17). */
export abstract class ProductionItem extends SyntaxNode {}

/**
 * A pattern that `matches` compares a value with, binding its variables (12.6). An expression is a pattern too, a
 * constant one: a position that holds a pattern holds a `Pattern` or an `Expression`.
 */
export abstract class Pattern extends SyntaxNode {}

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
  scope: one(() => [Identifier, ParameterizedName, UnitName]),
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

const LocalNameSpec = {
  name: one(() => [Identifier]),
};
export interface LocalName extends Properties<typeof LocalNameSpec> {}
/**
 * `local::name`: in the constraints of `randomize() with`, a name in the scope that calls `randomize`, not in the
 * object (18.7.1).
 */
export class LocalName extends Name {
  static override SPEC = LocalNameSpec;
  static override SINCE: Availability | null = sv(2009);
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

// --- Attributes (5.12) ---

const AttributeInstanceSpec = {
  specs: many(() => [AttributeSpec]),
};
export interface AttributeInstance extends Properties<typeof AttributeInstanceSpec> {}
/** `(* specs *)`: attributes for tools, such as `(* keep *)` or `(* full_case, parallel_case *)` (5.12). */
export class AttributeInstance extends SyntaxNode {
  static override SPEC = AttributeInstanceSpec;
  static override SINCE: Availability | null = verilog(2001);
}

const AttributeSpecSpec = {
  name: one(() => [Identifier]),
  value: optional(() => [Expression]),
};
export interface AttributeSpec extends Properties<typeof AttributeSpecSpec> {}
/** `name = value`, or `name` alone, in an attribute instance (5.12). */
export class AttributeSpec extends SyntaxNode {
  static override SPEC = AttributeSpecSpec;
  static override SINCE: Availability | null = verilog(2001);
}

const AttributedItemSpec = {
  attributes: many(() => [AttributeInstance]),
  item: one(() => [Item]),
};
export interface AttributedItem extends Properties<typeof AttributedItemSpec> {}
/** `(* ... *) item`: an item with its attributes (5.12). */
export class AttributedItem extends Item {
  static override SPEC = AttributedItemSpec;
  static override SINCE: Availability | null = verilog(2001);
}

const AttributedStatementSpec = {
  attributes: many(() => [AttributeInstance]),
  statement: one(() => [Statement]),
};
export interface AttributedStatement extends Properties<typeof AttributedStatementSpec> {}
/** `(* ... *) statement`: a statement with its attributes (5.12). */
export class AttributedStatement extends Statement {
  static override SPEC = AttributedStatementSpec;
  static override SINCE: Availability | null = verilog(2001);
}

const AttributedPortSpec = {
  attributes: many(() => [AttributeInstance]),
  port: one(() => [Port]),
};
export interface AttributedPort extends Properties<typeof AttributedPortSpec> {}
/** `(* ... *) port`: a port in a design unit's header with its attributes (5.12). */
export class AttributedPort extends Port {
  static override SPEC = AttributedPortSpec;
  static override SINCE: Availability | null = verilog(2001);
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
  extern: flag(),
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
 * items declare. `labeled` repeats the name after `endmodule`. An `extern` one is a header alone, which the module
 * of its name, with `.*` for its ports, defines (23.2.1).
 */
export class ModuleDeclaration extends Item {
  static override SPEC = ModuleDeclarationSpec;
  static override FEATURES: Features = {
    lifetime: [[true, verilog(2001)]],
    imports: [[true, sv(2009)]],
    labeled: [[true, sv()]],
    extern: [[true, sv()]],
  };
  override check(): string[] {
    return unitProblems(this);
  }
}

const InterfaceDeclarationSpec = {
  extern: flag(),
  lifetime: optionalChoice(...LIFETIMES),
  name: one(() => [Identifier]),
  imports: many(() => [ImportDeclaration]),
  parameters: many(() => [ParameterDeclaration, TypeParameterDeclaration]),
  ports: many(() => [Port]),
  items: many(() => [Item, Directive, Comment]),
  labeled: flag(),
};
export interface InterfaceDeclaration extends Properties<typeof InterfaceDeclarationSpec> {}
/** `interface name #(parameters) (ports); items endinterface` (25.3), or an `extern` header alone. */
export class InterfaceDeclaration extends Item {
  static override SPEC = InterfaceDeclarationSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { imports: [[true, sv(2009)]] };
  override check(): string[] {
    return unitProblems(this);
  }
}

const ProgramDeclarationSpec = {
  extern: flag(),
  lifetime: optionalChoice(...LIFETIMES),
  name: one(() => [Identifier]),
  imports: many(() => [ImportDeclaration]),
  parameters: many(() => [ParameterDeclaration, TypeParameterDeclaration]),
  ports: many(() => [Port]),
  items: many(() => [Item, Directive, Comment]),
  labeled: flag(),
};
export interface ProgramDeclaration extends Properties<typeof ProgramDeclarationSpec> {}
/** `program name #(parameters) (ports); items endprogram` (24.3), or an `extern` header alone. */
export class ProgramDeclaration extends Item {
  static override SPEC = ProgramDeclarationSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { imports: [[true, sv(2009)]] };
  override check(): string[] {
    return unitProblems(this);
  }
}

const CheckerDeclarationSpec = {
  name: one(() => [Identifier]),
  ports: many(() => [AssertionPort]),
  items: many(() => [Item, Directive, Comment]),
  labeled: flag(),
};
export interface CheckerDeclaration extends Properties<typeof CheckerDeclarationSpec> {}
/**
 * `checker name(ports); items endchecker`: assertions with their modeling code, instantiated as a module is, or in
 * a procedure (17). Its ports are as a property's; its variables may be `rand`, free for formal tools to choose
 * (17.7). `labeled` repeats the name after `endchecker`.
 */
export class CheckerDeclaration extends Item {
  static override SPEC = CheckerDeclarationSpec;
  static override SINCE: Availability | null = sv(2009);
}

const ConfigDeclarationSpec = {
  name: one(() => [Identifier]),
  localparams: many(() => [ParameterDeclaration]),
  design: many(() => [ConfigCell]),
  rules: many(() => [ConfigRule, Directive, Comment]),
  labeled: flag(),
};
export interface ConfigDeclaration extends Properties<typeof ConfigDeclarationSpec> {}
/**
 * `config name; localparams design cells; rules endconfig`: which libraries' cells a design's instances use (33.4).
 * `labeled` repeats the name after `endconfig`.
 */
export class ConfigDeclaration extends Item {
  static override SPEC = ConfigDeclarationSpec;
  static override SINCE: Availability | null = verilog(2001);
  static override FEATURES: Features = { localparams: [[true, sv(2009)]] };
}

const ConfigCellSpec = {
  library: optional(() => [Identifier]),
  cell: one(() => [Identifier]),
};
export interface ConfigCell extends Properties<typeof ConfigCellSpec> {}
/** `library.cell`, or `cell` of the libraries a rule searches (33.4.1). */
export class ConfigCell extends SyntaxNode {
  static override SPEC = ConfigCellSpec;
}

const ConfigRuleSpec = {
  keyword: choice(...CONFIG_RULE_KEYWORDS),
  path: many(() => [Identifier]),
  cell: optional(() => [ConfigCell]),
  clause: one(() => [ConfigLiblist, ConfigUse]),
};
export interface ConfigRule extends Properties<typeof ConfigRuleSpec> {}
/**
 * `default liblist libraries;`, `instance path clause;` or `cell name clause;`: where an instance, or a cell, comes
 * from (33.4.1).
 */
export class ConfigRule extends SyntaxNode {
  static override SPEC = ConfigRuleSpec;
  static override SINCE: Availability | null = verilog(2001);
  override check(): string[] {
    if ((this.keyword === "instance") !== (this.path.length > 0) || (this.keyword === "cell") !== (this.cell !== null)) {
      return ["a ConfigRule has a path for an instance, a cell for a cell, and neither for the default"];
    }
    if (this.keyword === "default" && this.clause instanceof ConfigUse) return ["a default ConfigRule has a liblist"];
    return [];
  }
}

const ConfigLiblistSpec = {
  libraries: many(() => [Identifier]),
};
export interface ConfigLiblist extends Properties<typeof ConfigLiblistSpec> {}
/** `liblist libraries`: the libraries a rule searches, in order (33.4.1.5). */
export class ConfigLiblist extends SyntaxNode {
  static override SPEC = ConfigLiblistSpec;
  static override SINCE: Availability | null = verilog(2001);
}

const ConfigUseSpec = {
  cell: optional(() => [ConfigCell]),
  parameters: many(() => [Expression, DataType, Connection]),
  config: flag(),
};
export interface ConfigUse extends Properties<typeof ConfigUseSpec> {}
/**
 * `use library.cell #(parameters) :config`: the cell an instance or a cell uses, with parameters, or a
 * configuration when `config` (33.4.1.6).
 */
export class ConfigUse extends SyntaxNode {
  static override SPEC = ConfigUseSpec;
  static override SINCE: Availability | null = verilog(2001);
  static override FEATURES: Features = { parameters: [[true, sv(2009)]] };
  override check(): string[] {
    if (this.cell === null && this.parameters.length === 0) return ["a ConfigUse has a cell or parameters"];
    if (this.config === true && this.cell === null) return ["a ConfigUse of a configuration has its cell"];
    return [];
  }
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
  left: optional(() => [Expression]),
  operator: optionalChoice(...SELECT_OPERATORS),
  right: optional(() => [Expression]),
};
export interface PortReference extends Properties<typeof PortReferenceSpec> {}
/**
 * A non-ANSI header's port, named in the header and declared by a `PortDeclaration` item (23.2.2.1), or a part of
 * it: `name[left]`, or `name[left operator right]`.
 */
export class PortReference extends Port {
  static override SPEC = PortReferenceSpec;
  override check(): string[] {
    if ((this.operator === null) !== (this.right === null) || (this.left === null && this.operator !== null)) {
      return ["a PortReference's select has a left, and an operator and a right, or neither"];
    }
    return [];
  }
}

const PortConcatenationSpec = {
  references: many(() => [PortReference]),
};
export interface PortConcatenation extends Properties<typeof PortConcatenationSpec> {}
/** `{references}`, a non-ANSI header's port made of several (23.2.2.1). */
export class PortConcatenation extends Port {
  static override SPEC = PortConcatenationSpec;
}

const ExplicitPortSpec = {
  name: one(() => [Identifier]),
  value: optional(() => [PortReference, PortConcatenation]),
};
export interface ExplicitPort extends Properties<typeof ExplicitPortSpec> {}
/**
 * `.name(value)`, a non-ANSI header's port named apart from what it connects, or connecting nothing
 * (23.2.2.1).
 */
export class ExplicitPort extends Port {
  static override SPEC = ExplicitPortSpec;
}

const WildcardPortSpec = {};
export interface WildcardPort extends Properties<typeof WildcardPortSpec> {}
/** `.*`, a header's ports as the `extern` declaration of its name gives them (23.2.1). */
export class WildcardPort extends Port {
  static override SPEC = WildcardPortSpec;
  static override SINCE: Availability | null = sv();
}

const EmptyPortSpec = {};
export interface EmptyPort extends Properties<typeof EmptyPortSpec> {}
/** A non-ANSI header's port left out: `module m (a, , b)` (23.2.2.1). */
export class EmptyPort extends Port {
  static override SPEC = EmptyPortSpec;
}

const ExplicitAnsiPortSpec = {
  direction: optionalChoice(...DIRECTIONS),
  name: one(() => [Identifier]),
  value: optional(() => [Expression]),
};
export interface ExplicitAnsiPort extends Properties<typeof ExplicitAnsiPortSpec> {}
/**
 * `direction .name(value)`, an ANSI header's port named apart from the expression it is (23.2.2.2). Without a
 * direction, it follows another ANSI port and inherits its direction.
 */
export class ExplicitAnsiPort extends Port {
  static override SPEC = ExplicitAnsiPortSpec;
  static override SINCE: Availability | null = sv();
}

const InterfacePortDeclarationSpec = {
  interface: one(() => [Identifier]),
  modport: one(() => [Identifier]),
  declarators: many(() => [VariableDeclarator]),
};
export interface InterfacePortDeclaration extends Properties<typeof InterfacePortDeclarationSpec> {}
/**
 * `interface_name.modport names;`: a non-ANSI header's ports of an interface type (25.3.3); without a modport, the
 * declaration is a variable's.
 */
export class InterfacePortDeclaration extends Item {
  static override SPEC = InterfacePortDeclarationSpec;
  static override SINCE: Availability | null = sv();
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
  restriction: optionalChoice(...FORWARD_KEYWORDS),
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
  static override FEATURES: Features = { restriction: [[true, sv(2023)]] };
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
/**
 * `string`, `chandle`, `event` or `void` (6.16, 6.14, 6.17, 6.13), or the type of an assertion's port:
 * `sequence`, `property` or `untyped` (16.8).
 */
export class KeywordType extends DataType {
  static override SPEC = KeywordTypeSpec;
  static override FEATURES: Features = {
    keyword: [
      ["string", sv()], ["chandle", sv()], ["void", sv()], ["sequence", sv(2009)], ["property", sv(2009)],
      ["untyped", sv(2009)]
    ],
  };
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
  qualifier: optionalChoice(...UNION_QUALIFIERS),
  packed: flag(),
  signing: optionalChoice(...SIGNINGS),
  members: many(() => [StructMember]),
  dimensions: many(() => [Dimension]),
};
export interface StructType extends Properties<typeof StructTypeSpec> {}
/**
 * `struct packed signed { members }` or `union ...`, with packed dimensions (7.2, 7.3). A union may be `tagged`,
 * its members told apart by a tag, or `soft`, its members of different widths (7.3.2, 7.3.1).
 */
export class StructType extends DataType {
  static override SPEC = StructTypeSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { qualifier: [["soft", sv(2023)]] };
  override check(): string[] {
    return this.qualifier !== null && this.keyword !== "union" ? ["a StructType with a qualifier is a union"] : [];
  }
}

const StructMemberSpec = {
  attributes: many(() => [AttributeInstance]),
  random: optionalChoice(...RANDOM_QUALIFIERS),
  type: one(() => [DataType]),
  declarators: many(() => [VariableDeclarator]),
};
export interface StructMember extends Properties<typeof StructMemberSpec> {}
/**
 * `random type declarators;` in a structure or union (7.2), `rand` or `randc` in one that is randomized
 * (18.4).
 */
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
  left: optional(() => [Expression]),
  right: optional(() => [Expression]),
  value: optional(() => [Expression]),
};
export interface EnumMember extends Properties<typeof EnumMemberSpec> {}
/**
 * `name = value` in an enumeration (6.19), or `name[left:right] = value`, members named from `name` with numbers
 * `left` to `right`, or with one number `left`, 0 to `left - 1`.
 */
export class EnumMember extends SyntaxNode {
  static override SPEC = EnumMemberSpec;
  override check(): string[] {
    return this.right !== null && this.left === null ? ["an EnumMember with a right has a left"] : [];
  }
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
  net_type: optionalChoice(...NET_TYPES),
  strength: optional(() => [DriveStrength, ChargeStrength]),
  expansion: optionalChoice(...NET_EXPANSIONS),
  type: optional(() => [DataType]),
  delay: optional(() => [DelayControl]),
  declarators: many(() => [VariableDeclarator]),
};
export interface NetDeclaration extends Properties<typeof NetDeclarationSpec> {}
/**
 * `net_type strength expansion type #delay declarators;` (6.7): a drive strength, or a `trireg`'s charge
 * strength, and `vectored` or `scalared`. Without a `net_type`, its `type` is a user-defined net type, a
 * `NamedType` (`nt #1 w;`) (6.6.7).
 */
export class NetDeclaration extends Item {
  static override SPEC = NetDeclarationSpec;
  static override FEATURES: Features = { net_type: [["uwire", verilog(2005)], ["interconnect", sv(2012)]] };
  override check(): string[] {
    if (this.strength instanceof ChargeStrength && this.net_type !== "trireg") {
      return ["a NetDeclaration with a charge strength is a trireg"];
    }
    if (this.net_type === null && (!(this.type instanceof NamedType) || this.strength !== null || this.expansion !== null)) {
      return ["a NetDeclaration without a net type has a user-defined one, a NamedType, alone"];
    }
    return [];
  }
}

const DriveStrengthSpec = {
  first: choice(...STRENGTHS),
  second: choice(...STRENGTHS),
};
export interface DriveStrength extends Properties<typeof DriveStrengthSpec> {}
/**
 * `(strength0, strength1)`, in either order: a net's or a continuous assignment's strengths of 0 and 1, of
 * `supply`, `strong`, `pull`, `weak` and `highz`, not both `highz` (6.3.2, 10.3.4).
 */
export class DriveStrength extends SyntaxNode {
  static override SPEC = DriveStrengthSpec;
  override check(): string[] {
    const [first, second] = [this.first, this.second];
    if (typeof first !== "string" || typeof second !== "string") return [];
    const ends = new Set([first.slice(-1), second.slice(-1)]);
    if (ends.size !== 2 || !ends.has("0") || !ends.has("1")) return ["a DriveStrength has a strength of 0 and one of 1"];
    if (first.startsWith("highz") && second.startsWith("highz")) return ["a DriveStrength is not highz for both"];
    return [];
  }
}

const ChargeStrengthSpec = {
  size: choice(...CHARGE_SIZES),
};
export interface ChargeStrength extends Properties<typeof ChargeStrengthSpec> {}
/** `(small)`, `(medium)` or `(large)`: a `trireg`'s charge strength (6.6.4.2). */
export class ChargeStrength extends SyntaxNode {
  static override SPEC = ChargeStrengthSpec;
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
  visibility: optionalChoice(...VISIBILITYS),
  type: one(() => [DataType]),
  name: one(() => [Identifier]),
  dimensions: many(() => [Dimension]),
};
export interface TypedefDeclaration extends Properties<typeof TypedefDeclarationSpec> {}
/** `typedef type name dimensions;` (6.18), `local` or `protected` in a class (8.18). */
export class TypedefDeclaration extends Item {
  static override SPEC = TypedefDeclarationSpec;
  static override SINCE: Availability | null = sv();
}

const EmptyItemSpec = {};
export interface EmptyItem extends Properties<typeof EmptyItemSpec> {}
/** `;` alone, where items are listed (A.1.4, A.1.9). */
export class EmptyItem extends Item {
  static override SPEC = EmptyItemSpec;
  static override SINCE: Availability | null = sv();
}

const DpiImportSpec = {
  spec: choice(...DPI_SPECS),
  property: optionalChoice(...DPI_PROPERTYS),
  c_name: optional(() => [Identifier]),
  prototype: one(() => [FunctionDeclaration, TaskDeclaration]),
};
export interface DpiImport extends Properties<typeof DpiImportSpec> {}
/**
 * `import "DPI-C" property c_name = prototype;`: a C function or task, `context` or a `pure` function, which
 * SystemVerilog calls by the prototype's name (35.5.4).
 */
export class DpiImport extends Item {
  static override SPEC = DpiImportSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { spec: [["DPI-C", sv(2009)]] };
  override check(): string[] {
    return this.property === "pure" && this.prototype instanceof TaskDeclaration ? ["a pure DpiImport is a function"] : [];
  }
}

const DpiExportSpec = {
  spec: choice(...DPI_SPECS),
  c_name: optional(() => [Identifier]),
  keyword: choice(...SUBROUTINE_KEYWORDS),
  name: one(() => [Identifier]),
};
export interface DpiExport extends Properties<typeof DpiExportSpec> {}
/** `export "DPI-C" c_name = function name;`: a function or task C calls (35.5.4). */
export class DpiExport extends Item {
  static override SPEC = DpiExportSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { spec: [["DPI-C", sv(2009)]] };
}

const BindDirectiveSpec = {
  target: one(() => [Expression]),
  instances: many(() => [Expression]),
  instantiation: one(() => [ModuleInstantiation]),
};
export interface BindDirective extends Properties<typeof BindDirectiveSpec> {}
/**
 * `bind target: instances instantiation;`: an instantiation into a module, an interface or a checker, or into
 * some of its instances, without changing its source (23.11).
 */
export class BindDirective extends Item {
  static override SPEC = BindDirectiveSpec;
  static override SINCE: Availability | null = sv();
}

const ElaborationTaskSpec = {
  name: choice(...ELABORATION_TASK_NAMES),
  arguments: many(() => [Expression, EmptyArgument]),
};
export interface ElaborationTask extends Properties<typeof ElaborationTaskSpec> {}
/**
 * `$fatal(arguments);`, `$error`, `$warning` or `$info` among items: a message, or a failure, when elaboration
 * reaches it (20.11).
 */
export class ElaborationTask extends Item {
  static override SPEC = ElaborationTaskSpec;
  static override SINCE: Availability | null = sv(2009);
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

const ExportDeclarationSpec = {
  all: flag(),
  items: many(() => [ImportItem]),
};
export interface ExportDeclaration extends Properties<typeof ExportDeclarationSpec> {}
/**
 * `export package::name, ...;` or `export *::*;` (`all`) in a package: names it imports that the packages which
 * import it see too (26.6).
 */
export class ExportDeclaration extends Item {
  static override SPEC = ExportDeclarationSpec;
  static override SINCE: Availability | null = sv(2009);
  override check(): string[] {
    return (this.all === true) === (this.items.length > 0) ? ["an ExportDeclaration exports all or items"] : [];
  }
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

const NetTypeDeclarationSpec = {
  type: one(() => [DataType]),
  name: one(() => [Identifier]),
  function: optional(() => [Name]),
};
export interface NetTypeDeclaration extends Properties<typeof NetTypeDeclarationSpec> {}
/** `nettype type name with function;`: a user-defined net type, resolved by `function` (6.6.7). */
export class NetTypeDeclaration extends Item {
  static override SPEC = NetTypeDeclarationSpec;
  static override SINCE: Availability | null = sv(2012);
}

const NetAliasSpec = {
  nets: many(() => [Expression]),
};
export interface NetAlias extends Properties<typeof NetAliasSpec> {}
/** `alias net = net = ...;`: two nets or more that are one (10.11). */
export class NetAlias extends Item {
  static override SPEC = NetAliasSpec;
  static override SINCE: Availability | null = sv();
  override check(): string[] {
    return this.nets.length < 2 ? ["a NetAlias has two nets or more"] : [];
  }
}

const DefParamSpec = {
  assignments: many(() => [DefParamAssignment]),
};
export interface DefParam extends Properties<typeof DefParamSpec> {}
/** `defparam target = value, ...;`: parameters of instances, set by their hierarchical names (23.10.1). */
export class DefParam extends Item {
  static override SPEC = DefParamSpec;
}

const DefParamAssignmentSpec = {
  target: one(() => [Expression]),
  value: one(() => [Expression]),
};
export interface DefParamAssignment extends Properties<typeof DefParamAssignmentSpec> {}
/** `target = value` in a `defparam`. */
export class DefParamAssignment extends SyntaxNode {
  static override SPEC = DefParamAssignmentSpec;
}

const TimeUnitsDeclarationSpec = {
  keyword: choice(...TIME_UNIT_KEYWORDS),
  time: one(() => [TimeLiteral]),
  precision: optional(() => [TimeLiteral]),
};
export interface TimeUnitsDeclaration extends Properties<typeof TimeUnitsDeclarationSpec> {}
/** `timeunit time / precision;` or `timeprecision time;` (3.14.2.2). */
export class TimeUnitsDeclaration extends Item {
  static override SPEC = TimeUnitsDeclarationSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { precision: [[true, sv(2009)]] };
  override check(): string[] {
    return this.precision !== null && this.keyword === "timeprecision"
      ? ["a timeprecision TimeUnitsDeclaration has no precision"] : [];
  }
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
  ports: many(() => [ModportPort, ModportSubroutine, ModportClocking]),
};
export interface ModportItem extends Properties<typeof ModportItemSpec> {}
/** `name (ports)` in a modport declaration (25.5). */
export class ModportItem extends SyntaxNode {
  static override SPEC = ModportItemSpec;
}

const ModportPortSpec = {
  attributes: many(() => [AttributeInstance]),
  direction: choice(...DIRECTIONS),
  explicit: flag(),
  name: one(() => [Identifier]),
  value: optional(() => [Expression]),
};
export interface ModportPort extends Properties<typeof ModportPortSpec> {}
/**
 * `direction name` in a modport, or `explicit`ly `direction .name(value)`, a port named apart from the expression
 * it is, or that is nothing (25.5.4). Attributes before a group of ports are each port's (A.2.9).
 */
export class ModportPort extends SyntaxNode {
  static override SPEC = ModportPortSpec;
  override check(): string[] {
    return this.value !== null && this.explicit !== true ? ["a ModportPort with a value is explicit"] : [];
  }
}

const ModportSubroutineSpec = {
  attributes: many(() => [AttributeInstance]),
  keyword: choice(...IMPORT_EXPORTS),
  name: optional(() => [Identifier]),
  prototype: optional(() => [FunctionDeclaration, TaskDeclaration]),
};
export interface ModportSubroutine extends Properties<typeof ModportSubroutineSpec> {}
/**
 * `import name` or `export name` in a modport, or with a `prototype`, a function's or a task's without its body
 * (`import task t(int a)`) (25.7), with its group's attributes.
 */
export class ModportSubroutine extends SyntaxNode {
  static override SPEC = ModportSubroutineSpec;
  override check(): string[] {
    return (this.name === null) === (this.prototype === null) ? ["a ModportSubroutine has a name or a prototype"] : [];
  }
}

const ModportClockingSpec = {
  attributes: many(() => [AttributeInstance]),
  name: one(() => [Identifier]),
};
export interface ModportClocking extends Properties<typeof ModportClockingSpec> {}
/** `clocking name` in a modport: a clocking block's signals, as it gives them (25.5.5), with its attributes. */
export class ModportClocking extends SyntaxNode {
  static override SPEC = ModportClockingSpec;
}

const ContinuousAssignSpec = {
  strength: optional(() => [DriveStrength]),
  delay: optional(() => [DelayControl]),
  assignments: many(() => [AssignmentExpression]),
};
export interface ContinuousAssign extends Properties<typeof ContinuousAssignSpec> {}
/** `assign strength #delay target = value, ...;` (10.3). */
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
  specifier: optionalChoice(...OVERRIDE_SPECIFIERS),
  final: flag(),
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
 * `extern`, defined outside the class, or `pure virtual` (8.10, 8.20, 8.24). A constructor is named `new`. A virtual
 * method's `:initial` or `:extends` `specifier` and `:final` say whether it overrides and may be overridden (8.20).
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
    specifier: [[true, sv(2023)]],
    final: [[true, sv(2023)]],
  };
  override check(): string[] {
    return methodProblems(this);
  }
}

const TaskDeclarationSpec = {
  extern: flag(),
  forkjoin: flag(),
  pure: flag(),
  virtual: flag(),
  visibility: optionalChoice(...VISIBILITYS),
  static: flag(),
  specifier: optionalChoice(...OVERRIDE_SPECIFIERS),
  final: flag(),
  lifetime: optionalChoice(...LIFETIMES),
  name: one(() => [Name]),
  ports: many(() => [TfPort]),
  body: many(() => [Item, Statement, Directive, Comment]),
  labeled: flag(),
};
export interface TaskDeclaration extends Properties<typeof TaskDeclarationSpec> {}
/**
 * `task lifetime name(ports); body endtask` (13.3). In a class, a method may be `local` or `protected`, `static`,
 * `virtual`, and a prototype without a body: `extern`, defined outside the class, or `pure virtual` (8.10, 8.20,
 * 8.24). A constructor is named `new`. A virtual method's `:initial` or `:extends` `specifier` and `:final` say
 * whether it overrides and may be overridden (8.20). In an interface, an `extern` prototype is a task a module exports
 * through a modport, and an `extern forkjoin` one a task several modules may export (25.7.4).
 */
export class TaskDeclaration extends Item {
  static override SPEC = TaskDeclarationSpec;
  static override FEATURES: Features = {
    lifetime: [[true, verilog(2001)]],
    labeled: [[true, sv()]],
    extern: [[true, sv()]],
    forkjoin: [[true, sv()]],
    pure: [[true, sv()]],
    virtual: [[true, sv()]],
    visibility: [[true, sv()]],
    static: [[true, sv()]],
    specifier: [[true, sv(2023)]],
    final: [[true, sv(2023)]],
  };
  override check(): string[] {
    if (this.forkjoin === true && this.extern !== true) return ["a forkjoin TaskDeclaration is extern"];
    return methodProblems(this);
  }
}

const TfPortSpec = {
  attributes: many(() => [AttributeInstance]),
  const: flag(),
  direction: optionalChoice(...DIRECTIONS),
  static: flag(),
  var: flag(),
  type: optional(() => [DataType]),
  name: one(() => [Identifier]),
  dimensions: many(() => [Dimension]),
  value: optional(() => [Expression]),
};
export interface TfPort extends Properties<typeof TfPortSpec> {}
/**
 * `direction var type name dimensions = default`, a task's or function's port in parentheses (13.3). Without a
 * direction or a type, a port inherits them from the one before it. A `ref` may be `const ref` or `ref static`
 * (13.5.2).
 */
export class TfPort extends SyntaxNode {
  static override SPEC = TfPortSpec;
  static override SINCE: Availability | null = verilog(2001);
  static override FEATURES: Features = {
    var: [[true, sv()]],
    value: [[true, sv()]],
    direction: [["ref", sv()]],
    const: [[true, sv()]],
    static: [[true, sv(2023)]],
  };
  override check(): string[] {
    return (this.const === true || this.static === true) && this.direction !== "ref"
      ? ["a const or static TfPort is a ref"] : [];
  }
}

// --- Classes (8) ---

const ClassDeclarationSpec = {
  virtual: flag(),
  interface: flag(),
  final: flag(),
  name: one(() => [Identifier]),
  parameters: many(() => [ParameterDeclaration, TypeParameterDeclaration]),
  base: optional(() => [NamedType]),
  arguments: many(() => [Expression, Connection]),
  defaulted: flag(),
  interfaces: many(() => [NamedType]),
  items: many(() => [Item, Directive, Comment]),
  labeled: flag(),
};
export interface ClassDeclaration extends Properties<typeof ClassDeclarationSpec> {}
/**
 * `virtual class name #(parameters) extends base(arguments) implements interfaces; items endclass`, or
 * `interface class name #(parameters) extends interfaces; items endclass` (8.3, 8.26). Its items are properties,
 * methods, parameters, types and classes. `labeled` repeats the name after `endclass`. A `final` class
 * (`class :final c`) has no derived classes, and a `defaulted` one passes its base its constructor's arguments
 * (`extends base(default)`) (8.15).
 */
export class ClassDeclaration extends Item {
  static override SPEC = ClassDeclarationSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = {
    interface: [[true, sv(2012)]],
    interfaces: [[true, sv(2012)]],
    final: [[true, sv(2023)]],
    defaulted: [[true, sv(2023)]],
  };
  override check(): string[] {
    if (this.interface === true && (this.virtual === true || this.base !== null || this.arguments.length > 0)) {
      return ["an interface ClassDeclaration has no virtual, base or arguments"];
    }
    if (this.arguments.length > 0 && this.base === null) return ["a ClassDeclaration with arguments has a base"];
    if (this.defaulted === true && (this.base === null || this.arguments.length > 0)) {
      return ["a ClassDeclaration with default arguments has a base and no others"];
    }
    return [];
  }
}

// --- Constraints (18) ---

const ConstraintDeclarationSpec = {
  static: flag(),
  specifier: optionalChoice(...OVERRIDE_SPECIFIERS),
  final: flag(),
  name: one(() => [Name]),
  items: many(() => [Constraint, Directive, Comment]),
};
export interface ConstraintDeclaration extends Properties<typeof ConstraintDeclarationSpec> {}
/**
 * `static constraint name { constraints }` in a class, or outside it with a qualified name (`constraint c::k { }`),
 * which defines a prototype (18.5). Its `:initial` or `:extends` `specifier` and `:final` say whether it overrides and
 * may be overridden (18.5.2).
 */
export class ConstraintDeclaration extends Item {
  static override SPEC = ConstraintDeclarationSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { specifier: [[true, sv(2023)]], final: [[true, sv(2023)]] };
}

const ConstraintPrototypeSpec = {
  qualifier: optionalChoice(...PROTOTYPE_QUALIFIERS),
  static: flag(),
  specifier: optionalChoice(...OVERRIDE_SPECIFIERS),
  final: flag(),
  name: one(() => [Identifier]),
};
export interface ConstraintPrototype extends Properties<typeof ConstraintPrototypeSpec> {}
/**
 * `qualifier static constraint name;`: a constraint defined outside its class, `extern` or by default, or `pure`,
 * which derived classes define (18.5.1), with a `specifier` and `final` as a declaration has.
 */
export class ConstraintPrototype extends Item {
  static override SPEC = ConstraintPrototypeSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = {
    qualifier: [["pure", sv(2012)]],
    specifier: [[true, sv(2023)]],
    final: [[true, sv(2023)]],
  };
}

const ConstraintBlockSpec = {
  items: many(() => [Constraint, Directive, Comment]),
};
export interface ConstraintBlock extends Properties<typeof ConstraintBlockSpec> {}
/** `{ constraints }`, the constraints an implication, a condition or a loop applies (18.5). */
export class ConstraintBlock extends Constraint {
  static override SPEC = ConstraintBlockSpec;
  static override SINCE: Availability | null = sv();
}

const ExpressionConstraintSpec = {
  soft: flag(),
  expression: one(() => [Expression]),
};
export interface ExpressionConstraint extends Properties<typeof ExpressionConstraintSpec> {}
/** `soft expression;`, an expression that must hold, or with `soft` should (18.5.14). */
export class ExpressionConstraint extends Constraint {
  static override SPEC = ExpressionConstraintSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { soft: [[true, sv(2012)]] };
}

const ImplicationConstraintSpec = {
  condition: one(() => [Expression]),
  body: one(() => [Constraint]),
};
export interface ImplicationConstraint extends Properties<typeof ImplicationConstraintSpec> {}
/** `condition -> body`: `body` holds where `condition` does (18.5.6). */
export class ImplicationConstraint extends Constraint {
  static override SPEC = ImplicationConstraintSpec;
  static override SINCE: Availability | null = sv();
}

const ConditionalConstraintSpec = {
  condition: one(() => [Expression]),
  consequence: one(() => [Constraint]),
  alternative: optional(() => [Constraint]),
};
export interface ConditionalConstraint extends Properties<typeof ConditionalConstraintSpec> {}
/** `if (condition) consequence else alternative` (18.5.7). */
export class ConditionalConstraint extends Constraint {
  static override SPEC = ConditionalConstraintSpec;
  static override SINCE: Availability | null = sv();
}

const ForeachConstraintSpec = {
  array: one(() => [Expression]),
  variables: many(() => [Identifier, EmptyArgument]),
  body: one(() => [Constraint]),
};
export interface ForeachConstraint extends Properties<typeof ForeachConstraintSpec> {}
/** `foreach (array[variables]) body`, a constraint on each element (18.5.8.1). */
export class ForeachConstraint extends Constraint {
  static override SPEC = ForeachConstraintSpec;
  static override SINCE: Availability | null = sv();
}

const SolveBeforeConstraintSpec = {
  solve: many(() => [Expression]),
  before: many(() => [Expression]),
};
export interface SolveBeforeConstraint extends Properties<typeof SolveBeforeConstraintSpec> {}
/** `solve solve before before;`, an order in which variables are chosen (18.5.10). */
export class SolveBeforeConstraint extends Constraint {
  static override SPEC = SolveBeforeConstraintSpec;
  static override SINCE: Availability | null = sv();
}

const DisableSoftConstraintSpec = {
  target: one(() => [Expression]),
};
export interface DisableSoftConstraint extends Properties<typeof DisableSoftConstraintSpec> {}
/** `disable soft target;`, which drops the soft constraints on a variable (18.5.14.2). */
export class DisableSoftConstraint extends Constraint {
  static override SPEC = DisableSoftConstraintSpec;
  static override SINCE: Availability | null = sv(2012);
}

const UniqueConstraintSpec = {
  set: many(() => [Expression, Range]),
};
export interface UniqueConstraint extends Properties<typeof UniqueConstraintSpec> {}
/** `unique { set }`: the variables and arrays of `set` have different values (18.5.5). */
export class UniqueConstraint extends Constraint {
  static override SPEC = UniqueConstraintSpec;
  static override SINCE: Availability | null = sv(2012);
}

const DistExpressionSpec = {
  value: one(() => [Expression]),
  items: many(() => [DistItem]),
};
export interface DistExpression extends Properties<typeof DistExpressionSpec> {}
/** `value dist { items }`, a distribution of a random variable's values, in a constraint (18.5.4). */
export class DistExpression extends Expression {
  static override SPEC = DistExpressionSpec;
  static override SINCE: Availability | null = sv();
}

const DistItemSpec = {
  value: optional(() => [Expression, Range]),
  operator: optionalChoice(...DIST_OPERATORS),
  weight: optional(() => [Expression]),
};
export interface DistItem extends Properties<typeof DistItemSpec> {}
/**
 * `value := weight` (each value of a range weighs `weight`) or `value :/ weight` (the range weighs `weight`), or
 * `default :/ weight` without a `value`; without a weight, a value weighs 1 (18.5.4).
 */
export class DistItem extends SyntaxNode {
  static override SPEC = DistItemSpec;
  static override SINCE: Availability | null = sv();
  override features(): [string, Availability][] {
    return this.value === null ? [["DistItem default", sv(2023)]] : [];
  }

  override check(): string[] {
    if ((this.operator === null) !== (this.weight === null)) {
      return ["a DistItem has both an operator and a weight, or neither"];
    }
    if (this.value === null && this.operator !== ":/") return ["a default DistItem weighs its values with :/"];
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

const GateInstantiationSpec = {
  keyword: optionalChoice(...GATE_KEYWORDS),
  primitive: optional(() => [Identifier]),
  strength: optional(() => [DriveStrength, PullStrength]),
  delay: optional(() => [DelayControl]),
  instances: many(() => [GateInstance]),
};
export interface GateInstantiation extends Properties<typeof GateInstantiationSpec> {}
/**
 * `gate strength #delay instances;`: built-in gates, switches and pulls (28.3), or a user-defined primitive's
 * instances without names (29.8), whose `primitive` is its name.
 */
export class GateInstantiation extends Item {
  static override SPEC = GateInstantiationSpec;
  override check(): string[] {
    if ((this.keyword === null) === (this.primitive === null)) return ["a GateInstantiation is a gate's or a primitive's"];
    if (this.strength instanceof PullStrength && this.keyword !== "pullup" && this.keyword !== "pulldown") {
      return ["a GateInstantiation with a pull strength is a pullup or a pulldown"];
    }
    return [];
  }
}

const GateInstanceSpec = {
  name: optional(() => [Identifier]),
  dimensions: many(() => [Dimension]),
  terminals: many(() => [Expression]),
};
export interface GateInstance extends Properties<typeof GateInstanceSpec> {}
/**
 * `name dimensions (terminals)`, a gate's instance: its output terminals, then its inputs; the name may be left
 * out (28.3).
 */
export class GateInstance extends SyntaxNode {
  static override SPEC = GateInstanceSpec;
  override check(): string[] {
    return this.dimensions.length > 0 && this.name === null ? ["a GateInstance with dimensions has a name"] : [];
  }
}

const PullStrengthSpec = {
  strength: choice(...STRENGTHS),
};
export interface PullStrength extends Properties<typeof PullStrengthSpec> {}
/** `(strength)`, a `pullup`'s or a `pulldown`'s strength (28.6). */
export class PullStrength extends SyntaxNode {
  static override SPEC = PullStrengthSpec;
}

const UdpDeclarationSpec = {
  extern: flag(),
  name: one(() => [Identifier]),
  ports: many(() => [UdpPort, Identifier, WildcardPort]),
  declarations: many(() => [UdpPort]),
  initial: optional(() => [UdpInitial]),
  entries: many(() => [UdpEntry, Comment, Directive]),
  labeled: flag(),
};
export interface UdpDeclaration extends Properties<typeof UdpDeclarationSpec> {}
/**
 * `primitive name (ports); declarations initial table entries endtable endprimitive`, a user-defined primitive:
 * its output from its inputs, and from its current state when its output is a `reg` (29). An ANSI header declares
 * its ports (`UdpPort`s); a non-ANSI one names them (`Identifier`s), and `declarations` declare them; `.*`, its only
 * port, takes them from an `extern` declaration of its name, a header alone (29.3). `labeled` repeats the name after
 * `endprimitive`.
 */
export class UdpDeclaration extends Item {
  static override SPEC = UdpDeclarationSpec;
  static override FEATURES: Features = { labeled: [[true, sv()]], extern: [[true, sv()]] };
  override check(): string[] {
    const wildcard = this.ports.some((p) => p instanceof WildcardPort);
    if (this.extern === true && (this.declarations.length > 0 || this.initial !== null || this.entries.length > 0
      || this.labeled === true || wildcard)) {
      return ["an extern UdpDeclaration is a header alone, with its ports"];
    }
    if (wildcard && this.ports.length > 1) return ["a UdpDeclaration's .* is its only port"];
    return [];
  }
}

const UdpPortSpec = {
  attributes: many(() => [AttributeInstance]),
  direction: optionalChoice(...UDP_DIRECTIONS),
  reg: flag(),
  names: many(() => [Identifier]),
  value: optional(() => [Expression]),
};
export interface UdpPort extends Properties<typeof UdpPortSpec> {}
/**
 * `output reg name = value`, `input names` or `reg name`: a primitive's port, or its output's state (29.3), with
 * its attributes.
 */
export class UdpPort extends SyntaxNode {
  static override SPEC = UdpPortSpec;
  override check(): string[] {
    if (this.direction === "input" && (this.reg === true || this.value !== null)) return ["an input UdpPort has no reg and no value"];
    if (this.direction === null && this.reg !== true) return ["a UdpPort without a direction is a reg"];
    if (this.value !== null && (this.reg !== true || this.names.length !== 1)) return ["a UdpPort with a value is one output reg"];
    return [];
  }
}

const UdpInitialSpec = {
  name: one(() => [Identifier]),
  value: one(() => [Expression]),
};
export interface UdpInitial extends Properties<typeof UdpInitialSpec> {}
/** `initial name = value;`, a sequential primitive's starting state (29.7). */
export class UdpInitial extends SyntaxNode {
  static override SPEC = UdpInitialSpec;
}

const UdpEntrySpec = {
  inputs: text(),
  current: optionalText(),
  output: text(),
};
export interface UdpEntry extends Properties<typeof UdpEntrySpec> {}
/**
 * `inputs : current : output;`, a row of a primitive's table: its inputs' levels and edges (`0 (01) ?`),
 * separated by spaces, and for a sequential primitive its current state; the output is a level, or `-` for no change
 * (29.3.6).
 */
export class UdpEntry extends SyntaxNode {
  static override SPEC = UdpEntrySpec;
  override check(): string[] {
    const [inputs, current, output] = [this.inputs, this.current, this.output];
    if (typeof inputs !== "string" || typeof output !== "string") return [];
    const edge = (f: string) => f.length === 4 && f.startsWith("(") && f.endsWith(")") && [...f.slice(1, 3)].every((c) => UDP_LEVELS.has(c));
    if (!inputs.split(" ").every((f) => UDP_INPUTS.has(f) || edge(f))) return ["a UdpEntry's inputs are levels and edges"];
    if (current !== null && !UDP_LEVELS.has(current as string)) return ["a UdpEntry's current state is a level"];
    if (!["0", "1", "x", "X"].includes(output) && (output !== "-" || current === null)) {
      return ["a UdpEntry's output is 0, 1 or x, or - with a current state"];
    }
    return [];
  }
}

const SpecifyBlockSpec = {
  items: many(() => [Item, Directive, Comment]),
};
export interface SpecifyBlock extends Properties<typeof SpecifyBlockSpec> {}
/** `specify items endspecify`: a module's paths, their delays, and its timing checks (30). */
export class SpecifyBlock extends Item {
  static override SPEC = SpecifyBlockSpec;
}

const SpecparamDeclarationSpec = {
  type: optional(() => [DataType]),
  assignments: many(() => [SpecparamAssignment]),
};
export interface SpecparamDeclaration extends Properties<typeof SpecparamDeclarationSpec> {}
/** `specparam range assignments;`, parameters of timing and delay, in a specify block or a module (6.20.5). */
export class SpecparamDeclaration extends Item {
  static override SPEC = SpecparamDeclarationSpec;
}

const SpecparamAssignmentSpec = {
  name: one(() => [Identifier]),
  value: one(() => [Expression]),
  limit: optional(() => [Expression]),
};
export interface SpecparamAssignment extends Properties<typeof SpecparamAssignmentSpec> {}
/** `name = value`, or `PATHPULSE$input$output = (reject, error)` with an error `limit` (30.7). */
export class SpecparamAssignment extends SyntaxNode {
  static override SPEC = SpecparamAssignmentSpec;
}

const PathDeclarationSpec = {
  condition: optional(() => [Expression]),
  ifnone: flag(),
  edge: optionalChoice(...EDGES),
  inputs: many(() => [Expression]),
  polarity: optionalChoice(...POLARITYS),
  operator: choice(...PATH_OPERATORS),
  outputs: many(() => [Expression]),
  data_polarity: optionalChoice(...DATA_POLARITYS),
  data: optional(() => [Expression]),
  delays: many(() => [Expression]),
};
export interface PathDeclaration extends Properties<typeof PathDeclarationSpec> {}
/**
 * `if (condition) (edge inputs polarity operator outputs) = delays;`, or `ifnone`: a module path and its delays
 * (30.3). `=>` is a parallel path, from one input to one output, and `*>` a full one, from each input to each output;
 * with `data`, an edge-sensitive path's outputs are `(outputs data_polarity data)`.
 */
export class PathDeclaration extends Item {
  static override SPEC = PathDeclarationSpec;
  override check(): string[] {
    if (this.ifnone === true && this.condition !== null) return ["an ifnone PathDeclaration has no condition"];
    if ((this.data === null) !== (this.data_polarity === null)) return ["a PathDeclaration's data has a polarity, and a polarity data"];
    if (this.operator === "=>" && (this.inputs.length !== 1 || this.outputs.length !== 1)) {
      return ["a parallel PathDeclaration has one input and one output"];
    }
    return [];
  }
}

const TimingCheckSpec = {
  name: choice(...TIMING_CHECK_NAMES),
  arguments: many(() => [Expression, TimingCheckEvent, EmptyArgument]),
};
export interface TimingCheck extends Properties<typeof TimingCheckSpec> {}
/** `$setup(arguments);` and the other system timing checks of a specify block (31). */
export class TimingCheck extends Item {
  static override SPEC = TimingCheckSpec;
}

const TimingCheckEventSpec = {
  edge: optionalChoice(...EDGES),
  descriptors: optionalText(),
  terminal: one(() => [Expression]),
  condition: optional(() => [Expression]),
};
export interface TimingCheckEvent extends Properties<typeof TimingCheckEventSpec> {}
/**
 * `edge [descriptors] terminal &&& condition`, an event a timing check checks: an edge of a terminal, when a
 * condition holds; `descriptors` are an `edge`'s transitions as written (`01, 10`) (31.8).
 */
export class TimingCheckEvent extends SyntaxNode {
  static override SPEC = TimingCheckEventSpec;
  override check(): string[] {
    return this.descriptors !== null && this.edge !== "edge" ? ["a TimingCheckEvent's descriptors are an edge's"] : [];
  }
}

const PulseStyleDeclarationSpec = {
  keyword: choice(...PULSE_STYLES),
  outputs: many(() => [Expression]),
};
export interface PulseStyleDeclaration extends Properties<typeof PulseStyleDeclarationSpec> {}
/**
 * `pulsestyle_onevent outputs;`, `pulsestyle_ondetect`, `showcancelled` or `noshowcancelled`: how outputs show
 * pulses (30.7.4).
 */
export class PulseStyleDeclaration extends Item {
  static override SPEC = PulseStyleDeclarationSpec;
  static override SINCE: Availability | null = verilog(2001);
}

const ModuleInstantiationSpec = {
  module: one(() => [Identifier, ScopedName]),
  parameters: many(() => [Expression, DataType, Connection]),
  instances: many(() => [Instance]),
};
export interface ModuleInstantiation extends Properties<typeof ModuleInstantiationSpec> {}
/**
 * `module #(parameters) instance (connections), ...;`, of a module, an interface, a program or a checker (23.3,
 * 17.3), which a package may hold (`p::c`). Parameters and connections are ordered expressions or
 * `NamedConnection`s.
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

const AttributedConnectionSpec = {
  attributes: many(() => [AttributeInstance]),
  connection: one(() => [Expression, Connection]),
};
export interface AttributedConnection extends Properties<typeof AttributedConnectionSpec> {}
/** `(* ... *) connection`: a port connection with attributes (23.3.2). */
export class AttributedConnection extends Connection {
  static override SPEC = AttributedConnectionSpec;
  static override SINCE: Availability | null = verilog(2001);
}

const NamedConnectionSpec = {
  name: one(() => [Identifier]),
  value: optional(() => [Expression, DataType, Property]),
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
  matches: flag(),
  items: many(() => [CaseItem, PatternCaseItem]),
};
export interface CaseStatement extends Properties<typeof CaseStatementSpec> {}
/**
 * `qualifier case (expression) inside items endcase`, or `casez` or `casex` (12.5), or `case (expression) matches`
 * of `PatternCaseItem`s (12.6.1).
 */
export class CaseStatement extends Statement {
  static override SPEC = CaseStatementSpec;
  static override FEATURES: Features = {
    qualifier: [["unique", sv()], ["priority", sv()], ["unique0", sv(2009)]],
    inside: [[true, sv()]],
    matches: [[true, sv()]],
  };
  override check(): string[] {
    if (this.inside === true && this.matches === true) return ["a CaseStatement is inside or matches, not both"];
    const patterns = this.items.map((i) => i instanceof PatternCaseItem);
    if (this.matches !== true && patterns.some((p) => p)) return ["a CaseStatement with PatternCaseItems matches"];
    if (this.matches === true && !patterns.every((p, i) => p || (this.items[i] as CaseItem).expressions.length === 0)) {
      return ["a matching CaseStatement has PatternCaseItems and a default"];
    }
    return [];
  }
}

const PatternCaseItemSpec = {
  pattern: one(() => [Pattern, Expression]),
  guard: optional(() => [Expression]),
  body: one(() => [Statement]),
};
export interface PatternCaseItem extends Properties<typeof PatternCaseItemSpec> {}
/** `pattern &&& guard: body` in a `case matches` (12.6.1). */
export class PatternCaseItem extends SyntaxNode {
  static override SPEC = PatternCaseItemSpec;
  static override SINCE: Availability | null = sv();
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
  variables: many(() => [Identifier, EmptyArgument]),
  body: one(() => [Statement]),
};
export interface ForeachStatement extends Properties<typeof ForeachStatementSpec> {}
/** `foreach (array[variables]) body` (12.7.3); a dimension it skips is an `EmptyArgument` (`q[, j]`). */
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
  timing: optional(() => [TimingControl]),
  event: one(() => [Expression]),
};
export interface EventTrigger extends Properties<typeof EventTriggerSpec> {}
/** `-> event;`, or `->> timing event;` when `nonblocking`, after a delay or an event control (15.5.1). */
export class EventTrigger extends Statement {
  static override SPEC = EventTriggerSpec;
  static override FEATURES: Features = { nonblocking: [[true, sv()]] };
  override check(): string[] {
    return this.timing !== null && this.nonblocking !== true ? ["an EventTrigger with a timing is nonblocking"] : [];
  }
}

const ForceStatementSpec = {
  keyword: choice(...FORCE_KEYWORDS),
  target: one(() => [Expression]),
  value: one(() => [Expression]),
};
export interface ForceStatement extends Properties<typeof ForceStatementSpec> {}
/**
 * `force target = value;` or `assign target = value;`: a procedural continuous assignment, which holds until
 * `release` or `deassign` (10.6).
 */
export class ForceStatement extends Statement {
  static override SPEC = ForceStatementSpec;
}

const ReleaseStatementSpec = {
  keyword: choice(...RELEASE_KEYWORDS),
  target: one(() => [Expression]),
};
export interface ReleaseStatement extends Properties<typeof ReleaseStatementSpec> {}
/** `release target;` or `deassign target;`, which ends a `force` or a procedural `assign` (10.6). */
export class ReleaseStatement extends Statement {
  static override SPEC = ReleaseStatementSpec;
}

const CheckerStatementSpec = {
  instantiation: one(() => [ModuleInstantiation]),
};
export interface CheckerStatement extends Properties<typeof CheckerStatementSpec> {}
/** A checker instantiated in a procedure, as its statement (17.3). */
export class CheckerStatement extends Statement {
  static override SPEC = CheckerStatementSpec;
  static override SINCE: Availability | null = sv(2009);
}

const WaitForkStatementSpec = {};
export interface WaitForkStatement extends Properties<typeof WaitForkStatementSpec> {}
/** `wait fork;`, until the processes this one forked end (9.6.1). */
export class WaitForkStatement extends Statement {
  static override SPEC = WaitForkStatementSpec;
  static override SINCE: Availability | null = sv();
}

const WaitOrderStatementSpec = {
  events: many(() => [Expression]),
  pass_action: optional(() => [Statement]),
  fail_action: optional(() => [Statement]),
};
export interface WaitOrderStatement extends Properties<typeof WaitOrderStatementSpec> {}
/** `wait_order (events) pass else fail`: until the events trigger in order (15.5.4). */
export class WaitOrderStatement extends Statement {
  static override SPEC = WaitOrderStatementSpec;
  static override SINCE: Availability | null = sv();
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

const RandCaseStatementSpec = {
  items: many(() => [RandCaseItem]),
};
export interface RandCaseStatement extends Properties<typeof RandCaseStatementSpec> {}
/** `randcase weight: body ... endcase`: one of the bodies, chosen at random by their weights (18.16). */
export class RandCaseStatement extends Statement {
  static override SPEC = RandCaseStatementSpec;
  static override SINCE: Availability | null = sv();
}

const RandCaseItemSpec = {
  weight: one(() => [Expression]),
  body: one(() => [Statement]),
};
export interface RandCaseItem extends Properties<typeof RandCaseItemSpec> {}
/** `weight: body` in a `randcase` (18.16). */
export class RandCaseItem extends SyntaxNode {
  static override SPEC = RandCaseItemSpec;
  static override SINCE: Availability | null = sv();
}

const RandSequenceStatementSpec = {
  first: optional(() => [Identifier]),
  productions: many(() => [Production]),
};
export interface RandSequenceStatement extends Properties<typeof RandSequenceStatementSpec> {}
/**
 * `randsequence (first) productions endsequence`: a sentence of productions, generated from `first`, or the first
 * production (18.17).
 */
export class RandSequenceStatement extends Statement {
  static override SPEC = RandSequenceStatementSpec;
  static override SINCE: Availability | null = sv();
}

const ProductionSpec = {
  type: optional(() => [DataType]),
  name: one(() => [Identifier]),
  ports: many(() => [TfPort]),
  rules: many(() => [ProductionRule]),
};
export interface Production extends Properties<typeof ProductionSpec> {}
/**
 * `type name(ports) : rules;`, a production and its rules, separated by `|`, of which one is chosen; a `void` or
 * typed production returns a value (18.17.7).
 */
export class Production extends SyntaxNode {
  static override SPEC = ProductionSpec;
  static override SINCE: Availability | null = sv();
}

const ProductionRuleSpec = {
  rand_join: flag(),
  bias: optional(() => [Expression]),
  items: many(() => [ProductionItem]),
  weight: optional(() => [Expression]),
  code: optional(() => [ProductionCode]),
};
export interface ProductionRule extends Properties<typeof ProductionRuleSpec> {}
/**
 * `items := weight { code }`: what a rule generates in order, chosen by its weight, after which its code runs;
 * or `rand join (bias) items`, its items interleaved at random (18.17.1, 18.17.5).
 */
export class ProductionRule extends SyntaxNode {
  static override SPEC = ProductionRuleSpec;
  static override SINCE: Availability | null = sv();
  override check(): string[] {
    if (this.bias !== null && this.rand_join !== true) return ["a ProductionRule with a bias is a rand join"];
    if (this.code !== null && this.weight === null) return ["a ProductionRule's code follows its weight"];
    return [];
  }
}

const ProductionCallSpec = {
  name: one(() => [Identifier]),
  arguments: many(() => [Expression, Connection]),
};
export interface ProductionCall extends Properties<typeof ProductionCallSpec> {}
/** `name(arguments)`: a production to generate (18.17.7). */
export class ProductionCall extends ProductionItem {
  static override SPEC = ProductionCallSpec;
  static override SINCE: Availability | null = sv();
}

const ProductionCodeSpec = {
  items: many(() => [Item, Statement, Directive, Comment]),
};
export interface ProductionCode extends Properties<typeof ProductionCodeSpec> {}
/** `{ items }`: code that runs where it is in a rule (18.17.2). */
export class ProductionCode extends ProductionItem {
  static override SPEC = ProductionCodeSpec;
  static override SINCE: Availability | null = sv();
}

const ProductionIfSpec = {
  condition: one(() => [Expression]),
  consequence: one(() => [ProductionCall]),
  alternative: optional(() => [ProductionCall]),
};
export interface ProductionIf extends Properties<typeof ProductionIfSpec> {}
/** `if (condition) consequence else alternative`, a production chosen by a condition (18.17.4). */
export class ProductionIf extends ProductionItem {
  static override SPEC = ProductionIfSpec;
  static override SINCE: Availability | null = sv();
}

const ProductionRepeatSpec = {
  count: one(() => [Expression]),
  item: one(() => [ProductionCall]),
};
export interface ProductionRepeat extends Properties<typeof ProductionRepeatSpec> {}
/** `repeat (count) item`, a production generated `count` times (18.17.4). */
export class ProductionRepeat extends ProductionItem {
  static override SPEC = ProductionRepeatSpec;
  static override SINCE: Availability | null = sv();
}

const ProductionCaseSpec = {
  expression: one(() => [Expression]),
  items: many(() => [ProductionCaseItem]),
};
export interface ProductionCase extends Properties<typeof ProductionCaseSpec> {}
/** `case (expression) items endcase`, a production chosen by a value (18.17.4). */
export class ProductionCase extends ProductionItem {
  static override SPEC = ProductionCaseSpec;
  static override SINCE: Availability | null = sv();
}

const ProductionCaseItemSpec = {
  values: many(() => [Expression]),
  item: one(() => [ProductionCall]),
};
export interface ProductionCaseItem extends Properties<typeof ProductionCaseItemSpec> {}
/** `values: item;`, or `default: item;` without values (18.17.4). */
export class ProductionCaseItem extends SyntaxNode {
  static override SPEC = ProductionCaseItemSpec;
  static override SINCE: Availability | null = sv();
}

const LabeledStatementSpec = {
  label: one(() => [Identifier]),
  statement: one(() => [Statement]),
};
export interface LabeledStatement extends Properties<typeof LabeledStatementSpec> {}
/**
 * `label: statement`, a statement named for `disable` and for its assertions' messages (9.3.5). A labeled block
 * is a named one instead: `x: begin ... end` is `begin : x ... end`.
 */
export class LabeledStatement extends Statement {
  static override SPEC = LabeledStatementSpec;
  static override SINCE: Availability | null = sv();
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

// === Assertions (16) ===

const ConcurrentAssertionSpec = {
  keyword: choice(...CONCURRENT_KEYWORDS),
  sequence: flag(),
  spec: one(() => [PropertySpec]),
  pass_action: optional(() => [Statement]),
  fail_action: optional(() => [Statement]),
};
export interface ConcurrentAssertion extends Properties<typeof ConcurrentAssertionSpec> {}
/**
 * `assert property (spec) pass else fail`, or `assume`, `cover` (of a property, or with `sequence` of a
 * sequence) or `restrict` (16.14). `cover` has no `fail`, and `restrict` no action.
 */
export class ConcurrentAssertion extends Statement {
  static override SPEC = ConcurrentAssertionSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { keyword: [["restrict", sv(2009)]] };
}

const ExpectStatementSpec = {
  spec: one(() => [PropertySpec]),
  pass_action: optional(() => [Statement]),
  fail_action: optional(() => [Statement]),
};
export interface ExpectStatement extends Properties<typeof ExpectStatementSpec> {}
/** `expect (spec) pass else fail`, which waits until a property passes or fails (16.17). */
export class ExpectStatement extends Statement {
  static override SPEC = ExpectStatementSpec;
  static override SINCE: Availability | null = sv();
}

const AssertionItemSpec = {
  label: optional(() => [Identifier]),
  assertion: one(() => [ConcurrentAssertion, ImmediateAssertion]),
};
export interface AssertionItem extends Properties<typeof AssertionItemSpec> {}
/** `label: assertion` among items: a concurrent assertion, or a deferred immediate one (16.4, 16.14). */
export class AssertionItem extends Item {
  static override SPEC = AssertionItemSpec;
  static override SINCE: Availability | null = sv();
}

const PropertySpecSpec = {
  clock: optional(() => [EventControl]),
  disable: optional(() => [Expression]),
  property: one(() => [Property, Expression]),
};
export interface PropertySpec extends Properties<typeof PropertySpecSpec> {}
/** `@(clock) disable iff (disable) property`: a property with its clock and its reset (16.12). */
export class PropertySpec extends SyntaxNode {
  static override SPEC = PropertySpecSpec;
  static override SINCE: Availability | null = sv();
}

const PropertyDeclarationSpec = {
  name: one(() => [Identifier]),
  ports: many(() => [AssertionPort]),
  variables: many(() => [VariableDeclaration]),
  spec: one(() => [PropertySpec]),
  labeled: flag(),
};
export interface PropertyDeclaration extends Properties<typeof PropertyDeclarationSpec> {}
/**
 * `property name(ports); variables spec; endproperty` (16.12). `labeled` repeats the name after `endproperty`;
 * without ports, the name has no parentheses.
 */
export class PropertyDeclaration extends Item {
  static override SPEC = PropertyDeclarationSpec;
  static override SINCE: Availability | null = sv();
}

const SequenceDeclarationSpec = {
  name: one(() => [Identifier]),
  ports: many(() => [AssertionPort]),
  variables: many(() => [VariableDeclaration]),
  sequence: one(() => [Sequence, Expression]),
  labeled: flag(),
};
export interface SequenceDeclaration extends Properties<typeof SequenceDeclarationSpec> {}
/** `sequence name(ports); variables sequence; endsequence` (16.8). */
export class SequenceDeclaration extends Item {
  static override SPEC = SequenceDeclarationSpec;
  static override SINCE: Availability | null = sv();
}

const LetDeclarationSpec = {
  name: one(() => [Identifier]),
  ports: many(() => [AssertionPort]),
  value: one(() => [Expression]),
};
export interface LetDeclaration extends Properties<typeof LetDeclarationSpec> {}
/** `let name(ports) = value;`, an expression with arguments, expanded where it is used (11.12). */
export class LetDeclaration extends Item {
  static override SPEC = LetDeclarationSpec;
  static override SINCE: Availability | null = sv(2009);
}

const AssertionPortSpec = {
  local: flag(),
  direction: optionalChoice(...PORT_DIRECTIONS),
  type: optional(() => [DataType]),
  name: one(() => [Identifier]),
  dimensions: many(() => [Dimension]),
  value: optional(() => [Property, Expression]),
};
export interface AssertionPort extends Properties<typeof AssertionPortSpec> {}
/**
 * `local direction type name dimensions = default`, a port of a property, a sequence or a `let` (16.8). Without a
 * type it is untyped, as `untyped` makes it.
 */
export class AssertionPort extends SyntaxNode {
  static override SPEC = AssertionPortSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { local: [[true, sv(2009)]] };
}

// --- Sequences (16.7) ---

const DelaySequenceSpec = {
  first: optional(() => [Sequence, Expression]),
  steps: many(() => [DelayStep]),
};
export interface DelaySequence extends Properties<typeof DelaySequenceSpec> {}
/** `first ##delay sequence ##delay sequence ...`, or without `first` a sequence that starts with a delay (16.7). */
export class DelaySequence extends Sequence {
  static override SPEC = DelaySequenceSpec;
  static override SINCE: Availability | null = sv();
}

const DelayStepSpec = {
  delay: one(() => [Expression, CycleRange]),
  sequence: one(() => [Sequence, Expression]),
};
export interface DelayStep extends Properties<typeof DelayStepSpec> {}
/** `##delay sequence` in a `DelaySequence`: a number of ticks, or a range of them (16.7). */
export class DelayStep extends SyntaxNode {
  static override SPEC = DelayStepSpec;
  static override SINCE: Availability | null = sv();
}

const CycleRangeSpec = {
  low: one(() => [Expression]),
  high: one(() => [Expression]),
};
export interface CycleRange extends Properties<typeof CycleRangeSpec> {}
/**
 * `[low:high]`, a range of ticks or of repetitions, `high` `$` when unbounded. `##[*]`, `[*]` and `[+]` are
 * `[0:$]`, `[*0:$]` and `[*1:$]` (16.7, 16.9.2).
 */
export class CycleRange extends SyntaxNode {
  static override SPEC = CycleRangeSpec;
  static override SINCE: Availability | null = sv();
}

const RepetitionSequenceSpec = {
  sequence: one(() => [Sequence, Expression]),
  operator: choice(...REPETITION_OPERATORS),
  count: one(() => [Expression, CycleRange]),
};
export interface RepetitionSequence extends Properties<typeof RepetitionSequenceSpec> {}
/**
 * `sequence[*count]` (consecutive), `[->count]` (goto) or `[=count]` (nonconsecutive), of a number or a range of
 * repetitions (16.9.2).
 */
export class RepetitionSequence extends Sequence {
  static override SPEC = RepetitionSequenceSpec;
  static override SINCE: Availability | null = sv();
}

const BinarySequenceSpec = {
  left: one(() => [Sequence, Expression]),
  operator: choice(...SEQUENCE_OPERATORS),
  right: one(() => [Sequence, Expression]),
};
export interface BinarySequence extends Properties<typeof BinarySequenceSpec> {}
/** `left operator right`: `and`, `or`, `intersect`, `within` or `throughout` (16.9). */
export class BinarySequence extends Sequence {
  static override SPEC = BinarySequenceSpec;
  static override SINCE: Availability | null = sv();
}

const ParenthesizedSequenceSpec = {
  sequence: one(() => [Sequence, Expression]),
  items: many(() => [Expression]),
};
export interface ParenthesizedSequence extends Properties<typeof ParenthesizedSequenceSpec> {}
/**
 * `(sequence, items)`: a sequence in parentheses, with the match items (assignments, calls) it runs when it
 * matches (16.10).
 */
export class ParenthesizedSequence extends Sequence {
  static override SPEC = ParenthesizedSequenceSpec;
  static override SINCE: Availability | null = sv();
}

const FirstMatchSequenceSpec = {
  sequence: one(() => [Sequence, Expression]),
  items: many(() => [Expression]),
};
export interface FirstMatchSequence extends Properties<typeof FirstMatchSequenceSpec> {}
/** `first_match(sequence, items)`: the sequence's first match only (16.9.8). */
export class FirstMatchSequence extends Sequence {
  static override SPEC = FirstMatchSequenceSpec;
  static override SINCE: Availability | null = sv();
}

const ClockedSequenceSpec = {
  clock: one(() => [EventControl]),
  sequence: one(() => [Sequence, Expression]),
};
export interface ClockedSequence extends Properties<typeof ClockedSequenceSpec> {}
/** `@(clock) sequence`, a sequence on its own clock (16.16). */
export class ClockedSequence extends Sequence {
  static override SPEC = ClockedSequenceSpec;
  static override SINCE: Availability | null = sv();
}

// --- Properties (16.12) ---

const ImplicationPropertySpec = {
  antecedent: one(() => [Sequence, Expression]),
  operator: choice(...IMPLICATION_OPERATORS),
  consequent: one(() => [Property, Expression]),
};
export interface ImplicationProperty extends Properties<typeof ImplicationPropertySpec> {}
/**
 * `antecedent |-> consequent` (overlapping), `|=>` (on the next tick), or `#-#` and `#=#`, which also need the
 * antecedent to match (16.12.7, 16.12.9).
 */
export class ImplicationProperty extends Property {
  static override SPEC = ImplicationPropertySpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { operator: [["#-#", sv(2009)], ["#=#", sv(2009)]] };
}

const BinaryPropertySpec = {
  left: one(() => [Property, Expression]),
  operator: choice(...PROPERTY_OPERATORS),
  right: one(() => [Property, Expression]),
};
export interface BinaryProperty extends Properties<typeof BinaryPropertySpec> {}
/**
 * `left operator right`: `and`, `or`, `iff`, `implies`, `until`, `s_until`, `until_with` or `s_until_with`
 * (16.12).
 */
export class BinaryProperty extends Property {
  static override SPEC = BinaryPropertySpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = {
    operator: [
      ["iff", sv(2009)], ["implies", sv(2009)], ["until", sv(2009)], ["s_until", sv(2009)], ["until_with", sv(2009)],
      ["s_until_with", sv(2009)]
    ],
  };
}

const UnaryPropertySpec = {
  operator: choice(...UNARY_PROPERTY_OPERATORS),
  range: optional(() => [Expression, CycleRange]),
  operand: one(() => [Property, Expression]),
};
export interface UnaryProperty extends Properties<typeof UnaryPropertySpec> {}
/**
 * `operator [range] operand`: `not`, `nexttime`, `s_nexttime`, `always`, `s_always`, `eventually` or
 * `s_eventually`, with a number of ticks or a range of them for those that take one (16.12).
 */
export class UnaryProperty extends Property {
  static override SPEC = UnaryPropertySpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = {
    operator: [
      ["nexttime", sv(2009)], ["s_nexttime", sv(2009)], ["always", sv(2009)], ["s_always", sv(2009)],
      ["eventually", sv(2009)], ["s_eventually", sv(2009)]
    ],
  };
}

const StrengthPropertySpec = {
  keyword: choice(...STRENGTH_KEYWORDS),
  sequence: one(() => [Sequence, Expression]),
};
export interface StrengthProperty extends Properties<typeof StrengthPropertySpec> {}
/** `strong(sequence)` or `weak(sequence)` (16.12.2). */
export class StrengthProperty extends Property {
  static override SPEC = StrengthPropertySpec;
  static override SINCE: Availability | null = sv(2009);
}

const AbortPropertySpec = {
  keyword: choice(...ABORT_KEYWORDS),
  condition: one(() => [Expression]),
  operand: one(() => [Property, Expression]),
};
export interface AbortProperty extends Properties<typeof AbortPropertySpec> {}
/** `accept_on(condition) operand`, or `reject_on`, `sync_accept_on` or `sync_reject_on` (16.12.14). */
export class AbortProperty extends Property {
  static override SPEC = AbortPropertySpec;
  static override SINCE: Availability | null = sv(2009);
}

const ConditionalPropertySpec = {
  condition: one(() => [Expression]),
  consequence: one(() => [Property, Expression]),
  alternative: optional(() => [Property, Expression]),
};
export interface ConditionalProperty extends Properties<typeof ConditionalPropertySpec> {}
/** `if (condition) consequence else alternative` (16.12.8). */
export class ConditionalProperty extends Property {
  static override SPEC = ConditionalPropertySpec;
  static override SINCE: Availability | null = sv();
}

const CasePropertySpec = {
  expression: one(() => [Expression]),
  items: many(() => [PropertyCaseItem]),
};
export interface CaseProperty extends Properties<typeof CasePropertySpec> {}
/** `case (expression) items endcase` (16.12.8). */
export class CaseProperty extends Property {
  static override SPEC = CasePropertySpec;
  static override SINCE: Availability | null = sv(2009);
}

const PropertyCaseItemSpec = {
  expressions: many(() => [Expression]),
  body: one(() => [Property, Expression]),
};
export interface PropertyCaseItem extends Properties<typeof PropertyCaseItemSpec> {}
/** `expressions: body;`, or `default: body;` without expressions, in a case property (16.12.8). */
export class PropertyCaseItem extends SyntaxNode {
  static override SPEC = PropertyCaseItemSpec;
  static override SINCE: Availability | null = sv(2009);
}

const ParenthesizedPropertySpec = {
  property: one(() => [Property, Expression]),
};
export interface ParenthesizedProperty extends Properties<typeof ParenthesizedPropertySpec> {}
/** `(property)`: a property in parentheses (16.12). */
export class ParenthesizedProperty extends Property {
  static override SPEC = ParenthesizedPropertySpec;
  static override SINCE: Availability | null = sv();
}

const ClockedPropertySpec = {
  clock: one(() => [EventControl]),
  property: one(() => [Property, Expression]),
};
export interface ClockedProperty extends Properties<typeof ClockedPropertySpec> {}
/** `@(clock) property`, a property on its own clock (16.16). */
export class ClockedProperty extends Property {
  static override SPEC = ClockedPropertySpec;
  static override SINCE: Availability | null = sv();
}

// --- Clocking blocks (14) ---

const ClockingDeclarationSpec = {
  scope: optionalChoice(...CLOCKING_SCOPES),
  name: optional(() => [Identifier]),
  clock: one(() => [EventControl]),
  items: many(() => [DefaultSkew, ClockingSignals, PropertyDeclaration, SequenceDeclaration, LetDeclaration, AttributedItem, Directive, Comment]),
  labeled: flag(),
};
export interface ClockingDeclaration extends Properties<typeof ClockingDeclarationSpec> {}
/**
 * `default clocking name @(event); items endclocking`, or `global` (14.3, 14.12, 14.14). A default clocking block
 * may have no name. `labeled` repeats the name after `endclocking`.
 */
export class ClockingDeclaration extends Item {
  static override SPEC = ClockingDeclarationSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { scope: [["global", sv(2009)]] };
}

const DefaultSkewSpec = {
  input: optional(() => [ClockingSkew]),
  output: optional(() => [ClockingSkew]),
};
export interface DefaultSkew extends Properties<typeof DefaultSkewSpec> {}
/** `default input skew output skew;` in a clocking block (14.3). */
export class DefaultSkew extends Item {
  static override SPEC = DefaultSkewSpec;
  static override SINCE: Availability | null = sv();
}

const ClockingSignalsSpec = {
  direction: choice(...CLOCKING_DIRECTIONS),
  input_skew: optional(() => [ClockingSkew]),
  output_skew: optional(() => [ClockingSkew]),
  signals: many(() => [ClockingSignal]),
};
export interface ClockingSignals extends Properties<typeof ClockingSignalsSpec> {}
/**
 * `direction input_skew output_skew signals;` in a clocking block (14.3). Both skews are for `input output`;
 * `inout` has none.
 */
export class ClockingSignals extends Item {
  static override SPEC = ClockingSignalsSpec;
  static override SINCE: Availability | null = sv();
}

const ClockingSignalSpec = {
  name: one(() => [Identifier]),
  value: optional(() => [Expression]),
};
export interface ClockingSignal extends Properties<typeof ClockingSignalSpec> {}
/** `name = value` in a clocking block: a signal, or with `value` an expression it stands for (14.5). */
export class ClockingSignal extends SyntaxNode {
  static override SPEC = ClockingSignalSpec;
  static override SINCE: Availability | null = sv();
}

const ClockingSkewSpec = {
  edge: optionalChoice(...EDGES),
  delay: optional(() => [DelayControl]),
};
export interface ClockingSkew extends Properties<typeof ClockingSkewSpec> {}
/**
 * `edge #delay`: when a clocking block samples or drives, relative to its clock (14.4). `#1step` is the time
 * literal `1step`.
 */
export class ClockingSkew extends SyntaxNode {
  static override SPEC = ClockingSkewSpec;
  static override SINCE: Availability | null = sv();
}

const DefaultClockingSpec = {
  name: one(() => [Identifier]),
};
export interface DefaultClocking extends Properties<typeof DefaultClockingSpec> {}
/** `default clocking name;`: the clocking block a scope's assertions and cycle delays use (14.12). */
export class DefaultClocking extends Item {
  static override SPEC = DefaultClockingSpec;
  static override SINCE: Availability | null = sv();
}

const DefaultDisableSpec = {
  condition: one(() => [Expression]),
};
export interface DefaultDisable extends Properties<typeof DefaultDisableSpec> {}
/** `default disable iff condition;`: the reset of a scope's concurrent assertions (16.15). */
export class DefaultDisable extends Item {
  static override SPEC = DefaultDisableSpec;
  static override SINCE: Availability | null = sv(2009);
}

// === Coverage (19) ===

const CovergroupDeclarationSpec = {
  extends: flag(),
  name: one(() => [Identifier]),
  ports: many(() => [TfPort]),
  clock: optional(() => [EventControl, BlockEventControl]),
  sample: optional(() => [SampleFunction]),
  items: many(() => [CoverageOption, Coverpoint, CoverCross, AttributedItem, Directive, Comment]),
  labeled: flag(),
};
export interface CovergroupDeclaration extends Properties<typeof CovergroupDeclarationSpec> {}
/**
 * `covergroup name(ports) @(clock); items endgroup`, or sampled `with function sample(ports)` (19.3, 19.8.1).
 * Its items are options, coverpoints and crosses. `labeled` repeats the name after `endgroup`. In a derived class,
 * `covergroup extends name` adds to its base class's covergroup of that name (19.4.1). A clock may be `@@(events)`,
 * of blocks' starts and ends.
 */
export class CovergroupDeclaration extends Item {
  static override SPEC = CovergroupDeclarationSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { extends: [[true, sv(2023)]] };
  override check(): string[] {
    if (this.clock !== null && this.sample !== null) return ["a CovergroupDeclaration has a clock or a sample, not both"];
    if (this.extends === true && this.ports.length > 0) return ["an extends CovergroupDeclaration has no ports"];
    return [];
  }
}

const SampleFunctionSpec = {
  ports: many(() => [TfPort]),
};
export interface SampleFunction extends Properties<typeof SampleFunctionSpec> {}
/** `with function sample(ports)`: a covergroup sampled by calling `sample` with these arguments (19.8.1). */
export class SampleFunction extends SyntaxNode {
  static override SPEC = SampleFunctionSpec;
  static override SINCE: Availability | null = sv(2009);
}

const CoverageOptionSpec = {
  target: one(() => [Expression]),
  value: one(() => [Expression]),
};
export interface CoverageOption extends Properties<typeof CoverageOptionSpec> {}
/** `option.name = value;` or `type_option.name = value;`, in a covergroup, a coverpoint or a cross (19.7). */
export class CoverageOption extends Item {
  static override SPEC = CoverageOptionSpec;
  static override SINCE: Availability | null = sv();
}

const CoverpointSpec = {
  label: optional(() => [Identifier]),
  type: optional(() => [DataType]),
  expression: one(() => [Expression]),
  condition: optional(() => [Expression]),
  items: many(() => [CoverageBins, CoverageOption, AttributedItem, Directive, Comment]),
};
export interface Coverpoint extends Properties<typeof CoverpointSpec> {}
/**
 * `type label: coverpoint expression iff (condition) { items }`: the values of an expression a covergroup
 * counts, in its bins (19.5); a labeled coverpoint may give the type its values have. Without items, it ends with
 * `;`.
 */
export class Coverpoint extends Item {
  static override SPEC = CoverpointSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { type: [[true, sv(2012)]] };
  override check(): string[] {
    return this.type !== null && this.label === null ? ["a Coverpoint with a type has a label"] : [];
  }
}

const CoverageBinsSpec = {
  wildcard: flag(),
  keyword: choice(...BINS_KEYWORDS),
  name: one(() => [Identifier]),
  array: flag(),
  size: optional(() => [Expression]),
  initializer: one(() => [BinsValues, BinsTransitions, BinsDefault, BinsExpression]),
  condition: optional(() => [Expression]),
};
export interface CoverageBins extends Properties<typeof CoverageBinsSpec> {}
/**
 * `wildcard keyword name[size] = initializer iff (condition);`: a bin of a coverpoint, `bins`, `illegal_bins` or
 * `ignore_bins` (19.5). With `array`, one bin per value, or `size` bins; `wildcard` lets `x`, `z` and `?` match any
 * bit.
 */
export class CoverageBins extends Item {
  static override SPEC = CoverageBinsSpec;
  static override SINCE: Availability | null = sv();
  override check(): string[] {
    return this.size !== null && this.array !== true ? ["a CoverageBins with a size is an array"] : [];
  }
}

const BinsValuesSpec = {
  values: many(() => [Expression, Range]),
  filter: optional(() => [Expression]),
};
export interface BinsValues extends Properties<typeof BinsValuesSpec> {}
/** `{ values } with (filter)`: the values a bin counts, which `filter` may thin out (19.5.1). */
export class BinsValues extends SyntaxNode {
  static override SPEC = BinsValuesSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { filter: [[true, sv(2012)]] };
}

const BinsTransitionsSpec = {
  sequences: many(() => [TransitionSequence]),
};
export interface BinsTransitions extends Properties<typeof BinsTransitionsSpec> {}
/** `(sequence), (sequence)`: the sequences of values a bin counts (19.5.2). */
export class BinsTransitions extends SyntaxNode {
  static override SPEC = BinsTransitionsSpec;
  static override SINCE: Availability | null = sv();
}

const TransitionSequenceSpec = {
  steps: many(() => [TransitionStep]),
};
export interface TransitionSequence extends Properties<typeof TransitionSequenceSpec> {}
/** `steps => steps => ...`: a sequence of values in a transition bin (19.5.2). */
export class TransitionSequence extends SyntaxNode {
  static override SPEC = TransitionSequenceSpec;
  static override SINCE: Availability | null = sv();
}

const TransitionStepSpec = {
  values: many(() => [Expression, Range]),
  operator: optionalChoice(...REPETITION_OPERATORS),
  count: optional(() => [Expression, CycleRange]),
};
export interface TransitionStep extends Properties<typeof TransitionStepSpec> {}
/** `values[*count]`: one of the values, repeated `count` times consecutively (`*`), or not (`->`, `=`) (19.5.2). */
export class TransitionStep extends SyntaxNode {
  static override SPEC = TransitionStepSpec;
  static override SINCE: Availability | null = sv();
  override check(): string[] {
    return (this.operator === null) !== (this.count === null)
      ? ["a TransitionStep has both an operator and a count, or neither"] : [];
  }
}

const BinsDefaultSpec = {
  sequence: flag(),
};
export interface BinsDefault extends Properties<typeof BinsDefaultSpec> {}
/** `default`: the values no other bin counts; with `sequence`, the transitions (19.5.1). */
export class BinsDefault extends SyntaxNode {
  static override SPEC = BinsDefaultSpec;
  static override SINCE: Availability | null = sv();
}

const BinsExpressionSpec = {
  expression: one(() => [Expression]),
  filter: optional(() => [Expression]),
};
export interface BinsExpression extends Properties<typeof BinsExpressionSpec> {}
/** `expression with (filter)`: the values an expression gives, or a coverpoint's (`cp with (item > 1)`) (19.5.1). */
export class BinsExpression extends SyntaxNode {
  static override SPEC = BinsExpressionSpec;
  static override SINCE: Availability | null = sv(2012);
}

const CoverCrossSpec = {
  label: optional(() => [Identifier]),
  items: many(() => [Expression]),
  condition: optional(() => [Expression]),
  body: many(() => [BinsSelection, CoverageOption, FunctionDeclaration, AttributedItem, Directive, Comment]),
};
export interface CoverCross extends Properties<typeof CoverCrossSpec> {}
/**
 * `label: cross items iff (condition) { body }`: the combinations of coverpoints' bins a covergroup counts
 * (19.6). Without a body, it ends with `;`.
 */
export class CoverCross extends Item {
  static override SPEC = CoverCrossSpec;
  static override SINCE: Availability | null = sv();
}

const BinsSelectionSpec = {
  keyword: choice(...BINS_KEYWORDS),
  name: one(() => [Identifier]),
  select: one(() => [BinsSelect, Expression]),
  condition: optional(() => [Expression]),
};
export interface BinsSelection extends Properties<typeof BinsSelectionSpec> {}
/** `keyword name = select iff (condition);`: a bin of a cross (19.6.1). */
export class BinsSelection extends Item {
  static override SPEC = BinsSelectionSpec;
  static override SINCE: Availability | null = sv();
}

const BinsOfSpec = {
  target: one(() => [Expression]),
  intersect: many(() => [Expression, Range]),
};
export interface BinsOf extends Properties<typeof BinsOfSpec> {}
/**
 * `binsof(target) intersect { values }`: the bins of a coverpoint, or one bin of it (`cp.low`), whose values
 * intersect `values` (19.6.1).
 */
export class BinsOf extends BinsSelect {
  static override SPEC = BinsOfSpec;
  static override SINCE: Availability | null = sv();
}

const BinaryBinsSelectSpec = {
  left: one(() => [BinsSelect, Expression]),
  operator: choice(...BINS_SELECT_OPERATORS),
  right: one(() => [BinsSelect, Expression]),
};
export interface BinaryBinsSelect extends Properties<typeof BinaryBinsSelectSpec> {}
/** `left && right` or `left || right` (19.6.1); slang groups both alike, to the left. */
export class BinaryBinsSelect extends BinsSelect {
  static override SPEC = BinaryBinsSelectSpec;
  static override SINCE: Availability | null = sv();
}

const NotBinsSelectSpec = {
  operand: one(() => [BinsSelect, Expression]),
};
export interface NotBinsSelect extends Properties<typeof NotBinsSelectSpec> {}
/** `!operand` (19.6.1). */
export class NotBinsSelect extends BinsSelect {
  static override SPEC = NotBinsSelectSpec;
  static override SINCE: Availability | null = sv();
}

const ParenthesizedBinsSelectSpec = {
  select: one(() => [BinsSelect, Expression]),
};
export interface ParenthesizedBinsSelect extends Properties<typeof ParenthesizedBinsSelectSpec> {}
/** `(select)` (19.6.1). */
export class ParenthesizedBinsSelect extends BinsSelect {
  static override SPEC = ParenthesizedBinsSelectSpec;
  static override SINCE: Availability | null = sv();
}

const MatchesBinsSelectSpec = {
  select: one(() => [FilteredBinsSelect, Expression]),
  count: one(() => [Expression]),
};
export interface MatchesBinsSelect extends Properties<typeof MatchesBinsSelectSpec> {}
/**
 * `select matches count`: the combinations a cross's name, or a filtered select, gives that `count` of its bins'
 * tuples match (19.6.1.2).
 */
export class MatchesBinsSelect extends BinsSelect {
  static override SPEC = MatchesBinsSelectSpec;
  static override SINCE: Availability | null = sv(2012);
}

const FilteredBinsSelectSpec = {
  select: one(() => [BinsSelect, Expression]),
  filter: one(() => [Expression]),
};
export interface FilteredBinsSelect extends Properties<typeof FilteredBinsSelectSpec> {}
/** `select with (filter)`: the combinations for which `filter` holds (19.6.1.2). */
export class FilteredBinsSelect extends BinsSelect {
  static override SPEC = FilteredBinsSelectSpec;
  static override SINCE: Availability | null = sv(2012);
}

// === Timing controls (9.4) ===

const DelayControlSpec = {
  value: one(() => [Expression]),
  fall: optional(() => [Expression]),
  turnoff: optional(() => [Expression]),
};
export interface DelayControl extends Properties<typeof DelayControlSpec> {}
/**
 * `#value`: a number, a time literal, a name or a parenthesized expression (9.4.1); or, of a net, a continuous
 * assignment or a gate, `#(value, fall, turnoff)`, its rise, fall and turn-off delays (28.16).
 */
export class DelayControl extends TimingControl {
  static override SPEC = DelayControlSpec;
  override check(): string[] {
    return this.turnoff !== null && this.fall === null ? ["a DelayControl with a turnoff has a fall"] : [];
  }
}

const CycleDelaySpec = {
  value: one(() => [Expression]),
};
export interface CycleDelay extends Properties<typeof CycleDelaySpec> {}
/** `##value`: a number of ticks of the default clocking block (14.11). */
export class CycleDelay extends TimingControl {
  static override SPEC = CycleDelaySpec;
  static override SINCE: Availability | null = sv();
}

const RepeatEventControlSpec = {
  count: one(() => [Expression]),
  event: one(() => [EventControl]),
};
export interface RepeatEventControl extends Properties<typeof RepeatEventControlSpec> {}
/** `repeat (count) @(events)`, an intra-assignment event control that waits for `count` of them (9.4.5). */
export class RepeatEventControl extends TimingControl {
  static override SPEC = RepeatEventControlSpec;
}

const BlockEventControlSpec = {
  events: many(() => [BlockEvent]),
};
export interface BlockEventControl extends Properties<typeof BlockEventControlSpec> {}
/** `@@(events)`, joined by `or`: a covergroup's clock, the starts and ends of blocks (19.3). */
export class BlockEventControl extends TimingControl {
  static override SPEC = BlockEventControlSpec;
  static override SINCE: Availability | null = sv();
}

const BlockEventSpec = {
  keyword: choice(...BLOCK_EVENT_KEYWORDS),
  name: one(() => [Expression]),
};
export interface BlockEvent extends Properties<typeof BlockEventSpec> {}
/** `begin name` or `end name`: the start or the end of a block, a function or a task (19.3). */
export class BlockEvent extends SyntaxNode {
  static override SPEC = BlockEventSpec;
  static override SINCE: Availability | null = sv();
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
  attributes: many(() => [AttributeInstance]),
  operand: one(() => [Expression]),
};
export interface UnaryExpression extends Properties<typeof UnaryExpressionSpec> {}
/** `operator operand`, including the reductions `&`, `~&`, `|`, `~|`, `^`, `~^` (11.4). */
export class UnaryExpression extends Expression {
  static override SPEC = UnaryExpressionSpec;
  static override FEATURES: Features = { attributes: [[true, verilog(2001)]] };
}

const IncrementExpressionSpec = {
  operator: choice(...INCREMENT_OPERATORS),
  postfix: flag(),
  operand: one(() => [Expression]),
  attributes: many(() => [AttributeInstance]),
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
  attributes: many(() => [AttributeInstance]),
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
    attributes: [[true, verilog(2001)]],
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
  attributes: many(() => [AttributeInstance]),
  consequence: one(() => [Expression]),
  alternative: one(() => [Expression]),
};
export interface ConditionalExpression extends Properties<typeof ConditionalExpressionSpec> {}
/** `condition ? consequence : alternative` (11.4.11). */
export class ConditionalExpression extends Expression {
  static override SPEC = ConditionalExpressionSpec;
  static override FEATURES: Features = { attributes: [[true, verilog(2001)]] };
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
  operator: optionalChoice(...TOLERANCE_OPERATORS),
  right: one(() => [Expression]),
};
export interface ValueRange extends Properties<typeof ValueRangeSpec> {}
/**
 * `[left:right]` in a set (11.4.13), or with an `operator` a tolerance range: `[center +/- width]` or
 * `[center +%- percent]`.
 */
export class ValueRange extends Range {
  static override SPEC = ValueRangeSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { operator: [[true, sv(2023)]] };
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
  count: optional(() => [Expression]),
  items: many(() => [Expression, PatternItem]),
};
export interface AssignmentPattern extends Properties<typeof AssignmentPatternSpec> {}
/**
 * `type'{items}` or `'{items}`: positional values, or `key: value` items, or with a `count` the positional values
 * repeated (`'{2{a, b}}`) (10.9).
 */
export class AssignmentPattern extends Expression {
  static override SPEC = AssignmentPatternSpec;
  static override SINCE: Availability | null = sv();
  override check(): string[] {
    if (this.count !== null && this.items.some((i) => i instanceof PatternItem)) {
      return ["a repeated AssignmentPattern has positional items only"];
    }
    return [];
  }
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
  defaulted: flag(),
};
export interface NewExpression extends Properties<typeof NewExpressionSpec> {}
/**
 * `new(arguments)`: a new object of the class the place it is assigned to has, or with `scope` of that class
 * (`c#(8)::new`) or the base class's constructor (`super.new`) (8.7, 8.15). `new` without arguments is written
 * without parentheses; `defaulted`, `super.new(default)` passes the constructor's own arguments (8.15).
 */
export class NewExpression extends Expression {
  static override SPEC = NewExpressionSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { defaulted: [[true, sv(2023)]] };
  override check(): string[] {
    if (this.defaulted === true && (!(this.scope instanceof SuperExpression) || this.arguments.length > 0)) {
      return ["a defaulted NewExpression is super.new(default)"];
    }
    return [];
  }
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

const RandomizeWithExpressionSpec = {
  call: one(() => [Expression]),
  restricted: flag(),
  variables: many(() => [Identifier]),
  items: many(() => [Constraint, Directive, Comment]),
};
export interface RandomizeWithExpression extends Properties<typeof RandomizeWithExpressionSpec> {}
/**
 * `call with (variables) { constraints }`: a call of `randomize` (an object's, `std::randomize` or the class's own)
 * with inline constraints (18.7). With `restricted`, the names `variables` lists (perhaps none) are the object's, and
 * other names are looked up where the call is (18.7.1).
 */
export class RandomizeWithExpression extends Expression {
  static override SPEC = RandomizeWithExpressionSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { restricted: [[true, sv(2012)]] };
}

const ArrayMethodWithExpressionSpec = {
  call: one(() => [Expression]),
  expression: one(() => [Expression]),
};
export interface ArrayMethodWithExpression extends Properties<typeof ArrayMethodWithExpressionSpec> {}
/**
 * `call with (expression)`: an array manipulation method whose elements are `item`, or what its argument names,
 * in `expression` (7.12).
 */
export class ArrayMethodWithExpression extends Expression {
  static override SPEC = ArrayMethodWithExpressionSpec;
  static override SINCE: Availability | null = sv();
}

const CallExpressionSpec = {
  callee: one(() => [Expression]),
  attributes: many(() => [AttributeInstance]),
  arguments: many(() => [Expression, Connection, Property]),
};
export interface CallExpression extends Properties<typeof CallExpressionSpec> {}
/**
 * `callee(arguments)`: a function or method call (13.5); arguments are ordered expressions or named
 * `NamedConnection`s. In an instance of a property or a sequence, an argument may be a property or a sequence
 * (16.8).
 */
export class CallExpression extends Expression {
  static override SPEC = CallExpressionSpec;
  static override FEATURES: Features = { attributes: [[true, verilog(2001)]] };
}

const SystemCallSpec = {
  name: text(),
  attributes: many(() => [AttributeInstance]),
  arguments: many(() => [Expression, DataType, EmptyArgument]),
};
export interface SystemCall extends Properties<typeof SystemCallSpec> {}
/**
 * `$name(arguments)`: a system task or function call, such as `$display` or `$clog2` (20). An argument may be a
 * data type, as `$bits` takes.
 */
export class SystemCall extends Expression {
  static override SPEC = SystemCallSpec;
  static override FEATURES: Features = { attributes: [[true, verilog(2001)]] };
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

const TaggedExpressionSpec = {
  member: one(() => [Identifier]),
  value: optional(() => [Expression]),
};
export interface TaggedExpression extends Properties<typeof TaggedExpressionSpec> {}
/** `tagged member value`: a tagged union's value, of one of its members (11.9). */
export class TaggedExpression extends Expression {
  static override SPEC = TaggedExpressionSpec;
  static override SINCE: Availability | null = sv();
}

const MatchesExpressionSpec = {
  value: one(() => [Expression]),
  pattern: one(() => [Pattern, Expression]),
};
export interface MatchesExpression extends Properties<typeof MatchesExpressionSpec> {}
/**
 * `value matches pattern`, a condition of an `if` or a `?:` that binds the pattern's variables there (12.6.2,
 * 12.6.3).
 */
export class MatchesExpression extends Expression {
  static override SPEC = MatchesExpressionSpec;
  static override SINCE: Availability | null = sv();
}

const PredicateExpressionSpec = {
  conditions: many(() => [Expression]),
};
export interface PredicateExpression extends Properties<typeof PredicateExpressionSpec> {}
/** `condition &&& condition ...`, conditions of an `if` or a `?:` that all hold, in order (12.6.2). */
export class PredicateExpression extends Expression {
  static override SPEC = PredicateExpressionSpec;
  static override SINCE: Availability | null = sv();
  override check(): string[] {
    return this.conditions.length < 2 ? ["a PredicateExpression has two conditions or more"] : [];
  }
}

const VariablePatternSpec = {
  name: one(() => [Identifier]),
};
export interface VariablePattern extends Properties<typeof VariablePatternSpec> {}
/** `.name`: any value, bound to a variable of that name (12.6). */
export class VariablePattern extends Pattern {
  static override SPEC = VariablePatternSpec;
  static override SINCE: Availability | null = sv();
}

const WildcardPatternSpec = {};
export interface WildcardPattern extends Properties<typeof WildcardPatternSpec> {}
/** `.*`: any value (12.6). */
export class WildcardPattern extends Pattern {
  static override SPEC = WildcardPatternSpec;
  static override SINCE: Availability | null = sv();
}

const TaggedPatternSpec = {
  member: one(() => [Identifier]),
  pattern: optional(() => [Pattern, Expression]),
};
export interface TaggedPattern extends Properties<typeof TaggedPatternSpec> {}
/** `tagged member pattern`: a tagged union's value of that member, which matches the pattern (12.6). */
export class TaggedPattern extends Pattern {
  static override SPEC = TaggedPatternSpec;
  static override SINCE: Availability | null = sv();
}

const StructurePatternSpec = {
  items: many(() => [Pattern, Expression, PatternMember]),
};
export interface StructurePattern extends Properties<typeof StructurePatternSpec> {}
/** `'{patterns}` or `'{member: pattern, ...}`: a structure's members, in order or by name (12.6). */
export class StructurePattern extends Pattern {
  static override SPEC = StructurePatternSpec;
  static override SINCE: Availability | null = sv();
  override check(): string[] {
    const named = this.items.map((i) => i instanceof PatternMember);
    return named.some((n) => n) && !named.every((n) => n) ? ["a StructurePattern's members are in order or by name, not both"] : [];
  }
}

const PatternMemberSpec = {
  name: one(() => [Identifier]),
  pattern: one(() => [Pattern, Expression]),
};
export interface PatternMember extends Properties<typeof PatternMemberSpec> {}
/** `member: pattern` in a structure pattern (12.6). */
export class PatternMember extends SyntaxNode {
  static override SPEC = PatternMemberSpec;
  static override SINCE: Availability | null = sv();
}

const StreamingConcatenationSpec = {
  operator: choice(...STREAM_OPERATORS),
  slice: optional(() => [Expression, DataType]),
  items: many(() => [StreamItem]),
};
export interface StreamingConcatenation extends Properties<typeof StreamingConcatenationSpec> {}
/**
 * `{>> slice {items}}` or `{<< slice {items}}`: items packed in a stream, in slices of `slice` bits or of a
 * type's size, from the left or the right (11.4.14).
 */
export class StreamingConcatenation extends Expression {
  static override SPEC = StreamingConcatenationSpec;
  static override SINCE: Availability | null = sv();
}

const StreamItemSpec = {
  expression: one(() => [Expression]),
  left: optional(() => [Expression]),
  operator: optionalChoice(...SELECT_OPERATORS),
  right: optional(() => [Expression]),
};
export interface StreamItem extends Properties<typeof StreamItemSpec> {}
/**
 * `expression with [left operator right]`, an item of a streaming concatenation, of an array's elements `left`,
 * `left:right`, `left+:right` or `left-:right` when it has a `with` (11.4.14.4).
 */
export class StreamItem extends SyntaxNode {
  static override SPEC = StreamItemSpec;
  static override SINCE: Availability | null = sv();
  static override FEATURES: Features = { left: [[true, sv(2009)]] };
  override check(): string[] {
    if ((this.operator === null) !== (this.right === null) || (this.left === null && this.operator !== null)) {
      return ["a StreamItem's `with` has a left, and an operator and a right, or neither"];
    }
    return [];
  }
}

const MinTypMaxExpressionSpec = {
  min: one(() => [Expression]),
  typ: one(() => [Expression]),
  max: one(() => [Expression]),
};
export interface MinTypMaxExpression extends Properties<typeof MinTypMaxExpressionSpec> {}
/** `min:typ:max`, a minimum, typical and maximum value, as delays have (11.11). */
export class MinTypMaxExpression extends Expression {
  static override SPEC = MinTypMaxExpressionSpec;
}

const EmptyArgumentSpec = {};
export interface EmptyArgument extends Properties<typeof EmptyArgumentSpec> {}
/**
 * A port connection, an argument or a `foreach` loop's variable left out: `u i(a, , b)`, `f(a, , b)`,
 * `$display(a,, b)`, `foreach (q[, j])` (23.3.2.2, 13.5, 12.7.3).
 */
export class EmptyArgument extends Connection {
  static override SPEC = EmptyArgumentSpec;
}

const RootExpressionSpec = {};
export interface RootExpression extends Properties<typeof RootExpressionSpec> {}
/** `$root`, the top of the design's hierarchy, where a hierarchical name starts (23.6). */
export class RootExpression extends Expression {
  static override SPEC = RootExpressionSpec;
  static override SINCE: Availability | null = sv();
}

const EmptyQueueSpec = {};
export interface EmptyQueue extends Properties<typeof EmptyQueueSpec> {}
/** `{}`, a queue or a dynamic array with no elements (7.10). */
export class EmptyQueue extends Expression {
  static override SPEC = EmptyQueueSpec;
  static override SINCE: Availability | null = sv();
}

const InterfaceTypeNameSpec = {
  interface: one(() => [Identifier]),
  name: one(() => [Identifier]),
};
export interface InterfaceTypeName extends Properties<typeof InterfaceTypeNameSpec> {}
/** `interface.name`: a type an interface port's interface declares, as `typedef` names it (6.18). */
export class InterfaceTypeName extends Name {
  static override SPEC = InterfaceTypeNameSpec;
  static override SINCE: Availability | null = sv();
}

const InterfaceMethodNameSpec = {
  port: one(() => [Identifier]),
  name: one(() => [Identifier]),
};
export interface InterfaceMethodName extends Properties<typeof InterfaceMethodNameSpec> {}
/**
 * `port.name`: in a module, the task or function an interface's `extern` prototype declares, defined for the
 * module's interface port `port` (25.7.4).
 */
export class InterfaceMethodName extends Name {
  static override SPEC = InterfaceMethodNameSpec;
  static override SINCE: Availability | null = sv();
}

const UnitNameSpec = {};
export interface UnitName extends Properties<typeof UnitNameSpec> {}
/** `$unit`, the compilation unit, as a scope: `$unit::name` (26.3). */
export class UnitName extends Name {
  static override SPEC = UnitNameSpec;
  static override SINCE: Availability | null = sv();
}

const TypeReferenceSpec = {
  operand: one(() => [Expression, DataType]),
};
export interface TypeReference extends Properties<typeof TypeReferenceSpec> {}
/** `type(operand)`: the type of an expression, or a type itself (6.23). */
export class TypeReference extends DataType {
  static override SPEC = TypeReferenceSpec;
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
  name: optional(() => [Identifier]),
  condition: optional(() => [Expression]),
  items: many(() => [Item, Statement, Constraint, Directive, Comment]),
  branches: many(() => [ElsifDirective]),
  alternative: many(() => [Item, Statement, Constraint, Directive, Comment]),
  has_else: flag(),
};
export interface IfdefDirective extends Properties<typeof IfdefDirectiveSpec> {}
/**
 * `` `ifdef name items `elsif name items `else items `endif ``, or `` `ifndef `` when `negated`, as a tree of its
 * branches (22.6). Branches hold what their place lists: items, statements or constraints. A branch the reading did
 * not take ends with its text as written, a `DisabledText`. In place of a name, a `condition` combines macros'
 * names with `!`, `&&`, `||`, `->`, `<->` and parentheses: `` `ifdef (A && !B) ``.
 */
export class IfdefDirective extends Directive {
  static override SPEC = IfdefDirectiveSpec;
  static override FEATURES: Features = { condition: [[true, sv(2023)]] };
  override check(): string[] {
    return conditionProblems(this);
  }
}

const ElsifDirectiveSpec = {
  name: optional(() => [Identifier]),
  condition: optional(() => [Expression]),
  items: many(() => [Item, Statement, Constraint, Directive, Comment]),
};
export interface ElsifDirective extends Properties<typeof ElsifDirectiveSpec> {}
/** `` `elsif name items `` or `` `elsif (condition) items ``, a branch of an `IfdefDirective` (22.6). */
export class ElsifDirective extends Directive {
  static override SPEC = ElsifDirectiveSpec;
  static override SINCE: Availability | null = verilog(2001);
  static override FEATURES: Features = { condition: [[true, sv(2023)]] };
  override check(): string[] {
    return conditionProblems(this);
  }
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

const UDP_LEVELS = new Set(["0", "1", "x", "X", "?", "b", "B"]);
const UDP_INPUTS = new Set([...UDP_LEVELS, "r", "R", "f", "F", "p", "P", "n", "N", "*"]);

/** An `extern` design unit is a header alone, and `.*` is a header's only port. */
function unitProblems(unit: ModuleDeclaration | InterfaceDeclaration | ProgramDeclaration): string[] {
  const kind = unit.kind().KIND;
  if (unit.extern === true && (unit.items.length > 0 || unit.labeled === true)) return [`an extern ${kind} has no items`];
  if (unit.ports.some((p) => p instanceof WildcardPort) && unit.ports.length > 1) return [`a ${kind}'s .* is its only port`];
  return [];
}

/** A directive has a name or a condition, and a condition only macros' names and `!`, `&&`, `||`, `->`, `<->`. */
function conditionProblems(directive: IfdefDirective | ElsifDirective): string[] {
  const kind = directive.kind().KIND;
  if ((directive.name === null) === (directive.condition === null)) return [`an ${kind} has a name or a condition`];
  if (directive.condition !== null && !(directive.condition instanceof ParenthesizedExpression)) {
    return [`an ${kind}'s condition is in parentheses`];
  }
  const nodes: unknown[] = directive.condition !== null ? [directive.condition] : [];
  while (nodes.length > 0) {
    const node = nodes.pop();
    if (node instanceof ParenthesizedExpression) {
      nodes.push(node.expression);
    } else if (node instanceof UnaryExpression && node.operator === "!" && node.attributes.length === 0) {
      nodes.push(node.operand);
    } else if (node instanceof BinaryExpression && ["&&", "||", "->", "<->"].includes(node.operator as string)
      && node.attributes.length === 0) {
      nodes.push(node.left, node.right);
    } else if (!(node instanceof NameExpression && node.name instanceof Identifier)) {
      return [`an ${kind}'s condition has macros' names, !, &&, ||, -> and <-> only`];
    }
  }
  return [];
}

// --- The language ---

export const KINDS = [
  Comment, Identifier, ScopedName, ParameterizedName, AttributeInstance, AttributeSpec, AttributedItem,
  AttributedStatement, AttributedPort, SourceText, ModuleDeclaration, InterfaceDeclaration, ProgramDeclaration,
  CheckerDeclaration, PackageDeclaration, ConfigDeclaration, ConfigCell, ConfigRule, ConfigLiblist, ConfigUse,
  AnsiPort, InterfacePort, InterfacePortDeclaration, PortReference, PortConcatenation, ExplicitPort, WildcardPort,
  EmptyPort, ExplicitAnsiPort, PortDeclaration, ParameterDeclaration, ParamAssignment, TypeParameterDeclaration,
  TypeAssignment, IntegerVectorType, IntegerAtomType, NonIntegerType, KeywordType, NamedType, VirtualInterfaceType,
  ImplicitType, StructType, StructMember, EnumType, EnumMember, RangeDimension, SizeDimension, UnsizedDimension,
  AssociativeDimension, QueueDimension, NetDeclaration, DriveStrength, ChargeStrength, VariableDeclaration,
  VariableDeclarator, ForwardTypedefDeclaration, TypedefDeclaration, EmptyItem, DpiImport, DpiExport, BindDirective,
  ElaborationTask, GenvarDeclaration, ImportDeclaration, ExportDeclaration, ImportItem, NetTypeDeclaration, NetAlias,
  DefParam, DefParamAssignment, TimeUnitsDeclaration, ModportDeclaration, ModportItem, ModportPort, ModportSubroutine,
  ModportClocking, ContinuousAssign, AlwaysConstruct, InitialConstruct, FinalConstruct, FunctionDeclaration,
  TaskDeclaration, TfPort, ClassDeclaration, GenerateRegion, GenerateFor, GenerateIf, GenerateCase, GenerateBlock,
  ModuleInstantiation, Instance, AttributedConnection, NamedConnection, WildcardConnection, GateInstantiation,
  GateInstance, PullStrength, UdpDeclaration, UdpPort, UdpInitial, UdpEntry, SpecifyBlock, SpecparamDeclaration,
  SpecparamAssignment, PathDeclaration, TimingCheck, TimingCheckEvent, PulseStyleDeclaration, AssignmentStatement,
  ExpressionStatement, NullStatement, SeqBlock, ParBlock, IfStatement, CaseStatement, CaseItem, PatternCaseItem,
  ForStatement, WhileStatement, DoWhileStatement, RepeatStatement, ForeverStatement, ForeachStatement, BreakStatement,
  ContinueStatement, ReturnStatement, TimedStatement, WaitStatement, EventTrigger, DisableStatement, ForceStatement,
  ReleaseStatement, CheckerStatement, WaitForkStatement, WaitOrderStatement, RandSequenceStatement, Production,
  ProductionRule, ProductionCall, ProductionCode, ProductionIf, ProductionRepeat, ProductionCase, ProductionCaseItem,
  ImmediateAssertion, DelayControl, RepeatEventControl, BlockEventControl, BlockEvent, EventControl, EventExpression,
  NameExpression, MemberExpression, IndexExpression, RangeSelect, IntegerLiteral, RealLiteral, TimeLiteral,
  UnbasedUnsizedLiteral, StringLiteral, UnaryExpression, IncrementExpression, BinaryExpression, AssignmentExpression,
  ConditionalExpression, InsideExpression, ValueRange, Concatenation, Replication, AssignmentPattern, PatternItem,
  CallExpression, SystemCall, CastExpression, ParenthesizedExpression, MacroUsage, DollarExpression, TaggedExpression,
  MatchesExpression, PredicateExpression, VariablePattern, WildcardPattern, TaggedPattern, StructurePattern,
  PatternMember, StreamingConcatenation, StreamItem, MinTypMaxExpression, EmptyArgument, RootExpression, EmptyQueue,
  InterfaceTypeName, InterfaceMethodName, UnitName, TypeReference, NullLiteral, ThisExpression, SuperExpression, NewExpression,
  NewCopyExpression, NewArrayExpression, RandomizeWithExpression, ArrayMethodWithExpression, DistExpression, DistItem,
  LocalName, ConstraintDeclaration, ConstraintPrototype, ConstraintBlock, ExpressionConstraint, ImplicationConstraint,
  ConditionalConstraint, ForeachConstraint, SolveBeforeConstraint, DisableSoftConstraint, UniqueConstraint,
  RandCaseStatement, RandCaseItem, LabeledStatement, ConcurrentAssertion, ExpectStatement, AssertionItem,
  PropertySpec, PropertyDeclaration, SequenceDeclaration, LetDeclaration, AssertionPort, DelaySequence, DelayStep,
  CycleRange, RepetitionSequence, BinarySequence, ParenthesizedSequence, FirstMatchSequence, ClockedSequence,
  ImplicationProperty, BinaryProperty, UnaryProperty, StrengthProperty, AbortProperty, ConditionalProperty,
  CaseProperty, PropertyCaseItem, ParenthesizedProperty, ClockedProperty, ClockingDeclaration, DefaultSkew,
  ClockingSignals, ClockingSignal, ClockingSkew, DefaultClocking, DefaultDisable, CycleDelay, CovergroupDeclaration,
  SampleFunction, CoverageOption, Coverpoint, CoverageBins, BinsValues, BinsTransitions, TransitionSequence,
  TransitionStep, BinsDefault, BinsExpression, CoverCross, BinsSelection, BinsOf, BinaryBinsSelect, NotBinsSelect,
  ParenthesizedBinsSelect, FilteredBinsSelect, MatchesBinsSelect, IncludeDirective, DefineDirective, UndefDirective,
  TimescaleDirective, DefaultNettypeDirective, IfdefDirective, ElsifDirective, DisabledText, OtherDirective,
];

/** The language, whose `Builders` are typed from this module's kinds. */
export const LANGUAGE: Language<typeof Self> = new Language("Verilog", KINDS, {
  base: { [VERILOG]: 1995, [SV]: 2005 },
});
