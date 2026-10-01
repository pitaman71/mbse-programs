/**
 * Writes this implementation's conformance files: `npm run conformance [directory]`.
 *
 * For each source in `conformance/sources`, it writes the tree the source parses to, as a JSON snapshot
 * (`<source>.json`), and the text that tree prints to (`<source>.cpp`, `<source>.py`); and it writes each language's
 * grammar (`<language>.grammar.json`). Every implementation must write the same bytes. The default directory is
 * `conformance/typescript5` at the repository root.
 */

import { mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, extname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { JSON as SchemaJSON } from "@mbse/schemas/Framework";

import * as Ccpp20 from "../Ccpp/Ccpp20.js";
import * as CcppSyntax from "../Ccpp/Syntax.js";
import type { Node, NodeClass } from "../Framework/Syntax.js";
import * as Python314 from "../Python/Python314.js";
import * as PythonSyntax from "../Python/Syntax.js";

export const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../../conformance");
type Standard = { parse(text: string): Node; print(node: Node): string };
/** By a source's suffix: the standard that parses and prints it, and the kind of its tree. */
const STANDARDS: Record<string, [Standard, NodeClass]> = {
  ".cpp": [Ccpp20, CcppSyntax.TranslationUnit], ".py": [Python314, PythonSyntax.Module],
};
const LANGUAGES = [CcppSyntax.LANGUAGE, PythonSyntax.LANGUAGE];

/** File name -> text, for every file this implementation writes. */
export function render(sources: string = join(ROOT, "sources")): Map<string, string> {
  const files = new Map<string, string>(LANGUAGES.map((language) => [
    `${language.name()}.grammar.json`, JSON.stringify(language.grammar(), null, 1) + "\n"]));
  for (const name of readdirSync(sources).sort()) {
    const suffix = extname(name);
    const [standard, root] = STANDARDS[suffix] as [Standard, NodeClass];
    const unit = standard.parse(readFileSync(join(sources, name), "utf8"));
    const stem = name.slice(0, -suffix.length);
    files.set(`${stem}.json`, SchemaJSON.ToJSON.Reachable(root.Schema, unit, { indent: 2 }) + "\n");
    files.set(`${stem}${suffix}`, standard.print(unit));
  }
  return files;
}

if (process.argv[1] !== undefined && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const directory = process.argv[2] ?? join(ROOT, "typescript5");
  mkdirSync(directory, { recursive: true });
  for (const [name, text] of render()) {
    writeFileSync(join(directory, name), text, "utf8");
    console.log("wrote", join(directory, name));
  }
}
