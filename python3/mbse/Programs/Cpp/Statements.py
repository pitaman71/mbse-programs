"""Statements: C++'s statements, declarations, class members and their parts, C++17 to C++23, with the GNU extensions
mbse-programs 0.3 kept, as value objects, as the user decided for the port
([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../docs/proposals/port/README.md#stage-3-the-whole-tree-as-values)):
"the whole AST is value objects". A source file, `Programs.Cpp.TranslationUnit`, is a `Programs.Framework.File`, a
reference object the workspace owns by its path, and holds its declarations and statements as one value, its `body`;
each statement and declaration kind refines `Programs.Framework.Statement`.

As the user decided (stage 4, "2(a)"): "`Programs.C` defines its kinds; `Programs.Cpp` defines only what C++ adds, its
union listing C's kinds and its own, as mbse-expressions' C++ writers derive from C's". A C kind's properties hold C's
terms, which a C++ term is not (mbse-expressions' `Cpp` is a dialect of its own, with its own copy of each kind it
shares with C), so C's kinds are reused as mbse-expressions' C++ reuses C's: by name and by definition, each a kind
`Programs.Cpp.<Kind>` with C's properties (`Programs.C.Statements.properties`, the table C defines its kinds by), its
expressions C++'s terms *(agent: a schema of C's cannot hold a C++ term)*. `Programs.Cpp.Statement`, the union of its
statements, lists C's kinds and C++'s own, each tagged by its kind's name in lower case. Where C++'s grammar changes a C
kind, the kind is restated here with C++'s properties:

- `IfStatement`: `constexpr`, `consteval` and `negated` (`if !consteval`, C++23, which has no condition), its
  `initializer` (C++17) and a `condition` that may declare (`Condition`);
- `SwitchStatement`: its `initializer`, and a `condition` that may declare; `WhileStatement` and `ForStatement`: a
  `condition` that may declare; a `for`'s and every other initializer an `InitStatement` (C++'s init-statement: a
  simple declaration, an alias declaration (C++23) or a term);
- `FunctionDefinition`: no K&R declarations, but its `virt_specifiers` (`override`, `final`), its trailing `requires`,
  a constructor's member `initializers`, and a `body` of `FunctionBody`: a block, a function-try-block (`TryStatement`),
  `= default` or `= delete`;
- `InitDeclarator`: its `initializer` C++'s (`Expressions.Cpp.Expressions.Initializer`: `= x`, `(x)` or `{x}`), and its
  trailing `requires`; `MemberDeclarator`: its `requires`, `virt_specifiers`, `pure` (`= 0`), `bitfield` and its
  default member `initializer` (C++20 after a bit-field).

C++'s own statements and declarations: `RangeForStatement` (C++20's `initializer`), `CoReturnStatement`, `TryStatement`
with its `Handler`s, `EmptyDeclaration` (`;` where a declaration stands), `NamespaceDefinition` (its `NamespaceName`s,
nested and inline), `NamespaceAliasDefinition`, `UsingDirective`, `UsingDeclaration` (its `UsingDeclarator`s),
`UsingEnumDeclaration` (C++20), `AliasDeclaration`, `LinkageSpecification` (`extern "C"`, braced or not),
`TemplateDeclaration` (its parameters, mbse-expressions' `TemplateParameter`s, its `requires`, and the declaration it
templates, `Templated`; an explicit specialization has no parameters), `ExplicitInstantiation` (`extern` with
C++11's), `ConceptDefinition` (C++20), and C++20's modules: `ModuleDeclaration`, `GlobalModuleFragment`,
`PrivateModuleFragment`, `ImportDeclaration` and `ExportDeclaration`, named and with the properties 0.3's Ccpp gave
them (`Ccpp/Syntax.py`).

Where a term holds statements or declarations, a property of the term holds them, as the user decided ("the crossover
should be modeled as a property of T_A"), each an open union of mbse-expressions' that `install` extends:

- a lambda's and a GNU statement expression's `block`, of `Expressions.Cpp.Expressions.Block`, extended with
  `Programs.Cpp.CompoundStatement` (`compoundstatement`);
- a class's, a struct's or a union's `members`, of `Expressions.Cpp.Expressions.Members`, extended with
  `Programs.Cpp.MemberList` (`memberlist`), its member specification;
- a conditional directive's `group`, of `Expressions.C.Preprocessor.Group`, which C's install extends too, extended
  with `Programs.Cpp.Group` and `Programs.Cpp.MemberGroup`, tagged `cpp_group` and `cpp_membergroup` *(agent: C's
  tags, `group` and `membergroup`, are C's kinds', and a store holding C++ holds C's install too)*.

Parts of the grammar:

- **Clauses**, refining `Programs.Framework.Clause`: a `try`'s `catch` (`Handler`, its `parameter` and its `body`), which
  only a `try` holds and which holds statements.
- **Members**, the elements of a `MemberList` (`Programs.Cpp.Members`, of the union `Programs.Cpp.Member`): a
  `MemberDeclaration` (C's, its declarators C++'s `MemberDeclarator`s; a nested class, a friend, a constructor's or a
  conversion's declaration among them), a member function's `FunctionDefinition`, an `AccessSpecifier` (`public:`), a
  `UsingDeclaration`, a `UsingEnumDeclaration`, an `AliasDeclaration`, a `StaticAssertDeclaration`, a
  `TemplateDeclaration`, an `EmptyDeclaration`, a `Directive`, a `Comment` and an `Error`, in source order, each with
  its line.
- **Parts that hold no statement**, value objects of what holds them: C's (`InitDeclarator`, `MemberDeclarator`,
  `AsmOperand`, `MemberList`, `Group`, `MemberGroup`), and `MemberInitializer` (`member(args)`, `member{items}`, a
  pack's `...`), `NamespaceName`, `UsingDeclarator`, `DefaultedBody` and `DeletedBody`.
- **Directives and comments** are statements, as for C ("3(a)"); among an enumeration's enumerators they are C
  Preprocessor's own terms, as mbse-expressions' Cpp Types holds them.
- **Invalid syntax** is `Programs.Cpp.Error`, refining `Programs.Framework.Error`: its `text` as written and the
  statements recovered within it, its `body`, a branch `error` of each union.

Each statement, clause and member has the line it begins on (`line`), absent where it was built rather than parsed. Run
`install` after `Programs.Framework.Model.install`, mbse-expressions' `Cpp`, `Cpp Types` and `C Preprocessor` installs
and `Programs.C.Statements.install`, each in a transaction of its own; run again, it writes nothing.
"""

