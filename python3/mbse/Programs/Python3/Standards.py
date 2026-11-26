"""Standards: the versions of Python 3 the language `Programs.Python3` covers, as data, the statement kinds each has,
and its statements' grammar clauses, which each allows or forbids.

As the user decided for the port ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../../docs/proposals/port/README.md#decided),
question 4), each language is a singleton by name, owning its statement kinds, "its standards recorded as data, as for
C and C++"; and a language "must correctly handle the closure of syntaxes across minor versions such as 3.11 - 3.14".
This records them as mbse-expressions records its dialects' (mbse-basis [CAP-268: standards as tagged data](mbse:mbse-basis/docs/capabilities/CAP-268.md#decided)),
and what changes from one version to the next within a kind as grammar clauses (mbse-basis [grammar clauses by
version](mbse:mbse-basis/proposals/GRAMMAR-CLAUSES.md), "No minimum versions": "PEP 614 removing a restriction is still
a conditional clause just with an opposite sense of version progression. That excludes having a "minimum version"
annotation which is hacky anyway"):

- `install` extends `Programs.Python3.Language` with the adjacencies `standards`, through
  `Expressions.Framework.Covers`, and `grammar_clauses`, through `Expressions.Framework.Specifies`, and adds it to the
  framework's union of dialects, `Expressions.Framework.Dialect`, as the branch `programs_python3`, which both relations
  link. Run after `Programs.Python3`'s install, in a transaction of its own; run again, it writes nothing.
- `define` writes the singleton `Programs.Python3` covering Python 3.0 to 3.15, each by its published name
  (`Python 3.12`), an `Expressions.Framework.Standard` with its body (`org.python`) and its version, and holding the
  statement and clause kinds it has (`Expressions.Framework.HasStandard`), by membership (`ONLY`), 3.0 flagged `before`
  and 3.15 `after` (`Framework.Standards.editions_spec`), so that Python 3.16, which the data does not represent, is
  guessed to have what 3.15 has; and owning its grammar clauses by name (`GRAMMAR_CLAUSES`), each allowed or forbidden
  by each version, written by mbse-expressions' writer (`Framework.Standards.grammar_clauses_spec`). Run after
  `install`, in a transaction of its own; run again, it writes nothing. Its frame binds the language (`dialect`, the
  symbol it gives the writer), each version by its name spelled as an identifier (`Python_3_12`) and each grammar
  clause by its index (`grammar_clause_0`).
- `prepare(store)` runs, each in a transaction of its own, mbse-expressions' `define`s for `Python3`, `Python Types`
  and `Python Patterns` (which record the expression, type and pattern kinds each version has, and their terms'
  grammar clauses, and which `Python3.store()` does not run), then `install` and `define`; it gives the store back.
  `Check` reads them.

A kind's availability is then read as mbse-expressions' are (`Expressions.Framework.Standards`): `kinds(standard)`
lists a version's, and a kind is available in a version where some dialect's standard of that name lists it; a grammar
clause, where `allows(standard, clause)` says so.

The grammar clauses, each named as `Check` reports it: `Import.is_lazy` and `ImportFrom.is_lazy` (3.15), `AugAssign.op
'@'` (3.5), `FunctionDef`'s, `AsyncFunctionDef`'s and `ClassDef`'s `type_params` (3.12), and PEP 614's decorator,
nested, as the proposal has it: "Python 3.0 to 3.8 have "a decorator holds a dotted name, optionally called" (a `name`,
an `attribute` whose value is one, or a `call` whose function is one), Python 3.9 on "a decorator holds any term"". Each
of the three kinds has both, `<kind> with a decorator holding a dotted name, optionally called`, allowed by 3.0 to 3.8
and forbidden by 3.9 on, and `<kind> with a decorator holding any term`, forbidden by 3.0 to 3.8 and allowed by 3.9
on; the first holds a `variable`, or an `attribute` or a `call` taking the nested `attribute of a dotted name` or `call
of a dotted name`, which no version names. `Check` reads the two as alternatives of one production: a decorator is
fine in a version that allows either one it takes *(agent)*.

And what Python 3.7 removed: the names `async` and `await`, which it reserved, where a statement declares them, a
definition's or an `except` clause's `name`, `global`'s and `nonlocal`'s `names` and an alias' `asname`
(`FunctionDef.name 'async' or 'await'`), allowed by 3.0 to 3.6, as mbse-expressions' `Python3` records them where a
term refers to them (`variable.name 'async' or 'await'`). An alias' `name` and a from-import's `module`, dotted names,
are not: a grammar clause says what a property's value is, not what a part of it is *(agent)*. Python 3.0 to 3.15
removed nothing else a statement holds; Python 2's `print` and `exec` statements were never Python 3's.

Decided by the agent, each *(agent)*:

- **The language owns its own standards and grammar clauses**, as each of mbse-expressions' dialects owns its own
  (`Python Types` and `Python Patterns` each own a "Python 3.12", apart from `Python3`'s), rather than tagging statement
  kinds with `Expressions.Python.Python3`'s; so each dialect's data stays its own, and they agree by designation. The
  nested grammar clauses of the decorator are the language's too, though their kinds (`attribute`, `call`) are
  `Python3`'s: a grammar clause is owned by the dialect whose grammar has the alternative.
- **Schema extension, here, for now**: `Programs.Python3.Language` in `Statements` has neither adjacency and is not a
  branch of `Expressions.Framework.Dialect`, which `Covers` and `Specifies` require of what owns a standard or a grammar
  clause; `install` adds them by extension, as mbse-expressions' dialects add theirs. Folding them into
  `Statements.install`, and `install`, `define` and the expression `define`s into `Python3.INSTALLS` (so that
  `Python3.store()` holds them), is a change asked of the model.
- **Only statement and clause kinds are tagged**: a module (`Programs.Python3.Module`) is in every version, and the
  value objects (`Alias`, `WithItem`) and named containers are parts of the statements that hold them.
- **A decorator holding any term** holds a term of any of `Python3`'s kinds but its extensions and invalid syntax
  (`ANY`).
- **An alias' grammar clauses are the language's**, `Programs.Python3.Alias` a part of the imports that hold it.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mbse.Expressions.Framework import Standards as FS, Terms
from mbse.Expressions.Python.Patterns import Expressions as PythonPatterns
from mbse.Expressions.Python.Python3 import Expressions as PythonExpressions
from mbse.Expressions.Python.Types import Expressions as PythonTypes

from .Statements import KINDS, LANGUAGE

__all__ = ["install", "define", "prepare", "ONLY", "GRAMMAR_CLAUSES", "ANY", "MINORS", "VERSIONS", "DIALECTS",
           "designation"]

MINORS = range(16)
"""The minor versions of Python 3 the language covers: 3.0 to 3.15."""

VERSIONS = tuple(f"Python_3_{minor}" for minor in MINORS)
"""The versions of Python 3 it covers, oldest first, each by its name spelled as an identifier, as `define`'s frame
binds it (`Python_3_12`)."""

ONLY = {**dict.fromkeys(("AsyncFor", "AsyncWith", "AsyncFunctionDef"), VERSIONS[5:]), "AnnAssign": VERSIONS[6:],
        "Match": VERSIONS[10:], "MatchCase": VERSIONS[10:], "TryStar": VERSIONS[11:], "TypeAlias": VERSIONS[12:]}
"""The statement and clause kinds that are not in every version, each with the versions that have it, from which
`define` writes the kinds each version has: membership, no minimum version."""

ANY = tuple(tag for tag in PythonExpressions.DIALECT.kinds()
            if tag not in PythonExpressions.EXTENSIONS and tag not in Terms.INVALID_KINDS)
"""The kinds of term a decorator holding any term may hold: `Python3`'s, but its extensions and invalid syntax."""

