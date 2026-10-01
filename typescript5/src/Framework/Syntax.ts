/**
 * Syntax: the protocols every language's abstract syntax trees implement, and the machinery that implements them.
 *
 * A language is a set of node kinds, grouped into categories (Expression, Statement, Declaration, ...). Every
 * language's trees are:
 *
 * - Plain in-memory objects. A kind is a class whose fields are declared once, in its static `SPEC`: natives
 *   (`text()`, `flag()`, `integer()`, or a `choice(...)` of strings) are attributes, and nodes or lists of nodes
 *   (`one(...)`, `optional(...)`, `many(...)`) are children. A kind's interface takes its fields' types from its spec
 *   (`interface K extends Fields<typeof KSpec> {}`). Nodes are mutable: a transpiler builds, reads and rewrites them
 *   directly.
 * - Serializable. Each kind has a meta-schema, an mbse-schemas reference object schema with the tag `kind` and one
 *   property per attribute, and a builder (`create()` / `clone()` / `update()`) that implements `Visitors.OfObject`,
 *   so `JSON`, `YAML` and `Plain` read and write trees. Children are entries of the adjacency `children`, to the
 *   relation `Children` (registered as 'Programs.Children' and shared by every language), which links a `parent` to a
 *   `child` with the child's `field` and, in a list, its `index`. Every kind also declares `parent`, the same relation
 *   seen from the child, which data never writes.
 * - Traversable through their fields alone: `children`, `walk`, `fold`, `same`, `copy`, `Parents`, `Visitor` and
 *   `Transformer` work for every language.
 * - Validatable: `Language.validate` reports missing fields, misplaced children, choices out of range and shared
 *   nodes.
 * - Standardized: each kind and feature records the standards that have it (`SINCE`, `FEATURES`), and a `Standard`
 *   (such as C++20) checks a tree against them, parses source text into trees and prints trees into source text.
 */

import { Errors, Proxies, Repr, Schemas } from "@mbse/schemas/Framework";
import type { Visitors } from "@mbse/schemas/Framework";

const { AttributeError, KeyError, LookupError, NotImplementedError, ValueError } = Errors;
const { repr, typeName } = Repr;
type Callback<V> = Visitors.Callback<V>;

export const CHILDREN = "Programs.Children";

/** A native value of a node: str, bool or int. */
export type Native = string | boolean | bigint;
type NativeToken = StringConstructor | BooleanConstructor | BigIntConstructor;
const NATIVES = new Map<NativeToken, string>([[String, "str"], [Boolean, "bool"], [BigInt, "int"]]);

function isNative(token: NativeToken, value: unknown): boolean {
  return typeof value === (token === String ? "string" : token === Boolean ? "boolean" : "bigint");
}

/** Where a feature exists, by language family ('C++', 'C'): the year of the first standard that has it, or [first,
 * last exclusive] for a feature a later standard removed. */
export type Availability = Readonly<Record<string, number | readonly [number, number]>>;

/** A kind's features: for each field, the values that make a feature of it (a choice, or `true`), each with where it
 * exists. */
export type Features = Readonly<Record<string, readonly (readonly [string | true, Availability])[]>>;

export function article(noun: string): string {
  return `${"aeiou".includes((noun[0] as string).toLowerCase()) ? "an" : "a"} ${noun}`;
}

interface HasProperty {
  property(name: string, callback: Callback<Visitors.OfProperty>): unknown;
}

function setNative(visitor: HasProperty, name: string, value: Native): void {
  visitor.property(name, (p) => p.value((a) => a.as_native((n) => n.set(value))));
}

// --- Fields ---

type Ctor<T> = abstract new (...args: any[]) => T;

/** How a kind's spec declares an attribute. */
export interface AttributeSpec<T = unknown, O extends boolean = boolean> {
  readonly field: "attribute";
  readonly native: NativeToken;
  readonly optional: O;
  readonly choices: readonly string[] | null;
  readonly type?: T;
}

/** How a kind's spec declares a child or a list of children. */
export interface ChildSpec<T = unknown, M extends boolean = boolean, O extends boolean = boolean> {
  readonly field: "child";
  readonly categories: () => readonly Ctor<unknown>[];
  readonly optional: O;
  readonly many: M;
  readonly type?: T;
}

export type FieldSpec = AttributeSpec | ChildSpec;
type Instances<A extends readonly Ctor<unknown>[]> = A[number] extends Ctor<infer T> ? T : never;

function attribute<T, O extends boolean>(native: NativeToken, optional: O, choices: readonly string[] | null) {
  return { field: "attribute", native, optional, choices } as AttributeSpec<T, O>;
}

function child<T, M extends boolean, O extends boolean>(categories: () => readonly Ctor<unknown>[], many: M,
  optional: O) {
  return { field: "child", categories, optional, many } as ChildSpec<T, M, O>;
}

/** A str attribute. */
export const text = () => attribute<string, false>(String, false, null);
/** A str attribute that may be absent. */
export const optionalText = () => attribute<string, true>(String, true, null);
/** A bool attribute: false unless set, and written only when true. */
export const flag = () => attribute<boolean, false>(Boolean, false, null);
/** An int attribute that may be absent. */
export const optionalInteger = () => attribute<bigint, true>(BigInt, true, null);
/** A str attribute limited to `choices`. */
export const choice = <const C extends readonly string[]>(...choices: C) =>
  attribute<C[number], false>(String, false, choices);
/** A str attribute limited to `choices`, that may be absent. */
export const optionalChoice = <const C extends readonly string[]>(...choices: C) =>
  attribute<C[number], true>(String, true, choices);
/** A child of one of `categories` (categories or kinds), given by a function because they may be declared later. */
export const one = <const A extends readonly Ctor<unknown>[]>(categories: () => A) =>
  child<Instances<A>, false, false>(categories, false, false);
