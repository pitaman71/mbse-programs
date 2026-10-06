/**
 * Definitions: the entities a Verilog source text declares, in its scopes, as IEEE 1800 resolves names (3.13, 23.9,
 * 26.3).
 *
 * - Scopes: the compilation unit (where design units, packages and `$unit`'s declarations are), each package, module,
 *   interface, program and class, each function and task, and each block: `begin`/`fork` blocks, generate blocks and
 *   `for` loops, named or not.
 * - Entity kinds: 'module', 'interface', 'program', 'package', 'parameter', 'localparam', 'type parameter', 'port',
 *   'net', 'variable', 'type', 'enumerator', 'genvar', 'modport', 'function', 'task', 'argument', 'instance', 'block',
 *   'class', 'constraint', 'property', 'sequence', 'let', 'clocking', 'clockvar', 'label' and 'import'. An enumeration's members are declared where the enumeration is, as SystemVerilog does.
 * - A non-ANSI port is one entity, which the header names and a port declaration declares.
 * - `import p::x` declares an 'import' entity whose `target` is `p::x`; `import p::*` makes the package's names visible
 *   where nothing nearer declares them, as wildcard imports do.
 * - A class's members are found in it, then in its base class (`extends`), or for an interface class in the interface
 *   classes it extends. A method or a constraint defined outside its class (`function void c::f()`, `constraint c::k`)
 *   is the entity its prototype declares, and its body sees the class's members. A `foreach` constraint's index
 *   variables are its own; `local::x` in `randomize() with` is `x` where the call is.
 * - A property, a sequence and a `let` have scopes of their own, where their ports are arguments; a named clocking
 *   block has one, where its signals are clockvars. A statement's label, and an assertion's, names a 'label'.
 * - An array method's `with (expression)` has its own scope, where the iterator is a variable: the name the call's
 *   argument gives it (`find(x) with (x > 0)`), or `item`.
 * - Lookup goes outward from a block to its design unit, then to the compilation unit. A package's and a class's names
 *   are qualified with `::` (`logger_pkg::FIELDS`, `packet::new`), a design unit's and a block's with `.`
 *   (`sampler.counter.count`).
 *
 * Not resolved: a member after `.` (of a structure, an object, an interface port or a hierarchical path), what an
 * instance's module declares, and a forward `typedef` (the declaration it announces is the entity).
 */

import { Entity, Program, Scope } from "../Framework/Definitions.js";
import { children, type SyntaxNode } from "../Framework/Syntax.js";
import * as S from "./Syntax.js";

type Method = (self: Definer, node: any, scope: Scope) => void;

const UNITS = new Map<Function, string>([[S.ModuleDeclaration, "module"], [S.InterfaceDeclaration, "interface"],
  [S.ProgramDeclaration, "program"], [S.PackageDeclaration, "package"]]);

class Definer {
  static METHODS = new Map<Function, Method>();
  readonly root: Scope;
  readonly program: Program;
  readonly imports: [Entity, S.ImportItem][] = [];
  readonly wildcards: [Scope, S.ImportItem][] = [];
  readonly classes: [Scope, S.ClassDeclaration][] = [];

  constructor(unit: S.SourceText) {
    this.root = new Scope("compilation unit", null, null, unit, ".");
    this.program = new Program(this.root);
  }

  /** The entity `name` declares in `scope`: a new one, or for a port or an argument declared twice (a non-ANSI port; a
   * method's prototype and its definition) the one already there. */
  entity(scope: Scope, kind: string, name: any, node: unknown): Entity {
    const existing = (scope.names.get(name.spelling) ?? []).filter((e) => e.kind === kind
      && (kind === "port" || kind === "argument"));
    const entity = existing[0] ?? this.program.add(new Entity(kind, name.spelling, scope));
    scope.declare(entity);
    entity.declarations.push(node);
    if (entity.definition === null) entity.definition = node;
    this.program.declares(name, entity);
    this.program.declares(node, entity);
    return entity;
  }

  /** A new scope for `node`, owned by an entity of `kind` when it is named. */
  scoped(scope: Scope, kind: string, name: any, node: unknown, scopeKind: string,
    separator: string | null = null): Scope {
    const owner = name !== null ? this.entity(scope, kind, name, node) : null;
    const inner = new Scope(scopeKind, owner, scope, node, separator);
    if (owner !== null) owner.scope = inner;
    return inner;
  }

