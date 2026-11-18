"""RegExp: a regular expression literal's pattern and flags read into the `TypeScript RegExp` term they encode, the
`regexpliteral` a `TypeScript5` `constant` holds as its `regexp`.

`read(pattern, flags)` gives the writer of that term, which `Parse` gives the constant's `regexp`, or None where they do
not parse: the dialect holds a constant's `regexp` "absent where they do not parse", and has no reader of its own
(mbse-basis [CAP-226: complete expression dialects](mbse:mbse-basis/docs/capabilities/CAP-226.md#decided), "The model
and printers here, the parsers mbse-programs'"). It reads ECMA-262's pattern grammar (22.2.1, "Patterns") of ECMAScript
2025, the 16th Edition, as the dialect's kinds hold it: in the `u` mode and the `v` mode (its class set expressions,
string disjunctions and properties of strings), and without them, the web-compatibility grammar of Annex B (B.1.2):
`]`, `{` and `}` as characters, a quantifiable lookahead, a legacy octal escape, `\\c` where no letter follows, an
identity escape of any character but `c` (and `k`, where the pattern names a group), a decimal escape beyond the
groups a legacy octal escape or characters, and a class range with a character set as an end its characters. Its trees
are regexpp's, the reference parser the dialect's kinds are named for (`@eslint-community/regexpp`, with its
`ecmaVersion` 2025 and `strict` off), and so is what it rejects: duplicate flags or a flag ECMAScript has not, `u` and
`v` together, a group named twice in one alternative (ES2025's duplicate names allowed in separate ones), a reference to
a group the pattern does not name, a quantifier's bounds out of order, a class range's ends out of order, a property
escape of a name or a value Unicode's tables (ECMA-262's tables 67 to 69, and Unicode 16's scripts) do not have, a
negated class that may hold strings, and in the `u` and `v` modes, what Annex B alone allows *(agent)*. A pattern
holding a line terminator does not parse: the literal ends there (12.9.5) *(agent)*.

What it writes, through the builders (mbse-basis [PRI-019: fluent builder
syntax](mbse:mbse-basis/docs/PRINCIPLES.md#PRI-019)): each node regexpp builds, as the dialect names its kind and its
properties; a node's spelling, `raw`, where the dialect keeps it (a character's, a character set's, a backreference's,
a quantifier's, and the flags'), so the term prints back as written; a flag that is false (`negate`, `unicodeSets`,
`strings`, a flags helper's) and a group's absent `modifiers` or `name` not written, as `Parse` writes what is absent; a
quantifier's `greedy` always, its absence not meaning false, and its `max` absent where it is unbounded, as the dialect
has it; a literal's `flags` only where it has some. Without the `u` and `v` modes a pattern is read, as ECMAScript reads
it, in UTF-16 code units: a character beyond the Basic Multilingual Plane, written as itself, is two characters, its
surrogates, written without their spelling, which no text holds alone, so they print as escapes, `\\uD83D\\uDE00`
*(agent)*. A group's name is written decoded, its escapes (`(?<\\u0061>)`) printing as the characters they write: a
`capturinggroup` keeps no spelling of its name. ID_Start and ID_Continue, which a group's name is spelled of, are read
as Python's `str.isidentifier` reads them, Unicode's XID_Start and XID_Continue *(agent)*."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NamedTuple

from mbse.Expressions.TypeScript.RegExp import Expressions as R

__all__ = ["read"]

Writer = Callable[[Any], Any]

_SYNTAX = frozenset(map(ord, "^$\\.*+?()[]{}|"))
_EXTENDED = frozenset(map(ord, "^$\\.*+?()[|"))  # what Annex B's ExtendedPatternCharacter is not
_DOUBLE = frozenset(map(ord, "&!#$%*+,.:;<=>?@^`~"))  # ClassSetReservedDoublePunctuator's characters
_CLASS_SYNTAX = frozenset(map(ord, "()[]{}/-\\|"))  # ClassSetSyntaxCharacter
_RESERVED = frozenset(map(ord, "&-!#%,:;<=>@`~"))  # ClassSetReservedPunctuator
_TERMINATORS = frozenset((0x0A, 0x0D, 0x2028, 0x2029))
_CONTROLS = {ord("f"): 0x0C, ord("n"): 0x0A, ord("r"): 0x0D, ord("t"): 0x09, ord("v"): 0x0B}
_SETS = {ord("d"): "digit", ord("s"): "space", ord("w"): "word"}
_MODIFIERS = {letter: name for name, letter in R.MODIFIERS}
_FLAGS = {letter: name for name, letter in R.FLAGS}
_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
_NAME = _LETTERS + "_"  # what a property's name is spelled of, and its value too, with digits
_VALUE = _NAME + "0123456789"
_DIGITS = "0123456789abcdefABCDEF"

# Unicode's properties, as ECMA-262 lists them (tables 67, 68 and 69) with their values' aliases, as regexpp's tables
# hold them for ES2025: the General_Category's values, the scripts (Unicode 16), the binary properties, and those of
# strings, which the `v` mode alone allows.
_CATEGORY = frozenset(("General_Category", "gc"))
_SCRIPT = frozenset(("Script", "Script_Extensions", "sc", "scx"))
_CATEGORIES = frozenset("""
C Cased_Letter Cc Cf Close_Punctuation Cn Co Combining_Mark Connector_Punctuation Control Cs Currency_Symbol
Dash_Punctuation Decimal_Number Enclosing_Mark Final_Punctuation Format Initial_Punctuation L LC Letter Letter_Number
Line_Separator Ll Lm Lo Lowercase_Letter Lt Lu M Mark Math_Symbol Mc Me Mn Modifier_Letter Modifier_Symbol N Nd Nl No
Nonspacing_Mark Number Open_Punctuation Other Other_Letter Other_Number Other_Punctuation Other_Symbol P
Paragraph_Separator Pc Pd Pe Pf Pi Po Private_Use Ps Punctuation S Sc Separator Sk Sm So Space_Separator Spacing_Mark
Surrogate Symbol Titlecase_Letter Unassigned Uppercase_Letter Z Zl Zp Zs cntrl digit punct""".split())
_SCRIPTS = frozenset("""
Adlam Adlm Aghb Ahom Anatolian_Hieroglyphs Arab Arabic Armenian Armi Armn Avestan Avst Bali Balinese Bamu Bamum Bass
Bassa_Vah Batak Batk Beng Bengali Bhaiksuki Bhks Bopo Bopomofo Brah Brahmi Brai Braille Bugi Buginese Buhd Buhid Cakm
Canadian_Aboriginal Cans Cari Carian Caucasian_Albanian Chakma Cham Cher Cherokee Chorasmian Chrs Common Copt Coptic
Cpmn Cprt Cuneiform Cypriot Cypro_Minoan Cyrillic Cyrl Deseret Deva Devanagari Diak Dives_Akuru Dogr Dogra Dsrt Dupl
Duployan Egyp Egyptian_Hieroglyphs Elba Elbasan Elym Elymaic Ethi Ethiopic Gara Garay Geor Georgian Glag Glagolitic
Gong Gonm Goth Gothic Gran Grantha Greek Grek Gujarati Gujr Gukh Gunjala_Gondi Gurmukhi Gurung_Khema Guru Han Hang
Hangul Hani Hanifi_Rohingya Hano Hanunoo Hatr Hatran Hebr Hebrew Hira Hiragana Hluw Hmng Hmnp Hrkt Hung
Imperial_Aramaic Inherited Inscriptional_Pahlavi Inscriptional_Parthian Ital Java Javanese Kaithi Kali Kana Kannada
Katakana Katakana_Or_Hiragana Kawi Kayah_Li Khar Kharoshthi Khitan_Small_Script Khmer Khmr Khoj Khojki Khudawadi
Kirat_Rai Kits Knda Krai Kthi Lana Lao Laoo Latin Latn Lepc Lepcha Limb Limbu Lina Linb Linear_A Linear_B Lisu Lyci
Lycian Lydi Lydian Mahajani Mahj Maka Makasar Malayalam Mand Mandaic Mani Manichaean Marc Marchen Masaram_Gondi
Medefaidrin Medf Meetei_Mayek Mend Mende_Kikakui Merc Mero Meroitic_Cursive Meroitic_Hieroglyphs Miao Mlym Modi Mong
Mongolian Mro Mroo Mtei Mult Multani Myanmar Mymr Nabataean Nag_Mundari Nagm Nand Nandinagari Narb Nbat New_Tai_Lue
Newa Nko Nkoo Nshu Nushu Nyiakeng_Puachue_Hmong Ogam Ogham Ol_Chiki Ol_Onal Olck Old_Hungarian Old_Italic
Old_North_Arabian Old_Permic Old_Persian Old_Sogdian Old_South_Arabian Old_Turkic Old_Uyghur Onao Oriya Orkh Orya
Osage Osge Osma Osmanya Ougr Pahawh_Hmong Palm Palmyrene Pau_Cin_Hau Pauc Perm Phag Phags_Pa Phli Phlp Phnx
Phoenician Plrd Prti Psalter_Pahlavi Qaac Qaai Rejang Rjng Rohg Runic Runr Samaritan Samr Sarb Saur Saurashtra Sgnw
Sharada Shavian Shaw Shrd Sidd Siddham SignWriting Sind Sinh Sinhala Sogd Sogdian Sogo Sora Sora_Sompeng Soyo Soyombo
Sund Sundanese Sunu Sunuwar Sylo Syloti_Nagri Syrc Syriac Tagalog Tagb Tagbanwa Tai_Le Tai_Tham Tai_Viet Takr Takri
Tale Talu Tamil Taml Tang Tangsa Tangut Tavt Telu Telugu Tfng Tglg Thaa Thaana Thai Tibetan Tibt Tifinagh Tirh Tirhuta
Tnsa Todhri Todr Toto Tulu_Tigalari Tutg Ugar Ugaritic Unknown Vai Vaii Vith Vithkuqi Wancho Wara Warang_Citi Wcho
Xpeo Xsux Yezi Yezidi Yi Yiii Zanabazar_Square Zanb Zinh Zyyy Zzzz""".split())
_BINARY = frozenset("""
AHex ASCII ASCII_Hex_Digit Alpha Alphabetic Any Assigned Bidi_C Bidi_Control Bidi_M Bidi_Mirrored CI CWCF CWCM CWKCF
CWL CWT CWU Case_Ignorable Cased Changes_When_Casefolded Changes_When_Casemapped Changes_When_Lowercased
Changes_When_NFKC_Casefolded Changes_When_Titlecased Changes_When_Uppercased DI Dash Default_Ignorable_Code_Point Dep
Deprecated Dia Diacritic EBase EComp EMod EPres Emoji Emoji_Component Emoji_Modifier Emoji_Modifier_Base
Emoji_Presentation Ext ExtPict Extended_Pictographic Extender Gr_Base Gr_Ext Grapheme_Base Grapheme_Extend Hex
Hex_Digit IDC IDS IDSB IDST IDS_Binary_Operator IDS_Trinary_Operator ID_Continue ID_Start Ideo Ideographic Join_C
Join_Control LOE Logical_Order_Exception Lower Lowercase Math NChar Noncharacter_Code_Point Pat_Syn Pat_WS
Pattern_Syntax Pattern_White_Space QMark Quotation_Mark RI Radical Regional_Indicator SD STerm Sentence_Terminal
Soft_Dotted Term Terminal_Punctuation UIdeo Unified_Ideograph Upper Uppercase VS Variation_Selector White_Space XIDC
XIDS XID_Continue XID_Start space""".split())
_STRINGS = frozenset(("Basic_Emoji", "Emoji_Keycap_Sequence", "RGI_Emoji", "RGI_Emoji_Flag_Sequence",
                      "RGI_Emoji_Modifier_Sequence", "RGI_Emoji_Tag_Sequence", "RGI_Emoji_ZWJ_Sequence"))


class _Invalid(Exception):
    """A pattern that does not parse under its flags."""


class _Read(NamedTuple):
    """A node read: its kind's tag, the writer of its term, where it starts, and a character's code point, or for a
    character set -1, which a class range cannot end with, or -2 where it may hold strings (the `v` mode's)."""

    kind: str
    write: Writer
    start: int
    value: int


_STRINGS_SET = -2


# --- Its kinds, written through the builders ---


def _character(raw: str | None, value: int) -> Writer:
    if raw is None:  # a surrogate of a character read in code units, which no text spells alone
        return lambda e: e.character(lambda c: c.value(value))
    return lambda e: e.character(lambda c: c.raw(raw).value(value))


def _escape_set(raw: str, kind: str, negate: bool) -> Writer:
    """`.`, `\\d`, `\\s` or `\\w`, or one of the last three negated."""
    if negate:
        return lambda e: e.characterset(lambda s: s.raw(raw).setKind(kind).negate(True))
    return lambda e: e.characterset(lambda s: s.raw(raw).setKind(kind))


def _property_set(raw: str, negate: bool, strings: bool, key: str, value: str | None) -> Writer:
    """A property escape, `\\p{...}` or `\\P{...}`."""
    def write(s: Any) -> Any:
        s = s.raw(raw).setKind("property")
        s = s.negate(True) if negate else s
        s = s.strings(True) if strings else s
        return s.key(key) if value is None else s.key(key).value(value)
    return lambda e: e.characterset(write)


def _assertion(kind: str, negate: bool) -> Writer:
    """`^`, `$`, `\\b` or `\\B`."""
    if negate:
        return lambda e: e.assertion(lambda a: a.assertionKind(kind).negate(True))
    return lambda e: e.assertion(lambda a: a.assertionKind(kind))


def _lookaround(kind: str, negate: bool, alternatives: list[Writer]) -> Writer:
    if negate:
        return lambda e: e.assertion(lambda a: a.assertionKind(kind).negate(True).alternatives(alternatives))
    return lambda e: e.assertion(lambda a: a.assertionKind(kind).alternatives(alternatives))


def _backreference(raw: str, ref: int | str) -> Writer:
    return lambda e: e.backreference(lambda b: b.raw(raw).ref(ref))


def _quantifier(raw: str | None, low: int, high: int | None, greedy: bool, element: Writer) -> Writer:
    def write(q: Any) -> Any:
        q = q.min(low) if raw is None else q.raw(raw).min(low)
        q = q if high is None else q.max(high)
        return q.greedy(greedy).element(element)
    return lambda e: e.quantifier(write)


def _flags(raw: str, names: dict[str, str]) -> Writer:
    """A flags helper, a literal's or a modifiers': its spelling and the flags it sets."""
    def write(f: Any) -> Any:
        f = f.raw(raw)
        for letter in raw:
            f = getattr(f, names[letter])(True)
        return f
    return write


def _modifiers(add: str, remove: str | None) -> Writer:
    if remove is None:
        return lambda e: e.modifiers(lambda m: m.add(_flags(add, _MODIFIERS)))
    return lambda e: e.modifiers(lambda m: m.add(_flags(add, _MODIFIERS)).remove(_flags(remove, _MODIFIERS)))


def _group(modifiers: Writer | None, alternatives: list[Writer]) -> Writer:
    if modifiers is None:
        return lambda e: e.group(lambda g: g.alternatives(alternatives))
    return lambda e: e.group(lambda g: g.modifiers(modifiers).alternatives(alternatives))


def _capturing(name: str | None, alternatives: list[Writer]) -> Writer:
    if name is None:
        return lambda e: e.capturinggroup(lambda g: g.alternatives(alternatives))
    return lambda e: e.capturinggroup(lambda g: g.name(name).alternatives(alternatives))


def _class(sets: bool, negate: bool, elements: list[Writer]) -> Writer:
    def write(c: Any) -> Any:
        c = c.unicodeSets(True) if sets else c
        return (c.negate(True) if negate else c).elements(elements)
    return lambda e: e.characterclass(write)


def _expression_class(negate: bool, expression: Writer) -> Writer:
    if negate:
        return lambda e: e.expressioncharacterclass(lambda x: x.negate(True).expression(expression))
    return lambda e: e.expressioncharacterclass(lambda x: x.expression(expression))


def _range(low: Writer, high: Writer) -> Writer:
    return lambda e: e.characterclassrange(lambda r: r.min(low).max(high))


def _operation(tag: str, left: Writer, right: Writer) -> Writer:
    """A class intersection, `&&`, or subtraction, `--`, by its tag."""
    return lambda e: getattr(e, tag)(lambda o: o.left(left).right(right))


def _disjunction(alternatives: list[Writer]) -> Writer:
    """A class string disjunction, `\\q{...}`."""
    return lambda e: e.classstringdisjunction(lambda d: d.alternatives(alternatives))


def _string(elements: list[Writer]) -> Writer:
    return lambda e: e.stringalternative(lambda s: s.elements(elements))


def _alternative(elements: list[Writer]) -> Writer:
    return lambda e: e.alternative(lambda a: a.elements(elements))


# --- The reader ---


def _scalar(cp: int) -> bool:
    """Whether a code point is a character Python spells: not a surrogate, nor the end of the pattern (-1)."""
    return 0 <= cp < 0xD800 or cp > 0xDFFF


def _id_start(cp: int) -> bool:
    return cp in (0x24, 0x5F) or (_scalar(cp) and chr(cp).isidentifier())


def _id_part(cp: int) -> bool:
    return cp in (0x24, 0x200C, 0x200D) or (_scalar(cp) and ("a" + chr(cp)).isidentifier())


def _separated(one: tuple[tuple[int, int], ...], other: tuple[tuple[int, int], ...]) -> bool:
    """Whether two groups stand in separate alternatives of one disjunction, by the disjunctions and the alternatives
    that hold each, outermost first: so one pattern may name both alike (ES2025)."""
    for (disjunction, alternative), (theirs, their_alternative) in zip(one, other):
        if disjunction != theirs:
            return False
        if alternative != their_alternative:
            return True
    return False


class _Reader:
    """Reads a pattern into its nodes, as regexpp's validator and parser do, one production a method: as code points
    in the `u` and `v` modes (`unicode`, and `sets` for the `v` mode's), as UTF-16 code units without them. `named` is
    whether `\\k` must name a group: in the `u` and `v` modes, and where the pattern names one."""

    def __init__(self, pattern: str, unicode: bool, sets: bool, named: bool):
        self.unicode, self.sets, self.named = unicode or sets, sets, named
        data = pattern.encode("utf-16-le")
        self.units = [ord(c) for c in pattern] if self.unicode else [
            int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data), 2)]
        self.i = 0
        self.groups = self.count_groups()
        self.names: dict[str, list[tuple[tuple[int, int], ...]]] = {}  # each group's name, by where each stands
        self.references: set[str] = set()
        self.branch: list[tuple[int, int]] = []  # the disjunctions and their alternatives that hold what is read
        self.disjunctions = 0

    # Characters

    def at(self, k: int) -> int:
        """The code point (or code unit) `k` past here, -1 past the end."""
        return self.units[self.i + k] if self.i + k < len(self.units) else -1

    def eat(self, text: str) -> bool:
        if all(self.at(k) == ord(c) for k, c in enumerate(text)):
            self.i += len(text)
            return True
        return False

    def raw(self, start: int) -> str | None:
        """The text from `start` to here: None where it splits a character into its surrogates."""
        if self.unicode:
            return "".join(map(chr, self.units[start:self.i]))
        try:
            return b"".join(u.to_bytes(2, "little") for u in self.units[start:self.i]).decode("utf-16-le")
        except UnicodeDecodeError:
            return None

    def number(self, base: int, most: int) -> int | None:
        """The number the digits of `base` here write, at most `most` of them and at least one, or None."""
        start, digits = self.i, _DIGITS[:base] if base <= 10 else _DIGITS
        while self.i - start < most and self.at(0) != -1 and chr(self.at(0)) in digits:
            self.i += 1
        return int(self.text(start), base) if self.i > start else None

    def hexadecimal(self, count: int) -> int | None:
        """The number `count` hexadecimal digits here write, or None where fewer stand here."""
        start = self.i
        value = self.number(16, count)
        if value is not None and self.i - start == count:
            return value
        self.i = start
        return None

    def count_groups(self) -> int:
        """The capturing groups the pattern opens, which a decimal escape refers to below them: each `(` outside a
        class but a `(?` that names no group."""
        count, escaped, in_class = 0, False, False
        for k, cp in enumerate(self.units):
            if escaped:
                escaped = False
            elif cp == 0x5C:
                escaped = True
            elif cp in (0x5B, 0x5D):
                in_class = cp == 0x5B
            elif cp == 0x28 and not in_class:
                after = self.units[k + 1:k + 4] + [-1, -1, -1]
                count += after[0] != 0x3F or (after[1] == 0x3C and after[2] not in (0x3D, 0x21))
        return count

    # Disjunctions and alternatives

    def pattern(self) -> Writer:
        alternatives = self.disjunction()
        if self.i < len(self.units) or self.references - set(self.names):  # an unmatched `)`, a `\\` that ends it,
            raise _Invalid  # a lone `]` or `}`; a reference to a name no group has
        return lambda e: e.pattern(lambda p: p.alternatives(alternatives))

    def disjunction(self) -> list[Writer]:
        self.disjunctions += 1
        self.branch.append((self.disjunctions, 0))
        alternatives = [self.alternative()]
        while self.eat("|"):
            self.branch[-1] = (self.branch[-1][0], len(alternatives))
            alternatives.append(self.alternative())
        self.branch.pop()
        if self.at(0) in (0x2A, 0x2B, 0x3F, 0x7B):  # nothing to repeat, or a lone `{`
            raise _Invalid
        return alternatives

    def alternative(self) -> Writer:
        elements: list[_Read] = []
        while self.at(0) != -1 and self.term(elements):
            pass
        return _alternative([element.write for element in elements])

    def term(self, elements: list[_Read]) -> bool:
        quantifiable = self.assertion(elements)
        if quantifiable is None:
            if not (self.atom(elements) if self.unicode else self.extended_atom(elements)):
                return False
            quantifiable = True
        if quantifiable:
            self.quantifier(elements)
        return True

    # Assertions and quantifiers

    def assertion(self, elements: list[_Read]) -> bool | None:
        """An assertion read into `elements`, and whether a quantifier may follow it, or None where there is none:
        Annex B's lookahead alone."""
        start = self.i
        for text, kind, negate in (("^", "start", False), ("$", "end", False), ("\\b", "word", False),
                                   ("\\B", "word", True)):
            if self.eat(text):
                elements.append(_Read(R.ASSERTION, _assertion(kind, negate), start, -1))
                return False
        for text, kind, negate in (("(?=", "lookahead", False), ("(?!", "lookahead", True),
                                   ("(?<=", "lookbehind", False), ("(?<!", "lookbehind", True)):
            if self.eat(text):
                alternatives = self.disjunction()
                if not self.eat(")"):
                    raise _Invalid
                elements.append(_Read(R.ASSERTION, _lookaround(kind, negate, alternatives), start, -1))
                return kind == "lookahead" and not self.unicode
        return None

    def braced(self) -> tuple[int, int | None] | None:
        """A braced quantifier's bounds, `{n}`, `{n,}` or `{n,m}`, its `max` None where it is unbounded, or None where
        there is none here; out of order, or in the `u` and `v` modes incomplete, a pattern that does not parse."""
        start = self.i
        if self.eat("{"):
            low = self.number(10, len(self.units))
            if low is not None:
                high = low
                if self.eat(","):
                    high = self.number(10, len(self.units))
                if self.eat("}"):
                    if high is not None and high < low:
                        raise _Invalid
                    return low, high
            if self.unicode:
                raise _Invalid
            self.i = start
        return None

    def quantifier(self, elements: list[_Read]) -> None:
        """A quantifier of the last of `elements`, where one follows it."""
        bounds = {"*": (0, None), "+": (1, None), "?": (0, 1)}.get(chr(self.at(0))) if self.at(0) != -1 else None
        if bounds is not None:
            self.i += 1
        else:
            bounds = self.braced()
            if bounds is None:
                return
        greedy = not self.eat("?")
        element = elements.pop()
        raw = self.raw(element.start)
        elements.append(_Read(R.QUANTIFIER, _quantifier(raw, *bounds, greedy, element.write), element.start, -1))

    # Atoms

    def character(self, elements: list[_Read]) -> bool:
        """A character as itself."""
        start, cp = self.i, self.at(0)
        self.i += 1
        elements.append(_Read(R.CHARACTER, _character(self.raw(start), cp), start, cp))
        return True

    def atom(self, elements: list[_Read]) -> bool:
        """An atom of the `u` and `v` modes."""
        if self.at(0) not in _SYNTAX:
            return self.character(elements)
        return self.dot(elements) or self.escaped(elements) or self.character_class(elements) or self.group(elements)

    def extended_atom(self, elements: list[_Read]) -> bool:
        """An atom of Annex B's grammar, without the `u` and `v` modes."""
        if self.dot(elements) or self.escaped(elements):
            return True
        if self.eat("\\"):  # `\\` where no escape follows: `\\c` without a control letter; `\\` a character
            if self.at(0) != 0x63:  # `\\` that ends the pattern
                self.i -= 1
                return False
            elements.append(_Read(R.CHARACTER, _character("\\", 0x5C), self.i - 1, 0x5C))
            return True
        if self.character_class(elements) or self.group(elements):
            return True
        if self.braced() is not None:  # nothing to repeat
            raise _Invalid
        return self.at(0) not in _EXTENDED and self.character(elements)

    def dot(self, elements: list[_Read]) -> bool:
        start = self.i
        if not self.eat("."):
            return False
        elements.append(_Read(R.CHARACTERSET, lambda e: e.characterset(lambda s: s.raw(".").setKind("any")), start, -1))
        return True

    def escaped(self, elements: list[_Read]) -> bool:
        """An atom escape, `\\` and what follows it: a backreference, a character set or a character."""
        start = self.i
        if not self.eat("\\"):
            return False
        found = self.backreference(start) or self.set_escape(start) or self.character_escape(start)
        if found is None and self.named and self.eat("k"):
            name = self.group_name()
            if name is None:
                raise _Invalid
            self.references.add(name)
            found = _Read(R.BACKREFERENCE, _backreference(self.text(start), name), start, -1)
        if found is None:
            if self.unicode:
                raise _Invalid
            self.i = start
            return False
        elements.append(found)
        return True

    def text(self, start: int) -> str:
        """The text from `start` to here, which spells no surrogate apart: an escape's."""
        return "".join(map(chr, self.units[start:self.i]))

    def backreference(self, start: int) -> _Read | None:
        """A decimal escape, a backreference to the group it numbers, or without the `u` and `v` modes, where the
        pattern has fewer groups, None, a legacy octal escape or characters (Annex B)."""
        if not 0x31 <= self.at(0) <= 0x39:
            return None
        here = self.i
        number = self.number(10, len(self.units))
        if number is not None and number <= self.groups:
            return _Read(R.BACKREFERENCE, _backreference(self.text(start), number), start, -1)
        if self.unicode:
            raise _Invalid
        self.i = here
        return None

    def set_escape(self, start: int) -> _Read | None:
        """A character class escape, its `\\` read: `\\d`, `\\D`, `\\s`, `\\S`, `\\w` or `\\W`, and in the `u` and `v`
        modes a property escape."""
        cp = self.at(0)
        if cp | 0x20 in _SETS:
            self.i += 1
            return _Read(R.CHARACTERSET, _escape_set(self.text(start), _SETS[cp | 0x20], cp < 0x61), start, -1)
        if not self.unicode or cp | 0x20 != 0x70:
            return None
        self.i += 1
        if not self.eat("{"):
            raise _Invalid
        key, value, strings = self.property()
        negate = cp == 0x50
        if not self.eat("}") or (negate and strings):
            raise _Invalid
        write = _property_set(self.text(start), negate, strings, key, value)
        return _Read(R.CHARACTERSET, write, start, _STRINGS_SET if strings else -1)

    def word(self, letters: str) -> str:
        """The name or the value of a property here, of ASCII `letters`."""
        start = self.i
        while self.at(0) != -1 and chr(self.at(0)) in letters:
            self.i += 1
        return self.text(start)

    def property(self) -> tuple[str, str | None, bool]:
        """A property escape's key, its value and whether it is a property of strings, by Unicode's tables."""
        start = self.i
        name = self.word(_NAME)
        if name and self.eat("="):
            value = self.word(_VALUE)
            if (name in _CATEGORY and value in _CATEGORIES) or (name in _SCRIPT and value in _SCRIPTS):
                return name, value, False
            raise _Invalid
        self.i = start
        lone = self.word(_VALUE)
        if lone in _CATEGORIES:
            return "General_Category", lone, False
        if lone in _BINARY or (self.sets and lone in _STRINGS):
            return lone, None, lone in _STRINGS
        raise _Invalid

    def character_escape(self, start: int) -> _Read | None:
        """A character escape, its `\\` read: its character, or None."""
        value = self.escape_value()
        if value is None:
            return None
        return _Read(R.CHARACTER, _character(self.raw(start), value), start, value)

    def escape_value(self) -> int | None:
        """The code point a character escape writes, its `\\` read: a control escape, `\\c` and a letter, `\\0`, a
        hexadecimal or a Unicode escape, a legacy octal escape (Annex B) or an identity escape; or None."""
        cp, after = self.at(0), self.at(1)
        if cp in _CONTROLS:
            self.i += 1
            return _CONTROLS[cp]
        if cp == 0x63 and after != -1 and chr(after) in _LETTERS:
            self.i += 2
            return after % 0x20
        if cp == 0x30 and not 0x30 <= after <= 0x39:
            self.i += 1
            return 0
        if cp in (0x75, 0x78):
            self.i += 1
            value = self.hexadecimal(2) if cp == 0x78 else self.unicode_escape(self.unicode)
            if value is not None:
                return value
            if self.unicode:
                raise _Invalid
            self.i -= 1  # Annex B: an identity escape
        if not self.unicode and 0x30 <= cp <= 0x37:
            return self.octal()
        identity = cp in _SYNTAX or cp == 0x2F if self.unicode else cp not in (-1, 0x63) and not (self.named and cp == 0x6B)
        if identity:
            self.i += 1
            return cp
        return None

    def octal(self) -> int:
        """A legacy octal escape's value (Annex B): `\\0` to `\\377`."""
        start = self.i
        value = self.number(8, 3 if self.at(0) <= 0x33 else 2)
        assert value is not None and self.i > start
        return value

    def unicode_escape(self, unicode: bool) -> int | None:
        """A Unicode escape's code point, its `\\u` read: `\\uHHHH`, and where `unicode`, a surrogate pair's escapes
        as one and `\\u{H...}`; or None where none stands here."""
        value = self.hexadecimal(4)
        if value is not None:
            here = self.i
            if unicode and 0xD800 <= value <= 0xDBFF and self.eat("\\u"):
                trail = self.hexadecimal(4)
                if trail is not None and 0xDC00 <= trail <= 0xDFFF:
                    return 0x10000 + (value - 0xD800) * 0x400 + trail - 0xDC00
                self.i = here
            return value
        start = self.i
        if unicode and self.eat("{"):
            value = self.number(16, len(self.units))
            if value is not None and value <= 0x10FFFF and self.eat("}"):
                return value
        self.i = start
        return None

    # Groups

    def group_name(self) -> str | None:
        """A group's name, `<name>`, decoded, or None where no `<` follows; where no name and `>` do, a pattern that does
        not parse."""
        if not self.eat("<"):
            return None
        name: list[str] = []
        while True:
            here, cp = self.i, self.at(0)
            if self.eat("\\u"):
                cp = self.unicode_escape(True)
                if cp is None:
                    raise _Invalid
            elif 0xD800 <= cp <= 0xDBFF and 0xDC00 <= self.at(1) <= 0xDFFF:  # a surrogate pair, read in code units
                cp = 0x10000 + (cp - 0xD800) * 0x400 + self.at(1) - 0xDC00
                self.i += 2
            else:
                self.i += 1
            if not (_id_part(cp) if name else _id_start(cp)):
                self.i = here
                break
            name.append(chr(cp))
        if not name or not self.eat(">"):
            raise _Invalid
        return "".join(name)

    def group(self, elements: list[_Read]) -> bool:
        """A capturing group, named or not, or a group that captures nothing, with its modifiers (ES2025)."""
        start = self.i
        if not self.eat("("):
            return False
        name = modifiers = None
        captures = not self.eat("?")
        if not captures:
            name = self.group_name()
            captures = name is not None
        if name is not None:
            if any(not _separated(tuple(self.branch), other) for other in self.names.get(name, [])):
                raise _Invalid  # named twice where both may match
            self.names.setdefault(name, []).append(tuple(self.branch))
        elif not captures:
            modifiers = self.modifiers()
            if not self.eat(":"):
                raise _Invalid
        alternatives = self.disjunction()
        if not self.eat(")"):
            raise _Invalid
        if captures:
            elements.append(_Read(R.CAPTURINGGROUP, _capturing(name, alternatives), start, -1))
        else:
            elements.append(_Read(R.GROUP, _group(modifiers, alternatives), start, -1))
        return True

    def letters(self) -> str:
        """A modifiers' letters, `ims`, each once."""
        start = self.i
        while self.at(0) in (0x69, 0x6D, 0x73):
            self.i += 1
        spelled = self.text(start)
        if len(set(spelled)) != len(spelled):
            raise _Invalid
        return spelled

    def modifiers(self) -> Writer | None:
        """A group's modifiers, `ims-ims`, or None where it has none."""
        add = self.letters()
        if not self.eat("-"):
            return _modifiers(add, None) if add else None
        remove = self.letters()
        if not (add or remove) or set(add) & set(remove):
            raise _Invalid
        return _modifiers(add, remove)

    # Classes

    def character_class(self, elements: list[_Read]) -> bool:
        start = self.i
        if not self.eat("["):
            return False
        negate = self.eat("^")
        if self.sets:
            read = self.class_set(start, negate)
        else:
            read = _Read(R.CHARACTERCLASS, _class(False, negate, self.class_ranges()), start, -1)
        if not self.eat("]"):
            raise _Invalid
        elements.append(read)
        return True

    def class_ranges(self) -> list[Writer]:
        """A class's elements, without the `v` mode: characters, character sets and ranges."""
        out: list[_Read] = []
        while (low := self.class_atom()) is not None:
            out.append(low)
            hyphen = self.i
            if not self.eat("-"):
                continue
            out.append(_Read(R.CHARACTER, _character("-", 0x2D), hyphen, 0x2D))
            high = self.class_atom()
            if high is None:
                break
            out.append(high)
            if low.value < 0 or high.value < 0:  # Annex B: a character set as an end, its characters and `-`
                if self.unicode:
                    raise _Invalid
                continue
            if low.value > high.value:
                raise _Invalid
            del out[-3:]
            out.append(_Read(R.CHARACTERCLASSRANGE, _range(low.write, high.write), low.start, -1))
        return [read.write for read in out]

    def class_atom(self) -> _Read | None:
        """A class's character or character set, without the `v` mode, or None where `]` or the end stands here."""
        start, cp = self.i, self.at(0)
        if cp not in (-1, 0x5C, 0x5D):
            self.i += 1
            return _Read(R.CHARACTER, _character(self.raw(start), cp), start, cp)
        if not self.eat("\\"):
            return None
        cp, after = self.at(0), self.at(1)
        value = None
        if cp == 0x62 or (self.unicode and cp == 0x2D):  # `\\b`, a backspace; `\\-`
            value, self.i = (0x08 if cp == 0x62 else 0x2D), self.i + 1
        elif not self.unicode and cp == 0x63 and (0x30 <= after <= 0x39 or after == 0x5F):  # Annex B: `\\c` and a
            value, self.i = after % 0x20, self.i + 2  # digit or `_`
        if value is not None:
            return _Read(R.CHARACTER, _character(self.text(start), value), start, value)
        found = self.set_escape(start) or self.character_escape(start)
        if found is not None:
            return found
        if self.unicode:
            raise _Invalid
        if cp == 0x63:  # Annex B: `\\c` without a control letter, `\\` a character
            return _Read(R.CHARACTER, _character("\\", 0x5C), start, 0x5C)
        self.i = start  # `\\k` where the pattern names a group, or a `\\` that ends it
        return None

    # Classes of the `v` mode: class set expressions

    def class_set(self, start: int, negate: bool) -> _Read:
        """A class of the `v` mode, its `[` and `^` read: a union of operands and ranges, a `characterclass`, or an
        intersection or a subtraction, an `expressioncharacterclass`; its code point -2 where it may hold strings,
        which a negated one may not."""
        elements: list[_Read] = []
        if self.at(0) == 0x5D:
            strings = False
        elif self.set_character(elements):
            strings = False
            if not self.set_range(elements):
                for operator, tag in (("&&", R.CLASSINTERSECTION), ("--", R.CLASSSUBTRACTION)):
                    if self.eat(operator):
                        return self.operation(start, negate, elements.pop(), operator, tag, False)
            strings = self.union(elements, strings)
        else:
            strings = self.set_operand(elements)
            if strings is None:
                raise _Invalid
            for operator, tag in (("&&", R.CLASSINTERSECTION), ("--", R.CLASSSUBTRACTION)):
                if self.eat(operator):
                    return self.operation(start, negate, elements.pop(), operator, tag, strings)
            strings = self.union(elements, strings)
        if negate and strings:
            raise _Invalid
        write = _class(True, negate, [read.write for read in elements])
        return _Read(R.CHARACTERCLASS, write, start, _STRINGS_SET if strings else -1)

    def operation(self, start: int, negate: bool, left: _Read, operator: str, tag: str, strings: bool) -> _Read:
        """An intersection or a subtraction of classes, its first `operator` read after its first operand, `left`, an
        `expressioncharacterclass`: what an intersection holds is a string only where each operand may hold one, what
        a subtraction holds only where its first may."""
        while True:
            operands: list[_Read] = []
            found = None if self.at(0) == ord(operator[0]) else self.set_operand(operands)
            if found is None:  # `&&&`, or no operand
                raise _Invalid
            if tag == R.CLASSINTERSECTION:
                strings = strings and found
            left = _Read(tag, _operation(tag, left.write, operands[0].write), left.start, -1)
            if not self.eat(operator):
                break
        if negate and strings:
            raise _Invalid
        return _Read(R.EXPRESSIONCHARACTERCLASS, _expression_class(negate, left.write), start,
                     _STRINGS_SET if strings else -1)

    def union(self, elements: list[_Read], strings: bool) -> bool:
        """A union's further operands and ranges, read into `elements`: whether it may hold strings."""
        while True:
            if self.set_character(elements):
                self.set_range(elements)
                continue
            found = self.set_operand(elements)
            if found is None:
                return strings
            strings = strings or found

    def set_range(self, elements: list[_Read]) -> bool:
        """A range, `a-z`, its first character the last of `elements`."""
        here = self.i
        if self.eat("-"):
            if self.set_character(elements):
                high, low = elements.pop(), elements.pop()
                if low.value > high.value:
                    raise _Invalid
                elements.append(_Read(R.CHARACTERCLASSRANGE, _range(low.write, high.write), low.start, -1))
                return True
            self.i = here
        return False

    def set_operand(self, elements: list[_Read]) -> bool | None:
        """A class set operand read into `elements`, but a character: a nested class, a character class escape or a
        class string disjunction, or else a character; whether it may hold strings, or None where none stands here."""
        start = self.i
        if self.eat("["):
            read = self.class_set(start, self.eat("^"))
            if not self.eat("]"):
                raise _Invalid
        elif self.eat("\\q{"):
            alternatives, strings = [], False
            while True:
                characters: list[_Read] = []
                while self.set_character(characters):
                    pass
                strings = strings or len(characters) != 1
                alternatives.append(_string([character.write for character in characters]))
                if not self.eat("|"):
                    break
            if not self.eat("}"):
                raise _Invalid
            read = _Read(R.CLASSSTRINGDISJUNCTION, _disjunction(alternatives), start, _STRINGS_SET if strings else -1)
        else:
            escape = self.set_escape(start) if self.eat("\\") else None
            if escape is None:
                self.i = start
                return False if self.set_character(elements) else None
            read = escape
        elements.append(read)
        return read.value == _STRINGS_SET

    def set_character(self, elements: list[_Read]) -> bool:
        """A class set character read into `elements`: any but a syntax character or a doubled punctuator, or an
        escape of a character, of a reserved punctuator, or `\\b`."""
        start, cp = self.i, self.at(0)
        if not (cp == self.at(1) and cp in _DOUBLE) and cp != -1 and cp not in _CLASS_SYNTAX:
            return self.character(elements)
        if not self.eat("\\"):
            return False
        value = self.escape_value()
        if value is None and (self.at(0) in _RESERVED or self.at(0) == 0x62):
            value = 0x08 if self.at(0) == 0x62 else self.at(0)
            self.i += 1
        if value is None:
            self.i = start
            return False
        elements.append(_Read(R.CHARACTER, _character(self.text(start), value), start, value))
        return True


def read(pattern: str, flags: str) -> Writer | None:
    """The writer of the `TypeScript RegExp` term a regular expression literal's `pattern` and `flags` encode, a
    `regexpliteral`, given where a term of the dialect stands; or None where they do not parse: a flag ECMAScript has
    not, a flag twice, `u` and `v` together, a line terminator in the pattern, or a pattern its flags' grammar
    rejects."""
    if any(c not in _FLAGS for c in flags) or len(set(flags)) != len(flags) or {"u", "v"} <= set(flags):
        return None
    if any(ord(c) in _TERMINATORS for c in pattern):
        return None
    unicode, sets = "u" in flags, "v" in flags
    try:
        reader = _Reader(pattern, unicode, sets, unicode or sets)
        body = reader.pattern()
        if reader.names and not reader.named:  # a pattern that names a group reads `\\k` as a reference to one
            reader = _Reader(pattern, unicode, sets, True)
            body = reader.pattern()
    except _Invalid:
        return None
    if not flags:
        return lambda e: e.regexpliteral(lambda r: r.pattern(body))
    return lambda e: e.regexpliteral(lambda r: r.pattern(body).flags(_flags(flags, _FLAGS)))
