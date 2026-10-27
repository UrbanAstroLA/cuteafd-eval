#!/usr/bin/env python3
"""MATH-500 answer checker (Block L reasoning). Standard library only.

Rule (fixed before any run):
  1. final_text(): the reply's final answer text. If the content contains "</think>" (vLLM with thinking off
     streams reasoning as content; see README), only the text after the last "</think>" counts.
  2. Extraction: the argument of the LAST \\boxed{...} (or \\fbox{...}) in the final text, braces matched.
     "\\boxed 5" (no braces) is accepted up to the next "$" or whitespace. No boxed answer -> "no_answer".
     The reasoning text is never searched (a boxed value there is recorded separately, not scored).
  3. Normalization: normalize() below, the Hendrycks et al. MATH steps (strip spaces, \\left/\\right, units
     text, degrees, dollar and percent signs, dfrac/tfrac -> frac, bare fractions a/b -> \\frac{a}{b},
     \\frac12 -> \\frac{1}{2}, \\sqrt2 -> \\sqrt{2}, "x = " prefixes of <= 2 chars, 0.5 -> \\frac{1}{2}), plus:
     \\text{..}/\\mbox{..} unwrapped, "\\," "\\;" "\\ " removed, trailing "." removed, thousands
     separators "1,000" -> "1000" only when every group after the first has exactly 3 digits.
  4. Equivalence: normalized strings equal, OR both parse as exact rationals (integers, decimals,
     \\frac{a}{b}, -\\frac{a}{b}) and are equal as Fractions. Nothing else (no symbolic algebra).
Self-test: selftest/math_check_selftest.json (extract from each MATH-500 reference solution, compare with
its `answer`).
"""
import re
from fractions import Fraction


def final_text(content):
    content = content or ""
    if "</think>" in content:
        return content.rsplit("</think>", 1)[1]
    return content


def last_boxed(text):
    """Return the argument of the last \\boxed{...} / \\fbox{...} in text, or None."""
    idx = max(text.rfind("\\boxed"), text.rfind("\\fbox"))
    if idx < 0:
        return None
    j = idx + (6 if text.startswith("\\boxed", idx) else 5)
    # "\boxed 5" form
    if j < len(text) and text[j] == " ":
        m = re.match(r" +([^\s$]+)", text[j:])
        return m.group(1) if m else None
    while j < len(text) and text[j] in " \t\n":
        j += 1
    if j >= len(text) or text[j] != "{":
        return None
    depth, k = 0, j
    while k < len(text):
        if text[k] == "{":
            depth += 1
        elif text[k] == "}":
            depth -= 1
            if depth == 0:
                return text[j + 1:k]
        k += 1
    return None


def _fix_fracs(s):
    parts = s.split("\\frac")
    out = parts[0]
    for p in parts[1:]:
        out += "\\frac"
        if p.startswith("{"):
            out += p
            continue
        if len(p) < 2:
            return s
        a, b, rest = p[0], p[1], p[2:]
        if b == "{":
            out += "{" + a + "}" + b + rest
        else:
            out += "{" + a + "}{" + b + "}" + rest
    return out


def _fix_a_slash_b(s):
    m = re.fullmatch(r"(-?\d+)/(\d+)", s)
    if m:
        return "\\frac{" + m.group(1) + "}{" + m.group(2) + "}"
    return s


def _remove_right_units(s):
    if "\\text{ " in s:
        return s.split("\\text{ ")[0]
    return s


def _fix_sqrt(s):
    return re.sub(r"\\sqrt(\w)", r"\\sqrt{\1}", s)


def _unwrap_text(s):
    prev = None
    while prev != s:
        prev = s
        s = re.sub(r"\\(?:text|textbf|mbox|mathrm)\{([^{}]*)\}", r"\1", s)
    return s


def normalize(s):
    if s is None:
        return None
    s = str(s).strip()
    s = s.replace("\n", "").replace("\\!", "")
    s = _remove_right_units(s)
    s = _unwrap_text(s)
    s = s.replace("\\\\", "\\")
    s = s.replace("tfrac", "frac").replace("dfrac", "frac")
    s = s.replace("\\left", "").replace("\\right", "")
    s = s.replace("^{\\circ}", "").replace("^\\circ", "").replace("°", "")
    s = s.replace("\\$", "").replace("$", "")
    s = s.replace("\\%", "").replace("%", "")
    s = s.replace("\\,", "").replace("\\;", "").replace("\\ ", "")
    s = s.replace(" .", " 0.").replace("{.", "{0.")
    s = s.strip()
    if s.endswith("."):
        s = s[:-1]
    if not s:
        return s
    if s[0] == ".":
        s = "0" + s
    sp = s.split("=")
    if len(sp) == 2 and len(sp[0].strip()) <= 2:
        s = sp[1]
    s = _fix_sqrt(s)
    s = s.replace(" ", "")
    s = _fix_fracs(s)
    if re.fullmatch(r"-?\d{1,3}(,\d{3})+(\.\d+)?", s):
        s = s.replace(",", "")
    if s == "0.5":
        s = "\\frac{1}{2}"
    s = _fix_a_slash_b(s)
    return s


def _as_fraction(s):
    if s is None:
        return None
    m = re.fullmatch(r"(-?)\\frac\{(-?\d+)\}\{(-?\d+)\}", s)
    try:
        if m:
            f = Fraction(int(m.group(2)), int(m.group(3)))
            return -f if m.group(1) else f
        if re.fullmatch(r"-?\d+(\.\d+)?", s):
            return Fraction(s)
    except (ValueError, ZeroDivisionError):
        return None
    return None


def is_equiv(pred, gold):
    a, b = normalize(pred), normalize(gold)
    if a is None or b is None:
        return False
    if a == b:
        return True
    fa, fb = _as_fraction(a), _as_fraction(b)
    return fa is not None and fb is not None and fa == fb


def check(content, gold, reasoning=None):
    """Score one reply. Returns a dict; `correct` is the only scored field."""
    ft = final_text(content)
    pred = last_boxed(ft)
    out = {"extracted": pred, "gold": gold, "status": "no_answer" if pred is None else None,
           "content_had_think_close": "</think>" in (content or ""),
           "reasoning_boxed": last_boxed(reasoning or "") if reasoning else None}
    if pred is not None:
        out["correct"] = is_equiv(pred, gold)
        out["status"] = "correct" if out["correct"] else "wrong"
    else:
        out["correct"] = False
    return out


if __name__ == "__main__":
    import json
    import sys
    rows = [json.loads(line) for line in open(sys.argv[1])]
    ok = sum(is_equiv(last_boxed(r["solution"]), r["answer"]) for r in rows)
    print(f"{ok}/{len(rows)} reference solutions match their answer")
