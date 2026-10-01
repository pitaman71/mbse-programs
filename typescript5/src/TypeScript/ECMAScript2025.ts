/**
 * ES2025: `parse` reads its source text into a TypeScript tree, `print` writes a tree as its source text, and
 * `check` lists the constructs of a tree that ES2025 lacks. `JSX` is the same standard with JSX.
 *
 *     import { ECMAScript2025 } from "@mbse/programs/TypeScript";
 *     const program = ECMAScript2025.parse("let n = 1;");
 *     const text = ECMAScript2025.print(program);
 */

import type { Node } from "../Framework/Syntax.js";
import type { Program } from "./Syntax.js";
import { ECMAScriptStandard } from "./_Standard.js";

export const STANDARD = new ECMAScriptStandard(2025);
export const JSX = new ECMAScriptStandard(2025, true);
export const parse = (text: string): Program => STANDARD.parse(text);
export const print = (node: Node): string => STANDARD.print(node);
export const check = (node: Node): string[] => STANDARD.check(node);
