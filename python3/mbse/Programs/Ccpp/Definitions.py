"""Definitions: the entities a C or C++ program declares, in the scopes the standard gives them.

`define(unit)` reads a translation unit and returns a `Framework.Definitions.Program`. Its entities have these kinds:

- 'namespace' (reopened namespaces are one entity) and 'namespace alias', whose `target` is the namespace;
- 'class' (also structs and unions), 'enumeration' and 'enumerator';
- 'function', one entity per signature, the types of its parameters as printed; a function's declarations and its
  definition are found by name and signature, also when the definition is out of line (`int A::f() { ... }`);
- 'variable', 'field' (a non-static data member), 'parameter' (of a function or lambda being defined) and
  'template parameter';
- 'type alias' (`typedef` and `using`), 'concept', 'label' and 'macro' (in `Program.macros`).

Scopes have the kinds 'namespace' (also the global scope), 'class', 'enumeration', 'function', 'block', 'template',
'lambda' and 'requires'. Inline and unnamed namespaces, unscoped enumerations and anonymous unions are transparent to
their enclosing scope, using-directives and `using enum` are followed, and a class looks names up in its bases.

What it does not do: evaluate preprocessing conditions (every branch's declarations are declared), tell explicit and
partial specializations from their primary template (they are its declarations), or declare what a friend declaration
declares.
"""

from __future__ import annotations

from typing import Any

from ..Framework.Definitions import Entity, Program, Scope
from ..Framework.Syntax import children
from . import Syntax as S
from ._Printer import Printer

__all__ = ["define", "name_of", "referents"]

_PRINTER = Printer()


def name_of(name: Any) -> str:
    """The name a `Name` node declares or refers to, as text: an identifier's spelling, a template's name without its
    arguments, `operator+`, `operator int*`, `~Point`, or a qualified name's last part."""
    if isinstance(name, S.QualifiedName):
        return name_of(name.name)
    if isinstance(name, S.TemplateId):
        return name_of(name.name)
    if isinstance(name, S.DestructorName):
        return "~" + (name_of(name.type) if isinstance(name.type, S.Name) else _PRINTER.text(name.type, 0))
    return _PRINTER.text(name, 0)


def _unnamed(declarator: Any) -> Any:
    """A copy of a declarator without its name, for printing the type it declares."""
    if declarator is None or isinstance(declarator, S.IdDeclarator):
        return None
    made = type(declarator)(**{f.name: getattr(declarator, f.name) for f in declarator.FIELDS})
    made.declarator = _unnamed(declarator.declarator)
    return made


def _signature(function: S.FunctionDeclarator) -> str:
    """A function's parameter types and qualifiers, as printed: `(int, const char*) const`."""
    types = []
    for p in function.parameters:
        if isinstance(p, S.EllipsisParameter):
            types.append("...")
        else:
            types.append(_PRINTER.text(S.TypeId(specifiers=p.specifiers, declarator=_unnamed(p.declarator)), 0))
    text = "(" + ", ".join(types) + ")"
    text += "".join(" " + q.keyword for q in function.qualifiers)
    return text + (" " + function.ref_qualifier if function.ref_qualifier is not None else "")


def _qualifiers(name: S.QualifiedName) -> list[str] | None:
    """The names of a qualified name's qualifiers; None if one is a decltype or splice, which only types tell."""
    names = [name_of(q) for q in name.qualifiers if isinstance(q, S.Name)]
    return names if len(names) == len(name.qualifiers) else None


def _resolve(name: Any, scope: Scope) -> list[Entity]:
    """The entities a `Name` node names, looked up from `scope`. Anything else, such as a decltype, names nothing
    found by name."""
    if isinstance(name, S.QualifiedName):
        names = _qualifiers(name)
        return [] if names is None else scope.qualified([*names, name_of(name.name)], from_global=name.global_scope)
    return scope.resolve(name_of(name))


def _keywords(specifiers: list[Any]) -> set[str]:
    return {s.keyword for s in specifiers if isinstance(s, S.DeclSpecifier)}


