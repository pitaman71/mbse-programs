"""Syntax: the abstract syntax of TypeScript and JavaScript, as one tree language.

The kinds follow typescript-estree (TSESTree), the ESTree of TypeScript that ESLint and its tools read: the same
kinds with the same names and fields, in source order, but for fields whose names are keywords of Python or clash
with the framework's tag `kind`: `kind` is `declarationKind`, `methodKind`, `propertyKind` or `moduleKind`, and
`async`, `await`, `in` and `out` are `isAsync`, `isAwait`, `isIn` and `isOut`. Each kind and feature records where
it exists in two families (`SINCE`, `FEATURES`): ECMAScript, by edition year (ES2015 is 2015), and TypeScript, by
version (`100 * major + minor`: 5.9 is 509). Type syntax is TypeScript's alone; proposals that TypeScript implements
before an ECMAScript edition has them (decorators, `accessor`, `using`, `import defer`) are TypeScript's too. JSX is
an extension, outside every edition and version, which the standards made with `jsx` accept.

Where TSESTree drops what a transpiler needs to see or a printer needs to write it back, the tree is concrete:

- Literals keep their spelling: `Literal.raw` is the literal as written (`0x_FF`, `1_000n`, `'a\\n'`, `/a/v`), and a
  template's parts are their raw text.
- Parentheses written in the source stay, as `ParenthesizedExpression` and `TSParenthesizedType`. Printing adds
  those a hand-built tree needs.
- Comments are kept where statements, class members, interface members and enum members are listed, as `Comment`;
  elsewhere they are dropped. A hashbang line is `Program.hashbang`.
- Lists hold no empty places: an array's hole (`[a, , b]`) is an `Elision`.

Not represented: what follows from the rest (`ExpressionStatement.directive`, `ArrowFunctionExpression.expression`,
`Program.sourceType`, `TSModuleDeclaration.global`), what TSESTree keeps only for compatibility (`assertions`,
`TSEnumDeclaration.members`, `TSMappedType.typeParameter`, `TSImportType.argument`), and the modifier keywords
(`TSAbstractKeyword`, ...), which the parser never writes.
"""

from __future__ import annotations

from typing import Literal as Choice

from ..Framework.Syntax import Availability, Language, Node

__all__ = ["LANGUAGE", "KINDS"]

ES, TS = "ECMAScript", "TypeScript"


def es(year: int, ts: int) -> Availability:
    """ECMAScript from the edition `year` on, and TypeScript from the version `ts` on."""
    return {ES: year, TS: ts}


def ts(version: int) -> Availability:
    """TypeScript from `version` on (`100 * major + minor`); not ECMAScript."""
    return {TS: version}


# --- Choices ---

DeclarationKind = Choice["var", "let", "const", "using", "await using"]
MethodKind = Choice["constructor", "method", "get", "set"]
PropertyKind = Choice["init", "get", "set"]
ModuleKind = Choice["global", "module", "namespace"]
ImportExportKind = Choice["type", "value"]
Accessibility = Choice["private", "protected", "public"]
AssignmentOperator = Choice["=", "+=", "-=", "*=", "/=", "%=", "**=", "<<=", ">>=", ">>>=", "&=", "|=", "^=", "&&=",
                            "||=", "??="]
BinaryOperator = Choice["==", "!=", "===", "!==", "<", "<=", ">", ">=", "<<", ">>", ">>>", "+", "-", "*", "/", "%",
                        "**", "|", "^", "&", "in", "instanceof"]
LogicalOperator = Choice["&&", "||", "??"]
UnaryOperator = Choice["-", "+", "!", "~", "typeof", "void", "delete"]
UpdateOperator = Choice["++", "--"]
TypeOperator = Choice["keyof", "readonly", "unique"]
MappedOptional = Choice["?", "+?", "-?"]
MappedReadonly = Choice["readonly", "+readonly", "-readonly"]
Phase = Choice["defer"]


def _a(noun: str) -> str:
    return f"{'an' if noun[0].lower() in 'aeiou' else 'a'} {noun}"


def _needs(node: Node, field: str, what: str) -> list[str]:
    """A problem if the list `field` of `node` is empty."""
    return [] if getattr(node, field) else [f"{_a(node.KIND)} needs {what}"]


# --- Categories ---


class Statement(Node):
    """A statement or a declaration, where statements are listed; also a comment there."""


class Expression(Node):
    """An expression."""


class Pattern(Node):
    """A destructuring pattern: what an assignment, a declaration or a parameter binds."""


class TypeNode(Node):
    """A type."""


class ClassElement(Node):
    """A member of a class body."""


class TypeElement(Node):
    """A member of an interface or an object type."""


# === Program, comments and names ===


class Comment(Statement):
    """`// text`, or with `block` `/* text */`. `text` excludes the delimiters. A `trailing` comment ends the line of
    the item before it."""

    block: bool
    text: str
    trailing: bool


class Program(Node):
    """A source file: `hashbang`, the text of a first line `#!...` without the `#!`, then its statements."""

    hashbang: str | None
    body: list[Statement]


class Identifier(Expression):
    """A name: a variable's, a property's, a label's or a type's. As a parameter or a binding, it may carry decorators,
    `?` and a type annotation."""

    decorators: list[Decorator]
    name: str
    optional: bool
    typeAnnotation: TSTypeAnnotation | None
    FEATURES = {"optional": {True: ts(100)}}

    def check(self) -> list[str]:
        name = self.name
        if type(name) is not str:
            return []
        return [] if name.replace("$", "_").isidentifier() else [f"{name!r} is not an identifier"]


class PrivateIdentifier(Expression):
    """`#name`, a class's private member; `name` excludes the `#`."""

    name: str
    SINCE = es(2022, 308)

    def check(self) -> list[str]:
        name = self.name
        if type(name) is not str:
            return []
        return [] if name.replace("$", "_").isidentifier() else [f"{name!r} is not an identifier"]


# === Literals and primary expressions ===


