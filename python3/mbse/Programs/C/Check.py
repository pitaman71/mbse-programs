"""Check: which editions of C have the constructs a stored translation unit uses, and whether it is a valid one.

A unit is a `Programs.C.TranslationUnit` that `Programs.Framework.TheWorkspace` owns by its path, as `Parse` writes it.
Both functions read it, within the transaction open on `store` or, where none is, within one of their own, and write
nothing; each raises LookupError where the workspace holds no file at `path`.

- `check(store, path, version)`: the problems of the constructs the unit uses that `version` lacks, in source order,
  each once. `version` is an edition of C, by its common name (`"C23"`), its designation (`"ISO/IEC 9899:2024"`) or
  the number its common name gives, as a tuple (`(23,)`) *(agent: as TypeScript5's `(5, 9)` and Python3's `(3, 12)`
  give their versions)*; LookupError where the language covers none such. The store must hold the standards
  (`Standards.prepare`).
- `validate(store, path)`: the unit's problems as a tree, in source order: each kind's own rules, ported from the 0.3
  language's validation, and its terms' problems, as their dialects validate them.

Each problem is located by its place in the unit's value, as `Definitions` anchors it, its steps joined by `.` as
TypeScript5's `Check` joins them *(agent)*: a statement's, declaration's or member declaration's is the property of what
holds it, with its index where that holds a list, from the unit's `body` (`body[2]`, `body[0].consequence`,
`body[3].body.body[0]`, a K&R definition's `body[1].declarations[0]`); a part's that holds no statement, its statement's
then its property (`body[0].declarators[1]`); a term's, helper's or kind's record of mbse-expressions', the place of the
outermost one that holds it, within its statement or its part (`body[0].expression`,
`body[0].declarators[0].initializer`, `body[2].specifiers[0]`, `body[1].declarators[0].declarator`). Statements
within a term, a statement expression's `block`, a struct's or a union's `members` and a conditional directive's
`group`, are located through the term's place, as `Definitions` anchors them: a struct's member declarations are
`body[0].specifiers[0].members.members[1]`, a directive's group's statements `body[3].directive.group.body[0]`. So:
`body[2]: StaticAssertDeclaration.keyword 'static_assert' needs C23`, `body[0].specifiers[0]: bitintspecifier needs
C23`. mbse-expressions' term readers stop where a term holds statements (`Terms.boundaries`): this module reads records
itself (`Objects.properties`, `Terms.kind_of`), as `Definitions` does, and reads what a block, a member list or a group
holds as statements.

What an edition has is read from data, as mbse-expressions records it (mbse-basis [CAP-268: standards as tagged data](mbse:mbse-basis/docs/capabilities/CAP-268.md#decided)):
a statement, declaration or member kind is available where a standard of that edition's designation, among those
`Programs.C` covers, lists its schema (`Standards`); a term's kind, where one of those of `C`, `C Types` or `C
Preprocessor` does (`Standards.DIALECTS`): C23's attribute declarations, `nullptr` (a `constant`) and `#elifdef`; and
`_Pragma("...")`, C Preprocessor's `pragmaexpression`, which every edition has. A kind no standard lists is not
checked: GNU's extensions (`asm`, a statement expression, `__extension__`, a label as a value, `&&l`, C's
`labeladdressexpression`), outside every edition, as mbse-expressions' `C` marks them, a part or a helper (GNU's asm
label, C Types' `AsmLabel`, among them), and invalid syntax, a `Programs.C.Error` and an `error` or `missing` term,
which `validate` reports *(agent)*. A kind's problem is `<kind> needs <the first edition that
has it>`: a statement's kind by its name (`AttributeDeclaration`), a term's by its tag (`constant`).

What a property's value makes available stays code, by the kind that holds it: a standard tags a kind, not a property
or a value of one *(agent)*. As the 0.3 language had them, C's (`Ccpp/Syntax.py`, `SINCE` and `FEATURES`; what arrived
before C11, as `restrict`, `inline` and designators, and C11's own, as `_Alignas`, `_Atomic`, `_Generic`,
`_Noreturn`, `_Static_assert` and `_Thread_local`, every edition has):

- statements, declarations and parts, `STATEMENT_FEATURES`: a label, a `case` or a `default` without a statement (C23);
  `static_assert` spelled so, and without a message (C23); and, beyond 0.3's data, a label before a declaration (C23,
  6.8.2), a function's definition with an unnamed parameter of its own (C23, 6.9.1), and a declaration whose type is
  inferred, `auto` with no type specifier (C23, 6.7.10), which `Parse` writes as the keyword `auto` *(agent)*;
- terms and helpers, `FEATURES`, which mbse-expressions does not record (a gap, reported there): C23's keywords as
  specifiers (`thread_local`, `constexpr`, `bool`, `_Decimal32` to `_Decimal128`), `typeof` and `typeof_unqual`,
  `_BitInt`, `auto` as C Types' `placeholdertypespecifier`, an enumeration's underlying type, attributes in `[[ ]]`,
  `alignas` and `alignof` spelled so, a `u8` character, `#warning` and `#embed`; and, beyond 0.3's data, a literal's
  digit separators, a binary integer, `true` and `false`, the suffix `wb` and the decimal floating suffixes, `_Float16`
  to `_Float128x` (C23's Annex H), and an empty initializer, `{}` (C23) *(agent)*.

Not checked: what C23 removed (a K&R definition, an old-style declaration of a function without a prototype), as
`check` lists what an edition lacks, not what it dropped; and trigraphs, which `Parse` keeps as tree-sitter reads them.

`validate`'s rules, each the 0.3 rule where one stands, located at the statement, member declaration or part:

- what a kind needs: a property, as 0.3's validation required each that is not optional (`an IfStatement needs a
  condition`, `a FunctionDefinition needs a body`, `an AsmOperand needs a constraint`), a list that is not empty (`an
  AttributeDeclaration needs an attribute`), and what goes together (`a GotoStatement needs a label or a target`, `a
  MemberDeclarator needs a declarator or a bitfield`); and, beyond 0.3's, `a SimpleDeclaration needs a specifier`, as
  for a member declaration and a function's definition: C99 removed the implicit `int`, and a function's definition's
  declarator declaring a function (`int m { ... }`), which the schemas hold where a unit is built, and which `Parse`
  keeps as invalid syntax where tree-sitter reads one (its departure 36) *(agent)*; a kind's word one
  of its choices (`StaticAssertDeclaration.keyword cannot be 'assert'`); and the dangling `else`, an `if` without one
  ending the consequence of an `if` with one;
- invalid syntax, as the user decided that a parse keeps it and validation reports it: each `Programs.C.Error`,
  `invalid syntax '<its text>'`, as mbse-expressions words an `error` term's (`Terms.invalid_problems`), located at the
  error; an `error` or `missing` term as its dialect validates it, below. An `Error` may stand wherever a statement or
  a member declaration may, and holds statements in its `body`, each of which is checked as one *(agent)*;
- terms: each term a statement or a part holds, as its dialect validates it (`C`'s, `C Types`' or `C Preprocessor`'s
  `DIALECT.validate`, each reading the others); a helper a statement holds alone (a specifier, a declarator, an
  attribute specifier), by its own checks (`C.Expressions.Kinds.problems`: an identifier's spelling, a literal's
  value) and its terms as their dialect validates them. The names a term refers to are taken as bound *(agent)*:
  binding them is the unit's, which `Definitions` resolves, not a term's. A literal of a type C leaves to the
  implementation (`1`'s `int`, `L'w'`'s `wchar_t`) is not checked against its range: mbse-expressions reads such a
  type from an ABI that a term's holder names, and a unit names none (a gap, reported), so the problem it gives, "'int'
  is not a type C defines, and its expression names no ABI", is dropped, as CPRS-01 drops it *(agent)*.

Dropped, as the model now holds them: a property's type and a child's category, and where a statement or a member
declaration may stand (a struct's members hold only member declarations, a block no member declaration), which the
schemas check on write; every rule on terms, which mbse-expressions' dialects own.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from mbse.Expressions.C.Expressions import Domains, Expressions as CExpressions, Kinds
from mbse.Expressions.C.Preprocessor import Expressions as CPreprocessor
from mbse.Expressions.C.Types import Expressions as CTypes
from mbse.Expressions.Framework import Objects, Standards as ExpressionStandards, Terms
from mbse.Schemas.Framework import Schemas as SchemaKinds

from ..Framework.Model import WORKSPACE
from .Standards import DIALECTS
from .Statements import KINDS, LANGUAGE

__all__ = ["check", "check_file", "validate", "validate_file", "FEATURES", "STATEMENT_FEATURES"]

Version = tuple[int, ...]

_STATEMENTS = frozenset(f"{LANGUAGE}.{kind}" for kind in (*KINDS, "Error", "MemberList", "Group", "MemberGroup"))
"""The schemas that have a statement's place: statements, declarations, member declarations, invalid syntax and the
parts that hold them."""
_EXPRESSIONS = "Expressions."
"""What mbse-expressions' schemas' names begin with: its terms', helpers' and kinds'."""
_DIALECTS = {"Expressions.C.Expressions.Term": CExpressions.DIALECT, "Expressions.C.Types.Term": CTypes.DIALECT,
             "Expressions.C.Preprocessor.Term": CPreprocessor.DIALECT}