/** A child of one of `categories`, that may be absent. */
export const optional = <const A extends readonly Ctor<unknown>[]>(categories: () => A) =>
  child<Instances<A>, false, true>(categories, false, true);
/** An ordered list of children of `categories`. */
export const many = <const A extends readonly Ctor<unknown>[]>(categories: () => A) =>
  child<Instances<A>, true, true>(categories, true, true);

type FieldType<S> = S extends ChildSpec<infer T, infer M, infer _O> ? (M extends true ? T[] : T | null)
  : S extends AttributeSpec<infer T, infer _O> ? (T extends boolean ? boolean : T | null) : never;

/** The fields a spec declares, typed: a kind's interface extends `Fields<typeof Spec>`. */
export type Fields<Spec> = { -readonly [K in keyof Spec]: FieldType<Spec[K]> };

/** A native field: `native` is String, Boolean or BigInt; a str attribute may be limited to `choices`. A bool is false
 * unless set, and is written only when true. */
export class Attribute {
  constructor(readonly name: string, readonly native: NativeToken, readonly optional = false,
    readonly choices: readonly string[] | null = null) {}

  describe(): Record<string, unknown> {
    const out: Record<string, unknown> = { name: this.name, type: NATIVES.get(this.native), optional: this.optional };
    if (this.choices !== null) out["choices"] = [...this.choices];
    return out;
  }
}

/** A field holding a node of one of `categories` (categories or kinds), or with `many` an ordered list of them. */
export class Child {
  constructor(readonly name: string, readonly categories: readonly Function[], readonly optional = false,
    readonly many = false) {}

  describe(): Record<string, unknown> {
    return { name: this.name, type: this.categories.map((c) => c.name), optional: this.optional, many: this.many };
  }
}

export type Field = Attribute | Child;

function fieldsOf(kind: NodeClass): Field[] {
  return Object.entries(kind.SPEC).map(([name, spec]) => (spec.field === "attribute"
    ? new Attribute(name, spec.native, spec.optional, spec.choices)
    : new Child(name, spec.categories() as unknown as Function[], spec.optional, spec.many)));
}

// --- Nodes ---

let nextIdentity = 0;

/** A kind or category: a class derived from `Node`. */
export type NodeClass = typeof Node;

function isUnset(value: unknown): boolean {
  return value === null || value === undefined || value === false || (Array.isArray(value) && value.length === 0);
}

function show(value: unknown): string {
  if (value instanceof Node) return value.toString();
  if (Array.isArray(value)) return `[${value.map(show).join(", ")}]`;
  return repr(value);
}

/**
 * Every language's nodes: kinds are leaf classes, and the classes between them and `Node` are categories.
 * `Language` sets `LANGUAGE`, `KIND`, `NAME`, `FIELDS` and `Schema` on each kind.
 *
 * `SINCE` is where a kind exists (by default, wherever its language exists). `FEATURES` maps a field to the values
 * that make a feature of it, each with where that feature exists: a choice or `true` for an attribute, `true` for a
 * child that is present or a list that is not empty. `EXTENSION` marks a kind no standard has, which every standard
 * accepts. `check()` and `features()` add a kind's own problems and features.
 */
export class Node implements Visitors.Visitable {
  static LANGUAGE: Language;
  static KIND: string;
  static NAME: string;
  static SPEC: Readonly<Record<string, FieldSpec>> = {};
  static FIELDS: readonly Field[] = [];
  static BY_NAME: ReadonlyMap<string, Field> = new Map();
  static Schema: Schemas.OfObject.Data;
  static SINCE: Availability | null = null;
  static FEATURES: Features = {};
  static EXTENSION = false;
  private readonly nodeIdentity = ++nextIdentity;

  /** A node of this kind, with the fields `values` gives; the others are null, false or empty. */
  constructor(values: object = {}) {
    const kind = this.constructor as NodeClass;
    if (!Object.prototype.hasOwnProperty.call(kind, "KIND")) throw new TypeError(`${kind.name} is not a kind of node`);
    const self = this as unknown as Record<string, unknown>;
    for (const field of kind.FIELDS) {
      self[field.name] = field instanceof Child && field.many ? []
        : field instanceof Attribute && field.native === Boolean ? false : null;
    }
    for (const [name, value] of Object.entries(values)) {
      const field = kind.BY_NAME.get(name);
      if (field === undefined) throw new TypeError(`${kind.KIND} has no field ${repr(name)}`);
      self[name] = field instanceof Child && field.many ? [...(value as Iterable<unknown>)] : value;
    }
  }

  /** The node's kind: its class. */
  kind(): NodeClass {
    return this.constructor as NodeClass;
  }

  /** A field's value. */
  field(name: string): unknown {
    return (this as unknown as Record<string, unknown>)[name];
  }

  /** The kind and the fields that are set: not null, false or an empty list. Python's `repr` of the node. */
  toString(): string {
    const shown = this.kind().FIELDS.filter((f) => !isUnset(this.field(f.name)))
      .map((f) => `${f.name}=${show(this.field(f.name))}`);
    return `${this.kind().KIND}(${shown.join(", ")})`;
  }

  // Visitors.Visitable

  identity(): unknown {
    return this.nodeIdentity;
  }

  schema_name(): string {
    return this.kind().NAME;
  }

  /** Nodes are reference objects, linked by their parents. */
  owner(): null {
    return null;
  }

  /** Writes the tag, the attributes that are set (a bool only when true), then one `children` entry per child, in
   * field order, with its field and, in a list, its index. */
  accept(visitor: Visitors.OfObject): void {
    setNative(visitor, "kind", this.kind().KIND);
    for (const field of this.kind().FIELDS) {
      const value = this.field(field.name);
      if (field instanceof Attribute && value !== null && value !== undefined && value !== false) {
        setNative(visitor, field.name, value as Native);
      }
    }
    for (const [name, index, node] of children(this)) writeChild(visitor, name, index, node);
  }

