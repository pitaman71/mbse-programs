/** The standards of Verilog (IEEE 1364) and SystemVerilog (IEEE 1800), each reading source text into Verilog trees and
 * printing them back. */

import { PrintError } from "../Framework/Errors.js";
import { type SyntaxNode, Standard } from "../Framework/Syntax.js";
import * as S from "./Syntax.js";
import * as Reader from "./_Reader.js";
import { Printer } from "./_Printer.js";

/** A standard of SystemVerilog, such as `new VerilogStandard(2023)`, or with `family` 'Verilog' of Verilog, such as
 * `new VerilogStandard(2005, "Verilog")`: slang reads its source text, which must use only the kinds and features the
 * standard has, and `Printer` prints its trees in one fixed layout. Its `version` is the standard's year. */
export class VerilogStandard extends Standard {
  private readonly printer = new Printer();

  constructor(year: number, family: string = S.SV) {
    super(S.LANGUAGE, family, year);
  }

  override label(version: number): string {
    return `${this.family}-${version}`;
  }

  /** The tree of a source file. `includePaths` are searched for `` `include `` files, and `defines` (`NAME` or
   * `NAME=value`) are predefined macros. Throws `ParseError` at the first error slang reports, at what the reader does
   * not support, or at the first construct the standard lacks. Reading runs the Python implementation (see
   * `_Reader`). */
  override parse(text: string, includePaths: readonly string[] = [], defines: readonly string[] = []): S.SourceText {
    return Reader.parse(text, this.version, this.family, includePaths, defines);
  }

  /** The source text of a tree: source text as a file, any other syntax node as the text it stands for. Throws
   * `PrintError` for an invalid tree, or one with a construct the standard lacks. */
  override print(node: SyntaxNode): string {
    let problems = this.language.validate(node);
    if (problems.length === 0) problems = this.check(node).map((p) => `${p}, but this is ${this.name()}`);
    if (problems.length > 0) throw new PrintError(problems[0]);
    return this.printer.print(node);
  }
}
