"""Reads Verilog and SystemVerilog source text into Verilog trees, delegating to slang, a complete SystemVerilog front
end (IEEE 1800-2023), through `pyslang`.

slang preprocesses as the standard does: it resolves `` `include `` (which must be found, on the include paths given),
expands macros and evaluates conditional compilation, keeping directives, comments and skipped branches as trivia, the
text attached to the tokens that follow them. `_Reader` rewrites slang's syntax tree into Verilog kinds:

- Directives and comments are read from the trivia of the tokens that start the items and statements of a list, and
  of the token that closes the list. Conditional compilation becomes a tree of its branches; a branch the preprocessor
  skipped keeps its text, as `DisabledText`. A directive anywhere else is refused.
- A macro use that expands to a whole expression becomes a `MacroUsage`; any other macro use is refused.
- What an included file contributes is not part of the including file's tree.

Any error slang reports is a `ParseError`. Positions are counted in characters (code points), never bytes, so that every
implementation reports the same line and column.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from typing import Any

import pyslang
from pyslang import parsing, syntax

from ..Framework.Errors import ParseError
from . import Syntax as S

__all__ = ["parse"]

K = syntax.SyntaxKind
T = parsing.TokenKind

_CONDITIONALS = {"IfDefDirective": "if", "IfNDefDirective": "if", "ElsIfDirective": "elsif", "ElseDirective": "else",
                 "EndIfDirective": "endif"}
_ASSIGNMENTS = {
    "AssignmentExpression", "AddAssignmentExpression", "SubtractAssignmentExpression", "MultiplyAssignmentExpression",
    "DivideAssignmentExpression", "ModAssignmentExpression", "AndAssignmentExpression", "OrAssignmentExpression",
    "XorAssignmentExpression", "LogicalLeftShiftAssignmentExpression", "LogicalRightShiftAssignmentExpression",
    "ArithmeticLeftShiftAssignmentExpression", "ArithmeticRightShiftAssignmentExpression",
}  # and "NonblockingAssignmentExpression", which slang reads only as a statement
_VECTORS = {"bit", "logic", "reg"}
_ATOMS = {"byte", "shortint", "int", "longint", "integer", "time"}
_REALS = {"shortreal", "real", "realtime"}


class _Source:
    """The text, with conversions from slang's byte offsets to character offsets and to lines and columns."""

    def __init__(self, text: str):
        self.text = text
        self.data = text.encode("utf-8")
        self._chars: list[int] | None = None
        if len(self.data) != len(text):
            self._chars = []
            for i, ch in enumerate(text):
                self._chars.extend([i] * len(ch.encode("utf-8")))
            self._chars.append(len(text))

    def offset(self, byte: int) -> int:
        return byte if self._chars is None else self._chars[min(byte, len(self._chars) - 1)]

    def error(self, message: str, offset: int) -> ParseError:
        line = self.text.count("\n", 0, offset) + 1
        column = offset - (self.text.rfind("\n", 0, offset) + 1) + 1
        return ParseError(message, line, column)


def _tokens(node: Any) -> Iterator[parsing.Token]:
    if isinstance(node, parsing.Token):
        yield node
        return
    if node is None:
        return
    for i in range(len(node)):
        yield from _tokens(node[i])


def _nodes(items: Any) -> list[Any]:
    """The syntax nodes of a list, without its separators."""
    return [items[i] for i in range(len(items)) if not isinstance(items[i], parsing.Token) and items[i] is not None]


def _text(token: parsing.Token | None) -> str:
    return "" if token is None else token.rawText