class Literal(Expression):
    """A string, number, bigint, regular expression, boolean or `null` literal, as written."""

    raw: str

    def check(self) -> list[str]:
        return [] if self.raw != "" else ["a Literal needs a raw"]

    def features(self) -> list[tuple[str, Availability]]:
        raw = self.raw
        if type(raw) is not str:
            return []
        if raw[:1] in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9") and raw.endswith("n"):
            return [("bigint Literal", es(2020, 302))]
        if "_" in raw and raw[:1] in ("0", "1", "2", "3", "4", "5", "6", "7", "8", "9", "."):
            return [("Literal with numeric separators", es(2021, 207))]
        return []


class TemplateElement(Node):
    """Text of a template literal between its substitutions, as written; `tail` for the last."""

    raw: str
    tail: bool


class TemplateLiteral(Expression):
    """`` `quasi${expression}quasi` ``: the texts and the substitutions between them."""

    quasis: list[TemplateElement]
    expressions: list[Expression]

    def check(self) -> list[str]:
        if len(self.quasis) == len(self.expressions) + 1:
            return []
        return ["a TemplateLiteral needs one more quasi than expressions"]


class TaggedTemplateExpression(Expression):
    """`` tag<typeArguments>`...` ``."""

    tag: Expression
    typeArguments: TSTypeParameterInstantiation | None
    quasi: TemplateLiteral


class ThisExpression(Expression):
    """`this`."""


class Super(Expression):
    """`super`, called or with a member."""


class ParenthesizedExpression(Expression):
    """`(expression)`: parentheses written in the source."""

    expression: Expression | Pattern


class Elision(Node):
    """A hole in an array, as in `[a, , b]`."""


class SpreadElement(Node):
    """`...argument` in an array, a call or an object."""

    argument: Expression


class ArrayExpression(Expression):
    """`[elements]`."""

    elements: list[Expression | SpreadElement | Elision]


class Property(Node):
    """`key: value` in an object or an object pattern; a method (`method`), an accessor (`propertyKind` 'get' or
    'set'), or the shorthand `key` (`shorthand`)."""

    propertyKind: PropertyKind
    computed: bool
    key: Expression
    optional: bool
    method: bool
    shorthand: bool
    value: Expression | Pattern | TSEmptyBodyFunctionExpression
    FEATURES = {"optional": {True: ts(100)}}


class ObjectExpression(Expression):
    """`{properties}`."""

    properties: list[Property | SpreadElement]


class FunctionExpression(Expression):
    """`async function* id<typeParameters>(params): returnType { body }`."""

    isAsync: bool
    generator: bool
    id: Identifier | None
    typeParameters: TSTypeParameterDeclaration | None
    params: list[Identifier | Pattern | TSParameterProperty]
    returnType: TSTypeAnnotation | None
    body: BlockStatement


class ArrowFunctionExpression(Expression):
    """`async <typeParameters>(params): returnType => body`; a body that is an expression is its value."""

    isAsync: bool
    typeParameters: TSTypeParameterDeclaration | None
    params: list[Identifier | Pattern]
    returnType: TSTypeAnnotation | None
    body: BlockStatement | Expression
    SINCE = es(2015, 100)


class ClassExpression(Expression):
    """`class id<typeParameters> extends superClass<superTypeArguments> implements ... { body }`, as an expression."""

    decorators: list[Decorator]
    id: Identifier | None
    typeParameters: TSTypeParameterDeclaration | None
    superClass: Expression | None
    superTypeArguments: TSTypeParameterInstantiation | None
    implements: list[TSClassImplements]
    body: ClassBody
    SINCE = es(2015, 106)


class MetaProperty(Expression):
    """`new.target` or `import.meta`."""

    meta: Identifier
    property: Identifier

    def features(self) -> list[tuple[str, Availability]]:
        meta = self.meta.name if isinstance(self.meta, Identifier) else None
        return [("import.meta", es(2020, 209))] if meta == "import" else []


# === Operations ===


class MemberExpression(Expression):
    """`object.property`, `object[property]` (`computed`), or with `optional` `object?.property`."""

    object: Expression
    optional: bool
    computed: bool
    property: Expression

    def features(self) -> list[tuple[str, Availability]]:
        return [("MemberExpression with ?.", es(2020, 307))] if self.optional else []


class CallExpression(Expression):
    """`callee<typeArguments>(arguments)`, or with `optional` `callee?.(arguments)`."""

    callee: Expression
    optional: bool
    typeArguments: TSTypeParameterInstantiation | None
    arguments: list[Expression | SpreadElement]

    def features(self) -> list[tuple[str, Availability]]:
        return [("CallExpression with ?.", es(2020, 307))] if self.optional else []


class ChainExpression(Expression):
    """An optional chain, `a?.b.c()`, whose members and calls short-circuit together."""

    expression: Expression
    SINCE = es(2020, 307)


class NewExpression(Expression):
    """`new callee<typeArguments>(arguments)`."""

    callee: Expression
    typeArguments: TSTypeParameterInstantiation | None
    arguments: list[Expression | SpreadElement]


class ImportExpression(Expression):
    """`import(source, options)`, or with `phase` `import.defer(source)`."""

    phase: Phase | None
    source: Expression
    options: Expression | None
    SINCE = es(2020, 204)
    FEATURES = {"phase": {"defer": ts(509)}, "options": {True: es(2025, 503)}}


class UpdateExpression(Expression):
    """`++argument` (`prefix`) or `argument--`."""

    operator: UpdateOperator
    prefix: bool
    argument: Expression


class UnaryExpression(Expression):
    """`operator argument`: `-x`, `!x`, `typeof x`, `void x`, `delete x`."""

    operator: UnaryOperator
    argument: Expression


class AwaitExpression(Expression):
    """`await argument`."""

    argument: Expression
    SINCE = es(2017, 107)


