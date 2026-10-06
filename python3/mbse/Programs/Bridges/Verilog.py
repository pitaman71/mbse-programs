"""Verilog: between mbse-expressions' SystemVerilog dialect and the Verilog language's syntax trees, both ways, tree to
tree.

From terms to syntax nodes: `expression(term)` is the SystemVerilog expression a term of the dialect writes, and a
constraint becomes SystemVerilog as `function_(name, ports, term)`, a function that returns it, `constraint(name,
term)`, a `constraint` block that holds it, or `assertion(term)`, an immediate assertion of it. Every term of the
dialect has a counterpart, and the expression prints as the dialect renders it, but that a unary operator's unary
operand is parenthesized, `-(-x)`, since IEEE 1800 makes the operand a primary. A constant is an unsized decimal, a real
or a string literal, a negative number a negation, and a real that is not finite `0.0 / 0.0` or `1.0 / 0.0`; a vector is
a sized literal in its base, as the dialect writes it.

From syntax nodes to terms: `term(expression)`, and `term_of_function`, `term_of_constraint` and `term_of_assertion`
for what the writers make. They raise `TranspileError` at the first syntax node the dialect cannot hold, with its path:
an unbased or an unsized based literal, a part-select with `+:` or `-:`, a tolerance range, a cast to a type the
dialect does not name, an iteration that is not a reduction over one iterator, a scoped name, attributes, and any other
kind of expression. A replication of several items repeats their concatenation. Literals are decoded as IEEE 1800 reads
them: a sized literal's digits are its bits, extended or truncated to its size, and a string's escapes are decoded.
"""

from __future__ import annotations

import math
import re
from typing import Any

from mbse.Expressions.Dialects.SystemVerilog import Domains, Expressions as E, Text

from ..Framework.Errors import TranspileError
from ..Framework.Syntax import Parents
from ..Verilog import Syntax as S

__all__ = ["expression", "function_", "constraint", "assertion", "term", "term_of_function", "term_of_constraint",
           "term_of_assertion", "decode"]

_VECTORS, _ATOMS = ("bit", "logic", "reg"), ("byte", "shortint", "int", "longint", "integer", "time")


# --- From terms to syntax nodes ---


def expression(term: Any) -> S.Expression:
    """The SystemVerilog expression `term` writes."""
    kind = term.KIND
    if kind == "constant":
        return _constant(term.value)
    if kind == "vector":
        return S.IntegerLiteral(spelling=Text.ToText(term))  # as the dialect writes it, in its base
    if kind == "identifier":
        return _name(term.name)
    if kind == "unary":
        return S.UnaryExpression(operator=term.operator, operand=expression(term.operand))
    if kind == "binary":
        return S.BinaryExpression(left=expression(term.left), operator=term.operator, right=expression(term.right))
    if kind == "conditional":
        return S.ConditionalExpression(condition=expression(term.condition), consequence=expression(term.consequent),
                                       alternative=expression(term.alternative))
    if kind == "concatenation":
        return S.Concatenation(items=[expression(p) for p in term.parts])
    if kind == "replication":
        return S.Replication(count=expression(term.count), items=[expression(term.value)])
    if kind == "select":
        return S.IndexExpression(value=expression(term.value), index=expression(term.index))
    if kind == "range":
        return S.RangeSelect(value=expression(term.value), left=expression(term.msb), operator=":",
                             right=expression(term.lsb))
    if kind == "inside":
        return S.InsideExpression(value=expression(term.value), set=[
            S.ValueRange(left=expression(i.low), right=expression(i.high)) if i.KIND == "span" else expression(i)
            for i in term.items])
    if kind == "cast":
        return S.CastExpression(type=_type(term), value=expression(term.operand))
    if kind == "member":
        return S.MemberExpression(value=expression(term.object), member=S.Identifier(spelling=term.name))
    if kind == "call":
        arguments = [expression(a) for a in term.arguments]
        if term.function.startswith("$"):
            return S.SystemCall(name=term.function, arguments=arguments)
        return S.CallExpression(callee=_name(term.function), arguments=arguments)
    if kind == "method":
        return S.CallExpression(callee=S.MemberExpression(value=expression(term.array),
                                                          member=S.Identifier(spelling=term.name)))
    if kind == "iterate":  # `array.method(name) with (body)`
        call = S.CallExpression(callee=S.MemberExpression(value=expression(term.array),
                                                          member=S.Identifier(spelling=term.method)),
                                arguments=[_name(term.name)])
        return S.ArrayMethodWithExpression(call=call, expression=expression(term.body))
    raise TranspileError(f"a {kind} is not an expression", "")  # a span, outside `inside`


