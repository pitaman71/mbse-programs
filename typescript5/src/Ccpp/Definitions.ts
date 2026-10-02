/**
 * Definitions: the entities a C or C++ program declares, in the scopes the standard gives them.
 *
 * `define(unit)` reads a translation unit and returns a `Framework.Definitions.Program`. Its entities have these kinds:
 *
 * - 'namespace' (reopened namespaces are one entity) and 'namespace alias', whose `target` is the namespace;
 * - 'class' (also structs and unions), 'enumeration' and 'enumerator';
 * - 'function', one entity per signature, the types of its parameters as printed; a function's declarations and its
 *   definition are found by name and signature, also when the definition is out of line (`int A::f() { ... }`);
 * - 'variable', 'field' (a non-static data member), 'parameter' (of a function or lambda being defined) and
 *   'template parameter';
 * - 'type alias' (`typedef` and `using`), 'concept', 'label' and 'macro' (in `Program.macros`).
 *
 * Scopes have the kinds 'namespace' (also the global scope), 'class', 'enumeration', 'function', 'block', 'template',
 * 'lambda' and 'requires'. Inline and unnamed namespaces, unscoped enumerations and anonymous unions are transparent to
 * their enclosing scope, using-directives and `using enum` are followed, and a class looks names up in its bases.
 *
 * What it does not do: evaluate preprocessing conditions (every branch's declarations are declared), tell explicit and
 * partial specializations from their primary template (they are its declarations), or declare what a friend
 * declaration declares.
 */

import { Entity, Program, Scope } from "../Framework/Definitions.js";
import { children, type SyntaxNode } from "../Framework/Syntax.js";
import * as S from "./Syntax.js";
import { Printer } from "./_Printer.js";

const PRINTER = new Printer();

/** The name a `Name` syntax node declares or refers to, as text: an identifier's spelling, a template's name without
 * its arguments, `operator+`, `operator int*`, `~Point`, or a qualified name's last part. */
export function name_of(name: SyntaxNode): string {
  if (name instanceof S.QualifiedName || name instanceof S.TemplateId) return name_of(name.name as SyntaxNode);
  if (name instanceof S.DestructorName) {
    return "~" + (name.type instanceof S.Name ? name_of(name.type) : PRINTER.text(name.type, 0));
  }
  return PRINTER.text(name, 0);
}

/** A copy of a declarator without its name, for printing the type it declares. */
function unnamed(declarator: any): any {
  if (declarator === null || declarator instanceof S.IdDeclarator) return null;
  const kind = declarator.kind();
  const made = new kind(Object.fromEntries(kind.PROPERTIES.map((f: { name: string }) =>
    [f.name, declarator.get(f.name)])));
  made.declarator = unnamed(declarator.declarator);
  return made;
}

/** A function's parameter types and qualifiers, as printed: `(int, const char*) const`. */
function signature(fn: S.FunctionDeclarator): string {
  const types = fn.parameters.map((p) => (p instanceof S.EllipsisParameter ? "..."
    : PRINTER.text(new S.TypeId({ specifiers: (p as S.ParameterDeclaration).specifiers,
      declarator: unnamed((p as S.ParameterDeclaration).declarator) }), 0)));
  return "(" + types.join(", ") + ")" + fn.qualifiers.map((q) => " " + q.keyword).join("")
    + (fn.ref_qualifier !== null ? " " + fn.ref_qualifier : "");
}

/** The names of a qualified name's qualifiers; null if one is a decltype or splice, which only types tell. */
function qualifiers(name: S.QualifiedName): string[] | null {
  const names = name.qualifiers.filter((q) => q instanceof S.Name).map((q) => name_of(q));
  return names.length === name.qualifiers.length ? names : null;
}

/** The entities a `Name` syntax node names, looked up from `scope`. Anything else, such as a decltype, names nothing
 * found by name. */
function resolve(name: SyntaxNode, scope: Scope): Entity[] {
  if (name instanceof S.QualifiedName) {
    const names = qualifiers(name);
    return names === null ? [] : scope.qualified([...names, name_of(name.name as SyntaxNode)], name.global_scope);
  }
  return scope.resolve(name_of(name));
}

