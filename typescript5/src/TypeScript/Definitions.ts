/**
 * Definitions: the names a TypeScript or JavaScript program declares, in the scopes ECMAScript and TypeScript give
 * them.
 *
 * `define(program)` reads a program and returns a `TypeScriptProgram`, a `Framework.Definitions.Program` whose
 * qualified names join with `.` (`Shapes.Point.area`). Its entities have these kinds:
 *
 * - 'variable' (`var`, `let`, `const`, `using`, and a `catch` clause's parameter), 'parameter' and 'function';
 * - 'class', with its members: 'method', 'property' (a parameter property included) and 'accessor' (`get`, `set` and
 *   `accessor`), private ones named with their `#`;
 * - 'interface', with its members 'method', 'property' and 'accessor'; 'type alias' and 'type parameter' (a mapped
 *   type's key and an `infer` binding included);
 * - 'enum' and 'enum member'; 'namespace' (`namespace A` and `module A`) and 'module' (`declare module "a"`);
 * - 'import': a name an import binds, `import a = b.c` included, whose `target` is what `b.c` names.
 *
 * Declarations of one name and kind in one scope are one entity: merged interfaces, namespaces and enums share their
 * scope, and a function's overloads, a `var` declared twice and an accessor's `get` and `set` are one entity. Its
 * `declarations` are in source order, and its `definition` is the first that is not an overload signature (a function
 * or a method without a body), if any.
 *
 * Scopes are 'module' (the program), 'function' (a function, an arrow function, a method or a signature: its type
 * parameters and parameters), 'block' (a block, a `for` statement, a `switch` statement's cases, a `catch` clause, a
 * named class expression), 'static block', 'class' and 'interface' (members, which lookup never finds unqualified),
 * 'enum', 'namespace', 'module' and 'type parameters' (of a generic class, interface or type alias, of a mapped type,
 * or the `infer` bindings of a conditional type). `var` binds in the nearest function, static block, namespace or
 * module; everything else in the nearest scope. `declare global { ... }` declares in the program's scope.
 *
 * A name has a meaning: TypeScript keeps values, types and namespaces apart, so one name can be a variable and an
 * interface at once. `TypeScriptProgram.space_of` tells which meaning a name has where it is written, and `referents`
 * finds only the entities with that meaning ('class', 'enum' and 'import' have every meaning).
 *
 * What it does not do: resolve properties (`a.b`, whose `b` depends on `a`'s value), a qualified name past its first
 * part, or the members of imported modules; follow `export *`, `with` statements, `eval` or globals that libraries
 * declare; or treat a lower-case JSX element (`<div>`) as anything but HTML.
 */

import { Entity, Program, Scope } from "../Framework/Definitions.js";
import { children, type SyntaxNode, walk } from "../Framework/Syntax.js";
import * as S from "./Syntax.js";

const meanings = (...spaces: string[]): ReadonlySet<string> => new Set(spaces);
/** The meanings each kind of entity has: what it can be named as. */
export const MEANINGS: Readonly<Record<string, ReadonlySet<string>>> = {
  variable: meanings("value"), parameter: meanings("value"), function: meanings("value"),
  "enum member": meanings("value"), class: meanings("value", "type", "namespace"),
  enum: meanings("value", "type", "namespace"), import: meanings("value", "type", "namespace"),
  namespace: meanings("value", "namespace"), module: meanings("namespace"), interface: meanings("type"),
  "type alias": meanings("type"), "type parameter": meanings("type"), method: meanings("value"),
  property: meanings("value"), accessor: meanings("value"),
};
/** Kinds of the names that are not located when they name a property, a member or a label. */
const NAMES: Function[] = [S.Identifier, S.PrivateIdentifier, S.JSXIdentifier];
/** Scopes where `var` binds. */
const VAR_SCOPES = new Set(["module", "function", "static block", "namespace"]);
/** Kinds whose syntax nodes open a scope of types. */
const TYPES: Function[] = [S.TypeNode, S.TSTypeAnnotation, S.TSTypeParameterInstantiation, S.TSInterfaceHeritage,
  S.TSClassImplements];