def function_(name: str, ports: list[tuple[str, str]], term: Any, type: str = "logic") -> S.FunctionDeclaration:
    """`function automatic type name(input port_type port, ...); return term; endfunction`: a constraint as a function of
    its ports, each a (type, name) of the dialect's types."""
    return S.FunctionDeclaration(lifetime="automatic", type=_keyword_type(type), name=S.Identifier(spelling=name),
                                 ports=[S.TfPort(direction="input", type=_keyword_type(t),
                                                 name=S.Identifier(spelling=n)) for t, n in ports],
                                 body=[S.ReturnStatement(value=expression(term))])


def constraint(name: str, term: Any) -> S.ConstraintDeclaration:
    """`constraint name { term; }`: a `constraint` block, within which randomization generates values."""
    return S.ConstraintDeclaration(name=S.Identifier(spelling=name),
                                   items=[S.ExpressionConstraint(expression=expression(term))])


def assertion(term: Any, message: str | None = None) -> S.ImmediateAssertion:
    """`assert (term) else $error("message");`: a constraint checked where the statement runs; without a message, the
    simulator reports its failure."""
    out = S.ImmediateAssertion(keyword="assert", expression=expression(term))
    if message is not None:
        out.fail_action = S.ExpressionStatement(expression=S.SystemCall(name="$error", arguments=[_constant(message)]))
    return out


def _name(name: str) -> S.Expression:
    """A name, or a dotted name's members; `this` is the keyword."""
    first, *rest = name.split(".")
    out: S.Expression = S.ThisExpression() if first == "this" else S.NameExpression(name=S.Identifier(spelling=first))
    for member in rest:
        out = S.MemberExpression(value=out, member=S.Identifier(spelling=member))
    return out


def _keyword_type(keyword: str) -> S.DataType:
    """A built-in type of the dialect, by its keyword."""
    if keyword in _VECTORS:
        return S.IntegerVectorType(keyword=keyword)
    if keyword in _ATOMS:
        return S.IntegerAtomType(keyword=keyword)
    return S.NonIntegerType(keyword=keyword)  # real, shortreal


def _type(term: Any) -> Any:
    """What a cast names: a width, a signedness or a built-in type."""
    if term.width is not None:
        return S.IntegerLiteral(spelling=str(term.width))
    if term.type in ("signed", "unsigned"):
        return S.ImplicitType(signing=term.type)
    return _keyword_type(term.type)


def _constant(value: Any) -> S.Expression:
    """The literal of a native value: a negation for a negative number, and `0.0 / 0.0` or `1.0 / 0.0` for a real
    that is not finite."""
    if type(value) is str:
        escapes = {"\\": "\\\\", '"': '\\"', "\n": "\\n", "\t": "\\t"}
        return S.StringLiteral(text="".join(escapes.get(c, c) for c in value))
    if type(value) is float and not math.isfinite(value):
        top = 0.0 if math.isnan(value) else 1.0 if value > 0 else -1.0
        return S.BinaryExpression(left=_constant(top), operator="/", right=S.RealLiteral(spelling="0.0"))
    text = repr(value)
    if text.startswith("-"):
        return S.UnaryExpression(operator="-", operand=_constant(-value))
    return S.RealLiteral(spelling=text) if type(value) is float else S.IntegerLiteral(spelling=text)


# --- From syntax nodes to terms ---


def term(node: Any) -> Any:
    """The term of the dialect that the SystemVerilog expression writes."""
    return _Reader(node).term(node)


def term_of_function(function: S.FunctionDeclaration) -> Any:
    """The term a function returns: its body, but for comments, is one `return`."""
    reader = _Reader(function)
    statements = [s for s in function.body if not isinstance(s, S.Comment)]
    if len(statements) != 1 or not isinstance(statements[0], S.ReturnStatement) or statements[0].value is None:
        raise TranspileError("the function's body must be one return of a value", "")
    return reader.term(statements[0].value)


def term_of_constraint(declaration: S.ConstraintDeclaration) -> Any:
    """The term a constraint holds: its items, but for comments, are one expression, not `soft`."""
    reader = _Reader(declaration)
    items = [i for i in declaration.items if not isinstance(i, S.Comment)]
    if len(items) != 1 or not isinstance(items[0], S.ExpressionConstraint) or items[0].soft:
        raise TranspileError("the constraint must hold one expression, not soft", "")
    return reader.term(items[0].expression)


