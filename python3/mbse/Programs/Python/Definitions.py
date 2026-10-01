"""Definitions: the names a Python module binds, in the scopes Python gives them.

`define(module)` reads a module and returns a `Framework.Definitions.Program`, whose qualified names join with `.`
(`Shape.area`). Its entities have these kinds:

- 'class' and 'function', each with its own scope;
- 'variable': a name bound by assignment, `for`, `with ... as`, `except ... as`, `del`, a pattern's capture or an
  assignment expression;
- 'parameter' (of a function or lambda), 'type parameter' and 'type alias';
- 'import': a name an import binds (`import a.b` binds `a`).

There is one entity per name per scope: every node that binds the name is one of its `declarations`, in source order,
and the first is its `definition`. The first binding visited decides its kind: the module's names are visited first,
then each function's and class's, as Python's symbol tables are built.

Scopes are those of Python's execution model (§4.2): 'module', 'class', 'function', 'lambda', 'comprehension' and
'type parameters' (the annotation scope of a generic function, class or type alias). A name bound anywhere in a scope
is local to it, unless `global` declares it the module's or `nonlocal` the nearest enclosing function's. Names are
looked up outwards through enclosing functions to the module, past class bodies: every scope's parent is the nearest
enclosing scope that is not a class. Decorators, defaults, a class's bases and the first iterable of a comprehension
are in the enclosing scope, and an assignment expression in a comprehension binds in the scope around it.

What it does not do: resolve attributes (`a.b`, whose `b` depends on `a`'s value) or the members of imported modules,
follow `from module import *`, see names that `exec` or `globals()` bind, or treat builtins as entities.
"""

from __future__ import annotations

from collections import deque
from typing import Any

from ..Framework.Definitions import Entity, Program, Scope
from ..Framework.Syntax import children, walk
from . import Syntax as S

__all__ = ["define", "referents"]