  /** Records `node` and what it declares in `scope`, then its children in the scopes they are in. */
  visit(node: SyntaxNode, scope: Scope): void {
    this.program.located(node, scope);
    const method = Definer.METHODS.get(node.constructor);
    if (method !== undefined) {
      method(this, node, scope);
      return;
    }
    for (const [, , child] of children(node)) this.visit(child, scope);
  }

  visitAll(nodes: readonly SyntaxNode[], scope: Scope): void {
    for (const node of nodes) this.visit(node, scope);
  }

  /** Records `node` and every syntax node under it as in `scope`, declaring nothing. */
  locate(node: SyntaxNode, scope: Scope): void {
    this.program.located(node, scope);
    for (const [, , child] of children(node)) this.locate(child, scope);
  }

  // Design units

  designUnit(node: any, scope: Scope): void {
    const kind = UNITS.get(node.constructor) as string;
    const inner = this.scoped(scope, kind, node.name, node, kind, kind === "package" ? "::" : ".");
    this.program.located(node.name, scope);
    for (const item of node.imports ?? []) this.visit(item, inner);
    for (const item of [...(node.parameters ?? []), ...(node.ports ?? []), ...node.items]) this.visit(item, inner);
  }

  importDeclaration(node: any, scope: Scope): void {
    for (const item of node.items) {
      this.locate(item, scope);
      if (item.name === null) {
        this.wildcards.push([scope, item]);
      } else {
        this.imports.push([this.entity(scope, "import", item.name, item), item]);
      }
    }
  }

  // Declarations

  parameter(node: any, scope: Scope): void {
    if (node instanceof S.TypeParameterDeclaration) {
      for (const assignment of node.assignments) {
        this.locate(assignment, scope);
        this.entity(scope, "type parameter", assignment.name, assignment);
      }
      return;
    }
    if (node.type !== null) this.visit(node.type, scope);
    for (const assignment of node.assignments as any[]) {
      this.visitAll([...assignment.dimensions, ...(assignment.value !== null ? [assignment.value] : [])], scope);
      this.program.located(assignment, scope);
      this.program.located(assignment.name, scope);
      this.entity(scope, node.keyword, assignment.name, assignment);
    }
  }

  port(node: any, scope: Scope): void {
    for (const [, , child] of children(node)) if (child !== node.name) this.visit(child, scope);
    this.program.located(node.name, scope);
    this.entity(scope, "port", node.name, node);
  }

  declarators(node: any, scope: Scope, kind: string): void {
    for (const [, , child] of children(node)) if (!(child instanceof S.VariableDeclarator)) this.visit(child, scope);
    for (const declarator of node.declarators as any[]) {
      this.visitAll([...declarator.dimensions, ...(declarator.value !== null ? [declarator.value] : [])], scope);
      this.program.located(declarator, scope);
      this.program.located(declarator.name, scope);
      this.entity(scope, kind, declarator.name, declarator);
    }
  }

  typedef(node: any, scope: Scope): void {
    this.visitAll([node.type, ...node.dimensions], scope);
    this.program.located(node.name, scope);
    this.entity(scope, "type", node.name, node);
  }

  enum(node: any, scope: Scope): void {
    if (node.base !== null) this.visit(node.base, scope);
    this.visitAll(node.dimensions, scope);
    for (const member of node.members) {
      this.program.located(member, scope);
      this.program.located(member.name, scope);
      if (member.value !== null) this.visit(member.value, scope);
      this.entity(scope, "enumerator", member.name, member);
    }
  }

  genvar(node: any, scope: Scope): void {
    for (const name of node.names) {
      this.program.located(name, scope);
      this.entity(scope, "genvar", name, node);
    }
  }

  modport(node: any, scope: Scope): void {
    for (const item of node.items) {
      this.locate(item, scope);
      this.entity(scope, "modport", item.name, item);
    }
  }

