/**
 * SystemVerilog (IEEE 1800-2023): `parse` reads its source text into a Verilog tree, `print` writes a tree as its source text,
 * and `check` lists the constructs of a tree that it lacks.
 *
 *     import { SystemVerilog2023 } from "@mbse/programs/Verilog";
 *     const unit = SystemVerilog2023.parse("module m; endmodule");
 *     const text = SystemVerilog2023.print(unit);
 */

import type { SyntaxNode } from "../Framework/Syntax.js";
import type { SourceText } from "./Syntax.js";
import { VerilogStandard } from "./_Standard.js";

export const STANDARD = new VerilogStandard(2023);
export const parse = (text: string, includePaths: readonly string[] = [], defines: readonly string[] = []): SourceText =>
  STANDARD.parse(text, includePaths, defines);
export const print = (node: SyntaxNode): string => STANDARD.print(node);
export const check = (node: SyntaxNode): string[] => STANDARD.check(node);