from typing import Any

from ..C import Statements as C

LANGUAGE = "Programs.Cpp"

REUSED = C.STATEMENTS
"""C's statement and declaration kinds, each a kind of C++'s by its name."""
STATEMENTS = REUSED + (
    "RangeForStatement", "CoReturnStatement", "TryStatement", "EmptyDeclaration", "NamespaceDefinition",
    "NamespaceAliasDefinition", "UsingDirective", "UsingDeclaration", "UsingEnumDeclaration", "AliasDeclaration",
    "LinkageSpecification", "TemplateDeclaration", "ExplicitInstantiation", "ConceptDefinition", "ModuleDeclaration",
    "GlobalModuleFragment", "PrivateModuleFragment", "ImportDeclaration", "ExportDeclaration")
CLAUSES = ("Handler",)
MEMBERS = ("MemberDeclaration", "AccessSpecifier")
PARTS = ("InitDeclarator", "MemberDeclarator", "MemberList", "Group", "MemberGroup", "AsmOperand", "MemberInitializer",
         "NamespaceName", "UsingDeclarator", "DefaultedBody", "DeletedBody")
KINDS = STATEMENTS + CLAUSES + MEMBERS
OWN = tuple(kind for kind in KINDS + PARTS if kind not in C.KINDS + C.PARTS)
"""The kinds and parts C++ adds to C's."""
RESTATED = ("IfStatement", "SwitchStatement", "WhileStatement", "ForStatement", "FunctionDefinition", "InitDeclarator",
            "MemberDeclarator")
"""C's kinds whose properties C++'s grammar changes, restated here."""
UNIONS = ("Statement", "Member", "InitStatement", "Condition", "FunctionBody", "Templated")
CONTAINERS = ("Body", "Members", "Declarators", "MemberDeclarators", "Specifiers", "Attributes", "AsmOperands",
              "Terms", "Identifiers", "Strs", "Handlers", "MemberInitializers", "NamespaceNames", "UsingDeclarators",
              "TemplateParameters")


class _Dialect:
    """The schemas C++'s statements hold expressions of, as `Programs.C.Statements.properties` reads them: C++'s, Cpp
    Types' and C Preprocessor's."""

    def __init__(self, txn: Any):
        Cpp = txn.Expressions.Cpp.Expressions
        self.S, self.Term, self.Identifier, self.Directive = txn.Schemas, Cpp.Term, Cpp.Identifier, (
            txn.Expressions.C.Preprocessor.Term)
        self.Specifier, self.Declarator, self.AttributeSpecifier = Cpp.Specifier, Cpp.Declarator, Cpp.AttributeSpecifier
        self.Cpp = Cpp  # its other helpers: a name, an initializer, a parameter


