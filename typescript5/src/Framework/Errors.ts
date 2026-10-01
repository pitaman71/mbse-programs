/**
 * Errors: the exceptions parsing and printing raise beyond mbse-schemas' own, named the same in every implementation.
 *
 * Both are `ValueError`s. `ParseError` locates its problem in the source text, with a 1-based line and column.
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