class _Definer:
    """Walks a tree, declaring entities into scopes and recording where every node is."""

    def __init__(self, unit: S.TranslationUnit):
        self.program = Program(Scope("namespace", None, None, unit))

    # Entities

    def entity(self, kind: str, name: str | None, scope: Scope, node: Any, *, definition: bool = False,
               signature: str | None = None) -> Entity:
        """The entity of this kind, name and signature in `scope`, declared there if it is new, with `node` among its
        declarations (and as its definition with `definition`, unless an earlier node defines it)."""
        found = None
        if name is not None and kind not in ("parameter", "template parameter", "label"):
            found = next((e for e in scope.names.get(name, []) if e.kind == kind and e.parent is scope
                          and e.signature == signature), None)
        if found is None:
            found = self.program.add(Entity(kind, name, scope))
            found.signature = signature
            scope.declare(found)
        found.declarations.append(node)
        if definition and found.definition is None:
            found.definition = node
        self.program.declares(node, found)
        return found

    def scope_for(self, entity: Entity, kind: str, parent: Scope, node: Any) -> Scope:
        """The entity's own scope, made the first time it is needed."""
        if entity.scope is None:
            entity.scope = Scope(kind, entity, parent, node)
        return entity.scope

    def target(self, name: Any, scope: Scope) -> Scope:
        """Where a declarator's name is declared: `scope`, or for a qualified name the scope its qualifiers name."""
        names = _qualifiers(name) if isinstance(name, S.QualifiedName) else None
        if names:
            found = scope.qualified(names, from_global=name.global_scope)
            scopes = [e.resolved().scope for e in found if e.resolved().scope is not None]
            if scopes:
                return scopes[0]
        return scope

    # Traversal

    def visit(self, node: Any, scope: Scope, lexical: Scope | None = None) -> None:
        """Records that `node` is in `scope`, then declares what it declares. `lexical` is where the scopes it opens
        are nested, when that is not `scope`: a template's parameters enclose what the template declares."""
        self.program.located(node, scope)
        handler = self.HANDLERS.get(type(node))
        if handler is not None:
            handler(self, node, scope, lexical or scope)
        else:
            self.visit_children(node, scope)

    def visit_children(self, node: Any, scope: Scope) -> None:
        for _, _, child in children(node):
            self.visit(child, scope)

    # Namespaces

    def namespace(self, node: S.NamespaceDefinition, scope: Scope, lexical: Scope) -> None:
        current = scope
        if not node.names:  # every unnamed namespace of a scope is the same one, transparent to the scope
            entity = next((s.owner for s in current.transparent if s.kind == "namespace" and s.owner is not None
                           and s.owner.name is None), None)
            if entity is None:
                entity = self.entity("namespace", None, current, node)
                current.transparent.append(self.scope_for(entity, "namespace", current, node))
            else:
                entity.declarations.append(node)
                self.program.declares(node, entity)
            current = entity.scope
        for i, part in enumerate(node.names):
            self.program.located(part, current)
            self.program.located(part.name, current)
            entity = self.entity("namespace", part.name.spelling, current, node)
            inner = self.scope_for(entity, "namespace", current, node)
            inline = part.inline or (node.inline and i == len(node.names) - 1)
            if inline and inner not in current.transparent:
                current.transparent.append(inner)
            current = inner
        for attribute in node.attributes:
            self.visit(attribute, scope)
        for item in node.items:
            self.visit(item, current)

    def namespace_alias(self, node: S.NamespaceAliasDefinition, scope: Scope, lexical: Scope) -> None:
        entity = self.entity("namespace alias", node.name.spelling, scope, node, definition=True)
        found = [e for e in _resolve(node.target, scope) if e.resolved().kind == "namespace"]
        entity.target = found[0] if found else None
        self.visit_children(node, scope)

    def using_directive(self, node: S.UsingDirective, scope: Scope, lexical: Scope) -> None:
        for entity in _resolve(node.name, scope):
            target = entity.resolved().scope
            if target is not None and target not in scope.using:
                scope.using.append(target)
        self.visit_children(node, scope)

    def using_declaration(self, node: S.UsingDeclaration, scope: Scope, lexical: Scope) -> None:
        for declarator in node.declarators:
            found = _resolve(declarator.name, scope)
            if found:
                for entity in found:
                    scope.declare(entity)
                self.program.declares(declarator, found[0])
            else:
                self.entity("using declaration", name_of(declarator.name), scope, declarator)
        self.visit_children(node, scope)

    def using_enum(self, node: S.UsingEnumDeclaration, scope: Scope, lexical: Scope) -> None:
        for entity in _resolve(node.type, scope):
            if entity.kind == "enumeration" and entity.scope is not None and entity.scope not in scope.transparent:
                scope.transparent.append(entity.scope)
        self.visit_children(node, scope)

    # Types

    def class_(self, node: S.ClassSpecifier, scope: Scope, lexical: Scope) -> None:
        name = name_of(node.name) if node.name is not None else None
        target = self.target(node.name, scope)
        entity = self.entity("class", name, target, node, definition=node.body is not None)
        for attribute in node.attributes:
            self.visit(attribute, scope)
        if node.name is not None:
            self.visit(node.name, scope)
        if node.body is None:
            return
        members = self.scope_for(entity, "class", lexical if target is scope else target, node)
        for base in node.bases:
            self.visit(base, scope)
            for found in _resolve(base.type, scope):  # a decltype or a splice finds nothing
                resolved = found.resolved()
                if resolved.kind == "class" and resolved.scope is not None and resolved.scope not in members.bases:
                    members.bases.append(resolved.scope)
        if name is None and node.key == "union" and target is scope:
            scope.transparent.append(members)  # an anonymous union's members are its enclosing scope's
        self.program.located(node.body, members)
        for item in node.body.items:
            self.visit(item, members)

    def enum(self, node: S.EnumSpecifier, scope: Scope, lexical: Scope) -> None:
        name = name_of(node.name) if node.name is not None else None
        target = self.target(node.name, scope)
        entity = self.entity("enumeration", name, target, node, definition=node.body is not None)
        for part in [*node.attributes, *([node.name] if node.name is not None else []),
                     *([node.base] if node.base is not None else [])]:
            self.visit(part, scope)
        if node.body is None:
            return
        members = self.scope_for(entity, "enumeration", target, node)
        if node.key == "enum" and members not in target.transparent:
            target.transparent.append(members)
        self.program.located(node.body, members)
        for item in node.body.enumerators:
            self.visit(item, members)

    def enumerator(self, node: S.Enumerator, scope: Scope, lexical: Scope) -> None:
        """An enumerator, listed directly or in a directive's branch, in its enumeration's scope."""
        self.entity("enumerator", node.name.spelling, scope, node, definition=True)
        self.visit_children(node, scope)

    # Declarations

    def simple(self, node: S.SimpleDeclaration, scope: Scope, lexical: Scope) -> None:
        keywords = _keywords(node.specifiers)
        for part in [*node.attributes, *node.specifiers]:
            if "friend" in keywords and isinstance(part, S.ClassSpecifier) and part.body is None:
                self.program.located(part, scope)
                self.visit_children(part, scope)
            else:
                self.visit(part, scope, lexical)
        for declarator in node.declarators:
            if "friend" not in keywords:
                self.declarator(declarator, keywords, scope, lexical)
            self.visit(declarator, scope)

    def declarator(self, node: S.InitDeclarator, keywords: set[str], scope: Scope, lexical: Scope) -> None:
        named, binder = S.binding(node.declarator)
        if isinstance(named, S.StructuredBindingDeclarator):
            for binding in named.bindings:
                inner, _ = S.binding(binding)
                self.program.declares(binding, self.entity("variable", name_of(inner.name), scope, binding,
                                                           definition=True))
            return
        if named is None:
            return
        target = self.target(named.name, scope)
        name = name_of(named.name)
        if "typedef" in keywords:
            entity = self.entity("type alias", name, target, node, definition=True)
        elif isinstance(binder, S.FunctionDeclarator):
            entity = self.entity("function", name, target, node, signature=_signature(binder))
        else:
            in_class = target.kind == "class"
            kind = "field" if in_class and "static" not in keywords else "variable"
            if target is not scope:  # an out-of-line definition, without `static`: the member declared before
                kind = next((e.kind for e in target.names.get(name, []) if e.kind in ("field", "variable")), kind)
            declares_only = ("extern" in keywords or (in_class and kind == "variable"
                                                      and not keywords & {"inline", "constexpr"}))
            entity = self.entity(kind, name, target, node,
                                 definition=node.initializer is not None or not declares_only)
        self.program.declares(named, entity)

    def function(self, node: S.FunctionDefinition, scope: Scope, lexical: Scope) -> None:
        for part in [*node.attributes, *node.specifiers]:
            self.visit(part, scope, lexical)
        named, binder = S.binding(node.declarator)
        target = self.target(named.name, scope)
        entity = None
        if "friend" not in _keywords(node.specifiers):
            signature = _signature(binder) if isinstance(binder, S.FunctionDeclarator) else None
            entity = self.entity("function", name_of(named.name), target, node, definition=True,
                                 signature=signature)
            self.program.declares(named, entity)
        inner = Scope("function", entity, lexical if target is scope else target, node)
        self.visit(node.declarator, scope)
        if isinstance(binder, S.FunctionDeclarator):
            for parameter in binder.parameters:
                self.parameter(parameter, inner, "parameter")
        for part in [*node.virt_specifiers, *([node.requires] if node.requires is not None else []),
                     *node.contracts, *node.initializers]:
            self.visit(part, inner)
        self.program.located(node.body, inner)
        if isinstance(node.body, S.CompoundStatement):
            self.block(node.body, inner)
        else:
            self.visit_children(node.body, inner)

    def parameter(self, node: Any, scope: Scope, kind: str) -> None:
        """Declares a parameter that names itself, in `scope`."""
        named, _ = S.binding(getattr(node, "declarator", None))
        if named is not None and not isinstance(named, S.StructuredBindingDeclarator):
            entity = self.entity(kind, name_of(named.name), scope, node, definition=True)
            self.program.declares(named, entity)

    def template(self, node: S.TemplateDeclaration, scope: Scope, lexical: Scope) -> None:
        parameters = Scope("template", None, lexical, node)
        for parameter in node.parameters:
            self.program.located(parameter, parameters)
            if isinstance(parameter, (S.TypeParameter, S.TemplateTemplateParameter)):
                if parameter.name is not None:
                    self.entity("template parameter", parameter.name.spelling, parameters, parameter,
                                definition=True)
                if isinstance(parameter, S.TemplateTemplateParameter):
                    self.template_parameters(parameter, parameters)
                    continue
                self.visit_children(parameter, parameters)
            else:
                self.parameter(parameter, parameters, "template parameter")
                self.visit_children(parameter, parameters)
        if node.requires is not None:
            self.visit(node.requires, parameters)
        self.visit(node.declaration, scope, parameters)
        inner = node.declaration
        candidates = [*inner.declarators, *inner.specifiers] if isinstance(inner, S.SimpleDeclaration) else [inner]
        declared = next((e for e in map(self.program.entity_of, candidates) if e is not None), None)
        if declared is not None:
            self.program.declares(node, declared)

    def template_parameters(self, node: S.TemplateTemplateParameter, scope: Scope) -> None:
        """A template template parameter's own parameters, which name nothing outside it."""
        inner = Scope("template", None, scope, node)
        for part in node.parameters:
            self.visit(part, inner)
        for part in [*([node.requires] if node.requires is not None else []),
                     *([node.name] if node.name is not None else []),
                     *([node.default] if node.default is not None else [])]:
            self.visit(part, scope)

    def alias(self, node: S.AliasDeclaration, scope: Scope, lexical: Scope) -> None:
        self.entity("type alias", node.name.spelling, scope, node, definition=True)
        self.visit_children(node, scope)

    def concept(self, node: S.ConceptDefinition, scope: Scope, lexical: Scope) -> None:
        self.entity("concept", node.name.spelling, scope, node, definition=True)
        self.visit_children(node, lexical)

    def define(self, node: S.DefineDirective, scope: Scope, lexical: Scope) -> None:
        self.entity("macro", node.name.spelling, self.program.macros, node, definition=True)
        self.visit_children(node, scope)

    # Statements

    def block(self, node: S.CompoundStatement, scope: Scope, lexical: Scope | None = None) -> None:
        inner = Scope("block", None, scope, node)
        self.program.located(node, scope)
        for item in node.items:
            self.visit(item, inner)

    def statement_scope(self, node: Any, scope: Scope, lexical: Scope) -> None:
        """An if, switch, while, for or range-for statement: the names its parts declare are local to it."""
        inner = Scope("block", None, scope, node)
        self.visit_children(node, inner)

    def handler(self, node: S.Handler, scope: Scope, lexical: Scope) -> None:
        inner = Scope("block", None, scope, node)
        self.parameter(node.parameter, inner, "variable")
        self.visit_children(node, inner)

    def labeled(self, node: S.LabeledStatement, scope: Scope, lexical: Scope) -> None:
        function = scope
        while function.parent is not None and function.kind not in ("function", "lambda"):
            function = function.parent
        self.entity("label", node.label.spelling, function, node, definition=True)
        self.visit_children(node, scope)

    def lambda_(self, node: S.LambdaExpression, scope: Scope, lexical: Scope) -> None:
        inner = Scope("lambda", None, scope, node)
        for parameter in node.template_parameters:
            if isinstance(parameter, (S.TypeParameter, S.TemplateTemplateParameter)):
                if parameter.name is not None:
                    self.entity("template parameter", parameter.name.spelling, inner, parameter, definition=True)
            else:
                self.parameter(parameter, inner, "template parameter")
        for capture in node.captures:
            if isinstance(capture, S.InitCapture):
                self.entity("variable", capture.name.spelling, inner, capture, definition=True)
        if node.declarator is not None:
            for parameter in node.declarator.parameters:
                self.parameter(parameter, inner, "parameter")
        for part in [*node.captures, *node.template_parameters,
                     *([node.template_requires] if node.template_requires is not None else []),
                     *node.attributes, *([node.declarator] if node.declarator is not None else [])]:
            self.visit(part, inner)
        self.program.located(node.body, inner)
        self.block(node.body, inner)

    def member(self, node: S.MemberExpression, scope: Scope, lexical: Scope) -> None:
        """`object.member`: the member is found in the object's class, which only types tell, so the member's name
        has no scope. What it holds that is found where the expression is (template arguments, qualifiers and the
        types of destructor and conversion names) is visited as usual."""
        self.visit(node.object, scope)
        name = node.member
        if isinstance(name, S.TemplateId):
            for argument in name.arguments:
                self.visit(argument, scope)
        elif not isinstance(name, S.Identifier):
            self.visit_children(name, scope)

    def requires(self, node: S.RequiresExpression, scope: Scope, lexical: Scope) -> None:
        inner = Scope("requires", None, scope, node)
        for parameter in node.parameters:
            self.parameter(parameter, inner, "parameter")
        self.visit_children(node, inner)

    HANDLERS: dict[type, Any] = {}


