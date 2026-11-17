"""Definitions: the names a Python 3 module binds, in the scopes Python gives them, read from the store.

As the user decided for the port ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../docs/proposals/port/README.md#decided),
6): entities, name resolution and the program stay code over the stored tree, computed on demand and never stored, and
a use of a name is anchored on its statement and the term's path, since a term is a value.

- `define(store, path)`: the `Program` of the module the workspace holds at `path`, read within the transaction open
  on `store`, or, where none is, within one of its own; LookupError where the workspace holds no file at `path`. What
  it gives back is plain data, holding no visitor, so that it outlives the transaction (mbse-basis
  [CAP-315: every read within a transaction or through a follow](mbse:mbse-basis/docs/capabilities/CAP-315.md#decided)).
- `referents(program, at)`: the entities the name at `at` (an `Anchor`, or its text) refers to, looked up from where
  it is.
- `Anchor`: a place in the module. Its `node` is the `References.OfObject` of its statement or clause (of the module,
  for the module itself), its `statement` that node's path below the module, rendered, its `property` the
  statement's property that holds the place (none, for the statement itself), and its `term` the place's path within
  that property's value: the names of the properties and the indices of the containers stepped through, terms,
  helpers (a call's `keywords`, a function's `args`) and value objects (an import's aliases) alike. `str(anchor)` is
  its text, which identifies it within its module: `body[1].body[0]:value.args[0]` is the first argument of the call
  that is the value of the first statement of the body of the module's second statement; `body[0]` the statement
  itself; `<module>` the module.
- `Program`, a `Framework.Definitions.Program` whose qualified names join with `.` (`Shape.area`), keyed by anchors'
  text: `entity_of(at)`, `scope_of(at)` and `lookup(name, at)` each take an `Anchor` or its text; `anchor(text)` gives
  the anchor of a place it located; `named(spelling)` gives, in source order, every place a name spelled so is
  written, bound or used; `path` is the module's path.

Its entities have these kinds:

- 'class' and 'function', each with its own scope;
- 'variable': a name bound by assignment, `for`, `with ... as`, `except ... as`, `del`, a pattern's capture or an
  assignment expression;
- 'parameter' (of a function or lambda), 'type parameter' and 'type alias';
- 'import': a name an import binds (`import a.b` binds `a`).

There is one entity per name per scope: every place that binds the name is one of its `declarations`, in source
order, and the first is its `definition`. The first binding visited decides its kind: the module's names are visited
first, then each function's and class's, as Python's symbol tables are built.

Scopes are those of Python's execution model (§4.2): 'module', 'class', 'function', 'lambda', 'comprehension' and
'type parameters' (the annotation scope of a generic function, class or type alias), each `node` the anchor of what
opens it (the module, a statement, a lambda's or a comprehension's term). A name bound anywhere in a scope is local to
it, unless `global` declares it the module's or `nonlocal` the nearest enclosing function's. Names are looked up
outwards through enclosing functions to the module, past class bodies: every scope's parent is the nearest enclosing
scope that is not a class. Decorators, defaults, a class's bases and the first iterable of a comprehension are in the
enclosing scope, and an assignment expression in a comprehension binds in the scope around it.

Every statement, clause and term is located in the scope it is evaluated in, as is every place that binds a name.
What it does not do: resolve attributes (`a.b`, whose `b` depends on `a`'s value) or the members of imported modules,
follow `from module import *`, see names that `exec` or `globals()` bind, or treat builtins as entities.

Decided by the agent where the port left it open, each *(agent)*:

- **`Framework.Definitions` is kept and adapted**, not rewritten: `Entity` and `Scope` are independent of how a node
  is held and move as they were; `Program` gained `key(node)`, a node's identity by default, which this module's
  `Program` overrides with an anchor's text, so that an anchor made anew finds what one made earlier recorded. Ccpp's,
  TypeScript's and Verilog's definitions, set aside for the port, keep keying by identity.
- **An anchor's text** is the statement's path, its parents' properties and indices from the module down
  (`body[1].orelse[0]`), then, for a place within it, `:`, the property, and the term's path, each property `.name` and
  each index `[i]` (`body[0]:targets[0].elts[1]`); the module is `<module>`. A term's kind is not a step: the term is
  the value its property holds, nor is the branch any other union holds (a target's, an f-string's part). Anchors are
  equal, and hash, as their text, and an anchor equals its text, so that a test or a reader names a place by it.
- **Source order** is each anchor's `order`: the statement's place (a statement before its children, its own
  properties before its children, a `try`'s `body`, `handlers`, `orelse` and `finalbody`, and so on), then the
  properties' order in each schema, which is `ast`'s, but a lambda's `args` before its `body`, and a dict
  comprehension's `key` before its value (`body`), as Python's source has them.
- **Where a name is bound is where it is written**: a function's, a class's and an `except` clause's name is its
  statement's `name` (`body[3]:name`), a type alias' its `name` term, an import's the alias (`body[0]:names[1]`), a
  parameter its `arg` (`body[3]:args.args[0]`), a type parameter its term (`body[3]:type_params[0]`), a pattern's
  capture its `name` (or a mapping pattern's `rest`) within the pattern (`body[0].cases[0]:pattern.patterns[0].name`),
  and a name in a target its `variable` term. A `def`'s, a `class`'s and a `type`'s own statement is declared too, so
  that `entity_of(statement)` gives what it defines. A name of `global` or `nonlocal` is declared, not a
  declaration, as it binds nothing.
- **The API is `define(store, path)`**, by the module's path in the workspace, as `Print.print_module` takes it, and
  joins an open transaction as it does: mbse-schemas 0.27 has no public query for whether one is open, so `define`
  reads the workspace and, where the store refuses the read as outside any transaction (ValueError), reads again
  within one of its own. A program is one module's, as Python's scopes are.
- **An anchor's reference is made on demand**: `References.of` costs about a millisecond a statement, a third of
  `define`'s time on the conformance source, so an anchor holds its statement's path, made from the module's reference
  and the property and index of each `HasParent` entry down to it, and makes the `References.OfObject` from it, through
  `Plain.FromPlain`, when `node` is first read (P3DEF-07 checks it against `References.of` for every statement).
- **What a target binds is walked here**: mbse-expressions' `Python3.target_names` and `Patterns.bound_names` give the
  names a target or a pattern binds as a set, not where each is written, so the walk that anchors them is this
  module's, its kinds those `target_names` reads (the tests check that the two agree).
"""