  subroutine(node: any, scope: Scope): void {
    const kind = node instanceof S.TaskDeclaration ? "task" : "function";
    const name = node.name instanceof S.Identifier ? node.name : null;
    let inner: Scope;
    if (name === null) {
      this.locate(node.name, scope);
      inner = this.outOfBlock(node, scope, kind);
    } else {
      inner = this.scoped(scope, kind, name, node, kind);
      this.program.located(name, scope);
    }
    if (node instanceof S.FunctionDeclaration && node.type !== null) this.visit(node.type, scope);
    for (const port of node.ports as any[]) {
      this.visitAll([...(port.type !== null ? [port.type] : []), ...port.dimensions,
        ...(port.value !== null ? [port.value] : [])], inner);
      this.program.located(port, inner);
      this.program.located(port.name, inner);
      this.entity(inner, "argument", port.name, port);
    }
    this.visitAll(node.body, inner);
  }

  /** The scope of a method or a constraint defined outside its class, `c::f`: in the class's scope, and the entity of
   * the prototype the class declares. Any other qualified name is not resolved. */
  outOfBlock(node: any, scope: Scope, kind: string): Scope {
    const qualified = node.name;
    const classes = qualified.scope instanceof S.Identifier && qualified.name instanceof S.Identifier
      ? scope.resolve(qualified.scope.spelling as string).filter((e) => e.kind === "class") : [];
    const owner = classes[0];
    if (owner === undefined) return new Scope(kind, null, scope, node);
    const members = (owner.scope as Scope).lookup(qualified.name.spelling);
    const entity = members[0] !== undefined && members[0].kind === kind ? members[0] : null;
    if (entity === null) return new Scope(kind, null, owner.scope, node);
    entity.declarations.push(node);
    entity.definition = node;
    this.program.declares(qualified.name, entity);
    this.program.declares(node, entity);
    // a method's prototype's scope, where the definition's arguments are its arguments; a constraint has none
    return entity.scope ?? new Scope(kind, entity, owner.scope, node);
  }

  classDeclaration(node: any, scope: Scope): void {
    const inner = this.scoped(scope, "class", node.name, node, "class", "::");
    this.program.located(node.name, scope);
    this.visitAll([...(node.base !== null ? [node.base] : []), ...node.arguments, ...node.interfaces], scope);
    this.visitAll([...node.parameters, ...node.items], inner);
    this.classes.push([inner, node]);
  }

  constraintDeclaration(node: any, scope: Scope): void {
    let inner = scope;
    if (node.name instanceof S.Identifier) {
      this.program.located(node.name, scope);
      this.entity(scope, "constraint", node.name, node);
    } else {
      this.locate(node.name, scope);
      inner = this.outOfBlock(node, scope, "constraint");
    }
    this.visitAll(node.items, inner);
  }

  constraintPrototype(node: any, scope: Scope): void {
    this.program.located(node.name, scope);
    this.entity(scope, "constraint", node.name, node);
  }

  assertionDeclaration(node: any, scope: Scope): void {
    const kind = node instanceof S.PropertyDeclaration ? "property" : node instanceof S.SequenceDeclaration ? "sequence" : "let";
    const inner = this.scoped(scope, kind, node.name, node, kind);
    this.program.located(node.name, scope);
    for (const port of node.ports) {
      this.visitAll([...(port.type !== null ? [port.type] : []), ...port.dimensions, ...(port.value !== null ? [port.value] : [])],
        inner);
      this.program.located(port, inner);
      this.program.located(port.name, inner);
      this.entity(inner, "argument", port.name, port);
    }
    const body = node instanceof S.PropertyDeclaration ? node.spec : node instanceof S.SequenceDeclaration ? node.sequence
      : node.value;
    this.visitAll([...(node.variables ?? []), body], inner);
  }

  clockingDeclaration(node: any, scope: Scope): void {
    this.visit(node.clock, scope);
    const inner = this.scoped(scope, "clocking", node.name, node, "clocking");
    if (node.name !== null) this.program.located(node.name, scope);
    this.visitAll(node.items, inner);
  }

  clockingSignals(node: any, scope: Scope): void {
    for (const skew of [node.input_skew, node.output_skew]) if (skew !== null) this.visit(skew, scope);
    for (const signal of node.signals) {
      this.program.located(signal, scope);
      this.program.located(signal.name, scope);
      if (signal.value !== null) this.visit(signal.value, scope.parent as Scope); // what it stands for is outside the block
      this.entity(scope, "clockvar", signal.name, signal);
    }
  }

  labeled(node: any, scope: Scope): void {
    if (node.label !== null) {
      this.program.located(node.label, scope);
      this.entity(scope, "label", node.label, node);
    }
    this.visit(node instanceof S.LabeledStatement ? node.statement : node.assertion, scope);
  }

