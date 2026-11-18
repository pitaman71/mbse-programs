"""Standards: the versions of TypeScript 5 the language `Programs.TypeScript5` covers, as data, and the statement kinds
each has.

As the user decided for the port ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../../docs/proposals/port/README.md#decided),
question 4), each language is a singleton by name, owning its statement kinds, "its standards recorded as data, as for
C and C++"; and on which: "Use Typescript 5.0-5.9 to version the typescript5 standards." This records them as
mbse-expressions records its dialects' (mbse-basis [CAP-268: standards as tagged data](mbse:mbse-basis/docs/capabilities/CAP-268.md#decided)):

- `install` extends `Programs.TypeScript5.Language` with the adjacency `standards`, through
  `Expressions.Framework.Covers`, and adds it to the framework's union of dialects, `Expressions.Framework.Dialect`, as
  the branch `programs_typescript5`, which `Covers` links. Run after `Programs.TypeScript5`'s install, in a transaction
  of its own; run again, it writes nothing.
- `define` writes the singleton `Programs.TypeScript5` covering TypeScript 5.0 to 5.9, each by its published name
  (`TypeScript 5.9`), an `Expressions.Framework.Standard` with its body (`com.microsoft`) and its version, and holding
  the statement, clause and member kinds it has (`Expressions.Framework.HasStandard`), each from the version it arrived
  in (`SINCE`). Run after `install`, in a transaction of its own; run again, it writes nothing. Its frame binds the
  language (`language`) and each version by its name spelled as an identifier (`TypeScript_5_9`).
- `prepare(store)` runs, each in a transaction of its own, mbse-expressions' `define`s for `TypeScript5`, `TypeScript
  Types` and `TypeScript Patterns` (which record the expression, type and pattern kinds each version has, and which
  `TypeScript5.store()` does not run), then `install` and `define`; it gives the store back. `Check` reads them.

A kind's availability is then read as mbse-expressions' are (`Expressions.Framework.Standards`): `kinds(standard)`
lists a version's, and a kind is available in a version where some dialect's standard of that name lists it.

Decided by the agent, each *(agent)*:

- **The language owns its own standards**, as each of mbse-expressions' dialects owns its own (`TypeScript Types` and
  `TypeScript Patterns` each own a "TypeScript 5.9", apart from `TypeScript5`'s), rather than tagging statement kinds
  with `Expressions.TypeScript.TypeScript5`'s; so each dialect's data stays its own, and they agree by designation.
- **Schema extension, here, for now**: `Programs.TypeScript5.Language` in `Statements` has no `standards` adjacency and
  is not a branch of `Expressions.Framework.Dialect`, which `Covers` requires of what owns a standard; `install` adds
  both by extension, as Python3's `Standards` does. Folding both into `Statements.install`, and `install`, `define` and
  the expression `define`s into `TypeScript5.INSTALLS`, is a change asked of the model.
- **Statement, clause and member kinds are tagged**, every one in every version: each is older than TypeScript 5.0
  (mbse-programs 0.3's `TypeScript/Syntax.py`, `SINCE`: `accessor` 4.9, a static block 4.4), as mbse-expressions'
  TypeScript family finds of its own. A program (`Programs.TypeScript5.Program`) is in every version, and the parts
  that hold no statement (a declarator, a specifier, a class's body) are parts of the statements that hold them.
- **`TypeScript RegExp` is not read**: it covers editions of ECMA-262, not versions of TypeScript, and the user
  decided that the versions are TypeScript's alone ("no ECMAScript editions").
- **What a property's value makes available stays code** (`Check.FEATURES`, `Check.STATEMENT_FEATURES`): a standard
  tags a kind's schema, not a property or a value of one (`VariableDeclaration.declarationKind 'using'` 5.2,
  `ImportDeclaration.phase 'defer'` 5.9), so mbse-basis CAP-268's data cannot hold them yet.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mbse.Expressions.TypeScript.Patterns import Expressions as TypeScriptPatterns
from mbse.Expressions.TypeScript.TypeScript5 import Expressions as TypeScriptExpressions
from mbse.Expressions.TypeScript.Types import Expressions as TypeScriptTypes

from .Statements import KINDS, LANGUAGE

__all__ = ["install", "define", "prepare", "SINCE", "MINORS", "DIALECTS", "designation"]

SINCE: dict[str, int] = {}
"""The minor version of TypeScript 5 each statement, clause or member kind arrived in, where it is not 5.0, from which
`define` writes the kinds each version has: none, every kind being older than TypeScript 5.0."""

MINORS = range(10)
"""The minor versions of TypeScript 5 the language covers: 5.0 to 5.9."""

DIALECTS = (LANGUAGE, "Expressions.TypeScript.TypeScript5", "Expressions.TypeScript.Types",
            "Expressions.TypeScript.Patterns")
"""The singletons whose standards say which kinds a TypeScript 5 program may hold: the language's own, for its
statements, then mbse-expressions' dialects, for the terms its statements hold."""