from __future__ import annotations

from collections import deque
from typing import Any

from mbse.Expressions.Framework import Objects, Terms
from mbse.Expressions.Python.Python3 import Expressions as P
from mbse.Schemas.Framework import Plain, References
from mbse.Schemas.Framework import Schemas as SchemaKinds

from ..Framework import Definitions
from ..Framework.Definitions import Entity, Scope
from ..Framework.Model import WORKSPACE

__all__ = ["Anchor", "Program", "define", "referents"]

_MODULE = "<module>"
_CHILDREN = {"body": 0, "handlers": 1, "cases": 1, "orelse": 2, "finalbody": 3}
"""Where each property holding statements comes in source: a `try`'s handlers, and a `match`'s cases, after its body."""
_SOURCE = {"Expressions.Python.Python3.Lambda": ("args", "body"),
           "Expressions.Python.Python3.DictComp": ("key", "body", "generators")}
"""The kinds whose properties' order is not their source's: a lambda's parameters come before its body, and a dict
comprehension's key before its value."""
_TARGETS = (P.TUPLE, P.LIST, P.STARRED, P.PARENTHESIZED)
"""The targets that hold targets, as `Python3.target_names` reads them."""
_PARAMETERS = ("posonlyargs", "args", "vararg", "kwonlyargs", "kwarg")
_RANKS: dict[str, dict[str, int]] = {}
"""Each schema's properties' places in source order, by the schema's name: a kind's properties are the same in every
store."""


