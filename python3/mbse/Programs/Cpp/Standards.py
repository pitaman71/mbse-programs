"""Standards: the editions of C++ the language `Programs.Cpp` covers, as data, the statement kinds each has, and the
grammar clauses each allows.

As the user decided for the port ([Porting to the stabilized mbse-schemas and mbse-expressions](../../../../../docs/proposals/port/README.md#decided),
question 4), each language is a singleton by name, owning its statement kinds, "its standards recorded as data, as for
C and C++"; and, asked how C and C++ divide into major versions: "Maybe C11, C17, C23 Cpp17, cpp20, cpp23". Stage 4
takes them as mbse-expressions' C++ dialects have them, ISO/IEC 14882:2017, 2020 and 2024, and records them as
`Programs.C.Standards` records C's (mbse-basis [CAP-268: standards as tagged data](mbse:mbse-basis/docs/capabilities/CAP-268.md#decided)):

- `install` extends `Programs.Cpp.Language` with the adjacencies `standards`, through `Expressions.Framework.Covers`,
  and `grammar_clauses`, through `Expressions.Framework.Specifies`, and adds it to the framework's union of dialects,
  `Expressions.Framework.Dialect`, as the branch `programs_cpp`. Run after `Programs.Cpp`'s install, in a transaction
  of its own; run again, it writes nothing.
- `define` writes the singleton `Programs.Cpp` covering C++17, C++20 and C++23, each by its designation (`ISO/IEC
  14882:2024`), an `Expressions.Framework.Standard` with its bodies (`org.iso`, `ch.iec`), its number (`14882`), its
  revision's year and its common name (`C++23`), as mbse-expressions' `Cpp` and `Cpp Types` write theirs, and holding
  the statement, declaration, clause and member kinds it has, C's among them by name (`Programs.Cpp.IfStatement`), by
  membership: each in every edition but those `ONLY` lists, in its editions alone, C++17 flagged `before` and C++23
  `after` (`Framework.Standards.editions_spec`), so that C++26, which the data does not represent, is guessed to have
  what C++23 has. And it writes the language's grammar clauses by name (`GRAMMAR_CLAUSES`), each allowed or forbidden
  by each edition, through mbse-expressions' writer (`Framework.Standards.grammar_clauses_spec`). Run after `install`,
  in a transaction of its own; run again, it writes nothing. Its frame binds the language (`dialect`, the symbol it
  gives the writer), each edition by its common name spelled as an identifier (`Cpp23`), as mbse-expressions' frames
  do, and each grammar clause by its index (`grammar_clause_0`).
- `prepare(store)` runs, each in a transaction of its own, the installs mbse-expressions' `Cpp` defines its domains
  with (`ISO/IEC 11404` and `IEEE 754`), mbse-expressions' `define`s for `Cpp`, `Cpp Types` and `C Preprocessor`
  (whose C++ editions record the directive kinds each has), then `install` and `define`; it gives the store back.
  `Check` reads them.

What an edition changes within a kind is a grammar clause, as for C (mbse-basis [grammar clauses by
version](mbse:mbse-basis/proposals/GRAMMAR-CLAUSES.md#decided), "No minimum versions"): an edition allows it or forbids
it. The language's own are its statements' (`GRAMMAR_CLAUSES`), from the 0.3 language's data (`Ccpp/Syntax.py`'s
`FEATURES`, C++'s):

- `if consteval`, an `if`'s `consteval` (C++23); an alias declaration as an init-statement, the `initializer` of an
  `if`, a `switch`, a `for` or a range-based `for` holding one (C++23); a range-based `for`'s `initializer` (C++20);
- a label, a `case` or a `default` without a statement, or before a declaration (C++23, [stmt.label]);
- a trailing `requires` of a function's definition, a declarator or a member's declarator, and a template's `requires`
  (C++20);
- a nested namespace's name `inline`, a namespace's `names` holding a name whose `inline` is set, nested (C++20);
- a bit-field's default member initializer, a member's declarator's `initializer` where it `requires` its `bitfield`
  (C++20, [class.mem]);
- a `static` `operator()` or `operator[]` (C++23, [over.call], [over.sub]): a function's definition's or a member
  declaration's `specifiers` holding a `declspecifier` `static`, where it `requires` its declarator to reach, through
  the declarators that hold one, nested, an `iddeclarator` whose name is that operator's.

What C++ removed within the editions it covers is its dialects' data: `register` among a declaration's specifiers
(C++17), a `declspecifier` of mbse-expressions' `Cpp`, which the declarations hold, and dynamic exception
specifications (C++17's `throw(int)`, C++20's `throw()`), recorded there, C++14 guessed to allow them. Nothing a
statement holds of its own was removed by C++17, C++20 or C++23 *(agent)*.

The terms' are mbse-expressions' dialects' own, which `Check` reads beside these: C++'s (`consteval`, `constinit`,
`char8_t`, `<=>`, lambdas' template parameters, attributes, `requires` and `static`, pack init-captures, constrained
placeholders and parameters, explicit object parameters, `auto(x)`, the suffixes `z` and `uz`, `explicit(condition)`)
and C Preprocessor's of C++'s designations (`#warning`, C++23's, and `#embed`, in none of them).

Decided by the agent, each *(agent)*, as `Programs.C.Standards` decides for C:

- **The language owns its own standards and its own grammar clauses**, apart from C's: `Programs.Cpp` and
  `Programs.C` are two singletons, each covering its own editions, and the kinds C++ reuses from C are C++'s own
  schemas (`Statements`), tagged here.
- **Schema extension, here, for now**, as C's, TypeScript5's and Python3's `Standards` do.
- **Statement, declaration, clause and member kinds are tagged**, from mbse-programs 0.3's `Ccpp/Syntax.py`: each is in
  every edition but C++20's concepts (`ConceptDefinition`), modules (`ModuleDeclaration`, `GlobalModuleFragment`,
  `PrivateModuleFragment`, `ImportDeclaration`, `ExportDeclaration`), `using enum` (`UsingEnumDeclaration`) and
  coroutines' `co_return` (`CoReturnStatement`), in C++20 and C++23 alone. C++23 adds no kind of its own: what it adds
  is grammar clauses. A translation unit is in every edition, and the parts that hold no statement are parts of the
  statements that hold them.
- **A grammar clause is keyed by its kind's or its part's name** (`InitDeclarator`), and named as `Check` names the
  language feature, by the kind that takes it. A range-based `for` with an alias declaration as its init-statement
  takes both its grammar clauses, C++23's and C++20's.
- **GNU's `asm` is in no edition** (`EXTENSIONS`), as for C.
- **The directives' editions are read from data**, as the expressions' and the types' are: mbse-expressions' `C
  Preprocessor`, which C++'s directives and `__has_include` are terms of, records C++17, C++20 and C++23 by C++'s
  designations beside C's, each with the kinds it has (`elifdefdirective`, `#elifdef` and `#elifndef`, C++23's;
  `hasincludeexpression` C++17's) and the grammar clauses each allows, and `Check` reads its standards of C++'s
  designations alone (`DIALECTS`).
- **Nested and required grammar clauses are the language's**, though their kinds are C++'s helpers (`iddeclarator`,
  `declspecifier`), as C's are; no edition names them, so each allows them.
- **What no grammar clause can express** would stay code, in `Check`: nothing does, of C++'s statements.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from mbse.Expressions.C.Preprocessor import Expressions as CPreprocessor
from mbse.Expressions.Cpp.Expressions import Expressions as CppExpressions
from mbse.Expressions.Cpp.Types import Expressions as CppTypes
from mbse.Expressions.Framework import Standards as FS
from mbse.Expressions.IEEE754 import Expressions as IEEE754
from mbse.Expressions.ISOIEC11404 import Expressions as ISOIEC11404

from .Statements import KINDS, LANGUAGE

__all__ = ["install", "define", "prepare", "ONLY", "EXTENSIONS", "EDITIONS", "DIALECTS", "GRAMMAR_CLAUSES"]

EDITIONS = {"C++17": ("ISO/IEC 14882:2017", 2017), "C++20": ("ISO/IEC 14882:2020", 2020),
            "C++23": ("ISO/IEC 14882:2024", 2024)}
"""The editions of C++ the language covers, by common name, in order: each its designation and its revision's year."""

