/**
 * TypeScriptToPython: translates TypeScript trees into Python trees, without parsing or printing text.
 *
 * `transpile(program)` reads a `TypeScript/Syntax.Program` and returns a `Python/Syntax.Module`, which `Python314`
 * prints. It covers a subset of TypeScript, and throws `TranspileError` at the first syntax node outside it, with the
 * syntax node's path:
 *
 * - Statements: variable declarations (names and array patterns), expressions, `if`, `while`, `do ... while`, `for`
 *   (as `for ... in range(...)` where it counts, as `while` otherwise), `for ... of`, `for ... in`, `switch` without
 *   fall-through, `break`, `continue`, `return`, `throw`, `try`, and blocks.
 * - Declarations: functions (async and generators too), classes (fields, parameter properties, constructors, methods,
 *   accessors, static members and `extends`), enums (of numbers or of strings), imports and exports of names, and type
 *   aliases; interfaces and other type-only declarations are dropped.
 * - Expressions: literals, templates (as f-strings), arrays, object literals (as `SimpleNamespace`), arrow functions
 *   and function expressions (as lambdas, or as functions declared before the statement), calls, `new`, members, every
 *   operator with a Python counterpart, and type assertions, which are dropped.
 * - Types, as annotations: keywords, references, arrays, tuples, unions, literals and records.
 *
 * What JavaScript's globals do is mapped where Python has a counterpart (`console.log` is `print`, `Math.floor` is
 * `math.floor`, `JSON.parse` is `json.loads`, `parseInt` is `int`), but only where the name is the global:
 * `Definitions` tells a global from a name the program declares. A few methods of arrays and strings are mapped by name
 * (`push` is `append`, `length` is `len`, `map` and `filter` are comprehensions), unless a class or interface of the
 * program declares a member of that name. A call to a mapped global or method with arguments its mapping does not take
 * fails.
 *
 * The translation keeps what code means where the two languages agree, and does not emulate where they differ: `%` of a
 * negative number, the truthiness of empty arrays and objects, `==` between values of different types, `+` between a
 * string and a number, and integers beyond 2 ** 53 behave as Python's do.
 */

import type { Entity, Scope } from "../Framework/Definitions.js";
import { TranspileError } from "../Framework/Errors.js";
import { children, copy, type SyntaxNode, Parents, walk } from "../Framework/Syntax.js";
import * as P from "../Python/Syntax.js";
import * as D from "../TypeScript/Definitions.js";
import * as S from "../TypeScript/Syntax.js";

/** Python's keywords, as `keyword.kwlist` lists them. */
const KEYWORDS = new Set(["False", "None", "True", "and", "as", "assert", "async", "await", "break", "class",
  "continue", "def", "del", "elif", "else", "except", "finally", "for", "from", "global", "if", "import", "in", "is",
  "lambda", "nonlocal", "not", "or", "pass", "raise", "return", "try", "while", "with", "yield"]);
/** Names the translation writes, which a name of the program must not take: Python's keywords and builtins it uses. */
const RESERVED: ReadonlySet<string> = new Set([...KEYWORDS, "self", "print", "len", "str", "int", "float", "bool",
  "isinstance", "list", "dict", "set", "range", "map", "filter", "vars", "super", "property", "staticmethod", "object",
  "Exception", "NotImplementedError", "math", "json", "random", "sys", "functools", "SimpleNamespace", "IntEnum",
  "StrEnum", "Any", "Literal"]);
/** Comparisons: TypeScript's operators, and Python's. */
const COMPARISONS: Record<string, P.ComparisonOperator> = {
  "==": "==", "===": "==", "!=": "!=", "!==": "!=", "<": "<", "<=": "<=", ">": ">", ">=": ">=", in: "in",
};
const BINARY = new Set(["+", "-", "*", "/", "%", "**", "<<", ">>", "&", "|", "^"]);

const Py = P.LANGUAGE.Builders;

const isIdentifier = (text: string) => /^[\p{XID_Start}_]\p{XID_Continue}*$/u.test(text);
const is = (kinds: Function[], node: unknown): boolean => kinds.some((k) => node instanceof k);
const notComment = (statements: SyntaxNode[]) => statements.some((s) => !(s instanceof P.Comment));

type Statements = (self: Translator, node: any) => SyntaxNode[];
type Expression = (self: Translator, node: any) => SyntaxNode;
type Global = (self: Translator, node: S.CallExpression) => SyntaxNode;
type Method = (self: Translator, target: SyntaxNode, node: S.CallExpression) => SyntaxNode;

/** Translates one program. Statements become lists of statements: an arrow function with a body, used as a value,
 * becomes a function declared before the statement that uses it. */
class Translator {
  static STATEMENTS = new Map<Function, Statements>();
  static EXPRESSIONS = new Map<Function, Expression>();
  readonly parents: Parents;
  readonly definitions: D.TypeScriptProgram;
  readonly imports = new Set<string>(); // the modules the translation needs
  readonly fromImports = new Map<string, Set<string>>(); // names to import from a module
  pending: SyntaxNode[] = []; // statements that must come before the current one
  lambdas = 0; // how deep in a lambda the translation is, where nothing can be declared
  readonly methods: boolean[] = []; // for each enclosing function, whether `self` is its `this`
  readonly catches = new Set<Entity>(); // the entities a `catch` clause binds
  readonly members: Set<string>;
  readonly taken: Set<string>;
  counter = 0;

  constructor(program: S.Program) {
    this.parents = new Parents(program);
    this.definitions = D.define(program);
    this.members = new Set([...this.definitions.entities()].filter((e) =>
      ["method", "property", "accessor"].includes(e.kind)).map((e) => e.name as string));
    this.taken = new Set([...walk(program)].filter((n) => n instanceof S.Identifier).map((n) =>
      (n as S.Identifier).name as string));
  }

  // Helpers

  error(node: SyntaxNode, message: string | null = null): TranspileError {
    return new TranspileError(message ?? `${node.kind().KIND} is not supported`, this.parents.path(node));
  }

  /** A name no name of the program takes, for a value the translation keeps. */
  fresh(stem: string): string {
    for (;;) {
      this.counter += 1;
      const made = `_${stem}${this.counter}`;
      if (!this.taken.has(made)) {
        this.taken.add(made);
        return made;
      }
    }
  }

  /** The module `module`, imported. */
  module(module: string): P.Name {
    this.imports.add(module);
    return Py.Name().id(module).create();
  }

  /** `imported` from `module`, imported. */
  imported(module: string, imported: string): P.Name {
    if (!this.fromImports.has(module)) this.fromImports.set(module, new Set());
    this.fromImports.get(module)?.add(imported);
    return Py.Name().id(imported).create();
  }

  /** The Python spelling of a TypeScript name: one the translation writes, or a keyword, takes a `_`. */
  static python(text: string): string {
    return RESERVED.has(text) ? text + "_" : text;
  }

  /** Whether `node` names a global: one the program does not declare. */
  isGlobal(node: S.Identifier): boolean {
    return D.referents(this.definitions, node).length === 0;
  }

  // The program

  program(program: S.Program): P.Module {
    const body = this.statements(program.body);
    const head: SyntaxNode[] = [...this.imports].sort().map((m) =>
      Py.Import().add_names(Py.Alias().name(Py.DottedName().add_names(m))).create());
    for (const module of [...this.fromImports.keys()].sort()) {
      const names = [...this.fromImports.get(module) as Set<string>].sort().map((n) =>
        Py.Alias().name(Py.DottedName().names([n])).create());
      head.push(Py.ImportFrom().module(Py.DottedName().names([module])).names(names).create());
    }
    return Py.Module().body([...head, ...body]).create();
  }

  // Statements

  statements(statements: readonly SyntaxNode[]): SyntaxNode[] {
    const out: SyntaxNode[] = [];
    for (const statement of statements) {
      const outer = this.pending;
      this.pending = [];
      const translated = this.statement(statement);
      out.push(...this.pending, ...translated);
      this.pending = outer;
    }
    return out;
  }

  /** A statement as a block's body, which is never empty. */
  block(statement: SyntaxNode): SyntaxNode[] {
    const body = this.statements(statement instanceof S.BlockStatement ? statement.body : [statement]);
    return notComment(body) ? body : [...body, Py.Pass().create()];
  }

  statement(node: SyntaxNode): SyntaxNode[] {
    const method = Translator.STATEMENTS.get(node.constructor);
    if (method === undefined) throw this.error(node);
    return method(this, node);
  }

  comment(node: S.Comment): SyntaxNode[] {
    const text = node.text as string;
    if (!node.block) return [Py.Comment().text(text).trailing(node.trailing).create()];
    return text.split("\n").map((line) => line.replace(/^[ *]+|[ *]+$/g, "")).filter((line) => line !== "")
      .map((line, i) => Py.Comment().text(" " + line).trailing(node.trailing && i === 0).create());
  }

