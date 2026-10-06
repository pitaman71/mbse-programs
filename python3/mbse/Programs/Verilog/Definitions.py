"""Definitions: the entities a Verilog source text declares, in its scopes, as IEEE 1800 resolves names (3.13, 23.9,
26.3).

- Scopes: the compilation unit (where design units, packages and `$unit`'s declarations are), each package, module,
  interface, program and class, each function and task, and each block: `begin`/`fork` blocks, generate blocks and
  `for` loops, named or not.
- Entity kinds: 'module', 'interface', 'program', 'package', 'parameter', 'localparam', 'type parameter', 'port',
  'net', 'variable', 'type', 'enumerator', 'genvar', 'modport', 'function', 'task', 'argument', 'instance', 'block', 'class'
  and 'import'. An enumeration's members are declared where the enumeration is, as SystemVerilog does.
- A non-ANSI port is one entity, which the header names and a port declaration declares.
- `import p::x` declares an 'import' entity whose `target` is `p::x`; `import p::*` makes the package's names visible
  where nothing nearer declares them, as wildcard imports do.
- A class's members are found in it, then in its base class (`extends`), or for an interface class in the interface
  classes it extends. A method defined outside its class (`function void c::f()`) is the entity its prototype
  declares, and its body sees the class's members.
- Lookup goes outward from a block to its design unit, then to the compilation unit. A package's and a class's names
  are qualified with `::` (`logger_pkg::FIELDS`, `packet::new`), a design unit's and a block's with `.`
  (`sampler.counter.count`).

Not resolved: a member after `.` (of a structure, an object, an interface port or a hierarchical path), what an
instance's module declares, and a forward `typedef` (the declaration it announces is the entity).
"""

from __future__ import annotations

from typing import Any

from ..Framework.Definitions import Entity, Program, Scope
from ..Framework.Syntax import SyntaxNode, children
from . import Syntax as S

__all__ = ["define", "referents"]

_UNITS = {S.ModuleDeclaration: "module", S.InterfaceDeclaration: "interface", S.ProgramDeclaration: "program",
          S.PackageDeclaration: "package"}


