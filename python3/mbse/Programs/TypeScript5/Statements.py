"""Statements: TypeScript 5's statements, declarations and their parts, 5.0 to 5.9, and the JavaScript they hold, as
value objects, as the user decided for the port
([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../docs/proposals/port/README.md#stage-3-the-whole-tree-as-values)):
"the whole AST is value objects". A source file, `Programs.TypeScript5.Program`, is a `Programs.Framework.File`, a
reference object the workspace owns by its path, and holds its statements as one value, its `body`; each statement kind
refines `Programs.Framework.Statement`.

Kinds follow typescript-estree, as mbse-programs 0.3 had them (`TypeScript/Syntax.py`) and mbse-expressions' TypeScript5
names its terms: the same kinds, with the same names and properties in source order, but for those whose names are
Python's keywords or clash with a kind's tag (`isAsync`, `isAwait`, `declarationKind`, `methodKind`, `moduleKind`), and
without what follows from the rest (`ExpressionStatement.directive`, `Program.sourceType`, `TSModuleDeclaration.global`)
or what typescript-estree keeps only for compatibility. A list of statements is a `Programs.TypeScript5.Body`, each
element a branch of the union `Programs.TypeScript5.Statement`, tagged by its kind's name in lower case
(`ifstatement`, `functiondeclaration`, `error`), as mbse-expressions' dialects tag theirs; a property that holds one
statement (`IfStatement.consequent`, `LabeledStatement.body`) holds a `Statement` itself.

A statement's expressions are mbse-expressions' TypeScript family's terms, value objects its properties hold: a
`TypeScript5` term (`Expressions.TypeScript.TypeScript5.Term`) where an expression stands, a `TypeScript Types` term
(`Expressions.TypeScript.Types.Term`) where a type does, a `TypeScript Patterns` term
(`Expressions.TypeScript.Patterns.Term`) where a binding pattern does (a declarator's `id`, a catch clause's `param`, a
`for ... of`'s target), and the dialect's own helpers (`TSTypeAnnotation`, `TSTypeParameterDeclaration`,
`TSTypeParameterInstantiation`, `Decorator`, `TSClassImplements`). Where a term holds statements, a property of the term
holds them, as the user decided ("the crossover should be modeled as a property of T_A"): a function's and an arrow's
`block`, of mbse-expressions' open union `Expressions.TypeScript.TypeScript5.Block`, which `install` extends with
`Programs.TypeScript5.BlockStatement` (`blockstatement`); a class expression's `classBody`, of
`Expressions.TypeScript.TypeScript5.ClassBody`, which it extends with `Programs.TypeScript5.ClassBody` (`classbody`).

Parts of the grammar:

- **Clauses**, refining `Programs.Framework.Clause`: a `switch`'s case (`SwitchCase`, its `consequent` statements) and a
  `try`'s `catch` (`CatchClause`), each allowed only within its statement and holding statements; a class's static
  block (`StaticBlock`) too *(agent: it holds statements and stands only in a class body)*.
- **Class members**, the elements of a `ClassBody` (`Programs.TypeScript5.ClassElement`): methods and accessors
  (`MethodDefinition`, `TSAbstractMethodDefinition`, each its `value` a function expression whose `block` holds its
  statements), fields (`PropertyDefinition`, `TSAbstractPropertyDefinition`, `AccessorProperty`,
  `TSAbstractAccessorProperty`), `StaticBlock`, `TSIndexSignature` (`TypeScript Types`'), comments and errors, in source
  order. Each member but a static block and an index signature is a value with its `line`, refining nothing of the
  framework's *(agent: a member that holds no statement of its own is no clause, VOC-032)*.
- **Parts that hold no statement**, value objects of what holds them: a declaration's `VariableDeclarator`s, an
  import's specifiers (`ImportSpecifier`, `ImportDefaultSpecifier`, `ImportNamespaceSpecifier`) and attributes
  (`ImportAttribute`), an export's specifiers (`ExportSpecifier`), an interface's heritage (`TSInterfaceHeritage`) and
  body (`TSInterfaceBody`, its members `TypeScript Types`' `TypeElement`s), an enum's body and members (`TSEnumBody`,
  `TSEnumMember`), a namespace's block (`TSModuleBlock`), and an import-equals' external reference
  (`TSExternalModuleReference`).
- **Where a grammar position takes either of two**, a union of them: a `for`'s `init`
  (`Programs.TypeScript5.ForInit`: a `variabledeclaration`, or a term, `expression`), a `for ... in`'s or `for ... of`'s
  `left` (`ForLeft`: a `variabledeclaration`, or a pattern, `pattern`), an export default's `declaration`
  (`DefaultDeclaration`: a `statement`, or a term, `expression`), an import's specifiers (`ImportClause`), a module's
  name (`ModuleName`: an `identifier` or a `literal`, or a `tsqualifiedname`), and an import-equals' reference
  (`ModuleReference`) *(agent, each)*.
- **Comments** are statements (`Comment`, its `text` without its delimiters, `block` where written `/* */`, `trailing`
  where it ends the line of what is before it), where statements, class members and enum members are listed;
  elsewhere they are dropped, as 0.3 dropped them. An interface's are `TypeScript Types`' own `Comment`.
- **Invalid syntax** is `Programs.TypeScript5.Error`, refining `Programs.Framework.Error`: its `text` as written, and
  the statements recovered within it, its `body`. It may stand wherever a statement, a clause or a class member may, a
  branch `error` of each union *(agent)*.

Each statement, clause and member has the line it begins on (`line`), absent where it was built rather than parsed. Run
`install` after `Programs.Framework.Model.install` and mbse-expressions' `TypeScript5`, `TypeScript Types`, `TypeScript
Patterns` and `TypeScript RegExp` installs, each in a transaction of its own; run again, it writes nothing.
"""

