"""Syntax: the abstract syntax of Python 3, as one tree language, organized as the language reference is.

The kinds follow Python's own abstract syntax, the `ast` module, through Python 3.15: the same kinds with the same
names and fields where `ast` has them (capitalized where `ast`'s are lowercase: `Arg`, `Keyword`, `Alias`,
`WithItem`, `MatchCase`, `Comprehension`), with fields in source order. Each kind and feature records the version
that introduced it (`SINCE`, `FEATURES`), which `Python312`, `Python314` and other versions check.

Where `ast` drops what a transpiler needs to see or a printer needs to write it back, the tree is concrete:

- Names are nodes (`Identifier`) wherever `ast` has an identifier string, so one traversal finds every use and
  declaration of a name. A module's dotted name is a `DottedName`.
- Literals keep their spelling: `Constant.spelling` is the literal as written (`0x_FF`, `1e3j`, `rb'\\d'`, a
  triple-quoted string with its newlines). f-strings and t-strings keep their prefix and quotes, the text between
  their replacement fields as written, and the text of each field's expression.
- Parentheses written around an expression stay, as `Parenthesized`; adjacent string literals stay, as
  `ConcatenatedString`. Printing adds the parentheses a hand-built tree needs.
- Comments are kept where statements are listed, as `Comment` statements; elsewhere they are dropped.
- Lists hold no empty places: a dict's `**mapping` is a `DictItem` without a key, a parameter's default is on its
  `Arg`, a comparison is a `Compare` of `Comparison`s, and `from m import *` imports an `Alias` without a name.

Not represented: the expression context (`ctx`: load, store or delete), which follows from where an expression is;
`AnnAssign.simple`, which follows from its target; type comments, which are comments; and Python 2's syntax.
"""

from __future__ import annotations

import keyword
from typing import Literal as Choice

from ..Framework.Syntax import Availability, Language, Node

__all__ = ["LANGUAGE", "KINDS"]

PY = "Python"


def py(minor: int) -> Availability:
    """Python 3.`minor` on. Versions are numbered `100 * major + minor`: 3.12 is 312."""
    return {PY: 300 + minor}


# --- Choices ---

BinaryOperator = Choice["+", "-", "*", "@", "/", "//", "%", "**", "<<", ">>", "|", "^", "&"]
UnaryOperator = Choice["not", "-", "+", "~"]
BooleanOperator = Choice["and", "or"]
ComparisonOperator = Choice["==", "!=", "<", "<=", ">", ">=", "is", "is not", "in", "not in"]
Quote = Choice["'", '"', "'''", '"""']
Conversion = Choice["s", "r", "a"]
Singleton = Choice["None", "True", "False"]
Delimiter = Choice["[]", "()"]


def _needs(node: Node, field: str, what: str) -> list[str]:
    """A problem if the list `field` of `node` is empty."""
    return [] if getattr(node, field) else [f"{_a(node.KIND)} needs {what}"]


def _a(noun: str) -> str:
    return f"{'an' if noun[0].lower() in 'aeiou' else 'a'} {noun}"


def _suite(node: Node, *fields: str) -> list[str]:
    """Problems with the blocks in `fields` of `node`: the first must hold a statement other than a comment, and the
    others, if they hold anything, too."""
    problems = []
    for i, field in enumerate(fields):
        body = getattr(node, field)
        if (i == 0 or body) and all(isinstance(s, Comment) for s in body):
            problems.append(f"{_a(node.KIND)} needs a statement in its {field}")
    return problems


# --- Categories ---


class Statement(Node):
    """A statement (simple statements, §7; compound statements, §8), or a comment where statements are listed."""


class Expression(Node):
    """An expression (§6)."""


class Pattern(Node):
    """A pattern of a `case` clause (§8.6.4)."""


class TypeParameter(Node):
    """A type parameter of a generic function, class or type alias (§8.11)."""


# === Lexical analysis (§2) ===


class Comment(Statement):
    """`# text`, where statements are listed. `text` excludes the `#`. A `trailing` comment ends the line of the
    statement or clause header before it."""

    text: str
    trailing: bool