function keywords(specifiers: readonly SyntaxNode[]): Set<string> {
  return new Set(specifiers.filter((s): s is S.DeclSpecifier => s instanceof S.DeclSpecifier).map((s) => s.keyword as string));
}

type Handler = (self: Definer, node: any, scope: Scope, lexical: Scope) => void;

/** Walks a tree, declaring entities into scopes and recording where every syntax node is. */
class Definer {
  static HANDLERS = new Map<Function, Handler>();
  readonly program: Program;

  constructor(unit: S.TranslationUnit) {
    this.program = new Program(new Scope("namespace", null, null, unit));
  }

  // Entities

  /** The entity of this kind, name and signature in `scope`, declared there if it is new, with `node` among its
   * declarations (and as its definition with `definition`, unless an earlier syntax node defines it). */
  entity(kind: string, name: string | null, scope: Scope, node: unknown, definition = false,
    sig: string | null = null): Entity {
    let found: Entity | undefined;
    if (name !== null && !["parameter", "template parameter", "label"].includes(kind)) {
      found = (scope.names.get(name) ?? []).find((e) => e.kind === kind && e.parent === scope && e.signature === sig);
    }
    if (found === undefined) {
      found = this.program.add(new Entity(kind, name, scope));
      found.signature = sig;
      scope.declare(found);
    }
    found.declarations.push(node);
    if (definition && found.definition === null) found.definition = node;
    this.program.declares(node, found);
    return found;
  }

  /** The entity's own scope, made the first time it is needed. */
  scopeFor(entity: Entity, kind: string, parent: Scope, node: unknown): Scope {
    entity.scope ??= new Scope(kind, entity, parent, node);
    return entity.scope;
  }

  /** Where a declarator's name is declared: `scope`, or for a qualified name the scope its qualifiers name. */
  target(name: SyntaxNode | null, scope: Scope): Scope {
    const names = name instanceof S.QualifiedName ? qualifiers(name) : null;
    if (names !== null && names.length > 0) {
      const found = scope.qualified(names, (name as S.QualifiedName).global_scope);
      const scopes = found.map((e) => e.resolved().scope).filter((s): s is Scope => s !== null);
      if (scopes.length > 0) return scopes[0] as Scope;
    }
    return scope;
  }

  // Traversal

  /** Records that `node` is in `scope`, then declares what it declares. `lexical` is where the scopes it opens are
   * nested, when that is not `scope`: a template's parameters enclose what the template declares. */
  visit(node: SyntaxNode, scope: Scope, lexical: Scope | null = null): void {
    this.program.located(node, scope);
    const handler = Definer.HANDLERS.get(node.constructor);
    if (handler !== undefined) handler(this, node, scope, lexical ?? scope);
    else this.visitChildren(node, scope);
  }

  visitChildren(node: SyntaxNode, scope: Scope): void {
    for (const [, , child] of children(node)) this.visit(child, scope);
  }

  visitAll(nodes: readonly (SyntaxNode | null)[], scope: Scope): void {
    for (const node of nodes) if (node !== null) this.visit(node, scope);
  }

  /** Declares a parameter that names itself, in `scope`. */
  parameter(node: SyntaxNode, scope: Scope, kind: string): void {
    const [named] = S.binding((node.get("declarator") ?? null) as S.Declarator | null);
    if (named instanceof S.IdDeclarator) {
      const entity = this.entity(kind, name_of(named.name as SyntaxNode), scope, node, true);
      this.program.declares(named, entity);
    }
  }

  block(node: S.CompoundStatement, scope: Scope): void {
    const inner = new Scope("block", null, scope, node);
    this.program.located(node, scope);
    for (const item of node.items) this.visit(item, inner);
  }

