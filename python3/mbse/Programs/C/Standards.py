"""Standards: the editions of C the language `Programs.C` covers, as data, the statement kinds each has, and the
grammar clauses each allows.

As the user decided for the port ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../../docs/proposals/port/README.md#decided),
question 4), each language is a singleton by name, owning its statement kinds, "its standards recorded as data, as for
C and C++"; and, asked how C and C++ divide into major versions: "Maybe C11, C17, C23 Cpp17, cpp20, cpp23", C17 being
C11's corrigenda, with no new syntax. Stage 4 takes them as mbse-expressions' C dialects have them, and this records
them as mbse-expressions records its dialects' (mbse-basis [CAP-268: standards as tagged data](mbse:mbse-basis/docs/capabilities/CAP-268.md#decided)):

- `install` extends `Programs.C.Language` with the adjacencies `standards`, through `Expressions.Framework.Covers`,
  and `grammar_clauses`, through `Expressions.Framework.Specifies`, and adds it to the framework's union of dialects,
  `Expressions.Framework.Dialect`, as the branch `programs_c`, which both link. Run after `Programs.C`'s install, in a
  transaction of its own; run again, it writes nothing.
- `define` writes the singleton `Programs.C` covering C11, C17 and C23, each by its designation (`ISO/IEC 9899:2024`),
  an `Expressions.Framework.Standard` with its bodies (`org.iso`, `ch.iec`), its number (`9899`), its revision's year
  and its common name (`C23`), as mbse-expressions' `C`, `C Types` and `C Preprocessor` write theirs, and holding the
  statement, declaration and member kinds it has (`Expressions.Framework.HasStandard`), by membership: each in every
  edition but those `ONLY` lists, in its editions alone. And it writes the language's grammar clauses by name
  (`GRAMMAR_CLAUSES`), each allowed or forbidden by each edition, through mbse-expressions' writer
  (`Framework.Standards.grammar_clauses_spec`). Run after `install`, in a transaction of its own; run again, it writes
  nothing. Its frame binds the language (`dialect`, as the writer names it), each edition by its common name (`C23`)
  and each grammar clause by its index (`grammar_clause_0`).
- `prepare(store)` runs, each in a transaction of its own, the installs mbse-expressions' `C` defines its domains with
  (`ISO/IEC 11404` and `IEEE 754`, which `C.INSTALLS` does not hold), mbse-expressions' `define`s for `C`, `C Types`
  and `C Preprocessor` (which record the expression, type and directive kinds each edition has and their grammar
  clauses, and which `C.store()` does not run), then `install` and `define`; it gives the store back. `Check` reads
  them.

A kind's availability is then read as mbse-expressions' are (`Expressions.Framework.Standards`): `kinds(standard)`
lists an edition's, and a kind is available in an edition where some dialect's standard of that designation lists it.
What an edition changes within a kind is a grammar clause, an alternative within a production of C's grammar, as the
user decided (mbse-basis [grammar clauses by version](mbse:mbse-basis/proposals/GRAMMAR-CLAUSES.md#decided), "No
minimum versions": "PEP 614 removing a restriction is still a conditional clause just with an opposite sense of version
progression"): an edition allows it or forbids it, and none has a minimum edition. The language's own are its
statements', C23's each (`GRAMMAR_CLAUSES`):

- a label, a `case` or a `default` without a statement, its `statement` absent (C23, 6.8.2), and before a declaration,
  its `statement` holding a declaration, a static assertion or an attribute declaration;
- `static_assert` spelled so, a static assertion's `keyword`, and without a message, its `message` absent;
- C23's helpers of C Types, `_BitInt`, `auto` as a type (C Types' `placeholdertypespecifier`) and attributes in `[[ ]]`,
  where a declaration, a member declaration or a function's definition holds them in its `specifiers`, and attributes
  in `[[ ]]` where one of them or an attributed statement holds them in its `attributes` (an attribute declaration is
  C23's alone), each
  named as C Types names the same where its type name or its parameter holds them
  (`SimpleDeclaration.specifiers holding a bitintspecifier`).

The terms' are mbse-expressions' dialects' own, which `Check` reads beside these: C's (a literal's digit separators, a
binary integer, its suffixes, `true` and `false`, an empty initializer, `alignof`), C Types' (C23's keywords, `typeof`,
an enumeration's underlying type, and C23's helpers where a type name or a parameter holds them) and C Preprocessor's
(`#warning` and `#embed`, a directive's name within `otherdirective`).

Decided by the agent, each *(agent)*:

- **The language owns its own standards and its own grammar clauses**, as each of mbse-expressions' dialects owns its
  own (`C Types` and `C Preprocessor` each own an "ISO/IEC 9899:2024", apart from `C`'s), rather than tagging statement
  kinds with `Expressions.C.Expressions`'; so each dialect's data stays its own, and they agree by designation.
- **Schema extension, here, for now**: `Programs.C.Language` in `Statements` has neither adjacency and is not a branch
  of `Expressions.Framework.Dialect`, which `Covers` and `Specifies` require of what owns a standard or a grammar
  clause; `install` adds them by extension, as TypeScript5's and Python3's `Standards` do. Folding them into
  `Statements.install`, and `install`, `define`, the expression `define`s and the domains' installs into
  `C.INSTALLS`, is a change asked of the model.
- **Statement, declaration and member kinds are tagged**, from mbse-programs 0.3's `Ccpp/Syntax.py`: each is in every
  edition but an attribute declaration (`[[fallthrough]];`), C23's alone. A static assertion is C11's, and C17 adds
  nothing. A translation unit is in every edition, and the parts that hold no statement (an init-declarator, a member
  list) are parts of the statements that hold them.
- **A grammar clause is keyed by its kind's name**, a C Types helper by its schema's name, lowercased, as C Types keys
  its own; and named as `Check` names the language feature, by the kind that takes it.
- **GNU's `asm` is in no edition** (`EXTENSIONS`), as mbse-expressions' `C` leaves GNU's statement expressions in none:
  C lists it among the common extensions only (ISO/IEC 9899, J.5.10). So `Check` does not check it, as an extension
  outside every edition.
- **What no grammar clause can express stays code**, `Check.UNRECORDED`, each with its reason: a function's definition
  with an unnamed parameter, and a declaration whose C's type is inferred, which each say what every element of a list
  holds, or what it does not.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mbse.Expressions.C.Expressions import Expressions as CExpressions
from mbse.Expressions.C.Preprocessor import Expressions as CPreprocessor
from mbse.Expressions.C.Types import Expressions as CTypes
from mbse.Expressions.Framework import Standards as FS
from mbse.Expressions.IEEE754 import Expressions as IEEE754
from mbse.Expressions.ISOIEC11404 import Expressions as ISOIEC11404

from .Statements import KINDS, LANGUAGE

__all__ = ["install", "define", "prepare", "ONLY", "EXTENSIONS", "EDITIONS", "DIALECTS", "GRAMMAR_CLAUSES"]

EDITIONS = {"C11": ("ISO/IEC 9899:2011", 2011), "C17": ("ISO/IEC 9899:2018", 2018),
            "C23": ("ISO/IEC 9899:2024", 2024)}
"""The editions of C the language covers, by common name, in order: each its designation and its revision's year."""

