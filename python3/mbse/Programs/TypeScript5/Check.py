"""Check: which versions of TypeScript 5 have the constructs a stored program uses, and whether it is a valid one.

A program is a `Programs.TypeScript5.Program` that `Programs.Framework.TheWorkspace` owns by its path, as `Parse` writes
it. Both functions read it, within the transaction open on `store` or, where none is, within one of their own, and
write nothing; each raises LookupError where the workspace holds no file at `path`.

- `check(store, path, version)`: the problems of the constructs the program uses that `version` lacks, in source order,
  each once. `version` is a version of TypeScript 5, as `(5, 9)` or by the name the language covers it by
  (`"TypeScript 5.9"`); LookupError where the language covers none such. The store must hold the standards
  (`Standards.prepare`).
- `validate(store, path)`: the program's problems as a tree, in source order: each kind's own rules, ported from the 0.3
  language's `check()` methods and its validation, and its terms' problems, as their dialects validate them.

Each problem is located by its place in the program's value, as `Definitions` anchors it, its steps joined by `.` as
Python3's `Check` joins them *(agent)*: a statement's, clause's or member's is the property of what holds it, with its
index where that holds a list, from the program's `body` (`body[2]`, `body[0].consequent`, `body[1].handler`,
`body[3].body.body[0]`, a class's member); a part's that holds no statement, its statement's then its property
(`body[0].declarations[1]`, `body[4].specifiers[0]`), and a grammar clause's, its property's (`body[0].phase`); a term's, the place of the outermost term, helper or part of
mbse-expressions' that holds it, within its statement or its part (`body[0].expression`,
`body[0].declarations[0].init`, `body[2].returnType`). Statements within a term, a function's or an arrow's `block`
and a class expression's `classBody`, are located through the term's place, as `Definitions` anchors them: the block
is `body[0].declarations[0].init.block`, its statements `body[0].declarations[0].init.block.body[1]`, and a class
expression's members `body[0].expression.classBody.body[2]`. So: `body[2].declarationKind:
VariableDeclaration.declarationKind 'using' needs TypeScript 5.2`, `body[0].expression: importexpression.options needs TypeScript 5.3`. mbse-expressions' term
readers stop where a term holds statements (`Terms.boundaries`): this module reads records itself
(`Objects.properties`, `Terms.kind_of`), as `Definitions` does, and reads what a block or a class body holds as
statements.

What a version has is read from data, as mbse-expressions records it (mbse-basis [CAP-268: standards as tagged data](mbse:mbse-basis/docs/capabilities/CAP-268.md#decided)):
a statement, clause or member kind is available where a standard of that version's name, among those
`Programs.TypeScript5` covers, lists its schema (`Standards`); a term's kind, where one of those of `TypeScript5`,
`TypeScript Types` or `TypeScript Patterns` does (`Standards.DIALECTS`). Every kind is in every version of TypeScript 5.
A kind no standard lists is not checked: JSX, an extension outside every version, as mbse-expressions' `TypeScript5`
marks it, a part or a helper, and invalid syntax, a `Programs.TypeScript5.Error` and an `error` or `missing` term,
which `validate` reports *(agent)*. A kind's problem is `<kind> needs <the first version that has it>`: a statement's
kind by its name (`AccessorProperty`), a term's by its tag (`importexpression`).

What a property's value makes available within a kind is data too, grammar clauses (mbse-basis [grammar clauses by
version](mbse:mbse-basis/proposals/GRAMMAR-CLAUSES.md)), read as mbse-expressions reads them
(`Expressions.Framework.Standards`): those a statement, a clause, a member or a part takes of the language's own
(`Standards`: `VariableDeclaration.declarationKind 'using'`, `ImportDeclaration.attributes`, `ImportSpecifier.imported
as a string`, ...), located at the property that holds what it says (`body[0].declarationKind`); and those a term or
a helper takes of its dialect's (`TypeScript5`'s `importexpression.options` and `importexpression.phase 'defer'`,
`TypeScript Types`' `tsimporttype.options`), located as its kind's problem is. A grammar clause the target does not
allow is `<its name> needs <the nearest version that allows it>`, the first after the target, else the last before it
*(agent)*: `body[0].declarationKind: VariableDeclaration.declarationKind 'using' needs TypeScript 5.2`. The target's
own entries decide, else its neighbours' flagged `before` and `after` (a version the data covers but does not represent
in a grammar clause's entries, as a store may add TypeScript 5.10), else a grammar clause is allowed
(`Framework.Standards.allows`); a dialect that does not cover the target has no say. The grammar clauses taken at one
place are alternatives of one production, the place fine in a version that allows one of them, as Python3's `Check`
reads them *(agent)*. What arrived before 5.0, as `accessor`, decorators, `satisfies`, `export type *` and `const` type
parameters, every version has.

What no grammar clause can say stays code, each with its reason: nothing, of TypeScript 5's.

`validate`'s rules, each the 0.3 rule where one stands, located at the statement, clause, member or part:

- what a kind needs: a property, as 0.3's validation required each that is not optional (`an IfStatement needs a
  test`, `a MethodDefinition needs a key`, `an ImportSpecifier needs an imported`), a list that is not empty (`a
  VariableDeclaration needs a declarator`), and what goes together (`a TryStatement needs a handler or a finalizer`, a
  `VariableDeclarator`'s `definite` a name with a type annotation); a kind's word one of its choices
  (`VariableDeclaration.declarationKind cannot be 'val'`); and the dangling `else`, an `if` without one ending the
  consequent of an `if` with one;
- invalid syntax, as the user decided that a parse keeps it and validation reports it: each
  `Programs.TypeScript5.Error`, `invalid syntax '<its text>'`, as mbse-expressions words an `error` term's
  (`Terms.invalid_problems`), located at the error; an `error` or `missing` term as its dialect validates it, below.
  An `Error` may stand wherever a statement, a clause or a member may, and holds statements in its `body`, each of
  which is checked as one *(agent)*;
- terms: each term a statement or a part holds, as its dialect validates it (`TypeScript5.DIALECT.validate`, which
  reads `TypeScript Types` and `TypeScript Patterns` too); a helper or a kind's record a statement holds alone (an
  annotation, type parameters, a class's name, an interface's member), by its own checks (`Nodes.check`) and its terms
  as their dialect validates them. The names a term refers to are taken as bound *(agent)*: binding them is the
  program's, which `Definitions` resolves, not a term's.

Dropped, as the model now holds them: a property's type and a child's category, and where a statement, a clause or a
member may stand (a `switch`'s `cases` hold only cases, a class's body only members), which the schemas check on write;
every rule on terms, which mbse-expressions' dialects own (an identifier's name, a template's quasis, a sequence's and
a union's members, type parameters, a literal's spelling). Not checked: JSX in a `.ts` file and `<T>x` in a `.tsx`
one, which `Parse` decides by the path, and `import.defer(...)`, which tree-sitter-typescript 0.23 does not read (`Parse`
keeps it an `error` term), so that only a written tree holds it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from mbse.Expressions.Framework import Objects, Standards as ExpressionStandards, Terms
from mbse.Expressions.TypeScript.TypeScript5 import Expressions as TypeScriptExpressions, Nodes
from mbse.Schemas.Framework import Schemas as SchemaKinds

from ..Framework.Model import WORKSPACE
from .Standards import DIALECTS, designation
from .Statements import KINDS, LANGUAGE

__all__ = ["check", "check_file", "validate", "validate_file"]

Version = tuple[int, ...]

_STATEMENTS = frozenset(f"{LANGUAGE}.{kind}" for kind in (*KINDS, "Error"))
"""The schemas that have a statement's place: statements, clauses, class members and invalid syntax."""
_EXPRESSIONS = "Expressions."
"""What mbse-expressions' schemas' names begin with: its terms', helpers' and kinds'."""


