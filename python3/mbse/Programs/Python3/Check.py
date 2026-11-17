"""Check: which versions of Python 3 have the constructs a stored module uses, and whether it is a valid one.

A module is a `Programs.Python3.Module` that `Programs.Framework.TheWorkspace` owns by its path, as `Parse` writes it.
Both functions read it, within the transaction open on `store` or, where none is, within one of their own, and write
nothing; each raises LookupError where the workspace holds no file at `path`.

- `check(store, path, version)`: the problems of the constructs the module uses that `version` lacks, in source order,
  each once. `version` is a version of Python 3, as `(3, 12)` or by the name the language covers it by (`"Python
  3.12"`); LookupError where the language covers none such. The store must hold the standards (`Standards.prepare`).
- `validate(store, path)`: the module's problems as a tree, in source order: each kind's own rules, ported from the 0.3
  language's `check()` methods, and its terms' problems, as their dialects validate them.

Each problem is located by its path from the module: a statement's is the property of what holds it and its index
there, from the module's `body` (`body[2]`, `body[0].orelse[0]`, `body[1].handlers[0]`); a statement's
property's, the statement's then the property, with its index where it holds a list (`body[0].value`,
`body[3].decorator_list[0]`). So: `body[2]: TypeAlias needs Python 3.12`, `body[0].value: namedexpr needs Python 3.8`.

What a version has is read from data, as mbse-expressions records it (mbse-basis [CAP-268: standards as tagged data](mbse:mbse-basis/docs/capabilities/CAP-268.md#decided)):
a statement or clause kind is available where a standard of that version's name, among those `Programs.Python3`
covers, lists its schema (`Standards`); a term's kind, where one of those of `Python3`, `Python Types` or `Python
Patterns` does (`Standards.DIALECTS`). A kind no standard lists (an extension, invalid syntax, a helper) is not checked: `check` skips invalid syntax, a
`Programs.Framework.Error` and an `error` or `missing` term, which `validate` reports *(agent)*.
A kind's problem is `<kind> needs <the first version that has it>`: a statement's kind by its name (`TypeAlias`), a
term's by its tag (`namedexpr`).

What a property's value makes available stays code, `FEATURES`, by the kind that holds it: a standard tags a kind, not a
property or a value of one *(agent)*. As the 0.3 language had them (`Python/Syntax.py`, `FEATURES` and `features()`):

- statements: `Import.is_lazy` and `ImportFrom.is_lazy` (3.15), `AugAssign.op '@'` (3.5), `FunctionDef`'s,
  `AsyncFunctionDef`'s and `ClassDef`'s `type_params` (3.12), and a decorator that is not a dotted name, optionally
  called (PEP 614, 3.9);
- terms, which mbse-expressions does not record (a gap, reported there): `binop.op '@'` (3.5), `comprehension.is_async`
  (3.6), `formattedvalue.debug` and `arguments.posonlyargs` (3.8), `subscript with an unpacked index` (3.11),
  `typevar`'s, `paramspec`'s and `typevartuple`'s `default_value` (3.13), and a `listcomp`, `setcomp` or
  `generatorexp` of unpacked elements and a `dictcomp` of unpacked mappings (3.15).

Not checked: an `except` clause's types unparenthesized (3.14), which the tree does not record (`Parse` writes a
`tuple` either way, the dialect's tuple not recording whether it was parenthesized: a gap, reported to mbse-expressions).

`validate`'s rules, each the 0.3 rule where one stands, located at the statement:

- what a kind needs: a property (`an If needs a test`), a list that is not empty (`an Assign needs a target`, `a Match
  needs a case`), a block holding a statement other than a comment (`a For needs a statement in its body`, and in its
  `orelse` and `finalbody` where it has them), and what goes together (`a Raise with a cause needs an exc`, `an
  ImportFrom needs a module or a level`, `a Try needs a handler or a finalbody`, `a Try with an orelse needs a
  handler`); an `AugAssign`'s `op` a binary operator;
- names: a name a statement declares (a definition's `name`, an `except` clause's, `global` and `nonlocal`'s, an
  alias' `asname`) an identifier that is not a keyword; an alias' `name` and an `ImportFrom`'s `module` dotted names of
  them, `*` an `ImportFrom`'s alias' name;
- invalid syntax, as the user decided that a parse keeps it and validation reports it (2026-11-17): each
  `Programs.Framework.Error`, `invalid syntax '<its text>'`, as mbse-expressions words an `error` term's
  (`Terms.invalid_problems`) *(agent)*, located at the error (`body[2]: invalid syntax 'x = = 1'`); an `Error` an
  empty text, `invalid syntax ''`, where a newline was missing; an `error` or `missing` term as its dialect validates
  it, below (`body[0].value: invalid syntax '(1 + )'`, `body[0].target: missing identifier`). So a caller who needs a
  clean tree validates it. An `Error` may stand wherever a statement or a clause may, and holds statements in its
  `body`, each of which is checked as one *(agent)*;
- terms: each term a statement holds, as its dialect validates it (`Python3.DIALECT.validate`, which reads `Python
  Types` and `Python Patterns` too): a `matchor` of two patterns, a `set` of an element, a lambda's parameters without
  annotations, ... The names a term refers to are taken as bound *(agent)*: binding them is the program's, which
  `Definitions` resolves, not a term's.

Dropped, as the model now holds them: a property's type (`Identifier.spelling must be a str`), a child's category and
where a statement or a clause may stand (a `try`'s `handlers` hold only `except` clauses, a block no clause), which the
schemas check on write; `DottedName` and `Identifier` as nodes (a name is a string); and every
rule on terms, which mbse-expressions' dialects own (`ConcatenatedString`, `Set`, comprehensions, `Compare`, `BoolOp`,
`Lambda`, `JoinedStr` and `TemplateStr` prefixes, `MatchMapping`, `MatchClass`, `MatchOr`).
"""

