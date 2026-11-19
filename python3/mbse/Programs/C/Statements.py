"""Statements: C's statements, declarations and their parts, C11 to C23, with the GNU extensions mbse-programs 0.3 kept,
as value objects, as the user decided for the port
([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../docs/proposals/port/README.md#stage-3-the-whole-tree-as-values)):
"the whole AST is value objects". A source file, `Programs.C.TranslationUnit`, is a `Programs.Framework.File`, a
reference object the workspace owns by its path, and holds its declarations and statements as one value, its `body`;
each statement and declaration kind refines `Programs.Framework.Statement`.

Kinds follow mbse-programs 0.3's Ccpp (`Ccpp/Syntax.py`), the kinds C has, with its names and its properties in source
order: C's own, as the user decided (stage 4, "2(a)"): "`Programs.C` defines its kinds; `Programs.Cpp` defines only
what C++ adds, its union listing C's kinds and its own". So no name says C (`IfStatement`, not `CIfStatement`), and a
property only C++ has is not here (an `if`'s initializer, a declarator's virt-specifiers). A list of statements is a
`Programs.C.Body`, each element a branch of the union `Programs.C.Statement`, tagged by its kind's name in lower case
(`ifstatement`, `simpledeclaration`, `error`), as mbse-expressions' dialects tag theirs; a property that holds one
statement (`IfStatement.consequence`, `LabeledStatement.statement`) holds a `Statement` itself. Declarations are
statements here, as 0.3 had blocks list them directly: C's grammar mixes them in a block, and a label may precede
either (C23).

A statement's expressions are mbse-expressions' C family's terms, value objects its properties hold: a `C` term
(`Expressions.C.Expressions.Term`) where an expression stands, and `C Types`' helpers where a declaration's parts stand:
its specifiers (`Expressions.C.Types.Specifier`, attribute specifiers among them), its declarators
(`Expressions.C.Types.Declarator`) and its attribute specifiers (`Expressions.C.Types.AttributeSpecifier`); a name is
C's `Identifier` (`Expressions.C.Expressions.Identifier`). Where a term holds statements or declarations, a property of
the term holds them, as the user decided ("the crossover should be modeled as a property of T_A"), each an open union of
mbse-expressions' that `install` extends:

- a GNU statement expression's `block`, of `Expressions.C.Expressions.Block`, extended with
  `Programs.C.CompoundStatement` (`compoundstatement`);
- a struct's or a union's `members`, of `Expressions.C.Types.Members`, extended with `Programs.C.MemberList`
  (`memberlist`), its member declarations;
- a conditional directive's `group`, of `Expressions.C.Preprocessor.Group`, the lines it governs, as the user decided
  for directives (stage 4, "3(a)": "a preprocessor directive between statements is a statement holding the directive
  term, and a conditional's statements a property of that term"): extended with `Programs.C.Group` (`group`), its
  statements and declarations, and `Programs.C.MemberGroup` (`membergroup`), its member declarations, where it stands
  among a struct's members *(agent: two branches, as a struct's members are no statements)*.

Parts of the grammar:

- **Clauses**: none. C's grammar has no part of a statement that only that statement holds and that holds
  statements: a `case` or `default` label is a labeled statement, which may stand anywhere within a `switch`'s body
  (Duff's device), so it is a statement, `CaseStatement` and `DefaultStatement`, as 0.3 had them *(agent)*.
- **Member declarations**, the elements of a `MemberList` (`Programs.C.Members`, of the union `Programs.C.Member`): a
  `MemberDeclaration`, its specifiers and its `MemberDeclarator`s (a declarator and a bit-field's width, either
  absent where the other is not: `int : 3`), a `StaticAssertDeclaration`, a `Directive`, a `Comment` and an `Error`, in
  source order, each with its line.
- **Directives** are statements (`Directive`, its `directive` the `C Preprocessor` term), as the user decided ("3(a)"),
  where statements and member declarations are listed; among an enumeration's enumerators they are `C Types`' own, as
  the dialect has them.
- **Parts that hold no statement**, value objects of what holds them: a declaration's `InitDeclarator`s (a declarator
  and what initializes it after `=`, a `C` term: C has no other initializer *(agent)*), a member declaration's
  `MemberDeclarator`s, an `asm` statement's `AsmOperand`s, and the `MemberList`, `Group` and `MemberGroup` above.
- **Where a grammar position takes either of two**, a union of them: a `for`'s `initializer`
  (`Programs.C.ForInit`: a `simpledeclaration`, or a term, `expression`) *(agent)*.
- **GNU's extensions** 0.3 kept: `AsmDeclaration` (`asm volatile goto (template : outputs : inputs : clobbers :
  labels)`, named as 0.3 named it, a statement within a function as at file scope), a `case` range
  (`CaseStatement.last`, `case 1 ... 3:`), and a computed `goto` (`GotoStatement.target`, `goto *p;`) *(agent: 0.3 had
  no computed `goto`)*.
- **Comments** are statements (`Comment`, its `text` without its delimiters, `block` where written `/* */`, `trailing`
  where it ends the line of what is before it), where statements and member declarations are listed; among an
  enumeration's enumerators they are `C Preprocessor`'s `comment` terms; elsewhere they are dropped, as 0.3 dropped
  them.
- **Invalid syntax** is `Programs.C.Error`, refining `Programs.Framework.Error`: its `text` as written, and the
  statements recovered within it, its `body`. It may stand wherever a statement or a member declaration may, a branch
  `error` of each union *(agent)*.

Each statement and member declaration has the line it begins on (`line`), absent where it was built rather than
parsed. Run `install` after `Programs.Framework.Model.install` and mbse-expressions' `C`, `C Types` and `C Preprocessor`
installs, each in a transaction of its own; run again, it writes nothing.
"""

