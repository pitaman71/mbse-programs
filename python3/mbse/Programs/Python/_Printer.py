"""Prints Python trees as Python source text, in one fixed layout.

The layout: four spaces per level, one statement per line, `elif` for an `orelse` that is one `If`, and, as PEP 8 has
it, two blank lines around top-level function and class definitions and one around nested ones. Parentheses written
in the tree are printed; those a tree built by hand needs are added, by the precedence of Python's grammar, which also
decides where an assignment expression (`:=`), a `yield` or a lambda must be parenthesized. The printer assumes a valid
tree: versions validate before they print.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from . import Syntax as S

__all__ = ["Printer"]

_INDENT = "    "

# Precedence: higher binds tighter. An operand is parenthesized when its precedence is below what its place needs.
YIELD, TUPLE, NAMED, EXPR, OR, AND, NOT, CMP, BOR, BXOR, BAND, SHIFT, SUM, TERM, FACTOR, POWER, AWAIT, PRIMARY, ATOM = \
    range(-1, 18)
_BINARY = {"|": BOR, "^": BXOR, "&": BAND, "<<": SHIFT, ">>": SHIFT, "+": SUM, "-": SUM, "*": TERM, "@": TERM,
           "/": TERM, "//": TERM, "%": TERM, "**": POWER}
_PRECEDENCE: dict[type, int] = {
    S.Yield: YIELD, S.YieldFrom: YIELD, S.NamedExpr: NAMED, S.Lambda: EXPR, S.IfExp: EXPR, S.Compare: CMP,
    S.Await: AWAIT, S.Attribute: PRIMARY, S.Subscript: PRIMARY, S.Call: PRIMARY, S.Starred: PRIMARY,
}


def _precedence(node: Any) -> int:
    if isinstance(node, S.BinOp):
        return _BINARY[node.op]
    if isinstance(node, S.UnaryOp):
        return NOT if node.op == "not" else FACTOR
    if isinstance(node, S.BoolOp):
        return AND if node.op == "and" else OR
    if isinstance(node, S.Tuple):
        return TUPLE if node.elts else ATOM
    return _PRECEDENCE.get(type(node), ATOM)


def _code(text: str) -> str:
    """The code of an expression's text: without comments, and without whitespace outside its strings."""
    out: list[str] = []
    i, quote = 0, None
    while i < len(text):
        ch = text[i]
        if quote is not None:
            if ch == "\\":
                out.append(text[i:i + 2])
                i += 2
                continue
            if text.startswith(quote, i):
                out.append(quote)
                i += len(quote)
                quote = None
                continue
            out.append(ch)
        elif ch == "#":
            while i < len(text) and text[i] != "\n":
                i += 1
            continue
        elif ch in "'\"":
            quote = text[i:i + 3] if text[i:i + 3] in ("'''", '"""') else ch
            out.append(quote)
            i += len(quote)
            continue
        elif ch not in " \t\n\r\f\v":
            out.append(ch)
        i += 1
    return "".join(out)


def _definition(node: Any) -> bool:
    return isinstance(node, (S.FunctionDef, S.AsyncFunctionDef, S.ClassDef))


