/** The versions of TypeScript and the editions of ECMAScript, each parsing source text into TypeScript trees and
 * printing them back, with JSX or without. */

import { PrintError } from "../Framework/Errors.js";
import { children, type Node, Standard } from "../Framework/Syntax.js";
import * as S from "./Syntax.js";
import * as Parser from "./_Parser.js";
import { Printer } from "./_Printer.js";

/** A standard of the TypeScript language: tree-sitter-typescript parses its source text (its `tsx` grammar with `jsx`),
 * which must use only the kinds and features the standard has, and `Printer` prints its trees in one fixed layout. With
 * `jsx`, source text may hold JSX but not the type assertion `<T>x`; without it, the reverse. */
abstract class TypeScriptLanguageStandard extends Standard {
  private readonly printer: Printer;

  constructor(family: string, version: number, readonly jsx: boolean) {
    super(S.LANGUAGE, family, version);
    this.printer = new Printer(jsx);
  }

  override problems(node: Node): string[] {
    if (this.jsx && node instanceof S.TSTypeAssertion) return [`${node.kind().KIND} is not allowed with JSX`];
    if (!this.jsx && node.kind().KIND.startsWith("JSX")) return [`${node.kind().KIND} needs JSX`];
    return super.problems(node);
  }

  /** The tree of a source file. Throws `ParseError` at the first syntax error, or at the first construct the standard
   * lacks. */
  override parse(text: string): S.Program {
    const [program, positions, source] = Parser.parse(text, this.jsx);
    const stack: Node[] = [program];
    while (stack.length > 0) {
      const node = stack.pop() as Node;
      const offset = positions.get(node) as number; // the parser places every node
      const problems = this.problems(node);
      if (problems.length > 0) throw source.error(`${problems[0]}, but this is ${this.name()}`, offset);
      stack.push(...children(node).reverse().map(([, , child]) => child));
    }
    return program;
  }

  /** The source text of a tree: a program as a file, any other node as the text it stands for. Throws `PrintError` for
   * an invalid tree, or one with a construct the standard lacks. */
  override print(node: Node): string {
    let problems = this.language.validate(node);
    if (problems.length === 0) problems = this.check(node).map((p) => `${p}, but this is ${this.name()}`);
    if (problems.length > 0) throw new PrintError(problems[0]);
    return this.printer.print(node);
  }
}

/** A version of TypeScript, such as `new TypeScriptStandard(5, 9)`, or with `jsx` its TSX. Its `version` is
 * `100 * major + minor`. */
export class TypeScriptStandard extends TypeScriptLanguageStandard {
  constructor(major: number, minor: number, jsx = false) {
    super(S.TS, 100 * major + minor, jsx);
  }

  override label(version: number): string {
    return `TypeScript ${Math.floor(version / 100)}.${version % 100}` + (this.jsx ? " with JSX" : "");
  }
}

/** An edition of ECMAScript, such as `new ECMAScriptStandard(2025)`, or with `jsx` its JSX: JavaScript, which has none
 * of TypeScript's own syntax. Its `version` is the edition's year. */
export class ECMAScriptStandard extends TypeScriptLanguageStandard {
  constructor(year: number, jsx = false) {
    super(S.ES, year, jsx);
  }

  override label(version: number): string {
    return `ES${version}` + (this.jsx ? " with JSX" : "");
  }
}