class BinaryExpression(Expression):
    """`left operator right`; `left` is a `PrivateIdentifier` in `#x in object`."""

    left: Expression
    operator: BinaryOperator
    right: Expression
    FEATURES = {"operator": {"**": es(2016, 107)}}

    def features(self) -> list[tuple[str, Availability]]:
        if isinstance(self.left, PrivateIdentifier):
            return [("BinaryExpression of #name in", es(2022, 405))]
        return []


class LogicalExpression(Expression):
    """`left && right`, `left || right` or `left ?? right`."""

    left: Expression
    operator: LogicalOperator
    right: Expression
    FEATURES = {"operator": {"??": es(2020, 307)}}


class ConditionalExpression(Expression):
    """`test ? consequent : alternate`."""

    test: Expression
    consequent: Expression
    alternate: Expression


class AssignmentExpression(Expression):
    """`left operator right`."""

    left: Expression | Pattern
    operator: AssignmentOperator
    right: Expression
    FEATURES = {"operator": {"**=": es(2016, 107), "&&=": es(2021, 400), "||=": es(2021, 400), "??=": es(2021, 400)}}


class SequenceExpression(Expression):
    """`expression, expression`."""

    expressions: list[Expression]

    def check(self) -> list[str]:
        return [] if len(self.expressions) > 1 else ["a SequenceExpression needs two expressions"]


class YieldExpression(Expression):
    """`yield argument`, or with `delegate` `yield* argument`."""

    delegate: bool
    argument: Expression | None
    SINCE = es(2015, 106)


# --- TypeScript's expressions ---


class TSAsExpression(Expression):
    """`expression as typeAnnotation`."""

    expression: Expression
    typeAnnotation: TypeNode
    SINCE = ts(106)


class TSSatisfiesExpression(Expression):
    """`expression satisfies typeAnnotation`."""

    expression: Expression
    typeAnnotation: TypeNode
    SINCE = ts(409)


class TSTypeAssertion(Expression):
    """`<typeAnnotation>expression`, which `.tsx` files do not have."""

    typeAnnotation: TypeNode
    expression: Expression
    SINCE = ts(100)


class TSNonNullExpression(Expression):
    """`expression!`."""

    expression: Expression
    SINCE = ts(200)


class TSInstantiationExpression(Expression):
    """`expression<typeArguments>`, without a call."""

    expression: Expression
    typeArguments: TSTypeParameterInstantiation
    SINCE = ts(407)


# === Patterns ===


class ArrayPattern(Pattern):
    """`[elements]: typeAnnotation`, destructuring."""

    decorators: list[Decorator]
    elements: list[Pattern | Expression | Elision]
    optional: bool
    typeAnnotation: TSTypeAnnotation | None
    SINCE = es(2015, 105)
    FEATURES = {"optional": {True: ts(100)}}


class ObjectPattern(Pattern):
    """`{properties}: typeAnnotation`, destructuring."""

    decorators: list[Decorator]
    properties: list[Property | RestElement]
    optional: bool
    typeAnnotation: TSTypeAnnotation | None
    SINCE = es(2015, 105)
    FEATURES = {"optional": {True: ts(100)}}


class AssignmentPattern(Pattern):
    """`left = right`: a binding with a default."""

    decorators: list[Decorator]
    left: Identifier | Pattern | Expression
    optional: bool
    typeAnnotation: TSTypeAnnotation | None
    right: Expression
    SINCE = es(2015, 105)
    FEATURES = {"optional": {True: ts(100)}}


class RestElement(Pattern):
    """`...argument: typeAnnotation`, the rest of an array, an object or a parameter list."""

    decorators: list[Decorator]
    argument: Identifier | Pattern | Expression
    optional: bool
    typeAnnotation: TSTypeAnnotation | None
    value: AssignmentPattern | None
    SINCE = es(2015, 105)
    FEATURES = {"optional": {True: ts(100)}}


# === Statements ===


class ExpressionStatement(Statement):
    """`expression;`; also a directive, `'use strict';`."""

    expression: Expression


class BlockStatement(Statement):
    """`{ body }`."""

    body: list[Statement]


class EmptyStatement(Statement):
    """`;`."""


class DebuggerStatement(Statement):
    """`debugger;`."""


class WithStatement(Statement):
    """`with (object) body`, which strict code does not have."""

    object: Expression
    body: Statement


class ReturnStatement(Statement):
    """`return argument;`."""

    argument: Expression | None


class LabeledStatement(Statement):
    """`label: body`."""

    label: Identifier
    body: Statement


class BreakStatement(Statement):
    """`break label;`."""

    label: Identifier | None


class ContinueStatement(Statement):
    """`continue label;`."""

    label: Identifier | None


class IfStatement(Statement):
    """`if (test) consequent else alternate`."""

    test: Expression
    consequent: Statement
    alternate: Statement | None

    def check(self) -> list[str]:
        if self.alternate is None:
            return []
        last = self.consequent
        while isinstance(last, (IfStatement, WhileStatement, ForStatement, ForInStatement, ForOfStatement,
                                LabeledStatement, WithStatement)):
            if isinstance(last, IfStatement):
                if last.alternate is None:
                    return ["an if without else ends the consequent, and would take the else"]
                last = last.alternate
            else:
                last = last.body
        return []


class SwitchCase(Node):
    """`case test: consequent`, or `default: consequent` without `test`."""

    test: Expression | None
    consequent: list[Statement]


class SwitchStatement(Statement):
    """`switch (discriminant) { cases }`."""

    discriminant: Expression
    cases: list[SwitchCase]


class ThrowStatement(Statement):
    """`throw argument;`."""

    argument: Expression


class CatchClause(Node):
    """`catch (param) body`, or `catch body` without `param`."""

    param: Identifier | Pattern | None
    body: BlockStatement

    def features(self) -> list[tuple[str, Availability]]:
        return [("CatchClause without a param", es(2019, 205))] if self.param is None else []


class TryStatement(Statement):
    """`try block catch... handler finally finalizer`."""

    block: BlockStatement
    handler: CatchClause | None
    finalizer: BlockStatement | None

    def check(self) -> list[str]:
        return [] if self.handler is not None or self.finalizer is not None else [
            "a TryStatement needs a handler or a finalizer"]