ONLY: dict[str, tuple[str, ...]] = {"AttributeDeclaration": ("C23",)}
"""The statement, declaration and member kinds that are not in every edition, each with the editions that have it, by
their common names: membership, no minimum edition."""

EXTENSIONS = ("AsmDeclaration",)
"""The kinds in no edition: GNU's."""

DIALECTS = (LANGUAGE, "Expressions.C.Expressions", "Expressions.C.Types", "Expressions.C.Preprocessor")
"""The singletons whose standards say which kinds and grammar clauses a C translation unit may hold: the language's own,
for its statements, then mbse-expressions' dialects, for the terms its statements hold."""

_C23 = ("C23",)
_LABELS = ("LabeledStatement", "CaseStatement", "DefaultStatement")
_DECLARATIONS = ("SimpleDeclaration", "StaticAssertDeclaration", "AttributeDeclaration")
_SPECIFIED = ("SimpleDeclaration", "MemberDeclaration", "FunctionDefinition")
"""The kinds that hold specifiers, C Types' helpers."""
_ATTRIBUTED = (*_SPECIFIED, "AttributedStatement")
"""The kinds that hold attribute specifiers, C Types' helpers, but an attribute declaration, C23's alone."""
_HELPERS = ("BitIntSpecifier", "PlaceholderTypeSpecifier", "StandardAttributeSpecifier")
"""The helpers of C Types that arrived in C23, which a grammar clause holds."""

