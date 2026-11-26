"""Check: which editions of C++ have the constructs a stored translation unit uses, and whether it is a valid one.

`Programs.C.Check` over C++'s kinds and terms: a unit is a `Programs.Cpp.TranslationUnit` that
`Programs.Framework.TheWorkspace` owns by its path, as `Parse` writes it. Both functions read it, within the
transaction open on `store` or, where none is, within one of their own, and write nothing; each raises LookupError where
the workspace holds no file at `path`.

- `check(store, path, version)`: the problems of the constructs the unit uses that `version` lacks, in source order,
  each once. `version` is an edition of C++, by its common name (`"C++23"`), its designation (`"ISO/IEC 14882:2024"`)
  or the number its common name gives, as a tuple (`(23,)`), as C's; LookupError where the language covers none such.
  The store must hold the standards (`Standards.prepare`).
- `validate(store, path)`: the unit's problems as a tree, in source order: each kind's own rules, ported from the 0.3
  language's validation, and its terms' problems, as their dialects validate them, but what depends on the target,
  which waits for an ABI to be applied (below).

Each problem is located by its place in the unit's value, as `Definitions` anchors it and as C's `Check` locates it,
its steps joined by `.`: a statement's, declaration's, clause's or member's is the property of what holds it, with its
index where that holds a list, from the unit's `body` (`body[2]`, `body[0].body.handlers[0]`); a part's, its
statement's then its property (`body[0].declarators[1]`); a term's or a helper's, the place of the outermost one that
holds it (`body[0].declarators[0].initializer`). Statements within a term, a lambda's `block`, a class's `members` and
a conditional directive's `group`, are located through the term's place (`body[0].specifiers[0].members.members[1]`,
`body[1].declarators[0].initializer.block.body[0]`). So: `body[2].body.body[0]: IfStatement.consteval needs C++23`,
`body[0]: ConceptDefinition needs C++20`.

What an edition has is read from data, as C's: a statement, declaration, clause or member kind is available where a
standard of that edition's designation, among those `Programs.Cpp` covers, lists its schema (`Standards`); a term's
kind, where one of `Cpp`'s, `Cpp Types`' or `C Preprocessor`'s of C++'s designations does (`Standards.DIALECTS`):
C++20's `requires`, `co_await`, `co_yield` and designated initializers, C++23's `#elifdef` and `#elifndef`
(`elifdefdirective`), and C++17's `__has_include` (`hasincludeexpression`), in every edition. A kind no standard lists
is not checked: GNU's extensions, a part or a helper, and invalid syntax, a `Programs.Cpp.Error` and an `error` or
`missing` term, which `validate` reports, as C's *(agent)*. A kind's problem is
`<kind> needs <the first edition that has it>`.

What an edition changes within a kind is read from data too, as C's: the grammar clauses each statement, member, part,
term and helper takes, of the dialect whose kind it is, the language's (`Standards.GRAMMAR_CLAUSES`: `if consteval`,
init-statements, labels, `requires`, nested inline namespaces, a bit-field's initializer, a `static` `operator()` or
`operator[]`) and `Cpp`'s, `Cpp Types`' and `C Preprocessor`'s (`consteval`, `char8_t`, `<=>`, lambdas' parts, explicit
object parameters, `auto(x)`, the suffix `z`, several indices, `#warning`, ...), each the target allows or forbids, as
C's reads them (`Framework.Standards.edition_allows`); a problem `<its name> needs <the edition nearest the target
that allows it>`, or `<its name> is in no edition` (`#embed`, which C Preprocessor allows in C23 alone).

What C++ removed is its dialects' data, which `check` reads as any: `register` among a declaration's specifiers, which
C++17 removed (`declspecifier.keyword 'register' is in no edition`), and dynamic exception specifications, `throw(int)`
removed by C++17 and `throw()` by C++20 (`throwspecifier without types needs C++17`). What no grammar clause can express
would stay code: nothing does, of C++'s. What C++17 has, every edition has: structured bindings among them.

Not checked: an abbreviated function template's `auto` parameter (C++20), which `check` cannot tell from a generic
lambda's (C++14) without its context *(agent)*.

`validate`'s rules, each the 0.3 rule where one stands, located at the statement, member or part: what a kind needs, a
property (`an IfStatement needs a consequence`, `a TryStatement needs a body`), a list that is not empty (`a
TryStatement needs a handler`, `a UsingDeclaration needs a declarator`), and what goes together (`an IfStatement needs a
condition` but a consteval one, `a GotoStatement needs a label or a target`, `an ImportDeclaration needs a name, a
partition or a header`, `an IfStatement negated needs consteval`); a kind's word one of its choices
(`AccessSpecifier.access cannot be 'friend'`); a function's definition's declarator declaring a function; and the
dangling `else`. C++ declares constructors, destructors, conversions and deduction guides with no type specifier, so a
declaration needs none *(agent: C's rule, C99's, is no rule of C++)*. Invalid syntax, as the user decided that a parse
keeps it and validation reports it: each `Programs.Cpp.Error`, `invalid syntax '<its text>'`, located at the error;
an `error` or `missing` term as its dialect validates it. Terms: each term a statement or a part holds, as its dialect
validates it (`Cpp`'s, `Cpp Types`' or `C Preprocessor`'s `DIALECT.validate`); a helper a statement holds alone, by its
own checks (`C.Expressions.Kinds.problems`, in C++) and its terms as their dialect validates them; the names a term
refers to taken as bound, binding being `Definitions`'.

**The ABI is applied last**, as for C. As the user decided, "Of course C and C++ need a ABI, but if we can model
programs in an abi-agnostic form and apply the ABI at the last minute, that would be advantageous". A program names no
ABI: a unit holds C++ as written, and nothing in its tree depends on a target. `validate` checks what does not depend
on one; the checks that do are not made: a literal's type and its range (`1`'s `int`, `'\\xc8'`'s `char`, whose
signedness C++ leaves to the implementation), `sizeof` and `alignof`, and constant evaluation (an array's size, a
`static_assert`'s condition, a bit-field's width, a template's constant argument): its terms are validated within
mbse-expressions' `Domains.Reading(None)`, which defers each check needing an ABI rather than reporting it. The ABI is
applied at the call that needs one, as C's (`Programs.C.Check`): `validate_for(store, path, abi)` validates within
`Domains.Reading` of the ABI dialect's singleton named `abi` (`Expressions.SystemV.AMD64`, `Expressions.Arm.AAPCS64`,
`ABIS`, C's, as each serves C and C++ alike), so that each literal's type and range is checked under that target, and
`prepare_abi(store, abi)`, C's, gives a store the ABI's schemas and types, after `Standards.prepare`.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from mbse.Expressions.C.Expressions import Domains, Kinds
from mbse.Expressions.C.Preprocessor import Expressions as CPreprocessor
from mbse.Expressions.Cpp.Expressions import Expressions as CppExpressions
from mbse.Expressions.Cpp.Types import Expressions as CppTypes
from mbse.Expressions.Framework import Objects, Terms

from ..C import Check as C
from ..C.Check import ABIS, _applied, _Availability, _bound, _branch, _check, _kind, _read, _terms, _walk, prepare_abi
from .Standards import DIALECTS
from .Statements import KINDS, LANGUAGE

__all__ = ["check", "check_file", "validate", "validate_file", "validate_for", "validate_file_for", "prepare_abi",
           "ABIS"]

Version = tuple[int, ...]

_HOLDERS = frozenset(f"{LANGUAGE}.{kind}" for kind in (*KINDS, "Error", "MemberList", "Group", "MemberGroup"))
"""The schemas that have a statement's place: statements, declarations, clauses, members, invalid syntax and the parts
that hold them."""
_DIALECTS = {"Expressions.Cpp.Expressions.Term": CppExpressions.DIALECT, "Expressions.Cpp.Types.Term": CppTypes.DIALECT,
             "Expressions.C.Preprocessor.Term": CPreprocessor.DIALECT}
"""The dialect that validates a term, by the union that holds it."""


def _unit(unit: Any) -> Iterator[tuple[str, str | None, Any, str, Any]]:
    """Every record of a unit's tree, as C's `_walk` gives it, from its `body`."""
    return _walk(Objects.properties(unit).get("body"), "body", None, _HOLDERS)


def _a(noun: str) -> str:
    """A noun with its article, as C's (`Programs.C.Check`), but `a` before a `U` read as `you` (`a Using...`)."""
    return f"a {noun}" if noun.startswith("Us") else C._a(noun)