  // Hooks

  /** The kind's own problems, beyond those of its fields; none by default. */
  check(): string[] {
    return [];
  }

  /** The kind's own features, beyond those `FEATURES` declares, each with where it exists; none by default. */
  features(): [string, Availability][] {
    return [];
  }

  /** Where this node's kind exists, if its attributes do not change that: `SINCE`, or null for wherever its language
   * exists. */
  availability(): Availability | null {
    return this.kind().SINCE;
  }
}

/** A node's children in field order, each with its field and, in a list, its index. Empty slots are skipped. */
export function children(node: Node): [string, number | null, Node][] {
  const out: [string, number | null, Node][] = [];
  for (const field of node.kind().FIELDS) {
    if (!(field instanceof Child)) continue;
    const value = node.field(field.name);
    if (field.many) {
      ((value ?? []) as (Node | null)[]).forEach((c, i) => { if (c !== null) out.push([field.name, i, c]); });
    } else if (value !== null) {
      out.push([field.name, null, value as Node]);
    }
  }
  return out;
}

function writeChild(visitor: Visitors.OfObject, field: string, index: number | null, node: Node): void {
  visitor.adjacency("children", (a) => a.add((entry) => {
    entry.link("child", (k) => k.set(node));
    setNative(entry, "field", field);
    if (index !== null) setNative(entry, "index", BigInt(index));
  }));
}

// --- Builders: Visitors that build nodes ---

/** `Visitors.OfProperty`, `OfAny` and `OfNative` over one native value. */
class _Native implements Visitors.OfProperty, Visitors.OfAny, Visitors.OfNative {
  constructor(private readonly propertyName: string, private readonly native: NativeToken,
    private readonly read: () => unknown, private readonly write: (value: unknown) => void) {}

  name(): string {
    return this.propertyName;
  }

  has(): boolean {
    const value = this.read();
    return isNative(this.native, value) && value !== false;
  }

  get(): Native {
    if (!this.has()) throw new AttributeError(`property ${repr(this.propertyName)} is not set`);
    return this.read() as Native;
  }

  set(value: Native): _Native {
    if (!isNative(this.native, value)) {
      throw new TypeError(`expected ${NATIVES.get(this.native)}, got ${typeName(value)}`);
    }
    this.write(value);
    return this;
  }

  clear(): _Native {
    this.write(this.native === Boolean ? false : null);
    return this;
  }

  value(callback: Callback<Visitors.OfAny>): _Native {
    callback(this);
    return this;
  }

  as_native(callback: Callback<Visitors.OfNative>): _Native {
    callback(this);
    return this;
  }

  as_object(_callback: Callback<Visitors.OfObject>): _Native {
    throw new TypeError(`property ${repr(this.propertyName)} is native`);
  }

  as_union(_callback: Callback<Visitors.OfUnion>): _Native {
    throw new TypeError(`property ${repr(this.propertyName)} is native`);
  }

  as_intersection(_callback: Callback<Visitors.OfIntersection>): _Native {
    throw new TypeError(`property ${repr(this.propertyName)} is native`);
  }

  as_indexed(_callback: Callback<Visitors.OfIndexed>): _Native {
    throw new TypeError(`property ${repr(this.propertyName)} is native`);
  }
}

/** `Visitors.OfLink` over the one link a `Children` entry sets. */
class _Link implements Visitors.OfLink {
  constructor(private readonly entry: _Entry) {}

  name(): string {
    return this.entry.other;
  }

  target(callback: Callback<Visitors.Visitable>): _Link {
    if (this.entry.target === null) throw new ValueError(`link ${repr(this.entry.other)} is not set`);
    callback(this.entry.target as Visitors.Visitable);
    return this;
  }

  set(target: Visitors.Visitable): _Link {
    this.entry.target = target;
    return this;
  }
}

/** `Visitors.OfEntry` for one entry of `Children`, seen from the end that fills `me`: it sets the other link, the
 * child's `field` and its `index`. */
class _Entry implements Visitors.OfEntry {
  readonly other: string;

  constructor(me: string, public target: unknown = null, public fieldName: string | null = null,
    public index: bigint | null = null) {
    this.other = me === "parent" ? "child" : "parent";
  }

  private native(name: string): _Native {
    return name === "field"
      ? new _Native("field", String, () => this.fieldName, (value) => { this.fieldName = value as string | null; })
      : new _Native("index", BigInt, () => this.index, (value) => { this.index = value as bigint | null; });
  }

  links(callback: Callback<Visitors.OfLink>): _Entry {
    callback(new _Link(this));
    return this;
  }

  link(name: string, callback: Callback<Visitors.OfLink>): _Entry {
    if (name !== this.other) throw new KeyError(`${repr(name)} is not a link this entry can set`);
    callback(new _Link(this));
    return this;
  }

  properties(callback: Callback<Visitors.OfProperty>): _Entry {
    for (const name of ["field", "index"]) if (this.has(name)) callback(this.native(name));
    return this;
  }

  has(name: string): boolean {
    return (name === "field" && this.fieldName !== null) || (name === "index" && this.index !== null);
  }

  property(name: string, callback: Callback<Visitors.OfProperty>): _Entry {
    if (name !== "field" && name !== "index") throw new KeyError(`unknown property ${repr(name)}`);
    callback(this.native(name));
    return this;
  }

  clear(name: string): _Entry {
    if (name === "field") this.fieldName = null;
    if (name === "index") this.index = null;
    return this;
  }
}

/** `Visitors.OfAdjacency` over a node's `children`, or over `parent`, whose entries are ignored (the parents'
 * children imply them). */
class _Adjacency implements Visitors.OfAdjacency {
  constructor(private readonly adjacencyName: string, private readonly own: string,
    private readonly list: _Entry[] | null) {}