class _Place:
    """Where a statement, a clause or the module is, as its reference is made of: the module's path, written by
    `References.of`, or its parent's place and the property and index there that hold it. Its reference is made on
    demand, a value that outlives the transaction."""

    __slots__ = ("store", "parent", "edge", "plain", "made")

    def __init__(self, store: Any, parent: _Place | None = None, edge: tuple[str, int] | None = None,
                 plain: Any = None):
        self.store, self.parent, self.edge, self.plain, self.made = store, parent, edge, plain, None

    def path(self) -> Any:
        """Its path as `Plain.ToPlain` writes a `Paths.OfRoot`: its parent's, then the entry that holds it."""
        if self.plain is None:
            parent = self.parent
            assert parent is not None and self.edge is not None
            entry = {"i": "body" if parent.parent is None else "children", "o": "parent",
                     "properties": {"property": self.edge[0], "index": self.edge[1]}, "next": {"target": {}}}
            self.plain = _extend(parent.path(), {"entry": entry})
        return self.plain

    def reference(self) -> Any:
        """Its `References.OfObject`."""
        if self.made is None:
            self.made = Plain.FromPlain(self.store)(self.store.registered("References.OfObject"), {"path": self.path()})
        return self.made


def _extend(path: Any, step: Any) -> Any:
    """A path, written as `Plain.ToPlain` writes it, with `step` in place of its target."""
    if "target" in path:
        return step
    if "entry" in path:
        return {"entry": {**path["entry"], "next": _extend(path["entry"]["next"], step)}}
    return {**path, "next": _extend(path["next"], step)}


class Anchor:
    """A place in a module: its statement's or clause's reference (`node`, a `References.OfObject`, made on demand),
    that statement's path, rendered (`statement`), the statement's property holding the place (`property`, None for
    the statement itself) and the place's path within that property's value (`term`, property names and container
    indices). `order` sorts anchors in source order. Equal, and hashed, as its text, and equal to its text."""

    __slots__ = ("_place", "statement", "property", "term", "order", "_text")

    def __init__(self, place: _Place, statement: str, property: str | None = None, term: tuple[str | int, ...] = (),
                 order: tuple[tuple[int, ...], ...] = ()):
        self._place, self.statement, self.property, self.term, self.order = place, statement, property, term, order
        if property is None:
            self._text = statement or _MODULE
        else:
            self._text = f"{statement}:{property}" + "".join(
                f"[{step}]" if isinstance(step, int) else f".{step}" for step in term)

    @property
    def node(self) -> Any:
        """The `References.OfObject` of the statement or clause the place is in, or of the module."""
        return self._place.reference()

    def child(self, property: str, index: int) -> Anchor:
        """The anchor of the statement or clause at `index` of this one's `property`."""
        statement = f"{self.statement}.{property}[{index}]" if self.statement else f"{property}[{index}]"
        return Anchor(_Place(self._place.store, self._place, (property, index)), statement,
                      order=(*self.order, (_CHILDREN[property], index)))

    def at(self, property: str, rank: int) -> Anchor:
        """The anchor of this statement's `property`, the `rank`th of its properties in source order."""
        return Anchor(self._place, self.statement, property, (), (*self.order, (-1, rank)))

    def step(self, step: str | int, rank: int) -> Anchor:
        """The anchor of a place within this one: a property, the `rank`th in source order, or a container's index."""
        return Anchor(self._place, self.statement, self.property, (*self.term, step),
                      (*self.order[:-1], (*self.order[-1], rank)))

    def __str__(self) -> str:
        return self._text

    def __repr__(self) -> str:
        return f"Anchor({self._text!r})"

    def __eq__(self, other: object) -> bool:
        """Equal to an anchor with its text, or to its text."""
        return str(other) == self._text if isinstance(other, (Anchor, str)) else NotImplemented

    def __hash__(self) -> int:
        return hash(self._text)


