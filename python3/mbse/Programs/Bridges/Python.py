"""Python: between mbse-expressions' Python dialect and the Python language's syntax trees, both ways, tree to tree.

From terms to syntax nodes: `expression(term)` is the Python expression a term of the dialect writes, `module(term)`
the module of its imports and then the expression, and `function_(name, parameters, term)` the function that returns
it, its imports first: a rule as code. Every term of the dialect has a counterpart, and the expression prints as the
dialect renders it, but for the parentheses the printer chooses. A constant is the literal `repr` writes, a negative
number a negation, and a float that is not finite `float('nan')` or `float('inf')`.

From syntax nodes to terms: `term(expression)` and `term_of_module(module)`, which reads a module of imports, then one
expression (comments are skipped), as the dialect's `parse` reads source. They raise `TranspileError` at the first
syntax node the dialect cannot hold, with its path: a comparison of more than one operator, a keyword argument, a
slice, a lambda other than `(lambda name: body)(value)` (a let), a generator of more than one `for`, and any other kind
of expression. `and` and `or` of more than two operands nest to the left. Literals are decoded as Python decodes them:
ints, floats, strings and bytes (with their prefixes, escapes and adjacent literals joined), and `True` and `False`;
`None`, `...`, imaginary numbers and `\\N{...}` escapes have no counterpart.
"""

from __future__ import annotations

import math
import re
from typing import Any

from mbse.Expressions.Dialects.Python import Domains, Expressions as E

from ..Framework.Errors import TranspileError
from ..Framework.Syntax import Parents
from ..Python import Syntax as P

__all__ = ["expression", "module", "function_", "term", "term_of_module", "decode"]

Py = P.LANGUAGE.Builders


# --- From terms to syntax nodes ---


def expression(term: Any) -> Any:
    """The Python expression `term` writes. A term with imports is a module (`module`) or a function (`function_`)."""
    return _syntax(term).create()


def module(term: Any) -> P.Module:
    """The module that writes `term`: its imports, then the expression as a statement."""
    imports, body = _imports(term)
    return Py.Module().body([*imports, Py.Expr().value(_syntax(body))]).create()


def function_(name: str, parameters: list[str], term: Any) -> P.FunctionDef:
    """`def name(parameters): return term`, with the term's imports first in its body."""
    imports, body = _imports(term)
    arguments = Py.Arguments().args([Py.Arg().arg(parameter) for parameter in parameters])
    return Py.FunctionDef().name(name).args(arguments).body([*imports, Py.Return().value(_syntax(body))]).create()


def _imports(term: Any) -> tuple[list[Any], Any]:
    """The import statements that enclose `term`, outermost first, and the expression within them."""
    imports: list[Any] = []
    while term.KIND in ("import", "importfrom"):
        alias = Py.Alias().name(Py.DottedName().names(term.module.split(".") if term.KIND == "import" else [term.name]))
        alias = alias.asname(term.alias)
        if term.KIND == "import":
            imports.append(Py.Import().add_names(alias).create())
        else:
            module_name = Py.DottedName().names(term.module.split("."))
            imports.append(Py.ImportFrom().module(module_name).add_names(alias).create())
        term = term.body
    return imports, term


def _syntax(term: Any) -> Any:
    """The builder of the syntax node that writes `term`."""
    kind = term.KIND
    if kind == "constant":
        return _constant(term.value)
    if kind == "name":
        return Py.Name().id(term.name)
    if kind == "attribute":
        return Py.Attribute().value(_syntax(term.value)).attr(term.attr)
    if kind == "subscript":
        return Py.Subscript().value(_syntax(term.value)).slice(_constant(term.key))
    if kind == "index":
        return Py.Subscript().value(_syntax(term.value)).slice(_syntax(term.index))
    if kind == "call":
        return Py.Call().func(_syntax(term.function)).args([_syntax(a) for a in term.arguments])
    if kind == "compare":
        comparison = Py.Comparison().op(term.operator).comparator(_syntax(term.right))
        return Py.Compare().left(_syntax(term.left)).add_comparisons(comparison)
    if kind == "boolop":  # `a and b and c`, nested to the left, is one BoolOp
        left = term.left
        values = [_syntax(term.right)]
        while left.KIND == "boolop" and left.operator == term.operator:
            values.insert(0, _syntax(left.right))
            left = left.left
        return Py.BoolOp().op(term.operator).values([_syntax(left), *values])
    if kind == "binop":
        return Py.BinOp().left(_syntax(term.left)).op(term.operator).right(_syntax(term.right))
    if kind == "unaryop":
        return Py.UnaryOp().op(term.operator).operand(_syntax(term.operand))
    if kind == "ifexp":
        return Py.IfExp().test(_syntax(term.test)).body(_syntax(term.body)).orelse(_syntax(term.orelse))
    if kind == "generator":
        clause = Py.Comprehension().target(Py.Name().id(term.name)).iter(_syntax(term.iterable)).ifs(
            [_syntax(c) for c in term.conditions])
        return Py.GeneratorExp().elt(_syntax(term.element)).add_generators(clause)
    if kind == "let":  # `(lambda name: body)(value)`
        parameters = Py.Arguments().add_args(Py.Arg().arg(term.name))
        return Py.Call().func(Py.Lambda().args(parameters).body(_syntax(term.body))).add_args(_syntax(term.value))
    raise TranspileError("an import can only enclose the whole expression", "")


