/**
 * Errors: the exceptions parsing, printing and transpiling raise beyond mbse-schemas' own, named the same in every
 * implementation.
 *
 * All are `ValueError`s. `ParseError` locates its problem in the source text, with a 1-based line and column, and
 * `TranspileError` in the tree, with the path to its node.
 */

import { Errors } from "@mbse/schemas/Framework";

/** Source text that is not a program of the standard: a syntax error, or a construct the standard lacks. */
export class ParseError extends Errors.ValueError {
  override name = "ParseError";

  constructor(message: string, readonly line: number, readonly column: number) {
    super(`line ${line}, column ${column}: ${message}`);
  }
}

/** A tree the standard cannot print: it is invalid, or uses a construct the standard lacks. */
export class PrintError extends Errors.ValueError {
  override name = "PrintError";
}

/** A tree a transpiler cannot translate: a construct the target has no counterpart for, or one outside the transpiler's
 * subset. `path` locates its node in the source tree, as `Parents.path` does. */
export class TranspileError extends Errors.ValueError {
  override name = "TranspileError";

  constructor(message: string, readonly path: string) {
    super(path ? `${path}: ${message}` : message);
  }
}