"""The dialect that validates a term, by the union that holds it."""
_NO_ABI = "and its expression names no ABI"
"""How mbse-expressions words a type it cannot read without an ABI (`int`), which a unit names none of."""


# --- Reading ---

def _branch(value: Any) -> tuple[Any, str, Any]:
    """What a property holds, through unions of unions: a term, its tag and its record; or a record, its kind's name in
    lower case (`identifier`, `simpledeclaration`) and itself."""
    if Terms.is_term(value):
        return (value, *Terms.kind_of(value))
    if isinstance(value.as_schema(), SchemaKinds.OfUnion.Data):
        ((_, held),) = Objects.properties(value).items()
        return _branch(held)
    return value, value.as_schema().name.rsplit(".", 1)[-1].lower(), value


def _walk(value: Any, where: str, root: str | None) -> Iterator[tuple[str, str | None, Any, str, Any]]:
    """Every record within what a property holds, parents first, in source order: each its place, the place of the
    outermost term, helper or kind's record of mbse-expressions' holding it (None for a statement, a member
    declaration, an error, a part holding statements or a part), the term or record itself, its tag and its record. A
    statement within a term, where its block, its member list or its group holds one, is one of them, at its place."""
    if isinstance(value, Objects.Listed):
        for i, element in enumerate(value.values):
            yield from _walk(element, f"{where}[{i}]", root)
        return
    if not hasattr(value, "as_schema"):
        return  # a scalar
    value, tag, record = _branch(value)
    name = record.as_schema().name
    if name in _STATEMENTS:
        root = None
    elif root is None and name.startswith(_EXPRESSIONS):
        root = where
    yield where, root, value, tag, record
    for prop, held in Objects.properties(record).items():
        yield from _walk(held, f"{where}.{prop}", root)