def check(store: Any, path: str, version: Version | str) -> list[str]:
    """The problems of the constructs the unit at `path` uses that `version` lacks, in source order, each once and
    located by its place: `body[0]: ConceptDefinition needs C++20`. `version` is `(17,)`, `(20,)` or `(23,)`, or the
    common name or the designation the language covers an edition by (`"C++23"`, `"ISO/IEC 14882:2024"`). Raises
    LookupError where the workspace holds no file at `path`, or the language covers no such edition (the store not
    prepared, `Standards.prepare`, among them)."""
    return _read(store, path, lambda unit: check_file(store, unit, version))


def check_file(store: Any, unit: Any, version: Version | str) -> list[str]:
    """`check` of a unit's visitor, a `Programs.Cpp.TranslationUnit` of `store`, read within the caller's
    transaction."""
    edition = f"C++{version[0]}" if isinstance(version, tuple) and len(version) == 1 else str(version)
    return _check(_Availability(store, LANGUAGE, edition, DIALECTS), _unit(unit))


# --- Validity ---

_NEEDS = {
    "Comment": ("text",), "Directive": ("directive",), "IfStatement": ("consequence",),
    "SwitchStatement": ("condition", "body"), "WhileStatement": ("condition", "body"),
    "DoStatement": ("body", "condition"), "ForStatement": ("body",), "LabeledStatement": ("label",),
    "CaseStatement": ("value",), "AttributedStatement": ("statement",), "AsmDeclaration": ("keyword", "template"),
    "AsmOperand": ("constraint", "value"), "FunctionDefinition": ("declarator", "body"),
    "StaticAssertDeclaration": ("keyword", "condition"), "InitDeclarator": ("declarator",),
    "RangeForStatement": ("declaration", "range", "body"), "TryStatement": ("body",), "Handler": ("parameter", "body"),
    "NamespaceName": ("name",), "NamespaceAliasDefinition": ("name", "target"), "UsingDirective": ("name",),
    "UsingDeclarator": ("name",), "UsingEnumDeclaration": ("type",), "AliasDeclaration": ("name", "type"),
    "LinkageSpecification": ("language",), "TemplateDeclaration": ("declaration",),
    "ExplicitInstantiation": ("declaration",), "ConceptDefinition": ("name", "constraint"),
    "MemberInitializer": ("member", "initializer"), "ModuleDeclaration": ("name",), "AccessSpecifier": ("access",),
}
"""The properties each kind needs set: those 0.3's validation required, not being optional."""

