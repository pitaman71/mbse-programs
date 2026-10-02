"""Syntax: the protocols every language's abstract syntax trees implement, and the machinery that implements them.

A language is a set of syntax node kinds, grouped into categories (Expression, Statement, Declaration, ...). Every
language's trees are:

- Plain in-memory objects. A kind is a class whose properties are declared once, as typed annotations: natives (`str`,
  `bool`, `int`, or a `Literal` of strings, a choice) are attributes, and syntax nodes or lists of syntax nodes are
  children. `X | None` marks a property optional. Syntax nodes are mutable: a transpiler builds, reads and rewrites them
  directly.
- Serializable. Each kind has a meta-schema, an mbse-schemas reference object schema with the tag `kind` and one
  property per attribute, and a builder (`create()` / `clone()` / `update()`) that implements `Visitors.OfObject`, so
  `JSON`, `YAML` and `Plain` read and write trees. Children are entries of the adjacency `children`, to the relation
  `Children` (registered as 'Programs.Children' and shared by every language), which links a `parent` to a `child` with
  the child's `property` and, in a list, its `index`. Every kind also declares `parent`, the same relation seen from the
  child, which data never writes.
- Traversable through their properties alone: `children`, `walk`, `fold`, `same`, `copy`, `Parents`, `Visitor` and
  `Transformer` work for every language.
- Validatable: `Language.validate` reports missing properties, misplaced children, choices out of range and shared
  syntax nodes.
- Standardized: each kind and feature records the standards that have it (`SINCE`, `FEATURES`), and a `Standard`
  (such as C++20) checks a tree against them, parses source text into trees and prints trees back into source text.
"""

from __future__ import annotations

import inspect
import types
import typing
from collections.abc import Callable, Hashable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, Union

from mbse.Schemas.Framework import Schemas, Stores, Visitors
from mbse.Schemas.Framework.Visitors import Native

__all__ = [
    "Attribute", "Child", "Property", "Availability", "SyntaxNode", "Builder", "OfStore", "Language", "Standard",
    "CHILDREN", "Children", "label", "children", "walk", "fold", "same", "copy", "Parents", "Visitor", "Transformer",
]

CHILDREN = "Programs.Children"
_NATIVES: dict[type, str] = {str: "str", bool: "bool", int: "int"}

# Where a feature exists, by language family ('C++', 'C', 'Python'): the version of the first standard that has it, or
# (first, last exclusive) for a feature a later standard removed.
Availability = Mapping[str, Union[int, tuple[int, int]]]


def _article(noun: str) -> str:
    return f"{'an' if noun[0].lower() in 'aeiou' else 'a'} {noun}"


def _type_name(value: object) -> str:
    return type(value).__name__


def _set(visitor: Any, name: str, value: Native) -> None:
    visitor.property(name, lambda p: p.value(lambda a: a.as_native(lambda n: n.set(value))))


# --- Properties ---


@dataclass(frozen=True)
class Attribute:
    """A native property: `native` is str, bool or int; a str attribute may be limited to `choices`. A bool is False
    unless set, and is written only when True."""

    name: str
    native: type
    optional: bool = False
    choices: tuple[str, ...] | None = None

    def describe(self) -> dict[str, Any]:
        out: dict[str, Any] = {"name": self.name, "type": _NATIVES[self.native], "optional": self.optional}
        if self.choices is not None:
            out["choices"] = list(self.choices)
        return out


@dataclass(frozen=True)
class Child:
    """A property holding a syntax node of one of `categories` (categories or kinds), or with `many` an ordered list of
    them."""

    name: str
    categories: tuple[type, ...]
    optional: bool = False
    many: bool = False

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "type": [c.__name__ for c in self.categories], "optional": self.optional,
                "many": self.many}


Property = Union[Attribute, Child]


def _property(kind: type, name: str, hint: Any) -> Property:
    """The property a typed annotation declares."""
    optional = False
    if typing.get_origin(hint) in (Union, types.UnionType):
        options = [a for a in typing.get_args(hint) if a is not type(None)]
        optional = len(options) < len(typing.get_args(hint))
        hint = options[0] if len(options) == 1 else Union[tuple(options)]
    origin, arguments = typing.get_origin(hint), typing.get_args(hint)
    if hint in _NATIVES:
        return Attribute(name, hint, optional)
    if origin is Literal:
        return Attribute(name, str, optional, tuple(arguments))
    many = origin is list
    if many:
        hint = arguments[0]
    members = typing.get_args(hint) if typing.get_origin(hint) in (Union, types.UnionType) else (hint,)
    if not all(isinstance(m, type) and issubclass(m, SyntaxNode) for m in members):
        raise TypeError(f"{kind.__name__}.{name}: a property holds a native, a choice, or syntax nodes, got {hint!r}")
    return Child(name, tuple(members), optional or many, many)


def _properties(kind: type) -> tuple[Property, ...]:
    """A kind's properties, in the order its classes annotate them, the most basic first. The annotations may be strings
    (`from __future__ import annotations`) or evaluated lazily (Python 3.14)."""
    hints = typing.get_type_hints(kind)
    names = [name for base in reversed(kind.__mro__) for name in inspect.get_annotations(base)]
    return tuple(_property(kind, name, hints[name]) for name in dict.fromkeys(names)
                 if typing.get_origin(hints[name]) is not ClassVar)


# --- Syntax nodes ---


