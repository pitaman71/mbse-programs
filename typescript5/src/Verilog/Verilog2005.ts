/**
 * Verilog (IEEE 1364-2005): `parse` reads its source text into a Verilog tree, `print` writes a tree as its source text,
 * and `check` lists the constructs of a tree that it lacks.
 *
 *     import { Verilog2005 } from "@mbse/programs/Verilog";
 *     const unit = Verilog2005.parse("module m; endmodule");
 *     const text = Verilog2005.print(unit);
 */

import type { SyntaxNode } from "../Framework/Syntax.js";
import type { SourceText } from "./Syntax.js";
import { VerilogStandard } from "./_Standard.js";

export const STANDARD = new VerilogStandard(2005, "Verilog");
export const parse = (text: string, includePaths: readonly string[] = [], defines: readonly string[] = []): SourceText =>
  STANDARD.parse(text, includePaths, defines);
export const print = (node: SyntaxNode): string => STANDARD.print(node);
export const check = (node: SyntaxNode): string[] => STANDARD.check(node);