  arrayMethodWith(node: any, scope: Scope): void {
    const inner = new Scope("with", null, scope, node);
    const call = node.call;
    const args = call instanceof S.CallExpression ? call.arguments : [];
    const iterator = args[0];
    if (args.length === 1 && iterator instanceof S.NameExpression && iterator.name instanceof S.Identifier) {
      this.visit(call.callee as SyntaxNode, scope); // `find(x)`: `x` names the iterator
      this.locate(iterator, scope);
      this.entity(inner, "variable", iterator.name, iterator);
    } else {
      this.visit(call, scope);
      const item = this.program.add(new Entity("variable", "item", inner));
      inner.declare(item);
      item.definition = node;
      item.declarations.push(node);
    }
    this.visit(node.expression, inner);
  }

  instance(node: any, scope: Scope): void {
    this.program.located(node.module, scope);
    this.visitAll(node.parameters, scope);
    for (const instance of node.instances) {
      this.program.located(instance, scope);
      this.program.located(instance.name, scope);
      this.visitAll([...instance.dimensions, ...instance.connections], scope);
      this.entity(scope, "instance", instance.name, instance);
    }
  }

  connection(node: any, scope: Scope): void {
    this.program.located(node.name, scope); // a port or argument of what is called: not resolved
    if (node.value !== null) this.visit(node.value, scope);
  }

  // Blocks

  block(node: any, scope: Scope): void {
    const inner = this.scoped(scope, "block", node.name, node, "block");
    if (node.name !== null) this.program.located(node.name, scope);
    this.visitAll(node.items, inner);
  }

  generateFor(node: any, scope: Scope): void {
    this.program.located(node.name, scope);
    this.visitAll([node.start, node.condition, node.step, node.body], scope);
  }

  forStatement(node: any, scope: Scope): void {
    const inner = new Scope("block", null, scope, node);
    this.visitAll([...node.initializers, ...(node.condition !== null ? [node.condition] : []), ...node.steps, node.body],
      inner);
  }

  foreach(node: any, scope: Scope): void {
    this.visit(node.array, scope);
    const inner = new Scope("block", null, scope, node);
    for (const variable of node.variables) {
      this.program.located(variable, inner);
      this.entity(inner, "variable", variable, node);
    }
    this.visit(node.body, inner);
  }

  resolveImports(): void {
    const packages = new Map(this.root.entities().filter((e) => e.kind === "package").map((e) => [e.name, e]));
    for (const [entity, item] of this.imports) {
      const pkg = packages.get(item.package?.spelling as string);
      if (pkg !== undefined) { // a package always has its scope
        const found = (pkg.scope as Scope).lookup((item.name as S.Identifier).spelling as string);
        if (found.length > 0) entity.target = found[0] as Entity;
      }
    }
    for (const [scope, item] of this.wildcards) {
      const pkg = packages.get(item.package?.spelling as string);
      if (pkg !== undefined && !scope.using.includes(pkg.scope as Scope)) scope.using.push(pkg.scope as Scope);
    }
  }

  /** Each class's base, or an interface class's interfaces, as the scopes its lookup goes on to. */
  resolveBases(): void {
    for (const [inner, node] of this.classes) {
      const bases = node.base !== null ? [node.base] : node.interface ? node.interfaces : [];
      for (const base of bases) {
        const found = lookup(inner.parent as Scope, base.name).filter((e) => e.kind === "class");
        if (found[0] !== undefined) inner.bases.push(found[0].scope as Scope);
      }
    }
  }
}

