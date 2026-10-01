# Test plan — python3

Scope: everything under `python3/mbse/Programs` (the framework, and the Ccpp, Python and TypeScript languages with their standards,
parsers, printers and definitions) and cross-implementation conformance. The design reference is `../../docs/PROGRAMS.md`; this plan and the
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
| `06_Python.ipynb` | PY | 4 | Python's kinds, categories and grammar, fields in source order; identifiers (Unicode, keywords, soft keywords); each kind's own checks; where kinds and features exist, by version, from 3.5 to 3.15 |
| `07_PythonParse.ipynb` | PYPRS | 12 | The conformance source parses, prints and parses back the same, and CPython's `ast` of its print is that of the source; literals' spellings; f-strings and t-strings; expressions, with the corrections of tree-sitter-python's precedence; assignment targets; simple and compound statements; definitions and type parameters; patterns; comments; the pre-pass for Python 3.13 and later; errors with line and column |
| `08_PythonPrint.ipynb` | PYPRT | 6 | Precedence, and where a walrus, `yield`, lambda or tuple needs parentheses; every kind printed alone; layout, `elif`, blank lines and comments; f-string fields' text; pattern parentheses and open sequences; printing validates and checks the version |
| `09_PythonDefinitions.ipynb` | PYDEF | 7 | One entity per name per scope, whatever binds it; lookup past class bodies, `global` and `nonlocal`; lambdas, comprehensions and assignment expressions; parameters, decorators, defaults and annotation scopes; pattern captures; what names refer to, and dotted lookup; every entity of the conformance source |
| `10_TypeScript.ipynb` | TS | 4 | The TypeScript language's kinds, categories and grammar, fields in source order; identifiers (Unicode and `$`); each kind's own checks, the dangling `else` included; where kinds and features exist, by ECMAScript edition and TypeScript version, and JSX in the standards made with it |
| `11_TypeScriptParse.ipynb` | TSPRS | 12 | The conformance sources parse, print and parse back the same, and hold every kind; literals' spellings and templates; expressions, with the corrections of tree-sitter-typescript's grouping of `as`, `satisfies` and `!`; statements; functions, classes and their members; modules, imports and exports, namespaces and ambient declarations; types, with the corrections of `readonly`; JSX; comments; the pre-pass; JavaScript through the editions of ECMAScript; errors with line and column |
| `12_TypeScriptPrint.ipynb` | TSPRT | 6 | Precedence of expressions; where an expression starts a statement, an arrow's body, a `for` or a default export; types' parentheses; every kind printed alone; layout and comments; printing validates and checks the standard, and JSX's `<T,>` |
| `13_TypeScriptDefinitions.ipynb` | TSDEF | 7 | What declares and what merges; `var` and block scopes; class and interface members and parameter properties; meanings (value, type, namespace) and what names refer to; namespaces, ambient modules and `import a = b.c`; types' own scopes and JSX's components; every entity of the conformance source |
| `14_Conformance.ipynb` | CONF | 3 | This implementation's corpus files are current, for every language; every other implementation wrote the same bytes; every snapshot reads back into a valid tree that prints the same text |

Total: 102 cases, with the same IDs in the same order in both implementations.