from typing import Any

LANGUAGE = "Programs.C"

STATEMENTS = (
    "Comment", "Directive", "ExpressionStatement", "CompoundStatement", "IfStatement", "SwitchStatement",
    "WhileStatement", "DoStatement", "ForStatement", "BreakStatement", "ContinueStatement", "ReturnStatement",
    "GotoStatement", "LabeledStatement", "CaseStatement", "DefaultStatement", "AttributedStatement", "AsmDeclaration",
    "SimpleDeclaration", "FunctionDefinition", "StaticAssertDeclaration", "AttributeDeclaration")
CLAUSES: tuple[str, ...] = ()
MEMBERS = ("MemberDeclaration",)
PARTS = ("InitDeclarator", "MemberDeclarator", "MemberList", "Group", "MemberGroup", "AsmOperand")
KINDS = STATEMENTS + CLAUSES + MEMBERS
UNIONS = ("Statement", "Member", "ForInit")
CONTAINERS = ("Body", "Members", "Declarators", "MemberDeclarators", "Declarations", "Specifiers", "Attributes",
              "AsmOperands", "Terms", "Identifiers")


def properties(_: Any, dialect: Any) -> dict[str, dict[str, Any]]:
    """Each of C's statement, declaration, member and part kinds' own properties, in source order, given the spec's
    symbols and the schemas its expressions are of (`dialect`'s `S`, `Term`, `Identifier`, `Specifier`, `Declarator`,
    `AttributeSpecifier` and `Directive`): the table `install` defines C's kinds by, and `Programs.Cpp` the kinds it
    reuses by, over C++'s terms, as the user decided (stage 4, "2(a)") *(a hook `Programs.Cpp` reads)*."""
    S, T, Identifier = dialect.S, dialect.Term, dialect.Identifier
    declaration = {"attributes": _.Attributes, "specifiers": _.Specifiers}  # what a declaration's are
    labeled = {"statement": _.Statement}  # a label's statement, absent where the label ends a block (C23)
    return {
        # comments and directives
        "Comment": {"text": S.OfStr, "block": S.OfBool, "trailing": S.OfBool},
        "Directive": {"directive": dialect.Directive},
        "Group": {"body": _.Body},
        "MemberGroup": {"members": _.Members},
        # statements
        "ExpressionStatement": {"expression": T},
        "CompoundStatement": {"body": _.Body},
        "IfStatement": {"condition": T, "consequence": _.Statement, "alternative": _.Statement},
        "SwitchStatement": {"condition": T, "body": _.Statement},
        "WhileStatement": {"condition": T, "body": _.Statement},
        "DoStatement": {"body": _.Statement, "condition": T},
        "ForStatement": {"initializer": _.ForInit, "condition": T, "increment": T, "body": _.Statement},
        "BreakStatement": {}, "ContinueStatement": {},
        "ReturnStatement": {"value": T},
        "GotoStatement": {"label": Identifier, "target": T},  # target: GNU's `goto *p;`
        "LabeledStatement": {"label": Identifier, **labeled},
        "CaseStatement": {"value": T, "last": T, **labeled},  # last: GNU's `case 1 ... 3:`
        "DefaultStatement": labeled,
        "AttributedStatement": {"attributes": _.Attributes, "statement": _.Statement},
        "AsmDeclaration": {
            "keyword": S.OfStr, "volatile": S.OfBool, "inline": S.OfBool, "goto": S.OfBool, "template": T,
            "outputs": _.AsmOperands, "inputs": _.AsmOperands, "clobbers": _.Terms, "labels": _.Identifiers},
        "AsmOperand": {"name": Identifier, "constraint": T, "value": T},
        # declarations
        "SimpleDeclaration": {**declaration, "declarators": _.Declarators},
        "InitDeclarator": {"declarator": dialect.Declarator, "initializer": T},
        "FunctionDefinition": {
            **declaration, "declarator": dialect.Declarator,
            "declarations": _.Declarations,  # a K&R definition's parameters' declarations
            "body": _.CompoundStatement},
        "StaticAssertDeclaration": {"keyword": S.OfStr, "condition": T, "message": T},
        "AttributeDeclaration": {"attributes": _.Attributes},
        # a struct's or a union's members
        "MemberList": {"members": _.Members},
        "MemberDeclaration": {**declaration, "declarators": _.MemberDeclarators},
        "MemberDeclarator": {"declarator": dialect.Declarator, "bitfield": T},
    }