class _Definer:
    """Declares what a module binds. Function and class bodies are visited once the scope around them is complete,
    so that `nonlocal` finds a binding that comes later in the enclosing function."""

    def __init__(self, module: S.Module):
        self.program = Program(Scope("module", None, None, module, separator="."))
        self.bodies: deque[tuple[list[Any], Scope]] = deque()

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

    def bind(self, scope: Scope, identifier: S.Identifier, node: Any, kind: str) -> Entity:
        """Binds `identifier` in `scope`, `node` binding it."""
        entity = self.entity(scope, identifier.spelling, kind)
        entity.declarations.append(node)
        self.program.declares(node, entity)
        self.program.declares(identifier, entity)
        self.program.located(identifier, scope)
        return entity

    def target(self, node: Any, scope: Scope) -> None:
        """An assignment target: names bind in `scope`, and other expressions are evaluated there."""
        self.program.located(node, scope)
        if isinstance(node, S.Name):
            self.bind(scope, node.id, node, "variable")
        elif isinstance(node, (S.Tuple, S.List)):
            for elt in node.elts:
                self.target(elt, scope)
        elif isinstance(node, (S.Starred, S.Parenthesized)):
            self.target(node.value, scope)
        else:
            self.visit(node, scope)

    def nonlocal_scope(self, scope: Scope, name: str) -> Scope | None:
        """The nearest enclosing function scope where `name` is bound, for `nonlocal name` in `scope`."""
        outer = scope.parent
        while outer is not None and outer.parent is not None:
            if outer.kind == "function" and name in outer.names:  # a lambda's body holds no `nonlocal`
                return outer
            outer = outer.parent
        return None

    # Visiting

    def visit(self, node: Any, scope: Scope) -> None:
        self.program.located(node, scope)
        method = self.HANDLERS.get(type(node))
        if method is not None:
            method(self, node, scope)
            return
        for _, _, child in children(node):
            self.visit(child, scope)

    def statements(self, statements: list[Any], scope: Scope) -> None:
        for statement in statements:
            self.visit(statement, scope)

    def visit_all(self, nodes: list[Any], scope: Scope) -> None:
        for node in nodes:
            if node is not None:
                self.visit(node, scope)

    def name(self, node: S.Name, scope: Scope) -> None:
        self.program.located(node.id, scope)

    def attribute(self, node: S.Attribute, scope: Scope) -> None:
        self.visit(node.value, scope)  # the attribute's name depends on the value: it is not located

    def keyword(self, node: S.Keyword, scope: Scope) -> None:
        self.visit(node.value, scope)

    def assign(self, node: S.Assign, scope: Scope) -> None:
        self.visit(node.value, scope)
        for target in node.targets:
            self.target(target, scope)

    def aug_assign(self, node: S.AugAssign, scope: Scope) -> None:
        self.visit(node.value, scope)
        self.target(node.target, scope)

    def ann_assign(self, node: S.AnnAssign, scope: Scope) -> None:
        self.visit(node.annotation, scope)
        if node.value is not None:
            self.visit(node.value, scope)
        self.target(node.target, scope)

    def delete(self, node: S.Delete, scope: Scope) -> None:
        for target in node.targets:
            self.target(target, scope)

    def for_(self, node: S.For | S.AsyncFor, scope: Scope) -> None:
        self.visit(node.iter, scope)
        self.target(node.target, scope)
        self.statements(node.body, scope)
        self.statements(node.orelse, scope)

    def with_(self, node: S.With | S.AsyncWith, scope: Scope) -> None:
        for item in node.items:
            self.program.located(item, scope)
            self.visit(item.context_expr, scope)
            if item.optional_vars is not None:
                self.target(item.optional_vars, scope)
        self.statements(node.body, scope)

    def handler(self, node: S.ExceptHandler, scope: Scope) -> None:
        if node.type is not None:
            self.visit(node.type, scope)
        if node.name is not None:
            self.bind(scope, node.name, node, "variable")
        self.statements(node.body, scope)

    def import_(self, node: S.Import | S.ImportFrom, scope: Scope) -> None:
        for alias in node.names:
            self.program.located(alias, scope)
            if alias.asname is not None:
                self.bind(scope, alias.asname, alias, "import")
            elif alias.name is not None:
                self.bind(scope, alias.name.names[0], alias, "import")  # `import a.b` binds `a`

    def global_(self, node: S.Global | S.Nonlocal, scope: Scope) -> None:
        for identifier in node.names:
            name = identifier.spelling
            outer = self.program.root if isinstance(node, S.Global) else self.nonlocal_scope(scope, name) or scope
            entity = self.entity(outer, name, "variable")
            scope.declare(entity)
            self.program.declares(identifier, entity)
            self.program.located(identifier, scope)

    def type_parameters(self, node: Any, scope: Scope) -> Scope:
        """The annotation scope of a generic function, class or type alias, with its type parameters; `scope`
        itself if it has none."""
        if not node.type_params:
            return scope
        inner = Scope("type parameters", None, self.enclosing(scope), node)
        for parameter in node.type_params:
            self.program.located(parameter, inner)
            self.bind(inner, parameter.name, parameter, "type parameter")
            bound = parameter.bound if isinstance(parameter, S.TypeVar) else None
            self.visit_all([bound, parameter.default_value], inner)
        return inner

    def function(self, node: S.FunctionDef | S.AsyncFunctionDef, scope: Scope) -> None:
        self.visit_all(node.decorator_list, scope)
        entity = self.bind(scope, node.name, node, "function")
        annotations = self.type_parameters(node, scope)
        inner = Scope("function", entity, self.enclosing(annotations), node)
        entity.scope = inner
        self.arguments(node.args, scope, annotations, inner)
        if node.returns is not None:
            self.visit(node.returns, annotations)
        self.bodies.append((node.body, inner))

    def arguments(self, node: S.Arguments, scope: Scope, annotations: Scope, inner: Scope) -> None:
        """Parameters bind in `inner`; their defaults are evaluated in `scope`, their annotations in
        `annotations`."""
        self.program.located(node, inner)
        for arg in [*node.posonlyargs, *node.args, node.vararg, *node.kwonlyargs, node.kwarg]:
            if arg is None:
                continue
            self.program.located(arg, inner)
            self.visit_all([arg.annotation], annotations)
            self.visit_all([arg.default_value], scope)
            self.bind(inner, arg.arg, arg, "parameter")

    def class_(self, node: S.ClassDef, scope: Scope) -> None:
        self.visit_all(node.decorator_list, scope)
        entity = self.bind(scope, node.name, node, "class")
        annotations = self.type_parameters(node, scope)
        self.visit_all([*node.bases, *node.keywords], annotations)
        entity.scope = Scope("class", entity, self.enclosing(annotations), node)
        self.bodies.append((node.body, entity.scope))

    def type_alias(self, node: S.TypeAlias, scope: Scope) -> None:
        self.program.located(node.name, scope)
        self.program.declares(node.name, self.bind(scope, node.name.id, node, "type alias"))
        self.visit(node.value, self.type_parameters(node, scope))

    def lambda_(self, node: S.Lambda, scope: Scope) -> None:
        inner = Scope("lambda", None, self.enclosing(scope), node)
        self.arguments(node.args, scope, scope, inner)
        self.visit(node.body, inner)

    def comprehension(self, node: S.ListComp | S.SetComp | S.GeneratorExp | S.DictComp, scope: Scope) -> None:
        inner = Scope("comprehension", None, self.enclosing(scope), node)
        for i, generator in enumerate(node.generators):
            self.program.located(generator, inner)
            self.visit(generator.iter, scope if i == 0 else inner)  # the first iterable is evaluated outside
            self.target(generator.target, inner)
            self.visit_all(generator.ifs, inner)
        if isinstance(node, S.DictComp):
            self.visit_all([node.key, node.value], inner)
        else:
            self.visit(node.elt, inner)

    def named_expr(self, node: S.NamedExpr, scope: Scope) -> None:
        self.visit(node.value, scope)
        outer = scope
        while outer.kind == "comprehension":
            outer = outer.parent  # type: ignore[assignment]  # it binds in the scope around the comprehensions
        self.program.located(node.target, scope)
        self.program.located(node.target.id, scope)
        self.bind(outer, node.target.id, node.target, "variable")

    def match_case(self, node: S.MatchCase, scope: Scope) -> None:
        self.visit(node.pattern, scope)
        self.visit_all([node.guard], scope)
        self.statements(node.body, scope)

    def capture(self, node: S.MatchAs | S.MatchStar, scope: Scope) -> None:
        if isinstance(node, S.MatchAs) and node.pattern is not None:
            self.visit(node.pattern, scope)
        if node.name is not None:
            self.bind(scope, node.name, node, "variable")

    def mapping(self, node: S.MatchMapping, scope: Scope) -> None:
        self.visit_all([*node.keys, *node.patterns], scope)
        if node.rest is not None:
            self.bind(scope, node.rest, node, "variable")

    def class_pattern(self, node: S.MatchClass, scope: Scope) -> None:
        self.visit_all([node.cls, *node.patterns, *node.kwd_patterns], scope)  # keyword names are attributes

    HANDLERS: dict[type, Any] = {
        S.Name: name, S.Attribute: attribute, S.Keyword: keyword, S.Assign: assign, S.AugAssign: aug_assign,
        S.AnnAssign: ann_assign, S.Delete: delete, S.For: for_, S.AsyncFor: for_, S.With: with_, S.AsyncWith: with_,
        S.ExceptHandler: handler, S.Import: import_, S.ImportFrom: import_, S.Global: global_, S.Nonlocal: global_,
        S.FunctionDef: function, S.AsyncFunctionDef: function, S.ClassDef: class_, S.TypeAlias: type_alias,
        S.Lambda: lambda_, S.ListComp: comprehension, S.SetComp: comprehension, S.GeneratorExp: comprehension,
        S.DictComp: comprehension, S.NamedExpr: named_expr, S.MatchCase: match_case, S.MatchAs: capture,
        S.MatchStar: capture, S.MatchMapping: mapping, S.MatchClass: class_pattern,
    }


def define(module: S.Module) -> Program:
    """The entities a module binds, in their scopes."""
    definer = _Definer(module)
    program = definer.program
    program.located(module, program.root)
    definer.bodies.append((module.body, program.root))
    while definer.bodies:
        body, scope = definer.bodies.popleft()
        definer.statements(body, scope)
    order = {id(node): i for i, node in enumerate(walk(module))}  # fields are in source order
    for entity in program.entities():
        entity.declarations.sort(key=lambda node: order[id(node)])
        entity.definition = entity.declarations[0] if entity.declarations else None
    return program


def referents(program: Program, name: Any) -> list[Entity]:
    """The entities a `Name`, or an `Identifier` of the program, refers to, looked up from where it is. An
    attribute's name depends on a value, and a keyword argument's on the function called, so they find nothing."""
    identifier = name.id if isinstance(name, S.Name) else name
    scope = program.scope_of(identifier)
    if scope is None:
        return []
    entity = program.entity_of(identifier)
    return [entity] if entity is not None else scope.resolve(identifier.spelling)