def _constant(value: Any) -> Any:
    """The builder of the literal of a native value: a negation for a negative number, and `float(...)` for a float
    that is not finite."""
    if type(value) is float and not math.isfinite(value):
        call = Py.Call().func(Py.Name().id("float")).add_args(Py.Constant().spelling(repr("nan" if math.isnan(
            value) else "inf")))
        return Py.UnaryOp().op("-").operand(call) if value < 0 else call
    text = repr(value)
    if text.startswith("-"):
        return Py.UnaryOp().op("-").operand(_constant(-value))
    return Py.Constant().spelling(text)


# --- From syntax nodes to terms ---


def term(expression: Any) -> Any:
    """The term of the dialect that the Python expression writes."""
    return _Reader(expression).term(expression)


def term_of_module(module: P.Module) -> Any:
    """The term a module writes: import statements, then one expression; comments are skipped."""
    reader = _Reader(module)
    statements = [s for s in module.body if not isinstance(s, P.Comment)]
    if not statements or not isinstance(statements[-1], P.Expr):
        raise TranspileError("the module must end with an expression", "")
    result = reader.term(statements[-1].value)
    for statement in reversed(statements[:-1]):
        if isinstance(statement, P.Import) and not statement.is_lazy:
            for alias in reversed(statement.names):
                result = E.import_(_dotted(alias.name), result, _spelling(alias.asname))
        elif isinstance(statement, P.ImportFrom) and not statement.is_lazy and not statement.level and (
                statement.module is not None):
            for alias in reversed(statement.names):
                if alias.name is None:
                    raise reader.error(statement, "import * binds names that cannot be known")
                result = E.importfrom(_dotted(statement.module), _dotted(alias.name), result, _spelling(alias.asname))
        else:
            raise reader.error(statement, "only imports may precede the expression")
    return result


def _bare(node: Any) -> Any:
    """`node` without the parentheses written around it."""
    while isinstance(node, P.Parenthesized):
        node = node.value
    return node


def _dotted(name: P.DottedName) -> str:
    return ".".join(identifier.spelling for identifier in name.names)


def _spelling(identifier: P.Identifier | None) -> str | None:
    return None if identifier is None else identifier.spelling