class WhileStatement(Statement):
    """`while (test) body`."""

    test: Expression
    body: Statement


class DoWhileStatement(Statement):
    """`do body while (test);`."""

    body: Statement
    test: Expression


class ForStatement(Statement):
    """`for (init; test; update) body`."""

    init: VariableDeclaration | Expression | None
    test: Expression | None
    update: Expression | None
    body: Statement


class ForInStatement(Statement):
    """`for (left in right) body`."""

    left: VariableDeclaration | Expression | Pattern
    right: Expression
    body: Statement


class ForOfStatement(Statement):
    """`for (left of right) body`, or with `isAwait` `for await (...)`."""

    isAwait: bool
    left: VariableDeclaration | Expression | Pattern
    right: Expression
    body: Statement
    SINCE = es(2015, 105)
    FEATURES = {"isAwait": {True: es(2018, 203)}}


class VariableDeclarator(Node):
    """`id: type = init`, or with `definite` `id!: type`."""

    id: Identifier | Pattern
    definite: bool
    init: Expression | None
    FEATURES = {"definite": {True: ts(207)}}

    def check(self) -> list[str]:
        if self.definite and not (isinstance(self.id, Identifier) and self.id.typeAnnotation is not None):
            return ["definite needs a name with a type annotation"]
        return []


class VariableDeclaration(Statement):
    """`declare kind declarations;`, `kind` being `var`, `let`, `const`, `using` or `await using`."""

    declare: bool
    declarationKind: DeclarationKind
    declarations: list[VariableDeclarator]
    FEATURES = {"declarationKind": {"let": es(2015, 105), "const": es(2015, 105), "using": ts(502),
                                    "await using": ts(502)},
                "declare": {True: ts(100)}}

    def check(self) -> list[str]:
        return _needs(self, "declarations", "a declarator")


class FunctionDeclaration(Statement):
    """`async function* id<typeParameters>(params): returnType { body }`."""

    isAsync: bool
    generator: bool
    id: Identifier | None
    typeParameters: TSTypeParameterDeclaration | None
    params: list[Identifier | Pattern | TSParameterProperty]
    returnType: TSTypeAnnotation | None
    body: BlockStatement
    FEATURES = {"isAsync": {True: es(2017, 107)}, "generator": {True: es(2015, 106)},
                "typeParameters": {True: ts(100)}, "returnType": {True: ts(100)}}


class TSDeclareFunction(Statement):
    """`declare function id<typeParameters>(params): returnType;`, or an overload's signature, without a body."""

    declare: bool
    isAsync: bool
    generator: bool
    id: Identifier | None
    typeParameters: TSTypeParameterDeclaration | None
    params: list[Identifier | Pattern | TSParameterProperty]
    returnType: TSTypeAnnotation | None
    SINCE = ts(100)


class Decorator(Node):
    """`@expression`."""

    expression: Expression
    SINCE = ts(105)


class ClassBody(Node):
    """`{ body }`: a class's members."""

    body: list[ClassElement | TSIndexSignature | Comment]


class ClassDeclaration(Statement):
    """`@decorators abstract class id<typeParameters> extends superClass<superTypeArguments> implements ... { body }`;
    without `id`, the default export's."""

    decorators: list[Decorator]
    declare: bool
    abstract: bool
    id: Identifier | None
    typeParameters: TSTypeParameterDeclaration | None
    superClass: Expression | None
    superTypeArguments: TSTypeParameterInstantiation | None
    implements: list[TSClassImplements]
    body: ClassBody
    SINCE = es(2015, 100)
    FEATURES = {"abstract": {True: ts(106)}, "declare": {True: ts(100)}, "implements": {True: ts(100)}}


class StaticBlock(ClassElement):
    """`static { body }`."""

    body: list[Statement]
    SINCE = es(2022, 404)


class MethodDefinition(ClassElement):
    """A class's method: `@decorators accessibility static override kind key?<...>(...) { ... }`; `methodKind` is
    'constructor', 'method', 'get' or 'set'."""

    decorators: list[Decorator]
    accessibility: Accessibility | None
    static: bool
    override: bool
    methodKind: MethodKind
    computed: bool
    key: Expression
    optional: bool
    value: FunctionExpression | TSEmptyBodyFunctionExpression
    FEATURES = {"override": {True: ts(403)}, "accessibility": {True: ts(100)}, "optional": {True: ts(200)}}


class TSAbstractMethodDefinition(ClassElement):
    """An `abstract` method, without a body."""

    decorators: list[Decorator]
    accessibility: Accessibility | None
    static: bool
    override: bool
    methodKind: MethodKind
    computed: bool
    key: Expression
    optional: bool
    value: FunctionExpression | TSEmptyBodyFunctionExpression
    SINCE = ts(106)


class TSEmptyBodyFunctionExpression(Node):
    """The signature of a method without a body: an overload's, an abstract one's, or a declared class's."""

    isAsync: bool
    generator: bool
    typeParameters: TSTypeParameterDeclaration | None
    params: list[Identifier | Pattern | TSParameterProperty]
    returnType: TSTypeAnnotation | None
    SINCE = ts(100)


class PropertyDefinition(ClassElement):
    """A class's field: `@decorators declare accessibility static override readonly key?!: type = value;`."""

    decorators: list[Decorator]
    declare: bool
    accessibility: Accessibility | None
    static: bool
    override: bool
    readonly: bool
    computed: bool
    key: Expression
    optional: bool
    definite: bool
    typeAnnotation: TSTypeAnnotation | None
    value: Expression | None
    SINCE = es(2022, 100)
    FEATURES = {"declare": {True: ts(307)}, "accessibility": {True: ts(100)}, "readonly": {True: ts(200)},
                "override": {True: ts(403)}, "optional": {True: ts(200)}, "definite": {True: ts(207)},
                "typeAnnotation": {True: ts(100)}}


