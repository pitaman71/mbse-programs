"""Syntax: the abstract syntax of Verilog and SystemVerilog, as one tree language (Verilog), organized as IEEE 1800's
grammar is.

The kinds cover SystemVerilog (IEEE 1800-2023)'s design subset and its classes: design units, ports and parameters,
data types, declarations, continuous assignments, procedural blocks and statements, generate constructs, instantiation,
functions and tasks, classes with their properties, methods and objects, constraints and randomization, immediate and
concurrent assertions with their properties and sequences, clocking blocks, covergroups and compiler directives.
Verilog (IEEE 1364) is a family of its own whose standards have fewer of them: each kind and feature records where it
exists in both families (`SINCE`, `FEATURES`), which `Verilog2005`, `SystemVerilog2017`, `SystemVerilog2023` and
`VerilogStandard(year, family)` check.

The tree is abstract where the grammar only spells and concrete where a transpiler needs to see what was written:

- Precedence levels collapse: every binary operator is a `BinaryExpression`. Parentheses written in the source stay,
  as `ParenthesizedExpression`, and printing adds those a hand-built tree needs.
- Names are syntax nodes (category `Name`) wherever they occur, so one traversal finds every use and declaration of a
  name. Expressions refer to them through `NameExpression`; a hierarchical name is `MemberExpression`s.
- Literals keep their spelling: size, base and digits with their underscores (`8'b0000_0100`), and the characters
  between a string's quotes, escapes included.
- Equivalent spellings are normalized: `@*` is `@(*)`, events joined by `,` are joined by `or`, and an event control
  of one name is parenthesized.
- Comments and compiler directives are kept where items and statements are listed; conditional compilation is a tree
  of its branches there.

Property names avoid Python's and TypeScript's reserved words: an `if` has a `consequence` and an `alternative`.
"""

from __future__ import annotations

from typing import Literal as Choice

from ..Framework.Syntax import Availability, Language, SyntaxNode

__all__ = ["LANGUAGE", "KINDS"]

VERILOG, SV = "Verilog", "SystemVerilog"


def sv(year: int = 2005) -> Availability:
    """SystemVerilog from `year` on; not Verilog."""
    return {SV: year}


def verilog(year: int) -> Availability:
    """Verilog from `year` on, and every SystemVerilog."""
    return {VERILOG: year, SV: 2005}


# --- Choices ---

Direction = Choice["input", "output", "inout", "ref"]
NetType = Choice["wire", "tri", "tri0", "tri1", "triand", "trior", "trireg", "wand", "wor", "supply0", "supply1",
                 "uwire", "interconnect"]
Signing = Choice["signed", "unsigned"]
Lifetime = Choice["static", "automatic"]
VectorKeyword = Choice["bit", "logic", "reg"]
AtomKeyword = Choice["byte", "shortint", "int", "longint", "integer", "time"]
RealKeyword = Choice["shortreal", "real", "realtime"]
SimpleKeyword = Choice["string", "chandle", "event", "void", "sequence", "property", "untyped"]
AlwaysKeyword = Choice["always", "always_comb", "always_ff", "always_latch"]
CaseKeyword = Choice["case", "casez", "casex"]
Qualifier = Choice["unique", "unique0", "priority"]
JoinKeyword = Choice["join", "join_any", "join_none"]
Edge = Choice["posedge", "negedge", "edge"]
AssertionKeyword = Choice["assert", "assume", "cover"]
Deferral = Choice["#0", "final"]
ParameterKeyword = Choice["parameter", "localparam"]
UnaryOperator = Choice["+", "-", "!", "~", "&", "~&", "|", "~|", "^", "~^", "^~"]
IncrementOperator = Choice["++", "--"]
BinaryOperator = Choice[
    "**", "*", "/", "%", "+", "-", "<<", ">>", "<<<", ">>>", "<", "<=", ">", ">=", "==", "!=", "===", "!==", "==?",
    "!=?", "&", "^", "^~", "~^", "|", "&&", "||", "->", "<->"]
AssignmentOperator = Choice["=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=", "<<<=", ">>>="]
StatementAssignment = Choice["=", "<=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=", "<<<=", ">>>="]
SelectOperator = Choice[":", "+:", "-:"]
UnbasedValue = Choice["0", "1", "x", "z", "X", "Z"]
ModuleKeyword = Choice["module", "macromodule"]
Visibility = Choice["local", "protected"]
RandomQualifier = Choice["rand", "randc"]
DistOperator = Choice[":=", ":/"]
ConcurrentKeyword = Choice["assert", "assume", "cover", "restrict"]
RepetitionOperator = Choice["*", "->", "="]
SequenceOperator = Choice["and", "or", "intersect", "within", "throughout"]
ImplicationOperator = Choice["|->", "|=>", "#-#", "#=#"]
PropertyOperator = Choice["and", "or", "iff", "implies", "until", "s_until", "until_with", "s_until_with"]
UnaryPropertyOperator = Choice["not", "nexttime", "s_nexttime", "always", "s_always", "eventually", "s_eventually"]
StrengthKeyword = Choice["strong", "weak"]
AbortKeyword = Choice["accept_on", "reject_on", "sync_accept_on", "sync_reject_on"]
PortDirection = Choice["input", "output", "inout"]
ClockingDirection = Choice["input", "output", "inout", "input output"]
ClockingScope = Choice["default", "global"]
StreamOperator = Choice[">>", "<<"]
ToleranceOperator = Choice["+/-", "+%-"]
BinsKeyword = Choice["bins", "illegal_bins", "ignore_bins"]
BinsSelectOperator = Choice["&&", "||"]
PrototypeQualifier = Choice["extern", "pure"]
ForwardKeyword = Choice["enum", "struct", "union", "class", "interface class"]
Strength = Choice["supply0", "strong0", "pull0", "weak0", "highz0", "supply1", "strong1", "pull1", "weak1", "highz1"]
ChargeSize = Choice["small", "medium", "large"]
NetExpansion = Choice["vectored", "scalared"]
TimeUnitKeyword = Choice["timeunit", "timeprecision"]
ImportExport = Choice["import", "export"]
OverrideSpecifier = Choice["initial", "extends"]
ForceKeyword = Choice["force", "assign"]
ReleaseKeyword = Choice["release", "deassign"]
ElaborationTaskName = Choice["$fatal", "$error", "$warning", "$info"]
DpiSpec = Choice["DPI-C", "DPI"]
DpiProperty = Choice["context", "pure"]
SubroutineKeyword = Choice["function", "task"]
UnionQualifier = Choice["tagged", "soft"]
GateKeyword = Choice["and", "nand", "or", "nor", "xor", "xnor", "buf", "not", "bufif0", "bufif1", "notif0",
                     "notif1", "nmos", "pmos", "rnmos", "rpmos", "cmos", "rcmos", "tran", "rtran", "tranif0", "tranif1",
                     "rtranif0", "rtranif1", "pullup", "pulldown"]
UdpDirection = Choice["output", "input"]
DefaultNettype = Choice["wire", "tri", "tri0", "tri1", "triand", "trior", "trireg", "wand", "wor", "uwire", "none"]


# --- Categories ---


class Name(SyntaxNode):
    """A name: what declarations declare and what expressions and types refer to (A.9.3)."""


class Expression(SyntaxNode):
    """An expression (11, A.8)."""


class Literal(Expression):
    """A literal number or string (5.7, 5.9)."""


class DataType(SyntaxNode):
    """A data type (6, A.2.2.1), or the implicit type of a declaration that gives only a signing or dimensions."""


class Dimension(SyntaxNode):
    """A packed or unpacked dimension (7.4, A.2.5)."""


class Item(SyntaxNode):
    """What source text, a design unit, a package or a generate block lists: design units, declarations, assignments,
    procedural blocks, generate constructs and instantiations (A.1)."""


class Port(SyntaxNode):
    """A port in a design unit's header: an ANSI port declaration, an interface port, or a non-ANSI port's name
    (23.2)."""


class Statement(SyntaxNode):
    """A procedural statement (12, A.6.4)."""


class TimingControl(SyntaxNode):
    """A delay or event control (9.4, A.6.5)."""


class Connection(SyntaxNode):
    """A named or wildcard connection of a port, a parameter or an argument (23.3.2, 13.5.4); ordered ones are
    expressions."""


class Range(SyntaxNode):
    """A range of values, in a set (`inside`, a case item) (11.4.13)."""


class Directive(SyntaxNode):
    """A compiler directive (22), where items or statements are listed."""


class Constraint(SyntaxNode):
    """A constraint on random variables, in a constraint block (18.5, A.1.10)."""


class Property(SyntaxNode):
    """A property: what a concurrent assertion checks (16.12, A.2.10). A sequence, and an expression, is a property
    too: a position that holds a property holds a `Property` or an `Expression`."""


class Pattern(SyntaxNode):
    """A pattern that `matches` compares a value with, binding its variables (12.6). An expression is a pattern too, a
    constant one: a position that holds a pattern holds a `Pattern` or an `Expression`."""


class ProductionItem(SyntaxNode):
    """What a `randsequence` production's rule lists: productions to generate, code, and their choices (18.17)."""


class BinsSelect(SyntaxNode):
    """A select expression: which combinations of a cross's bins a bin of the cross holds (19.6.1). A cross's name, or
    an expression, is one too: a position that holds a select holds a `BinsSelect` or an `Expression`."""


class Sequence(Property):
    """A sequence: a pattern of values over clock ticks (16.7, A.2.10). An expression is a sequence of one tick too: a
    position that holds a sequence holds a `Sequence` or an `Expression`."""


# === Lexical conventions (5) ===


class Comment(SyntaxNode):
    """`// text` or, with `block`, `/* text */`. `text` excludes the delimiters. A `trailing` comment ends the line of
    the item before it (5.4)."""

    block: bool
    text: str
    trailing: bool


class Identifier(Name):
    """A simple identifier, letters, digits, `_` and `$` not starting with a digit or `$`, or an escaped one: `\\` and
    printable characters up to white space, which the spelling ends with no space (5.6)."""

    spelling: str

    def check(self) -> list[str]:
        spelling = self.spelling
        if type(spelling) is not str or not spelling:
            return []
        if spelling[0] == "\\":
            if len(spelling) > 1 and all("!" <= ch <= "~" for ch in spelling[1:]):
                return []
        elif spelling[0] not in "0123456789$" and all(ch.isascii() and (ch.isalnum() or ch in "_$") for ch in spelling):
            return []
        return [f"{spelling!r} is not an identifier"]


class ScopedName(Name):
    """`scope::name`: a name in a package or a class, whose scope may be a parameterized class (26.3, 8.23). A name
    of several scopes nests to the right: `p::c::x` is `p::(c::x)`."""

    scope: Identifier | ParameterizedName | UnitName
    name: Name
    SINCE = sv()


class LocalName(Name):
    """`local::name`: in the constraints of `randomize() with`, a name in the scope that calls `randomize`, not in the
    object (18.7.1)."""

    name: Identifier
    SINCE = sv(2009)


class ParameterizedName(Name):
    """`name #(parameters)`: a parameterized class, as a type or as a scope (8.25). Parameters are ordered expressions
    or types, or `NamedConnection`s."""

    name: Identifier
    parameters: list[Expression | DataType | Connection]
    SINCE = sv()


# --- Attributes (5.12) ---


class AttributeInstance(SyntaxNode):
    """`(* specs *)`: attributes for tools, such as `(* keep *)` or `(* full_case, parallel_case *)` (5.12)."""

    specs: list[AttributeSpec]
    SINCE = verilog(2001)


class AttributeSpec(SyntaxNode):
    """`name = value`, or `name` alone, in an attribute instance (5.12)."""

    name: Identifier
    value: Expression | None
    SINCE = verilog(2001)


class AttributedItem(Item):
    """`(* ... *) item`: an item with its attributes (5.12)."""

    attributes: list[AttributeInstance]
    item: Item
    SINCE = verilog(2001)


