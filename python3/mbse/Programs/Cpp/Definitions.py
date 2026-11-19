"""Definitions: the names a C++ translation unit declares, in the scopes C++ gives them, read from the store.

As the user decided for the port ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../docs/proposals/port/README.md#decided),
6): entities, name resolution and the program stay code over the stored tree, computed on demand and never stored, and
a use of a name is anchored on its statement and the term's path, since a term is a value. This module is
`Programs.C.Definitions` over C++'s kinds and terms, its definer extended with what C++ adds, as C++'s kinds reuse C's
("2(a)"):

- `define(store, path)`, `define_file(store, unit)`, `referents(program, at)`, `Anchor` and `Program` are C's
  (`Programs.C.Definitions`), each place an `Anchor` whose text identifies it within its unit
  (`body[1].body.body[0]:declarators[0].initializer`), and a `Program` whose qualified names join with `::`
  (`geo::v1::Point`), its global scope a 'namespace'.
- `MEANINGS`: the name space each kind of entity is in.

Its entities have these kinds, ported from mbse-programs 0.3's (`Ccpp/Definitions.py`):

- 'namespace' (a namespace reopened is one entity) and 'namespace alias', whose `target` is the namespace;
- 'class' (a class, a struct or a union), 'enumeration' and 'enumerator';
- 'function', one entity per signature (its parameters' types and its qualifiers, `(int, const char *) const`, its
  `signature`), its declarations and its definition found by name and signature, an out-of-line one too (`int A::f()
  { ... }`);
- 'variable', 'field' (a non-static data member), 'parameter' (of a function, a prototype, a lambda or a `requires`)
  and 'template parameter';
- 'type alias' (`typedef` and `using`), 'concept', 'using declaration' (a using-declarator naming nothing the unit
  declares), 'label', and 'macro' (in `Program.macros`, as C's).

Scopes are 0.3's: 'namespace' (the unit, a namespace), 'class', 'enumeration' (a scoped one's, and an unscoped one's,
transparent to its enclosing scope), 'function', 'block', 'template', 'lambda' and 'requires'; and C's 'prototype', a
function declarator's parameters but a definition's own. Unnamed and inline namespaces, unscoped enumerations and
anonymous unions are transparent to their enclosing scope; using-directives and `using enum` are followed; a class
looks names up in its bases; a qualified name (`std::vector`, `::f`) is looked up qualified. A name is in one of three
name spaces (`Program.space_of`): 'ordinary', every name C++ declares, 'label' and 'macro', as C's.

Where C++ adds to C's rules, each *(agent)*, as 0.3 decided where it did:

- **A template's parameters are in a scope of its own**, enclosing what it declares: the declaration's name binds in
  the scope the template stands in, its parts and the scopes it opens (a class's members, a function's body) see the
  parameters. A template declares the entity its declaration declares. An explicit or a partial specialization
  (`template <> struct Traits<int>`) is a declaration of its primary template's entity, as 0.3 had it.
- **Out-of-line definitions**: a qualified declarator's name (`int Vector<T>::convert()`, `int A::count = 0;`) binds
  in the scope its qualifiers name, merging with the member declared there; the function's scope is nested in that
  class's, so its members are found from its body.
- **Classes**: a class's members, its nested types and member functions included, are in its scope; its bases, its
  attributes and its name's template arguments are evaluated where it stands; a member's default initializer, a
  bit-field's width and a member function's body see the class's members. An anonymous union's members are its
  enclosing scope's, as an anonymous struct's or union's member's are, as C's.
- **Friends declare nothing**, as 0.3: a friend's class and functions are uses of their names.
- **An explicit instantiation declares nothing**: its class is a use of the template's name.
- **Statements that declare** (`if`, `switch`, `while`, `for`, a range-based `for`) each open a block, which their
  initializer's and their condition's declarations are in; a handler (`catch`) opens one, its parameter a 'variable'.
- **Lambdas** open a 'lambda' scope: an init-capture binds a 'variable' there, a simple capture is a use of the
  enclosing scope's name, its template parameters and its parameters bind there, and its block is a block within it;
  its labels are its own.
- **A namespace's names** nest (`namespace a::inline b`), each binding in the one before; an `export`ed declaration
  and a linkage specification's declarations bind in the scope they stand in; a module's or an import's name is a
  dotted string (`geo.shapes`), naming no entity of the unit.
- **Uses of names**: an identifier where a term, a type or a declarator's qualifier holds a name; a qualified name, a
  template's name and an operator's, a conversion's, a destructor's or a literal operator's name, each one name at its
  place, written as text (`std::vector`, `Point`, `operator+`, `operator int`, `~Point`, `operator""_km`), the
  template arguments within it visited as uses. A member's name (`a.b`'s `b`) and a designator's are not visited, as
  C's.

What it does not do, as 0.3: choose among overloads, resolve names that depend on types (members, dependent names),
tell a typedef name from other names where the parser did not (`Parse`, item 48), or bind a structured binding's
names, which mbse-expressions' C++ cannot hold yet (`Parse`, item 44).
"""