  expressionStatement(node: S.ExpressionStatement): SyntaxNode[] {
    const expression: any = node.expression;
    if (expression instanceof S.AssignmentExpression) return this.assignment(expression);
    if (expression instanceof S.UpdateExpression) {
      return [Py.AugAssign().target(this.target(expression.argument)).op(expression.operator === "++" ? "+" : "-")
        .value(Py.Constant().spelling("1")).create()];
    }
    if (expression instanceof S.UnaryExpression && expression.operator === "delete") {
      return [Py.Delete().targets([this.target(expression.argument)]).create()];
    }
    if (expression instanceof S.CallExpression) {
      const each = this.forEach(expression);
      if (each !== null) return each;
      const mapped = this.setCall(expression);
      if (mapped !== null) return mapped;
    }
    return [Py.Expr().value(this.expression(expression)).create()];
  }

  assignment(node: S.AssignmentExpression): SyntaxNode[] {
    const operator = node.operator as string;
    if (["&&=", "||=", "??="].includes(operator)) { // `a ||= b` assigns only where `a` is falsy
      const target = this.target(node.left);
      const current = this.expression(node.left);
      const test = operator === "&&=" ? current : operator === "||=" ? Py.UnaryOp().op("not").operand(current).create()
        : Py.Compare().left(current).add_comparisons(
          Py.Comparison().op("is").comparator(Py.Constant().spelling("None"))).create();
      const assign = Py.Assign().targets([target]).value(this.expression(node.right));
      return [Py.If().test(test).add_body(assign).create()];
    }
    if (operator !== "=") {
      const op = operator.slice(0, -1);
      if (!BINARY.has(op)) throw this.error(node, `the operator ${operator} is not supported`);
      return [Py.AugAssign().target(this.target(node.left)).op(op as P.BinaryOperator)
        .value(this.expression(node.right)).create()];
    }
    const targets = [this.target(node.left)];
    let value: any = node.right;
    while (value instanceof S.AssignmentExpression && value.operator === "=") { // `a = b = c`
      targets.push(this.target(value.left));
      value = value.right;
    }
    return [Py.Assign().targets(targets).value(this.expression(value)).create()];
  }

  /** What an assignment assigns to. */
  target(node: any): SyntaxNode {
    if (node instanceof S.Identifier || node instanceof S.MemberExpression) {
      const translated = this.expression(node);
      if (is([P.Name, P.Attribute, P.Subscript], translated)) return translated;
    }
    if (node instanceof S.ArrayPattern) {
      return Py.Tuple().elts(node.elements.map((e) => this.patternElement(e))).create();
    }
    if (node instanceof S.ParenthesizedExpression) return this.target(node.expression);
    throw this.error(node, `${node.kind().KIND} as a target is not supported`);
  }

  patternElement(node: any): SyntaxNode {
    if (node instanceof S.Elision) return Py.Name().id("_").create();
    if (node instanceof S.RestElement) return Py.Starred().value(this.target(node.argument)).create();
    return this.target(node);
  }

  variables(node: S.VariableDeclaration): SyntaxNode[] {
    if (node.declarationKind === "using" || node.declarationKind === "await using") {
      throw this.error(node, `${node.declarationKind} is not supported`);
    }
    if (node.declare) return [];
    const out: SyntaxNode[] = [];
    for (const declarator of node.declarations) {
      const init: any = declarator.init;
      if (init !== null && declarator.id instanceof S.Identifier
        && is([S.ArrowFunctionExpression, S.FunctionExpression], init) && init.body instanceof S.BlockStatement) {
        out.push(this.function(init, Translator.python(declarator.id.name as string))); // `const f = () => {}`
        continue;
      }
      const target = this.binding(declarator.id);
      const value = init === null ? Py.Constant().spelling("None").create() : this.expression(init);
      const annotation = declarator.id instanceof S.Identifier ? this.annotation(declarator.id) : null;
      if (annotation !== null && init !== null) {
        out.push(Py.AnnAssign().target(target).annotation(annotation).value(value).create());
      }
      else out.push(Py.Assign().targets([target]).value(value).create());
    }
    return out;
  }

  binding(node: any): SyntaxNode {
    if (node instanceof S.Identifier) return Py.Name().id(Translator.python(node.name as string)).create();
    if (node instanceof S.ArrayPattern) {
      return Py.Tuple().elts(node.elements.map((e: any) => e instanceof S.Elision ? Py.Name().id("_")
        : e instanceof S.RestElement ? Py.Starred().value(this.binding(e.argument)) : this.binding(e))).create();
    }
    throw this.error(node, `${node.kind().KIND} as a binding is not supported`);
  }

  ifStatement(node: S.IfStatement): SyntaxNode[] {
    let orelse: SyntaxNode[] = [];
    if (node.alternate !== null) {
      orelse = node.alternate instanceof S.IfStatement ? this.statements([node.alternate]) : this.block(node.alternate);
    }
    return [Py.If().test(this.expression(node.test)).body(this.block(node.consequent as SyntaxNode)).orelse(orelse)
      .create()];
  }

  whileStatement(node: S.WhileStatement): SyntaxNode[] {
    return [Py.While().test(this.expression(node.test)).body(this.block(node.body as SyntaxNode)).create()];
  }

  /** `do body while (test)`: a `while True` that breaks after the body, which must not `continue`. */
  doWhile(node: S.DoWhileStatement): SyntaxNode[] {
    this.noContinue(node.body as SyntaxNode, node);
    const stop = Py.If().test(this.negate(this.expression(node.test))).body([Py.Break()]).create();
    return [Py.While().test(Py.Constant().spelling("True")).body([...this.block(node.body as SyntaxNode), stop])
      .create()];
  }

  negate(test: any): SyntaxNode {
    if (test instanceof P.UnaryOp && test.op === "not") return test.operand as SyntaxNode;
    return Py.UnaryOp().op("not").operand(test).create();
  }

  /** Throws if `body` continues the loop it is the body of: its translation would skip what follows the body. */
  noContinue(body: SyntaxNode, loop: SyntaxNode): void {
    for (const node of walk(body)) {
      if (node instanceof S.ContinueStatement && this.loopOf(node) === loop) {
        throw this.error(node, "continue in this loop is not supported");
      }
    }
  }

  /** The loop a `break` or `continue` leaves, or for a `break` the `switch`; null outside of them. */
  loopOf(node: SyntaxNode): SyntaxNode | null {
    for (const ancestor of this.parents.ancestors(node)) {
      if (is([S.WhileStatement, S.DoWhileStatement, S.ForStatement, S.ForInStatement, S.ForOfStatement], ancestor)
        || (ancestor instanceof S.SwitchStatement && node instanceof S.BreakStatement)) {
        return ancestor;
      }
      if (is([S.FunctionDeclaration, S.FunctionExpression, S.ArrowFunctionExpression], ancestor)) break;
    }
    return null;
  }

  forStatement(node: S.ForStatement): SyntaxNode[] {
    const counted = this.counted(node);
    if (counted !== null) return counted;
    this.noContinue(node.body as SyntaxNode, node);
    const out: SyntaxNode[] = [];
    if (node.init instanceof S.VariableDeclaration) out.push(...this.variables(node.init));
    else if (node.init !== null) out.push(...this.update(node.init));
    let body = this.block(node.body as SyntaxNode);
    if (node.update !== null) body = [...body.filter((s) => !(s instanceof P.Pass)), ...this.update(node.update)];
    const test = node.test === null ? Py.Constant().spelling("True").create() : this.expression(node.test);
    return [...out, Py.While().test(test).body(body).create()];
  }

  update(node: any): SyntaxNode[] {
    if (node instanceof S.SequenceExpression) return node.expressions.flatMap((e) => this.update(e));
    return this.expressionStatement(new S.ExpressionStatement({ expression: node }));
  }

