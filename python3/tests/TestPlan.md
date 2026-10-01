# Test plan — python3

Scope: everything under `python3/mbse/Programs` (the framework, the Ccpp language, its standards, parser, printer and
definitions) and cross-implementation conformance. The design reference is `../../docs/PROGRAMS.md`; this plan and the
TypeScript one mirror each other case for case, with the deliberate differences of `../../docs/EQUIVALENCE.md`.
mbse-schemas is tested in mbse-schemas.

## Running

```sh
uv run pytest                 # every notebook under tests/
uv run coverage run -m pytest && uv run coverage combine && uv run coverage report   # fails below 100%
uv run python -m mbse.Programs.Conformance.write   # regenerate ../conformance/python3
```

## Suites

| Notebook | Suite | Cases | Focus |
|---|---|---|---|
| `01_Syntax.ipynb` | SYN | 11 | The framework, on a toy language: fields from annotations (also lazily evaluated ones) and their errors; nodes' construction, defaults, `repr` and identity; meta-schemas, registration and JSON snapshots; builders (`create`/`clone`/`update`) and their errors; builders, entries and links against the mbse-schemas visitor protocols; the registry; validation (required fields, categories, choices, sharing, cycles, kinds' own checks); standards' availability and problems; `children`, `walk`, `fold`, `same` and `copy` with sharing and cycles; `Parents` and in-place changes; `Visitor` and `Transformer` |
| `02_Ccpp.ipynb` | CPP | 4 | Ccpp's kinds and categories and its grammar; identifiers; where kinds exist (C++ only, C only, both, since and until which standard); features that depend on fields' values |
| `03_Parse.ipynb` | PRS | 13 | The conformance source parses to a valid tree that prints and parses back the same; names, literals, expressions, lambdas and requires-expressions, declarations, declarators, statements, classes, enumerations and templates, directives and comments, modules and the pre-pass, by tree shape and by printed text; errors with line and column in characters, unsupported syntax, and constructs the standard lacks; C's generic selections, compound literals and designators |
| `04_Print.ipynb` | PRT | 6 | Precedence and the parentheses it adds; declarators' parentheses; every kind printed alone; layout of statements and declarations, and the constructs no parser writes yet; directives, comments and enumerators; printing validates and checks the standard |
| `05_Definitions.ipynb` | DEF | 7 | Entities, scopes and lookup on hand-built scopes; namespaces (reopened, nested, inline, unnamed, aliased, used); classes (members, bases, out-of-line definitions, unnamed classes, friends); enumerations, aliases, concepts, templates and macros; functions, parameters, blocks, statement scopes, labels, lambdas and handlers; `referents` from where a name is; every entity of the conformance source |
| `06_Conformance.ipynb` | CONF | 3 | This implementation's corpus files are current; every other implementation wrote the same bytes; every snapshot reads back into a valid tree that prints the same text |

Total: 44 cases, with the same IDs in the same order in both implementations.