const is = (kinds: Function[], node: unknown): boolean => kinds.some((k) => node instanceof k);

/** What a program declares, and for each name written in it the meaning it has there. */
export class TypeScriptProgram extends Program {
  private readonly spaces = new Map<unknown, string>();

  /** Records that the name `node` is written as a `space`: 'value', 'type' or 'namespace'. */
  means(node: unknown, space: string): void {
    this.spaces.set(node, space);
  }

  /** The meaning the name `node` has where it is written: 'value', 'type' or 'namespace'; null for a name that
   * declares, or that names something of any meaning (an export's). */
  space_of(node: unknown): string | null {
    return this.spaces.get(node) ?? null;
  }
}

type Handler = (self: Definer, node: any, scope: Scope, space: string) => void;

/** Declares what a program binds, visiting each syntax node with its scope and the meaning a name has there. */
class Definer {
  static HANDLERS = new Map<Function, Handler>();
  readonly program: TypeScriptProgram;
  readonly imports: [Entity, any, Scope][] = [];

  constructor(program: S.Program) {
    this.program = new TypeScriptProgram(new Scope("module", null, null, program, "."));
  }

  // Scopes and bindings

  /** The scope where a `var` in `scope` binds. */
  static varScope(scope: Scope): Scope {
    while (!VAR_SCOPES.has(scope.kind)) scope = scope.parent as Scope;
    return scope;
  }

  /** The entity of `kind` named `name` in `scope`, a new one if there is none, with `node` declaring it. */
  declare(scope: Scope, name: string, node: unknown, kind: string): Entity {
    const found = (scope.names.get(name) ?? []).find((e) => e.kind === kind);
    const entity = found ?? scope.declare(this.program.add(new Entity(kind, name, scope)));
    entity.declarations.push(node);
    this.program.declares(node, entity);
    return entity;
  }

  /** Binds `identifier` in `scope`, `node` declaring it. */
  bind(scope: Scope, identifier: any, node: unknown, kind: string): Entity {
    const entity = this.declare(scope, identifier.name, node, kind);
    this.program.declares(identifier, entity);
    this.program.located(identifier, scope);
    return entity;
  }

  /** Binds `identifier` in `scope` as an entity with members, and the scope of its members: the one an earlier
   * declaration of it opened, or a new one of the kind `opens`. */
  owner(scope: Scope, identifier: any, node: unknown, kind: string, opens: string): Scope {
    const entity = this.bind(scope, identifier, node, kind);
    entity.scope ??= new Scope(opens, entity, scope, node);
    return entity.scope;
  }

  /** A binding pattern: its names bind in `scope` as `kind`; its defaults, computed keys and annotations are in `inner`
   * (by default `scope`). */
  target(node: any, scope: Scope, kind: string, inner: Scope = scope): void {
    this.program.located(node, inner);
    if (node instanceof S.Elision) return;
    if (node instanceof S.Identifier) {
      if (node.name !== "this") this.bind(scope, node, node, kind); // `this: T` declares the type of `this`
      this.visitAll(node.decorators, inner, "value");
      this.visitAll([node.typeAnnotation], inner, "type");
      return;
    }
    if (node instanceof S.TSParameterProperty) {
      this.visitAll(node.decorators, inner, "value");
      this.target(node.parameter, scope, kind, inner);
      return;
    }
    this.visitAll(node.decorators, inner, "value");
    this.visitAll([node.typeAnnotation], inner, "type");
    if (node instanceof S.ArrayPattern) {
      for (const element of node.elements) this.target(element, scope, kind, inner);
    } else if (node instanceof S.ObjectPattern) {
      for (const item of node.properties) {
        this.program.located(item, inner);
        if (item instanceof S.Property) {
          if (item.computed) this.visit(item.key, inner, "value");
          this.target(item.value, scope, kind, inner);
        } else {
          this.target(item, scope, kind, inner);
        }
      }
    } else if (node instanceof S.AssignmentPattern) {
      this.target(node.left, scope, kind, inner);
      this.visit(node.right, inner, "value");
    } else { // a RestElement
      this.target(node.argument, scope, kind, inner);
      this.visitAll([node.value], inner, "value");
    }
  }