# --- Reading ---

def _branch(value: Any) -> tuple[Any, str, Any]:
    """What a property holds, through unions of unions: a term, its tag and its record; or a record, its kind's name in
    lower case (`identifier`, `variabledeclaration`) and itself."""
    if Terms.is_term(value):
        return (value, *Terms.kind_of(value))
    if isinstance(value.as_schema(), SchemaKinds.OfUnion.Data):
        ((_, held),) = Objects.properties(value).items()
        return _branch(held)
    return value, value.as_schema().name.rsplit(".", 1)[-1].lower(), value


def _walk(value: Any, where: str, root: str | None) -> Iterator[tuple[str, str | None, Any, str, Any]]:
    """Every record within what a property holds, parents first, in source order: each its place, the place of the
    outermost term, helper or kind's record of mbse-expressions' holding it (None for a statement, a clause, a member,
    an error or a part), the term or record itself, its tag and its record. A statement within a term, where its block
    or class body holds one, is one of them, at its place."""
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


def _program(program: Any) -> Iterator[tuple[str, str | None, Any, str, Any]]:
    """Every record of a program's tree, as `_walk` gives it, from its `body`."""
    return _walk(Objects.properties(program).get("body"), "body", None)


def _module(store: Any, path: str, read: Callable[[Any], list[str]]) -> list[str]:
    """`read` of the program at `path`, within a transaction of its own, so called with none open on `store`, as the
    user decided that whether one is open is no flag on the store (mbse-basis CAP-315)."""
    with store.transaction():
        return read(store.singleton(WORKSPACE).files({"path": path}))  # LookupError, where it holds none