class SyntaxNode:
    """Every language's syntax nodes: kinds are leaf classes, and the classes between them and `SyntaxNode` are
    categories. `Language` sets `LANGUAGE`, `KIND`, `NAME`, `PROPERTIES` and `Schema` on each kind.

    `SINCE` is where a kind exists (by default, wherever its language exists). `FEATURES` maps a property to the values
    that make a feature of it, each with where that feature exists: a choice or True for an attribute, True for a
    child that is present or a list that is not empty. `EXTENSION` marks a kind no standard has, which every standard
    accepts. `check()` and `features()` add a kind's own problems and features."""

    LANGUAGE: ClassVar[Language]
    KIND: ClassVar[str]
    NAME: ClassVar[str]
    PROPERTIES: ClassVar[tuple[Property, ...]] = ()
    Schema: ClassVar[Schemas.OfObject.Data]
    SINCE: ClassVar[Availability | None] = None
    FEATURES: ClassVar[Mapping[str, Mapping[Any, Availability]]] = {}
    EXTENSION: ClassVar[bool] = False

    def __init__(self, **values: Any):
        kind = type(self)
        if "KIND" not in vars(kind):
            raise TypeError(f"{kind.__name__} is not a kind of syntax node")
        for prop in kind.PROPERTIES:
            default: Any = [] if isinstance(prop, Child) and prop.many else None
            setattr(self, prop.name, False if isinstance(prop, Attribute) and prop.native is bool else default)
        for name, value in values.items():
            prop = kind._BY_NAME.get(name)  # type: ignore[attr-defined]
            if prop is None:
                raise TypeError(f"{kind.KIND} has no property {name!r}")
            setattr(self, name, list(value) if isinstance(prop, Child) and prop.many else value)

    def __repr__(self) -> str:
        """The kind and the properties that are set: not None, False or an empty list."""
        shown = [f"{f.name}={getattr(self, f.name)!r}" for f in self.PROPERTIES if not _unset(getattr(self, f.name))]
        return f"{self.KIND}({', '.join(shown)})"

    # Visitors.Visitable

    def identity(self) -> Hashable:
        return id(self)

    def schema_name(self) -> str:
        return self.NAME

    def owner(self) -> None:
        """Syntax nodes are reference objects, linked by their parents."""
        return None

    def accept(self, visitor: Visitors.OfObject) -> None:
        """Writes the tag, the attributes that are set (a bool only when True), then one `children` entry per child,
        in property order, with its property and, in a list, its index."""
        _set(visitor, "kind", self.KIND)
        for prop in self.PROPERTIES:
            value = getattr(self, prop.name)
            if isinstance(prop, Attribute) and value is not None and value is not False:
                _set(visitor, prop.name, value)
        for name, index, child in children(self):
            _write_child(visitor, name, index, child)

    # Hooks

    def check(self) -> list[str]:
        """The kind's own problems, beyond those of its properties; none by default."""
        return []

    def features(self) -> list[tuple[str, Availability]]:
        """The kind's own features, beyond those `FEATURES` declares, each with where it exists; none by default."""
        return []

    def availability(self) -> Availability | None:
        """Where this syntax node's kind exists, if its attributes do not change that: `SINCE`, or None for wherever its
        language exists."""
        return self.SINCE


def _unset(value: Any) -> bool:
    return value is None or value is False or (isinstance(value, list) and not value)


def children(node: SyntaxNode) -> list[tuple[str, int | None, SyntaxNode]]:
    """A syntax node's children in property order, each with its property and, in a list, its index. Empty slots are
    skipped."""
    out: list[tuple[str, int | None, SyntaxNode]] = []
    for prop in node.PROPERTIES:
        if isinstance(prop, Child):
            value = getattr(node, prop.name)
            if prop.many:
                out.extend((prop.name, i, c) for i, c in enumerate(value or ()) if c is not None)
            elif value is not None:
                out.append((prop.name, None, value))
    return out


def _write_child(visitor: Visitors.OfObject, prop: str, index: int | None, child: SyntaxNode) -> None:
    def fill(entry: Visitors.OfEntry) -> None:
        entry.link("child", lambda k: k.set(child))
        _set(entry, "property", prop)
        if index is not None:
            _set(entry, "index", index)

    visitor.adjacency("children", lambda a: a.add(fill))


# --- Builders: Visitors that build syntax nodes ---


class _Native:
    """`Visitors.OfProperty`, `OfAny` and `OfNative` over one native value."""

    def __init__(self, name: str, native: type, read: Callable[[], Any], write: Callable[[Any], None]):
        self._name, self._native, self._read, self._write = name, native, read, write

    def name(self) -> str:
        return self._name

    def has(self) -> bool:
        value = self._read()
        return type(value) is self._native and value is not False

    def get(self) -> Native:
        if not self.has():
            raise AttributeError(f"property {self._name!r} is not set")
        return self._read()

    def set(self, value: Native) -> _Native:
        if type(value) is not self._native:
            raise TypeError(f"expected {_NATIVES[self._native]}, got {_type_name(value)}")
        self._write(value)
        return self

    def clear(self) -> _Native:
        self._write(False if self._native is bool else None)
        return self

    def value(self, callback: Callable[[Visitors.OfAny], Any]) -> _Native:
        callback(self)
        return self

    def as_native(self, callback: Callable[[Visitors.OfNative], Any]) -> _Native:
        callback(self)
        return self

    def as_object(self, callback: Callable[[Visitors.OfObject], Any]) -> _Native:
        raise TypeError(f"property {self._name!r} is native")

    def as_union(self, callback: Callable[[Visitors.OfUnion], Any]) -> _Native:
        raise TypeError(f"property {self._name!r} is native")

    def as_intersection(self, callback: Callable[[Visitors.OfIntersection], Any]) -> _Native:
        raise TypeError(f"property {self._name!r} is native")

    def as_indexed(self, callback: Callable[[Visitors.OfIndexed], Any]) -> _Native:
        raise TypeError(f"property {self._name!r} is native")