class AttributedStatement(Statement):
    """`(* ... *) statement`: a statement with its attributes (5.12)."""

    attributes: list[AttributeInstance]
    statement: Statement
    SINCE = verilog(2001)


class AttributedPort(Port):
    """`(* ... *) port`: a port in a design unit's header with its attributes (5.12)."""

    attributes: list[AttributeInstance]
    port: Port
    SINCE = verilog(2001)


# === Source text (A.1) ===


class SourceText(SyntaxNode):
    """A source file: design units, declarations, directives and comments (3.12, A.1.2)."""

    items: list[Item | Directive | Comment]


class ModuleDeclaration(Item):
    """`module name #(parameters) (ports); items endmodule` (23.2). Parameters in the header are listed even when
    empty; ports are `AnsiPort`s or `InterfacePort`s, or for a non-ANSI header `PortReference`s, which `PortDeclaration`
    items declare. `labeled` repeats the name after `endmodule`. An `extern` one is a header alone, which the module
    of its name, with `.*` for its ports, defines (23.2.1)."""

    extern: bool
    keyword: ModuleKeyword
    lifetime: Lifetime | None
    name: Identifier
    imports: list[ImportDeclaration]
    parameters: list[ParameterDeclaration | TypeParameterDeclaration]
    ports: list[Port]
    items: list[Item | Directive | Comment]
    labeled: bool
    FEATURES = {"lifetime": {True: verilog(2001)}, "imports": {True: sv(2009)}, "labeled": {True: sv()},
                "extern": {True: sv()}}

    def check(self) -> list[str]:
        return _unit_problems(self)


class InterfaceDeclaration(Item):
    """`interface name #(parameters) (ports); items endinterface` (25.3), or an `extern` header alone."""

    extern: bool
    lifetime: Lifetime | None
    name: Identifier
    imports: list[ImportDeclaration]
    parameters: list[ParameterDeclaration | TypeParameterDeclaration]
    ports: list[Port]
    items: list[Item | Directive | Comment]
    labeled: bool
    SINCE = sv()
    FEATURES = {"imports": {True: sv(2009)}}

    def check(self) -> list[str]:
        return _unit_problems(self)


class ProgramDeclaration(Item):
    """`program name #(parameters) (ports); items endprogram` (24.3), or an `extern` header alone."""

    extern: bool
    lifetime: Lifetime | None
    name: Identifier
    imports: list[ImportDeclaration]
    parameters: list[ParameterDeclaration | TypeParameterDeclaration]
    ports: list[Port]
    items: list[Item | Directive | Comment]
    labeled: bool
    SINCE = sv()
    FEATURES = {"imports": {True: sv(2009)}}

    def check(self) -> list[str]:
        return _unit_problems(self)


def _unit_problems(unit: ModuleDeclaration | InterfaceDeclaration | ProgramDeclaration) -> list[str]:
    """An `extern` design unit is a header alone, and `.*` is a header's only port."""
    kind = type(unit).__name__
    if unit.extern is True and (unit.items or unit.labeled is True):
        return [f"an extern {kind} has no items"]
    if any(isinstance(p, WildcardPort) for p in unit.ports) and len(unit.ports) > 1:
        return [f"a {kind}'s .* is its only port"]
    return []


class CheckerDeclaration(Item):
    """`checker name(ports); items endchecker`: assertions with their modeling code, instantiated as a module is, or in
    a procedure (17). Its ports are as a property's; its variables may be `rand`, free for formal tools to choose
    (17.7). `labeled` repeats the name after `endchecker`."""

    name: Identifier
    ports: list[AssertionPort]
    items: list[Item | Directive | Comment]
    labeled: bool
    SINCE = sv(2009)


class PackageDeclaration(Item):
    """`package name; items endpackage` (26.2)."""

    lifetime: Lifetime | None
    name: Identifier
    items: list[Item | Directive | Comment]
    labeled: bool
    SINCE = sv()


# === Ports (23.2) ===


class AnsiPort(Port):
    """A port declared in an ANSI header: `direction net_type var type name dimensions = default` (23.2.2.2). Without
    a direction, a type or a net type, a port inherits them from the port before it."""

    direction: Direction | None
    net_type: NetType | None
    var: bool
    type: DataType | None
    name: Identifier
    dimensions: list[Dimension]
    value: Expression | None
    SINCE = verilog(2001)
    FEATURES = {"var": {True: sv()}, "value": {True: sv()}, "direction": {"ref": sv()}}


class InterfacePort(Port):
    """`interface_name.modport name` or `interface.modport name`, a port of an interface type (25.3.3). Without an
    `interface`, the port is generic (`interface`)."""

    interface: Identifier | None
    modport: Identifier | None
    name: Identifier
    dimensions: list[Dimension]
    SINCE = sv()


class PortReference(Port):
    """A non-ANSI header's port, named in the header and declared by a `PortDeclaration` item (23.2.2.1), or a part of
    it: `name[left]`, or `name[left operator right]`."""

    name: Identifier
    left: Expression | None
    operator: SelectOperator | None
    right: Expression | None

    def check(self) -> list[str]:
        if (self.operator is None) != (self.right is None) or self.left is None and self.operator is not None:
            return ["a PortReference's select has a left, and an operator and a right, or neither"]
        return []


class PortConcatenation(Port):
    """`{references}`, a non-ANSI header's port made of several (23.2.2.1)."""

    references: list[PortReference]


class ExplicitPort(Port):
    """`.name(value)`, a non-ANSI header's port named apart from what it connects, or connecting nothing
    (23.2.2.1)."""

    name: Identifier
    value: PortReference | PortConcatenation | None


class WildcardPort(Port):
    """`.*`, a header's ports as the `extern` declaration of its name gives them (23.2.1)."""

    SINCE = sv()


class EmptyPort(Port):
    """A non-ANSI header's port left out: `module m (a, , b)` (23.2.2.1)."""


class ExplicitAnsiPort(Port):
    """`direction .name(value)`, an ANSI header's port named apart from the expression it is (23.2.2.2). Without a
    direction, it follows another ANSI port and inherits its direction."""

    direction: Direction | None
    name: Identifier
    value: Expression | None
    SINCE = sv()


class PortDeclaration(Item):
    """`direction net_type var type names;`, declaring non-ANSI ports in the body, or Verilog-1995 task and function
    ports (23.2.2.1)."""

    direction: Direction
    net_type: NetType | None
    var: bool
    type: DataType | None
    declarators: list[VariableDeclarator]
    FEATURES = {"var": {True: sv()}, "direction": {"ref": sv()}}


# === Parameters (6.20) ===


class ParameterDeclaration(Item):
    """`parameter type name = value, ...;` or `localparam ...` (6.20.1). In a header's parameter list, each is one
    entry, which may give no keyword (it is then a `parameter`, or the keyword of the entry before it) and, as a
    `parameter`, no value."""

    keyword: ParameterKeyword | None
    type: DataType | None
    assignments: list[ParamAssignment]
    FEATURES = {"keyword": {"localparam": verilog(2001)}}


class ParamAssignment(SyntaxNode):
    """`name dimensions = value` in a parameter declaration (A.2.4)."""

    name: Identifier
    dimensions: list[Dimension]
    value: Expression | None


class TypeParameterDeclaration(Item):
    """`parameter type name = type, ...` or `localparam type ...`, or in a header's parameter list `type name = type`
    without a keyword (6.20.3)."""

    keyword: ParameterKeyword | None
    restriction: ForwardKeyword | None
    assignments: list[TypeAssignment]
    SINCE = sv()
    FEATURES = {"restriction": {True: sv(2023)}}


class TypeAssignment(SyntaxNode):
    """`name = type` in a type parameter declaration (A.2.4)."""

    name: Identifier
    type: DataType | None


# === Data types (6) ===


class IntegerVectorType(DataType):
    """`bit`, `logic` or `reg`, with a signing and packed dimensions (6.11)."""

    keyword: VectorKeyword
    signing: Signing | None
    dimensions: list[Dimension]
    FEATURES = {"keyword": {"bit": sv(), "logic": sv()}, "signing": {"signed": verilog(2001), "unsigned": sv()}}


class IntegerAtomType(DataType):
    """`byte`, `shortint`, `int`, `longint`, `integer` or `time`, with a signing (6.11)."""

    keyword: AtomKeyword
    signing: Signing | None
    FEATURES = {"keyword": {"byte": sv(), "shortint": sv(), "int": sv(), "longint": sv()}, "signing": {True: sv()}}


class NonIntegerType(DataType):
    """`shortreal`, `real` or `realtime` (6.12)."""

    keyword: RealKeyword
    FEATURES = {"keyword": {"shortreal": sv()}}


class KeywordType(DataType):
    """`string`, `chandle`, `event` or `void` (6.16, 6.14, 6.17, 6.13), or the type of an assertion's port:
    `sequence`, `property` or `untyped` (16.8)."""

    keyword: SimpleKeyword
    FEATURES = {"keyword": {"string": sv(), "chandle": sv(), "void": sv(), "sequence": sv(2009), "property": sv(2009),
                            "untyped": sv(2009)}}


class NamedType(DataType):
    """A type by its name: a typedef, a type parameter or an interface's type, with packed dimensions (6.18)."""

    name: Name
    dimensions: list[Dimension]
    SINCE = sv()


class VirtualInterfaceType(DataType):
    """`virtual interface name #(parameters).modport`, a variable's type that refers to an interface instance
    (25.9). `interface_keyword` writes the optional `interface`."""

    interface_keyword: bool
    interface: Identifier
    parameters: list[Expression | DataType | Connection]
    modport: Identifier | None
    SINCE = sv()


class ImplicitType(DataType):
    """The type a declaration gives by a signing and packed dimensions alone, such as `input [7:0] a` (6.10); also
    the `signed` or `unsigned` of a cast."""

    signing: Signing | None
    dimensions: list[Dimension]
    FEATURES = {"signing": {"signed": verilog(2001), "unsigned": sv()}}


class StructType(DataType):
    """`struct packed signed { members }` or `union ...`, with packed dimensions (7.2, 7.3). A union may be `tagged`,
    its members told apart by a tag, or `soft`, its members of different widths (7.3.2, 7.3.1)."""

    keyword: Choice["struct", "union"]
    qualifier: UnionQualifier | None
    packed: bool
    signing: Signing | None
    members: list[StructMember]
    dimensions: list[Dimension]
    SINCE = sv()
    FEATURES = {"qualifier": {"soft": sv(2023)}}

    def check(self) -> list[str]:
        if self.qualifier is not None and self.keyword != "union":
            return ["a StructType with a qualifier is a union"]
        return []


class StructMember(SyntaxNode):
    """`random type declarators;` in a structure or union (7.2), `rand` or `randc` in one that is randomized
    (18.4)."""

    random: RandomQualifier | None
    type: DataType
    declarators: list[VariableDeclarator]


class EnumType(DataType):
    """`enum base { members }`, with packed dimensions (6.19)."""

    base: DataType | None
    members: list[EnumMember]
    dimensions: list[Dimension]
    SINCE = sv()


class EnumMember(SyntaxNode):
    """`name = value` in an enumeration (6.19), or `name[left:right] = value`, members named from `name` with numbers
    `left` to `right`, or with one number `left`, 0 to `left - 1`."""

    name: Identifier
    left: Expression | None
    right: Expression | None
    value: Expression | None

    def check(self) -> list[str]:
        return ["an EnumMember with a right has a left"] if self.right is not None and self.left is None else []


# --- Dimensions (7.4) ---


class RangeDimension(Dimension):
    """`[left:right]` (7.4.1)."""

    left: Expression
    right: Expression


class SizeDimension(Dimension):
    """`[size]`, an unpacked dimension of `size` elements from 0 (7.4.2)."""

    size: Expression
    SINCE = sv()


class UnsizedDimension(Dimension):
    """`[]`, a dynamic array's (7.5)."""

    SINCE = sv()


class AssociativeDimension(Dimension):
    """`[type]` or `[*]`, an associative array's index (7.8)."""

    type: DataType | None
    SINCE = sv()


