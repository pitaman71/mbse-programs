/**
 * ES2020: `parse` reads its source text into a TypeScript tree, `print` writes a tree as its source text, and
 * `check` lists the constructs of a tree that ES2020 lacks. `JSX` is the same standard with JSX.
 *
 *     import { ECMAScript2020 } from "@mbse/programs/TypeScript";
 *     const program = ECMAScript2020.parse("let n = 1;");
 *     const text = ECMAScript2020.print(program);
 */

import type { SyntaxNode } from "../Framework/Syntax.js";
import type { Program } from "./Syntax.js";
import { ECMAScriptStandard } from "./_Standard.js";

export const STANDARD = new ECMAScriptStandard(2020);
export const JSX = new ECMAScriptStandard(2020, true);
export const parse = (text: string): Program => STANDARD.parse(text);
export const print = (node: SyntaxNode): string => STANDARD.print(node);
export const check = (node: SyntaxNode): string[] => STANDARD.check(node);
