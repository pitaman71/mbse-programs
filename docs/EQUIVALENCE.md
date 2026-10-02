# Equivalence of the implementations

`python3/` and `typescript5/` implement the same package, and follow mbse-schemas' rules for equivalence
([`EQUIVALENCE.md`](../submodules/mbse-schemas/docs/EQUIVALENCE.md)): the same API and messages, byte-identical JSON,
interchangeable data, the same test cases under the same IDs, and full coverage in both. This document covers what is
specific to this package: the framework, the Ccpp, Python and TypeScript languages with their standards, and the
transpilers.

## How it is checked

| Check | Where |
|---|---|
| Every test case exists in both implementations, same ID, same order | `python3/tests/*.ipynb`, `typescript5/tests/*.ipynb` |
| The kinds are the same: names, categories, fields, choices and availability | each language's grammar (`Ccpp.grammar.json`, `Python.grammar.json`, `TypeScript.grammar.json`), which CONF-02 compares byte for byte |
| Parsing gives the same tree, and printing the same text | the snapshots and printed text of the corpus (`cpp20.cpp`, `python314.py`, `typescript59.ts`, `typescript59-jsx.tsx`), compared by CONF-02 and read back by CONF-03 |
| Errors report the same message, line and column | PRS-12, PRT-06, PYPRS-12, PYPRT-06, TSPRS-12 and TSPRT-06, the same in both suites |
| Python trees mean what CPython reads | PYPRS-01, in the Python suite, reads the printed conformance source back with CPython's `ast` |
| TypeScript trees are what typescript-estree reads | TSPRS-01, in the TypeScript suite, compares each conformance source's tree, and what typescript-estree reads of its print, with typescript-estree's own |
| Transpiling gives the same tree, which means what the source means | TRN-01 checks each translation in `conformance/transpilers/` against what both implementations write, and that it prints what the source prints; TRN-02 to TRN-07 are the same tables in both suites |
| Full code coverage in both | the coverage gates below |

Each language's `typescript5/src/<Language>/Syntax.ts` mirrors `python3/mbse/Programs/<Language>/Syntax.py` kind for
kind, field for field and in the same order; a kind added to one and not the other changes the grammar, and CONF-02
fails.

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
| The parser | tree-sitter's Python binding, with the tree-sitter-cpp and tree-sitter-python wheels | web-tree-sitter, with each grammar's wasm, loaded by a top-level `await` when a language's `_Parser` is first imported; `Framework/_TreeSitter` initializes web-tree-sitter once for all | web-tree-sitter needs no native build; the wasm is the same grammar, pinned to the same version | PRS-01, PYPRS-01 |
| Checking Python trees against CPython | PYPRS-01 compares CPython's `ast` of the conformance source with that of its print | none | TypeScript cannot run CPython; CONF-02 makes TypeScript's tree Python's | PYPRS-01 |
| Checking TypeScript trees against typescript-estree | none | TSPRS-01 compares the conformance sources' trees, and typescript-estree's reading of their print, with typescript-estree's | Python cannot run typescript-estree; CONF-02 makes Python's tree TypeScript's | TSPRS-01 |
| Identifiers of TypeScript | `str.isidentifier()` with `$` read as `_` | a regular expression of Unicode's `XID_Start` and `XID_Continue`, with `$` read as `_` | as Python's identifiers | TS-02 |
| Python identifiers | `str.isidentifier()` and `keyword.iskeyword()` | a regular expression of Unicode's `XID_Start` and `XID_Continue`, and Python's keywords | each runtime's own Unicode tables, which agree but for characters one runtime's Unicode version has and the other's lacks | PY-02 |
| Positions | the text is passed to tree-sitter as UTF-16LE, and its byte offsets converted to code points | converted from UTF-16 units to code points | each runtime's own string offsets; tree-sitter reads UTF-16 in both, since its error recovery depends on the encoding | PRS-12, TSPRS-12 |
| Import paths | `mbse.Programs.Framework`, `mbse.Programs.Ccpp` (`.Syntax`, `.Definitions`, `.Ccpp17`, `.Ccpp20`), `mbse.Programs.Python` (`.Syntax`, `.Definitions`, `.Python312`, `.Python314`) `mbse.Programs.TypeScript` (`.Syntax`, `.Definitions`, `.TypeScript50`, `.TypeScript59`, `.ECMAScript2020`, `.ECMAScript2025`) and `mbse.Programs.Transpilers` (`.TypeScriptToPython`), in the shared `mbse` namespace package | `@mbse/programs/Framework`, `@mbse/programs/Ccpp`, `@mbse/programs/Python`, `@mbse/programs/TypeScript` and `@mbse/programs/Transpilers`, with the same modules as paths; `@mbse/schemas` is a `file:` dependency on the submodule | a module specifier is a path, not a dotted name | all |
| TypeScript's meanings | `MEANINGS` maps an entity's kind to a `frozenset` of meanings | `MEANINGS` maps it to a `ReadonlySet` | each language's idiom | TSDEF-04 |
| Running transpiled programs | TRN-01 runs each translation with `exec` and compares what it prints with `.out` | TRN-01 runs each TypeScript program in Node (compiled by `typescript`'s `transpileModule`, run by `vm`) and compares what it logs with `.out` | each implementation runs the language it is written in; together they check that the source and its translation print the same | TRN-01 |
