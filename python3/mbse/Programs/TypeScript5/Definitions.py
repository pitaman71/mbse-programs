"""Definitions: the names a TypeScript 5 program declares, in the scopes ECMAScript and TypeScript give them, read from
the store.

As the user decided for the port ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../docs/proposals/port/README.md#decided),
6): entities, name resolution and the program stay code over the stored tree, computed on demand and never stored, and
a use of a name is anchored on its statement and the term's path, since a term is a value.

- `define(store, path)`: the `Program` of the source file the workspace holds at `path`, read within a transaction of
  its own, so called with none open on `store`; LookupError where the workspace holds no file at `path`.
  `define_file(store, program)` reads a program's visitor within the caller's transaction. What either gives back is
  plain data, holding no visitor, so that it outlives the transaction (mbse-basis
  [CAP-315: every read within a transaction or through a follow](mbse:mbse-basis/docs/capabilities/CAP-315.md#decided)).
- `referents(program, at)`: the entities the name at `at` (an `Anchor`, or its text) refers to, looked up from where
  it is, with the meaning it has there.
- `Anchor`: a place in the program, as the whole tree is values (stage 3's design): its `statement` the place of its
  statement, clause or class member below the program, rendered, its `property` the statement's property that holds
  the place (none, for the statement itself), and its `term` the place's path within that property's value: the names
  of the properties and the indices of the containers stepped through, terms, helpers (an annotation, a type
  parameter) and parts (a declarator, a specifier) alike. `str(anchor)` is its text, which identifies it within its
  program: `body[1].consequent.body[0]:expression.left` is the left operand of the expression statement first in the
  block that is the consequent of the program's second statement; `body[0]` the statement itself; `<program>` the
  program.
- `Program`, a `Framework.Definitions.Program` whose qualified names join with `.` (`Shapes.Point.area`), keyed by
  anchors' text: `entity_of(at)`, `scope_of(at)` and `lookup(name, at)` each take an `Anchor` or its text;
  `anchor(text)` gives the anchor of a place it located; `named(spelling)` gives, in source order, every place a name
  spelled so is written, bound or used; `space_of(at)` the meaning a name has where it is written; `path` is the
  program's path.
- `MEANINGS`: the meanings each kind of entity has.

Its entities have these kinds, as mbse-programs 0.3 had them (`TypeScript/Definitions.py`), whose rules this module
ports:

- 'variable' (`var`, `let`, `const`, `using`, and a `catch` clause's parameter), 'parameter' and 'function';
- 'class', with its members: 'method', 'property' (a parameter property included) and 'accessor' (`get`, `set` and
  `accessor`), private ones named with their `#`;
- 'interface', with its members 'method', 'property' and 'accessor'; 'type alias' and 'type parameter' (a mapped
  type's key and an `infer` binding included);
- 'enum' and 'enum member'; 'namespace' (`namespace A` and `module A`) and 'module' (`declare module "a"`);
- 'import': a name an import binds, `import a = b.c` included, whose `target` is what `b.c` names.

Declarations of one name and kind in one scope are one entity: merged interfaces, namespaces and enums share their
scope, and a function's overloads, a `var` declared twice and an accessor's `get` and `set` are one entity. Its
`declarations` are in source order, and its `definition` is the first that is not an overload signature (a function or
a method without a body, an interface's member), if any. Every name is declared before any is looked up, so a use
finds a declaration later in its scope, as hoisting does for `var` and functions (the temporal dead zone of `let`,
`const` and classes is not modeled).

Scopes are 'module' (the program), 'function' (a function, an arrow function, a method or a signature: its type
parameters and parameters), 'block' (a block, a `for` statement, a `switch` statement's cases, a `catch` clause, a
named class expression), 'static block', 'class' and 'interface' (members, which lookup never finds unqualified),
'enum', 'namespace', 'module' and 'type parameters' (of a generic class, interface or type alias, of a mapped type, or
the `infer` bindings of a conditional type), each `node` the anchor of what opens it. `var` binds in the nearest
function, static block, namespace or module; everything else in the nearest scope. `declare global { ... }` declares in
the program's scope.

A name has a meaning: TypeScript keeps values, types and namespaces apart, so one name can be a variable and an
interface at once. `Program.space_of` tells which meaning a name has where it is written, and `referents` finds only the
entities with that meaning ('class', 'enum' and 'import' have every meaning).

Every statement, clause, class member and term is located in the scope it is evaluated in, as is every place that
binds a name, but for the names that name no entity of the program, which are not visited: a property's name (`a.b`'s
`b`, a non-computed key), a qualified name's later parts, a label, a meta-property, an import's imported and an
export's exported name, a re-export's specifiers, an import's or export's attributes, a named tuple member's label, an
index signature's parameter, `declare global`'s `global`, `as const`'s `const`, and a lower-case JSX element's name
(`<div>`, HTML) and an attribute's. What it does not do: resolve properties (`a.b`, whose `b` depends on `a`'s value),
a qualified name past its first part, or the members of imported modules; follow `export *`, `with` statements, `eval`
or globals that libraries declare.

Decided by the agent where the port left it open, each *(agent)*:

- **An anchor's text** follows Python3's (`Python3.Definitions`): a statement's place is its parents' properties from
  the program down, each holding a list with its index (`body[1]`, `cases[0]`) and each holding one statement without
  (`.consequent`, `.handler`, `.body`), as `body[1].consequent.body[0]`; then, for a place within it, `:`, the property,
  and the term's path, each property `.name` and each index `[i]` (`body[0]:declarations[0].id`). A term's kind is not
  a step, nor is the branch any other union holds (a `for`'s `init`, an import's specifier, a JSX tag's name). The
  program is `<program>`. Anchors are equal, and hash, as their text, and an anchor equals its text.
- **Statements within a term**, a function expression's or a block-bodied arrow's `block` and a class expression's
  `classBody`, are anchored at the term's place followed by the statement places within: the block itself is
  `body[0]:declarations[0].init.block`, its statements `body[0]:declarations[0].init.block.body[1]`, and a place within
  one of them follows a further `:` (`body[0]:declarations[0].init.block.body[1]:expression`). A class expression's
  members are `body[0]:declarations[0].init.classBody.body[2]`, and a method's statements, its value's block,
  `body[0].body.body[2]:value.block.body[0]`. The same holds wherever a statement stands in a term's place: an `Error`
  among an enum's members, a comment there.
- **What has a statement's place**: statements, clauses (a `switch`'s case, a `catch` clause, a static block), class
  members and `Error`s, and the parts that hold them: a function's body (`body[3].body`), a class's body
  (`body[0].body`, its members `body[0].body.body[2]`) and a namespace's block (`body[5].body`). A `for`'s declaration
  and an export's declared statement are statements too (`body[2].init`, `body[4].declaration`). Parts that hold no
  statement are places within their statement's property: a declarator (`body[0]:declarations[1]`), an import's or
  export's specifier, an enum's member (`body[6]:body.members[0]`) and an interface's (`body[7]:body.body[0]`).
- **Where a name is bound is where it is written**: a declaration's `id` (`body[3]:id`), a member's `key`
  (`body[0].body.body[1]:key`, an interface's `body[7]:body.body[0].key`), an enum member's `id`, a specifier's
  `local` (`body[0]:specifiers[1].local`), a type parameter's `name` (`body[2]:typeParameters.params[0].name`), a
  mapped type's `key`, a namespace's name or each part of `a.b.c`, and the identifier a pattern binds. What declares
  it is declared too, so that `entity_of` gives what it defines: a declaration's statement, a member, an enum member, a
  function or class expression's term. A parameter property is declared at the parameter (`…:value.params[0]`), its
  parameter at the identifier within (`…:value.params[0].parameter`).
- **Source order** is each anchor's `order`: the statement's place, then the properties' order in each schema, which
  is typescript-estree's source order, but an arrow's `body` after its parameters and return type, and a mapped type's
  constraint (`value`) after its key and its type (`body`) last, as TypeScript's source has them.
- **The API is `define(store, path)` and `define_file(store, program)`**, as Python3's: one program per source file,
  as TypeScript scopes a module's names to it.
- **Invalid syntax binds what tree-sitter recovered within it**, as Python3's: a `Programs.TypeScript5.Error` is located
  in the scope it stands in, wherever it stands (a statement, a case, a class member, an enum member), and the
  statements recovered within it are defined in that scope; its own text binds nothing. An `error` term's recovered
  terms are visited as read, a name in them a use, and a `missing` term binds nothing.
- **Terms are read record by record** (`Objects.properties`, `Terms.kind_of`), never through mbse-expressions' generic
  term readers, which a block or a class body within a term does not belong to: a term's `block` and `classBody` are
  read here.
"""