  /** `for (let i = a; i < b; i++)` as `for i in range(a, b)`, where the body does not assign `i`; null for any other
   * `for`. */
  counted(node: S.ForStatement): SyntaxNode[] | null {
    const init: any = node.init;
    const test: any = node.test;
    const update: any = node.update;
    if (!(init instanceof S.VariableDeclaration && init.declarations.length === 1
      && (init.declarations[0] as S.VariableDeclarator).id instanceof S.Identifier
      && (init.declarations[0] as S.VariableDeclarator).init !== null)) {
      return null;
    }
    const declarator = init.declarations[0] as S.VariableDeclarator;
    const counter = (declarator.id as S.Identifier).name as string;
    if (!(test instanceof S.BinaryExpression && test.left instanceof S.Identifier && test.left.name === counter
      && ["<", "<=", ">", ">="].includes(test.operator as string))) {
      return null;
    }
    let step: number | null = null;
    if (update instanceof S.UpdateExpression && update.argument instanceof S.Identifier
      && update.argument.name === counter) {
      step = update.operator === "++" ? 1 : -1;
    } else if (update instanceof S.AssignmentExpression && (update.operator === "+=" || update.operator === "-=")
      && update.left instanceof S.Identifier && update.left.name === counter && update.right instanceof S.Literal
      && /^[0-9]+$/.test(update.right.raw as string)) {
      step = Number(update.right.raw) * (update.operator === "+=" ? 1 : -1);
    }
    if (step === null || (step > 0) !== ["<", "<="].includes(test.operator as string)) return null;
    for (const n of walk(node.body as SyntaxNode)) { // the body must not change the counter
      const assigned = n instanceof S.AssignmentExpression ? n.left
        : n instanceof S.UpdateExpression ? n.argument : null;
      if (assigned instanceof S.Identifier && assigned.name === counter) return null;
    }
    let stop: SyntaxNode = this.expression(test.right);
    if (test.operator === "<=" || test.operator === ">=") { // one past the bound, folded where the bound is a number
      const past = step > 0 ? 1 : -1;
      stop = stop instanceof P.Constant && /^[0-9]+$/.test(stop.spelling as string)
        ? Py.Constant().spelling(String(Number(stop.spelling) + past)).create()
        : Py.BinOp().left(stop).op(past > 0 ? "+" : "-").right(Py.Constant().spelling("1")).create();
    }
    const bounds = [this.expression(declarator.init), stop];
    if (step !== 1) bounds.push(Py.Constant().spelling(String(step)).create());
    const iterable = Py.Call().func(Py.Name().id("range")).args(bounds);
    return [Py.For().target(Py.Name().id(Translator.python(counter))).iter(iterable)
      .body(this.block(node.body as SyntaxNode)).create()];
  }

  forOf(node: any): SyntaxNode[] {
    const left = node.left;
    const target = left instanceof S.VariableDeclaration
      ? this.binding((left.declarations[0] as S.VariableDeclarator).id) : this.target(left);
    let iterable = this.expression(node.right);
    if (node instanceof S.ForInStatement) { // the keys of an object
      iterable = Py.Call().func(Py.Name().id("vars")).add_args(iterable).create();
    }
    else if (node.isAwait) throw this.error(node, "for await is not supported");
    return [Py.For().target(target).iter(iterable).body(this.block(node.body)).create()];
  }

  /** `switch` as `if ... elif ... else`: each case must end its body, with `break`, `return`, `throw` or `continue`,
   * but for cases that only share the next one's body. */
  switchStatement(node: S.SwitchStatement): SyntaxNode[] {
    const out: SyntaxNode[] = [];
    let subject = this.expression(node.discriminant);
    if (!(subject instanceof P.Name || subject instanceof P.Constant)) {
      const made = this.fresh("subject");
      out.push(Py.Assign().targets([Py.Name().id(made)]).value(subject).create());
      subject = Py.Name().id(made).create();
    }
    const branches: [SyntaxNode[], SyntaxNode[]][] = []; // each branch's tests (none for default) and body
    let tests: SyntaxNode[] = [];
    let fallback = false;
    node.cases.forEach((kase, i) => {
      const body = kase.consequent.filter((s) => !(s instanceof S.Comment));
      if (kase.test === null) {
        fallback = true;
      } else {
        const test = Py.Comparison().op("==").comparator(this.expression(kase.test)).create();
        tests.push(Py.Compare().left(copy(subject)).comparisons([test]).create());
      }
      if (body.length === 0 && i + 1 < node.cases.length) return; // shares the next case's body
      const last = body.at(-1);
      if (last !== undefined && !is([S.BreakStatement, S.ReturnStatement, S.ThrowStatement, S.ContinueStatement], last)
        && i + 1 < node.cases.length) {
        throw this.error(kase, "a case that falls through is not supported");
      }
      const final = last instanceof S.BreakStatement ? last : null; // which `if` makes
      const kept = kase.consequent.filter((s) => s !== final);
      for (const n of kept.flatMap((s) => [...walk(s)])) {
        if (n instanceof S.BreakStatement && n.label === null && this.loopOf(n) === node) {
          throw this.error(n, "break within a case is not supported");
        }
      }
      branches.push([fallback ? [] : tests, this.block(new S.BlockStatement({ body: kept }))]);
      tests = [];
      fallback = false;
    });
    let chain: SyntaxNode[] = [];
    for (const [branchTests, body] of [...branches].reverse()) {
      if (branchTests.length === 0) {
        chain = body;
      } else {
        const test = branchTests.length === 1 ? branchTests[0] as SyntaxNode
          : Py.BoolOp().op("or").values(branchTests).create();
        chain = [Py.If().test(test).body(body).orelse(chain).create()];
      }
    }
    return [...out, ...chain];
  }

  jump(node: S.BreakStatement | S.ContinueStatement): SyntaxNode[] {
    if (this.loopOf(node) === null) throw this.error(node, `${node.kind().KIND} outside of a loop is not supported`);
    return [node instanceof S.BreakStatement ? Py.Break().create() : Py.Continue().create()];
  }

  returnStatement(node: S.ReturnStatement): SyntaxNode[] {
    return [Py.Return().value(node.argument === null ? null : this.expression(node.argument)).create()];
  }

  throwStatement(node: S.ThrowStatement): SyntaxNode[] {
    return [Py.Raise().exc(this.expression(node.argument)).create()];
  }

  tryStatement(node: S.TryStatement): SyntaxNode[] {
    const handlers: P.ExceptHandler[] = [];
    const handler = node.handler;
    if (handler !== null) {
      const param: any = handler.param;
      if (param !== null && !(param instanceof S.Identifier)) {
        throw this.error(param, "a pattern in catch is not supported");
      }
      if (param !== null) this.catches.add(this.definitions.entity_of(param) as Entity);
      handlers.push(Py.ExceptHandler().type(Py.Name().id("Exception"))
        .name(param === null ? null : Translator.python(param.name as string))
        .body(this.block(handler.body as SyntaxNode)).create());
    }
    const finalbody = node.finalizer === null ? [] : this.block(node.finalizer);
    return [Py.Try().body(this.block(node.block as SyntaxNode)).handlers(handlers).finalbody(finalbody).create()];
  }

  // Declarations

  functionDeclaration(node: any): SyntaxNode[] {
    if (node instanceof S.TSDeclareFunction) return []; // an overload's signature
    return [this.function(node, Translator.python(node.id.name))];
  }

  /** A function, an arrow function or a method as a `def`; `prefix` are statements its body starts with. An arrow
   * function's `this` is the enclosing function's. */
  function(node: any, made: string, method = false, decorators: SyntaxNode[] = [],
    prefix: SyntaxNode[] = []): SyntaxNode {
    if (node.generator === true && node.isAsync) throw this.error(node, "an async generator is not supported");
    const arrow = node instanceof S.ArrowFunctionExpression;
    this.methods.push(method || (arrow && this.methods.length > 0 && this.methods.at(-1) === true));
    const args = this.parameters(node.params, method);
    let body: SyntaxNode[];
    if (node.body instanceof S.BlockStatement) {
      body = this.statements(node.body.body);
    } else {
      const outer = this.pending;
      this.pending = [];
      const value = this.expression(node.body);
      body = [...this.pending, Py.Return().value(value).create()];
      this.pending = outer;
    }
    body = [...this.outerNames(node), ...prefix, ...body];
    if (!notComment(body)) body.push(Py.Pass().create());
    this.methods.pop();
    const kind = node.isAsync ? P.AsyncFunctionDef : P.FunctionDef;
    return new kind({ decorator_list: decorators, name: Py.Identifier().spelling(made).create(), args,
      returns: node.returnType !== null ? this.type(node.returnType.typeAnnotation) : null, body });
  }

  /** `global` and `nonlocal` for the names a function assigns but does not declare: in TypeScript, assigning a name of
   * an enclosing scope assigns it there, where Python would make it the function's own. */
  outerNames(node: any): SyntaxNode[] {
    if (!(node.body instanceof S.BlockStatement)) return [];
    const own = this.definitions.scope_of(node.body);
    const found = { global: [] as string[], nonlocal: [] as string[] };
    for (const target of this.assigned(node.body)) {
      const entities = D.referents(this.definitions, target);
      if (entities.length === 0) continue;
      let scope = (entities[0] as Entity).parent as Scope;
      while (!["function", "module", "static block"].includes(scope.kind)) scope = scope.parent as Scope;
      if (scope !== own) {
        const which = scope.parent === null ? found.global : found.nonlocal;
        const made = Translator.python(target.name as string);
        if (!which.includes(made)) which.push(made);
      }
    }
    const out: SyntaxNode[] = [];
    if (found.global.length > 0) out.push(Py.Global().names(found.global).create());
    if (found.nonlocal.length > 0) out.push(Py.Nonlocal().names(found.nonlocal).create());
    return out;
  }