def _unit(unit: Any) -> Iterator[tuple[str, str | None, Any, str, Any]]:
    """Every record of a unit's tree, as `_walk` gives it, from its `body`."""
    return _walk(Objects.properties(unit).get("body"), "body", None)


def _read(store: Any, path: str, read: Callable[[Any], list[str]]) -> list[str]:
    """`read` of the unit at `path`, within a transaction of its own, so called with none open on `store`, as the user
    decided that whether one is open is no flag on the store (mbse-basis CAP-315)."""
    with store.transaction():
        return read(store.singleton(WORKSPACE).files({"path": path}))  # LookupError, where it holds none


def _kind(record: Any) -> str:
    """A statement's, member declaration's or part's kind: its schema's name, without its language's
    (`IfStatement`)."""
    return record.as_schema().name.rsplit(".", 1)[-1]


def _a(noun: str) -> str:
    return f"{'an' if noun[0].lower() in 'aeiou' else 'a'} {noun}"


def _unique(problems: list[str]) -> list[str]:
    return list(dict.fromkeys(problems))


# --- Features ---

def _keyword(words: dict[str, str]) -> Callable[[Terms.Node], list[tuple[str, str]]]:
    """The features of a kind's keyword: each word's, and the edition it arrived in."""
    def found(node: Terms.Node) -> list[tuple[str, str]]:
        word = node.attributes.get("keyword")
        return [(f"{node.kind}.keyword {word!r}", words[word])] if word in words else []
    return found