  declarator(node: S.InitDeclarator, words: Set<string>, scope: Scope): void {
    const [named, binder] = S.binding(node.declarator);
    if (named instanceof S.StructuredBindingDeclarator) {
      for (const binding of named.bindings) {
        const [inner] = S.binding(binding);
        const declared = name_of((inner as S.IdDeclarator).name as SyntaxNode);
        this.program.declares(binding, this.entity("variable", declared, scope, binding, true));
      }
      return;
    }
    if (named === null) return;
    const target = this.target(named.name, scope);
    const name = name_of(named.name as SyntaxNode);
    let entity: Entity;
    if (words.has("typedef")) {
      entity = this.entity("type alias", name, target, node, true);
    } else if (binder instanceof S.FunctionDeclarator) {
      entity = this.entity("function", name, target, node, false, signature(binder));
    } else {
      const inClass = target.kind === "class";
      let kind = inClass && !words.has("static") ? "field" : "variable";
      if (target !== scope) { // an out-of-line definition, without `static`: the member declared before
        kind = (target.names.get(name) ?? []).find((e) => e.kind === "field" || e.kind === "variable")?.kind ?? kind;
      }
      const declaresOnly = words.has("extern") || (inClass && kind === "variable" && !words.has("inline")
        && !words.has("constexpr"));
      entity = this.entity(kind, name, target, node, node.initializer !== null || !declaresOnly);
    }
    this.program.declares(named, entity);
  }

  /** A template template parameter's own parameters, which name nothing outside it. */
  templateParameters(node: S.TemplateTemplateParameter, scope: Scope): void {
    const inner = new Scope("template", null, scope, node);
    this.visitAll(node.parameters, inner);
    this.visitAll([node.requires, node.name, node.default], scope);
  }
}

const H = Definer.HANDLERS;