  name(): string {
    return this.adjacencyName;
  }

  me(): string {
    return this.own;
  }

  entries(callback: Callback<Visitors.OfEntry>): _Adjacency {
    for (const entry of [...(this.list ?? [])]) callback(entry);
    return this;
  }

  add(callback: Callback<Visitors.OfEntry>): _Adjacency {
    const entry = new _Entry(this.own);
    callback(entry);
    this.list?.push(entry);
    return this;
  }

  remove(entry: Visitors.OfEntry): _Adjacency {
    if (this.list !== null) this.list.splice(0, this.list.length, ...this.list.filter((e) => e !== entry));
    return this;
  }
}

/**
 * Shared by every kind's builder: `create()` / `clone()` / `update()` with the rules and messages of every builder,
 * and `Visitors.OfObject` over the tag `kind`, the kind's attributes and its `children` entries. None of them
 * validate. DSL: `.set(field, value)` sets an attribute, a child or a list of children, and `.add(field, child)`
 * appends to a list.
 */
export class Builder implements Visitors.OfObject {
  static KIND: NodeClass;
  private readonly source: Node | undefined;
  private values = new Map<string, unknown>();
  private list: _Entry[] = [];

  constructor(instance?: Node) {
    const kind = this.kindClass;
    if (instance !== undefined && instance !== null && instance.constructor !== kind) {
      throw new TypeError(`expected ${article(kind.KIND)} to build from, got ${typeName(instance)}`);
    }
    this.source = instance ?? undefined;
    if (this.source !== undefined) {
      for (const f of kind.FIELDS) if (f instanceof Attribute) this.values.set(f.name, this.source.field(f.name));
      this.list = children(this.source).map(([name, index, node]) =>
        new _Entry("parent", node, name, index === null ? null : BigInt(index)));
    }
  }

  private get kindClass(): NodeClass {
    return (this.constructor as typeof Builder).KIND;
  }

  // DSL

  private childField(name: string): Child {
    const field = this.kindClass.BY_NAME.get(name);
    if (!(field instanceof Child)) throw new KeyError(`${this.kindClass.KIND} has no child field ${repr(name)}`);
    return field;
  }

  set(name: string, value: unknown): this {
    if (this.kindClass.BY_NAME.get(name) instanceof Attribute) {
      this.values.set(name, value);
      return this;
    }
    const field = this.childField(name);
    this.list = this.list.filter((entry) => entry.fieldName !== name);
    if (field.many) {
      (value as Node[]).forEach((node, i) => this.list.push(new _Entry("parent", node, name, BigInt(i))));
    } else if (value !== null && value !== undefined) {
      this.list.push(new _Entry("parent", value, name));
    }
    return this;
  }

  add(name: string, node: Node): this {
    if (!this.childField(name).many) throw new TypeError(`${this.kindClass.KIND}.${name} holds one child; use set()`);
    const index = this.list.filter((entry) => entry.fieldName === name).length;
    this.list.push(new _Entry("parent", node, name, BigInt(index)));
    return this;
  }

  // Finalizing

  create(): any {
    if (this.source !== undefined) {
      throw new ValueError("create() is only valid without a source instance; use clone() or update()");
    }
    return this.make();
  }

  clone(): any {
    if (this.source === undefined) throw new ValueError("clone() is only valid with a source instance");
    return this.make();
  }

  update(): any {
    if (this.source === undefined) throw new ValueError("update() is only valid with a source instance");
    const made = this.make();
    for (const field of this.kindClass.FIELDS) {
      (this.source as unknown as Record<string, unknown>)[field.name] = made.field(field.name);
    }
    return this.source;
  }

  private make(): Node {
    const kind = this.kindClass;
    const values = new Map(this.values);
    const lists = new Map<string, _Entry[]>();
    for (const entry of this.list) {
      if (entry.target === null) throw new ValueError("link 'child' is not set");
      if (entry.fieldName === null) throw new ValueError("a child entry needs a field");
      const field = kind.BY_NAME.get(entry.fieldName);
      if (!(field instanceof Child)) {
        throw new ValueError(`${article(kind.KIND)} has no child field ${repr(entry.fieldName)}`);
      }
      if (!(entry.target instanceof Node)) throw new TypeError(`a child must be a node, got ${typeName(entry.target)}`);
      if (field.many) {
        lists.set(field.name, [...(lists.get(field.name) ?? []), entry]);
      } else if (entry.index !== null) {
        throw new ValueError(`${kind.KIND}.${field.name} holds one child, not a list`);
      } else if (values.has(field.name)) {
        throw new ValueError(`${kind.KIND}.${field.name} holds one child, got several`);
      } else {
        values.set(field.name, entry.target);
      }
    }
    for (const [name, entries] of lists) {
      const last = BigInt(entries.length);
      const key = (entry: _Entry) => entry.index ?? last;
      const ordered = entries.map((entry, i) => [entry, i] as const)
        .sort(([a, i], [b, j]) => (key(a) < key(b) ? -1 : key(a) > key(b) ? 1 : i - j));
      values.set(name, ordered.map(([entry]) => entry.target));
    }
    return new (kind as unknown as new (values: object) => Node)(Object.fromEntries(values));
  }

  // Visitors.OfObject

  private checkKind(kind: unknown): void {
    if (kind !== null && kind !== this.kindClass.KIND) {
      throw new ValueError(`expected kind ${repr(this.kindClass.KIND)}, got ${repr(kind)}`);
    }
  }

  private names(): string[] {
    return ["kind", ...this.kindClass.FIELDS.filter((f) => f instanceof Attribute).map((f) => f.name)];
  }

