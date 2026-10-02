/**
 * Definitions: the names a Python module binds, in the scopes Python gives them.
 *
 * `define(module)` reads a module and returns a `Framework.Definitions.Program`, whose qualified names join with `.`
 * (`Shape.area`). Its entities have these kinds:
 *
 * - 'class' and 'function', each with its own scope;
 * - 'variable': a name bound by assignment, `for`, `with ... as`, `except ... as`, `del`, a pattern's capture or an
 *   assignment expression;
 * - 'parameter' (of a function or lambda), 'type parameter' and 'type alias';
 * - 'import': a name an import binds (`import a.b` binds `a`).
 *
 * There is one entity per name per scope: every syntax node that binds the name is one of its `declarations`, in source
 * order, and the first is its `definition`. The first binding visited decides its kind: the module's names are visited
 * first, then each function's and class's, as Python's symbol tables are built.
 *
 * Scopes are those of Python's execution model (§4.2): 'module', 'class', 'function', 'lambda', 'comprehension' and
 * 'type parameters' (the annotation scope of a generic function, class or type alias). A name bound anywhere in a scope
 * is local to it, unless `global` declares it the module's or `nonlocal` the nearest enclosing function's. Names are
 * looked up outwards through enclosing functions to the module, past class bodies: every scope's parent is the nearest
 * enclosing scope that is not a class. Decorators, defaults, a class's bases and the first iterable of a comprehension
 * are in the enclosing scope, and an assignment expression in a comprehension binds in the scope around it.
 *
 * What it does not do: resolve attributes (`a.b`, whose `b` depends on `a`'s value) or the members of imported modules,
 * follow `from module import *`, see names that `exec` or `globals()` bind, or treat builtins as entities.
 */

import { Entity, Program, Scope } from "../Framework/Definitions.js";
import { children, type SyntaxNode, walk } from "../Framework/Syntax.js";
import * as S from "./Syntax.js";

type Handler = (self: Definer, node: any, scope: Scope) => void;

/** Declares what a module binds. Function and class bodies are visited once the scope around them is complete, so that
 * `nonlocal` finds a binding that comes later in the enclosing function. */
class Definer {
  static HANDLERS = new Map<Function, Handler>();
  readonly program: Program;
  readonly bodies: [SyntaxNode[], Scope][] = [];

  constructor(module: S.Module) {
    this.program = new Program(new Scope("module", null, null, module, "."));
  }

  // Scopes and bindings

  /** The scope where a scope opened in `scope` looks names up next: `scope` itself, past class bodies. */
  static enclosing(scope: Scope): Scope {
    while (scope.kind === "class") scope = scope.parent as Scope;
    return scope;
  }

  /** The entity `name` names in `scope`, which a global or nonlocal declaration may have brought in; a new one of
   * `kind` if there is none. */
  entity(scope: Scope, name: string, kind: string): Entity {
    const found = scope.names.get(name);
    if (found !== undefined) return found[0] as Entity;
    const entity = this.program.add(new Entity(kind, name, scope));
    scope.declare(entity);
    return entity;
  }

  /** Binds `identifier` in `scope`, `node` binding it. */
  bind(scope: Scope, identifier: S.Identifier, node: SyntaxNode, kind: string): Entity {
    const entity = this.entity(scope, identifier.spelling as string, kind);
    entity.declarations.push(node);
    this.program.declares(node, entity);
    this.program.declares(identifier, entity);
    this.program.located(identifier, scope);
    return entity;
  }

  /** An assignment target: names bind in `scope`, and other expressions are evaluated there. */
  target(node: SyntaxNode, scope: Scope): void {
    this.program.located(node, scope);
    if (node instanceof S.Name) {
      this.bind(scope, node.id as S.Identifier, node, "variable");
    } else if (node instanceof S.Tuple || node instanceof S.List) {
      for (const elt of node.elts) this.target(elt, scope);
    } else if (node instanceof S.Starred || node instanceof S.Parenthesized) {
      this.target(node.value as SyntaxNode, scope);
    } else {
      this.visit(node, scope);
    }
  }

  /** The nearest enclosing function scope where `name` is bound, for `nonlocal name` in `scope`. */
  nonlocalScope(scope: Scope, name: string): Scope | null {
    let outer = scope.parent;
    while (outer !== null && outer.parent !== null) {
      if (outer.kind === "function" && outer.names.has(name)) return outer; // a lambda's body holds no `nonlocal`
      outer = outer.parent;
    }
    return null;
  }

  // Visiting

  visit(node: SyntaxNode, scope: Scope): void {
    this.program.located(node, scope);
    const method = Definer.HANDLERS.get(node.constructor);
    if (method !== undefined) {
      method(this, node, scope);
      return;
    }
    for (const [, , child] of children(node)) this.visit(child, scope);
  }

  statements(statements: SyntaxNode[], scope: Scope): void {
    for (const statement of statements) this.visit(statement, scope);
  }

