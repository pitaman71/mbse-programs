/**
 * TypeScript 5.0: `parse` reads its source text into a TypeScript tree, `print` writes a tree as its source text, and
 * `check` lists the constructs of a tree that TypeScript 5.0 lacks. `JSX` is the same standard with JSX.
 *
 *     import { TypeScript50 } from "@mbse/programs/TypeScript";
 *     const program = TypeScript50.parse("let n: number = 1;");
 *     const text = TypeScript50.print(program);
 */

import type { Node } from "../Framework/Syntax.js";
import type { Program } from "./Syntax.js";
import { TypeScriptStandard } from "./_Standard.js";

export const STANDARD = new TypeScriptStandard(5, 0);
export const JSX = new TypeScriptStandard(5, 0, true);
export const parse = (text: string): Program => STANDARD.parse(text);
export const print = (node: Node): string => STANDARD.print(node);
export const check = (node: Node): string[] => STANDARD.check(node);