from __future__ import annotations

from typing import Any

from mbse.Expressions.Framework import Objects, Terms
from mbse.Schemas.Framework import Plain, References
from mbse.Schemas.Framework import Schemas as SchemaKinds

from ..Framework import Definitions
from ..Framework.Definitions import Entity, Scope
from ..Framework.Model import WORKSPACE
from . import Statements

__all__ = ["Anchor", "MEANINGS", "Program", "define", "define_file", "referents"]

MEANINGS: dict[str, frozenset[str]] = {
    "variable": frozenset({"value"}), "parameter": frozenset({"value"}), "function": frozenset({"value"}),
    "enum member": frozenset({"value"}), "class": frozenset({"value", "type", "namespace"}),
    "enum": frozenset({"value", "type", "namespace"}), "import": frozenset({"value", "type", "namespace"}),
    "namespace": frozenset({"value", "namespace"}), "module": frozenset({"namespace"}),
    "interface": frozenset({"type"}), "type alias": frozenset({"type"}), "type parameter": frozenset({"type"}),
    "method": frozenset({"value"}), "property": frozenset({"value"}), "accessor": frozenset({"value"}),
}
"""The meanings each kind of entity has: what it can be named as."""

_PROGRAM = "<program>"
_STATEMENTS = frozenset(f"{Statements.LANGUAGE}.{kind}" for kind in (*Statements.KINDS, "Error"))
"""The schemas that have a statement's place: statements, clauses, class members and invalid syntax."""
_TYPES = "Expressions.TypeScript.Types.Term"
_HERITAGE = ("tsinterfaceheritage", "tsclassimplements")
"""The helpers whose expression names a type."""
_VAR_SCOPES = {"module", "function", "static block", "namespace"}
"""The scopes where `var` binds."""
_SOURCE = {"Expressions.TypeScript.TypeScript5.ArrowFunctionExpression": (
               "isAsync", "typeParameters", "params", "returnType", "body"),
           "Expressions.TypeScript.Types.TSMappedType": ("readonly", "key", "value", "nameType", "optional", "body")}