class TSAbstractPropertyDefinition(ClassElement):
    """An `abstract` field, without a value."""

    decorators: list[Decorator]
    declare: bool
    accessibility: Accessibility | None
    static: bool
    override: bool
    readonly: bool
    computed: bool
    key: Expression
    optional: bool
    definite: bool
    typeAnnotation: TSTypeAnnotation | None
    value: Expression | None
    SINCE = ts(200)


class AccessorProperty(ClassElement):
    """`accessor key: type = value;`, a field with a getter and a setter."""

    decorators: list[Decorator]
    declare: bool
    accessibility: Accessibility | None
    static: bool
    override: bool
    readonly: bool
    computed: bool
    key: Expression
    optional: bool
    definite: bool
    typeAnnotation: TSTypeAnnotation | None
    value: Expression | None
    SINCE = ts(409)


class TSAbstractAccessorProperty(ClassElement):
    """`abstract accessor key: type;`."""

    decorators: list[Decorator]
    declare: bool
    accessibility: Accessibility | None
    static: bool
    override: bool
    readonly: bool
    computed: bool
    key: Expression
    optional: bool
    definite: bool
    typeAnnotation: TSTypeAnnotation | None
    value: Expression | None
    SINCE = ts(409)


class TSParameterProperty(Node):
    """A constructor's parameter that declares a field: `accessibility static override readonly parameter`."""

    decorators: list[Decorator]
    accessibility: Accessibility | None
    static: bool
    override: bool
    readonly: bool
    parameter: Identifier | AssignmentPattern
    SINCE = ts(100)


# === Modules ===


class ImportAttribute(Node):
    """`key: value` in `with { ... }`."""

    key: Identifier | Literal
    value: Literal


class ImportSpecifier(Node):
    """`imported as local`, or with `importKind` 'type' `type imported as local`."""

    importKind: ImportExportKind
    imported: Identifier | Literal
    local: Identifier
    FEATURES = {"importKind": {"type": ts(405)}}


class ImportDefaultSpecifier(Node):
    """`local`, the default export's binding."""

    local: Identifier


class ImportNamespaceSpecifier(Node):
    """`* as local`."""

    local: Identifier


class ImportDeclaration(Statement):
    """`import type defer specifiers from source with { attributes };`, or `import source;` without specifiers."""

    importKind: ImportExportKind
    phase: Phase | None
    specifiers: list[ImportDefaultSpecifier | ImportNamespaceSpecifier | ImportSpecifier]
    source: Literal
    attributes: list[ImportAttribute]
    SINCE = es(2015, 105)
    FEATURES = {"importKind": {"type": ts(308)}, "phase": {"defer": ts(509)}, "attributes": {True: es(2025, 503)}}


class ExportSpecifier(Node):
    """`local as exported`, or with `exportKind` 'type' `type local as exported`."""

    exportKind: ImportExportKind
    local: Identifier | Literal
    exported: Identifier | Literal
    FEATURES = {"exportKind": {"type": ts(405)}}


class ExportNamedDeclaration(Statement):
    """`export declaration`, or `export type { specifiers } from source with { attributes };`."""

    exportKind: ImportExportKind
    declaration: Statement | None
    specifiers: list[ExportSpecifier]
    source: Literal | None
    attributes: list[ImportAttribute]
    SINCE = es(2015, 105)
    FEATURES = {"exportKind": {"type": ts(308)}, "attributes": {True: es(2025, 503)}}


class ExportDefaultDeclaration(Statement):
    """`export default declaration`."""

    declaration: Statement | Expression
    SINCE = es(2015, 105)


class ExportAllDeclaration(Statement):
    """`export type * as exported from source with { attributes };`."""

    exportKind: ImportExportKind
    exported: Identifier | Literal | None
    source: Literal
    attributes: list[ImportAttribute]
    SINCE = es(2015, 105)
    FEATURES = {"exportKind": {"type": ts(500)}, "exported": {True: es(2020, 308)},
                "attributes": {True: es(2025, 503)}}


class TSImportEqualsDeclaration(Statement):
    """`import type id = moduleReference;`."""

    importKind: ImportExportKind
    id: Identifier
    moduleReference: Identifier | TSQualifiedName | TSExternalModuleReference
    SINCE = ts(100)


class TSExternalModuleReference(Node):
    """`require(expression)`, in `import x = require('m')`."""

    expression: Literal
    SINCE = ts(100)


class TSExportAssignment(Statement):
    """`export = expression;`."""

    expression: Expression
    SINCE = ts(100)


class TSNamespaceExportDeclaration(Statement):
    """`export as namespace id;`."""

    id: Identifier
    SINCE = ts(200)


# === TypeScript's declarations ===


class TSTypeAnnotation(Node):
    """`: typeAnnotation`, after a binding, a parameter, a field or a signature."""

    typeAnnotation: TypeNode
    SINCE = ts(100)


class TSTypeParameter(Node):
    """`const in out name extends constraint = default`."""

    const: bool
    isIn: bool
    isOut: bool
    name: Identifier
    constraint: TypeNode | None
    default: TypeNode | None
    SINCE = ts(100)
    FEATURES = {"const": {True: ts(500)}, "isIn": {True: ts(407)}, "isOut": {True: ts(407)},
                "default": {True: ts(203)}}


class TSTypeParameterDeclaration(Node):
    """`<params>`, a declaration's type parameters."""

    params: list[TSTypeParameter]
    SINCE = ts(100)

    def check(self) -> list[str]:
        return _needs(self, "params", "a type parameter")


class TSTypeParameterInstantiation(Node):
    """`<params>`, type arguments."""

    params: list[TypeNode]
    SINCE = ts(100)


class TSTypeAliasDeclaration(Statement):
    """`declare type id<typeParameters> = typeAnnotation;`."""

    declare: bool
    id: Identifier
    typeParameters: TSTypeParameterDeclaration | None
    typeAnnotation: TypeNode
    SINCE = ts(104)


