"""Definitions: the names a C translation unit declares, in the scopes and name spaces C gives them, read from the
store.

As the user decided for the port ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../docs/proposals/port/README.md#decided),
6): entities, name resolution and the program stay code over the stored tree, computed on demand and never stored, and
a use of a name is anchored on its statement and the term's path, since a term is a value.

- `define(store, path)`: the `Program` of the translation unit the workspace holds at `path`, read within a transaction
  of its own, so called with none open on `store`; LookupError where the workspace holds no file at `path`.
  `define_file(store, unit)` reads a unit's visitor within the caller's transaction. What either gives back is plain
  data, holding no visitor, so that it outlives the transaction (mbse-basis
  [CAP-315: every read within a transaction or through a follow](mbse:mbse-basis/docs/capabilities/CAP-315.md#decided)).
- `referents(program, at)`: the entities the name at `at` (an `Anchor`, or its text) refers to, looked up from where
  it is, in the name space it is written in.
- `Anchor`: a place in the unit, as the whole tree is values (stage 3's design): its `statement` the place of its
  statement, declaration or member declaration below the unit, rendered, its `property` the statement's property that
  holds the place (none, for the statement itself), and its `term` the place's path within that property's value: the
  names of the properties and the indices of the containers stepped through, terms, helpers (a specifier, a
  declarator) and parts (an init-declarator) alike. `str(anchor)` is its text, which identifies it within its unit:
  `body[1].body.body[0]:declarators[0].initializer.left` is the left operand of the initializer of the first
  declaration in the body of the unit's second declaration; `body[0]` the declaration itself; `<unit>` the unit.
- `Program`, a `Framework.Definitions.Program` whose qualified names join with `.` (`point.x`), keyed by anchors'
  text: `entity_of(at)`, `scope_of(at)` and `lookup(name, at)` each take an `Anchor` or its text; `anchor(text)` gives
  the anchor of a place it located; `named(spelling)` gives, in source order, every place a name spelled so is
  written, bound or used; `space_of(at)` the name space a name is written in; `path` is the unit's path; `macros` the
  scope of its macros.
- `MEANINGS`: the name space each kind of entity is in.

Its entities have these kinds, ported from mbse-programs 0.3's (`Ccpp/Definitions.py`), named for C *(agent: 0.3's
'class' was C++'s)*:

- 'variable', 'function', 'parameter' (of a function definition, or of a prototype, in its own scope), 'type alias'
  (`typedef`) and 'enumerator': C's ordinary identifiers;
- 'struct', 'union' and 'enumeration': its tags, each struct or union with its members, 'field', in a scope of its own;
- 'label', in its function's scope, which a `goto`, an `asm goto`'s labels and GNU's `&&label` refer to;
- 'macro', each `#define`'s name, in the program's `macros`, as 0.3 had them *(agent)*.

Declarations of one name and kind in one scope are one entity: a function's prototypes and its definition, a variable
declared `extern` and defined, a tag declared and then defined, a macro defined twice. Its `declarations` are in source
order, and its `definition` is the first that defines it, if any: a function's definition, a variable's declaration
but an `extern` one without an initializer, a tag's specifier with its body, a `typedef`, and every other kind's first.
Every name is declared before any is looked up, so a use finds a declaration later in its scope (C's point of
declaration is not modeled).

Scopes are C's (ISO/IEC 9899, 6.2.1): 'file' (the unit), 'function' (a function definition: its parameters, the
outermost block of its body, and its labels), 'block' (a compound statement, a statement expression's, and a `for`
statement), 'prototype' (a function declarator's parameters, but a definition's own), and the members of a struct or a
union ('struct', 'union'), which lookup never finds unqualified; each `node` the anchor of what opens it. C's name
spaces (6.2.3) keep labels, tags, each struct's or union's members and ordinary identifiers apart, so one name can be a
variable and a tag at once; macros are the preprocessor's. `Program.space_of` tells which a name is written in
('ordinary', 'tag', 'label', 'member' or 'macro'), and `referents` finds only the entities in it. A tag is in the scope
its specifier stands in, a struct's member declarations' specifiers included (C has no scope of a struct's), and so is
an enumeration's enumerator.

Every statement, declaration, member declaration and term is located in the scope it is evaluated in, as is every
place that binds a name, but for the names that name no entity of the program, which are not visited: a member's name
(`a.b`'s `b`, a designator's `.b`), an `asm` operand's symbolic name, a macro's parameters, and an attribute's name.
What it does not do: resolve members (`a.b`, whose `b` depends on `a`'s type), run the preprocessor (a macro's
replacement is text, and `#undef` is not read), tell typedef names from other names where the parser did not (`Parse`,
item 39), or follow names into included files.

Decided by the agent where the port left it open, each *(agent)*:

- **An anchor's text** follows TypeScript5's (`TypeScript5.Definitions`): a statement's place is its parents'
  properties from the unit down, each holding a list with its index (`body[1]`, `members[0]`) and each holding one
  statement without (`.consequence`, `.body`), as `body[1].body.body[0]`; then, for a place within it, `:`, the
  property, and the term's path, each property `.name` and each index `[i]`
  (`body[0]:declarators[0].declarator.name`). A term's kind is not a step, nor is the branch any other union holds (a
  specifier's, a declarator's, a `for`'s initializer). The unit is `<unit>`. Anchors are equal, and hash, as their
  text, and an anchor equals its text.
- **What has a statement's place**: statements, declarations, member declarations and `Error`s, and the parts that
  hold them: a struct's or a union's member list, a conditional directive's group (`Group`, `MemberGroup`) and a
  K&R definition's parameters' declarations (`body[0].declarations[1]`). Where they stand within a term, they are
  anchored at the term's place followed by the statement places within: a struct's member list is
  `body[0]:specifiers[0].members`, its member declarations `body[0]:specifiers[0].members.members[1]`; a statement
  expression's block `body[2]:declarators[0].initializer.block`, its statements
  `body[2]:declarators[0].initializer.block.body[0]`; a directive's group `body[3]:directive.group`, its statements
  `body[3]:directive.group.body[0]`, and its `#else`'s `body[3]:directive.alternative.group.body[0]`. A place within
  one of them follows a further `:` (`body[0]:specifiers[0].members.members[1]:declarators[0]`).
- **Where a name is bound is where it is written**: a declarator's identifier's `name`
  (`body[0]:declarators[1].declarator.declarator.name`), a tag's `name` within its specifier, an enumerator's `name`, a
  label's `label`, a `#define`'s `name`. What declares it is declared too, so that `entity_of` gives what it defines:
  an init-declarator, a member declarator, a parameter declaration, a function definition, a tag's specifier, an
  enumerator, a labeled statement and a `#define`.
- **Both branches of a conditional directive bind**, each group's statements in the scope the directive stands in, as
  0.3 declared every branch's: the preprocessor is not run, so which branch is compiled is not known, and a name each
  branch declares is one entity with a declaration in each (`#ifdef A int x; #else long x; #endif`). A group among a
  struct's members declares members; among an enumeration's enumerators, enumerators.
- **Macros are entities**, as 0.3 had them, in the program's `macros`, a scope of their own outside every other: a
  name in a conditional's condition, `#ifdef`'s, `defined(...)`'s and an `#include`'s macro is in the name space
  'macro'; a name elsewhere is an ordinary identifier, which finds the macro of its name where no ordinary entity is
  visible, the preprocessor not being run to tell (`MAX(a, b)` finds the macro `MAX`).
- **Linkage**: a block's `extern` declaration and a block's function declaration declare the file scope's entity of
  their name and kind, found from the block too (6.2.2, 4: they have the linkage of a prior declaration); a K&R
  definition's declarations declare its parameters. Internal and external linkage are not told apart.
- **The body of a function is its scope**: a definition's parameters and the declarations of its body's outermost
  block are in one scope, 'function' (6.2.1, 4), which its labels are in too; a `for` statement opens a block (6.8.5,
  5), and so does a compound statement. A selection's or an iteration's substatement opens none of its own, as it can
  declare nothing but through a compound statement.
- **An anonymous struct or union member's members** (C11, 6.7.2.1, 13) are its enclosing struct's or union's: its
  scope is transparent to theirs.
- **Invalid syntax binds what tree-sitter recovered within it**, as TypeScript5's: a `Programs.C.Error` is located in
  the scope it stands in, wherever it stands (a statement, a member declaration), and the statements recovered within
  it are defined in that scope (a member's, in its struct's enclosing scope); its own text binds nothing. An `error`
  term's recovered terms are visited as read, a name in them a use, and a `missing` term binds nothing.
- **Terms are read record by record** (`Objects.properties`, `Terms.kind_of`), never through mbse-expressions' generic
  term readers, which a statement expression's block, a struct's members and a directive's group do not belong to
  (`Terms.boundaries`): this module reads them.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, cast

from mbse.Expressions.Framework import Objects, Terms
from mbse.Schemas.Framework import Plain, References
from mbse.Schemas.Framework import Schemas as SchemaKinds

from ..Framework import Definitions
from ..Framework.Definitions import Entity, Scope
from ..Framework.Model import WORKSPACE
from . import Statements

__all__ = ["Anchor", "MEANINGS", "Program", "define", "define_file", "referents"]

ORDINARY, TAG, LABEL, MEMBER, MACRO = "ordinary", "tag", "label", "member", "macro"

MEANINGS: dict[str, str] = {
    "variable": ORDINARY, "function": ORDINARY, "parameter": ORDINARY, "type alias": ORDINARY,
    "enumerator": ORDINARY, "struct": TAG, "union": TAG, "enumeration": TAG, "field": MEMBER, "label": LABEL,
    "macro": MACRO,
}
"""The name space each kind of entity is in."""

_UNIT = "<unit>"
_STATEMENTS = frozenset(f"{Statements.LANGUAGE}.{kind}" for kind in (
    *Statements.KINDS, "Error", "MemberList", "Group", "MemberGroup"))
"""The schemas that have a statement's place: statements, declarations, member declarations, invalid syntax and the
parts that hold them."""
_TAGS = {"struct": "struct", "union": "union", "enum": "enumeration"}
"""The kind of entity a tag's keyword declares."""
_RANKS: dict[str, dict[str, int]] = {}
"""Each schema's properties' places in source order, by the schema's name."""