class Identifier(Node):
    """An identifier (§2.3): a letter or `_`, then letters, digits and `_`, as Unicode defines them, other than a
    keyword. Soft keywords (`match`, `case`, `type`, `_`, `lazy`) are identifiers."""

    spelling: str

    def check(self) -> list[str]:
        spelling = self.spelling
        if type(spelling) is not str:
            return []
        if not spelling.isidentifier():
            return [f"{spelling!r} is not an identifier"]
        if keyword.iskeyword(spelling):
            return [f"{spelling!r} is a keyword"]
        return []


class DottedName(Node):
    """`name.name...`, a module's name in an import (§7.11)."""

    names: list[Identifier]

    def check(self) -> list[str]:
        return _needs(self, "names", "a name")


# === Expressions (§6) ===

# --- Atoms (§6.2) ---


class Name(Expression):
    """A name used as an expression (§6.2.1): read, assigned or deleted."""

    id: Identifier


class Constant(Expression):
    """A literal (§2.6) as written: a number, a string or bytes literal with its prefix and quotes, `None`, `True`,
    `False` or `...`."""

    spelling: str


class ConcatenatedString(Expression):
    """Adjacent string literals, which make one string (§2.6.2): `'a' "b"`, `'a' f'{b}'`."""

    values: list[Constant | JoinedStr | TemplateStr]

    def check(self) -> list[str]:
        return [] if len(self.values) > 1 else ["a ConcatenatedString needs two strings"]


class StringText(Node):
    """Text of an f-string, a t-string or a format spec between replacement fields, as written: escapes and doubled
    braces (`{{`) included."""

    spelling: str


class FormatSpec(Node):
    """`:spec` after a replacement field's expression, which may hold replacement fields itself."""

    values: list[StringText | FormattedValue]


class FormattedValue(Node):
    """`{value=!conversion:format_spec}` in an f-string (§2.6.3). `text` is the field as written from after `{` to
    its conversion, format spec or `}`: the expression with its whitespace, and with `debug` (`{x = }`) the `=` and
    the whitespace after it, which a self-documenting field writes into the string. Printing writes `text` while it
    still spells `value`, and `value` otherwise."""

    value: Expression
    text: str | None
    debug: bool
    conversion: Conversion | None
    format_spec: FormatSpec | None
    FEATURES = {"debug": {True: py(8)}}


class Interpolation(Node):
    """`{value=!conversion:format_spec}` in a t-string (§2.6.4), as `FormattedValue`; `text` is also what the
    template records as the expression."""

    value: Expression
    text: str | None
    debug: bool
    conversion: Conversion | None
    format_spec: FormatSpec | None
    SINCE = py(14)


class JoinedStr(Expression):
    """An f-string (§2.6.3): `prefix` (`f`, `rf`, `Fr`, ...), then `quote`, the text and replacement fields, and the
    quote again."""

    prefix: str
    quote: Quote
    values: list[StringText | FormattedValue]
    SINCE = py(6)

    def check(self) -> list[str]:
        return _prefix(self, "fF")


class TemplateStr(Expression):
    """A t-string (§2.6.4), written as an f-string with `t` for `f`."""

    prefix: str
    quote: Quote
    values: list[StringText | Interpolation]
    SINCE = py(14)

    def check(self) -> list[str]:
        return _prefix(self, "tT")


def _prefix(node: JoinedStr | TemplateStr, letters: str) -> list[str]:
    prefix = node.prefix
    if type(prefix) is not str:
        return []
    if sorted(prefix.lower()) not in ([letters[0]], sorted(letters[0] + "r")):
        return [f"{node.KIND}.prefix cannot be {prefix!r}"]
    return []


class Parenthesized(Expression):
    """`(value)`: parentheses written in the source (§6.2.3). A parenthesized tuple is a `Parenthesized` `Tuple`."""

    value: Expression


class Tuple(Expression):
    """`elt, elt` (§6.15); `()` when empty. Parentheses written around it are a `Parenthesized`."""

    elts: list[Expression]


