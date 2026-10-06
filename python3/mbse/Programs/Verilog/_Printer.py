"""Prints Verilog trees as SystemVerilog source text, in one fixed layout.

The layout: four spaces per level, `begin` on the line it opens and `end else begin`, one item or statement per line,
a design unit's parameters and ports one per line, directives at the start of their line, and a blank line around
items that span several lines. Parentheses written in the tree are printed; those a tree built by hand needs are added,
by the precedence of IEEE 1800's Table 11-2. The printer assumes a valid tree: standards validate before they print.
"""

from __future__ import annotations

from typing import Any

from . import Syntax as S

__all__ = ["Printer"]

_INDENT = "    "

# Precedence (Table 11-2): higher binds tighter.
IMPLY, CONDITIONAL, OR, AND, BOR, BXOR, BAND, EQUALITY, RELATIONAL, SHIFT, ADDITIVE, MULTIPLICATIVE, POWER, UNARY, \
    PRIMARY = range(1, 16)
_BINARY = {
    "->": IMPLY, "<->": IMPLY, "||": OR, "&&": AND, "|": BOR, "^": BXOR, "^~": BXOR, "~^": BXOR, "&": BAND,
    "==": EQUALITY, "!=": EQUALITY, "===": EQUALITY, "!==": EQUALITY, "==?": EQUALITY, "!=?": EQUALITY,
    "<": RELATIONAL, "<=": RELATIONAL, ">": RELATIONAL, ">=": RELATIONAL, "<<": SHIFT, ">>": SHIFT, "<<<": SHIFT,
    ">>>": SHIFT, "+": ADDITIVE, "-": ADDITIVE, "*": MULTIPLICATIVE, "/": MULTIPLICATIVE, "%": MULTIPLICATIVE,
    "**": POWER,
}
_RIGHT = {IMPLY, CONDITIONAL}  # right-associative levels


def _precedence(node: Any) -> int:
    if isinstance(node, S.BinaryExpression):
        return _BINARY[node.operator]
    if isinstance(node, S.InsideExpression):
        return RELATIONAL
    if isinstance(node, S.ConditionalExpression):
        return CONDITIONAL
    if isinstance(node, (S.UnaryExpression, S.IncrementExpression)):
        return UNARY
    if isinstance(node, S.AssignmentExpression):
        return 0
    return PRIMARY


def _prototype(node: Any) -> bool:
    """Whether a function or task is a prototype, without a body: `extern` or `pure`."""
    return node.extern or node.pure


def _multiline(node: Any) -> bool:
    if isinstance(node, (S.FunctionDeclaration, S.TaskDeclaration)):
        return not _prototype(node)
    return isinstance(node, (S.ModuleDeclaration, S.InterfaceDeclaration, S.ProgramDeclaration, S.PackageDeclaration,
                             S.ClassDeclaration, S.AlwaysConstruct, S.InitialConstruct, S.FinalConstruct,
                             S.GenerateRegion, S.GenerateFor, S.GenerateIf, S.GenerateCase, S.GenerateBlock,
                             S.IfdefDirective))


