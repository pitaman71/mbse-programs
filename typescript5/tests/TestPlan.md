<!-- nav -->
[← Python test plan](../../python3/tests/TestPlan.md) · [Home](../../README.md)

# Test plan — typescript5

Scope: everything under `typescript5/src` (the framework, and the Ccpp, Python, TypeScript and Verilog languages with their
standards, parsers, printers and definitions, the transpilers and the bridges) and cross-implementation conformance. The design reference is `../../docs/PROGRAMS.md`; this plan and the
Python one mirror each other case for case, with the deliberate differences of `../../docs/EQUIVALENCE.md`.
mbse-schemas is tested in mbse-schemas.

## Running

```sh
npm test                      # type-check, then every notebook under tests/ and tutorials/
npm run coverage              # fails below 100% statements, branches, functions or lines
npm run conformance           # regenerate ../conformance/typescript5
```

## Suites

| Notebook | Suite | Cases | Focus |
|---|---|---|---|
| `01_Syntax.ipynb` | SYN | 11 | as in Python; SYN-01 reads properties from specs (Python's annotation cases have no counterpart), SYN-02 shows syntax nodes with `toString` |
| `02_Ccpp.ipynb` | CPP | 4 | as in Python |
| `03_Parse.ipynb` | PRS | 13 | as in Python, through web-tree-sitter; PRS-12's positions are converted from UTF-16 units |
| `04_Print.ipynb` | PRT | 6 | as in Python |
| `05_Definitions.ipynb` | DEF | 7 | as in Python |
| `06_Python.ipynb` | PY | 4 | as in Python |
| `07_PythonParse.ipynb` | PYPRS | 12 | as in Python, but for PYPRS-01's check against CPython, which TypeScript cannot run |
| `08_PythonPrint.ipynb` | PYPRT | 6 | as in Python |
| `09_PythonDefinitions.ipynb` | PYDEF | 7 | as in Python |
| `10_TypeScript.ipynb` | TS | 4 | as in Python |
| `11_TypeScriptParse.ipynb` | TSPRS | 12 | as in Python, and TSPRS-01 also compares the conformance sources' trees, and what typescript-estree reads of their print, with typescript-estree's own, which Python cannot run |
| `12_TypeScriptPrint.ipynb` | TSPRT | 6 | as in Python |
| `13_TypeScriptDefinitions.ipynb` | TSDEF | 7 | as in Python |
| `14_TypeScriptToPython.ipynb` | TRN | 7 | as in Python, but TRN-01 runs the TypeScript programs themselves in Node, and compares what they print with what the Python side's translations print |
| `15_PythonBridge.ipynb` | BRG | 7 | as in Python, but for the checks against the dialect's `parse`, `ast.literal_eval` and running the function, which need Python |
| `16_Conformance.ipynb` | CONF | 3 | as in Python, from this side |
| `17_Skill.ipynb` | SKL | 3 | as in Python; SKL-02 type-checks the skill's TypeScript program strictly, then runs it |
| `18_Verilog.ipynb` | VLG | 11 | as in Python |
| `19_VerilogRead.ipynb` | VLGRD | 20 | as in Python, reading through the Python implementation; VLGRD-13 reads through it directly, and fails clearly when its interpreter cannot run |
| `20_VerilogPrint.ipynb` | VLGPRT | 14 | as in Python |
| `21_VerilogDefinitions.ipynb` | VLGDEF | 10 | as in Python |

Total: 174 cases, with the same IDs in the same order in both implementations.

---

<!-- nav -->
[← Python test plan](../../python3/tests/TestPlan.md) · [Home](../../README.md)