class _Reader:
    """Reads the syntax nodes of one tree into terms, locating errors by their path in it."""

    def __init__(self, root: Any):
        self.parents = Parents(root)

    def error(self, node: Any, message: str) -> TranspileError:
        return TranspileError(message, self.parents.path(node))

    def term(self, node: Any) -> Any:
        node = _bare(node)
        if isinstance(node, (P.Constant, P.ConcatenatedString)):
            return E.constant(self.literal(node))
        if isinstance(node, P.Name):
            return E.name(node.id.spelling)
        if isinstance(node, P.Attribute):
            return E.attribute(self.term(node.value), node.attr.spelling)
        if isinstance(node, P.Subscript):
            index = _bare(node.slice)
            if isinstance(index, (P.Slice, P.Tuple)):
                raise self.error(index, "slices are not supported")
            if isinstance(index, P.Constant) and type(key := self.literal(index)) is str:
                return E.subscript(self.term(node.value), key)
            return E.index(self.term(node.value), self.term(node.slice))
        if isinstance(node, P.GeneratorExp):
            clause = node.generators[0]
            if len(node.generators) != 1 or clause.is_async or not isinstance(clause.target, P.Name):
                raise self.error(node, "a generator has one for, over a name")
            return E.generator(clause.target.id.spelling, self.term(clause.iter), self.term(node.elt),
                               *(self.term(c) for c in clause.ifs))
        if isinstance(node, P.Call):
            return self.call(node)
        if isinstance(node, P.Compare):
            if len(node.comparisons) != 1:
                raise self.error(node, "a comparison has one operator")
            comparison = node.comparisons[0]
            self.operator(comparison, comparison.op, Domains.COMPARE)
            return E.compare(comparison.op, self.term(node.left), self.term(comparison.comparator))
        if isinstance(node, P.BoolOp):
            result = self.term(node.values[0])
            for value in node.values[1:]:
                result = E.boolop(node.op, result, self.term(value))
            return result
        if isinstance(node, P.BinOp):
            self.operator(node, node.op, Domains.BINOP)
            return E.binop(node.op, self.term(node.left), self.term(node.right))
        if isinstance(node, P.UnaryOp):
            return E.unaryop(node.op, self.term(node.operand))
        if isinstance(node, P.IfExp):
            return E.ifexp(self.term(node.test), self.term(node.body), self.term(node.orelse))
        raise self.error(node, f"{node.KIND} has no counterpart in the Python dialect")

    def operator(self, node: Any, operator: str, vocabulary: Any) -> None:
        if operator not in vocabulary:
            raise self.error(node, f"the operator '{operator}' has no counterpart in the Python dialect")

    def call(self, node: P.Call) -> Any:
        if node.keywords:
            raise self.error(node.keywords[0], "keyword arguments are not supported")
        function = _bare(node.func)
        if isinstance(function, P.Lambda):
            parameters = function.args
            if len(parameters.args) != 1 or len(node.args) != 1 or parameters.posonlyargs or parameters.vararg or \
                    parameters.kwonlyargs or parameters.kwarg or parameters.args[0].default_value is not None:
                raise self.error(node, "a let binds one name")
            return E.let_(parameters.args[0].arg.spelling, self.term(node.args[0]), self.term(function.body))
        return E.call(self.term(node.func), *(self.term(argument) for argument in node.args))

    def literal(self, node: Any) -> Any:
        """The native value a literal writes, as Python decodes it."""
        if isinstance(node, P.ConcatenatedString):
            parts = [self.literal(part) if isinstance(part, P.Constant) else self.term(part) for part in node.values]
            if len({type(part) for part in parts}) != 1:
                raise self.error(node, "bytes and strings cannot be joined")
            return b"".join(parts) if type(parts[0]) is bytes else "".join(parts)
        try:
            return decode(node.spelling)
        except ValueError as error:
            raise self.error(node, str(error)) from None


# --- Python's literals ---

_ESCAPES = {"\\": "\\", "'": "'", '"': '"', "a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t",
            "v": "\v"}


def decode(spelling: str) -> Any:
    """The native value of a Python literal's spelling; ValueError for one the dialect cannot hold."""
    if spelling in ("True", "False"):
        return spelling == "True"
    if spelling[-1] in "jJ" or spelling in ("None", "..."):
        raise ValueError("only native constants are supported")
    if re.fullmatch(r"0[xX][0-9a-fA-F_]+|0[oO][0-7_]+|0[bB][01_]+|[0-9][0-9_]*", spelling):
        return int(spelling.replace("_", ""), 0)
    if spelling[0] in "0123456789.":
        return float(spelling.replace("_", ""))
    prefix = re.match(r"[a-zA-Z]*", spelling).group(0).lower()  # type: ignore[union-attr]
    quote = spelling[len(prefix):len(prefix) + 3] if spelling[len(prefix):len(prefix) + 3] in ('"""', "'''") else (
        spelling[len(prefix)])
    body = spelling[len(prefix) + len(quote):-len(quote)]
    raw, binary = "r" in prefix, "b" in prefix
    text = body if raw else _unescape(body, binary)
    return text.encode("latin-1") if binary else text


def _unescape(body: str, binary: bool) -> str:
    """The characters a literal's body writes, its escapes decoded; for bytes, each character is a byte."""
    out, i = [], 0
    while i < len(body):
        c = body[i]
        if c != "\\":
            out.append(c)
            i += 1
            continue
        e = body[i + 1]
        if e == "\n":
            i += 2
        elif e in _ESCAPES:
            out.append(_ESCAPES[e])
            i += 2
        elif e in "01234567":
            digits = re.match(r"[0-7]{1,3}", body[i + 1:]).group(0)  # type: ignore[union-attr]
            out.append(chr(int(digits, 8) & 0xFF if binary else int(digits, 8)))
            i += 1 + len(digits)
        elif e == "x" or (not binary and e in "uU"):
            size = {"x": 2, "u": 4, "U": 8}[e]
            code = int(body[i + 2:i + 2 + size], 16)
            if code > 0x10FFFF:
                raise ValueError("an escape beyond U+10FFFF")
            out.append(chr(code))
            i += 2 + size
        elif e == "N" and not binary:
            raise ValueError("a \\N{...} escape is not supported")
        else:  # an unknown escape keeps its backslash
            out.append(c)
            i += 1
    return "".join(out)
