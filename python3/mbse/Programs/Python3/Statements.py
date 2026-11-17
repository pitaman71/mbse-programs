"""Statements: Python 3's statement kinds, through 3.15, as value objects, as the user decided for the port
([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../docs/proposals/port/README.md#stage-3-the-whole-tree-as-values)):
"the whole AST is value objects". A module, `Programs.Python3.Module`, is a `Programs.Framework.File`, a reference
object the workspace owns by its path, and holds its statements as one value, its `body`; each statement kind refines
`Programs.Framework.Statement`, and holds the statements of its blocks as its properties (`body`, `orelse`,
`finalbody`), its clauses too (`handlers`, `cases`). A list of statements is a `Programs.Python3.Body`, each element a
branch of the union `Programs.Python3.Statement`, tagged by its kind's name in lower case (`if`, `functiondef`,
`error`) *(agent, as mbse-expressions' dialects tag their kinds)*.

A statement's expressions are mbse-expressions' terms, value objects its properties hold: a `Python3` term
(`Expressions.Python.Python3.Term`) where `ast` holds an expression; a `Python Types` term
(`Expressions.Python.Types.Term`) for an annotation, a return type, a type alias' value and a type parameter; a
`Python Patterns` term (`Expressions.Python.Patterns.Term`) for a case's pattern; and the `Python3` dialect's own
helpers for a function's parameters (`Arguments`) and a class's keywords (`Keyword`). A name a statement declares is a
string, as `ast` has it (`FunctionDef.name`, `Global.names`, `alias.name`), but a type alias' name, which `ast` makes a
`Name`, is a term. An `except` clause and a `case` are clauses, refining `Programs.Framework.Clause`, never statements,
as the user decided: a `try`'s `handlers` hold `Programs.Python3.Handler`s (an `ExceptHandler`), a `match`'s `cases`
`Programs.Python3.Case`s (a `MatchCase`). An import's aliases and a `with` statement's items are value objects. A
comment is a statement, `trailing` where it ends the line of the statement before it.

Invalid syntax is `Programs.Python3.Error`, refining `Programs.Framework.Error`: its `text` as written, and the
statements recovered within it, its `body`. It may stand wherever a statement or a clause may, a branch `error` of
each union *(agent)*.

Kinds follow `ast`'s names and properties, without `ctx`, `type_comment` and positions but for the line a statement
begins on (`line`, `Programs.Framework.Statement`'s); where a property is absent, it is absent (`Return.value`). Run
`install` after `Programs.Framework.Model.install` and mbse-expressions' `Python3`, `Python Types` and `Python Patterns`
installs, each in a transaction of its own; run again, it writes nothing.
"""

from typing import Any

LANGUAGE = "Programs.Python3"

STATEMENTS = ("Comment", "Expr", "Assign", "AugAssign", "AnnAssign", "Assert", "Pass", "Delete", "Return", "Raise",
              "Break", "Continue", "Import", "ImportFrom", "Global", "Nonlocal", "TypeAlias", "If", "While", "For",
              "AsyncFor", "Try", "TryStar", "With", "AsyncWith", "Match", "FunctionDef", "AsyncFunctionDef",
              "ClassDef")
CLAUSES = ("ExceptHandler", "MatchCase")
KINDS = STATEMENTS + CLAUSES
CONTAINERS = ("Terms", "TypeTerms", "Names", "Aliases", "WithItems", "Keywords", "Body", "Handlers", "Cases")
UNIONS = ("Statement", "Handler", "Case")