class List(Expression):
    """`[elt, elt]` (§6.2.5)."""

    elts: list[Expression]


class Set(Expression):
    """`{elt, elt}` (§6.2.6)."""

    elts: list[Expression]

    def check(self) -> list[str]:
        return _needs(self, "elts", "an element")  # `{}` is a dict


class DictItem(Node):
    """`key: value` in a dict display, or `**value` without a key."""

    key: Expression | None
    value: Expression


class Dict(Expression):
    """`{key: value, **mapping}` (§6.2.7)."""

    items: list[DictItem]


class Comprehension(Node):
    """`for target in iter if condition...` in a comprehension, or `async for` with `is_async` (§6.2.4)."""

    is_async: bool
    target: Expression
    iter: Expression
    ifs: list[Expression]
    FEATURES = {"is_async": {True: py(6)}}


def _unpacked(node: ListComp | SetComp | GeneratorExp) -> list[tuple[str, Availability]]:
    return [(f"{node.KIND} of unpacked elements", py(15))] if isinstance(node.elt, Starred) else []


class ListComp(Expression):
    """`[elt for ...]` (§6.2.4, §6.2.5); `[*elt for ...]` unpacks."""

    elt: Expression
    generators: list[Comprehension]

    def check(self) -> list[str]:
        return _needs(self, "generators", "a for clause")

    def features(self) -> list[tuple[str, Availability]]:
        return _unpacked(self)


class SetComp(Expression):
    """`{elt for ...}` (§6.2.4, §6.2.6)."""

    elt: Expression
    generators: list[Comprehension]

    def check(self) -> list[str]:
        return _needs(self, "generators", "a for clause")

    def features(self) -> list[tuple[str, Availability]]:
        return _unpacked(self)


class DictComp(Expression):
    """`{key: value for ...}` (§6.2.4, §6.2.7); without `value`, `{**key for ...}`."""

    key: Expression
    value: Expression | None
    generators: list[Comprehension]

    def check(self) -> list[str]:
        return _needs(self, "generators", "a for clause")

    def features(self) -> list[tuple[str, Availability]]:
        return [("DictComp of unpacked mappings", py(15))] if self.value is None else []


class GeneratorExp(Expression):
    """`(elt for ...)` (§6.2.8); the parentheses are its own, and a call's sole argument shares the call's."""

    elt: Expression
    generators: list[Comprehension]

    def check(self) -> list[str]:
        return _needs(self, "generators", "a for clause")

    def features(self) -> list[tuple[str, Availability]]:
        return _unpacked(self)


class Yield(Expression):
    """`yield value` (§6.2.9)."""

    value: Expression | None


class YieldFrom(Expression):
    """`yield from value` (§6.2.9)."""

    value: Expression


# --- Primaries (§6.3) ---


class Attribute(Expression):
    """`value.attr` (§6.3.1)."""

    value: Expression
    attr: Identifier


class Subscript(Expression):
    """`value[slice]` (§6.3.2); several indices are a `Tuple`."""

    value: Expression
    slice: Expression

    def features(self) -> list[tuple[str, Availability]]:
        elts = self.slice.elts if isinstance(self.slice, Tuple) else [self.slice]
        return [("Subscript with an unpacked index", py(11))] if any(isinstance(e, Starred) for e in elts) else []


class Slice(Expression):
    """`lower:upper:step`, an index of a subscript (§6.3.3)."""

    lower: Expression | None
    upper: Expression | None
    step: Expression | None


class Keyword(Node):
    """`arg=value` in a call or a class's bases, or `**value` without `arg` (§6.3.4)."""

    arg: Identifier | None
    value: Expression


class Call(Expression):
    """`func(args, keywords)` (§6.3.4). As in `ast`, positional arguments (also `*iterable`) come before keyword
    arguments (also `**mapping`), which is the order in which they are evaluated."""

    func: Expression
    args: list[Expression]
    keywords: list[Keyword]