from typing import Any

LANGUAGE = "Programs.TypeScript5"

STATEMENTS = (
    "Comment", "ExpressionStatement", "BlockStatement", "EmptyStatement", "DebuggerStatement", "WithStatement",
    "ReturnStatement", "LabeledStatement", "BreakStatement", "ContinueStatement", "IfStatement", "SwitchStatement",
    "ThrowStatement", "TryStatement", "WhileStatement", "DoWhileStatement", "ForStatement", "ForInStatement",
    "ForOfStatement", "VariableDeclaration", "FunctionDeclaration", "TSDeclareFunction", "ClassDeclaration",
    "ImportDeclaration", "ExportNamedDeclaration", "ExportDefaultDeclaration", "ExportAllDeclaration",
    "TSImportEqualsDeclaration", "TSExportAssignment", "TSNamespaceExportDeclaration", "TSTypeAliasDeclaration",
    "TSInterfaceDeclaration", "TSEnumDeclaration", "TSModuleDeclaration")
CLAUSES = ("SwitchCase", "CatchClause", "StaticBlock")
MEMBERS = ("MethodDefinition", "TSAbstractMethodDefinition", "PropertyDefinition", "TSAbstractPropertyDefinition",
           "AccessorProperty", "TSAbstractAccessorProperty")
PARTS = ("ClassBody", "VariableDeclarator", "ImportSpecifier", "ImportDefaultSpecifier", "ImportNamespaceSpecifier",
         "ImportAttribute", "ExportSpecifier", "TSInterfaceHeritage", "TSInterfaceBody", "TSEnumBody", "TSEnumMember",
         "TSModuleBlock", "TSExternalModuleReference")
KINDS = STATEMENTS + CLAUSES + MEMBERS
UNIONS = ("Statement", "Case", "Handler", "ClassElement", "EnumElement", "ForInit", "ForLeft", "DefaultDeclaration",
          "ImportClause", "ModuleName", "ModuleReference")
CONTAINERS = ("Body", "Cases", "ClassElements", "EnumElements", "Declarators", "ImportClauses", "ImportAttributes",
              "ExportSpecifiers", "Heritages", "Decorators", "Implements", "TypeElements", "Parameters")


