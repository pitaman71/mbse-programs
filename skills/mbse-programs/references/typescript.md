# mbse-programs in TypeScript

Import each language from `@mbse/programs/<Language>` (`Ccpp`, `Python`, `TypeScript`): its `Syntax`, its
`Definitions` and its standards. The traversals are `@mbse/programs/Framework/Syntax`'s, the errors
`@mbse/programs/Framework`'s `Errors`, the transpilers `@mbse/programs/Transpilers` and the bridges
`@mbse/programs/Bridges`. The API mirrors Python name for name, snake_case included (`add_args`, `function_`,
`visit_Return`), and writes the same JSON byte for byte.

## A complete program

The same program as in Python.

```typescript
import { Expressions as E } from "@mbse/expressions";
import * as PythonDialect from "@mbse/expressions/Dialects/Python";
import * as Translators from "@mbse/expressions/Translators";
import { Python as Bridge } from "@mbse/programs/Bridges";
import { Errors } from "@mbse/programs/Framework";
import { Parents, Transformer, copy, same, walk, type SyntaxNode } from "@mbse/programs/Framework/Syntax";
import { Definitions, Python312, Python314, PythonStandard, Syntax as P } from "@mbse/programs/Python";
import { TypeScriptToPython } from "@mbse/programs/Transpilers";
import { TypeScript59, Syntax as T } from "@mbse/programs/TypeScript";
import { JSON as SchemaJSON } from "@mbse/schemas/Framework";

const check = (condition: boolean, message: string) => { if (!condition) throw new Error(message); };
const Py = P.LANGUAGE.Builders; // a fluent builder per kind, typed from the language: one setter per property

// Parse source into a tree of the language's own abstract syntax (Python's follows `ast`), and print it back.
const module = Python314.parse("def area(w, h):\n    x = w * h\n    return x\n\n\ndef perimeter(w, h):\n    x = 2 * (w + h)\n    return x\n") as P.Module;
check(Python314.print(module).startsWith("def area(w, h):\n    x = w * h\n"), "printed");

// Rename one variable by what names refer to, never by spelling: perimeter's x is another entity.
const program = Definitions.define(module);
const [x] = program.lookup("x", (module.body[0] as P.FunctionDef).body[0]);
for (const node of walk(module)) {
  if (node instanceof P.Name && x !== undefined && Definitions.referents(program, node).includes(x)) node.id!.spelling = "result";
}
check(Python314.print(module).includes("result = w * h") && Python314.print(module).includes("x = 2 * (w + h)"), "renamed");

// Rewrite by kind: a Transformer's visit_<Kind> returns what replaces each syntax node (a list splices statements).
class LogReturns extends Transformer {
  visit_Return(node: P.Return): SyntaxNode[] {
    const log = Py.Expr().value((b) => b.Call().func((b) => b.Name().id("log")).add_args(copy(node.value as P.Expression))).create();
    return [log, node]; // copy: a syntax node has one parent
  }
}
new LogReturns().visit(module);
check(P.LANGUAGE.validate(module).length === 0 && Python314.print(module).includes("log(result)"), "rewritten");
check(new Parents(module).path((module.body[0] as P.FunctionDef).body[1] as SyntaxNode) === "body[0].body[1]", "path");

// Build a tree: the printer adds the parentheses precedence needs.
const sum = ((Python314.parse("a + b\n") as P.Module).body[0] as P.Expr).value;
const twice = Py.BinOp().left(sum).op("*").right((b) => b.Constant().spelling("2")).create();
check(Python314.print(twice).trim() === "(a + b) * 2", "parenthesized");

// Standards check, parse and print only what their version has.
const modern = Python314.parse('greeting = t"hello {name}"\n');
check(Python312.check(modern)[0] === "body[0].value: TemplateStr needs Python 3.14", "checked");
try {
  Python312.parse('greeting = t"hello {name}"\n');
  check(false, "parsed");
} catch (error) {
  check(error instanceof Errors.ParseError && error.message.startsWith("line 1, column 12"), "parse error");
}
check(new PythonStandard(3, 15).check(modern).length === 0, "3.15");

// Trees are mbse-schemas data: a JSON snapshot, byte-identical in both implementations, reads back the same.
const text = SchemaJSON.ToJSON(P.LANGUAGE.Builders).Reachable(P.Module.Schema, module);
check(same(SchemaJSON.FromJSON(P.LANGUAGE.Builders).Reachable(P.Module.Schema, text) as SyntaxNode, module), "snapshot");

// Transpile TypeScript to Python, tree to tree.
const ts = TypeScript59.parse("for (let i = 0; i < 3; i++) {\n    console.log(i * 2);\n}\n") as T.Program;
check(Python314.print(TypeScriptToPython.transpile(ts)) === "for i in range(0, 3):\n    print(i * 2)\n", "transpiled");

// Bridge a constraint kept as data (mbse-expressions) into a Python function, and code back into a constraint.
const self = E.variable("this");
const constraint = E.literal(2.0).le(self.celsius).and_(self.celsius.le(8.0)).data;
const term = Translators.between(E.DIALECT, PythonDialect.Expressions.DIALECT).forward(constraint);
check(Python314.print(Bridge.function_("in_range", ["this"], term)).trim()
  === "def in_range(this):\n    return 2.0 <= this.celsius and this.celsius <= 8.0", "bridged");
const back = Bridge.term(((Python314.parse("this.hours <= 48\n") as P.Module).body[0] as P.Expr).value!);
check((Translators.between(PythonDialect.Expressions.DIALECT, E.DIALECT).forward(back) as E.OfOperation.Data).name === "le", "read back");
```