def term_of_assertion(statement: S.ImmediateAssertion) -> Any:
    """The term an immediate assertion checks."""
    return _Reader(statement).term(statement.expression)


class _Reader:
    """Reads the syntax nodes of one tree into terms, locating errors by their path in it."""

    def __init__(self, root: Any):
        self.parents = Parents(root)

    def error(self, node: Any, message: str) -> TranspileError:
        return TranspileError(message, self.parents.path(node))

    def term(self, node: Any) -> Any:
        while isinstance(node, S.ParenthesizedExpression):
            node = node.expression
        if getattr(node, "attributes", None):
            raise self.error(node, "attributes have no counterpart in the SystemVerilog dialect")
        if isinstance(node, (S.IntegerLiteral, S.RealLiteral, S.StringLiteral)):
            try:
                return decode(node)
            except ValueError as error:
                raise self.error(node, str(error)) from None
        if isinstance(node, S.NameExpression) and isinstance(node.name, S.Identifier):
            return E.identifier(node.name.spelling)
        if isinstance(node, S.ThisExpression):  # the object a constraint is about, as in a class's method
            return E.identifier("this")
        if isinstance(node, S.UnaryExpression):
            self.operator(node, node.operator, Domains.UNARY)
            return E.unary(node.operator, self.term(node.operand))
        if isinstance(node, S.BinaryExpression):
            self.operator(node, node.operator, Domains.BINARY)
            return E.binary(node.operator, self.term(node.left), self.term(node.right))
        if isinstance(node, S.ConditionalExpression):
            return E.conditional(self.term(node.condition), self.term(node.consequence), self.term(node.alternative))
        if isinstance(node, S.Concatenation):
            return E.concatenation(*(self.term(i) for i in node.items))
        if isinstance(node, S.Replication):
            value = self.term(node.items[0]) if len(node.items) == 1 else E.concatenation(*(self.term(i)
                                                                                            for i in node.items))
            return E.replication(self.term(node.count), value)
        if isinstance(node, S.IndexExpression):
            return E.select(self.term(node.value), self.term(node.index))
        if isinstance(node, S.RangeSelect):
            if node.operator != ":":
                raise self.error(node, f"a part-select with {node.operator} has no counterpart in the dialect")
            return E.range_(self.term(node.value), self.term(node.left), self.term(node.right))
        if isinstance(node, S.InsideExpression):
            return E.inside(self.term(node.value), *(self.item(i) for i in node.set))
        if isinstance(node, S.CastExpression):
            return E.cast(self.cast(node), self.term(node.value))
        if isinstance(node, S.MemberExpression):
            return E.member(self.term(node.value), node.member.spelling)
        if isinstance(node, S.SystemCall):
            return E.call(node.name, *(self.argument(a) for a in node.arguments))
        if isinstance(node, S.CallExpression):
            return self.call(node)
        if isinstance(node, S.ArrayMethodWithExpression):
            return self.iteration(node)
        raise self.error(node, f"{node.KIND} has no counterpart in the SystemVerilog dialect")

    def operator(self, node: Any, operator: str, vocabulary: Any) -> None:
        if operator not in vocabulary:
            raise self.error(node, f"the operator '{operator}' has no counterpart in the SystemVerilog dialect")

    def item(self, node: Any) -> Any:
        """An item of `inside`: a value, or a span `[low:high]`."""
        if isinstance(node, S.ValueRange):
            if node.operator is not None:
                raise self.error(node, "a tolerance range has no counterpart in the dialect")
            return E.span(self.term(node.left), self.term(node.right))
        return self.term(node)

    def cast(self, node: S.CastExpression) -> str | int:
        """What a cast names: a built-in type's keyword, a signedness (not `const`), or a width."""
        kind = node.type
        if isinstance(kind, (S.IntegerVectorType, S.IntegerAtomType, S.NonIntegerType)) and kind.keyword in E.CASTS \
                and not getattr(kind, "signing", None) and not getattr(kind, "dimensions", None):
            return kind.keyword
        if isinstance(kind, S.ImplicitType) and kind.signing in ("signed", "unsigned") and not kind.dimensions:
            return kind.signing
        if isinstance(kind, S.IntegerLiteral) and kind.spelling.isdigit():
            return int(kind.spelling)
        raise self.error(kind, "a cast names a built-in type, a signedness or a width")

    def argument(self, node: Any) -> Any:
        if isinstance(node, (S.DataType, S.EmptyArgument)):
            raise self.error(node, "an argument is an expression")
        return self.term(node)

    def call(self, node: S.CallExpression) -> Any:
        callee = node.callee
        if isinstance(callee, S.MemberExpression) and callee.member.spelling in E.METHODS and not node.arguments:
            return E.method(self.term(callee.value), callee.member.spelling)
        return E.call(self.function(callee), *(self.argument(a) for a in node.arguments))

    def iteration(self, node: S.ArrayMethodWithExpression) -> Any:
        """`array.method(name) with (body)`, of a reduction."""
        call = node.call
        callee = call.callee if isinstance(call, S.CallExpression) else None
        arguments = call.arguments if isinstance(call, S.CallExpression) else []
        if not isinstance(callee, S.MemberExpression) or callee.member.spelling not in E.REDUCTIONS or \
                len(arguments) != 1 or not isinstance(arguments[0], S.NameExpression) or \
                not isinstance(arguments[0].name, S.Identifier):
            raise self.error(node, f"an iteration is a reduction ({', '.join(E.REDUCTIONS)}) of one iterator")
        return E.iterate(self.term(callee.value), callee.member.spelling, arguments[0].name.spelling,
                         self.term(node.expression))

    def function(self, node: Any) -> str:
        """A function's name, or a dotted name's."""
        if isinstance(node, S.MemberExpression):
            return f"{self.function(node.value)}.{node.member.spelling}"
        if isinstance(node, S.NameExpression) and isinstance(node.name, S.Identifier):
            return node.name.spelling
        if isinstance(node, S.ThisExpression):
            return "this"
        raise self.error(node, "a function is called by its name")


