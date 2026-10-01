# Conformance corpus

`sources/` holds source files. Each implementation parses them and commits what it writes here, under
`<implementation>/` (`python3/mbse/Programs/Conformance/write.py`, `typescript5/src/Conformance/write.ts`):

| File | Holds |
|---|---|
| `Ccpp.grammar.json`, `Python.grammar.json`, `TypeScript.grammar.json` | each language as data: every kind, its category, fields, choices and availability |
| `<source>.json` | the tree a source parses to, as a reachable snapshot (indent 2) |
| `<source>.cpp`, `<source>.py`, `<source>.ts`, `<source>.tsx` | the text that tree prints to |

| Source | Covers |
|---|---|
| `cpp20.cpp` | every C++20 construct tree-sitter-cpp parses, once or more: a global module fragment and module declarations, imports and exports, directives and comments, namespaces, classes, templates and concepts, every expression and statement kind, lambdas and coroutines |
| `python314.py` | every kind of the Python language, parsed as Python 3.14: imports of every form, type aliases with type parameters and defaults, every literal and string form (f-strings with nested fields, self-documenting fields and format specs, t-strings), decorators, generic classes and functions with every kind of parameter, every operator, comprehensions, every statement, `except*` and unparenthesized `except` types, patterns of every kind, and comments |
| `typescript59.ts` | every kind of the TypeScript language but JSX's, parsed as TypeScript 5.9: imports and exports of every form, with attributes, `import defer` and import equals, every literal, statement and expression, destructuring, generators and async functions, overloads and assertion signatures, decorated and abstract classes with every kind of member, interfaces, every type form, enums, namespaces, ambient modules and `declare global`, `using`, and comments |
| `typescript59-jsx.tsx` | JSX's kinds, parsed as TypeScript 5.9 with JSX: elements, fragments, attributes and spread attributes, namespaced and member names, text with character references, expressions and spread children, and a generic arrow function |

The CONF test suite in each implementation checks that its own files are current, that they are byte-identical to
every other implementation's, and that every implementation's snapshots read back into valid trees that print the same
text and parse back to the same tree.

Regenerate:

```sh
(cd python3 && uv run python -m mbse.Programs.Conformance.write)
(cd typescript5 && npm run conformance)
```