class _Link:
    """`Visitors.OfLink` over the one link a `Children` entry sets."""

    def __init__(self, entry: _Entry):
        self._entry = entry

    def name(self) -> str:
        return self._entry.other

    def target(self, callback: Callable[[Visitors.Visitable], Any]) -> _Link:
        if self._entry.target is None:
            raise ValueError(f"link {self._entry.other!r} is not set")
        callback(self._entry.target)
        return self

    def set(self, target: Visitors.Visitable) -> _Link:
        self._entry.target = target
        return self


class _Entry:
    """`Visitors.OfEntry` for one entry of `Children`, seen from the end that fills `me`: it sets the other link, the
    child's `property` and its `index`."""

    # the entry's properties, by the attribute holding each
    _ATTRIBUTES = {"property": "property_name", "index": "index"}

    def __init__(self, me: str, target: Any = None, property_name: str | None = None, index: int | None = None):
        self.other = "child" if me == "parent" else "parent"
        self.target, self.property_name, self.index = target, property_name, index

    def _property(self, name: str) -> _Native:
        native, attribute = (str if name == "property" else int), self._ATTRIBUTES[name]
        return _Native(name, native, lambda: getattr(self, attribute), lambda value: setattr(self, attribute, value))

    def links(self, callback: Callable[[Visitors.OfLink], Any]) -> _Entry:
        callback(_Link(self))
        return self

    def link(self, name: str, callback: Callable[[Visitors.OfLink], Any]) -> _Entry:
        if name != self.other:
            raise KeyError(f"{name!r} is not a link this entry can set")
        callback(_Link(self))
        return self

    def properties(self, callback: Callable[[Visitors.OfProperty], Any]) -> _Entry:
        for name, attribute in self._ATTRIBUTES.items():
            if getattr(self, attribute) is not None:
                callback(self._property(name))
        return self

    def has(self, name: str) -> bool:
        return name in self._ATTRIBUTES and getattr(self, self._ATTRIBUTES[name]) is not None

    def property(self, name: str, callback: Callable[[Visitors.OfProperty], Any]) -> _Entry:
        if name not in self._ATTRIBUTES:
            raise KeyError(f"unknown property {name!r}")
        callback(self._property(name))
        return self

    def clear(self, name: str) -> _Entry:
        if name in self._ATTRIBUTES:
            setattr(self, self._ATTRIBUTES[name], None)
        return self


class _Adjacency:
    """`Visitors.OfAdjacency` over a syntax node's `children`, or over `parent`, whose entries are ignored (the parents'
    children imply them)."""

    def __init__(self, name: str, me: str, entries: list[_Entry] | None):
        self._name, self._me, self._entries = name, me, entries

    def name(self) -> str:
        return self._name

    def me(self) -> str:
        return self._me

    def entries(self, callback: Callable[[Visitors.OfEntry], Any]) -> _Adjacency:
        for entry in list(self._entries or []):
            callback(entry)
        return self

    def add(self, callback: Callable[[Visitors.OfEntry], Any]) -> _Adjacency:
        entry = _Entry(self._me)
        callback(entry)
        if self._entries is not None:
            self._entries.append(entry)
        return self

    def remove(self, entry: Visitors.OfEntry) -> _Adjacency:
        if self._entries is not None:
            self._entries[:] = [e for e in self._entries if e is not entry]
        return self