def properties(_: Any, dialect: Any) -> dict[str, dict[str, Any]]:
    """Each kind's and part's own properties, in source order: C's (`Programs.C.Statements.properties`), but those C++
    restates, and C++'s own, given the spec's symbols and C++'s schemas."""
    S, T, Identifier, Declarator = dialect.S, dialect.Term, dialect.Identifier, dialect.Declarator
    Cpp = dialect.Cpp
    declaration = {"attributes": _.Attributes, "specifiers": _.Specifiers}
    return {
        **C.properties(_, dialect),
        # C's kinds, as C++ has them
        "IfStatement": {"constexpr": S.OfBool, "consteval": S.OfBool, "negated": S.OfBool,
                        "initializer": _.InitStatement, "condition": _.Condition, "consequence": _.Statement,
                        "alternative": _.Statement},
        "SwitchStatement": {"initializer": _.InitStatement, "condition": _.Condition, "body": _.Statement},
        "WhileStatement": {"condition": _.Condition, "body": _.Statement},
        "ForStatement": {"initializer": _.InitStatement, "condition": _.Condition, "increment": T,
                         "body": _.Statement},
        "FunctionDefinition": {**declaration, "declarator": Declarator, "virt_specifiers": _.Strs, "requires": T,
                               "initializers": _.MemberInitializers, "body": _.FunctionBody},
        "InitDeclarator": {"declarator": Declarator, "initializer": Cpp.Initializer, "requires": T},
        "MemberDeclarator": {"declarator": Declarator, "requires": T, "virt_specifiers": _.Strs, "pure": S.OfBool,
                             "bitfield": T, "initializer": Cpp.Initializer},
        # statements
        "RangeForStatement": {"initializer": _.InitStatement, "declaration": _.SimpleDeclaration, "range": T,
                              "body": _.Statement},
        "CoReturnStatement": {"value": T},
        "TryStatement": {"body": _.CompoundStatement, "handlers": _.Handlers},
        "Handler": {"parameter": Cpp.Parameter, "body": _.CompoundStatement},  # `catch (...)`: an ellipsis
        # declarations
        "EmptyDeclaration": {},
        "NamespaceDefinition": {"inline": S.OfBool, "attributes": _.Attributes, "names": _.NamespaceNames,
                                "body": _.Body},
        "NamespaceName": {"inline": S.OfBool, "name": Identifier},
        "NamespaceAliasDefinition": {"name": Identifier, "target": Cpp.Name},
        "UsingDirective": {"attributes": _.Attributes, "name": Cpp.Name},
        "UsingDeclaration": {"declarators": _.UsingDeclarators},
        "UsingDeclarator": {"typename_keyword": S.OfBool, "name": Cpp.Name, "pack": S.OfBool},
        "UsingEnumDeclaration": {"type": Cpp.Name},
        "AliasDeclaration": {"name": Identifier, "attributes": _.Attributes, "type": _.TypesTerm},
        "LinkageSpecification": {"language": S.OfStr, "braced": S.OfBool, "body": _.Body},
        "TemplateDeclaration": {"parameters": _.TemplateParameters, "requires": T, "declaration": _.Templated},
        "ExplicitInstantiation": {"extern": S.OfBool, "declaration": _.SimpleDeclaration},
        "ConceptDefinition": {"name": Identifier, "attributes": _.Attributes, "constraint": T},
        "MemberInitializer": {"member": Cpp.Name, "initializer": Cpp.Initializer, "pack": S.OfBool},
        "DefaultedBody": {}, "DeletedBody": {},
        # modules: names dotted, as written (`std.core`)
        "ModuleDeclaration": {"export": S.OfBool, "name": S.OfStr, "partition": S.OfStr, "attributes": _.Attributes},
        "GlobalModuleFragment": {}, "PrivateModuleFragment": {},
        "ImportDeclaration": {"export": S.OfBool, "name": S.OfStr, "partition": S.OfStr, "header": S.OfStr,
                              "system": S.OfBool, "attributes": _.Attributes},
        "ExportDeclaration": {"braced": S.OfBool, "body": _.Body},
        # a class's members
        "AccessSpecifier": {"access": S.OfStr},
    }