  /** The names `node` assigns, outside the functions within it, in source order. */
  assigned(node: SyntaxNode): S.Identifier[] {
    const out: S.Identifier[] = [];
    const stack: SyntaxNode[] = [node];
    while (stack.length > 0) {
      const item: any = stack.pop();
      if (is([S.FunctionDeclaration, S.FunctionExpression, S.ArrowFunctionExpression, S.ClassDeclaration,
        S.ClassExpression], item)) {
        continue;
      }
      const target = item instanceof S.AssignmentExpression ? item.left : item instanceof S.UpdateExpression
        ? item.argument : null;
      if (target instanceof S.Identifier) out.push(target);
      stack.push(...children(item).reverse().map(([, , child]) => child));
    }
    return out;
  }

  parameters(params: any[], method: boolean): P.Arguments {
    const args: P.Arg[] = method ? [Py.Arg().arg("self").create()] : [];
    let vararg: P.Arg | null = null;
    for (let param of params) {
      if (param instanceof S.TSParameterProperty) param = param.parameter;
      let fallback: SyntaxNode | null = null;
      if (param instanceof S.AssignmentPattern) {
        fallback = this.expression(param.right);
        param = param.left;
      }
      if (param instanceof S.RestElement && param.argument instanceof S.Identifier) {
        vararg = Py.Arg().arg(Translator.python(param.argument.name as string)).create();
        continue;
      }
      if (!(param instanceof S.Identifier)) {
        throw this.error(param, `${param.kind().KIND} as a parameter is not supported`);
      }
      if (param.name === "this") continue;
      if (param.optional && fallback === null) fallback = Py.Constant().spelling("None").create();
      args.push(Py.Arg().arg(Translator.python(param.name as string)).annotation(this.annotation(param))
        .default_value(fallback).create());
    }
    return Py.Arguments().args(args).vararg(vararg).create();
  }

  annotation(node: any): SyntaxNode | null {
    return node.typeAnnotation === null ? null : this.type(node.typeAnnotation.typeAnnotation);
  }

  classDeclaration(node: S.ClassDeclaration): SyntaxNode[] {
    if (node.declare) return [];
    if (node.decorators.length > 0) throw this.error(node.decorators[0] as SyntaxNode, "a decorator is not supported");
    const bases: SyntaxNode[] = [];
    const base: any = node.superClass;
    if (base !== null) {
      const error = base instanceof S.Identifier && base.name === "Error" && this.isGlobal(base);
      bases.push(error ? Py.Name().id("Exception").create() : this.expression(base));
    }
    const body: SyntaxNode[] = [];
    const fields: SyntaxNode[] = []; // instance fields, which the constructor assigns
    let constructor: any = null;
    for (const member of (node.body as S.ClassBody).body as any[]) {
      if (member instanceof S.Comment) {
        body.push(...this.comment(member));
      } else if (member instanceof S.PropertyDefinition || member instanceof S.TSAbstractPropertyDefinition) {
        body.push(...this.field(member, fields));
      } else if (member instanceof S.MethodDefinition || member instanceof S.TSAbstractMethodDefinition) {
        if (member.methodKind === "constructor") constructor = member;
        else if (!(member.value instanceof S.TSEmptyBodyFunctionExpression)
          || member instanceof S.TSAbstractMethodDefinition) {
          body.push(this.method(member));
        }
      } else if (!(member instanceof S.TSIndexSignature)) { // an index signature is a type
        throw this.error(member);
      }
    }
    if (constructor !== null || fields.length > 0) { // after the class's own attributes, before its methods
      const index = body.findIndex((s) => s instanceof P.FunctionDef || s instanceof P.AsyncFunctionDef);
      body.splice(index < 0 ? body.length : index, 0, this.constructorDef(constructor, fields, base !== null));
    }
    if (!notComment(body)) body.push(Py.Pass().create());
    const className = Py.Identifier().spelling(Translator.python((node.id as S.Identifier).name as string)).create();
    return [Py.ClassDef().name(className).bases(bases).body(body).create()];
  }

  memberName(member: any): string {
    if (member.computed) throw this.error(member, "a computed member name is not supported");
    if (!(member.key instanceof S.Identifier || member.key instanceof S.PrivateIdentifier)) {
      throw this.error(member, "a member named by a literal is not supported");
    }
    return Translator.propertyName(member.key);
  }

  field(member: any, fields: SyntaxNode[]): SyntaxNode[] {
    const made = this.memberName(member);
    const annotation = member.typeAnnotation === null ? null : this.type(member.typeAnnotation.typeAnnotation);
    if (member.static) {
      const value = member.value === null ? Py.Constant().spelling("None").create() : this.expression(member.value);
      if (annotation !== null) {
        return [Py.AnnAssign().target(Py.Name().id(made)).annotation(annotation).value(value).create()];
      }
      return [Py.Assign().targets([Py.Name().id(made)]).value(value).create()];
    }
    if (member.value !== null) {
      this.methods.push(true);
      const target = Py.Attribute().value(Py.Name().id("self")).attr(made);
      fields.push(Py.Assign().add_targets(target).value(this.expression(member.value)).create());
      this.methods.pop();
    }
    if (annotation !== null) return [Py.AnnAssign().target(Py.Name().id(made)).annotation(annotation).create()];
    return [];
  }

  /** `__init__`: the constructor's body, with the parameter properties and the fields assigned after `super` is
   * called, or first; or, without a constructor, one that passes its arguments to `super`. */
  constructorDef(member: any, fields: SyntaxNode[], derived: boolean): SyntaxNode {
    if (member === null) {
      const node = new S.FunctionExpression({ params: derived ? [new S.RestElement({ argument: new S.Identifier({
        name: "args" }) })] : [], body: new S.BlockStatement() });
      const prefix: SyntaxNode[] = [];
      if (derived) {
        const args = Py.Starred().value(Py.Name().id("args")).create();
        const init = Py.Attribute().value(Py.Call().func(Py.Name().id("super"))).attr("__init__");
        prefix.push(Py.Expr().value(Py.Call().func(init).add_args(args)).create());
      }
      return this.function(node, "__init__", true, [], [...prefix, ...fields]);
    }
    const value = member.value;
    const properties: SyntaxNode[] = []; // `constructor(private x)` assigns `self.x = x`
    for (const param of value.params) {
      if (param instanceof S.TSParameterProperty) {
        const bound: any = param.parameter instanceof S.AssignmentPattern ? param.parameter.left : param.parameter;
        const made = Translator.python(bound.name);
        const target = Py.Attribute().value(Py.Name().id("self")).attr(made);
        properties.push(Py.Assign().add_targets(target).value(Py.Name().id(made)).create());
      }
    }
    const made = this.function(value, "__init__", true) as P.FunctionDef;
    const statements = made.body;
    const found = statements.findIndex((s: any) => s instanceof P.Expr && s.value instanceof P.Call
      && s.value.func instanceof P.Attribute && (s.value.func.attr as P.Identifier).spelling === "__init__");
    statements.splice(found + 1, 0, ...properties, ...fields);
    const kept = statements.filter((s) => !(s instanceof P.Pass));
    made.body = kept.length > 0 ? kept : [Py.Pass().create()];
    return made;
  }

  method(member: any): SyntaxNode {
    let made = this.memberName(member);
    if (made === "toString" && !member.static && member.value.params.length === 0) {
      made = "__str__"; // what `String(x)` and templates call, as `str(x)` and f-strings do
    }
    if (member instanceof S.TSAbstractMethodDefinition) {
      const raise = Py.Raise().exc(Py.Name().id("NotImplementedError")).create();
      const value: any = member.value;
      const node = new S.FunctionExpression({ params: value.params, returnType: value.returnType,
        body: new S.BlockStatement() });
      return this.function(node, made, !member.static, [], [raise]);
    }
    const decorators: SyntaxNode[] = [];
    if (member.static) decorators.push(Py.Name().id("staticmethod").create());
    if (member.methodKind === "get") decorators.push(Py.Name().id("property").create());
    else if (member.methodKind === "set") {
      decorators.push(Py.Attribute().value(Py.Name().id(made)).attr("setter").create());
    }
    return this.function(member.value, made, !member.static, decorators);
  }

