/**
 * Definitions: the entities a Verilog source text declares, in its scopes, as IEEE 1800 resolves names (3.13, 23.9,
 * 26.3).
 *
 * - Scopes: the compilation unit (where design units, packages and `$unit`'s declarations are), each package, module,
 *   interface and program, each function and task, and each block: `begin`/`fork` blocks, generate blocks and `for`
 *   loops, named or not.
 * - Entity kinds: 'module', 'interface', 'program', 'package', 'parameter', 'localparam', 'type parameter', 'port',
 *   'net', 'variable', 'type', 'enumerator', 'genvar', 'modport', 'function', 'task', 'argument', 'instance', 'block'
 *   and 'import'. An enumeration's members are declared where the enumeration is, as SystemVerilog does.
 * - A non-ANSI port is one entity, which the header names and a port declaration declares.
 * - `import p::x` declares an 'import' entity whose `target` is `p::x`; `import p::*` makes the package's names visible
 *   where nothing nearer declares them, as wildcard imports do.
 * - Lookup goes outward from a block to its design unit, then to the compilation unit. A package's names are qualified
 *   with `::` (`logger_pkg::FIELDS`), a design unit's and a block's with `.` (`sampler.counter.count`).
 *
 * Not resolved: a member after `.` (of a structure, an interface port or a hierarchical path), and what an instance's
 * module declares.
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

  constructor(unit: S.SourceText) {
    this.root = new Scope("compilation unit", null, null, unit, ".");
    this.program = new Program(this.root);
  }

  /** The entity `name` declares in `scope`: a new one, or for a port declared twice the one already there. */
  entity(scope: Scope, kind: string, name: any, node: unknown): Entity {
    const existing = (scope.names.get(name.spelling) ?? []).filter((e) => e.kind === kind && kind === "port");
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
    if (name === null) this.locate(node.name, scope); // `p::f`, an out-of-block definition: not resolved
    const inner = this.scoped(scope, kind, name, node, kind);
    if (name !== null) this.program.located(name, scope);
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
];
for (const [kinds, method] of methods) for (const kind of kinds) Definer.METHODS.set(kind, method);

/** The entities a source text declares, in their scopes. */
export function define(unit: S.SourceText): Program {
  const definer = new Definer(unit);
  definer.program.located(unit, definer.root);
  for (const item of unit.items) definer.visit(item, definer.root);
  definer.resolveImports();
  return definer.program;
}

/** The entities a `NameExpression`, an `Identifier` or a `ScopedName` of the program refers to, looked up from where it
 * is: an identifier that declares an entity refers to it; a `p::x` to `x` in package `p`. */
export function referents(program: Program, name: any): Entity[] {
  if (name instanceof S.NameExpression) name = name.name;
  if (name instanceof S.ScopedName) {
    const packages = program.root.lookup(name.scope?.spelling as string).filter((e) => e.kind === "package");
    const pkg = packages[0];
    if (pkg === undefined || pkg.scope === null || !(name.name instanceof S.Identifier)) return [];
    return pkg.scope.lookup(name.name.spelling as string);
  }
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
