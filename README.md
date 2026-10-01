# mbse-programs

Programs as language-neutral data: complete abstract syntax trees, which a transpiler builds, reads and rewrites in
memory without ever parsing or printing a string. Each language's trees cover the union of its most recent standards,
every detail included, and record which standard has each construct. Standards parse source text into trees, delegating
to an established parser, and print trees back into source text. Trees are [mbse-schemas](https://github.com/pitaman71/mbse-schemas)
data, so they can be stored and sent as JSON or YAML.

The first language is Ccpp, C and C++ as one tree language, with C++17 and C++20 parsed by
[tree-sitter-cpp](https://github.com/tree-sitter/tree-sitter-cpp).

```python
from mbse.Programs.Ccpp import Ccpp17, Ccpp20, Syntax as S
from mbse.Programs.Framework.Syntax import walk

unit = Ccpp20.parse("int twice(int x) { return x * 2; }\nint y = twice(3);\n")
for node in walk(unit):
    if isinstance(node, S.Identifier) and node.spelling == "twice":
        node.spelling = "doubled"
unit.items.append(S.StaticAssertDeclaration(keyword="static_assert", condition=S.BinaryExpression(
    left=S.IntegerLiteral(spelling="1"), operator="<=>", right=S.IntegerLiteral(spelling="2"))))
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
unit.items.push(new S.StaticAssertDeclaration({ keyword: "static_assert", condition: new S.BinaryExpression({
  left: new S.IntegerLiteral({ spelling: "1" }), operator: "<=>", right: new S.IntegerLiteral({ spelling: "2" }) }) }));
Ccpp20.print(unit);
Ccpp17.check(unit);
```

It has two equivalent implementations, in Python and TypeScript, with the same API, the same messages, the same trees
and byte-identical JSON. Python imports it from `mbse.Programs` (next to `mbse.Schemas`, in the shared `mbse` namespace
package), TypeScript from `@mbse/programs` (next to `@mbse/schemas`).

## Getting started

mbse-schemas is a git submodule, so clone with it:

```sh
git clone --recurse-submodules git@github.com:pitaman71/mbse-programs.git
```

Python (3.11+, managed with [uv](https://docs.astral.sh/uv/)); mbse-schemas is installed from the submodule:

```sh
cd python3
uv sync --all-extras
uv run pytest
```

TypeScript (Node 22 or later; with [nvm](https://github.com/nvm-sh/nvm), `nvm use` picks the version in `.nvmrc`):

```sh
cd typescript5
nvm use
npm install
npm test                       # type-check and run the test suites
```

## Documentation

| Read | For |
|---|---|
| [`docs/PROGRAMS.md`](docs/PROGRAMS.md) | The design: trees, standards, Ccpp, parsing and its gaps, printing, definitions, and open questions |
| [`docs/EQUIVALENCE.md`](docs/EQUIVALENCE.md) | How the two implementations are kept equivalent, and where they deliberately differ |
| [`AGENTS.md`](AGENTS.md), [`llms.txt`](llms.txt) | Guidance for AI agents |
| [`python3/tests/TestPlan.md`](python3/tests/TestPlan.md), [`typescript5/tests/TestPlan.md`](typescript5/tests/TestPlan.md) | The test suites |
| [`conformance/`](conformance/README.md) | The shared corpus both implementations must parse, write and print identically |

## Repository layout

```
submodules/mbse-schemas/  the framework trees are serialized with
docs/                     the design (PROGRAMS.md) and how the implementations are kept equivalent (EQUIVALENCE.md)
python3/                  Python implementation: mbse/Programs (Framework, Ccpp, Conformance) and tests
typescript5/              TypeScript implementation: src (Framework, Ccpp, Conformance) and tests
conformance/              the corpus's sources, and the files each implementation writes from them
```

## Status

Built in both languages: the framework (trees, meta-schemas and builders, validation, standards, traversal and
in-place rewriting, and definitions with lookup) and Ccpp: 171 kinds covering C++26 and C23, the standards C++17 and
C++20 (and any year of C++ or C), parsing through tree-sitter-cpp 0.23.4, printing, and the definitions of a
translation unit. Not built yet: the constructs tree-sitter-cpp 0.23 cannot parse
([PROGRAMS.md, Parsing](docs/PROGRAMS.md#parsing)) are built and printed but not parsed; overloads and dependent names
are not resolved; further languages (Verilog, Python, TypeScript) are planned.
