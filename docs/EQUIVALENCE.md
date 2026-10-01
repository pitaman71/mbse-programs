# Equivalence of the implementations

`python3/` and `typescript5/` implement the same package, and follow mbse-schemas' rules for equivalence
([`EQUIVALENCE.md`](../submodules/mbse-schemas/docs/EQUIVALENCE.md)): the same API and messages, byte-identical JSON,
interchangeable data, the same test cases under the same IDs, and full coverage in both. This document covers what is
specific to this package: the framework, the Ccpp language and its standards.

## How it is checked

| Check | Where |
|---|---|
| Every test case exists in both implementations, same ID, same order | `python3/tests/*.ipynb`, `typescript5/tests/*.ipynb` |
| The kinds are the same: names, categories, fields, choices and availability | `Ccpp.grammar.json`, which CONF-02 compares byte for byte |
| Parsing gives the same tree, and printing the same text | the snapshot and the printed text of the corpus, compared by CONF-02 and read back by CONF-03 |
| Errors report the same message, line and column | the PRS-12 and PRT-06 cases, the same in both suites |
| Full code coverage in both | the coverage gates below |

`typescript5/src/Ccpp/Syntax.ts` mirrors `python3/mbse/Programs/Ccpp/Syntax.py` kind for kind, field for field and in
the same order; a kind added to one and not the other changes the grammar, and CONF-02 fails.

## Coverage

| | Python | TypeScript |
|---|---|---|
| Command | `uv run coverage run -m pytest && uv run coverage combine && uv run coverage report` | `npm run coverage` |
| Required | 100% of statements and branches | 100% of statements, branches, functions and lines |

A gap in one implementation is closed by an assertion in the shared case, in both suites, never by a one-language
test.

## Deliberate differences

Beyond mbse-schemas' own (native types, `Map` for plain data, errors, and so on):

| Area | Python | TypeScript | Why | Cases |
|---|---|---|---|---|
| Declaring a kind's fields | typed annotations, read with `inspect.get_annotations` (so they work with and without `from __future__ import annotations`, and with Python 3.14's lazy annotations) | a `static SPEC` of field constructors (`text()`, `flag()`, `optionalInteger()`, `choice(...)`, `one(() => [...])`, `optional(...)`, `many(...)`), and `interface K extends Fields<typeof KSpec> {}` for the instance's type | TypeScript's types are erased at runtime; a spec is the nearest declaration that is both typed and readable | SYN-01 |
| Choices | `typing.Literal` aliases, such as `PrimitiveKeyword` | constant arrays, such as `PRIMITIVE_KEYWORDS`, and their element types | a `Literal` is a runtime object in Python, a type only in TypeScript | SYN-01, CPP-01 |
| Constructing a node | keyword arguments: `S.Identifier(spelling="x")` | an object literal: `new S.Identifier({ spelling: "x" })` | no keyword arguments | all |
| Integers | `int` | `bigint` | as mbse-schemas | SYN-02, PRT-03 |
| Reading a node's kind and fields | `type(node)`, `getattr(node, name)` | `node.kind()`, `node.field(name)` | a class's static members are reached through the instance's constructor | SYN-02 |
| Showing a node | `repr(node)` | `node.toString()`, the same text | each language's idiom | SYN-02 |
| Feature tables | `FEATURES` is a dict of field to {value or `True`: availability} | an object of field to a list of [value or `true`, availability] pairs | a JavaScript object's keys are strings only | CPP-03, CPP-04 |
| Kinds and categories of a language | dicts | `Map`s | as mbse-schemas | CPP-01 |
| Options | `Language(name, kinds, base=...)` | `new Language(name, kinds, { base })` | no keyword arguments | SYN-03 |
| The parser | tree-sitter's Python binding, with the tree-sitter-cpp wheel | web-tree-sitter, with tree-sitter-cpp's wasm, loaded by a top-level `await` when `Ccpp/_Parser` is first imported | web-tree-sitter needs no native build; the wasm is the same grammar, pinned to the same version | PRS-01 |
| Positions | converted from tree-sitter's byte offsets to code points | converted from UTF-16 units to code points | each runtime's own string offsets | PRS-12 |
| Import paths | `mbse.Programs.Framework` and `mbse.Programs.Ccpp` (`.Syntax`, `.Definitions`, `.Ccpp17`, `.Ccpp20`), in the shared `mbse` namespace package | `@mbse/programs/Framework` and `@mbse/programs/Ccpp` (`/Syntax`, `/Definitions`, `/Ccpp17`, `/Ccpp20`); `@mbse/schemas` is a `file:` dependency on the submodule | a module specifier is a path, not a dotted name | all |