_LISTS = {"AttributedStatement": ("attributes", "an attribute"), "AttributeDeclaration": ("attributes", "an attribute"),
          "TryStatement": ("handlers", "a handler"), "UsingDeclaration": ("declarators", "a declarator")}
"""The lists each kind needs to hold an element, by kind: the list's property, and what it needs."""

_CHOICES = {("StaticAssertDeclaration", "keyword"): ("static_assert",),
            ("AsmDeclaration", "keyword"): ("asm", "__asm__", "__asm"),
            ("AccessSpecifier", "access"): ("public", "protected", "private")}
"""The words a kind's property may be, by the kind and the property's name, as 0.3 had them."""

_DANGLING = {"IfStatement": "consequence", "WhileStatement": "body", "ForStatement": "body", "SwitchStatement": "body",
             "RangeForStatement": "body", "LabeledStatement": "statement", "CaseStatement": "statement",
             "DefaultStatement": "statement", "AttributedStatement": "statement"}
"""The statements that end with a statement of their own, by the property that holds it."""


def _dangles(statement: Any) -> bool:
    """Whether a statement ends with an `if` without `else`, which would take an `else` written after it."""
    while statement is not None:
        _, _, record = _branch(statement)
        kind, held = _kind(record), Objects.properties(record)
        if kind not in _DANGLING:
            return False
        if kind == "IfStatement" and "alternative" not in held:
            return True
        statement = held.get("alternative" if kind == "IfStatement" else _DANGLING[kind])
    return False