from __future__ import annotations

import keyword
from collections.abc import Callable, Iterator
from typing import Any

from mbse.Expressions.Framework import Objects, Standards as ExpressionStandards, Terms
from mbse.Expressions.Python.Python3 import Domains, Expressions as PythonExpressions

from ..Framework.Model import WORKSPACE
from .Standards import DIALECTS, designation
from .Statements import LANGUAGE

__all__ = ["check", "validate", "FEATURES", "STATEMENT_FEATURES"]

Version = tuple[int, ...]


# --- Reading ---

def _kind(node: Any) -> str:
    """A statement's or a clause's kind: its schema's name, without its language's (`If`)."""
    return node.as_schema().name.rsplit(".", 1)[-1]


_BLOCK = ("body", "handlers", "orelse", "finalbody", "cases")
"""The properties that hold statements, clauses or errors, in source order: a module's, a statement's, a clause's and an
error's."""


def _children(node: Any) -> list[tuple[str, int, Any]]:
    """The statements, clauses and errors a module, a statement, a clause or an error holds, each its property, its
    index and its record, in source order."""
    held = Objects.properties(node)
    return [(name, index, Terms.kind_of(element)[1]) for name in _BLOCK if name in held
            for index, element in enumerate(held[name].values)]


def _module(store: Any, path: str, read: Callable[[Any], list[str]]) -> list[str]:
    """`read` of the module at `path`, within a transaction of its own, so called with none open on `store`, as the
    user decided that whether one is open is no flag on the store (mbse-basis CAP-315)."""
    with store.transaction():
        return read(store.singleton(WORKSPACE).files({"path": path}))  # LookupError, where it holds none


def _statements(module: Any) -> Iterator[tuple[str, Any, Any]]:
    """Every statement and clause of a module, each its path, itself and its parent, parents first, in source order."""
    stack = [(f"{prop}[{index}]", child, module) for prop, index, child in reversed(_children(module))]
    while stack:
        where, node, parent = stack.pop()
        yield where, node, parent
        stack += [(f"{where}.{prop}[{index}]", child, node) for prop, index, child in reversed(_children(node))]


def _properties(node: Any) -> Iterator[tuple[str, Any]]:
    """A statement's properties that are set, but its line and the statements it holds, each by its path from the
    statement (`.value`, `.targets[1]`) and what it holds: a list's elements each by its index."""
    for name, held in Objects.properties(node).items():
        if name == "line" or name in _BLOCK:
            continue
        if isinstance(held, Objects.Listed):
            yield from ((f".{name}[{i}]", element) for i, element in enumerate(held.values))
        else:
            yield f".{name}", held


def _a(noun: str) -> str:
    return f"{'an' if noun[0].lower() in 'aeiou' else 'a'} {noun}"


def _unique(problems: list[str]) -> list[str]:
    return list(dict.fromkeys(problems))


# --- Terms ---

def _nodes(value: Any) -> Iterator[tuple[Terms.Node, str | None]]:
    """Every term and helper within what a property holds, each as its `Terms.Node`, with its kind's schema's name for
    a term (None for a helper), parents first: a term, or a value object holding them (an `Arguments`, a `Keyword`, an
    `Alias`, a `WithItem`); none within a scalar."""
    if Terms.is_term(value):
        tag, record = Terms.kind_of(value)
        yield from _nested(Terms.node(tag, record), record.as_schema().name)
    elif Objects.is_object(value):
        yield from _nested(Terms.node(value.as_schema().name.rsplit(".", 1)[-1].lower(), value), None)


