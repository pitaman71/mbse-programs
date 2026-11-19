"""Standards: the editions of C the language `Programs.C` covers, as data, and the statement kinds each has.

As the user decided for the port ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../../docs/proposals/port/README.md#decided),
question 4), each language is a singleton by name, owning its statement kinds, "its standards recorded as data, as for
C and C++"; and, asked how C and C++ divide into major versions: "Maybe C11, C17, C23 Cpp17, cpp20, cpp23", C17 being
C11's corrigenda, with no new syntax. Stage 4 takes them as mbse-expressions' C dialects have them, and this records
them as mbse-expressions records its dialects' (mbse-basis [CAP-268: standards as tagged data](mbse:mbse-basis/docs/capabilities/CAP-268.md#decided)):

- `install` extends `Programs.C.Language` with the adjacency `standards`, through `Expressions.Framework.Covers`, and
  adds it to the framework's union of dialects, `Expressions.Framework.Dialect`, as the branch `programs_c`, which
  `Covers` links. Run after `Programs.C`'s install, in a transaction of its own; run again, it writes nothing.
- `define` writes the singleton `Programs.C` covering C11, C17 and C23, each by its designation (`ISO/IEC 9899:2024`),
  an `Expressions.Framework.Standard` with its bodies (`org.iso`, `ch.iec`), its number (`9899`), its revision's year
  and its common name (`C23`), as mbse-expressions' `C`, `C Types` and `C Preprocessor` write theirs, and holding the
  statement, declaration and member kinds it has (`Expressions.Framework.HasStandard`), each from the edition it
  arrived in (`SINCE`). Run after `install`, in a transaction of its own; run again, it writes nothing. Its frame binds
  the language (`language`) and each edition by its common name (`C23`).
- `prepare(store)` runs, each in a transaction of its own, the installs mbse-expressions' `C` defines its domains with
  (`ISO/IEC 11404` and `IEEE 754`, which `C.INSTALLS` does not hold), mbse-expressions' `define`s for `C`, `C Types`
  and `C Preprocessor` (which record the expression, type and directive kinds each edition has, and which `C.store()`
  does not run), then `install` and `define`; it gives the store back. `Check` reads them.

A kind's availability is then read as mbse-expressions' are (`Expressions.Framework.Standards`): `kinds(standard)`
lists an edition's, and a kind is available in an edition where some dialect's standard of that designation lists it.

Decided by the agent, each *(agent)*:

- **The language owns its own standards**, as each of mbse-expressions' dialects owns its own (`C Types` and `C
  Preprocessor` each own an "ISO/IEC 9899:2024", apart from `C`'s), rather than tagging statement kinds with
  `Expressions.C.Expressions`'; so each dialect's data stays its own, and they agree by designation.
- **Schema extension, here, for now**: `Programs.C.Language` in `Statements` has no `standards` adjacency and is not a
  branch of `Expressions.Framework.Dialect`, which `Covers` requires of what owns a standard; `install` adds both by
  extension, as TypeScript5's and Python3's `Standards` do. Folding both into `Statements.install`, and `install`,
  `define`, the expression `define`s and the domains' installs into `C.INSTALLS`, is a change asked of the model.
- **Statement, declaration and member kinds are tagged**, from mbse-programs 0.3's `Ccpp/Syntax.py` (`SINCE`, C's):
  each is in C11 but an attribute declaration (`[[fallthrough]];`), C23's. A static assertion is C11's, and C17 adds
  nothing. A translation unit is in every edition, and the parts that hold no statement (an init-declarator, a member
  list) are parts of the statements that hold them.
- **GNU's `asm` is in no edition** (`EXTENSIONS`), as mbse-expressions' `C` leaves GNU's statement expressions in none:
  C lists it among the common extensions only (ISO/IEC 9899, J.5.10). So `Check` does not check it, as an extension
  outside every edition.
- **What a property's value makes available stays code** (`Check.FEATURES`, `Check.STATEMENT_FEATURES`): a standard
  tags a kind's schema, not a property or a value of one (a label without a statement, `static_assert` spelled so, C23),
  so mbse-basis CAP-268's data cannot hold them yet.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mbse.Expressions.C.Expressions import Expressions as CExpressions
from mbse.Expressions.C.Preprocessor import Expressions as CPreprocessor
from mbse.Expressions.C.Types import Expressions as CTypes
from mbse.Expressions.IEEE754 import Expressions as IEEE754
from mbse.Expressions.ISOIEC11404 import Expressions as ISOIEC11404

from .Statements import KINDS, LANGUAGE

__all__ = ["install", "define", "prepare", "SINCE", "EXTENSIONS", "EDITIONS", "DIALECTS"]

EDITIONS = {"C11": ("ISO/IEC 9899:2011", 2011), "C17": ("ISO/IEC 9899:2018", 2018),
            "C23": ("ISO/IEC 9899:2024", 2024)}
"""The editions of C the language covers, by common name, in order: each its designation and its revision's year."""