class _Reader:
    """Rewrites a slang syntax tree into Verilog nodes, recording where each node starts in `positions`."""

    def __init__(self, tree: syntax.SyntaxTree, source: _Source):
        self.tree, self.source = tree, source
        self.manager = tree.sourceManager
        self.positions: dict[int, int] = {}
        self.placed: list[Any] = []  # the nodes placed, kept alive so that no other node takes their `id`
        self.buffer: Any = None
        self.listed: set[int] = set()  # tokens whose trivia were read as a list's comments and directives
        self.macros: set[int] = set()  # tokens read as part of a macro use
        self.expansions: dict[int, int] = {}  # the number of tokens of each macro use, by its offset
        self.start: Any = None  # the location of the file's first token

    # Positions and errors

    def location(self, token: parsing.Token) -> Any:
        location = token.location
        if self.manager.isMacroLoc(location):
            location = self.manager.getExpansionLoc(location)
            while self.manager.isMacroLoc(location):
                location = self.manager.getExpansionLoc(location)
        return location

    def offset_of(self, token: parsing.Token) -> int:
        return self.source.offset(self.location(token).offset)

    def first(self, node: Any) -> parsing.Token:
        if isinstance(node, parsing.Token):
            return node
        return node.getFirstToken()

    def at(self, node: Any) -> int:
        return self.offset_of(self.first(node))

    def error(self, node: Any, message: str) -> ParseError:
        return self.source.error(message, self.at(node))

    def unsupported(self, node: Any) -> ParseError:
        return self.error(node, f"unsupported syntax: {node.kind.name}")

    def made(self, at: Any, node: Any) -> Any:
        if id(node) not in self.positions:
            self.positions[id(node)] = self.at(at)
            self.placed.append(node)
        return node

    def main(self, location: Any) -> bool:
        return location.buffer == self.buffer

    # Tokens

    def token_text(self, token: parsing.Token) -> str:
        """A token's text; a token a macro expanded is refused unless a macro use took it."""
        if self.manager.isMacroLoc(token.location) and id(token) not in self.macros:
            raise self.source.error("unsupported syntax: a macro use that is not a whole expression",
                                    self.offset_of(token))
        return token.rawText

    def spelling(self, node: Any) -> str:
        """The text of a node's tokens as written, with the whitespace between them."""
        out: list[str] = []
        for i, token in enumerate(_tokens(node)):
            if i:
                out.append("".join(t.getRawText() for t in token.trivia))
            out.append(self.token_text(token))
        return "".join(out)

    def identifier(self, token: parsing.Token) -> S.Identifier:
        return self.made(token, S.Identifier(spelling=self.token_text(token)))

    # Lists of items and statements

    def leading(self, token: parsing.Token) -> list[tuple[str, Any, Any]]:
        """The comments and directives in a token's trivia, in source order, as (role, syntax, converted): role 'item'
        for a comment or a directive, or a conditional's role. A comment is trailing when no line ends between the
        token before it and the comment."""
        self.listed.add(id(token))
        out: list[tuple[str, Any, Any]] = []
        line_ended = [token.location == self.start]  # the file's first token follows no token

        def scan(trivia_list: Any, at: parsing.Token) -> None:
            for trivia in trivia_list:
                kind = trivia.kind.name
                if kind == "EndOfLine":
                    line_ended[0] = True
                elif kind in ("LineComment", "BlockComment"):
                    out.append(("item", at, self.comment(trivia.getRawText(), at, not line_ended[0])))
                elif kind == "Directive":
                    directive = trivia.syntax()
                    first = directive.getFirstToken()
                    if not self.main(first.location):
                        continue
                    scan(first.trivia, first)
                    name = directive.kind.name
                    if name == "MacroUsage":
                        raise self.error(directive, "unsupported syntax: a macro use that is not a whole expression")
                    if name in _CONDITIONALS:
                        out.append((_CONDITIONALS[name], directive, None))
                    else:
                        out.append(("item", directive, self.made(directive, self.directive(directive))))
                    line_ended[0] = True  # a directive ends its line
                elif kind in ("DisabledText", "SkippedTokens", "SkippedSyntax"):
                    raise self.source.error("unsupported syntax: skipped text", self.offset_of(token))

        scan(token.trivia, token)
        return out

    def comment(self, text: str, at: Any, trailing: bool) -> S.Comment:
        block = text.startswith("/*")
        node = S.Comment(block=block, text=text[2:-2] if block else text[2:].rstrip("\r"), trailing=trailing)
        return self.made(at, node)

    def items(self, members: Sequence[Any], closer: parsing.Token, statements: bool = False,
              convert: Callable[[Any], Any] | None = None) -> list[Any]:
        """The items (or with `statements`, the block items and statements; with `convert`, what it converts each
        member to) of a list, with the comments and directives before each and before `closer`, conditional
        compilation grouped into trees."""
        flat: list[tuple[str, Any, Any]] = []
        for member in members:
            flat.extend(self.leading(member.getFirstToken()))
            if self.main(member.getFirstToken().location):  # not what an included file contributes
                converted = convert(member) if convert is not None else self.member(member, statements)
                flat.append(("item", member, converted))
        flat.extend(self.leading(closer))
        return self.group(flat, 0, len(flat), None)[0]

    def member(self, member: Any, statements: bool) -> Any:
        if statements and member.kind.name not in self.ITEMS:
            return self.statement(member)
        return self.item(member)

    def group(self, flat: list[tuple[str, Any, Any]], i: int, end: int, opener: Any) -> tuple[list[Any], int]:
        out: list[Any] = []
        while i < end:
            role, at, converted = flat[i]
            if role == "item":
                out.append(converted)
                i += 1
            elif role == "if":
                node, i = self.ifdef(flat, i, end)
                out.append(node)
            elif opener is None:
                raise self.error(at, f"unexpected {_text(at.directive)}")
            else:
                return out, i
        if opener is not None:
            raise self.error(opener, "expected `endif")
        return out, i

    def ifdef(self, flat: list[tuple[str, Any, Any]], i: int, end: int) -> tuple[S.IfdefDirective, int]:
        opener = flat[i][1]
        node = S.IfdefDirective(negated=opener.kind.name == "IfNDefDirective", name=self.condition_name(opener))
        node.items, i = self.branch(opener, flat, i + 1, end)
        while i < end and flat[i][0] == "elsif":
            directive = flat[i][1]
            branch = self.made(directive, S.ElsifDirective(name=self.condition_name(directive)))
            branch.items, i = self.branch(directive, flat, i + 1, end)
            node.branches.append(branch)
        if i < end and flat[i][0] == "else":
            node.has_else = True
            node.alternative, i = self.branch(flat[i][1], flat, i + 1, end)
        return self.made(opener, node), i + 1  # past its `endif: a branch ends at one, or `group` refuses

    def branch(self, directive: Any, flat: list[tuple[str, Any, Any]], i: int, end: int) -> tuple[list[Any], int]:
        items, i = self.group(flat, i, end, directive)
        disabled = list(directive.disabledTokens)
        if disabled:
            text = "".join("".join(t.getRawText() for t in token.trivia) + token.rawText for token in disabled)
            items = [*items, self.made(directive, S.DisabledText(text=text.strip("\n").rstrip()))]
        return items, i

    def condition_name(self, directive: Any) -> S.Identifier:
        expression = directive.expr
        if expression is None or expression.kind.name != "NamedConditionalDirectiveExpression":
            raise self.unsupported(directive)
        token = expression.name
        return self.made(token, S.Identifier(spelling=token.rawText))

    # Directives

    def directive(self, node: Any) -> Any:
        name = node.kind.name
        if name == "IncludeDirective":
            path = node.fileName.rawText
            return S.IncludeDirective(path=path[1:-1], system=path.startswith("<"))
        if name == "DefineDirective":
            out = S.DefineDirective(name=S.Identifier(spelling=node.name.rawText), body=self.macro_body(node))
            if node.formalArguments is not None:
                out.function_like = True
                out.parameters = [S.Identifier(spelling=a.name.rawText) for a in _nodes(node.formalArguments.args)]
            return out
        if name == "UndefDirective":
            return S.UndefDirective(name=S.Identifier(spelling=node.name.rawText))
        if name == "TimeScaleDirective":
            return S.TimescaleDirective(unit=node.timeUnit.rawText, precision=node.timePrecision.rawText)
        if name == "DefaultNetTypeDirective":
            return S.DefaultNettypeDirective(net_type=node.netType.rawText)
        return S.OtherDirective(text=self.directive_text(node))

    def macro_body(self, node: Any) -> str:
        out: list[str] = []
        for i, token in enumerate(node.body):
            if i:
                out.append("".join(t.getRawText() for t in token.trivia))
            out.append(token.rawText)
        return "".join(out)

    def directive_text(self, node: Any) -> str:
        out: list[str] = []
        for i, token in enumerate(_tokens(node)):
            if i:
                out.append("".join(t.getRawText() for t in token.trivia))
            out.append(token.rawText)
        return "".join(out).strip()

    # Design units

    def unit(self, node: Any) -> S.SourceText:
        items = self.items(_nodes(node.members), node.endOfFile)
        return self.made(node, S.SourceText(items=items))

    def item(self, node: Any) -> Any:
        method = self.ITEMS.get(node.kind.name)
        if method is None:
            raise self.unsupported(node)
        return self.made(node, method(self, node))

    def design_unit(self, node: Any) -> Any:
        header = node.header
        kind = node.kind.name
        if kind == "PackageDeclaration":
            out: Any = S.PackageDeclaration()
        elif kind == "InterfaceDeclaration":
            out = S.InterfaceDeclaration()
        elif kind == "ProgramDeclaration":
            out = S.ProgramDeclaration()
        else:
            out = S.ModuleDeclaration(keyword=header.moduleKeyword.rawText)
        out.lifetime = _text(header.lifetime) or None
        out.name = self.identifier(header.name)
        if kind != "PackageDeclaration":
            out.imports = [self.made(i, self.import_declaration(i)) for i in _nodes(header.imports)]
            if header.parameters is not None:
                out.parameters = self.parameter_ports(header.parameters)
            if header.ports is not None:
                out.ports = self.ports(header.ports)
        out.labeled = node.blockName is not None
        out.items = self.items(_nodes(node.members), node.endmodule)
        return out

    def parameter_ports(self, node: Any) -> list[Any]:
        out: list[Any] = []
        for declaration in _nodes(node.declarations):
            out.append(self.made(declaration, self.parameter(declaration)))
        return out

    def ports(self, node: Any) -> list[S.Port]:
        if node.kind.name == "WildcardPortList":
            raise self.unsupported(node)
        out: list[S.Port] = []
        for port in _nodes(node.ports):
            kind = port.kind.name
            if kind == "ImplicitAnsiPort":
                out.append(self.made(port, self.ansi_port(port)))
            elif kind == "ImplicitNonAnsiPort":
                reference = port.expr
                if reference.kind.name != "PortReference" or reference.select is not None:
                    raise self.unsupported(port)
                out.append(self.made(port, S.PortReference(name=self.identifier(reference.name))))
            else:
                raise self.unsupported(port)
        return out

    def ansi_port(self, port: Any) -> S.Port:
        header = port.header
        declarator = port.declarator
        name = self.identifier(declarator.name)
        dimensions = [self.dimension(d) for d in _nodes(declarator.dimensions)]
        if header.kind.name == "InterfacePortHeader":
            interface = header.nameOrKeyword
            node: Any = S.InterfacePort(interface=None if interface.kind.name == "InterfaceKeyword"
                                        else self.identifier(interface), name=name, dimensions=dimensions)
            if header.modport is not None:
                node.modport = self.identifier(header.modport.member)
            return node
        node = S.AnsiPort(name=name, dimensions=dimensions)
        if declarator.initializer is not None:
            node.value = self.expression(declarator.initializer.expr)
        node.direction = _text(header.direction) or None
        self.port_type(header, node)
        return node

    def port_type(self, header: Any, out: Any) -> None:
        """The net type or `var`, and the data type, of a NetPortHeader or a VariablePortHeader (slang reads
        `interconnect` as a net type, and refuses `const` on a port of a design unit)."""
        if header.kind.name == "NetPortHeader":
            out.net_type = _text(header.netType) or None
        else:
            out.var = bool(header.varKeyword)
        out.type = self.data_type(header.dataType)

    def port_declaration(self, node: Any) -> S.PortDeclaration:
        header = node.header
        if header.kind.name == "InterfacePortHeader":  # `bus_if.source out;`
            raise self.unsupported(header)
        out = S.PortDeclaration(direction=_text(header.direction))
        self.port_type(header, out)
        out.declarators = self.declarators(node.declarators)
        return out

    # Parameters

    def parameter(self, node: Any) -> Any:
        if node.kind.name == "ParameterDeclarationStatement":
            return self.parameter(node.parameter)
        keyword = _text(node.keyword) or None  # a header's entry may have none
        if node.kind.name == "TypeParameterDeclaration":
            if node.typeRestriction is not None:
                raise self.unsupported(node)
            assignments = []
            for declarator in _nodes(node.declarators):
                assignment = S.TypeAssignment(name=self.identifier(declarator.name))
                if declarator.assignment is not None:
                    assignment.type = self.data_type(declarator.assignment.type)
                assignments.append(self.made(declarator, assignment))
            return S.TypeParameterDeclaration(keyword=keyword, assignments=assignments)
        out = S.ParameterDeclaration(keyword=keyword, type=self.data_type(node.type))
        for declarator in _nodes(node.declarators):
            assignment = S.ParamAssignment(name=self.identifier(declarator.name),
                                           dimensions=[self.dimension(d) for d in _nodes(declarator.dimensions)])
            if declarator.initializer is not None:
                assignment.value = self.expression(declarator.initializer.expr)
            out.assignments.append(self.made(declarator, assignment))
        return out

    # Data types

    def data_type(self, node: Any) -> S.DataType | None:
        if node is None:
            return None
        kind = node.kind.name
        if kind == "ImplicitType":
            dimensions = [self.dimension(d) for d in _nodes(node.dimensions)]
            signing = _text(node.signing) or None
            if signing is None and not dimensions:
                return None
            return self.made(node, S.ImplicitType(signing=signing, dimensions=dimensions))
        if hasattr(node, "keyword") and (kind.endswith("Type") or kind == "Untyped") \
                and kind not in ("EnumType", "StructType", "UnionType"):
            keyword = self.token_text(node.keyword)
            if keyword in _VECTORS:
                dimensions = [self.dimension(d) for d in _nodes(node.dimensions)]
                return self.made(node, S.IntegerVectorType(keyword=keyword, signing=_text(node.signing) or None,
                                                           dimensions=dimensions))
            if keyword in _ATOMS:
                if _nodes(node.dimensions):
                    raise self.unsupported(node)
                return self.made(node, S.IntegerAtomType(keyword=keyword, signing=_text(node.signing) or None))
            if keyword in _REALS:
                return self.made(node, S.NonIntegerType(keyword=keyword))
            # `string`, `chandle`, `event` or `void`: slang reads the other keyword types (`untyped`, `property`,
            # `sequence`) only where the reader refuses what declares them
            return self.made(node, S.KeywordType(keyword=keyword))
        if kind == "NamedType":
            return self.made(node, S.NamedType(name=self.name(node.name)))
        if kind == "VirtualInterfaceType":
            out = S.VirtualInterfaceType(interface_keyword=bool(node.interfaceKeyword),
                                         interface=self.identifier(node.name),
                                         parameters=self.parameter_values(node.parameters))
            if node.modport is not None:
                out.modport = self.identifier(node.modport.member)
            return self.made(node, out)
        if kind in ("StructType", "UnionType"):
            if bool(node.taggedOrSoft):
                raise self.unsupported(node)
            members = []
            for member in _nodes(node.members):
                if bool(member.randomQualifier):
                    raise self.unsupported(member)
                members.append(self.made(member, S.StructMember(type=self.data_type(member.type),
                                                                declarators=self.declarators(member.declarators))))
            return self.made(node, S.StructType(keyword=node.keyword.rawText, packed=bool(node.packed),
                                                signing=_text(node.signing) or None, members=members,
                                                dimensions=[self.dimension(d) for d in _nodes(node.dimensions)]))
        if kind == "EnumType":
            members = []
            for member in _nodes(node.members):
                if _nodes(member.dimensions):
                    raise self.unsupported(member)
                enum = S.EnumMember(name=self.identifier(member.name))
                if member.initializer is not None:
                    enum.value = self.expression(member.initializer.expr)
                members.append(self.made(member, enum))
            return self.made(node, S.EnumType(base=self.data_type(node.baseType), members=members,
                                              dimensions=[self.dimension(d) for d in _nodes(node.dimensions)]))
        raise self.unsupported(node)

    def name(self, node: Any) -> S.Name:
        """A name: an identifier, a parameterized class `c #(...)`, `new`, or `scope::name`, whose scopes, which slang
        nests to the left (`(p::c)::x`), nest to the right (`p::(c::x)`)."""
        kind = node.kind.name
        if kind == "IdentifierName":
            return self.identifier(node.identifier)
        if kind == "ClassName":
            return self.made(node, S.ParameterizedName(name=self.identifier(node.identifier),
                                                       parameters=self.parameter_values(node.parameters)))
        if kind == "ConstructorName":
            return self.made(node, S.Identifier(spelling="new"))
        if kind == "ScopedName" and node.left.kind.name == "LocalScope" and node.right.kind.name == "IdentifierName":
            return self.made(node, S.LocalName(name=self.identifier(node.right.identifier)))
        if kind == "ScopedName" and node.separator.rawText == "::":
            steps = []  # (the scope's syntax, the ScopedName that has it), innermost last
            while node.kind.name == "ScopedName" and node.separator.rawText == "::":
                steps.append(node)
                node = node.left
            out = self.name(steps[0].right)
            for step, scope in zip(steps, [*(s.right for s in steps[1:]), node]):
                if scope.kind.name not in ("IdentifierName", "ClassName"):
                    raise self.unsupported(steps[-1])
                out = self.made(step, S.ScopedName(scope=self.name(scope), name=out))
            return out
        raise self.unsupported(node)

    def dimension(self, node: Any) -> S.Dimension:
        specifier = node.specifier
        if specifier is None:
            return self.made(node, S.UnsizedDimension())
        kind = specifier.kind.name
        if kind == "RangeDimensionSpecifier":
            selector = specifier.selector
            if selector.kind.name == "BitSelect":
                inner = selector.expr
                if inner.kind.name.endswith("Type") and inner.kind.name != "NamedType":  # `[string]`: an index type
                    return self.made(node, S.AssociativeDimension(type=self.data_type(inner)))
                return self.made(node, S.SizeDimension(size=self.expression(inner)))
            if selector.kind.name == "SimpleRangeSelect":
                return self.made(node, S.RangeDimension(left=self.expression(selector.left),
                                                        right=self.expression(selector.right)))
            raise self.unsupported(selector)
        if kind == "WildcardDimensionSpecifier":
            return self.made(node, S.AssociativeDimension())
        bound = specifier.maxSizeClause  # a QueueDimensionSpecifier: slang reads `[type]` as a BitSelect
        return self.made(node, S.QueueDimension(bound=None if bound is None else self.expression(bound.expr)))

    # Declarations

    def declarators(self, items: Any) -> list[S.VariableDeclarator]:
        out = []
        for declarator in _nodes(items):
            node = S.VariableDeclarator(name=self.identifier(declarator.name),
                                        dimensions=[self.dimension(d) for d in _nodes(declarator.dimensions)])
            if declarator.initializer is not None:
                node.value = self.expression(declarator.initializer.expr)
            out.append(self.made(declarator, node))
        return out

    def data_declaration(self, node: Any) -> S.VariableDeclaration:
        modifiers = [t.rawText for t in node.modifiers]
        out = S.VariableDeclaration(const="const" in modifiers, var="var" in modifiers)
        for modifier in modifiers:  # slang allows only these outside a class
            if modifier in ("static", "automatic"):
                out.lifetime = modifier
        out.type = self.data_type(node.type)
        out.declarators = self.declarators(node.declarators)
        return out

    def net_declaration(self, node: Any) -> S.NetDeclaration:
        if node.strength is not None or bool(node.expansionHint):
            raise self.unsupported(node)
        out = S.NetDeclaration(net_type=node.netType.rawText, type=self.data_type(node.type))
        if node.delay is not None:
            out.delay = self.delay(node.delay)
        out.declarators = self.declarators(node.declarators)
        return out

    def typedef(self, node: Any) -> S.TypedefDeclaration:
        return S.TypedefDeclaration(type=self.data_type(node.type), name=self.identifier(node.name),
                                    dimensions=[self.dimension(d) for d in _nodes(node.dimensions)])

    def genvar(self, node: Any) -> S.GenvarDeclaration:
        return S.GenvarDeclaration(names=[self.identifier(i.identifier) for i in _nodes(node.identifiers)])

    def import_declaration(self, node: Any) -> S.ImportDeclaration:
        items = []
        for item in _nodes(node.items):
            name = None if item.item.rawText == "*" else self.identifier(item.item)
            items.append(self.made(item, S.ImportItem(package=self.identifier(item.package), name=name)))
        return S.ImportDeclaration(items=items)

    def modport(self, node: Any) -> S.ModportDeclaration:
        items = []
        for item in _nodes(node.items):
            out = S.ModportItem(name=self.identifier(item.name))
            for group in _nodes(item.ports.ports):
                if group.kind.name != "ModportSimplePortList":
                    raise self.unsupported(group)
                direction = group.direction.rawText
                for port in _nodes(group.ports):
                    if port.kind.name != "ModportNamedPort":
                        raise self.unsupported(port)
                    name = self.identifier(port.name)
                    out.ports.append(self.made(port, S.ModportPort(direction=direction, name=name)))
            items.append(self.made(item, out))
        return S.ModportDeclaration(items=items)

    def continuous_assign(self, node: Any) -> S.ContinuousAssign:
        if node.strength is not None:
            raise self.unsupported(node)
        out = S.ContinuousAssign()
        if node.delay is not None:
            out.delay = self.delay(node.delay)
        out.assignments = [self.expression(a) for a in _nodes(node.assignments)]  # slang reads only assignments
        return out

    def procedural_block(self, node: Any) -> Any:
        keyword = node.keyword.rawText
        body = self.statement(node.statement)
        if keyword == "initial":
            return S.InitialConstruct(body=body)
        if keyword == "final":
            return S.FinalConstruct(body=body)
        return S.AlwaysConstruct(keyword=keyword, body=body)

    def subroutine(self, node: Any) -> Any:
        out = self.prototype(node.prototype)
        out.labeled = node.endBlockName is not None
        out.body = self.items(_nodes(node.items), node.end, statements=True)
        return out

    def prototype(self, prototype: Any) -> Any:
        """A function or a task as its prototype declares it, without a body."""
        if _nodes(prototype.specifiers):  # `:initial`, `:extends`, `:final`
            raise self.unsupported(prototype)
        task = prototype.keyword.rawText == "task"
        out: Any = S.TaskDeclaration() if task else S.FunctionDeclaration(type=self.data_type(prototype.returnType))
        out.lifetime = _text(prototype.lifetime) or None
        out.name = self.name(prototype.name)
        if prototype.portList is not None:
            out.ports = [self.made(p, self.tf_port(p)) for p in _nodes(prototype.portList.ports)]
        return out

    # Classes

    def class_declaration(self, node: Any) -> S.ClassDeclaration:
        if node.finalSpecifier is not None:
            raise self.unsupported(node)
        kind = _text(node.virtualOrInterface)
        out = S.ClassDeclaration(virtual=kind == "virtual", interface=kind == "interface",
                                 name=self.identifier(node.name),
                                 labeled=node.endBlockName is not None)
        if node.parameters is not None:
            out.parameters = self.parameter_ports(node.parameters)
        extends = node.extendsClause
        if extends is not None:
            if extends.defaultedArg is not None:
                raise self.unsupported(extends)
            out.base = self.made(extends.baseName, S.NamedType(name=self.name(extends.baseName)))
            if extends.arguments is not None:
                out.arguments = self.arguments(extends.arguments)
        if node.implementsClause is not None:
            out.interfaces = [self.made(i, S.NamedType(name=self.name(i)))
                              for i in _nodes(node.implementsClause.interfaces)]
        out.items = self.items(_nodes(node.items), node.endClass)
        return out

    def qualified(self, node: Any, out: Any) -> Any:
        """`out` with a class item's qualifiers, which slang has checked are those of a property or a method."""
        for qualifier in node.qualifiers:
            word = qualifier.rawText
            if word in ("local", "protected"):
                out.visibility = word
            elif word in ("rand", "randc"):
                out.random = word
            elif word == "const":
                out.const = True
            elif word == "static":
                if isinstance(out, S.VariableDeclaration):
                    out.lifetime = "static"
                else:
                    out.static = True
            else:  # pure, virtual, extern
                setattr(out, word, True)
        return out

    def class_property(self, node: Any) -> Any:
        declaration = node.declaration
        if declaration.kind.name != "DataDeclaration":
            if node.qualifiers:  # a qualified typedef or parameter
                raise self.unsupported(node)
            return self.item(declaration)
        return self.qualified(node, self.data_declaration(declaration))

    def class_method(self, node: Any) -> Any:
        return self.qualified(node, self.subroutine(node.declaration))

    def class_prototype(self, node: Any) -> Any:
        return self.qualified(node, self.prototype(node.prototype))

    # Constraints

    def constraint_declaration(self, node: Any) -> S.ConstraintDeclaration:
        if _nodes(node.specifiers):  # `:initial`, `:extends`, `:final`
            raise self.unsupported(node)
        return S.ConstraintDeclaration(static=any(q.rawText == "static" for q in node.qualifiers),
                                       name=self.name(node.name), items=self.constraint_items(node.block))

    def constraint_prototype(self, node: Any) -> S.ConstraintPrototype:
        if _nodes(node.specifiers):
            raise self.unsupported(node)
        words = [q.rawText for q in node.qualifiers]
        return S.ConstraintPrototype(qualifier=next((w for w in words if w in ("extern", "pure")), None),
                                     static="static" in words, name=self.identifier(node.name.identifier))

    def constraint_items(self, block: Any) -> list[Any]:
        """The constraints of `{ ... }`, with the comments and directives among them."""
        return self.items(_nodes(block.items), block.closeBrace, convert=self.constraint)

    def constraint(self, node: Any) -> S.Constraint:
        kind = node.kind.name
        if kind == "ConstraintBlock":
            out: Any = S.ConstraintBlock(items=self.constraint_items(node))
        elif kind == "ExpressionConstraint":
            out = S.ExpressionConstraint(soft=bool(node.soft), expression=self.expression(node.expr))
        elif kind == "ImplicationConstraint":
            out = S.ImplicationConstraint(condition=self.expression(node.left), body=self.constraint(node.constraints))
        elif kind == "ConditionalConstraint":
            out = S.ConditionalConstraint(condition=self.expression(node.condition),
                                          consequence=self.constraint(node.constraints))
            if node.elseClause is not None:
                out.alternative = self.constraint(node.elseClause.constraints)
        elif kind == "LoopConstraint":
            loop = node.loopList
            out = S.ForeachConstraint(array=self.expression(loop.arrayName), variables=self.loop_variables(loop),
                                      body=self.constraint(node.constraints))
        elif kind == "SolveBeforeConstraint":
            out = S.SolveBeforeConstraint(solve=[self.expression(e) for e in _nodes(node.beforeExpr)],
                                          before=[self.expression(e) for e in _nodes(node.afterExpr)])
        elif kind == "DisableConstraint":
            out = S.DisableSoftConstraint(target=self.expression(node.name))
        else:  # a UniquenessConstraint: slang has no other kind of constraint
            out = S.UniqueConstraint(set=[self.range_or_expression(r) for r in _nodes(node.ranges.valueRanges)])
        return self.made(node, out)

    def dist(self, node: Any) -> S.DistExpression:
        out = S.DistExpression(value=self.expression(node.expr))
        for item in _nodes(node.distribution.items):
            default = item.kind.name == "DefaultDistItem"
            dist = S.DistItem(value=None if default else self.range_or_expression(item.range))
            if item.weight is not None:
                dist.operator = item.weight.op.rawText + _text(item.weight.extraOp)
                dist.weight = self.expression(item.weight.expr)
            out.items.append(self.made(item, dist))
        return out

    def with_clause(self, node: Any) -> S.Expression:
        """`call with (...)`: with constraints, a `randomize` (whose parentheses list variables); without, an array
        method (whose parentheses hold an expression)."""
        call = self.expression(node.method)
        arguments = [] if node.args is None else _nodes(node.args.expressions)
        if node.constraints is None:
            return S.ArrayMethodWithExpression(call=call, expression=self.expression(arguments[0]))
        variables = []
        for argument in arguments:
            if argument.kind.name != "IdentifierName":
                raise self.unsupported(argument)
            variables.append(self.identifier(argument.identifier))
        return S.RandomizeWithExpression(call=call, restricted=node.args is not None, variables=variables,
                                         items=self.constraint_items(node.constraints))

    def forward_typedef(self, node: Any) -> S.ForwardTypedefDeclaration:
        out = S.ForwardTypedefDeclaration(name=self.identifier(node.name))
        restriction = node.typeRestriction
        if restriction is not None:
            out.keyword = " ".join(t.rawText for t in (restriction.keyword1, restriction.keyword2) if t)
        return out

    def tf_port(self, node: Any) -> S.TfPort:
        if bool(node.constKeyword) or bool(node.staticKeyword):
            raise self.unsupported(node)
        declarator = node.declarator
        out = S.TfPort(direction=_text(node.direction) or None, var=bool(node.varKeyword),
                       type=self.data_type(node.dataType), name=self.identifier(declarator.name),
                       dimensions=[self.dimension(d) for d in _nodes(declarator.dimensions)])
        if declarator.initializer is not None:
            out.value = self.expression(declarator.initializer.expr)
        return out

    # Generate constructs

    def generate_region(self, node: Any) -> S.GenerateRegion:
        return S.GenerateRegion(items=self.items(_nodes(node.members), node.endgenerate))

    def generate_body(self, node: Any) -> Any:
        return self.item(node)

    def generate_block(self, node: Any) -> S.GenerateBlock:
        out = S.GenerateBlock()
        if node.label is not None:
            out.name = self.identifier(node.label.name)
        elif node.beginName is not None:
            out.name = self.identifier(node.beginName.name)
        out.labeled = node.endName is not None
        out.items = self.items(_nodes(node.members), node.end)
        return out

    def loop_generate(self, node: Any) -> S.GenerateFor:
        return S.GenerateFor(genvar=bool(node.genvar), name=self.identifier(node.identifier),
                             start=self.expression(node.initialExpr), condition=self.expression(node.stopExpr),
                             step=self.expression(node.iterationExpr), body=self.generate_body(node.block))

    def if_generate(self, node: Any) -> S.GenerateIf:
        out = S.GenerateIf(condition=self.expression(node.condition), consequence=self.generate_body(node.block))
        if node.elseClause is not None:
            out.alternative = self.generate_body(node.elseClause.clause)
        return out

    def case_generate(self, node: Any) -> S.GenerateCase:
        out = S.GenerateCase(expression=self.expression(node.condition))
        for item in _nodes(node.items):
            if item.kind.name == "DefaultCaseItem":
                out.items.append(self.made(item, S.CaseItem(body=self.generate_body(item.clause))))
            else:
                values = [self.expression(e) for e in _nodes(item.expressions)]
                out.items.append(self.made(item, S.CaseItem(expressions=values, body=self.generate_body(item.clause))))
        return out

    # Instantiation

    def parameter_values(self, node: Any) -> list[Any]:
        """The values of `#(...)`: ordered expressions or types, or `NamedConnection`s; none without it."""
        out: list[Any] = []
        if node is None:
            return out
        for assignment in _nodes(node.parameters):
            if assignment.kind.name == "OrderedParamAssignment":
                out.append(self.expression_or_type(assignment.expr))
            else:
                connection = S.NamedConnection(name=self.identifier(assignment.name))
                if assignment.expr is not None:
                    connection.value = self.expression_or_type(assignment.expr)
                out.append(self.made(assignment, connection))
        return out

    def instantiation(self, node: Any) -> S.ModuleInstantiation:
        out = S.ModuleInstantiation(module=self.identifier(node.type),
                                    parameters=self.parameter_values(node.parameters))
        for instance in _nodes(node.instances):
            declaration = instance.decl
            item = S.Instance(name=self.identifier(declaration.name),
                              dimensions=[self.dimension(d) for d in _nodes(declaration.dimensions)])
            for connection in _nodes(instance.connections):
                kind = connection.kind.name
                if kind == "OrderedPortConnection":  # an empty one is an EmptyPortConnection
                    item.connections.append(self.expression(connection.expr))
                elif kind == "NamedPortConnection":
                    named = S.NamedConnection(name=self.identifier(connection.name),
                                              implicit=not connection.openParen)
                    if connection.expr is not None:
                        named.value = self.expression(connection.expr)
                    item.connections.append(self.made(connection, named))
                elif kind == "WildcardPortConnection":
                    item.connections.append(self.made(connection, S.WildcardConnection()))
                else:
                    raise self.unsupported(connection)
            out.instances.append(self.made(instance, item))
        return out

    def expression_or_type(self, node: Any) -> Any:
        while node.kind.name in ("SimplePropertyExpr", "SimpleSequenceExpr") \
                and getattr(node, "repetition", None) is None:
            node = node.expr  # what slang reads as a property, then a sequence, when it may be one
        if node.kind.name.endswith("Type") and node.kind.name not in ("NamedType",):
            return self.data_type(node)
        return self.expression(node)

    # Statements

    def statement(self, node: Any) -> S.Statement:
        label = getattr(node, "label", None)
        kind = node.kind.name
        method = self.STATEMENTS.get(kind)
        if method is None:
            raise self.unsupported(node)
        out = method(self, node)
        if label is not None:
            if isinstance(out, (S.SeqBlock, S.ParBlock)) and out.name is None:  # `x: begin` is `begin : x`
                out.name = self.identifier(label.name)
            else:
                out = S.LabeledStatement(label=self.identifier(label.name), statement=self.made(node, out))
        return self.made(node, out)

    def optional_statement(self, node: Any) -> S.Statement | None:
        if node is None or node.kind.name == "EmptyStatement":
            return None
        return self.statement(node)

    def expression_statement(self, node: Any) -> S.Statement:
        expression = node.expr
        if expression.kind.name in _ASSIGNMENTS or expression.kind.name == "NonblockingAssignmentExpression":
            out = S.AssignmentStatement(target=self.expression(expression.left), operator=self.token_text(
                expression.operatorToken))
            value = expression.right
            if value.kind.name == "TimingControlExpression":
                out.timing = self.timing(value.timing)
                value = value.expr
            out.value = self.expression(value)
            return out
        return S.ExpressionStatement(expression=self.expression(expression))

    def empty(self, node: Any) -> S.NullStatement:
        return S.NullStatement()

    def block(self, node: Any) -> S.Statement:
        out: Any = S.SeqBlock() if node.kind.name == "SequentialBlockStatement" else S.ParBlock(join=node.end.rawText)
        if node.blockName is not None:
            out.name = self.identifier(node.blockName.name)
        out.labeled = node.endBlockName is not None
        out.items = self.items(_nodes(node.items), node.end, statements=True)
        return out

    def conditional(self, node: Any) -> S.IfStatement:
        out = S.IfStatement(qualifier=_text(node.uniqueOrPriority) or None, condition=self.predicate(node.predicate),
                            consequence=self.statement(node.statement))
        if node.elseClause is not None:
            out.alternative = self.statement(node.elseClause.clause)
        return out

    def predicate(self, node: Any) -> S.Expression:
        conditions = _nodes(node.conditions)
        if len(conditions) != 1 or conditions[0].matchesClause is not None:
            raise self.unsupported(node)
        return self.expression(conditions[0].expr)

    def case(self, node: Any) -> S.CaseStatement:
        inside = _text(node.matchesOrInside)
        if inside == "matches":
            raise self.unsupported(node)
        out = S.CaseStatement(qualifier=_text(node.uniqueOrPriority) or None, keyword=node.caseKeyword.rawText,
                              expression=self.expression(node.expr), inside=inside == "inside")
        for item in _nodes(node.items):
            if item.kind.name == "DefaultCaseItem":
                out.items.append(self.made(item, S.CaseItem(body=self.statement(item.clause))))
            else:  # a StandardCaseItem: a PatternCaseItem is only in `case matches`
                values = [self.range_or_expression(e) for e in _nodes(item.expressions)]
                out.items.append(self.made(item, S.CaseItem(expressions=values, body=self.statement(item.clause))))
        return out

    def loop(self, node: Any) -> S.Statement:
        keyword = node.repeatOrWhile.rawText
        if keyword == "repeat":
            return S.RepeatStatement(count=self.expression(node.expr), body=self.statement(node.statement))
        return S.WhileStatement(condition=self.expression(node.expr), body=self.statement(node.statement))

    def do_while(self, node: Any) -> S.DoWhileStatement:
        return S.DoWhileStatement(body=self.statement(node.statement), condition=self.expression(node.expr))

    def forever(self, node: Any) -> S.ForeverStatement:
        return S.ForeverStatement(body=self.statement(node.statement))

    def for_loop(self, node: Any) -> S.ForStatement:
        out = S.ForStatement(body=self.statement(node.statement))
        for initializer in _nodes(node.initializers):
            if initializer.kind.name == "ForVariableDeclaration":
                declarator = initializer.declarator
                item = S.VariableDeclarator(name=self.identifier(declarator.name))
                if declarator.initializer is not None:
                    item.value = self.expression(declarator.initializer.expr)
                declaration = S.VariableDeclaration(var=bool(initializer.varKeyword),
                                                    type=self.data_type(initializer.type),
                                                    declarators=[self.made(declarator, item)])
                out.initializers.append(self.made(initializer, declaration))
            else:  # slang reads only assignments
                out.initializers.append(self.expression(initializer))
        if node.stopExpr is not None:
            out.condition = self.expression(node.stopExpr)
        out.steps = [self.expression(s) for s in _nodes(node.steps)]
        return out

    def loop_variables(self, loop: Any) -> list[S.Identifier]:
        """The index variables of `foreach (array[variables])`, none of which may be skipped."""
        variables = []
        for variable in _nodes(loop.loopVariables):
            if variable.kind.name == "EmptyIdentifierName":
                raise self.unsupported(variable)
            token = variable.identifier if hasattr(variable, "identifier") else variable.name
            variables.append(self.identifier(token))
        return variables

    def foreach(self, node: Any) -> S.ForeachStatement:
        loop = node.loopList
        return S.ForeachStatement(array=self.expression(loop.arrayName), variables=self.loop_variables(loop),
                                  body=self.statement(node.statement))

    def void_call(self, node: Any) -> S.ExpressionStatement:
        """`void'(call);`: a function's result, discarded, as an expression statement of the cast."""
        cast = S.CastExpression(type=self.made(node, S.KeywordType(keyword="void")), value=self.expression(node.expr))
        return S.ExpressionStatement(expression=self.made(node, cast))

    def randcase(self, node: Any) -> S.RandCaseStatement:
        return S.RandCaseStatement(items=[self.made(i, S.RandCaseItem(weight=self.expression(i.expr),
                                                                      body=self.statement(i.statement)))
                                          for i in _nodes(node.items)])

    def jump(self, node: Any) -> S.Statement:
        return S.BreakStatement() if node.breakOrContinue.rawText == "break" else S.ContinueStatement()

    def return_statement(self, node: Any) -> S.ReturnStatement:
        return S.ReturnStatement(value=None if node.returnValue is None else self.expression(node.returnValue))

    def timing_statement(self, node: Any) -> S.TimedStatement:
        return S.TimedStatement(timing=self.timing(node.timingControl), body=self.optional_statement(node.statement))

    def wait(self, node: Any) -> S.WaitStatement:
        return S.WaitStatement(condition=self.expression(node.expr), body=self.optional_statement(node.statement))

    def trigger(self, node: Any) -> S.EventTrigger:
        if node.timing is not None:
            raise self.unsupported(node)
        return S.EventTrigger(nonblocking=node.trigger.rawText == "->>", event=self.expression(node.name))

    def disable(self, node: Any) -> S.DisableStatement:
        return S.DisableStatement(target=self.expression(node.name))

    def disable_fork(self, node: Any) -> S.DisableStatement:
        return S.DisableStatement()

    def assertion(self, node: Any) -> S.ImmediateAssertion:
        expression = node.expr.expression  # its parentheses are the statement's own
        out = S.ImmediateAssertion(keyword=node.keyword.rawText, expression=self.expression(expression))
        if node.delay is not None:
            out.deferral = "final" if bool(node.delay.finalKeyword) else "#0"
        out.pass_action = self.optional_statement(node.action.statement)  # at least `;`
        if node.action.elseClause is not None:
            out.fail_action = self.optional_statement(node.action.elseClause.clause)
        return out

    # Assertions

    def actions(self, node: Any, out: Any) -> Any:
        """`out` with the actions of an action block: what passes, and after `else` what fails."""
        out.pass_action = self.optional_statement(node.statement)  # at least `;`
        if node.elseClause is not None:
            out.fail_action = self.optional_statement(node.elseClause.clause)
        return out

    def concurrent(self, node: Any) -> S.ConcurrentAssertion:
        return self.actions(node.action, S.ConcurrentAssertion(
            keyword=node.keyword.rawText, sequence=node.propertyOrSequence.rawText == "sequence",
            spec=self.property_spec(node.propertySpec)))

    def expect(self, node: Any) -> S.ExpectStatement:
        return self.actions(node.action, S.ExpectStatement(spec=self.property_spec(node.propertySpec)))

    def assertion_item(self, node: Any) -> S.AssertionItem:
        """A concurrent or a deferred immediate assertion among items, with its label."""
        statement = node.statement
        convert = self.assertion if node.kind.name == "ImmediateAssertionMember" else self.concurrent
        out = S.AssertionItem(assertion=self.made(statement, convert(statement)))
        if statement.label is not None:
            out.label = self.identifier(statement.label.name)
        return out

    def property_spec(self, node: Any) -> S.PropertySpec:
        out = S.PropertySpec(property=self.property(node.expr))
        if node.clocking is not None:
            out.clock = self.timing(node.clocking)
        if node.disable is not None:
            out.disable = self.expression(node.disable.expr)  # its parentheses are the clause's own
        return self.made(node, out)

    def assertion_ports(self, node: Any) -> list[S.AssertionPort]:
        out = []
        for port in [] if node is None else _nodes(node.ports):
            item = S.AssertionPort(local=bool(port.local), direction=_text(port.direction) or None,
                                   type=self.data_type(port.type), name=self.identifier(port.name),
                                   dimensions=[self.dimension(d) for d in _nodes(port.dimensions)])
            if port.defaultValue is not None:
                item.value = self.property(port.defaultValue.expr)
            out.append(self.made(port, item))
        return out

    def local_variables(self, node: Any) -> list[S.VariableDeclaration]:
        return [self.made(v, S.VariableDeclaration(var=bool(v.var), type=self.data_type(v.type),
                                                   declarators=self.declarators(v.declarators)))
                for v in _nodes(node.variables)]

    def property_declaration(self, node: Any) -> S.PropertyDeclaration:
        return S.PropertyDeclaration(name=self.identifier(node.name), ports=self.assertion_ports(node.portList),
                                     variables=self.local_variables(node), spec=self.property_spec(node.propertySpec),
                                     labeled=node.endBlockName is not None)

    def sequence_declaration(self, node: Any) -> S.SequenceDeclaration:
        return S.SequenceDeclaration(name=self.identifier(node.name), ports=self.assertion_ports(node.portList),
                                     variables=self.local_variables(node), sequence=self.sequence(node.seqExpr),
                                     labeled=node.endBlockName is not None)

    def let_declaration(self, node: Any) -> S.LetDeclaration:
        return S.LetDeclaration(name=self.identifier(node.identifier), ports=self.assertion_ports(node.portList),
                                value=self.expression(node.expr))

    def cycle_range(self, node: Any) -> Any:
        """A number of ticks or repetitions, `[n]`, or a range of them, `[low:high]`."""
        if node.kind.name == "BitSelect":
            return self.expression(node.expr)
        # a SimpleRangeSelect: slang refuses any other range of ticks
        return self.made(node, S.CycleRange(low=self.expression(node.left), high=self.expression(node.right)))

    def unbounded(self, at: Any, low: str) -> S.CycleRange:
        """`[low:$]`, which `[*]` and `[+]` stand for."""
        return self.made(at, S.CycleRange(low=self.made(at, S.IntegerLiteral(spelling=low)),
                                          high=self.made(at, S.DollarExpression())))

    def sequence(self, node: Any) -> Any:
        """A sequence, or an expression where the sequence is one."""
        kind = node.kind.name
        if kind == "SimplePropertyExpr":
            return self.sequence(node.expr)
        if kind == "SimpleSequenceExpr":
            return self.repeated(node, self.expression(node.expr))
        if kind == "DelayedSequenceExpr":
            out: Any = S.DelaySequence(first=None if node.first is None else self.sequence(node.first))
            for element in _nodes(node.elements):
                if element.delayVal is not None:
                    delay = self.expression(element.delayVal)
                elif element.range is not None:
                    delay = self.cycle_range(element.range)
                else:  # `##[*]`, `##[+]`
                    delay = self.unbounded(element, "0" if element.op.rawText == "*" else "1")
                out.steps.append(self.made(element, S.DelayStep(delay=delay, sequence=self.sequence(element.expr))))
        elif kind in ("AndSequenceExpr", "OrSequenceExpr", "IntersectSequenceExpr", "WithinSequenceExpr",
                      "ThroughoutSequenceExpr"):
            out = S.BinarySequence(left=self.sequence(node.left), operator=node.op.rawText,
                                   right=self.sequence(node.right))
        elif kind == "ParenthesizedSequenceExpr":
            out = S.ParenthesizedSequence(sequence=self.sequence(node.expr), items=self.match_items(node.matchList))
            return self.repeated(node, self.made(node, out))
        elif kind == "FirstMatchSequenceExpr":
            out = S.FirstMatchSequence(sequence=self.sequence(node.expr), items=self.match_items(node.matchList))
        else:  # a ClockingSequenceExpr: slang reads nothing else where a sequence is
            out = S.ClockedSequence(clock=self.timing(node.event), sequence=self.sequence(node.expr))
        return self.made(node, out)

    def repeated(self, node: Any, out: Any) -> Any:
        """`out` with the repetition `node` gives it, if any: `[*n]`, `[->n]`, `[=n]`, `[*]` or `[+]`."""
        repetition = node.repetition
        if repetition is None:
            return out
        operator = repetition.op.rawText
        if repetition.selector is not None:
            count = self.cycle_range(repetition.selector)
        else:
            count = self.unbounded(repetition, "0" if operator == "*" else "1")
            operator = "*"
        return self.made(node, S.RepetitionSequence(sequence=out, operator=operator, count=count))

    def match_items(self, node: Any) -> list[Any]:
        return [] if node is None else [self.expression(i) for i in _nodes(node.items)]

    def property(self, node: Any) -> Any:
        """A property, or a sequence or an expression where the property is one (in a SimplePropertyExpr)."""
        kind = node.kind.name
        if kind == "SimplePropertyExpr":
            return self.sequence(node.expr)
        if kind in ("ImplicationPropertyExpr", "FollowedByPropertyExpr"):
            out: Any = S.ImplicationProperty(antecedent=self.sequence(node.left), operator=node.op.rawText,
                                             consequent=self.property(node.right))
        elif node.__class__.__name__ == "BinaryPropertyExprSyntax":
            out = S.BinaryProperty(left=self.property(node.left), operator=node.op.rawText,
                                   right=self.property(node.right))
        elif kind == "UnaryPropertyExpr":
            out = S.UnaryProperty(operator=node.op.rawText, operand=self.property(node.expr))
        elif kind == "UnarySelectPropertyExpr":
            out = S.UnaryProperty(operator=node.op.rawText, operand=self.property(node.expr),
                                  range=None if node.selector is None else self.cycle_range(node.selector))
        elif kind == "StrongWeakPropertyExpr":
            out = S.StrengthProperty(keyword=node.keyword.rawText, sequence=self.sequence(node.expr))
        elif kind == "AcceptOnPropertyExpr":
            out = S.AbortProperty(keyword=node.keyword.rawText, condition=self.expression(node.condition),
                                  operand=self.property(node.expr))
        elif kind == "ConditionalPropertyExpr":
            out = S.ConditionalProperty(condition=self.expression(node.condition), consequence=self.property(node.expr))
            if node.elseClause is not None:
                out.alternative = self.property(node.elseClause.expr)
        elif kind == "CasePropertyExpr":
            items = []
            for item in _nodes(node.items):
                expressions = [] if item.kind.name == "DefaultPropertyCaseItem" else [
                    self.expression(e) for e in _nodes(item.expressions)]
                body = self.property(item.expr)
                items.append(self.made(item, S.PropertyCaseItem(expressions=expressions, body=body)))
            out = S.CaseProperty(expression=self.expression(node.expr), items=items)
        elif kind == "ParenthesizedPropertyExpr":
            if node.matchList is not None:
                raise self.unsupported(node)
            out = S.ParenthesizedProperty(property=self.property(node.expr))
        else:  # a ClockingPropertyExpr: slang wraps a sequence where a property is in a SimplePropertyExpr
            out = S.ClockedProperty(clock=self.timing(node.event), property=self.property(node.expr))
        return self.made(node, out)

    # Coverage

    def covergroup(self, node: Any) -> S.CovergroupDeclaration:
        if node.extends:  # IEEE 1800-2023's `covergroup extends`: not a kind yet
            raise self.unsupported(node)
        out = S.CovergroupDeclaration(name=self.identifier(node.name), labeled=node.endBlockName is not None)
        if node.portList is not None:
            out.ports = [self.made(p, self.tf_port(p)) for p in _nodes(node.portList.ports)]
        event = node.event
        if event is not None:
            if event.kind.name == "WithFunctionSample":
                ports = [] if event.portList is None else [self.made(p, self.tf_port(p))
                                                           for p in _nodes(event.portList.ports)]
                out.sample = self.made(event, S.SampleFunction(ports=ports))
            elif event.kind.name == "BlockCoverageEvent":  # `@@(begin f)`: not a kind yet
                raise self.unsupported(event)
            else:
                out.clock = self.timing(event)
        out.items = self.items(_nodes(node.members), node.endgroup, convert=self.coverage_item)
        return out

    def coverage_item(self, node: Any) -> Any:
        """An item of a covergroup, a coverpoint or a cross: an option, a coverpoint, a cross, a bin, or a function."""
        kind = node.kind.name
        if kind == "CoverageOption":
            out: Any = S.CoverageOption(target=self.expression(node.expr.left), value=self.expression(node.expr.right))
        elif kind == "Coverpoint":
            out = S.Coverpoint(type=self.data_type(node.type), expression=self.expression(node.expr),
                               condition=self.coverage_condition(node.iff))
            if node.label is not None:
                out.label = self.identifier(node.label.name)
            if not node.emptySemi:
                out.items = self.items(_nodes(node.members), node.closeBrace, convert=self.coverage_item)
        elif kind == "CoverageBins":
            out = S.CoverageBins(wildcard=bool(node.wildcard), keyword=node.keyword.rawText,
                                 name=self.identifier(node.name),
                                 array=node.size is not None, initializer=self.bins_initializer(node.initializer),
                                 condition=self.coverage_condition(node.iff))
            if node.size is not None and node.size.expr is not None:
                out.size = self.expression(node.size.expr)
        elif kind == "CoverCross":
            out = S.CoverCross(items=[self.expression(i) for i in _nodes(node.items)],
                               condition=self.coverage_condition(node.iff))
            if node.label is not None:
                out.label = self.identifier(node.label.name)
            if not node.emptySemi:
                out.body = self.items(_nodes(node.members), node.closeBrace, convert=self.coverage_item)
        elif kind == "BinsSelection":
            out = S.BinsSelection(keyword=node.keyword.rawText, name=self.identifier(node.name),
                                  select=self.bins_select(node.expr), condition=self.coverage_condition(node.iff))
        else:
            return self.item(node)
        return self.made(node, out)

    def coverage_condition(self, node: Any) -> Any:
        return None if node is None else self.expression(node.expr)  # `iff (condition)`: its parentheses are its own

    def with_filter(self, node: Any) -> Any:
        return None if node is None else self.expression(node.expr)

    def bins_initializer(self, node: Any) -> Any:
        kind = node.kind.name
        if kind == "RangeCoverageBinInitializer":
            out: Any = S.BinsValues(values=[self.range_or_expression(r) for r in _nodes(node.ranges.valueRanges)],
                                    filter=self.with_filter(node.withClause))
        elif kind == "DefaultCoverageBinInitializer":
            out = S.BinsDefault(sequence=bool(node.sequenceKeyword))
        elif kind == "IdWithExprCoverageBinInitializer":
            name = self.made(node, S.NameExpression(name=self.identifier(node.id)))
            out = S.BinsExpression(expression=name, filter=self.with_filter(node.withClause))
        elif kind == "ExpressionCoverageBinInitializer":
            out = S.BinsExpression(expression=self.expression(node.expr))
        else:  # a TransListCoverageBinInitializer: slang has no other initializer
            sequences = []
            for transition in _nodes(node.sets):
                steps = []
                for step in _nodes(transition.ranges):
                    item = S.TransitionStep(values=[self.range_or_expression(v) for v in _nodes(step.items)])
                    if step.repeat is not None:
                        item.operator = step.repeat.specifier.rawText
                        item.count = self.cycle_range(step.repeat.selector)
                    steps.append(self.made(step, item))
                sequences.append(self.made(transition, S.TransitionSequence(steps=steps)))
            out = S.BinsTransitions(sequences=sequences)
        return self.made(node, out)

    def bins_select(self, node: Any) -> Any:
        """A select expression, or the expression it is."""
        kind = node.kind.name
        if kind == "SimpleBinsSelectExpr":
            if node.matchesClause is not None:  # `matches`: not a kind yet
                raise self.unsupported(node)
            return self.expression(node.expr)
        if kind == "BinsSelectConditionExpr":
            out: Any = S.BinsOf(target=self.expression(node.name))
            if node.intersects is not None:
                out.intersect = [self.range_or_expression(r) for r in _nodes(node.intersects.ranges.valueRanges)]
        elif kind == "BinaryBinsSelectExpr":
            out = S.BinaryBinsSelect(left=self.bins_select(node.left), operator=node.op.rawText,
                                     right=self.bins_select(node.right))
        elif kind == "UnaryBinsSelectExpr":
            out = S.NotBinsSelect(operand=self.bins_select(node.expr))
        elif kind == "ParenthesizedBinsSelectExpr":
            out = S.ParenthesizedBinsSelect(select=self.bins_select(node.expr))
        else:  # a BinSelectWithFilterExpr: slang has no other select expression
            if node.matchesClause is not None:
                raise self.unsupported(node)
            out = S.FilteredBinsSelect(select=self.bins_select(node.expr), filter=self.expression(node.filter))
        return self.made(node, out)

    # Clocking blocks

    def clocking_declaration(self, node: Any) -> S.ClockingDeclaration:
        out = S.ClockingDeclaration(scope=_text(node.globalOrDefault) or None, labeled=node.endBlockName is not None,
                                    clock=self.made(node.event, S.EventControl(events=self.events(node.event))))
        if node.blockName.rawText:  # a default clocking block may have no name
            out.name = self.identifier(node.blockName)
        out.items = self.items(_nodes(node.items), node.endClocking, convert=self.clocking_item)
        return out

    def clocking_item(self, node: Any) -> Any:
        kind = node.kind.name
        if kind == "DefaultSkewItem":
            direction = node.direction
            out: Any = S.DefaultSkew(input=self.skew(direction.inputSkew), output=self.skew(direction.outputSkew))
        elif kind == "ClockingItem":
            direction = node.direction
            words = [t.rawText for t in (direction.input, direction.output) if t]
            out = S.ClockingSignals(direction=" ".join(words), input_skew=self.skew(direction.inputSkew),
                                    output_skew=self.skew(direction.outputSkew))
            for declaration in _nodes(node.decls):
                signal = S.ClockingSignal(name=self.identifier(declaration.name))
                if declaration.value is not None:
                    signal.value = self.expression(declaration.value.expr)
                out.signals.append(self.made(declaration, signal))
        else:
            return self.item(node)
        return self.made(node, out)

    def skew(self, node: Any) -> S.ClockingSkew | None:
        if node is None:
            return None
        out = S.ClockingSkew(edge=_text(node.edge) or None)
        delay = node.delay
        if delay is not None:
            value = self.made(delay, S.TimeLiteral(spelling="1step")) if delay.kind.name == "OneStepDelay" \
                else self.expression(delay.delayValue)
            out.delay = self.made(delay, S.DelayControl(value=value))
        return self.made(node, out)

    def default_clocking(self, node: Any) -> S.DefaultClocking:
        return S.DefaultClocking(name=self.identifier(node.name))

    def default_disable(self, node: Any) -> S.DefaultDisable:
        return S.DefaultDisable(condition=self.expression(node.expr))

    # Timing controls

    def timing(self, node: Any) -> S.TimingControl:
        kind = node.kind.name
        if kind == "DelayControl":
            return self.delay(node)
        if kind == "EventControl":
            return self.made(node, S.EventControl(events=[self.made(node, S.EventExpression(
                expression=self.expression(node.eventName)))]))
        if kind == "EventControlWithExpression":
            return self.made(node, S.EventControl(events=self.events(node.expr)))
        if kind == "ImplicitEventControl":
            return self.made(node, S.EventControl())
        if kind == "CycleDelay":
            return self.made(node, S.CycleDelay(value=self.expression(node.delayValue)))
        raise self.unsupported(node)

    def delay(self, node: Any) -> S.DelayControl:
        if node.kind.name == "Delay3":  # a net's or an assignment's `#(value)`; rise, fall and turn-off delays: refused
            if node.delay2 is not None:
                raise self.unsupported(node)
            value = self.made(node, S.ParenthesizedExpression(expression=self.expression(node.delay1)))
            return self.made(node, S.DelayControl(value=value))
        return self.made(node, S.DelayControl(value=self.expression(node.delayValue)))

    def events(self, node: Any) -> list[S.EventExpression]:
        kind = node.kind.name
        if kind == "BinaryEventExpression":
            return self.events(node.left) + self.events(node.right)
        if kind == "ParenthesizedEventExpression":
            return self.events(node.expr)
        out = S.EventExpression(edge=_text(node.edge) or None, expression=self.expression(node.expr))  # a signal
        if node.iffClause is not None:
            out.condition = self.expression(node.iffClause.expr)
        return [self.made(node, out)]

    # Expressions

    def expression(self, node: Any) -> S.Expression:
        macro = self.macro_use(node)
        if macro is not None:
            return macro
        kind = node.kind.name
        if kind in ("SimplePropertyExpr", "SimpleSequenceExpr"):
            if getattr(node, "repetition", None) is not None:
                raise self.unsupported(node)
            return self.expression(node.expr)
        method = self.EXPRESSIONS.get(kind)
        if method is None:
            if kind in _ASSIGNMENTS:
                method = _Reader.assignment
            elif node.__class__.__name__ == "BinaryExpressionSyntax":
                method = _Reader.binary
            elif node.__class__.__name__ == "LiteralExpressionSyntax":
                method = _Reader.literal
            elif node.__class__.__name__ == "PrefixUnaryExpressionSyntax":
                method = _Reader.prefix
            elif node.__class__.__name__ == "PostfixUnaryExpressionSyntax":
                method = _Reader.postfix
            else:
                raise self.unsupported(node)
        return self.made(node, method(self, node))

    def macro_use(self, node: Any) -> S.MacroUsage | None:
        """A `MacroUsage` for an expression whose tokens all come from one macro expansion."""
        tokens = list(_tokens(node))
        first = tokens[0]
        usage = next((t.syntax() for t in first.trivia if t.kind.name == "Directive"
                      and t.syntax().kind.name == "MacroUsage"), None)
        if usage is None or not self.manager.isMacroLoc(first.location):
            return None
        site = self.location(first)
        if any(not self.manager.isMacroLoc(t.location) or self.location(t) != site for t in tokens) \
                or len(tokens) != self.expansions.get(site.offset, 0):  # the whole expansion, not a part of it
            return None
        for token in tokens:
            self.macros.add(id(token))
        name = usage.directive.rawText[1:]
        out = S.MacroUsage(name=self.made(usage, S.Identifier(spelling=name)))
        if usage.args is not None:
            out.arguments = self.directive_text(usage.args)[1:-1]
        return self.made(usage, out)

    def binary(self, node: Any) -> S.BinaryExpression:
        return S.BinaryExpression(left=self.expression(node.left), operator=self.token_text(node.operatorToken),
                                  right=self.expression(node.right))

    def assignment(self, node: Any) -> S.AssignmentExpression:
        return S.AssignmentExpression(target=self.expression(node.left), operator=self.token_text(node.operatorToken),
                                      value=self.expression(node.right))

    def prefix(self, node: Any) -> S.Expression:
        operator = self.token_text(node.operatorToken)
        if operator in ("++", "--"):
            return S.IncrementExpression(operator=operator, operand=self.expression(node.operand))
        return S.UnaryExpression(operator=operator, operand=self.expression(node.operand))

    def postfix(self, node: Any) -> S.IncrementExpression:
        return S.IncrementExpression(operator=self.token_text(node.operatorToken), postfix=True,
                                     operand=self.expression(node.operand))

    def literal(self, node: Any) -> S.Expression:
        kind = node.kind.name
        text = self.token_text(node.literal)
        if kind == "IntegerLiteralExpression":
            return S.IntegerLiteral(spelling=text)
        if kind == "RealLiteralExpression":
            return S.RealLiteral(spelling=text)
        if kind == "TimeLiteralExpression":
            return S.TimeLiteral(spelling=text)
        if kind == "UnbasedUnsizedLiteralExpression":
            return S.UnbasedUnsizedLiteral(value=text[1:])
        if kind == "StringLiteralExpression":
            if text.startswith('"""'):
                return S.StringLiteral(text=text[3:-3], triple=True)
            return S.StringLiteral(text=text[1:-1])
        return S.DollarExpression()  # a WildcardLiteralExpression, `$`: the literals' last kind

    def vector(self, node: Any) -> S.IntegerLiteral:
        return S.IntegerLiteral(spelling=self.spelling(node))

    def identifier_name(self, node: Any) -> S.Expression:
        return S.NameExpression(name=self.identifier(node.identifier))

    def identifier_select(self, node: Any) -> S.Expression:
        value: S.Expression = self.made(node.identifier, S.NameExpression(name=self.identifier(node.identifier)))
        for select in _nodes(node.selectors):
            value = self.select(select, value)
        return value

    def select(self, node: Any, value: S.Expression) -> S.Expression:
        selector = node.selector
        kind = selector.kind.name
        if kind == "BitSelect":
            return self.made(node, S.IndexExpression(value=value, index=self.expression(selector.expr)))
        operator = {"SimpleRangeSelect": ":", "AscendingRangeSelect": "+:", "DescendingRangeSelect": "-:"}[kind]
        return self.made(node, S.RangeSelect(value=value, left=self.expression(selector.left), operator=operator,
                                             right=self.expression(selector.right)))

    def element_select(self, node: Any) -> S.Expression:
        return self.select(node.select, self.expression(node.left))

    def scoped(self, node: Any) -> S.Expression:
        if node.separator.rawText == "::":
            return S.NameExpression(name=self.name(node))
        right = node.right
        value = self.expression(node.left)
        if right.kind.name == "IdentifierName":
            return S.MemberExpression(value=value, member=self.identifier(right.identifier))
        if right.kind.name == "IdentifierSelectName":
            member = self.identifier(right.identifier)
            out: S.Expression = self.made(right, S.MemberExpression(value=value, member=member))
            for select in _nodes(right.selectors):
                out = self.select(select, out)
            return out
        raise self.unsupported(node)

    def member_access(self, node: Any) -> S.MemberExpression:
        return S.MemberExpression(value=self.expression(node.left), member=self.identifier(node.name))

    def conditional_expression(self, node: Any) -> S.ConditionalExpression:
        return S.ConditionalExpression(condition=self.predicate(node.predicate), consequence=self.expression(node.left),
                                       alternative=self.expression(node.right))

    def inside(self, node: Any) -> S.InsideExpression:
        return S.InsideExpression(value=self.expression(node.expr),
                                  set=[self.range_or_expression(r) for r in _nodes(node.ranges.valueRanges)])

    def range_or_expression(self, node: Any) -> Any:
        if node.kind.name == "ValueRangeExpression":
            if node.op and node.op.rawText != ":":
                raise self.unsupported(node)
            return self.made(node, S.ValueRange(left=self.expression(node.left), right=self.expression(node.right)))
        return self.expression(node)

    def concatenation(self, node: Any) -> S.Concatenation:
        return S.Concatenation(items=[self.expression(e) for e in _nodes(node.expressions)])

    def replication(self, node: Any) -> S.Replication:
        return S.Replication(count=self.expression(node.expression),
                             items=[self.expression(e) for e in _nodes(node.concatenation.expressions)])

    def pattern(self, node: Any) -> S.AssignmentPattern:
        out = S.AssignmentPattern(type=None if node.type is None else self.data_type(node.type))
        pattern = node.pattern
        kind = pattern.kind.name
        if kind == "SimpleAssignmentPattern":
            out.items = [self.expression(e) for e in _nodes(pattern.items)]
        elif kind == "StructuredAssignmentPattern":
            for item in _nodes(pattern.items):
                key = item.key
                entry = S.PatternItem(value=self.expression(item.expr))
                if key.kind.name == "DefaultPatternKeyExpression":
                    entry.key = None
                elif key.kind.name.endswith("Type") and key.kind.name != "NamedType":
                    entry.key = self.data_type(key)
                else:
                    entry.key = self.expression(key)
                out.items.append(self.made(item, entry))
        else:
            raise self.unsupported(pattern)
        return out

    def invocation(self, node: Any) -> S.Expression:
        left = node.left
        arguments = [] if node.arguments is None else self.arguments(node.arguments)
        if left.kind.name == "SystemName":
            return S.SystemCall(name=self.token_text(left.systemIdentifier), arguments=arguments)
        return S.CallExpression(callee=self.expression(left), arguments=arguments)

    def arguments(self, node: Any) -> list[Any]:
        out: list[Any] = []
        for argument in _nodes(node.parameters):
            kind = argument.kind.name
            if kind == "OrderedArgument":
                out.append(self.expression_or_type(argument.expr))
            elif kind == "NamedArgument":
                named = S.NamedConnection(name=self.identifier(argument.name))
                if argument.expr is not None:
                    named.value = self.expression(argument.expr)
                out.append(self.made(argument, named))
            else:  # an EmptyArgument
                raise self.unsupported(argument)
        return out

    def system_name(self, node: Any) -> S.SystemCall:
        return S.SystemCall(name=self.token_text(node.systemIdentifier))

    def cast(self, node: Any) -> S.CastExpression:
        target = node.left
        value = node.right.expression  # a cast's parentheses are its own
        kind = target.kind.name
        if kind.endswith("Type") and kind not in ("NamedType",) or kind == "ImplicitType":
            cast_type: Any = self.data_type(target)
        else:
            cast_type = self.expression(target)
        return S.CastExpression(type=cast_type, value=self.expression(value))

    def signed_cast(self, node: Any) -> S.CastExpression:
        return S.CastExpression(type=self.made(node, S.ImplicitType(signing=node.signing.rawText)),
                                value=self.expression(node.inner.expression))

    def new_class(self, node: Any) -> S.NewExpression:
        out = S.NewExpression(arguments=[] if node.argList is None else self.arguments(node.argList))
        scoped = node.scopedNew
        if scoped.kind.name == "ScopedName":  # `super.new` or `c::new`
            left = scoped.left
            out.scope = self.made(left, S.SuperExpression()) if left.kind.name == "SuperHandle" else self.name(left)
        return out

    def copy_class(self, node: Any) -> S.NewCopyExpression:
        return S.NewCopyExpression(value=self.expression(node.expr))

    def new_array(self, node: Any) -> S.NewArrayExpression:
        out = S.NewArrayExpression(size=self.expression(node.sizeExpr))
        if node.initializer is not None:
            out.value = self.expression(node.initializer.expression)  # its parentheses are the expression's own
        return out

    def null(self, node: Any) -> S.NullLiteral:
        return S.NullLiteral()

    def this(self, node: Any) -> S.ThisExpression:
        return S.ThisExpression()

    def super_handle(self, node: Any) -> S.SuperExpression:
        return S.SuperExpression()

    def parenthesized(self, node: Any) -> S.ParenthesizedExpression:
        return S.ParenthesizedExpression(expression=self.expression(node.expression))

    # Dispatch

    ITEMS = {
        "ModuleDeclaration": design_unit, "InterfaceDeclaration": design_unit, "ProgramDeclaration": design_unit,
        "PackageDeclaration": design_unit, "ParameterDeclarationStatement": parameter,
        "TypeParameterDeclaration": parameter, "ParameterDeclaration": parameter,
        "DataDeclaration": data_declaration, "NetDeclaration": net_declaration, "TypedefDeclaration": typedef,
        "GenvarDeclaration": genvar, "PackageImportDeclaration": import_declaration, "ModportDeclaration": modport,
        "ContinuousAssign": continuous_assign, "AlwaysBlock": procedural_block, "AlwaysCombBlock": procedural_block,
        "AlwaysFFBlock": procedural_block, "AlwaysLatchBlock": procedural_block, "InitialBlock": procedural_block,
        "FinalBlock": procedural_block, "FunctionDeclaration": subroutine, "TaskDeclaration": subroutine,
        "GenerateRegion": generate_region, "GenerateBlock": generate_block, "LoopGenerate": loop_generate,
        "IfGenerate": if_generate, "CaseGenerate": case_generate, "HierarchyInstantiation": instantiation,
        "PortDeclaration": port_declaration, "ClassDeclaration": class_declaration,
        "ClassPropertyDeclaration": class_property, "ClassMethodDeclaration": class_method,
        "ClassMethodPrototype": class_prototype, "ForwardTypedefDeclaration": forward_typedef,
        "ConstraintDeclaration": constraint_declaration, "ConstraintPrototype": constraint_prototype,
        "ConcurrentAssertionMember": assertion_item, "ImmediateAssertionMember": assertion_item,
        "PropertyDeclaration": property_declaration, "SequenceDeclaration": sequence_declaration,
        "LetDeclaration": let_declaration, "ClockingDeclaration": clocking_declaration,
        "DefaultClockingReference": default_clocking, "DefaultDisableDeclaration": default_disable,
        "CovergroupDeclaration": covergroup,
    }
    STATEMENTS = {
        "ExpressionStatement": expression_statement, "EmptyStatement": empty,
        "SequentialBlockStatement": block, "ParallelBlockStatement": block, "ConditionalStatement": conditional,
        "CaseStatement": case, "LoopStatement": loop, "DoWhileStatement": do_while, "ForeverStatement": forever,
        "ForLoopStatement": for_loop, "ForeachLoopStatement": foreach, "RandCaseStatement": randcase,
        "AssertPropertyStatement": concurrent, "AssumePropertyStatement": concurrent,
        "CoverPropertyStatement": concurrent, "CoverSequenceStatement": concurrent,
        "RestrictPropertyStatement": concurrent, "ExpectPropertyStatement": expect,
        "VoidCastedCallStatement": void_call, "JumpStatement": jump,
        "ReturnStatement": return_statement, "TimingControlStatement": timing_statement, "WaitStatement": wait,
        "BlockingEventTriggerStatement": trigger, "NonblockingEventTriggerStatement": trigger,
        "DisableStatement": disable, "DisableForkStatement": disable_fork, "ImmediateAssertStatement": assertion,
        "ImmediateAssumeStatement": assertion, "ImmediateCoverStatement": assertion,
    }
    EXPRESSIONS = {
        "IdentifierName": identifier_name, "IdentifierSelectName": identifier_select, "ScopedName": scoped,
        "ElementSelectExpression": element_select, "MemberAccessExpression": member_access,
        "IntegerVectorExpression": vector, "ConditionalExpression": conditional_expression,
        "InsideExpression": inside, "ConcatenationExpression": concatenation,
        "MultipleConcatenationExpression": replication, "AssignmentPatternExpression": pattern,
        "InvocationExpression": invocation, "SystemName": system_name,
        "CastExpression": cast, "SignedCastExpression": signed_cast, "ParenthesizedExpression": parenthesized,
        "NewClassExpression": new_class, "CopyClassExpression": copy_class, "NewArrayExpression": new_array,
        "NullLiteralExpression": null, "ThisHandle": this, "SuperHandle": super_handle, "ExpressionOrDist": dist,
        "ArrayOrRandomizeMethodExpression": with_clause,
    }