class QueueDimension(Dimension):
    """`[$]` or `[$:bound]` (7.10)."""

    bound: Expression | None
    SINCE = sv()


# === Declarations (A.2) ===


class NetDeclaration(Item):
    """`net_type strength expansion type #delay declarators;` (6.7): a drive strength, or a `trireg`'s charge
    strength, and `vectored` or `scalared`. Without a `net_type`, its `type` is a user-defined net type, a
    `NamedType` (`nt #1 w;`) (6.6.7)."""

    net_type: NetType | None
    strength: DriveStrength | ChargeStrength | None
    expansion: NetExpansion | None
    type: DataType | None
    delay: DelayControl | None
    declarators: list[VariableDeclarator]
    FEATURES = {"net_type": {"uwire": verilog(2005), "interconnect": sv(2012)}}

    def check(self) -> list[str]:
        if isinstance(self.strength, ChargeStrength) and self.net_type != "trireg":
            return ["a NetDeclaration with a charge strength is a trireg"]
        if self.net_type is None and (not isinstance(self.type, NamedType) or self.strength is not None
                                      or self.expansion is not None):
            return ["a NetDeclaration without a net type has a user-defined one, a NamedType, alone"]
        return []


class DriveStrength(SyntaxNode):
    """`(strength0, strength1)`, in either order: a net's or a continuous assignment's strengths of 0 and 1, of
    `supply`, `strong`, `pull`, `weak` and `highz`, not both `highz` (6.3.2, 10.3.4)."""

    first: Strength
    second: Strength

    def check(self) -> list[str]:
        if not isinstance(self.first, str) or not isinstance(self.second, str):
            return []
        if {self.first[-1], self.second[-1]} != {"0", "1"}:
            return ["a DriveStrength has a strength of 0 and one of 1"]
        if self.first.startswith("highz") and self.second.startswith("highz"):
            return ["a DriveStrength is not highz for both"]
        return []


class ChargeStrength(SyntaxNode):
    """`(small)`, `(medium)` or `(large)`: a `trireg`'s charge strength (6.6.4.2)."""

    size: ChargeSize


class VariableDeclaration(Item):
    """`visibility random const var lifetime type declarators;` (6.8); in a class, a property, which may be `local`
    or `protected` and `rand` or `randc`, and is `static` by its `lifetime` (8.5, 18.4)."""

    visibility: Visibility | None
    random: RandomQualifier | None
    const: bool
    var: bool
    lifetime: Lifetime | None
    type: DataType | None
    declarators: list[VariableDeclarator]
    FEATURES = {"const": {True: sv()}, "var": {True: sv()}, "lifetime": {True: sv()}, "visibility": {True: sv()},
                "random": {True: sv()}}


class VariableDeclarator(SyntaxNode):
    """`name dimensions = value` in a net, variable, port or member declaration (A.2.3)."""

    name: Identifier
    dimensions: list[Dimension]
    value: Expression | None


class ForwardTypedefDeclaration(Item):
    """`typedef keyword name;`, which declares a type before its definition (6.18)."""

    keyword: ForwardKeyword | None
    name: Identifier
    SINCE = sv()
    FEATURES = {"keyword": {"interface class": sv(2012)}}


class TypedefDeclaration(Item):
    """`typedef type name dimensions;` (6.18), `local` or `protected` in a class (8.18)."""

    visibility: Visibility | None
    type: DataType
    name: Identifier
    dimensions: list[Dimension]
    SINCE = sv()


class EmptyItem(Item):
    """`;` alone, where items are listed (A.1.4, A.1.9)."""

    SINCE = sv()


class DpiImport(Item):
    """`import "DPI-C" property c_name = prototype;`: a C function or task, `context` or a `pure` function, which
    SystemVerilog calls by the prototype's name (35.5.4)."""

    spec: DpiSpec
    property: DpiProperty | None
    c_name: Identifier | None
    prototype: FunctionDeclaration | TaskDeclaration
    SINCE = sv()
    FEATURES = {"spec": {"DPI-C": sv(2009)}}

    def check(self) -> list[str]:
        if self.property == "pure" and isinstance(self.prototype, TaskDeclaration):
            return ["a pure DpiImport is a function"]
        return []


class DpiExport(Item):
    """`export "DPI-C" c_name = function name;`: a function or task C calls (35.5.4)."""

    spec: DpiSpec
    c_name: Identifier | None
    keyword: SubroutineKeyword
    name: Identifier
    SINCE = sv()
    FEATURES = {"spec": {"DPI-C": sv(2009)}}


class BindDirective(Item):
    """`bind target: instances instantiation;`: an instantiation into a module, an interface or a checker, or into
    some of its instances, without changing its source (23.11)."""

    target: Expression
    instances: list[Expression]
    instantiation: ModuleInstantiation
    SINCE = sv()


class ElaborationTask(Item):
    """`$fatal(arguments);`, `$error`, `$warning` or `$info` among items: a message, or a failure, when elaboration
    reaches it (20.11)."""

    name: ElaborationTaskName
    arguments: list[Expression | EmptyArgument]
    SINCE = sv(2009)


class GenvarDeclaration(Item):
    """`genvar names;` (27.4)."""

    names: list[Identifier]
    SINCE = verilog(2001)


class ImportDeclaration(Item):
    """`import package::name, package::*;` (26.3)."""

    items: list[ImportItem]
    SINCE = sv()


class ExportDeclaration(Item):
    """`export package::name, ...;` or `export *::*;` (`all`) in a package: names it imports that the packages which
    import it see too (26.6)."""

    all: bool
    items: list[ImportItem]
    SINCE = sv(2009)

    def check(self) -> list[str]:
        return ["an ExportDeclaration exports all or items"] if (self.all is True) == bool(self.items) else []


class ImportItem(SyntaxNode):
    """`package::name`, or `package::*` without a `name` (26.3)."""

    package: Identifier
    name: Identifier | None


class NetTypeDeclaration(Item):
    """`nettype type name with function;`: a user-defined net type, resolved by `function` (6.6.7)."""

    type: DataType
    name: Identifier
    function: Name | None
    SINCE = sv(2012)


class NetAlias(Item):
    """`alias net = net = ...;`: two nets or more that are one (10.11)."""

    nets: list[Expression]
    SINCE = sv()

    def check(self) -> list[str]:
        return ["a NetAlias has two nets or more"] if len(self.nets) < 2 else []


class DefParam(Item):
    """`defparam target = value, ...;`: parameters of instances, set by their hierarchical names (23.10.1)."""

    assignments: list[DefParamAssignment]


class DefParamAssignment(SyntaxNode):
    """`target = value` in a `defparam`."""

    target: Expression
    value: Expression


class TimeUnitsDeclaration(Item):
    """`timeunit time / precision;` or `timeprecision time;` (3.14.2.2)."""

    keyword: TimeUnitKeyword
    time: TimeLiteral
    precision: TimeLiteral | None
    SINCE = sv()
    FEATURES = {"precision": {True: sv(2009)}}

    def check(self) -> list[str]:
        if self.precision is not None and self.keyword == "timeprecision":
            return ["a timeprecision TimeUnitsDeclaration has no precision"]
        return []


class ModportDeclaration(Item):
    """`modport items;` in an interface (25.5)."""

    items: list[ModportItem]
    SINCE = sv()


class ModportItem(SyntaxNode):
    """`name (ports)` in a modport declaration (25.5)."""

    name: Identifier
    ports: list[ModportPort | ModportSubroutine | ModportClocking]


class ModportPort(SyntaxNode):
    """`direction name` in a modport, or `explicit`ly `direction .name(value)`, a port named apart from the expression
    it is, or that is nothing (25.5.4)."""

    direction: Direction
    explicit: bool
    name: Identifier
    value: Expression | None

    def check(self) -> list[str]:
        if self.value is not None and self.explicit is not True:
            return ["a ModportPort with a value is explicit"]
        return []


class ModportSubroutine(SyntaxNode):
    """`import name` or `export name` in a modport, or with a `prototype`, a function's or a task's without its body
    (`import task t(int a)`) (25.7)."""

    keyword: ImportExport
    name: Identifier | None
    prototype: FunctionDeclaration | TaskDeclaration | None

    def check(self) -> list[str]:
        if (self.name is None) == (self.prototype is None):
            return ["a ModportSubroutine has a name or a prototype"]
        return []


class ModportClocking(SyntaxNode):
    """`clocking name` in a modport: a clocking block's signals, as it gives them (25.5.5)."""

    name: Identifier


class ContinuousAssign(Item):
    """`assign strength #delay target = value, ...;` (10.3)."""

    strength: DriveStrength | None
    delay: DelayControl | None
    assignments: list[AssignmentExpression]


class AlwaysConstruct(Item):
    """`always body`, `always_comb`, `always_ff` or `always_latch` (9.2.2)."""

    keyword: AlwaysKeyword
    body: Statement
    FEATURES = {"keyword": {"always_comb": sv(), "always_ff": sv(), "always_latch": sv()}}


class InitialConstruct(Item):
    """`initial body` (9.2.1)."""

    body: Statement


class FinalConstruct(Item):
    """`final body` (9.2.3)."""

    body: Statement
    SINCE = sv()


class FunctionDeclaration(Item):
    """`function lifetime type name(ports); body endfunction` (13.4). The body lists declarations and statements in
    order. Without ports in parentheses, Verilog-1995 style, `PortDeclaration`s in the body declare them.
    In a class, a method may be `local` or `protected`, `static`, `virtual`, and a prototype without a body:
    `extern`, defined outside the class, or `pure virtual` (8.10, 8.20, 8.24). A constructor is named `new`. A virtual
    method's `:initial` or `:extends` `specifier` and `:final` say whether it overrides and may be overridden (8.20).
    """

    extern: bool
    pure: bool
    virtual: bool
    visibility: Visibility | None
    static: bool
    specifier: OverrideSpecifier | None
    final: bool
    lifetime: Lifetime | None
    type: DataType | None
    name: Name
    ports: list[TfPort]
    body: list[Item | Statement | Directive | Comment]
    labeled: bool
    FEATURES = {"lifetime": {True: verilog(2001)}, "labeled": {True: sv()}, "extern": {True: sv()},
                "pure": {True: sv()}, "virtual": {True: sv()}, "visibility": {True: sv()}, "static": {True: sv()},
                "specifier": {True: sv(2023)}, "final": {True: sv(2023)}}

    def check(self) -> list[str]:
        return _method_problems(self)


class TaskDeclaration(Item):
    """`task lifetime name(ports); body endtask` (13.3). In a class, a method may be `local` or `protected`, `static`,
    `virtual`, and a prototype without a body: `extern`, defined outside the class, or `pure virtual` (8.10, 8.20,
    8.24). A constructor is named `new`. A virtual method's `:initial` or `:extends` `specifier` and `:final` say
    whether it overrides and may be overridden (8.20)."""

    extern: bool
    pure: bool
    virtual: bool
    visibility: Visibility | None
    static: bool
    specifier: OverrideSpecifier | None
    final: bool
    lifetime: Lifetime | None
    name: Name
    ports: list[TfPort]
    body: list[Item | Statement | Directive | Comment]
    labeled: bool
    FEATURES = {"lifetime": {True: verilog(2001)}, "labeled": {True: sv()}, "extern": {True: sv()},
                "pure": {True: sv()}, "virtual": {True: sv()}, "visibility": {True: sv()}, "static": {True: sv()},
                "specifier": {True: sv(2023)}, "final": {True: sv(2023)}}

    def check(self) -> list[str]:
        return _method_problems(self)


def _method_problems(method: FunctionDeclaration | TaskDeclaration) -> list[str]:
    """A `pure` method is `virtual`, and a prototype (`extern` or `pure`) has no body."""
    kind = type(method).__name__
    if method.pure is True and method.virtual is not True:
        return [f"a pure {kind} is virtual"]
    if (method.extern is True or method.pure is True) and (method.body or method.labeled is True):
        return [f"an extern or pure {kind} has no body"]
    return []