SINCE: dict[str, str] = {"AttributeDeclaration": "C23"}
"""The edition each statement, declaration or member kind arrived in, by its common name, where it is not C11, from
which `define` writes the kinds each edition has."""

EXTENSIONS = ("AsmDeclaration",)
"""The kinds in no edition: GNU's."""

DIALECTS = (LANGUAGE, "Expressions.C.Expressions", "Expressions.C.Types", "Expressions.C.Preprocessor")
"""The singletons whose standards say which kinds a C translation unit may hold: the language's own, for its
statements, then mbse-expressions' dialects, for the terms its statements hold."""


def install(txn: Any) -> Any:
    """`Programs.C.Language` given the adjacency `standards` (`Expressions.Framework.Covers`), and made a branch of
    `Expressions.Framework.Dialect`, by schema extension: run after `Programs.C`'s install, in a transaction of its own;
    run again, it writes nothing."""
    S, Framework = txn.Schemas, txn.Expressions.Framework
    return txn.uid("mbse.Programs.C.Standards/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"Language": S.OfObject, "Dialects": S.OfUnion})
        .spec([
            lambda _: _.Language.name(f"{LANGUAGE}.Language").adjacencies({
                "standards": lambda a: a.relation([Framework.Covers]).me("dialect")}),
            lambda _: _.Dialects.name("Expressions.Framework.Dialect").branches([
                lambda t: t.name("programs_c").schema([_.Language])]),
        ])]))])


def define(txn: Any) -> Any:
    """The editions of C the singleton `Programs.C` covers, by designation (`standards`), C11, C17 and C23, each with
    its formal reference's parts, its common name and the statement, declaration and member kinds it has (`SINCE`, but
    `EXTENSIONS`). Run after `install`, in a transaction of its own; run again, it writes nothing."""
    Language, Standard = txn.Programs.C.Language, txn.Expressions.Framework.Standard
    every = {kind: getattr(txn.Programs.C, kind).as_schema() for kind in KINDS if kind not in EXTENSIONS}
    order = list(EDITIONS)

    def edition(name: str) -> Callable[[Any], Any]:
        kinds = [schema for kind, schema in every.items() if order.index(SINCE.get(kind, "C11")) <= order.index(name)]
        return lambda _: getattr(_, name).bodies(["org.iso", "ch.iec"]).number("9899").revision(
            lambda r: r.year(EDITIONS[name][1])).names([name]).kinds(kinds)

    return txn.uid("mbse.Programs.C.define/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"language": Language, **{name: Standard for name in EDITIONS}})
        .spec([
            lambda _: _.language.standards({designation: lambda e, name=name: e.standard(getattr(_, name))
                                            for name, (designation, _year) in EDITIONS.items()}),
            *(edition(name) for name in EDITIONS),
        ])]))])


def prepare(store: Any) -> Any:
    """`store`, holding `C.INSTALLS`, given the data `Check` reads: the installs of `ISO/IEC 11404` and `IEEE 754`,
    mbse-expressions' `define`s for `C`, `C Types` and `C Preprocessor`, then `install` and `define`, each in a
    transaction of its own. Run again, it writes nothing."""
    for each in (ISOIEC11404.install, IEEE754.install, CExpressions.define, CTypes.define, CPreprocessor.define,
                 install, define):
        store.transaction(each)
    return store