def _rules(kind: str, held: dict[str, Any]) -> list[str]:
    """A statement's, a member's or a part's own problems, given its kind and its properties that are set."""
    problems = [f"{_a(kind)} needs {_a(name)}" for name in _NEEDS.get(kind, ()) if name not in held]
    if kind in _LISTS and not (_LISTS[kind][0] in held and held[_LISTS[kind][0]].values):
        problems.append(f"{_a(kind)} needs {_LISTS[kind][1]}")
    problems += [f"{kind}.{name} cannot be {held[name]!r}" for (owner, name), words in _CHOICES.items()
                 if owner == kind and name in held and held[name] not in words]
    if kind == "IfStatement" and "condition" not in held and not held.get("consteval"):
        problems.append("an IfStatement needs a condition")
    if kind == "IfStatement" and held.get("negated") and not held.get("consteval"):
        problems.append("an IfStatement negated needs consteval")
    if kind == "GotoStatement" and "label" not in held and "target" not in held:
        problems.append("a GotoStatement needs a label or a target")
    if kind == "MemberDeclarator" and "declarator" not in held and "bitfield" not in held:
        problems.append("a MemberDeclarator needs a declarator or a bitfield")
    if kind == "ImportDeclaration" and not {"name", "partition", "header"} & set(held):
        problems.append("an ImportDeclaration needs a name, a partition or a header")
    if kind == "FunctionDefinition" and "declarator" in held and C._binder(held["declarator"])[0] != (
            "functiondeclarator"):
        problems.append("a FunctionDefinition's declarator declares no function")
    if kind == "IfStatement" and "alternative" in held and _dangles(held.get("consequence")):
        problems.append("an if without else ends the consequence, and would take the else")
    return problems


def _validated(term: Any) -> list[str]:
    """A term's problems, as the dialect whose union holds it validates it."""
    return _DIALECTS[term.as_schema().name].validate(term, _bound(term))


def _term_problems(value: Any, tag: str, record: Any) -> list[str]:
    """The problems of the outermost term or helper of mbse-expressions' that a statement or a part holds: a term's, as
    its dialect validates it; a helper's, its own checks, in C++, and its terms' as their dialect validates them."""
    if Terms.is_term(value):
        return _validated(value)
    own = Kinds.problems(Terms.node(tag, record), Domains.Types(record, "Cpp.Expressions"),
                         CppExpressions.SUFFIXES, CppExpressions.PREFIXES, "C++")
    return own + [problem for term in _terms(record, _HOLDERS) for problem in _validated(term)]


def _validate(unit: Any) -> list[str]:
    problems: list[str] = []
    for where, root, value, tag, record in _unit(unit):
        if root is None:
            kind, held = _kind(record), Objects.properties(record)
            if kind == "Error":
                problems += [f"{where}: {p}" for p in Terms.invalid_problems("error", held)]
            problems += [f"{where}: {p}" for p in _rules(kind, held)]
        elif root == where:
            problems += [f"{where}: {p}" for p in _term_problems(value, tag, record)]
    return problems


def validate(store: Any, path: str) -> list[str]:
    """The problems of the unit at `path` as a tree, in source order, each located by its place: its kinds' own rules,
    and its terms' problems as their dialects validate them, those that need an ABI deferred. Raises LookupError where
    the workspace holds no file at `path`."""
    return _read(store, path, validate_file)


def validate_file(unit: Any) -> list[str]:
    """`validate` of a unit's visitor, read within the caller's transaction."""
    return Domains.Reading(None).run(lambda: _validate(unit))


def validate_for(store: Any, path: str, abi: str) -> list[str]:
    """`validate` of the unit at `path` with the ABI dialect named `abi` applied (`ABIS`): what `validate` defers, each
    literal's type and range, checked under that target. The store must hold the ABI (`prepare_abi`). Raises
    LookupError where the workspace holds no file at `path`, or the store no such ABI."""
    return _read(store, path, lambda unit: validate_file_for(store, unit, abi))


def validate_file_for(store: Any, unit: Any, abi: str) -> list[str]:
    """`validate_for` of a unit's visitor, read within the caller's transaction."""
    return _applied(store, unit, abi, _validate)