class TfPort(SyntaxNode):
    """`direction var type name dimensions = default`, a task's or function's port in parentheses (13.3). Without a
    direction or a type, a port inherits them from the one before it. A `ref` may be `const ref` or `ref static`
    (13.5.2)."""

    const: bool
    direction: Direction | None
    static: bool
    var: bool
    type: DataType | None
    name: Identifier
    dimensions: list[Dimension]
    value: Expression | None
    SINCE = verilog(2001)
    FEATURES = {"var": {True: sv()}, "value": {True: sv()}, "direction": {"ref": sv()}, "const": {True: sv()},
                "static": {True: sv(2023)}}

    def check(self) -> list[str]:
        if (self.const is True or self.static is True) and self.direction != "ref":
            return ["a const or static TfPort is a ref"]
        return []


# --- Classes (8) ---


class ClassDeclaration(Item):
    """`virtual class name #(parameters) extends base(arguments) implements interfaces; items endclass`, or
    `interface class name #(parameters) extends interfaces; items endclass` (8.3, 8.26). Its items are properties,
    methods, parameters, types and classes. `labeled` repeats the name after `endclass`. A `final` class
    (`class :final c`) has no derived classes, and a `defaulted` one passes its base its constructor's arguments
    (`extends base(default)`) (8.15)."""

    virtual: bool
    interface: bool
    final: bool
    name: Identifier
    parameters: list[ParameterDeclaration | TypeParameterDeclaration]
    base: NamedType | None
    arguments: list[Expression | Connection]
    defaulted: bool
    interfaces: list[NamedType]
    items: list[Item | Directive | Comment]
    labeled: bool
    SINCE = sv()
    FEATURES = {"interface": {True: sv(2012)}, "interfaces": {True: sv(2012)}, "final": {True: sv(2023)},
                "defaulted": {True: sv(2023)}}

    def check(self) -> list[str]:
        if self.interface is True and (self.virtual is True or self.base is not None or self.arguments):
            return ["an interface ClassDeclaration has no virtual, base or arguments"]
        if self.arguments and self.base is None:
            return ["a ClassDeclaration with arguments has a base"]
        if self.defaulted is True and (self.base is None or self.arguments):
            return ["a ClassDeclaration with default arguments has a base and no others"]
        return []


# --- Constraints (18) ---


class ConstraintDeclaration(Item):
    """`static constraint name { constraints }` in a class, or outside it with a qualified name (`constraint c::k { }`),
    which defines a prototype (18.5). Its `:initial` or `:extends` `specifier` and `:final` say whether it overrides and
    may be overridden (18.5.2)."""

    static: bool
    specifier: OverrideSpecifier | None
    final: bool
    name: Name
    items: list[Constraint | Directive | Comment]
    SINCE = sv()
    FEATURES = {"specifier": {True: sv(2023)}, "final": {True: sv(2023)}}


class ConstraintPrototype(Item):
    """`qualifier static constraint name;`: a constraint defined outside its class, `extern` or by default, or `pure`,
    which derived classes define (18.5.1), with a `specifier` and `final` as a declaration has."""

    qualifier: PrototypeQualifier | None
    static: bool
    specifier: OverrideSpecifier | None
    final: bool
    name: Identifier
    SINCE = sv()
    FEATURES = {"qualifier": {"pure": sv(2012)}, "specifier": {True: sv(2023)}, "final": {True: sv(2023)}}


class ConstraintBlock(Constraint):
    """`{ constraints }`, the constraints an implication, a condition or a loop applies (18.5)."""

    items: list[Constraint | Directive | Comment]
    SINCE = sv()


class ExpressionConstraint(Constraint):
    """`soft expression;`, an expression that must hold, or with `soft` should (18.5.14)."""

    soft: bool
    expression: Expression
    SINCE = sv()
    FEATURES = {"soft": {True: sv(2012)}}


class ImplicationConstraint(Constraint):
    """`condition -> body`: `body` holds where `condition` does (18.5.6)."""

    condition: Expression
    body: Constraint
    SINCE = sv()


class ConditionalConstraint(Constraint):
    """`if (condition) consequence else alternative` (18.5.7)."""

    condition: Expression
    consequence: Constraint
    alternative: Constraint | None
    SINCE = sv()


class ForeachConstraint(Constraint):
    """`foreach (array[variables]) body`, a constraint on each element (18.5.8.1)."""

    array: Expression
    variables: list[Identifier | EmptyArgument]
    body: Constraint
    SINCE = sv()


class SolveBeforeConstraint(Constraint):
    """`solve solve before before;`, an order in which variables are chosen (18.5.10)."""

    solve: list[Expression]
    before: list[Expression]
    SINCE = sv()


class DisableSoftConstraint(Constraint):
    """`disable soft target;`, which drops the soft constraints on a variable (18.5.14.2)."""

    target: Expression
    SINCE = sv(2012)


class UniqueConstraint(Constraint):
    """`unique { set }`: the variables and arrays of `set` have different values (18.5.5)."""

    set: list[Expression | Range]
    SINCE = sv(2012)


class DistExpression(Expression):
    """`value dist { items }`, a distribution of a random variable's values, in a constraint (18.5.4)."""

    value: Expression
    items: list[DistItem]
    SINCE = sv()


class DistItem(SyntaxNode):
    """`value := weight` (each value of a range weighs `weight`) or `value :/ weight` (the range weighs `weight`), or
    `default :/ weight` without a `value`; without a weight, a value weighs 1 (18.5.4)."""

    value: Expression | Range | None
    operator: DistOperator | None
    weight: Expression | None
    SINCE = sv()

    def features(self) -> list[tuple[str, Availability]]:
        return [("DistItem default", sv(2023))] if self.value is None else []

    def check(self) -> list[str]:
        if (self.operator is None) != (self.weight is None):
            return ["a DistItem has both an operator and a weight, or neither"]
        if self.value is None and self.operator != ":/":
            return ["a default DistItem weighs its values with :/"]
        return []


# --- Generate constructs (27) ---


class GenerateRegion(Item):
    """`generate items endgenerate` (27.3)."""

    items: list[Item | Directive | Comment]
    SINCE = verilog(2001)


class GenerateFor(Item):
    """`for (genvar name = start; condition; step) body` (27.4)."""

    genvar: bool
    name: Identifier
    start: Expression
    condition: Expression
    step: Expression
    body: Item
    SINCE = verilog(2001)
    FEATURES = {"genvar": {True: verilog(2005)}}


class GenerateIf(Item):
    """`if (condition) consequence else alternative` among items (27.5)."""

    condition: Expression
    consequence: Item
    alternative: Item | None
    SINCE = verilog(2001)


class GenerateCase(Item):
    """`case (expression) items endcase` among items (27.5)."""

    expression: Expression
    items: list[CaseItem]
    SINCE = verilog(2001)


class GenerateBlock(Item):
    """`begin : name items end : name` in a generate construct (27.3). `labeled` repeats the name after `end`."""

    name: Identifier | None
    items: list[Item | Directive | Comment]
    labeled: bool
    SINCE = verilog(2001)
    FEATURES = {"labeled": {True: sv()}}


# --- Instantiation (23.3) ---


class GateInstantiation(Item):
    """`gate strength #delay instances;`: built-in gates, switches and pulls (28.3), or a user-defined primitive's
    instances without names (29.8), whose `primitive` is its name."""

    keyword: GateKeyword | None
    primitive: Identifier | None
    strength: DriveStrength | PullStrength | None
    delay: DelayControl | None
    instances: list[GateInstance]

    def check(self) -> list[str]:
        if (self.keyword is None) == (self.primitive is None):
            return ["a GateInstantiation is a gate's or a primitive's"]
        if isinstance(self.strength, PullStrength) and self.keyword not in ("pullup", "pulldown"):
            return ["a GateInstantiation with a pull strength is a pullup or a pulldown"]
        return []


class GateInstance(SyntaxNode):
    """`name dimensions (terminals)`, a gate's instance: its output terminals, then its inputs; the name may be left
    out (28.3)."""

    name: Identifier | None
    dimensions: list[Dimension]
    terminals: list[Expression]

    def check(self) -> list[str]:
        return ["a GateInstance with dimensions has a name"] if self.dimensions and self.name is None else []


class PullStrength(SyntaxNode):
    """`(strength)`, a `pullup`'s or a `pulldown`'s strength (28.6)."""

    strength: Strength


class UdpDeclaration(Item):
    """`primitive name (ports); declarations initial table entries endtable endprimitive`, a user-defined primitive:
    its output from its inputs, and from its current state when its output is a `reg` (29). An ANSI header declares
    its ports (`UdpPort`s); a non-ANSI one names them (`Identifier`s), and `declarations` declare them. `labeled`
    repeats the name after `endprimitive`."""

    name: Identifier
    ports: list[UdpPort | Identifier]
    declarations: list[UdpPort]
    initial: UdpInitial | None
    entries: list[UdpEntry | Comment | Directive]
    labeled: bool
    FEATURES = {"labeled": {True: sv()}}


class UdpPort(SyntaxNode):
    """`output reg name = value`, `input names` or `reg name`: a primitive's port, or its output's state (29.3)."""

    direction: UdpDirection | None
    reg: bool
    names: list[Identifier]
    value: Expression | None

    def check(self) -> list[str]:
        if self.direction == "input" and (self.reg is True or self.value is not None):
            return ["an input UdpPort has no reg and no value"]
        if self.direction is None and self.reg is not True:
            return ["a UdpPort without a direction is a reg"]
        if self.value is not None and (self.reg is not True or len(self.names) != 1):
            return ["a UdpPort with a value is one output reg"]
        return []


class UdpInitial(SyntaxNode):
    """`initial name = value;`, a sequential primitive's starting state (29.7)."""

    name: Identifier
    value: Expression


class UdpEntry(SyntaxNode):
    """`inputs : current : output;`, a row of a primitive's table: its inputs' levels and edges (`0 (01) ?`),
    separated by spaces, and for a sequential primitive its current state; the output is a level, or `-` for no change
    (29.3.6)."""

    inputs: str
    current: str | None
    output: str

    def check(self) -> list[str]:
        if not isinstance(self.inputs, str) or not isinstance(self.output, str):
            return []
        fields = self.inputs.split(" ")
        if not all(f in _UDP_INPUTS or len(f) == 4 and f[0] + f[3] == "()" and set(f[1:3]) <= _UDP_LEVELS
                   for f in fields):
            return ["a UdpEntry's inputs are levels and edges"]
        if self.current is not None and self.current not in _UDP_LEVELS:
            return ["a UdpEntry's current state is a level"]
        if self.output not in ("0", "1", "x", "X") and (self.output != "-" or self.current is None):
            return ["a UdpEntry's output is 0, 1 or x, or - with a current state"]
        return []


_UDP_LEVELS = {"0", "1", "x", "X", "?", "b", "B"}
_UDP_INPUTS = _UDP_LEVELS | {"r", "R", "f", "F", "p", "P", "n", "N", "*"}


class ModuleInstantiation(Item):
    """`module #(parameters) instance (connections), ...;`, of a module, an interface, a program or a checker (23.3,
    17.3), which a package may hold (`p::c`). Parameters and connections are ordered expressions or
    `NamedConnection`s."""

    module: Identifier | ScopedName
    parameters: list[Expression | DataType | Connection]
    instances: list[Instance]


class Instance(SyntaxNode):
    """`name dimensions (connections)` in an instantiation (23.3.2)."""

    name: Identifier
    dimensions: list[Dimension]
    connections: list[Expression | Connection]


class NamedConnection(Connection):
    """`.name(value)`; `.name()` without a value leaves it unconnected, and an `implicit` `.name` connects it to
    what has its name (23.3.2.2, 23.3.2.3). In a call, a named argument."""

    name: Identifier
    value: Expression | DataType | None
    implicit: bool
    FEATURES = {"implicit": {True: sv()}}


class WildcardConnection(Connection):
    """`.*`, connecting every port to what has its name (23.3.2.4)."""

    SINCE = sv()


