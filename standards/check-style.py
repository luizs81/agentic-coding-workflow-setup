#!/usr/bin/env python3
"""Check markdown prose against the four mechanical ASD-STE100 rules."""

import argparse
import re
import sys

MAX_SENTENCE_WORDS = 25
MAX_PARAGRAPH_SENTENCES = 4
# Only these three. "could"/"would" have legitimate conditional uses in review prose.
MODALS = re.compile(r"\b(should|may|might)\b", re.I)

# Sentence-final period that is not an abbreviation, an initial, or a section number.
ABBREV = re.compile(r"\b(e\.g|i\.e|etc|vs|approx|Fig|No|Mr|Ms|Dr|St|§\d)\.$", re.I)


def strip_noise(text):
    """Blank out everything that is not prose, keeping line numbers intact."""
    out = []
    in_fence = in_front = False
    for i, line in enumerate(text.splitlines()):
        if i == 0 and line.strip() == "---":
            in_front = True
            out.append("")
            continue
        if in_front:
            if line.strip() == "---":
                in_front = False
            out.append("")
            continue
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            out.append("")
            continue
        if in_fence or line.startswith("#") or line.lstrip().startswith("|"):
            out.append("")
            continue
        line = re.sub(r"`[^`]*`", "X", line)          # inline code -> one token
        line = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", line)  # links -> label
        # A list marker starts a new block. Mark it, then strip it.
        if re.match(r"^\s*([-*+]|\d+\.)\s+", line):
            line = "\x00" + re.sub(r"^\s*([-*+]|\d+\.)\s+", "", line)
        out.append(line)
    return out


def split_sentences(block):
    parts, buf = [], ""
    for tok in re.split(r"(?<=[.!?])(\s+)", block):
        if tok.isspace():
            if ABBREV.search(buf.strip()):
                buf += tok
            else:
                parts.append(buf.strip())
                buf = ""
        else:
            buf += tok
    if buf.strip():
        parts.append(buf.strip())
    return [p for p in parts if p]


def words(sentence):
    return re.findall(r"[A-Za-z][\w'/-]*", sentence)


def check(path):
    lines = strip_noise(open(path, encoding="utf-8").read())
    findings = []

    # Blocks: runs of non-blank prose lines. A blank line or a list marker ends one.
    # Each fragment keeps its line number, so a finding reports where it really is.
    blocks, para = [], []
    for n, line in enumerate(lines, 1):
        bullet = line.startswith("\x00")
        text = line.lstrip("\x00").strip()
        if not text:
            if para:
                blocks.append(para)
            para = []
            continue
        if bullet and para:
            blocks.append(para)
            para = []
        para.append((n, text))
    if para:
        blocks.append(para)

    for para in blocks:
        block = " ".join(t for _, t in para)
        # Map each character offset in `block` back to a source line.
        offsets, pos = [], 0
        for n, t in para:
            offsets.append((pos, n))
            pos += len(t) + 1

        def line_of(sentence):
            i = block.find(sentence)
            return next(n for off, n in reversed(offsets) if off <= max(i, 0))

        sentences = split_sentences(block)
        lineno = para[0][0]
        if len(sentences) > MAX_PARAGRAPH_SENTENCES:
            findings.append(
                (lineno, "WARN", f"paragraph has {len(sentences)} sentences "
                                 f"(max {MAX_PARAGRAPH_SENTENCES})"))
        for s in sentences:
            n = len(words(s))
            if n < 3:
                continue
            at = line_of(s)
            if n > MAX_SENTENCE_WORDS:
                findings.append(
                    (at, "ERROR", f"sentence is {n} words "
                                  f"(max {MAX_SENTENCE_WORDS}): {s[:70]}..."))
            # A quoted modal is mentioned, not used. The style rule itself names them.
            hit = MODALS.search(re.sub(r'["“][^"”]{1,20}["”]', "X", s))
            if hit:
                findings.append(
                    (at, "ERROR", f'"{hit.group(0)}": use must / must not / can'))
            if "—" in s:
                findings.append((at, "WARN", "em-dash aside: split the sentence"))
    return sorted(findings)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--warn-as-error", action="store_true")
    args = ap.parse_args()

    failed = False
    for path in args.paths:
        for lineno, level, msg in check(path):
            print(f"{path}:{lineno}: {level}: {msg}")
            if level == "ERROR" or args.warn_as_error:
                failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