  private native(name: string): _Native {
    if (name === "kind") return new _Native("kind", String, () => this.kindClass.KIND, (kind) => this.checkKind(kind));
    const field = this.kindClass.BY_NAME.get(name) as Attribute;
    return new _Native(name, field.native, () => this.values.get(name) ?? null,
      (value) => { this.values.set(name, value); });
  }

  properties(callback: Callback<Visitors.OfProperty>): this {
    for (const name of this.names()) if (this.has(name)) callback(this.native(name));
    return this;
  }

  has(name: string): boolean {
    return this.names().includes(name) && this.native(name).has();
  }

  property(name: string, callback: Callback<Visitors.OfProperty>): this {
    if (!this.names().includes(name)) throw new KeyError(`unknown property ${repr(name)}`);
    callback(this.native(name));
    return this;
  }

  clear(name: string): this {
    if (name !== "kind" && this.names().includes(name)) this.native(name).clear();
    return this;
  }

  private parent(): boolean {
    return this.kindClass.FIELDS.some((f) => f instanceof Child);
  }

  adjacencies(callback: Callback<Visitors.OfAdjacency>): this {
    for (const name of this.parent() ? ["children", "parent"] : ["parent"]) this.adjacency(name, callback);
    return this;
  }

  adjacency(name: string, callback: Callback<Visitors.OfAdjacency>): this {
    if (name === "children" && this.parent()) callback(new _Adjacency("children", "parent", this.list));
    else if (name === "parent") callback(new _Adjacency("parent", "child", null));
    else throw new KeyError(`unknown adjacency ${repr(name)}`);
    return this;
  }

  /** Nodes hold no value objects, so there is nothing to identify. */
  identify(_value: Visitors.Visitable): this {
    return this;
  }
}

// --- Meta-schemas and the registry ---

function nativeProperty(name: string, native: NativeToken) {
  return (p: Schemas.OfProperty.Builder) => p.name(name).of((t) => t.as_native(native as Schemas.OfNative.Spec));
}

export const Children = new Schemas.OfRelation.Builder().links("parent", "child")
  .properties(nativeProperty("field", String), nativeProperty("index", BigInt)).unique("child").create();
Proxies.register(CHILDREN, Children);
const CHILDREN_ADJACENCY = (r: Schemas.OfAdjacency.Builder) => r.name("children").of(Children).me("parent");
const PARENT_ADJACENCY = (r: Schemas.OfAdjacency.Builder) => r.name("parent").of(Children).me("child");

/** A kind's meta-schema: the tag, one property per attribute, and the adjacencies `children` (if it has child fields)
 * and `parent`. */
function schemaOf(kind: NodeClass): Schemas.OfObject.Data {
  const attributes = kind.FIELDS.filter((f): f is Attribute => f instanceof Attribute)
    .map((f) => nativeProperty(f.name, f.native));
  const relations = kind.FIELDS.some((f) => f instanceof Child) ? [CHILDREN_ADJACENCY, PARENT_ADJACENCY]
    : [PARENT_ADJACENCY];
  return new Schemas.OfObject.Builder().ref().properties(nativeProperty("kind", String), ...attributes)
    .relations(...relations).create();
}

/** Builds a language's nodes from snapshots: `registry['Programs.Ccpp.Identifier'](instance)` returns a builder, as
 * `Plain.FromPlain` expects. `schema` and `name_of` look the meta-schemas up. */
export class Registry {
  private readonly schemas: Map<string, Schemas.OfObject.Data | Schemas.OfRelation.Data>;
  readonly [name: string]: unknown;

  constructor(schemas: ReadonlyMap<string, Schemas.OfObject.Data>, builders: ReadonlyMap<string, typeof Builder>) {
    this.schemas = new Map<string, Schemas.OfObject.Data | Schemas.OfRelation.Data>([...schemas, [CHILDREN, Children]]);
    for (const [name, builder] of builders) {
      (this as Record<string, unknown>)[name] = (instance?: Node) => new builder(instance);
    }
  }

  schema(name: string): Schemas.OfObject.Data {
    if (name === CHILDREN) throw new TypeError(`${repr(name)} is a relation; no relation builder is exposed`);
    const found = this.schemas.get(name);
    if (found === undefined) throw new AttributeError(`no schema registered as ${repr(name)}`);
    return found as Schemas.OfObject.Data;
  }

  name_of(schema: unknown): string {
    for (const [name, registered] of this.schemas) if (registered === schema) return name;
    throw new LookupError("schema is not registered");
  }

  /** The value a node holds in its attribute `name`. */
  member(instance: unknown, name: string): unknown {
    return (instance as Record<string, unknown>)[name];
  }
}

// --- Languages ---

/** The classes between a kind and `Node`, its category first. */
function ancestors(kind: Function): Function[] {
  const out: Function[] = [];
  for (let base = Object.getPrototypeOf(kind); base !== Node; base = Object.getPrototypeOf(base)) out.push(base);
  return out;
}

type BranchBuilder = Parameters<Parameters<Schemas.OfUnion.Builder["branches"]>[0]>[0];

/** A language declared by its kinds, from which it derives their fields, builders, meta-schemas (registered with
 * `Proxies` as 'Programs.<name>.<Kind>'), the union `Schema` of every kind, whose branches are named by the kinds,
 * and the registry `Builders`. `BASE` is where a kind exists unless it says otherwise. */
export class Language {
  readonly BASE: Availability;
  readonly classes: readonly NodeClass[];
  readonly Schema: Schemas.OfUnion.Data;
  readonly Builders: Registry;
  private readonly languageName: string;
  private readonly byKind = new Map<string, NodeClass>();
  private readonly byCategory = new Map<string, Function>();

