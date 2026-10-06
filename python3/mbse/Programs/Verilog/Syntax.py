"""Syntax: the abstract syntax of Verilog and SystemVerilog, as one tree language (Verilog), organized as IEEE 1800's
grammar is.

The kinds cover the design subset of SystemVerilog (IEEE 1800-2023): design units, ports and parameters, data types,
declarations, continuous assignments, procedural blocks and statements, generate constructs, instantiation, functions
and tasks, immediate assertions and compiler directives. Verilog (IEEE 1364) is a family of its own whose standards have
fewer of them: each kind and feature records where it exists in both families (`SINCE`, `FEATURES`), which
`Verilog2005`, `SystemVerilog2017`, `SystemVerilog2023` and `VerilogStandard(year, family)` check. Verification
constructs (classes, constraints, properties and sequences, covergroups) are not kinds yet.

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
SimpleKeyword = Choice["string", "chandle", "event", "void"]
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
    """`scope::name`: a name in a package, or `$unit` (26.3)."""

    scope: Identifier
    name: Name
    SINCE = sv()


# === Source text (A.1) ===


class SourceText(SyntaxNode):
    """A source file: design units, declarations, directives and comments (3.12, A.1.2)."""

    items: list[Item | Directive | Comment]


class ModuleDeclaration(Item):
    """`module name #(parameters) (ports); items endmodule` (23.2). Parameters in the header are listed even when
    empty; ports are `AnsiPort`s or `InterfacePort`s, or for a non-ANSI header `PortReference`s, which `PortDeclaration`
    items declare. `labeled` repeats the name after `endmodule`."""

    keyword: ModuleKeyword
    lifetime: Lifetime | None
    name: Identifier
    imports: list[ImportDeclaration]
    parameters: list[ParameterDeclaration | TypeParameterDeclaration]
    ports: list[Port]
    items: list[Item | Directive | Comment]
    labeled: bool
    FEATURES = {"lifetime": {True: verilog(2001)}, "imports": {True: sv(2009)}, "labeled": {True: sv()}}


class InterfaceDeclaration(Item):
    """`interface name #(parameters) (ports); items endinterface` (25.3)."""

    lifetime: Lifetime | None
    name: Identifier
    imports: list[ImportDeclaration]
    parameters: list[ParameterDeclaration | TypeParameterDeclaration]
    ports: list[Port]
    items: list[Item | Directive | Comment]
    labeled: bool
    SINCE = sv()
    FEATURES = {"imports": {True: sv(2009)}}


class ProgramDeclaration(Item):
    """`program name #(parameters) (ports); items endprogram` (24.3)."""

    lifetime: Lifetime | None
    name: Identifier
    imports: list[ImportDeclaration]
    parameters: list[ParameterDeclaration | TypeParameterDeclaration]
    ports: list[Port]
    items: list[Item | Directive | Comment]
    labeled: bool
    SINCE = sv()
    FEATURES = {"imports": {True: sv(2009)}}


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
    """A non-ANSI header's port, named in the header and declared by a `PortDeclaration` item (23.2.2.1)."""

    name: Identifier


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
    entry, and a `parameter` there may give no value."""

    keyword: ParameterKeyword
    type: DataType | None
    assignments: list[ParamAssignment]
    FEATURES = {"keyword": {"localparam": verilog(2001)}}


class ParamAssignment(SyntaxNode):
    """`name dimensions = value` in a parameter declaration (A.2.4)."""

    name: Identifier
    dimensions: list[Dimension]
    value: Expression | None


class TypeParameterDeclaration(Item):
    """`parameter type name = type, ...` or `localparam type ...` (6.20.3)."""

    keyword: ParameterKeyword
    assignments: list[TypeAssignment]
    SINCE = sv()


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
    """`string`, `chandle`, `event` or `void` (6.16, 6.14, 6.17, 6.13)."""

    keyword: SimpleKeyword
    FEATURES = {"keyword": {"string": sv(), "chandle": sv(), "void": sv()}}


class NamedType(DataType):
    """A type by its name: a typedef, a type parameter or an interface's type, with packed dimensions (6.18)."""

    name: Name
    dimensions: list[Dimension]
    SINCE = sv()


