# Conformance corpus

`sources/` holds source files. Each implementation parses them and commits what it writes here, under
`<implementation>/` (`python3/mbse/Programs/Conformance/write.py`, `typescript5/src/Conformance/write.ts`):

| File | Holds |
|---|---|
| `Ccpp.grammar.json` | the Ccpp language as data: every kind, its category, fields, choices and availability |
| `<source>.json` | the tree a source parses to, as a reachable snapshot (indent 2) |
| `<source>.cpp` | the text that tree prints to |

| Source | Covers |
|---|---|
| `cpp20.cpp` | every C++20 construct tree-sitter-cpp parses, once or more: a global module fragment and module declarations, imports and exports, directives and comments, namespaces, classes, templates and concepts, every expression and statement kind, lambdas and coroutines |

The CONF test suite in each implementation checks that its own files are current, that they are byte-identical to
every other implementation's, and that every implementation's snapshots read back into valid trees that print the same
text and parse back to the same tree.

Regenerate:

```sh
(cd python3 && uv run python -m mbse.Programs.Conformance.write)
(cd typescript5 && npm run conformance)
```