class _Definer:
    def __init__(self, unit: S.SourceText):
        self.root = Scope("compilation unit", None, None, unit, separator=".")
        self.program = Program(self.root)
        self.imports: list[tuple[Entity, S.ImportItem, Scope]] = []
        self.wildcards: list[tuple[Scope, S.ImportItem]] = []
        self.classes: list[tuple[Scope, S.ClassDeclaration]] = []

    def entity(self, scope: Scope, kind: str, name: S.Identifier, node: Any) -> Entity:
        """The entity `name` declares in `scope`: a new one, or for a port or an argument declared twice (a non-ANSI
        port; a method's prototype and its definition) the one already there."""
        existing = [e for e in scope.names.get(name.spelling, []) if e.kind == kind and kind in ("port", "argument")]
        entity = existing[0] if existing else self.program.add(Entity(kind, name.spelling, scope))
        scope.declare(entity)
        entity.declarations.append(node)
        if entity.definition is None:
            entity.definition = node
        self.program.declares(name, entity)
        self.program.declares(node, entity)
        return entity

    def scoped(self, scope: Scope, kind: str, name: S.Identifier | None, node: Any, scope_kind: str,
               separator: str | None = None) -> Scope:
        """A new scope for `node`, owned by an entity of `kind` when it is named."""
        owner = self.entity(scope, kind, name, node) if name is not None else None
        inner = Scope(scope_kind, owner, scope, node, separator=separator)
        if owner is not None:
            owner.scope = inner
        return inner

    def visit(self, node: Any, scope: Scope) -> None:
        """Records `node` and what it declares in `scope`, then its children in the scopes they are in."""
        self.program.located(node, scope)
        method = self.METHODS.get(type(node))
        if method is not None:
            method(self, node, scope)
            return
        for _, _, child in children(node):
            self.visit(child, scope)

    def visit_all(self, nodes: list[Any], scope: Scope) -> None:
        for node in nodes:
            self.visit(node, scope)

    def locate(self, node: Any, scope: Scope) -> None:
        """Records `node` and every syntax node under it as in `scope`, declaring nothing."""
        self.program.located(node, scope)
        for _, _, child in children(node):
            self.locate(child, scope)

    # Design units

    def design_unit(self, node: Any, scope: Scope) -> None:
        kind = _UNITS[type(node)]
        inner = self.scoped(scope, kind, node.name, node, kind, "::" if kind == "package" else ".")
        self.program.located(node.name, scope)
        for item in getattr(node, "imports", []):
            self.visit(item, inner)
        for item in [*getattr(node, "parameters", []), *getattr(node, "ports", []), *node.items]:
            self.visit(item, inner)

    def import_declaration(self, node: S.ImportDeclaration, scope: Scope) -> None:
        for item in node.items:
            self.locate(item, scope)
            if item.name is None:
                self.wildcards.append((scope, item))
            else:
                entity = self.entity(scope, "import", item.name, item)
                self.imports.append((entity, item, scope))

    # Declarations

    def parameter(self, node: Any, scope: Scope) -> None:
        if isinstance(node, S.TypeParameterDeclaration):
            for assignment in node.assignments:
                self.locate(assignment, scope)
                self.entity(scope, "type parameter", assignment.name, assignment)
            return
        if node.type is not None:
            self.visit(node.type, scope)
        for assignment in node.assignments:
            self.visit_all([*assignment.dimensions, *([assignment.value] if assignment.value is not None else [])],
                           scope)
            self.program.located(assignment, scope)
            self.program.located(assignment.name, scope)
            self.entity(scope, node.keyword, assignment.name, assignment)

    def port(self, node: Any, scope: Scope) -> None:
        for _, _, child in children(node):
            if child is not node.name:
                self.visit(child, scope)
        self.program.located(node.name, scope)
        self.entity(scope, "port", node.name, node)

    def declarators(self, node: Any, scope: Scope, kind: str) -> None:
        for _, _, child in children(node):
            if not isinstance(child, S.VariableDeclarator):
                self.visit(child, scope)
        for declarator in node.declarators:
            self.visit_all([*declarator.dimensions, *([declarator.value] if declarator.value is not None else [])],
                           scope)
            self.program.located(declarator, scope)
            self.program.located(declarator.name, scope)
            self.entity(scope, kind, declarator.name, declarator)

    def net(self, node: S.NetDeclaration, scope: Scope) -> None:
        self.declarators(node, scope, "net")

    def variable(self, node: S.VariableDeclaration, scope: Scope) -> None:
        self.declarators(node, scope, "variable")

    def port_declaration(self, node: S.PortDeclaration, scope: Scope) -> None:
        self.declarators(node, scope, "port")

    def typedef(self, node: S.TypedefDeclaration, scope: Scope) -> None:
        self.visit_all([node.type, *node.dimensions], scope)
        self.program.located(node.name, scope)
        self.entity(scope, "type", node.name, node)

    def enum(self, node: S.EnumType, scope: Scope) -> None:
        if node.base is not None:
            self.visit(node.base, scope)
        self.visit_all(node.dimensions, scope)
        for member in node.members:
            self.program.located(member, scope)
            self.program.located(member.name, scope)
            if member.value is not None:
                self.visit(member.value, scope)
            self.entity(scope, "enumerator", member.name, member)

    def genvar(self, node: S.GenvarDeclaration, scope: Scope) -> None:
        for name in node.names:
            self.program.located(name, scope)
            self.entity(scope, "genvar", name, node)

    def modport(self, node: S.ModportDeclaration, scope: Scope) -> None:
        for item in node.items:
            self.locate(item, scope)
            self.entity(scope, "modport", item.name, item)

    def subroutine(self, node: Any, scope: Scope) -> None:
        kind = "task" if isinstance(node, S.TaskDeclaration) else "function"
        name = node.name if isinstance(node.name, S.Identifier) else None
        if name is None:
            self.locate(node.name, scope)
            inner = self.out_of_block(node, scope, kind)
        else:
            inner = self.scoped(scope, kind, name, node, kind)
            self.program.located(name, scope)
        if isinstance(node, S.FunctionDeclaration) and node.type is not None:
            self.visit(node.type, scope)
        for port in node.ports:
            self.visit_all([*([port.type] if port.type is not None else []), *port.dimensions,
                            *([port.value] if port.value is not None else [])], inner)
            self.program.located(port, inner)
            self.program.located(port.name, inner)
            self.entity(inner, "argument", port.name, port)
        self.visit_all(node.body, inner)

    def out_of_block(self, node: Any, scope: Scope, kind: str) -> Scope:
        """The scope of a method defined outside its class, `c::f`: in the class's scope, and the entity of the
        prototype the class declares. Any other qualified name is not resolved."""
        qualified = node.name
        classes = [e for e in scope.resolve(qualified.scope.spelling) if e.kind == "class"] \
            if isinstance(qualified.scope, S.Identifier) and isinstance(qualified.name, S.Identifier) else []
        if not classes:
            return Scope(kind, None, scope, node)
        members = classes[0].scope.lookup(qualified.name.spelling)
        entity = members[0] if members and members[0].kind == kind else None
        if entity is None:
            return Scope(kind, None, classes[0].scope, node)
        entity.declarations.append(node)
        entity.definition = node
        self.program.declares(qualified.name, entity)
        self.program.declares(node, entity)
        return entity.scope  # the prototype's, where the definition's arguments are its arguments

    def class_declaration(self, node: S.ClassDeclaration, scope: Scope) -> None:
        inner = self.scoped(scope, "class", node.name, node, "class", "::")
        self.program.located(node.name, scope)
        self.visit_all([*([node.base] if node.base is not None else []), *node.arguments, *node.interfaces], scope)
        self.visit_all([*node.parameters, *node.items], inner)
        self.classes.append((inner, node))

    def instance(self, node: S.ModuleInstantiation, scope: Scope) -> None:
        self.program.located(node.module, scope)
        self.visit_all(node.parameters, scope)
        for instance in node.instances:
            self.program.located(instance, scope)
            self.program.located(instance.name, scope)
            self.visit_all([*instance.dimensions, *instance.connections], scope)
            self.entity(scope, "instance", instance.name, instance)

    def connection(self, node: S.NamedConnection, scope: Scope) -> None:
        self.program.located(node.name, scope)  # a port or argument of what is called: not resolved
        if node.value is not None:
            self.visit(node.value, scope)

    # Blocks

    def block(self, node: Any, scope: Scope) -> None:
        inner = self.scoped(scope, "block", node.name, node, "block")
        if node.name is not None:
            self.program.located(node.name, scope)
        self.visit_all(node.items, inner)

    def generate_for(self, node: S.GenerateFor, scope: Scope) -> None:
        self.program.located(node.name, scope)
        self.visit_all([node.start, node.condition, node.step, node.body], scope)

    def for_statement(self, node: S.ForStatement, scope: Scope) -> None:
        inner = Scope("block", None, scope, node)
        self.visit_all([*node.initializers, *([node.condition] if node.condition is not None else []), *node.steps,
                        node.body], inner)

    def foreach(self, node: S.ForeachStatement, scope: Scope) -> None:
        self.visit(node.array, scope)
        inner = Scope("block", None, scope, node)
        for variable in node.variables:
            self.program.located(variable, inner)
            self.entity(inner, "variable", variable, node)
        self.visit(node.body, inner)

    METHODS = {
        S.ModuleDeclaration: design_unit, S.InterfaceDeclaration: design_unit, S.ProgramDeclaration: design_unit,
        S.PackageDeclaration: design_unit, S.ImportDeclaration: import_declaration, S.ParameterDeclaration: parameter,
        S.TypeParameterDeclaration: parameter, S.AnsiPort: port, S.InterfacePort: port, S.PortReference: port,
        S.NetDeclaration: net, S.VariableDeclaration: variable, S.PortDeclaration: port_declaration,
        S.TypedefDeclaration: typedef, S.EnumType: enum, S.GenvarDeclaration: genvar, S.ModportDeclaration: modport,
        S.FunctionDeclaration: subroutine, S.TaskDeclaration: subroutine, S.ModuleInstantiation: instance,
        S.NamedConnection: connection, S.SeqBlock: block, S.ParBlock: block, S.GenerateBlock: block,
        S.GenerateFor: generate_for, S.ForStatement: for_statement, S.ForeachStatement: foreach,
        S.ClassDeclaration: class_declaration,
    }

    def resolve_imports(self) -> None:
        packages = {e.name: e for e in self.root.entities() if e.kind == "package"}
        for entity, item, _ in self.imports:
            package = packages.get(item.package.spelling)
            if package is not None:  # a package always has its scope
                found = package.scope.lookup(item.name.spelling)
                if found:
                    entity.target = found[0]
        for scope, item in self.wildcards:
            package = packages.get(item.package.spelling)
            if package is not None and package.scope not in scope.using:
                scope.using.append(package.scope)

    def resolve_bases(self) -> None:
        """Each class's base, or an interface class's interfaces, as the scopes its lookup goes on to."""
        for inner, node in self.classes:
            for base in [node.base] if node.base is not None else node.interfaces if node.interface else []:
                found = [e for e in _lookup(inner.parent, base.name) if e.kind == "class"]
                if found:
                    inner.bases.append(found[0].scope)


