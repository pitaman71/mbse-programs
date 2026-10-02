"""Definitions: the names a TypeScript or JavaScript program declares, in the scopes ECMAScript and TypeScript give
them.

`define(program)` reads a program and returns a `TypeScriptProgram`, a `Framework.Definitions.Program` whose
qualified names join with `.` (`Shapes.Point.area`). Its entities have these kinds:

- 'variable' (`var`, `let`, `const`, `using`, and a `catch` clause's parameter), 'parameter' and 'function';
- 'class', with its members: 'method', 'property' (a parameter property included) and 'accessor' (`get`, `set` and
  `accessor`), private ones named with their `#`;
- 'interface', with its members 'method', 'property' and 'accessor'; 'type alias' and 'type parameter' (a mapped
  type's key and an `infer` binding included);
- 'enum' and 'enum member'; 'namespace' (`namespace A` and `module A`) and 'module' (`declare module "a"`);
- 'import': a name an import binds, `import a = b.c` included, whose `target` is what `b.c` names.

Declarations of one name and kind in one scope are one entity: merged interfaces, namespaces and enums share their
scope, and a function's overloads, a `var` declared twice and an accessor's `get` and `set` are one entity. Its
`declarations` are in source order, and its `definition` is the first that is not an overload signature (a function
or a method without a body), if any.

Scopes are 'module' (the program), 'function' (a function, an arrow function, a method or a signature: its type
parameters and parameters), 'block' (a block, a `for` statement, a `switch` statement's cases, a `catch` clause, a
named class expression), 'static block', 'class' and 'interface' (members, which lookup never finds unqualified),
'enum', 'namespace', 'module' and 'type parameters' (of a generic class, interface or type alias, of a mapped type,
or the `infer` bindings of a conditional type). `var` binds in the nearest function, static block, namespace or
module; everything else in the nearest scope. `declare global { ... }` declares in the program's scope.

A name has a meaning: TypeScript keeps values, types and namespaces apart, so one name can be a variable and an
interface at once. `TypeScriptProgram.space_of` tells which meaning a name has where it is written, and `referents`
finds only the entities with that meaning ('class', 'enum' and 'import' have every meaning).

What it does not do: resolve properties (`a.b`, whose `b` depends on `a`'s value), a qualified name past its first
part, or the members of imported modules; follow `export *`, `with` statements, `eval` or globals that libraries
declare; or treat a lower-case JSX element (`<div>`) as anything but HTML.
"""

from __future__ import annotations

from typing import Any

from ..Framework.Definitions import Entity, Program, Scope
from ..Framework.Syntax import children, walk
from . import Syntax as S

__all__ = ["TypeScriptProgram", "MEANINGS", "define", "referents"]

# The meanings each kind of entity has: what it can be named as.
MEANINGS: dict[str, frozenset[str]] = {
    "variable": frozenset({"value"}), "parameter": frozenset({"value"}), "function": frozenset({"value"}),
    "enum member": frozenset({"value"}), "class": frozenset({"value", "type", "namespace"}),
    "enum": frozenset({"value", "type", "namespace"}), "import": frozenset({"value", "type", "namespace"}),
    "namespace": frozenset({"value", "namespace"}), "module": frozenset({"namespace"}),
    "interface": frozenset({"type"}), "type alias": frozenset({"type"}), "type parameter": frozenset({"type"}),
    "method": frozenset({"value"}), "property": frozenset({"value"}), "accessor": frozenset({"value"}),
}
# Kinds of the names that are not located when they name a property, a member or a label.
_NAMES = (S.Identifier, S.PrivateIdentifier, S.JSXIdentifier)
# Scopes where `var` binds.
_VAR_SCOPES = {"module", "function", "static block", "namespace"}
# Kinds whose syntax nodes open a scope of types.
_TYPES = (S.TypeNode, S.TSTypeAnnotation, S.TSTypeParameterInstantiation, S.TSInterfaceHeritage,
          S.TSClassImplements)