class ImplicitType(DataType):
    """The type a declaration gives by a signing and packed dimensions alone, such as `input [7:0] a` (6.10); also
    the `signed` or `unsigned` of a cast."""

    signing: Signing | None
    dimensions: list[Dimension]
    FEATURES = {"signing": {"signed": verilog(2001), "unsigned": sv()}}


class StructType(DataType):
    """`struct packed signed { members }` or `union ...`, with packed dimensions (7.2, 7.3)."""

    keyword: Choice["struct", "union"]
    packed: bool
    signing: Signing | None
    members: list[StructMember]
    dimensions: list[Dimension]
    SINCE = sv()


class StructMember(SyntaxNode):
    """`type declarators;` in a structure or union (7.2)."""

    type: DataType
    declarators: list[VariableDeclarator]


class EnumType(DataType):
    """`enum base { members }`, with packed dimensions (6.19)."""

    base: DataType | None
    members: list[EnumMember]
    dimensions: list[Dimension]
    SINCE = sv()


class EnumMember(SyntaxNode):
    """`name = value` in an enumeration (6.19)."""

    name: Identifier
    value: Expression | None


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
    """`net_type type #delay declarators;` (6.7)."""

    net_type: NetType
    type: DataType | None
    delay: DelayControl | None
    declarators: list[VariableDeclarator]
    FEATURES = {"net_type": {"uwire": verilog(2005), "interconnect": sv(2012)}}


class VariableDeclaration(Item):
    """`const var lifetime type declarators;` (6.8)."""

    const: bool
    var: bool
    lifetime: Lifetime | None
    type: DataType | None
    declarators: list[VariableDeclarator]
    FEATURES = {"const": {True: sv()}, "var": {True: sv()}, "lifetime": {True: sv()}}


class VariableDeclarator(SyntaxNode):
    """`name dimensions = value` in a net, variable, port or member declaration (A.2.3)."""

    name: Identifier
    dimensions: list[Dimension]
    value: Expression | None


class TypedefDeclaration(Item):
    """`typedef type name dimensions;` (6.18)."""

    type: DataType
    name: Identifier
    dimensions: list[Dimension]
    SINCE = sv()


class GenvarDeclaration(Item):
    """`genvar names;` (27.4)."""

    names: list[Identifier]
    SINCE = verilog(2001)


class ImportDeclaration(Item):
    """`import package::name, package::*;` (26.3)."""

    items: list[ImportItem]
    SINCE = sv()


class ImportItem(SyntaxNode):
    """`package::name`, or `package::*` without a `name` (26.3)."""

    package: Identifier
    name: Identifier | None


class ModportDeclaration(Item):
    """`modport items;` in an interface (25.5)."""

    items: list[ModportItem]
    SINCE = sv()


class ModportItem(SyntaxNode):
    """`name (ports)` in a modport declaration (25.5)."""

    name: Identifier
    ports: list[ModportPort]


class ModportPort(SyntaxNode):
    """`direction name` in a modport (25.5)."""

    direction: Direction
    name: Identifier