  visitAll(nodes: (SyntaxNode | null)[], scope: Scope): void {
    for (const node of nodes) if (node !== null) this.visit(node, scope);
  }

  /** The annotation scope of a generic function, class or type alias, with its type parameters; `scope` itself if it
   * has none. */
  typeParameters(node: S.FunctionDef | S.AsyncFunctionDef | S.ClassDef | S.TypeAlias, scope: Scope): Scope {
    if (node.type_params.length === 0) return scope;
    const inner = new Scope("type parameters", null, Definer.enclosing(scope), node);
    for (const parameter of node.type_params as (S.TypeVar | S.ParamSpec | S.TypeVarTuple)[]) {
      this.program.located(parameter, inner);
      this.bind(inner, parameter.name as S.Identifier, parameter, "type parameter");
      const bound = parameter instanceof S.TypeVar ? parameter.bound : null;
      this.visitAll([bound, parameter.default_value], inner);
    }
    return inner;
  }

  /** Parameters bind in `inner`; their defaults are evaluated in `scope`, their annotations in `annotations`. */
  arguments(node: S.Arguments, scope: Scope, annotations: Scope, inner: Scope): void {
    this.program.located(node, inner);
    for (const arg of [...node.posonlyargs, ...node.args, node.vararg, ...node.kwonlyargs, node.kwarg]) {
      if (arg === null) continue;
      this.program.located(arg, inner);
      this.visitAll([arg.annotation], annotations);
      this.visitAll([arg.default_value], scope);
      this.bind(inner, arg.arg as S.Identifier, arg, "parameter");
    }
  }
}

const loop: Handler = (self, node: S.For | S.AsyncFor, scope) => {
  self.visit(node.iter as SyntaxNode, scope);
  self.target(node.target as SyntaxNode, scope);
  self.statements(node.body, scope);
  self.statements(node.orelse, scope);
};
const withItems: Handler = (self, node: S.With | S.AsyncWith, scope) => {
  for (const item of node.items) {
    self.program.located(item, scope);
    self.visit(item.context_expr as SyntaxNode, scope);
    if (item.optional_vars !== null) self.target(item.optional_vars, scope);
  }
  self.statements(node.body, scope);
};
const imports: Handler = (self, node: S.Import | S.ImportFrom, scope) => {
  for (const alias of node.names) {
    self.program.located(alias, scope);
    if (alias.asname !== null) self.bind(scope, alias.asname, alias, "import");
    else if (alias.name !== null) self.bind(scope, alias.name.names[0] as S.Identifier, alias, "import"); // `a.b` binds `a`
  }
};
const declarations: Handler = (self, node: S.Global | S.Nonlocal, scope) => {
  for (const identifier of node.names) {
    const name = identifier.spelling as string;
    const outer = node instanceof S.Global ? self.program.root : self.nonlocalScope(scope, name) ?? scope;
    const entity = self.entity(outer, name, "variable");
    scope.declare(entity);
    self.program.declares(identifier, entity);
    self.program.located(identifier, scope);
  }
};
const fn: Handler = (self, node: S.FunctionDef | S.AsyncFunctionDef, scope) => {
  self.visitAll(node.decorator_list, scope);
  const entity = self.bind(scope, node.name as S.Identifier, node, "function");
  const annotations = self.typeParameters(node, scope);
  const inner = new Scope("function", entity, Definer.enclosing(annotations), node);
  entity.scope = inner;
  self.arguments(node.args as S.Arguments, scope, annotations, inner);
  if (node.returns !== null) self.visit(node.returns, annotations);
  self.bodies.push([node.body, inner]);
};
const comprehension: Handler = (self, node: S.ListComp | S.SetComp | S.GeneratorExp | S.DictComp, scope) => {
  const inner = new Scope("comprehension", null, Definer.enclosing(scope), node);
  node.generators.forEach((generator, i) => {
    self.program.located(generator, inner);
    self.visit(generator.iter as SyntaxNode, i === 0 ? scope : inner); // the first iterable is evaluated outside
    self.target(generator.target as SyntaxNode, inner);
    self.visitAll(generator.ifs, inner);
  });
  if (node instanceof S.DictComp) self.visitAll([node.key, node.value], inner);
  else self.visit(node.elt as SyntaxNode, inner);
};
const capture: Handler = (self, node: S.MatchAs | S.MatchStar, scope) => {
  if (node instanceof S.MatchAs && node.pattern !== null) self.visit(node.pattern, scope);
  if (node.name !== null) self.bind(scope, node.name, node, "variable");
};