class Starred(Expression):
    """`*value`: unpacked in a display, a call, a subscript or an assignment target (§6.3.4, §7.2)."""

    value: Expression


class Await(Expression):
    """`await value` (§6.4)."""

    value: Expression
    SINCE = py(5)


# --- Operators (§6.5–§6.13) ---


class UnaryOp(Expression):
    """`op operand`: `-x`, `+x`, `~x` (§6.6) or `not x` (§6.11)."""

    op: UnaryOperator
    operand: Expression


class BinOp(Expression):
    """`left op right` (§6.5, §6.7–§6.9)."""

    left: Expression
    op: BinaryOperator
    right: Expression
    FEATURES = {"op": {"@": py(5)}}


class Comparison(Node):
    """`op comparator`, one link of a comparison chain."""

    op: ComparisonOperator
    comparator: Expression


class Compare(Expression):
    """`left op comparator op comparator...` (§6.10)."""

    left: Expression
    comparisons: list[Comparison]

    def check(self) -> list[str]:
        return _needs(self, "comparisons", "a comparison")


class BoolOp(Expression):
    """`value and value...` or `value or value...` (§6.11)."""

    op: BooleanOperator
    values: list[Expression]

    def check(self) -> list[str]:
        return [] if len(self.values) > 1 else ["a BoolOp needs two values"]


class NamedExpr(Expression):
    """`target := value` (§6.12)."""

    target: Name
    value: Expression
    SINCE = py(8)


class IfExp(Expression):
    """`body if test else orelse` (§6.13)."""

    body: Expression
    test: Expression
    orelse: Expression


class Arg(Node):
    """A parameter: `arg: annotation = default_value` (§8.7). A lambda's parameters have no annotations."""

    arg: Identifier
    annotation: Expression | None
    default_value: Expression | None


class Arguments(Node):
    """A parameter list (§8.7): `posonlyargs, /, args, *vararg, kwonlyargs, **kwarg`. A bare `*` comes before
    keyword-only parameters when there is no `vararg`."""

    posonlyargs: list[Arg]
    args: list[Arg]
    vararg: Arg | None
    kwonlyargs: list[Arg]
    kwarg: Arg | None
    FEATURES = {"posonlyargs": {True: py(8)}}


class Lambda(Expression):
    """`lambda args: body` (§6.14)."""

    args: Arguments
    body: Expression

    def check(self) -> list[str]:
        args = self.args
        if not isinstance(args, Arguments):
            return []
        parameters = [*args.posonlyargs, *args.args, args.vararg, *args.kwonlyargs, args.kwarg]
        annotated = any(isinstance(a, Arg) and a.annotation is not None for a in parameters)
        return ["a Lambda's parameters have no annotations"] if annotated else []


# === Simple statements (§7) ===


class Expr(Statement):
    """An expression statement (§7.1)."""

    value: Expression


class Assign(Statement):
    """`target = target = value` (§7.2)."""

    targets: list[Expression]
    value: Expression

    def check(self) -> list[str]:
        return _needs(self, "targets", "a target")


class AugAssign(Statement):
    """`target op= value` (§7.2.1); `op` is the binary operator, as `+` for `+=`."""

    target: Expression
    op: BinaryOperator
    value: Expression
    FEATURES = {"op": {"@": py(5)}}


class AnnAssign(Statement):
    """`target: annotation = value` (§7.2.2)."""

    target: Expression
    annotation: Expression
    value: Expression | None
    SINCE = py(6)


class Assert(Statement):
    """`assert test, msg` (§7.3)."""

    test: Expression
    msg: Expression | None


class Pass(Statement):
    """`pass` (§7.4)."""


class Delete(Statement):
    """`del target, target` (§7.5)."""

    targets: list[Expression]

    def check(self) -> list[str]:
        return _needs(self, "targets", "a target")


class Return(Statement):
    """`return value` (§7.6)."""

    value: Expression | None


class Raise(Statement):
    """`raise exc from cause` (§7.8)."""

    exc: Expression | None
    cause: Expression | None

    def check(self) -> list[str]:
        return ["a Raise with a cause needs an exc"] if self.cause is not None and self.exc is None else []


