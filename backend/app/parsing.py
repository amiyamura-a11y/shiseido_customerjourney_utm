"""Parsing of individual action strings such as
``D−24｜外部サイト_大衆向けEC_Yahoo！ショッピング_1回目``.

The format is ``D<minus><n><bar><individual variable>_<k>回目``.
* minus may be U+2212 (−), ASCII hyphen, full-width hyphen or en dash
* bar may be full-width ｜ or ASCII |
* the individual variable may itself contain underscores, so the repeat suffix
  is recognised from the END of the string and the variable is never split.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

MINUS = "[\u2212\uff0d\u2013\u2014\uff70\\-]"
BAR = "[｜|]"
_PATTERN = re.compile(
    rf"^\s*[DdＤ]\s*{MINUS}?\s*(?P<dn>\d+)\s*{BAR}\s*(?P<body>.+?)\s*$"
)
_REPEAT = re.compile(r"^(?P<var>.+?)_(?P<rep>\d+)\s*回目\s*$")


@dataclass(frozen=True)
class ParsedAction:
    days_before_reference: int | None
    individual_variable: str
    repeat_index: int | None
    raw: str
    error: str | None = None


def parse_action(raw: str) -> ParsedAction:
    """Parse one action cell. Never raises; unparsable cells keep the raw text."""
    text = ("" if raw is None else str(raw)).strip()
    if not text:
        return ParsedAction(None, "", None, text, "empty")
    m = _PATTERN.match(text)
    if not m:
        return ParsedAction(None, text, None, text, "no_dn_prefix")
    dn = int(m.group("dn"))
    body = m.group("body")
    r = _REPEAT.match(body)
    if not r:
        return ParsedAction(dn, body, None, text, "no_repeat_suffix")
    return ParsedAction(dn, r.group("var"), int(r.group("rep")), text, None)