  /** An enum of numbers, as an `IntEnum`, or of strings, as a `StrEnum`. */
  enumDeclaration(node: S.TSEnumDeclaration): SyntaxNode[] {
    if (node.declare) return [];
    const members = (node.body as S.TSEnumBody).members.filter((m) => !(m instanceof S.Comment)) as S.TSEnumMember[];
    const strings = members.some((m) => m.initializer instanceof S.Literal
      && /^['"]/.test(m.initializer.raw as string));
    const body: SyntaxNode[] = [];
    let following = 0;
    for (const member of members) {
      if (member.computed || !(member.id instanceof S.Identifier)) {
        throw this.error(member, "an enum member must be named by a name");
      }
      const made = Translator.propertyName(member.id);
      let value: SyntaxNode;
      const initializer: any = member.initializer;
      if (initializer === null) {
        if (strings) throw this.error(member, "a member of a string enum needs a value");
        value = Py.Constant().spelling(String(following)).create();
        following += 1;
      } else if (initializer instanceof S.Literal && (strings || /^[0-9]+$/.test(initializer.raw as string))) {
        value = this.expression(initializer);
        if (!strings) following = Number(initializer.raw) + 1;
      } else {
        throw this.error(initializer, "an enum member's value must be a literal");
      }
      body.push(Py.Assign().targets([Py.Name().id(made)]).value(value).create());
    }
    const base = this.imported("enum", strings ? "StrEnum" : "IntEnum");
    const className = Py.Identifier().spelling(Translator.python((node.id as S.Identifier).name as string)).create();
    return [Py.ClassDef().name(className).bases([base]).body(body.length > 0 ? body : [Py.Pass()]).create()];
  }

  typeAlias(node: S.TSTypeAliasDeclaration): SyntaxNode[] {
    const value = this.type(node.typeAnnotation);
    if (value === null || node.typeParameters !== null) return [];
    const alias = Py.Name().id(Translator.python((node.id as S.Identifier).name as string));
    return [Py.TypeAlias().name(alias).value(value).create()];
  }

  importDeclaration(node: S.ImportDeclaration): SyntaxNode[] {
    if (node.importKind === "type") return [];
    const [level, names] = this.modulePath(node.source as S.Literal);
    const out: SyntaxNode[] = [];
    const named: P.Alias[] = [];
    const parent = (): P.DottedName | null =>
      (names.length > 1 ? Py.DottedName().names(names.slice(0, -1)).create() : null);
    for (const specifier of node.specifiers as any[]) {
      if (specifier instanceof S.ImportNamespaceSpecifier) {
        const local = Translator.python((specifier.local as S.Identifier).name as string);
        if (level > 0) {
          const alias = Py.Alias().name(Py.DottedName().names(names.slice(-1).map((n) => copy(n)))).asname(local);
          out.push(Py.ImportFrom().level(BigInt(level)).module(parent()).add_names(alias).create());
        } else {
          const alias = Py.Alias().name(Py.DottedName().names(names.map((n) => copy(n)))).asname(local);
          out.push(Py.Import().add_names(alias).create());
        }
      } else if (specifier instanceof S.ImportSpecifier) {
        if (specifier.importKind === "type") continue;
        if (!(specifier.imported instanceof S.Identifier)) {
          throw this.error(specifier, "importing a name that is a string is not supported");
        }
        const imported = Translator.python(specifier.imported.name as string);
        const local = Translator.python((specifier.local as S.Identifier).name as string);
        named.push(Py.Alias().name(Py.DottedName().add_names(imported)).asname(local === imported ? null : local)
          .create());
      } else {
        throw this.error(specifier, "a default import is not supported");
      }
    }
    if (named.length > 0) {
      const module = Py.DottedName().names(names.map((n) => copy(n)));
      out.unshift(Py.ImportFrom().level(level > 0 ? BigInt(level) : null).module(module).names(named).create());
    }
    if (node.specifiers.length === 0) {
      if (level === 0) {
        out.push(Py.Import().add_names(Py.Alias().name(Py.DottedName().names(names))).create());
      } else {
        const alias = Py.Alias().name(Py.DottedName().names(names.slice(-1)));
        out.push(Py.ImportFrom().level(BigInt(level)).module(parent()).add_names(alias).create());
      }
    }
    return out;
  }

  /** A module's level (how many packages up, for a relative path) and its dotted name: `./a/b` is `.a.b`. */
  modulePath(source: S.Literal): [number, P.Identifier[]] {
    const raw = source.raw as string;
    let path = raw.slice(1, -1);
    let level = 0;
    if (path.startsWith(".")) {
      level = 1;
      if (path.startsWith("./")) path = path.slice(2);
      while (path.startsWith("../")) {
        level += 1;
        path = path.slice(3);
      }
    }
    path = path.replace(/\.(ts|js|mjs|cjs)$/, "");
    const parts = path.split("/").filter((p) => p !== "");
    if (parts.length === 0 || parts.some((p) => !/^[A-Za-z_$][A-Za-z0-9_$-]*$/.test(p))) {
      throw this.error(source, `the module ${raw} has no Python name`);
    }
    return [level, parts.map((p) =>
      Py.Identifier().spelling(Translator.python(p.replaceAll("-", "_").replaceAll("$", "_"))).create())];
  }

  exportNamed(node: S.ExportNamedDeclaration): SyntaxNode[] {
    if (node.declaration !== null) return this.statement(node.declaration);
    if (node.source !== null) throw this.error(node, "a re-export is not supported");
    return []; // Python exports every name a module binds
  }

  exportDefault(node: S.ExportDefaultDeclaration): SyntaxNode[] {
    const declaration: any = node.declaration;
    if ((declaration instanceof S.FunctionDeclaration || declaration instanceof S.ClassDeclaration)
      && declaration.id !== null) {
      return this.statement(declaration);
    }
    throw this.error(node, "a default export of a value is not supported");
  }

  // Expressions

  expression(node: any): SyntaxNode {
    const method = Translator.EXPRESSIONS.get(node.constructor);
    if (method === undefined) throw this.error(node);
    return method(this, node);
  }

  identifier(node: S.Identifier): SyntaxNode {
    const text = node.name as string;
    if (this.isGlobal(node)) {
      if (text === "undefined") return Py.Constant().spelling("None").create();
      if (text === "NaN" || text === "Infinity") {
        return Py.Attribute().value(this.module("math")).attr(text === "NaN" ? "nan" : "inf").create();
      }
      if (text in GLOBALS || text in OBJECTS) throw this.error(node, `the global ${text} is not supported here`);
    }
    return Py.Name().id(Translator.python(text)).create();
  }

  literal(node: S.Literal): SyntaxNode {
    let raw = node.raw as string;
    if (raw === "true" || raw === "false") return Py.Constant().spelling(raw === "true" ? "True" : "False").create();
    if (raw === "null") return Py.Constant().spelling("None").create();
    if (raw.startsWith("'") || raw.startsWith("\"")) return Py.Constant().spelling(Translator.string(raw)).create();
    if (raw.startsWith("/")) throw this.error(node, "a regular expression is not supported");
    if (raw.endsWith("n")) raw = raw.slice(0, -1); // a bigint: Python's integers have no bounds
    if (/^0[0-7]+$/.test(raw)) raw = "0o" + raw.slice(1); // a legacy octal
    return Py.Constant().spelling(raw).create();
  }

  /** A Python string literal's spelling of a TypeScript one: escapes Python lacks rewritten. */
  static string(raw: string): string {
    return raw.replace(/\\u\{([0-9a-fA-F]+)\}/g, (_m, hex: string) => "\\U" + hex.padStart(8, "0"));
  }

  template(node: S.TemplateLiteral): SyntaxNode {
    const values: (P.StringText | P.FormattedValue)[] = [];
    node.quasis.forEach((quasi, i) => {
      const text = Translator.string(quasi.raw as string).replaceAll("{", "{{").replaceAll("}", "}}")
        .replaceAll("\\`", "`").replaceAll("\"", "\\\"").replaceAll("\n", "\\n");
      if (text !== "") values.push(Py.StringText().spelling(text).create());
      if (i < node.expressions.length) {
        values.push(Py.FormattedValue().value(this.expression(node.expressions[i])).create());
      }
    });
    return Py.JoinedStr().prefix("f").quote("\"").values(values).create();
  }

  thisExpression(node: S.ThisExpression): SyntaxNode {
    if (this.methods.length === 0 || !this.methods.at(-1)) {
      throw this.error(node, "this outside a method is not supported");
    }
    return Py.Name().id("self").create();
  }

  array(node: S.ArrayExpression): SyntaxNode {
    const elements = node.elements.map((element: any) => {
      if (element instanceof S.Elision) throw this.error(element, "a hole in an array is not supported");
      return element instanceof S.SpreadElement ? Py.Starred().value(this.expression(element.argument)).create()
        : this.expression(element);
    });
    return Py.List().elts(elements).create();
  }

  object(node: S.ObjectExpression): SyntaxNode {
    const keywords: P.Keyword[] = [];
    for (const item of node.properties as any[]) {
      if (item instanceof S.SpreadElement || item.method || item.propertyKind !== "init" || item.computed) {
        throw this.error(item, `${item instanceof S.SpreadElement ? "a spread" : "this property"} in an object `
          + "literal is not supported");
      }
      const key: string | null = item.key instanceof S.Identifier ? item.key.name
        : item.key instanceof S.Literal && /^['"]/.test(item.key.raw) ? item.key.raw.slice(1, -1) : null;
      if (key === null || !isIdentifier(key)) throw this.error(item, "a key that is not a name is not supported");
      keywords.push(Py.Keyword().arg(KEYWORDS.has(key) ? key + "_" : key).value(this.expression(item.value)).create());
    }
    return Py.Call().func(this.imported("types", "SimpleNamespace")).keywords(keywords).create();
  }

  unary(node: S.UnaryExpression): SyntaxNode {
    const operator = node.operator as string;
    if (["typeof", "void", "delete"].includes(operator)) {
      throw this.error(node, `the operator ${operator} is not supported`);
    }
    return Py.UnaryOp().op((operator === "!" ? "not" : operator) as P.UnaryOperator)
      .operand(this.expression(node.argument)).create();
  }

  binary(node: S.BinaryExpression | S.LogicalExpression): SyntaxNode {
    const operator = node.operator as string;
    if (node.left instanceof S.PrivateIdentifier) throw this.error(node, "#name in is not supported");
    const left = this.expression(node.left);
    const right = this.expression(node.right);
    if (operator === "&&" || operator === "||") {
      return Py.BoolOp().op(operator === "&&" ? "and" : "or").values([left, right]).create();
    }
    const isNotNone = (value: SyntaxNode) => Py.Compare().left(value).add_comparisons(
      Py.Comparison().op("is not").comparator(Py.Constant().spelling("None"))).create();
    if (operator === "??") { // `a ?? b`: `a` is evaluated once, kept in a name unless it is one or a constant
      let value = left;
      let tested = left;
      if (!(left instanceof P.Name || left instanceof P.Constant)) {
        const named: P.Name = Py.Name().id(this.fresh("value")).create();
        tested = Py.NamedExpr().target(named).value(left).create();
        value = named;
      }
      return Py.IfExp().test(isNotNone(tested)).body(copy(value)).orelse(right).create();
    }
    if (operator === "instanceof") return Py.Call().func(Py.Name().id("isinstance")).args([left, right]).create();
    const comparison = COMPARISONS[operator];
    if (comparison !== undefined) {
      let op = comparison;
      if (right instanceof P.Constant && right.spelling === "None" && (op === "==" || op === "!=")) {
        op = op === "==" ? "is" : "is not"; // `x === null`
      }
      return Py.Compare().left(left).comparisons([Py.Comparison().op(op).comparator(right)]).create();
    }
    if (!BINARY.has(operator)) throw this.error(node, `the operator ${operator} is not supported`);
    let [first, second] = [left, right];
    if (operator === "+" && Translator.textual(left) !== Translator.textual(right)) { // `"n" + 1` makes a string of 1
      if (Translator.textual(left)) second = Py.Call().func(Py.Name().id("str")).args([right]).create();
      else first = Py.Call().func(Py.Name().id("str")).args([left]).create();
    }
    return Py.BinOp().left(first).op(operator as P.BinaryOperator).right(second).create();
  }

  /** Whether `node` is a string literal, an f-string or a sum that makes a string, which `+` makes a string of the
   * other operand. */
  static textual(node: SyntaxNode): boolean {
    if (node instanceof P.BinOp && node.op === "+") {
      return Translator.textual(node.left as SyntaxNode) || Translator.textual(node.right as SyntaxNode);
    }
    return node instanceof P.JoinedStr || (node instanceof P.Constant && /^['"]/.test(node.spelling as string));
  }

  conditional(node: S.ConditionalExpression): SyntaxNode {
    return Py.IfExp().test(this.expression(node.test)).body(this.expression(node.consequent))
      .orelse(this.expression(node.alternate)).create();
  }

  assignmentExpression(node: S.AssignmentExpression): SyntaxNode {
    if (node.operator === "=" && node.left instanceof S.Identifier && this.lambdas === 0) { // else a lambda's own
      return Py.NamedExpr().target(Py.Name().id(Translator.python(node.left.name as string)))
        .value(this.expression(node.right)).create();
    }
    throw this.error(node, "an assignment within an expression is not supported");
  }

  member(node: S.MemberExpression): SyntaxNode {
    const target: any = node.object;
    if (node.computed) {
      return Py.Subscript().value(this.expression(target)).slice(this.expression(node.property)).create();
    }
    const made = Translator.propertyName(node.property);
    if (target instanceof S.Identifier && this.isGlobal(target) && (target.name as string) in OBJECTS) {
      const mapped = (OBJECTS[target.name as string] as Record<string, unknown>)[made];
      if (typeof mapped !== "string") throw this.error(node, `${target.name}.${made} is not supported`); // a function
      return this.globalValue(mapped);
    }
    if (made === "length" && !this.members.has(made)) {
      return Py.Call().func(Py.Name().id("len")).add_args(this.expression(target)).create();
    }
    if (made === "size" && !this.members.has(made)) {
      return Py.Call().func(Py.Name().id("len")).add_args(this.expression(target)).create();
    }
    if (made === "message" && target instanceof S.Identifier && this.caught(target)) {
      return Py.Call().func(Py.Name().id("str")).args([this.expression(target)]).create(); // an exception's message
    }
    return Py.Attribute().value(this.expression(target)).attr(made).create();
  }

  /** A property's Python name: `#x` is `_x`, and a keyword takes a `_`. */
  static propertyName(key: any): string {
    if (key instanceof S.PrivateIdentifier) return "_" + key.name;
    return KEYWORDS.has(key.name) ? key.name + "_" : key.name;
  }

  /** `module.name` (or a builtin) for a global's member, its module imported. */
  globalValue(path: string): SyntaxNode {
    const dot = path.lastIndexOf(".");
    return dot >= 0 ? Py.Attribute().value(this.module(path.slice(0, dot))).attr(path.slice(dot + 1)).create()
      : Py.Name().id(path).create();
  }

  caught(node: S.Identifier): boolean {
    const found = D.referents(this.definitions, node);
    return found.length > 0 && this.catches.has(found[0] as Entity);
  }

  callExpression(node: S.CallExpression): SyntaxNode {
    const callee: any = node.callee;
    if (callee instanceof S.Super) {
      const init = Py.Attribute().value(Py.Call().func(Py.Name().id("super"))).attr("__init__");
      return Py.Call().func(init).args(this.arguments(node.arguments)).create();
    }
    if (callee instanceof S.MemberExpression && callee.object instanceof S.Super) {
      const parent = Py.Call().func(Py.Name().id("super"));
      const method = Py.Attribute().value(parent).attr(Translator.propertyName(callee.property));
      return Py.Call().func(method).args(this.arguments(node.arguments)).create();
    }
    if (callee instanceof S.Identifier && this.isGlobal(callee) && (callee.name as string) in GLOBALS) {
      return (GLOBALS[callee.name as string] as Global)(this, node);
    }
    if (callee instanceof S.MemberExpression && !callee.computed && callee.object instanceof S.Identifier
      && this.isGlobal(callee.object) && (callee.object.name as string) in OBJECTS) {
      const property = (callee.property as S.Identifier).name as string;
      const mapped = (OBJECTS[callee.object.name as string] as Record<string, unknown>)[property];
      if (typeof mapped !== "function") {
        throw this.error(node, `${callee.object.name}.${property}() is not supported`);
      }
      return (mapped as Global)(this, node);
    }
    if (callee instanceof S.MemberExpression && !callee.computed && callee.property instanceof S.Identifier
      && (callee.property.name as string) in METHODS && !this.members.has(callee.property.name as string)) {
      return (METHODS[callee.property.name as string] as Method)(this, this.expression(callee.object), node);
    }
    return Py.Call().func(this.expression(callee)).args(this.arguments(node.arguments)).create();
  }

  arguments(args: readonly any[]): SyntaxNode[] {
    return args.map((a) => a instanceof S.SpreadElement ? Py.Starred().value(this.expression(a.argument)).create()
      : this.expression(a));
  }

  /** The arguments of a call that a mapping translates, which must be as many as one of `counts`. */
  argumentsOf(node: S.CallExpression, ...counts: number[]): SyntaxNode[] {
    const args = this.arguments(node.arguments);
    if (!counts.includes(args.length) || args.some((a) => a instanceof P.Starred)) {
      throw this.error(node, "this call's arguments are not supported");
    }
    return args;
  }

  newExpression(node: S.NewExpression): SyntaxNode {
    const callee: any = node.callee;
    if (callee instanceof S.Identifier && this.isGlobal(callee)) {
      const mapped = ({ Error: "Exception", TypeError: "TypeError", RangeError: "ValueError", Set: "set",
        Map: "dict" } as Record<string, string>)[callee.name as string];
      if (mapped === undefined) throw this.error(node, `new ${callee.name} is not supported`);
      return Py.Call().func(Py.Name().id(mapped)).args(this.arguments(node.arguments)).create();
    }
    return Py.Call().func(this.expression(callee)).args(this.arguments(node.arguments)).create();
  }

  /** An arrow function or a function expression used as a value: a lambda where its body is an expression, and a
   * function declared before the statement otherwise. */
  functionValue(node: any): SyntaxNode {
    if (node instanceof S.ArrowFunctionExpression && !(node.body instanceof S.BlockStatement) && !node.isAsync) {
      const names: string[] = [];
      for (const param of node.params as any[]) {
        if (!(param instanceof S.Identifier)) throw this.error(param, "a lambda's parameters must be names");
        names.push(Translator.python(param.name as string));
      }
      this.lambdas += 1;
      this.methods.push(this.methods.length > 0 && this.methods.at(-1) === true);
      const body = this.expression(node.body);
      this.methods.pop();
      this.lambdas -= 1;
      const args = Py.Arguments().args(names.map((n) => Py.Arg().arg(n))).create();
      return Py.Lambda().args(args).body(body).create();
    }
    if (this.lambdas > 0) throw this.error(node, "a function with a body within a lambda is not supported");
    const made = node.id !== undefined && node.id !== null ? Translator.python(node.id.name) : this.fresh("function");
    this.pending.push(this.function(node, made));
    return Py.Name().id(made).create();
  }

  /** The parameter and body of the callback `node` passes, if it is an arrow function of one name with an expression
   * for its body. */
  callback(node: S.CallExpression): [P.Name, SyntaxNode] | null {
    if (node.arguments.length !== 1) return null;
    const f: any = node.arguments[0];
    if (f instanceof S.ArrowFunctionExpression && f.params.length === 1 && f.params[0] instanceof S.Identifier
      && !(f.body instanceof S.BlockStatement)) {
      this.lambdas += 1;
      const body = this.expression(f.body);
      this.lambdas -= 1;
      return [Py.Name().id(Translator.python(f.params[0].name as string)).create(), body];
    }
    return null;
  }

  /** `items.forEach(x => ...)` as a statement: a `for` loop. */
  forEach(node: S.CallExpression): SyntaxNode[] | null {
    const callee: any = node.callee;
    if (!(callee instanceof S.MemberExpression && !callee.computed && callee.property instanceof S.Identifier
      && callee.property.name === "forEach" && !this.members.has("forEach") && node.arguments.length === 1)) {
      return null;
    }
    const f: any = node.arguments[0];
    if (!(f instanceof S.ArrowFunctionExpression && f.params.length === 1 && f.params[0] instanceof S.Identifier)) {
      throw this.error(f, "forEach takes an arrow function of one parameter here");
    }
    const body = f.body instanceof S.BlockStatement ? this.block(f.body)
      : [Py.Expr().value(this.expression(f.body)).create()];
    return [Py.For().target(Py.Name().id(Translator.python(f.params[0].name as string)))
      .iter(this.expression(callee.object)).body(body).create()];
  }

  /** `map.set(k, v)` as a statement: an assignment to `map[k]`. */
  setCall(node: S.CallExpression): SyntaxNode[] | null {
    const callee: any = node.callee;
    if (callee instanceof S.MemberExpression && !callee.computed && callee.property instanceof S.Identifier
      && callee.property.name === "set" && !this.members.has("set") && node.arguments.length === 2) {
      const [key, value] = this.arguments(node.arguments) as [SyntaxNode, SyntaxNode];
      const subscript = Py.Subscript().value(this.expression(callee.object)).slice(key).create();
      return [Py.Assign().targets([subscript]).value(value).create()];
    }
    return null;
  }

  // Types

  /** A type as an annotation; null where Python has no counterpart, which leaves the annotation out. */
  type(node: any): SyntaxNode | null {
    const keyword = new Map<Function, string>([[S.TSNumberKeyword, "float"], [S.TSStringKeyword, "str"],
      [S.TSBooleanKeyword, "bool"], [S.TSBigIntKeyword, "int"], [S.TSObjectKeyword, "object"],
      [S.TSUnknownKeyword, "object"], [S.TSVoidKeyword, "None"], [S.TSUndefinedKeyword, "None"],
      [S.TSNullKeyword, "None"]]).get(node.constructor);
    if (keyword !== undefined) {
      return keyword === "None" ? Py.Constant().spelling("None").create() : Py.Name().id(keyword).create();
    }
    if (node instanceof S.TSAnyKeyword) return this.imported("typing", "Any");
    if (node instanceof S.TSArrayType) {
      const element = this.type(node.elementType);
      return element === null ? null : Py.Subscript().value(Py.Name().id("list")).slice(element).create();
    }
    if (node instanceof S.TSTypeOperator && node.operator === "readonly" && node.typeAnnotation !== null) {
      return this.type(node.typeAnnotation);
    }
    if (node instanceof S.TSTupleType) {
      const elements = node.elementTypes.map((t) => this.type(t));
      return elements.includes(null) || elements.length === 0 ? null
        : Py.Subscript().value(Py.Name().id("tuple")).slice(Py.Tuple().elts(elements as SyntaxNode[])).create();
    }
    if (node instanceof S.TSUnionType) {
      const types = node.types.map((t) => this.type(t));
      if (types.includes(null)) return null;
      return (types as SyntaxNode[]).reduce((union, t) => Py.BinOp().left(union).op("|").right(t).create());
    }
    if (node instanceof S.TSParenthesizedType) return this.type(node.typeAnnotation);
    if (node instanceof S.TSLiteralType && node.literal instanceof S.Literal) {
      return Py.Subscript().value(this.imported("typing", "Literal")).slice(this.literal(node.literal)).create();
    }
    if (node instanceof S.TSTypeReference && node.typeName instanceof S.Identifier) {
      const text = node.typeName.name as string;
      const args = node.typeArguments === null ? [] : node.typeArguments.params.map((t) => this.type(t));
      if (args.includes(null)) return null;
      const slice = (): SyntaxNode =>
        (args.length === 1 ? args[0] as SyntaxNode : Py.Tuple().elts(args as SyntaxNode[]).create());
      const generic = ({ Array: "list", ReadonlyArray: "list", Set: "set", Map: "dict", Record: "dict" } as
        Record<string, string>)[text];
      if (generic !== undefined && args.length > 0) {
        return Py.Subscript().value(Py.Name().id(generic)).slice(slice()).create();
      }
      if (["Promise", "Array", "Set", "Map", "Record", "Partial", "Readonly"].includes(text)) return null;
      if (args.length > 0) return Py.Subscript().value(Py.Name().id(Translator.python(text))).slice(slice()).create();
      return Py.Name().id(Translator.python(text)).create();
    }
    return null;
  }
}

const T = Translator.prototype;
const statements = (method: (this: Translator, node: any) => SyntaxNode[]): Statements => (self, node) =>
  method.call(self, node);
const expression = (method: (this: Translator, node: any) => SyntaxNode): Expression => (self, node) =>
  method.call(self, node);
/** A type assertion, which Python does not check. */
const stripped: Expression = (self, node) => self.expression(node.expression);
const skip: Statements = () => []; // type-only

Translator.STATEMENTS = new Map<Function, Statements>([
  [S.Comment, statements(T.comment)], [S.ExpressionStatement, statements(T.expressionStatement)],
  [S.VariableDeclaration, statements(T.variables)], [S.IfStatement, statements(T.ifStatement)],
  [S.WhileStatement, statements(T.whileStatement)], [S.DoWhileStatement, statements(T.doWhile)],
  [S.ForStatement, statements(T.forStatement)], [S.ForOfStatement, statements(T.forOf)],
  [S.ForInStatement, statements(T.forOf)], [S.SwitchStatement, statements(T.switchStatement)],
  [S.BreakStatement, statements(T.jump)], [S.ContinueStatement, statements(T.jump)],
  [S.ReturnStatement, statements(T.returnStatement)], [S.ThrowStatement, statements(T.throwStatement)],
  [S.TryStatement, statements(T.tryStatement)], [S.BlockStatement, (self, node) => self.statements(node.body)],
  [S.EmptyStatement, skip], [S.FunctionDeclaration, statements(T.functionDeclaration)],
  [S.TSDeclareFunction, statements(T.functionDeclaration)], [S.ClassDeclaration, statements(T.classDeclaration)],
  [S.TSEnumDeclaration, statements(T.enumDeclaration)], [S.TSTypeAliasDeclaration, statements(T.typeAlias)],
  [S.TSInterfaceDeclaration, skip], [S.ImportDeclaration, statements(T.importDeclaration)],
  [S.ExportNamedDeclaration, statements(T.exportNamed)], [S.ExportDefaultDeclaration, statements(T.exportDefault)],
]);

Translator.EXPRESSIONS = new Map<Function, Expression>([
  [S.Identifier, expression(T.identifier)], [S.Literal, expression(T.literal)],
  [S.TemplateLiteral, expression(T.template)],
  [S.ThisExpression, expression(T.thisExpression)], [S.ArrayExpression, expression(T.array)],
  [S.ObjectExpression, expression(T.object)], [S.UnaryExpression, expression(T.unary)],
  [S.BinaryExpression, expression(T.binary)], [S.LogicalExpression, expression(T.binary)],
  [S.ConditionalExpression, expression(T.conditional)], [S.AssignmentExpression, expression(T.assignmentExpression)],
  [S.MemberExpression, expression(T.member)], [S.CallExpression, expression(T.callExpression)],
  [S.NewExpression, expression(T.newExpression)], [S.ArrowFunctionExpression, expression(T.functionValue)],
  [S.FunctionExpression, expression(T.functionValue)],
  [S.AwaitExpression, (self, node) => Py.Await().value(self.expression(node.argument)).create()],
  [S.YieldExpression, (self, node) => {
    const value = node.argument === null ? null : self.expression(node.argument);
    return node.delegate ? Py.YieldFrom().value(value).create() : Py.Yield().value(value).create();
  }],
  [S.ParenthesizedExpression, stripped], [S.TSAsExpression, stripped], [S.TSSatisfiesExpression, stripped],
  [S.TSNonNullExpression, stripped], [S.TSTypeAssertion, stripped],
]);

const consoleCall = (stream: string | null): Global => (self, node) => {
  const keywords = stream === null ? []
    : [Py.Keyword().arg("file").value(Py.Attribute().value(self.module("sys")).attr(stream))];
  return Py.Call().func(Py.Name().id("print")).args(self.arguments(node.arguments)).keywords(keywords).create();
};
/** A global function that is a Python function of the same arguments. */
const fn = (path: string): Global => (self, node) =>
  Py.Call().func(self.globalValue(path)).args(self.arguments(node.arguments)).create();
/** `JSON.stringify(x)`, which writes no spaces, as `json.dumps` does with these separators. */
const stringify: Global = (self, node) => {
  const separators = Py.Tuple().elts([Py.Constant().spelling("','"), Py.Constant().spelling("':'")]).create();
  return Py.Call().func(Py.Attribute().value(self.module("json")).attr("dumps")).args(self.arguments(node.arguments))
    .add_keywords(Py.Keyword().arg("separators").value(separators)).create();
};
const power: Global = (self, node) => {
  const [base, exponent] = self.argumentsOf(node, 2) as [SyntaxNode, SyntaxNode];
  return Py.BinOp().left(base).op("**").right(exponent).create();
};
/** `Object.keys(o)` and the like, of an object, which is a `SimpleNamespace`. */
const objectView = (view: string): Global => (self, node) => {
  const [value] = self.argumentsOf(node, 1) as [SyntaxNode];
  const names = Py.Call().func(Py.Name().id("vars")).args([value]).create();
  const listed = view === "keys" ? names : Py.Call().func(Py.Attribute().value(names).attr(view));
  return Py.Call().func(Py.Name().id("list")).add_args(listed).create();
};
const isArray: Global = (self, node) => {
  const [value] = self.argumentsOf(node, 1) as [SyntaxNode];
  return Py.Call().func(Py.Name().id("isinstance")).args([value, Py.Name().id("list")]).create();
};

/** Global functions, by name, and the members of global objects, by object and name: a Python path for a value, or a
 * function that translates a call. */
const GLOBALS: Record<string, Global> = {
  String: fn("str"), Number: fn("float"), Boolean: fn("bool"), parseInt: fn("int"), parseFloat: fn("float"),
};
const OBJECTS: Record<string, Record<string, Global | string>> = {
  console: { log: consoleCall(null), error: consoleCall("stderr"), warn: consoleCall("stderr") },
  Math: { floor: fn("math.floor"), ceil: fn("math.ceil"), sqrt: fn("math.sqrt"), trunc: fn("math.trunc"),
    abs: fn("abs"), max: fn("max"), min: fn("min"), random: fn("random.random"), pow: power, log: fn("math.log"),
    exp: fn("math.exp"), PI: "math.pi", E: "math.e" },
  JSON: { stringify, parse: fn("json.loads") },
  Object: { keys: objectView("keys"), values: objectView("values"), entries: objectView("items") },
  Array: { isArray },
};

/** A method that is Python's method of another name. */
const rename = (renamed: string): Method => (self, target, node) =>
  Py.Call().func(Py.Attribute().value(target).attr(renamed)).args(self.arguments(node.arguments)).create();
const push: Method = (self, target, node) => {
  const args = self.arguments(node.arguments);
  if (args.length === 1 && !(args[0] instanceof P.Starred)) {
    return Py.Call().func(Py.Attribute().value(target).attr("append")).args(args).create();
  }
  return Py.Call().func(Py.Attribute().value(target).attr("extend")).args([Py.List().elts(args)]).create();
};
/** `includes` and `has`: `in`. */
const contains: Method = (self, target, node) => {
  const [value] = self.argumentsOf(node, 1) as [SyntaxNode];
  return Py.Compare().left(value).comparisons([Py.Comparison().op("in").comparator(target)]).create();
};
const join: Method = (self, target, node) => {
  const args = self.argumentsOf(node, 0, 1);
  const separator = args.length > 0 ? args[0] as SyntaxNode : Py.Constant().spelling("','").create();
  const strings = Py.Call().func(Py.Name().id("map")).args([Py.Name().id("str"), target]);
  return Py.Call().func(Py.Attribute().value(separator).attr("join")).add_args(strings).create();
};
const slice: Method = (self, target, node) => {
  const args = self.argumentsOf(node, 0, 1, 2);
  return Py.Subscript().value(target).slice(Py.Slice().lower(args[0] ?? null).upper(args[1] ?? null)).create();
};
/** `map` and `filter` of a callback: a list comprehension where the callback is a lambda of one name, and Python's
 * `map` or `filter` otherwise. */
const comprehension = (kind: "map" | "filter"): Method => (self, target, node) => {
  const found = self.callback(node);
  if (found !== null) {
    const [variable, body] = found;
    if (kind === "map") {
      return Py.ListComp().elt(body).generators([Py.Comprehension().target(variable).iter(target)]).create();
    }
    const generator = Py.Comprehension().target(variable).iter(target).add_ifs(body);
    return Py.ListComp().elt(Py.Name().id((variable.id as P.Identifier).spelling as string)).add_generators(generator)
      .create();
  }
  const [f] = self.argumentsOf(node, 1) as [SyntaxNode];
  return Py.Call().func(Py.Name().id("list")).args([Py.Call().func(Py.Name().id(kind)).args([f, target])]).create();
};
const reduce: Method = (self, target, node) => {
  const [f, ...rest] = self.argumentsOf(node, 1, 2) as [SyntaxNode, ...SyntaxNode[]];
  const reduce = Py.Attribute().value(self.module("functools")).attr("reduce");
  return Py.Call().func(reduce).args([f, target, ...rest]).create();
};
const toString: Method = (self, target, node) => {
  self.argumentsOf(node, 0);
  return Py.Call().func(Py.Name().id("str")).args([target]).create();
};

/** Methods of arrays, strings, maps and sets, by name. */
const METHODS: Record<string, Method> = {
  push, includes: contains, join, slice, map: comprehension("map"), filter: comprehension("filter"), reduce,
  toString, has: contains, toUpperCase: rename("upper"),
  toLowerCase: rename("lower"), trim: rename("strip"), startsWith: rename("startswith"), endsWith: rename("endswith"),
  entries: rename("items"),
};

/** The Python module that does what `program` does. Throws `TranspileError` at the first syntax node it cannot
 * translate. */
export function transpile(program: S.Program): P.Module {
  return new Translator(program).program(program);
}