ONLY: dict[str, tuple[str, ...]] = {kind: ("C++20", "C++23") for kind in (
    "ConceptDefinition", "ModuleDeclaration", "GlobalModuleFragment", "PrivateModuleFragment", "ImportDeclaration",
    "ExportDeclaration", "UsingEnumDeclaration", "CoReturnStatement")}
"""The statement, declaration, clause and member kinds that are not in every edition, each with the editions that have
it, by their common names: C++20's, in C++20 and C++23; membership, no minimum edition."""

EXTENSIONS = ("AsmDeclaration",)
"""The kinds in no edition: GNU's."""

DIALECTS = (LANGUAGE, "Expressions.Cpp.Expressions", "Expressions.Cpp.Types", "Expressions.C.Preprocessor")
"""The singletons whose standards say which kinds and grammar clauses a C++ translation unit may hold: the language's
own, for its statements, then mbse-expressions' dialects, for the terms its statements hold, C Preprocessor's of C++'s
designations alone."""

_CPP20, _CPP23 = ("Cpp20", "Cpp23"), ("Cpp23",)
_LABELS = ("LabeledStatement", "CaseStatement", "DefaultStatement")
_DECLARATIONS = ("SimpleDeclaration", "StaticAssertDeclaration", "AliasDeclaration", "AttributeDeclaration")
_INITIALIZED = ("IfStatement", "SwitchStatement", "ForStatement", "RangeForStatement")
"""The statements that hold an init-statement."""
_PARTS = ("InitDeclarator", "MemberDeclarator", "NamespaceName")
"""The parts a grammar clause is about, beside the kinds."""
_HELPERS = ("DeclSpecifier", "OperatorName", "IdDeclarator", "PackDeclarator", "PointerDeclarator",
            "ReferenceDeclarator", "ArrayDeclarator", "FunctionDeclarator", "ParenthesizedDeclarator")