def _kind(record: Any) -> str:
    """A statement's, clause's, member's or part's kind: its schema's name, without its language's (`IfStatement`)."""
    return record.as_schema().name.rsplit(".", 1)[-1]


def _a(noun: str) -> str:
    return f"{'an' if noun[0].lower() in 'aeiou' else 'a'} {noun}"


def _unique(problems: list[str]) -> list[str]:
    return list(dict.fromkeys(problems))


# --- Versions ---

def _version(standard: Any) -> Version:
    """A stored standard's version, from its revision: (5, 9)."""
    return tuple(int(part) for part in str(ExpressionStandards.properties(standard)["revision"][1]).split("."))


class _Availability:
    """What the store's standards say: the target version, each kind's schema's versions, by its schema's name, and
    each dialect's grammar clauses and its standard of the target's name."""

    def __init__(self, store: Any, version: Version | str):
        language = store.singleton(LANGUAGE)
        tag = designation(version[1]) if isinstance(version, tuple) and version[:1] == (5,) else str(version)
        target = ExpressionStandards.find(language, tag)
        if target is None:
            raise LookupError(f"{LANGUAGE} covers no version {version!r}: run Standards.prepare on the store")
        self.target, self.name = _version(target), str(ExpressionStandards.designation_of(target))
        self.revision = ExpressionStandards.properties(target)["revision"]
        self.versions: dict[str, set[Version]] = {}
        self.grammar: dict[str, tuple[Any, set[str]]] = {}
        for dialect in DIALECTS:
            singleton = store.singleton(dialect)
            standards = ExpressionStandards.standards(singleton)
            if not standards:
                raise LookupError(f"{dialect} covers no version: run Standards.prepare on the store")
            for standard in standards.values():
                for kind in ExpressionStandards.kinds(standard):
                    self.versions.setdefault(kind.name, set()).add(_version(standard))
            kinds = {ExpressionStandards.grammar_clause(clause)["kind"].name
                     for clause in ExpressionStandards.grammar_clauses(singleton).values()}
            self.grammar[dialect] = (singleton, kinds)

    def kind(self, schema: str, what: str) -> list[str]:
        """The problem of a kind, by its schema's name, that the target lacks: none where it has it, or where no
        standard lists it."""
        versions = self.versions.get(schema)
        if not versions or self.target in versions:
            return []
        return [f"{what} needs TypeScript {'.'.join(map(str, min(versions)))}"]

    def nearest(self, dialect: Any, clause: Any) -> str:
        """The version nearest the target that allows a grammar clause: the first after it, else the last before it."""
        standards = ExpressionStandards.standards(dialect)
        allowing = sorted((_version(standard), name) for name, standard in standards.items()
                          if ExpressionStandards.allows(standard, clause))
        later = [name for at, name in allowing if at > self.target]
        return later[0] if later else allowing[-1][1]

    def clauses(self, dialect: str, record: Any) -> list[tuple[str, str]]:
        """The problems of the grammar clauses of `dialect` that a record takes and the target lacks, each with its
        place within the record, its property's (`.phase`): those taken at one place are alternatives, the place fine
        where the target allows one of them."""
        singleton, kinds = self.grammar[dialect]
        if record.as_schema().name not in kinds:
            return []
        places: dict[str, list[Any]] = {}
        for clause, _ in ExpressionStandards.takes(singleton, record):
            places.setdefault(f".{ExpressionStandards.grammar_clause(clause)['property']}", []).append(clause)
        return [(place, f"{ExpressionStandards.grammar_clause_name(clause)} needs {self.nearest(singleton, clause)}")
                for place, taken in places.items() if not any(self.allows(singleton, each) for each in taken)
                for clause in taken]

    def allows(self, dialect: Any, clause: Any) -> bool:
        """Whether the target allows a grammar clause of a dialect: by the dialect's own version of its designation,
        or, where the dialect does not represent it, as its neighbours' flagged entries guess
        (`Framework.Standards.edition_allows`)."""
        return ExpressionStandards.edition_allows(dialect, self.name, self.revision, clause)


