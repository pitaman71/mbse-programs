/**
 * Reads Verilog source text into trees through slang, which runs only in Python: each read runs the Python
 * implementation's `mbse.Programs.Verilog.read` and loads the JSON snapshot it writes, so that both implementations
 * read the same trees and report the same errors.
 *
 * The Python interpreter is `MBSE_PROGRAMS_PYTHON` if it is set, and otherwise the virtual environment of this
 * repository's `python3` (`uv sync` there creates it). Reading Verilog needs Node; printing, checking and definitions do
 * not.
 */

import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { JSON as SchemaJSON } from "@mbse/schemas/Framework";

import { ParseError } from "../Framework/Errors.js";
import * as S from "./Syntax.js";

/** The Python interpreter that reads Verilog. */
export function python(): string {
  return process.env["MBSE_PROGRAMS_PYTHON"] ?? fileURLToPath(new URL("../../../python3/.venv/bin/python", import.meta.url));
}

/** The tree of a source file of `family` and `year`, as `VerilogStandard.parse` reads it. Throws `ParseError` where
 * the Python implementation raises it, and `Error` when Python cannot be run. */
export function parse(text: string, year: number, family: string, includePaths: readonly string[],
  defines: readonly string[]): S.SourceText {
  const request = JSON.stringify({ text, year, family, include_paths: includePaths, defines });
  const interpreter = python();
  let output: string;
  try {
    output = execFileSync(interpreter, ["-m", "mbse.Programs.Verilog.read"],
      { input: request, encoding: "utf-8", maxBuffer: 1 << 30, stdio: ["pipe", "pipe", "pipe"] });
  } catch (error) {
    throw new Error(`reading Verilog runs ${interpreter} with mbse-programs and pyslang installed, which failed: `
      + `${(error as Error).message}`);
  }
  const response = JSON.parse(output) as { tree?: string; error?: string; line?: number; column?: number };
  if (response.tree === undefined) throw new ParseError(response.error as string, response.line as number, response.column as number);
  return SchemaJSON.FromJSON(S.LANGUAGE.Builders).Reachable(S.SourceText.Schema, response.tree) as S.SourceText;
}