GRAMMAR_CLAUSES = (
    *(FS.absent(f"{label} without a statement", label, "statement", _C23) for label in _LABELS),
    *(FS.kinds_of(f"{label} before a declaration", label, "statement", _DECLARATIONS, (), _C23) for label in _LABELS),
    FS.values("StaticAssertDeclaration.keyword 'static_assert'", "StaticAssertDeclaration", "keyword",
              ("static_assert",), _C23),
    FS.absent("StaticAssertDeclaration without a message", "StaticAssertDeclaration", "message", _C23),
    *(FS.kinds_of(f"{holder}.specifiers holding a {helper.lower()}", holder, "specifiers", (helper.lower(),), (), _C23)
      for holder in _SPECIFIED for helper in _HELPERS),
    *(FS.kinds_of(f"{holder}.attributes holding a standardattributespecifier", holder, "attributes",
                  ("standardattributespecifier",), (), _C23) for holder in _ATTRIBUTED),
)
"""The language's grammar clauses, its statements', each with the editions that allow it, by their frame symbols, every
other forbidding it, named as `Check` names the language feature."""


def install(txn: Any) -> Any:
    """`Programs.C.Language` given the adjacencies `standards` (`Expressions.Framework.Covers`) and `grammar_clauses`
    (`Expressions.Framework.Specifies`), and made a branch of `Expressions.Framework.Dialect`, by schema extension: run
    after `Programs.C`'s install, in a transaction of its own; run again, it writes nothing."""
    S, Framework = txn.Schemas, txn.Expressions.Framework
    return txn.uid("mbse.Programs.C.Standards/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"Language": S.OfObject, "Dialects": S.OfUnion})
        .spec([
            lambda _: _.Language.name(f"{LANGUAGE}.Language").adjacencies({
                "standards": lambda a: a.relation([Framework.Covers]).me("dialect"),
                "grammar_clauses": lambda a: a.relation([Framework.Specifies]).me("dialect")}),
            lambda _: _.Dialects.name("Expressions.Framework.Dialect").branches([
                lambda t: t.name("programs_c").schema([_.Language])]),
        ])]))])


def define(txn: Any) -> Any:
    """The editions of C the singleton `Programs.C` covers, by designation (`standards`), C11, C17 and C23, each with
    its formal reference's parts, its common name and the statement, declaration and member kinds it has (`ONLY`, but
    `EXTENSIONS`), and its grammar clauses by name (`grammar_clauses`), each allowed or forbidden by each edition
    (`GRAMMAR_CLAUSES`). Run after `install`, in a transaction of its own; run again, it writes nothing."""
    Language, Standard = txn.Programs.C.Language, txn.Expressions.Framework.Standard
    every = {kind: getattr(txn.Programs.C, kind).as_schema() for kind in KINDS if kind not in EXTENSIONS}
    schemas = {**every, **{helper.lower(): getattr(txn.Expressions.C.Types, helper).as_schema() for helper in _HELPERS}}
    editions = [list(EDITIONS)]
    clauses, specs = FS.grammar_clauses_spec(txn, "dialect", GRAMMAR_CLAUSES, schemas, editions)

    def edition(name: str) -> Callable[[Any], Any]:
        kinds = [schema for kind, schema in every.items() if name in ONLY.get(kind, (name,))]
        return lambda _: getattr(_, name).bodies(["org.iso", "ch.iec"]).number("9899").revision(
            lambda r: r.year(EDITIONS[name][1])).names([name]).kinds(kinds)

    return txn.uid("mbse.Programs.C.define/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"dialect": Language, **{name: Standard for name in EDITIONS}, **clauses})
        .spec([
            lambda _: _.dialect.standards({designation: lambda e, name=name: e.standard(getattr(_, name))
                                           for name, (designation, _year) in EDITIONS.items()}),
            *(edition(name) for name in EDITIONS),
            # its oldest edition flagged `before`, its newest `after`
            *FS.editions_spec(editions),
            *specs,
        ])]))])


def prepare(store: Any) -> Any:
    """`store`, holding `C.INSTALLS`, given the data `Check` reads: the installs of `ISO/IEC 11404` and `IEEE 754`,
    mbse-expressions' `define`s for `C`, `C Types` and `C Preprocessor`, then `install` and `define`, each in a
    transaction of its own. Run again, it writes nothing."""
    for each in (ISOIEC11404.install, IEEE754.install, CExpressions.define, CTypes.define, CPreprocessor.define,
                 install, define):
        store.transaction(each)
    return store