def designation(minor: int) -> str:
    """A version's published name, by which each dialect covers it: `TypeScript 5.9`."""
    return f"TypeScript 5.{minor}"


def install(txn: Any) -> Any:
    """`Programs.TypeScript5.Language` given the adjacency `standards` (`Expressions.Framework.Covers`), and made a
    branch of `Expressions.Framework.Dialect`, by schema extension: run after `Programs.TypeScript5`'s install, in a
    transaction of its own; run again, it writes nothing."""
    S, Framework = txn.Schemas, txn.Expressions.Framework
    return txn.uid("mbse.Programs.TypeScript5.Standards/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"Language": S.OfObject, "Dialects": S.OfUnion})
        .spec([
            lambda _: _.Language.name(f"{LANGUAGE}.Language").adjacencies({
                "standards": lambda a: a.relation([Framework.Covers]).me("dialect")}),
            lambda _: _.Dialects.name("Expressions.Framework.Dialect").branches([
                lambda t: t.name("programs_typescript5").schema([_.Language])]),
        ])]))])


def define(txn: Any) -> Any:
    """The versions of TypeScript 5 the singleton `Programs.TypeScript5` covers, by their published names
    (`standards`), 5.0 to 5.9, each with its body, its version and the statement, clause and member kinds it has
    (`SINCE`). Run after `install`, in a transaction of its own; run again, it writes nothing."""
    Language, Standard = txn.Programs.TypeScript5.Language, txn.Expressions.Framework.Standard
    every = {kind: getattr(txn.Programs.TypeScript5, kind).as_schema() for kind in KINDS}

    def version(minor: int) -> Callable[[Any], Any]:
        kinds = [schema for kind, schema in every.items() if SINCE.get(kind, 0) <= minor]
        return lambda _: getattr(_, f"TypeScript_5_{minor}").bodies(["com.microsoft"]).revision(
            lambda r: r.version(f"5.{minor}")).kinds(kinds)

    return txn.uid("mbse.Programs.TypeScript5.define/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"language": Language, **{f"TypeScript_5_{minor}": Standard for minor in MINORS}})
        .spec([
            lambda _: _.language.standards({designation(minor): lambda e, minor=minor: e.standard(
                getattr(_, f"TypeScript_5_{minor}")) for minor in MINORS}),
            *(version(minor) for minor in MINORS),
        ])]))])


def prepare(store: Any) -> Any:
    """`store`, holding `TypeScript5.INSTALLS`, given the data `Check` reads: mbse-expressions' `define`s for
    `TypeScript5`, `TypeScript Types` and `TypeScript Patterns`, then `install` and `define`, each in a transaction of
    its own. Run again, it writes nothing."""
    for each in (TypeScriptExpressions.define, TypeScriptTypes.define, TypeScriptPatterns.define, install, define):
        store.transaction(each)
    return store