class Break(Statement):
    """`break` (§7.9)."""


class Continue(Statement):
    """`continue` (§7.10)."""


class Alias(Node):
    """`name as asname` in an import; without `name`, the `*` of `from module import *` (§7.11)."""

    name: DottedName | None
    asname: Identifier | None


class Import(Statement):
    """`import name as asname, ...`, or with `is_lazy` `lazy import ...` (§7.11)."""

    is_lazy: bool
    names: list[Alias]
    FEATURES = {"is_lazy": {True: py(15)}}

    def check(self) -> list[str]:
        return _needs(self, "names", "a name")


class ImportFrom(Statement):
    """`from module import names`, or with `is_lazy` `lazy from ...` (§7.11). `level` counts the dots of a relative
    import (`from ..module`); None for an absolute one."""

    is_lazy: bool
    level: int | None
    module: DottedName | None
    names: list[Alias]
    FEATURES = {"is_lazy": {True: py(15)}}

    def check(self) -> list[str]:
        problems = _needs(self, "names", "a name")
        if self.module is None and not self.level:
            problems.append("an ImportFrom needs a module or a level")
        return problems


class Global(Statement):
    """`global name, name` (§7.12)."""

    names: list[Identifier]

    def check(self) -> list[str]:
        return _needs(self, "names", "a name")


class Nonlocal(Statement):
    """`nonlocal name, name` (§7.13)."""

    names: list[Identifier]

    def check(self) -> list[str]:
        return _needs(self, "names", "a name")


class TypeAlias(Statement):
    """`type name[type_params] = value` (§7.14)."""

    name: Name
    type_params: list[TypeParameter]
    value: Expression
    SINCE = py(12)


# === Compound statements (§8) ===


class If(Statement):
    """`if test: body else: orelse` (§8.1). An `orelse` that is one `If` is printed as `elif`."""

    test: Expression
    body: list[Statement]
    orelse: list[Statement]

    def check(self) -> list[str]:
        return _suite(self, "body", "orelse")


class While(Statement):
    """`while test: body else: orelse` (§8.2)."""

    test: Expression
    body: list[Statement]
    orelse: list[Statement]

    def check(self) -> list[str]:
        return _suite(self, "body", "orelse")


class For(Statement):
    """`for target in iter: body else: orelse` (§8.3)."""

    target: Expression
    iter: Expression
    body: list[Statement]
    orelse: list[Statement]

    def check(self) -> list[str]:
        return _suite(self, "body", "orelse")


class AsyncFor(Statement):
    """`async for target in iter: body else: orelse` (§8.9.2)."""

    target: Expression
    iter: Expression
    body: list[Statement]
    orelse: list[Statement]
    SINCE = py(5)

    def check(self) -> list[str]:
        return _suite(self, "body", "orelse")


class ExceptHandler(Node):
    """`except type as name: body` (§8.4). Several types are a `Tuple`, unparenthesized since Python 3.14."""

    type: Expression | None
    name: Identifier | None
    body: list[Statement]

    def check(self) -> list[str]:
        return _suite(self, "body")

    def features(self) -> list[tuple[str, Availability]]:
        return [("ExceptHandler with unparenthesized types", py(14))] if isinstance(self.type, Tuple) else []


def _try(node: Try | TryStar) -> list[str]:
    problems = _suite(node, "body", "orelse", "finalbody")
    if not node.handlers and not node.finalbody:
        problems.append(f"{_a(node.KIND)} needs a handler or a finalbody")
    elif node.orelse and not node.handlers:
        problems.append(f"{_a(node.KIND)} with an orelse needs a handler")
    return problems


class Try(Statement):
    """`try: body except...: handlers else: orelse finally: finalbody` (§8.4)."""

    body: list[Statement]
    handlers: list[ExceptHandler]
    orelse: list[Statement]
    finalbody: list[Statement]

    def check(self) -> list[str]:
        return _try(self)