Binding = Callable[[str, "Anchor"], None]
"""What binds a declarator's name, given the name and where it is written."""


class Anchor:
    """A place in a unit: its statement's, declaration's or member declaration's place from the unit, rendered
    (`statement`), the statement's property holding the place (`property`, None for the statement itself) and the
    place's path within that property's value (`term`, property names and container indices). `order` sorts anchors in
    source order. Equal, and hashed, as its text, and equal to its text."""

    __slots__ = ("statement", "property", "term", "order", "_text")

    def __init__(self, statement: str, property: str | None = None, term: tuple[str | int, ...] = (),
                 order: tuple[tuple[int, ...], ...] = ()):
        self.statement, self.property, self.term, self.order = statement, property, term, order
        if property is None:
            self._text = statement or _UNIT
        else:
            self._text = f"{statement}:{property}" + "".join(
                f"[{step}]" if isinstance(step, int) else f".{step}" for step in term)

    def child(self, property: str, index: int | None, rank: int) -> Anchor:
        """The anchor of the statement this one's `property`, the `rank`th of its properties in source order, holds: at
        `index`, where it holds a list, or alone."""
        step = property if index is None else f"{property}[{index}]"
        return Anchor(f"{self.statement}.{step}" if self.statement else step,
                      order=(*self.order, (rank,) if index is None else (rank, index)))

    def at(self, step: str | int, rank: int) -> Anchor:
        """The place `step` within this one, the `rank`th in source order: the statement's property, for a
        statement's anchor; a property or a container's index, for any other."""
        if self.property is None:
            return Anchor(self.statement, step, (), (*self.order, (rank,)))  # type: ignore[arg-type]
        return Anchor(self.statement, self.property, (*self.term, step), (*self.order[:-1], (*self.order[-1], rank)))

    def opened(self) -> Anchor:
        """The anchor of a statement, a member list or a group standing at this place within a term: this place's
        text, as the statement's."""
        return Anchor(self._text, order=self.order)

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
    """What a unit declares: `Framework.Definitions.Program`, keyed by anchors' text, with every place a name is written
    and the name space it is written in."""

    def __init__(self, path: str, root: Anchor):
        super().__init__(Scope("file", None, None, root, separator="."))
        self.macros = Scope("macros", None, None, root, separator=".")
        self.path = path
        self._names: dict[str, tuple[Anchor, str]] = {}
        self._anchors: dict[str, Anchor] = {}
        self._spaces: dict[str, str] = {}

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

    def means(self, at: Anchor, space: str) -> None:
        """Records that the name at `at` is written in the name space `space`."""
        self._spaces[str(at)] = space

    def space_of(self, at: Any) -> str | None:
        """The name space the name at `at` is written in: 'ordinary', 'tag', 'label' or 'macro'; None for a name that
        declares."""
        return self._spaces.get(str(at))