class Builder:
    """Shared by every kind's builder: `create()` / `clone()` / `update()` with the rules and messages of every builder,
    and `Visitors.OfObject` over the tag `kind`, the kind's attributes and its `children` entries. None of them
    validate. DSL: `.set(property, value)` sets an attribute, a child or a list of children, and `.add(property, child)`
    appends to a list.

    Each kind's builder is also fluent, with one setter per property, named as the property, or with a trailing `_`
    where the builder has a method of that name (`update_`): an attribute's setter takes its value, a child's takes a
    `Spec` (see `child`), and a list's takes a list of them, which `add_<property>` appends to one at a time. `None`
    clears a property."""

    _kind: ClassVar[type[SyntaxNode]]

    def __init__(self, instance: Any = None):
        if instance is not None and type(instance) is not self._kind:
            raise TypeError(f"expected {_article(self._kind.KIND)} to build from, got {_type_name(instance)}")
        self._source = instance
        self._values: dict[str, Any] = {}
        self._entries: list[_Entry] = []
        if instance is not None:
            self._values = {f.name: getattr(instance, f.name) for f in self._kind.PROPERTIES
                            if isinstance(f, Attribute)}
            self._entries = [_Entry("parent", child, name, index) for name, index, child in children(instance)]

    # DSL

    def _child_property(self, name: str) -> Child:
        prop = self._kind._BY_NAME.get(name)  # type: ignore[attr-defined]
        if not isinstance(prop, Child):
            raise KeyError(f"{self._kind.KIND} has no child property {name!r}")
        return prop

    def set(self, name: str, value: Any) -> Any:
        prop = self._kind._BY_NAME.get(name)  # type: ignore[attr-defined]
        if isinstance(prop, Attribute):
            self._values[name] = value
            return self
        prop = self._child_property(name)
        self._entries = [entry for entry in self._entries if entry.property_name != name]
        if prop.many:
            self._entries += [_Entry("parent", child, name, i) for i, child in enumerate(value)]
        elif value is not None:
            self._entries.append(_Entry("parent", value, name))
        return self

    def add(self, name: str, child: SyntaxNode) -> Any:
        if not self._child_property(name).many:
            raise TypeError(f"{self._kind.KIND}.{name} holds one child; use set()")
        index = sum(1 for entry in self._entries if entry.property_name == name)
        self._entries.append(_Entry("parent", child, name, index))
        return self

    def child(self, name: str, spec: Any) -> SyntaxNode | None:
        """The syntax node a `Spec` gives the child property `name`: a syntax node itself; a builder, finalized; or a
        function that makes one, which is passed the builder of the property's kind where the property holds one kind,
        and the language's `Builders` otherwise, so that it names the kind. A property that holds one kind, whose only
        property is an attribute, also takes that attribute's value (an `Identifier` takes its spelling)."""
        prop = self._child_property(name)
        if spec is None or isinstance(spec, SyntaxNode):
            return spec
        if isinstance(spec, Builder):
            return spec.finish()
        kind = _one_kind(prop)
        if callable(spec):
            made = spec(kind.LANGUAGE.builder(kind) if kind is not None else self._kind.LANGUAGE.Builders)
            if isinstance(made, Builder):
                return made.finish()
            if isinstance(made, SyntaxNode):
                return made
            raise TypeError(f"the function for {self._kind.KIND}.{name} must return a builder or a syntax node, got "
                            f"{_type_name(made)}")
        if kind is not None and len(kind.PROPERTIES) == 1 and isinstance(kind.PROPERTIES[0], Attribute) and (
                type(spec) is kind.PROPERTIES[0].native):
            return kind(**{kind.PROPERTIES[0].name: spec})
        raise TypeError(f"{self._kind.KIND}.{name} takes a syntax node, a builder or a function that makes one, got "
                        f"{_type_name(spec)}")

    # Finalizing

    def finish(self) -> Any:
        """`clone()` for a builder made from an instance, and `create()` otherwise."""
        return self.create() if self._source is None else self.clone()

    def create(self) -> Any:
        if self._source is not None:
            raise ValueError("create() is only valid without a source instance; use clone() or update()")
        return self._make()

    def clone(self) -> Any:
        if self._source is None:
            raise ValueError("clone() is only valid with a source instance")
        return self._make()

    def update(self) -> Any:
        if self._source is None:
            raise ValueError("update() is only valid with a source instance")
        made = self._make()
        for prop in self._kind.PROPERTIES:
            setattr(self._source, prop.name, getattr(made, prop.name))
        return self._source

    def _make(self) -> Any:
        kind = self._kind
        values: dict[str, Any] = dict(self._values)
        lists: dict[str, list[_Entry]] = {}
        for entry in self._entries:
            if entry.target is None:
                raise ValueError("link 'child' is not set")
            if entry.property_name is None:
                raise ValueError("a child entry needs a property")
            prop = kind._BY_NAME.get(entry.property_name)  # type: ignore[attr-defined]
            if not isinstance(prop, Child):
                raise ValueError(f"{_article(kind.KIND)} has no child property {entry.property_name!r}")
            if not isinstance(entry.target, SyntaxNode):
                raise TypeError(f"a child must be a syntax node, got {_type_name(entry.target)}")
            if prop.many:
                lists.setdefault(prop.name, []).append(entry)
            elif entry.index is not None:
                raise ValueError(f"{kind.KIND}.{prop.name} holds one child, not a list")
            elif prop.name in values:
                raise ValueError(f"{kind.KIND}.{prop.name} holds one child, got several")
            else:
                values[prop.name] = entry.target
        for name, entries in lists.items():
            last = len(entries)
            ordered = sorted(entries, key=lambda e: last if e.index is None else e.index)
            values[name] = [entry.target for entry in ordered]
        return kind(**values)

    # Visitors.OfObject

    def _check_kind(self, kind: Any) -> None:
        if kind is not None and kind != self._kind.KIND:
            raise ValueError(f"expected kind {self._kind.KIND!r}, got {kind!r}")

    def _names(self) -> list[str]:
        return ["kind", *(f.name for f in self._kind.PROPERTIES if isinstance(f, Attribute))]

    def _native(self, name: str) -> _Native:
        if name == "kind":
            return _Native("kind", str, lambda: self._kind.KIND, self._check_kind)
        prop = self._kind._BY_NAME[name]  # type: ignore[attr-defined]
        return _Native(name, prop.native, lambda: self._values.get(name),
                       lambda value: self._values.__setitem__(name, value))

    def properties(self, callback: Callable[[Visitors.OfProperty], Any]) -> Builder:
        for name in self._names():
            if self.has(name):
                callback(self._native(name))
        return self

    def has(self, name: str) -> bool:
        return name in self._names() and self._native(name).has()

    def property(self, name: str, callback: Callable[[Visitors.OfProperty], Any]) -> Builder:
        if name not in self._names():
            raise KeyError(f"unknown property {name!r}")
        callback(self._native(name))
        return self

    def clear(self, name: str) -> Builder:
        if name != "kind" and name in self._names():
            self._native(name).clear()
        return self

    def _parent(self) -> bool:
        return any(isinstance(f, Child) for f in self._kind.PROPERTIES)

    def adjacencies(self, callback: Callable[[Visitors.OfAdjacency], Any]) -> Builder:
        for name in ["children", "parent"] if self._parent() else ["parent"]:
            self.adjacency(name, callback)
        return self

    def adjacency(self, name: str, callback: Callable[[Visitors.OfAdjacency], Any]) -> Builder:
        if name == "children" and self._parent():
            callback(_Adjacency("children", "parent", self._entries))
        elif name == "parent":
            callback(_Adjacency("parent", "child", None))
        else:
            raise KeyError(f"unknown adjacency {name!r}")
        return self

    def identify(self, value: Visitors.Visitable) -> Builder:
        """Syntax nodes hold no value objects, so there is nothing to identify."""
        return self


