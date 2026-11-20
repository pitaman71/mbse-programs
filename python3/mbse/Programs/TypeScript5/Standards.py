"""Standards: the versions of TypeScript 5 the language `Programs.TypeScript5` covers, as data, the statement kinds
each has, and its statements' grammar clauses, which each allows or forbids.

As the user decided for the port ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../../docs/proposals/port/README.md#decided),
question 4), each language is a singleton by name, owning its statement kinds, "its standards recorded as data, as for
C and C++"; and on which: "Use Typescript 5.0-5.9 to version the typescript5 standards." This records them as
mbse-expressions records its dialects' (mbse-basis [CAP-268: standards as tagged data](mbse:mbse-basis/docs/capabilities/CAP-268.md#decided)),
and what changes from one version to the next within a kind as grammar clauses (mbse-basis [grammar clauses by
version](mbse:mbse-basis/proposals/GRAMMAR-CLAUSES.md)):

- `install` extends `Programs.TypeScript5.Language` with the adjacencies `standards`, through
  `Expressions.Framework.Covers`, and `grammar_clauses`, through `Expressions.Framework.Specifies`, and adds it to the
  framework's union of dialects, `Expressions.Framework.Dialect`, as the branch `programs_typescript5`, which both
  relations link. Run after `Programs.TypeScript5`'s install, in a transaction of its own; run again, it writes nothing.
- `define` writes the singleton `Programs.TypeScript5` covering TypeScript 5.0 to 5.9, each by its published name
  (`TypeScript 5.9`), an `Expressions.Framework.Standard` with its body (`com.microsoft`) and its version, and holding
  the statement, clause and member kinds it has (`Expressions.Framework.HasStandard`), by membership (`ONLY`); and
  owning its grammar clauses by name (`GRAMMAR_CLAUSES`), each allowed or forbidden by each version, written by
  mbse-expressions' writer (`Framework.Standards.grammar_clauses_spec`). Run after `install`, in a transaction of its
  own; run again, it writes nothing. Its frame binds the language (`dialect`, as that writer names it), each version
  by its name spelled as an identifier (`TypeScript_5_9`) and each grammar clause by its index (`grammar_clause_0`).
- `prepare(store)` runs, each in a transaction of its own, mbse-expressions' `define`s for `TypeScript5`, `TypeScript
  Types` and `TypeScript Patterns` (which record the expression, type and pattern kinds each version has, and their
  terms' grammar clauses, and which `TypeScript5.store()` does not run), then `install` and `define`; it gives the
  store back. `Check` reads them.

A kind's availability is then read as mbse-expressions' are (`Expressions.Framework.Standards`): `kinds(standard)`
lists a version's, and a kind is available in a version where some dialect's standard of that name lists it; a grammar
clause, where `allows(standard, clause)` says so.

The grammar clauses, each named as `Check` reports it, as the 0.3 language had them within TypeScript 5
(`TypeScript/Syntax.py`, `FEATURES`): `VariableDeclaration.declarationKind`'s `'using'` and `'await using'` (5.2),
`ImportDeclaration`'s, `ExportNamedDeclaration`'s and `ExportAllDeclaration`'s `attributes` (5.3), and
`ImportDeclaration.phase 'defer'` (5.9); and, beyond 0.3's data, a module's name as a string,
`ImportSpecifier.imported`, `ExportSpecifier.local` and `.exported` and `ExportAllDeclaration.exported` holding a
`literal` (`import { "a-b" as x }`, `export { x as "a-b" }`, `export * as "a-b" from`), which TypeScript 5.6 accepts
*(agent)*.

Decided by the agent, each *(agent)*:

- **The language owns its own standards and grammar clauses**, as each of mbse-expressions' dialects owns its own
  (`TypeScript Types` and `TypeScript Patterns` each own a "TypeScript 5.9", apart from `TypeScript5`'s), rather than
  tagging statement kinds with `Expressions.TypeScript.TypeScript5`'s; so each dialect's data stays its own, and they
  agree by designation.
- **Schema extension, here, for now**: `Programs.TypeScript5.Language` in `Statements` has neither adjacency and is
  not a branch of `Expressions.Framework.Dialect`, which `Covers` and `Specifies` require of what owns a standard or a
  grammar clause; `install` adds them by extension, as Python3's `Standards` does. Folding them into
  `Statements.install`, and `install`, `define` and the expression `define`s into `TypeScript5.INSTALLS`, is a change
  asked of the model.
- **Statement, clause and member kinds are tagged**, every one in every version: each is older than TypeScript 5.0
  (mbse-programs 0.3's `TypeScript/Syntax.py`: `accessor` 4.9, a static block 4.4), as mbse-expressions' TypeScript
  family finds of its own. So `ONLY` is empty, kept so that the membership is read as Python3's is. A program
  (`Programs.TypeScript5.Program`) is in every version, and the parts that hold no statement (a declarator, a
  specifier, a class's body) are parts of the statements that hold them; a part's grammar clauses are the language's
  (`ImportSpecifier.imported as a string`).
- **`TypeScript RegExp` is not read**: it covers editions of ECMA-262, not versions of TypeScript, and the user
  decided that the versions are TypeScript's alone ("no ECMAScript editions").
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mbse.Expressions.Framework import Standards as FS
from mbse.Expressions.TypeScript.Patterns import Expressions as TypeScriptPatterns
from mbse.Expressions.TypeScript.TypeScript5 import Expressions as TypeScriptExpressions
from mbse.Expressions.TypeScript.Types import Expressions as TypeScriptTypes

from .Statements import KINDS, LANGUAGE, PARTS

__all__ = ["install", "define", "prepare", "ONLY", "GRAMMAR_CLAUSES", "MINORS", "VERSIONS", "DIALECTS", "designation"]

MINORS = range(10)
"""The minor versions of TypeScript 5 the language covers: 5.0 to 5.9."""

VERSIONS = tuple(f"TypeScript_5_{minor}" for minor in MINORS)
"""The versions of TypeScript 5 it covers, oldest first, each by its name spelled as an identifier, as `define`'s frame
binds it (`TypeScript_5_9`)."""

ONLY: dict[str, tuple[str, ...]] = {}
"""The statement, clause and member kinds that are not in every version, each with the versions that have it, from
which `define` writes the kinds each version has: none, every kind being older than TypeScript 5.0."""

GRAMMAR_CLAUSES = (
    *(FS.values(f"VariableDeclaration.declarationKind {word!r}", "VariableDeclaration", "declarationKind", (word,),
                VERSIONS[2:]) for word in ("using", "await using")),
    *(FS.present(f"{kind}.attributes", kind, "attributes", VERSIONS[3:])
      for kind in ("ImportDeclaration", "ExportNamedDeclaration", "ExportAllDeclaration")),
    FS.values("ImportDeclaration.phase 'defer'", "ImportDeclaration", "phase", ("defer",), VERSIONS[9:]),
    *(FS.kinds_of(f"{kind}.{name} as a string", kind, name, ("literal",), (), VERSIONS[6:])
      for kind, name in (("ImportSpecifier", "imported"), ("ExportSpecifier", "local"), ("ExportSpecifier", "exported"),
                         ("ExportAllDeclaration", "exported"))),
)
"""Its statements' and parts' grammar clauses, each with the versions that allow it, every other forbidding it, named
as `Check` reports them: what a property's value makes available within a kind, keyed by its kind's name, a term's
kind by its tag in `TypeScript5` (`literal`)."""

DIALECTS = (LANGUAGE, "Expressions.TypeScript.TypeScript5", "Expressions.TypeScript.Types",
            "Expressions.TypeScript.Patterns")
"""The singletons whose standards say which kinds and grammar clauses a TypeScript 5 program may hold: the language's
own, for its statements, then mbse-expressions' dialects, for the terms its statements hold."""