def _arrived(edition: str) -> Callable[[Terms.Node], list[tuple[str, str]]]:
    """A helper's own feature: the kind itself, which arrived in `edition`."""
    return lambda node: [(node.kind, edition)]


_DECIMAL = ("df", "dd", "dl")


def _literal(node: Terms.Node) -> list[tuple[str, str]]:
    held = node.attributes
    found = [("literal with digit separators", "C23")] if held.get("separators") else []
    found += [("literal.base 2", "C23")] if held.get("base") == 2 else []
    suffix = str(held.get("suffix", "")).lower()
    found += [(f"literal.suffix {held['suffix']!r}", "C23")] if "wb" in suffix or suffix in _DECIMAL else []
    found += [("literal.prefix 'u8' of a character", "C23")] if held.get("prefix") == "u8" and held.get(
        "quote") == "'" else []
    return found + ([(f"literal {held['text']!r}", "C23")] if held.get("text") in ("true", "false") else [])


_FLOATS = ("_Float16", "_Float32", "_Float64", "_Float128", "_Float32x", "_Float64x", "_Float128x")

FEATURES: dict[str, Callable[[Terms.Node], list[tuple[str, str]]]] = {
    "literal": _literal,
    "initializerlist": lambda node: [("initializerlist without items", "C23")] if not node.many else [],
    "alignofexpression": _keyword({"alignof": "C23"}),
    "declspecifier": _keyword({"thread_local": "C23", "constexpr": "C23"}),
    "primitivetypespecifier": _keyword({"bool": "C23", "_Decimal32": "C23", "_Decimal64": "C23", "_Decimal128": "C23",
                                        **{word: "C23" for word in _FLOATS}}),
    "typeofspecifier": _keyword({"typeof": "C23", "typeof_unqual": "C23"}),
    "bitintspecifier": _arrived("C23"), "placeholdertypespecifier": _arrived("C23"),
    "standardattributespecifier": _arrived("C23"),
    "enumspecifier": lambda node: [("enumspecifier.base", "C23")] if node.subterms.get("base") is not None else [],
    "alignasspecifier": _keyword({"alignas": "C23"}),
    "otherdirective": lambda node: [(f"#{node.attributes['directive']}", "C23")] if node.attributes.get(
        "directive") in ("warning", "embed") else [],
}
"""The features of a term or a helper that its properties' values make, by its kind (its tag, or its helper's): each
feature's name, and the edition it arrived in, by its common name *(agent: code until mbse-expressions records
them)*."""


def _labeled(kind: str, held: dict[str, Any]) -> list[tuple[str, str]]:
    """A label's features: without a statement, or before a declaration (C23)."""
    if "statement" not in held:
        return [(f"{kind} without a statement", "C23")]
    labeled = _kind(_branch(held["statement"])[2])
    return [(f"{kind} before a declaration", "C23")] if labeled in (
        "SimpleDeclaration", "StaticAssertDeclaration", "AttributeDeclaration") else []