def _nested(node: Terms.Node, schema: str | None) -> Iterator[tuple[Terms.Node, str | None]]:
    yield node, schema
    for term in (*node.subterms.values(), *node.many):
        if term is not None:
            yield from _nodes(term)
    for helper in node.helpers.values():
        for each in helper if isinstance(helper, tuple) else (helper,):
            yield from _nested(each, None)


def _tag(term: Any) -> str:
    return Terms.kind_of(term)[0]


def _starred(term: Any) -> bool:
    return term is not None and _tag(term) == "starred"


def _unpacked_index(node: Terms.Node) -> bool:
    index = node.subterms["slice"]
    if _tag(index) == "tuple":
        tag, record = Terms.kind_of(index)
        return any(_starred(element) for element in Terms.node(tag, record).many)
    return _starred(index)


def _unpacked(node: Terms.Node) -> list[tuple[str, int]]:
    return [(f"{node.kind} of unpacked elements", 15)] if _starred(node.subterms["body"]) else []


def _default(node: Terms.Node) -> list[tuple[str, int]]:
    return [(f"{node.kind}.default_value", 13)] if node.subterms["default_value"] is not None else []


FEATURES: dict[str, Callable[[Terms.Node], list[tuple[str, int]]]] = {
    "binop": lambda node: [("binop.op '@'", 5)] if node.attributes.get("op") == "@" else [],
    "comprehension": lambda node: [("comprehension.is_async", 6)] if node.attributes.get("is_async") else [],
    "formattedvalue": lambda node: [("formattedvalue.debug", 8)] if node.attributes.get("debug") else [],
    "arguments": lambda node: [("arguments.posonlyargs", 8)] if node.helpers.get("posonlyargs") else [],
    "subscript": lambda node: [("subscript with an unpacked index", 11)] if _unpacked_index(node) else [],
    "typevar": _default, "paramspec": _default, "typevartuple": _default,
    "listcomp": _unpacked, "setcomp": _unpacked, "generatorexp": _unpacked,
    "dictcomp": lambda node: [("dictcomp of unpacked mappings", 15)] if node.subterms["body"] is None else [],
}
"""The features of a term or a helper that its properties' values make, by its kind (its tag, or its helper's): each
feature's name, and the minor version of Python 3 it arrived in *(agent: code until mbse-expressions records them)*."""


# --- Statements ---

def _dotted(term: Any) -> bool:
    """Whether a term is a dotted name: a name, or an attribute of one."""
    tag, record = Terms.kind_of(term)
    node = Terms.node(tag, record)
    return tag == "variable" or (tag == "attribute" and _dotted(node.subterms["value"]))


def _decorator(term: Any) -> bool:
    """Whether a decorator is one every Python 3 has: a dotted name, optionally called (PEP 614)."""
    tag, record = Terms.kind_of(term)
    return _dotted(Terms.node(tag, record).subterms["func"] if tag == "call" else term)


def _definition(kind: str, held: dict[str, Any]) -> list[tuple[str, int]]:
    found = [(f"{kind}.type_params", 12)] if "type_params" in held else []
    decorators = held.get("decorator_list")
    if decorators is not None and not all(_decorator(d) for d in decorators.values):
        found.append((f"{kind} with a decorator that is not a dotted name", 9))
    return found


def _lazy(kind: str, held: dict[str, Any]) -> list[tuple[str, int]]:
    return [(f"{kind}.is_lazy", 15)] if held.get("is_lazy") else []


STATEMENT_FEATURES: dict[str, Callable[[str, dict[str, Any]], list[tuple[str, int]]]] = {
    "Import": _lazy, "ImportFrom": _lazy,
    "AugAssign": lambda kind, held: [("AugAssign.op '@'", 5)] if held.get("op") == "@" else [],
    "FunctionDef": _definition, "AsyncFunctionDef": _definition, "ClassDef": _definition,
}
"""The features of a statement that its properties' values make, by its kind, given its kind and its properties that
are set: each feature's name, and the minor version of Python 3 it arrived in *(agent: code, as a standard tags a
kind, not a property)*."""


# --- Versions ---

def _version(standard: Any) -> Version:
    """A stored standard's version, from its revision: (3, 12)."""
    return tuple(int(part) for part in str(ExpressionStandards.properties(standard)["revision"][1]).split("."))


