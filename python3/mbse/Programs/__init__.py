"""mbse-programs: programs as language-neutral data.

Complete abstract syntax trees for programming languages, as plain in-memory objects that serialize through
mbse-schemas, with the entities they declare, and standards that parse source text into trees and print trees into
source text. A transpiler written against these trees never parses or prints strings. See docs/PROGRAMS.md at
https://github.com/pitaman71/mbse-programs.

The framework is `mbse.Programs.Framework`, and the languages are packages beside it: `mbse.Programs.Ccpp` for C and
C++, and `mbse.Programs.Python` for Python."""