def _one_kind(prop: Child) -> type[SyntaxNode] | None:
    """The kind a property holds, if it is declared with one kind rather than with categories."""
    only = prop.categories[0]
    return only if len(prop.categories) == 1 and "KIND" in vars(only) else None


def _setters(kind: type[SyntaxNode]) -> dict[str, Callable[..., Any]]:
    """The fluent setters of `kind`'s builder, by name."""
    def setter(prop: Property) -> Callable[..., Any]:
        if isinstance(prop, Attribute):
            return lambda self, value: self.set(prop.name, value)
        if prop.many:
            return lambda self, specs: self.set(prop.name, [self.child(prop.name, s) for s in specs])
        return lambda self, spec: self.set(prop.name, self.child(prop.name, spec))

    out: dict[str, Callable[..., Any]] = {}
    for prop in kind.PROPERTIES:
        out[prop.name + "_" if prop.name in vars(Builder) else prop.name] = setter(prop)
        if isinstance(prop, Child) and prop.many:
            out[f"add_{prop.name}"] = lambda self, spec, name=prop.name: self.add(name, self.child(name, spec))
    return out


# --- Meta-schemas and the store ---


def _native(name: str, native: type) -> Callable[[Any], Any]:
    return lambda p: p.name(name).of(lambda t: t.as_native(native))


Children = (
    Schemas.OfRelation.Builder().name(CHILDREN).links("parent", "child")
    .properties(_native("property", str), _native("index", int)).unique("child").create()
)
_CHILDREN = lambda r: r.name("children").of(Children).me("parent")  # noqa: E731
_PARENT = lambda r: r.name("parent").of(Children).me("child")  # noqa: E731


def _schema(kind: type[SyntaxNode]) -> Schemas.OfObject.Data:
    """A kind's meta-schema: the tag, one property per attribute, and the adjacencies `children` (if it has child
    properties) and `parent`."""
    attributes = [_native(f.name, f.native) for f in kind.PROPERTIES if isinstance(f, Attribute)]
    relations = [_CHILDREN, _PARENT] if any(isinstance(f, Child) for f in kind.PROPERTIES) else [_PARENT]
    return (Schemas.OfObject.Builder().name(kind.NAME).ref().properties(_native("kind", str), *attributes)
            .relations(*relations).create())


class OfStore(Stores.Catalog):
    """A store of a language's syntax nodes (see mbse-schemas' `Stores`): its meta-schemas by name, and a builder for each
    kind by the meta-schema's name or the kind's own (`store.builder('Programs.Ccpp.Identifier', instance)`,
    `store.Identifier(instance)`), as `Plain.FromPlain` expects. A language has no singleton schemas, so its store holds
    no data: the nodes its builders make are the program's, and its extents are empty."""

    def __init__(self, schemas: Mapping[str, Any], builders: Mapping[str, type]):
        super().__init__()
        self._factories: dict[str, type] = {}
        for schema in [*schemas.values(), Children]:
            self.register(schema)
        for name, builder in builders.items():
            for alias in (name, builder._kind.KIND):  # type: ignore[attr-defined]
                self._factories[alias] = builder
                setattr(self, alias, lambda instance=None, alias=alias: self.builder(alias, instance))

    def builder(self, name: str, instance: Any = None) -> Builder:
        if name not in self._factories:
            self.schema(name)  # raises for an unknown name or a relation
        return self._factories[name](instance)  # type: ignore[no-any-return]

    def member(self, instance: Any, name: str) -> Any:
        """The value a syntax node holds in its attribute `name`."""
        return getattr(instance, name)


# --- Languages ---