  constructor(name: string, kinds: readonly NodeClass[], options: { base: Availability }) {
    this.languageName = name;
    this.BASE = options.base;
    this.classes = [...kinds];
    const schemas = new Map<string, Schemas.OfObject.Data>();
    const builders = new Map<string, typeof Builder>();
    for (const kind of kinds) {
      Object.assign(kind, { LANGUAGE: this, KIND: kind.name, NAME: `Programs.${name}.${kind.name}` });
      this.byKind.set(kind.KIND, kind);
      for (const base of ancestors(kind).reverse()) if (!this.byCategory.has(base.name)) this.byCategory.set(base.name, base);
    }
    for (const kind of kinds) { // fields refer to other kinds, so they are read once every kind is known
      const fields = fieldsOf(kind);
      Object.assign(kind, { FIELDS: fields, BY_NAME: new Map(fields.map((f) => [f.name, f])) });
      kind.Schema = schemaOf(kind);
      schemas.set(kind.NAME, kind.Schema);
      builders.set(kind.NAME, class extends Builder { static override KIND = kind; });
    }
    for (const [schemaName, schema] of schemas) Proxies.register(schemaName, schema);
    this.Schema = new Schemas.OfUnion.Builder().branches(
      ...kinds.map((kind) => (b: BranchBuilder) => b.name(kind.KIND).of(kind.Schema))).create();
    this.Builders = new Registry(schemas, builders);
  }

  name(): string {
    return this.languageName;
  }

  /** Every kind, by name, in declaration order. */
  kinds(): Map<string, NodeClass> {
    return new Map(this.byKind);
  }

  /** Every category, by name, in the order kinds first name them. */
  categories(): Map<string, Function> {
    return new Map(this.byCategory);
  }

  /** A builder for `kind`, or for `instance` of it. */
  builder(kind: string | NodeClass, instance?: Node): Builder {
    const name = typeof kind === "string" ? kind : kind.name;
    const found = this.byKind.get(name);
    if (found === undefined) throw new KeyError(`${this.languageName} has no kind ${repr(name)}`);
    return (this.Builders[found.NAME] as (instance?: Node) => Builder)(instance);
  }

  private isNode(value: unknown): value is Node {
    return value instanceof Node && this.classes.includes(value.kind());
  }

  /** The meta-schema of `node`'s kind: the root schema for its snapshots. */
  schema_of(node: unknown): Schemas.OfObject.Data {
    if (!this.isNode(node)) throw new TypeError(`not ${article(this.languageName)} node: ${show(node)}`);
    return node.kind().Schema;
  }

  toString(): string {
    return `<language ${this.languageName}>`;
  }

  /** The language as plain data: its categories, and each kind's category, availability, features and fields. Every
   * implementation describes a language identically. */
  grammar(): Record<string, unknown> {
    const since = (availability: Availability | null) => (availability === null ? null
      : Object.fromEntries(Object.entries(availability).map(([k, v]) => [k, Array.isArray(v) ? [...v] : v])));
    return {
      language: this.languageName,
      base: since(this.BASE),
      categories: [...this.byCategory].map(([n, c]) => ({ name: n, base: Object.getPrototypeOf(c).name })),
      kinds: this.classes.map((k) => ({
        kind: k.KIND, category: Object.getPrototypeOf(k).name, since: since(k.SINCE), extension: k.EXTENSION,
        features: Object.fromEntries(Object.entries(k.FEATURES).map(([f, values]) =>
          [f, Object.fromEntries(values.map(([v, a]) => [v === true ? "true" : v, since(a)]))])),
        fields: k.FIELDS.map((f) => f.describe()),
      })),
    };
  }

  // Checks

  /** Problems with the tree at `node`, each prefixed with the path to the node it concerns: required fields that are
   * missing, children of the wrong category, attributes of the wrong type or out of their choices, nodes that appear
   * twice, cycles, and each kind's own problems. */
  validate(node: unknown): string[] {
    const problems: string[] = [];
    const seen = new Map<Node, string>();
    const at = (path: string, problem: string) => (path ? `${path}: ${problem}` : problem);

    const visit = (item: unknown, path: string): void => {
      if (!this.isNode(item)) {
        problems.push(at(path, `not ${article(this.languageName)} node: ${show(item)}`));
        return;
      }
      if (seen.has(item)) {
        problems.push(at(path, `the node is also at ${seen.get(item) || "the root"}`));
        return;
      }
      seen.set(item, path);
      const kind = item.kind();
      for (const field of kind.FIELDS) {
        const value = item.field(field.name);
        if (field instanceof Attribute) {
          problems.push(...attributeProblems(kind, field, value).map((p) => at(path, p)));
          continue;
        }
        const where = path ? `${path}.${field.name}` : field.name;
        if (!field.many) {
          if (value === null || value === undefined) {
            if (!field.optional) problems.push(at(path, `${article(kind.KIND)} needs ${article(field.name)}`));
          } else if (placed(kind, field, value, where, problems)) {
            visit(value, where);
          }
          continue;
        }
        if (!Array.isArray(value)) {
          problems.push(at(path, `${kind.KIND}.${field.name} must be a list, got ${typeName(value)}`));
          continue;
        }
        value.forEach((child: unknown, i: number) => {
          if (child === null || child === undefined) problems.push(at(path, `${kind.KIND}.${field.name}[${i}] is empty`));
          else if (placed(kind, field, child, `${where}[${i}]`, problems)) visit(child, `${where}[${i}]`);
        });
      }
      problems.push(...item.check().map((p) => at(path, p)));
    };

    visit(node, "");
    return problems;
  }
}

function attributeProblems(kind: NodeClass, field: Attribute, value: unknown): string[] {
  if (value === null || value === undefined || (value === false && field.native === Boolean)) {
    return field.optional || field.native === Boolean ? [] : [`${article(kind.KIND)} needs ${article(field.name)}`];
  }
  if (!isNative(field.native, value)) {
    return [`${kind.KIND}.${field.name} must be ${article(NATIVES.get(field.native) as string)}, got ${typeName(value)}`];
  }
  if (field.choices !== null && !field.choices.includes(value as string)) {
    return [`${kind.KIND}.${field.name} cannot be ${repr(value)}`];
  }
  return [];
}

