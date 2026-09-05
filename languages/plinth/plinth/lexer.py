"""PLINTH lexer (~stdlib only).

Whitespace is insignificant except as a token separator (01_LANGUAGE.md
Sec 2); newlines carry no grammatical meaning here -- only line/col tracking
for error messages. (Reading: the grammar in Sec 4 shows NEWLINE after block
headers for readability of the examples; the parser recovers block
boundaries structurally via keyword shape + explicit end_* terminators, so
no NEWLINE token is needed. See the language agent's final report for this
call.)

Deliberate gotcha (01_LANGUAGE.md Sec 5.4): a NUMBER glued directly to a
UNIT with no space forms one QUANTITY token. A NUMBER followed by
whitespace and then a bare unit word is a lexical error (E043) -- the
space itself is the mistake.
"""
import re

from grammar import UNITS, all_keyword_names


class PlinthError(Exception):
    """Uniform error type raised by lexer/parser/checker/runtime.

    Carries everything needed to build one entry of the Sec 5 verifier
    result contract's `errors` array.
    """

    def __init__(self, code, line, col, message):
        super().__init__(message)
        self.code = code
        self.line = line
        self.col = col
        self.message = message


ALL_RESERVED = all_keyword_names()

_UNIT_ALT = "|".join(UNITS)
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
_QUANTITY_RE = re.compile(rf"-?\d+(?:\.\d+)?(?:{_UNIT_ALT})(?![A-Za-z0-9_])")
_UNIT_SUFFIX_RE = re.compile(rf"(?:{_UNIT_ALT})(?![A-Za-z0-9_])$")
_UNIT_WORD_RE = re.compile(rf"(?:{_UNIT_ALT})(?![A-Za-z0-9_])")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_STRING_RE = re.compile(r'"[^"\n]*"')


class Token:
    __slots__ = ("kind", "value", "line", "col")

    def __init__(self, kind, value, line, col):
        self.kind = kind
        self.value = value
        self.line = line
        self.col = col

    def __repr__(self):
        return f"Token({self.kind}, {self.value!r}, {self.line}:{self.col})"


def tokenize(source):
    tokens = []
    i = 0
    n = len(source)
    line = 1
    col = 1

    def advance(k=1):
        nonlocal i, line, col
        for _ in range(k):
            if i < n and source[i] == "\n":
                line += 1
                col = 1
            else:
                col += 1
            i += 1

    while i < n:
        ch = source[i]
        if ch in " \t\r\n":
            advance()
            continue
        if ch == "#":
            while i < n and source[i] != "\n":
                advance()
            continue

        start_line, start_col = line, col

        m = _QUANTITY_RE.match(source, i)
        if m:
            text = m.group(0)
            um = _UNIT_SUFFIX_RE.search(text)
            unit = um.group(0)
            num_text = text[: -len(unit)]
            tokens.append(Token("QUANTITY", (float(num_text), unit), start_line, start_col))
            advance(len(text))
            continue

        m = _NUM_RE.match(source, i)
        if m:
            text = m.group(0)
            advance(len(text))
            # Gotcha detection: NUMBER <space(s)> UNIT-word -> E043. A bare
            # NUMBER not followed (after whitespace) by a recognized unit
            # word is left alone; the checker decides if it's legal there.
            j = i
            while j < n and source[j] in " \t":
                j += 1
            if j > i:
                um = _UNIT_WORD_RE.match(source, j)
                if um:
                    raise PlinthError(
                        "E043", start_line, start_col,
                        f"space between number and unit near '{text} {um.group(0)}'; "
                        f"write '{text}{um.group(0)}' with no space",
                    )
            tokens.append(Token("NUMBER", float(text), start_line, start_col))
            continue

        m = _STRING_RE.match(source, i)
        if m:
            text = m.group(0)
            tokens.append(Token("STRING", text[1:-1], start_line, start_col))
            advance(len(text))
            continue

        if source[i:i + 2] == "<-":
            tokens.append(Token("ARROW", "<-", start_line, start_col))
            advance(2)
            continue

        if ch == "=":
            tokens.append(Token("EQUALS", "=", start_line, start_col))
            advance()
            continue

        if ch == '"':
            # unterminated string (no closing quote on this line)
            raise PlinthError("E001", start_line, start_col, "unterminated string literal")

        m = _IDENT_RE.match(source, i)
        if m:
            text = m.group(0)
            advance(len(text))
            if text == "true":
                tokens.append(Token("BOOL", True, start_line, start_col))
            elif text == "false":
                tokens.append(Token("BOOL", False, start_line, start_col))
            elif text in ALL_RESERVED:
                tokens.append(Token("KEYWORD", text, start_line, start_col))
            else:
                tokens.append(Token("IDENT", text, start_line, start_col))
            continue

        raise PlinthError("E001", start_line, start_col, f"unexpected character {ch!r}")

    tokens.append(Token("EOF", None, line, col))
    return tokens