def _check(available: _Availability, program: Any) -> list[str]:
    problems: list[str] = []
    for where, root, _, tag, record in _program(program):
        schema = record.as_schema().name
        if root is None:  # a statement, a clause, a member, an error or a part, at its place
            problems += [f"{where}: {problem}" for problem in available.kind(schema, _kind(record))]
            problems += [f"{where}{place}: {problem}" for place, problem in available.clauses(LANGUAGE, record)]
        else:  # within a term, at the outermost's place
            found = available.kind(schema, tag)
            found += [problem for dialect in DIALECTS[1:] for _, problem in available.clauses(dialect, record)]
            problems += [f"{root}: {problem}" for problem in found]
    return _unique(problems)


def check(store: Any, path: str, version: Version | str) -> list[str]:
    """The problems of the constructs the program at `path` uses that `version` lacks, in source order, each once and
    located by its place: `body[2].declarationKind: VariableDeclaration.declarationKind 'using' needs TypeScript 5.2`.
    `version` is `(5, minor)` or a name the language covers a version by (`"TypeScript 5.9"`). Raises LookupError where
    the workspace holds no file at `path`, or the language covers no such version (the store not prepared,
    `Standards.prepare`, among them)."""
    return _module(store, path, lambda program: check_file(store, program, version))


def check_file(store: Any, program: Any, version: Version | str) -> list[str]:
    """`check` of a program's visitor, a `Programs.TypeScript5.Program` of `store`, read within the caller's
    transaction."""
    return _check(_Availability(store, version), program)


# --- Validity ---

_NEEDS = {
    "Comment": ("text",), "ExpressionStatement": ("expression",), "WithStatement": ("object", "body"),
    "LabeledStatement": ("label", "body"), "IfStatement": ("test", "consequent"), "SwitchStatement": ("discriminant",),
    "ThrowStatement": ("argument",), "TryStatement": ("block",), "CatchClause": ("body",),
    "WhileStatement": ("test", "body"), "DoWhileStatement": ("body", "test"), "ForStatement": ("body",),
    "ForInStatement": ("left", "right", "body"), "ForOfStatement": ("left", "right", "body"),
    "VariableDeclaration": ("declarationKind",), "VariableDeclarator": ("id",), "FunctionDeclaration": ("body",),
    "ClassDeclaration": ("body",), "MethodDefinition": ("methodKind", "key", "value"),
    "TSAbstractMethodDefinition": ("methodKind", "key", "value"), "PropertyDefinition": ("key",),
    "TSAbstractPropertyDefinition": ("key",), "AccessorProperty": ("key",), "TSAbstractAccessorProperty": ("key",),
    "ImportDeclaration": ("importKind", "source"), "ImportSpecifier": ("importKind", "imported", "local"),
    "ImportDefaultSpecifier": ("local",), "ImportNamespaceSpecifier": ("local",), "ImportAttribute": ("key", "value"),
    "ExportNamedDeclaration": ("exportKind",), "ExportSpecifier": ("exportKind", "local", "exported"),
    "ExportDefaultDeclaration": ("declaration",), "ExportAllDeclaration": ("exportKind", "source"),
    "TSImportEqualsDeclaration": ("importKind", "id", "moduleReference"), "TSExternalModuleReference": ("expression",),
    "TSExportAssignment": ("expression",), "TSNamespaceExportDeclaration": ("id",),
    "TSTypeAliasDeclaration": ("id", "typeAnnotation"), "TSInterfaceDeclaration": ("id", "body"),
    "TSInterfaceHeritage": ("expression",), "TSEnumDeclaration": ("id", "body"), "TSEnumMember": ("id",),
    "TSModuleDeclaration": ("moduleKind", "id"),
}
"""The properties each kind needs set: those 0.3's validation required, not being optional."""