class ContinuousAssign(Item):
    """`assign #delay target = value, ...;` (10.3)."""

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
    order. Without ports in parentheses, Verilog-1995 style, `PortDeclaration`s in the body declare them."""

    lifetime: Lifetime | None
    type: DataType | None
    name: Name
    ports: list[TfPort]
    body: list[Item | Statement | Directive | Comment]
    labeled: bool
    FEATURES = {"lifetime": {True: verilog(2001)}, "labeled": {True: sv()}}


class TaskDeclaration(Item):
    """`task lifetime name(ports); body endtask` (13.3)."""

    lifetime: Lifetime | None
    name: Name
    ports: list[TfPort]
    body: list[Item | Statement | Directive | Comment]
    labeled: bool
    FEATURES = {"lifetime": {True: verilog(2001)}, "labeled": {True: sv()}}


class TfPort(SyntaxNode):
    """`direction var type name dimensions = default`, a task's or function's port in parentheses (13.3). Without a
    direction or a type, a port inherits them from the one before it."""

    direction: Direction | None
    var: bool
    type: DataType | None
    name: Identifier
    dimensions: list[Dimension]
    value: Expression | None
    SINCE = verilog(2001)
    FEATURES = {"var": {True: sv()}, "value": {True: sv()}, "direction": {"ref": sv()}}


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


class ModuleInstantiation(Item):
    """`module #(parameters) instance (connections), ...;`, of a module, an interface or a program (23.3).
    Parameters and connections are ordered expressions or `NamedConnection`s."""

    module: Identifier
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
    """`qualifier case (expression) inside items endcase`, or `casez` or `casex` (12.5)."""

    qualifier: Qualifier | None
    keyword: CaseKeyword
    expression: Expression
    inside: bool
    items: list[CaseItem]
    FEATURES = {"qualifier": {"unique": sv(), "priority": sv(), "unique0": sv(2009)}, "inside": {True: sv()}}


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
    """`foreach (array[variables]) body` (12.7.3)."""

    array: Expression
    variables: list[Identifier]
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
    """`-> event;`, or `->> event;` when `nonblocking` (15.5.1)."""

    nonblocking: bool
    event: Expression
    FEATURES = {"nonblocking": {True: sv()}}


class DisableStatement(Statement):
    """`disable target;`, or `disable fork;` without a target (9.6.2, 9.6.3)."""

    target: Expression | None

    def features(self) -> list[tuple[str, Availability]]:
        return [("DisableStatement fork", sv())] if self.target is None else []


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


# === Timing controls (9.4) ===


class DelayControl(TimingControl):
    """`#value`: a number, a time literal, a name or a parenthesized expression (9.4.1)."""

    value: Expression


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
    operand: Expression


class IncrementExpression(Expression):
    """`++operand`, `--operand`, or with `postfix` `operand++`, `operand--` (11.4.2)."""

    operator: IncrementOperator
    postfix: bool
    operand: Expression
    SINCE = sv()


class BinaryExpression(Expression):
    """`left operator right` (11.4)."""

    left: Expression
    operator: BinaryOperator
    right: Expression
    FEATURES = {"operator": {"**": verilog(2001), "<<<": verilog(2001), ">>>": verilog(2001), "==?": sv(),
                             "!=?": sv(), "->": sv(2009), "<->": sv(2009)}}


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
    consequence: Expression
    alternative: Expression


class InsideExpression(Expression):
    """`value inside {set}` (11.4.13)."""

    value: Expression
    set: list[Expression | Range]
    SINCE = sv()


class ValueRange(Range):
    """`[left:right]` in a set (11.4.13)."""

    left: Expression
    right: Expression
    SINCE = sv()


class Concatenation(Expression):
    """`{items}` (11.4.12)."""

    items: list[Expression]


class Replication(Expression):
    """`{count{items}}` (11.4.12.1)."""

    count: Expression
    items: list[Expression]


class AssignmentPattern(Expression):
    """`type'{items}` or `'{items}`: positional values, or `key: value` items (10.9)."""

    type: DataType | None
    items: list[Expression | PatternItem]
    SINCE = sv()


class PatternItem(SyntaxNode):
    """`key: value` in an assignment pattern, or `default: value` without a key (10.9.1)."""

    key: Expression | DataType | None
    value: Expression


class CallExpression(Expression):
    """`callee(arguments)`: a function or method call (13.5); arguments are ordered expressions or named
    `NamedConnection`s."""

    callee: Expression
    arguments: list[Expression | Connection]


class SystemCall(Expression):
    """`$name(arguments)`: a system task or function call, such as `$display` or `$clog2` (20). An argument may be a
    data type, as `$bits` takes."""

    name: str
    arguments: list[Expression | DataType]

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
    branches (22.6). Branches hold what their place lists: items, or statements. A branch the reading did not take
    ends with its text as written, a `DisabledText`."""

    negated: bool
    name: Identifier
    items: list[Item | Statement | Directive | Comment]
    branches: list[ElsifDirective]
    alternative: list[Item | Statement | Directive | Comment]
    has_else: bool