  /** Binds type parameters in `scope`, their constraints and defaults there too. */
  typeParameters(parameters: S.TSTypeParameterDeclaration | null, scope: Scope): void {
    if (parameters === null) return;
    this.program.located(parameters, scope);
    for (const parameter of parameters.params) this.typeParameter(parameter, scope);
  }

  typeParameter(parameter: S.TSTypeParameter, scope: Scope): void {
    this.program.located(parameter, scope);
    this.bind(scope, parameter.name, parameter, "type parameter");
    this.visitAll([parameter.constraint, parameter.default], scope, "type");
  }

  /** The scope of a generic class's, interface's or type alias's type parameters; `scope` if it has none. */
  generic(node: any, scope: Scope): Scope {
    if (node.typeParameters === null) return scope;
    const inner = new Scope("type parameters", null, scope, node);
    this.typeParameters(node.typeParameters, inner);
    return inner;
  }

  // Visiting

  visit(node: any, scope: Scope, space: string): void {
    if (is(TYPES, node) && !(node instanceof S.TSTypeQuery)) space = "type";
    this.program.located(node, scope);
    const method = Definer.HANDLERS.get(node.constructor);
    if (method !== undefined) {
      method(this, node, scope, space);
      return;
    }
    for (const [, , child] of children(node)) this.visit(child, scope, space);
  }

  visitAll(nodes: readonly unknown[], scope: Scope, space: string): void {
    for (const node of nodes) if (node !== null) this.visit(node, scope, space);
  }

  statements(statements: readonly unknown[], scope: Scope): void {
    this.visitAll(statements, scope, "value");
  }

  /** The meaning of `a` in `a.b` written as a `space`. */
  static qualifier(space: string): string {
    return space === "value" ? "value" : "namespace";
  }

  /** An interface member, or a member of an object type: its key, if computed, and its type. */
  keyed(node: any, scope: Scope): void {
    if (node.computed) this.visit(node.key, scope, "value");
    if (node instanceof S.TSMethodSignature) {
      this.signature(node, new Scope("function", null, scope, node));
    }
    else this.visitAll([node.typeAnnotation], scope, "type");
  }

  /** An element's name: `Component` and the `a` of `a.b` name values; `div` and `svg:path` name HTML. */
  jsxName(node: any, scope: Scope): void {
    let root = node;
    while (root instanceof S.JSXMemberExpression) root = root.object;
    if (root instanceof S.JSXIdentifier && (root !== node || !/^\p{Lowercase}/u.test(root.name as string))) {
      this.program.located(root, scope);
      this.program.means(root, "value");
    }
  }

  // Declarations

  /** A function, an arrow function or a method's value: its scope, holding its type parameters and parameters, and
   * its body. */
  function(node: any, scope: Scope, entity: Entity | null = null): void {
    const inner = new Scope("function", entity, scope, node);
    const overload = is([S.TSDeclareFunction, S.TSEmptyBodyFunctionExpression], node);
    if (entity !== null && (entity.scope === null || !overload)) {
      entity.scope = inner; // an overloaded function's scope is its implementation's
    }
    if (node instanceof S.FunctionExpression && node.id !== null) {
      this.bind(inner, node.id, node, "function"); // a function expression's name is its own
    }
    this.signature(node, inner);
    const body = node.body ?? null;
    if (body instanceof S.BlockStatement) {
      this.program.located(body, inner);
      this.statements(body.body, inner);
    } else if (body !== null) {
      this.visit(body, inner, "value");
    }
  }

  /** A signature's type parameters, parameters and return type, which bind and are in `inner`. */
  signature(node: any, inner: Scope): void {
    this.typeParameters(node.typeParameters, inner);
    for (const parameter of node.params) this.target(parameter, inner, "parameter");
    this.visitAll([node.returnType], inner, "type");
  }