class Language:
    """A language declared by its kinds, from which it derives their properties, builders, meta-schemas (named
    'Programs.<name>.<Kind>'), the union `Schema` of every kind, whose branches are named by the kinds, and the store
    `Builders` of its syntax nodes. `BASE` is where a kind exists unless it says otherwise."""

    def __init__(self, name: str, kinds: Sequence[type[SyntaxNode]], *, base: Availability):
        self._name, self.BASE = name, base
        self.classes = tuple(kinds)
        self._kinds: dict[str, type[SyntaxNode]] = {}
        self._categories: dict[str, type[SyntaxNode]] = {}
        schemas: dict[str, Any] = {}
        builders: dict[str, type] = {}
        for kind in kinds:
            kind.LANGUAGE, kind.KIND, kind.NAME = self, kind.__name__, f"Programs.{name}.{kind.__name__}"
            self._kinds[kind.KIND] = kind
            for base_class in reversed(kind.__mro__[1:kind.__mro__.index(SyntaxNode)]):
                self._categories.setdefault(base_class.__name__, base_class)
        for kind in kinds:  # properties refer to other kinds, so they are read once every kind is known
            kind.PROPERTIES = _properties(kind)
            kind._BY_NAME = {f.name: f for f in kind.PROPERTIES}  # type: ignore[attr-defined]
            kind.Schema = schemas[kind.NAME] = _schema(kind)
            builders[kind.NAME] = type(f"{kind.KIND}Builder", (Builder,), {"_kind": kind, **_setters(kind)})
        self.Schema = Schemas.OfUnion.Builder().branches(
            *(lambda b, kind=kind: b.name(kind.KIND).of(kind.Schema) for kind in kinds)
        ).create()
        self.Builders = OfStore(schemas, builders)

    def name(self) -> str:
        return self._name

    def kinds(self) -> dict[str, type[SyntaxNode]]:
        """Every kind, by name, in declaration order."""
        return dict(self._kinds)

    def categories(self) -> dict[str, type[SyntaxNode]]:
        """Every category, by name, in the order kinds first name them."""
        return dict(self._categories)

    def builder(self, kind: str | type[SyntaxNode], instance: Any = None) -> Builder:
        """A builder for `kind`, or for `instance` of it."""
        name = kind if isinstance(kind, str) else kind.__name__
        if name not in self._kinds:
            raise KeyError(f"{self._name} has no kind {name!r}")
        return getattr(self.Builders, self._kinds[name].NAME)(instance)

    def schema_of(self, node: Any) -> Schemas.OfObject.Data:
        """The meta-schema of `node`'s kind: the root schema for its snapshots."""
        if not isinstance(node, self.classes):
            raise TypeError(f"not {_article(self._name)} syntax node: {node!r}")
        return type(node).Schema

    def __repr__(self) -> str:
        return f"<language {self._name}>"

    def grammar(self) -> dict[str, Any]:
        """The language as plain data: its categories, and each kind's category, availability, features and properties.
        Every implementation describes a language identically."""
        def since(availability: Availability | None) -> Any:
            return None if availability is None else {k: list(v) if isinstance(v, tuple) else v
                                                      for k, v in availability.items()}

        return {
            "language": self._name,
            "base": since(self.BASE),
            "categories": [{"name": n, "base": c.__mro__[1].__name__} for n, c in self._categories.items()],
            "kinds": [{
                "kind": k.KIND, "category": k.__mro__[1].__name__, "since": since(k.SINCE), "extension": k.EXTENSION,
                "features": {f: {str(v).lower() if v is True else v: since(a) for v, a in values.items()}
                             for f, values in k.FEATURES.items()},
                "properties": [f.describe() for f in k.PROPERTIES],
            } for k in self.classes],
        }

    # Checks

    def validate(self, node: Any) -> list[str]:
        """Problems with the tree at `node`, each prefixed with the path to the syntax node it concerns: required
        properties that are missing, children of the wrong category, attributes of the wrong type or out of their
        choices, syntax nodes that appear twice, cycles, and each kind's own problems."""
        problems: list[str] = []
        seen: dict[int, str] = {}

        def at(path: str, problem: str) -> str:
            return f"{path}: {problem}" if path else problem

        def visit(node: Any, path: str) -> None:
            if not isinstance(node, self.classes):
                problems.append(at(path, f"not {_article(self._name)} syntax node: {node!r}"))
                return
            if id(node) in seen:
                problems.append(at(path, f"the syntax node is also at {seen[id(node)] or 'the root'}"))
                return
            seen[id(node)] = path
            kind = type(node)
            for prop in kind.PROPERTIES:
                value = getattr(node, prop.name)
                if isinstance(prop, Attribute):
                    problems.extend(at(path, p) for p in _attribute_problems(kind, prop, value))
                    continue
                where = f"{path}.{prop.name}" if path else prop.name
                if not prop.many:
                    if value is None:
                        if not prop.optional:
                            problems.append(at(path, f"{_article(kind.KIND)} needs {_article(prop.name)}"))
                    elif _placed(kind, prop, value, where, problems):
                        visit(value, where)
                    continue
                if not isinstance(value, list):
                    problems.append(at(path, f"{kind.KIND}.{prop.name} must be a list, got {_type_name(value)}"))
                    continue
                for i, item in enumerate(value):
                    if item is None:
                        problems.append(at(path, f"{kind.KIND}.{prop.name}[{i}] is empty"))
                    elif _placed(kind, prop, item, f"{where}[{i}]", problems):
                        visit(item, f"{where}[{i}]")
            problems.extend(at(path, p) for p in node.check())

        visit(node, "")
        return problems


def _attribute_problems(kind: type[SyntaxNode], prop: Attribute, value: Any) -> list[str]:
    if value is None or (value is False and prop.native is bool):
        return [] if prop.optional or prop.native is bool else [f"{_article(kind.KIND)} needs {_article(prop.name)}"]
    if type(value) is not prop.native:
        return [f"{kind.KIND}.{prop.name} must be {_article(_NATIVES[prop.native])}, got {_type_name(value)}"]
    if prop.choices is not None and value not in prop.choices:
        return [f"{kind.KIND}.{prop.name} cannot be {value!r}"]
    return []