# === Statements (12) ===


class AssignmentStatement(Statement):
    """`target = timing value;`: blocking (`=`), nonblocking (`<=`) or an assignment operator (`+=`), with an
    intra-assignment delay or event control (10.4, 11.4.1)."""

    target: Expression
    operator: StatementAssignment
    timing: TimingControl | None
    value: Expression
    FEATURES = {"operator": {op: sv() for op in ("+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=", "<<<=",
                                                 ">>>=")}}


class ExpressionStatement(Statement):
    """`expression;`: a call, or an increment or decrement (12.3)."""

    expression: Expression


class NullStatement(Statement):
    """`;` (12.3)."""


class SeqBlock(Statement):
    """`begin : name items end : name`, declarations then statements (9.3.1). `labeled` repeats the name after `end`."""

    name: Identifier | None
    items: list[Item | Statement | Directive | Comment]
    labeled: bool
    FEATURES = {"labeled": {True: sv()}}


class ParBlock(Statement):
    """`fork : name items join` or `join_any` or `join_none` (9.3.2)."""

    name: Identifier | None
    items: list[Item | Statement | Directive | Comment]
    join: JoinKeyword
    labeled: bool
    FEATURES = {"join": {"join_any": sv(), "join_none": sv()}, "labeled": {True: sv()}}


class IfStatement(Statement):
    """`qualifier if (condition) consequence else alternative` (12.4)."""

    qualifier: Qualifier | None
    condition: Expression
    consequence: Statement
    alternative: Statement | None
    FEATURES = {"qualifier": {"unique": sv(), "priority": sv(), "unique0": sv(2009)}}


class CaseStatement(Statement):
    """`qualifier case (expression) inside items endcase`, or `casez` or `casex` (12.5), or `case (expression) matches`
    of `PatternCaseItem`s (12.6.1)."""

    qualifier: Qualifier | None
    keyword: CaseKeyword
    expression: Expression
    inside: bool
    matches: bool
    items: list[CaseItem | PatternCaseItem]
    FEATURES = {"qualifier": {"unique": sv(), "priority": sv(), "unique0": sv(2009)}, "inside": {True: sv()},
                "matches": {True: sv()}}

    def check(self) -> list[str]:
        if self.inside is True and self.matches is True:
            return ["a CaseStatement is inside or matches, not both"]
        patterns = [isinstance(i, PatternCaseItem) for i in self.items]
        if self.matches is not True and any(patterns):
            return ["a CaseStatement with PatternCaseItems matches"]
        if self.matches is True and not all(p or not i.expressions for p, i in zip(patterns, self.items)):
            return ["a matching CaseStatement has PatternCaseItems and a default"]
        return []


class PatternCaseItem(SyntaxNode):
    """`pattern &&& guard: body` in a `case matches` (12.6.1)."""

    pattern: Pattern | Expression
    guard: Expression | None
    body: Statement
    SINCE = sv()


class CaseItem(SyntaxNode):
    """`expressions: body`, or `default: body` without expressions, in a case statement or a case generate construct
    (12.5)."""

    expressions: list[Expression | Range]
    body: Statement | Item


class ForStatement(Statement):
    """`for (initializers; condition; steps) body` (12.7.1)."""

    initializers: list[VariableDeclaration | AssignmentExpression]
    condition: Expression | None
    steps: list[Expression]
    body: Statement

    def features(self) -> list[tuple[str, Availability]]:
        if any(isinstance(i, VariableDeclaration) for i in self.initializers) or len(self.initializers) > 1:
            return [("ForStatement.initializers declarations", sv())]
        return []


class WhileStatement(Statement):
    """`while (condition) body` (12.7.4)."""

    condition: Expression
    body: Statement


class DoWhileStatement(Statement):
    """`do body while (condition);` (12.7.5)."""

    body: Statement
    condition: Expression
    SINCE = sv()


class RepeatStatement(Statement):
    """`repeat (count) body` (12.7.2)."""

    count: Expression
    body: Statement


class ForeverStatement(Statement):
    """`forever body` (12.7.2)."""

    body: Statement


class ForeachStatement(Statement):
    """`foreach (array[variables]) body` (12.7.3); a dimension it skips is an `EmptyArgument` (`q[, j]`)."""

    array: Expression
    variables: list[Identifier | EmptyArgument]
    body: Statement
    SINCE = sv()


class BreakStatement(Statement):
    """`break;` (12.8)."""

    SINCE = sv()


class ContinueStatement(Statement):
    """`continue;` (12.8)."""

    SINCE = sv()


class ReturnStatement(Statement):
    """`return value;` (12.8)."""

    value: Expression | None
    SINCE = sv()


class TimedStatement(Statement):
    """`timing body`, a statement after a delay or an event control; without a body, `timing;` (9.4)."""

    timing: TimingControl
    body: Statement | None


class WaitStatement(Statement):
    """`wait (condition) body`; without a body, `wait (condition);` (9.4.3)."""

    condition: Expression
    body: Statement | None


class EventTrigger(Statement):
    """`-> event;`, or `->> timing event;` when `nonblocking`, after a delay or an event control (15.5.1)."""

    nonblocking: bool
    timing: TimingControl | None
    event: Expression
    FEATURES = {"nonblocking": {True: sv()}}

    def check(self) -> list[str]:
        if self.timing is not None and self.nonblocking is not True:
            return ["an EventTrigger with a timing is nonblocking"]
        return []


class ForceStatement(Statement):
    """`force target = value;` or `assign target = value;`: a procedural continuous assignment, which holds until
    `release` or `deassign` (10.6)."""

    keyword: ForceKeyword
    target: Expression
    value: Expression


class ReleaseStatement(Statement):
    """`release target;` or `deassign target;`, which ends a `force` or a procedural `assign` (10.6)."""

    keyword: ReleaseKeyword
    target: Expression


class CheckerStatement(Statement):
    """A checker instantiated in a procedure, as its statement (17.3)."""

    instantiation: ModuleInstantiation
    SINCE = sv(2009)


class WaitForkStatement(Statement):
    """`wait fork;`, until the processes this one forked end (9.6.1)."""

    SINCE = sv()


class WaitOrderStatement(Statement):
    """`wait_order (events) pass else fail`: until the events trigger in order (15.5.4)."""

    events: list[Expression]
    pass_action: Statement | None
    fail_action: Statement | None
    SINCE = sv()


class DisableStatement(Statement):
    """`disable target;`, or `disable fork;` without a target (9.6.2, 9.6.3)."""

    target: Expression | None

    def features(self) -> list[tuple[str, Availability]]:
        return [("DisableStatement fork", sv())] if self.target is None else []


class RandCaseStatement(Statement):
    """`randcase weight: body ... endcase`: one of the bodies, chosen at random by their weights (18.16)."""

    items: list[RandCaseItem]
    SINCE = sv()


class RandCaseItem(SyntaxNode):
    """`weight: body` in a `randcase` (18.16)."""

    weight: Expression
    body: Statement
    SINCE = sv()


class RandSequenceStatement(Statement):
    """`randsequence (first) productions endsequence`: a sentence of productions, generated from `first`, or the first
    production (18.17)."""

    first: Identifier | None
    productions: list[Production]
    SINCE = sv()


class Production(SyntaxNode):
    """`type name(ports) : rules;`, a production and its rules, separated by `|`, of which one is chosen; a `void` or
    typed production returns a value (18.17.7)."""

    type: DataType | None
    name: Identifier
    ports: list[TfPort]
    rules: list[ProductionRule]
    SINCE = sv()


class ProductionRule(SyntaxNode):
    """`items := weight { code }`: what a rule generates in order, chosen by its weight, after which its code runs;
    or `rand join (bias) items`, its items interleaved at random (18.17.1, 18.17.5)."""

    rand_join: bool
    bias: Expression | None
    items: list[ProductionItem]
    weight: Expression | None
    code: ProductionCode | None
    SINCE = sv()

    def check(self) -> list[str]:
        if self.bias is not None and self.rand_join is not True:
            return ["a ProductionRule with a bias is a rand join"]
        if self.code is not None and self.weight is None:
            return ["a ProductionRule's code follows its weight"]
        return []


class ProductionCall(ProductionItem):
    """`name(arguments)`: a production to generate (18.17.7)."""

    name: Identifier
    arguments: list[Expression | Connection]
    SINCE = sv()


class ProductionCode(ProductionItem):
    """`{ items }`: code that runs where it is in a rule (18.17.2)."""

    items: list[Item | Statement | Directive | Comment]
    SINCE = sv()


class ProductionIf(ProductionItem):
    """`if (condition) consequence else alternative`, a production chosen by a condition (18.17.4)."""

    condition: Expression
    consequence: ProductionCall
    alternative: ProductionCall | None
    SINCE = sv()


class ProductionRepeat(ProductionItem):
    """`repeat (count) item`, a production generated `count` times (18.17.4)."""

    count: Expression
    item: ProductionCall
    SINCE = sv()


class ProductionCase(ProductionItem):
    """`case (expression) items endcase`, a production chosen by a value (18.17.4)."""

    expression: Expression
    items: list[ProductionCaseItem]
    SINCE = sv()


class ProductionCaseItem(SyntaxNode):
    """`values: item;`, or `default: item;` without values (18.17.4)."""

    values: list[Expression]
    item: ProductionCall
    SINCE = sv()


class LabeledStatement(Statement):
    """`label: statement`, a statement named for `disable` and for its assertions' messages (9.3.5). A labeled block
    is a named one instead: `x: begin ... end` is `begin : x ... end`."""

    label: Identifier
    statement: Statement
    SINCE = sv()


class ImmediateAssertion(Statement):
    """`assert (expression) pass else fail`, or `assume` or `cover`, deferred with `#0` or `final` (16.3, 16.4).
    `cover` has no `fail`."""

    keyword: AssertionKeyword
    deferral: Deferral | None
    expression: Expression
    pass_action: Statement | None
    fail_action: Statement | None
    SINCE = sv()
    FEATURES = {"deferral": {"#0": sv(2009), "final": sv(2012)}}


# === Assertions (16) ===


class ConcurrentAssertion(Statement):
    """`assert property (spec) pass else fail`, or `assume`, `cover` (of a property, or with `sequence` of a
    sequence) or `restrict` (16.14). `cover` has no `fail`, and `restrict` no action."""

    keyword: ConcurrentKeyword
    sequence: bool
    spec: PropertySpec
    pass_action: Statement | None
    fail_action: Statement | None
    SINCE = sv()
    FEATURES = {"keyword": {"restrict": sv(2009)}}


class ExpectStatement(Statement):
    """`expect (spec) pass else fail`, which waits until a property passes or fails (16.17)."""

    spec: PropertySpec
    pass_action: Statement | None
    fail_action: Statement | None
    SINCE = sv()


class AssertionItem(Item):
    """`label: assertion` among items: a concurrent assertion, or a deferred immediate one (16.4, 16.14)."""

    label: Identifier | None
    assertion: ConcurrentAssertion | ImmediateAssertion
    SINCE = sv()


class PropertySpec(SyntaxNode):
    """`@(clock) disable iff (disable) property`: a property with its clock and its reset (16.12)."""

    clock: EventControl | None
    disable: Expression | None
    property: Property | Expression
    SINCE = sv()


class PropertyDeclaration(Item):
    """`property name(ports); variables spec; endproperty` (16.12). `labeled` repeats the name after `endproperty`;
    without ports, the name has no parentheses."""

    name: Identifier
    ports: list[AssertionPort]
    variables: list[VariableDeclaration]
    spec: PropertySpec
    labeled: bool
    SINCE = sv()


class SequenceDeclaration(Item):
    """`sequence name(ports); variables sequence; endsequence` (16.8)."""

    name: Identifier
    ports: list[AssertionPort]
    variables: list[VariableDeclaration]
    sequence: Sequence | Expression
    labeled: bool
    SINCE = sv()


