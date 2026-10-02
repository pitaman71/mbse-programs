/** The versions of Python, each parsing source text into Python trees and printing them back. */

import { PrintError } from "../Framework/Errors.js";
import { children, type SyntaxNode, Standard } from "../Framework/Syntax.js";
import * as S from "./Syntax.js";
import * as Parser from "./_Parser.js";
import { Printer } from "./_Printer.js";

/** A version of Python, such as `new PythonStandard(3, 14)`: tree-sitter-python parses its source text, which must use
 * only the kinds and features the version has, and `Printer` prints its trees in one fixed layout. Its `version` is
 * `100 * major + minor`. */
export class PythonStandard extends Standard {
  private readonly printer = new Printer();

  constructor(major: number, minor: number) {
    super(S.LANGUAGE, S.PY, 100 * major + minor);
  }

  override label(version: number): string {
    return `Python ${Math.floor(version / 100)}.${version % 100}`;
  }

  /** The tree of a source file. Throws `ParseError` at the first syntax error, or at the first construct the version
   * lacks. */
  override parse(text: string): S.Module {
    const [module, positions, source] = Parser.parse(text);
    const stack: SyntaxNode[] = [module];
    while (stack.length > 0) {
      const node = stack.pop() as SyntaxNode;
      const offset = positions.get(node) as number; // the parser places every syntax node
      const problems = this.problems(node);
      if (problems.length > 0) throw source.error(`${problems[0]}, but this is ${this.name()}`, offset);
      stack.push(...children(node).reverse().map(([, , child]) => child));
    }
    return module;
  }

  /** The source text of a tree: a module as a file, any other syntax node as the text it stands for. Throws
   * `PrintError` for an invalid tree, or one with a construct the version lacks. */
  override print(node: SyntaxNode): string {
    let problems = this.language.validate(node);
    if (problems.length === 0) problems = this.check(node).map((p) => `${p}, but this is ${this.name()}`);
    if (problems.length > 0) throw new PrintError(problems[0]);
    return this.printer.print(node);
  }
}