_CHOICES = {"declarationKind": ("var", "let", "const", "using", "await using"),
            "methodKind": ("constructor", "method", "get", "set"), "moduleKind": ("global", "module", "namespace"),
            "importKind": ("type", "value"), "exportKind": ("type", "value"),
            "accessibility": ("private", "protected", "public"), "phase": ("defer",)}
"""The words a kind's property may be, by the property's name, as 0.3 had them."""

_DANGLING = {"IfStatement": "consequent", "WhileStatement": "body", "ForStatement": "body", "ForInStatement": "body",
             "ForOfStatement": "body", "LabeledStatement": "body", "WithStatement": "body"}
"""The statements that end with a statement of their own, by the property that holds it: an `if`'s, its consequent
(or its alternate, where it has one)."""


def _dangles(statement: Any) -> bool:
    """Whether a statement ends with an `if` without `else`, which would take an `else` written after it."""
    while statement is not None:
        _, _, record = _branch(statement)
        kind, held = _kind(record), Objects.properties(record)
        if kind not in _DANGLING:
            return False
        if kind == "IfStatement" and "alternate" not in held:
            return True
        statement = held.get("alternate" if kind == "IfStatement" else _DANGLING[kind])
    return False


def _annotated(pattern: Any) -> bool:
    """Whether a pattern is a name with a type annotation."""
    _, tag, record = _branch(pattern)
    return tag == "identifier" and "typeAnnotation" in Objects.properties(record)


def _rules(kind: str, held: dict[str, Any]) -> list[str]:
    """A statement's, a clause's, a member's or a part's own problems, given its kind and its properties that are
    set."""
    problems = [f"{_a(kind)} needs {_a(name)}" for name in _NEEDS.get(kind, ()) if name not in held]
    problems += [f"{kind}.{name} cannot be {held[name]!r}" for name, words in _CHOICES.items()
                 if name in held and held[name] not in words]
    if kind == "VariableDeclaration" and not ("declarations" in held and held["declarations"].values):
        problems.append("a VariableDeclaration needs a declarator")
    if kind == "TryStatement" and "handler" not in held and "finalizer" not in held:
        problems.append("a TryStatement needs a handler or a finalizer")
    if kind == "IfStatement" and "alternate" in held and _dangles(held.get("consequent")):
        problems.append("an if without else ends the consequent, and would take the else")
    if kind == "VariableDeclarator" and held.get("definite") and not _annotated(held.get("id")):
        problems.append("definite needs a name with a type annotation")
    return problems


def _terms(held: Any) -> Iterator[Any]:
    """The terms a value holds: itself, or a list's, or a value object's, in order, none within a term."""
    if isinstance(held, Objects.Listed):
        for element in held.values:
            yield from _terms(element)
    elif Terms.is_term(held):
        yield held
    elif Objects.is_object(held):
        for value in Objects.properties(held).values():
            yield from _terms(value)


def _bound(term: Any) -> set[str]:
    """The names a term refers to or binds, taken as bound."""
    return {name for t in Terms.walk(term) if isinstance(name := Terms.name_of(t), str)}


def _term_problems(value: Any, tag: str, record: Any) -> list[str]:
    """The problems of the outermost term, helper or kind's record of mbse-expressions' that a statement or a part
    holds: a term's, as its dialect validates it; another's, its own checks, and its terms' as their dialect validates
    them."""
    if Terms.is_term(value):
        return TypeScriptExpressions.DIALECT.validate(value, _bound(value))
    return Nodes.check(tag)(record) + [problem for term in _terms(record)
                                       for problem in TypeScriptExpressions.DIALECT.validate(term, _bound(term))]


def _validate(program: Any) -> list[str]:
    problems: list[str] = []
    for where, root, value, tag, record in _program(program):
        if root is None:
            kind, held = _kind(record), Objects.properties(record)
            if kind == "Error":
                problems += [f"{where}: {p}" for p in Terms.invalid_problems("error", held)]
            problems += [f"{where}: {p}" for p in _rules(kind, held)]
        elif root == where:
            problems += [f"{where}: {p}" for p in _term_problems(value, tag, record)]
    return problems


def validate(store: Any, path: str) -> list[str]:
    """The problems of the program at `path` as a tree, in source order, each located by its place: its kinds' own
    rules, and its terms' problems as their dialects validate them. Raises LookupError where the workspace holds no
    file at `path`."""
    return _module(store, path, validate_file)


def validate_file(program: Any) -> list[str]:
    """`validate` of a program's visitor, read within the caller's transaction."""
    return _validate(program)