class TypeScriptProgram(Program):
    """What a program declares, and for each name written in it the meaning it has there."""

    def __init__(self, root: Scope):
        super().__init__(root)
        self._spaces: dict[int, str] = {}

    def means(self, node: Any, space: str) -> None:
        """Records that the name `node` is written as a `space`: 'value', 'type' or 'namespace'."""
        self._spaces[id(node)] = space

    def space_of(self, node: Any) -> str | None:
        """The meaning the name `node` has where it is written: 'value', 'type' or 'namespace'; None for a name
        that declares, or that names something of any meaning (an export's)."""
        return self._spaces.get(id(node))


class _Definer:
    """Declares what a program binds, visiting each syntax node with its scope and the meaning a name has there."""

    def __init__(self, program: S.Program):
        self.program = TypeScriptProgram(Scope("module", None, None, program, separator="."))
        self.imports: list[tuple[Entity, Any, Scope]] = []

    # Scopes and bindings

    @staticmethod
    def var_scope(scope: Scope) -> Scope:
        """The scope where a `var` in `scope` binds."""
        while scope.kind not in _VAR_SCOPES:
            scope = scope.parent  # type: ignore[assignment]
        return scope

    def declare(self, scope: Scope, name: str, node: Any, kind: str) -> Entity:
        """The entity of `kind` named `name` in `scope`, a new one if there is none, with `node` declaring it."""
        found = [e for e in scope.names.get(name, []) if e.kind == kind]
        entity = found[0] if found else scope.declare(self.program.add(Entity(kind, name, scope)))
        entity.declarations.append(node)
        self.program.declares(node, entity)
        return entity

    def bind(self, scope: Scope, identifier: Any, node: Any, kind: str) -> Entity:
        """Binds `identifier` in `scope`, `node` declaring it."""
        entity = self.declare(scope, identifier.name, node, kind)
        self.program.declares(identifier, entity)
        self.program.located(identifier, scope)
        return entity

    def owner(self, scope: Scope, identifier: Any, node: Any, kind: str, opens: str) -> tuple[Entity, Scope]:
        """Binds `identifier` in `scope` as an entity with members, and the scope of its members: the one an earlier
        declaration of it opened, or a new one of the kind `opens`."""
        entity = self.bind(scope, identifier, node, kind)
        if entity.scope is None:
            entity.scope = Scope(opens, entity, scope, node)
        return entity, entity.scope

    def target(self, node: Any, scope: Scope, kind: str, inner: Scope | None = None) -> None:
        """A binding pattern: its names bind in `scope` as `kind`; its defaults, computed keys and annotations are in
        `inner` (by default `scope`)."""
        inner = scope if inner is None else inner
        self.program.located(node, inner)
        if isinstance(node, S.Elision):
            return
        if isinstance(node, S.Identifier):
            if node.name != "this":  # `this: T` declares the type of `this`, not a parameter
                self.bind(scope, node, node, kind)
            self.visit_all(node.decorators, inner, "value")
            self.visit_all([node.typeAnnotation], inner, "type")
            return
        if isinstance(node, S.TSParameterProperty):
            self.visit_all(node.decorators, inner, "value")
            self.target(node.parameter, scope, kind, inner)
            return
        self.visit_all(node.decorators, inner, "value")
        self.visit_all([node.typeAnnotation], inner, "type")
        if isinstance(node, S.ArrayPattern):
            for element in node.elements:
                self.target(element, scope, kind, inner)
        elif isinstance(node, S.ObjectPattern):
            for item in node.properties:
                self.program.located(item, inner)
                if isinstance(item, S.Property):
                    if item.computed:
                        self.visit(item.key, inner, "value")
                    self.target(item.value, scope, kind, inner)
                else:
                    self.target(item, scope, kind, inner)
        elif isinstance(node, S.AssignmentPattern):
            self.target(node.left, scope, kind, inner)
            self.visit(node.right, inner, "value")
        else:  # a RestElement
            self.target(node.argument, scope, kind, inner)
            self.visit_all([node.value], inner, "value")

    def type_parameters(self, parameters: S.TSTypeParameterDeclaration | None, scope: Scope) -> None:
        """Binds type parameters in `scope`, their constraints and defaults there too."""
        if parameters is None:
            return
        self.program.located(parameters, scope)
        for parameter in parameters.params:
            self.type_parameter(parameter, scope)

    def type_parameter(self, parameter: S.TSTypeParameter, scope: Scope) -> None:
        self.program.located(parameter, scope)
        self.bind(scope, parameter.name, parameter, "type parameter")
        self.visit_all([parameter.constraint, parameter.default], scope, "type")

    def generic(self, node: Any, scope: Scope) -> Scope:
        """The scope of a generic class's, interface's or type alias's type parameters; `scope` if it has none."""
        if node.typeParameters is None:
            return scope
        inner = Scope("type parameters", None, scope, node)
        self.type_parameters(node.typeParameters, inner)
        return inner

    # Visiting

    def visit(self, node: Any, scope: Scope, space: str) -> None:
        if isinstance(node, _TYPES) and not isinstance(node, S.TSTypeQuery):
            space = "type"
        self.program.located(node, scope)
        method = self.HANDLERS.get(type(node))
        if method is not None:
            method(self, node, scope, space)
            return
        for _, _, child in children(node):
            self.visit(child, scope, space)

    def visit_all(self, nodes: list[Any], scope: Scope, space: str) -> None:
        for node in nodes:
            if node is not None:
                self.visit(node, scope, space)

    def statements(self, statements: list[Any], scope: Scope) -> None:
        self.visit_all(statements, scope, "value")

    def identifier(self, node: S.Identifier, scope: Scope, space: str) -> None:
        self.program.means(node, space)
        self.visit_all(node.decorators, scope, "value")
        self.visit_all([node.typeAnnotation], scope, "type")

    def qualifier(self, space: str) -> str:
        """The meaning of `a` in `a.b` written as a `space`."""
        return "value" if space == "value" else "namespace"

    def member(self, node: S.MemberExpression, scope: Scope, space: str) -> None:
        self.visit(node.object, scope, self.qualifier(space))
        if node.computed:
            self.visit(node.property, scope, "value")  # a property's name depends on the value: it is not located

    def qualified(self, node: S.TSQualifiedName, scope: Scope, space: str) -> None:
        self.visit(node.left, scope, self.qualifier(space))

    def type_query(self, node: S.TSTypeQuery, scope: Scope, space: str) -> None:
        self.visit(node.exprName, scope, "value")
        self.visit_all([node.typeArguments], scope, "type")

    def import_type(self, node: S.TSImportType, scope: Scope, space: str) -> None:
        self.visit_all([node.options, node.typeArguments], scope, space)  # its qualifier names the module's members

    def property(self, node: S.Property, scope: Scope, space: str) -> None:
        if node.computed:
            self.visit(node.key, scope, "value")
        self.visit(node.value, scope, "value")

    def keyed(self, node: Any, scope: Scope, space: str) -> None:
        """An interface member, or a member of an object type: its key, if computed, and its type."""
        if node.computed:
            self.visit(node.key, scope, "value")
        if isinstance(node, S.TSMethodSignature):
            self.signature(node, Scope("function", None, scope, node))
        else:
            self.visit_all([node.typeAnnotation], scope, "type")

    def index_signature(self, node: S.TSIndexSignature, scope: Scope, space: str) -> None:
        for parameter in node.parameters:  # its parameter names nothing
            self.visit_all([parameter.typeAnnotation], scope, "type")
        self.visit_all([node.typeAnnotation], scope, "type")

    def unnamed(self, node: Any, scope: Scope, space: str) -> None:
        """A syntax node whose names name no entity of the program: a label, a meta-property, an export's exported
        name."""

    def export_specifier(self, node: S.ExportSpecifier, scope: Scope, space: str) -> None:
        self.program.located(node.local, scope)  # it exports whatever the name means

    def export_named(self, node: S.ExportNamedDeclaration, scope: Scope, space: str) -> None:
        self.visit_all([node.declaration], scope, "value")
        if node.source is None:
            self.visit_all(node.specifiers, scope, "value")

    def labeled(self, node: S.LabeledStatement, scope: Scope, space: str) -> None:
        self.visit(node.body, scope, "value")

    def jsx_name(self, node: Any, scope: Scope, space: str) -> None:
        """An element's name: `Component` and the `a` of `a.b` name values; `div` and `svg:path` name HTML."""
        root = node
        while isinstance(root, S.JSXMemberExpression):
            root = root.object
        if isinstance(root, S.JSXIdentifier) and (root is not node or not root.name[:1].islower()):
            self.program.located(root, scope)
            self.program.means(root, "value")

    def jsx_opening(self, node: S.JSXOpeningElement, scope: Scope, space: str) -> None:
        self.jsx_name(node.name, scope, space)
        self.visit_all([node.typeArguments, *node.attributes], scope, "value")

    def jsx_closing(self, node: S.JSXClosingElement, scope: Scope, space: str) -> None:
        self.jsx_name(node.name, scope, space)

    def jsx_attribute(self, node: S.JSXAttribute, scope: Scope, space: str) -> None:
        self.visit_all([node.value], scope, "value")

    # Declarations

    def variables(self, node: S.VariableDeclaration, scope: Scope, space: str) -> None:
        binding = self.var_scope(scope) if node.declarationKind == "var" else scope
        for declarator in node.declarations:
            self.program.located(declarator, scope)
            self.target(declarator.id, binding, "variable", scope)
            self.visit_all([declarator.init], scope, "value")

    def function(self, node: Any, scope: Scope, space: str, entity: Entity | None = None) -> Scope:
        """A function, an arrow function or a method's value: its scope, holding its type parameters and parameters,
        and its body."""
        inner = Scope("function", entity, scope, node)
        if entity is not None and (entity.scope is None or not isinstance(
                node, (S.TSDeclareFunction, S.TSEmptyBodyFunctionExpression))):
            entity.scope = inner  # an overloaded function's scope is its implementation's
        if isinstance(node, S.FunctionExpression) and node.id is not None:  # a function expression's name is its own
            self.bind(inner, node.id, node, "function")
        self.signature(node, inner)
        body = getattr(node, "body", None)
        if isinstance(body, S.BlockStatement):
            self.program.located(body, inner)
            self.statements(body.body, inner)
        elif body is not None:
            self.visit(body, inner, "value")
        return inner

    def signature(self, node: Any, inner: Scope) -> None:
        """A signature's type parameters, parameters and return type, which bind and are in `inner`."""
        self.type_parameters(node.typeParameters, inner)
        for parameter in node.params:
            self.target(parameter, inner, "parameter")
        self.visit_all([node.returnType], inner, "type")

    def signature_type(self, node: Any, scope: Scope, space: str) -> None:
        """A function type, a constructor type, or a call or construct signature: a scope of its own."""
        self.signature(node, Scope("function", None, scope, node))

    def function_declaration(self, node: Any, scope: Scope, space: str) -> None:
        entity = self.bind(scope, node.id, node, "function") if node.id is not None else None
        self.function(node, scope, space, entity)

    def function_expression(self, node: Any, scope: Scope, space: str) -> None:
        self.function(node, scope, space)

    def class_(self, node: S.ClassDeclaration | S.ClassExpression, scope: Scope, space: str) -> None:
        self.visit_all(node.decorators, scope, "value")
        outer = scope
        if isinstance(node, S.ClassExpression) and node.id is not None:  # its name is its own
            outer = Scope("block", None, scope, node)
        entity = None if node.id is None else self.bind(outer, node.id, node, "class")
        heritage = self.generic(node, outer)
        members = Scope("class", entity, heritage, node) if entity is None or entity.scope is None else entity.scope
        if entity is not None:
            entity.scope = members
        self.visit_all([node.superClass], heritage, "value")
        self.visit_all([node.superTypeArguments, *node.implements], heritage, "type")
        self.program.located(node.body, members)
        for element in node.body.body:
            self.element(element, members, heritage)

    def element(self, node: Any, members: Scope, scope: Scope) -> None:
        """A class member: it is declared in `members`; its decorators, computed key and value are in `scope`."""
        self.program.located(node, members)
        if isinstance(node, S.StaticBlock):
            inner = Scope("static block", None, scope, node)
            self.statements(node.body, inner)
            return
        if isinstance(node, (S.Comment, S.TSIndexSignature)):
            self.visit(node, scope, "value")
            return
        self.visit_all(node.decorators, scope, "value")
        if node.computed:
            self.visit(node.key, scope, "value")
        if isinstance(node, (S.MethodDefinition, S.TSAbstractMethodDefinition)):
            kind = "accessor" if node.methodKind in ("get", "set") else "method"
            entity = self.declare_member(node, members, kind)
            self.program.located(node.value, scope)
            self.function(node.value, scope, "value", entity)
            for parameter in node.value.params:
                if isinstance(parameter, S.TSParameterProperty):
                    name = parameter.parameter
                    name = name.left if isinstance(name, S.AssignmentPattern) else name
                    self.declare(members, name.name, parameter, "property")
            return
        kind = "accessor" if isinstance(node, (S.AccessorProperty, S.TSAbstractAccessorProperty)) else "property"
        self.declare_member(node, members, kind)
        self.visit_all([node.typeAnnotation], scope, "type")
        self.visit_all([node.value], scope, "value")

    def declare_member(self, node: Any, members: Scope, kind: str) -> Entity | None:
        """Declares a member named by its key; None for a computed key, which names no member."""
        name = self.key_name(node.key, node.computed)
        if name is None:
            return None
        entity = self.declare(members, name, node, kind)
        if isinstance(node.key, (S.Identifier, S.PrivateIdentifier)):
            self.program.declares(node.key, entity)
            self.program.located(node.key, members)
        return entity

    @staticmethod
    def key_name(key: Any, computed: bool) -> str | None:
        """The name a key gives: an identifier's, `#` and a private name's, a string's or a number's value as
        written; None for a computed key."""
        if computed:
            return None
        if isinstance(key, S.Identifier):
            return key.name
        if isinstance(key, S.PrivateIdentifier):
            return "#" + key.name
        raw = key.raw
        return raw[1:-1] if raw[:1] in ("'", '"') else raw

    def interface(self, node: S.TSInterfaceDeclaration, scope: Scope, space: str) -> None:
        members = self.owner(scope, node.id, node, "interface", "interface")[1]
        inner = self.generic(node, scope)
        self.visit_all(node.extends, inner, "type")
        self.program.located(node.body, members)
        for item in node.body.body:
            self.program.located(item, members)
            if isinstance(item, (S.TSPropertySignature, S.TSMethodSignature)):
                kind = "property" if isinstance(item, S.TSPropertySignature) else (
                    "accessor" if item.methodKind in ("get", "set") else "method")
                self.declare_member(item, members, kind)
            self.visit(item, inner, "type")

    def type_alias(self, node: S.TSTypeAliasDeclaration, scope: Scope, space: str) -> None:
        self.bind(scope, node.id, node, "type alias")
        self.visit(node.typeAnnotation, self.generic(node, scope), "type")

    def enum(self, node: S.TSEnumDeclaration, scope: Scope, space: str) -> None:
        _, members = self.owner(scope, node.id, node, "enum", "enum")
        self.program.located(node.body, members)
        for item in node.body.members:
            self.program.located(item, members)
            if isinstance(item, S.Comment):
                continue
            name = self.key_name(item.id, item.computed)
            if name is None:
                self.visit(item.id, members, "value")
            else:
                entity = self.declare(members, name, item, "enum member")
                self.program.declares(item.id, entity)
                self.program.located(item.id, members)
            self.visit_all([item.initializer], members, "value")

    def module(self, node: S.TSModuleDeclaration, scope: Scope, space: str) -> None:
        if node.moduleKind == "global":
            self.statements(node.body.body, self.program.root)  # type: ignore[union-attr]
            return
        names: list[Any] = []
        name = node.id
        while isinstance(name, S.TSQualifiedName):  # `namespace a.b.c` declares `a`, `a.b` and `a.b.c`
            names.insert(0, name.right)
            self.program.located(name, scope)
            name = name.left
        names.insert(0, name)
        inner = scope
        for identifier in names:
            if isinstance(identifier, S.Literal):
                entity = self.declare(inner, identifier.raw[1:-1], node, "module")
                self.program.declares(identifier, entity)
                self.program.located(identifier, inner)
                if entity.scope is None:
                    entity.scope = Scope("module", entity, inner, node)
                inner = entity.scope
            else:
                inner = self.owner(inner, identifier, node, "namespace", "namespace")[1]
        if node.body is not None:
            self.program.located(node.body, inner)
            self.statements(node.body.body, inner)

    def import_declaration(self, node: S.ImportDeclaration, scope: Scope, space: str) -> None:
        for specifier in node.specifiers:
            self.program.located(specifier, scope)
            self.bind(scope, specifier.local, specifier, "import")
        self.visit_all(node.attributes, scope, "value")

    def import_equals(self, node: S.TSImportEqualsDeclaration, scope: Scope, space: str) -> None:
        entity = self.bind(scope, node.id, node, "import")
        reference = node.moduleReference
        if not isinstance(reference, S.TSExternalModuleReference):
            self.imports.append((entity, reference, scope))
        self.visit(reference, scope, "namespace")

    # Scopes of statements and types

    def block(self, node: S.BlockStatement, scope: Scope, space: str) -> None:
        self.statements(node.body, Scope("block", None, scope, node))

    def loop(self, node: Any, scope: Scope, space: str) -> None:
        inner = Scope("block", None, scope, node)
        for _, _, child in children(node):
            self.visit(child, inner, "value")

    def switch(self, node: S.SwitchStatement, scope: Scope, space: str) -> None:
        self.visit(node.discriminant, scope, "value")
        self.visit_all(node.cases, Scope("block", None, scope, node), "value")

    def catch(self, node: S.CatchClause, scope: Scope, space: str) -> None:
        inner = Scope("block", None, scope, node)
        if node.param is not None:
            self.target(node.param, inner, "variable")
        self.program.located(node.body, inner)
        self.statements(node.body.body, inner)

    def mapped(self, node: S.TSMappedType, scope: Scope, space: str) -> None:
        self.visit(node.constraint, scope, "type")
        inner = Scope("type parameters", None, scope, node)
        self.bind(inner, node.key, node, "type parameter")
        self.visit_all([node.nameType, node.typeAnnotation], inner, "type")

    def conditional(self, node: S.TSConditionalType, scope: Scope, space: str) -> None:
        self.visit(node.checkType, scope, "type")
        inner = Scope("type parameters", None, scope, node)  # where `infer` binds, seen by the true branch
        self.visit_all([node.extendsType, node.trueType], inner, "type")
        self.visit(node.falseType, scope, "type")

    def infer(self, node: S.TSInferType, scope: Scope, space: str) -> None:
        self.type_parameter(node.typeParameter, scope)

    def predicate(self, node: S.TSTypePredicate, scope: Scope, space: str) -> None:
        self.visit(node.parameterName, scope, "value")
        self.visit_all([node.typeAnnotation], scope, "type")

    def asserted(self, node: Any, scope: Scope, space: str) -> None:
        """`x as T`, `x satisfies T` or `<T>x`, where in `as const` the name `const` names nothing."""
        annotation = node.typeAnnotation
        const = isinstance(annotation, S.TSTypeReference) and isinstance(annotation.typeName, S.Identifier) and (
            annotation.typeName.name == "const" and annotation.typeArguments is None)
        for _, _, child in children(node):  # in source order
            if child is not annotation:
                self.visit(child, scope, "value")
            elif not const:
                self.visit(child, scope, "type")

    def tuple_member(self, node: S.TSNamedTupleMember, scope: Scope, space: str) -> None:
        self.visit(node.elementType, scope, "type")

    HANDLERS: dict[type, Any] = {
        S.Identifier: identifier, S.MemberExpression: member, S.TSQualifiedName: qualified,
        S.TSTypeQuery: type_query, S.TSImportType: import_type, S.Property: property,
        S.TSPropertySignature: keyed, S.TSMethodSignature: keyed, S.TSIndexSignature: index_signature,
        S.MetaProperty: unnamed, S.BreakStatement: unnamed, S.ContinueStatement: unnamed,
        S.ExportAllDeclaration: unnamed, S.ExportSpecifier: export_specifier, S.ExportNamedDeclaration: export_named,
        S.LabeledStatement: labeled, S.JSXOpeningElement: jsx_opening, S.JSXClosingElement: jsx_closing,
        S.JSXAttribute: jsx_attribute, S.VariableDeclaration: variables,
        S.FunctionDeclaration: function_declaration, S.TSDeclareFunction: function_declaration,
        S.FunctionExpression: function_expression, S.ArrowFunctionExpression: function_expression,
        S.TSEmptyBodyFunctionExpression: function_expression,
        S.TSFunctionType: signature_type, S.TSConstructorType: signature_type,
        S.TSCallSignatureDeclaration: signature_type, S.TSConstructSignatureDeclaration: signature_type,
        S.ClassDeclaration: class_, S.ClassExpression: class_, S.TSInterfaceDeclaration: interface,
        S.TSTypeAliasDeclaration: type_alias, S.TSEnumDeclaration: enum, S.TSModuleDeclaration: module,
        S.ImportDeclaration: import_declaration, S.TSImportEqualsDeclaration: import_equals,
        S.BlockStatement: block, S.ForStatement: loop, S.ForInStatement: loop, S.ForOfStatement: loop,
        S.SwitchStatement: switch, S.CatchClause: catch, S.TSMappedType: mapped, S.TSConditionalType: conditional,
        S.TSInferType: infer, S.TSAsExpression: asserted, S.TSSatisfiesExpression: asserted,
        S.TSTypeAssertion: asserted, S.TSTypePredicate: predicate, S.TSNamedTupleMember: tuple_member,
    }


