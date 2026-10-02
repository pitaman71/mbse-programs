/**
 * Definitions: what a program declares, organized by meaning rather than by syntax.
 *
 * A program declares entities (namespaces, classes, functions, variables, ...) in scopes. Each `Entity` records the
 * syntax nodes that declare it and the one that defines it; each `Scope` maps names to the entities declared in it and
 * knows where unqualified lookup goes next. A language builds a `Program` from its trees (for Ccpp,
 * `Ccpp.Definitions.define`), and every language's programs are read through these classes.
 *
 * Lookup follows what every language shares:
 *
 * - A scope finds a name among its own declarations, then in its *transparent* scopes, whose names are its own (C++
 *   inline and unnamed namespaces, unscoped enumerations, anonymous unions), then in its *bases* (a class's base
 *   classes).
 * - Unqualified lookup (`Scope.resolve`) tries a scope, then the scopes its using-directives name, then its parent,
 *   outwards to the global scope.
 * - Qualified lookup (`Scope.qualified`) resolves each qualifier to a scope, following aliases, then finds the last
 *   name in it.
 *
 * Entities are found by name only: choosing among overloads, and names that depend on types, are not resolved.
 */

/** Something a program declares. `kind` names what it is in its language ('namespace', 'class', 'function', ...);
 * `name` is null for an unnamed entity. `parent` is the scope it is declared in, and `scope` its own members, for an
 * entity that has them. `declarations` are the syntax nodes that declare it, in source order, and `definition` the one
 * that defines it, if any. `signature` tells overloaded functions apart, and `target` is what an alias names. */
export class Entity {
  scope: Scope | null = null;
  declarations: unknown[] = [];
  definition: unknown = null;
  signature: string | null = null;
  target: Entity | null = null;

  constructor(readonly kind: string, readonly name: string | null, readonly parent: Scope | null) {}

  /** The names of the entity and the named entities enclosing it, outermost first, joined by its scope's separator,
   * such as 'geo::v1::Point' or 'shapes.Point.area'. Unnamed entities are left out. */
  qualified_name(): string {
    const parts: string[] = [];
    for (let entity: Entity | null = this; entity !== null; entity = entity.parent?.owner ?? null) {
      if (entity.name !== null) parts.push(entity.name);
    }
    return parts.reverse().join(this.parent?.separator ?? "::");
  }

  /** The entity itself, or for an alias the entity it names, followed through aliases of aliases. */
  resolved(): Entity {
    let entity: Entity = this;
    const seen = new Set<Entity>();
    while (entity.target !== null && !seen.has(entity)) {
      seen.add(entity);
      entity = entity.target;
    }
    return entity;
  }

  toString(): string {
    return `<${this.kind} ${this.qualified_name() || "(unnamed)"}>`;
  }
}

/** A region of a program where names are declared: `kind` names it in its language ('namespace', 'class', 'block',
 * ...), `owner` is the entity whose members it holds (null for blocks and the global scope), `parent` the enclosing
 * scope, and `node` the syntax node that opens it. Qualified names join names with `separator`: by default the
 * parent's, and '::' without a parent. */
export class Scope {
  readonly names = new Map<string, Entity[]>();
  readonly transparent: Scope[] = [];
  readonly using: Scope[] = [];
  readonly bases: Scope[] = [];

  readonly separator: string;

  constructor(readonly kind: string, readonly owner: Entity | null, readonly parent: Scope | null,
    readonly node: unknown = null, separator: string | null = null) {
    this.separator = separator ?? parent?.separator ?? "::";
  }

  /** Makes `entity` found by `name` (by default its own) in this scope. */
  declare(entity: Entity, name: string | null = null): Entity {
    const key = name ?? entity.name;
    if (key !== null) {
      const found = this.names.get(key) ?? [];
      if (!found.includes(entity)) found.push(entity);
      this.names.set(key, found);
    }
    return entity;
  }

  /** The entities found by name in this scope itself, in the order they were first declared. */
  entities(): Entity[] {
    const out: Entity[] = [];
    for (const found of this.names.values()) for (const e of found) if (!out.includes(e)) out.push(e);
    return out;
  }

