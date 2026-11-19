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
kind, where one of `Cpp`'s or `Cpp Types`' does (`Standards.DIALECTS`): C++20's `requires`, `co_await`, `co_yield`
and designated initializers. A kind no standard lists is not checked: GNU's extensions, a part or a helper, C
Preprocessor's directives (whose standards are C's alone, a gap of mbse-expressions', reported), and invalid syntax, a
`Programs.Cpp.Error` and an `error` or `missing` term, which `validate` reports, as C's *(agent)*. A kind's problem is
`<kind> needs <the first edition that has it>`.

What a property's value makes available stays code, by the kind that holds it, as C's: a standard tags a kind, not a
property or a value of one *(agent)*. From the 0.3 language's data (`Ccpp/Syntax.py`, `SINCE` and `FEATURES`, C++'s
since C++17; what C++17 has, every edition has):

- statements, declarations, clauses and parts, `STATEMENT_FEATURES`: `if consteval` (C++23); a range-based `for`'s
  initializer (C++20); an alias declaration as an init-statement (C++23); a label, a `case` or a `default` without a
  statement or before a declaration (C++23); a trailing `requires` of a function's definition, a declarator or a
  member's declarator, and a template's `requires` (C++20); a bit-field's default member initializer (C++20); a nested
  namespace's name `inline` (C++20); and, beyond 0.3's data, a `static` `operator()` or `operator[]` (C++23)
  *(agent)*;
- terms and helpers, `FEATURES`: `consteval` and `constinit` (C++20), `char8_t` (C++20), `<=>` and `operator<=>`, and
  `operator co_await` (C++20), a lambda's template parameters (C++20) and attributes (C++23), its `requires` (C++20), a
  pack init-capture (C++20), a constrained placeholder, `Number auto` (C++20), a type parameter's constraint (C++20), a
  template template parameter's `requires` (C++20), an explicit object parameter (C++23), structured bindings (C++17)
  and `explicit(condition)` (C++20); and, beyond 0.3's data, `__has_include` (C++17), a
  static lambda (C++23), a subscript of several indices (C++23), `auto(x)` and `auto{x}` (C++23), the literal suffixes
  `z` and `uz` (C++23), and C Preprocessor's `#elifdef`, `#elifndef` and `#warning` (C++23), whose dialect records C's
  editions only *(agent)*.

Not checked: what an edition removed (`register`, dynamic exception specifications), as `check` lists what an edition
lacks, not what it dropped; and an abbreviated function template's `auto` parameter (C++20), which `check` cannot
tell from a generic lambda's (C++14) without its context *(agent)*.

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

from collections.abc import Callable, Iterator
from typing import Any

from mbse.Expressions.C.Expressions import Domains, Kinds
from mbse.Expressions.C.Preprocessor import Expressions as CPreprocessor
from mbse.Expressions.Cpp.Expressions import Expressions as CppExpressions
from mbse.Expressions.Cpp.Types import Expressions as CppTypes
from mbse.Expressions.Framework import Objects, Terms

from ..C import Check as C
from ..C.Check import ABIS, _applied, _Availability, _bound, _branch, _kind, _read, _terms, _unique, _walk, prepare_abi
from .Standards import DIALECTS
from .Statements import KINDS, LANGUAGE

__all__ = ["check", "check_file", "validate", "validate_file", "validate_for", "validate_file_for", "prepare_abi",
           "ABIS", "FEATURES", "STATEMENT_FEATURES"]

Version = tuple[int, ...]
Found = list[tuple[str, str]]

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


def _many(held: Any) -> tuple[Any, ...]:
    return () if held is None else held.values


def _record(value: Any) -> tuple[str, dict[str, Any]]:
    """What a property holds, through unions: its tag and its properties."""
    _, tag, record = _branch(value)
    return tag, Objects.properties(record)


# --- Features ---

def _word(name: str, words: dict[str, str]) -> Callable[[str, dict[str, Any]], Found]:
    """The features of a kind's property `name`, a word: each word's, and the edition it arrived in."""
    def found(tag: str, held: dict[str, Any]) -> Found:
        word = held.get(name)
        return [(f"{tag}.{name} {word!r}", words[word])] if word in words else []
    return found


def _set(name: str, edition: str) -> Callable[[str, dict[str, Any]], Found]:
    """The feature of a kind's property `name`, set and not empty, which arrived in `edition`."""
    def found(tag: str, held: dict[str, Any]) -> Found:
        value = held.get(name)
        empty = value is None or isinstance(value, Objects.Listed) and not value.values
        return [] if empty else [(f"{tag}.{name}", edition)]
    return found


def _lambda_declarator(tag: str, held: dict[str, Any]) -> Found:
    words = [_record(s)[1].get("keyword") for s in _many(held.get("specifiers"))]
    return _set("requires", "C++20")(tag, held) + ([(f"{tag} static", "C++23")] if "static" in words else [])


def _literal(tag: str, held: dict[str, Any]) -> Found:
    suffix = str(held.get("suffix") or "").lower()
    return [(f"{tag}.suffix {held['suffix']!r}", "C++23")] if suffix in ("z", "uz", "zu") else []