def _signature(node: Any) -> bool:
    """Whether a declaration is an overload signature: a function or a method without a body."""
    return isinstance(node, (S.TSDeclareFunction, S.TSAbstractMethodDefinition)) or (
        isinstance(node, S.MethodDefinition) and isinstance(node.value, S.TSEmptyBodyFunctionExpression)) or (
        isinstance(node, (S.TSMethodSignature, S.TSPropertySignature)))


def define(program: S.Program) -> TypeScriptProgram:
    """The entities a program declares, in their scopes."""
    definer = _Definer(program)
    out = definer.program
    out.located(program, out.root)
    definer.statements(program.body, out.root)
    for entity, reference, scope in definer.imports:  # `import a = b.c`, once every namespace is declared
        names: list[str] = []
        while isinstance(reference, S.TSQualifiedName):
            names.insert(0, reference.right.name)
            reference = reference.left
        found = [e for e in _resolve(scope, reference.name, "namespace") if e is not entity]
        for name in names:
            scopes = [e.resolved().scope for e in found if e.resolved().scope is not None]
            found = scopes[0].lookup(name) if scopes else []
        entity.target = found[0] if found else None
    stack: list[tuple[Any, Scope]] = [(program, out.root)]
    while stack:  # every other syntax node is in its parent's scope, but for the names of properties and members
        node, scope = stack.pop()
        found = out.scope_of(node)
        if found is None and not isinstance(node, _NAMES):
            out.located(node, scope)
        stack.extend((child, found or scope) for _, _, child in children(node))
    order = {id(node): i for i, node in enumerate(walk(program))}  # properties are in source order
    for entity in out.entities():
        entity.declarations.sort(key=lambda node: order[id(node)])
        entity.definition = next((d for d in entity.declarations if not _signature(d)), None)
    return out


def _resolve(scope: Scope | None, name: str, space: str | None) -> list[Entity]:
    """Unqualified lookup of `name` from `scope`, outwards, finding only entities with the meaning `space` (any, for
    None)."""
    while scope is not None:
        found = [e for e in scope.lookup(name) if space is None or space in MEANINGS[e.kind]]
        if found:
            return found
        scope = scope.parent
    return []


def referents(program: TypeScriptProgram, name: Any) -> list[Entity]:
    """The entities an `Identifier` (or a `JSXIdentifier`) of the program refers to, looked up from where it is,
    with the meaning it has there. A property's name depends on a value, and a qualified name's later parts on its
    first, so they find nothing."""
    scope = program.scope_of(name)
    if scope is None:
        return []
    entity = program.entity_of(name)
    return [entity] if entity is not None else _resolve(scope, name.name, program.space_of(name))
