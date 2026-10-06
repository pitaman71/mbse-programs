---
name: mbse-programs
description: Read, change, check and generate source code as complete syntax trees instead of strings, for C and C++ (Ccpp), Python, TypeScript/JavaScript and Verilog/SystemVerilog, in Python or TypeScript - parse with an established parser (tree-sitter, or slang for Verilog), walk and rewrite trees, resolve what names refer to, check a tree against a language standard (C++17, Python 3.12, ES2025, SystemVerilog 2023, ...), print it as source, store it as JSON, transpile TypeScript to Python, and turn mbse-expressions rules into Python code and back. Use when writing a code generator, refactoring tool, linter, transpiler or codemod; when generated code must respect precedence, scoping or a target language version; when rules or specifications kept as data must become production source code; or when writing code that imports mbse.Programs or @mbse/programs.
---

# mbse-programs

A program here is a tree, not text: each language's complete abstract syntax, as plain mutable objects, built, read and
changed in memory. Text appears only at the edges, where a *standard* (`Python314`, `Ccpp20`, `TypeScript59`, ...)
parses source into a tree, delegating to an established parser (tree-sitter, or slang for Verilog), and prints a tree back with the parentheses and layout its
grammar needs. Trees are [mbse-schemas](https://github.com/pitaman71/mbse-schemas) data, so they save as JSON,
byte-identically in Python (`mbse.Programs`) and TypeScript (`@mbse/programs`).

```python fragment
module = Python314.parse("def area(w, h):\n    return w * h\n")
for node in walk(module):                                  # every syntax node, parents first
    if isinstance(node, P.Identifier) and node.spelling == "area":
        node.spelling = "rectangle_area"
Python314.print(module)                                    # 'def rectangle_area(w, h):\n    return w * h\n'
```

The languages are Ccpp (C and C++ as one tree language), Python (whose kinds follow `ast`), TypeScript (TypeScript
and JavaScript as one, whose kinds follow typescript-estree) and Verilog (Verilog and SystemVerilog as one, whose kinds
follow IEEE 1800's grammar). A transpiler maps TypeScript to Python, and a bridge maps
mbse-expressions' Python dialect to Python's trees and back, so that rules kept as data become code.

## When to use it

- Code must be generated, and pasting strings would get precedence, quoting, scoping or layout wrong.
- Code must be changed structurally: a refactoring, a codemod, a lint fix, a rename that follows scopes.
- Generated or changed code must run on a given language version, and that must be checked, not hoped.
- Rules kept as data (mbse-expressions) must become source code, or existing code must be read into rules.
- Two programs in different languages must share parsed trees.

It is a poor fit for formatting-preserving edits: printers write one fixed layout, and comments inside expressions are
dropped. For the rules themselves use the
[mbse-expressions skill](https://github.com/pitaman71/mbse-expressions/blob/main/skills/mbse-expressions/SKILL.md).
Why the mbse repositories exist, and this one's part: [MBSE.md](https://github.com/pitaman71/mbse-programs/blob/main/MBSE.md).

## Rules that prevent most mistakes

1. **Work on trees; text only at the edges.** Parse, change, then print with the standard you deploy to. Never build
   source by concatenation: build syntax nodes with `LANGUAGE.Builders.<Kind>()` and let the printer parenthesize.
2. **The kinds are the language's own abstract syntax**: Python's are `ast`'s (`FunctionDef`, `BinOp`, `Name`), with
   names as `Identifier` syntax nodes (`node.id.spelling`); TypeScript's are typescript-estree's (`Identifier.name`);
   Ccpp's follow the C++ grammar (`Identifier.spelling`, specifiers and declarators). Look a kind's properties up in
   the grammar (`LANGUAGE.grammar()`) rather than guessing.
3. **A syntax node has one parent.** Using one in two places is invalid (`validate` says "the syntax node is also at
   ..."); `copy(node)` makes the second.
4. **Rename by meaning, not spelling.** `Definitions.define(tree)` gives entities and scopes; `referents(program,
   name)` tells what a name refers to. Matching spellings renames unrelated locals and attributes.
5. **Standards decide what's allowed.** `check(tree)` lists what a standard lacks, by path; `parse` raises `ParseError`
   (line and column, in code points) and `print` raises `PrintError` for constructs it lacks. Other versions:
   `PythonStandard(major, minor)`, `CcppStandard(year, "C++" or "C")`, `TypeScriptStandard(major, minor, jsx)`,
   `ECMAScriptStandard(year, jsx)`, `VerilogStandard(year, "SystemVerilog" or "Verilog")`.
6. **Builders take specs.** A child's setter takes a syntax node, a builder, or a function given the property's kind's
   builder (one kind) or the language's `Builders` (a category); a kind whose only property is an attribute takes the
   value directly (`.name("f")` makes the `Identifier`). Lists have `add_<property>`.
7. **Change trees with the framework's tools**: assignment for small edits, `Transformer.visit_<Kind>` returning a
   replacement (or a list to splice, or None to remove), `Parents` for parent, path, `replace` and `remove`.
8. **Transpilers and bridges refuse at a path.** `TranspileError` names the syntax node they can't translate; they
   don't approximate. What the languages do differently (`%` of negatives, truthiness, number printing) is not
   emulated.
9. **Parsers have documented gaps** (some C++23/26, Python 3.13+ and TypeScript 5.x constructs): such trees build and
   print but don't parse. Verilog's reader refuses what its kinds don't hold (tagged unions, primitives, specify blocks), by name. In
   TypeScript, Verilog parses through the Python implementation, so it needs `python3/`'s environment. Check [languages.md](references/languages.md) before relying on one.
10. **In TypeScript**, narrow syntax nodes with `instanceof` and `as`, make other versions with `new`, and expect
   strict null checks on optional children (`node.id!`).

## Load the reference for your task

| Task | Read |
|---|---|
| Write Python: a complete program, API cheat sheet, traps | [references/python.md](references/python.md) |
| Write TypeScript: the same program, the differences from Python | [references/typescript.md](references/typescript.md) |
| Know a language: its kinds, standards, parsing gaps, printing and definitions | [references/languages.md](references/languages.md) |
| Rewrite trees, transpile between languages, or bridge rules and code | [references/transpiling.md](references/transpiling.md) |

Deeper material is in the repository: `python3/tutorials/` and `typescript5/tutorials/` teach it in eight case
studies, with outputs, and `docs/PROGRAMS.md` holds the design, every parser's gaps and the open questions. Links use
`https://github.com/pitaman71/mbse-programs/blob/main/<path>`; in a checkout, `<path>` is relative to the repository
root.