/** Whether `child` may fill `field`; if not, says why. */
function placed(kind: NodeClass, field: Child, child: unknown, where: string, problems: string[]): boolean {
  if (field.categories.some((c) => child instanceof c)) return true;
  const expected = field.categories.map((c) => article(c.name)).join(" or ");
  const got = child instanceof Node && Object.prototype.hasOwnProperty.call(child.kind(), "KIND")
    ? article(child.kind().KIND) : typeName(child);
  problems.push(`${where}: ${kind.KIND}.${field.name} must be ${expected}, got ${got}`);
  return false;
}

// --- Standards ---

/** A standard's usual name: 'C++20', 'C++98', 'C11'. */
export function label(family: string, year: number): string {
  return `${family}${String(year % 100).padStart(2, "0")}`;
}

/** Whether a field's value makes the feature `key`: true for a bool that is set, a child that is present or a list
 * that is not empty, a choice for an attribute equal to it. */
function uses(value: unknown, key: string | true): boolean {
  if (key === true) return !isUnset(value);
  return typeof value === "string" && value === key;
}

/** A standard of a language family, such as C++20 (`family` 'C++', `year` 2020): which kinds and features it has,
 * and how source text of it is parsed into trees and trees printed into it. Languages derive their standards from
 * this class and implement `parse` and `print`. */
export class Standard {
  constructor(readonly language: Language, readonly family: string, readonly year: number) {}

  name(): string {
    return label(this.family, this.year);
  }

  toString(): string {
    return `<standard ${this.name()}>`;
  }

  /** Whether this standard has a feature that exists where `availability` says. */
  has(availability: Availability): boolean {
    return this.missing(availability) === null;
  }

  /** Why this standard lacks a feature that exists where `availability` says, as a predicate; null if it has it. */
  private missing(availability: Availability): string | null {
    const span = availability[this.family];
    if (span === undefined) return `is not ${this.family}`;
    const [first, last] = typeof span === "number" ? [span, null] : span;
    if (this.year < first) return `needs ${label(this.family, first)}`;
    if (last !== null && this.year >= last) return `was removed in ${label(this.family, last)}`;
    return null;
  }

  /** The features of `node` itself that this standard lacks. */
  problems(node: Node): string[] {
    const kind = node.kind();
    if (kind.EXTENSION) return [];
    const found: string[] = [];
    const missing = this.missing(node.availability() ?? this.language.BASE);
    if (missing !== null) found.push(`${kind.KIND} ${missing}`);
    for (const [name, values] of Object.entries(kind.FEATURES)) {
      const value = node.field(name);
      for (const [key, availability] of values) {
        if (!uses(value, key)) continue;
        const absent = this.missing(availability);
        if (absent !== null) found.push(`${kind.KIND}.${name}${key === true ? "" : ` ${repr(key)}`} ${absent}`);
      }
    }
    for (const [feature, availability] of node.features()) {
      const absent = this.missing(availability);
      if (absent !== null) found.push(`${feature} ${absent}`);
    }
    return found;
  }

  /** The features of the tree at `node` that this standard lacks, each prefixed with the path to its node. */
  check(node: Node): string[] {
    const out: string[] = [];
    for (const [path, item] of paths(node)) out.push(...this.problems(item).map((p) => (path ? `${path}: ${p}` : p)));
    return out;
  }

  /** The tree of a source text of this standard. Throws `Errors.ParseError` for text that is not. */
  parse(_text: string): Node {
    throw new NotImplementedError(`${this.name()} has no parser`);
  }

  /** The source text of a tree, in this standard. Throws `Errors.PrintError` for a tree it cannot print. */
  print(_node: Node): string {
    throw new NotImplementedError(`${this.name()} has no printer`);
  }
}

// --- Traversal ---

/** Every node of the tree at `root`, each once, with its path, parents before their children. */
function* paths(root: Node): Generator<[string, Node]> {
  const seen = new Set<Node>();
  const stack: [string, Node][] = [["", root]];
  while (stack.length > 0) {
    const [path, node] = stack.pop() as [string, Node];
    if (seen.has(node)) continue;
    seen.add(node);
    yield [path, node];
    for (const [name, index, child] of children(node).reverse()) {
      const where = index === null ? name : `${name}[${index}]`;
      stack.push([path ? `${path}.${where}` : where, child]);
    }
  }
}

/** Every node reachable from `node`, each once, parents before their children and children in field order. Shared
 * nodes are visited once, and cycles end the walk rather than repeat it. */
export function* walk(node: Node): Generator<Node> {
  for (const [, item] of paths(node)) yield item;
}

/** Combines a tree bottom-up: `fn(node, results)` is called once per node, shared ones included, with the results for
 * its children in field order. Throws on cycles. */
export function fold<R>(node: Node, fn: (node: Node, results: R[]) => R): R {
  const memo = new Map<Node, R>();
  const active = new Set<Node>();
  const visit = (item: Node): R => {
    if (memo.has(item)) return memo.get(item) as R;
    if (active.has(item)) throw new ValueError("the tree contains a cycle");
    active.add(item);
    const results = children(item).map(([, , child]) => visit(child));
    active.delete(item);
    memo.set(item, fn(item, results));
    return memo.get(item) as R;
  };
  return visit(node);
}

/** Whether two trees have the same structure: co-traverses them, comparing kinds, attributes and children in order.
 * Sharing is not compared. */