def parse(text: str, include_paths: Sequence[str] = (),
          defines: Sequence[str] = ()) -> tuple[S.SourceText, dict[int, int], _Source]:
    """The tree of `text`, the offset where each of its nodes starts (by `id`), and the source, for locating
    problems. `include_paths` are searched for `` `include `` files, and `defines` (`NAME` or `NAME=value`) are
    predefined macros. Raises `ParseError` at the first error slang reports, or at what the reader does not support."""
    source = _Source(text)
    manager = pyslang.SourceManager()
    options = parsing.PreprocessorOptions()
    options.additionalIncludePaths = list(include_paths)
    options.predefines = list(defines)
    lexer, parser = parsing.LexerOptions(), parsing.ParserOptions()
    for each in (options, lexer, parser):  # the whole language: standards check what each version lacks
        each.languageVersion = pyslang.LanguageVersion.v1800_2023
    tree = syntax.SyntaxTree.fromFileInMemory(text, manager, "source", "", pyslang.Bag([options, lexer, parser]))
    reader = _Reader(tree, source)
    for diagnostic in tree.diagnostics:
        if diagnostic.isError():
            location = diagnostic.location
            offset = source.offset(location.offset) if location.buffer == reader._main_buffer(tree) else 0
            raise source.error(_message(diagnostic), offset)
    reader.buffer = reader._main_buffer(tree)
    reader.start = tree.root.getFirstToken().location
    for token in _tokens(tree.root):  # how many tokens each macro use expands to, by where it is
        if manager.isMacroLoc(token.location):
            offset = reader.location(token).offset
            reader.expansions[offset] = reader.expansions.get(offset, 0) + 1
    attributes: list[Any] = []  # `(* ... *)`: not kinds yet, so refused rather than dropped
    tree.root.visit(lambda n: attributes.append(n) if isinstance(n, syntax.SyntaxNode)
                    and n.kind.name == "AttributeInstance" and reader.main(n.getFirstToken().location) else None)
    if attributes:
        raise reader.unsupported(attributes[0])
    unit = reader.unit(tree.root)
    return unit, reader.positions, source


def _message(diagnostic: Any) -> str:
    name = str(diagnostic.code).split("(")[-1].rstrip(")")
    words = "".join(f" {c.lower()}" if c.isupper() else c for c in name).strip()
    return words


def _main_buffer(self: _Reader, tree: Any) -> Any:
    return tree.root.getFirstToken().location.buffer if tree.root.getFirstToken() is not None else None


_Reader._main_buffer = _main_buffer  # type: ignore[attr-defined]