class LetDeclaration(Item):
    """`let name(ports) = value;`, an expression with arguments, expanded where it is used (11.12)."""

    name: Identifier
    ports: list[AssertionPort]
    value: Expression
    SINCE = sv(2009)


class AssertionPort(SyntaxNode):
    """`local direction type name dimensions = default`, a port of a property, a sequence or a `let` (16.8). Without a
    type it is untyped, as `untyped` makes it."""

    local: bool
    direction: PortDirection | None
    type: DataType | None
    name: Identifier
    dimensions: list[Dimension]
    value: Property | Expression | None
    SINCE = sv()
    FEATURES = {"local": {True: sv(2009)}}


# --- Sequences (16.7) ---


class DelaySequence(Sequence):
    """`first ##delay sequence ##delay sequence ...`, or without `first` a sequence that starts with a delay (16.7)."""

    first: Sequence | Expression | None
    steps: list[DelayStep]
    SINCE = sv()


class DelayStep(SyntaxNode):
    """`##delay sequence` in a `DelaySequence`: a number of ticks, or a range of them (16.7)."""

    delay: Expression | CycleRange
    sequence: Sequence | Expression
    SINCE = sv()


class CycleRange(SyntaxNode):
    """`[low:high]`, a range of ticks or of repetitions, `high` `$` when unbounded. `##[*]`, `[*]` and `[+]` are
    `[0:$]`, `[*0:$]` and `[*1:$]` (16.7, 16.9.2)."""

    low: Expression
    high: Expression
    SINCE = sv()


class RepetitionSequence(Sequence):
    """`sequence[*count]` (consecutive), `[->count]` (goto) or `[=count]` (nonconsecutive), of a number or a range of
    repetitions (16.9.2)."""

    sequence: Sequence | Expression
    operator: RepetitionOperator
    count: Expression | CycleRange
    SINCE = sv()


class BinarySequence(Sequence):
    """`left operator right`: `and`, `or`, `intersect`, `within` or `throughout` (16.9)."""

    left: Sequence | Expression
    operator: SequenceOperator
    right: Sequence | Expression
    SINCE = sv()


class ParenthesizedSequence(Sequence):
    """`(sequence, items)`: a sequence in parentheses, with the match items (assignments, calls) it runs when it
    matches (16.10)."""

    sequence: Sequence | Expression
    items: list[Expression]
    SINCE = sv()


class FirstMatchSequence(Sequence):
    """`first_match(sequence, items)`: the sequence's first match only (16.9.8)."""

    sequence: Sequence | Expression
    items: list[Expression]
    SINCE = sv()


class ClockedSequence(Sequence):
    """`@(clock) sequence`, a sequence on its own clock (16.16)."""

    clock: EventControl
    sequence: Sequence | Expression
    SINCE = sv()


# --- Properties (16.12) ---


class ImplicationProperty(Property):
    """`antecedent |-> consequent` (overlapping), `|=>` (on the next tick), or `#-#` and `#=#`, which also need the
    antecedent to match (16.12.7, 16.12.9)."""

    antecedent: Sequence | Expression
    operator: ImplicationOperator
    consequent: Property | Expression
    SINCE = sv()
    FEATURES = {"operator": {"#-#": sv(2009), "#=#": sv(2009)}}


class BinaryProperty(Property):
    """`left operator right`: `and`, `or`, `iff`, `implies`, `until`, `s_until`, `until_with` or `s_until_with`
    (16.12)."""

    left: Property | Expression
    operator: PropertyOperator
    right: Property | Expression
    SINCE = sv()
    FEATURES = {"operator": {op: sv(2009) for op in ("iff", "implies", "until", "s_until", "until_with",
                                                     "s_until_with")}}


class UnaryProperty(Property):
    """`operator [range] operand`: `not`, `nexttime`, `s_nexttime`, `always`, `s_always`, `eventually` or
    `s_eventually`, with a number of ticks or a range of them for those that take one (16.12)."""

    operator: UnaryPropertyOperator
    range: Expression | CycleRange | None
    operand: Property | Expression
    SINCE = sv()
    FEATURES = {"operator": {op: sv(2009) for op in ("nexttime", "s_nexttime", "always", "s_always", "eventually",
                                                     "s_eventually")}}


class StrengthProperty(Property):
    """`strong(sequence)` or `weak(sequence)` (16.12.2)."""

    keyword: StrengthKeyword
    sequence: Sequence | Expression
    SINCE = sv(2009)


class AbortProperty(Property):
    """`accept_on(condition) operand`, or `reject_on`, `sync_accept_on` or `sync_reject_on` (16.12.14)."""

    keyword: AbortKeyword
    condition: Expression
    operand: Property | Expression
    SINCE = sv(2009)


class ConditionalProperty(Property):
    """`if (condition) consequence else alternative` (16.12.8)."""

    condition: Expression
    consequence: Property | Expression
    alternative: Property | Expression | None
    SINCE = sv()


class CaseProperty(Property):
    """`case (expression) items endcase` (16.12.8)."""

    expression: Expression
    items: list[PropertyCaseItem]
    SINCE = sv(2009)


class PropertyCaseItem(SyntaxNode):
    """`expressions: body;`, or `default: body;` without expressions, in a case property (16.12.8)."""

    expressions: list[Expression]
    body: Property | Expression
    SINCE = sv(2009)


class ParenthesizedProperty(Property):
    """`(property)`: a property in parentheses (16.12)."""

    property: Property | Expression
    SINCE = sv()


class ClockedProperty(Property):
    """`@(clock) property`, a property on its own clock (16.16)."""

    clock: EventControl
    property: Property | Expression
    SINCE = sv()


# --- Clocking blocks (14) ---


class ClockingDeclaration(Item):
    """`default clocking name @(event); items endclocking`, or `global` (14.3, 14.12, 14.14). A default clocking block
    may have no name. `labeled` repeats the name after `endclocking`."""

    scope: ClockingScope | None
    name: Identifier | None
    clock: EventControl
    items: list[DefaultSkew | ClockingSignals | PropertyDeclaration | SequenceDeclaration | LetDeclaration | Directive
                | Comment]
    labeled: bool
    SINCE = sv()
    FEATURES = {"scope": {"global": sv(2009)}}


class DefaultSkew(Item):
    """`default input skew output skew;` in a clocking block (14.3)."""

    input: ClockingSkew | None
    output: ClockingSkew | None
    SINCE = sv()


class ClockingSignals(Item):
    """`direction input_skew output_skew signals;` in a clocking block (14.3). Both skews are for `input output`;
    `inout` has none."""

    direction: ClockingDirection
    input_skew: ClockingSkew | None
    output_skew: ClockingSkew | None
    signals: list[ClockingSignal]
    SINCE = sv()


class ClockingSignal(SyntaxNode):
    """`name = value` in a clocking block: a signal, or with `value` an expression it stands for (14.5)."""

    name: Identifier
    value: Expression | None
    SINCE = sv()


class ClockingSkew(SyntaxNode):
    """`edge #delay`: when a clocking block samples or drives, relative to its clock (14.4). `#1step` is the time
    literal `1step`."""

    edge: Edge | None
    delay: DelayControl | None
    SINCE = sv()


class DefaultClocking(Item):
    """`default clocking name;`: the clocking block a scope's assertions and cycle delays use (14.12)."""

    name: Identifier
    SINCE = sv()


class DefaultDisable(Item):
    """`default disable iff condition;`: the reset of a scope's concurrent assertions (16.15)."""

    condition: Expression
    SINCE = sv(2009)


# === Coverage (19) ===


class CovergroupDeclaration(Item):
    """`covergroup name(ports) @(clock); items endgroup`, or sampled `with function sample(ports)` (19.3, 19.8.1).
    Its items are options, coverpoints and crosses. `labeled` repeats the name after `endgroup`."""

    name: Identifier
    ports: list[TfPort]
    clock: EventControl | None
    sample: SampleFunction | None
    items: list[CoverageOption | Coverpoint | CoverCross | Directive | Comment]
    labeled: bool
    SINCE = sv()

    def check(self) -> list[str]:
        return ["a CovergroupDeclaration has a clock or a sample, not both"] \
            if self.clock is not None and self.sample is not None else []


class SampleFunction(SyntaxNode):
    """`with function sample(ports)`: a covergroup sampled by calling `sample` with these arguments (19.8.1)."""

    ports: list[TfPort]
    SINCE = sv(2009)


class CoverageOption(Item):
    """`option.name = value;` or `type_option.name = value;`, in a covergroup, a coverpoint or a cross (19.7)."""

    target: Expression
    value: Expression
    SINCE = sv()


class Coverpoint(Item):
    """`type label: coverpoint expression iff (condition) { items }`: the values of an expression a covergroup
    counts, in its bins (19.5); a labeled coverpoint may give the type its values have. Without items, it ends with
    `;`."""

    label: Identifier | None
    type: DataType | None
    expression: Expression
    condition: Expression | None
    items: list[CoverageBins | CoverageOption | Directive | Comment]
    SINCE = sv()
    FEATURES = {"type": {True: sv(2012)}}

    def check(self) -> list[str]:
        return ["a Coverpoint with a type has a label"] if self.type is not None and self.label is None else []


class CoverageBins(Item):
    """`wildcard keyword name[size] = initializer iff (condition);`: a bin of a coverpoint, `bins`, `illegal_bins` or
    `ignore_bins` (19.5). With `array`, one bin per value, or `size` bins; `wildcard` lets `x`, `z` and `?` match any
    bit."""

    wildcard: bool
    keyword: BinsKeyword
    name: Identifier
    array: bool
    size: Expression | None
    initializer: BinsValues | BinsTransitions | BinsDefault | BinsExpression
    condition: Expression | None
    SINCE = sv()

    def check(self) -> list[str]:
        return ["a CoverageBins with a size is an array"] if self.size is not None and self.array is not True else []


class BinsValues(SyntaxNode):
    """`{ values } with (filter)`: the values a bin counts, which `filter` may thin out (19.5.1)."""

    values: list[Expression | Range]
    filter: Expression | None
    SINCE = sv()
    FEATURES = {"filter": {True: sv(2012)}}


class BinsTransitions(SyntaxNode):
    """`(sequence), (sequence)`: the sequences of values a bin counts (19.5.2)."""

    sequences: list[TransitionSequence]
    SINCE = sv()


class TransitionSequence(SyntaxNode):
    """`steps => steps => ...`: a sequence of values in a transition bin (19.5.2)."""

    steps: list[TransitionStep]
    SINCE = sv()


class TransitionStep(SyntaxNode):
    """`values[*count]`: one of the values, repeated `count` times consecutively (`*`), or not (`->`, `=`) (19.5.2)."""

    values: list[Expression | Range]
    operator: RepetitionOperator | None
    count: Expression | CycleRange | None
    SINCE = sv()

    def check(self) -> list[str]:
        return ["a TransitionStep has both an operator and a count, or neither"] \
            if (self.operator is None) != (self.count is None) else []


class BinsDefault(SyntaxNode):
    """`default`: the values no other bin counts; with `sequence`, the transitions (19.5.1)."""

    sequence: bool
    SINCE = sv()


class BinsExpression(SyntaxNode):
    """`expression with (filter)`: the values an expression gives, or a coverpoint's (`cp with (item > 1)`) (19.5.1)."""

    expression: Expression
    filter: Expression | None
    SINCE = sv(2012)


class CoverCross(Item):
    """`label: cross items iff (condition) { body }`: the combinations of coverpoints' bins a covergroup counts
    (19.6). Without a body, it ends with `;`."""

    label: Identifier | None
    items: list[Expression]
    condition: Expression | None
    body: list[BinsSelection | CoverageOption | FunctionDeclaration | Directive | Comment]
    SINCE = sv()


class BinsSelection(Item):
    """`keyword name = select iff (condition);`: a bin of a cross (19.6.1)."""

    keyword: BinsKeyword
    name: Identifier
    select: BinsSelect | Expression
    condition: Expression | None
    SINCE = sv()


