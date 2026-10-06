/**
 * Writes this implementation's conformance files: `npm run conformance [directory]`.
 *
 * For each source in `conformance/sources`, it writes the tree the source parses to, as a JSON snapshot
 * (`<source>.json`), and the text that tree prints to (`<source>.cpp`, `<source>.py`, `<source>.ts`, `<source>.tsx`,
 * `<source>.sv`); `.svh` files are included by sources, not read on their own; and it writes each language's grammar
 * (`<language>.grammar.json`). Every implementation must write the same bytes.
 * The default directory is `conformance/typescript5` at the repository root.
 *
 * It also writes, beside each program of `conformance/transpilers/typescript-to-python`, the Python it translates to
 * (`<program>.py`), which every implementation must write alike too.
 */

import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { JSON as SchemaJSON } from "@mbse/schemas/Framework";

import * as Ccpp20 from "../Ccpp/Ccpp20.js";
import * as CcppSyntax from "../Ccpp/Syntax.js";
import type { SyntaxNode, SyntaxNodeClass } from "../Framework/Syntax.js";
import * as Python314 from "../Python/Python314.js";
import * as PythonSyntax from "../Python/Syntax.js";
import { transpile } from "../Transpilers/TypeScriptToPython.js";
import * as TypeScriptSyntax from "../TypeScript/Syntax.js";
import * as TypeScript59 from "../TypeScript/TypeScript59.js";
import * as SystemVerilog2023 from "../Verilog/SystemVerilog2023.js";
import * as VerilogSyntax from "../Verilog/Syntax.js";

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../../conformance");
type Standard = { parse(text: string, includePaths?: string[]): SyntaxNode; print(node: SyntaxNode): string };
/** By a source's suffix: the standard that parses and prints it, and the kind of its tree. */
const STANDARDS: Record<string, [Standard, SyntaxNodeClass]> = {
  ".cpp": [Ccpp20, CcppSyntax.TranslationUnit], ".py": [Python314, PythonSyntax.Module],
  ".ts": [TypeScript59.STANDARD, TypeScriptSyntax.Program], ".tsx": [TypeScript59.JSX, TypeScriptSyntax.Program],
  ".sv": [SystemVerilog2023.STANDARD, VerilogSyntax.SourceText],
};
const LANGUAGES = [CcppSyntax.LANGUAGE, PythonSyntax.LANGUAGE, TypeScriptSyntax.LANGUAGE, VerilogSyntax.LANGUAGE];
const INCLUDED = new Set([".svh"]); // files sources include, read with them

/** File name -> text, for every file this implementation writes. */
export function render(sources: string = join(ROOT, "sources")): Map<string, string> {
  const files = new Map<string, string>(LANGUAGES.map((language) => [
    `${language.name()}.grammar.json`, JSON.stringify(language.grammar(), null, 1) + "\n"]));
  for (const name of readdirSync(sources).sort()) {
    const suffix = extname(name);
    if (INCLUDED.has(suffix)) continue;
    const [standard, root] = STANDARDS[suffix] as [Standard, SyntaxNodeClass];
    const text = readFileSync(join(sources, name), "utf8");
    const unit = suffix === ".sv" ? standard.parse(text, [sources]) : standard.parse(text);
    const stem = name.slice(0, -suffix.length);
    files.set(`${stem}.json`, SchemaJSON.ToJSON(root.LANGUAGE.Builders).Reachable(root.Schema, unit, { indent: 2 }) + "\n");
    files.set(`${stem}${suffix}`, standard.print(unit));
  }
  return files;
}

/** File name -> text, for the Python each TypeScript program translates to. */
export function transpiled(programs: string = join(ROOT, "transpilers", "typescript-to-python")): Map<string, string> {
  return new Map(readdirSync(programs).filter((name) => name.endsWith(".ts")).sort().map((name) => [
    `${name.slice(0, -3)}.py`,
    Python314.print(transpile(TypeScript59.parse(readFileSync(join(programs, name), "utf8")))),
  ]));
}

if (process.argv[1] !== undefined && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const directory = process.argv[2] ?? join(ROOT, "typescript5");
  mkdirSync(directory, { recursive: true });
  for (const [name, text] of render()) {
    writeFileSync(join(directory, name), text, "utf8");
    console.log("wrote", join(directory, name));
  }
  const programs = join(ROOT, "transpilers", "typescript-to-python");
  for (const [name, text] of transpiled(programs)) {
    writeFileSync(join(programs, name), text, "utf8");
    console.log("wrote", join(programs, name));
  }
}
