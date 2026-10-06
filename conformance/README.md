<!-- nav -->
[← Equivalence of the implementations](../docs/EQUIVALENCE.md) · [Home](../README.md) · [Python test plan →](../python3/tests/TestPlan.md)

# Conformance corpus

`sources/` holds source files. Each implementation parses them and commits what it writes here, under
`<implementation>/` (`python3/mbse/Programs/Conformance/write.py`, `typescript5/src/Conformance/write.ts`):

| File | Holds |
|---|---|
| `Ccpp.grammar.json`, `Python.grammar.json`, `TypeScript.grammar.json`, `Verilog.grammar.json` | each language as data: every kind, its category, properties, choices and availability |
| `<source>.json` | the tree a source parses to, as a reachable snapshot (indent 2) |
| `<source>.cpp`, `<source>.py`, `<source>.ts`, `<source>.tsx`, `<source>.sv` | the text that tree prints to |

| Source | Covers |
|---|---|
| `cpp20.cpp` | every C++20 construct tree-sitter-cpp parses, once or more: a global module fragment and module declarations, imports and exports, directives and comments, namespaces, classes, templates and concepts, every expression and statement kind, lambdas and coroutines |
| `python314.py` | every kind of the Python language, parsed as Python 3.14: imports of every form, type aliases with type parameters and defaults, every literal and string form (f-strings with nested fields, self-documenting fields and format specs, t-strings), decorators, generic classes and functions with every kind of parameter, every operator, comprehensions, every statement, `except*` and unparenthesized `except` types, patterns of every kind, and comments |
| `typescript59.ts` | every kind of the TypeScript language but JSX's, parsed as TypeScript 5.9: imports and exports of every form, with attributes, `import defer` and import equals, every literal, statement and expression, destructuring, generators and async functions, overloads and assertion signatures, decorated and abstract classes with every kind of member, interfaces, every type form, enums, namespaces, ambient modules and `declare global`, `using`, and comments |
| `systemverilog2023.sv` | every kind of the Verilog language, read by slang as SystemVerilog 2023: a cold-chain logger's datapath and its testbench's classes, with a package of parameters, enumerations, structures, functions and tasks, an interface with modports, modules with ANSI and non-ANSI headers and every form of port, modports with subroutines, clocking blocks and explicit ports, nets and variables of every type, every procedural block, statement and timing control (`force`, `wait fork` and `wait_order` included), elaboration tasks, DPI imports and exports, `bind`, an `extern` module defined with `.*`, rise, fall and turn-off delays, strengths, net types, aliases, `defparam` and time units, generate loops, conditionals and cases, instantiation of every form, immediate assertions, a clocking block, property and sequence declarations with every operator, concurrent assertions, `expect`, cycle delays, `let` and labels, a covergroup with bins of every kind and crosses, attributes on items, ports, statements, operators and calls, every expression, macro uses, compiler directives and conditional compilation, and a testbench package of an interface class, a virtual class with random and protected properties and extern and pure virtual methods, derived classes, a final class with default arguments, methods and constraints with specifiers, a conditional with an `` `ifdef `` condition, constructors, copies, dynamic arrays and virtual interfaces, constraints of every kind, `randomize() with`, array methods with `with` and `randcase`, `randsequence`, checkers and their instances, package exports, a user-defined net, tagged and soft unions with `matches` in `case`, `if` and `?:`, user-defined primitives, combinational and sequential, gates, switches and pulls, a specify block with specify parameters, module paths, timing checks and pulse styles, `covergroup extends` with `super.new(default)`, a `@@` covergroup, `matches` in crosses, a non-ANSI interface port, attributes on members, ports, connections and coverage and clocking items, a sequence argument, and a configuration of the design's libraries; it includes `defs.svh`, which is read with it, not on its own |
| `typescript59-jsx.tsx` | JSX's kinds, parsed as TypeScript 5.9 with JSX: elements, fragments, attributes and spread attributes, namespaced and member names, text with character references, expressions and spread children, and a generic arrow function |

`transpilers/<transpiler>/` holds the programs of each transpiler (`typescript-to-python/` so far): for each program,
the source (`<program>.ts`), what it prints when it runs (`<program>.out`, from Node), and its translation
(`<program>.py`), which both implementations write identically. The TRN suite checks that the translations are current,
and that they print what the programs print.

The CONF test suite in each implementation checks that its own files are current, that they are byte-identical to
every other implementation's, and that every implementation's snapshots read back into valid trees that print the same
text and parse back to the same tree.

Regenerate:

```sh
(cd python3 && uv run python -m mbse.Programs.Conformance.write)
(cd typescript5 && npm run conformance)
```

---

<!-- nav -->
[← Equivalence of the implementations](../docs/EQUIVALENCE.md) · [Home](../README.md) · [Python test plan →](../python3/tests/TestPlan.md)