def designation(minor: int) -> str:
    """A version's published name, by which each dialect covers it: `TypeScript 5.9`."""
    return f"TypeScript 5.{minor}"


def install(txn: Any) -> Any:
    """`Programs.TypeScript5.Language` given the adjacencies `standards` (`Expressions.Framework.Covers`) and
    `grammar_clauses` (`Expressions.Framework.Specifies`), and made a branch of `Expressions.Framework.Dialect`, by
    schema extension: run after `Programs.TypeScript5`'s install, in a transaction of its own; run again, it writes
    nothing."""
    S, Framework = txn.Schemas, txn.Expressions.Framework
    return txn.uid("mbse.Programs.TypeScript5.Standards/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"Language": S.OfObject, "Dialects": S.OfUnion})
        .spec([
            lambda _: _.Language.name(f"{LANGUAGE}.Language").adjacencies({
                "standards": lambda a: a.relation([Framework.Covers]).me("dialect"),
                "grammar_clauses": lambda a: a.relation([Framework.Specifies]).me("dialect")}),
            lambda _: _.Dialects.name("Expressions.Framework.Dialect").branches([
                lambda t: t.name("programs_typescript5").schema([_.Language])]),
        ])]))])


def define(txn: Any) -> Any:
    """The versions of TypeScript 5 the singleton `Programs.TypeScript5` covers, by their published names
    (`standards`), 5.0 to 5.9, each with its body, its version and the statement, clause and member kinds it has
    (`ONLY`), and its grammar clauses by name (`grammar_clauses`), each allowed or forbidden by each version
    (`GRAMMAR_CLAUSES`). Run after `install`, in a transaction of its own; run again, it writes nothing."""
    Language, Standard = txn.Programs.TypeScript5.Language, txn.Expressions.Framework.Standard
    every = {kind: getattr(txn.Programs.TypeScript5, kind).as_schema() for kind in KINDS}
    parts = {kind: getattr(txn.Programs.TypeScript5, kind).as_schema() for kind in PARTS}
    terms = {branch.name: branch.schema for branch in txn.Expressions.TypeScript.TypeScript5.Term.as_schema().branches}
    clauses, specs = FS.grammar_clauses_spec(txn, GRAMMAR_CLAUSES, {**every, **parts, **terms}, [VERSIONS])

    def version(minor: int) -> Callable[[Any], Any]:
        kinds = [schema for kind, schema in every.items() if VERSIONS[minor] in ONLY.get(kind, VERSIONS)]
        return lambda _: getattr(_, VERSIONS[minor]).bodies(["com.microsoft"]).revision(
            lambda r: r.version(f"5.{minor}")).kinds(kinds)

    return txn.uid("mbse.Programs.TypeScript5.define/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"dialect": Language, **dict.fromkeys(VERSIONS, Standard), **clauses})
        .spec([
            lambda _: _.dialect.standards({designation(minor): lambda e, minor=minor: e.standard(
                getattr(_, VERSIONS[minor])) for minor in MINORS}),
            *(version(minor) for minor in MINORS),
            # its statements' and parts' grammar clauses, each allowed or forbidden by each version
            *specs,
        ])]))])


def prepare(store: Any) -> Any:
    """`store`, holding `TypeScript5.INSTALLS`, given the data `Check` reads: mbse-expressions' `define`s for
    `TypeScript5`, `TypeScript Types` and `TypeScript Patterns`, then `install` and `define`, each in a transaction of
    its own. Run again, it writes nothing."""
    for each in (TypeScriptExpressions.define, TypeScriptTypes.define, TypeScriptPatterns.define, install, define):
        store.transaction(each)
    return store