class _Dialect:
    """The schemas C's statements hold expressions of, as `properties` reads them: C's, C Types' and C Preprocessor's."""

    def __init__(self, txn: Any):
        C, Types = txn.Expressions.C.Expressions, txn.Expressions.C.Types
        self.S, self.Term, self.Identifier, self.Directive = txn.Schemas, C.Term, C.Identifier, (
            txn.Expressions.C.Preprocessor.Term)
        self.Specifier, self.Declarator, self.AttributeSpecifier = (
            Types.Specifier, Types.Declarator, Types.AttributeSpecifier)


def install(txn: Any) -> Any:
    """C's statement and declaration kinds, their parts, its translation unit and its language's singleton, upserted,
    and its compound statement, member list and groups added to mbse-expressions' open unions."""
    S, F = txn.Schemas, txn.Programs.Framework
    dialect = _Dialect(txn)
    T, Identifier = dialect.Term, dialect.Identifier

    def kind(name: str) -> Any:
        """A statement or member kind: a value object refining `Statement` (a member, nothing), with its own
        properties (`properties`), made within its spec, given the spec's symbols, and its line."""
        base = [F.Statement] if name in STATEMENTS else []
        line = {} if base else {"line": S.OfInt}
        return lambda _: getattr(_, name).name(f"{LANGUAGE}.{name}").refines(base).properties(
            {**line, **properties(_, dialect)[name]})

    def part(name: str) -> Any:
        return lambda _: getattr(_, name).name(f"{LANGUAGE}.{name}").properties(properties(_, dialect)[name])

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

    return txn.uid("mbse.Programs.C/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"Language": S.OfObject, "TranslationUnit": S.OfObject, "Error": S.OfObject,
                  "Block": S.OfUnion, "MemberLists": S.OfUnion, "Groups": S.OfUnion,  # mbse-expressions' open unions
                  **{name: S.OfContainer for name in CONTAINERS}, **{name: S.OfUnion for name in UNIONS},
                  **{name: S.OfObject for name in KINDS + PARTS}})
        .spec([
            lambda _: _.Language.name(f"{LANGUAGE}.Language").ref(True).singleton(LANGUAGE),
            lambda _: _.TranslationUnit.name(f"{LANGUAGE}.TranslationUnit").ref(True).refines([F.File]).properties({
                "body": _.Body}),
            lambda _: _.Error.name(f"{LANGUAGE}.Error").refines([F.Error]).properties({"body": _.Body}),
            # the unions and containers
            union("Statement", tags(*STATEMENTS)),
            union("Member", tags("MemberDeclaration", "StaticAssertDeclaration", "Directive", "Comment")),
            union("ForInit", lambda _: [("simpledeclaration", _.SimpleDeclaration), ("expression", T)]),
            named("Body", lambda _: _.Statement), named("Members", lambda _: _.Member),
            named("Declarators", lambda _: _.InitDeclarator), named("MemberDeclarators", lambda _: _.MemberDeclarator),
            named("Declarations", lambda _: _.SimpleDeclaration), named("Specifiers", lambda _: dialect.Specifier),
            named("Attributes", lambda _: dialect.AttributeSpecifier), named("AsmOperands", lambda _: _.AsmOperand),
            named("Terms", lambda _: T), named("Identifiers", lambda _: Identifier),
            # mbse-expressions' open unions, given this grammar's compound statement, member list and groups
            lambda _: _.Block.name("Expressions.C.Expressions.Block").branches([
                lambda t: t.name("compoundstatement").schema([_.CompoundStatement])]),
            lambda _: _.MemberLists.name("Expressions.C.Types.Members").branches([
                lambda t: t.name("memberlist").schema([_.MemberList])]),
            lambda _: _.Groups.name("Expressions.C.Preprocessor.Group").branches([
                lambda t: t.name("group").schema([_.Group]), lambda t: t.name("membergroup").schema([_.MemberGroup])]),
            # the kinds and their parts, each with its properties (`properties`)
            *(kind(name) for name in KINDS), *(part(name) for name in PARTS),
        ])]))])