class TSInterfaceHeritage(Node):
    """`expression<typeArguments>`, which an interface extends."""

    expression: Expression
    typeArguments: TSTypeParameterInstantiation | None
    SINCE = ts(100)


class TSClassImplements(Node):
    """`expression<typeArguments>`, which a class implements."""

    expression: Expression
    typeArguments: TSTypeParameterInstantiation | None
    SINCE = ts(100)


class TSInterfaceBody(Node):
    """`{ body }`: an interface's members."""

    body: list[TypeElement | Comment]
    SINCE = ts(100)


class TSInterfaceDeclaration(Statement):
    """`declare interface id<typeParameters> extends ... { body }`."""

    declare: bool
    id: Identifier
    typeParameters: TSTypeParameterDeclaration | None
    extends: list[TSInterfaceHeritage]
    body: TSInterfaceBody
    SINCE = ts(100)


class TSEnumMember(Node):
    """`id = initializer`; `computed` for `[id]`."""

    computed: bool
    id: Expression
    initializer: Expression | None
    SINCE = ts(100)


class TSEnumBody(Node):
    """`{ members }`."""

    members: list[TSEnumMember | Comment]
    SINCE = ts(100)


class TSEnumDeclaration(Statement):
    """`declare const enum id { body }`."""

    declare: bool
    const: bool
    id: Identifier
    body: TSEnumBody
    SINCE = ts(100)
    FEATURES = {"const": {True: ts(104)}}


class TSModuleBlock(Node):
    """`{ body }`: a namespace's or module's statements."""

    body: list[Statement]
    SINCE = ts(100)


class TSModuleDeclaration(Statement):
    """`declare namespace id { body }`, `declare module 'id' { body }` or `declare global { body }`; `moduleKind` is
    'namespace', 'module' or 'global'. A declared module may have no body."""

    declare: bool
    moduleKind: ModuleKind
    id: Identifier | Literal | TSQualifiedName
    body: TSModuleBlock | None
    SINCE = ts(100)
    FEATURES = {"moduleKind": {"namespace": ts(105), "global": ts(108)}}


# --- Signatures and members ---


class TSPropertySignature(TypeElement):
    """`readonly key?: typeAnnotation;`, in an interface or an object type."""

    accessibility: Accessibility | None
    static: bool
    readonly: bool
    computed: bool
    key: Expression
    optional: bool
    typeAnnotation: TSTypeAnnotation | None
    SINCE = ts(100)


class TSMethodSignature(TypeElement):
    """`get key?<typeParameters>(params): returnType;`; `methodKind` is 'method', 'get' or 'set'."""

    accessibility: Accessibility | None
    static: bool
    readonly: bool
    methodKind: MethodKind
    computed: bool
    key: Expression
    optional: bool
    typeParameters: TSTypeParameterDeclaration | None
    params: list[Identifier | Pattern | TSParameterProperty]
    returnType: TSTypeAnnotation | None
    SINCE = ts(100)
    FEATURES = {"methodKind": {"get": ts(403), "set": ts(403)}}


class TSCallSignatureDeclaration(TypeElement):
    """`<typeParameters>(params): returnType;`."""

    typeParameters: TSTypeParameterDeclaration | None
    params: list[Identifier | Pattern | TSParameterProperty]
    returnType: TSTypeAnnotation | None
    SINCE = ts(100)


class TSConstructSignatureDeclaration(TypeElement):
    """`new <typeParameters>(params): returnType;`."""

    typeParameters: TSTypeParameterDeclaration | None
    params: list[Identifier | Pattern | TSParameterProperty]
    returnType: TSTypeAnnotation | None
    SINCE = ts(100)


class TSIndexSignature(TypeElement):
    """`static readonly [parameters]: typeAnnotation;`, in an interface, an object type or a class."""

    accessibility: Accessibility | None
    static: bool
    readonly: bool
    parameters: list[Identifier | Pattern | TSParameterProperty]
    typeAnnotation: TSTypeAnnotation | None
    SINCE = ts(100)
    FEATURES = {"static": {True: ts(403)}}


# === Types ===


class TSAnyKeyword(TypeNode):
    """`any`."""

    SINCE = ts(100)


class TSUnknownKeyword(TypeNode):
    """`unknown`."""

    SINCE = ts(300)


class TSNumberKeyword(TypeNode):
    """`number`."""

    SINCE = ts(100)


class TSBigIntKeyword(TypeNode):
    """`bigint`."""

    SINCE = ts(302)


class TSBooleanKeyword(TypeNode):
    """`boolean`."""

    SINCE = ts(100)


class TSStringKeyword(TypeNode):
    """`string`."""

    SINCE = ts(100)


class TSSymbolKeyword(TypeNode):
    """`symbol`."""

    SINCE = ts(100)


class TSObjectKeyword(TypeNode):
    """`object`."""

    SINCE = ts(202)


class TSNeverKeyword(TypeNode):
    """`never`."""

    SINCE = ts(200)


class TSVoidKeyword(TypeNode):
    """`void`."""

    SINCE = ts(100)


class TSUndefinedKeyword(TypeNode):
    """`undefined`."""

    SINCE = ts(200)


class TSNullKeyword(TypeNode):
    """`null`."""

    SINCE = ts(200)


class TSIntrinsicKeyword(TypeNode):
    """`intrinsic`, the body of the compiler's own type aliases."""

    SINCE = ts(401)


class TSThisType(TypeNode):
    """`this`, as a type."""

    SINCE = ts(107)


class TSQualifiedName(TypeNode):
    """`left.right`, a name in a namespace."""

    left: Identifier | ThisExpression | TSQualifiedName
    right: Identifier
    SINCE = ts(100)


class TSTypeReference(TypeNode):
    """`typeName<typeArguments>`."""

    typeName: Identifier | ThisExpression | TSQualifiedName
    typeArguments: TSTypeParameterInstantiation | None
    SINCE = ts(100)


class TSParenthesizedType(TypeNode):
    """`(typeAnnotation)`: parentheses written in the source."""

    typeAnnotation: TypeNode
    SINCE = ts(100)