from __future__ import annotations

from typing import Any

from mbse.Expressions.Framework import Objects
from mbse.Schemas.Framework import Plain, References

from ..C import Definitions as C
from ..C.Definitions import Anchor, _branch, _keywords, _many, _rank
from ..Framework.Definitions import Entity, Scope
from ..Framework.Model import WORKSPACE
from . import Print, Statements

__all__ = ["Anchor", "MEANINGS", "Program", "define", "define_file", "referents"]

ORDINARY, LABEL, MACRO = "ordinary", "label", "macro"

MEANINGS: dict[str, str] = {
    "namespace": ORDINARY, "namespace alias": ORDINARY, "class": ORDINARY, "enumeration": ORDINARY,
    "enumerator": ORDINARY, "function": ORDINARY, "variable": ORDINARY, "field": ORDINARY, "parameter": ORDINARY,
    "template parameter": ORDINARY, "type alias": ORDINARY, "concept": ORDINARY, "using declaration": ORDINARY,
    "label": LABEL, "macro": MACRO,
}
"""The name space each kind of entity is in."""

_HOLDERS = frozenset(f"{Statements.LANGUAGE}.{kind}" for kind in (
    *Statements.KINDS, "Error", "MemberList", "Group", "MemberGroup"))
"""The schemas that have a statement's place: statements, declarations, clauses, members, invalid syntax and the parts
that hold them."""
_SEPARATOR = "::"


class Program(C.Program):
    """What a unit declares: C's `Program` (`Programs.C.Definitions.Program`), its global scope a 'namespace' whose
    qualified names join with `::`."""

    def __init__(self, path: str, root: Anchor):
        super().__init__(path, root)
        self.root = Scope("namespace", None, None, root, separator=_SEPARATOR)
        self.macros = Scope("macros", None, None, root, separator=_SEPARATOR)

    def declared_within(self, at: Anchor) -> Entity | None:
        """The first entity a place declares at `at` or within its statement (its declarator, its specifier)."""
        text = str(at)
        return next((entity for key, entity in self._declares.items() if key == text or key.startswith(
            f"{text}:")), None)


# --- Reading ---


def _name(value: Any) -> str | None:
    """The text of a name: an identifier's spelling, a qualified name's parts joined by `::` (from `::` where it starts
    with it), a template's name without its arguments, and an operator's, a conversion's, a destructor's or a literal
    operator's as C++ writes it; None for a qualifier no text names (`decltype(x)`)."""
    tag, record = _branch(value)
    props = Objects.properties(record)
    if tag == "identifier":
        return props["spelling"]  # type: ignore[no-any-return]
    if tag == "templateid":
        return _name(props["name"])
    if tag == "qualifiedname":
        parts = [_name(q) for q in _many(props.get("qualifiers"))] + [_name(props["name"])]
        if None in parts:
            return None
        return ("::" if props.get("global_scope") else "") + _SEPARATOR.join(parts)  # type: ignore[arg-type]
    if tag == "destructorname":
        inner = _name(props["type"])
        return None if inner is None else f"~{inner}"
    if tag in ("operatorname", "conversionname", "literaloperatorname"):
        return Print.Printer().written(value)
    return None  # a decltype


def _split(name: str) -> tuple[list[str], bool]:
    """A qualified name's parts, and whether it starts with `::`."""
    parts = name.split(_SEPARATOR)
    return (parts[1:], True) if parts[0] == "" else (parts, False)


def _qualified(scope: Scope, name: str) -> list[Entity]:
    """The entities a name names from `scope`: qualified lookup of a qualified name, unqualified of any other."""
    parts, from_global = _split(name)
    if len(parts) == 1 and not from_global:
        return scope.resolve(name)
    return scope.qualified(parts, from_global=from_global)


def _function(declarator: Any) -> dict[str, Any] | None:
    """The properties of the function's declarator nearest the name a declarator declares, but parentheses; None where
    it declares no function."""
    tag, record = _branch(declarator)
    props = Objects.properties(record)
    held = props.get("declarator")
    if held is None:
        return None
    if tag != "parenthesizeddeclarator" and C._named(held):
        return props if tag == "functiondeclarator" else None
    return _function(held)


def _shape(declarator: Any) -> str:
    """What an abstract declarator adds to its parameter's type, in a signature: `*`, `&`, `&&`, `[]`, `()`, `...`."""
    if declarator is None:
        return ""
    tag, record = _branch(declarator)
    props = Objects.properties(record)
    inner = _shape(props.get("declarator"))
    quals = "".join(" " + Objects.properties(_branch(q)[1])["keyword"] for q in _many(props.get("qualifiers")))
    return {"pointerdeclarator": f"*{quals}{inner}", "referencedeclarator": ("&&" if props.get("rvalue") else "&") +
            inner, "arraydeclarator": f"{inner}[]", "functiondeclarator": f"{inner}()",
            "packdeclarator": f"...{inner}"}.get(tag, inner)


