# Test plan — typescript5

Scope: everything under `typescript5/src` (the framework, and the Ccpp and Python languages with their standards,
parsers, printers and definitions) and cross-implementation conformance. The design reference is `../../docs/PROGRAMS.md`; this plan and the
Python one mirror each other case for case, with the deliberate differences of `../../docs/EQUIVALENCE.md`.
mbse-schemas is tested in mbse-schemas.

## Running

```sh
npm test                      # type-check, then every notebook under tests/
npm run coverage              # fails below 100% statements, branches, functions or lines
npm run conformance           # regenerate ../conformance/typescript5
```

## Suites

| Notebook | Suite | Cases | Focus |
|---|---|---|---|
| `01_Syntax.ipynb` | SYN | 11 | as in Python; SYN-01 reads fields from specs (Python's annotation cases have no counterpart), SYN-02 shows nodes with `toString` |
| `02_Ccpp.ipynb` | CPP | 4 | as in Python |
| `03_Parse.ipynb` | PRS | 13 | as in Python, through web-tree-sitter; PRS-12's positions are converted from UTF-16 units |
| `04_Print.ipynb` | PRT | 6 | as in Python |
| `05_Definitions.ipynb` | DEF | 7 | as in Python |
| `06_Python.ipynb` | PY | 4 | as in Python |
| `07_PythonParse.ipynb` | PYPRS | 12 | as in Python, but for PYPRS-01's check against CPython, which TypeScript cannot run |
| `08_PythonPrint.ipynb` | PYPRT | 6 | as in Python |
| `09_PythonDefinitions.ipynb` | PYDEF | 7 | as in Python |
| `10_Conformance.ipynb` | CONF | 3 | as in Python, from this side |

Total: 73 cases, with the same IDs in the same order in both implementations.
