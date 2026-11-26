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
  language's validation, and its terms' problems, as their dialects validate them, but what depends on the target,
  which waits for an ABI to be applied (below).

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
`body[2]: StaticAssertDeclaration.keyword 'static_assert' needs C23`, `body[0].specifiers[0]: declspecifier.keyword
'thread_local' needs C23`. mbse-expressions' term readers stop where a term holds statements (`Terms.boundaries`): this
module reads records itself (`Objects.properties`, `Terms.kind_of`), as `Definitions` does, and reads what a block, a
member list or a group holds as statements.

What an edition has is read from data, as mbse-expressions records it (mbse-basis [CAP-268: standards as tagged data](mbse:mbse-basis/docs/capabilities/CAP-268.md#decided)):
a statement, declaration or member kind is available where a standard of that edition's designation, among those
`Programs.C` covers, lists its schema (`Standards`); a term's kind, where one of those of `C`, `C Types` or `C
Preprocessor` does (`Standards.DIALECTS`), of that designation, a dialect's editions of another language (C
Preprocessor's C++ editions) not read: C23's attribute declarations, `nullptr` (a `constant`), `#elifdef` and
`__has_include` (`hasincludeexpression`); and `_Pragma("...")`, C Preprocessor's `pragmaexpression`, which every edition
has. A kind no standard lists is not checked: GNU's extensions (`asm`, a statement expression, `__extension__`, a label
as a value, `&&l`, C's `labeladdressexpression`), outside every edition, as mbse-expressions' `C` marks them, a part or
a helper (GNU's asm label, C Types' `AsmLabel`, among them), and invalid syntax, a `Programs.C.Error` and an `error` or
`missing` term, which `validate` reports *(agent)*. A kind's problem is `<kind> needs <the first edition that has it>`:
a statement's kind by its name (`AttributeDeclaration`), a term's by its tag (`constant`).

What an edition changes within a kind is read from data too, its grammar clauses (mbse-basis [grammar clauses by
version](mbse:mbse-basis/proposals/GRAMMAR-CLAUSES.md#decided)), each an edition allows or forbids: for each statement,
member declaration, part, term and helper, the grammar clauses it takes, of the dialect whose kind it is
(`Framework.Standards.takes`), the language's for its statements (`Standards.GRAMMAR_CLAUSES`: a label without a
statement or before a declaration, `static_assert` spelled so and without a message, C23's helpers where a declaration
holds them, an inferred type, an unnamed parameter of a function's definition, and a K&R definition, which C23
removed), `C`'s, `C Types`' and `C Preprocessor`'s for its terms and helpers (a literal's digit separators, a `u8`
character, C23's keywords, `#warning`, `#embed`, ...), and whether the target allows each, by each dialect's edition of
the target's designation, or, where a dialect does not represent it, as its neighbours' flagged entries guess
(`Framework.Standards.edition_allows`): a grammar clause no edition names is allowed. A grammar clause's problem is
`<its name> needs <the edition nearest the target that allows it>`, the first after it, else the last before it, as
Python3's `Check` names one *(agent)* (`SimpleDeclaration.specifiers holding a bitintspecifier needs C23`,
`FunctionDefinition with a declaration list needs C17`), located where a kind's would be, or `<its name> is in no
edition`, where none does.

What no grammar clause can express would stay code: nothing does, of C's. What arrived before C11, as `restrict`,
`inline` and designators, and C11's own, as `_Alignas`, `_Atomic`, `_Generic`, `_Noreturn`, `_Static_assert` and
`_Thread_local`, every edition has.

Not checked: trigraphs, which C23 removed, and which `Parse` keeps as tree-sitter reads them; and a function's
declaration without a prototype (`int f();`), which C23 reads as one with no parameters, no syntax removed.

`validate`'s rules, each the 0.3 rule where one stands, located at the statement, member declaration or part:

- what a kind needs: a property, as 0.3's validation required each that is not optional (`an IfStatement needs a
  condition`, `a FunctionDefinition needs a body`, `an AsmOperand needs a constraint`), a list that is not empty (`an
  AttributeDeclaration needs an attribute`), and what goes together (`a GotoStatement needs a label or a target`, `a
  MemberDeclarator needs a declarator or a bitfield`); and, beyond 0.3's, `a SimpleDeclaration needs a specifier`, as
  for a member declaration and a function's definition: C99 removed the implicit `int`, and a function's definition's
  declarator declaring a function (`int m { ... }`), which the schemas hold where a unit is built, and which `Parse`
  keeps as invalid syntax where tree-sitter reads one (its departure 37) *(agent)*; a kind's word one
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
  binding them is the unit's, which `Definitions` resolves, not a term's. What depends on the target is deferred,
  below.

**The ABI is applied last.** As the user decided, "Of course C and C++ need a ABI, but if we can model programs in an
abi-agnostic form and apply the ABI at the last minute, that would be advantageous". A program names no ABI: a unit
holds C as written, and nothing in its tree depends on a target. `validate` checks what does not depend on one; the
checks that do are not made: a literal's type and its range (`1`'s `int`, `L'w'`'s `wchar_t`, which C leaves to the
implementation), `sizeof` and `_Alignof`, and constant evaluation (an array's size, a `static_assert`'s condition, a
bit-field's width, a `case` label's value): its terms are validated within mbse-expressions' `Domains.Reading(None)`,
which defers each check needing an ABI rather than reporting it. The ABI is applied at the call that needs one:
`validate_for(store, path, abi)` validates within `Domains.Reading` of the ABI dialect's singleton named `abi`
(`Expressions.SystemV.AMD64`, `Expressions.Arm.AAPCS64`, `ABIS`), so that each literal's type and range is checked under
that target, and `prepare_abi(store, abi)` gives a store the ABI's schemas and types, after `Standards.prepare`.

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
from mbse.Expressions.Arm import AAPCS64
from mbse.Expressions.SystemV import AMD64
from mbse.Expressions.Framework import Objects, Standards as ExpressionStandards, Terms
from mbse.Schemas.Framework import Schemas as SchemaKinds

from ..Framework.Model import WORKSPACE
from .Standards import DIALECTS
from .Statements import KINDS, LANGUAGE

__all__ = ["check", "check_file", "validate", "validate_file", "validate_for", "validate_file_for", "prepare_abi",
           "ABIS"]

Version = tuple[int, ...]

_STATEMENTS = frozenset(f"{LANGUAGE}.{kind}" for kind in (*KINDS, "Error", "MemberList", "Group", "MemberGroup"))
"""The schemas that have a statement's place: statements, declarations, member declarations, invalid syntax and the
parts that hold them."""
_EXPRESSIONS = "Expressions."
"""What mbse-expressions' schemas' names begin with: its terms', helpers' and kinds'."""
_DIALECTS = {"Expressions.C.Expressions.Term": CExpressions.DIALECT, "Expressions.C.Types.Term": CTypes.DIALECT,
             "Expressions.C.Preprocessor.Term": CPreprocessor.DIALECT}
"""The dialect that validates a term, by the union that holds it."""
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


def _walk(value: Any, where: str, root: str | None, holders: frozenset[str]) -> Iterator[
        tuple[str, str | None, Any, str, Any]]:
    """Every record within what a property holds, parents first, in source order: each its place, the place of the
    outermost term, helper or kind's record of mbse-expressions' holding it (None for a statement, a member
    declaration, an error, a part holding statements or a part), the term or record itself, its tag and its record. A
    statement within a term, where its block, its member list or its group holds one, is one of them, at its place.
    `holders` are the schemas that have a statement's place, the language's *(agent: a parameter, so that
    `Programs.Cpp.Check` reuses it over C++'s)*."""
    if isinstance(value, Objects.Listed):
        for i, element in enumerate(value.values):
            yield from _walk(element, f"{where}[{i}]", root, holders)
        return
    if not hasattr(value, "as_schema"):
        return  # a scalar
    value, tag, record = _branch(value)
    name = record.as_schema().name
    if name in holders:
        root = None
    elif root is None and name.startswith(_EXPRESSIONS):
        root = where
    yield where, root, value, tag, record
    for prop, held in Objects.properties(record).items():
        yield from _walk(held, f"{where}.{prop}", root, holders)


def _unit(unit: Any) -> Iterator[tuple[str, str | None, Any, str, Any]]:
    """Every record of a unit's tree, as `_walk` gives it, from its `body`."""
    return _walk(Objects.properties(unit).get("body"), "body", None, _STATEMENTS)


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


# --- Declarators ---

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


# --- Editions ---

def _year(standard: Any) -> int:
    """A stored edition's revision's year: 2024."""
    return ExpressionStandards.properties(standard)["revision"][1]  # type: ignore[no-any-return, index]


class _Availability:
    """What the store's standards say of the target edition: each kind's schema's editions' years, by its schema's
    name, among the editions the language covers by designation (a dialect's other editions, C Preprocessor's C++
    editions in C's, not read); and each grammar clause the target forbids, by its kind's schema's name, with its
    dialect and its problem. `language` is the singleton covering the editions, `edition` the target's common name or
    designation, and `dialects` the singletons whose standards list kinds and whose grammar clauses `check` reads
    *(agent: parameters, so that `Programs.Cpp.Check` reuses it)*.

    A grammar clause is read against its dialect's edition of the target's designation, or, where its dialect does not
    represent it, guessed from the dialect's flagged neighbours by revision (`Framework.Standards.edition_allows`)."""

    def __init__(self, store: Any, language: str, edition: str, dialects: tuple[str, ...]):
        target = ExpressionStandards.find(store.singleton(language), edition)
        if target is None:
            raise LookupError(f"{language} covers no edition {edition!r}: run Standards.prepare on the store")
        self.target = _year(target)
        self.covered = covered = ExpressionStandards.standards(store.singleton(language))
        self.edition = ExpressionStandards.tags(target)[-1]
        self.years = {ExpressionStandards.tags(s)[-1]: _year(s) for s in covered.values()}
        self.names = {year: name for name, year in self.years.items()}
        self.versions: dict[str, set[int]] = {}
        self.clauses: dict[str, dict[str, tuple[Any, dict[str, str]]]] = {}
        for dialect in dialects:
            singleton = store.singleton(dialect)
            standards = ExpressionStandards.standards(singleton)
            if not standards:
                raise LookupError(f"{dialect} covers no edition: run Standards.prepare on the store")
            for designation, standard in standards.items():
                if designation not in covered:  # another language's, as C Preprocessor's C++ editions are C's
                    continue
                for kind in ExpressionStandards.kinds(standard):
                    self.versions.setdefault(kind.name, set()).add(_year(standard))
            self._forbidden(dialect, singleton)

    def _forbidden(self, dialect: str, singleton: Any) -> None:
        """Each grammar clause of a dialect that the target forbids, by its kind's schema's name, with its problem,
        read for each edition the language covers, by its designation and its revision: by the dialect's own edition
        of that designation, or, where the dialect does not represent it, as its neighbours' flagged entries guess
        (`Framework.Standards.edition_allows`). A problem names the edition nearest the target that allows it, the
        first after it, else the last before it, as Python3's `Check` does *(agent)*."""
        editions = [(designation, _year(own), ExpressionStandards.tags(own)[-1])
                    for designation, own in self.covered.items()]
        for name, clause in ExpressionStandards.grammar_clauses(singleton).items():
            allowing = [(year, edition) for designation, year, edition in editions
                        if ExpressionStandards.edition_allows(singleton, designation, ("year", year), clause)]
            if self.edition not in (edition for _, edition in allowing):
                kind = ExpressionStandards.grammar_clause(clause)["kind"].name
                problems = self.clauses.setdefault(kind, {}).setdefault(dialect, (singleton, {}))[1]
                later = [edition for year, edition in allowing if year > self.target]
                nearest = later[0] if later else allowing[-1][1] if allowing else None
                problems[name] = f"{name} is in no edition" if nearest is None else f"{name} needs {nearest}"

    def kind(self, schema: str, what: str) -> list[str]:
        """The problem of a kind, by its schema's name, that the target lacks: none where it has it, or where no
        standard lists it."""
        versions = self.versions.get(schema)
        if not versions or self.target in versions:
            return []
        return [f"{what} needs {self.names[min(versions)]}"]

    def grammar_clauses(self, record: Any) -> list[str]:
        """The problems of the grammar clauses a record takes that the target forbids, in its dialect's order: `<its
        name> needs <the first edition the language covers that allows it>`, or, where none does, `<its name> is in no
        edition`."""
        return [problems[name] for singleton, problems in self.clauses.get(record.as_schema().name, {}).values()
                for clause, _ in ExpressionStandards.takes(singleton, record)
                if (name := str(ExpressionStandards.grammar_clause_name(clause))) in problems]



def _check(available: _Availability, records: Iterator[tuple[str, str | None, Any, str, Any]]) -> list[str]:
    """The problems of a unit's `records`, as `_walk` gives them, that the target lacks: each kind's, and each grammar
    clause's its records take *(agent: `Programs.Cpp.Check` reuses it)*."""
    problems: list[str] = []
    for where, root, _, tag, record in records:
        kind = _kind(record) if root is None else tag  # a statement's, a member's, an error's or a part's, or a term's
        found = available.kind(record.as_schema().name, kind) + available.grammar_clauses(record)
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
    edition = f"C{version[0]}" if isinstance(version, tuple) and len(version) == 1 else str(version)
    return _check(_Availability(store, LANGUAGE, edition, DIALECTS), _unit(unit))


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


def _terms(held: Any, holders: frozenset[str]) -> Iterator[Any]:
    """The terms a value holds: itself, or a list's, or a value object's, in order, none within a term or a part holding
    statements, one of `holders`."""
    if isinstance(held, Objects.Listed):
        for element in held.values:
            yield from _terms(element, holders)
    elif Terms.is_term(held):
        yield held
    elif Objects.is_object(held) and _branch(held)[2].as_schema().name not in holders:
        for value in Objects.properties(held).values():
            yield from _terms(value, holders)


def _bound(term: Any) -> set[str]:
    """The names a term refers to or binds, taken as bound."""
    return {name for t in Terms.walk(term) if isinstance(name := Terms.name_of(t), str)}


def _validated(term: Any) -> list[str]:
    """A term's problems, as the dialect whose union holds it validates it."""
    return _DIALECTS[term.as_schema().name].validate(term, _bound(term))


def _term_problems(value: Any, tag: str, record: Any) -> list[str]:
    """The problems of the outermost term or helper of mbse-expressions' that a statement or a part holds: a term's, as
    its dialect validates it; a helper's, its own checks, and its terms' as their dialect validates them."""
    if Terms.is_term(value):
        return _validated(value)
    own = Kinds.problems(Terms.node(tag, record), Domains.Types(record, "C.Expressions"))
    return own + [problem for term in _terms(record, _STATEMENTS) for problem in _validated(term)]


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


def _applied(store: Any, unit: Any, abi: str, validated: Callable[[Any], list[str]]) -> list[str]:
    """A unit's problems as `validated` reads them, within `Domains.Reading` of the ABI named `abi` (`ABIS`)."""
    if abi not in ABIS:
        raise LookupError(f"no ABI {abi!r}: one of {', '.join(ABIS)}")
    return Domains.Reading(store.singleton(abi)).run(lambda: validated(unit))


ABIS = {"Expressions.SystemV.AMD64": AMD64, "Expressions.Arm.AAPCS64": AAPCS64}
"""The ABIs a unit may be validated under, each by its dialect's singleton's name, and its module."""


def prepare_abi(store: Any, abi: str) -> Any:
    """`store`, prepared by `Standards.prepare`, given the ABI named `abi` (`ABIS`): its schemas and its types, its
    `install` and `define`, each in a transaction of its own. Run again, it writes nothing."""
    for each in (ABIS[abi].install, ABIS[abi].define):
        store.transaction(each)
    return store
