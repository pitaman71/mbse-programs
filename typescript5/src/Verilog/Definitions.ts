/**
 * Definitions: the entities a Verilog source text declares, in its scopes, as IEEE 1800 resolves names (3.13, 23.9,
 * 26.3).
 *
 * - Scopes: the compilation unit (where design units, packages and `$unit`'s declarations are), each package, module,
 *   interface, program and class, each function and task, and each block: `begin`/`fork` blocks, generate blocks and
 *   `for` loops, named or not.
 * - Entity kinds: 'module', 'interface', 'program', 'package', 'parameter', 'localparam', 'type parameter', 'port',
 *   'net', 'variable', 'type', 'enumerator', 'genvar', 'modport', 'function', 'task', 'argument', 'instance',
 *   'block', 'class', 'constraint', 'property', 'sequence', 'let', 'clocking', 'clockvar', 'label', 'covergroup',
 *   'coverpoint', 'cross', 'bins', 'production', 'checker', 'primitive', 'specparam', 'config' and 'import'. An
 *   enumeration's members are declared where the enumeration is, as SystemVerilog does; a member `name[2]` declares
 *   `name0` and `name1`, and `name[1:3]` declares `name1` to `name3` (with decimal numbers). A `nettype` declares a
 *   'type'.
 * - An `extern` design unit or primitive declares nothing: the unit or primitive of its name does, and with `.*` takes
 *   the extern's parameters and ports. A DPI import declares its function or task; a C name is not looked up. `bind`
 *   finds its target where it is, and its instances and connections in the target; what it instantiates is declared
 *   nowhere.
 * - A non-ANSI port is one entity, which the header names and a port declaration declares. An explicit port's own name
 *   (`.p(x)`) is outside the module: what it connects is found inside.
 * - `import p::x` declares an 'import' entity whose `target` is `p::x`; `import p::*` makes the package's names visible
 *   where nothing nearer declares them, as wildcard imports do.
 * - A class's members are found in it, then in its base class (`extends`), or for an interface class in the interface
 *   classes it extends. A method or a constraint defined outside its class (`function void c::f()`, `constraint c::k`)
 *   is the entity its prototype declares, and its body sees the class's members. A `foreach` constraint's index
 *   variables are its own; `local::x` in `randomize() with` is `x` where the call is.
 * - A property, a sequence, a `let`, a checker and a `randsequence`'s production have scopes of their own, where
 *   their ports are arguments, and a `randsequence` one where its productions are; a named clocking block has one,
 *   where its signals are clockvars. A statement's label, and an assertion's, names a 'label'.
 * - A covergroup has a scope, where its ports and its `sample` function's are arguments; a coverpoint and a cross have
 *   scopes, where their bins are, and a labeled one is an entity. A bin's `with (filter)` has a scope where `item` is.
 * - A pattern's variables (`.v`) are declared in a block of their own, which the `case` item's guard and body, or the
 *   `if`'s or `?:`'s condition and consequence, see.
 * - An array method's `with (expression)` has its own scope, where the iterator is a variable: the name the call's
 *   argument gives it (`find(x) with (x > 0)`), or `item`.
 * - Lookup goes outward from a block to its design unit, then to the compilation unit. A package's and a class's names
 *   are qualified with `::` (`logger_pkg::FIELDS`, `packet::new`), a design unit's and a block's with `.`
 *   (`sampler.counter.count`).
 *
 * Not resolved: a member after `.` (of a structure, an object, an interface port or a hierarchical path, or an
 * interface's type: `bus.t`), what an instance's module declares, a forward `typedef` (the declaration it announces is
 * the entity), and the macros' names of `` `ifdef `` and `` `elsif ``.
 */