class BinsOf(BinsSelect):
    """`binsof(target) intersect { values }`: the bins of a coverpoint, or one bin of it (`cp.low`), whose values
    intersect `values` (19.6.1)."""

    target: Expression
    intersect: list[Expression | Range]
    SINCE = sv()


class BinaryBinsSelect(BinsSelect):
    """`left && right` or `left || right` (19.6.1); slang groups both alike, to the left."""

    left: BinsSelect | Expression
    operator: BinsSelectOperator
    right: BinsSelect | Expression
    SINCE = sv()


class NotBinsSelect(BinsSelect):
    """`!operand` (19.6.1)."""

    operand: BinsSelect | Expression
    SINCE = sv()


class ParenthesizedBinsSelect(BinsSelect):
    """`(select)` (19.6.1)."""

    select: BinsSelect | Expression
    SINCE = sv()


class FilteredBinsSelect(BinsSelect):
    """`select with (filter)`: the combinations for which `filter` holds (19.6.1.2)."""

    select: BinsSelect | Expression
    filter: Expression
    SINCE = sv(2012)


# === Timing controls (9.4) ===


class DelayControl(TimingControl):
    """`#value`: a number, a time literal, a name or a parenthesized expression (9.4.1); or, of a net, a continuous
    assignment or a gate, `#(value, fall, turnoff)`, its rise, fall and turn-off delays (28.16)."""

    value: Expression
    fall: Expression | None
    turnoff: Expression | None

    def check(self) -> list[str]:
        return ["a DelayControl with a turnoff has a fall"] if self.turnoff is not None and self.fall is None else []


class CycleDelay(TimingControl):
    """`##value`: a number of ticks of the default clocking block (14.11)."""

    value: Expression
    SINCE = sv()


class RepeatEventControl(TimingControl):
    """`repeat (count) @(events)`, an intra-assignment event control that waits for `count` of them (9.4.5)."""

    count: Expression
    event: EventControl


class EventControl(TimingControl):
    """`@(events)`, joined by `or`, or `@(*)` without events (9.4.2)."""

    events: list[EventExpression]

    def features(self) -> list[tuple[str, Availability]]:
        return [("EventControl *", verilog(2001))] if not self.events else []


class EventExpression(SyntaxNode):
    """`edge expression iff condition` (9.4.2)."""

    edge: Edge | None
    expression: Expression
    condition: Expression | None
    FEATURES = {"edge": {"edge": sv()}, "condition": {True: sv()}}


# === Expressions (11) ===


class NameExpression(Expression):
    """A name used as a value (A.8.4)."""

    name: Name


class MemberExpression(Expression):
    """`value.member`: a structure's member, an interface's signal, or a step of a hierarchical name (7.2, 23.6)."""

    value: Expression
    member: Identifier


class IndexExpression(Expression):
    """`value[index]`: a bit select or an array element (11.5.1)."""

    value: Expression
    index: Expression


class RangeSelect(Expression):
    """`value[left:right]`, or an indexed part select `value[base+:width]` or `value[base-:width]` (11.5.1)."""

    value: Expression
    left: Expression
    operator: SelectOperator
    right: Expression
    FEATURES = {"operator": {"+:": verilog(2001), "-:": verilog(2001)}}


class IntegerLiteral(Literal):
    """An integer, spelled as written: size, signing, base and digits, with underscores, `x`, `z` and `?` (5.7.1)."""

    spelling: str


class RealLiteral(Literal):
    """A real number, spelled as written (5.7.2)."""

    spelling: str


class TimeLiteral(Literal):
    """A time, such as `10ns`, spelled as written (5.8)."""

    spelling: str
    SINCE = sv()


class UnbasedUnsizedLiteral(Literal):
    """`'0`, `'1`, `'x` or `'z`: every bit of its context's width (5.7.1)."""

    value: UnbasedValue
    SINCE = sv()


class StringLiteral(Literal):
    """`"text"`, or with `triple` `\"\"\"text\"\"\"`, spelled as written, escapes and line breaks included (5.9)."""

    text: str
    triple: bool
    FEATURES = {"triple": {True: sv(2023)}}


class UnaryExpression(Expression):
    """`operator operand`, including the reductions `&`, `~&`, `|`, `~|`, `^`, `~^` (11.4)."""

    operator: UnaryOperator
    attributes: list[AttributeInstance]
    operand: Expression
    FEATURES = {"attributes": {True: verilog(2001)}}


class IncrementExpression(Expression):
    """`++operand`, `--operand`, or with `postfix` `operand++`, `operand--` (11.4.2)."""

    operator: IncrementOperator
    postfix: bool
    operand: Expression
    attributes: list[AttributeInstance]
    SINCE = sv()


class BinaryExpression(Expression):
    """`left operator right` (11.4)."""

    left: Expression
    operator: BinaryOperator
    attributes: list[AttributeInstance]
    right: Expression
    FEATURES = {"operator": {"**": verilog(2001), "<<<": verilog(2001), ">>>": verilog(2001), "==?": sv(),
                             "!=?": sv(), "->": sv(2009), "<->": sv(2009)}, "attributes": {True: verilog(2001)}}


class AssignmentExpression(Expression):
    """`target operator value`: in a continuous assignment, a `for` loop's initializers and steps, or parenthesized as
    an expression (10.3, 11.4.1)."""

    target: Expression
    operator: AssignmentOperator
    value: Expression
    FEATURES = {"operator": {op: sv() for op in ("+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>=", "<<<=",
                                                 ">>>=")}}


class ConditionalExpression(Expression):
    """`condition ? consequence : alternative` (11.4.11)."""

    condition: Expression
    attributes: list[AttributeInstance]
    consequence: Expression
    alternative: Expression
    FEATURES = {"attributes": {True: verilog(2001)}}


class InsideExpression(Expression):
    """`value inside {set}` (11.4.13)."""

    value: Expression
    set: list[Expression | Range]
    SINCE = sv()


class ValueRange(Range):
    """`[left:right]` in a set (11.4.13), or with an `operator` a tolerance range: `[center +/- width]` or
    `[center +%- percent]`."""

    left: Expression
    operator: ToleranceOperator | None
    right: Expression
    SINCE = sv()
    FEATURES = {"operator": {True: sv(2023)}}


class Concatenation(Expression):
    """`{items}` (11.4.12)."""

    items: list[Expression]


class Replication(Expression):
    """`{count{items}}` (11.4.12.1)."""

    count: Expression
    items: list[Expression]


class AssignmentPattern(Expression):
    """`type'{items}` or `'{items}`: positional values, or `key: value` items, or with a `count` the positional values
    repeated (`'{2{a, b}}`) (10.9)."""

    type: DataType | None
    count: Expression | None
    items: list[Expression | PatternItem]
    SINCE = sv()

    def check(self) -> list[str]:
        if self.count is not None and any(isinstance(i, PatternItem) for i in self.items):
            return ["a repeated AssignmentPattern has positional items only"]
        return []


class PatternItem(SyntaxNode):
    """`key: value` in an assignment pattern, or `default: value` without a key (10.9.1)."""

    key: Expression | DataType | None
    value: Expression


class NullLiteral(Literal):
    """`null`, the handle of no object (8.4)."""

    SINCE = sv()


class ThisExpression(Expression):
    """`this`, the object a method runs on (8.11)."""

    SINCE = sv()


class SuperExpression(Expression):
    """`super`, the object a method runs on as its base class (8.15)."""

    SINCE = sv()


class NewExpression(Expression):
    """`new(arguments)`: a new object of the class the place it is assigned to has, or with `scope` of that class
    (`c#(8)::new`) or the base class's constructor (`super.new`) (8.7, 8.15). `new` without arguments is written
    without parentheses."""

    scope: Name | SuperExpression | None
    arguments: list[Expression | Connection]
    SINCE = sv()


class NewCopyExpression(Expression):
    """`new value`: a shallow copy of an object (8.12)."""

    value: Expression
    SINCE = sv()


class NewArrayExpression(Expression):
    """`new[size](value)`: a dynamic array of `size` elements, copying `value`'s first ones (7.5.1)."""

    size: Expression
    value: Expression | None
    SINCE = sv()


class RandomizeWithExpression(Expression):
    """`call with (variables) { constraints }`: a call of `randomize` (an object's, `std::randomize` or the class's own)
    with inline constraints (18.7). With `restricted`, the names `variables` lists (perhaps none) are the object's, and
    other names are looked up where the call is (18.7.1)."""

    call: Expression
    restricted: bool
    variables: list[Identifier]
    items: list[Constraint | Directive | Comment]
    SINCE = sv()
    FEATURES = {"restricted": {True: sv(2012)}}


class ArrayMethodWithExpression(Expression):
    """`call with (expression)`: an array manipulation method whose elements are `item`, or what its argument names,
    in `expression` (7.12)."""

    call: Expression
    expression: Expression
    SINCE = sv()


class CallExpression(Expression):
    """`callee(arguments)`: a function or method call (13.5); arguments are ordered expressions or named
    `NamedConnection`s."""

    callee: Expression
    attributes: list[AttributeInstance]
    arguments: list[Expression | Connection]
    FEATURES = {"attributes": {True: verilog(2001)}}


class SystemCall(Expression):
    """`$name(arguments)`: a system task or function call, such as `$display` or `$clog2` (20). An argument may be a
    data type, as `$bits` takes."""

    name: str
    attributes: list[AttributeInstance]
    arguments: list[Expression | DataType | EmptyArgument]
    FEATURES = {"attributes": {True: verilog(2001)}}

    def check(self) -> list[str]:
        name = self.name
        if type(name) is not str or not name:
            return []
        if name[0] != "$" or len(name) < 2 or not all(ch.isascii() and (ch.isalnum() or ch in "_$") for ch in name[1:]):
            return [f"{name!r} is not a system task or function name"]
        return []


class CastExpression(Expression):
    """`type'(value)`: a cast to a type, a width (`8'(x)`) or a signing (`signed'(x)`, an `ImplicitType`) (6.24.1)."""

    type: DataType | Expression
    value: Expression
    SINCE = sv()


class ParenthesizedExpression(Expression):
    """`(expression)` (A.8.4)."""

    expression: Expression


class MacroUsage(Expression):
    """`` `name `` or `` `name(arguments) ``, a text macro used as a value (22.5.1). `arguments` keeps the text between
    the parentheses."""

    name: Identifier
    arguments: str | None


class DollarExpression(Expression):
    """`$`, the last element of a queue or an unbounded range (7.10.1)."""

    SINCE = sv()


class TaggedExpression(Expression):
    """`tagged member value`: a tagged union's value, of one of its members (11.9)."""

    member: Identifier
    value: Expression | None
    SINCE = sv()


class MatchesExpression(Expression):
    """`value matches pattern`, a condition of an `if` or a `?:` that binds the pattern's variables there (12.6.2,
    12.6.3)."""

    value: Expression
    pattern: Pattern | Expression
    SINCE = sv()


class PredicateExpression(Expression):
    """`condition &&& condition ...`, conditions of an `if` or a `?:` that all hold, in order (12.6.2)."""

    conditions: list[Expression]
    SINCE = sv()

    def check(self) -> list[str]:
        return ["a PredicateExpression has two conditions or more"] if len(self.conditions) < 2 else []


class VariablePattern(Pattern):
    """`.name`: any value, bound to a variable of that name (12.6)."""

    name: Identifier
    SINCE = sv()


class WildcardPattern(Pattern):
    """`.*`: any value (12.6)."""

    SINCE = sv()


class TaggedPattern(Pattern):
    """`tagged member pattern`: a tagged union's value of that member, which matches the pattern (12.6)."""

    member: Identifier
    pattern: Pattern | Expression | None
    SINCE = sv()


class StructurePattern(Pattern):
    """`'{patterns}` or `'{member: pattern, ...}`: a structure's members, in order or by name (12.6)."""

    items: list[Pattern | Expression | PatternMember]
    SINCE = sv()

    def check(self) -> list[str]:
        named = [isinstance(i, PatternMember) for i in self.items]
        if any(named) and not all(named):
            return ["a StructurePattern's members are in order or by name, not both"]
        return []