def install(txn: Any) -> Any:
    """C++'s statement, declaration and member kinds, their parts, its translation unit and its language's singleton,
    upserted, and its compound statement, member list and groups added to mbse-expressions' open unions."""
    S, F = txn.Schemas, txn.Programs.Framework
    dialect = _Dialect(txn)
    T = dialect.Term

    def kind(name: str) -> Any:
        """A statement, clause or member kind: a value object refining `Statement` or `Clause` (a member, nothing),
        with its own properties, and its line."""
        base = [F.Clause] if name in CLAUSES else [F.Statement] if name in STATEMENTS else []
        line = {} if base else {"line": S.OfInt}
        return lambda _: getattr(_, name).name(f"{LANGUAGE}.{name}").refines(base).properties(
            {**line, **properties(_, dialect)[name]})

    def part(name: str) -> Any:
        return lambda _: getattr(_, name).name(f"{LANGUAGE}.{name}").properties(properties(_, dialect)[name])

    def union(name: str, branches: Any) -> Any:
        """A union of `branches`, each a tag and the schema it names, and the language's error."""
        return lambda _: getattr(_, name).name(f"{LANGUAGE}.{name}").branches([
            *(lambda t, tag=tag, schema=schema: t.name(tag).schema([schema]) for tag, schema in branches(_)),
            lambda t: t.name("error").schema([_.Error])])

    def tags(*names: str) -> Any:
        return lambda _: [(name.lower(), getattr(_, name)) for name in names]

    def named(name: str, element: Any) -> Any:
        """A named container: a list, by index, of `element`."""
        return lambda _: getattr(_, name).name(f"{LANGUAGE}.{name}").index([S.OfInt]).element([element(_)])

    return txn.uid("mbse.Programs.Cpp/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"Language": S.OfObject, "TranslationUnit": S.OfObject, "Error": S.OfObject,
                  "Block": S.OfUnion, "MemberLists": S.OfUnion, "Groups": S.OfUnion,  # mbse-expressions' open unions
                  "TypesTerm": S.OfUnion,  # Cpp Types' `Term`, by name
                  **{name: S.OfContainer for name in CONTAINERS}, **{name: S.OfUnion for name in UNIONS},
                  **{name: S.OfObject for name in KINDS + PARTS}})
        .spec([
            lambda _: _.Language.name(f"{LANGUAGE}.Language").ref(True).singleton(LANGUAGE),
            lambda _: _.TranslationUnit.name(f"{LANGUAGE}.TranslationUnit").ref(True).refines([F.File]).properties({
                "body": _.Body}),
            lambda _: _.Error.name(f"{LANGUAGE}.Error").refines([F.Error]).properties({"body": _.Body}),
            lambda _: _.TypesTerm.name("Expressions.Cpp.Types.Term"),
            # the unions and containers
            union("Statement", tags(*STATEMENTS)),
            union("Member", tags("MemberDeclaration", "FunctionDefinition", "AccessSpecifier", "UsingDeclaration",
                                 "UsingEnumDeclaration", "AliasDeclaration", "StaticAssertDeclaration",
                                 "TemplateDeclaration", "EmptyDeclaration", "Directive", "Comment")),
            union("InitStatement", lambda _: [("simpledeclaration", _.SimpleDeclaration),
                                              ("aliasdeclaration", _.AliasDeclaration), ("expression", T)]),
            union("Condition", lambda _: [("simpledeclaration", _.SimpleDeclaration), ("expression", T)]),
            union("FunctionBody", tags("CompoundStatement", "TryStatement", "DefaultedBody", "DeletedBody")),
            union("Templated", tags("SimpleDeclaration", "FunctionDefinition", "AliasDeclaration", "ConceptDefinition",
                                    "TemplateDeclaration", "MemberDeclaration")),
            named("Body", lambda _: _.Statement), named("Members", lambda _: _.Member),
            named("Declarators", lambda _: _.InitDeclarator), named("MemberDeclarators", lambda _: _.MemberDeclarator),
            named("Specifiers", lambda _: dialect.Specifier),
            named("Attributes", lambda _: dialect.AttributeSpecifier), named("AsmOperands", lambda _: _.AsmOperand),
            named("Terms", lambda _: T), named("Identifiers", lambda _: dialect.Identifier),
            named("Strs", lambda _: S.OfStr), named("Handlers", lambda _: _.Handler),
            named("MemberInitializers", lambda _: _.MemberInitializer),
            named("NamespaceNames", lambda _: _.NamespaceName),
            named("UsingDeclarators", lambda _: _.UsingDeclarator),
            named("TemplateParameters", lambda _: dialect.Cpp.TemplateParameter),
            # mbse-expressions' open unions, given this grammar's compound statement, member list and groups
            lambda _: _.Block.name("Expressions.Cpp.Expressions.Block").branches([
                lambda t: t.name("compoundstatement").schema([_.CompoundStatement])]),
            lambda _: _.MemberLists.name("Expressions.Cpp.Expressions.Members").branches([
                lambda t: t.name("memberlist").schema([_.MemberList])]),
            lambda _: _.Groups.name("Expressions.C.Preprocessor.Group").branches([
                lambda t: t.name("cpp_group").schema([_.Group]),
                lambda t: t.name("cpp_membergroup").schema([_.MemberGroup])]),
            # the kinds and their parts, each with its properties (`properties`)
            *(kind(name) for name in KINDS), *(part(name) for name in PARTS),
        ])]))])