class Printer:
    """Prints source text as a file, and any other syntax node as the text it stands for: an item or a statement as
    its lines, an expression or a part (a port, a dimension, ...) as its text."""

    def print(self, node: Any) -> str:
        if isinstance(node, S.SourceText):
            return "".join(line + "\n" for line in self.items(node.items, 0))
        if isinstance(node, (S.Item, S.Statement, S.Directive, S.Comment)):
            return "\n".join(self.item(node, 0))
        return self.text(node)

    # Lists of items and statements

    def items(self, items: list[Any], level: int, after: list[str] | None = None) -> list[str]:
        """The lines of a list of items. A trailing comment ends the line before it: for the first item, the last line
        of `after`, the header the items follow."""
        lines: list[str] = []
        previous_multiline = False
        for i, item in enumerate(items):
            host = lines if lines else after
            if isinstance(item, S.Comment) and item.trailing and host:
                host[-1] += "  " + self.comment(item)
                continue
            starts = _multiline(item) and not self.led(items, i) or isinstance(item, S.Comment) and self.leads(items, i)
            if lines and (previous_multiline or starts):
                lines.append("")
            lines.extend(self.item(item, level))
            previous_multiline = _multiline(item)
        return lines

    @staticmethod
    def leads(items: list[Any], i: int) -> bool:
        """Whether the comment `items[i]` starts the comments directly before a multi-line item."""
        j = i
        while j < len(items) and isinstance(items[j], S.Comment):
            j += 1
        return j < len(items) and _multiline(items[j]) and (
            i == 0 or not isinstance(items[i - 1], S.Comment) or items[i - 1].trailing)

    @staticmethod
    def led(items: list[Any], i: int) -> bool:
        return i > 0 and isinstance(items[i - 1], S.Comment) and not items[i - 1].trailing

    def comment(self, node: S.Comment) -> str:
        return f"/*{node.text}*/" if node.block else f"//{node.text}"

    def item(self, node: Any, level: int) -> list[str]:
        pad = _INDENT * level
        if isinstance(node, S.Comment):
            return [pad + line if i == 0 else line for i, line in enumerate(self.comment(node).split("\n"))]
        if isinstance(node, S.Directive):
            return self.directive(node, level)
        if isinstance(node, S.Statement):
            return self.statement(node, level)
        method = self.ITEMS[type(node)]
        return method(self, node, level)

    # Directives

    def directive(self, node: Any, level: int) -> list[str]:
        if isinstance(node, S.IfdefDirective):
            lines = [f"`{'ifndef' if node.negated else 'ifdef'} {node.name.spelling}"]
            lines.extend(self.branch(node.items, level))
            for branch in node.branches:
                lines.append(f"`elsif {branch.name.spelling}")
                lines.extend(self.branch(branch.items, level))
            if node.has_else:
                lines.append("`else")
                lines.extend(self.branch(node.alternative, level))
            lines.append("`endif")
            return lines
        if isinstance(node, S.DisabledText):
            return node.text.split("\n")
        if isinstance(node, S.IncludeDirective):
            return [f"`include <{node.path}>" if node.system else f'`include "{node.path}"']
        if isinstance(node, S.DefineDirective):
            parameters = f"({', '.join(p.spelling for p in node.parameters)})" if node.function_like else ""
            return [f"`define {node.name.spelling}{parameters}" + (f" {node.body}" if node.body else "")]
        if isinstance(node, S.UndefDirective):
            return [f"`undef {node.name.spelling}"]
        if isinstance(node, S.TimescaleDirective):
            return [f"`timescale {node.unit} / {node.precision}"]
        if isinstance(node, S.DefaultNettypeDirective):
            return [f"`default_nettype {node.net_type}"]
        return [node.text]  # an OtherDirective: the tree is valid, so nothing else is here

    def branch(self, items: list[Any], level: int) -> list[str]:
        out: list[str] = []
        for item in items:
            if isinstance(item, S.Statement):
                out.extend(self.statement(item, level))
            else:
                out.extend(self.item(item, level))
        return out

    # Design units

    def design_unit(self, node: Any, level: int) -> list[str]:
        pad = _INDENT * level
        keyword = {S.ModuleDeclaration: getattr(node, "keyword", None) or "module", S.InterfaceDeclaration: "interface",
                   S.ProgramDeclaration: "program", S.PackageDeclaration: "package"}[type(node)]
        end = {"module": "endmodule", "macromodule": "endmodule", "interface": "endinterface", "program": "endprogram",
               "package": "endpackage"}[keyword]
        head = f"{pad}{keyword}{f' {node.lifetime}' if node.lifetime else ''} {node.name.spelling}"
        lines: list[str] = []
        imports = getattr(node, "imports", [])
        if imports:
            lines.append(head)
            lines.extend(f"{pad}{_INDENT}{self.import_text(i)};" for i in imports)
            head = pad
        parameters = getattr(node, "parameters", [])
        ports = getattr(node, "ports", [])
        if parameters:
            lines.append(head + ("#(" if head == pad else " #("))
            lines.extend(f"{pad}{_INDENT}{self.parameter_text(p)}{',' if i < len(parameters) - 1 else ''}"
                         for i, p in enumerate(parameters))
            head = pad + ")"
        if ports and all(isinstance(p, S.PortReference) for p in ports):  # a non-ANSI header's names, on one line
            names = ", ".join(p.name.spelling for p in ports)
            lines.append((head + " (" if head.strip() else head + "(") + names + ");")
            lines.extend(self.items(node.items, level + 1, after=lines))
            lines.append(f"{pad}{end}" + (f" : {node.name.spelling}" if node.labeled else ""))
            return lines
        if ports:
            lines.append(head + " (" if head.strip() else head + "(")
            lines.extend(f"{pad}{_INDENT}{self.port(p)}{',' if i < len(ports) - 1 else ''}"
                         for i, p in enumerate(ports))
            head = pad + ")"
        lines.append(head + ";")
        lines.extend(self.items(node.items, level + 1, after=lines))
        lines.append(f"{pad}{end}" + (f" : {node.name.spelling}" if node.labeled else ""))
        return lines

    def port(self, node: Any) -> str:
        if isinstance(node, S.PortReference):
            return node.name.spelling
        dimensions = "".join(self.dimension(d) for d in node.dimensions)
        if isinstance(node, S.InterfacePort):
            interface = node.interface.spelling if node.interface is not None else "interface"
            modport = f".{node.modport.spelling}" if node.modport is not None else ""
            return f"{interface}{modport} {node.name.spelling}{dimensions}"
        parts = [node.direction, node.net_type, "var" if node.var else None, self.type_text(node.type)
                 if node.type is not None else None]
        head = " ".join(p for p in parts if p)
        value = f" = {self.text(node.value)}" if node.value is not None else ""
        return (head + " " if head else "") + node.name.spelling + dimensions + value

    def port_declaration(self, node: S.PortDeclaration, level: int) -> list[str]:
        parts = [node.direction, node.net_type, "var" if node.var else None,
                 self.type_text(node.type) if node.type is not None else None]
        return [_INDENT * level + " ".join(p for p in parts if p) + " " + self.declarators(node.declarators) + ";"]

    # Parameters

    def parameter_text(self, node: Any) -> str:
        if isinstance(node, S.TypeParameterDeclaration):
            assignments = ", ".join(a.name.spelling + (f" = {self.type_text(a.type)}" if a.type is not None else "")
                                    for a in node.assignments)
            return " ".join(p for p in (node.keyword, "type", assignments) if p)
        assignments = ", ".join(a.name.spelling + "".join(self.dimension(d) for d in a.dimensions)
                                + (f" = {self.text(a.value)}" if a.value is not None else "") for a in node.assignments)
        return " ".join(p for p in (node.keyword, self.type_text(node.type) if node.type is not None else None,
                                    assignments) if p)

    def parameter(self, node: Any, level: int) -> list[str]:
        return [_INDENT * level + self.parameter_text(node) + ";"]

    # Data types

    def type_text(self, node: Any) -> str:
        dimensions = "".join(self.dimension(d) for d in getattr(node, "dimensions", []))
        if isinstance(node, S.IntegerVectorType):
            return " ".join(p for p in (node.keyword, node.signing) if p) + (f" {dimensions}" if dimensions else "")
        if isinstance(node, S.IntegerAtomType):
            return " ".join(p for p in (node.keyword, node.signing) if p)
        if isinstance(node, (S.NonIntegerType, S.KeywordType)):
            return node.keyword
        if isinstance(node, S.NamedType):
            return self.name(node.name) + (f" {dimensions}" if dimensions else "")
        if isinstance(node, S.VirtualInterfaceType):
            head = "virtual interface" if node.interface_keyword else "virtual"
            modport = f".{node.modport.spelling}" if node.modport is not None else ""
            return f"{head} {node.interface.spelling}{self.parameter_values(node.parameters)}{modport}"
        if isinstance(node, S.ImplicitType):
            return " ".join(p for p in (node.signing, dimensions) if p)
        if isinstance(node, S.StructType):
            head = " ".join(p for p in (node.keyword, "packed" if node.packed else None, node.signing) if p)
            members = " ".join(f"{self.type_text(m.type)} {self.declarators(m.declarators)};" for m in node.members)
            return f"{head} {{ {members} }}" + (f" {dimensions}" if dimensions else "")
        base = f" {self.type_text(node.base)}" if node.base is not None else ""  # an EnumType
        members = ", ".join(m.name.spelling + (f" = {self.text(m.value)}" if m.value is not None else "")
                            for m in node.members)
        return f"enum{base} {{{members}}}" + (f" {dimensions}" if dimensions else "")

    def struct_lines(self, node: S.StructType, level: int) -> list[str]:
        """A structure or union over several lines, one member per line."""
        pad = _INDENT * level
        head = " ".join(p for p in (node.keyword, "packed" if node.packed else None, node.signing) if p)
        lines = [f"{head} {{"]
        lines.extend(f"{pad}{_INDENT}{self.type_text(m.type)} {self.declarators(m.declarators)};" for m in node.members)
        dimensions = "".join(self.dimension(d) for d in node.dimensions)
        lines.append(f"{pad}}}" + (f" {dimensions}" if dimensions else ""))
        return lines

    def name(self, node: Any) -> str:
        if isinstance(node, S.ScopedName):
            return f"{self.name(node.scope)}::{self.name(node.name)}"
        if isinstance(node, S.ParameterizedName):
            return node.name.spelling + self.parameter_values(node.parameters)
        return node.spelling

    def parameter_values(self, parameters: list[Any]) -> str:
        """` #(values)`, or nothing without values."""
        return " #(" + ", ".join(self.connection(p) for p in parameters) + ")" if parameters else ""

    def dimension(self, node: Any) -> str:
        if isinstance(node, S.RangeDimension):
            return f"[{self.text(node.left)}:{self.text(node.right)}]"
        if isinstance(node, S.SizeDimension):
            return f"[{self.text(node.size)}]"
        if isinstance(node, S.UnsizedDimension):
            return "[]"
        if isinstance(node, S.AssociativeDimension):
            return f"[{self.type_text(node.type) if node.type is not None else '*'}]"
        return f"[${f':{self.text(node.bound)}' if node.bound is not None else ''}]"  # a QueueDimension

    # Declarations

    def declarators(self, declarators: list[S.VariableDeclarator]) -> str:
        return ", ".join(d.name.spelling + "".join(self.dimension(x) for x in d.dimensions)
                         + (f" = {self.text(d.value)}" if d.value is not None else "") for d in declarators)

    def declaration_head(self, node: Any) -> str:
        parts: list[str | None] = []
        if isinstance(node, S.NetDeclaration):
            parts = [node.net_type, self.type_text(node.type) if node.type is not None else None,
                     self.timing_text(node.delay) if node.delay is not None else None]
        else:
            parts = [self.variable_prefix(node), self.type_text(node.type) if node.type is not None else None]
        return " ".join(p for p in parts if p)

    def variable_prefix(self, node: Any) -> str:
        """What a variable declaration says before its type: `local rand const var static`."""
        return " ".join(p for p in (node.visibility, node.random, "const" if node.const else None,
                                    "var" if node.var else None, node.lifetime) if p)

    def declaration(self, node: Any, level: int) -> list[str]:
        pad = _INDENT * level
        kind = getattr(node, "type", None)
        if isinstance(kind, S.StructType) and len(kind.members) > 1:
            lines = self.struct_lines(kind, level)
            prefix = self.variable_prefix(node) if isinstance(node, S.VariableDeclaration) else node.net_type
            lines[0] = pad + (prefix + " " if prefix else "") + lines[0]
            lines[-1] += " " + self.declarators(node.declarators) + ";"
            return lines
        return [pad + self.declaration_head(node) + " " + self.declarators(node.declarators) + ";"]

    def typedef(self, node: S.TypedefDeclaration, level: int) -> list[str]:
        pad = _INDENT * level
        dimensions = "".join(self.dimension(d) for d in node.dimensions)
        if isinstance(node.type, S.StructType) and len(node.type.members) > 1:
            lines = self.struct_lines(node.type, level)
            lines[0] = f"{pad}typedef {lines[0]}"
            lines[-1] += f" {node.name.spelling}{dimensions};"
            return lines
        return [f"{pad}typedef {self.type_text(node.type)} {node.name.spelling}{dimensions};"]

    def genvar(self, node: S.GenvarDeclaration, level: int) -> list[str]:
        return [f"{_INDENT * level}genvar {', '.join(n.spelling for n in node.names)};"]

    def import_text(self, node: S.ImportDeclaration) -> str:
        return "import " + ", ".join(f"{i.package.spelling}::{i.name.spelling if i.name is not None else '*'}"
                                     for i in node.items)

    def import_declaration(self, node: S.ImportDeclaration, level: int) -> list[str]:
        return [_INDENT * level + self.import_text(node) + ";"]

    def modport(self, node: S.ModportDeclaration, level: int) -> list[str]:
        items = ", ".join(f"{i.name.spelling} ({', '.join(f'{p.direction} {p.name.spelling}' for p in i.ports)})"
                          for i in node.items)
        return [f"{_INDENT * level}modport {items};"]

    def continuous_assign(self, node: S.ContinuousAssign, level: int) -> list[str]:
        delay = f" {self.timing_text(node.delay)}" if node.delay is not None else ""
        return [f"{_INDENT * level}assign{delay} {', '.join(self.text(a) for a in node.assignments)};"]

    def procedural(self, node: Any, level: int) -> list[str]:
        keyword = node.keyword if isinstance(node, S.AlwaysConstruct) else (
            "initial" if isinstance(node, S.InitialConstruct) else "final")
        return self.headed(_INDENT * level + keyword, node.body, level)

    def subroutine(self, node: Any, level: int) -> list[str]:
        pad = _INDENT * level
        task = isinstance(node, S.TaskDeclaration)
        parts = ["extern" if node.extern else None, "pure" if node.pure else None, "virtual" if node.virtual else None,
                 node.visibility, "static" if node.static else None, "task" if task else "function", node.lifetime]
        if not task and node.type is not None:
            parts.append(self.type_text(node.type))
        head = " ".join(p for p in parts if p) + " " + self.name(node.name)
        if node.ports:
            head += "(" + ", ".join(self.tf_port(p) for p in node.ports) + ")"
        lines = [pad + head + ";"]
        if _prototype(node):
            return lines
        lines.extend(self.items(node.body, level + 1, after=lines))
        end = "endtask" if task else "endfunction"
        lines.append(pad + end + (f" : {self.name(node.name)}" if node.labeled else ""))
        return lines

    def class_declaration(self, node: S.ClassDeclaration, level: int) -> list[str]:
        pad = _INDENT * level
        keyword = "virtual class" if node.virtual else "interface class" if node.interface else "class"
        head = f"{pad}{keyword} {node.name.spelling}"
        lines: list[str] = []
        if node.parameters:
            lines.append(head + " #(")
            lines.extend(f"{pad}{_INDENT}{self.parameter_text(p)}{',' if i < len(node.parameters) - 1 else ''}"
                         for i, p in enumerate(node.parameters))
            head = pad + ")"
        if node.base is not None:
            arguments = f"({', '.join(self.connection(a) for a in node.arguments)})" if node.arguments else ""
            head += f" extends {self.type_text(node.base)}{arguments}"
        if node.interfaces:
            head += f" {'extends' if node.interface else 'implements'} " + ", ".join(self.type_text(i)
                                                                                     for i in node.interfaces)
        lines.append(head + ";")
        lines.extend(self.items(node.items, level + 1, after=lines))
        lines.append(f"{pad}endclass" + (f" : {node.name.spelling}" if node.labeled else ""))
        return lines

    def forward_typedef(self, node: S.ForwardTypedefDeclaration, level: int) -> list[str]:
        keyword = f"{node.keyword} " if node.keyword else ""
        return [f"{_INDENT * level}typedef {keyword}{node.name.spelling};"]

    def tf_port(self, node: S.TfPort) -> str:
        parts = [node.direction, "var" if node.var else None, self.type_text(node.type) if node.type is not None
                 else None, node.name.spelling + "".join(self.dimension(d) for d in node.dimensions)]
        text = " ".join(p for p in parts if p)
        return text + (f" = {self.text(node.value)}" if node.value is not None else "")

    # Generate constructs

    def generate_region(self, node: S.GenerateRegion, level: int) -> list[str]:
        pad = _INDENT * level
        lines = [f"{pad}generate"]
        return [*lines, *self.items(node.items, level + 1, after=lines), f"{pad}endgenerate"]

    def generate_for(self, node: S.GenerateFor, level: int) -> list[str]:
        genvar = "genvar " if node.genvar else ""
        head = (f"{_INDENT * level}for ({genvar}{node.name.spelling} = {self.text(node.start)}; "
                f"{self.text(node.condition)}; {self.text(node.step)})")
        return self.generate_headed(head, node.body, level)

    def generate_if(self, node: S.GenerateIf, level: int) -> list[str]:
        lines = self.generate_headed(f"{_INDENT * level}if ({self.text(node.condition)})", node.consequence, level)
        alternative = node.alternative
        if alternative is None:
            return lines
        if isinstance(alternative, S.GenerateIf):  # else if
            tail = self.generate_if(alternative, level)
            tail[0] = "else " + tail[0].strip()
        else:
            tail = self.generate_headed("else", alternative, level)
        if isinstance(node.consequence, S.GenerateBlock):
            lines[-1] += " " + tail[0]
            return lines + tail[1:]
        return lines + [_INDENT * level + tail[0], *tail[1:]]

    def generate_case(self, node: S.GenerateCase, level: int) -> list[str]:
        pad = _INDENT * level
        lines = [f"{pad}case ({self.text(node.expression)})"]
        for item in node.items:
            label = ", ".join(self.text(e) for e in item.expressions) if item.expressions else "default"
            lines.extend(self.generate_headed(f"{pad}{_INDENT}{label}:", item.body, level + 1))
        lines.append(f"{pad}endcase")
        return lines

    def generate_headed(self, head: str, body: Any, level: int) -> list[str]:
        """`head body`: a block opens on the header's line, any other item goes on the next."""
        if isinstance(body, S.GenerateBlock):
            block = self.generate_block(body, level)
            return [head + " " + block[0].strip(), *block[1:]]
        return [head, *self.item(body, level + 1)]

    def generate_block(self, node: S.GenerateBlock, level: int) -> list[str]:
        pad = _INDENT * level
        name = f" : {node.name.spelling}" if node.name is not None else ""
        end = f" : {node.name.spelling}" if node.labeled and node.name is not None else ""
        lines = [f"{pad}begin{name}"]
        return [*lines, *self.items(node.items, level + 1, after=lines), f"{pad}end{end}"]

    # Instantiation

    def instantiation(self, node: S.ModuleInstantiation, level: int) -> list[str]:
        parameters = self.parameter_values(node.parameters)
        instances = ", ".join(
            i.name.spelling + "".join(self.dimension(d) for d in i.dimensions)
            + " (" + ", ".join(self.connection(c) for c in i.connections) + ")" for i in node.instances)
        return [f"{_INDENT * level}{node.module.spelling}{parameters} {instances};"]

    def connection(self, node: Any) -> str:
        if isinstance(node, S.WildcardConnection):
            return ".*"
        if isinstance(node, S.NamedConnection):
            if node.implicit:
                return f".{node.name.spelling}"
            value = "" if node.value is None else self.type_or_text(node.value)
            return f".{node.name.spelling}({value})"
        return self.type_or_text(node)

    def type_or_text(self, node: Any) -> str:
        return self.type_text(node) if isinstance(node, S.DataType) else self.text(node)

    # Statements

    def headed(self, head: str, body: Any, level: int) -> list[str]:
        """`head body`: a block opens on the header's line, a null statement ends it, and any other statement goes on
        the next line, one level in."""
        if isinstance(body, (S.SeqBlock, S.ParBlock, S.TimedStatement)):
            lines = self.statement(body, level)
            return [head + " " + lines[0].strip(), *lines[1:]]
        if isinstance(body, S.NullStatement):
            return [head + ";"]
        return [head, *self.statement(body, level + 1)]

    def statement(self, node: Any, level: int) -> list[str]:
        method = self.STATEMENTS.get(type(node))
        if method is not None:
            return method(self, node, level)
        return [_INDENT * level + self.simple(node)]

    def simple(self, node: Any) -> str:
        if isinstance(node, S.AssignmentStatement):
            timing = f"{self.timing_text(node.timing)} " if node.timing is not None else ""
            return f"{self.text(node.target)} {node.operator} {timing}{self.text(node.value)};"
        if isinstance(node, S.ExpressionStatement):
            return self.text(node.expression) + ";"
        if isinstance(node, S.NullStatement):
            return ";"
        if isinstance(node, S.BreakStatement):
            return "break;"
        if isinstance(node, S.ContinueStatement):
            return "continue;"
        if isinstance(node, S.ReturnStatement):
            return "return" + (f" {self.text(node.value)}" if node.value is not None else "") + ";"
        if isinstance(node, S.EventTrigger):
            return f"{'->>' if node.nonblocking else '->'} {self.text(node.event)};"
        return f"disable {self.text(node.target) if node.target is not None else 'fork'};"  # a DisableStatement

    def block(self, node: Any, level: int) -> list[str]:
        pad = _INDENT * level
        opener = "begin" if isinstance(node, S.SeqBlock) else "fork"
        closer = "end" if isinstance(node, S.SeqBlock) else node.join
        name = f" : {node.name.spelling}" if node.name is not None else ""
        end = f" : {node.name.spelling}" if node.labeled and node.name is not None else ""
        lines = [f"{pad}{opener}{name}"]
        return [*lines, *self.items(node.items, level + 1, after=lines), f"{pad}{closer}{end}"]

    def if_statement(self, node: S.IfStatement, level: int, head: str | None = None) -> list[str]:
        pad = _INDENT * level
        qualifier = f"{node.qualifier} " if node.qualifier else ""
        start = (head if head is not None else pad) + f"{qualifier}if ({self.text(node.condition)})"
        lines = self.headed(start, node.consequence, level)
        alternative = node.alternative
        if alternative is None:
            return lines
        block = isinstance(node.consequence, (S.SeqBlock, S.ParBlock))
        if isinstance(alternative, S.IfStatement) and alternative.qualifier is None:
            if block:
                tail = self.if_statement(alternative, level, head="else ")
                lines[-1] += " " + tail[0]
                return lines + tail[1:]
            return lines + self.if_statement(alternative, level, head=pad + "else ")
        if block:
            tail = self.headed("else", alternative, level)
            lines[-1] += " " + tail[0]
            return lines + tail[1:]
        return lines + self.headed(pad + "else", alternative, level)

    def case(self, node: S.CaseStatement, level: int) -> list[str]:
        pad = _INDENT * level
        qualifier = f"{node.qualifier} " if node.qualifier else ""
        lines = [f"{pad}{qualifier}{node.keyword} ({self.text(node.expression)}){' inside' if node.inside else ''}"]
        for item in node.items:
            label = ", ".join(self.range_text(e) for e in item.expressions) if item.expressions else "default"
            head = f"{pad}{_INDENT}{label}:"
            if isinstance(item.body, S.NullStatement):
                lines.append(f"{head} ;")
            elif isinstance(item.body, (S.SeqBlock, S.ParBlock)):
                lines.extend(self.headed(head, item.body, level + 1))
            elif isinstance(item.body, S.Statement) and len(self.statement(item.body, 0)) == 1:
                lines.append(f"{head} {self.statement(item.body, 0)[0]}")
            else:
                lines.extend(self.headed(head, item.body, level + 1))
        lines.append(f"{pad}endcase")
        return lines

    def loop(self, node: Any, level: int) -> list[str]:
        pad = _INDENT * level
        if isinstance(node, S.ForStatement):
            initializers = ", ".join(self.for_initializer(i) for i in node.initializers)
            condition = self.text(node.condition) if node.condition is not None else ""
            steps = ", ".join(self.text(s) for s in node.steps)
            return self.headed(f"{pad}for ({initializers}; {condition}; {steps})", node.body, level)
        if isinstance(node, S.WhileStatement):
            return self.headed(f"{pad}while ({self.text(node.condition)})", node.body, level)
        if isinstance(node, S.RepeatStatement):
            return self.headed(f"{pad}repeat ({self.text(node.count)})", node.body, level)
        if isinstance(node, S.ForeverStatement):
            return self.headed(f"{pad}forever", node.body, level)
        if isinstance(node, S.ForeachStatement):
            variables = ", ".join(v.spelling for v in node.variables)
            return self.headed(f"{pad}foreach ({self.text(node.array)}[{variables}])", node.body, level)
        lines = self.headed(f"{pad}do", node.body, level)  # a DoWhileStatement
        tail = f"while ({self.text(node.condition)});"
        if isinstance(node.body, (S.SeqBlock, S.ParBlock)):
            lines[-1] += " " + tail
        else:
            lines.append(pad + tail)
        return lines

    def for_initializer(self, node: Any) -> str:
        if isinstance(node, S.VariableDeclaration):
            head = self.declaration_head(node)
            return (head + " " if head else "") + self.declarators(node.declarators)
        return self.text(node)

    def timed(self, node: S.TimedStatement, level: int) -> list[str]:
        head = _INDENT * level + self.timing_text(node.timing)
        if node.body is None:
            return [head + ";"]
        if isinstance(node.body, (S.SeqBlock, S.ParBlock)):
            return self.headed(head, node.body, level)
        inner = self.statement(node.body, 0)
        if len(inner) == 1:
            return [f"{head} {inner[0]}"]
        return self.headed(head, node.body, level)

    def wait(self, node: S.WaitStatement, level: int) -> list[str]:
        head = f"{_INDENT * level}wait ({self.text(node.condition)})"
        if node.body is None:
            return [head + ";"]
        inner = self.statement(node.body, 0)
        if len(inner) == 1 and not isinstance(node.body, (S.SeqBlock, S.ParBlock)):
            return [f"{head} {inner[0]}"]
        return self.headed(head, node.body, level)

    def assertion(self, node: S.ImmediateAssertion, level: int) -> list[str]:
        pad = _INDENT * level
        deferral = f" {node.deferral}" if node.deferral else ""
        head = f"{pad}{node.keyword}{deferral} ({self.text(node.expression)})"
        if node.pass_action is None and node.fail_action is None:
            return [head + ";"]
        lines: list[str] = []
        if node.pass_action is not None:
            inner = self.statement(node.pass_action, 0)
            if len(inner) == 1:
                lines = [f"{head} {inner[0]}"]
            else:
                lines = self.headed(head, node.pass_action, level)
        else:
            lines = [head]
        if node.fail_action is not None:
            inner = self.statement(node.fail_action, 0)
            if len(inner) == 1:
                lines[-1] += f" else {inner[0]}"
            else:
                tail = self.headed("else", node.fail_action, level)
                lines[-1] += " " + tail[0]
                lines.extend(tail[1:])
        return lines

    # Timing controls

    def timing_text(self, node: Any) -> str:
        if isinstance(node, S.DelayControl):
            value = node.value
            text = self.text(value)
            simple = isinstance(value, (S.IntegerLiteral, S.RealLiteral, S.TimeLiteral, S.NameExpression,
                                        S.ParenthesizedExpression, S.MacroUsage))
            return f"#{text}" if simple else f"#({text})"
        if not node.events:
            return "@(*)"
        return "@(" + " or ".join(self.event(e) for e in node.events) + ")"

    def event(self, node: S.EventExpression) -> str:
        text = (f"{node.edge} " if node.edge else "") + self.text(node.expression)
        return text + (f" iff {self.text(node.condition)}" if node.condition is not None else "")

    # Expressions

    def range_text(self, node: Any) -> str:
        if isinstance(node, S.ValueRange):
            return f"[{self.text(node.left)}:{self.text(node.right)}]"
        return self.text(node)

    def operand(self, node: Any, level: int) -> str:
        text = self.text(node)
        return f"({text})" if _precedence(node) < level else text

    def text(self, node: Any) -> str:
        if isinstance(node, S.NameExpression):
            return self.name(node.name)
        if isinstance(node, S.MemberExpression):
            return f"{self.operand(node.value, PRIMARY)}.{node.member.spelling}"
        if isinstance(node, S.IndexExpression):
            return f"{self.operand(node.value, PRIMARY)}[{self.text(node.index)}]"
        if isinstance(node, S.RangeSelect):
            operator = node.operator if node.operator == ":" else f" {node.operator} "
            return f"{self.operand(node.value, PRIMARY)}[{self.text(node.left)}{operator}{self.text(node.right)}]"
        if isinstance(node, (S.IntegerLiteral, S.RealLiteral, S.TimeLiteral)):
            return node.spelling
        if isinstance(node, S.UnbasedUnsizedLiteral):
            return f"'{node.value}"
        if isinstance(node, S.StringLiteral):
            return f'"""{node.text}"""' if node.triple else f'"{node.text}"'
        if isinstance(node, S.UnaryExpression):
            operand = self.operand(node.operand, UNARY + 1)
            if isinstance(node.operand, (S.UnaryExpression, S.IncrementExpression)):
                operand = f"({self.text(node.operand)})"
            return f"{node.operator}{operand}"
        if isinstance(node, S.IncrementExpression):
            operand = self.operand(node.operand, PRIMARY)
            return f"{operand}{node.operator}" if node.postfix else f"{node.operator}{operand}"
        if isinstance(node, S.BinaryExpression):
            level = _BINARY[node.operator]
            left_level, right_level = (level + 1, level) if level in _RIGHT else (level, level + 1)
            return f"{self.operand(node.left, left_level)} {node.operator} {self.operand(node.right, right_level)}"
        if isinstance(node, S.AssignmentExpression):
            return f"{self.text(node.target)} {node.operator} {self.text(node.value)}"
        if isinstance(node, S.ConditionalExpression):
            return (f"{self.operand(node.condition, CONDITIONAL + 1)} ? "
                    f"{self.operand(node.consequence, CONDITIONAL + 1)} : "
                    f"{self.operand(node.alternative, CONDITIONAL)}")
        if isinstance(node, S.InsideExpression):
            ranges = ", ".join(self.range_text(r) for r in node.set)
            return f"{self.operand(node.value, RELATIONAL + 1)} inside {{{ranges}}}"
        if isinstance(node, S.Concatenation):
            return "{" + ", ".join(self.text(i) for i in node.items) + "}"
        if isinstance(node, S.Replication):
            return f"{{{self.operand(node.count, PRIMARY)}{{{', '.join(self.text(i) for i in node.items)}}}}}"
        if isinstance(node, S.AssignmentPattern):
            prefix = self.type_text(node.type) if node.type is not None else ""
            return f"{prefix}'{{{', '.join(self.pattern_item(i) for i in node.items)}}}"
        if isinstance(node, S.CallExpression):
            return f"{self.operand(node.callee, PRIMARY)}({', '.join(self.connection(a) for a in node.arguments)})"
        if isinstance(node, S.SystemCall):
            if not node.arguments:
                return node.name
            return f"{node.name}({', '.join(self.type_or_text(a) for a in node.arguments)})"
        if isinstance(node, S.CastExpression):
            target = (self.type_text(node.type) if isinstance(node.type, S.DataType)
                      else self.operand(node.type, PRIMARY))
            return f"{target}'({self.text(node.value)})"
        if isinstance(node, S.ParenthesizedExpression):
            return f"({self.text(node.expression)})"
        if isinstance(node, S.MacroUsage):
            return f"`{node.name.spelling}" + (f"({node.arguments})" if node.arguments is not None else "")
        if isinstance(node, S.DollarExpression):
            return "$"
        if isinstance(node, S.NullLiteral):
            return "null"
        if isinstance(node, S.ThisExpression):
            return "this"
        if isinstance(node, S.SuperExpression):
            return "super"
        if isinstance(node, S.NewExpression):
            scope = ""
            if isinstance(node.scope, S.SuperExpression):
                scope = "super."
            elif node.scope is not None:
                scope = self.name(node.scope) + "::"
            arguments = f"({', '.join(self.connection(a) for a in node.arguments)})" if node.arguments else ""
            return f"{scope}new{arguments}"
        if isinstance(node, S.NewCopyExpression):
            return f"new {self.operand(node.value, PRIMARY)}"
        if isinstance(node, S.NewArrayExpression):
            value = f"({self.text(node.value)})" if node.value is not None else ""
            return f"new[{self.text(node.size)}]{value}"
        return self.port(node) if isinstance(node, S.Port) else self.dimension(node) if isinstance(node, S.Dimension) \
            else self.type_text(node)

    def pattern_item(self, node: Any) -> str:
        if not isinstance(node, S.PatternItem):
            return self.text(node)
        key = "default" if node.key is None else self.type_or_text(node.key)
        return f"{key}: {self.text(node.value)}"

    # Dispatch

    ITEMS = {
        S.ModuleDeclaration: design_unit, S.InterfaceDeclaration: design_unit, S.ProgramDeclaration: design_unit,
        S.PackageDeclaration: design_unit, S.PortDeclaration: port_declaration, S.ParameterDeclaration: parameter,
        S.TypeParameterDeclaration: parameter, S.NetDeclaration: declaration, S.VariableDeclaration: declaration,
        S.TypedefDeclaration: typedef, S.GenvarDeclaration: genvar, S.ImportDeclaration: import_declaration,
        S.ModportDeclaration: modport, S.ContinuousAssign: continuous_assign, S.AlwaysConstruct: procedural,
        S.InitialConstruct: procedural, S.FinalConstruct: procedural, S.FunctionDeclaration: subroutine,
        S.TaskDeclaration: subroutine, S.GenerateRegion: generate_region, S.GenerateFor: generate_for,
        S.GenerateIf: generate_if, S.GenerateCase: generate_case, S.GenerateBlock: generate_block,
        S.ModuleInstantiation: instantiation, S.ClassDeclaration: class_declaration,
        S.ForwardTypedefDeclaration: forward_typedef,
    }
    STATEMENTS = {
        S.SeqBlock: block, S.ParBlock: block, S.IfStatement: if_statement, S.CaseStatement: case,
        S.ForStatement: loop, S.WhileStatement: loop, S.RepeatStatement: loop, S.ForeverStatement: loop,
        S.ForeachStatement: loop, S.DoWhileStatement: loop, S.TimedStatement: timed, S.WaitStatement: wait,
        S.ImmediateAssertion: assertion,
    }
