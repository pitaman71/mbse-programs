/** The standards of C and C++, each parsing source text into Ccpp trees and printing them back. */

import { PrintError } from "../Framework/Errors.js";
import { children, type SyntaxNode, Standard } from "../Framework/Syntax.js";
import * as S from "./Syntax.js";
import * as Parser from "./_Parser.js";
import { Printer } from "./_Printer.js";

/** A standard of C++, or with `family` 'C' of C: tree-sitter-cpp parses its source text, which must use only the kinds
 * and features the standard has, and `Printer` prints its trees in one fixed layout. */
export class CcppStandard extends Standard {
  private readonly printer = new Printer();

  constructor(year: number, family: string = S.CPP) {
    super(S.LANGUAGE, family, year);
  }

  /** The tree of a source file. Throws `ParseError` at the first syntax error, or at the first construct the standard
   * lacks. */
  override parse(text: string): S.TranslationUnit {
    const [unit, positions, source] = Parser.parse(text);
    const stack: [SyntaxNode, number][] = [[unit, 0]];
    while (stack.length > 0) {
      const [node, inherited] = stack.pop() as [SyntaxNode, number];
      const offset = positions.get(node) ?? inherited;
      const problems = this.problems(node);
      if (problems.length > 0) throw source.error(`${problems[0]}, but this is ${this.name()}`, offset);
      stack.push(...children(node).reverse().map(([, , child]): [SyntaxNode, number] => [child, offset]));
    }
    return unit;
  }

  /** The source text of a tree: a translation unit as a file, any other syntax node as the text it stands for. Throws
   * `PrintError` for an invalid tree, or one with a construct the standard lacks. */
  override print(node: SyntaxNode): string {
    let problems = this.language.validate(node);
    if (problems.length === 0) problems = this.check(node).map((p) => `${p}, but this is ${this.name()}`);
    if (problems.length > 0) throw new PrintError(problems[0]);
    return this.printer.print(node);
  }
}