def _placed(kind: type[SyntaxNode], prop: Child, child: Any, where: str, problems: list[str]) -> bool:
    """Whether `child` may fill `property`; if not, says why."""
    if isinstance(child, prop.categories):
        return True
    expected = " or ".join(_article(c.__name__) for c in prop.categories)
    got = _article(child.KIND) if isinstance(child, SyntaxNode) and "KIND" in vars(type(child)) else _type_name(child)
    problems.append(f"{where}: {kind.KIND}.{prop.name} must be {expected}, got {got}")
    return False


# --- Standards ---


class Standard:
    """A standard of a language family, such as C++20 (`family` 'C++', `version` 2020): which kinds and features it
    has, and how source text of it is parsed into trees and trees printed into it. Languages derive their standards
    from this class and implement `parse` and `print`."""

    def __init__(self, language: Language, family: str, version: int):
        self.language, self.family, self.version = language, family, version

    def name(self) -> str:
        return self.label(self.version)

    def label(self, version: int) -> str:
        """The name of the family's standard `version`; by default a year's, such as 'C++20'."""
        return label(self.family, version)

    def __repr__(self) -> str:
        return f"<standard {self.name()}>"

    def has(self, availability: Availability) -> bool:
        """Whether this standard has a feature that exists where `availability` says."""
        return self._missing(availability) is None

    def _missing(self, availability: Availability) -> str | None:
        """Why this standard lacks a feature that exists where `availability` says, as a predicate; None if it has
        it."""
        if self.family not in availability:
            return f"is not {self.family}"
        span = availability[self.family]
        first, last = span if isinstance(span, tuple) else (span, None)
        if self.version < first:
            return f"needs {self.label(first)}"
        if last is not None and self.version >= last:
            return f"was removed in {self.label(last)}"
        return None

    def problems(self, node: SyntaxNode) -> list[str]:
        """The features of `node` itself that this standard lacks."""
        kind = type(node)
        if kind.EXTENSION:
            return []
        found: list[str] = []
        missing = self._missing(node.availability() or self.language.BASE)
        if missing is not None:
            found.append(f"{kind.KIND} {missing}")
        for name, values in kind.FEATURES.items():
            value = getattr(node, name)
            for key, availability in values.items():
                if _uses(value, key):
                    missing = self._missing(availability)
                    if missing is not None:
                        found.append(f"{kind.KIND}.{name}{'' if key is True else f' {key!r}'} {missing}")
        for feature, availability in node.features():
            missing = self._missing(availability)
            if missing is not None:
                found.append(f"{feature} {missing}")
        return found

    def check(self, node: SyntaxNode) -> list[str]:
        """The features of the tree at `node` that this standard lacks, each prefixed with the path to its syntax
        node."""
        out: list[str] = []
        for path, item in _paths(node):
            out.extend(f"{path}: {p}" if path else p for p in self.problems(item))
        return out

    def parse(self, text: str) -> SyntaxNode:
        """The tree of a source text of this standard. Raises `Errors.ParseError` for text that is not."""
        raise NotImplementedError(f"{self.name()} has no parser")

    def print(self, node: SyntaxNode) -> str:
        """The source text of a tree, in this standard. Raises `Errors.PrintError` for a tree it cannot print."""
        raise NotImplementedError(f"{self.name()} has no printer")


def _uses(value: Any, key: Any) -> bool:
    """Whether a property's value makes the feature `key`: True for a bool that is set, a child that is present or a
    list that is not empty, a choice for an attribute equal to it."""
    if key is True:
        return not _unset(value)
    return type(value) is str and value == key


def label(family: str, year: int) -> str:
    """A standard's usual name: 'C++20', 'C++98', 'C11'."""
    return f"{family}{year % 100:02d}"


# --- Traversal ---


def _paths(root: SyntaxNode) -> Iterator[tuple[str, SyntaxNode]]:
    """Every syntax node of the tree at `root`, each once, with its path, parents before their children."""
    seen: set[int] = set()
    stack: list[tuple[str, SyntaxNode]] = [("", root)]
    while stack:
        path, node = stack.pop()
        if id(node) in seen:
            continue
        seen.add(id(node))
        yield path, node
        for name, index, child in reversed(children(node)):
            where = name if index is None else f"{name}[{index}]"
            stack.append((f"{path}.{where}" if path else where, child))


def walk(node: SyntaxNode) -> Iterator[SyntaxNode]:
    """Every syntax node reachable from `node`, each once, parents before their children and children in property order.
    Shared syntax nodes are visited once, and cycles end the walk rather than repeat it."""
    for _, item in _paths(node):
        yield item


def fold(node: SyntaxNode, function: Callable[[SyntaxNode, list[Any]], Any]) -> Any:
    """Combines a tree bottom-up: `function(node, results)` is called once per syntax node, shared ones included, with
    the results for its children in property order. Raises on cycles."""
    memo: dict[int, Any] = {}
    active: set[int] = set()

    def visit(item: SyntaxNode) -> Any:
        if id(item) in memo:
            return memo[id(item)]
        if id(item) in active:
            raise ValueError("the tree contains a cycle")
        active.add(id(item))
        results = [visit(child) for _, _, child in children(item)]
        active.discard(id(item))
        memo[id(item)] = function(item, results)
        return memo[id(item)]

    return visit(node)