def _assertion(kind: str, held: dict[str, Any]) -> list[tuple[str, str]]:
    found = [(f"{kind}.keyword 'static_assert'", "C23")] if held.get("keyword") == "static_assert" else []
    return found + ([(f"{kind} without a message", "C23")] if "message" not in held else [])


_UNTYPED = ("declspecifier", "cvqualifier", "standardattributespecifier", "alignasspecifier", "gnuattributespecifier",
            "declspecspecifier")
"""The specifiers that name no type: storage classes, function specifiers and qualifiers, and attributes."""


def _inferred(kind: str, held: dict[str, Any]) -> list[tuple[str, str]]:
    """A declaration's type inferred (C23, 6.7.10): `auto` and no type specifier."""
    specifiers = [_branch(specifier) for specifier in (held["specifiers"].values if "specifiers" in held else ())]
    words = [Objects.properties(record).get("keyword") for _, _, record in specifiers]
    inferred = "auto" in words and all(tag in _UNTYPED for _, tag, _ in specifiers)
    return [(f"{kind} with an inferred type", "C23")] if inferred else []


def _unnamed(parameter: Any) -> bool:
    """Whether a parameter of a function's definition is unnamed: an ellipsis and a lone `void` are none."""
    _, tag, record = _branch(parameter)
    held = Objects.properties(record)
    if tag != "parameterdeclaration" or "declarator" in held:
        return False
    keywords = [Objects.properties(_branch(s)[2]).get("keyword") for s in held["specifiers"].values]
    return keywords != ["void"]


def _named(declarator: Any) -> bool:
    """Whether a declarator is, within its parentheses, the identifier it declares."""
    _, tag, record = _branch(declarator)
    while tag == "parenthesizeddeclarator":
        _, tag, record = _branch(Objects.properties(record)["declarator"])
    return tag == "iddeclarator"


def _binder(declarator: Any) -> tuple[str, dict[str, Any]]:
    """The declarator nearest the name a declarator declares, but parentheses, its tag and its properties: a function's
    declarator, where it declares a function, not that of the type a function returns."""
    _, tag, record = _branch(declarator)
    while "declarator" in (fields := Objects.properties(record)) and not _named(fields["declarator"]):
        _, tag, record = _branch(fields["declarator"])
    return tag, fields


def _definition(kind: str, held: dict[str, Any]) -> list[tuple[str, str]]:
    """A function's definition's features: a parameter of its own unnamed (C23), not one of the type it returns."""
    tag, fields = _binder(held["declarator"])
    parameters = fields["parameters"].values if "parameters" in fields else ()
    unnamed = tag == "functiondeclarator" and any(map(_unnamed, parameters))
    return [(f"{kind} with an unnamed parameter", "C23")] if unnamed else []


STATEMENT_FEATURES: dict[str, Callable[[str, dict[str, Any]], list[tuple[str, str]]]] = {
    "LabeledStatement": _labeled, "CaseStatement": _labeled, "DefaultStatement": _labeled,
    "StaticAssertDeclaration": _assertion, "FunctionDefinition": _definition, "SimpleDeclaration": _inferred,
}
"""The features of a statement, a member declaration or a part that its properties' values make, by its kind, given its
kind and its properties that are set: each feature's name, and the edition it arrived in, by its common name *(agent:
code, as a standard tags a kind, not a property)*."""


# --- Editions ---

def _year(standard: Any) -> int:
    """A stored edition's revision's year: 2024."""
    return ExpressionStandards.properties(standard)["revision"][1]  # type: ignore[no-any-return, index]