_DEFINITIONS = ("FunctionDef", "AsyncFunctionDef", "ClassDef")
_DOTTED = ("variable", "attribute")
_RESERVED = ("async", "await")
_NAMED = (*((kind, "name") for kind in (*_DEFINITIONS, "ExceptHandler")), ("Global", "names"), ("Nonlocal", "names"),
          ("Alias", "asname"))
"""The names a statement or an alias declares, each by its kind and its property, an identifier or identifiers."""

GRAMMAR_CLAUSES = (
    *(FS.values(f"{kind}.is_lazy", kind, "is_lazy", (True,), VERSIONS[15:]) for kind in ("Import", "ImportFrom")),
    FS.values("AugAssign.op '@'", "AugAssign", "op", ("@",), VERSIONS[5:]),
    *(FS.present(f"{kind}.type_params", kind, "type_params", VERSIONS[12:]) for kind in _DEFINITIONS),
    # PEP 614: a restriction removed, a grammar clause 3.9 forbids and one it allows
    *(FS.kinds_of(f"{kind} with a decorator holding a dotted name, optionally called", kind, "decorator_list",
                  (*_DOTTED, "call"), ("attribute of a dotted name", "call of a dotted name"), VERSIONS[:9])
      for kind in _DEFINITIONS),
    *(FS.kinds_of(f"{kind} with a decorator holding any term", kind, "decorator_list", ANY, (), VERSIONS[9:])
      for kind in _DEFINITIONS),
    # nested: no version names them
    FS.kinds_of("attribute of a dotted name", "attribute", "value", _DOTTED, ("attribute of a dotted name",), None),
    FS.kinds_of("call of a dotted name", "call", "func", _DOTTED, ("attribute of a dotted name",), None),
    # removed: the names `async` and `await`, which Python 3.7 reserved
    *(FS.values(f"{kind}.{name} 'async' or 'await'", kind, name, _RESERVED, VERSIONS[:7]) for kind, name in _NAMED),
)
"""Its statements' grammar clauses, each with the versions that allow it, every other forbidding it, named as `Check`
reports them: what a property's value makes available within a statement kind, keyed by its kind's name, a nested
grammar clause's kind by its tag in `Python3` (`attribute`)."""