  classLike(node: S.ClassDeclaration | S.ClassExpression, scope: Scope): void {
    this.visitAll(node.decorators, scope, "value");
    let outer = scope;
    if (node instanceof S.ClassExpression && node.id !== null) { // its name is its own
      outer = new Scope("block", null, scope, node);
    }
    const entity = node.id === null ? null : this.bind(outer, node.id, node, "class");
    const heritage = this.generic(node, outer);
    const members = entity?.scope ?? new Scope("class", entity, heritage, node);
    if (entity !== null) entity.scope = members;
    this.visitAll([node.superClass], heritage, "value");
    this.visitAll([node.superTypeArguments, ...node.implements], heritage, "type");
    const body = node.body as S.ClassBody;
    this.program.located(body, members);
    for (const element of body.body) this.element(element, members, heritage);
  }

  /** A class member: it is declared in `members`; its decorators, computed key and value are in `scope`. */
  element(node: any, members: Scope, scope: Scope): void {
    this.program.located(node, members);
    if (node instanceof S.StaticBlock) {
      this.statements(node.body, new Scope("static block", null, scope, node));
      return;
    }
    if (node instanceof S.Comment || node instanceof S.TSIndexSignature) {
      this.visit(node, scope, "value");
      return;
    }
    this.visitAll(node.decorators, scope, "value");
    if (node.computed) this.visit(node.key, scope, "value");
    if (node instanceof S.MethodDefinition || node instanceof S.TSAbstractMethodDefinition) {
      const kind = node.methodKind === "get" || node.methodKind === "set" ? "accessor" : "method";
      const entity = this.declareMember(node, members, kind);
      this.program.located(node.value, scope);
      this.function(node.value, scope, entity);
      for (const parameter of (node.value as any).params) {
        if (parameter instanceof S.TSParameterProperty) {
          let name: any = parameter.parameter;
          if (name instanceof S.AssignmentPattern) name = name.left;
          this.declare(members, name.name, parameter, "property");
        }
      }
      return;
    }
    const kind = is([S.AccessorProperty, S.TSAbstractAccessorProperty], node) ? "accessor" : "property";
    this.declareMember(node, members, kind);
    this.visitAll([node.typeAnnotation], scope, "type");
    this.visitAll([node.value], scope, "value");
  }

  /** Declares a member named by its key; null for a computed key, which names no member. */
  declareMember(node: any, members: Scope, kind: string): Entity | null {
    const name = Definer.keyName(node.key, node.computed);
    if (name === null) return null;
    const entity = this.declare(members, name, node, kind);
    if (node.key instanceof S.Identifier || node.key instanceof S.PrivateIdentifier) {
      this.program.declares(node.key, entity);
      this.program.located(node.key, members);
    }
    return entity;
  }

  /** The name a key gives: an identifier's, `#` and a private name's, a string's or a number's value as written; null
   * for a computed key. */
  static keyName(key: any, computed: boolean): string | null {
    if (computed) return null;
    if (key instanceof S.Identifier) return key.name as string;
    if (key instanceof S.PrivateIdentifier) return "#" + key.name;
    const raw = key.raw as string;
    return raw.startsWith("'") || raw.startsWith('"') ? raw.slice(1, -1) : raw;
  }

  module(node: S.TSModuleDeclaration, scope: Scope): void {
    const body = node.body as S.TSModuleBlock | null;
    if (node.moduleKind === "global") {
      this.statements((body as S.TSModuleBlock).body, this.program.root);
      return;
    }
    const names: any[] = [];
    let name: any = node.id;
    while (name instanceof S.TSQualifiedName) { // `namespace a.b.c` declares `a`, `a.b` and `a.b.c`
      names.unshift(name.right);
      this.program.located(name, scope);
      name = name.left;
    }
    names.unshift(name);
    let inner = scope;
    for (const identifier of names) {
      if (identifier instanceof S.Literal) {
        const entity = this.declare(inner, (identifier.raw as string).slice(1, -1), node, "module");
        this.program.declares(identifier, entity);
        this.program.located(identifier, inner);
        entity.scope ??= new Scope("module", entity, inner, node);
        inner = entity.scope;
      } else {
        inner = this.owner(inner, identifier, node, "namespace", "namespace");
      }
    }
    if (body !== null) {
      this.program.located(body, inner);
      this.statements(body.body, inner);
    }
  }
}

