"""Definitions: what a program declares, organized by meaning rather than by syntax.

A program declares entities (namespaces, classes, functions, variables, ...) in scopes. Each `Entity` records the
syntax nodes that declare it and the one that defines it; each `Scope` maps names to the entities declared in it and
knows where unqualified lookup goes next. A language builds a `Program` from its trees (for Ccpp,
`Ccpp.Definitions.define`), and every language's programs are read through these classes.

Lookup follows what every language shares:

- A scope finds a name among its own declarations, then in its *transparent* scopes, whose names are its own (C++
  inline and unnamed namespaces, unscoped enumerations, anonymous unions), then in its *bases* (a class's base
  classes).
- Unqualified lookup (`Scope.resolve`) tries a scope, then the scopes its using-directives name, then its parent,
  outwards to the global scope.
- Qualified lookup (`Scope.qualified`) resolves each qualifier to a scope, following aliases, then finds the last name
  in it.

Entities are found by name only: choosing among overloads, and names that depend on types, are not resolved.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

__all__ = ["Entity", "Scope", "Program"]


class Entity:
    """Something a program declares. `kind` names what it is in its language ('namespace', 'class', 'function',
    ...); `name` is None for an unnamed entity. `parent` is the scope it is declared in, and `scope` its own members,
    for an entity that has them. `declarations` are the nodes that declare it, in source order, and `definition` the
    one that defines it, if any. `signature` tells overloaded functions apart, and `target` is what an alias names."""

    def __init__(self, kind: str, name: str | None, parent: Scope | None):
        self.kind, self.name, self.parent = kind, name, parent
        self.scope: Scope | None = None
        self.declarations: list[Any] = []
        self.definition: Any = None
        self.signature: str | None = None
        self.target: Entity | None = None

    def qualified_name(self) -> str:
        """The names of the entity and the named entities enclosing it, outermost first, joined by its scope's
        separator, such as 'geo::v1::Point' or 'shapes.Point.area'. Unnamed entities are left out."""
        parts: list[str] = []
        entity: Entity | None = self
        while entity is not None:
            if entity.name is not None:
                parts.append(entity.name)
            entity = entity.parent.owner if entity.parent is not None else None
        return (self.parent.separator if self.parent is not None else "::").join(reversed(parts))

    def resolved(self) -> Entity:
        """The entity itself, or for an alias the entity it names, followed through aliases of aliases."""
        entity, seen = self, set()
        while entity.target is not None and id(entity) not in seen:
            seen.add(id(entity))
            entity = entity.target
        return entity

    def __repr__(self) -> str:
        return f"<{self.kind} {self.qualified_name() or '(unnamed)'}>"


class Scope:
    """A region of a program where names are declared: `kind` names it in its language ('namespace', 'class',
    'block', ...), `owner` is the entity whose members it holds (None for blocks and the global scope), `parent` the
    enclosing scope, and `node` the syntax node that opens it. Qualified names join names with `separator`: by default
    the parent's, and '::' without a parent."""

    def __init__(self, kind: str, owner: Entity | None, parent: Scope | None, node: Any = None,
                 separator: str | None = None):
        self.kind, self.owner, self.parent, self.node = kind, owner, parent, node
        self.separator = separator if separator is not None else parent.separator if parent is not None else "::"
        self.names: dict[str, list[Entity]] = {}
        self.transparent: list[Scope] = []
        self.using: list[Scope] = []
        self.bases: list[Scope] = []

    def declare(self, entity: Entity, name: str | None = None) -> Entity:
        """Makes `entity` found by `name` (by default its own) in this scope."""
        key = entity.name if name is None else name
        if key is not None:
            found = self.names.setdefault(key, [])
            if entity not in found:
                found.append(entity)
        return entity

    def entities(self) -> list[Entity]:
        """The entities found by name in this scope itself, in the order they were first declared."""
        out: list[Entity] = []
        for found in self.names.values():
            out.extend(e for e in found if e not in out)
        return out

    def lookup(self, name: str) -> list[Entity]:
        """The entities `name` names in this scope: its own, its transparent scopes', or failing those its bases'."""
        found = self._own(name, set())
        if found:
            return found
        for base in self.bases:
            found = base.lookup(name)
            if found:
                return found
        return []

    def _own(self, name: str, seen: set[int]) -> list[Entity]:
        if id(self) in seen:
            return []
        seen.add(id(self))
        found = list(self.names.get(name, []))
        for scope in self.transparent:
            found.extend(e for e in scope._own(name, seen) if e not in found)
        return found

    def resolve(self, name: str) -> list[Entity]:
        """Unqualified lookup: the entities `name` names here, in the namespaces this scope's using-directives name,
        or in an enclosing scope, the nearest first."""
        scope: Scope | None = self
        while scope is not None:
            found = scope.lookup(name)
            for used in scope.using:
                found.extend(e for e in used.lookup(name) if e not in found)
            if found:
                return found
            scope = scope.parent
        return []

    def qualified(self, names: list[str], from_global: bool = False) -> list[Entity]:
        """Qualified lookup of `a::b::c` (`names` ['a', 'b', 'c']) from this scope, or from the global scope with
        `from_global`: each qualifier must name an entity with a scope, an alias of one included."""
        if not names:
            return []
        scope: Scope | None = self.root() if from_global else None
        for name in names[:-1]:
            found = scope.lookup(name) if scope is not None else self.resolve(name)
            scopes = [e.resolved().scope for e in found if e.resolved().scope is not None]
            if not scopes:
                return []
            scope = scopes[0]
        return scope.lookup(names[-1]) if scope is not None else self.resolve(names[-1])

    def root(self) -> Scope:
        scope = self
        while scope.parent is not None:
            scope = scope.parent
        return scope

    def __repr__(self) -> str:
        owner = f" {self.owner.qualified_name()}" if self.owner is not None and self.owner.name is not None else ""
        return f"<{self.kind} scope{owner}>"


class Program:
    """What a set of trees declares: the global scope, every entity, and for each node the entity it declares and
    the scope it is in."""

    def __init__(self, root: Scope):
        self.root = root
        self.macros = Scope("macros", None, None)
        self._entities: list[Entity] = []
        self._declares: dict[int, Entity] = {}
        self._scopes: dict[int, Scope] = {}

    def add(self, entity: Entity) -> Entity:
        """Records a new entity."""
        self._entities.append(entity)
        return entity

    def declares(self, node: Any, entity: Entity) -> None:
        """Records that `node` declares `entity`."""
        self._declares[id(node)] = entity

    def located(self, node: Any, scope: Scope) -> None:
        """Records that `node` is in `scope`."""
        self._scopes.setdefault(id(node), scope)

    def entities(self) -> Iterator[Entity]:
        """Every entity, in the order the program first declares them."""
        return iter(self._entities)

    def entity_of(self, node: Any) -> Entity | None:
        """The entity `node` declares or defines; None if it declares none."""
        return self._declares.get(id(node))

    def scope_of(self, node: Any) -> Scope | None:
        """The innermost scope `node` is in; None for a node outside the program's trees."""
        return self._scopes.get(id(node))

    def lookup(self, name: str, at: Any = None) -> list[Entity]:
        """The entities a name written as text names, such as 'std::vector' or '::main', where `at` is (by default,
        in the global scope). Its parts are joined by the global scope's separator."""
        scope = self.scope_of(at) if at is not None else None
        scope = scope or self.root
        parts = name.split(self.root.separator)
        if parts[0] == "":
            return scope.qualified(parts[1:], from_global=True)
        return scope.qualified(parts)