def same(a: Any, b: Any) -> bool:
    """Whether two trees have the same structure: co-traverses them, comparing kinds, attributes and children in
    order. Sharing is not compared."""
    assumed: set[tuple[int, int]] = set()

    def visit(x: Any, y: Any) -> bool:
        if not isinstance(x, SyntaxNode) or not isinstance(y, SyntaxNode):
            return x is y
        if (id(x), id(y)) in assumed:
            return True  # a cycle: the same if they are the same everywhere else
        assumed.add((id(x), id(y)))
        if type(x) is not type(y):
            return False
        for prop in x.PROPERTIES:
            u, v = getattr(x, prop.name), getattr(y, prop.name)
            if isinstance(prop, Attribute):
                if type(u) is not type(v) or u != v:
                    return False
            elif prop.many:
                if len(u) != len(v) or not all(map(visit, u, v)):
                    return False
            elif not visit(u, v):
                return False
        return True

    return visit(a, b)


def copy(node: SyntaxNode) -> Any:
    """A deep copy of the tree at `node`. Syntax nodes shared within it are shared within the copy."""
    copies: dict[int, SyntaxNode] = {}

    def visit(item: Any) -> Any:
        if not isinstance(item, SyntaxNode):
            return item
        if id(item) not in copies:
            made = copies[id(item)] = type(item)()
            for prop in item.PROPERTIES:
                value = getattr(item, prop.name)
                setattr(made, prop.name, [visit(c) for c in value] if isinstance(prop, Child) and prop.many
                        else visit(value))
        return copies[id(item)]

    return visit(node)


class Parents:
    """Where each syntax node of a tree is: its parent, property and index. Taken once, it stays right while the tree
    changes only through `replace` and `remove`."""

    def __init__(self, root: SyntaxNode):
        self.root = root
        self._where: dict[int, tuple[SyntaxNode, str, int | None]] = {}
        for item in walk(root):
            for name, index, child in children(item):
                self._where.setdefault(id(child), (item, name, index))

    def parent(self, node: SyntaxNode) -> SyntaxNode | None:
        """The syntax node's parent; None for the root or a syntax node outside the tree."""
        where = self._where.get(id(node))
        return None if where is None else where[0]

    def location(self, node: SyntaxNode) -> tuple[SyntaxNode, str, int | None] | None:
        """The syntax node's parent, the property holding it, and its index in that property if it is a list."""
        return self._where.get(id(node))

    def ancestors(self, node: SyntaxNode) -> Iterator[SyntaxNode]:
        """The syntax node's parent, its parent's parent, and so on to the root."""
        parent = self.parent(node)
        while parent is not None:
            yield parent
            parent = self.parent(parent)

    def path(self, node: SyntaxNode) -> str:
        """The path from the root to the syntax node, such as 'items[0].body.items[2]'; '' for the root."""
        parts: list[str] = []
        where = self._where.get(id(node))
        while where is not None:
            parent, name, index = where
            parts.append(name if index is None else f"{name}[{index}]")
            where = self._where.get(id(parent))
        return ".".join(reversed(parts))

    def replace(self, node: SyntaxNode, replacement: SyntaxNode | list[SyntaxNode] | None) -> None:
        """Puts `replacement` where `node` is: a syntax node, None to empty a single property or remove from a list, or
        a list of syntax nodes to splice into a list."""
        where = self._where.get(id(node))
        if where is None:
            raise ValueError("the syntax node has no parent in this tree")
        parent, name, index = where
        added = replacement if isinstance(replacement, list) else [] if replacement is None else [replacement]
        if index is None:
            if isinstance(replacement, list):
                raise TypeError(f"{parent.KIND}.{name} holds one syntax node, not a list")
            setattr(parent, name, replacement)
        else:
            getattr(parent, name)[index:index + 1] = added
        del self._where[id(node)]
        for item in added:
            for descendant in walk(item):
                for n, j, child in children(descendant):
                    self._where[id(child)] = (descendant, n, j)
        if index is None:
            for item in added:
                self._where[id(item)] = (parent, name, None)
        else:
            for i, item in enumerate(getattr(parent, name)):
                self._where[id(item)] = (parent, name, i)

    def remove(self, node: SyntaxNode) -> None:
        """Takes `node` out of the tree: empties its property, or removes it from its list."""
        self.replace(node, None)


class Visitor:
    """Walks a tree by kind: `visit(node)` calls `visit_<Kind>(node)` if the visitor defines it, and otherwise
    `generic_visit(node)`, which visits the syntax node's children in property order."""

    def visit(self, node: SyntaxNode) -> Any:
        return getattr(self, f"visit_{node.KIND}", self.generic_visit)(node)

    def generic_visit(self, node: SyntaxNode) -> Any:
        for _, _, child in children(node):
            self.visit(child)
        return None


class Transformer(Visitor):
    """Rewrites a tree by kind, in place: `visit` returns what replaces the syntax node, which `generic_visit` stores.
    It returns the syntax node itself to keep it, another syntax node to replace it, None to remove it (from a list, or
    emptying its property) or, in a list, a list of syntax nodes to splice in."""

    def generic_visit(self, node: SyntaxNode) -> Any:
        for prop in node.PROPERTIES:
            if not isinstance(prop, Child):
                continue
            value = getattr(node, prop.name)
            if prop.many:
                items: list[SyntaxNode] = []
                for child in value:
                    result = self.visit(child)
                    if isinstance(result, list):
                        items.extend(result)
                    elif result is not None:
                        items.append(result)
                setattr(node, prop.name, items)
            elif value is not None:
                result = self.visit(value)
                if isinstance(result, list):
                    raise TypeError(f"{node.KIND}.{prop.name} holds one syntax node, not a list")
                setattr(node, prop.name, result)
        return node
