"""TypeScript and JavaScript as one tree language: the abstract syntax (`Syntax`), the names a program declares
(`Definitions`), and the standards that parse and print source text (`TypeScript50`, `TypeScript59`, `ECMAScript2020`,
`ECMAScript2025`, each with a `JSX` variant)."""

from . import Definitions, ECMAScript2020, ECMAScript2025, Syntax, TypeScript50, TypeScript59

__all__ = ["Syntax", "Definitions", "TypeScript50", "TypeScript59", "ECMAScript2020", "ECMAScript2025"]
