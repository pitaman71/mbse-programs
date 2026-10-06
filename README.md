<!-- nav -->
[Why the mbse repositories exist →](MBSE.md)

# mbse-programs

`mbse-programs` is where executable specifications become production source code: each target language's complete
syntax tree is data, so generators build and rewrite real programs, not text templates, and print them through each
language's established tooling. It is the code layer of the mbse repositories' [executable specifications](MBSE.md).

Programs as language-neutral data: complete abstract syntax trees, which a transpiler builds, reads and rewrites in
memory without ever parsing or printing a string. Each language's trees cover the union of its most recent standards,
every detail included, and record which standard has each construct. Standards parse source text into trees, delegating
to an established parser, and print trees back into source text. Trees are [mbse-schemas](https://github.com/pitaman71/mbse-schemas)
data, so they can be stored and sent as JSON or YAML.

The languages are Ccpp, C and C++ as one tree language, with C++17 and C++20 parsed by
[tree-sitter-cpp](https://github.com/tree-sitter/tree-sitter-cpp); Python, whose kinds follow Python's own `ast`
module through Python 3.15, with Python 3.12 and 3.14 parsed by
[tree-sitter-python](https://github.com/tree-sitter/tree-sitter-python); and TypeScript, TypeScript and JavaScript as
one tree language whose kinds follow typescript-estree, with TypeScript 5.0 and 5.9 and ES2020 and ES2025, each with
JSX or without, parsed by [tree-sitter-typescript](https://github.com/tree-sitter/tree-sitter-typescript); and Verilog,
Verilog and SystemVerilog as one tree language, with Verilog-2005 and SystemVerilog 2017 and 2023 read by
[slang](https://github.com/MikePopoloski/slang), a complete SystemVerilog front end. A first transpiler translates a
subset of TypeScript into Python, tree to tree.

```python
from mbse.Programs.Ccpp import Ccpp17, Ccpp20, Syntax as S
from mbse.Programs.Framework.Syntax import walk

unit = Ccpp20.parse("int twice(int x) { return x * 2; }\nint y = twice(3);\n")
for node in walk(unit):
    if isinstance(node, S.Identifier) and node.spelling == "twice":
        node.spelling = "doubled"
Cc = S.LANGUAGE.Builders   # a fluent builder per kind
unit.items.append(Cc.StaticAssertDeclaration().keyword("static_assert").condition(
    lambda b: b.BinaryExpression().left(Cc.IntegerLiteral().spelling("1")).operator("<=>")
    .right(Cc.IntegerLiteral().spelling("2"))).create())
Ccpp20.print(unit)   # 'int doubled(int x) {\n    return x * 2;\n}\nint y = doubled(3);\nstatic_assert(1 <=> 2);\n'
Ccpp17.check(unit)   # ["items[2].condition: BinaryExpression.operator '<=>' needs C++20"]
```

```typescript
import { Ccpp17, Ccpp20, Syntax as S } from "@mbse/programs/Ccpp";
import { walk } from "@mbse/programs/Framework/Syntax";

const unit = Ccpp20.parse("int twice(int x) { return x * 2; }\nint y = twice(3);\n");
for (const node of walk(unit)) {
  if (node instanceof S.Identifier && node.spelling === "twice") node.spelling = "doubled";
}
const Cc = S.LANGUAGE.Builders; // a fluent builder per kind, typed
unit.items.push(Cc.StaticAssertDeclaration().keyword("static_assert").condition((b) => b.BinaryExpression()
  .left(Cc.IntegerLiteral().spelling("1")).operator("<=>").right(Cc.IntegerLiteral().spelling("2"))).create());
Ccpp20.print(unit);
Ccpp17.check(unit);
```

The same, for Python:

```python
from mbse.Programs.Framework.Syntax import walk
from mbse.Programs.Python import Python314, Syntax as P

module = Python314.parse("def twice(x):\n    return x * 2\n\nprint(twice(3))\n")
for node in walk(module):
    if isinstance(node, P.Identifier) and node.spelling == "twice":
        node.spelling = "doubled"
Py = P.LANGUAGE.Builders
module.body.insert(0, Py.Import().is_lazy(True).add_names(lambda b: b.name(lambda b: b.add_names("json"))).create())
Python314.check(module)   # ['body[0]: Import.is_lazy needs Python 3.15']
module.body[0].is_lazy = False
Python314.print(module)   # 'import json\n\n\ndef doubled(x):\n    return x * 2\n\n\nprint(doubled(3))\n'
```

And for TypeScript, whose JavaScript is the editions of ECMAScript:

```python
from mbse.Programs.Framework.Syntax import walk
from mbse.Programs.TypeScript import ECMAScript2025, TypeScript59, Syntax as T

program = TypeScript59.parse("function twice(x: number) { return x * 2; }\nconst y = twice(3);\n")
for node in walk(program):
    if isinstance(node, T.Identifier) and node.name == "twice":
        node.name = "doubled"
TypeScript59.print(program)   # 'function doubled(x: number) {\n    return x * 2;\n}\nconst y = doubled(3);\n'
ECMAScript2025.check(program)[0]   # 'body[0].params[0].typeAnnotation: TSTypeAnnotation is not ECMAScript'
```

It has two equivalent implementations, in Python and TypeScript, with the same API, the same messages, the same trees
and byte-identical JSON. Python imports it from `mbse.Programs` (next to `mbse.Schemas`, in the shared `mbse` namespace
package), TypeScript from `@mbse/programs` (next to `@mbse/schemas`).

## Getting started

mbse-programs depends on [mbse-schemas](https://github.com/pitaman71/mbse-schemas) and
[mbse-expressions](https://github.com/pitaman71/mbse-expressions), which live beside it as sibling checkouts. Clone this
repository, then the siblings at the commits it pins (`siblings.json`):

```sh
git clone git@github.com:pitaman71/mbse-programs.git
python3 mbse-programs/scripts/siblings.py clone   # mbse-schemas and mbse-expressions, at their pinned commits
cd mbse-programs
```

`clone` skips a sibling that is already there, so repositories cloned side by side by hand are used as they are.
A sibling it clones is checked out at its pinned commit, in detached HEAD; to change it, switch to a branch first
(`git -C ../mbse-schemas switch main`). `python3 scripts/siblings.py check` reports when it has moved past its
pinned commit, which is expected while developing; see `scripts/siblings.py help` for `check --strict` and `pin`.
`scripts/siblings.py` runs the tool kept in mbse-schemas (`../mbse-schemas/scripts/siblings.py`), cloning
mbse-schemas first if it is missing.

For parallel work (several agents, or several tasks at once), give each its own workspace: worktrees of this
repository and of its siblings, side by side, so that each installs its own siblings and none sees another's
half-finished changes. A worktree of this repository alone does not work, since its siblings would not be beside it.

```sh
python3 scripts/siblings.py workspace ../worktrees/a --branch a                     # this repository on a
python3 scripts/siblings.py workspace ../worktrees/b --branch b --edit mbse-schemas # and mbse-schemas too
python3 scripts/siblings.py land ../worktrees/b                                     # once done: merged, tagged, removed
python3 scripts/siblings.py push                                                    # then published, siblings first
python3 scripts/siblings.py remove ../worktrees/a                                   # or abandoned (branches are kept)
```

`land` fast-forwards each repository's checkout to its workspace branch, siblings before their dependents, tags each
new version `v<version>`, and removes the workspace and its merged branches. It refuses, before changing anything, a
branch that does not fast-forward, or a dependent that pins an edited sibling at another commit than its branch, so
that the pinned commits are the ones landed. `push` then pushes this repository and its siblings, siblings first, so
that every pinned commit is on its remote before the pin is; it pushes only what the remote lacks, so it is safe to
rerun. `land --push` does both.

Python (3.11+, managed with [uv](https://docs.astral.sh/uv/)); the siblings are installed from their checkouts:

```sh
cd python3
uv sync --all-extras
uv run pytest
```

TypeScript (Node 22 or later; with [nvm](https://github.com/nvm-sh/nvm), `nvm use` picks the version in `.nvmrc`).
`npm install` checks the siblings, links `@mbse/schemas` to the sibling checkout and installs its own dependencies:

```sh
cd typescript5
nvm use
npm install
npm test                       # type-check and run the test suites and the tutorials
```

## Documentation

| Read | For |
|---|---|
| [Python tutorial](python3/tutorials/README.md), [TypeScript tutorial](typescript5/tutorials/README.md) | Eight case studies, from code as text to code generated from rules: trees, rewriting, standards, names, three languages, snapshots, transpiling and bridges. Start here. |
| [Programs design](docs/PROGRAMS.md) | The design: trees, standards, Ccpp, Python and TypeScript, parsing and its gaps, printing, definitions, transpiling, bridges to mbse-expressions, and open questions |
| [Equivalence](docs/EQUIVALENCE.md) | How the two implementations are kept equivalent, and where they deliberately differ |
| [Guide for AI agents](AGENTS.md), [Agent skill](skills/mbse-programs/SKILL.md), [Summary for LLMs](llms.txt) | Guidance for AI agents, layered so each loads only what its task needs. The skill also ships inside both packages |
| [Python test plan](python3/tests/TestPlan.md), [TypeScript test plan](typescript5/tests/TestPlan.md) | The test suites |
| [Conformance corpus](conformance/README.md) | The shared corpus both implementations must parse, write and print identically, and the transpilers' programs |

## Repository layout

```
docs/                     the design (PROGRAMS.md) and how the implementations are kept equivalent (EQUIVALENCE.md)
python3/                  Python implementation: mbse/Programs (Framework, Ccpp, Python, TypeScript, Transpilers, Bridges, Conformance), tests and tutorials
typescript5/              TypeScript implementation: src (Framework, Ccpp, Python, TypeScript, Transpilers, Bridges, Conformance), tests and tutorials
skills/                   the agent skill (SKILL.md plus per-task references); skills/sync.sh copies it into both packages
conformance/              the corpus's sources, the files each implementation writes from them, and the transpilers'
                          programs
```

## Status

Built in both languages: the framework (trees, meta-schemas and builders, validation, standards, traversal and
in-place rewriting, and definitions with lookup), and four languages:

- Ccpp: 171 kinds covering C++26 and C23, the standards C++17 and C++20 (and any year of C++ or C), parsing through
  tree-sitter-cpp 0.23.4, printing, and the definitions of a translation unit.
- Python: 86 kinds following `ast` through Python 3.15, the versions 3.12 and 3.14 (and any other), parsing through
  tree-sitter-python 0.25.0 with nine corrections of its grammar, printing, and the definitions of a module with
  Python's scoping. Checked against CPython 3.14 on its standard library.
- TypeScript: 163 kinds following typescript-estree through TypeScript 5.9 and ES2025, with JSX, the standards
  TypeScript 5.0 and 5.9 and ES2020 and ES2025 (and any other version or edition), each with JSX or without, parsing
  through tree-sitter-typescript 0.23.2 with corrections of its grammar, printing, and the definitions of a program,
  which keep values, types and namespaces apart. Checked against typescript-estree on 1,857 files.
- Verilog: 280 kinds covering SystemVerilog 2023's design subset and its verification constructs (design units, ports of
  every form, parameters, data types, declarations, procedural blocks, statements, generate constructs, instantiation,
  functions and tasks, classes with their properties, methods and objects, constraints, `randomize() with` and
  `randcase`, `randsequence`, sequences and properties, concurrent and immediate assertions, checkers, clocking blocks,
  `let`, covergroups, attributes, every expression, tagged unions and `matches`, strengths, net types, aliases,
  `defparam`, time units, gates, user-defined primitives, specify blocks, configurations and compiler directives), with
  Verilog as a family of its own; the standards Verilog-2005 and SystemVerilog 2017 and 2023 (and any other year of
  either), reading through slang 12.0.0 (`pyslang`), which TypeScript runs through the Python implementation, printing,
  and the definitions of a source file with packages, imports, classes and hierarchical scopes. Comments, directives and
  conditional compilation are kept as trees, and what is outside the kinds (attributes on modport ports, `extern`
  primitives) is refused by name.

And one transpiler, TypeScript to Python, over the subset of TypeScript that ordinary code is written in: statements,
functions, classes, enums, imports and type annotations, with JavaScript's common globals and methods mapped to
Python's. Its programs print the same in Node and, translated, in CPython.

And one bridge, between mbse-expressions' Python dialect and Python's syntax trees, both ways: a rule stored as data
becomes a Python expression or function, and Python source becomes a rule, in TypeScript too.

Not built yet: the constructs the parsers cannot read ([Parsing, in the design](docs/PROGRAMS.md#parsing), [Parsing
Python](docs/PROGRAMS.md#parsing-python), [Parsing TypeScript](docs/PROGRAMS.md#parsing-typescript)) are built and
printed but not parsed; overloads, dependent names, attributes and properties are not resolved; transpilers beyond the
first are planned.

---

<!-- nav -->
[Why the mbse repositories exist →](MBSE.md)