# --- Reading ---

def _rank(record: Any, name: str) -> int:
    """Where a property of a statement, a term, a helper or a part comes in source, among its schema's: its schema's
    order, which is C's source order."""
    schema = record.as_schema()
    ranks = _RANKS.get(schema.name)
    if ranks is None:
        ranks = _RANKS[schema.name] = {prop: i for i, prop in enumerate(schema.properties)}
    return ranks[name]


def _branch(value: Any) -> tuple[str, Any]:
    """A term's kind and record, the record any other union holds and its branch's tag, through unions of unions; or a
    record and its kind's name in lower case (`identifier`)."""
    if Terms.is_term(value):
        return Terms.kind_of(value)
    if isinstance(value.as_schema(), SchemaKinds.OfUnion.Data):
        ((_, held),) = Objects.properties(value).items()
        return _branch(held)
    return value.as_schema().name.rsplit(".", 1)[-1].lower(), value


def _statements(value: Any, holders: frozenset[str]) -> bool:
    """Whether a property's value is a statement, a member declaration, an error or a part holding them, or a list of
    them: one of `holders`, the schemas that have a statement's place."""
    if isinstance(value, Objects.Listed):
        value = value.values[0] if value.values else None
    return hasattr(value, "as_schema") and not Terms.is_term(value) and (
        _branch(value)[1].as_schema().name in holders)