# --- SystemVerilog's literals ---

_DIGITS = {"b": 1, "o": 3, "h": 4}
_ESCAPES = {"n": "\n", "t": "\t", "\\": "\\", '"': '"', "v": "\v", "f": "\f", "a": "\a"}


def decode(literal: Any) -> Any:
    """The term of a literal: a constant, or a sized literal's vector; ValueError for one the dialect cannot hold."""
    if isinstance(literal, S.StringLiteral):
        return E.constant(_unescape(literal.text))
    spelling = literal.spelling.replace("_", "")
    if isinstance(literal, S.RealLiteral):
        return E.constant(float(spelling))
    if "'" not in spelling:
        return E.constant(int(spelling))
    match = re.fullmatch(r"([0-9]+)'([sS]?)([bBoOdDhH])([0-9a-fA-FxXzZ?]+)", spelling)
    if match is None:
        raise ValueError("an unsized based literal has no counterpart in the dialect")
    size, signed, base, digits = int(match.group(1)), bool(match.group(2)), match.group(3).lower(), match.group(4)
    if base == "d":
        bits = digits.lower().replace("?", "z") * size if digits.lower() in ("x", "z", "?") else (
            format(int(digits), "b"))
    else:
        bits = "".join(d.lower().replace("?", "z") * _DIGITS[base] if d.lower() in "xz?" else
                       format(int(d, 16), "b").zfill(_DIGITS[base]) for d in digits)
    fill = bits[0] if bits[0] in "xz" else "0"
    bits = (fill * size + bits)[-size:]  # extended or truncated to its size
    return E.vector(bits, signed or None, base)


def _unescape(text: str) -> str:
    """The characters a string literal writes, its escapes decoded (5.9.1)."""
    out, i = [], 0
    while i < len(text):
        c = text[i]
        if c != "\\" or i + 1 == len(text):
            out.append(c)
            i += 1
            continue
        e = text[i + 1]
        if e in _ESCAPES:
            out.append(_ESCAPES[e])
            i += 2
        elif e in "01234567":
            digits = re.match(r"[0-7]{1,3}", text[i + 1:]).group(0)  # type: ignore[union-attr]
            out.append(chr(int(digits, 8)))
            i += 1 + len(digits)
        elif e == "x" and re.match(r"[0-9a-fA-F]{1,2}", text[i + 2:]):
            digits = re.match(r"[0-9a-fA-F]{1,2}", text[i + 2:]).group(0)  # type: ignore[union-attr]
            out.append(chr(int(digits, 16)))
            i += 2 + len(digits)
        elif e == "\n":  # a line continued
            i += 2
        else:  # an unknown escape is the character itself
            out.append(e)
            i += 2
    return "".join(out)
