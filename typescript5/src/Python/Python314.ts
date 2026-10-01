/**
 * Python 3.14: `parse` reads its source text into a Python tree, `print` writes a tree as its source text, and
 * `check` lists the constructs of a tree that Python 3.14 lacks.
 *
 *     import { Python314 } from "@mbse/programs/Python";
 *     const module = Python314.parse("print('hello')");
 *     const text = Python314.print(module);
 */

import type { Node } from "../Framework/Syntax.js";
import type { Module } from "./Syntax.js";
import { PythonStandard } from "./_Standard.js";

export const STANDARD = new PythonStandard(3, 14);
export const parse = (text: string): Module => STANDARD.parse(text);
export const print = (node: Node): string => STANDARD.print(node);
export const check = (node: Node): string[] => STANDARD.check(node);