def _many(held: Any) -> tuple[Any, ...]:
    """A container's elements; none where it is absent."""
    return () if held is None else held.values


def _spelling(name: Any) -> str:
    """The spelling of the identifier a name holds."""
    return Objects.properties(_branch(name)[1])["spelling"]


def _named(value: Any) -> bool:
    """Whether a declarator is, within its parentheses, the identifier it declares."""
    tag, record = _branch(value)
    while tag == "parenthesizeddeclarator":
        tag, record = _branch(Objects.properties(record)["declarator"])
    return tag == "iddeclarator"


def _derived(value: Any) -> str | None:
    """The kind of the declarator nearest the name a declarator declares, but parentheses (`functiondeclarator`,
    `pointerdeclarator`, `arraydeclarator`); None where it is the name itself, or declares none."""
    tag, record = _branch(value)
    held = Objects.properties(record).get("declarator")
    if held is None:
        return None
    if tag != "parenthesizeddeclarator" and _named(held):
        return tag
    return _derived(held)


def _keywords(specifiers: Any) -> set[str]:
    """The keywords of a declaration's storage-class and function specifiers (`typedef`, `extern`, `static`)."""
    found = set()
    for specifier in _many(specifiers):
        tag, record = _branch(specifier)
        if tag == "declspecifier":
            found.add(Objects.properties(record)["keyword"])
    return found


# --- Defining ---