def _signature(function: dict[str, Any]) -> str:
    """A function's parameters' types and its qualifiers, as written: `(int, const char *) const &`."""
    printer = Print.Printer()
    types = []
    for parameter in _many(function.get("parameters")):
        tag, record = _branch(parameter)
        props = Objects.properties(record)
        types.append("..." if tag == "ellipsisparameter" else " ".join(
            printer.written(s) for s in _many(props.get("specifiers"))) + _shape(props.get("declarator")))
    quals = "".join(" " + Objects.properties(_branch(q)[1])["keyword"] for q in _many(function.get("qualifiers")))
    reference = f" {function['ref_qualifier']}" if function.get("ref_qualifier") else ""
    return f"({', '.join(types)}){quals}{reference}"


def _declared(declarator: Any) -> Any:
    """The name a declarator declares, within its declarators; None for an abstract one."""
    tag, record = _branch(declarator)
    props = Objects.properties(record)
    if tag == "iddeclarator":
        return props["name"]
    return _declared(props["declarator"]) if "declarator" in props else None


# --- Defining ---


class _Definer(C._Definer):
    """C's definer (`Programs.C.Definitions._Definer`) over C++'s kinds and terms, and what C++ adds."""

    HOLDERS = _HOLDERS

    # Scopes and bindings

    def bind(self, scope: Scope, name: str, at: Anchor, kind: str) -> Entity:
        return self.bind_as(scope, name, at, kind, None)

    def bind_as(self, scope: Scope, name: str, at: Anchor, kind: str, signature: str | None) -> Entity:
        """Binds `name`, written at `at` in `scope`, as an entity of `kind` and `signature` (a function's): the one of
        that name, kind and signature in the scope it binds in, or a new one. A qualified name binds in the scope its
        qualifiers name, where they name one; any other but a template's parameter in the nearest scope that is no
        template's."""
        target, name = self.target(scope, name)
        while target.kind == "template" and kind != "template parameter":
            target = target.parent  # type: ignore[assignment]
        found = [e for e in target.names.get(name, []) if e.kind == kind and e.parent is target and (
            e.signature == signature)]
        if found:
            entity = found[0]
        else:
            entity = target.declare(self.program.add(Entity(kind, name, target)))
            entity.signature = signature
        entity.declarations.append(at)
        self.program.declares(at, entity)
        self.program.located(at, scope)
        self.program.written(at, name)
        return entity

    @staticmethod
    def target(scope: Scope, name: str) -> tuple[Scope, str]:
        """Where a declarator's name binds, and its last part: the scope a qualified name's qualifiers name, where they
        name one, or `scope`."""
        parts, from_global = _split(name)
        if len(parts) == 1 and not from_global:
            return scope, name
        if not parts[:-1]:
            return scope.root(), parts[-1]
        found = [e.resolved().scope for e in scope.qualified(parts[:-1], from_global=from_global)]
        scopes = [s for s in found if s is not None]
        return (scopes[0] if scopes else scope), parts[-1]

    @staticmethod
    def lexical(scope: Scope, entity: Entity | None) -> Scope:
        """The scope a scope `entity` opens is nested in: `scope`, where it binds there or in the scope a template's
        parameters enclose; the scope its qualifiers name, for an out-of-line definition."""
        if entity is None or entity.parent is None:
            return scope
        inner: Scope | None = scope
        while inner is not None and inner.kind == "template":
            inner = inner.parent
        return scope if entity.parent is inner else entity.parent

    @staticmethod
    def function_scope(scope: Scope) -> Scope:
        """The scope of the function or the lambda `scope` is in, where its labels are; the unit's, outside every
        one."""
        while scope.kind not in ("function", "lambda") and scope.parent is not None:
            scope = scope.parent
        return scope

    def resolved(self, scope: Scope, name: Any) -> list[Entity]:
        """The entities a name names from `scope`, as the unit declares them so far."""
        text = _name(name)
        return [] if text is None else _qualified(scope, text)

    # Names and terms

    def named(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """A qualified name, a template's name, or an operator's, a conversion's, a destructor's or a literal
        operator's: a use of its text at its place, the template arguments and the types within it visited."""
        text = _name(record)
        if text is not None:
            self.use(at, scope, text, space)
        self.within(record, props, scope, at)

    def within(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """What a name holds that is evaluated where it stands: a template's arguments, a conversion's type, and its
        qualifiers' own."""
        for name, value in props.items():
            place = at.at(name, _rank(record, name))
            if name in ("arguments", "type"):
                self.visit(value, scope, place, ORDINARY)
            elif name == "qualifiers":
                for i, qualifier in enumerate(value.values):
                    self.qualifier(qualifier, scope, place.at(i, i))
            elif name == "name" and _branch(value)[0] != "identifier":
                inner = _branch(value)[1]
                self.program.located(place, scope)
                self.within(inner, Objects.properties(inner), scope, place)

    def qualifier(self, value: Any, scope: Scope, at: Anchor) -> None:
        """A qualifier of a qualified name, which the name's text holds: its template arguments, or a decltype's
        expression, evaluated; an identifier, the name's own, is not visited."""
        tag, record = _branch(value)
        if tag == "templateid":
            self.program.located(at, scope)
            self.within(record, Objects.properties(record), scope, at)
        elif tag != "identifier":
            self.program.located(at, scope)
            self.fields(record, scope, at, ORDINARY)

    def lambda_(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """A lambda: its scope, its init-captures' names and its parameters bound there, its block within it."""
        inner = Scope("lambda", None, scope, at)
        for name, value in props.items():
            place = at.at(name, _rank(record, name))
            if name == "captures":
                for i, capture in enumerate(value.values):
                    self.capture(capture, scope, inner, place.at(i, i))
            elif name == "template_parameters":
                self.template_parameters(value, inner, place)
            elif name == "declarator":
                self.program.located(place, inner)
                _, declarator = _branch(value)
                for field, held in Objects.properties(declarator).items():
                    where = place.at(field, _rank(declarator, field))
                    if field == "parameters":
                        self.parameters(held, inner, where)
                    else:
                        self.visit(held, inner, where, ORDINARY)
            else:
                self.visit(value, inner, place, ORDINARY)

    def capture(self, value: Any, scope: Scope, inner: Scope, at: Anchor) -> None:
        """A lambda's capture: an init-capture's name a variable of the lambda's, its initializer evaluated where the
        lambda stands; a simple capture's name a use there."""
        tag, record = _branch(value)
        props = Objects.properties(record)
        self.program.located(at, scope)
        if tag == "initcapture":
            self.prop(record, props, "initializer", scope, at, ORDINARY)
            name = at.at("name", _rank(record, "name"))
            self.program.declares(at, self.bind(inner, Objects.properties(_branch(props["name"])[1])["spelling"],
                                                name, "variable"))
        else:
            self.fields(record, scope, at, ORDINARY)

    def requires_expression(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """A requires-expression: its parameters in a scope of its own, which its requirements see."""
        inner = Scope("requires", None, scope, at)
        for name, value in props.items():
            place = at.at(name, _rank(record, name))
            if name == "parameters":
                self.parameters(value, inner, place)
            else:
                self.visit(value, inner, place, ORDINARY)

    def specifier(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """A class's or an enumeration's specifier where it is no declaration's alone: with its body it declares its
        name; without, it uses it."""
        self.tag(record, props, scope, at, False)

    def tag(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, alone: bool) -> Scope | None:
        """A class's or an enumeration's specifier, in `scope`: with its body, or `alone` in its declaration (`class
        S;`), it declares its name there, or where its qualifiers name; without, it uses it. Its members, and its
        enumerators, are in a scope of its own, which it gives back (None for an enumeration's, or none)."""
        kind = "enumeration" if record.as_schema().name.endswith("EnumSpecifier") else "class"
        body, entity = props.get("body", False), None
        self.prop(record, props, "attributes", scope, at, ORDINARY)
        if "name" in props:
            place = at.at("name", _rank(record, "name"))
            text = _name(props["name"])
            if (body or alone) and text is not None:
                entity = self.bind(scope, text, place, kind)
                self.program.declares(at, entity)
                if not body:
                    self.declarations.add(str(place))
                _, held = _branch(props["name"])
                self.within(held, Objects.properties(held), scope, place)  # a specialization's arguments
            else:
                self.visit(props["name"], scope, place, ORDINARY)
        elif body:
            entity = self.program.add(Entity(kind, None, scope))
            entity.declarations.append(at)
            self.program.declares(at, entity)
        self.prop(record, props, "base", scope, at, ORDINARY)
        parent = self.lexical(scope, entity)
        if kind == "enumeration":
            if body:
                members = Scope("enumeration", entity, parent, at)
                if entity is not None and entity.scope is None:
                    entity.scope = members
                if props.get("key") == "enum":  # unscoped: its enumerators are its enclosing scope's too
                    (entity.parent if entity is not None else scope).transparent.append(members)  # type: ignore[union-attr]
                self.prop(record, props, "enumerators", members, at, ORDINARY)
            return None
        members = Scope("class", entity, parent, at)
        bases = at.at("bases", _rank(record, "bases")) if "bases" in props else None
        for i, base in enumerate(_many(props.get("bases"))):
            self.visit(base, scope, bases.at(i, i), ORDINARY)  # type: ignore[union-attr]
            fields = Objects.properties(_branch(base)[1])
            for found in self.resolved(scope, fields["type"]):
                resolved = found.resolved()
                if resolved.kind == "class" and resolved.scope is not None and resolved.scope not in members.bases:
                    members.bases.append(resolved.scope)
        if "members" not in props:
            return None
        where = at.at("members", _rank(record, "members")).opened()
        members.node = where
        if entity is not None and entity.scope is None:
            entity.scope = members
        if "name" not in props and alone:  # an anonymous union's members are its enclosing scope's
            scope.transparent.append(members)
        self.member_list(_branch(props["members"])[1], members, where)
        return members

    def template_parameters(self, held: Any, scope: Scope, at: Anchor) -> None:
        """A template's parameters, each binding its name in `scope`, a template's or a lambda's, as a template
        parameter: a type's, a template's (its own parameters in a scope of their own) or a constant's."""
        self.program.located(at, scope)
        for i, parameter in enumerate(held.values):
            each = at.at(i, i)
            self.program.located(each, scope)
            tag, record = _branch(parameter)
            props = Objects.properties(record)
            if tag == "parameterdeclaration":
                self.parameter(record, props, scope, each, "template parameter")
                continue
            for name, value in props.items():
                place = each.at(name, _rank(record, name))
                if name == "name":
                    self.program.declares(each, self.bind(scope, Objects.properties(_branch(value)[1])["spelling"],
                                                          place, "template parameter"))
                elif name == "parameters":  # a template template parameter's, which name nothing outside it
                    self.template_parameters(value, Scope("template", None, scope, each), place)
                else:
                    self.visit(value, scope, place, ORDINARY)

    # Declarators

    def declarator(self, value: Any, scope: Scope, at: Anchor, bind: C.Binding, function: Scope | None) -> None:
        """C's, a name C++'s: its text bound, the template arguments and the types within it evaluated."""
        self.program.located(at, scope)
        tag, record = _branch(value)
        props = Objects.properties(record)
        for name, held in props.items():
            place = at.at(name, _rank(record, name))
            if name == "name":
                text = _name(held)
                if text is not None:
                    bind(text, place)
                _, inner = _branch(held)
                self.within(inner, Objects.properties(inner), scope, place)
            elif name == "declarator":
                self.declarator(held, scope, place, bind, function)
            elif name == "parameters":
                inner_scope = function if function is not None and C._named(props["declarator"]) else Scope(
                    "prototype", None, scope, at)
                self.parameters(held, inner_scope, place)
            else:
                self.visit(held, scope, place, ORDINARY)

    def parameters(self, held: Any, scope: Scope, at: Anchor) -> None:
        """A function's or a lambda's parameters, each binding its name in `scope`, where its parts and its default are
        evaluated too."""
        self.program.located(at, scope)
        for i, parameter in enumerate(held.values):
            each = at.at(i, i)
            self.program.located(each, scope)
            tag, record = _branch(parameter)
            if tag == "parameterdeclaration":
                self.parameter(record, Objects.properties(record), scope, each, "parameter")

    def parameter(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, kind: str) -> None:
        """A parameter's declaration, its name bound in `scope` as an entity of `kind`."""
        self.prop(record, props, "attributes", scope, at, ORDINARY)
        self.prop(record, props, "specifiers", scope, at, ORDINARY)
        if "declarator" in props:
            self.declarator(props["declarator"], scope, at.at("declarator", _rank(record, "declarator")),
                            lambda name, place: self.program.declares(at, self.bind(scope, name, place, kind)), None)
        self.prop(record, props, "default", scope, at, ORDINARY)

    TERMS: dict[str, Any] = {}

    # Statements

    def declaration(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.declare(node, props, scope, at, "declarators")

    def member_declaration(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:  # type: ignore[override]
        """A member declaration, in its class's scope `scope`: its members, its nested types and its member functions
        declared there."""
        self.declare(node, props, scope, at, "declarators")

    def declare(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor,  # type: ignore[override]
                property: str) -> None:
        """A declaration or a member declaration: its specifiers and attributes in `scope`, where each declarator binds
        its name, as an entity of the kind its keywords, its declarator and its scope give; a declaration of nothing
        but a class or an enumeration (`class S;`) declares it, and a friend's nothing."""
        keywords = _keywords(props.get("specifiers"))
        friend = "friend" in keywords
        self.prop(node, props, "attributes", scope, at, ORDINARY)
        specifiers = at.at("specifiers", _rank(node, "specifiers"))
        alone = property not in props
        for i, specifier in enumerate(_many(props.get("specifiers"))):
            tag, record = _branch(specifier)
            if tag in ("classspecifier", "enumspecifier") and not friend:
                self.program.located(specifiers.at(i, i), scope)
                self.tag(record, Objects.properties(record), scope, specifiers.at(i, i), alone)
            else:
                self.visit(specifier, scope, specifiers.at(i, i), ORDINARY)
        declarators = at.at(property, _rank(node, property)) if not alone else at
        for i, declarator in enumerate(_many(props.get(property))):
            each = declarators.at(i, i)
            self.program.located(each, scope)
            fields = Objects.properties(declarator)
            if "declarator" in fields:
                self.declarator(fields["declarator"], scope, each.at("declarator", _rank(declarator, "declarator")),
                                self.binder(scope, each, keywords, fields["declarator"], friend, fields), None)
            for name in ("requires", "bitfield", "initializer"):
                self.prop(declarator, fields, name, scope, each, ORDINARY)

    def binder(self, scope: Scope, each: Anchor, keywords: set[str], declarator: Any, friend: bool,
               fields: dict[str, Any]) -> C.Binding:
        """What binds a declarator's name: as a use, a friend's; as a type alias, a `typedef`'s; as a function (with
        its signature), a function's declarator; as a field, a class's non-static data member's; as a variable,
        any other, a block's `extern` one the unit's, as C's."""
        function = _function(declarator)

        def bind(name: str, place: Anchor) -> None:
            if friend:
                self.use(place, scope, name, ORDINARY)
                return
            target, last = self.target(scope, name)
            if "typedef" in keywords:
                kind = "type alias"
            elif function is not None:
                kind = "function"
            else:
                kind = "field" if target.kind == "class" and "static" not in keywords else "variable"
                if target is not scope:  # an out-of-line definition: the member declared before
                    kind = next((e.kind for e in target.names.get(last, []) if e.kind in ("field", "variable")), kind)
            linked = scope.kind not in ("namespace", "class", "prototype", "template") and kind in (
                "function", "variable") and (kind == "function" or "extern" in keywords)
            signature = _signature(function) if function is not None else None
            if linked:  # found from `scope` too, where it is written
                self.program.located(place, scope)
            entity = self.bind_as(self.program.root if linked else scope, name, place, kind, signature)
            if linked:
                scope.declare(entity)
            self.program.declares(each, entity)
            only = kind == "function" or "extern" in keywords and "initializer" not in fields or (
                target.kind == "class" and kind == "variable" and not keywords & {"inline", "constexpr"} and (
                    "initializer" not in fields))
            if only:
                self.declarations.add(str(place))

        return bind

    def function_definition(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """A function's definition: its name in `scope`, or where its qualifiers name, and the scope it opens, holding
        its parameters, its body's declarations and its labels, nested in its class's for a member's; its member
        initializers and its body evaluated there. A friend's declares nothing."""
        keywords = _keywords(props.get("specifiers"))
        friend = "friend" in keywords
        self.prop(node, props, "attributes", scope, at, ORDINARY)
        specifiers = at.at("specifiers", _rank(node, "specifiers"))
        for i, specifier in enumerate(_many(props.get("specifiers"))):
            self.visit(specifier, scope, specifiers.at(i, i), ORDINARY)
        function = _function(props["declarator"])
        name = _declared(props["declarator"])
        text = None if name is None else _name(name)
        target, last = self.target(scope, text) if text is not None else (scope, None)
        parent = scope if target is scope else target
        inner = Scope("function", None, parent, at)

        def bind(name: str, place: Anchor) -> None:
            if friend:
                self.use(place, scope, name, ORDINARY)
                return
            entity = self.bind_as(scope, name, place, "function", None if function is None else _signature(function))
            self.program.declares(at, entity)
            inner.owner, entity.scope = entity, inner

        self.declarator(props["declarator"], scope, at.at("declarator", _rank(node, "declarator")), bind, inner)
        for name in ("requires", "initializers"):
            self.prop(node, props, name, inner, at, ORDINARY)
        body = at.child("body", None, _rank(node, "body"))
        tag, record = _branch(props["body"])
        if tag == "compoundstatement":
            self.program.located(body, inner)
            self.children(record, inner, body)
        elif tag == "trystatement":  # a function-try-block
            self.statement(record, inner, body)
        else:  # `= default` or `= delete`, a part
            self.program.located(at.at("body", _rank(node, "body")), inner)

    def handler(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """A `catch`: its parameter a variable of a block of its own, which its body is."""
        inner = Scope("block", None, scope, at)
        place = at.at("parameter", _rank(node, "parameter"))
        self.program.located(place, inner)
        tag, record = _branch(props["parameter"])
        if tag == "parameterdeclaration":
            self.parameter(record, Objects.properties(record), inner, place, "variable")
        body = at.child("body", None, _rank(node, "body"))
        self.program.located(body, inner)
        self.children(props["body"], inner, body)

    def namespace(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """A namespace's definition: each of its names a namespace within the one before, an inline one transparent to
        it, an unnamed one transparent to the scope it stands in (every unnamed one of a scope one entity); its body in
        the innermost."""
        self.prop(node, props, "attributes", scope, at, ORDINARY)
        current = scope
        names = _many(props.get("names"))
        if not names:
            entity = next((s.owner for s in scope.transparent if s.kind == "namespace" and s.owner is not None and (
                s.owner.name is None)), None)
            if entity is None:
                entity = self.program.add(Entity("namespace", None, scope))
                entity.scope = Scope("namespace", entity, scope, at)
                scope.transparent.append(entity.scope)
            entity.declarations.append(at)
            self.program.declares(at, entity)
            current = entity.scope  # type: ignore[assignment]
        place = at.at("names", _rank(node, "names"))
        for i, part in enumerate(names):
            each = place.at(i, i)
            self.program.located(each, current)
            fields = Objects.properties(part)
            entity = self.bind(current, Objects.properties(_branch(fields["name"])[1])["spelling"], each.at(
                "name", _rank(part, "name")), "namespace")
            self.program.declares(at, entity)
            if entity.scope is None:
                entity.scope = Scope("namespace", entity, current, at)
            if (fields.get("inline") or props.get("inline") and i == len(names) - 1) and (
                    entity.scope not in current.transparent):
                current.transparent.append(entity.scope)
            current = entity.scope
        if "body" in props:
            self.child(node, "body", props["body"], current, at)

    def namespace_alias(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        entity = self.bind(scope, Objects.properties(_branch(props["name"])[1])["spelling"], at.at(
            "name", _rank(node, "name")), "namespace alias")
        self.program.declares(at, entity)
        found = [e for e in self.resolved(scope, props["target"]) if e.resolved().kind == "namespace"]
        entity.target = found[0] if found else None
        self.prop(node, props, "target", scope, at, ORDINARY)

    def using_directive(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """`using namespace n;`: the namespace's names found from `scope`."""
        self.parts(node, props, scope, at)
        for entity in self.resolved(scope, props["name"]):
            target = entity.resolved().scope
            if target is not None and target not in scope.using:
                scope.using.append(target)

    def using_declaration(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """`using a::b;`: each declarator's entities found from `scope` by their name; a 'using declaration' where the
        unit declares none."""
        place = at.at("declarators", _rank(node, "declarators"))
        for i, declarator in enumerate(_many(props.get("declarators"))):
            each = place.at(i, i)
            self.program.located(each, scope)
            fields = Objects.properties(declarator)
            name = each.at("name", _rank(declarator, "name"))
            found = self.resolved(scope, fields["name"])
            self.visit(fields["name"], scope, name, ORDINARY)
            if found:
                for entity in found:
                    scope.declare(entity)
                self.program.declares(each, found[0])
            else:
                text = _name(fields["name"])
                self.program.declares(each, self.bind(scope, _split(text)[0][-1] if text else "", name,
                                                      "using declaration"))

    def using_enum(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """`using enum E;`: its enumerators found from `scope`."""
        self.parts(node, props, scope, at)
        for entity in self.resolved(scope, props["type"]):
            if entity.kind == "enumeration" and entity.scope is not None and entity.scope not in scope.transparent:
                scope.transparent.append(entity.scope)

    def alias(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.program.declares(at, self.bind(scope, Objects.properties(_branch(props["name"])[1])["spelling"], at.at(
            "name", _rank(node, "name")), "type alias"))
        self.prop(node, props, "attributes", scope, at, ORDINARY)
        self.prop(node, props, "type", scope, at, ORDINARY)

    def concept(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.program.declares(at, self.bind(scope, Objects.properties(_branch(props["name"])[1])["spelling"], at.at(
            "name", _rank(node, "name")), "concept"))
        self.prop(node, props, "attributes", scope, at, ORDINARY)
        self.prop(node, props, "constraint", scope, at, ORDINARY)

    def template(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """A template: its parameters in a scope of its own, which its `requires` and its declaration see; it declares
        what its declaration declares."""
        inner = Scope("template", None, scope, at)
        if "parameters" in props:
            self.template_parameters(props["parameters"], inner, at.at("parameters", _rank(node, "parameters")))
        self.prop(node, props, "requires", inner, at, ORDINARY)
        place = at.child("declaration", None, _rank(node, "declaration"))
        self.statement(_branch(props["declaration"])[1], inner, place)
        declared = self.program.declared_within(place)
        if declared is not None:
            self.program.declares(at, declared)

    def instantiation(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """An explicit instantiation: its declaration's names are uses of the template's."""
        place = at.child("declaration", None, _rank(node, "declaration"))
        self.program.located(place, scope)
        record = _branch(props["declaration"])[1]
        fields = Objects.properties(record)
        specifiers = place.at("specifiers", _rank(record, "specifiers"))
        for i, specifier in enumerate(_many(fields.get("specifiers"))):
            self.visit(specifier, scope, specifiers.at(i, i), ORDINARY)
        declarators = place.at("declarators", _rank(record, "declarators")) if "declarators" in fields else place
        for i, declarator in enumerate(_many(fields.get("declarators"))):
            each = declarators.at(i, i)
            self.program.located(each, scope)
            self.declarator(Objects.properties(declarator)["declarator"], scope, each.at(
                "declarator", _rank(declarator, "declarator")), lambda name, where: self.use(
                    where, scope, name, ORDINARY), None)

    def member_list(self, node: Any, members: Scope, at: Anchor) -> None:
        """A class's members, or a group of them, each in its scope `members`."""
        self.program.located(at, members)
        rank = _rank(node, "members")
        for i, element in enumerate(_many(Objects.properties(node).get("members"))):
            self.statement(_branch(element)[1], members, at.child("members", i, rank))

    STATEMENTS: dict[str, Any] = {}


_Definer.TERMS.update({
    **C._Definer.TERMS,
    **{tag: _Definer.named for tag in (
        "qualifiedname", "templateid", "operatorname", "conversionname", "destructorname", "literaloperatorname")},
    "lambdaexpression": _Definer.lambda_, "requiresexpression": _Definer.requires_expression,
    "classspecifier": _Definer.specifier, "enumspecifier": _Definer.specifier,
})

_Definer.STATEMENTS.update({
    **C._Definer.STATEMENTS,
    **{kind: _Definer.loop for kind in ("IfStatement", "SwitchStatement", "WhileStatement", "ForStatement",
                                        "RangeForStatement")},
    "SimpleDeclaration": _Definer.declaration, "MemberDeclaration": _Definer.member_declaration,
    "FunctionDefinition": _Definer.function_definition, "Handler": _Definer.handler,
    "NamespaceDefinition": _Definer.namespace, "NamespaceAliasDefinition": _Definer.namespace_alias,
    "UsingDirective": _Definer.using_directive, "UsingDeclaration": _Definer.using_declaration,
    "UsingEnumDeclaration": _Definer.using_enum, "AliasDeclaration": _Definer.alias,
    "ConceptDefinition": _Definer.concept, "TemplateDeclaration": _Definer.template,
    "ExplicitInstantiation": _Definer.instantiation,
})


def define(store: Any, path: str) -> Program:
    """The entities the unit at `path` declares, in their scopes (`define_file`), read within a transaction of its own,
    so called with none open on `store`; LookupError where the workspace holds no file at `path`."""
    with store.transaction():
        return define_file(store, store.singleton(WORKSPACE).files({"path": path}))  # LookupError, where it holds none


def define_file(store: Any, unit: Any) -> Program:
    """The entities a unit declares, in their scopes: its visitor, a `Programs.Cpp.TranslationUnit` of `store`, read
    within the caller's transaction. What it gives back holds no visitor, so it outlives the transaction."""
    reference = References.of(store, unit)
    plain = Plain.ToPlain(store)(reference.as_schema(), reference)["path"]
    path = plain["next"]["entry"]["properties"]["path"]  # its key in the workspace's files
    return _Definer(Program(path, Anchor(""))).define(unit)  # type: ignore[return-value]


def _resolve(program: Program, scope: Scope | None, name: str, space: str | None) -> list[Entity]:
    """Lookup of `name` from `scope`, finding only entities in the name space `space`: a label outwards to its
    function's scope; an ordinary name unqualified, following using-directives, or qualified; a macro among the
    program's macros, and an ordinary name, failing any, too."""
    found: list[Entity] = []
    if space == LABEL:
        while scope is not None and not found:
            found = [e for e in scope.lookup(name) if e.kind == "label"]
            scope = scope.parent
    elif space == ORDINARY and scope is not None:
        parts, from_global = _split(name)
        if len(parts) > 1 or from_global:
            found = scope.qualified(parts, from_global=from_global)
        while scope is not None and not found:
            found = [e for e in scope.lookup(name) + [e for used in scope.using for e in used.lookup(name)] if (
                e.kind != "label")]
            scope = scope.parent
    return found or (program.macros.lookup(name) if space in (ORDINARY, MACRO) else [])


def referents(program: Program, at: Any) -> list[Entity]:
    """The entities the name written at `at` (an `Anchor`, or its text) refers to, looked up from where it is, in the
    name space it is written in: the one it binds or declares, or the ones its name resolves to. A place where no name
    is written, and a member's name (which depends on a type), find nothing."""
    name = program.name_at(at)
    if name is None:
        return []
    entity = program.entity_of(at)
    return [entity] if entity is not None else _resolve(program, program.scope_of(at), name, program.space_of(at))