def define(unit: S.SourceText) -> Program:
    """The entities a source text declares, in their scopes."""
    definer = _Definer(unit)
    definer.program.located(unit, definer.root)
    for item in unit.items:
        definer.visit(item, definer.root)
    definer.resolve_imports()
    definer.resolve_bases()
    return definer.program


def _spelling(name: Any) -> str:
    """The spelling of an identifier, or of a parameterized class's name."""
    return name.name.spelling if isinstance(name, S.ParameterizedName) else name.spelling


def _lookup(scope: Scope, name: Any) -> list[Entity]:
    """The entities a name finds from `scope`: an identifier or a parameterized class as lookup resolves it, and
    `p::c::x` as `x` in `c` in the package or class `p` that `p` resolves to."""
    if not isinstance(name, S.ScopedName):
        return scope.resolve(_spelling(name))
    found = scope.resolve(_spelling(name.scope))
    while True:  # each scope, a package or a class, in the one before it
        holders = [e for e in found if e.kind in ("package", "class")]
        if not holders:
            return []
        inner = holders[0].scope.lookup  # a package or a class always has its scope
        if not isinstance(name.name, S.ScopedName):
            return inner(_spelling(name.name))
        name = name.name
        found = inner(_spelling(name.scope))


def referents(program: Program, name: Any) -> list[Entity]:
    """The entities a `NameExpression`, an `Identifier` or a `ScopedName` of the program refers to, looked up from
    where it is: an identifier that declares an entity refers to it; `p::x` to `x` in the package or class `p`, found
    from where the name is, and `p::c::x` to `x` in `c` in `p`."""
    if isinstance(name, S.NameExpression):
        name = name.name
    if isinstance(name, S.ScopedName):
        return _lookup(program.scope_of(name) or program.root, name)
    scope = program.scope_of(name)
    if scope is None:
        return []
    entity = program.entity_of(name)
    if entity is not None:
        return [entity]
    out: list[Entity] = []
    for entity in scope.resolve(name.spelling):
        entity = entity.resolved() if entity.kind == "import" and entity.target is not None else entity
        if entity not in out:
            out.append(entity)
    return out
