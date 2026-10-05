<!-- nav -->
[← Why the mbse repositories exist](../../MBSE.md) · [Home](../../README.md) · [1 · Programs as data →](01_Programs_As_Data.ipynb)

# Tutorial: programs as data, in eight case studies

This tutorial teaches mbse-programs by solving real problems, one per notebook, each building on the ones before it. It
starts where a programmer starts, with code as text, and ends with code generated from the rules of an executable
specification: parsed, changed, checked, resolved, shared and translated as trees along the way.

It's written for Python programmers who write code that reads, changes or writes code: refactoring tools, linters,
code generators, transpilers. A TypeScript port with the same case studies and the same answers is the
[TypeScript tutorial](../../typescript5/tutorials/README.md). The rules of case study 8 are mbse-expressions'; its
[tutorial](https://github.com/pitaman71/mbse-expressions/blob/main/python3/tutorials/README.md) explains them. The
[design document](../../docs/PROGRAMS.md) is the reference for everything here.

## Running the notebooks

```sh
cd python3
uv sync --all-extras
uv run --with jupyterlab jupyter lab tutorials/   # or open them in VS Code with the project's .venv as the kernel
```

Each notebook runs top to bottom in a fresh kernel. They're committed with their outputs, so you can just read them;
`uv run pytest tutorials` runs them all as tests. `toolkit.py` holds `outline`, which shows a tree one syntax node per
line.

## The case studies

| # | Notebook | The problem | What you learn |
|---|---|---|---|
| 1 | [Programs as data](01_Programs_As_Data.ipynb) | A generator that pastes strings gets precedence wrong | Parsing into a tree; kinds that follow the language's own syntax tree; attributes and children; printing; building trees with builders; validation |
| 2 | [Changing code safely](02_Changing_Code_Safely.ipynb) | Replacing `print` with a logger, without a regular expression | `walk`; changing syntax nodes in place; `Transformer`; `Parents`, paths, `replace` and `remove`; one parent per syntax node, and `copy` |
| 3 | [Which standard?](03_Which_Standard.ipynb) | Code for laptops on 3.14 and servers on 3.12 | Where kinds and features exist; `check`; parsing and printing refusing what a standard lacks; any version; the grammar as data |
| 4 | [What names refer to](04_What_Names_Refer_To.ipynb) | Renaming one `x` without renaming the others | Entities and scopes; `lookup` and `referents`; a rename that follows scopes; `global` and class bodies |
| 5 | [One framework, three languages](05_One_Framework_Three_Languages.ipynb) | Firmware in C++, a dashboard in TypeScript, a pipeline in Python | Ccpp and TypeScript trees; the same tools in every language; C and C++, TypeScript and ECMAScript standards; definitions in each language |
| 6 | [Trees on the wire](06_Trees_On_The_Wire.ipynb) | A Python analyzer and a TypeScript editor plugin sharing trees | JSON snapshots; reading them back; byte-identical across implementations; the grammar as data |
| 7 | [From one language to another](07_From_One_Language_To_Another.ipynb) | Validation logic in TypeScript, needed in a Python batch job | Transpiling TypeScript to Python; idioms, not copies; classes, getters and enums; refusing at a path |
| 8 | [From rules to code](08_From_Rules_To_Code.ipynb) | A rule kept as data, needed as reviewed Python code | Bridges: rules into functions and modules, code back into rules; what a rule can't hold |

---

<!-- nav -->
[← Why the mbse repositories exist](../../MBSE.md) · [Home](../../README.md) · [1 · Programs as data →](01_Programs_As_Data.ipynb)