const methods: [Function[], Method][] = [
  [[S.ModuleDeclaration, S.InterfaceDeclaration, S.ProgramDeclaration, S.PackageDeclaration], (d, n, s) => d.designUnit(n, s)],
  [[S.ImportDeclaration], (d, n, s) => d.importDeclaration(n, s)],
  [[S.ParameterDeclaration, S.TypeParameterDeclaration], (d, n, s) => d.parameter(n, s)],
  [[S.AnsiPort, S.InterfacePort, S.PortReference], (d, n, s) => d.port(n, s)],
  [[S.NetDeclaration], (d, n, s) => d.declarators(n, s, "net")],
  [[S.VariableDeclaration], (d, n, s) => d.declarators(n, s, "variable")],
  [[S.PortDeclaration], (d, n, s) => d.declarators(n, s, "port")],
  [[S.TypedefDeclaration], (d, n, s) => d.typedef(n, s)],
  [[S.EnumType], (d, n, s) => d.enum(n, s)],
  [[S.GenvarDeclaration], (d, n, s) => d.genvar(n, s)],
  [[S.ModportDeclaration], (d, n, s) => d.modport(n, s)],
  [[S.FunctionDeclaration, S.TaskDeclaration], (d, n, s) => d.subroutine(n, s)],
  [[S.ModuleInstantiation], (d, n, s) => d.instance(n, s)],
  [[S.NamedConnection], (d, n, s) => d.connection(n, s)],
  [[S.SeqBlock, S.ParBlock, S.GenerateBlock], (d, n, s) => d.block(n, s)],
  [[S.GenerateFor], (d, n, s) => d.generateFor(n, s)],
  [[S.ForStatement], (d, n, s) => d.forStatement(n, s)],
  [[S.ForeachStatement], (d, n, s) => d.foreach(n, s)],
  [[S.ClassDeclaration], (d, n, s) => d.classDeclaration(n, s)],
  [[S.ConstraintDeclaration], (d, n, s) => d.constraintDeclaration(n, s)],
  [[S.ConstraintPrototype], (d, n, s) => d.constraintPrototype(n, s)],
  [[S.ForeachConstraint], (d, n, s) => d.foreach(n, s)],
  [[S.ArrayMethodWithExpression], (d, n, s) => d.arrayMethodWith(n, s)],
  [[S.PropertyDeclaration, S.SequenceDeclaration, S.LetDeclaration], (d, n, s) => d.assertionDeclaration(n, s)],
  [[S.ClockingDeclaration], (d, n, s) => d.clockingDeclaration(n, s)],
  [[S.ClockingSignals], (d, n, s) => d.clockingSignals(n, s)],
  [[S.LabeledStatement, S.AssertionItem], (d, n, s) => d.labeled(n, s)],
];
for (const [kinds, method] of methods) for (const kind of kinds) Definer.METHODS.set(kind, method);

/** The entities a source text declares, in their scopes. */
export function define(unit: S.SourceText): Program {
  const definer = new Definer(unit);
  definer.program.located(unit, definer.root);
  for (const item of unit.items) definer.visit(item, definer.root);
  definer.resolveImports();
  definer.resolveBases();
  return definer.program;
}

/** The spelling of an identifier, or of a parameterized class's name. */
function spelling(name: any): string {
  return name instanceof S.ParameterizedName ? name.name?.spelling as string : name.spelling;
}

/** The entities a name finds from `scope`: an identifier or a parameterized class as lookup resolves it, and
 * `p::c::x` as `x` in `c` in the package or class `p` that `p` resolves to. */
function lookup(scope: Scope, name: any): Entity[] {
  if (!(name instanceof S.ScopedName)) return scope.resolve(spelling(name));
  let found = scope.resolve(spelling(name.scope));
  for (;;) { // each scope, a package or a class, in the one before it
    const holder = found.find((e) => e.kind === "package" || e.kind === "class");
    if (holder === undefined) return [];
    const inner = holder.scope as Scope; // a package or a class always has its scope
    if (!(name.name instanceof S.ScopedName)) return inner.lookup(spelling(name.name));
    name = name.name;
    found = inner.lookup(spelling(name.scope));
  }
}

/** The entities a `NameExpression`, an `Identifier` or a `ScopedName` of the program refers to, looked up from where it
 * is: an identifier that declares an entity refers to it; `p::x` to `x` in the package or class `p`, found from where
 * the name is, and `p::c::x` to `x` in `c` in `p`. */
export function referents(program: Program, name: any): Entity[] {
  if (name instanceof S.NameExpression) name = name.name;
  if (name instanceof S.LocalName) name = name.name;
  if (name instanceof S.ScopedName) return lookup(program.scope_of(name) ?? program.root, name);
  const scope = program.scope_of(name);
  if (scope === null) return [];
  const entity = program.entity_of(name);
  if (entity !== null) return [entity];
  const out: Entity[] = [];
  for (let found of scope.resolve((name as S.Identifier).spelling as string)) {
    found = found.kind === "import" && found.target !== null ? found.resolved() : found;
    if (!out.includes(found)) out.push(found);
  }
  return out;
}