class ElsifDirective(Directive):
    """`` `elsif name items ``, a branch of an `IfdefDirective` (22.6)."""

    name: Identifier
    items: list[Item | Statement | Directive | Comment]
    SINCE = verilog(2001)


class DisabledText(Directive):
    """The text of a conditional branch the preprocessor skipped, as written: it is not parsed, since which branch is
    taken depends on the macros defined (22.6)."""

    text: str


class OtherDirective(Directive):
    """Any other directive, as written: `` `resetall ``, `` `celldefine ``, `` `line ``, ... (22)."""

    text: str


# --- The language ---

KINDS: list[type[SyntaxNode]] = [
    Comment, Identifier, ScopedName,
    SourceText, ModuleDeclaration, InterfaceDeclaration, ProgramDeclaration, PackageDeclaration,
    AnsiPort, InterfacePort, PortReference, PortDeclaration,
    ParameterDeclaration, ParamAssignment, TypeParameterDeclaration, TypeAssignment,
    IntegerVectorType, IntegerAtomType, NonIntegerType, KeywordType, NamedType, ImplicitType, StructType, StructMember,
    EnumType, EnumMember,
    RangeDimension, SizeDimension, UnsizedDimension, AssociativeDimension, QueueDimension,
    NetDeclaration, VariableDeclaration, VariableDeclarator, TypedefDeclaration, GenvarDeclaration, ImportDeclaration,
    ImportItem, ModportDeclaration, ModportItem, ModportPort, ContinuousAssign, AlwaysConstruct, InitialConstruct,
    FinalConstruct, FunctionDeclaration, TaskDeclaration, TfPort,
    GenerateRegion, GenerateFor, GenerateIf, GenerateCase, GenerateBlock,
    ModuleInstantiation, Instance, NamedConnection, WildcardConnection,
    AssignmentStatement, ExpressionStatement, NullStatement, SeqBlock, ParBlock, IfStatement, CaseStatement, CaseItem,
    ForStatement, WhileStatement, DoWhileStatement, RepeatStatement, ForeverStatement, ForeachStatement,
    BreakStatement, ContinueStatement, ReturnStatement, TimedStatement, WaitStatement, EventTrigger, DisableStatement,
    ImmediateAssertion,
    DelayControl, EventControl, EventExpression,
    NameExpression, MemberExpression, IndexExpression, RangeSelect, IntegerLiteral, RealLiteral, TimeLiteral,
    UnbasedUnsizedLiteral, StringLiteral, UnaryExpression, IncrementExpression, BinaryExpression, AssignmentExpression,
    ConditionalExpression, InsideExpression, ValueRange, Concatenation, Replication, AssignmentPattern, PatternItem,
    CallExpression, SystemCall, CastExpression, ParenthesizedExpression, MacroUsage, DollarExpression,
    IncludeDirective, DefineDirective, UndefDirective, TimescaleDirective, DefaultNettypeDirective, IfdefDirective,
    ElsifDirective, DisabledText, OtherDirective,
]

LANGUAGE = Language("Verilog", KINDS, base={VERILOG: 1995, SV: 2005})

__all__ += [k.__name__ for k in KINDS] + [
    "Name", "Expression", "Literal", "DataType", "Dimension", "Item", "Port", "Statement", "TimingControl",
    "Connection", "Range", "Directive", "sv", "verilog", "VERILOG", "SV"]