class TSLiteralType(TypeNode):
    """A literal as a type: a string, number, bigint or boolean literal, a negated number, or a template literal."""

    literal: Literal | UnaryExpression | TemplateLiteral
    SINCE = ts(108)


class TSTemplateLiteralType(TypeNode):
    """`` `quasi${type}quasi` ``, a template literal type."""

    quasis: list[TemplateElement]
    types: list[TypeNode]
    SINCE = ts(401)

    def check(self) -> list[str]:
        if len(self.quasis) == len(self.types) + 1:
            return []
        return ["a TSTemplateLiteralType needs one more quasi than types"]


class TSArrayType(TypeNode):
    """`elementType[]`."""

    elementType: TypeNode
    SINCE = ts(100)


class TSTupleType(TypeNode):
    """`[elementTypes]`."""

    elementTypes: list[TypeNode]
    SINCE = ts(100)


class TSNamedTupleMember(TypeNode):
    """`label?: elementType`, in a tuple."""

    label: Identifier
    optional: bool
    elementType: TypeNode
    SINCE = ts(400)


class TSOptionalType(TypeNode):
    """`typeAnnotation?`, in a tuple."""

    typeAnnotation: TypeNode
    SINCE = ts(300)


class TSRestType(TypeNode):
    """`...typeAnnotation`, in a tuple."""

    typeAnnotation: TypeNode
    SINCE = ts(300)


class TSUnionType(TypeNode):
    """`type | type`."""

    types: list[TypeNode]
    SINCE = ts(104)

    def check(self) -> list[str]:
        return [] if len(self.types) > 1 else ["a TSUnionType needs two types"]


class TSIntersectionType(TypeNode):
    """`type & type`."""

    types: list[TypeNode]
    SINCE = ts(106)

    def check(self) -> list[str]:
        return [] if len(self.types) > 1 else ["a TSIntersectionType needs two types"]


class TSFunctionType(TypeNode):
    """`<typeParameters>(params) => returnType`."""

    typeParameters: TSTypeParameterDeclaration | None
    params: list[Identifier | Pattern | TSParameterProperty]
    returnType: TSTypeAnnotation | None
    SINCE = ts(100)


class TSConstructorType(TypeNode):
    """`abstract new <typeParameters>(params) => returnType`."""

    abstract: bool
    typeParameters: TSTypeParameterDeclaration | None
    params: list[Identifier | Pattern | TSParameterProperty]
    returnType: TSTypeAnnotation | None
    SINCE = ts(100)
    FEATURES = {"abstract": {True: ts(402)}}


class TSTypeLiteral(TypeNode):
    """`{ members }`, an object type."""

    members: list[TypeElement | Comment]
    SINCE = ts(100)


class TSMappedType(TypeNode):
    """`{ readonly [key in constraint as nameType]?: typeAnnotation }`."""

    readonly: MappedReadonly | None
    key: Identifier
    constraint: TypeNode
    nameType: TypeNode | None
    optional: MappedOptional | None
    typeAnnotation: TypeNode | None
    SINCE = ts(201)
    FEATURES = {"nameType": {True: ts(401)}, "optional": {"+?": ts(208), "-?": ts(208)},
                "readonly": {"+readonly": ts(208), "-readonly": ts(208)}}


class TSIndexedAccessType(TypeNode):
    """`objectType[indexType]`."""

    objectType: TypeNode
    indexType: TypeNode
    SINCE = ts(201)


class TSTypeOperator(TypeNode):
    """`keyof typeAnnotation`, `readonly typeAnnotation` or `unique symbol`."""

    operator: TypeOperator
    typeAnnotation: TypeNode | None
    SINCE = ts(201)
    FEATURES = {"operator": {"readonly": ts(304), "unique": ts(207)}}


class TSTypeQuery(TypeNode):
    """`typeof exprName<typeArguments>`."""

    exprName: Identifier | ThisExpression | TSQualifiedName | TSImportType
    typeArguments: TSTypeParameterInstantiation | None
    SINCE = ts(100)


class TSImportType(TypeNode):
    """`import(source, options).qualifier<typeArguments>`."""

    source: Literal
    options: ObjectExpression | None
    qualifier: Identifier | ThisExpression | TSQualifiedName | None
    typeArguments: TSTypeParameterInstantiation | None
    SINCE = ts(209)


class TSConditionalType(TypeNode):
    """`checkType extends extendsType ? trueType : falseType`."""

    checkType: TypeNode
    extendsType: TypeNode
    trueType: TypeNode
    falseType: TypeNode
    SINCE = ts(208)


class TSInferType(TypeNode):
    """`infer typeParameter`, in a conditional type's `extends`."""

    typeParameter: TSTypeParameter
    SINCE = ts(208)


class TSTypePredicate(TypeNode):
    """`asserts parameterName is typeAnnotation`, a function's return type."""

    asserts: bool
    parameterName: Identifier | TSThisType
    typeAnnotation: TSTypeAnnotation | None
    SINCE = ts(106)
    FEATURES = {"asserts": {True: ts(307)}}


# === JSX, an extension that the standards made with `jsx` accept ===


class JSXIdentifier(Node):
    """A JSX name, which may hold `-`."""

    name: str
    EXTENSION = True


class JSXNamespacedName(Node):
    """`namespace:name`."""

    namespace: JSXIdentifier
    name: JSXIdentifier
    EXTENSION = True


class JSXMemberExpression(Node):
    """`object.property`, a tag's name."""

    object: JSXIdentifier | JSXMemberExpression
    property: JSXIdentifier
    EXTENSION = True


class JSXEmptyExpression(Node):
    """Nothing, in `{}` or `{/* comment */}`."""

    EXTENSION = True


class JSXExpressionContainer(Node):
    """`{expression}`."""

    expression: Expression | JSXEmptyExpression
    EXTENSION = True


class JSXSpreadChild(Node):
    """`{...expression}`, a child."""

    expression: Expression | JSXEmptyExpression
    EXTENSION = True