class TryStar(Statement):
    """`try` with `except*` handlers, which match exception groups (§8.4.2)."""

    body: list[Statement]
    handlers: list[ExceptHandler]
    orelse: list[Statement]
    finalbody: list[Statement]
    SINCE = py(11)

    def check(self) -> list[str]:
        return _try(self)


class WithItem(Node):
    """`context_expr as optional_vars` (§8.5)."""

    context_expr: Expression
    optional_vars: Expression | None


class With(Statement):
    """`with items: body` (§8.5)."""

    items: list[WithItem]
    body: list[Statement]

    def check(self) -> list[str]:
        return _needs(self, "items", "an item") + _suite(self, "body")


class AsyncWith(Statement):
    """`async with items: body` (§8.9.3)."""

    items: list[WithItem]
    body: list[Statement]
    SINCE = py(5)

    def check(self) -> list[str]:
        return _needs(self, "items", "an item") + _suite(self, "body")


class MatchCase(Node):
    """`case pattern if guard: body` (§8.6)."""

    pattern: Pattern
    guard: Expression | None
    body: list[Statement]
    SINCE = py(10)

    def check(self) -> list[str]:
        return _suite(self, "body")


class Match(Statement):
    """`match subject: cases` (§8.6)."""

    subject: Expression
    cases: list[MatchCase]
    SINCE = py(10)

    def check(self) -> list[str]:
        return _needs(self, "cases", "a case")


def _decorators(node: FunctionDef | AsyncFunctionDef | ClassDef) -> list[tuple[str, Availability]]:
    """PEP 614: before Python 3.9, a decorator is a dotted name, optionally called."""
    def dotted(e: Expression) -> bool:
        return isinstance(e, Name) or (isinstance(e, Attribute) and dotted(e.value))

    relaxed = any(not dotted(d.func if isinstance(d, Call) else d) for d in node.decorator_list)
    return [(f"{node.KIND} with a decorator that is not a dotted name", py(9))] if relaxed else []


class FunctionDef(Statement):
    """`@decorator def name[type_params](args) -> returns: body` (§8.7)."""

    decorator_list: list[Expression]
    name: Identifier
    type_params: list[TypeParameter]
    args: Arguments
    returns: Expression | None
    body: list[Statement]
    FEATURES = {"type_params": {True: py(12)}}

    def check(self) -> list[str]:
        return _suite(self, "body")

    def features(self) -> list[tuple[str, Availability]]:
        return _decorators(self)


class AsyncFunctionDef(Statement):
    """`async def`, otherwise as `FunctionDef` (§8.9.1)."""

    decorator_list: list[Expression]
    name: Identifier
    type_params: list[TypeParameter]
    args: Arguments
    returns: Expression | None
    body: list[Statement]
    SINCE = py(5)
    FEATURES = {"type_params": {True: py(12)}}

    def check(self) -> list[str]:
        return _suite(self, "body")

    def features(self) -> list[tuple[str, Availability]]:
        return _decorators(self)


class ClassDef(Statement):
    """`@decorator class name[type_params](bases, keywords): body` (§8.8)."""

    decorator_list: list[Expression]
    name: Identifier
    type_params: list[TypeParameter]
    bases: list[Expression]
    keywords: list[Keyword]
    body: list[Statement]
    FEATURES = {"type_params": {True: py(12)}}

    def check(self) -> list[str]:
        return _suite(self, "body")

    def features(self) -> list[tuple[str, Availability]]:
        return _decorators(self)


# --- Patterns (§8.6.4) ---


class MatchValue(Pattern):
    """A value pattern: a literal, or a dotted name (§8.6.4.3, §8.6.4.8)."""

    value: Expression
    SINCE = py(10)


class MatchSingleton(Pattern):
    """`None`, `True` or `False`, compared by identity (§8.6.4.3)."""

    value: Singleton
    SINCE = py(10)


class MatchSequence(Pattern):
    """`[p, p]`, `(p, p)`, or `p, p` without `delimiters` (§8.6.4.9)."""

    delimiters: Delimiter | None
    patterns: list[Pattern]
    SINCE = py(10)