FEATURES: dict[str, Callable[[str, dict[str, Any]], Found]] = {
    "declspecifier": _word("keyword", {"consteval": "C++20", "constinit": "C++20"}),
    "primitivetypespecifier": _word("keyword", {"char8_t": "C++20"}),
    "binaryexpression": _word("operator", {"<=>": "C++20"}),
    "operatorname": _word("operator", {"<=>": "C++20", "co_await": "C++20"}),
    "lambdaexpression": lambda tag, held: _set("template_parameters", "C++20")(tag, held) + _set(
        "attributes", "C++23")(tag, held),
    "lambdadeclarator": _lambda_declarator,
    "initcapture": lambda tag, held: [(f"{tag}.pack", "C++20")] if held.get("pack") else [],
    "placeholdertypespecifier": _set("constraint", "C++20"),
    "typeparameter": _set("constraint", "C++20"),
    "templatetemplateparameter": _set("requires", "C++20"),
    "parameterdeclaration": lambda tag, held: [(f"{tag}.this_keyword", "C++23")] if held.get("this_keyword") else [],
    "subscriptexpression": lambda tag, held: [(f"{tag} of several indices", "C++23")] if len(
        _many(held.get("indices"))) > 1 else [],
    "functionalcastexpression": lambda tag, held: [(f"{tag} of auto", "C++23")] if _record(held["type"])[0] == (
        "placeholdertypespecifier") else [],
    "literal": _literal,
    "explicitspecifier": _set("condition", "C++20"),
    "structuredbindingdeclarator": lambda tag, held: [(tag, "C++17")],
    "hasincludeexpression": lambda tag, held: [(tag, "C++17")],
    "elifdefdirective": lambda tag, held: [(tag, "C++23")],
    "otherdirective": lambda tag, held: [("#warning", "C++23")] if held.get("directive") == "warning" else [],
}
"""The features of a term or a helper that its properties' values make, by its kind (its tag, or its helper's), given
its tag and its properties that are set: each feature's name, and the edition it arrived in, by its common name *(agent: code until
mbse-expressions records them)*."""


def _alias(kind: str, held: dict[str, Any]) -> Found:
    """An alias declaration as an init-statement (C++23)."""
    initializer = held.get("initializer")
    return [(f"{kind} with an alias declaration as its init-statement", "C++23")] if initializer is not None and (
        _record(initializer)[0] == "aliasdeclaration") else []


def _labeled(kind: str, held: dict[str, Any]) -> Found:
    """A label's features: without a statement, or before a declaration (C++23)."""
    if "statement" not in held:
        return [(f"{kind} without a statement", "C++23")]
    return [(f"{kind} before a declaration", "C++23")] if _record(held["statement"])[0] in (
        "simpledeclaration", "staticassertdeclaration", "aliasdeclaration", "attributedeclaration") else []


def _requires(kind: str, held: dict[str, Any]) -> Found:
    return [(f"{kind}.requires", "C++20")] if "requires" in held else []


def _operator(kind: str, held: dict[str, Any]) -> Found:
    """A `static` `operator()` or `operator[]` (C++23)."""
    words = [_record(s)[1].get("keyword") for s in _many(held.get("specifiers"))]
    declarators = [held["declarator"]] if "declarator" in held else [
        Objects.properties(d).get("declarator") for d in _many(held.get("declarators"))]
    operators = [_named(d) for d in declarators if d is not None]
    return [(f"{kind} static {operator}", "C++23") for operator in operators if "static" in words and operator in (
        "operator()", "operator[]")]


def _named(declarator: Any) -> str | None:
    """The operator's name a declarator declares (`operator()`); None for any other."""
    tag, held = _record(declarator)
    if tag == "iddeclarator":
        name, fields = _record(held["name"])
        return f"operator{fields['operator']}" if name == "operatorname" else None
    return _named(held["declarator"]) if "declarator" in held else None


STATEMENT_FEATURES: dict[str, Callable[[str, dict[str, Any]], Found]] = {
    "IfStatement": lambda kind, held: ([(f"{kind}.consteval", "C++23")] if held.get("consteval") else []) + _alias(
        kind, held),
    "SwitchStatement": _alias, "ForStatement": _alias,
    "RangeForStatement": lambda kind, held: _alias(kind, held) or ([(f"{kind}.initializer", "C++20")] if (
        "initializer" in held) else []),
    "LabeledStatement": _labeled, "CaseStatement": _labeled, "DefaultStatement": _labeled,
    "FunctionDefinition": lambda kind, held: _requires(kind, held) + _operator(kind, held),
    "MemberDeclaration": _operator, "InitDeclarator": _requires, "TemplateDeclaration": _requires,
    "MemberDeclarator": lambda kind, held: _requires(kind, held) + ([(f"{kind} with a bit-field's initializer", "C++20")]
                                                                     if "bitfield" in held and "initializer" in held
                                                                     else []),
    "NamespaceDefinition": lambda kind, held: [(f"{kind} with an inline nested name", "C++20")] if any(
        Objects.properties(n).get("inline") for n in _many(held.get("names"))) else [],
}
"""The features of a statement, a member or a part that its properties' values make, by its kind, given its kind and its
properties that are set: each feature's name, and the edition it arrived in *(agent: code, as a standard tags a kind,
not a property)*."""


# --- Editions ---

def _check(available: _Availability, unit: Any) -> list[str]:
    problems: list[str] = []
    for where, root, _, tag, record in _unit(unit):
        schema, held = record.as_schema().name, Objects.properties(record)
        if root is None:  # a statement, a member, an error or a part, at its place
            kind = _kind(record)
            found = available.kind(schema, kind)
            found += available.features(STATEMENT_FEATURES.get(kind, lambda *_: [])(kind, held))
        else:  # within a term or a helper, at the outermost's place
            found = available.kind(schema, tag)
            found += available.features(FEATURES.get(tag, lambda *_: [])(tag, held))
        problems += [f"{where if root is None else root}: {problem}" for problem in found]
    return _unique(problems)


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
    return _check(_Availability(store, LANGUAGE, edition, DIALECTS), unit)


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