  /** The entities `name` names in this scope: its own, its transparent scopes', or failing those its bases'. */
  lookup(name: string): Entity[] {
    const found = this.own(name, new Set());
    if (found.length > 0) return found;
    for (const base of this.bases) {
      const inherited = base.lookup(name);
      if (inherited.length > 0) return inherited;
    }
    return [];
  }

  private own(name: string, seen: Set<Scope>): Entity[] {
    if (seen.has(this)) return [];
    seen.add(this);
    const found = [...(this.names.get(name) ?? [])];
    for (const scope of this.transparent) for (const e of scope.own(name, seen)) if (!found.includes(e)) found.push(e);
    return found;
  }

  /** Unqualified lookup: the entities `name` names here, in the namespaces this scope's using-directives name, or in
   * an enclosing scope, the nearest first. */
  resolve(name: string): Entity[] {
    for (let scope: Scope | null = this; scope !== null; scope = scope.parent) {
      const found = scope.lookup(name);
      for (const used of scope.using) for (const e of used.lookup(name)) if (!found.includes(e)) found.push(e);
      if (found.length > 0) return found;
    }
    return [];
  }

  /** Qualified lookup of `a::b::c` (`names` ['a', 'b', 'c']) from this scope, or from the global scope with
   * `fromGlobal`: each qualifier must name an entity with a scope, an alias of one included. */
  qualified(names: readonly string[], fromGlobal = false): Entity[] {
    if (names.length === 0) return [];
    let scope: Scope | null = fromGlobal ? this.root() : null;
    for (const name of names.slice(0, -1)) {
      const found = scope !== null ? scope.lookup(name) : this.resolve(name);
      const scopes = found.map((e) => e.resolved().scope).filter((s): s is Scope => s !== null);
      if (scopes.length === 0) return [];
      scope = scopes[0] as Scope;
    }
    const last = names[names.length - 1] as string;
    return scope !== null ? scope.lookup(last) : this.resolve(last);
  }

  root(): Scope {
    let scope: Scope = this;
    while (scope.parent !== null) scope = scope.parent;
    return scope;
  }

  toString(): string {
    const owner = this.owner !== null && this.owner.name !== null ? ` ${this.owner.qualified_name()}` : "";
    return `<${this.kind} scope${owner}>`;
  }
}

/** What a set of trees declares: the global scope, every entity, and for each syntax node the entity it declares and
 * the scope it is in. */
export class Program {
  readonly macros = new Scope("macros", null, null);
  private readonly all: Entity[] = [];
  private readonly declared = new Map<unknown, Entity>();
  private readonly scopes = new Map<unknown, Scope>();

  constructor(readonly root: Scope) {}

  /** Records a new entity. */
  add(entity: Entity): Entity {
    this.all.push(entity);
    return entity;
  }

  /** Records that `node` declares `entity`. */
  declares(node: unknown, entity: Entity): void {
    this.declared.set(node, entity);
  }

  /** Records that `node` is in `scope`. */
  located(node: unknown, scope: Scope): void {
    if (!this.scopes.has(node)) this.scopes.set(node, scope);
  }

  /** Every entity, in the order the program first declares them. */
  entities(): IterableIterator<Entity> {
    return this.all[Symbol.iterator]();
  }

  /** The entity `node` declares or defines; null if it declares none. */
  entity_of(node: unknown): Entity | null {
    return this.declared.get(node) ?? null;
  }

  /** The innermost scope `node` is in; null for a syntax node outside the program's trees. */
  scope_of(node: unknown): Scope | null {
    return this.scopes.get(node) ?? null;
  }

  /** The entities a name written as text names, such as 'std::vector' or '::main', where `at` is (by default, in the
   * global scope). Its parts are joined by the global scope's separator. */
  lookup(name: string, at: unknown = null): Entity[] {
    const scope = (at !== null ? this.scope_of(at) : null) ?? this.root;
    const parts = name.split(this.root.separator);
    if (parts[0] === "") return scope.qualified(parts.slice(1), true);
    return scope.qualified(parts);
  }
}