class MatchMapping(Pattern):
    """`{key: pattern, **rest}` (§8.6.4.10); `keys` and `patterns` pair up."""

    keys: list[Expression]
    patterns: list[Pattern]
    rest: Identifier | None
    SINCE = py(10)

    def check(self) -> list[str]:
        return [] if len(self.keys) == len(self.patterns) else ["a MatchMapping needs a pattern for each key"]


class MatchClass(Pattern):
    """`cls(pattern, kwd_attr=kwd_pattern)` (§8.6.4.11); `kwd_attrs` and `kwd_patterns` pair up."""

    cls: Expression
    patterns: list[Pattern]
    kwd_attrs: list[Identifier]
    kwd_patterns: list[Pattern]
    SINCE = py(10)

    def check(self) -> list[str]:
        return [] if len(self.kwd_attrs) == len(self.kwd_patterns) else [
            "a MatchClass needs a pattern for each keyword"]


class MatchStar(Pattern):
    """`*name` in a sequence pattern, or `*_` without `name` (§8.6.4.9)."""

    name: Identifier | None
    SINCE = py(10)


class MatchAs(Pattern):
    """`pattern as name` (§8.6.4.5); a capture `name` without `pattern`; the wildcard `_` without either."""

    pattern: Pattern | None
    name: Identifier | None
    SINCE = py(10)


class MatchOr(Pattern):
    """`pattern | pattern` (§8.6.4.4)."""

    patterns: list[Pattern]
    SINCE = py(10)

    def check(self) -> list[str]:
        return [] if len(self.patterns) > 1 else ["a MatchOr needs two patterns"]


# --- Type parameters (§8.11) ---


class TypeVar(TypeParameter):
    """`name: bound = default_value` (§8.11.1)."""

    name: Identifier
    bound: Expression | None
    default_value: Expression | None
    SINCE = py(12)
    FEATURES = {"default_value": {True: py(13)}}


class ParamSpec(TypeParameter):
    """`**name = default_value` (§8.11.1)."""

    name: Identifier
    default_value: Expression | None
    SINCE = py(12)
    FEATURES = {"default_value": {True: py(13)}}


class TypeVarTuple(TypeParameter):
    """`*name = default_value` (§8.11.1)."""

    name: Identifier
    default_value: Expression | None
    SINCE = py(12)
    FEATURES = {"default_value": {True: py(13)}}


# === Top-level components (§9) ===


class Module(Node):
    """A source file: its statements (§9.2)."""

    body: list[Statement]


KINDS: list[type[Node]] = [
    Comment, Identifier, DottedName,
    Name, Constant, ConcatenatedString, StringText, FormatSpec, FormattedValue, Interpolation, JoinedStr, TemplateStr,
    Parenthesized, Tuple, List, Set, DictItem, Dict, Comprehension, ListComp, SetComp, DictComp, GeneratorExp, Yield,
    YieldFrom, Attribute, Subscript, Slice, Keyword, Call, Starred, Await, UnaryOp, BinOp, Comparison, Compare, BoolOp,
    NamedExpr, IfExp, Arg, Arguments, Lambda,
    Expr, Assign, AugAssign, AnnAssign, Assert, Pass, Delete, Return, Raise, Break, Continue, Alias, Import, ImportFrom,
    Global, Nonlocal, TypeAlias,
    If, While, For, AsyncFor, ExceptHandler, Try, TryStar, WithItem, With, AsyncWith, MatchCase, Match, FunctionDef,
    AsyncFunctionDef, ClassDef,
    MatchValue, MatchSingleton, MatchSequence, MatchMapping, MatchClass, MatchStar, MatchAs, MatchOr,
    TypeVar, ParamSpec, TypeVarTuple,
    Module,
]

LANGUAGE = Language("Python", KINDS, base=py(0))

__all__ += [k.__name__ for k in KINDS] + ["Statement", "Expression", "Pattern", "TypeParameter", "py", "PY"]