H.set(S.NamespaceDefinition, (self, node: S.NamespaceDefinition, scope) => {
  let current = scope;
  if (node.names.length === 0) { // every unnamed namespace of a scope is the same one, transparent to the scope
    let entity = current.transparent.find((s) => s.kind === "namespace" && s.owner !== null && s.owner.name === null)?.owner;
    if (entity === undefined || entity === null) {
      entity = self.entity("namespace", null, current, node);
      current.transparent.push(self.scopeFor(entity, "namespace", current, node));
    } else {
      entity.declarations.push(node);
      self.program.declares(node, entity);
    }
    current = entity.scope as Scope;
  }
  node.names.forEach((part, i) => {
    self.program.located(part, current);
    self.program.located(part.name, current);
    const entity = self.entity("namespace", (part.name as S.Identifier).spelling, current, node);
    const inner = self.scopeFor(entity, "namespace", current, node);
    if ((part.inline || (node.inline && i === node.names.length - 1)) && !current.transparent.includes(inner)) {
      current.transparent.push(inner);
    }
    current = inner;
  });
  self.visitAll(node.attributes, scope);
  self.visitAll(node.items, current);
});
H.set(S.NamespaceAliasDefinition, (self, node: S.NamespaceAliasDefinition, scope) => {
  const entity = self.entity("namespace alias", (node.name as S.Identifier).spelling, scope, node, true);
  entity.target = resolve(node.target as SyntaxNode, scope).find((e) => e.resolved().kind === "namespace") ?? null;
  self.visitChildren(node, scope);
});
H.set(S.UsingDirective, (self, node: S.UsingDirective, scope) => {
  for (const entity of resolve(node.name as SyntaxNode, scope)) {
    const target = entity.resolved().scope;
    if (target !== null && !scope.using.includes(target)) scope.using.push(target);
  }
  self.visitChildren(node, scope);
});
H.set(S.UsingDeclaration, (self, node: S.UsingDeclaration, scope) => {
  for (const declarator of node.declarators) {
    const found = resolve(declarator.name as SyntaxNode, scope);
    if (found.length > 0) {
      for (const entity of found) scope.declare(entity);
      self.program.declares(declarator, found[0] as Entity);
    } else {
      self.entity("using declaration", name_of(declarator.name as SyntaxNode), scope, declarator);
    }
  }
  self.visitChildren(node, scope);
});
H.set(S.UsingEnumDeclaration, (self, node: S.UsingEnumDeclaration, scope) => {
  for (const entity of resolve(node.type as SyntaxNode, scope)) {
    if (entity.kind === "enumeration" && entity.scope !== null && !scope.transparent.includes(entity.scope)) {
      scope.transparent.push(entity.scope);
    }
  }
  self.visitChildren(node, scope);
});
H.set(S.ClassSpecifier, (self, node: S.ClassSpecifier, scope, lexical) => {
  const name = node.name !== null ? name_of(node.name) : null;
  const target = self.target(node.name, scope);
  const entity = self.entity("class", name, target, node, node.body !== null);
  self.visitAll([...node.attributes, node.name], scope);
  if (node.body === null) return;
  const members = self.scopeFor(entity, "class", target === scope ? lexical : target, node);
  for (const base of node.bases) {
    self.visit(base, scope);
    for (const found of resolve(base.type as SyntaxNode, scope)) { // a decltype or a splice finds nothing
      const resolved = found.resolved();
      if (resolved.kind === "class" && resolved.scope !== null && !members.bases.includes(resolved.scope)) {
        members.bases.push(resolved.scope);
      }
    }
  }
  if (name === null && node.key === "union" && target === scope) scope.transparent.push(members); // its members are its scope's
  self.program.located(node.body, members);
  self.visitAll(node.body.items, members);
});
H.set(S.EnumSpecifier, (self, node: S.EnumSpecifier, scope) => {
  const name = node.name !== null ? name_of(node.name) : null;
  const target = self.target(node.name, scope);
  const entity = self.entity("enumeration", name, target, node, node.body !== null);
  self.visitAll([...node.attributes, node.name, node.base], scope);
  if (node.body === null) return;
  const members = self.scopeFor(entity, "enumeration", target, node);
  if (node.key === "enum" && !target.transparent.includes(members)) target.transparent.push(members);
  self.program.located(node.body, members);
  self.visitAll(node.body.enumerators, members);
});
H.set(S.Enumerator, (self, node: S.Enumerator, scope) => { // listed directly or in a directive's branch
  self.entity("enumerator", (node.name as S.Identifier).spelling, scope, node, true);
  self.visitChildren(node, scope);
});
H.set(S.SimpleDeclaration, (self, node: S.SimpleDeclaration, scope, lexical) => {
  const words = keywords(node.specifiers);
  for (const part of [...node.attributes, ...node.specifiers]) {
    if (words.has("friend") && part instanceof S.ClassSpecifier && part.body === null) {
      self.program.located(part, scope);
      self.visitChildren(part, scope);
    } else {
      self.visit(part, scope, lexical);
    }
  }
  for (const declarator of node.declarators) {
    if (!words.has("friend")) self.declarator(declarator, words, scope);
    self.visit(declarator, scope);
  }
});
H.set(S.FunctionDefinition, (self, node: S.FunctionDefinition, scope, lexical) => {
  for (const part of [...node.attributes, ...node.specifiers]) self.visit(part, scope, lexical);
  const [named, binder] = S.binding(node.declarator) as [S.IdDeclarator, S.Declarator | null];
  const target = self.target(named.name, scope);
  let entity: Entity | null = null;
  if (!keywords(node.specifiers).has("friend")) {
    entity = self.entity("function", name_of(named.name as SyntaxNode), target, node, true,
      binder instanceof S.FunctionDeclarator ? signature(binder) : null);
    self.program.declares(named, entity);
  }
  const inner = new Scope("function", entity, target === scope ? lexical : target, node);
  self.visit(node.declarator as SyntaxNode, scope);
  if (binder instanceof S.FunctionDeclarator) for (const p of binder.parameters) self.parameter(p, inner, "parameter");
  self.visitAll([...node.virt_specifiers, node.requires, ...node.contracts, ...node.initializers], inner);
  self.program.located(node.body, inner);
  if (node.body instanceof S.CompoundStatement) self.block(node.body, inner);
  else self.visitChildren(node.body as SyntaxNode, inner);
});
H.set(S.TemplateDeclaration, (self, node: S.TemplateDeclaration, scope, lexical) => {
  const parameters = new Scope("template", null, lexical, node);
  for (const parameter of node.parameters) {
    self.program.located(parameter, parameters);
    if (parameter instanceof S.TypeParameter || parameter instanceof S.TemplateTemplateParameter) {
      if (parameter.name !== null) self.entity("template parameter", parameter.name.spelling, parameters, parameter, true);
      if (parameter instanceof S.TemplateTemplateParameter) {
        self.templateParameters(parameter, parameters);
        continue;
      }
      self.visitChildren(parameter, parameters);
    } else {
      self.parameter(parameter, parameters, "template parameter");
      self.visitChildren(parameter, parameters);
    }
  }
  self.visitAll([node.requires], parameters);
  self.visit(node.declaration as SyntaxNode, scope, parameters);
  const inner = node.declaration;
  const candidates = inner instanceof S.SimpleDeclaration ? [...inner.declarators, ...inner.specifiers] : [inner];
  const declared = candidates.map((c) => self.program.entity_of(c)).find((e) => e !== null);
  if (declared !== undefined) self.program.declares(node, declared as Entity);
});
H.set(S.AliasDeclaration, (self, node: S.AliasDeclaration, scope) => {
  self.entity("type alias", (node.name as S.Identifier).spelling, scope, node, true);
  self.visitChildren(node, scope);
});
H.set(S.ConceptDefinition, (self, node: S.ConceptDefinition, scope, lexical) => {
  self.entity("concept", (node.name as S.Identifier).spelling, scope, node, true);
  self.visitChildren(node, lexical);
});
H.set(S.DefineDirective, (self, node: S.DefineDirective, scope) => {
  self.entity("macro", (node.name as S.Identifier).spelling, self.program.macros, node, true);
  self.visitChildren(node, scope);
});
H.set(S.CompoundStatement, (self, node: S.CompoundStatement, scope) => self.block(node, scope));
for (const kind of [S.IfStatement, S.SwitchStatement, S.WhileStatement, S.ForStatement, S.RangeForStatement]) {
  // the names its parts declare are local to the statement
  H.set(kind, (self, node, scope) => self.visitChildren(node, new Scope("block", null, scope, node)));
}
H.set(S.Handler, (self, node: S.Handler, scope) => {
  const inner = new Scope("block", null, scope, node);
  self.parameter(node.parameter as SyntaxNode, inner, "variable");
  self.visitChildren(node, inner);
});
H.set(S.LabeledStatement, (self, node: S.LabeledStatement, scope) => {
  let fn = scope;
  while (fn.parent !== null && fn.kind !== "function" && fn.kind !== "lambda") fn = fn.parent;
  self.entity("label", (node.label as S.Identifier).spelling, fn, node, true);
  self.visitChildren(node, scope);
});
H.set(S.LambdaExpression, (self, node: S.LambdaExpression, scope) => {
  const inner = new Scope("lambda", null, scope, node);
  for (const parameter of node.template_parameters) {
    if (parameter instanceof S.TypeParameter || parameter instanceof S.TemplateTemplateParameter) {
      if (parameter.name !== null) self.entity("template parameter", parameter.name.spelling, inner, parameter, true);
    } else {
      self.parameter(parameter, inner, "template parameter");
    }
  }
  for (const capture of node.captures) {
    if (capture instanceof S.InitCapture) self.entity("variable", (capture.name as S.Identifier).spelling, inner, capture, true);
  }
  if (node.declarator !== null) for (const p of node.declarator.parameters) self.parameter(p, inner, "parameter");
  self.visitAll([...node.captures, ...node.template_parameters, node.template_requires, ...node.attributes, node.declarator], inner);
  self.program.located(node.body, inner);
  self.block(node.body as S.CompoundStatement, inner);
});
H.set(S.MemberExpression, (self, node: S.MemberExpression, scope) => {
  // the member is found in the object's class, which only types tell, so its name has no scope; what it holds that is
  // found where the expression is (template arguments, qualifiers, the types of destructor and conversion names) is
  self.visit(node.object as SyntaxNode, scope);
  const name = node.member;
  if (name instanceof S.TemplateId) self.visitAll(name.arguments, scope);
  else if (!(name instanceof S.Identifier)) self.visitChildren(name as SyntaxNode, scope);
});
H.set(S.RequiresExpression, (self, node: S.RequiresExpression, scope) => {
  const inner = new Scope("requires", null, scope, node);
  for (const p of node.parameters) self.parameter(p, inner, "parameter");
  self.visitChildren(node, inner);
});

/** The entities a translation unit declares, in their scopes. */
export function define(unit: S.TranslationUnit): Program {
  const definer = new Definer(unit);
  definer.program.located(unit, definer.program.root);
  definer.visitAll(unit.items, definer.program.root);
  return definer.program;
}

/** The entities a `Name` syntax node of the program refers to, looked up from where it is. A member's name after `.` or
 * `->` depends on types, so it finds nothing. */
export function referents(program: Program, name: SyntaxNode): Entity[] {
  const scope = program.scope_of(name);
  return scope === null ? [] : resolve(name, scope);
}
