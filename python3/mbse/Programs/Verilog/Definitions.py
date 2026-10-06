"""Definitions: the entities a Verilog source text declares, in its scopes, as IEEE 1800 resolves names (3.13, 23.9,
26.3).

- Scopes: the compilation unit (where design units, packages and `$unit`'s declarations are), each package, module,
  interface, program and class, each function and task, and each block: `begin`/`fork` blocks, generate blocks and
  `for` loops, named or not.
- Entity kinds: 'module', 'interface', 'program', 'package', 'parameter', 'localparam', 'type parameter', 'port',
  'net', 'variable', 'type', 'enumerator', 'genvar', 'modport', 'function', 'task', 'argument', 'instance', 'block',
  'class', 'constraint', 'property', 'sequence', 'let', 'clocking', 'clockvar', 'label', 'covergroup', 'coverpoint',
  'cross', 'bins' and 'import'. An enumeration's members are declared where the enumeration is, as SystemVerilog does;
  a member `name[2]` declares `name0` and `name1`, and `name[1:3]` declares `name1` to `name3` (with decimal numbers).
  A `nettype` declares a 'type'.
- A non-ANSI port is one entity, which the header names and a port declaration declares. An explicit port's own name
  (`.p(x)`) is outside the module: what it connects is found inside.
- `import p::x` declares an 'import' entity whose `target` is `p::x`; `import p::*` makes the package's names visible
  where nothing nearer declares them, as wildcard imports do.
- A class's members are found in it, then in its base class (`extends`), or for an interface class in the interface
  classes it extends. A method or a constraint defined outside its class (`function void c::f()`, `constraint c::k`)
  is the entity its prototype declares, and its body sees the class's members. A `foreach` constraint's index
  variables are its own; `local::x` in `randomize() with` is `x` where the call is.
- A property, a sequence and a `let` have scopes of their own, where their ports are arguments; a named clocking block
  has one, where its signals are clockvars. A statement's label, and an assertion's, names a 'label'.
- A covergroup has a scope, where its ports and its `sample` function's are arguments; a coverpoint and a cross have
  scopes, where their bins are, and a labeled one is an entity. A bin's `with (filter)` has a scope where `item` is.
- An array method's `with (expression)` has its own scope, where the iterator is a variable: the name the call's
  argument gives it (`find(x) with (x > 0)`), or `item`.
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

    def entity(self, scope: Scope, kind: str, name: S.Identifier, node: Any, spelling: str | None = None) -> Entity:
        """The entity `name` declares in `scope`, as `spelling` if it is given: a new one, or for a port or an argument
        declared twice (a non-ANSI port; a method's prototype and its definition) the one already there."""
        spelling = name.spelling if spelling is None else spelling
        existing = [e for e in scope.names.get(spelling, []) if e.kind == kind and kind in ("port", "argument")]
        entity = existing[0] if existing else self.program.add(Entity(kind, spelling, scope))
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

    def explicit_port(self, node: Any, scope: Scope) -> None:
        if node.value is not None:  # its name is outside, and not looked up
            self.visit(node.value, scope)

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
            self.visit_all([p for p in (member.left, member.right, member.value) if p is not None], scope)
            if member.left is None:
                self.entity(scope, "enumerator", member.name, member)
                continue
            declared = [self.entity(scope, "enumerator", member.name, member, f"{member.name.spelling}{number}")
                        for number in _numbers(member.left, member.right)]
            if declared:  # the member's name declares the first
                self.program.declares(member.name, declared[0])
                self.program.declares(member, declared[0])

    def net_type(self, node: S.NetTypeDeclaration, scope: Scope) -> None:
        self.visit_all([node.type, *([node.function] if node.function is not None else [])], scope)
        self.program.located(node.name, scope)
        self.entity(scope, "type", node.name, node)

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
        """The scope of a method or a constraint defined outside its class, `c::f`: in the class's scope, and the
        entity of the prototype the class declares. Any other qualified name is not resolved."""
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
        # a method's prototype's scope, where the definition's arguments are its arguments; a constraint has none
        return entity.scope or Scope(kind, entity, classes[0].scope, node)

    def class_declaration(self, node: S.ClassDeclaration, scope: Scope) -> None:
        inner = self.scoped(scope, "class", node.name, node, "class", "::")
        self.program.located(node.name, scope)
        self.visit_all([*([node.base] if node.base is not None else []), *node.arguments, *node.interfaces], scope)
        self.visit_all([*node.parameters, *node.items], inner)
        self.classes.append((inner, node))

    def constraint_declaration(self, node: S.ConstraintDeclaration, scope: Scope) -> None:
        if isinstance(node.name, S.Identifier):
            self.program.located(node.name, scope)
            self.entity(scope, "constraint", node.name, node)
            inner = scope
        else:
            self.locate(node.name, scope)
            inner = self.out_of_block(node, scope, "constraint")
        self.visit_all(node.items, inner)

    def covergroup(self, node: S.CovergroupDeclaration, scope: Scope) -> None:
        if node.clock is not None:
            self.visit(node.clock, scope)
        inner = self.scoped(scope, "covergroup", node.name, node, "covergroup")
        self.program.located(node.name, scope)
        for port in [*node.ports, *(node.sample.ports if node.sample is not None else [])]:
            self.visit_all([*([port.type] if port.type is not None else []), *port.dimensions,
                            *([port.value] if port.value is not None else [])], inner)
            self.program.located(port, inner)
            self.program.located(port.name, inner)
            self.entity(inner, "argument", port.name, port)
        if node.sample is not None:
            self.program.located(node.sample, inner)
        self.visit_all(node.items, inner)

    def coverpoint(self, node: Any, scope: Scope) -> None:
        if isinstance(node, S.Coverpoint):
            parts = [*([node.type] if node.type is not None else []), node.expression]
            kind, body = "coverpoint", node.items
        else:
            kind, parts, body = "cross", node.items, node.body
        self.visit_all([*parts, *([node.condition] if node.condition is not None else [])], scope)
        inner = self.scoped(scope, kind, node.label, node, kind)
        if node.label is not None:
            self.program.located(node.label, scope)
        self.visit_all(body, inner)

    def bins(self, node: Any, scope: Scope) -> None:
        self.program.located(node.name, scope)
        self.entity(scope, "bins", node.name, node)
        if isinstance(node, S.BinsSelection):
            parts = [node.select]
        else:
            parts = [*([node.size] if node.size is not None else []), node.initializer]
        self.visit_all([*parts, *([node.condition] if node.condition is not None else [])], scope.parent)

    def bins_filter(self, node: Any, scope: Scope) -> None:
        """Values with a `with (filter)`, where `item` is each value."""
        self.visit_all(node.values if isinstance(node, S.BinsValues) else [node.expression], scope)
        if node.filter is not None:
            inner = Scope("with", None, scope, node)
            item = self.program.add(Entity("variable", "item", inner))
            inner.declare(item)
            item.definition = node
            item.declarations.append(node)
            self.visit(node.filter, inner)

    def array_method_with(self, node: S.ArrayMethodWithExpression, scope: Scope) -> None:
        inner = Scope("with", None, scope, node)
        call = node.call
        arguments = call.arguments if isinstance(call, S.CallExpression) else []
        if len(arguments) == 1 and isinstance(arguments[0], S.NameExpression) \
                and isinstance(arguments[0].name, S.Identifier):  # `find(x)`: `x` names the iterator
            self.visit(call.callee, scope)
            self.locate(arguments[0], scope)
            self.entity(inner, "variable", arguments[0].name, arguments[0])
        else:
            self.visit(call, scope)
            iterator = self.program.add(Entity("variable", "item", inner))
            inner.declare(iterator)
            iterator.definition = node
            iterator.declarations.append(node)
        self.visit(node.expression, inner)

    def assertion_declaration(self, node: Any, scope: Scope) -> None:
        kind = {S.PropertyDeclaration: "property", S.SequenceDeclaration: "sequence"}.get(type(node), "let")
        inner = self.scoped(scope, kind, node.name, node, kind)
        self.program.located(node.name, scope)
        for port in node.ports:
            self.visit_all([*([port.type] if port.type is not None else []), *port.dimensions,
                            *([port.value] if port.value is not None else [])], inner)
            self.program.located(port, inner)
            self.program.located(port.name, inner)
            self.entity(inner, "argument", port.name, port)
        body = node.spec if isinstance(node, S.PropertyDeclaration) else \
            node.sequence if isinstance(node, S.SequenceDeclaration) else node.value
        self.visit_all([*getattr(node, "variables", []), body], inner)

    def clocking_declaration(self, node: S.ClockingDeclaration, scope: Scope) -> None:
        self.visit(node.clock, scope)
        inner = self.scoped(scope, "clocking", node.name, node, "clocking")
        if node.name is not None:
            self.program.located(node.name, scope)
        self.visit_all(node.items, inner)

    def clocking_signals(self, node: S.ClockingSignals, scope: Scope) -> None:
        for skew in (node.input_skew, node.output_skew):
            if skew is not None:
                self.visit(skew, scope)
        for signal in node.signals:
            self.program.located(signal, scope)
            self.program.located(signal.name, scope)
            if signal.value is not None:
                self.visit(signal.value, scope.parent)  # what it stands for is outside the block
            self.entity(scope, "clockvar", signal.name, signal)

    def labeled(self, node: Any, scope: Scope) -> None:
        label = node.label
        if label is not None:
            self.program.located(label, scope)
            self.entity(scope, "label", label, node)
        self.visit(node.statement if isinstance(node, S.LabeledStatement) else node.assertion, scope)

    def constraint_prototype(self, node: S.ConstraintPrototype, scope: Scope) -> None:
        self.program.located(node.name, scope)
        self.entity(scope, "constraint", node.name, node)

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

    def foreach(self, node: Any, scope: Scope) -> None:
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
        S.ExplicitPort: explicit_port, S.ExplicitAnsiPort: explicit_port,
        S.NetDeclaration: net, S.VariableDeclaration: variable, S.PortDeclaration: port_declaration,
        S.TypedefDeclaration: typedef, S.NetTypeDeclaration: net_type, S.EnumType: enum, S.GenvarDeclaration: genvar,
        S.ModportDeclaration: modport,
        S.FunctionDeclaration: subroutine, S.TaskDeclaration: subroutine, S.ModuleInstantiation: instance,
        S.NamedConnection: connection, S.SeqBlock: block, S.ParBlock: block, S.GenerateBlock: block,
        S.GenerateFor: generate_for, S.ForStatement: for_statement, S.ForeachStatement: foreach,
        S.ClassDeclaration: class_declaration, S.ConstraintDeclaration: constraint_declaration,
        S.ConstraintPrototype: constraint_prototype, S.ForeachConstraint: foreach,
        S.ArrayMethodWithExpression: array_method_with, S.PropertyDeclaration: assertion_declaration,
        S.SequenceDeclaration: assertion_declaration, S.LetDeclaration: assertion_declaration,
        S.ClockingDeclaration: clocking_declaration, S.ClockingSignals: clocking_signals, S.LabeledStatement: labeled,
        S.AssertionItem: labeled, S.CovergroupDeclaration: covergroup, S.Coverpoint: coverpoint,
        S.CoverCross: coverpoint,
        S.CoverageBins: bins, S.BinsSelection: bins, S.BinsValues: bins_filter, S.BinsExpression: bins_filter,
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


def _numbers(left: Any, right: Any) -> list[int]:
    """The numbers of an enumeration's member `name[left:right]`, or of `name[left]` 0 to `left - 1`; none when they
    are not decimal numbers."""
    bounds = [b.spelling.replace("_", "") if isinstance(b, S.IntegerLiteral) else "" for b in (left, right)
              if b is not None]
    if not all(b.isdigit() for b in bounds):
        return []
    if right is None:
        return list(range(int(bounds[0])))
    first, last = int(bounds[0]), int(bounds[1])
    step = 1 if last >= first else -1
    return list(range(first, last + step, step))


def _spelling(name: Any) -> str:
    """The spelling of an identifier, or of a parameterized class's name."""
    return name.name.spelling if isinstance(name, S.ParameterizedName) else name.spelling


def _lookup(scope: Scope, name: Any) -> list[Entity]:
    """The entities a name finds from `scope`: an identifier or a parameterized class as lookup resolves it,
    `p::c::x` as `x` in `c` in the package or class `p` that `p` resolves to, and `$unit::x` as `x` in the
    compilation unit."""
    if not isinstance(name, S.ScopedName):
        return scope.resolve(_spelling(name))
    if isinstance(name.scope, S.UnitName):  # `$unit::x`: in the compilation unit
        while scope.parent is not None:
            scope = scope.parent
        return _lookup(scope, name.name) if isinstance(name.name, S.ScopedName) else scope.lookup(_spelling(name.name))
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
    if isinstance(name, S.LocalName):
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