"""The kinds whose properties' order is not their source's: an arrow's body comes after its parameters, and a mapped
type's constraint after its key, its type last."""
_TARGETS = {"arraypattern": "elements", "objectpattern": "properties", "assignmentpattern": "left",
            "restelement": "argument", "tsparameterproperty": "parameter", "property": "value"}
"""The patterns that hold patterns, by the property that holds them."""
_RANKS: dict[str, dict[str, int]] = {}
"""Each schema's properties' places in source order, by the schema's name."""


class Anchor:
    """A place in a program: its statement's, clause's or member's place from the program, rendered (`statement`), the
    statement's property holding the place (`property`, None for the statement itself) and the place's path within
    that property's value (`term`, property names and container indices). `order` sorts anchors in source order.
    Equal, and hashed, as its text, and equal to its text."""

    __slots__ = ("statement", "property", "term", "order", "_text")

    def __init__(self, statement: str, property: str | None = None, term: tuple[str | int, ...] = (),
                 order: tuple[tuple[int, ...], ...] = ()):
        self.statement, self.property, self.term, self.order = statement, property, term, order
        if property is None:
            self._text = statement or _PROGRAM
        else:
            self._text = f"{statement}:{property}" + "".join(
                f"[{step}]" if isinstance(step, int) else f".{step}" for step in term)

    def child(self, property: str, index: int | None, rank: int) -> Anchor:
        """The anchor of the statement, clause or member this one's `property`, the `rank`th of its properties in
        source order, holds: at `index`, where it holds a list, or alone."""
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
        """The anchor of a statement, a block or a class body standing at this place within a term: this place's text,
        as the statement's."""
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
    """What a program declares: `Framework.Definitions.Program`, keyed by anchors' text, with every place a name is
    written and the meaning it has there."""

    def __init__(self, path: str, root: Anchor):
        super().__init__(Scope("module", None, None, root, separator="."))
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
        """Records that the name at `at` is written as a `space`: 'value', 'type' or 'namespace'."""
        self._spaces[str(at)] = space

    def space_of(self, at: Any) -> str | None:
        """The meaning the name at `at` has where it is written: 'value', 'type' or 'namespace'; None for a name that
        declares, or that names something of any meaning (an export's)."""
        return self._spaces.get(str(at))


# --- Reading ---

def _rank(record: Any, name: str) -> int:
    """Where a property of a statement, a term, a helper or a part comes in source, among its schema's."""
    schema = record.as_schema()
    ranks = _RANKS.get(schema.name)
    if ranks is None:
        first = _SOURCE.get(schema.name, ())
        names = [*first, *(prop for prop in schema.properties if prop not in first)]
        ranks = _RANKS[schema.name] = {prop: i for i, prop in enumerate(names)}
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


def _statements(value: Any) -> bool:
    """Whether a property's value is a statement, a clause, a member or an error, or a list of them."""
    if isinstance(value, Objects.Listed):
        value = value.values[0] if value.values else None
    return hasattr(value, "as_schema") and not Terms.is_term(value) and (
        _branch(value)[1].as_schema().name in _STATEMENTS)


def _many(held: Any) -> tuple[Any, ...]:
    """A container's elements; none where it is absent."""
    return () if held is None else held.values


def _key_name(key: Any, computed: bool) -> str | None:
    """The name a member's key gives: an identifier's, `#` and a private name's, a string's value or a number's as
    written; None for a computed key."""
    if computed:
        return None
    tag, record = _branch(key)
    fields = Objects.properties(record)
    if tag == "identifier":
        return fields["name"]
    if tag == "privateidentifier":
        return "#" + fields["name"]
    return fields["value"] if "quote" in fields else fields["text"]


# --- Defining ---