class _Definer:
    """Declares what a unit binds, visiting each place with its scope and the name space a name is written in there.
    `HOLDERS` are the schemas that have a statement's place, its language's *(agent: a class attribute, so that
    `Programs.Cpp.Definitions` reuses the definer over C++'s)*."""

    HOLDERS = _STATEMENTS

    def __init__(self, program: Program):
        self.program = program
        self.declarations: set[str] = set()
        """The places of the declarations that define nothing: a prototype, an `extern` declaration, a tag without its
        body."""

    # Scopes and bindings

    def bind(self, scope: Scope, name: str, at: Anchor, kind: str) -> Entity:
        """Binds `name` in `scope` as an entity of `kind`, written at `at`: the one of that name and kind there, or a
        new one."""
        found = [e for e in scope.names.get(name, []) if e.kind == kind and e.parent is scope]
        entity = found[0] if found else scope.declare(self.program.add(Entity(kind, name, scope)))
        entity.declarations.append(at)
        self.program.declares(at, entity)
        self.program.located(at, scope)
        self.program.written(at, name)
        return entity

    def link(self, scope: Scope, name: str, at: Anchor, kind: str) -> Entity:
        """Binds `name` as the file scope's entity of `kind`, written at `at` in `scope`, and makes it found from
        `scope`: a block's `extern` declaration or function declaration."""
        self.program.located(at, scope)
        return scope.declare(self.bind(self.program.root, name, at, kind))

    def use(self, at: Anchor, scope: Scope, name: str, space: str) -> None:
        """Records that `name`, written at `at` in `scope`, is used in the name space `space`."""
        self.program.located(at, scope)
        self.program.written(at, name)
        self.program.means(at, space)

    @staticmethod
    def function_scope(scope: Scope) -> Scope:
        """The scope of the function `scope` is in, where its labels are; the file's, outside every function."""
        while scope.kind != "function" and scope.parent is not None:
            scope = scope.parent
        return scope

    # Terms

    def visit(self, value: Any, scope: Scope, at: Anchor, space: str) -> None:
        """A value a property holds, evaluated in `scope` where a name is in the name space `space`: a term, a helper, a
        part, a statement or a part holding statements standing in a term's place, a container of them, or a scalar."""
        if isinstance(value, Objects.Listed):
            for i, element in enumerate(value.values):
                self.visit(element, scope, at.at(i, i), space)
            return
        if not hasattr(value, "as_schema"):
            return  # a scalar: a name a term holds is its own
        tag, record = _branch(value)
        if record.as_schema().name in self.HOLDERS:
            self.statement(record, scope, at.opened())
            return
        self.term(tag, record, scope, at, space)

    def term(self, tag: str, record: Any, scope: Scope, at: Anchor, space: str) -> None:
        """A term, a helper or a part of kind `tag`, at `at`."""
        self.program.located(at, scope)
        handler = self.TERMS.get(tag)
        if handler is None:
            self.fields(record, scope, at, space)
        else:
            handler(self, record, Objects.properties(record), scope, at, space)

    def fields(self, record: Any, scope: Scope, at: Anchor, space: str) -> None:
        """A term's, a helper's or a part's properties, each evaluated in `scope`."""
        for name, value in Objects.properties(record).items():
            self.visit(value, scope, at.at(name, _rank(record, name)), space)

    def prop(self, record: Any, props: dict[str, Any], name: str, scope: Scope, at: Anchor, space: str) -> None:
        """A property of a statement, a term or a helper, evaluated in `scope`, where it is set."""
        if name in props:
            self.visit(props[name], scope, at.at(name, _rank(record, name)), space)

    def variable(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.use(at, scope, props["name"], space)

    def identifier(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.use(at, scope, props["spelling"], space)

    def member(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.prop(record, props, "object", scope, at, space)  # its member's name depends on the object's type

    def label_address(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """GNU's `&&label`: its name a label's, looked up in its function's scope, as a `goto`'s."""
        self.use(at.at("label", _rank(record, "label")), scope, _spelling(props["label"]), LABEL)

    def unnamed(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """A term whose names name no entity of the program: a designator's member."""

    def preprocessed(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """A directive or a term the preprocessor reads: its condition's, its name's and its macro's names are macros';
        what it governs (its group, its items) is evaluated as where it stands."""
        for name, value in props.items():
            self.visit(value, scope, at.at(name, _rank(record, name)), MACRO if name in (
                "condition", "name", "macro") else ORDINARY)

    def define_macro(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """`#define`: its name a macro's; its parameters name nothing but in its replacement, which is text."""
        name = at.at("name", _rank(record, "name"))
        self.program.located(name, scope)  # written where the directive stands, which the macros' scope is not
        self.program.declares(at, self.bind(self.program.macros, _spelling(props["name"]), name, "macro"))

    def enumerator(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.program.declares(at, self.bind(scope, _spelling(props["name"]), at.at("name", _rank(record, "name")),
                                            "enumerator"))
        self.prop(record, props, "attributes", scope, at, ORDINARY)
        self.prop(record, props, "value", scope, at, ORDINARY)

    def specifier(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """A struct's, a union's or an enumeration's specifier, which names its tag."""
        self.tag(record, props, scope, at, False)

    def tag(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, alone: bool) -> Scope | None:
        """A struct's, a union's or an enumeration's specifier, in `scope`: with its body, or `alone` in its
        declaration (`struct s;`), it declares its tag there; without, it uses it. Its enumerators are declared in
        `scope`, its members in a scope of their own, which it gives back (None for an enumeration's, or none)."""
        self.prop(record, props, "attributes", scope, at, ORDINARY)
        kind, body = _TAGS[props["key"]], props.get("body", False)
        entity = None
        if "name" in props:
            name, place = _spelling(props["name"]), at.at("name", _rank(record, "name"))
            if body or alone:
                entity = self.bind(scope, name, place, kind)
                self.program.declares(at, entity)
                if not body:
                    self.declarations.add(str(place))
            else:
                self.use(place, scope, name, TAG)
        elif body:
            entity = self.program.add(Entity(kind, None, scope))
            entity.declarations.append(at)
            self.program.declares(at, entity)
        self.prop(record, props, "base", scope, at, ORDINARY)
        self.prop(record, props, "enumerators", scope, at, ORDINARY)
        if "members" not in props:
            return None
        where = at.at("members", _rank(record, "members")).opened()
        members = Scope(kind, entity, scope, where)
        if entity is not None and entity.scope is None:
            entity.scope = members
        self.member_list(_branch(props["members"])[1], members, where)
        return members

    def type_name(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """A type name (`typeid`): its specifiers, and its abstract declarator, which binds no name of its own."""
        self.prop(record, props, "specifiers", scope, at, ORDINARY)
        if "declarator" in props:
            self.declarator(props["declarator"], scope, at.at("declarator", _rank(record, "declarator")),
                            lambda name, place: self.use(place, scope, name, ORDINARY), None)

    # Declarators

    def declarator(self, value: Any, scope: Scope, at: Anchor, bind: Binding, function: Scope | None) -> None:
        """A declarator, its parts evaluated in `scope`: the name it declares bound by `bind`; a function declarator's
        parameters in a prototype scope of their own, but those of the one declaring the name, which bind in
        `function` where it is given (a function's definition's)."""
        self.program.located(at, scope)
        tag, record = _branch(value)
        props = Objects.properties(record)
        for name, held in props.items():
            place = at.at(name, _rank(record, name))
            if name == "name":  # an identifier's
                bind(_spelling(held), place)
            elif name == "declarator":
                self.declarator(held, scope, place, bind, function)
            elif name == "parameters":
                inner = function if function is not None and _named(props["declarator"]) else Scope(
                    "prototype", None, scope, at)
                self.parameters(held, inner, place)
            else:
                self.visit(held, scope, place, ORDINARY)

    def parameters(self, held: Any, scope: Scope, at: Anchor) -> None:
        """A function declarator's parameters, each binding its name in `scope`, where its parts are evaluated too."""
        self.program.located(at, scope)
        for i, parameter in enumerate(held.values):
            each = at.at(i, i)
            self.program.located(each, scope)
            tag, record = _branch(parameter)
            props = Objects.properties(record)
            self.prop(record, props, "attributes", scope, each, ORDINARY)
            self.prop(record, props, "specifiers", scope, each, ORDINARY)
            if "declarator" in props:
                self.declarator(props["declarator"], scope, each.at("declarator", _rank(record, "declarator")),
                                lambda name, place, each=each: self.program.declares(
                                    each, self.bind(scope, name, place, "parameter")), None)

    TERMS: dict[str, Any] = {
        "variable": variable, "identifier": identifier, "memberexpression": member, "fielddesignator": unnamed,
        "labeladdressexpression": label_address,
        "classspecifier": specifier, "enumspecifier": specifier, "enumerator": enumerator, "typeid": type_name,
        "definedirective": define_macro, "ifdirective": preprocessed, "ifdefdirective": preprocessed,
        "elifdirective": preprocessed, "elifdefdirective": preprocessed, "includedirective": preprocessed,
        "definedexpression": preprocessed,
    }

    # Statements

    def statement(self, node: Any, scope: Scope, at: Anchor) -> None:
        """A statement, a declaration, invalid syntax or a part holding them, at `at`."""
        self.program.located(at, scope)
        handler = self.STATEMENTS.get(node.as_schema().name.rsplit(".", 1)[-1], _Definer.parts)
        handler(self, node, Objects.properties(node), scope, at)

    def child(self, node: Any, name: str, value: Any, scope: Scope, at: Anchor) -> None:
        """The statements `node`'s property `name` holds, each at its place."""
        rank = _rank(node, name)
        if isinstance(value, Objects.Listed):
            for i, element in enumerate(value.values):
                self.statement(_branch(element)[1], scope, at.child(name, i, rank))
        else:
            self.statement(_branch(value)[1], scope, at.child(name, None, rank))

    def children(self, node: Any, scope: Scope, at: Anchor) -> None:
        """The statements a statement, a part or an error holds, in source order, in `scope`."""
        for name, value in Objects.properties(node).items():
            if _statements(value, self.HOLDERS):
                self.child(node, name, value, scope, at)

    def parts(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """A statement's properties, each in `scope`: its statements at their places, its terms evaluated."""
        for name, value in props.items():
            if _statements(value, self.HOLDERS):
                self.child(node, name, value, scope, at)
            else:
                self.visit(value, scope, at.at(name, _rank(node, name)), ORDINARY)

    def block(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.children(node, Scope("block", None, scope, at), at)

    def loop(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.parts(node, props, Scope("block", None, scope, at), at)

    def labeled(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        label = self.bind(self.function_scope(scope), _spelling(props["label"]), at.at("label", _rank(node, "label")),
                          "label")
        self.program.declares(at, label)
        self.children(node, scope, at)

    def goto(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        if "label" in props:
            self.use(at.at("label", _rank(node, "label")), scope, _spelling(props["label"]), LABEL)
        self.prop(node, props, "target", scope, at, ORDINARY)  # GNU's `goto *p;`

    def asm(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """An `asm` statement: its labels' names are labels; its operands' symbolic names name nothing."""
        for name, value in props.items():
            place = at.at(name, _rank(node, name))
            if name == "labels":
                for i, label in enumerate(value.values):
                    self.use(place.at(i, i), scope, _spelling(label), LABEL)
            elif name in ("outputs", "inputs"):
                for i, operand in enumerate(value.values):
                    each = place.at(i, i)
                    self.program.located(each, scope)
                    fields = Objects.properties(operand)
                    self.prop(operand, fields, "constraint", scope, each, ORDINARY)
                    self.prop(operand, fields, "value", scope, each, ORDINARY)
            else:
                self.visit(value, scope, place, ORDINARY)

    def kind_of(self, keywords: set[str], declarator: Any) -> str:
        """The kind of entity a declaration's declarator declares, given its specifiers' keywords."""
        if "typedef" in keywords:
            return "type alias"
        return "function" if _derived(declarator) == "functiondeclarator" else "variable"

    def declaration(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.declare(node, props, scope, at, lambda keywords, declarator: self.kind_of(keywords, declarator))

    def declare(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor,
                kind: Callable[[set[str], Any], str]) -> None:
        """A declaration: its specifiers and its attributes in `scope`, where each declarator binds its name, as an
        entity of the `kind` its keywords and its declarator give; a declaration of nothing but a tag (`struct s;`)
        declares it."""
        keywords = _keywords(props.get("specifiers"))
        self.prop(node, props, "attributes", scope, at, ORDINARY)
        specifiers = at.at("specifiers", _rank(node, "specifiers"))
        alone = "declarators" not in props
        for i, specifier in enumerate(_many(props.get("specifiers"))):
            tag, record = _branch(specifier)
            if alone and tag in ("classspecifier", "enumspecifier"):
                self.program.located(specifiers.at(i, i), scope)
                self.tag(record, Objects.properties(record), scope, specifiers.at(i, i), True)
            else:
                self.visit(specifier, scope, specifiers.at(i, i), ORDINARY)
        declarators = at.at("declarators", _rank(node, "declarators"))
        for i, declarator in enumerate(_many(props.get("declarators"))):
            each = declarators.at(i, i)
            self.program.located(each, scope)
            fields = Objects.properties(declarator)
            entity_kind = kind(keywords, fields["declarator"])
            linked = scope is not self.program.root and scope.kind != "prototype" and entity_kind in (
                "function", "variable") and (entity_kind == "function" or "extern" in keywords)
            declaration_only = entity_kind == "function" or "extern" in keywords and "initializer" not in fields

            def bind(name: str, place: Anchor, each: Anchor = each, entity_kind: str = entity_kind,
                     linked: bool = linked, declaration_only: bool = declaration_only) -> None:
                entity = (self.link if linked else self.bind)(scope, name, place, entity_kind)
                self.program.declares(each, entity)
                if declaration_only:
                    self.declarations.add(str(place))

            self.declarator(fields["declarator"], scope, each.at("declarator", _rank(declarator, "declarator")),
                            bind, None)
            self.prop(declarator, fields, "initializer", scope, each, ORDINARY)

    def function_definition(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """A function's definition: its name in `scope`, and the scope it opens, holding its parameters, its K&R
        declarations of them, its body's declarations and its labels."""
        self.prop(node, props, "attributes", scope, at, ORDINARY)
        self.prop(node, props, "specifiers", scope, at, ORDINARY)
        inner = Scope("function", None, scope, at)

        def bind(name: str, place: Anchor) -> None:
            entity = self.bind(scope, name, place, "function")
            self.program.declares(at, entity)
            inner.owner, entity.scope = entity, inner

        self.declarator(props["declarator"], scope, at.at("declarator", _rank(node, "declarator")), bind, inner)
        if "declarations" in props:  # a K&R definition's: its parameters'
            rank = _rank(node, "declarations")
            for i, declaration in enumerate(props["declarations"].values):
                where = at.child("declarations", i, rank)
                self.program.located(where, inner)
                self.declare(declaration, Objects.properties(declaration), inner, where, lambda *_: "parameter")
        body = at.child("body", None, _rank(node, "body"))
        self.program.located(body, inner)
        self.children(props["body"], inner, body)

    def member_group(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.member_list(node, scope, at)

    def member_list(self, node: Any, members: Scope, at: Anchor) -> None:
        """A struct's or a union's member declarations, or a group of them, each declaring its members in `members`."""
        self.program.located(at, members)
        rank = _rank(node, "members")
        for i, element in enumerate(_many(Objects.properties(node).get("members"))):
            self.member_declaration(_branch(element)[1], members, at.child("members", i, rank))

    def member_declaration(self, node: Any, members: Scope, at: Anchor) -> None:
        """A member declaration: its members declared in `members`; its specifiers, its attributes and its bit-fields'
        widths evaluated in the scope the struct stands in, where its tags are declared. An anonymous struct's or
        union's members are `members`' own."""
        self.program.located(at, members)
        enclosing: Scope = members.parent  # type: ignore[assignment]
        kind = node.as_schema().name.rsplit(".", 1)[-1]
        props = Objects.properties(node)
        if kind == "Directive":  # its group's members are `members`'
            self.statement(node, members, at)
            return
        if kind != "MemberDeclaration":  # a static assertion, a comment, or invalid syntax
            self.statement(node, enclosing, at)
            return
        self.prop(node, props, "attributes", enclosing, at, ORDINARY)
        specifiers = at.at("specifiers", _rank(node, "specifiers"))
        for i, specifier in enumerate(_many(props.get("specifiers"))):
            tag, record = _branch(specifier)
            fields = Objects.properties(record)
            if tag == "classspecifier" and "name" not in fields and "members" in fields and "declarators" not in props:
                self.program.located(specifiers.at(i, i), enclosing)  # anonymous: its members are `members`'
                members.transparent.append(cast(Scope, self.tag(record, fields, enclosing, specifiers.at(i, i), False)))
            else:
                self.visit(specifier, enclosing, specifiers.at(i, i), ORDINARY)
        declarators = at.at("declarators", _rank(node, "declarators"))
        for i, declarator in enumerate(_many(props.get("declarators"))):
            each = declarators.at(i, i)
            self.program.located(each, members)
            fields = Objects.properties(declarator)
            if "declarator" in fields:
                self.declarator(fields["declarator"], enclosing, each.at("declarator", _rank(declarator, "declarator")),
                                lambda name, place, each=each: self.program.declares(
                                    each, self.bind(members, name, place, "field")), None)
            self.prop(declarator, fields, "bitfield", enclosing, each, ORDINARY)

    STATEMENTS: dict[str, Any] = {
        "CompoundStatement": block, "ForStatement": loop, "LabeledStatement": labeled, "GotoStatement": goto,
        "AsmDeclaration": asm, "SimpleDeclaration": declaration, "FunctionDefinition": function_definition,
        "MemberGroup": member_group,
    }

    def define(self, node: Any) -> Program:
        program = self.program
        program.located(program.root.node, program.root)
        self.children(node, program.root, program.root.node)
        for entity in program.entities():
            entity.declarations.sort(key=lambda anchor: anchor.order)
            entity.definition = next((d for d in entity.declarations if str(d) not in self.declarations), None)
        return program


def define(store: Any, path: str) -> Program:
    """The entities the unit at `path` declares, in their scopes (`define_file`), read within a transaction of its own,
    so called with none open on `store`; LookupError where the workspace holds no file at `path`."""
    with store.transaction():
        return define_file(store, store.singleton(WORKSPACE).files({"path": path}))  # LookupError, where it holds none


def define_file(store: Any, unit: Any) -> Program:
    """The entities a unit declares, in their scopes: its visitor, a `Programs.C.TranslationUnit` of `store`, read
    within the caller's transaction. What it gives back holds no visitor, so it outlives the transaction."""
    reference = References.of(store, unit)
    plain = Plain.ToPlain(store)(reference.as_schema(), reference)["path"]
    path = plain["next"]["entry"]["properties"]["path"]  # its key in the workspace's files
    return _Definer(Program(path, Anchor(""))).define(unit)


def _resolve(program: Program, scope: Scope | None, name: str, space: str | None) -> list[Entity]:
    """Unqualified lookup of `name` from `scope`, outwards, finding only entities in the name space `space`: a macro
    among the program's macros, and an ordinary identifier, failing any, too."""
    if space != MACRO:
        while scope is not None:
            found = [e for e in scope.lookup(name) if MEANINGS[e.kind] == space]
            if found:
                return found
            scope = scope.parent
    return program.macros.lookup(name) if space in (ORDINARY, MACRO) else []


def referents(program: Program, at: Any) -> list[Entity]:
    """The entities the name written at `at` (an `Anchor`, or its text) refers to, looked up from where it is, in the
    name space it is written in: the one it binds or declares, or the ones its name resolves to. A place where no name
    is written, and a member's name (which depends on a type), find nothing."""
    name = program.name_at(at)
    if name is None:
        return []
    entity = program.entity_of(at)
    return [entity] if entity is not None else _resolve(program, program.scope_of(at), name, program.space_of(at))