"""The helpers of C++'s a grammar clause is about, by their schemas' names, keyed lowercased (`declspecifier`)."""
_DECLARATORS = ("packdeclarator", "pointerdeclarator", "referencedeclarator", "arraydeclarator", "functiondeclarator",
                "parenthesizeddeclarator")
"""The declarators that hold a declarator."""


def _static(operator: str) -> tuple[FS.GrammarClause, ...]:
    """A `static` `operator()` or `operator[]` (C++23, [over.call], [over.sub]): a function's definition or a member
    declaration with a specifier `static`, whose declarator reaches, through those that hold it, the operator's name."""
    reaching = (f"iddeclarator of operator{operator}",
                *(f"{declarator} reaching operator{operator}" for declarator in _DECLARATORS))
    declarators = (*_DECLARATORS, "iddeclarator")
    return (
        *(FS.requires(FS.kinds_of(f"{kind} static operator{operator}", kind, "specifiers", ("declspecifier",),
                                  ("declspecifier.keyword 'static'",), _CPP23),
                      (f"{kind}.{name} reaching operator{operator}",))
          for kind, name in (("FunctionDefinition", "declarator"), ("MemberDeclaration", "declarators"))),
        FS.kinds_of(f"FunctionDefinition.declarator reaching operator{operator}", "FunctionDefinition", "declarator",
                    declarators, reaching, None),  # required: no edition names it, nor those below
        FS.kinds_of(f"MemberDeclaration.declarators reaching operator{operator}", "MemberDeclaration", "declarators",
                    ("MemberDeclarator",), (f"MemberDeclarator.declarator reaching operator{operator}",), None),
        FS.kinds_of(f"MemberDeclarator.declarator reaching operator{operator}", "MemberDeclarator", "declarator",
                    declarators, reaching, None),
        *(FS.kinds_of(name, declarator, "declarator", declarators, reaching, None)
          for name, declarator in zip(reaching[1:], _DECLARATORS)),
        FS.kinds_of(reaching[0], "iddeclarator", "name", ("operatorname",), (f"operatorname.operator '{operator}'",),
                    None),
        FS.values(f"operatorname.operator '{operator}'", "operatorname", "operator", (operator,), None),
    )


GRAMMAR_CLAUSES = (
    FS.values("IfStatement.consteval", "IfStatement", "consteval", (True,), _CPP23),
    *(FS.kinds_of(f"{kind} with an alias declaration as its init-statement", kind, "initializer", ("AliasDeclaration",),
                  (), _CPP23) for kind in _INITIALIZED),
    FS.present("RangeForStatement.initializer", "RangeForStatement", "initializer", _CPP20),
    *(FS.absent(f"{label} without a statement", label, "statement", _CPP23) for label in _LABELS),
    *(FS.kinds_of(f"{label} before a declaration", label, "statement", _DECLARATIONS, (), _CPP23) for label in _LABELS),
    *(FS.present(f"{kind}.requires", kind, "requires", _CPP20)
      for kind in ("FunctionDefinition", "InitDeclarator", "TemplateDeclaration", "MemberDeclarator")),
    FS.kinds_of("NamespaceDefinition with an inline nested name", "NamespaceDefinition", "names", ("NamespaceName",),
                ("NamespaceName.inline",), _CPP20),
    FS.values("NamespaceName.inline", "NamespaceName", "inline", (True,), None),  # nested
    # a bit-field's default member initializer (C++20, [class.mem]): its `bitfield` and its `initializer` together (an
    # initializer alone is C++11's)
    FS.requires(FS.present("MemberDeclarator with a bit-field's initializer", "MemberDeclarator", "initializer",
                           _CPP20), ("MemberDeclarator.bitfield",)),
    FS.present("MemberDeclarator.bitfield", "MemberDeclarator", "bitfield", None),  # required: no edition names it
    *_static("()"),
    *_static("[]"),
    FS.values("declspecifier.keyword 'static'", "declspecifier", "keyword", ("static",), None),  # nested
)
"""The language's grammar clauses, its statements', each with the editions that allow it, by their frame symbols, every
other forbidding it, or none naming it where it is only nested, named as `Check` names the language feature."""


