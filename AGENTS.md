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

## Invariants when changing code

The conventions every mbse repository shares are stated once in mbse-basis; this file cites them and keeps
only what differs here.

- **Vocabulary**: [VOC-007: property](../mbse-basis/docs/VOCABULARY.md#VOC-007), [VOC-026: schema](../mbse-basis/docs/VOCABULARY.md#VOC-026), [VOC-008: term](../mbse-basis/docs/VOCABULARY.md#VOC-008), [VOC-009: syntax node](../mbse-basis/docs/VOCABULARY.md#VOC-009) and [VOC-002: constraint](../mbse-basis/docs/VOCABULARY.md#VOC-002), each qualified with whose it is where it meets a language's own term ([the vocabulary](../mbse-basis/docs/VOCABULARY.md), its introduction).
- **Documents**: navigation lines, the README opening with why, and what this file holds ([Rules for every document](../mbse-basis/docs/README.md#rules-for-every-document)).
- **Equivalence**: [PRI-028: both implementations change together](../mbse-basis/docs/PRINCIPLES.md#PRI-028), [PRI-037: the same conformance corpora](../mbse-basis/docs/PRINCIPLES.md#PRI-037), [PRI-038: the same cases in both languages](../mbse-basis/docs/PRINCIPLES.md#PRI-038), [PRI-039: 100% coverage of both](../mbse-basis/docs/PRINCIPLES.md#PRI-039) and [PRI-040: deliberate differences listed](../mbse-basis/docs/PRINCIPLES.md#PRI-040), the differences listed in `docs/EQUIVALENCE.md`. Here: each language's `Syntax.ts` mirrors its `Syntax.py` kind for kind and property for property, in the same order; regenerate the corpora (Commands) and let CONF-02 compare them.
- **Tests and tutorials**: [PRI-035: tests are notebooks: one suite each, the same case IDs in the same order in both languages](../mbse-basis/docs/PRINCIPLES.md#PRI-035); [PRI-034: tutorials run as tests, committed with their outputs](../mbse-basis/docs/PRINCIPLES.md#PRI-034). `pytest` and `npm test` run `tutorials/` beside `tests/`.
- **The skill**: [PRI-036: every program in a skill is complete and run; fragments are tagged as fragments](../mbse-basis/docs/PRINCIPLES.md#PRI-036), which SKL-02 checks. After editing `skills/mbse-programs/`, run `skills/sync.sh`; SKL-01 fails until the packaged copies match (the copy [PRI-016: guidance written once](../mbse-basis/docs/PRINCIPLES.md#PRI-016) plans to remove). SKL-03 checks every link in this file, `llms.txt` and the skill.
- **Work**: [PRI-029: parallel work in polyrepo workspaces](../mbse-basis/docs/PRINCIPLES.md#PRI-029), [PRI-031: the version is the contract](../mbse-basis/docs/PRINCIPLES.md#PRI-031), [PRI-032: a sibling's gap is reported, not worked around](../mbse-basis/docs/PRINCIPLES.md#PRI-032) and [PRI-033: work lands by branch and pull request](../mbse-basis/docs/PRINCIPLES.md#PRI-033).
- **Behavior is decided in mbse-basis items**: the capabilities of [FEA-008: expressive program models](../mbse-basis/docs/features/FEA-008.md), recorded as the basis says ([Detail files](../mbse-basis/docs/README.md#detail-files)).
- **Trees are complete** ([CAP-036: complete kinds for Python, TypeScript and C and C++](../mbse-basis/docs/capabilities/CAP-036.md)). A construct of any standard of the language is a tree of its kinds, whether or not the parser
  reads it. A new kind records where it exists (`SINCE`, `FEATURES`, or `EXTENSION`), and the printer prints it.
- **Transpilers never touch text** ([PRI-006: text is one more dialect](../mbse-basis/docs/PRINCIPLES.md#PRI-006); [PRI-019: fluent builder syntax](../mbse-basis/docs/PRINCIPLES.md#PRI-019)). Everything a transpiler needs is on the tree, in `Framework.Syntax`'s traversals or
  in `Definitions`; only standards parse and print. Transpilers build syntax nodes with the target language's fluent
  builders (`LANGUAGE.Builders.<Kind>()`), not with constructors or helpers of their own. A transpiler's programs are in
  `conformance/transpilers/`: a program's `.out` is what Node prints when it runs, and its translation (`.py`) is
  regenerated with the corpora. A construct outside the transpiler's subset raises `TranspileError`, never translates
  into code that means otherwise.
- **The parsers are pinned.** tree-sitter-cpp 0.23.4, tree-sitter-python 0.25.0 and tree-sitter-typescript 0.23.2, in
  both implementations (the Python wheels and the npm packages' wasm), so their trees are the same; both pass tree-sitter
  UTF-16, so its error recovery is the same too. Upgrading one is a change to both, and to the gaps and corrections in
  mbse-basis [CAP-026: Python, TypeScript and C and C++ read as written](../mbse-basis/docs/capabilities/CAP-026.md) and [CAP-038: every construct of Python's standards](../mbse-basis/docs/capabilities/CAP-038.md#blocked), [CAP-092: every construct of TypeScript's standards](../mbse-basis/docs/capabilities/CAP-092.md#blocked) and [CAP-093: every construct of C's and C++'s standards](../mbse-basis/docs/capabilities/CAP-093.md#blocked). A Python construct that tree-sitter-python reads unlike CPython is corrected in the converter, and
  checked against CPython's `ast` (PYPRS-01 does it for the conformance source); a TypeScript construct that
  tree-sitter-typescript reads unlike TypeScript is corrected likewise, and checked against typescript-estree, which
  the TypeScript suite runs (TSPRS-01). typescript-estree, an npm package, is the oracle for a TypeScript tree.
- **Verilog reads through slang, in Python only.** pyslang 12.0.0 is pinned in `python3/pyproject.toml`; TypeScript's
  `parse` runs the Python implementation's reader (`python -m mbse.Programs.Verilog.read`) and loads its snapshot, so
  its tests need `uv sync` in `python3/` first. The reader converts slang's tree and refuses, by name and position, what
  the kinds do not hold; it never rewrites source text.
- Never write to `~/.claude/projects/*/memory/` or any hidden memory: what is worth keeping goes in the repository.

## Commands

```sh
python3 ../mbse-basis/scripts/polyrepo.py clone # the siblings, beside this repository, at their pinned commits
python3 ../mbse-basis/scripts/polyrepo.py check # the siblings are present and compatible with siblings.json
cd python3 && uv sync --all-extras              # Python: use uv, never pip
uv run coverage run -m pytest && uv run coverage combine && uv run coverage report
uv run python -m mbse.Programs.Conformance.write

cd typescript5 && nvm use && npm install        # TypeScript: Node 22 or later
npm run coverage                                # type-checks, runs every notebook, gates at 100%
npm run conformance
```

## Related repositories

- [mbse-schemas](https://github.com/pitaman71/mbse-schemas): the schemas trees are serialized with. It is a sibling
  checkout, `../mbse-schemas`, pinned by version and commit in `siblings.json` (see mbse-basis' `scripts/polyrepo.py`).
- [mbse-expressions](https://github.com/pitaman71/mbse-expressions): expressions as data, whose dialects the bridges
  (`Bridges`) carry to and from the languages' trees. It is a sibling checkout, `../mbse-expressions`, pinned in
  `siblings.json`.
