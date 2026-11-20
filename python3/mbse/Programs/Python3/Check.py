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

What a property's value makes available within a kind is data too, grammar clauses (mbse-basis [grammar clauses by
version](mbse:mbse-basis/proposals/GRAMMAR-CLAUSES.md)), read as mbse-expressions reads them
(`Expressions.Framework.Standards`): those a statement or a clause takes of the language's own (`Standards`:
`Import.is_lazy`, `AugAssign.op '@'`, `FunctionDef.type_params`, PEP 614's decorator, ...), located at the property that
holds what it says (`body[0].is_lazy`), or, where that property holds a list and the grammar clause a term of one of
its kinds, at each element that is one (`body[2].decorator_list[0]`); and those a term or a helper takes of its
dialect's (`Python3`'s `binop.op '@'`, `Python Types`' `typevar.default_value`, ...), located as its kind's problem
is. A grammar clause the target does not allow is `<its name> needs <the nearest version that allows it>`, the first
after the target, else the last before it *(agent)*: `body[2].decorator_list[0]: FunctionDef with a decorator holding
any term needs Python 3.9`. The target's own entries decide, else its neighbours' flagged `before` and `after` (a
version the data covers but does not represent in a grammar clause's entries, as a store may add Python 3.16), else a
grammar clause is allowed (`Framework.Standards.allows`); a dialect that does not cover the target has no say.

The grammar clauses a syntax node or a term takes at one place are alternatives of one production: the place is fine
in a version that allows one of them, and otherwise each is a problem *(agent)*. So PEP 614, which removed a
restriction: a dotted name, optionally called, takes both of a definition's decorator grammar clauses, Python 3.0 to
3.8 allowing the one and 3.9 on the other, and is fine in each; any other term takes the second alone.

What no grammar clause can say stays code, each with its reason: nothing, of Python 3's. Not checked: an `except`
clause's types unparenthesized (3.14), which the tree does not record (`Parse` writes a `tuple` either way, the
dialect's tuple not recording whether it was parenthesized: a gap, reported to mbse-expressions).

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

__all__ = ["check", "check_file", "validate", "validate_file"]

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

def _records(value: Any) -> Iterator[tuple[str, Any]]:
    """Every term and helper within what a property holds, and every value object holding them (an `Arguments`, a
    `Keyword`, an `Alias`, a `WithItem`), each its tag (a helper's, its schema's name's last part in lower case) and its
    record, parents first, in order; none within a scalar."""
    if isinstance(value, Objects.Listed):
        for element in value.values:
            yield from _records(element)
        return
    if Terms.is_term(value):
        tag, record = Terms.kind_of(value)
    elif Objects.is_object(value):
        tag, record = value.as_schema().name.rsplit(".", 1)[-1].lower(), value
    else:
        return  # a scalar
    yield tag, record
    for held in Objects.properties(record).values():
        yield from _records(held)


# --- Versions ---

def _version(standard: Any) -> Version:
    """A stored standard's version, from its revision: (3, 12)."""
    return tuple(int(part) for part in str(ExpressionStandards.properties(standard)["revision"][1]).split("."))


def _holds(dialect: Any, said: dict[str, Any], element: Any) -> bool:
    """Whether a list's element is what a grammar clause, as `grammar_clause` says it, holds: a term of one of its
    kinds that takes each of its nested grammar clauses of that kind."""
    record = Terms.kind_of(element)[1]
    schema = record.as_schema()
    taken = {ExpressionStandards.grammar_clause_name(c) for c in ExpressionStandards.takes(dialect, record)}
    return any(kind is schema for kind in said["kinds"]) and all(
        ExpressionStandards.grammar_clause_name(nested) in taken for nested in said.get("nested", ())
        if ExpressionStandards.grammar_clause(nested)["kind"] is schema)


def _places(dialect: Any, record: Any, clause: Any) -> list[str]:
    """Where within a syntax node or a term a grammar clause it takes holds what it says: its property (`.op`), or,
    where that holds a list and the grammar clause a term of one of its kinds, each element that is one
    (`.decorator_list[1]`)."""
    said = ExpressionStandards.grammar_clause(clause)
    held = Objects.properties(record).get(said["property"])
    if "kinds" not in said or not isinstance(held, Objects.Listed):
        return [f".{said['property']}"]
    return [f".{said['property']}[{i}]" for i, element in enumerate(held.values) if _holds(dialect, said, element)]


class _Availability:
    """What the store's standards say: the target version, each kind's schema's versions, by its schema's name, and
    each dialect's grammar clauses and its standard of the target's name."""

    def __init__(self, store: Any, version: Version | str):
        language = store.singleton(LANGUAGE)
        tag = designation(version[1]) if isinstance(version, tuple) and version[:1] == (3,) else str(version)
        target = ExpressionStandards.find(language, tag)
        if target is None:
            raise LookupError(f"{LANGUAGE} covers no version {version!r}: run Standards.prepare on the store")
        self.target, self.name = _version(target), str(ExpressionStandards.designation_of(target))
        self.versions: dict[str, set[Version]] = {}
        self.grammar: dict[str, tuple[Any, Any, set[str]]] = {}
        for dialect in DIALECTS:
            singleton = store.singleton(dialect)
            standards = ExpressionStandards.standards(singleton)
            if not standards:
                raise LookupError(f"{dialect} covers no version: run Standards.prepare on the store")
            for standard in standards.values():
                for kind in ExpressionStandards.kinds(standard):
                    self.versions.setdefault(kind.name, set()).add(_version(standard))
            kinds = {ExpressionStandards.grammar_clause(clause)["kind"].name
                     for clause in ExpressionStandards.grammar_clauses(singleton).values()}
            self.grammar[dialect] = (singleton, ExpressionStandards.find(singleton, self.name), kinds)

    def kind(self, schema: str, what: str) -> list[str]:
        """The problem of a kind, by its schema's name, that the target lacks: none where it has it, or where no
        standard lists it."""
        versions = self.versions.get(schema)
        if not versions or self.target in versions:
            return []
        return [f"{what} needs Python {'.'.join(map(str, min(versions)))}"]

    def nearest(self, dialect: Any, clause: Any) -> str:
        """The version nearest the target that allows a grammar clause: the first after it, else the last before it."""
        allowing = sorted((_version(standard), name) for name, standard in ExpressionStandards.standards(dialect).items()
                          if ExpressionStandards.allows(standard, clause))
        later = [name for at, name in allowing if at > self.target]
        return later[0] if later else allowing[-1][1]

    def clauses(self, dialect: str, record: Any) -> list[tuple[str, str]]:
        """The problems of the grammar clauses of `dialect` that a syntax node or a term takes and the target lacks,
        each with its place within it (`_places`): those taken at one place are alternatives, the place fine where
        the target allows one of them."""
        singleton, target, kinds = self.grammar[dialect]
        if record.as_schema().name not in kinds:
            return []
        places: dict[str, list[Any]] = {}
        for clause in ExpressionStandards.takes(singleton, record):
            for place in _places(singleton, record, clause):
                places.setdefault(place, []).append(clause)
        return [(place, f"{ExpressionStandards.grammar_clause_name(clause)} needs {self.nearest(singleton, clause)}")
                for place, taken in places.items()
                if target is not None and not any(ExpressionStandards.allows(target, each) for each in taken)
                for clause in taken]


def _check(available: _Availability, module: Any) -> list[str]:
    problems: list[str] = []
    for where, node, _ in _statements(module):
        problems += [f"{where}: {problem}" for problem in available.kind(node.as_schema().name, _kind(node))]
        problems += [f"{where}{place}: {problem}" for place, problem in available.clauses(LANGUAGE, node)]
        for at, held in _properties(node):
            for tag, record in _records(held):
                found = available.kind(record.as_schema().name, tag)
                found += [problem for dialect in DIALECTS[1:] for _, problem in available.clauses(dialect, record)]
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