def install(txn: Any) -> Any:
    """Python 3's statement kinds, its module and its language's singleton, upserted."""
    S, F, E = txn.Schemas, txn.Programs.Framework, txn.Expressions.Python
    T, Ty, Pt = E.Python3.Term, E.Types.Term, E.Patterns.Term

    def kind(name: str, properties: Any = lambda _: {}) -> Any:
        """A statement or clause kind: a value object refining `Statement` or `Clause`, with its own properties,
        made within its spec, given the spec's symbols, so that each container is the kind's own."""
        base = F.Clause if name in CLAUSES else F.Statement
        return lambda _: getattr(_, name).name(f"{LANGUAGE}.{name}").refines([base]).properties(properties(_))

    def union(name: str, kinds: tuple[str, ...]) -> Any:
        """A union of kinds, each tagged by its name in lower case, and the language's error."""
        return lambda _: getattr(_, name).name(f"{LANGUAGE}.{name}").branches([
            *(lambda t, kind=kind: t.name(kind.lower()).schema([getattr(_, kind)]) for kind in kinds),
            lambda t: t.name("error").schema([_.Error])])

    def function(_: Any) -> dict[str, Any]:
        """A function's properties, async or not."""
        return {"decorator_list": _.Terms, "name": S.OfStr, "type_params": _.TypeTerms, "args": E.Python3.Arguments,
                "returns": Ty, "body": _.Body}

    def block(_: Any) -> dict[str, Any]:
        """A `try`'s properties, with `*` or without."""
        return {"body": _.Body, "handlers": _.Handlers, "orelse": _.Body, "finalbody": _.Body}

    def named(name: str, element: Any) -> Any:
        """A named container: a list, by index, of `element`."""
        return lambda _: getattr(_, name).name(f"{LANGUAGE}.{name}").index([S.OfInt]).element([element(_)])

    return txn.uid("mbse.Programs.Python3/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"Language": S.OfObject, "Module": S.OfObject, "Alias": S.OfObject, "WithItem": S.OfObject,
                  "Error": S.OfObject, **{name: S.OfContainer for name in CONTAINERS},
                  **{name: S.OfUnion for name in UNIONS}, **{name: S.OfObject for name in KINDS}})
        .spec([
            lambda _: _.Language.name(f"{LANGUAGE}.Language").ref(True).singleton(LANGUAGE),
            lambda _: _.Module.name(f"{LANGUAGE}.Module").ref(True).refines([F.File]).properties({"body": _.Body}),
            lambda _: _.Error.name(f"{LANGUAGE}.Error").refines([F.Error]).properties({"body": _.Body}),
            union("Statement", STATEMENTS), union("Handler", ("ExceptHandler",)), union("Case", ("MatchCase",)),
            named("Body", lambda _: _.Statement), named("Handlers", lambda _: _.Handler),
            named("Cases", lambda _: _.Case),
            lambda _: _.Alias.name(f"{LANGUAGE}.Alias").properties({"name": S.OfStr, "asname": S.OfStr}),
            lambda _: _.WithItem.name(f"{LANGUAGE}.WithItem").properties({"context_expr": T, "optional_vars": T}),
            named("Terms", lambda _: T), named("TypeTerms", lambda _: Ty), named("Names", lambda _: S.OfStr),
            named("Aliases", lambda _: _.Alias), named("WithItems", lambda _: _.WithItem),
            named("Keywords", lambda _: E.Python3.Keyword),
            kind("Comment", lambda _: {"text": S.OfStr, "trailing": S.OfBool}),
            kind("Expr", lambda _: {"value": T}),
            kind("Assign", lambda _: {"targets": _.Terms, "value": T}),
            kind("AugAssign", lambda _: {"target": T, "op": S.OfStr, "value": T}),
            kind("AnnAssign", lambda _: {"target": T, "annotation": Ty, "value": T}),
            kind("Assert", lambda _: {"test": T, "msg": T}),
            kind("Pass"), kind("Break"), kind("Continue"),
            kind("Delete", lambda _: {"targets": _.Terms}),
            kind("Return", lambda _: {"value": T}),
            kind("Raise", lambda _: {"exc": T, "cause": T}),
            kind("Import", lambda _: {"is_lazy": S.OfBool, "names": _.Aliases}),
            kind("ImportFrom", lambda _: {"is_lazy": S.OfBool, "level": S.OfInt, "module": S.OfStr,
                                          "names": _.Aliases}),
            kind("Global", lambda _: {"names": _.Names}),
            kind("Nonlocal", lambda _: {"names": _.Names}),
            kind("TypeAlias", lambda _: {"name": T, "type_params": _.TypeTerms, "value": Ty}),
            kind("If", lambda _: {"test": T, "body": _.Body, "orelse": _.Body}),
            kind("While", lambda _: {"test": T, "body": _.Body, "orelse": _.Body}),
            kind("For", lambda _: {"target": T, "iter": T, "body": _.Body, "orelse": _.Body}),
            kind("AsyncFor", lambda _: {"target": T, "iter": T, "body": _.Body, "orelse": _.Body}),
            kind("Try", block), kind("TryStar", block),
            kind("ExceptHandler", lambda _: {"type": T, "name": S.OfStr, "body": _.Body}),
            kind("With", lambda _: {"items": _.WithItems, "body": _.Body}),
            kind("AsyncWith", lambda _: {"items": _.WithItems, "body": _.Body}),
            kind("Match", lambda _: {"subject": T, "cases": _.Cases}),
            kind("MatchCase", lambda _: {"pattern": Pt, "guard": T, "body": _.Body}),
            kind("FunctionDef", function),
            kind("AsyncFunctionDef", function),
            kind("ClassDef", lambda _: {"decorator_list": _.Terms, "name": S.OfStr, "type_params": _.TypeTerms,
                                        "bases": _.Terms, "keywords": _.Keywords, "body": _.Body}),
        ])]))])