class _Availability:
    """What the store's standards say: the target edition's year, each kind's schema's editions' years, by its schema's
    name, and each edition's year and common name."""

    def __init__(self, store: Any, version: Version | str):
        language = store.singleton(LANGUAGE)
        tag = f"C{version[0]}" if isinstance(version, tuple) and len(version) == 1 else str(version)
        target = ExpressionStandards.find(language, tag)
        if target is None:
            raise LookupError(f"{LANGUAGE} covers no edition {version!r}: run Standards.prepare on the store")
        self.target = _year(target)
        self.years = {ExpressionStandards.properties(s)["names"][0]: _year(s)  # type: ignore[index]
                      for s in ExpressionStandards.standards(language).values()}
        self.names = {year: name for name, year in self.years.items()}
        self.versions: dict[str, set[int]] = {}
        for dialect in DIALECTS:
            standards = ExpressionStandards.standards(store.singleton(dialect))
            if not standards:
                raise LookupError(f"{dialect} covers no edition: run Standards.prepare on the store")
            for standard in standards.values():
                for kind in ExpressionStandards.kinds(standard):
                    self.versions.setdefault(kind.name, set()).add(_year(standard))

    def kind(self, schema: str, what: str) -> list[str]:
        """The problem of a kind, by its schema's name, that the target lacks: none where it has it, or where no
        standard lists it."""
        versions = self.versions.get(schema)
        if not versions or self.target in versions:
            return []
        return [f"{what} needs {self.names[min(versions)]}"]

    def features(self, found: list[tuple[str, str]]) -> list[str]:
        return [f"{feature} needs {edition}" for feature, edition in found if self.target < self.years[edition]]


def _check(available: _Availability, unit: Any) -> list[str]:
    problems: list[str] = []
    for where, root, _, tag, record in _unit(unit):
        schema = record.as_schema().name
        if root is None:  # a statement, a member declaration, an error or a part, at its place
            kind = _kind(record)
            found = available.kind(schema, kind)
            found += available.features(STATEMENT_FEATURES.get(kind, lambda *_: [])(kind, Objects.properties(record)))
        else:  # within a term or a helper, at the outermost's place
            found = available.kind(schema, tag)
            found += available.features(FEATURES[tag](Terms.node(tag, record)) if tag in FEATURES else [])
        problems += [f"{where if root is None else root}: {problem}" for problem in found]
    return _unique(problems)


def check(store: Any, path: str, version: Version | str) -> list[str]:
    """The problems of the constructs the unit at `path` uses that `version` lacks, in source order, each once and
    located by its place: `body[2]: StaticAssertDeclaration.keyword 'static_assert' needs C23`. `version` is `(11,)`,
    `(17,)` or `(23,)`, or the common name or the designation the language covers an edition by (`"C23"`, `"ISO/IEC
    9899:2024"`). Raises LookupError where the workspace holds no file at `path`, or the language covers no such
    edition (the store not prepared, `Standards.prepare`, among them)."""
    return _read(store, path, lambda unit: check_file(store, unit, version))


def check_file(store: Any, unit: Any, version: Version | str) -> list[str]:
    """`check` of a unit's visitor, a `Programs.C.TranslationUnit` of `store`, read within the caller's transaction."""
    return _check(_Availability(store, version), unit)


# --- Validity ---

_NEEDS = {
    "Comment": ("text",), "Directive": ("directive",), "IfStatement": ("condition", "consequence"),
    "SwitchStatement": ("condition", "body"), "WhileStatement": ("condition", "body"),
    "DoStatement": ("body", "condition"), "ForStatement": ("body",), "LabeledStatement": ("label",),
    "CaseStatement": ("value",), "AttributedStatement": ("statement",), "AsmDeclaration": ("keyword", "template"),
    "AsmOperand": ("constraint", "value"), "FunctionDefinition": ("declarator", "body"),
    "StaticAssertDeclaration": ("keyword", "condition"), "InitDeclarator": ("declarator",),
}
"""The properties each kind needs set: those 0.3's validation required, not being optional."""

_LISTS = {"SimpleDeclaration": ("specifiers", "a specifier"), "MemberDeclaration": ("specifiers", "a specifier"),
          "FunctionDefinition": ("specifiers", "a specifier"), "AttributedStatement": ("attributes", "an attribute"),
          "AttributeDeclaration": ("attributes", "an attribute")}