class JSXText(Node):
    """Text between tags, as written."""

    raw: str
    EXTENSION = True


class JSXAttribute(Node):
    """`name=value`, or `name` without a value."""

    name: JSXIdentifier | JSXNamespacedName
    value: Literal | JSXExpressionContainer | JSXElement | JSXFragment | None
    EXTENSION = True


class JSXSpreadAttribute(Node):
    """`{...argument}`, an attribute."""

    argument: Expression
    EXTENSION = True


class JSXOpeningElement(Node):
    """`<name<typeArguments> attributes>`, or with `selfClosing` `<name ... />`."""

    name: JSXIdentifier | JSXMemberExpression | JSXNamespacedName
    typeArguments: TSTypeParameterInstantiation | None
    attributes: list[JSXAttribute | JSXSpreadAttribute]
    selfClosing: bool
    EXTENSION = True


class JSXClosingElement(Node):
    """`</name>`."""

    name: JSXIdentifier | JSXMemberExpression | JSXNamespacedName
    EXTENSION = True


class JSXElement(Expression):
    """`<name ...>children</name>`."""

    openingElement: JSXOpeningElement
    children: list[JSXText | JSXExpressionContainer | JSXSpreadChild | JSXElement | JSXFragment]
    closingElement: JSXClosingElement | None
    EXTENSION = True


class JSXOpeningFragment(Node):
    """`<>`."""

    EXTENSION = True


class JSXClosingFragment(Node):
    """`</>`."""

    EXTENSION = True


class JSXFragment(Expression):
    """`<>children</>`."""

    openingFragment: JSXOpeningFragment
    children: list[JSXText | JSXExpressionContainer | JSXSpreadChild | JSXElement | JSXFragment]
    closingFragment: JSXClosingFragment
    EXTENSION = True


KINDS: list[type[Node]] = [
    Comment, Program, Identifier, PrivateIdentifier,
    Literal, TemplateElement, TemplateLiteral, TaggedTemplateExpression, ThisExpression, Super,
    ParenthesizedExpression, Elision, SpreadElement, ArrayExpression, Property, ObjectExpression, FunctionExpression,
    ArrowFunctionExpression, ClassExpression, MetaProperty,
    MemberExpression, CallExpression, ChainExpression, NewExpression, ImportExpression, UpdateExpression,
    UnaryExpression, AwaitExpression, BinaryExpression, LogicalExpression, ConditionalExpression, AssignmentExpression,
    SequenceExpression, YieldExpression,
    TSAsExpression, TSSatisfiesExpression, TSTypeAssertion, TSNonNullExpression, TSInstantiationExpression,
    ArrayPattern, ObjectPattern, AssignmentPattern, RestElement,
    ExpressionStatement, BlockStatement, EmptyStatement, DebuggerStatement, WithStatement, ReturnStatement,
    LabeledStatement, BreakStatement, ContinueStatement, IfStatement, SwitchCase, SwitchStatement, ThrowStatement,
    CatchClause, TryStatement, WhileStatement, DoWhileStatement, ForStatement, ForInStatement, ForOfStatement,
    VariableDeclarator, VariableDeclaration, FunctionDeclaration, TSDeclareFunction, Decorator, ClassBody,
    ClassDeclaration, StaticBlock, MethodDefinition, TSAbstractMethodDefinition, TSEmptyBodyFunctionExpression,
    PropertyDefinition, TSAbstractPropertyDefinition, AccessorProperty, TSAbstractAccessorProperty,
    TSParameterProperty,
    ImportAttribute, ImportSpecifier, ImportDefaultSpecifier, ImportNamespaceSpecifier, ImportDeclaration,
    ExportSpecifier, ExportNamedDeclaration, ExportDefaultDeclaration, ExportAllDeclaration,
    TSImportEqualsDeclaration, TSExternalModuleReference, TSExportAssignment, TSNamespaceExportDeclaration,
    TSTypeAnnotation, TSTypeParameter, TSTypeParameterDeclaration, TSTypeParameterInstantiation,
    TSTypeAliasDeclaration, TSInterfaceHeritage, TSClassImplements, TSInterfaceBody, TSInterfaceDeclaration,
    TSEnumMember, TSEnumBody, TSEnumDeclaration, TSModuleBlock, TSModuleDeclaration,
    TSPropertySignature, TSMethodSignature, TSCallSignatureDeclaration, TSConstructSignatureDeclaration,
    TSIndexSignature,
    TSAnyKeyword, TSUnknownKeyword, TSNumberKeyword, TSBigIntKeyword, TSBooleanKeyword, TSStringKeyword,
    TSSymbolKeyword, TSObjectKeyword, TSNeverKeyword, TSVoidKeyword, TSUndefinedKeyword, TSNullKeyword,
    TSIntrinsicKeyword, TSThisType, TSQualifiedName, TSTypeReference, TSParenthesizedType, TSLiteralType,
    TSTemplateLiteralType, TSArrayType, TSTupleType, TSNamedTupleMember, TSOptionalType, TSRestType, TSUnionType,
    TSIntersectionType, TSFunctionType, TSConstructorType, TSTypeLiteral, TSMappedType, TSIndexedAccessType,
    TSTypeOperator, TSTypeQuery, TSImportType, TSConditionalType, TSInferType, TSTypePredicate,
    JSXIdentifier, JSXNamespacedName, JSXMemberExpression, JSXEmptyExpression, JSXExpressionContainer,
    JSXSpreadChild, JSXText, JSXAttribute, JSXSpreadAttribute, JSXOpeningElement, JSXClosingElement, JSXElement,
    JSXOpeningFragment, JSXClosingFragment, JSXFragment,
]

LANGUAGE = Language("TypeScript", KINDS, base={ES: 2015, TS: 100})

__all__ += [k.__name__ for k in KINDS] + [
    "Statement", "Expression", "Pattern", "TypeNode", "ClassElement", "TypeElement", "es", "ts", "ES", "TS"]