class Printer:
    """Prints a module as a file, and any other node as the text it stands for: a statement as its lines, an
    expression, a pattern or a part (an `Arg`, a `Keyword`, an `Alias`, ...) as its text."""

    def print(self, node: Any) -> str:
        if isinstance(node, S.Module):
            lines = self.block(node.body, 0, top=True)
            return "".join(line + "\n" for line in lines)
        if isinstance(node, (S.Statement, S.ExceptHandler, S.MatchCase)):
            return "\n".join(self.statement(node, 0))
        return self.text(node)

    # Statements

    def block(self, statements: list[Any], level: int, top: bool = False) -> list[str]:
        """The lines of a list of statements at `level`, with blank lines around definitions: two at the top level,
        one elsewhere. Comments directly before a definition stay with it."""
        lines: list[str] = []
        blank = 2 if top else 1
        after_definition = False
        for i, statement in enumerate(statements):
            if isinstance(statement, S.Comment) and statement.trailing and lines:
                lines[-1] += f"  #{statement.text}"
                continue
            starts = (_definition(statement) and not self.led(statements, i)) or (
                isinstance(statement, S.Comment) and self.leads(statements, i))
            if lines and (after_definition or starts):
                lines.extend([""] * blank)
            lines.extend(self.statement(statement, level))
            after_definition = _definition(statement)
        return lines

    @staticmethod
    def leads(statements: list[Any], i: int) -> bool:
        """Whether the comment `statements[i]` starts the comments directly before a definition."""
        j = i
        while j < len(statements) and isinstance(statements[j], S.Comment):
            j += 1
        return j < len(statements) and _definition(statements[j]) and (
            i == 0 or not isinstance(statements[i - 1], S.Comment) or statements[i - 1].trailing)

    @staticmethod
    def led(statements: list[Any], i: int) -> bool:
        """Whether `statements[i]` follows a comment that leads it: blank lines go before that comment."""
        return i > 0 and isinstance(statements[i - 1], S.Comment) and not statements[i - 1].trailing

    def suite(self, header: str, body: list[Any], level: int) -> list[str]:
        """`header:` and the indented body, a leading trailing comment on the header's line."""
        lines = [_INDENT * level + header + ":"]
        if body and isinstance(body[0], S.Comment) and body[0].trailing:
            lines[0] += f"  #{body[0].text}"
            body = body[1:]
        return lines + self.block(body, level + 1)

    def statement(self, node: Any, level: int) -> list[str]:
        method = self.STATEMENTS.get(type(node))
        if method is not None:
            return method(self, node, level)
        return [_INDENT * level + self.simple(node)]

    def simple(self, node: Any) -> str:
        return self.SIMPLE[type(node)](self, node)

    def comment(self, node: S.Comment) -> str:
        return f"#{node.text}"

    def expr(self, node: S.Expr) -> str:
        return self.value(node.value)

    def assign(self, node: S.Assign) -> str:
        return " = ".join([*(self.e(t, TUPLE) for t in node.targets), self.value(node.value)])

    def aug_assign(self, node: S.AugAssign) -> str:
        return f"{self.e(node.target, TUPLE)} {node.op}= {self.value(node.value)}"

    def ann_assign(self, node: S.AnnAssign) -> str:
        value = "" if node.value is None else f" = {self.value(node.value)}"
        return f"{self.e(node.target, PRIMARY)}: {self.e(node.annotation, EXPR)}{value}"

    def assert_(self, node: S.Assert) -> str:
        msg = "" if node.msg is None else f", {self.e(node.msg, EXPR)}"
        return f"assert {self.e(node.test, EXPR)}{msg}"

    def delete(self, node: S.Delete) -> str:
        return "del " + ", ".join(self.e(t, BOR) for t in node.targets)

    def return_(self, node: S.Return) -> str:
        return "return" if node.value is None else f"return {self.value(node.value, TUPLE)}"

    def raise_(self, node: S.Raise) -> str:
        text = "raise"
        if node.exc is not None:
            text += f" {self.e(node.exc, EXPR)}"
        if node.cause is not None:
            text += f" from {self.e(node.cause, EXPR)}"
        return text

    def import_(self, node: S.Import) -> str:
        return ("lazy " if node.is_lazy else "") + "import " + ", ".join(self.text(a) for a in node.names)

    def import_from(self, node: S.ImportFrom) -> str:
        module = "." * (node.level or 0) + ("" if node.module is None else self.text(node.module))
        names = ", ".join(self.text(a) for a in node.names)
        return f"{'lazy ' if node.is_lazy else ''}from {module} import {names}"

    def type_alias(self, node: S.TypeAlias) -> str:
        return f"type {self.text(node.name)}{self.type_params(node.type_params)} = {self.e(node.value, EXPR)}"

    SIMPLE: dict[type, Callable[[Printer, Any], str]] = {
        S.Comment: comment, S.Expr: expr, S.Assign: assign, S.AugAssign: aug_assign, S.AnnAssign: ann_assign,
        S.Assert: assert_, S.Pass: lambda self, node: "pass", S.Break: lambda self, node: "break",
        S.Continue: lambda self, node: "continue", S.Delete: delete, S.Return: return_, S.Raise: raise_,
        S.Import: import_, S.ImportFrom: import_from, S.TypeAlias: type_alias,
        S.Global: lambda self, node: "global " + ", ".join(self.text(n) for n in node.names),
        S.Nonlocal: lambda self, node: "nonlocal " + ", ".join(self.text(n) for n in node.names),
    }

    def orelse(self, orelse: list[Any], level: int) -> list[str]:
        if not orelse:
            return []
        if len(orelse) == 1 and isinstance(orelse[0], S.If):
            elif_ = orelse[0]
            return [*self.suite(f"elif {self.e(elif_.test, NAMED)}", elif_.body, level),
                    *self.orelse(elif_.orelse, level)]
        return self.suite("else", orelse, level)

    def if_(self, node: S.If, level: int) -> list[str]:
        return [*self.suite(f"if {self.e(node.test, NAMED)}", node.body, level), *self.orelse(node.orelse, level)]

    def while_(self, node: S.While, level: int) -> list[str]:
        return [*self.suite(f"while {self.e(node.test, NAMED)}", node.body, level),
                *(self.suite("else", node.orelse, level) if node.orelse else [])]

    def for_(self, node: S.For | S.AsyncFor, level: int) -> list[str]:
        keyword = "async for" if isinstance(node, S.AsyncFor) else "for"
        header = f"{keyword} {self.e(node.target, TUPLE)} in {self.value(node.iter, TUPLE)}"
        return [*self.suite(header, node.body, level), *(self.suite("else", node.orelse, level) if node.orelse else [])]

    def try_(self, node: S.Try | S.TryStar, level: int) -> list[str]:
        lines = self.suite("try", node.body, level)
        for handler in node.handlers:
            lines += self.handler(handler, level, star=isinstance(node, S.TryStar))
        if node.orelse:
            lines += self.suite("else", node.orelse, level)
        if node.finalbody:
            lines += self.suite("finally", node.finalbody, level)
        return lines

    def handler(self, node: S.ExceptHandler, level: int, star: bool = False) -> list[str]:
        header = "except*" if star else "except"
        if node.type is not None:
            header += f" {self.e(node.type, TUPLE if node.name is None else EXPR)}"
        if node.name is not None:
            header += f" as {self.text(node.name)}"
        return self.suite(header, node.body, level)

    def with_(self, node: S.With | S.AsyncWith, level: int) -> list[str]:
        keyword = "async with" if isinstance(node, S.AsyncWith) else "with"
        return self.suite(f"{keyword} {', '.join(self.text(i) for i in node.items)}", node.body, level)

    def match(self, node: S.Match, level: int) -> list[str]:
        lines = [f"{_INDENT * level}match {self.e(node.subject, TUPLE)}:"]
        for case in node.cases:
            lines += self.case(case, level + 1)
        return lines

    def case(self, node: S.MatchCase, level: int) -> list[str]:
        guard = "" if node.guard is None else f" if {self.e(node.guard, NAMED)}"
        return self.suite(f"case {self.p(node.pattern, open_sequence=True)}{guard}", node.body, level)

    def decorators(self, node: Any, level: int) -> list[str]:
        return [f"{_INDENT * level}@{self.e(d, NAMED)}" for d in node.decorator_list]

    def function(self, node: S.FunctionDef | S.AsyncFunctionDef, level: int) -> list[str]:
        keyword = "async def" if isinstance(node, S.AsyncFunctionDef) else "def"
        returns = "" if node.returns is None else f" -> {self.e(node.returns, EXPR)}"
        name = self.text(node.name) + self.type_params(node.type_params)
        header = f"{keyword} {name}({self.text(node.args)}){returns}"
        return [*self.decorators(node, level), *self.suite(header, node.body, level)]

    def class_(self, node: S.ClassDef, level: int) -> list[str]:
        arguments = [*(self.e(b, NAMED) for b in node.bases), *(self.text(k) for k in node.keywords)]
        header = f"class {self.text(node.name)}{self.type_params(node.type_params)}"
        if arguments:
            header += f"({', '.join(arguments)})"
        return [*self.decorators(node, level), *self.suite(header, node.body, level)]

    STATEMENTS: dict[type, Callable[[Printer, Any, int], list[str]]] = {
        S.If: if_, S.While: while_, S.For: for_, S.AsyncFor: for_, S.Try: try_, S.TryStar: try_, S.With: with_,
        S.AsyncWith: with_, S.Match: match, S.FunctionDef: function, S.AsyncFunctionDef: function, S.ClassDef: class_,
        S.ExceptHandler: handler, S.MatchCase: case,
    }

    def type_params(self, params: list[Any]) -> str:
        return f"[{', '.join(self.text(p) for p in params)}]" if params else ""

    # Expressions

    def e(self, node: Any, needed: int) -> str:
        """`node`'s text, parenthesized if it binds less than its place needs."""
        text = self.text(node)
        return f"({text})" if _precedence(node) < needed else text

    def value(self, node: Any, needed: int = YIELD) -> str:
        """A statement's value, which may be a tuple and, at `YIELD`, a `yield`, but not an assignment expression."""
        return f"({self.text(node)})" if isinstance(node, S.NamedExpr) else self.e(node, needed)

    def text(self, node: Any) -> str:
        return self.TEXTS[type(node)](self, node)

    def constant(self, node: S.Constant) -> str:
        return node.spelling

    def concatenated(self, node: S.ConcatenatedString) -> str:
        return " ".join(self.text(v) for v in node.values)

    def joined(self, node: S.JoinedStr | S.TemplateStr) -> str:
        return node.prefix + node.quote + "".join(self.text(v) for v in node.values) + node.quote

    def field(self, node: S.FormattedValue | S.Interpolation) -> str:
        value = self.e(node.value, YIELD)
        if isinstance(node.value, (S.Lambda, S.NamedExpr)):
            value = f"({value})"  # their colons would start a format spec
        text = node.text
        if text is not None and _code(text) != _code(value) + ("=" if node.debug else ""):
            text = None  # it no longer spells the value
        if text is None:
            text = (" " + value if value.startswith("{") else value) + ("=" if node.debug else "")
        conversion = "" if node.conversion is None else f"!{node.conversion}"
        spec = "" if node.format_spec is None else ":" + "".join(self.text(v) for v in node.format_spec.values)
        return "{" + text + conversion + spec + "}"

    def tuple(self, node: S.Tuple) -> str:
        if not node.elts:
            return "()"
        if len(node.elts) == 1:
            return self.e(node.elts[0], EXPR) + ","
        return ", ".join(self.e(e, EXPR) for e in node.elts)

    def parenthesized(self, node: S.Parenthesized) -> str:
        value = node.value
        if isinstance(value, S.Tuple) and value.elts:
            inner = ", ".join(self.e(e, NAMED) for e in value.elts) + ("," if len(value.elts) == 1 else "")
            return f"({inner})"
        return f"({self.e(value, YIELD)})"

    def comprehensions(self, generators: list[S.Comprehension]) -> str:
        return "".join(" " + self.text(g) for g in generators)

    def comprehension(self, node: S.Comprehension) -> str:
        text = f"{'async ' if node.is_async else ''}for {self.e(node.target, TUPLE)} in {self.e(node.iter, OR)}"
        return text + "".join(f" if {self.e(i, OR)}" for i in node.ifs)

    def dict_item(self, node: S.DictItem) -> str:
        if node.key is None:
            return f"**{self.e(node.value, BOR)}"
        return f"{self.e(node.key, EXPR)}: {self.e(node.value, EXPR)}"

    def dict_comp(self, node: S.DictComp) -> str:
        item = f"**{self.e(node.key, BOR)}" if node.value is None else (
            f"{self.e(node.key, EXPR)}: {self.e(node.value, EXPR)}")
        return "{" + item + self.comprehensions(node.generators) + "}"

    def yield_(self, node: S.Yield) -> str:
        return "yield" if node.value is None else f"yield {self.e(node.value, TUPLE)}"

    def attribute(self, node: S.Attribute) -> str:
        value = self.e(node.value, PRIMARY)
        if isinstance(node.value, S.Constant) and value.replace("_", "").isdigit():
            value = f"({value})"  # `1.real` would be a number
        return f"{value}.{self.text(node.attr)}"

    def subscript(self, node: S.Subscript) -> str:
        index = node.slice
        if isinstance(index, S.Tuple) and index.elts:
            inner = ", ".join(self.e(e, NAMED) for e in index.elts) + ("," if len(index.elts) == 1 else "")
        else:
            inner = self.e(index, NAMED)
        return f"{self.e(node.value, PRIMARY)}[{inner}]"

    def slice_(self, node: S.Slice) -> str:
        parts = ["" if p is None else self.e(p, EXPR) for p in (node.lower, node.upper)]
        text = ":".join(parts)
        return text if node.step is None else f"{text}:{self.e(node.step, EXPR)}"

    def call(self, node: S.Call) -> str:
        if len(node.args) == 1 and not node.keywords and isinstance(node.args[0], S.GeneratorExp):
            generator = node.args[0]
            return f"{self.e(node.func, PRIMARY)}({self.e(generator.elt, NAMED)}" \
                   f"{self.comprehensions(generator.generators)})"
        arguments = [*(self.e(a, NAMED) for a in node.args), *(self.text(k) for k in node.keywords)]
        return f"{self.e(node.func, PRIMARY)}({', '.join(arguments)})"

    def keyword(self, node: S.Keyword) -> str:
        if node.arg is None:
            return f"**{self.e(node.value, EXPR)}"
        return f"{self.text(node.arg)}={self.e(node.value, EXPR)}"

    def starred(self, node: S.Starred) -> str:
        return f"*{self.e(node.value, BOR)}"

    def unary(self, node: S.UnaryOp) -> str:
        if node.op == "not":
            return f"not {self.e(node.operand, NOT)}"
        return f"{node.op}{self.e(node.operand, FACTOR)}"

    def binary(self, node: S.BinOp) -> str:
        level = _BINARY[node.op]
        if node.op == "**":
            return f"{self.e(node.left, AWAIT)} ** {self.e(node.right, FACTOR)}"
        return f"{self.e(node.left, level)} {node.op} {self.e(node.right, level + 1)}"

    def compare(self, node: S.Compare) -> str:
        return self.e(node.left, BOR) + "".join(f" {c.op} {self.e(c.comparator, BOR)}" for c in node.comparisons)

    def bool_op(self, node: S.BoolOp) -> str:
        needed = NOT if node.op == "and" else AND
        return f" {node.op} ".join(self.e(v, needed) for v in node.values)

    def if_exp(self, node: S.IfExp) -> str:
        return f"{self.e(node.body, OR)} if {self.e(node.test, OR)} else {self.e(node.orelse, EXPR)}"

    def lambda_(self, node: S.Lambda) -> str:
        args = self.text(node.args)
        return f"lambda{' ' if args else ''}{args}: {self.e(node.body, EXPR)}"

    def arg(self, node: S.Arg) -> str:
        text = self.text(node.arg)
        if node.annotation is not None:
            text += f": {self.e(node.annotation, EXPR)}"
        if node.default_value is not None:
            text += f" = {self.e(node.default_value, EXPR)}" if node.annotation is not None else (
                f"={self.e(node.default_value, EXPR)}")
        return text

    def arguments(self, node: S.Arguments) -> str:
        parts = [self.text(a) for a in node.posonlyargs]
        if node.posonlyargs:
            parts.append("/")
        parts += [self.text(a) for a in node.args]
        if node.vararg is not None:
            parts.append("*" + self.text(node.vararg))
        elif node.kwonlyargs:
            parts.append("*")
        parts += [self.text(a) for a in node.kwonlyargs]
        if node.kwarg is not None:
            parts.append("**" + self.text(node.kwarg))
        return ", ".join(parts)

    def alias(self, node: S.Alias) -> str:
        if node.name is None:
            return "*"
        return self.text(node.name) + ("" if node.asname is None else f" as {self.text(node.asname)}")

    def with_item(self, node: S.WithItem) -> str:
        text = self.e(node.context_expr, EXPR)
        return text if node.optional_vars is None else f"{text} as {self.e(node.optional_vars, PRIMARY)}"

    def type_var(self, node: S.TypeVar | S.ParamSpec | S.TypeVarTuple) -> str:
        star = {S.TypeVar: "", S.ParamSpec: "**", S.TypeVarTuple: "*"}[type(node)]
        text = star + self.text(node.name)
        if isinstance(node, S.TypeVar) and node.bound is not None:
            text += f": {self.e(node.bound, EXPR)}"
        if node.default_value is not None:
            text += f" = {self.e(node.default_value, EXPR)}"
        return text

    TEXTS: dict[type, Callable[[Printer, Any], str]] = {
        S.Identifier: lambda self, node: node.spelling,
        S.DottedName: lambda self, node: ".".join(self.text(n) for n in node.names),
        S.Name: lambda self, node: self.text(node.id),
        S.Constant: constant, S.ConcatenatedString: concatenated, S.JoinedStr: joined, S.TemplateStr: joined,
        S.StringText: lambda self, node: node.spelling, S.FormattedValue: field, S.Interpolation: field,
        S.FormatSpec: lambda self, node: ":" + "".join(self.text(v) for v in node.values),
        S.Parenthesized: parenthesized, S.Tuple: tuple,
        S.List: lambda self, node: "[" + ", ".join(self.e(e, NAMED) for e in node.elts) + "]",
        S.Set: lambda self, node: "{" + ", ".join(self.e(e, NAMED) for e in node.elts) + "}",
        S.DictItem: dict_item, S.Dict: lambda self, node: "{" + ", ".join(self.text(i) for i in node.items) + "}",
        S.Comprehension: comprehension,
        S.ListComp: lambda self, node: f"[{self.e(node.elt, NAMED)}{self.comprehensions(node.generators)}]",
        S.SetComp: lambda self, node: f"{{{self.e(node.elt, NAMED)}{self.comprehensions(node.generators)}}}",
        S.DictComp: dict_comp,
        S.GeneratorExp: lambda self, node: f"({self.e(node.elt, NAMED)}{self.comprehensions(node.generators)})",
        S.Yield: yield_, S.YieldFrom: lambda self, node: f"yield from {self.e(node.value, EXPR)}",
        S.Attribute: attribute, S.Subscript: subscript, S.Slice: slice_, S.Keyword: keyword, S.Call: call,
        S.Starred: starred, S.Await: lambda self, node: f"await {self.e(node.value, PRIMARY)}",
        S.UnaryOp: unary, S.BinOp: binary, S.Compare: compare,
        S.Comparison: lambda self, node: f"{node.op} {self.e(node.comparator, BOR)}",
        S.BoolOp: bool_op, S.IfExp: if_exp, S.Lambda: lambda_,
        S.NamedExpr: lambda self, node: f"{self.text(node.target)} := {self.e(node.value, EXPR)}",
        S.Arg: arg, S.Arguments: arguments, S.Alias: alias, S.WithItem: with_item,
        S.TypeVar: type_var, S.ParamSpec: type_var, S.TypeVarTuple: type_var,
    }

    # Patterns

    def p(self, node: Any, open_sequence: bool = False) -> str:
        """A pattern's text. An open sequence, `case a, b:`, is written only where `open_sequence` allows it."""
        if isinstance(node, S.MatchSequence) and node.delimiters is None and not open_sequence:
            return f"({self.sequence(node)})" if node.patterns else "()"
        return self.PATTERNS[type(node)](self, node)

    def sequence(self, node: S.MatchSequence) -> str:
        text = ", ".join(self.p(p) for p in node.patterns)
        return text + ("," if len(node.patterns) == 1 else "")

    def match_sequence(self, node: S.MatchSequence) -> str:
        if node.delimiters == "[]":
            return "[" + ", ".join(self.p(p) for p in node.patterns) + "]"
        if node.delimiters == "()" or not node.patterns:
            return f"({self.sequence(node)})"
        return self.sequence(node)

    def match_mapping(self, node: S.MatchMapping) -> str:
        items = [f"{self.text(k)}: {self.p(p)}" for k, p in zip(node.keys, node.patterns)]
        if node.rest is not None:
            items.append(f"**{self.text(node.rest)}")
        return "{" + ", ".join(items) + "}"

    def match_class(self, node: S.MatchClass) -> str:
        arguments = [self.p(p) for p in node.patterns]
        arguments += [f"{self.text(a)}={self.p(p)}" for a, p in zip(node.kwd_attrs, node.kwd_patterns)]
        return f"{self.e(node.cls, PRIMARY)}({', '.join(arguments)})"

    def match_as(self, node: S.MatchAs) -> str:
        if node.pattern is None:
            return "_" if node.name is None else self.text(node.name)
        pattern = self.p(node.pattern)
        if isinstance(node.pattern, S.MatchAs) and node.pattern.pattern is not None:
            pattern = f"({pattern})"
        return f"{pattern} as {'_' if node.name is None else self.text(node.name)}"

    def match_or(self, node: S.MatchOr) -> str:
        parts = []
        for p in node.patterns:
            text = self.p(p)
            if isinstance(p, S.MatchOr) or (isinstance(p, S.MatchAs) and p.pattern is not None):
                text = f"({text})"
            parts.append(text)
        return " | ".join(parts)

    PATTERNS: dict[type, Callable[[Printer, Any], str]] = {
        S.MatchValue: lambda self, node: self.text(node.value), S.MatchSingleton: lambda self, node: node.value,
        S.MatchSequence: match_sequence, S.MatchMapping: match_mapping, S.MatchClass: match_class,
        S.MatchStar: lambda self, node: "*" + ("_" if node.name is None else self.text(node.name)),
        S.MatchAs: match_as, S.MatchOr: match_or,
    }

    TEXTS.update({kind: lambda self, node: self.p(node) for kind in PATTERNS})