import { Entity, Program, Scope } from "../Framework/Definitions.js";
import { children, type SyntaxNode, walk } from "../Framework/Syntax.js";
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
  readonly binds: [Scope, S.BindDirective][] = [];
  readonly externs = new Map<string, any>();

  constructor(unit: S.SourceText) {
    this.root = new Scope("compilation unit", null, null, unit, ".");
    this.program = new Program(this.root);
    for (const item of unit.items as any[]) if (item.extern === true) this.externs.set(item.name.spelling, item);
  }

  /** The entity `name` declares in `scope`, as `spelling` if it is given: a new one, or for a port or an argument
   * declared twice (a non-ANSI port; a method's prototype and its definition) the one already there. */
  entity(scope: Scope, kind: string, name: any, node: unknown, spelling: string | null = null): Entity {
    const named = spelling ?? name.spelling;
    const existing = (scope.names.get(named) ?? []).filter((e) => e.kind === kind
      && (kind === "port" || kind === "argument"));
    const entity = existing[0] ?? this.program.add(new Entity(kind, named, scope));
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
    if (node.extern === true) { // a header alone: the unit of its name declares
      this.locate(node, scope);
      return;
    }
    const kind = UNITS.get(node.constructor) as string;
    const inner = this.scoped(scope, kind, node.name, node, kind, kind === "package" ? "::" : ".");
    this.program.located(node.name, scope);
    for (const item of node.imports ?? []) this.visit(item, inner);
    let parameters: any[] = node.parameters ?? [];
    let ports: any[] = node.ports ?? [];
    const extern = this.externs.get(node.name.spelling);
    if (ports.some((p) => p instanceof S.WildcardPort) && extern !== undefined) { // `.*`: the extern's ports
      parameters = parameters.length > 0 ? parameters : extern.parameters;
      ports = extern.ports;
    }
    for (const item of [...parameters, ...ports, ...node.items]) this.visit(item, inner);
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

  explicitPort(node: any, scope: Scope): void {
    if (node.value !== null) this.visit(node.value, scope); // its name is outside, and not looked up
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

  /** `bus_if.mp a;`: the interface is found where it is; its modport, the interface's, is not looked up. */
  interfacePortDeclaration(node: any, scope: Scope): void {
    this.program.located(node.interface, scope);
    for (const declarator of node.declarators) {
      this.visitAll(declarator.dimensions, scope);
      this.program.located(declarator, scope);
      this.program.located(declarator.name, scope);
      this.entity(scope, "port", declarator.name, declarator);
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
      this.visitAll([member.left, member.right, member.value].filter((p) => p !== null), scope);
      if (member.left === null) {
        this.entity(scope, "enumerator", member.name, member);
        continue;
      }
      const declared = numbers(member.left, member.right).map((number) =>
        this.entity(scope, "enumerator", member.name, member, `${member.name.spelling}${number}`));
      if (declared.length > 0) { // the member's name declares the first
        this.program.declares(member.name, declared[0] as Entity);
        this.program.declares(member, declared[0] as Entity);
      }
    }
  }

  netType(node: any, scope: Scope): void {
    this.visitAll([node.type, ...(node.function !== null ? [node.function] : [])], scope);
    this.program.located(node.name, scope);
    this.entity(scope, "type", node.name, node);
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
    if (node.name instanceof S.InterfaceMethodName) { // `port.t`: the interface's task, not looked up
      this.locate(node.name, scope);
      inner = new Scope(kind, null, scope, node);
    } else if (name === null) {
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

  /** A `randsequence` has a scope of its productions, and each production one of its ports. */
  randsequence(node: any, scope: Scope): void {
    const inner = new Scope("block", null, scope, node);
    if (node.first !== null) this.program.located(node.first, inner);
    for (const production of node.productions) {
      this.visitAll(production.type !== null ? [production.type] : [], scope);
      const own = this.scoped(inner, "production", production.name, production, "production");
      this.program.located(production.name, inner);
      for (const port of production.ports) {
        this.visitAll([...(port.type !== null ? [port.type] : []), ...port.dimensions,
          ...(port.value !== null ? [port.value] : [])], own);
        this.program.located(port, own);
        this.program.located(port.name, own);
        this.entity(own, "argument", port.name, port);
      }
      this.visitAll(production.rules, own);
    }
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

  covergroup(node: any, scope: Scope): void {
    if (node.clock !== null) this.visit(node.clock, scope);
    const inner = this.scoped(scope, "covergroup", node.name, node, "covergroup");
    this.program.located(node.name, scope);
    for (const port of [...node.ports, ...(node.sample !== null ? node.sample.ports : [])]) {
      this.visitAll([...(port.type !== null ? [port.type] : []), ...port.dimensions, ...(port.value !== null ? [port.value] : [])],
        inner);
      this.program.located(port, inner);
      this.program.located(port.name, inner);
      this.entity(inner, "argument", port.name, port);
    }
    if (node.sample !== null) this.program.located(node.sample, inner);
    this.visitAll(node.items, inner);
  }

  coverpoint(node: any, scope: Scope): void {
    const point = node instanceof S.Coverpoint;
    const kind = point ? "coverpoint" : "cross";
    const parts = point ? [...(node.type !== null ? [node.type] : []), node.expression] : node.items;
    this.visitAll([...parts, ...(node.condition !== null ? [node.condition] : [])], scope);
    const inner = this.scoped(scope, kind, node.label, node, kind);
    if (node.label !== null) this.program.located(node.label, scope);
    this.visitAll(point ? node.items : node.body, inner);
  }

  bins(node: any, scope: Scope): void {
    this.program.located(node.name, scope);
    this.entity(scope, "bins", node.name, node);
    const parts = node instanceof S.BinsSelection ? [node.select]
      : [...(node.size !== null ? [node.size] : []), node.initializer];
    this.visitAll([...parts, ...(node.condition !== null ? [node.condition] : [])], scope.parent as Scope);
  }

  /** Values with a `with (filter)`, where `item` is each value. */
  binsFilter(node: any, scope: Scope): void {
    this.visitAll(node instanceof S.BinsValues ? node.values : [node.expression], scope);
    if (node.filter !== null) {
      const inner = new Scope("with", null, scope, node);
      const item = this.program.add(new Entity("variable", "item", inner));
      inner.declare(item);
      item.definition = node;
      item.declarations.push(node);
      this.visit(node.filter, inner);
    }
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

  /** A configuration has a scope of its localparams; its cells and libraries are the libraries', not looked up. */
  configDeclaration(node: any, scope: Scope): void {
    const inner = this.scoped(scope, "config", node.name, node, "config");
    this.program.located(node.name, scope);
    this.visitAll(node.localparams, inner);
    for (const rule of node.rules) {
      if (rule instanceof S.ConfigRule && rule.clause instanceof S.ConfigUse) this.visitAll(rule.clause.parameters, inner);
    }
  }

  checkerDeclaration(node: any, scope: Scope): void {
    const inner = this.scoped(scope, "checker", node.name, node, "checker");
    this.program.located(node.name, scope);
    for (const port of node.ports) {
      this.visitAll([...(port.type !== null ? [port.type] : []), ...port.dimensions,
        ...(port.value !== null ? [port.value] : [])], inner);
      this.program.located(port, inner);
      this.program.located(port.name, inner);
      this.entity(inner, "argument", port.name, port);
    }
    this.visitAll(node.items, inner);
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

  specparam(node: any, scope: Scope): void {
    this.visitAll(node.type !== null ? [node.type] : [], scope);
    for (const assignment of node.assignments) {
      this.visitAll([assignment.value, ...(assignment.limit !== null ? [assignment.limit] : [])], scope);
      this.program.located(assignment, scope);
      this.program.located(assignment.name, scope);
      this.entity(scope, "specparam", assignment.name, assignment);
    }
  }

  gateInstantiation(node: any, scope: Scope): void {
    if (node.primitive !== null) this.program.located(node.primitive, scope);
    this.visitAll([node.strength, node.delay].filter((p) => p !== null), scope);
    for (const instance of node.instances) {
      this.program.located(instance, scope);
      this.visitAll([...instance.dimensions, ...instance.terminals], scope);
      if (instance.name !== null) {
        this.program.located(instance.name, scope);
        this.entity(scope, "instance", instance.name, instance);
      }
    }
  }

  /** A primitive has a scope where its ports are: one entity each, which its header and its declarations name. */
  udpDeclaration(node: any, scope: Scope): void {
    if (node.extern === true) { // a header alone: the primitive of its name declares
      this.locate(node, scope);
      return;
    }
    const inner = this.scoped(scope, "primitive", node.name, node, "primitive", ".");
    this.program.located(node.name, scope);
    let ports = node.ports;
    if (ports.some((p: any) => p instanceof S.WildcardPort)) { // `.*`: the extern's ports, or the declarations' alone
      for (const port of ports) this.program.located(port, inner);
      ports = this.externs.get(node.name.spelling)?.ports ?? [];
    }
    for (const port of [...ports, ...node.declarations]) {
      this.program.located(port, inner);
      if (port instanceof S.Identifier) { // a non-ANSI header's name
        this.entity(inner, "port", port, port);
        continue;
      }
      if (port.value !== null) this.visit(port.value, inner);
      for (const name of port.names) {
        this.program.located(name, inner);
        if (port.direction !== null) this.entity(inner, "port", name, port); // `reg q;` names an output again
      }
    }
    if (node.initial !== null) this.locate(node.initial, inner);
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

  /** `if (x matches .v) body`: a pattern's variables are seen by the condition and the consequence. */
  ifStatement(node: any, scope: Scope): void {
    const inner = this.patternVariables(node.condition, scope);
    this.visitAll([node.condition, node.consequence], inner);
    if (node.alternative !== null) this.visit(node.alternative, scope);
  }

  conditional(node: any, scope: Scope): void {
    const inner = this.patternVariables(node.condition, scope);
    this.visitAll([node.condition, ...node.attributes, node.consequence], inner);
    this.visit(node.alternative, scope);
  }

  patternCaseItem(node: any, scope: Scope): void {
    const inner = this.patternVariables(node.pattern, scope);
    this.visitAll([node.pattern, ...(node.guard !== null ? [node.guard] : []), node.body], inner);
  }

  /** A block scope where the variables of `node`'s patterns are declared, or `scope` when it has none. */
  patternVariables(node: any, scope: Scope): Scope {
    const variables = [...walk(node)].filter((n) => n instanceof S.VariablePattern) as S.VariablePattern[];
    if (variables.length === 0) return scope;
    const inner = new Scope("block", null, scope, node);
    for (const variable of variables) {
      this.program.located(variable.name, inner);
      this.entity(inner, "variable", variable.name, variable);
    }
    return inner;
  }

  foreach(node: any, scope: Scope): void {
    this.visit(node.array, scope);
    const inner = new Scope("block", null, scope, node);
    for (const variable of node.variables) {
      this.program.located(variable, inner);
      if (variable instanceof S.Identifier) this.entity(inner, "variable", variable, node); // not a dimension it skips
    }
    this.visit(node.body, inner);
  }

  /** A conditional's branches; its macros' names are not the program's. */
  ifdef(node: any, scope: Scope): void {
    for (const branch of node.branches) this.program.located(branch, scope);
    this.visitAll([...node.items, ...node.alternative, ...node.branches.flatMap((b: any) => b.items)], scope);
  }

  /** `bus.t`: `bus` is found where the name is; `t`, in the interface, is not. */
  dpiImport(node: any, scope: Scope): void {
    this.visit(node.prototype, scope); // its C name is not looked up
  }

  dpiExport(node: any, scope: Scope): void {
    this.program.located(node.name, scope);
  }

  /** `bind target ...`: the target is found where the directive is; its instances and connections, once the target is
   * known, in the target. */
  bind(node: any, scope: Scope): void {
    this.visit(node.target, scope);
    this.binds.push([scope, node]);
  }

  resolveBinds(): void {
    for (const [scope, node] of this.binds) {
      const targets = referents(this.program, node.target).filter((e) => e.scope !== null);
      const inner = targets.length > 0 ? targets[0]?.scope as Scope : scope;
      for (const part of [...node.instances, node.instantiation]) this.locate(part as SyntaxNode, inner);
    }
  }

  interfaceType(node: any, scope: Scope): void {
    this.program.located(node.interface, scope);
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
  [[S.ExplicitPort, S.ExplicitAnsiPort], (d, n, s) => d.explicitPort(n, s)],
  [[S.IfdefDirective], (d, n, s) => d.ifdef(n, s)],
  [[S.InterfaceTypeName], (d, n, s) => d.interfaceType(n, s)],
  [[S.DpiImport], (d, n, s) => d.dpiImport(n, s)],
  [[S.RandSequenceStatement], (d, n, s) => d.randsequence(n, s)],
  [[S.CheckerDeclaration], (d, n, s) => d.checkerDeclaration(n, s)],
  [[S.ConfigDeclaration], (d, n, s) => d.configDeclaration(n, s)],
  [[S.ExportDeclaration], () => undefined], // what a package exports is not followed: its names are not looked up
  [[S.IfStatement], (d, n, s) => d.ifStatement(n, s)],
  [[S.ConditionalExpression], (d, n, s) => d.conditional(n, s)],
  [[S.PatternCaseItem], (d, n, s) => d.patternCaseItem(n, s)],
  [[S.VariablePattern], () => undefined], // declared where its pattern's variables are
  [[S.GateInstantiation], (d, n, s) => d.gateInstantiation(n, s)],
  [[S.UdpDeclaration], (d, n, s) => d.udpDeclaration(n, s)],
  [[S.SpecparamDeclaration], (d, n, s) => d.specparam(n, s)],
  [[S.DpiExport], (d, n, s) => d.dpiExport(n, s)],
  [[S.BindDirective], (d, n, s) => d.bind(n, s)],
  [[S.NetDeclaration], (d, n, s) => d.declarators(n, s, "net")],
  [[S.VariableDeclaration], (d, n, s) => d.declarators(n, s, "variable")],
  [[S.PortDeclaration], (d, n, s) => d.declarators(n, s, "port")],
  [[S.TypedefDeclaration], (d, n, s) => d.typedef(n, s)],
  [[S.InterfacePortDeclaration], (d, n, s) => d.interfacePortDeclaration(n, s)],
  [[S.NetTypeDeclaration], (d, n, s) => d.netType(n, s)],
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
  [[S.CovergroupDeclaration], (d, n, s) => d.covergroup(n, s)],
  [[S.Coverpoint, S.CoverCross], (d, n, s) => d.coverpoint(n, s)],
  [[S.CoverageBins, S.BinsSelection], (d, n, s) => d.bins(n, s)],
  [[S.BinsValues, S.BinsExpression], (d, n, s) => d.binsFilter(n, s)],
];
for (const [kinds, method] of methods) for (const kind of kinds) Definer.METHODS.set(kind, method);

/** The entities a source text declares, in their scopes. */
export function define(unit: S.SourceText): Program {
  const definer = new Definer(unit);
  definer.program.located(unit, definer.root);
  for (const item of unit.items) definer.visit(item, definer.root);
  definer.resolveImports();
  definer.resolveBases();
  definer.resolveBinds();
  return definer.program;
}

/** The numbers of an enumeration's member `name[left:right]`, or of `name[left]` 0 to `left - 1`; none when they are not
 * decimal numbers. */
function numbers(left: any, right: any): number[] {
  const bounds = [left, right].filter((b) => b !== null)
    .map((b) => (b instanceof S.IntegerLiteral ? (b.spelling as string).replaceAll("_", "") : ""));
  if (!bounds.every((b) => /^[0-9]+$/.test(b))) return [];
  if (right === null) return Array.from({ length: Number(bounds[0]) }, (_, i) => i);
  const [first, last] = [Number(bounds[0]), Number(bounds[1])];
  const step = last >= first ? 1 : -1;
  return Array.from({ length: Math.abs(last - first) + 1 }, (_, i) => first + i * step);
}

/** The spelling of an identifier, or of a parameterized class's name. */
function spelling(name: any): string {
  return name instanceof S.ParameterizedName ? name.name?.spelling as string : name.spelling;
}

/** The entities a name finds from `scope`: an identifier or a parameterized class as lookup resolves it,
 * `p::c::x` as `x` in `c` in the package or class `p` that `p` resolves to, and `$unit::x` as `x` in the
 * compilation unit. */
function lookup(scope: Scope, name: any): Entity[] {
  if (!(name instanceof S.ScopedName)) return scope.resolve(spelling(name));
  if (name.scope instanceof S.UnitName) { // `$unit::x`: in the compilation unit
    while (scope.parent !== null) scope = scope.parent;
    return name.name instanceof S.ScopedName ? lookup(scope, name.name) : scope.lookup(spelling(name.name));
  }
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
