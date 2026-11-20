"""Standards: the editions of C++ the language `Programs.Cpp` covers, as data, and the statement kinds each has.

As the user decided for the port ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../../docs/proposals/port/README.md#decided),
question 4), each language is a singleton by name, owning its statement kinds, "its standards recorded as data, as for
C and C++"; and, asked how C and C++ divide into major versions: "Maybe C11, C17, C23 Cpp17, cpp20, cpp23". Stage 4
takes them as mbse-expressions' C++ dialects have them, ISO/IEC 14882:2017, 2020 and 2024, and records them as
`Programs.C.Standards` records C's (mbse-basis [CAP-268: standards as tagged data](mbse:mbse-basis/docs/capabilities/CAP-268.md#decided)):

- `install` extends `Programs.Cpp.Language` with the adjacency `standards`, through `Expressions.Framework.Covers`, and
  adds it to the framework's union of dialects, `Expressions.Framework.Dialect`, as the branch `programs_cpp`. Run
  after `Programs.Cpp`'s install, in a transaction of its own; run again, it writes nothing.
- `define` writes the singleton `Programs.Cpp` covering C++17, C++20 and C++23, each by its designation (`ISO/IEC
  14882:2024`), an `Expressions.Framework.Standard` with its bodies (`org.iso`, `ch.iec`), its number (`14882`), its
  revision's year and its common name (`C++23`), as mbse-expressions' `Cpp` and `Cpp Types` write theirs, and holding
  the statement, declaration, clause and member kinds it has, C's among them by name (`Programs.Cpp.IfStatement`),
  each from the edition it arrived in (`SINCE`). Run after `install`, in a transaction of its own; run again, it
  writes nothing. Its frame binds the language (`language`) and each edition by its common name spelled as an
  identifier (`Cpp23`), as mbse-expressions' frames do.
- `prepare(store)` runs, each in a transaction of its own, the installs mbse-expressions' `Cpp` defines its domains
  with (`ISO/IEC 11404` and `IEEE 754`), mbse-expressions' `define`s for `Cpp`, `Cpp Types` and `C Preprocessor`
  (whose C++ editions record the directive kinds each has), then `install` and `define`; it gives the store back.
  `Check` reads them.

Decided by the agent, each *(agent)*, as `Programs.C.Standards` decides for C:

- **The language owns its own standards**, apart from C's: `Programs.Cpp` and `Programs.C` are two singletons, each
  covering its own editions, and the kinds C++ reuses from C are C++'s own schemas (`Statements`), tagged here.
- **Schema extension, here, for now**, as C's, TypeScript5's and Python3's `Standards` do.
- **Statement, declaration, clause and member kinds are tagged**, from mbse-programs 0.3's `Ccpp/Syntax.py` (`SINCE`,
  C++'s): each is in C++17 but C++20's concepts (`ConceptDefinition`), modules (`ModuleDeclaration`,
  `GlobalModuleFragment`, `PrivateModuleFragment`, `ImportDeclaration`, `ExportDeclaration`), `using enum`
  (`UsingEnumDeclaration`) and coroutines' `co_return` (`CoReturnStatement`). C++23 adds no kind of its own: what it
  adds a property's value makes (`Check.STATEMENT_FEATURES`). A translation unit is in every edition, and the parts that
  hold no statement are parts of the statements that hold them.
- **GNU's `asm` is in no edition** (`EXTENSIONS`), as for C.
- **The directives' editions are read from data**, as the expressions' and the types' are: mbse-expressions' `C
  Preprocessor`, which C++'s directives and `__has_include` are terms of, records C++17, C++20 and C++23 by C++'s
  designations beside C's, each with the kinds it has (`elifdefdirective`, `#elifdef` and `#elifndef`, C++23's;
  `hasincludeexpression` C++17's), and `Check` reads its standards of C++'s designations alone (`DIALECTS`). A
  directive's name within `otherdirective` (`#warning`, C++23's) is a feature of a property's value, which its data
  does not record, and stays code (`Check.FEATURES`).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mbse.Expressions.C.Preprocessor import Expressions as CPreprocessor
from mbse.Expressions.Cpp.Expressions import Expressions as CppExpressions
from mbse.Expressions.Cpp.Types import Expressions as CppTypes
from mbse.Expressions.IEEE754 import Expressions as IEEE754
from mbse.Expressions.ISOIEC11404 import Expressions as ISOIEC11404

from .Statements import KINDS, LANGUAGE

__all__ = ["install", "define", "prepare", "SINCE", "EXTENSIONS", "EDITIONS", "DIALECTS"]

EDITIONS = {"C++17": ("ISO/IEC 14882:2017", 2017), "C++20": ("ISO/IEC 14882:2020", 2020),
            "C++23": ("ISO/IEC 14882:2024", 2024)}
"""The editions of C++ the language covers, by common name, in order: each its designation and its revision's year."""