"""The lists each kind needs to hold an element, by kind: the list's property, and what it needs."""

_CHOICES = {("StaticAssertDeclaration", "keyword"): ("static_assert", "_Static_assert"),
            ("AsmDeclaration", "keyword"): ("asm", "__asm__", "__asm")}
"""The words a kind's property may be, by the kind and the property's name, as 0.3 had them."""

_DANGLING = {"IfStatement": "consequence", "WhileStatement": "body", "ForStatement": "body", "SwitchStatement": "body",
             "LabeledStatement": "statement", "CaseStatement": "statement", "DefaultStatement": "statement",
             "AttributedStatement": "statement"}
"""The statements that end with a statement of their own, by the property that holds it: an `if`'s, its consequence
(or its alternative, where it has one)."""


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
    """A statement's, a member declaration's or a part's own problems, given its kind and its properties that are
    set."""
    problems = [f"{_a(kind)} needs {_a(name)}" for name in _NEEDS.get(kind, ()) if name not in held]
    if kind in _LISTS and not (_LISTS[kind][0] in held and held[_LISTS[kind][0]].values):
        problems.append(f"{_a(kind)} needs {_LISTS[kind][1]}")
    problems += [f"{kind}.{name} cannot be {held[name]!r}" for (owner, name), words in _CHOICES.items()
                 if owner == kind and name in held and held[name] not in words]
    if kind == "GotoStatement" and "label" not in held and "target" not in held:
        problems.append("a GotoStatement needs a label or a target")
    if kind == "MemberDeclarator" and "declarator" not in held and "bitfield" not in held:
        problems.append("a MemberDeclarator needs a declarator or a bitfield")
    if kind == "FunctionDefinition" and "declarator" in held and _binder(held["declarator"])[0] != "functiondeclarator":
        problems.append("a FunctionDefinition's declarator declares no function")
    if kind == "IfStatement" and "alternative" in held and _dangles(held.get("consequence")):
        problems.append("an if without else ends the consequence, and would take the else")
    return problems


def _terms(held: Any) -> Iterator[Any]:
    """The terms a value holds: itself, or a list's, or a value object's, in order, none within a term or a part holding
    statements."""
    if isinstance(held, Objects.Listed):
        for element in held.values:
            yield from _terms(element)
    elif Terms.is_term(held):
        yield held
    elif Objects.is_object(held) and _branch(held)[2].as_schema().name not in _STATEMENTS:
        for value in Objects.properties(held).values():
            yield from _terms(value)


def _bound(term: Any) -> set[str]:
    """The names a term refers to or binds, taken as bound."""
    return {name for t in Terms.walk(term) if isinstance(name := Terms.name_of(t), str)}


def _known(problems: list[str]) -> list[str]:
    """Problems but those of a type C leaves to the implementation, which only an ABI defines and a unit names none."""
    return [problem for problem in problems if not problem.endswith(_NO_ABI)]


def _validated(term: Any) -> list[str]:
    """A term's problems, as the dialect whose union holds it validates it."""
    return _known(_DIALECTS[term.as_schema().name].validate(term, _bound(term)))


def _term_problems(value: Any, tag: str, record: Any) -> list[str]:
    """The problems of the outermost term or helper of mbse-expressions' that a statement or a part holds: a term's, as
    its dialect validates it; a helper's, its own checks, and its terms' as their dialect validates them."""
    if Terms.is_term(value):
        return _validated(value)
    own = _known(Kinds.problems(Terms.node(tag, record), Domains.Types(record, "C.Expressions")))
    return own + [problem for term in _terms(record) for problem in _validated(term)]


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
    and its terms' problems as their dialects validate them. Raises LookupError where the workspace holds no file at
    `path`."""
    return _read(store, path, validate_file)


def validate_file(unit: Any) -> list[str]:
    """`validate` of a unit's visitor, read within the caller's transaction."""
    return _validate(unit)
