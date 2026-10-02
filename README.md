# mbse-programs

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
JSX or without, parsed by [tree-sitter-typescript](https://github.com/tree-sitter/tree-sitter-typescript). A first
transpiler translates a subset of TypeScript into Python, tree to tree.

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

mbse-programs depends on [mbse-schemas](https://github.com/pitaman71/mbse-schemas), which lives beside it as a
sibling checkout. Clone this repository, then the siblings at the versions it pins (`siblings.json`):

```sh
git clone git@github.com:pitaman71/mbse-programs.git
python3 mbse-programs/scripts/siblings.py clone   # mbse-schemas, beside it, at its pinned tag
cd mbse-programs
```

`clone` skips a sibling that is already there, so repositories cloned side by side by hand are used as they are.
A sibling it clones is checked out at its tag, in detached HEAD; to change it, switch to a branch first
(`git -C ../mbse-schemas switch main`). `python3 scripts/siblings.py check` reports when it has moved past its
pinned tag, which is expected while developing; see `scripts/siblings.py` for `check --strict` and `pin`.

Python (3.11+, managed with [uv](https://docs.astral.sh/uv/)); mbse-schemas is installed from the sibling:

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
npm test                       # type-check and run the test suites
```

## Documentation

| Read | For |
|---|---|
| [`docs/PROGRAMS.md`](docs/PROGRAMS.md) | The design: trees, standards, Ccpp, Python and TypeScript, parsing and its gaps, printing, definitions, transpiling, and open questions |
| [`docs/EQUIVALENCE.md`](docs/EQUIVALENCE.md) | How the two implementations are kept equivalent, and where they deliberately differ |
| [`AGENTS.md`](AGENTS.md), [`llms.txt`](llms.txt) | Guidance for AI agents |
| [`python3/tests/TestPlan.md`](python3/tests/TestPlan.md), [`typescript5/tests/TestPlan.md`](typescript5/tests/TestPlan.md) | The test suites |
| [`conformance/`](conformance/README.md) | The shared corpus both implementations must parse, write and print identically, and the transpilers' programs |

## Repository layout

```
docs/                     the design (PROGRAMS.md) and how the implementations are kept equivalent (EQUIVALENCE.md)
python3/                  Python implementation: mbse/Programs (Framework, Ccpp, Python, TypeScript, Transpilers, Conformance) and tests
typescript5/              TypeScript implementation: src (Framework, Ccpp, Python, TypeScript, Transpilers, Conformance) and tests
conformance/              the corpus's sources, the files each implementation writes from them, and the transpilers'
                          programs
```

## Status

Built in both languages: the framework (trees, meta-schemas and builders, validation, standards, traversal and
in-place rewriting, and definitions with lookup), and three languages:

- Ccpp: 171 kinds covering C++26 and C23, the standards C++17 and C++20 (and any year of C++ or C), parsing through
  tree-sitter-cpp 0.23.4, printing, and the definitions of a translation unit.
- Python: 86 kinds following `ast` through Python 3.15, the versions 3.12 and 3.14 (and any other), parsing through
  tree-sitter-python 0.25.0 with nine corrections of its grammar, printing, and the definitions of a module with
  Python's scoping. Checked against CPython 3.14 on its standard library.
- TypeScript: 163 kinds following typescript-estree through TypeScript 5.9 and ES2025, with JSX, the standards
  TypeScript 5.0 and 5.9 and ES2020 and ES2025 (and any other version or edition), each with JSX or without, parsing
  through tree-sitter-typescript 0.23.2 with corrections of its grammar, printing, and the definitions of a program,
  which keep values, types and namespaces apart. Checked against typescript-estree on 1,857 files.

And one transpiler, TypeScript to Python, over the subset of TypeScript that ordinary code is written in: statements,
functions, classes, enums, imports and type annotations, with JavaScript's common globals and methods mapped to
Python's. Its programs print the same in Node and, translated, in CPython.

Not built yet: the constructs the parsers cannot read ([PROGRAMS.md](docs/PROGRAMS.md#parsing),
[Parsing Python](docs/PROGRAMS.md#parsing-python), [Parsing TypeScript](docs/PROGRAMS.md#parsing-typescript)) are
built and printed but not parsed; overloads, dependent names, attributes and properties are not resolved; further
languages (Verilog) are planned, and transpilers beyond the first.