def _symbol(name: str) -> str:
    """An edition's common name spelled as an identifier: `Cpp23`."""
    return name.replace("+", "p")


def install(txn: Any) -> Any:
    """`Programs.Cpp.Language` given the adjacencies `standards` (`Expressions.Framework.Covers`) and `grammar_clauses`
    (`Expressions.Framework.Specifies`), and made a branch of `Expressions.Framework.Dialect`, by schema extension: run
    after `Programs.Cpp`'s install, in a transaction of its own; run again, it writes nothing."""
    S, Framework = txn.Schemas, txn.Expressions.Framework
    return txn.uid("mbse.Programs.Cpp.Standards/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"Language": S.OfObject, "Dialects": S.OfUnion})
        .spec([
            lambda _: _.Language.name(f"{LANGUAGE}.Language").adjacencies({
                "standards": lambda a: a.relation([Framework.Covers]).me("dialect"),
                "grammar_clauses": lambda a: a.relation([Framework.Specifies]).me("dialect")}),
            lambda _: _.Dialects.name("Expressions.Framework.Dialect").branches([
                lambda t: t.name("programs_cpp").schema([_.Language])]),
        ])]))])


def define(txn: Any) -> Any:
    """The editions of C++ the singleton `Programs.Cpp` covers, by designation (`standards`), C++17, C++20 and C++23,
    each with its formal reference's parts, its common name and the statement, declaration, clause and member kinds it
    has (`ONLY`, but `EXTENSIONS`), and its grammar clauses by name (`grammar_clauses`), each allowed or forbidden by
    each edition (`GRAMMAR_CLAUSES`). Run after `install`, in a transaction of its own; run again, it writes
    nothing."""
    Language, Standard = txn.Programs.Cpp.Language, txn.Expressions.Framework.Standard
    every = {kind: getattr(txn.Programs.Cpp, kind).as_schema() for kind in KINDS if kind not in EXTENSIONS}
    schemas = {**every, **{part: getattr(txn.Programs.Cpp, part).as_schema() for part in _PARTS},
               **{helper.lower(): getattr(txn.Expressions.Cpp.Expressions, helper).as_schema() for helper in _HELPERS}}
    editions = [[_symbol(name) for name in EDITIONS]]
    clauses, specs = FS.grammar_clauses_spec(txn, "dialect", GRAMMAR_CLAUSES, schemas, editions)

    def edition(name: str) -> Callable[[Any], Any]:
        kinds = [schema for kind, schema in every.items() if name in ONLY.get(kind, (name,))]
        return lambda _: getattr(_, _symbol(name)).bodies(["org.iso", "ch.iec"]).number("14882").revision(
            lambda r: r.year(EDITIONS[name][1])).names([name]).kinds(kinds)

    return txn.uid("mbse.Programs.Cpp.define/1").mutations([lambda mu: mu.upsert(lambda u: u.exists([lambda p: p
        .symbols({"dialect": Language, **{_symbol(name): Standard for name in EDITIONS}, **clauses})
        .spec([
            lambda _: _.dialect.standards({designation: lambda e, name=name: e.standard(getattr(_, _symbol(name)))
                                           for name, (designation, _year) in EDITIONS.items()}),
            *(edition(name) for name in EDITIONS),
            # its oldest edition flagged `before`, its newest `after`
            *FS.editions_spec(editions),
            *specs,
        ])]))])


def prepare(store: Any) -> Any:
    """`store`, holding `Cpp.INSTALLS`, given the data `Check` reads: the installs of `ISO/IEC 11404` and `IEEE 754`,
    mbse-expressions' `define`s for `Cpp`, `Cpp Types` and `C Preprocessor`, then `install` and `define`, each in a
    transaction of its own. Run again, it writes nothing."""
    for each in (ISOIEC11404.install, IEEE754.install, CppExpressions.define, CppTypes.define, CPreprocessor.define,
                 install, define):
        store.transaction(each)
    return store