const D = Definer;
const unnamed: Handler = () => {}; // a label, a meta-property, an export's exported name: none names an entity
const fn: Handler = (self, node, scope) => self.function(node, scope);
const signatureType: Handler = (self, node, scope) => // a scope of its own
  self.signature(node, new Scope("function", null, scope, node));
const loop: Handler = (self, node, scope) => {
  const inner = new Scope("block", null, scope, node);
  for (const [, , child] of children(node)) self.visit(child, inner, "value");
};
/** `x as T`, `x satisfies T` or `<T>x`, where in `as const` the name `const` names nothing. */
const asserted: Handler = (self, node, scope) => {
  const annotation = node.typeAnnotation;
  const constant = annotation instanceof S.TSTypeReference && annotation.typeName instanceof S.Identifier
    && annotation.typeName.name === "const" && annotation.typeArguments === null;
  for (const [, , child] of children(node)) { // in source order
    if (child !== annotation) self.visit(child, scope, "value");
    else if (!constant) self.visit(child, scope, "type");
  }
};

Definer.HANDLERS = new Map<Function, Handler>([
  [S.Identifier, (self, node, scope, space) => {
    self.program.means(node, space);
    self.visitAll(node.decorators, scope, "value");
    self.visitAll([node.typeAnnotation], scope, "type");
  }],
  [S.MemberExpression, (self, node, scope, space) => {
    self.visit(node.object, scope, D.qualifier(space));
    if (node.computed) self.visit(node.property, scope, "value"); // a property's name depends on the value
  }],
  [S.TSQualifiedName, (self, node, scope, space) => self.visit(node.left, scope, D.qualifier(space))],
  [S.TSTypeQuery, (self, node, scope) => {
    self.visit(node.exprName, scope, "value");
    self.visitAll([node.typeArguments], scope, "type");
  }],
  [S.TSImportType, (self, node, scope, space) => // its qualifier names the module's members
    self.visitAll([node.options, node.typeArguments], scope, space)],
  [S.Property, (self, node, scope) => {
    if (node.computed) self.visit(node.key, scope, "value");
    self.visit(node.value, scope, "value");
  }],
  [S.TSPropertySignature, (self, node, scope) => self.keyed(node, scope)],
  [S.TSMethodSignature, (self, node, scope) => self.keyed(node, scope)],
  [S.TSIndexSignature, (self, node, scope) => {
    for (const parameter of node.parameters) self.visitAll([parameter.typeAnnotation], scope, "type"); // names nothing
    self.visitAll([node.typeAnnotation], scope, "type");
  }],
  [S.MetaProperty, unnamed], [S.BreakStatement, unnamed], [S.ContinueStatement, unnamed],
  [S.ExportAllDeclaration, unnamed],
  [S.ExportSpecifier, (self, node, scope) => self.program.located(node.local, scope)], // whatever the name means
  [S.ExportNamedDeclaration, (self, node, scope) => {
    self.visitAll([node.declaration], scope, "value");
    if (node.source === null) self.visitAll(node.specifiers, scope, "value");
  }],
  [S.LabeledStatement, (self, node, scope) => self.visit(node.body, scope, "value")],
  [S.JSXOpeningElement, (self, node, scope) => {
    self.jsxName(node.name, scope);
    self.visitAll([node.typeArguments, ...node.attributes], scope, "value");
  }],
  [S.JSXClosingElement, (self, node, scope) => self.jsxName(node.name, scope)],
  [S.JSXAttribute, (self, node, scope) => self.visitAll([node.value], scope, "value")],
  [S.VariableDeclaration, (self, node, scope) => {
    const binding = node.declarationKind === "var" ? D.varScope(scope) : scope;
    for (const declarator of node.declarations) {
      self.program.located(declarator, scope);
      self.target(declarator.id, binding, "variable", scope);
      self.visitAll([declarator.init], scope, "value");
    }
  }],
  [S.FunctionDeclaration, (self, node, scope) => self.function(node, scope,
    node.id === null ? null : self.bind(scope, node.id, node, "function"))],
  [S.TSDeclareFunction, (self, node, scope) => self.function(node, scope, self.bind(scope, node.id, node, "function"))],
  [S.FunctionExpression, fn], [S.ArrowFunctionExpression, fn], [S.TSEmptyBodyFunctionExpression, fn],
  [S.TSFunctionType, signatureType], [S.TSConstructorType, signatureType],
  [S.TSCallSignatureDeclaration, signatureType], [S.TSConstructSignatureDeclaration, signatureType],
  [S.ClassDeclaration, (self, node, scope) => self.classLike(node, scope)],
  [S.ClassExpression, (self, node, scope) => self.classLike(node, scope)],
  [S.TSInterfaceDeclaration, (self, node, scope) => {
    const members = self.owner(scope, node.id, node, "interface", "interface");
    const inner = self.generic(node, scope);
    self.visitAll(node.extends, inner, "type");
    self.program.located(node.body, members);
    for (const item of node.body.body) {
      self.program.located(item, members);
      if (item instanceof S.TSPropertySignature) {
        self.declareMember(item, members, "property");
      } else if (item instanceof S.TSMethodSignature) {
        const accessor = item.methodKind === "get" || item.methodKind === "set";
        self.declareMember(item, members, accessor ? "accessor" : "method");
      }
      self.visit(item, inner, "type");
    }
  }],
  [S.TSTypeAliasDeclaration, (self, node, scope) => {
    self.bind(scope, node.id, node, "type alias");
    self.visit(node.typeAnnotation, self.generic(node, scope), "type");
  }],
  [S.TSEnumDeclaration, (self, node, scope) => {
    const members = self.owner(scope, node.id, node, "enum", "enum");
    self.program.located(node.body, members);
    for (const item of node.body.members) {
      self.program.located(item, members);
      if (item instanceof S.Comment) continue;
      const name = D.keyName(item.id, item.computed);
      if (name === null) {
        self.visit(item.id, members, "value");
      } else {
        const entity = self.declare(members, name, item, "enum member");
        self.program.declares(item.id, entity);
        self.program.located(item.id, members);
      }
      self.visitAll([item.initializer], members, "value");
    }
  }],
  [S.TSModuleDeclaration, (self, node, scope) => self.module(node, scope)],
  [S.ImportDeclaration, (self, node, scope) => {
    for (const specifier of node.specifiers) {
      self.program.located(specifier, scope);
      self.bind(scope, specifier.local, specifier, "import");
    }
    self.visitAll(node.attributes, scope, "value");
  }],
  [S.TSImportEqualsDeclaration, (self, node, scope) => {
    const entity = self.bind(scope, node.id, node, "import");
    const reference = node.moduleReference;
    if (!(reference instanceof S.TSExternalModuleReference)) self.imports.push([entity, reference, scope]);
    self.visit(reference, scope, "namespace");
  }],
  [S.BlockStatement, (self, node, scope) => self.statements(node.body, new Scope("block", null, scope, node))],
  [S.ForStatement, loop], [S.ForInStatement, loop], [S.ForOfStatement, loop],
  [S.SwitchStatement, (self, node, scope) => {
    self.visit(node.discriminant, scope, "value");
    self.visitAll(node.cases, new Scope("block", null, scope, node), "value");
  }],
  [S.CatchClause, (self, node, scope) => {
    const inner = new Scope("block", null, scope, node);
    if (node.param !== null) self.target(node.param, inner, "variable");
    self.program.located(node.body, inner);
    self.statements(node.body.body, inner);
  }],
  [S.TSMappedType, (self, node, scope) => {
    self.visit(node.constraint, scope, "type");
    const inner = new Scope("type parameters", null, scope, node);
    self.bind(inner, node.key, node, "type parameter");
    self.visitAll([node.nameType, node.typeAnnotation], inner, "type");
  }],
  [S.TSConditionalType, (self, node, scope) => {
    self.visit(node.checkType, scope, "type");
    const inner = new Scope("type parameters", null, scope, node); // where `infer` binds, seen by the true branch
    self.visitAll([node.extendsType, node.trueType], inner, "type");
    self.visit(node.falseType, scope, "type");
  }],
  [S.TSInferType, (self, node, scope) => self.typeParameter(node.typeParameter, scope)],
  [S.TSAsExpression, asserted], [S.TSSatisfiesExpression, asserted], [S.TSTypeAssertion, asserted],
  [S.TSTypePredicate, (self, node, scope) => {
    self.visit(node.parameterName, scope, "value");
    self.visitAll([node.typeAnnotation], scope, "type");
  }],
  [S.TSNamedTupleMember, (self, node, scope) => self.visit(node.elementType, scope, "type")],
]);