export function same(a: unknown, b: unknown): boolean {
  const assumed = new Set<string>();
  const ids = new Map<Node, number>();
  const id = (node: Node) => { if (!ids.has(node)) ids.set(node, ids.size); return ids.get(node); };
  const visit = (x: unknown, y: unknown): boolean => {
    if (!(x instanceof Node) || !(y instanceof Node)) return x === y;
    const pair = `${id(x)},${id(y)}`;
    if (assumed.has(pair)) return true; // a cycle: the same if they are the same everywhere else
    assumed.add(pair);
    if (x.constructor !== y.constructor) return false;
    for (const field of x.kind().FIELDS) {
      const u = x.field(field.name);
      const v = y.field(field.name);
      if (field instanceof Attribute) {
        if (typeof u !== typeof v || u !== v) return false;
      } else if (field.many) {
        const us = u as unknown[];
        const vs = v as unknown[];
        if (us.length !== vs.length || !us.every((item, i) => visit(item, vs[i]))) return false;
      } else if (!visit(u, v)) {
        return false;
      }
    }
    return true;
  };
  return visit(a, b);
}

/** A deep copy of the tree at `node`. Nodes shared within it are shared within the copy. */
export function copy<T extends Node>(node: T): T {
  const copies = new Map<Node, Node>();
  const visit = (item: unknown): unknown => {
    if (!(item instanceof Node)) return item;
    if (!copies.has(item)) {
      const made = new (item.kind() as unknown as new () => Node)();
      copies.set(item, made);
      for (const field of item.kind().FIELDS) {
        const value = item.field(field.name);
        (made as unknown as Record<string, unknown>)[field.name] = field instanceof Child && field.many
          ? (value as unknown[]).map(visit) : visit(value);
      }
    }
    return copies.get(item);
  };
  return visit(node) as T;
}

/** Where each node of a tree is: its parent, field and index. Taken once, it stays right while the tree changes only
 * through `replace` and `remove`. */
export class Parents {
  private readonly where = new Map<Node, [Node, string, number | null]>();

  constructor(readonly root: Node) {
    for (const item of walk(root)) {
      for (const [name, index, child] of children(item)) if (!this.where.has(child)) this.where.set(child, [item, name, index]);
    }
  }

  /** The node's parent; null for the root or a node outside the tree. */
  parent(node: Node): Node | null {
    return this.where.get(node)?.[0] ?? null;
  }

  /** The node's parent, the field holding it, and its index in that field if it is a list. */
  location(node: Node): [Node, string, number | null] | null {
    return this.where.get(node) ?? null;
  }

  /** The node's parent, its parent's parent, and so on to the root. */
  * ancestors(node: Node): Generator<Node> {
    for (let parent = this.parent(node); parent !== null; parent = this.parent(parent)) yield parent;
  }

  /** The path from the root to the node, such as 'items[0].body.items[2]'; '' for the root. */
  path(node: Node): string {
    const parts: string[] = [];
    for (let where = this.where.get(node); where !== undefined; where = this.where.get(where[0])) {
      const [, name, index] = where;
      parts.push(index === null ? name : `${name}[${index}]`);
    }
    return parts.reverse().join(".");
  }

  /** Puts `replacement` where `node` is: a node, null to empty a single field or remove from a list, or a list of nodes
   * to splice into a list. */
  replace(node: Node, replacement: Node | Node[] | null): void {
    const where = this.where.get(node);
    if (where === undefined) throw new ValueError("the node has no parent in this tree");
    const [parent, name, index] = where;
    const added = Array.isArray(replacement) ? replacement : replacement === null ? [] : [replacement];
    const holder = parent as unknown as Record<string, unknown>;
    if (index === null) {
      if (Array.isArray(replacement)) throw new TypeError(`${parent.kind().KIND}.${name} holds one node, not a list`);
      holder[name] = replacement;
    } else {
      (holder[name] as Node[]).splice(index, 1, ...added);
    }
    this.where.delete(node);
    for (const item of added) {
      for (const descendant of walk(item)) {
        for (const [n, j, child] of children(descendant)) this.where.set(child, [descendant, n, j]);
      }
    }
    if (index === null) {
      for (const item of added) this.where.set(item, [parent, name, null]);
    } else {
      (holder[name] as Node[]).forEach((item, i) => this.where.set(item, [parent, name, i]));
    }
  }

  /** Takes `node` out of the tree: empties its field, or removes it from its list. */
  remove(node: Node): void {
    this.replace(node, null);
  }
}

/** Walks a tree by kind: `visit(node)` calls `visit_<Kind>(node)` if the visitor defines it, and otherwise
 * `generic_visit(node)`, which visits the node's children in field order. */
export class Visitor {
  visit(node: Node): any {
    const method = (this as unknown as Record<string, unknown>)[`visit_${node.kind().KIND}`];
    return typeof method === "function" ? method.call(this, node) : this.generic_visit(node);
  }

  generic_visit(node: Node): any {
    for (const [, , child] of children(node)) this.visit(child);
    return null;
  }
}

/** Rewrites a tree by kind, in place: `visit` returns what replaces the node, which `generic_visit` stores. It returns
 * the node itself to keep it, another node to replace it, null to remove it (from a list, or emptying its field) or,
 * in a list, a list of nodes to splice in. */
export class Transformer extends Visitor {
  override generic_visit(node: Node): any {
    const holder = node as unknown as Record<string, unknown>;
    for (const field of node.kind().FIELDS) {
      if (!(field instanceof Child)) continue;
      const value = node.field(field.name);
      if (field.many) {
        const items: Node[] = [];
        for (const child of value as Node[]) {
          const result = this.visit(child);
          if (Array.isArray(result)) items.push(...result);
          else if (result !== null && result !== undefined) items.push(result);
        }
        holder[field.name] = items;
      } else if (value !== null) {
        const result = this.visit(value as Node);
        if (Array.isArray(result)) throw new TypeError(`${node.kind().KIND}.${field.name} holds one node, not a list`);
        holder[field.name] = result ?? null;
      }
    }
    return node;
  }
}