class PatternMember(SyntaxNode):
    """`member: pattern` in a structure pattern (12.6)."""

    name: Identifier
    pattern: Pattern | Expression
    SINCE = sv()


class StreamingConcatenation(Expression):
    """`{>> slice {items}}` or `{<< slice {items}}`: items packed in a stream, in slices of `slice` bits or of a
    type's size, from the left or the right (11.4.14)."""

    operator: StreamOperator
    slice: Expression | DataType | None
    items: list[StreamItem]
    SINCE = sv()


class StreamItem(SyntaxNode):
    """`expression with [left operator right]`, an item of a streaming concatenation, of an array's elements `left`,
    `left:right`, `left+:right` or `left-:right` when it has a `with` (11.4.14.4)."""

    expression: Expression
    left: Expression | None
    operator: SelectOperator | None
    right: Expression | None
    SINCE = sv()
    FEATURES = {"left": {True: sv(2009)}}

    def check(self) -> list[str]:
        if (self.operator is None) != (self.right is None) or self.left is None and self.operator is not None:
            return ["a StreamItem's `with` has a left, and an operator and a right, or neither"]
        return []


class MinTypMaxExpression(Expression):
    """`min:typ:max`, a minimum, typical and maximum value, as delays have (11.11)."""

    min: Expression
    typ: Expression
    max: Expression


class EmptyArgument(Connection):
    """A port connection, an argument or a `foreach` loop's variable left out: `u i(a, , b)`, `f(a, , b)`,
    `$display(a,, b)`, `foreach (q[, j])` (23.3.2.2, 13.5, 12.7.3)."""


class RootExpression(Expression):
    """`$root`, the top of the design's hierarchy, where a hierarchical name starts (23.6)."""

    SINCE = sv()


class EmptyQueue(Expression):
    """`{}`, a queue or a dynamic array with no elements (7.10)."""

    SINCE = sv()


class InterfaceTypeName(Name):
    """`interface.name`: a type an interface port's interface declares, as `typedef` names it (6.18)."""

    interface: Identifier
    name: Identifier
    SINCE = sv()


class UnitName(Name):
    """`$unit`, the compilation unit, as a scope: `$unit::name` (26.3)."""

    SINCE = sv()


class TypeReference(DataType):
    """`type(operand)`: the type of an expression, or a type itself (6.23)."""

    operand: Expression | DataType
    SINCE = sv()


# === Compiler directives (22) ===


class IncludeDirective(Directive):
    """`` `include "path" ``, or `` `include <path> `` when `system` (22.4)."""

    path: str
    system: bool
    FEATURES = {"system": {True: sv(2009)}}


class DefineDirective(Directive):
    """`` `define name body ``, or with `function_like` `` `define name(parameters) body `` (22.5.1). `body` keeps its
    text, line continuations included."""

    name: Identifier
    function_like: bool
    parameters: list[Identifier]
    body: str


class UndefDirective(Directive):
    """`` `undef name `` (22.5.2)."""

    name: Identifier


class TimescaleDirective(Directive):
    """`` `timescale unit / precision ``, each a magnitude and a unit, such as `1ns` (22.7)."""

    unit: str
    precision: str


class DefaultNettypeDirective(Directive):
    """`` `default_nettype net_type ``, or `none` (22.8)."""

    net_type: DefaultNettype
    FEATURES = {"net_type": {"none": verilog(2001), "uwire": verilog(2005)}}


class IfdefDirective(Directive):
    """`` `ifdef name items `elsif name items `else items `endif ``, or `` `ifndef `` when `negated`, as a tree of its
    branches (22.6). Branches hold what their place lists: items, statements or constraints. A branch the reading did
    not take ends with its text as written, a `DisabledText`. In place of a name, a `condition` combines macros'
    names with `!`, `&&`, `||`, `->`, `<->` and parentheses: `` `ifdef (A && !B) ``."""

    negated: bool
    name: Identifier | None
    condition: Expression | None
    items: list[Item | Statement | Constraint | Directive | Comment]
    branches: list[ElsifDirective]
    alternative: list[Item | Statement | Constraint | Directive | Comment]
    has_else: bool
    FEATURES = {"condition": {True: sv(2023)}}

    def check(self) -> list[str]:
        return _condition_problems(self)


class ElsifDirective(Directive):
    """`` `elsif name items `` or `` `elsif (condition) items ``, a branch of an `IfdefDirective` (22.6)."""

    name: Identifier | None
    condition: Expression | None
    items: list[Item | Statement | Constraint | Directive | Comment]
    SINCE = verilog(2001)
    FEATURES = {"condition": {True: sv(2023)}}

    def check(self) -> list[str]:
        return _condition_problems(self)


def _condition_problems(directive: IfdefDirective | ElsifDirective) -> list[str]:
    """A directive has a name or a condition, and a condition only macros' names and `!`, `&&`, `||`, `->`, `<->`."""
    kind = type(directive).__name__
    if (directive.name is None) == (directive.condition is None):
        return [f"an {kind} has a name or a condition"]
    if directive.condition is not None and not isinstance(directive.condition, ParenthesizedExpression):
        return [f"an {kind}'s condition is in parentheses"]
    nodes = [directive.condition] if directive.condition is not None else []
    while nodes:
        node = nodes.pop()
        if isinstance(node, ParenthesizedExpression):
            nodes.append(node.expression)
        elif isinstance(node, UnaryExpression) and node.operator == "!" and not node.attributes:
            nodes.append(node.operand)
        elif isinstance(node, BinaryExpression) and node.operator in ("&&", "||", "->", "<->") and not node.attributes:
            nodes.extend([node.left, node.right])
        elif not (isinstance(node, NameExpression) and isinstance(node.name, Identifier)):
            return [f"an {kind}'s condition has macros' names, !, &&, ||, -> and <-> only"]
    return []


class DisabledText(Directive):
    """The text of a conditional branch the preprocessor skipped, as written: it is not parsed, since which branch is
    taken depends on the macros defined (22.6)."""

    text: str


class OtherDirective(Directive):
    """Any other directive, as written: `` `resetall ``, `` `celldefine ``, `` `line ``, ... (22)."""

    text: str


# --- The language ---

KINDS: list[type[SyntaxNode]] = [
    Comment, Identifier, ScopedName, ParameterizedName, AttributeInstance, AttributeSpec, AttributedItem,
    AttributedStatement, AttributedPort,
    SourceText, ModuleDeclaration, InterfaceDeclaration, ProgramDeclaration, CheckerDeclaration, PackageDeclaration,
    AnsiPort, InterfacePort, PortReference, PortConcatenation, ExplicitPort, WildcardPort, EmptyPort, ExplicitAnsiPort,
    PortDeclaration,
    ParameterDeclaration, ParamAssignment, TypeParameterDeclaration, TypeAssignment,
    IntegerVectorType, IntegerAtomType, NonIntegerType, KeywordType, NamedType, VirtualInterfaceType, ImplicitType,
    StructType, StructMember,
    EnumType, EnumMember,
    RangeDimension, SizeDimension, UnsizedDimension, AssociativeDimension, QueueDimension,
    NetDeclaration, DriveStrength, ChargeStrength, VariableDeclaration, VariableDeclarator,
    ForwardTypedefDeclaration, TypedefDeclaration, EmptyItem, DpiImport, DpiExport, BindDirective,
    ElaborationTask, GenvarDeclaration, ImportDeclaration,
    ExportDeclaration, ImportItem,
    NetTypeDeclaration, NetAlias, DefParam, DefParamAssignment, TimeUnitsDeclaration, ModportDeclaration, ModportItem,
    ModportPort, ModportSubroutine, ModportClocking, ContinuousAssign, AlwaysConstruct, InitialConstruct,
    FinalConstruct, FunctionDeclaration, TaskDeclaration, TfPort, ClassDeclaration,
    GenerateRegion, GenerateFor, GenerateIf, GenerateCase, GenerateBlock,
    ModuleInstantiation, Instance, NamedConnection, WildcardConnection, GateInstantiation, GateInstance, PullStrength,
    UdpDeclaration, UdpPort, UdpInitial, UdpEntry,
    AssignmentStatement, ExpressionStatement, NullStatement, SeqBlock, ParBlock, IfStatement, CaseStatement, CaseItem,
    PatternCaseItem,
    ForStatement, WhileStatement, DoWhileStatement, RepeatStatement, ForeverStatement, ForeachStatement,
    BreakStatement, ContinueStatement, ReturnStatement, TimedStatement, WaitStatement, EventTrigger, DisableStatement,
    ForceStatement, ReleaseStatement, CheckerStatement, WaitForkStatement, WaitOrderStatement, RandSequenceStatement,
    Production,
    ProductionRule, ProductionCall, ProductionCode, ProductionIf, ProductionRepeat, ProductionCase, ProductionCaseItem,
    ImmediateAssertion,
    DelayControl, RepeatEventControl, EventControl, EventExpression,
    NameExpression, MemberExpression, IndexExpression, RangeSelect, IntegerLiteral, RealLiteral, TimeLiteral,
    UnbasedUnsizedLiteral, StringLiteral, UnaryExpression, IncrementExpression, BinaryExpression, AssignmentExpression,
    ConditionalExpression, InsideExpression, ValueRange, Concatenation, Replication, AssignmentPattern, PatternItem,
    CallExpression, SystemCall, CastExpression, ParenthesizedExpression, MacroUsage, DollarExpression,
    TaggedExpression, MatchesExpression, PredicateExpression, VariablePattern, WildcardPattern, TaggedPattern,
    StructurePattern, PatternMember, StreamingConcatenation, StreamItem, MinTypMaxExpression, EmptyArgument,
    RootExpression, EmptyQueue,
    InterfaceTypeName, UnitName,
    TypeReference,
    NullLiteral, ThisExpression, SuperExpression, NewExpression, NewCopyExpression, NewArrayExpression,
    RandomizeWithExpression, ArrayMethodWithExpression, DistExpression, DistItem, LocalName,
    ConstraintDeclaration, ConstraintPrototype, ConstraintBlock, ExpressionConstraint, ImplicationConstraint,
    ConditionalConstraint, ForeachConstraint, SolveBeforeConstraint, DisableSoftConstraint, UniqueConstraint,
    RandCaseStatement, RandCaseItem,
    LabeledStatement, ConcurrentAssertion, ExpectStatement, AssertionItem, PropertySpec, PropertyDeclaration,
    SequenceDeclaration, LetDeclaration, AssertionPort, DelaySequence, DelayStep, CycleRange, RepetitionSequence,
    BinarySequence, ParenthesizedSequence, FirstMatchSequence, ClockedSequence, ImplicationProperty, BinaryProperty,
    UnaryProperty, StrengthProperty, AbortProperty, ConditionalProperty, CaseProperty, PropertyCaseItem,
    ParenthesizedProperty, ClockedProperty, ClockingDeclaration, DefaultSkew, ClockingSignals, ClockingSignal,
    ClockingSkew, DefaultClocking, DefaultDisable, CycleDelay,
    CovergroupDeclaration, SampleFunction, CoverageOption, Coverpoint, CoverageBins, BinsValues, BinsTransitions,
    TransitionSequence, TransitionStep, BinsDefault, BinsExpression, CoverCross, BinsSelection, BinsOf,
    BinaryBinsSelect, NotBinsSelect, ParenthesizedBinsSelect, FilteredBinsSelect,
    IncludeDirective, DefineDirective, UndefDirective, TimescaleDirective, DefaultNettypeDirective, IfdefDirective,
    ElsifDirective, DisabledText, OtherDirective,
]

LANGUAGE = Language("Verilog", KINDS, base={VERILOG: 1995, SV: 2005})

__all__ += [k.__name__ for k in KINDS] + [
    "Name", "Expression", "Literal", "DataType", "Dimension", "Item", "Port", "Statement", "TimingControl",
    "Connection", "Range", "Directive", "Constraint", "Property", "Sequence", "BinsSelect", "sv", "verilog", "VERILOG",
    "SV"]