## Differences from Python

| Python | TypeScript |
|---|---|
| `P.FunctionDef(name=...)`, keyword properties | `new P.FunctionDef({ name: ... })`; builders are usually simpler |
| `isinstance(node, P.Name)` | `node instanceof P.Name`, which narrows the type; `as` where the kind is known (`module.body[0] as P.FunctionDef`) |
| optional children read freely | strict null checks: `node.id!.spelling`, `expr.value!` |
| `PythonStandard(3, 15)`, `TypeScriptStandard(5, 9, jsx=True)` | `new PythonStandard(3, 15)`, `new TypeScriptStandard(5, 9, true)`, `new CcppStandard(2011, "C")` |
| `ECMAScript2025.JSX` | the same: `ECMAScript2025.JSX` |
| `Transformer` subclass with `def visit_Return(self, node)` | `class X extends Transformer { visit_Return(node: P.Return) { ... } }` |
| `program.entities()` and entities' `repr` (`<variable area.x>`) | `[...program.entities()]`, and `String(entity)` for the same text |
| `JSON.ToJSON(...).Reachable(schema, tree, indent=2)` | `JSON.ToJSON(...).Reachable(schema, tree, { indent: 2 })`, from `@mbse/schemas/Framework` |
| `from mbse.Programs.Transpilers.TypeScriptToPython import transpile` | `import { TypeScriptToPython } from "@mbse/programs/Transpilers"`, then `TypeScriptToPython.transpile(program)` |
| Python generated by a transpiler or a bridge can be run with `exec` | TypeScript can't run Python; mbse-expressions' Python dialect evaluates a bridged constraint's term (`PythonDialect.Evaluators.OfAny`) |
| the parsers load as the module is imported | the same: web-tree-sitter initializes once, at import, with top-level `await` (ES modules only) |

## Go deeper

| Topic | Read |
|---|---|
| The Python tutorial's nine case studies, in TypeScript | [typescript5/tutorials/](https://github.com/pitaman71/mbse-programs/blob/main/typescript5/tutorials/README.md) |
| Where the implementations deliberately differ, and why | [EQUIVALENCE.md](https://github.com/pitaman71/mbse-programs/blob/main/docs/EQUIVALENCE.md) |
| Every behavior, as test cases | [the test plan](https://github.com/pitaman71/mbse-programs/blob/main/typescript5/tests/TestPlan.md) |
