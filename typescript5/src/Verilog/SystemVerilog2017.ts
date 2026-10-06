/**
 * SystemVerilog (IEEE 1800-2017): `parse` reads its source text into a Verilog tree, `print` writes a tree as its source text,
 * and `check` lists the constructs of a tree that it lacks.
 *
 *     import { SystemVerilog2017 } from "@mbse/programs/Verilog";
 *     const unit = SystemVerilog2017.parse("module m; endmodule");
 *     const text = SystemVerilog2017.print(unit);
 */

import type { SyntaxNode } from "../Framework/Syntax.js";
import type { SourceText } from "./Syntax.js";
import { VerilogStandard } from "./_Standard.js";

export const STANDARD = new VerilogStandard(2017);
export const parse = (text: string, includePaths: readonly string[] = [], defines: readonly string[] = []): SourceText =>
  STANDARD.parse(text, includePaths, defines);
export const print = (node: SyntaxNode): string => STANDARD.print(node);
export const check = (node: SyntaxNode): string[] => STANDARD.check(node);
