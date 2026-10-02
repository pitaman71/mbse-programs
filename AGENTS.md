# Guide for AI agents

mbse-programs represents programs as complete abstract syntax trees, built on
[mbse-schemas](https://github.com/pitaman71/mbse-schemas): plain in-memory objects that a transpiler builds, reads and
rewrites without parsing or printing strings, each language covering the union of its standards, and standards that
parse and print source text by delegating to an established parser. The languages are Ccpp (C and C++, with C++17 and
C++20, parsed by tree-sitter-cpp), Python (kinds following `ast`, with Python 3.12 and 3.14, parsed by
tree-sitter-python) and TypeScript (TypeScript and JavaScript, kinds following typescript-estree, with TypeScript 5.0
and 5.9 and ES2020 and ES2025, with JSX or without, parsed by tree-sitter-typescript). A first transpiler translates a
subset of TypeScript into Python. Two equivalent implementations exist: `python3/` and `typescript5/`.

## Start here

| You want to | Read |
|---|---|
| Use the library: parse, build, rewrite or print trees | [README.md](README.md), then the module docstrings of `Framework/Syntax` and of each language's `Syntax` and `Definitions` |
| Understand a design rule, a known gap or an open question | [docs/PROGRAMS.md](docs/PROGRAMS.md), by section |
| Change the framework, a kind, the parser or the printer | this file, then [docs/EQUIVALENCE.md, Deliberate differences](docs/EQUIVALENCE.md#deliberate-differences) |
| Change or add a transpiler | [docs/PROGRAMS.md, Transpiling](docs/PROGRAMS.md#transpiling), then the transpiler's module docstring |
| Find or add a test case | [python3/tests/TestPlan.md](python3/tests/TestPlan.md) (TypeScript's plan lists only its differences) |
| Model the data trees are stored with | [mbse-schemas' AGENTS.md](https://github.com/pitaman71/mbse-schemas/blob/main/AGENTS.md), in the sibling checkout |

## Invariants when changing code

- **Parallel work happens in workspaces.** Agents working at the same time each get a workspace from
  `python3 scripts/siblings.py workspace <dir> --branch <name>` (with `--edit <sibling>` for a change that spans
  repositories), and install there. A worktree of this repository alone, such as an agent's built-in worktree
  isolation, breaks the relative paths to the siblings.
- **The two implementations are equivalent.** Change both in the same commit, with the same names, the same error
  classes and byte-identical messages. Each language's `Syntax.ts` mirrors its `Syntax.py` kind for kind and property
  for property, in the same order. JSON output must be byte-identical: regenerate the corpora and let CONF-02 compare
  them. A difference not listed in `docs/EQUIVALENCE.md` is a bug.
- **Tests are Jupyter notebooks**, one suite per notebook, with the same case IDs in the same order in both
  languages. Each case is a markdown cell `## ID · title` followed by one code cell. Notebooks are JSON written with
  `indent=1`, `sort_keys=True` and `ensure_ascii=False`.
- **Coverage is 100%** in both languages (statements and branches; in TypeScript also functions and lines). Close a gap
  with an assertion in the shared case, in both suites. Remove code no input reaches rather than excluding it.
- **Trees are complete.** A construct of any standard of the language is a tree of its kinds, whether or not the parser
  reads it. A new kind records where it exists (`SINCE`, `FEATURES`, or `EXTENSION`), and the printer prints it.
- **Transpilers never touch text.** Everything a transpiler needs is on the tree, in `Framework.Syntax`'s traversals or
  in `Definitions`; only standards parse and print. Transpilers build syntax nodes with the target language's fluent
  builders (`LANGUAGE.Builders.<Kind>()`), not with constructors or helpers of their own. A transpiler's programs are in
  `conformance/transpilers/`: a program's `.out` is what Node prints when it runs, and its translation (`.py`) is
  regenerated with the corpora. A construct outside the transpiler's subset raises `TranspileError`, never translates
  into code that means otherwise.
- **The parsers are pinned.** tree-sitter-cpp 0.23.4, tree-sitter-python 0.25.0 and tree-sitter-typescript 0.23.2, in
  both implementations (the Python wheels and the npm packages' wasm), so their trees are the same; both pass tree-sitter
  UTF-16, so its error recovery is the same too. Upgrading one is a change to both, and to the gaps and corrections in
  `docs/PROGRAMS.md`. A Python construct that tree-sitter-python reads unlike CPython is corrected in the converter, and
  checked against CPython's `ast` (PYPRS-01 does it for the conformance source); a TypeScript construct that
  tree-sitter-typescript reads unlike TypeScript is corrected likewise, and checked against typescript-estree, which
  the TypeScript suite runs (TSPRS-01). typescript-estree, an npm package, is the oracle for a TypeScript tree.
- **Behavior is decided in `docs/PROGRAMS.md`.** Record new decisions under Resolved, and put what stays undecided
  under Open questions.

## Commands

```sh
python3 scripts/siblings.py clone            # mbse-schemas, beside this repository, at its pinned tag
python3 scripts/siblings.py check            # the siblings are present and compatible with siblings.json
cd python3 && uv sync --all-extras           # Python: use uv, never pip
uv run coverage run -m pytest && uv run coverage combine && uv run coverage report
uv run python -m mbse.Programs.Conformance.write

cd typescript5 && nvm use && npm install     # TypeScript: Node 22 or later
npm run coverage                             # type-checks, runs every notebook, gates at 100%
npm run conformance
```

## Related repositories

- [mbse-schemas](https://github.com/pitaman71/mbse-schemas): the schemas trees are serialized with. It is a
  sibling checkout, `../mbse-schemas`, pinned by version in `siblings.json` (see `scripts/siblings.py`).
- [mbse-expressions](https://github.com/pitaman71/mbse-expressions): expressions as data, the sibling this repository's
  conventions follow.
