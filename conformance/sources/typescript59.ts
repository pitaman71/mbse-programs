#!/usr/bin/env node
// The conformance source for TypeScript 5.9: every kind but JSX's, which typescript59-jsx.tsx holds.
/* Comments are kept where statements and members are listed. */
import defaults, { readFile as read, type Stats } from "node:fs";
import * as path from "node:path";
import data from "./data.json" with { type: "json" };
import "./side-effect";
import fs = require("node:fs");
import Point2 = Geometry.Point;
export * from "./all";
export * as everything from "./all";
export type { Stats };
export { read as readAgain, path };

declare const process: { argv: string[] };
var hoisted = 1, unset;
let [first, , ...others] = [1, 2, 3, 4];
const { a: renamed = 1, b, ...rest } = { a: 1, b: 2, c: 3 };
let definite!: number;
const big = 1_000n + 0xFF_FFn, octal = 0o17, binary = 0b1010, real = 1.5e-3, str = 'a\n', other = "b";
const pattern = /ab+c/giv, template = `x ${hoisted} y ${`nested ${b}`}`;
const tagged = String.raw`a\nb${hoisted}`;

label: for (let i = 0; i < 10; i++) {
    if (i === 2) continue label;
    else if (i > 8) break label;
    else {
        ;
    }
}
for (const key in rest) debugger;
for (const value of others) {
}
for await (const chunk of [Promise.resolve(1)]) {
}
while (hoisted < 3) hoisted++;
do {
    --hoisted;
} while (hoisted > 0);
switch (hoisted) {
    case 0: // trailing
        break;
    default:
        hoisted = -hoisted;
}
try {
    throw new Error("e");
} catch {
} finally {
}
try {
} catch ({ message }) {
    void message;
}
with (Math) {
    max(1, 2);
}

function* generator(x: number = 1, ...ys: number[]): Generator<number> {
    yield x;
    yield* ys;
}
async function asynchronous(this: Window, p?: string): Promise<void> {
    await p;
    const m = import.meta;
    const loaded = await import("./module", { with: { type: "json" } });
}
function overloaded(a: string): string;
function overloaded(a: number): number;
function overloaded(a: any) {
    return a;
}
function guard(x: unknown): x is string {
    return typeof x === "string";
}
function check(x: unknown): asserts x {
}

const arrow = async <T,>(t: T): Promise<T> => t;
const objectArrow = () => ({ key: 1 });
const expression = function named() {
    return named;
};
const object = {
    plain: 1,
    "quoted": 2,
    [Symbol.iterator]: 3,
    hoisted,
    method() {
        return super.toString();
    },
    get getter() {
        return 1;
    },
    set setter(v) {
    },
    async *asyncGenerator() {
    },
    ...rest,
};
const sequence = (hoisted, unset);
const conditional = hoisted ? first : others;
const logical = (hoisted ?? 1) || (unset && 2);
const binary2 = 1 + 2 * 3 ** 4 - (5 % 6) / 7 << 1 >> 2 >>> 3 & 4 | 5 ^ 6;
const relational = 1 < 2 && 2 <= 3 && 3 > 2 && 3 >= 2 && 1 == 1 && 1 != 2 && 1 === 1 && 1 !== 2;
const typed = "key" in object && object instanceof Object;
const unary = [!true, -1, +1, ~1, typeof b, void 0, delete object.plain];
let assigned = 1;
assigned += 1; assigned -= 1; assigned *= 2; assigned /= 2; assigned %= 2; assigned **= 2; assigned <<= 1;
assigned >>= 1; assigned >>>= 1; assigned &= 1; assigned |= 1; assigned ^= 1; assigned &&= 1; assigned ||= 1;
assigned ??= 1;
[first, ...others] = [1, 2];
({ b: assigned } = { b: 1 });
const chained = object?.plain?.toString?.()?.[0];
const nonNull = definite!;
const asserted = <number>hoisted;
const cast = hoisted as unknown as number;
const satisfied = { x: 1 } satisfies Record<string, number>;
const constant = [1, 2] as const;
const instantiated = Array<string>;
const created = new Map<string, number>();
const holes = [1, , 2];

@decorator
@decorator.call()
export class Container<T extends object = {}> extends Base<T> implements Shape, Other<T> {
    #secret = 1;
    static count = 0;
    declare readonly label?: string;
    protected override definite!: number;
    accessor size = 1;
    [key: string]: unknown;
    constructor(private readonly value: T, public label2 = "x") {
        super();
    }
    get area(): number {
        return this.#secret;
    }
    set area(v: number) {
    }
    static {
        Container.count++;
    }
    method?(): void;
    has(other: object) {
        return #secret in other;
    }
}
export abstract class Abstract {
    abstract run(): void;
    abstract name: string;
    abstract accessor count: number;
}
const classExpression = class Named {
    m() {
        return Named;
    }
};

interface Shape {
    readonly area: number;
    name?: string;
    move(dx: number, dy: number): void;
    get size(): number;
    set size(v: number);
    (call: string): void;
    new (construct: string): Shape;
    [index: number]: string;
}
interface Other<T> extends Shape, Base<T> {
}
type Alias<in out T> = T | null | undefined;
type Everything = [any, unknown, number, bigint, boolean, string, symbol, object, never, void, this];
type Literals = "a" | 1 | true | -1 | `prefix-${string}`;
type Arrays = string[] | readonly number[] | [a: string, b?: number, ...rest: boolean[]] | [string?, ...number[]];
type Functions = ((a: string) => void) | (new (b: number) => Shape) | (abstract new () => object);
type Members = { a: string; b?(): void } & { [key: string]: unknown };
type Mapped<T> = { readonly [K in keyof T as `get${string & K}`]-?: T[K] };
type Unmapped<T> = { -readonly [K in keyof T]+?: T[K] };
type Conditional<T> = T extends (infer U extends string)[] ? U : never;
type Queried = typeof object.plain;
type Imported = import("./module").Name<string>;
type Qualified = Geometry.Point;
type Unique = unique symbol;
type Upper<S extends string> = intrinsic;
type Generic<const T> = T;
type Predicate = (x: unknown) => x is string;
type Indexed = Shape["area"];

enum Color {
    Red,
    Green = Red + 1,
    "Blue-ish" = 4,
}
declare const enum Flags {
}
namespace Geometry {
    export interface Point {
        x: number;
    }
}
namespace Outer.Inner {
}
declare module "virtual" {
    export const v: number;
}
declare module "shorthand";
declare global {
    interface Window {
        app: string;
    }
}
declare function ambient(): void;
using resource = { [Symbol.dispose]() {} };
await using asyncResource = { async [Symbol.asyncDispose]() {} };
import defer * as lazy from "./lazy";
export default hoisted;
export = Container;
export as namespace Library;