class _Availability:
    """What the store's standards say: the target version, and each kind's schema's versions, by its schema's name."""

    def __init__(self, store: Any, version: Version | str):
        language = store.singleton(LANGUAGE)
        tag = designation(version[1]) if isinstance(version, tuple) and version[:1] == (3,) else str(version)
        target = ExpressionStandards.find(language, tag)
        if target is None:
            raise LookupError(f"{LANGUAGE} covers no version {version!r}: run Standards.prepare on the store")
        self.target, self.name = _version(target), str(ExpressionStandards.designation_of(target))
        self.versions: dict[str, set[Version]] = {}
        for dialect in DIALECTS:
            standards = ExpressionStandards.standards(store.singleton(dialect))
            if not standards:
                raise LookupError(f"{dialect} covers no version: run Standards.prepare on the store")
            for standard in standards.values():
                for kind in ExpressionStandards.kinds(standard):
                    self.versions.setdefault(kind.name, set()).add(_version(standard))

    def kind(self, schema: str, what: str) -> list[str]:
        """The problem of a kind, by its schema's name, that the target lacks: none where it has it, or where no
        standard lists it."""
        versions = self.versions.get(schema)
        if not versions or self.target in versions:
            return []
        return [f"{what} needs Python {'.'.join(map(str, min(versions)))}"]

    def features(self, found: list[tuple[str, int]]) -> list[str]:
        return [f"{feature} needs Python 3.{minor}" for feature, minor in found if self.target < (3, minor)]


def _check(available: _Availability, module: Any) -> list[str]:
    problems: list[str] = []
    for where, node, _ in _statements(module):
        kind = _kind(node)
        own = available.kind(node.as_schema().name, kind)
        own += available.features(STATEMENT_FEATURES.get(kind, lambda *_: [])(kind, Objects.properties(node)))
        problems += [f"{where}: {problem}" for problem in own]
        for at, held in _properties(node):
            for term, schema in _nodes(held):
                found = [] if schema is None else available.kind(schema, term.kind)
                found += available.features(FEATURES.get(term.kind, lambda _: [])(term))
                problems += [f"{where}{at}: {problem}" for problem in found]
    return _unique(problems)


def check(store: Any, path: str, version: Version | str) -> list[str]:
    """The problems of the constructs the module at `path` uses that `version` lacks, in source order, each once and
    located by its path: `body[2]: TypeAlias needs Python 3.12`. `version` is `(3, minor)` or a name the language
    covers a version by (`"Python 3.12"`). Raises LookupError where the workspace holds no file at `path`, or the
    language covers no such version (the store not prepared, `Standards.prepare`, among them)."""
    return _module(store, path, lambda module: check_file(store, module, version))


def check_file(store: Any, module: Any, version: Version | str) -> list[str]:
    """`check` of a module's visitor, a `Programs.Python3.Module` of `store`, read within the caller's transaction."""
    return _check(_Availability(store, version), module)


# --- Validity ---

_BLOCKS = {"If": ("body", "orelse"), "While": ("body", "orelse"), "For": ("body", "orelse"),
           "AsyncFor": ("body", "orelse"), "Try": ("body", "orelse", "finalbody"),
           "TryStar": ("body", "orelse", "finalbody"), "ExceptHandler": ("body",), "With": ("body",),
           "AsyncWith": ("body",), "MatchCase": ("body",), "FunctionDef": ("body",), "AsyncFunctionDef": ("body",),
           "ClassDef": ("body",), "Module": ("body",)}
"""The blocks of statements each kind holds, the first of which needs a statement other than a comment, and the others,
where they hold any, too (a module's may be empty)."""

_NEEDS = {"Expr": ("value",), "Assign": ("value",), "AugAssign": ("target", "op", "value"),
          "AnnAssign": ("target", "annotation"), "Assert": ("test",), "TypeAlias": ("name", "value"), "If": ("test",),
          "While": ("test",), "For": ("target", "iter"), "AsyncFor": ("target", "iter"), "Match": ("subject",),
          "MatchCase": ("pattern",), "FunctionDef": ("name", "args"), "AsyncFunctionDef": ("name", "args"),
          "ClassDef": ("name",)}
"""The properties each kind needs set."""

_LISTS = {"Assign": ("targets", "a target"), "Delete": ("targets", "a target"), "Import": ("names", "a name"),
          "ImportFrom": ("names", "a name"), "Global": ("names", "a name"), "Nonlocal": ("names", "a name"),
          "With": ("items", "an item"), "AsyncWith": ("items", "an item")}
"""The list each kind needs not empty, and what it needs, by name."""


def _identifier(name: Any) -> list[str]:
    if not name.isidentifier():
        return [f"{name!r} is not an identifier"]
    return [f"{name!r} is a keyword"] if keyword.iskeyword(name) else []


