"""Parse: Python 3 source text as the transaction that writes its module, delegating to tree-sitter-python.

`parse(text, path)` reads `text` at once, raising `ParseError` (its line and column) where it does not parse, and gives
the transaction's callback, which a caller executes, `store.transaction(parse(text, path))`, or builds to write it,
`Plain.ToPlain(store).Transaction(store.Mutations.OfTransaction(parse(text, path, store)))`. Executed in a store holding
the installs (mbse-expressions' `Framework`, ISO/IEC 11404, IEEE 754, `Python3`, `Python Types`, `Python Patterns`, then
`Programs.Framework.Model` and `Programs.Python3`), it is one upsert, `uid(path)`, whose symbols bind the workspace
(`ws`, its singleton `Programs.Framework.TheWorkspace`), the module (`module`) and each statement (`s0`, `s1`, ... in
source order); its spec puts the module in the workspace's `files` by `path`, sets each statement's properties and
links each to its parent, the module's `body` or a statement's `children`, by the parent's property that holds it and
its index there. Its frame gives the module and every statement by symbol.

As the port decided ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../../docs/proposals/port/README.md#stage-2-python3-the-design-for-review-2026-11-16)),
statements are `Programs.Python3`'s kinds, owned reference objects; expressions are mbse-expressions' `Python3` terms,
nested values, written here from tree-sitter's tree with their concrete syntax as far as the dialect keeps it:
parentheses written in the source (`parenthesized`), a literal's spelling (`text`, `prefix`, `quote`, `base`,
`separators`), adjacent strings (`concatenatedstring`), and an f-string's or a t-string's text and fields as written.
Annotations, return types, type aliases' values and type parameters are `Python Types` terms; a case's pattern a
`Python Patterns` term. mbse-expressions' `Text.FromText`, which reads through CPython's `ast` and loses spelling, is
not used. tree-sitter-python builds a concrete syntax tree; `_Converter` rewrites it one node type at a time.

Reused from mbse-programs 0.3 (`Python/_Parser.py`), as it was: the source and its offsets (`_Source`), counted in
characters (code points), never bytes, so that every implementation reports the same line and column; the pre-pass
(`_prepare`) for what tree-sitter-python 0.25 cannot parse (lazy imports, dict comprehensions that unpack, type
parameters' defaults), which rewrites them keeping every other character where it was, the converter putting them
back; the regrouping of binary operators by Python's precedence (`_LEVELS`); comments' attachment; and the errors.

Decided here *(agent, for review)*:

- **Schemas, resolved through the transaction or the store.** The callback names its schemas through what
  `store.transaction` gives it (`txn.Programs.Python3.If`); `store.Mutations.OfTransaction` gives a bare builder,
  which names none, so `parse` takes the store for that (`parse(text, path, store)`), and then resolves through it.
- **A tuple is a `tuple`, parenthesized or not.** The dialect's `tuple` carries its parentheses (its printer writes
  `(a, b)`), so `a, b` and `(a, b)` are both a `tuple`, never a `parenthesized` tuple, which would print twice; which
  of the two the source wrote is lost (a gap, reported to mbse-expressions). `(a)` is a `parenthesized` name, `(x): int`
  a `parenthesized` target. An `except` clause's types are a `tuple` whether written `except (A, B):` or, as Python
  3.14 allows, `except A, B:`.
- **What is absent is absent.** A property tree-sitter's tree gives no value (`Return.value`, an empty list, a flag
  that is false: `Comment.trailing`, `Import.is_lazy`) is not written; an absolute import's `level` (`ast`'s 0) is not
  written. A function's `args` is always written, an `Arguments`, empty where it has no parameters.
- **A wildcard import is the alias `*`**, as `ast` has it.
- **A literal's value** is what CPython reads its spelling as (`ast.literal_eval` of the literal alone): a string's or
  bytes' value, an int's, a float's; a complex number a `constant` with its `complex`; `None` and `...` `constant`s.
  Each keeps its spelling, as `Text.FromText` writes it.
- **Positions**: each statement's line is written as its `location`, `Programs.Framework.HasLocation` to its module;
  an expression, a value, has none.
- **Invalid syntax raises**, as 0.3 did: tree-sitter's `ERROR` and `MISSING` nodes raise `ParseError` at the first,
  in source order, though the dialects have `error` and `missing` kinds that could hold them (a follow-up).
"""

from __future__ import annotations

import ast
import warnings
from collections.abc import Callable
from typing import Any

import tree_sitter_python
from mbse.Expressions.Framework import Terms as FT
from mbse.Expressions.Python.Python3 import Expressions as P
from tree_sitter import Language as _Grammar
from tree_sitter import Node as _TS
from tree_sitter import Parser as _TSParser

from ..Framework.Errors import ParseError
from ..Framework.Model import WORKSPACE

__all__ = ["parse", "ParseError", "WORKSPACE"]

_PARSER = _TSParser(_Grammar(tree_sitter_python.language()))

_EXTRAS = {"comment", "line_continuation"}
_PYTHON2 = {"exec_statement"}
_CLAUSES = {"elif_clause", "else_clause", "except_clause", "finally_clause", "case_clause"}
# Python's binary operators, by precedence, the loosest first. tree-sitter-python 0.25 groups `^` and `&` as one level,
# so the converter regroups chains of binary operators by these.
_LEVELS = [("|",), ("^",), ("&",), ("<<", ">>"), ("+", "-"), ("*", "@", "/", "//", "%"), ("**",)]
_LANGUAGE = "Programs.Python3"


# --- Source text ---


