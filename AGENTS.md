# Guide for AI agents

mbse-programs represents programs as complete abstract syntax trees, built on
[mbse-schemas](https://github.com/pitaman71/mbse-schemas): plain in-memory objects that a transpiler builds, reads and
rewrites without parsing or printing strings, each language covering the union of its standards, and standards that
parse and print source text by delegating to an established parser. The languages are Ccpp (C and C++, with C++17 and
C++20, parsed by tree-sitter-cpp), Python (kinds following `ast`, with Python 3.12 and 3.14, parsed by
tree-sitter-python) and TypeScript (TypeScript and JavaScript, kinds following typescript-estree, with TypeScript 5.0
and 5.9 and ES2020 and ES2025, with JSX or without, parsed by tree-sitter-typescript) and Verilog (Verilog and
SystemVerilog, with Verilog-2005 and SystemVerilog 2017 and 2023, read by slang). A first transpiler translates a
subset of TypeScript into Python, and bridges carry expressions between mbse-expressions' Python and SystemVerilog
dialects and the languages' trees. Two equivalent implementations exist: `python3/` and `typescript5/`.

## Start here

| You want to | Read |
|---|---|
| Learn it by example, from code as text to code generated from constraints | [python3/tutorials/README.md](python3/tutorials/README.md), nine case studies; the same in [typescript5/tutorials/](typescript5/tutorials/README.md) |
| Know why the mbse repositories exist, and this one's part in them | [MBSE.md](MBSE.md) |
| Use the library: parse, build, rewrite, check, print, transpile or bridge trees | [skills/mbse-programs/SKILL.md](skills/mbse-programs/SKILL.md), a skill. It loads its references only as needed |
| Understand a design decision, a known gap or an open question | mbse-basis [FEA-008: expressive program models](../mbse-basis/docs/features/FEA-008.md) and its capabilities' detail files |
| Change the framework, a kind, the parser or the printer | this file, then [docs/EQUIVALENCE.md, Deliberate differences](docs/EQUIVALENCE.md#deliberate-differences) |
| Change or add a transpiler | mbse-basis [CAP-088: TypeScript transpiled to Python](../mbse-basis/docs/capabilities/CAP-088.md#transpiling), then the transpiler's module docstring |
| Find or add a test case | [python3/tests/TestPlan.md](python3/tests/TestPlan.md) (TypeScript's plan lists only its differences) |
| Model the data trees are stored with | [mbse-schemas' AGENTS.md](https://github.com/pitaman71/mbse-schemas/blob/main/AGENTS.md), in the sibling checkout |

## Read before any work

Agents must read these mbse-basis documents before doing any work:

- [The mbse basis](../mbse-basis/docs/README.md)
- [Principles](../mbse-basis/docs/PRINCIPLES.md)
- [Features](../mbse-basis/docs/features/README.md)
- [Capabilities](../mbse-basis/docs/capabilities/README.md)

These may be read selectively, on demand: [Vocabulary](../mbse-basis/docs/VOCABULARY.md) and
[Qualities](../mbse-basis/docs/QUALITIES.md).

Never write to `~/.claude/projects/*/memory/` or any hidden memory: what is worth keeping goes in the repository.

## This repository

- The printer prints every kind, a new one included.
- A transpiler finds everything it needs on the tree, in `Framework.Syntax`'s traversals or in `Definitions`.
- Upgrading a pinned parser changes the gaps listed, as blocked, in the capabilities for each language's standards.

## Commands

```sh
python3 ../mbse-basis/scripts/polyrepo.py clone # the siblings, beside this repository, at their pinned commits
python3 ../mbse-basis/scripts/polyrepo.py check # the siblings are present and compatible with siblings.json
cd python3 && uv sync --all-extras              # Python: use uv, never pip
uv run coverage run -m pytest && uv run coverage combine && uv run coverage report
uv run python -m mbse.Programs.Conformance.write

cd typescript5 && nvm use && npm install        # TypeScript: Node 22 or later; Verilog's tests need python3's uv sync
npm run coverage                                # type-checks, runs every notebook, gates at 100%
npm run conformance

skills/sync.sh                                  # after editing skills/mbse-programs/: the packaged copies (SKL-01)
```

## Related repositories

- [mbse-schemas](https://github.com/pitaman71/mbse-schemas): the schemas trees are serialized with. It is a sibling
  checkout, `../mbse-schemas`, pinned by version and commit in `siblings.json` (see mbse-basis' `scripts/polyrepo.py`).
- [mbse-expressions](https://github.com/pitaman71/mbse-expressions): expressions as data, whose dialects the bridges
  (`Bridges`) carry to and from the languages' trees. It is a sibling checkout, `../mbse-expressions`, pinned in
  `siblings.json`.