def install(txn: Any) -> Any:
    """TypeScript 5's statement kinds, their parts, its program and its language's singleton, upserted, and its block
    and class body added to mbse-expressions' open unions."""
    S, F = txn.Schemas, txn.Programs.Framework
    TS = txn.Expressions.TypeScript
    E, Ty, Pt = TS.TypeScript5, TS.Types, TS.Patterns
    T, TypeTerm, PatternTerm = E.Term, Ty.Term, Pt.Term
    Identifier, Literal = E.Identifier, E.Literal
    Annotation, Parameters, Arguments = E.TSTypeAnnotation, E.TSTypeParameterDeclaration, E.TSTypeParameterInstantiation

    def kind(name: str, properties: Any = lambda _: {}) -> Any:
        """A statement, clause or member kind: a value object refining `Statement` or `Clause` (a member, nothing),
        with its own properties, made within its spec, given the spec's symbols, and its line."""
        base = [F.Clause] if name in CLAUSES else [F.Statement] if name in STATEMENTS else []
        line = {} if base else {"line": S.OfInt}
        return lambda _: getattr(_, name).name(f"{LANGUAGE}.{name}").refines(base).properties(
            {**line, **properties(_)})

    def part(name: str, properties: Any) -> Any:
        return lambda _: getattr(_, name).name(f"{LANGUAGE}.{name}").properties(properties(_))

    def union(name: str, branches: Any) -> Any:
        """A union of `branches`, each a tag and the schema it names, given the spec's symbols, and the language's
        error."""
        return lambda _: getattr(_, name).name(f"{LANGUAGE}.{name}").branches([
            *(lambda t, tag=tag, schema=schema: t.name(tag).schema([schema]) for tag, schema in branches(_)),
            lambda t: t.name("error").schema([_.Error])])

    def tags(*names: str) -> Any:
        return lambda _: [(name.lower(), getattr(_, name)) for name in names]

    def named(name: str, element: Any) -> Any:
        """A named container: a list, by index, of `element`."""
        return lambda _: getattr(_, name).name(f"{LANGUAGE}.{name}").index([S.OfInt]).element([element(_)])

    def function(_: Any) -> dict[str, Any]:
        """A function declaration's properties; a `declare`d one has no body."""
        return {"isAsync": S.OfBool, "generator": S.OfBool, "id": Identifier, "typeParameters": Parameters,
                "params": _.Parameters, "returnType": Annotation}

    def member(_: Any) -> dict[str, Any]:
        """What a class member's modifiers and key are."""
        return {"decorators": _.Decorators, "accessibility": S.OfStr, "static": S.OfBool, "override": S.OfBool}

    def field(_: Any) -> dict[str, Any]:
        return {**member(_), "declare": S.OfBool, "readonly": S.OfBool, "computed": S.OfBool, "key": T,
                "optional": S.OfBool, "definite": S.OfBool, "typeAnnotation": Annotation, "value": T}

    def method(_: Any) -> dict[str, Any]:
        return {**member(_), "methodKind": S.OfStr, "computed": S.OfBool, "key": T, "optional": S.OfBool, "value": T}

    def loop(_: Any) -> dict[str, Any]:
        return {"left": _.ForLeft, "right": T, "body": _.Statement}

    return txn.uid("mbse.Programs.TypeScript5/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"Language": S.OfObject, "Program": S.OfObject, "Error": S.OfObject, "Block": S.OfUnion,
                  "ClassBodies": S.OfUnion,  # mbse-expressions' open unions, extended
                  **{name: S.OfContainer for name in CONTAINERS}, **{name: S.OfUnion for name in UNIONS},
                  **{name: S.OfObject for name in KINDS + PARTS}})
        .spec([
            lambda _: _.Language.name(f"{LANGUAGE}.Language").ref(True).singleton(LANGUAGE),
            lambda _: _.Program.name(f"{LANGUAGE}.Program").ref(True).refines([F.File]).properties({
                "hashbang": S.OfStr, "body": _.Body}),
            lambda _: _.Error.name(f"{LANGUAGE}.Error").refines([F.Error]).properties({"body": _.Body}),
            # the unions and containers
            union("Statement", tags(*STATEMENTS)),
            union("Case", tags("SwitchCase")),
            union("Handler", tags("CatchClause")),
            union("ClassElement", lambda _: [*tags(*MEMBERS, "StaticBlock", "Comment")(_),
                                             ("tsindexsignature", Ty.TSIndexSignature)]),
            union("EnumElement", tags("TSEnumMember", "Comment")),
            union("ForInit", lambda _: [("variabledeclaration", _.VariableDeclaration), ("expression", T)]),
            union("ForLeft", lambda _: [("variabledeclaration", _.VariableDeclaration), ("pattern", PatternTerm)]),
            union("DefaultDeclaration", lambda _: [("statement", _.Statement), ("expression", T)]),
            union("ImportClause", tags("ImportSpecifier", "ImportDefaultSpecifier", "ImportNamespaceSpecifier")),
            union("ModuleName", lambda _: [("identifier", Identifier), ("literal", Literal),
                                           ("tsqualifiedname", Ty.TSQualifiedName)]),
            union("ModuleReference", lambda _: [("identifier", Identifier), ("tsqualifiedname", Ty.TSQualifiedName),
                                                ("tsexternalmodulereference", _.TSExternalModuleReference)]),
            named("Body", lambda _: _.Statement), named("Cases", lambda _: _.Case),
            named("ClassElements", lambda _: _.ClassElement), named("EnumElements", lambda _: _.EnumElement),
            named("Declarators", lambda _: _.VariableDeclarator), named("ImportClauses", lambda _: _.ImportClause),
            named("ImportAttributes", lambda _: _.ImportAttribute),
            named("ExportSpecifiers", lambda _: _.ExportSpecifier), named("Heritages", lambda _: _.TSInterfaceHeritage),
            named("Decorators", lambda _: E.Decorator), named("Implements", lambda _: E.TSClassImplements),
            named("TypeElements", lambda _: Ty.TypeElement), named("Parameters", lambda _: PatternTerm),
            # mbse-expressions' open unions, given this grammar's block and class body
            lambda _: _.Block.name("Expressions.TypeScript.TypeScript5.Block").branches([
                lambda t: t.name("blockstatement").schema([_.BlockStatement])]),
            lambda _: _.ClassBodies.name("Expressions.TypeScript.TypeScript5.ClassBody").branches([
                lambda t: t.name("classbody").schema([_.ClassBody])]),
            # statements
            kind("Comment", lambda _: {"text": S.OfStr, "block": S.OfBool, "trailing": S.OfBool}),
            kind("ExpressionStatement", lambda _: {"expression": T}),
            kind("BlockStatement", lambda _: {"body": _.Body}),
            kind("EmptyStatement"), kind("DebuggerStatement"),
            kind("WithStatement", lambda _: {"object": T, "body": _.Statement}),
            kind("ReturnStatement", lambda _: {"argument": T}),
            kind("LabeledStatement", lambda _: {"label": Identifier, "body": _.Statement}),
            kind("BreakStatement", lambda _: {"label": Identifier}),
            kind("ContinueStatement", lambda _: {"label": Identifier}),
            kind("IfStatement", lambda _: {"test": T, "consequent": _.Statement, "alternate": _.Statement}),
            kind("SwitchStatement", lambda _: {"discriminant": T, "cases": _.Cases}),
            kind("SwitchCase", lambda _: {"test": T, "consequent": _.Body}),
            kind("ThrowStatement", lambda _: {"argument": T}),
            kind("TryStatement", lambda _: {"block": _.BlockStatement, "handler": _.Handler,
                                            "finalizer": _.BlockStatement}),
            kind("CatchClause", lambda _: {"param": PatternTerm, "body": _.BlockStatement}),
            kind("WhileStatement", lambda _: {"test": T, "body": _.Statement}),
            kind("DoWhileStatement", lambda _: {"body": _.Statement, "test": T}),
            kind("ForStatement", lambda _: {"init": _.ForInit, "test": T, "update": T, "body": _.Statement}),
            kind("ForInStatement", loop),
            kind("ForOfStatement", lambda _: {"isAwait": S.OfBool, **loop(_)}),
            # declarations
            kind("VariableDeclaration", lambda _: {"declare": S.OfBool, "declarationKind": S.OfStr,
                                                   "declarations": _.Declarators}),
            part("VariableDeclarator", lambda _: {"id": PatternTerm, "definite": S.OfBool, "init": T}),
            kind("FunctionDeclaration", lambda _: {**function(_), "body": _.BlockStatement}),
            kind("TSDeclareFunction", lambda _: {"declare": S.OfBool, **function(_)}),
            kind("ClassDeclaration", lambda _: {
                "decorators": _.Decorators, "declare": S.OfBool, "abstract": S.OfBool, "id": Identifier,
                "typeParameters": Parameters, "superClass": T, "superTypeArguments": Arguments,
                "implements": _.Implements, "body": _.ClassBody}),
            part("ClassBody", lambda _: {"body": _.ClassElements}),
            kind("StaticBlock", lambda _: {"body": _.Body}),
            kind("MethodDefinition", method), kind("TSAbstractMethodDefinition", method),
            kind("PropertyDefinition", field), kind("TSAbstractPropertyDefinition", field),
            kind("AccessorProperty", field), kind("TSAbstractAccessorProperty", field),
            # modules
            kind("ImportDeclaration", lambda _: {"importKind": S.OfStr, "phase": S.OfStr,
                                                 "specifiers": _.ImportClauses, "source": Literal,
                                                 "attributes": _.ImportAttributes}),
            part("ImportSpecifier", lambda _: {"importKind": S.OfStr, "imported": T, "local": Identifier}),
            part("ImportDefaultSpecifier", lambda _: {"local": Identifier}),
            part("ImportNamespaceSpecifier", lambda _: {"local": Identifier}),
            part("ImportAttribute", lambda _: {"key": T, "value": Literal}),
            kind("ExportNamedDeclaration", lambda _: {"exportKind": S.OfStr, "declaration": _.Statement,
                                                      "specifiers": _.ExportSpecifiers, "source": Literal,
                                                      "attributes": _.ImportAttributes}),
            part("ExportSpecifier", lambda _: {"exportKind": S.OfStr, "local": T, "exported": T}),
            kind("ExportDefaultDeclaration", lambda _: {"declaration": _.DefaultDeclaration}),
            kind("ExportAllDeclaration", lambda _: {"exportKind": S.OfStr, "exported": T, "source": Literal,
                                                    "attributes": _.ImportAttributes}),
            kind("TSImportEqualsDeclaration", lambda _: {"importKind": S.OfStr, "id": Identifier,
                                                         "moduleReference": _.ModuleReference}),
            part("TSExternalModuleReference", lambda _: {"expression": Literal}),
            kind("TSExportAssignment", lambda _: {"expression": T}),
            kind("TSNamespaceExportDeclaration", lambda _: {"id": Identifier}),
            # TypeScript's declarations
            kind("TSTypeAliasDeclaration", lambda _: {"declare": S.OfBool, "id": Identifier,
                                                      "typeParameters": Parameters, "typeAnnotation": TypeTerm}),
            kind("TSInterfaceDeclaration", lambda _: {"declare": S.OfBool, "id": Identifier,
                                                      "typeParameters": Parameters, "extends": _.Heritages,
                                                      "body": _.TSInterfaceBody}),
            part("TSInterfaceHeritage", lambda _: {"expression": T, "typeArguments": Arguments}),
            part("TSInterfaceBody", lambda _: {"body": _.TypeElements}),
            kind("TSEnumDeclaration", lambda _: {"declare": S.OfBool, "const": S.OfBool, "id": Identifier,
                                                 "body": _.TSEnumBody}),
            part("TSEnumBody", lambda _: {"members": _.EnumElements}),
            part("TSEnumMember", lambda _: {"line": S.OfInt, "computed": S.OfBool, "id": T, "initializer": T}),
            kind("TSModuleDeclaration", lambda _: {"declare": S.OfBool, "moduleKind": S.OfStr, "id": _.ModuleName,
                                                   "body": _.TSModuleBlock}),
            part("TSModuleBlock", lambda _: {"body": _.Body}),
        ])]))])