/** Whether a declaration is an overload signature: a function or a method without a body. */
function signature(node: unknown): boolean {
  return is([S.TSDeclareFunction, S.TSAbstractMethodDefinition, S.TSMethodSignature, S.TSPropertySignature], node)
    || (node instanceof S.MethodDefinition && node.value instanceof S.TSEmptyBodyFunctionExpression);
}

/** The entities a program declares, in their scopes. */
export function define(program: S.Program): TypeScriptProgram {
  const definer = new Definer(program);
  const out = definer.program;
  out.located(program, out.root);
  definer.statements(program.body, out.root);
  for (const [entity, start, scope] of definer.imports) { // `import a = b.c`, once every namespace is declared
    const names: string[] = [];
    let reference = start;
    while (reference instanceof S.TSQualifiedName) {
      names.unshift((reference.right as S.Identifier).name as string);
      reference = reference.left;
    }
    let found = resolve(scope, reference.name, "namespace").filter((e) => e !== entity);
    for (const name of names) {
      const scopes = found.map((e) => e.resolved().scope).filter((s): s is Scope => s !== null);
      found = scopes.length > 0 ? (scopes[0] as Scope).lookup(name) : [];
    }
    entity.target = found[0] ?? null;
  }
  const stack: [SyntaxNode, Scope][] = [[program, out.root]];
  while (stack.length > 0) { // every other node is in its parent's scope, but for the names of properties and members
    const [node, scope] = stack.pop() as [SyntaxNode, Scope];
    const found = out.scope_of(node);
    if (found === null && !is(NAMES, node)) out.located(node, scope);
    stack.push(...children(node).map(([, , child]): [SyntaxNode, Scope] => [child, found ?? scope]));
  }
  const order = new Map<unknown, number>();
  let i = 0;
  for (const node of walk(program)) order.set(node, i++); // properties are in source order
  for (const entity of out.entities()) {
    entity.declarations.sort((a, b) => (order.get(a) as number) - (order.get(b) as number));
    entity.definition = entity.declarations.find((d) => !signature(d)) ?? null;
  }
  return out;
}

/** Unqualified lookup of `name` from `scope`, outwards, finding only entities with the meaning `space` (any, for
 * null). */
function resolve(scope: Scope | null, name: string, space: string | null): Entity[] {
  while (scope !== null) {
    const found = scope.lookup(name)
      .filter((e) => space === null || (MEANINGS[e.kind] as ReadonlySet<string>).has(space));
    if (found.length > 0) return found;
    scope = scope.parent;
  }
  return [];
}

/** The entities an `Identifier` (or a `JSXIdentifier`) of the program refers to, looked up from where it is, with the
 * meaning it has there. A property's name depends on a value, and a qualified name's later parts on its first, so they
 * find nothing. */
export function referents(program: TypeScriptProgram, name: S.Identifier | S.JSXIdentifier): Entity[] {
  const scope = program.scope_of(name);
  if (scope === null) return [];
  const entity = program.entity_of(name);
  return entity !== null ? [entity] : resolve(scope, name.name as string, program.space_of(name));
}