_Definer.HANDLERS.update({
    S.NamespaceDefinition: _Definer.namespace, S.NamespaceAliasDefinition: _Definer.namespace_alias,
    S.UsingDirective: _Definer.using_directive, S.UsingDeclaration: _Definer.using_declaration,
    S.UsingEnumDeclaration: _Definer.using_enum, S.ClassSpecifier: _Definer.class_, S.EnumSpecifier: _Definer.enum,
    S.Enumerator: _Definer.enumerator,
    S.SimpleDeclaration: _Definer.simple, S.FunctionDefinition: _Definer.function,
    S.TemplateDeclaration: _Definer.template, S.AliasDeclaration: _Definer.alias,
    S.ConceptDefinition: _Definer.concept, S.DefineDirective: _Definer.define,
    S.CompoundStatement: _Definer.block,
    **{k: _Definer.statement_scope for k in (S.IfStatement, S.SwitchStatement, S.WhileStatement, S.ForStatement,
                                             S.RangeForStatement)},
    S.Handler: _Definer.handler, S.LabeledStatement: _Definer.labeled, S.LambdaExpression: _Definer.lambda_,
    S.RequiresExpression: _Definer.requires, S.MemberExpression: _Definer.member,
})


def define(unit: S.TranslationUnit) -> Program:
    """The entities a translation unit declares, in their scopes."""
    definer = _Definer(unit)
    definer.program.located(unit, definer.program.root)
    for item in unit.items:
        definer.visit(item, definer.program.root)
    return definer.program


def referents(program: Program, name: Any) -> list[Entity]:
    """The entities a `Name` node of the program refers to, looked up from where it is. A member's name after `.`
    or `->` depends on types, so it finds nothing."""
    scope = program.scope_of(name)
    return [] if scope is None else _resolve(name, scope)