def _dotted_name(name: Any) -> list[str]:
    return [problem for part in name.split(".") for problem in _identifier(part)]


def _names(kind: str, held: dict[str, Any]) -> list[tuple[str, str]]:
    """The problems of the names a statement declares, each by the path of the property that holds it."""
    found: list[tuple[str, str]] = []
    if kind in ("FunctionDef", "AsyncFunctionDef", "ClassDef", "ExceptHandler") and "name" in held:
        found += [(".name", p) for p in _identifier(held["name"])]
    if kind in ("Global", "Nonlocal") and "names" in held:
        found += [(f".names[{i}]", p) for i, name in enumerate(held["names"].values) for p in _identifier(name)]
    if kind in ("Import", "ImportFrom") and "names" in held:
        for i, alias in enumerate(held["names"].values):
            parts = Objects.properties(alias)
            name, asname = parts.get("name"), parts.get("asname")
            if name is None:
                found.append((f".names[{i}]", "an alias needs a name"))
            elif not (kind == "ImportFrom" and name == "*"):
                found += [(f".names[{i}]", p) for p in _dotted_name(name)]
            found += [(f".names[{i}]", p) for p in ([] if asname is None else _identifier(asname))]
    if kind == "ImportFrom" and "module" in held:
        found += [(".module", p) for p in _dotted_name(held["module"])]
    return found


def _rules(kind: str, held: dict[str, Any], children: dict[str, list[Any]]) -> list[str]:
    """A statement's own problems, given its kind, its properties that are set and its children by property."""
    problems = [f"{_a(kind)} needs {_a(name)}" for name in _NEEDS.get(kind, ()) if name not in held]
    if kind in _LISTS and _LISTS[kind][0] not in held:
        problems.append(f"{_a(kind)} needs {_LISTS[kind][1]}")
    if kind == "AugAssign" and "op" in held and held["op"] not in Domains.BINOP:
        problems.append(f"AugAssign.op cannot be {held['op']!r}")
    if kind == "Raise" and "cause" in held and "exc" not in held:
        problems.append("a Raise with a cause needs an exc")
    if kind == "ImportFrom" and "module" not in held and not held.get("level"):
        problems.append("an ImportFrom needs a module or a level")
    if kind == "Match" and not children.get("cases"):
        problems.append("a Match needs a case")
    for i, block in enumerate(_BLOCKS.get(kind, ())):
        statements = children.get(block, [])
        if (i == 0 or statements) and all(_kind(s) == "Comment" for s in statements):
            problems.append(f"{_a(kind)} needs a statement in its {block}")
    if kind in ("Try", "TryStar"):
        if not children.get("handlers") and not children.get("finalbody"):
            problems.append(f"{_a(kind)} needs a handler or a finalbody")
        elif children.get("orelse") and not children.get("handlers"):
            problems.append(f"{_a(kind)} with an orelse needs a handler")
    return problems


def _terms(held: Any) -> Iterator[Any]:
    """The terms a property holds: itself, or a list's, or a value object's, in order."""
    if isinstance(held, Objects.Listed):
        for element in held.values:
            yield from _terms(element)
    elif Terms.is_term(held):
        yield held
    elif Objects.is_object(held):
        for value in Objects.properties(held).values():
            yield from _terms(value)


def _bound(term: Any) -> set[str]:
    """The names a term refers to or binds, taken as bound."""
    return {name for t in Terms.walk(term) if isinstance(name := Terms.name_of(t), str)}


def _validate(module: Any) -> list[str]:
    problems: list[str] = []
    for where, node, _ in _statements(module):
        kind, held = _kind(node), Objects.properties(node)
        children: dict[str, list[Any]] = {}
        for prop, _, child in _children(node):
            children.setdefault(prop, []).append(child)
        if kind == "Error":
            problems += [f"{where}: {p}" for p in Terms.invalid_problems("error", held)]
        problems += [f"{where}: {p}" for p in _rules(kind, held, children)]
        problems += [f"{where}{at}: {p}" for at, p in _names(kind, held)]
        for at, value in _properties(node):
            for term in _terms(value):
                problems += [f"{where}{at}: {p}" for p in PythonExpressions.DIALECT.validate(term, _bound(term))]
    return problems


def validate(store: Any, path: str) -> list[str]:
    """The problems of the module at `path` as a tree, in source order, each located by its path: its kinds' own rules,
    and its terms' problems as their dialects validate them. Raises LookupError where the workspace holds no file at
    `path`."""
    return _module(store, path, validate_file)


def validate_file(module: Any) -> list[str]:
    """`validate` of a module's visitor, read within the caller's transaction."""
    return _validate(module)