DIALECTS = (LANGUAGE, "Expressions.Python.Python3", "Expressions.Python.Types", "Expressions.Python.Patterns")
"""The singletons whose standards say which kinds and grammar clauses a Python 3 module may hold: the language's own,
for its statements, then mbse-expressions' dialects, for the terms its statements hold."""


def designation(minor: int) -> str:
    """A version's published name, by which each dialect covers it: `Python 3.12`."""
    return f"Python 3.{minor}"


def install(txn: Any) -> Any:
    """`Programs.Python3.Language` given the adjacencies `standards` (`Expressions.Framework.Covers`) and
    `grammar_clauses` (`Expressions.Framework.Specifies`), and made a branch of `Expressions.Framework.Dialect`, by
    schema extension: run after `Programs.Python3`'s install, in a transaction of its own; run again, it writes
    nothing."""
    S, Framework = txn.Schemas, txn.Expressions.Framework
    return txn.uid("mbse.Programs.Python3.Standards/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"Language": S.OfObject, "Dialects": S.OfUnion})
        .spec([
            lambda _: _.Language.name(f"{LANGUAGE}.Language").adjacencies({
                "standards": lambda a: a.relation([Framework.Covers]).me("dialect"),
                "grammar_clauses": lambda a: a.relation([Framework.Specifies]).me("dialect")}),
            lambda _: _.Dialects.name("Expressions.Framework.Dialect").branches([
                lambda t: t.name("programs_python3").schema([_.Language])]),
        ])]))])


def define(txn: Any) -> Any:
    """The versions of Python 3 the singleton `Programs.Python3` covers, by their published names (`standards`), 3.0
    to 3.15, each with its body, its version and the statement and clause kinds it has (`ONLY`), and its grammar
    clauses by name (`grammar_clauses`), each allowed or forbidden by each version (`GRAMMAR_CLAUSES`). Run after
    `install`, in a transaction of its own; run again, it writes nothing."""
    Language, Standard = txn.Programs.Python3.Language, txn.Expressions.Framework.Standard
    every = {kind: getattr(txn.Programs.Python3, kind).as_schema() for kind in KINDS}
    terms = {branch.name: branch.schema for branch in txn.Expressions.Python.Python3.Term.as_schema().branches}
    clauses, specs = FS.grammar_clauses_spec(txn, "dialect", GRAMMAR_CLAUSES,
                                             {**every, "Alias": txn.Programs.Python3.Alias.as_schema(), **terms},
                                             [VERSIONS])

    def version(minor: int) -> Callable[[Any], Any]:
        kinds = [schema for kind, schema in every.items() if VERSIONS[minor] in ONLY.get(kind, VERSIONS)]
        return lambda _: getattr(_, VERSIONS[minor]).bodies(["org.python"]).revision(
            lambda r: r.version(f"3.{minor}")).kinds(kinds)

    return txn.uid("mbse.Programs.Python3.define/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"dialect": Language, **dict.fromkeys(VERSIONS, Standard), **clauses})
        .spec([
            lambda _: _.dialect.standards({designation(minor): lambda e, minor=minor: e.standard(
                getattr(_, VERSIONS[minor])) for minor in MINORS}),
            *(version(minor) for minor in MINORS),
            # its oldest version flagged `before`, its newest `after`
            *FS.editions_spec([VERSIONS]),
            # its statements' grammar clauses, each allowed or forbidden by each version
            *specs,
        ])]))])


def prepare(store: Any) -> Any:
    """`store`, holding `Python3.INSTALLS`, given the data `Check` reads: mbse-expressions' `define`s for `Python3`,
    `Python Types` and `Python Patterns`, then `install` and `define`, each in a transaction of its own. Run again, it
    writes nothing."""
    for each in (PythonExpressions.define, PythonTypes.define, PythonPatterns.define, install, define):
        store.transaction(each)
    return store
