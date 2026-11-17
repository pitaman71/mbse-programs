"""Standards: the versions of Python 3 the language `Programs.Python3` covers, as data, and the statement kinds each has.

As the user decided for the port ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../../docs/proposals/port/README.md#decided),
question 4), each language is a singleton by name, owning its statement kinds, "its standards recorded as data, as for
C and C++"; and a language "must correctly handle the closure of syntaxes across minor versions such as 3.11 - 3.14".
This records them as mbse-expressions records its dialects' (mbse-basis [CAP-268: standards as tagged data](mbse:mbse-basis/docs/capabilities/CAP-268.md#decided)):

- `install` extends `Programs.Python3.Language` with the adjacency `standards`, through
  `Expressions.Framework.Covers`, and adds it to the framework's union of dialects, `Expressions.Framework.Dialect`, as
  the branch `programs_python3`, which `Covers` links. Run after `Programs.Python3`'s install, in a transaction of its
  own; run again, it writes nothing.
- `define` writes the singleton `Programs.Python3` covering Python 3.0 to 3.15, each by its published name
  (`Python 3.12`), an `Expressions.Framework.Standard` with its body (`org.python`) and its version, and holding the
  statement and clause kinds it has (`Expressions.Framework.HasStandard`), each from the version it arrived in
  (`SINCE`). Run after `install`, in a transaction of its own; run again, it writes nothing. Its frame binds the
  language (`language`) and each version by its name spelled as an identifier (`Python_3_12`).
- `prepare(store)` runs, each in a transaction of its own, mbse-expressions' `define`s for `Python3`, `Python Types`
  and `Python Patterns` (which record the expression, type and pattern kinds each version has, and which
  `Python3.store()` does not run), then `install` and `define`; it gives the store back. `Check` reads them.

A kind's availability is then read as mbse-expressions' are (`Expressions.Framework.Standards`): `kinds(standard)`
lists a version's, and a kind is available in a version where some dialect's standard of that name lists it.

Decided by the agent, each *(agent)*:

- **The language owns its own standards**, as each of mbse-expressions' dialects owns its own (`Python Types` and
  `Python Patterns` each own a "Python 3.12", apart from `Python3`'s), rather than tagging statement kinds with
  `Expressions.Python.Python3`'s; so each dialect's data stays its own, and they agree by designation.
- **Schema extension, here, for now**: `Programs.Python3.Language` in `Statements` has no `standards` adjacency and is
  not a branch of `Expressions.Framework.Dialect`, which `Covers` requires of what owns a standard; `install` adds both
  by extension, as mbse-expressions' dialects add theirs. Folding both into `Statements.install`, and `install`,
  `define` and the expression `define`s into `Python3.INSTALLS` (so that `Python3.store()` holds them), is a change
  asked of the model.
- **Only statement and clause kinds are tagged**: a module (`Programs.Python3.Module`) is in every version, and the
  value objects (`Alias`, `WithItem`) and named containers are parts of the statements that hold them.
- **What a property's value makes available stays code** (`Check.FEATURES`): a standard tags a kind's schema, not a
  property or a value of one (`Import.is_lazy` 3.15, `FunctionDef.type_params` 3.12, `binop`'s `@` 3.5), so mbse-basis
  CAP-268's data cannot hold them yet.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mbse.Expressions.Python.Patterns import Expressions as PythonPatterns
from mbse.Expressions.Python.Python3 import Expressions as PythonExpressions
from mbse.Expressions.Python.Types import Expressions as PythonTypes

from .Statements import KINDS, LANGUAGE

__all__ = ["install", "define", "prepare", "SINCE", "MINORS", "DIALECTS", "designation"]

SINCE = {"AsyncFor": 5, "AsyncWith": 5, "AsyncFunctionDef": 5, "AnnAssign": 6, "Match": 10, "MatchCase": 10,
         "TryStar": 11, "TypeAlias": 12}
"""The minor version of Python 3 each statement or clause kind arrived in, where it is not 3.0, from which `define`
writes the kinds each version has."""

MINORS = range(16)
"""The minor versions of Python 3 the language covers: 3.0 to 3.15."""

DIALECTS = (LANGUAGE, "Expressions.Python.Python3", "Expressions.Python.Types", "Expressions.Python.Patterns")
"""The singletons whose standards say which kinds a Python 3 module may hold: the language's own, for its statements,
then mbse-expressions' dialects, for the terms its statements hold."""


def designation(minor: int) -> str:
    """A version's published name, by which each dialect covers it: `Python 3.12`."""
    return f"Python 3.{minor}"


def install(txn: Any) -> Any:
    """`Programs.Python3.Language` given the adjacency `standards` (`Expressions.Framework.Covers`), and made a branch
    of `Expressions.Framework.Dialect`, by schema extension: run after `Programs.Python3`'s install, in a transaction of
    its own; run again, it writes nothing."""
    S, Framework = txn.Schemas, txn.Expressions.Framework
    return txn.uid("mbse.Programs.Python3.Standards/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"Language": S.OfObject, "Dialects": S.OfUnion})
        .spec([
            lambda _: _.Language.name(f"{LANGUAGE}.Language").adjacencies({
                "standards": lambda a: a.relation([Framework.Covers]).me("dialect")}),
            lambda _: _.Dialects.name("Expressions.Framework.Dialect").branches([
                lambda t: t.name("programs_python3").schema([_.Language])]),
        ])]))])


def define(txn: Any) -> Any:
    """The versions of Python 3 the singleton `Programs.Python3` covers, by their published names (`standards`), 3.0
    to 3.15, each with its body, its version and the statement and clause kinds it has (`SINCE`). Run after `install`,
    in a transaction of its own; run again, it writes nothing."""
    Language, Standard = txn.Programs.Python3.Language, txn.Expressions.Framework.Standard
    every = {kind: getattr(txn.Programs.Python3, kind).as_schema() for kind in KINDS}

    def version(minor: int) -> Callable[[Any], Any]:
        kinds = [schema for kind, schema in every.items() if SINCE.get(kind, 0) <= minor]
        return lambda _: getattr(_, f"Python_3_{minor}").bodies(["org.python"]).revision(
            lambda r: r.version(f"3.{minor}")).kinds(kinds)

    return txn.uid("mbse.Programs.Python3.define/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"language": Language, **{f"Python_3_{minor}": Standard for minor in MINORS}})
        .spec([
            lambda _: _.language.standards({designation(minor): lambda e, minor=minor: e.standard(
                getattr(_, f"Python_3_{minor}")) for minor in MINORS}),
            *(version(minor) for minor in MINORS),
        ])]))])


def prepare(store: Any) -> Any:
    """`store`, holding `Python3.INSTALLS`, given the data `Check` reads: mbse-expressions' `define`s for `Python3`,
    `Python Types` and `Python Patterns`, then `install` and `define`, each in a transaction of its own. Run again, it
    writes nothing."""
    for each in (PythonExpressions.define, PythonTypes.define, PythonPatterns.define, install, define):
        store.transaction(each)
    return store
