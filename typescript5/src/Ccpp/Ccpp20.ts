/**
 * C++20 (ISO/IEC 14882:2020): `parse` reads its source text into a Ccpp tree, `print` writes a tree as its source
 * text, and `check` lists the constructs of a tree that C++20 lacks.
 *
 *     import { Ccpp20 } from "@mbse/programs/Ccpp";
 *     const unit = Ccpp20.parse("int main() { return 0; }");
 *     const text = Ccpp20.print(unit);
 */

import type { SyntaxNode } from "../Framework/Syntax.js";
import type { TranslationUnit } from "./Syntax.js";
import { CcppStandard } from "./_Standard.js";

export const STANDARD = new CcppStandard(2020);
export const parse = (text: string): TranslationUnit => STANDARD.parse(text);
export const print = (node: SyntaxNode): string => STANDARD.print(node);
export const check = (node: SyntaxNode): string[] => STANDARD.check(node);
