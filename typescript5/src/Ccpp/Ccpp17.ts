/**
 * C++17 (ISO/IEC 14882:2017): `parse` reads its source text into a Ccpp tree, `print` writes a tree as its source
 * text, and `check` lists the constructs of a tree that C++17 lacks.
 *
 *     import { Ccpp17 } from "@mbse/programs/Ccpp";
 *     const unit = Ccpp17.parse("int main() { return 0; }");
 *     const text = Ccpp17.print(unit);
 */

import type { Node } from "../Framework/Syntax.js";
import type { TranslationUnit } from "./Syntax.js";
import { CcppStandard } from "./_Standard.js";

export const STANDARD = new CcppStandard(2017);
export const parse = (text: string): TranslationUnit => STANDARD.parse(text);
export const print = (node: Node): string => STANDARD.print(node);
export const check = (node: Node): string[] => STANDARD.check(node);