class Program(Definitions.Program):
    """What a module declares: `Framework.Definitions.Program`, keyed by anchors' text, with every place a name is
    written."""

    def __init__(self, path: str, module: Anchor):
        super().__init__(Scope("module", None, None, module, separator="."))
        self.path = path
        self._names: dict[str, tuple[Anchor, str]] = {}
        self._anchors: dict[str, Anchor] = {}

    def key(self, node: Any) -> Any:
        """An anchor's text, or the text given for one."""
        return str(node)

    def located(self, node: Any, scope: Scope) -> None:
        """Records that the place `node`, an anchor, is in `scope`."""
        self._anchors.setdefault(str(node), node)
        super().located(node, scope)

    def anchor(self, text: Any) -> Anchor | None:
        """The anchor of a place the program located, given its text; None where it located none."""
        return self._anchors.get(str(text))

    def written(self, at: Anchor, name: str) -> None:
        """Records that `name` is written at `at`."""
        self._names[str(at)] = (at, name)

    def name_at(self, at: Any) -> str | None:
        """The name written at `at`; None where none is."""
        found = self._names.get(str(at))
        return None if found is None else found[1]

    def named(self, spelling: str) -> list[Anchor]:
        """Every place a name spelled `spelling` is written, bound or used, in source order."""
        return sorted((at for at, name in self._names.values() if name == spelling), key=lambda at: at.order)


# --- Reading ---

def _rank(record: Any, name: str) -> int:
    """Where a property of a statement, a term or a helper comes in source, among its schema's."""
    schema = record.as_schema()
    ranks = _RANKS.get(schema.name)
    if ranks is None:
        names = list(schema.properties)
        for first in reversed(_SOURCE.get(schema.name, ())):
            names.remove(first)
            names.insert(0, first)
        ranks = _RANKS[schema.name] = {prop: i for i, prop in enumerate(names)}
    return ranks[name]


def _kind(value: Any) -> tuple[str, Any] | None:
    """A term's kind and record, or the branch any other union holds (a target's, an f-string's part) and its record;
    None for any other value, a helper."""
    if Terms.is_term(value):
        return Terms.kind_of(value)
    if isinstance(value.as_schema(), SchemaKinds.OfUnion.Data):
        ((tag, record),) = Objects.properties(value).items()
        return tag, record
    return None


def _many(held: Any) -> tuple[Any, ...]:
    """A container's elements; none where it is absent."""
    return () if held is None else held.values


# --- Defining ---