class _Definer:
    """Declares what a program binds, visiting each place with its scope and the meaning a name has there."""

    def __init__(self, program: Program):
        self.program = program
        self.imports: list[tuple[Entity, list[str], Scope]] = []
        self.signatures: set[str] = set()

    # Scopes and bindings

    @staticmethod
    def var_scope(scope: Scope) -> Scope:
        """The scope where a `var` in `scope` binds."""
        while scope.kind not in _VAR_SCOPES:
            scope = scope.parent  # type: ignore[assignment]
        return scope

    def bind(self, scope: Scope, name: str, at: Anchor, kind: str) -> Entity:
        """Binds `name` in `scope` as an entity of `kind`, written at `at`: the one of that name and kind there, or a
        new one."""
        found = [e for e in scope.names.get(name, []) if e.kind == kind]
        entity = found[0] if found else scope.declare(self.program.add(Entity(kind, name, scope)))
        entity.declarations.append(at)
        self.program.declares(at, entity)
        self.program.located(at, scope)
        self.program.written(at, name)
        return entity

    def owner(self, scope: Scope, name: str, at: Anchor, kind: str, node: Anchor) -> Entity:
        """Binds `name` in `scope` as an entity with members, a scope of its own of `kind`: the one an earlier
        declaration of it opened, or a new one, opened by `node`."""
        entity = self.bind(scope, name, at, kind)
        if entity.scope is None:
            entity.scope = Scope(kind, entity, scope, node)
        return entity

    def target(self, value: Any, scope: Scope, kind: str, inner: Scope, at: Anchor) -> None:
        """A binding pattern: its names bind in `scope` as `kind`; its defaults, computed keys and annotations are in
        `inner`."""
        tag, record = _branch(value)
        props = Objects.properties(record)
        self.program.located(at, inner)
        if tag == "identifier":
            if props["name"] != "this":  # `this: T` declares the type of `this`, not a parameter
                self.bind(scope, props["name"], at, kind)
            self.prop(record, props, "decorators", inner, at, "value")
            self.prop(record, props, "typeAnnotation", inner, at, "type")
        elif tag in _TARGETS:
            for name, held in props.items():
                place = at.at(name, _rank(record, name))
                if name == _TARGETS[tag] and isinstance(held, Objects.Listed):
                    for i, element in enumerate(held.values):
                        self.target(element, scope, kind, inner, place.at(i, i))
                elif name == _TARGETS[tag]:
                    self.target(held, scope, kind, inner, place)
                elif name != "key" or props.get("computed"):  # an object pattern's key, but a computed one, is a name
                    self.visit(held, inner, place, "value")
        else:
            self.visit(value, inner, at, "value")

    def type_parameters(self, record: Any, scope: Scope, at: Anchor) -> None:
        """Binds a declaration's type parameters in `scope`, their constraints and defaults there too."""
        self.program.located(at, scope)
        where = at.at("params", _rank(record, "params"))
        for i, parameter in enumerate(Objects.properties(record)["params"].values):
            self.type_parameter(parameter, scope, where.at(i, i))

    def type_parameter(self, record: Any, scope: Scope, at: Anchor) -> None:
        self.program.located(at, scope)
        props = Objects.properties(record)
        self.bind(scope, Objects.properties(props["name"])["name"], at.at("name", _rank(record, "name")),
                  "type parameter")
        for name in ("constraint", "default"):
            if name in props:
                self.visit(props[name], scope, at.at(name, _rank(record, name)), "type")

    def generic(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> Scope:
        """The scope of a generic class's, interface's or type alias's type parameters; `scope` if it has none."""
        if "typeParameters" not in props:
            return scope
        inner = Scope("type parameters", None, scope, at)
        self.type_parameters(props["typeParameters"], inner, at.at("typeParameters", _rank(record, "typeParameters")))
        return inner

    # Terms

    def visit(self, value: Any, scope: Scope, at: Anchor, space: str) -> None:
        """A value a property holds, evaluated in `scope` where a name means a `space`: a term, a helper, a part, a
        statement standing in a term's place, a container of them, or a scalar."""
        if isinstance(value, Objects.Listed):
            for i, element in enumerate(value.values):
                self.visit(element, scope, at.at(i, i), space)
            return
        if not hasattr(value, "as_schema"):
            return  # a scalar: a name a term holds is its own
        if Terms.is_term(value) and value.as_schema().name == _TYPES:
            space = "type"
        tag, record = _branch(value)
        if record.as_schema().name in _STATEMENTS:
            self.statement(record, scope, at.opened())
            return
        self.term(tag, record, scope, at, "type" if tag in _HERITAGE else space)

    def term(self, tag: str, record: Any, scope: Scope, at: Anchor, space: str) -> None:
        """A term, a helper or a part of kind `tag`, at `at`."""
        self.program.located(at, scope)
        handler = self.TERMS.get(tag)
        if handler is None:
            self.fields(record, scope, at, space)
        else:
            handler(self, record, Objects.properties(record), scope, at, space)

    def keeping(self, value: Any, scope: Scope, at: Anchor, space: str) -> None:
        """A term a name is written in as a `space`, which it keeps though the term is a type's."""
        self.term(*_branch(value), scope, at, space)

    def fields(self, record: Any, scope: Scope, at: Anchor, space: str) -> None:
        """A term's, a helper's or a part's properties, each evaluated in `scope`."""
        for name, value in Objects.properties(record).items():
            self.visit(value, scope, at.at(name, _rank(record, name)), space)

    def prop(self, record: Any, props: dict[str, Any], name: str, scope: Scope, at: Anchor, space: str) -> None:
        """A property of a statement, a term or a helper, evaluated in `scope`, where it is set."""
        if name in props:
            self.visit(props[name], scope, at.at(name, _rank(record, name)), space)

    def identifier(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.program.written(at, props["name"])
        self.program.means(at, space)
        self.prop(record, props, "decorators", scope, at, "value")
        self.prop(record, props, "typeAnnotation", scope, at, "type")

    @staticmethod
    def qualifier(space: str) -> str:
        """The meaning of `a` in `a.b` written as a `space`."""
        return "value" if space == "value" else "namespace"

    def member(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.visit(props["object"], scope, at.at("object", _rank(record, "object")), self.qualifier(space))
        if props.get("computed"):
            self.prop(record, props, "property", scope, at, "value")  # a property's name depends on the value

    def qualified(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.keeping(props["left"], scope, at.at("left", _rank(record, "left")), self.qualifier(space))

    def type_query(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.keeping(props["exprName"], scope, at.at("exprName", _rank(record, "exprName")), "value")
        self.prop(record, props, "typeArguments", scope, at, "type")

    def import_type(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.prop(record, props, "options", scope, at, space)  # its qualifier names the module's members
        self.prop(record, props, "typeArguments", scope, at, space)

    def property(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        if props.get("computed"):
            self.prop(record, props, "key", scope, at, "value")
        self.prop(record, props, "value", scope, at, "value")

    def keyed(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """An interface's member, or an object type's: its key, if computed, and its type."""
        if props.get("computed"):
            self.prop(record, props, "key", scope, at, "value")
        if "returnType" in record.as_schema().properties:  # a method's
            self.signature(record, props, Scope("function", None, scope, at), at)
        else:
            self.prop(record, props, "typeAnnotation", scope, at, "type")

    def index_signature(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        parameters = at.at("parameters", _rank(record, "parameters"))
        for i, parameter in enumerate(props["parameters"].values):  # its parameter names nothing
            held = _branch(parameter)[1]
            self.prop(held, Objects.properties(held), "typeAnnotation", scope, parameters.at(i, i), "type")
        self.prop(record, props, "typeAnnotation", scope, at, "type")

    def unnamed(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """A term whose names name no entity of the program: a meta-property."""

    def tuple_member(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.prop(record, props, "elementType", scope, at, "type")  # its label names nothing

    def jsx_name(self, value: Any, scope: Scope, at: Anchor) -> None:
        """An element's name: `Component` and the `a` of `a.b` name values; `div` and `svg:path` name HTML."""
        tag, root = _branch(value)
        member = tag == "jsxmemberexpression"
        while tag == "jsxmemberexpression":
            at = at.at("object", _rank(root, "object"))
            tag, root = _branch(Objects.properties(root)["object"])
        if tag == "jsxidentifier" and (member or not Objects.properties(root)["name"][:1].islower()):
            self.program.located(at, scope)
            self.program.written(at, Objects.properties(root)["name"])
            self.program.means(at, "value")

    def jsx_opening(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.jsx_name(props["name"], scope, at.at("name", _rank(record, "name")))
        self.prop(record, props, "typeArguments", scope, at, "type")
        self.prop(record, props, "attributes", scope, at, "value")

    def jsx_closing(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.jsx_name(props["name"], scope, at.at("name", _rank(record, "name")))

    def jsx_attribute(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.prop(record, props, "value", scope, at, "value")

    def function(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, entity: Entity | None) -> None:
        """A function, an arrow function, a method's value or a function's declaration: the scope it opens, holding
        its type parameters and parameters, and its body, a block or an arrow's expression."""
        inner = Scope("function", entity, scope, at)
        signature = record.as_schema().name.endswith(("TSDeclareFunction", "TSEmptyBodyFunctionExpression"))
        if entity is not None and (entity.scope is None or not signature):
            entity.scope = inner  # an overloaded function's scope is its implementation's
        if "id" in props and record.as_schema().name.endswith("FunctionExpression"):  # its name is its own
            self.program.declares(at, self.bind(inner, Objects.properties(props["id"])["name"],
                                                at.at("id", _rank(record, "id")), "function"))
        self.signature(record, props, inner, at)
        if "body" in props and _statements(props["body"]):  # a function's declaration's
            self.body(props["body"], inner, at.child("body", None, _rank(record, "body")))
        else:  # an arrow's expression
            self.prop(record, props, "body", inner, at, "value")
        if "block" in props:
            self.body(_branch(props["block"])[1], inner, at.at("block", _rank(record, "block")).opened())

    def function_expression(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.function(record, props, scope, at, None)

    def signature(self, record: Any, props: dict[str, Any], inner: Scope, at: Anchor) -> None:
        """A signature's type parameters, parameters and return type, which bind and are in `inner`."""
        if "typeParameters" in props:
            self.type_parameters(props["typeParameters"], inner,
                                 at.at("typeParameters", _rank(record, "typeParameters")))
        parameters = at.at("params", _rank(record, "params"))
        for i, parameter in enumerate(_many(props.get("params"))):
            self.target(parameter, inner, "parameter", inner, parameters.at(i, i))
        self.prop(record, props, "returnType", inner, at, "type")

    def signature_type(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """A function type, a constructor type, or a call or construct signature: a scope of its own."""
        self.signature(record, props, Scope("function", None, scope, at), at)

    def class_(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """A class's declaration or expression: its name, its heritage in its type parameters' scope, and its
        members."""
        self.prop(record, props, "decorators", scope, at, "value")
        expression = "classBody" in record.as_schema().properties
        outer = Scope("block", None, scope, at) if expression and "id" in props else scope  # its name is its own
        entity = None
        if "id" in props:
            entity = self.bind(outer, Objects.properties(props["id"])["name"], at.at("id", _rank(record, "id")),
                               "class")
            self.program.declares(at, entity)
        heritage = self.generic(record, props, outer, at)
        members = Scope("class", entity, heritage, at)
        if entity is not None:
            entity.scope = members
        for name in ("superClass", "superTypeArguments", "implements"):
            self.prop(record, props, name, heritage, at, "value")
        if expression:
            body, where = _branch(props["classBody"])[1], at.at("classBody", _rank(record, "classBody")).opened()
        else:
            body, where = props["body"], at.child("body", None, _rank(record, "body"))
        self.program.located(where, members)
        rank = _rank(body, "body")
        for i, element in enumerate(_many(Objects.properties(body).get("body"))):
            self.element(_branch(element)[1], members, heritage, where.child("body", i, rank))

    def element(self, node: Any, members: Scope, scope: Scope, at: Anchor) -> None:
        """A class member: it is declared in `members`; its decorators, computed key and value are in `scope`."""
        self.program.located(at, members)
        kind = node.as_schema().name.rsplit(".", 1)[-1]
        props = Objects.properties(node)
        if kind == "StaticBlock":
            self.children(node, Scope("static block", None, scope, at), at)
            return
        if kind == "TSIndexSignature":
            self.term("tsindexsignature", node, scope, at, "value")
            return
        if "key" not in props:  # a comment, or invalid syntax
            self.statement(node, scope, at)
            return
        self.prop(node, props, "decorators", scope, at, "value")
        if props.get("computed"):
            self.prop(node, props, "key", scope, at, "value")
        if "methodKind" in props:
            entity = self.declare_member(node, props, members, at, "accessor" if props["methodKind"] in (
                "get", "set") else "method")
            value = at.at("value", _rank(node, "value"))
            self.program.located(value, scope)
            tag, function = _branch(props["value"])
            parameters = Objects.properties(function)
            self.function(function, parameters, scope, value, entity)
            if tag == "tsemptybodyfunctionexpression" and entity is not None:
                self.signatures.add(str(entity.declarations[-1]))
            where = value.at("params", _rank(function, "params"))
            for i, parameter in enumerate(_many(parameters.get("params"))):
                tag, held = _branch(parameter)
                if tag == "tsparameterproperty":  # its parameter, by its name
                    tag, name = _branch(Objects.properties(held)["parameter"])
                    if tag == "assignmentpattern":
                        name = _branch(Objects.properties(name)["left"])[1]
                    self.bind(members, Objects.properties(name)["name"], where.at(i, i), "property")
            return
        self.declare_member(node, props, members, at, "accessor" if kind in (
            "AccessorProperty", "TSAbstractAccessorProperty") else "property")
        self.prop(node, props, "typeAnnotation", scope, at, "type")
        self.prop(node, props, "value", scope, at, "value")

    def declare_member(self, record: Any, props: dict[str, Any], members: Scope, at: Anchor,
                       kind: str) -> Entity | None:
        """Declares a member named by its key, written at the key; None for a computed key, which names no member."""
        name = _key_name(props["key"], props.get("computed", False))
        if name is None:
            return None
        entity = self.bind(members, name, at.at("key", _rank(record, "key")), kind)
        self.program.declares(at, entity)
        return entity

    def mapped(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.prop(record, props, "value", scope, at, "type")  # its constraint
        inner = Scope("type parameters", None, scope, at)
        self.bind(inner, Objects.properties(props["key"])["name"], at.at("key", _rank(record, "key")),
                  "type parameter")
        self.prop(record, props, "nameType", inner, at, "type")
        self.prop(record, props, "body", inner, at, "type")  # its type

    def conditional(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.prop(record, props, "checkType", scope, at, "type")
        inner = Scope("type parameters", None, scope, at)  # where `infer` binds, seen by the true branch
        self.prop(record, props, "extendsType", inner, at, "type")
        self.prop(record, props, "trueType", inner, at, "type")
        self.prop(record, props, "falseType", scope, at, "type")

    def infer(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.type_parameter(props["typeParameter"], scope, at.at("typeParameter", _rank(record, "typeParameter")))

    def predicate(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        self.keeping(props["parameterName"], scope, at.at("parameterName", _rank(record, "parameterName")), "value")
        self.prop(record, props, "typeAnnotation", scope, at, "type")

    def asserted(self, record: Any, props: dict[str, Any], scope: Scope, at: Anchor, space: str) -> None:
        """`x as T`, `x satisfies T` or `<T>x`, where in `as const` the name `const` names nothing."""
        tag, annotation = _branch(props["typeAnnotation"])
        named = Objects.properties(annotation)
        const = tag == "tstypereference" and "typeArguments" not in named and Objects.properties(
            _branch(named["typeName"])[1]).get("name") == "const"
        for name in props:
            if name != "typeAnnotation" or not const:
                self.prop(record, props, name, scope, at, "value")

    TERMS: dict[str, Any] = {
        "identifier": identifier, "memberexpression": member, "tsqualifiedname": qualified, "tstypequery": type_query,
        "tsimporttype": import_type, "property": property, "tspropertysignature": keyed, "tsmethodsignature": keyed,
        "tsindexsignature": index_signature, "metaproperty": unnamed, "tsnamedtuplemember": tuple_member,
        "jsxopeningelement": jsx_opening, "jsxclosingelement": jsx_closing, "jsxattribute": jsx_attribute,
        "functionexpression": function_expression, "arrowfunctionexpression": function_expression,
        "tsemptybodyfunctionexpression": function_expression, "tsfunctiontype": signature_type,
        "tsconstructortype": signature_type, "tscallsignaturedeclaration": signature_type,
        "tsconstructsignaturedeclaration": signature_type, "classexpression": class_, "tsmappedtype": mapped,
        "tsconditionaltype": conditional, "tsinfertype": infer, "tstypepredicate": predicate,
        "tsasexpression": asserted, "tssatisfiesexpression": asserted, "tstypeassertion": asserted,
    }

    # Statements

    def statement(self, node: Any, scope: Scope, at: Anchor) -> None:
        """A statement, a clause or invalid syntax, at `at`."""
        self.program.located(at, scope)
        handler = self.STATEMENTS.get(node.as_schema().name.rsplit(".", 1)[-1], _Definer.parts)
        handler(self, node, Objects.properties(node), scope, at)

    def child(self, node: Any, name: str, value: Any, scope: Scope, at: Anchor) -> None:
        """The statements, clauses, members or errors `node`'s property `name` holds, each at its place."""
        rank = _rank(node, name)
        if isinstance(value, Objects.Listed):
            for i, element in enumerate(value.values):
                self.statement(_branch(element)[1], scope, at.child(name, i, rank))
        else:
            self.statement(_branch(value)[1], scope, at.child(name, None, rank))

    def children(self, node: Any, scope: Scope, at: Anchor) -> None:
        """The statements a statement, a clause, a block or an error holds, in source order, in `scope`."""
        for name, value in Objects.properties(node).items():
            if _statements(value):
                self.child(node, name, value, scope, at)

    def body(self, node: Any, scope: Scope, at: Anchor) -> None:
        """A block that is a function's body or a clause's, whose statements are in `scope`, the scope it opens."""
        self.program.located(at, scope)
        self.children(node, scope, at)

    def parts(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """A statement's properties, each in `scope`: its statements at their places, its terms evaluated."""
        for name, value in props.items():
            if _statements(value):
                self.child(node, name, value, scope, at)
            else:
                self.visit(value, scope, at.at(name, _rank(node, name)), "value")

    def unnamed_statement(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        """A statement whose names name no entity of the program: a `break`'s or `continue`'s label, an `export *`."""

    def labeled(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.children(node, scope, at)

    def block(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.children(node, Scope("block", None, scope, at), at)

    def loop(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.parts(node, props, Scope("block", None, scope, at), at)

    def switch(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.prop(node, props, "discriminant", scope, at, "value")
        self.children(node, Scope("block", None, scope, at), at)

    def catch(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        inner = Scope("block", None, scope, at)
        if "param" in props:
            self.target(props["param"], inner, "variable", inner, at.at("param", _rank(node, "param")))
        self.body(props["body"], inner, at.child("body", None, _rank(node, "body")))

    def variables(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        binding = self.var_scope(scope) if props["declarationKind"] == "var" else scope
        declarations = at.at("declarations", _rank(node, "declarations"))
        for i, declarator in enumerate(props["declarations"].values):
            each = declarations.at(i, i)
            self.program.located(each, scope)
            fields = Objects.properties(declarator)
            self.target(fields["id"], binding, "variable", scope, each.at("id", _rank(declarator, "id")))
            self.prop(declarator, fields, "init", scope, each, "value")

    def function_declaration(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        entity = None
        if "id" in props:  # `export default function () {}` declares none
            entity = self.bind(scope, Objects.properties(props["id"])["name"], at.at("id", _rank(node, "id")),
                               "function")
            self.program.declares(at, entity)
            if "body" not in props:
                self.signatures.add(str(entity.declarations[-1]))
        self.function(node, props, scope, at, entity)

    def class_declaration(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.class_(node, props, scope, at, "value")

    def interface(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        entity = self.owner(scope, Objects.properties(props["id"])["name"], at.at("id", _rank(node, "id")),
                            "interface", at)
        self.program.declares(at, entity)
        members: Scope = entity.scope  # type: ignore[assignment]
        inner = self.generic(node, props, scope, at)
        self.prop(node, props, "extends", inner, at, "type")
        body = at.at("body", _rank(node, "body"))
        self.program.located(body, members)
        items = body.at("body", _rank(props["body"], "body"))
        for i, item in enumerate(_many(Objects.properties(props["body"]).get("body"))):
            each = items.at(i, i)
            self.program.located(each, members)
            tag, record = _branch(item)
            if tag in ("tspropertysignature", "tsmethodsignature"):
                fields = Objects.properties(record)
                kind = "property" if tag == "tspropertysignature" else "accessor" if fields["methodKind"] in (
                    "get", "set") else "method"
                member = self.declare_member(record, fields, members, each, kind)
                if member is not None:
                    self.signatures.add(str(member.declarations[-1]))  # a signature declares, and defines nothing
            self.term(tag, record, inner, each, "type")

    def type_alias(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.program.declares(at, self.bind(scope, Objects.properties(props["id"])["name"],
                                            at.at("id", _rank(node, "id")), "type alias"))
        self.prop(node, props, "typeAnnotation", self.generic(node, props, scope, at), at, "type")

    def enum(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        entity = self.owner(scope, Objects.properties(props["id"])["name"], at.at("id", _rank(node, "id")), "enum", at)
        self.program.declares(at, entity)
        members: Scope = entity.scope  # type: ignore[assignment]
        body = at.at("body", _rank(node, "body"))
        self.program.located(body, members)
        items = body.at("members", _rank(props["body"], "members"))
        for i, item in enumerate(_many(Objects.properties(props["body"]).get("members"))):
            each = items.at(i, i)
            tag, record = _branch(item)
            if tag != "tsenummember":  # a comment, or invalid syntax
                self.visit(item, members, each, "value")
                continue
            self.program.located(each, members)
            fields = Objects.properties(record)
            name = _key_name(fields["id"], fields.get("computed", False))
            if name is None:
                self.prop(record, fields, "id", members, each, "value")
            else:
                self.program.declares(each, self.bind(members, name, each.at("id", _rank(record, "id")),
                                                      "enum member"))
            self.prop(record, fields, "initializer", members, each, "value")

    def module(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        inner = scope
        if props["moduleKind"] == "global":  # `declare global`: its names are the program's
            inner = self.program.root
        else:
            names: list[tuple[str, Anchor, str]] = []  # `namespace a.b.c` declares `a`, `a.b` and `a.b.c`
            place = at.at("id", _rank(node, "id"))
            tag, name = _branch(props["id"])
            while tag == "tsqualifiedname":
                self.program.located(place, scope)
                fields = Objects.properties(name)
                names.insert(0, (Objects.properties(fields["right"])["name"],
                                 place.at("right", _rank(name, "right")), "namespace"))
                place = place.at("left", _rank(name, "left"))
                tag, name = _branch(fields["left"])
            fields = Objects.properties(name)
            names.insert(0, (fields["value"], place, "module") if tag == "literal" else (
                fields["name"], place, "namespace"))
            for name, place, kind in names:
                entity = self.owner(inner, name, place, kind, at)
                self.program.declares(at, entity)
                inner = entity.scope  # type: ignore[assignment]
        if "body" in props:
            self.body(props["body"], inner, at.child("body", None, _rank(node, "body")))

    def import_(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        specifiers = at.at("specifiers", _rank(node, "specifiers"))
        for i, specifier in enumerate(_many(props.get("specifiers"))):
            each = specifiers.at(i, i)
            self.program.located(each, scope)
            record = _branch(specifier)[1]
            local = Objects.properties(record)["local"]
            self.bind(scope, Objects.properties(local)["name"], each.at("local", _rank(record, "local")), "import")

    def import_equals(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        entity = self.bind(scope, Objects.properties(props["id"])["name"], at.at("id", _rank(node, "id")), "import")
        self.program.declares(at, entity)
        tag, reference = _branch(props["moduleReference"])
        names: list[str] = []
        while tag == "tsqualifiedname":
            fields = Objects.properties(reference)
            names.insert(0, Objects.properties(fields["right"])["name"])
            tag, reference = _branch(fields["left"])
        if tag == "identifier":  # not `require("m")`
            self.imports.append((entity, [Objects.properties(reference)["name"], *names], scope))
        self.prop(node, props, "moduleReference", scope, at, "namespace")

    def export_named(self, node: Any, props: dict[str, Any], scope: Scope, at: Anchor) -> None:
        self.children(node, scope, at)
        if "source" in props:  # its names are another module's
            return
        specifiers = at.at("specifiers", _rank(node, "specifiers"))
        for i, specifier in enumerate(_many(props.get("specifiers"))):
            each = specifiers.at(i, i)
            self.program.located(each, scope)
            local = each.at("local", _rank(specifier, "local"))
            self.program.located(local, scope)  # it exports whatever the name means
            self.program.written(local, Objects.properties(_branch(Objects.properties(specifier)["local"])[1])["name"])

    STATEMENTS: dict[str, Any] = {
        "VariableDeclaration": variables, "FunctionDeclaration": function_declaration,
        "TSDeclareFunction": function_declaration, "ClassDeclaration": class_declaration,
        "TSInterfaceDeclaration": interface, "TSTypeAliasDeclaration": type_alias, "TSEnumDeclaration": enum,
        "TSModuleDeclaration": module, "ImportDeclaration": import_, "TSImportEqualsDeclaration": import_equals,
        "ExportNamedDeclaration": export_named, "ExportAllDeclaration": unnamed_statement,
        "BreakStatement": unnamed_statement, "ContinueStatement": unnamed_statement, "LabeledStatement": labeled,
        "BlockStatement": block, "ForStatement": loop, "ForInStatement": loop, "ForOfStatement": loop,
        "SwitchStatement": switch, "CatchClause": catch,
    }

    def define(self, node: Any) -> Program:
        program = self.program
        program.located(program.root.node, program.root)
        self.children(node, program.root, program.root.node)
        for entity, names, scope in self.imports:  # `import a = b.c`, once every namespace is declared
            found = [e for e in _resolve(scope, names[0], "namespace") if e is not entity]
            for name in names[1:]:
                scopes = [e.resolved().scope for e in found if e.resolved().scope is not None]
                found = scopes[0].lookup(name) if scopes else []  # type: ignore[union-attr]
            entity.target = found[0] if found else None
        for entity in program.entities():
            entity.declarations.sort(key=lambda anchor: anchor.order)
            entity.definition = next((d for d in entity.declarations if str(d) not in self.signatures), None)
        return program


def define(store: Any, path: str) -> Program:
    """The entities the program at `path` declares, in their scopes (`define_file`), read within a transaction of its
    own, so called with none open on `store`; LookupError where the workspace holds no file at `path`."""
    with store.transaction():
        return define_file(store, store.singleton(WORKSPACE).files({"path": path}))  # LookupError, where it holds none


def define_file(store: Any, program: Any) -> Program:
    """The entities a program declares, in their scopes: its visitor, a `Programs.TypeScript5.Program` of `store`, read
    within the caller's transaction. What it gives back holds no visitor, so it outlives the transaction."""
    reference = References.of(store, program)
    plain = Plain.ToPlain(store)(reference.as_schema(), reference)["path"]
    path = plain["next"]["entry"]["properties"]["path"]  # its key in the workspace's files
    return _Definer(Program(path, Anchor(""))).define(program)


def _resolve(scope: Scope | None, name: str, space: str | None) -> list[Entity]:
    """Unqualified lookup of `name` from `scope`, outwards, finding only entities with the meaning `space` (any, for
    None)."""
    while scope is not None:
        found = [e for e in scope.lookup(name) if space is None or space in MEANINGS[e.kind]]
        if found:
            return found
        scope = scope.parent
    return []


def referents(program: Program, at: Any) -> list[Entity]:
    """The entities the name written at `at` (an `Anchor`, or its text) refers to, looked up from where it is, with the
    meaning it has there: the one it binds or declares, or the ones its name resolves to. A place where no name is
    written, a property's name (which depends on a value) and a qualified name's later parts (on its first) find
    nothing."""
    name = program.name_at(at)
    if name is None:
        return []
    entity = program.entity_of(at)
    return [entity] if entity is not None else _resolve(program.scope_of(at), name, program.space_of(at))