Definer.HANDLERS = new Map<Function, Handler>([
  [S.Name, (self, node: S.Name, scope) => self.program.located(node.id, scope)],
  // the name is not located
  [S.Attribute, (self, node: S.Attribute, scope) => self.visit(node.value as SyntaxNode, scope)],
  [S.Keyword, (self, node: S.Keyword, scope) => self.visit(node.value as SyntaxNode, scope)],
  [S.Assign, (self, node: S.Assign, scope) => {
    self.visit(node.value as SyntaxNode, scope);
    for (const target of node.targets) self.target(target, scope);
  }],
  [S.AugAssign, (self, node: S.AugAssign, scope) => {
    self.visit(node.value as SyntaxNode, scope);
    self.target(node.target as SyntaxNode, scope);
  }],
  [S.AnnAssign, (self, node: S.AnnAssign, scope) => {
    self.visit(node.annotation as SyntaxNode, scope);
    if (node.value !== null) self.visit(node.value, scope);
    self.target(node.target as SyntaxNode, scope);
  }],
  [S.Delete, (self, node: S.Delete, scope) => {
    for (const target of node.targets) self.target(target, scope);
  }],
  [S.For, loop], [S.AsyncFor, loop], [S.With, withItems], [S.AsyncWith, withItems],
  [S.ExceptHandler, (self, node: S.ExceptHandler, scope) => {
    if (node.type !== null) self.visit(node.type, scope);
    if (node.name !== null) self.bind(scope, node.name, node, "variable");
    self.statements(node.body, scope);
  }],
  [S.Import, imports], [S.ImportFrom, imports], [S.Global, declarations], [S.Nonlocal, declarations],
  [S.FunctionDef, fn], [S.AsyncFunctionDef, fn],
  [S.ClassDef, (self, node: S.ClassDef, scope) => {
    self.visitAll(node.decorator_list, scope);
    const entity = self.bind(scope, node.name as S.Identifier, node, "class");
    const annotations = self.typeParameters(node, scope);
    self.visitAll([...node.bases, ...node.keywords], annotations);
    entity.scope = new Scope("class", entity, Definer.enclosing(annotations), node);
    self.bodies.push([node.body, entity.scope]);
  }],
  [S.TypeAlias, (self, node: S.TypeAlias, scope) => {
    const name = node.name as S.Name;
    self.program.located(name, scope);
    self.program.declares(name, self.bind(scope, name.id as S.Identifier, node, "type alias"));
    self.visit(node.value as SyntaxNode, self.typeParameters(node, scope));
  }],
  [S.Lambda, (self, node: S.Lambda, scope) => {
    const inner = new Scope("lambda", null, Definer.enclosing(scope), node);
    self.arguments(node.args as S.Arguments, scope, scope, inner);
    self.visit(node.body as SyntaxNode, inner);
  }],
  [S.ListComp, comprehension], [S.SetComp, comprehension], [S.GeneratorExp, comprehension],
  [S.DictComp, comprehension],
  [S.NamedExpr, (self, node: S.NamedExpr, scope) => {
    self.visit(node.value as SyntaxNode, scope);
    let outer = scope;
    while (outer.kind === "comprehension") outer = outer.parent as Scope; // it binds in the scope around them
    const target = node.target as S.Name;
    self.program.located(target, scope);
    self.program.located(target.id, scope);
    self.bind(outer, target.id as S.Identifier, target, "variable");
  }],
  [S.MatchCase, (self, node: S.MatchCase, scope) => {
    self.visit(node.pattern as SyntaxNode, scope);
    self.visitAll([node.guard], scope);
    self.statements(node.body, scope);
  }],
  [S.MatchAs, capture], [S.MatchStar, capture],
  [S.MatchMapping, (self, node: S.MatchMapping, scope) => {
    self.visitAll([...node.keys, ...node.patterns], scope);
    if (node.rest !== null) self.bind(scope, node.rest, node, "variable");
  }],
  [S.MatchClass, (self, node: S.MatchClass, scope) => {
    self.visitAll([node.cls, ...node.patterns, ...node.kwd_patterns], scope); // keyword names are attributes
  }],
]);

/** The entities a module binds, in their scopes. */
export function define(module: S.Module): Program {
  const definer = new Definer(module);
  const program = definer.program;
  program.located(module, program.root);
  definer.bodies.push([module.body, program.root]);
  while (definer.bodies.length > 0) {
    const [body, scope] = definer.bodies.shift() as [SyntaxNode[], Scope];
    definer.statements(body, scope);
  }
  // properties are in source order
  const order = new Map<unknown, number>([...walk(module)].map((node, i) => [node, i]));
  for (const entity of program.entities()) {
    entity.declarations.sort((a, b) => (order.get(a) as number) - (order.get(b) as number));
    entity.definition = entity.declarations[0] ?? null;
  }
  return program;
}

/** The entities a `Name`, or an `Identifier` of the program, refers to, looked up from where it is. An attribute's name
 * depends on a value, and a keyword argument's on the function called, so they find nothing. */
export function referents(program: Program, name: SyntaxNode): Entity[] {
  const identifier = name instanceof S.Name ? name.id as S.Identifier : name as S.Identifier;
  const scope = program.scope_of(identifier);
  if (scope === null) return [];
  const entity = program.entity_of(identifier);
  return entity !== null ? [entity] : scope.resolve(identifier.spelling as string);
}