class _Definer:
    """Declares what a module binds. Function and class bodies are visited once the scope around them is complete,
    so that `nonlocal` finds a binding that comes later in the enclosing function."""

    def __init__(self, program: Program):
        self.program = program
        self.bodies: deque[tuple[Any, str, Scope, Anchor]] = deque()

    # Scopes and bindings

    @staticmethod
    def enclosing(scope: Scope) -> Scope:
        """The scope where a scope opened in `scope` looks names up next: `scope` itself, past class bodies."""
        while scope.kind == "class":
            scope = scope.parent  # type: ignore[assignment]
        return scope

    def entity(self, scope: Scope, name: str, kind: str) -> Entity:
        """The entity `name` names in `scope`, which a global or nonlocal declaration may have brought in; a new one
        of `kind` if there is none."""
        found = scope.names.get(name)
        if found:
            return found[0]
        entity = self.program.add(Entity(kind, name, scope))
        scope.declare(entity)
        return entity

    def bind(self, scope: Scope, name: str, at: Anchor, kind: str) -> Entity:
        """Binds `name` in `scope`, written at `at`."""
        entity = self.entity(scope, name, kind)
        entity.declarations.append(at)
        self.program.declares(at, entity)
        self.program.located(at, scope)
        self.program.written(at, name)
        return entity

    def nonlocal_scope(self, scope: Scope, name: str) -> Scope | None:
        """The nearest enclosing function scope where `name` is bound, for `nonlocal name` in `scope`."""
        outer = scope.parent
        while outer is not None and outer.parent is not None:
            if outer.kind == "function" and name in outer.names:  # a lambda's body holds no `nonlocal`
                return outer
            outer = outer.parent
        return None

    # Terms

    def visit(self, value: Any, scope: Scope, at: Anchor) -> None:
        """A value a property holds, evaluated in `scope`: a term, a helper, a container of them, or a scalar."""
        if isinstance(value, Objects.Listed):
            for i, element in enumerate(value.values):
                self.visit(element, scope, at.step(i, i))
            return
        if not hasattr(value, "as_schema"):
            return  # a scalar: a name a term holds is its own, an attribute's or a keyword's
        kind = _kind(value)
        if kind is None:
            self.fields(value, scope, at)  # a helper
            return
        tag, record = kind
        self.program.located(at, scope)
        handler = self.TERMS.get(tag)
        if handler is None:
            self.fields(record, scope, at)
        else:
            handler(self, record, Objects.properties(record), scope, at)

    def fields(self, record: Any, scope: Scope, at: Anchor) -> None:
        """A term's or a helper's properties, each evaluated in `scope`."""
        for name, value in Objects.properties(record).items():
            self.visit(value, scope, at.step(name, _rank(record, name)))

    def target(self, value: Any, scope: Scope, at: Anchor) -> None:
        """An assignment target: names bind in `scope`, and other expressions are evaluated there."""
        tag, record = _kind(value)  # type: ignore[misc]
        self.program.located(at, scope)
        if tag == P.NAME:
            self.bind(scope, Objects.properties(record)["name"], at, "variable")
        elif tag in _TARGETS:
            for name, held in Objects.properties(record).items():
                inner = at.step(name, _rank(record, name))
                if isinstance(held, Objects.Listed):
                    for i, element in enumerate(held.values):
                        self.target(element, scope, inner.step(i, i))
                else:
                    self.target(held, scope, inner)
        else:
            self.visit(value, scope, at)

    def name(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.program.written(at, props["name"])

    def named_expr(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.visit(props["value"], scope, at.step("value", _rank(record, "value")))
        outer = scope
        while outer.kind == "comprehension":
            outer = outer.parent  # type: ignore[assignment]  # it binds in the scope around the comprehensions
        target = at.step("target", _rank(record, "target"))
        self.program.located(target, scope)
        self.target(props["target"], outer, target)

    def lambda_(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        inner = Scope("lambda", None, self.enclosing(scope), at)
        if "args" in props:
            self.arguments(props["args"], at.step("args", _rank(record, "args")), scope, scope, inner)
        self.visit(props["body"], inner, at.step("body", _rank(record, "body")))

    def comprehension(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        inner = Scope("comprehension", None, self.enclosing(scope), at)
        generators = at.step("generators", _rank(record, "generators"))
        for i, generator in enumerate(_many(props.get("generators"))):
            each = generators.step(i, i)
            self.program.located(each, inner)
            clause = Objects.properties(generator)
            self.visit(clause["iter"], scope if i == 0 else inner, each.step("iter", _rank(generator, "iter")))
            self.target(clause["target"], inner, each.step("target", _rank(generator, "target")))
            self.visit(clause.get("ifs"), inner, each.step("ifs", _rank(generator, "ifs")))
        for name in ("key", "body"):
            if name in props:
                self.visit(props[name], inner, at.step(name, _rank(record, name)))

    def capture(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """A pattern that captures: an `as` pattern's name, a star pattern's, a mapping pattern's rest."""
        for name, value in props.items():
            inner = at.step(name, _rank(record, name))
            if name in ("name", "rest"):
                self.bind(scope, value, inner, "variable")
            else:
                self.visit(value, scope, inner)

    TERMS: dict[str, Any] = {
        P.NAME: name, P.NAMEDEXPR: named_expr, P.LAMBDA: lambda_, P.LISTCOMP: comprehension,
        P.SETCOMP: comprehension, P.GENERATOREXP: comprehension, P.DICTCOMP: comprehension,
        "matchas": capture, "matchstar": capture, "matchmapping": capture,
    }

    def arguments(self, arguments: Any, at: Anchor, scope: Scope, annotations: Scope, inner: Scope) -> None:
        """Parameters bind in `inner`; their defaults are evaluated in `scope`, their annotations in
        `annotations`."""
        self.program.located(at, inner)
        props = Objects.properties(arguments)
        for name in _PARAMETERS:
            if name not in props:
                continue
            held, where = props[name], at.step(name, _rank(arguments, name))
            many = isinstance(held, Objects.Listed)
            for i, arg in enumerate(held.values if many else (held,)):
                each = where.step(i, i) if many else where
                self.program.located(each, inner)
                fields = Objects.properties(arg)
                if "annotation" in fields:
                    self.visit(fields["annotation"], annotations, each.step("annotation", _rank(arg, "annotation")))
                if "default_value" in fields:
                    self.visit(fields["default_value"], scope, each.step("default_value", _rank(arg, "default_value")))
                self.bind(inner, fields["arg"], each, "parameter")

    # Statements

    def children(self, node: Any, adjacency: str, scope: Scope, at: Anchor) -> None:
        """A statement's statements and clauses (a module's, by its `body`), in source order."""
        entries = sorted(((str(e.property.get()), int(e.index.get()), e.child) for e in getattr(node, adjacency)),
                         key=lambda entry: (_CHILDREN[entry[0]], entry[1]))
        for prop, index, child in entries:
            self.statement(child, scope, at.child(prop, index))

    def statement(self, node: Any, scope: Scope, at: Anchor) -> None:
        self.program.located(at, scope)
        kind = node.as_schema().name.rsplit(".", 1)[-1]
        props = Objects.properties(node)
        handler = self.STATEMENTS.get(kind)
        if handler is not None:
            handler(self, node, props, scope, at)
            return
        for name, value in props.items():
            self.visit(value, scope, at.at(name, _rank(node, name)))
        self.children(node, "children", scope, at)

    def prop(self, node: Any, props: dict[str, Any], name: str, scope: Scope, at: Anchor) -> None:
        """A statement's property, evaluated in `scope`, where it is set."""
        if name in props:
            self.visit(props[name], scope, at.at(name, _rank(node, name)))

    def targets(self, node: Any, props: dict[str, Any], name: str, scope: Scope, at: Anchor) -> None:
        """A statement's target, or each of its targets, binding in `scope`, where it has any."""
        if name not in props:
            return
        held, where = props[name], at.at(name, _rank(node, name))
        if isinstance(held, Objects.Listed):
            for i, element in enumerate(held.values):
                self.target(element, scope, where.step(i, i))
        else:
            self.target(held, scope, where)

    def assign(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.prop(node, props, "annotation", scope, at)
        self.prop(node, props, "value", scope, at)
        self.targets(node, props, "targets", scope, at)
        self.targets(node, props, "target", scope, at)

    def for_(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.prop(node, props, "iter", scope, at)
        self.targets(node, props, "target", scope, at)
        self.children(node, "children", scope, at)

    def with_(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        items = at.at("items", _rank(node, "items"))
        for i, item in enumerate(_many(props.get("items"))):
            each = items.step(i, i)
            self.program.located(each, scope)
            fields = Objects.properties(item)
            self.visit(fields["context_expr"], scope, each.step("context_expr", _rank(item, "context_expr")))
            if "optional_vars" in fields:
                self.target(fields["optional_vars"], scope, each.step("optional_vars", _rank(item, "optional_vars")))
        self.children(node, "children", scope, at)

    def handler(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.prop(node, props, "type", scope, at)
        if "name" in props:
            self.bind(scope, props["name"], at.at("name", _rank(node, "name")), "variable")
        self.children(node, "children", scope, at)

    def import_(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        names = at.at("names", _rank(node, "names"))
        for i, alias in enumerate(_many(props.get("names"))):
            each = names.step(i, i)
            self.program.located(each, scope)
            fields = Objects.properties(alias)
            if "asname" in fields:
                self.bind(scope, fields["asname"], each, "import")
            elif fields["name"] != "*":  # `from m import *` binds what it cannot see
                self.bind(scope, fields["name"].split(".")[0], each, "import")  # `import a.b` binds `a`

    def global_(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        names = at.at("names", _rank(node, "names"))
        is_global = node.as_schema().name.endswith(".Global")
        for i, name in enumerate(_many(props.get("names"))):
            outer = self.program.root if is_global else self.nonlocal_scope(scope, name) or scope
            entity = self.entity(outer, name, "variable")
            scope.declare(entity)
            each = names.step(i, i)
            self.program.declares(each, entity)
            self.program.located(each, scope)
            self.program.written(each, name)

    def type_parameters(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> Scope:
        """The annotation scope of a generic function, class or type alias, with its type parameters; `scope`
        itself if it has none."""
        parameters = _many(props.get("type_params"))
        if not parameters:
            return scope
        inner = Scope("type parameters", None, self.enclosing(scope), at)
        where = at.at("type_params", _rank(node, "type_params"))
        for i, parameter in enumerate(parameters):
            each = where.step(i, i)
            self.program.located(each, inner)
            tag, record = Terms.kind_of(parameter)
            fields = Objects.properties(record)
            self.bind(inner, fields["name"], each, "type parameter")
            for name in ("bound", "default_value"):
                if name in fields:
                    self.visit(fields[name], inner, each.step(name, _rank(record, name)))
        return inner

    def function(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.prop(node, props, "decorator_list", scope, at)
        entity = self.bind(scope, props["name"], at.at("name", _rank(node, "name")), "function")
        self.program.declares(at, entity)
        annotations = self.type_parameters(node, props, scope, at)
        inner = Scope("function", entity, self.enclosing(annotations), at)
        entity.scope = inner
        self.arguments(props["args"], at.at("args", _rank(node, "args")), scope, annotations, inner)
        self.prop(node, props, "returns", annotations, at)
        self.bodies.append((node, "children", inner, at))

    def class_(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.prop(node, props, "decorator_list", scope, at)
        entity = self.bind(scope, props["name"], at.at("name", _rank(node, "name")), "class")
        self.program.declares(at, entity)
        annotations = self.type_parameters(node, props, scope, at)
        self.prop(node, props, "bases", annotations, at)
        self.prop(node, props, "keywords", annotations, at)
        entity.scope = Scope("class", entity, self.enclosing(annotations), at)
        self.bodies.append((node, "children", entity.scope, at))

    def type_alias(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        name = at.at("name", _rank(node, "name"))
        self.program.located(name, scope)
        entity = self.bind(scope, Objects.properties(Terms.kind_of(props["name"])[1])["name"], name, "type alias")
        self.program.declares(at, entity)
        self.prop(node, props, "value", self.type_parameters(node, props, scope, at), at)

    def match_case(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.prop(node, props, "pattern", scope, at)
        self.prop(node, props, "guard", scope, at)
        self.children(node, "children", scope, at)

    STATEMENTS: dict[str, Any] = {
        "Assign": assign, "AugAssign": assign, "AnnAssign": assign, "Delete": assign, "For": for_, "AsyncFor": for_,
        "With": with_, "AsyncWith": with_, "ExceptHandler": handler, "Import": import_, "ImportFrom": import_,
        "Global": global_, "Nonlocal": global_, "FunctionDef": function, "AsyncFunctionDef": function,
        "ClassDef": class_, "TypeAlias": type_alias, "MatchCase": match_case,
    }

    def define(self, module: Any) -> Program:
        program = self.program
        program.located(program.root.node, program.root)
        self.bodies.append((module, "body", program.root, program.root.node))
        while self.bodies:
            node, adjacency, scope, at = self.bodies.popleft()
            self.children(node, adjacency, scope, at)
        for entity in program.entities():
            entity.declarations.sort(key=lambda anchor: anchor.order)
            entity.definition = entity.declarations[0] if entity.declarations else None
        return program


def define(store: Any, path: str) -> Program:
    """The entities the module at `path` binds, in their scopes, read within the transaction open on `store`, or
    within one of its own; LookupError where the workspace holds no file at `path`."""
    try:
        workspace = store.singleton(WORKSPACE)
    except ValueError:  # "a store is read only within a transaction": none is open
        with store.transaction():
            return define(store, path)
    module = workspace.files({"path": path})  # LookupError, where it holds none
    reference = References.of(store, module)
    plain = Plain.ToPlain(store)(reference.as_schema(), reference)["path"]
    place = _Place(store, plain=plain)
    place.made = reference
    program = Program(path, Anchor(place, ""))
    return _Definer(program).define(module)


def referents(program: Program, at: Any) -> list[Entity]:
    """The entities the name written at `at` (an `Anchor`, or its text) refers to, looked up from where it is: the one
    it binds or declares, or the ones its name resolves to. A place where no name is written, an attribute's name
    (which depends on a value) and a keyword argument's (on the function called) find nothing."""
    name = program.name_at(at)
    if name is None:
        return []
    entity = program.entity_of(at)
    return [entity] if entity is not None else program.scope_of(at).resolve(name)  # type: ignore[union-attr]