class _Source:
    """The text being parsed, as given and as tree-sitter parses it (`data`, which is `cleaned` in UTF-16), with
    conversions from tree-sitter's byte offsets to character offsets, and from character offsets to lines and
    columns. The cleaned text has the same characters as the text, but for those the pre-pass rewrote."""

    def __init__(self, text: str, cleaned: str | None = None):
        self.text = text
        self.data = (text if cleaned is None else cleaned).encode("utf-16-le")
        self._chars: list[int] | None = None
        if len(self.data) != 2 * len(text):  # a character beyond the Basic Multilingual Plane takes two units
            self._chars = [0] * (len(self.data) // 2 + 1)
            at = 0
            for i, ch in enumerate(text if cleaned is None else cleaned):
                for _ in range(len(ch.encode("utf-16-le")) // 2):
                    self._chars[at] = i
                    at += 1
            self._chars[at] = len(text)

    def offset(self, byte: int) -> int:
        return byte // 2 if self._chars is None else self._chars[byte // 2]

    def error(self, message: str, offset: int) -> ParseError:
        line = self.text.count("\n", 0, offset) + 1
        column = offset - (self.text.rfind("\n", 0, offset) + 1) + 1
        return ParseError(message, line, column)

    def line(self, offset: int) -> int:
        return self.text.count("\n", 0, offset) + 1


# --- The pre-pass: what tree-sitter-python cannot parse ---


class _Prepared:
    """What the pre-pass rewrote, by the character offset where the construct starts: lazy imports, set
    comprehensions that are dict comprehensions that unpack, and type parameters' defaults (the offset and text of
    each default)."""

    def __init__(self) -> None:
        self.lazy: set[int] = set()
        self.unpacking: set[int] = set()
        self.defaults: dict[int, tuple[int, str]] = {}


def _tokens(source: _Source, root: _TS) -> list[tuple[int, int, str]]:
    """The tokens of a tree, as character spans and their text: each leaf, but each string whole, without comments."""
    out: list[tuple[int, int, str]] = []
    stack = [root]
    while stack:
        ts = stack.pop()
        if ts.type in _EXTRAS:
            continue
        if ts.child_count == 0 or ts.type == "string":
            start, end = source.offset(ts.start_byte), source.offset(ts.end_byte)
            out.append((start, end, source.text[start:end]))
            continue
        stack.extend(reversed(ts.children))
    return out


def _closing(tokens: list[tuple[int, int, str]], i: int) -> int:
    """The index of the bracket that closes the one at `tokens[i]`, or of the last token if none does."""
    depth = 0
    for j in range(i, len(tokens)):
        if tokens[j][2] in ("(", "[", "{"):
            depth += 1
        elif tokens[j][2] in (")", "]", "}"):
            depth -= 1
            if depth == 0:
                return j
    return len(tokens) - 1


def _prepare(text: str, root: _TS, source: _Source) -> tuple[str, _Prepared]:
    """The text with the constructs tree-sitter-python cannot parse rewritten, and what was rewritten."""
    found = _Prepared()
    chars = list(text)
    tokens = _tokens(source, root)

    def blank(start: int, end: int) -> None:
        for p in range(start, end):
            if chars[p] != "\n":
                chars[p] = " "

    for i, (start, end, word) in enumerate(tokens):
        following = tokens[i + 1][2] if i + 1 < len(tokens) else ""
        line_start = text.rfind("\n", 0, start) + 1
        if word == "lazy" and following in ("import", "from") and not text[line_start:start].strip():
            # `lazy import` becomes `import    `, which keeps the statement where it starts
            after = tokens[i + 1]
            chars[start:after[1]] = list(following.ljust(after[1] - start))
            found.lazy.add(start)
        elif word == "{" and following == "**":
            close = _closing(tokens, i)
            depth, comprehension = 0, False
            for _, _, inner in tokens[i + 1:close]:
                depth += {"(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1}.get(inner, 0)
                if depth == 0 and inner == ":":
                    break
                comprehension = comprehension or (depth == 0 and inner == "for")
            else:
                if comprehension:
                    blank(tokens[i + 1][0], tokens[i + 1][1])
                    found.unpacking.add(start)
        elif word == "[" and i >= 2 and tokens[i - 2][2] in ("def", "class", "type"):
            close = _closing(tokens, i)
            depth, parameter, equals = 0, None, None
            for j in range(i + 1, close + 1):
                s, e, inner = tokens[j]
                if depth == 0 and inner in (",", "]") and j <= close:
                    if equals is not None and equals + 1 < j:
                        found.defaults[parameter] = (tokens[equals + 1][0], text[tokens[equals + 1][0]:s])
                        blank(tokens[equals][0], s)
                    parameter, equals = None, None
                    continue
                if parameter is None:
                    parameter = s
                if depth == 0 and inner == "=":
                    equals = j
                depth += {"(": 1, "[": 1, "{": 1, ")": -1, "]": -1, "}": -1}.get(inner, 0)
    return "".join(chars), found


# --- Terms: the writers of the dialects' terms ---


def _record(fields: dict[str, Any]) -> Callable[[Any], Any]:
    """The writer of a value object's fields that are given: None and an empty list are absent."""
    given = {name: value for name, value in fields.items() if value is not None and value != []}

    def write(r: Any) -> Any:
        for name, value in given.items():
            getattr(r, name)(value)
        return r

    return write


def _term(kind: str, **fields: Any) -> FT.Writer:
    """A term of `Python Types` or `Python Patterns`, which have no writers: its kind's branch of the union it is
    written to, and its fields."""
    record = _record(fields)
    return FT.Writer(lambda union: getattr(union, kind)(record))


def _helper(kind: str, **fields: Any) -> P.Helper:
    """A value object that is no term (`Arguments`, `Arg`, `Alias`, `WithItem`), and its fields."""
    return P.Helper(kind, _record(fields))


def _literal(value: Any, text: str) -> P.Writer:
    """A literal with its spelling: a basic scalar's `literal`, with what its text encodes (a string's or bytes' prefix
    and quotes, an int's base, digit separators), or Python3's `constant` (`None`, `...`, a complex number)."""
    separators = True if "_" in text and type(value) is not str and type(value) is not bytes else None
    if value is None or value is Ellipsis:
        fields = {"singleton": "None" if value is None else "...", "text": text}
        return P.Writer(lambda u: getattr(u, P.CONSTANT)(_record(fields)))
    if type(value) is complex:
        number = P.Helper("complex", lambda r: r.real(value.real).imag(value.imag))
        fields = {"text": text, "separators": separators, "complex": number}
        return P.Writer(lambda u: getattr(u, P.CONSTANT)(_record(fields)))
    encoded: dict[str, Any] = {}
    if type(value) in (str, bytes):
        prefix = text[:len(text) - len(text.lstrip("rRbBuU"))]
        body = text[len(prefix):]
        encoded = {"prefix": prefix or None, "quote": body[:3] if body[:3] in ("'''", '"""') else body[0]}
    elif type(value) is int:
        encoded = {"base": {"0x": 16, "0o": 8, "0b": 2}.get(text[:2].lower(), 10), "separators": separators}
    elif type(value) is float:
        encoded = {"separators": separators}
    spelling = _record(encoded)
    return P.Writer(lambda u: getattr(u, P.LITERAL)(lambda r: spelling(r.value(lambda p: p.as_scalar(value)).text(text))))


# --- The converter ---


class _Statement:
    """A statement, as the transaction writes it: its symbol, its kind, its properties, its line, and its children, by
    the property that holds them."""

    __slots__ = ("symbol", "kind", "properties", "line", "children")

    def __init__(self, symbol: str, kind: str, line: int):
        self.symbol, self.kind, self.line = symbol, kind, line
        self.properties: dict[str, Any] = {}
        self.children: list[tuple[str, int, _Statement]] = []

    def set(self, **properties: Any) -> _Statement:
        self.properties.update({name: value for name, value in properties.items()
                                if value is not None and value != [] and value is not False})
        return self

    def hold(self, property: str, statements: list[_Statement]) -> _Statement:
        self.children += [(property, i, statement) for i, statement in enumerate(statements)]
        return self


class _Converter:
    """Rewrites a tree-sitter-python tree into statements and terms. `shift` and `origin` place a tree parsed from a
    part of the text: its offsets are `shift` past those of the part, and its errors are located in `origin`.
    `statements` collects every statement made, in source order; `retype`, where given, is the offset of a name `Type`
    that the source spells `type`."""

    def __init__(self, source: _Source, prepared: _Prepared, shift: int = 0, origin: _Source | None = None,
                 made: list[_Statement] | None = None, retype: int | None = None):
        self.source, self.pre, self.shift, self.origin = source, prepared, shift, origin or source
        self.made: list[_Statement] = [] if made is None else made
        self.retype = retype

    # Helpers

    def at(self, ts: _TS) -> int:
        return self.shift + self.source.offset(ts.start_byte)

    def text(self, ts: _TS) -> str:
        return self.source.data[ts.start_byte:ts.end_byte].decode("utf-16-le")

    def between(self, start: int, end: int) -> str:
        """The text between two byte offsets."""
        return self.source.data[start:end].decode("utf-16-le")

    def error(self, ts: _TS, message: str) -> ParseError:
        return self.origin.error(message, self.at(ts))

    def unsupported(self, ts: _TS) -> ParseError:
        return self.error(ts, f"unsupported syntax: {ts.type}")

    def new(self, ts: _TS, kind: str) -> _Statement:
        """A statement of `kind`, starting where `ts` does."""
        statement = _Statement("s?", kind, self.origin.line(self.at(ts)))
        self.made.append(statement)
        return statement

    @staticmethod
    def kids(ts: _TS) -> list[_TS]:
        """The children of `ts`, without comments and line continuations."""
        return [c for c in ts.children if c.type not in _EXTRAS]

    @staticmethod
    def named(ts: _TS) -> list[_TS]:
        return [c for c in ts.children if c.is_named and c.type not in _EXTRAS]

    @staticmethod
    def field(ts: _TS, name: str) -> _TS | None:
        return ts.child_by_field_name(name)

    @staticmethod
    def fields(ts: _TS, name: str) -> list[_TS]:
        return [c for i, c in enumerate(ts.children) if ts.field_name_for_child(i) == name]

    @staticmethod
    def has(ts: _TS, token: str) -> bool:
        return any(not c.is_named and c.type == token for c in ts.children)

    @staticmethod
    def require(ts: _TS, name: str) -> _TS:
        """A field the grammar requires, which tree-sitter always writes: it reports a missing one as an error."""
        return ts.child_by_field_name(name)  # type: ignore[return-value]

    def identifier(self, ts: _TS) -> str:
        if self.retype is not None and self.at(ts) == self.retype:
            return "type"
        return self.text(ts)

    def name(self, ts: _TS) -> P.Writer:
        return P.name(self.identifier(ts))

    # Errors

    def check(self, ts: _TS) -> None:
        """Raises for the first syntax error in `ts`, in source order, and for Python 2's statements."""
        stack = [ts]
        while stack:
            node = stack.pop()
            if node.type == "ERROR":
                raise self.error(node, "syntax error")
            if node.is_missing:
                raise self.error(node, f"expected {node.type}")
            if node.type in _PYTHON2:
                raise self.error(node, f"unsupported syntax: {node.type}, which is Python 2")
            stack.extend(reversed(node.children))

    # Statements

    def module(self, ts: _TS) -> list[_Statement]:
        self.check(ts)
        return self.statements(ts.children)

    def statements(self, nodes: list[_TS], header: _TS | None = None) -> list[_Statement]:
        """The statements and comments among `nodes`. A comment is trailing on the line where the node before it
        ends; for the first, that is `header`, the clause whose block the statements are."""
        out: list[_Statement] = []
        previous = header
        for ts in nodes:
            if ts.type == "comment":
                trailing = previous is not None and previous.end_point[0] == ts.start_point[0]
                out.append(self.new(ts, "Comment").set(text=self.text(ts)[1:].rstrip("\r"), trailing=trailing))
            elif ts.is_named and ts.type != "line_continuation":
                out.append(self.statement(ts))
            else:
                continue
            previous = ts
        return out

    def block(self, ts: _TS, clause: _TS) -> list[_Statement]:
        """The statements of the block `ts` of `clause`, with the comments tree-sitter lists beside the block: in the
        clause between its header and the block, and after the block until the next clause."""
        header = max((c for c in clause.children if c.type == ":" and c.start_byte < ts.start_byte),
                     key=lambda c: c.start_byte)
        before = [c for c in clause.children
                  if c.type == "comment" and header.start_byte < c.start_byte < ts.start_byte]
        after = self.after(ts)
        if clause.type in _CLAUSES:
            after += self.after(clause)
        return self.statements([*before, *ts.children, *after], header)

    @staticmethod
    def after(ts: _TS) -> list[_TS]:
        """The comments that follow `ts` among its siblings, up to the next sibling that is not one."""
        out: list[_TS] = []
        sibling = ts.next_sibling
        while sibling is not None and sibling.type == "comment":
            out.append(sibling)
            sibling = sibling.next_sibling
        return out

    def statement(self, ts: _TS) -> _Statement:
        return self.STATEMENTS[ts.type](self, ts)  # check() has raised for any other

    def expression_statement(self, ts: _TS) -> _Statement:
        kids = self.named(ts)
        if len(kids) > 1 or self.has(ts, ","):
            return self.new(ts, "Expr").set(value=P.tuple_(*(self.expression(k) for k in kids)))
        inner = kids[0]
        if inner.type == "assignment":
            annotation = self.field(inner, "type")
            right = self.field(inner, "right")
            if annotation is not None:
                made = self.new(ts, "AnnAssign")
                return made.set(target=self.target(self.require(inner, "left")), annotation=self.type(annotation),
                                value=None if right is None else self.expression(right))
            made = self.new(ts, "Assign")
            targets = [self.target(self.require(inner, "left"))]
            while right.type == "assignment":  # type: ignore[union-attr]
                targets.append(self.target(self.require(right, "left")))  # type: ignore[arg-type]
                right = self.require(right, "right")  # type: ignore[arg-type]
            return made.set(targets=targets, value=self.expression(right))  # type: ignore[arg-type]
        if inner.type == "augmented_assignment":
            made = self.new(ts, "AugAssign")
            return made.set(target=self.target(self.require(inner, "left")),
                            op=self.text(self.require(inner, "operator"))[:-1],
                            value=self.expression(self.require(inner, "right")))
        made = self.new(ts, "Expr")
        return made.set(value=self.expression(inner))

    def return_statement(self, ts: _TS) -> _Statement:
        made = self.new(ts, "Return")
        kids = self.named(ts)
        return made.set(value=self.expression(kids[0]) if kids else None)

    def delete_statement(self, ts: _TS) -> _Statement:
        made = self.new(ts, "Delete")
        target = self.named(ts)[0]
        targets = self.named(target) if target.type == "expression_list" else [target]
        return made.set(targets=[self.target(t) for t in targets])

    def raise_statement(self, ts: _TS) -> _Statement:
        made = self.new(ts, "Raise")
        cause = self.field(ts, "cause")
        kids = [k for k in self.named(ts) if cause is None or k.id != cause.id]
        return made.set(exc=self.expression(kids[0]) if kids else None,
                        cause=None if cause is None else self.expression(cause))

    def assert_statement(self, ts: _TS) -> _Statement:
        made = self.new(ts, "Assert")
        kids = self.named(ts)
        return made.set(test=self.expression(kids[0]), msg=self.expression(kids[1]) if len(kids) > 1 else None)

    def global_statement(self, ts: _TS) -> _Statement:
        return self.new(ts, "Global").set(names=[self.identifier(k) for k in self.named(ts)])

    def nonlocal_statement(self, ts: _TS) -> _Statement:
        return self.new(ts, "Nonlocal").set(names=[self.identifier(k) for k in self.named(ts)])

    def dotted(self, ts: _TS) -> str:
        return ".".join(self.identifier(k) for k in self.named(ts))

    def alias(self, ts: _TS) -> P.Helper:
        if ts.type == "aliased_import":
            return _helper("alias", name=self.dotted(self.require(ts, "name")),
                           asname=self.identifier(self.require(ts, "alias")))
        return _helper("alias", name=self.dotted(ts))

    def import_statement(self, ts: _TS) -> _Statement:
        made = self.new(ts, "Import")
        return made.set(is_lazy=self.at(ts) in self.pre.lazy, names=[self.alias(n) for n in self.fields(ts, "name")])

    def import_from_statement(self, ts: _TS) -> _Statement:
        made = self.new(ts, "ImportFrom").set(is_lazy=self.at(ts) in self.pre.lazy)
        module = self.require(ts, "module_name")
        if module.type == "relative_import":
            names = self.named(module)[1:]
            made.set(level=self.text(self.named(module)[0]).count("."),
                     module=self.dotted(names[0]) if names else None)
        else:
            made.set(module=self.dotted(module))
        wildcard = any(c.type == "wildcard_import" for c in ts.children)
        return made.set(names=[_helper("alias", name="*")] if wildcard else [
            self.alias(n) for n in self.fields(ts, "name")])

    def future_import_statement(self, ts: _TS) -> _Statement:
        made = self.new(ts, "ImportFrom")
        return made.set(module="__future__", names=[self.alias(n) for n in self.fields(ts, "name")])

    def type_alias_statement(self, ts: _TS) -> _Statement:
        left = self.named(self.require(ts, "left"))[0]
        if left.type not in ("identifier", "generic_type"):
            return self.reread(ts)
        made = self.new(ts, "TypeAlias")
        if left.type == "generic_type":
            name, parameters = self.named(left)
            made.set(name=self.name(name), type_params=self.type_parameters(parameters))
        else:
            made.set(name=self.name(left))
        return made.set(value=self.type(self.require(ts, "right")))

    def reread(self, ts: _TS) -> _Statement:
        """An assignment to an expression that starts with the name `type`, as `type(t).name = value`, which
        tree-sitter-python reads as a type alias: it is parsed again with `Type` for `type`, which is then put back."""
        source = _Source("Type" + self.text(ts)[4:])
        tree = _PARSER.parse(source.data, encoding="utf16le")
        converter = _Converter(source, _Prepared(), self.at(ts), self.origin, self.made, self.at(ts))
        converter.check(tree.root_node)
        return converter.statement(converter.named(tree.root_node)[0])

    def print_statement(self, ts: _TS) -> _Statement:
        """`print >> file, value`, which is Python 3 too: a tuple of a shift and the values. tree-sitter-python
        reads it as Python 2's print statement, which without `>>` is not Python 3."""
        chevron = next((c for c in ts.children if c.type == "chevron"), None)
        if chevron is None:
            raise self.error(ts, "unsupported syntax: print_statement, which is Python 2")
        made = self.new(ts, "Expr")
        shift = P.binop(">>", P.name("print"), self.expression(self.named(chevron)[0]))
        values = [self.expression(a) for a in self.fields(ts, "argument")]
        return made.set(value=P.tuple_(shift, *values) if values else shift)

    def simple(kind: str) -> Callable[[_Converter, _TS], _Statement]:  # type: ignore[misc]
        return lambda self, ts: self.new(ts, kind)

    # Compound statements

    def if_statement(self, ts: _TS) -> _Statement:
        made = self.new(ts, "If").set(test=self.expression(self.require(ts, "condition")))
        made.hold("body", self.block(self.require(ts, "consequence"), ts))
        last = made
        for clause in self.fields(ts, "alternative"):
            if clause.type == "elif_clause":
                elif_ = self.new(clause, "If").set(test=self.expression(self.require(clause, "condition")))
                last.hold("orelse", [elif_])
                elif_.hold("body", self.block(self.require(clause, "consequence"), clause))
                last = elif_
            else:
                last.hold("orelse", self.block(self.require(clause, "body"), clause))
        return made

    def orelse(self, ts: _TS) -> list[_Statement]:
        clause = self.field(ts, "alternative")
        return [] if clause is None else self.block(self.require(clause, "body"), clause)

    def while_statement(self, ts: _TS) -> _Statement:
        made = self.new(ts, "While").set(test=self.expression(self.require(ts, "condition")))
        return made.hold("body", self.block(self.require(ts, "body"), ts)).hold("orelse", self.orelse(ts))

    def for_statement(self, ts: _TS) -> _Statement:
        made = self.new(ts, "AsyncFor" if self.has(ts, "async") else "For")
        made.set(target=self.target(self.require(ts, "left")), iter=self.expression(self.require(ts, "right")))
        return made.hold("body", self.block(self.require(ts, "body"), ts)).hold("orelse", self.orelse(ts))

    def try_statement(self, ts: _TS) -> _Statement:
        clauses = self.named(ts)[1:]
        star = any(c.type == "except_clause" and self.has(c, "*") for c in clauses)
        made = self.new(ts, "TryStar" if star else "Try")
        made.hold("body", self.block(self.require(ts, "body"), ts))
        handlers, orelse, finalbody = [], [], []
        for clause in clauses:
            if clause.type == "except_clause":
                handlers.append(self.handler(clause))
            elif clause.type == "else_clause":
                orelse = self.block(self.require(clause, "body"), clause)
            else:
                finalbody = self.block(self.named(clause)[0], clause)
        return made.hold("handlers", handlers).hold("orelse", orelse).hold("finalbody", finalbody)

    def handler(self, ts: _TS) -> _Statement:
        made = self.new(ts, "ExceptHandler")
        values = self.fields(ts, "value")
        if len(values) == 1 and values[0].type == "as_pattern":
            made.set(name=self.identifier(self.named(self.require(values[0], "alias"))[0]))
            values = [self.named(values[0])[0]]
        if len(values) > 1:
            made.set(type=P.tuple_(*(self.expression(v) for v in values)))
        elif values:
            made.set(type=self.expression(values[0]))
        return made.hold("body", self.block(self.named(ts)[-1], ts))

    def with_statement(self, ts: _TS) -> _Statement:
        made = self.new(ts, "AsyncWith" if self.has(ts, "async") else "With")
        items = []
        for item in self.named(self.named(ts)[0]):
            value = self.require(item, "value")
            if value.type == "parenthesized_expression" and self.named(value)[0].type == "as_pattern":
                value = self.named(value)[0]  # `with (manager() as target):`, one item in parentheses
            if value.type == "as_pattern":
                target = self.named(self.require(value, "alias"))[0]
                items.append(_helper("withitem", context_expr=self.expression(self.named(value)[0]),
                                     optional_vars=self.target(target)))
            else:
                items.append(_helper("withitem", context_expr=self.expression(value)))
        return made.set(items=items).hold("body", self.block(self.require(ts, "body"), ts))

    def match_statement(self, ts: _TS) -> _Statement:
        made = self.new(ts, "Match")
        subjects = self.fields(ts, "subject")
        made.set(subject=P.tuple_(*(self.expression(s) for s in subjects))
                 if len(subjects) > 1 or self.has(ts, ",") else self.expression(subjects[0]))
        cases = []
        for clause in self.fields(self.require(ts, "body"), "alternative"):
            case = self.new(clause, "MatchCase")
            patterns = [c for c in self.named(clause) if c.type == "case_pattern"]
            pattern = _term("matchsequence", patterns=[self.pattern(p) for p in patterns]) \
                if len(patterns) > 1 or self.has(clause, ",") else self.pattern(patterns[0])
            guard = self.field(clause, "guard")
            case.set(pattern=pattern, guard=None if guard is None else self.expression(self.named(guard)[0]))
            cases.append(case.hold("body", self.block(self.require(clause, "consequence"), clause)))
        return made.hold("cases", cases)

    def function_definition(self, ts: _TS) -> _Statement:
        made = self.new(ts, "AsyncFunctionDef" if self.has(ts, "async") else "FunctionDef")
        parameters = self.field(ts, "type_parameters")
        returns = self.field(ts, "return_type")
        made.set(name=self.identifier(self.require(ts, "name")),
                 type_params=None if parameters is None else self.type_parameters(parameters),
                 args=self.arguments(self.require(ts, "parameters")),
                 returns=None if returns is None else self.type(returns))
        return made.hold("body", self.block(self.require(ts, "body"), ts))

    def class_definition(self, ts: _TS) -> _Statement:
        made = self.new(ts, "ClassDef")
        parameters = self.field(ts, "type_parameters")
        made.set(name=self.identifier(self.require(ts, "name")),
                 type_params=None if parameters is None else self.type_parameters(parameters))
        superclasses = self.field(ts, "superclasses")
        if superclasses is not None:
            bases, keywords = self.call_arguments(superclasses)
            made.set(bases=bases, keywords=keywords)
        return made.hold("body", self.block(self.require(ts, "body"), ts))

    def decorated_definition(self, ts: _TS) -> _Statement:
        decorators = [self.expression(self.named(d)[0]) for d in self.named(ts) if d.type == "decorator"]
        made = self.statement(self.require(ts, "definition"))
        properties = dict(made.properties)
        made.properties = {"decorator_list": decorators}
        return made.set(**properties)

    STATEMENTS: dict[str, Callable[[_Converter, _TS], Any]] = {
        "expression_statement": expression_statement, "return_statement": return_statement,
        "delete_statement": delete_statement, "raise_statement": raise_statement,
        "assert_statement": assert_statement, "pass_statement": simple("Pass"),
        "break_statement": simple("Break"), "continue_statement": simple("Continue"),
        "global_statement": global_statement, "nonlocal_statement": nonlocal_statement,
        "import_statement": import_statement, "import_from_statement": import_from_statement,
        "future_import_statement": future_import_statement, "type_alias_statement": type_alias_statement,
        "print_statement": print_statement,
        "if_statement": if_statement, "while_statement": while_statement, "for_statement": for_statement,
        "try_statement": try_statement, "with_statement": with_statement, "match_statement": match_statement,
        "function_definition": function_definition, "class_definition": class_definition,
        "decorated_definition": decorated_definition,
    }

    # Parameters

    def arguments(self, ts: _TS) -> P.Helper:
        """A function's parameter list, an `Arguments`."""
        return _helper("arguments", **self.parameters(ts))

    def parameters(self, ts: _TS) -> dict[str, Any]:
        """A function's or a lambda's parameters, by group: `posonlyargs`, `args`, `vararg`, `kwonlyargs`, `kwarg`."""
        made: dict[str, Any] = {"posonlyargs": [], "args": [], "vararg": None, "kwonlyargs": [], "kwarg": None}
        keyword_only = False
        for p in self.named(ts):
            if p.type == "positional_separator":
                made["posonlyargs"], made["args"] = made["args"], []
            elif p.type == "keyword_separator":
                keyword_only = True
            elif p.type in ("list_splat_pattern", "dictionary_splat_pattern") or (
                    p.type == "typed_parameter" and self.named(p)[0].type != "identifier"):
                splat = p if p.type != "typed_parameter" else self.named(p)[0]
                annotation = self.field(p, "type")
                arg = P.arg(self.identifier(self.named(splat)[0]),
                            annotation=None if annotation is None else self.type(annotation))
                if splat.type == "list_splat_pattern":
                    made["vararg"], keyword_only = arg, True
                else:
                    made["kwarg"] = arg
            else:
                made["kwonlyargs" if keyword_only else "args"].append(self.parameter(p))
        return made

    def parameter(self, ts: _TS) -> P.Helper:
        if ts.type == "identifier":
            return P.arg(self.identifier(ts))
        if ts.type == "typed_parameter":
            return P.arg(self.identifier(self.named(ts)[0]), annotation=self.type(self.require(ts, "type")))
        if ts.type not in ("default_parameter", "typed_default_parameter"):
            raise self.unsupported(ts)
        name = self.require(ts, "name")
        if name.type != "identifier":
            raise self.unsupported(name)
        annotation = self.field(ts, "type")
        return P.arg(self.identifier(name), self.expression(self.require(ts, "value")),
                     None if annotation is None else self.type(annotation))

    def type_parameters(self, ts: _TS) -> list[FT.Writer]:
        """A type parameter list, each a `Python Types` term: `typevar`, `paramspec` or `typevartuple`."""
        out: list[FT.Writer] = []
        for t in self.named(ts):
            inner = self.named(t)[0]
            default = self.pre.defaults.get(self.at(t))
            default_value = None if default is None else self.part(*default)
            if inner.type == "constrained_type":
                name, bound = self.named(inner)
                out.append(_term("typevar", name=self.identifier(self.named(name)[0]), bound=self.type(bound),
                                 default_value=default_value))
            elif inner.type == "splat_type":
                kind = "paramspec" if self.has(inner, "**") else "typevartuple"
                out.append(_term(kind, name=self.identifier(self.named(inner)[0]), default_value=default_value))
            elif inner.type == "identifier":
                out.append(_term("typevar", name=self.identifier(inner), default_value=default_value))
            else:
                raise self.unsupported(inner)
        return out

    def part(self, offset: int, text: str) -> P.Writer:
        """The expression `text`, at `offset` of the text, which the pre-pass removed."""
        source = _Source(f"({text})")
        tree = _PARSER.parse(source.data, encoding="utf16le")
        converter = _Converter(source, _Prepared(), offset - 1, self.origin, [])
        converter.check(tree.root_node)
        statement = converter.named(tree.root_node)[0]
        return converter.expression(converter.named(converter.named(statement)[0])[0])

    # Annotations: tree-sitter-python's type grammar

    def type(self, ts: _TS) -> P.Writer:
        """An annotation, or the value of a type alias: tree-sitter's `type`, which holds an expression or a
        construct of its type grammar."""
        inner = self.named(ts)[0] if ts.type == "type" else ts
        if inner.type == "generic_type":
            name, parameters = self.named(inner)
            elts = [self.type(t) for t in self.named(parameters)]
            return P.subscript(self.expression(name), elts[0] if len(elts) == 1 else P.tuple_(*elts))
        if inner.type == "union_type":
            # `a | b | c` groups to the left, which tree-sitter-python's type grammar writes to the right
            members: list[_TS] = []

            def flatten(node: _TS) -> None:
                node = self.named(node)[0] if node.type == "type" else node
                if node.type == "union_type" or (
                        node.type == "binary_operator" and self.text(self.require(node, "operator")) == "|"):
                    for member in self.named(node) if node.type == "union_type" else (
                            self.require(node, "left"), self.require(node, "right")):
                        flatten(member)
                else:
                    members.append(node)

            flatten(inner)
            union = self.type(members[0])
            for member in members[1:]:
                union = P.binop("|", union, self.type(member))
            return union
        if inner.type == "splat_type":
            return P.starred(self.name(self.named(inner)[0]))
        return self.expression(inner)

    # Assignment targets: tree-sitter-python's patterns

    def target(self, ts: _TS) -> P.Writer:
        if ts.type in ("pattern_list", "tuple_pattern"):
            elts = [self.target(k) for k in self.named(ts)]
            if ts.type == "tuple_pattern" and len(elts) == 1 and not self.has(ts, ","):
                return P.parenthesized(elts[0])
            return P.tuple_(*elts)
        if ts.type == "list_pattern":
            return P.list_(*(self.target(k) for k in self.named(ts)))
        if ts.type == "list_splat_pattern":
            return P.starred(self.target(self.named(ts)[0]))
        return self.expression(ts)

    # Expressions

    def expression(self, ts: _TS) -> P.Writer:
        method = self.EXPRESSIONS.get(ts.type)
        if method is None:
            raise self.unsupported(ts)
        return method(self, ts)

    def constant(self, ts: _TS) -> P.Writer:
        text = self.text(ts)
        if ts.type == "ellipsis":
            return _literal(Ellipsis, text)
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")  # an invalid escape, `'\d'`, which Python warns of
                value = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            raise self.error(ts, f"unsupported syntax: {text}") from None
        return _literal(value, text)

    def string(self, ts: _TS) -> P.Writer:
        start = self.named(ts)[0]
        quote_at = next(i for i, ch in enumerate(self.text(start)) if ch in "'\"")
        prefix, quote = self.text(start)[:quote_at], self.text(start)[quote_at:]
        if not any(ch in prefix for ch in "fFtT"):
            return self.constant(ts)
        template = any(ch in prefix for ch in "tT")
        fields = [c for c in self.named(ts) if c.type == "interpolation"]
        # the text ends at the closing quote: tree-sitter-python counts the backslashes before it in a raw string as
        # part of its end, as in `fr'\\'`
        end = ts.end_byte - 2 * len(quote)
        values = self.pieces(start.end_byte, end, fields, template)
        return P.templatestr(values, prefix, quote) if template else P.joinedstr(values, prefix, quote)

    def pieces(self, start: int, end: int, fields: list[_TS], template: bool) -> list[Any]:
        """The text (a str) and replacement fields between two byte offsets of an f-string, t-string or format
        spec."""
        out: list[Any] = []
        at = start
        for field in fields:
            if field.start_byte > at:
                out.append(self.between(at, field.start_byte))
            out.append(self.replacement(field, template))
            at = field.end_byte
        if end > at:
            out.append(self.between(at, end))
        return out

    def replacement(self, ts: _TS, template: bool) -> P.Helper:
        """A replacement field: an interpolation of a t-string, or else a formatted value."""
        write = P.interpolation if template else P.formattedvalue
        expression = self.require(ts, "expression")
        conversion = self.field(ts, "type_conversion")
        spec = self.field(ts, "format_specifier")
        closing = ts.children[-1]
        end = (conversion or spec or closing).start_byte
        debug = self.has(ts, "=")
        if expression.type == "named_expression" and spec is None:
            # `{x:=10}` formats `x` with the spec `=10`, which tree-sitter-python reads as an assignment expression
            name = self.require(expression, "name")
            colon = next(c for c in expression.children if c.type == ":=")
            return write(self.name(name), None, (self.between(colon.start_byte + 2, closing.start_byte),), debug,
                         self.between(ts.children[0].end_byte, name.end_byte))
        format_spec = None
        if spec is not None:
            fields = [c for c in self.named(spec) if c.type == "format_expression"]
            format_spec = tuple(self.pieces(spec.children[0].end_byte, spec.end_byte, fields, False))
        return write(self.expression(expression), None if conversion is None else self.text(conversion)[1:],
                     format_spec, debug, self.between(ts.children[0].end_byte, end))

    def concatenated_string(self, ts: _TS) -> P.Writer:
        return P.concatenatedstring(*(self.expression(k) for k in self.named(ts)))

    def parenthesized_expression(self, ts: _TS) -> P.Writer:
        return P.parenthesized(self.expression(self.named(ts)[0]))

    def tuple(self, ts: _TS) -> P.Writer:
        return P.tuple_(*(self.expression(k) for k in self.named(ts)))

    def list_(self, ts: _TS) -> P.Writer:
        return P.list_(*(self.expression(k) for k in self.named(ts)))

    def set_(self, ts: _TS) -> P.Writer:
        return P.set_(*(self.expression(k) for k in self.named(ts)))

    def dictionary(self, ts: _TS) -> P.Writer:
        items = []
        for k in self.named(ts):
            if k.type == "pair":
                items.append((self.expression(self.require(k, "key")), self.expression(self.require(k, "value"))))
            else:
                items.append((None, self.expression(self.named(k)[0])))
        return P.dict_(*items)

    def generators(self, ts: _TS) -> list[P.Helper]:
        clauses: list[tuple[_TS, Any, Any, list[Any]]] = []
        for clause in self.named(ts)[1:]:
            if clause.type == "for_in_clause":
                right = [k for k in self.fields(clause, "right") if k.is_named]
                iter_ = self.expression(right[0]) if len(right) == 1 else P.tuple_(
                    *(self.expression(r) for r in right))
                clauses.append((clause, self.target(self.require(clause, "left")), iter_, []))
            else:
                clauses[-1][3].append(self.expression(self.named(clause)[0]))
        return [P.comprehension(target, iter_, ifs, self.has(clause, "async"))
                for clause, target, iter_, ifs in clauses]

    def list_comprehension(self, ts: _TS) -> P.Writer:
        return P.listcomp(self.expression(self.require(ts, "body")), *self.generators(ts))

    def set_comprehension(self, ts: _TS) -> P.Writer:
        if self.at(ts) in self.pre.unpacking:
            return P.dictcomp(self.expression(self.require(ts, "body")), None, *self.generators(ts))
        return P.setcomp(self.expression(self.require(ts, "body")), *self.generators(ts))

    def dictionary_comprehension(self, ts: _TS) -> P.Writer:
        pair = self.require(ts, "body")
        return P.dictcomp(self.expression(self.require(pair, "key")), self.expression(self.require(pair, "value")),
                          *self.generators(ts))

    def generator_expression(self, ts: _TS) -> P.Writer:
        return P.generatorexp(self.expression(self.require(ts, "body")), *self.generators(ts))

    def yield_(self, ts: _TS) -> P.Writer:
        kids = self.named(ts)
        if self.has(ts, "from"):
            return P.yieldfrom(self.expression(kids[0]))
        return P.yield_(self.expression(kids[0]) if kids else None)

    def attribute(self, ts: _TS) -> P.Writer:
        return P.attribute(self.expression(self.require(ts, "object")), self.identifier(self.require(ts, "attribute")))

    def subscript(self, ts: _TS) -> P.Writer:
        elts = [self.expression(i) for i in self.fields(ts, "subscript")]
        index = elts[0] if len(elts) == 1 and not self.has(ts, ",") else P.tuple_(*elts)
        return P.subscript(self.expression(self.require(ts, "value")), index)

    def slice_(self, ts: _TS) -> P.Writer:
        parts: list[Any] = [None, None, None]
        colons = 0
        for c in self.kids(ts):
            if c.type == ":":
                colons += 1
            else:
                parts[colons] = self.expression(c)
        return P.slice_(*parts)

    def call_arguments(self, ts: _TS) -> tuple[list[P.Writer], list[P.Helper]]:
        args: list[P.Writer] = []
        keywords: list[P.Helper] = []
        for k in self.named(ts):
            if k.type == "keyword_argument":
                keywords.append(P.keyword(self.identifier(self.require(k, "name")),
                                          self.expression(self.require(k, "value"))))
            elif k.type == "dictionary_splat":
                keywords.append(P.keyword(None, self.expression(self.named(k)[0])))
            else:
                args.append(self.expression(k))
        return args, keywords

    def call(self, ts: _TS) -> P.Writer:
        arguments = self.require(ts, "arguments")
        func = self.expression(self.require(ts, "function"))
        if arguments.type == "generator_expression":
            return P.call(func, self.expression(arguments))
        args, keywords = self.call_arguments(arguments)
        return P.call(func, *args, *keywords)

    def splat(self, ts: _TS) -> P.Writer:
        return P.starred(self.expression(self.named(ts)[0]))

    def await_(self, ts: _TS) -> P.Writer:
        value = self.named(ts)[0]
        if value.type == "binary_operator" and self.text(self.require(value, "operator")) == "**":
            # `await x ** y` is `(await x) ** y`, which tree-sitter-python reads as `await (x ** y)`
            return P.binop("**", P.await_(self.expression(self.require(value, "left"))),
                           self.expression(self.require(value, "right")))
        return P.await_(self.expression(value))

    def unary_operator(self, ts: _TS) -> P.Writer:
        return P.unaryop(self.text(self.require(ts, "operator")), self.expression(self.require(ts, "argument")))

    def not_operator(self, ts: _TS) -> P.Writer:
        return P.unaryop("not", self.expression(self.require(ts, "argument")))

    def binary_operator(self, ts: _TS) -> P.Writer:
        """A chain of binary operators, regrouped by Python's precedence."""
        operands: list[_TS] = []
        operators: list[str] = []

        def flatten(node: _TS) -> None:
            if node.type == "binary_operator":
                flatten(self.require(node, "left"))
                operators.append(self.text(self.require(node, "operator")))
                flatten(self.require(node, "right"))
            else:
                operands.append(node)

        flatten(ts)
        values = [self.expression(o) for o in operands]

        def build(low: int, high: int, level: int) -> P.Writer:
            """The operands `low` to `high`, with the operators between them, at precedence `level` or above."""
            if low == high:
                return values[low]
            group = _LEVELS[level]
            splits = [k for k in range(low, high) if operators[k] in group]
            if not splits:
                return build(low, high, level + 1)
            k = splits[0] if group == ("**",) else splits[-1]  # `**` groups to the right, the others to the left
            right_level = level if group == ("**",) else level + 1
            left_level = level + 1 if group == ("**",) else level
            return P.binop(operators[k], build(low, k, left_level), build(k + 1, high, right_level))

        return build(0, len(values) - 1, 0)

    def boolean_operator(self, ts: _TS) -> P.Writer:
        op = self.text(self.require(ts, "operator"))
        return P.boolop(op, *self.operands(ts, op))

    def operands(self, ts: _TS, op: str) -> list[P.Writer]:
        """The operands of a chain of `op`, `and` or `or`, flattened where tree-sitter nests the same operator."""
        values: list[P.Writer] = []
        for side in (self.require(ts, "left"), self.require(ts, "right")):
            if side.type == "boolean_operator" and self.text(self.require(side, "operator")) == op:
                values.extend(self.operands(side, op))
            else:
                values.append(self.expression(side))
        return values

    def comparison_operator(self, ts: _TS) -> P.Writer:
        operands = [c for c in self.named(ts) if ts.field_name_for_child(ts.children.index(c)) != "operators"]
        links = []
        for op, operand in zip(self.fields(ts, "operators"), operands[1:]):
            spelling = " ".join(self.text(op).split())
            if spelling == "<>":
                raise self.error(op, "unsupported syntax: <>, which is Python 2")
            links.append((spelling, self.expression(operand)))
        return P.compare(links[0][0], self.expression(operands[0]), links[0][1], *links[1:])

    def conditional_expression(self, ts: _TS) -> P.Writer:
        body, test, orelse = self.named(ts)
        if body.type == "named_expression":
            # `x := a if b else c` is `x := (a if b else c)`, which tree-sitter-python reads as `(x := a) if b else c`
            value = P.ifexp(self.expression(test), self.expression(self.require(body, "value")),
                            self.expression(orelse))
            return P.namedexpr(self.name(self.require(body, "name")), value)
        return P.ifexp(self.expression(test), self.expression(body), self.expression(orelse))

    def named_expression(self, ts: _TS) -> P.Writer:
        return P.namedexpr(self.name(self.require(ts, "name")), self.expression(self.require(ts, "value")))

    def lambda_(self, ts: _TS) -> P.Writer:
        parameters = self.field(ts, "parameters")
        groups = {} if parameters is None else self.parameters(parameters)
        return P.lambda_(self.expression(self.require(ts, "body")), **groups)

    def identifier_expression(self, ts: _TS) -> P.Writer:
        return self.name(ts)

    EXPRESSIONS: dict[str, Callable[[_Converter, _TS], Any]] = {
        "identifier": identifier_expression, "integer": constant, "float": constant, "true": constant,
        "false": constant, "none": constant, "ellipsis": constant, "string": string,
        "concatenated_string": concatenated_string, "parenthesized_expression": parenthesized_expression,
        "tuple": tuple, "expression_list": tuple, "pattern_list": tuple, "list": list_,
        "set": set_, "dictionary": dictionary, "list_comprehension": list_comprehension,
        "set_comprehension": set_comprehension, "dictionary_comprehension": dictionary_comprehension,
        "generator_expression": generator_expression, "yield": yield_, "attribute": attribute,
        "subscript": subscript, "slice": slice_, "call": call, "list_splat": splat, "list_splat_pattern": splat,
        "await": await_, "unary_operator": unary_operator,
        "not_operator": not_operator, "binary_operator": binary_operator, "boolean_operator": boolean_operator,
        "comparison_operator": comparison_operator, "conditional_expression": conditional_expression,
        "named_expression": named_expression, "lambda": lambda_,
    }

    # Patterns: `Python Patterns` terms

    def pattern(self, ts: _TS) -> FT.Writer:
        """A pattern: a `case_pattern`, or what one holds."""
        if ts.type == "_":
            return _term("matchas")
        if ts.type == "case_pattern":
            kids = self.kids(ts)
            if kids[0].type == "-":
                return _term("matchvalue", value=self.signed(kids))
            return self.pattern(kids[0])
        method = self.PATTERNS.get(ts.type)
        if method is not None:
            return method(self, ts)
        if ts.type in ("none", "true", "false"):
            return _term("matchsingleton", value=self.text(ts))
        return _term("matchvalue", value=self.expression(ts))

    def signed(self, kids: list[_TS]) -> P.Writer:
        """A negative number, `-1`, which tree-sitter-python writes as two tokens."""
        return P.unaryop("-", self.expression(kids[1]))

    def as_pattern(self, ts: _TS) -> FT.Writer:
        pattern, name = self.named(ts)
        return _term("matchas", pattern=self.pattern(pattern), name=self.identifier(name))

    def union_pattern(self, ts: _TS) -> FT.Writer:
        patterns: list[FT.Writer] = []
        kids = [k for k in self.kids(ts) if k.type != "|"]
        i = 0
        while i < len(kids):
            k = kids[i]
            if k.type == "-":  # tree-sitter lists `-1` as two alternatives' worth of children
                patterns.append(_term("matchvalue", value=self.signed(kids[i:i + 2])))
                i += 1
            else:
                patterns.append(self.pattern(k))
            i += 1
        return _term("matchor", patterns=patterns)

    def list_pattern(self, ts: _TS) -> FT.Writer:
        return _term("matchsequence", delimiters="[]", patterns=[self.pattern(k) for k in self.named(ts)])

    def tuple_pattern(self, ts: _TS) -> FT.Writer:
        patterns = [self.pattern(k) for k in self.named(ts)]
        if len(patterns) == 1 and not self.has(ts, ","):
            return patterns[0]  # a group: `(pattern)`
        return _term("matchsequence", delimiters="()", patterns=patterns)

    def splat_pattern(self, ts: _TS) -> FT.Writer:
        names = self.named(ts)
        return _term("matchstar", name=self.identifier(names[0]) if names else None)

    def dotted_pattern(self, ts: _TS) -> FT.Writer:
        names = self.named(ts)
        if len(names) == 1:
            return _term("matchas", name=self.identifier(names[0]))
        return _term("matchvalue", value=self.dotted_expression(ts))

    def dotted_expression(self, ts: _TS) -> P.Writer:
        names = self.named(ts)
        value = self.name(names[0])
        for name in names[1:]:
            value = P.attribute(value, self.identifier(name))
        return value

    def dict_pattern(self, ts: _TS) -> FT.Writer:
        keys: list[P.Writer] = []
        patterns: list[FT.Writer] = []
        rest = None
        kids = self.kids(ts)
        i = 0
        while i < len(kids):
            k = kids[i]
            if k.type == "splat_pattern":
                rest = self.identifier(self.named(k)[0])
            elif ts.field_name_for_child(ts.children.index(k)) == "key":
                key = [k]
                if k.type == "-":
                    i += 1
                    key.append(kids[i])
                keys.append(self.signed(key) if k.type == "-" else self.pattern_value(k))
            elif k.type == "case_pattern":
                patterns.append(self.pattern(k))
            i += 1
        return _term("matchmapping", keys=keys, patterns=patterns, rest=rest)

    def pattern_value(self, ts: _TS) -> P.Writer:
        """A literal or dotted name in a pattern, as an expression."""
        if ts.type == "dotted_name":
            return self.dotted_expression(ts)
        if ts.type == "complex_pattern":
            return self.complex(ts)
        return self.expression(ts)

    def complex(self, ts: _TS) -> P.Writer:
        kids = self.kids(ts)
        if kids[0].type == "-":
            left = P.unaryop("-", self.expression(kids[1]))
            kids = kids[2:]
        else:
            left, kids = self.expression(kids[0]), kids[1:]
        return P.binop(kids[0].type, left, self.expression(kids[1]))

    def complex_pattern(self, ts: _TS) -> FT.Writer:
        return _term("matchvalue", value=self.complex(ts))

    def class_pattern(self, ts: _TS) -> FT.Writer:
        names = self.named(ts)
        patterns: list[FT.Writer] = []
        kwd_attrs: list[str] = []
        kwd_patterns: list[FT.Writer] = []
        for k in names[1:]:
            inner = self.kids(k)[0]
            if inner.type == "as_pattern" and self.kids(self.named(inner)[0])[0].type == "keyword_pattern":
                # `name=pattern as alias`, which tree-sitter-python reads as `(name=pattern) as alias`
                keyword, alias = self.kids(self.named(inner)[0])[0], self.named(inner)[-1]
                name, *value = self.kids(keyword)
                kwd_attrs.append(self.identifier(name))
                kwd_patterns.append(_term("matchas", pattern=self.keyword_value(value[1:]),
                                          name=self.identifier(alias)))
            elif inner.type == "keyword_pattern":
                name, *value = self.kids(inner)
                kwd_attrs.append(self.identifier(name))
                kwd_patterns.append(self.keyword_value(value[1:]))
            else:
                patterns.append(self.pattern(k))
        return _term("matchclass", cls=self.dotted_expression(names[0]), patterns=patterns, kwd_attrs=kwd_attrs,
                     kwd_patterns=kwd_patterns)

    def keyword_value(self, kids: list[_TS]) -> FT.Writer:
        """The pattern of a keyword pattern, which tree-sitter does not wrap in a `case_pattern`."""
        if kids[0].type == "-":
            return _term("matchvalue", value=self.signed(kids))
        return self.pattern(kids[0])

    PATTERNS: dict[str, Callable[[_Converter, _TS], Any]] = {
        "as_pattern": as_pattern, "union_pattern": union_pattern, "list_pattern": list_pattern,
        "tuple_pattern": tuple_pattern, "splat_pattern": splat_pattern, "dotted_name": dotted_pattern,
        "dict_pattern": dict_pattern, "class_pattern": class_pattern, "complex_pattern": complex_pattern,
    }


# --- The transaction ---


def _resolver(txn: Any, store: Any) -> Callable[[str], Any]:
    """A schema by its name: the store's, where given, else as the transaction names it."""
    if store is not None:
        return store.registered
    cache: dict[str, Any] = {}

    def resolve(name: str) -> Any:
        if name not in cache:
            found = txn
            for part in name.split("."):
                found = getattr(found, part)
            cache[name] = found
        return cache[name]

    return resolve


def _spec(statement: _Statement) -> Callable[[Any], Any]:
    """The spec item that writes a statement: its properties, its location, and its children, each by the property
    that holds it and its index there."""
    properties, line = statement.properties, statement.line
    children = [(property, index, child.symbol) for property, index, child in statement.children]

    def write(_: Any) -> Any:
        r = getattr(_, statement.symbol)
        for name, value in properties.items():
            getattr(r, name)(value)
        r.location([lambda e: e.file(_.module).line(line)])
        if children:
            r.children([lambda e, p=p, i=i, s=s: e.child(getattr(_, s)).property(p).index(i)
                        for p, i, s in children])
        return r

    return write


def parse(text: str, path: str, store: Any = None) -> Callable[[Any], Any]:
    """The callback of the transaction that writes `text`, Python 3 source, as the module at `path` in the
    workspace: given to `store.transaction`, or, with `store`, to `store.Mutations.OfTransaction`. Raises
    `ParseError` for text tree-sitter-python cannot parse, or a construct the dialects cannot hold, now, before any
    transaction."""
    source = _Source(text)
    tree = _PARSER.parse(source.data, encoding="utf16le")
    prepared = _Prepared()
    if tree.root_node.has_error:
        cleaned, prepared = _prepare(text, tree.root_node, source)
        source = _Source(text, cleaned)
        tree = _PARSER.parse(source.data, encoding="utf16le")
    converter = _Converter(source, prepared)
    body = converter.module(tree.root_node)
    statements = converter.made
    for i, statement in enumerate(statements):
        statement.symbol = f"s{i}"
    items = [_spec(statement) for statement in statements]
    top = [(i, statement.symbol) for i, statement in enumerate(body)]

    def transaction(txn: Any) -> Any:
        schema = _resolver(txn, store)
        symbols = {"ws": schema("Programs.Framework.Workspace"), "module": schema(f"{_LANGUAGE}.Module"),
                   **{statement.symbol: schema(f"{_LANGUAGE}.{statement.kind}") for statement in statements}}
        return txn.uid(path).mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
            .symbols(symbols)
            .spec([
                lambda _: _.ws.files({path: lambda e: e.file(_.module)}),
                lambda _: _.module.body([lambda e, i=i, s=s: e.child(getattr(_, s)).property("body").index(i)
                                         for i, s in top]),
                *items,
            ])]))])

    return transaction