SINCE: dict[str, str] = {
    "ConceptDefinition": "C++20", "ModuleDeclaration": "C++20", "GlobalModuleFragment": "C++20",
    "PrivateModuleFragment": "C++20", "ImportDeclaration": "C++20", "ExportDeclaration": "C++20",
    "UsingEnumDeclaration": "C++20", "CoReturnStatement": "C++20"}
"""The edition each statement, declaration, clause or member kind arrived in, by its common name, where it is not
C++17, from which `define` writes the kinds each edition has."""

EXTENSIONS = ("AsmDeclaration",)
"""The kinds in no edition: GNU's."""

DIALECTS = (LANGUAGE, "Expressions.Cpp.Expressions", "Expressions.Cpp.Types", "Expressions.C.Preprocessor")
"""The singletons whose standards say which kinds a C++ translation unit may hold: the language's own, for its
statements, then mbse-expressions' dialects, for the terms its statements hold, C Preprocessor's of C++'s designations
alone."""


def _symbol(name: str) -> str:
    """An edition's common name spelled as an identifier: `Cpp23`."""
    return name.replace("+", "p")


def install(txn: Any) -> Any:
    """`Programs.Cpp.Language` given the adjacency `standards` (`Expressions.Framework.Covers`), and made a branch of
    `Expressions.Framework.Dialect`, by schema extension: run after `Programs.Cpp`'s install, in a transaction of its
    own; run again, it writes nothing."""
    S, Framework = txn.Schemas, txn.Expressions.Framework
    return txn.uid("mbse.Programs.Cpp.Standards/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"Language": S.OfObject, "Dialects": S.OfUnion})
        .spec([
            lambda _: _.Language.name(f"{LANGUAGE}.Language").adjacencies({
                "standards": lambda a: a.relation([Framework.Covers]).me("dialect")}),
            lambda _: _.Dialects.name("Expressions.Framework.Dialect").branches([
                lambda t: t.name("programs_cpp").schema([_.Language])]),
        ])]))])


def define(txn: Any) -> Any:
    """The editions of C++ the singleton `Programs.Cpp` covers, by designation (`standards`), C++17, C++20 and C++23,
    each with its formal reference's parts, its common name and the statement, declaration, clause and member kinds it
    has (`SINCE`, but `EXTENSIONS`). Run after `install`, in a transaction of its own; run again, it writes nothing."""
    Language, Standard = txn.Programs.Cpp.Language, txn.Expressions.Framework.Standard
    every = {kind: getattr(txn.Programs.Cpp, kind).as_schema() for kind in KINDS if kind not in EXTENSIONS}
    order = list(EDITIONS)

    def edition(name: str) -> Callable[[Any], Any]:
        kinds = [schema for kind, schema in every.items() if order.index(SINCE.get(kind, "C++17")) <= order.index(name)]
        return lambda _: getattr(_, _symbol(name)).bodies(["org.iso", "ch.iec"]).number("14882").revision(
            lambda r: r.year(EDITIONS[name][1])).names([name]).kinds(kinds)

    return txn.uid("mbse.Programs.Cpp.define/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"language": Language, **{_symbol(name): Standard for name in EDITIONS}})
        .spec([
            lambda _: _.language.standards({designation: lambda e, name=name: e.standard(getattr(_, _symbol(name)))
                                            for name, (designation, _year) in EDITIONS.items()}),
            *(edition(name) for name in EDITIONS),
        ])]))])


def prepare(store: Any) -> Any:
    """`store`, holding `Cpp.INSTALLS`, given the data `Check` reads: the installs of `ISO/IEC 11404` and `IEEE 754`,
    mbse-expressions' `define`s for `Cpp`, `Cpp Types` and `C Preprocessor`, then `install` and `define`, each in a
    transaction of its own. Run again, it writes nothing."""
    for each in (ISOIEC11404.install, IEEE754.install, CppExpressions.define, CppTypes.define, CPreprocessor.define,
                 install, define):
        store.transaction(each)
    return store
