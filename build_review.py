#!/usr/bin/env python3
"""Build review.phext: the Automatic Shields review register (eis).

Every deviation the checker (shields.py) finds becomes one flag atom in
review.txt — plain-text blocks separated by a line of ===, fields as
key: value. A flag records the observed behavior, the baseline it
deviates from, an evidence pointer, the source record it was read from,
a timestamp, and a disposition (open until Will or Emise dispositions
it). Edit the text source, never the .phext.

Regenerate:  python3 build_review.py
Check:       python3 build_review.py --check
             (rebuilds in memory; prints CURRENT / DRIFT, exit 0/1)

The Home scroll (1.1.1/1.1.1/1.1.1) is generated: its counts (total
flags, open flags, per-baseline counts) are calculated here from the
flag atoms — rollups are calculated, never hand-written. Flag N
(1-based, in source order) sits at scroll 1.1.1/1.1.1/1.1.(N+1).
Phext implode follows the reference delimiter walk, the same state
machine as the house register builders.
"""
import hashlib
import os
import sys
from collections import Counter

LEVEL_BYTES = [0x01, 0x1F, 0x1E, 0x1D, 0x1C, 0x1A, 0x19, 0x18, 0x17]  # library..scroll
DELIM_SET = set(LEVEL_BYTES)

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(HERE, "review.txt")
OUT_PATH = os.path.join(HERE, "review.phext")
HOME_COORD = "1.1.1/1.1.1/1.1.1"

FIELDS = ("id", "baseline", "observed", "evidence", "source", "timestamp", "disposition")


def parse_coord(s):
    parts = s.replace("/", ".").split(".")
    assert len(parts) == 9, f"coordinate must have 9 components: {s}"
    vals = tuple(int(p) for p in parts)
    assert all(v >= 1 for v in vals), f"no coordinate component below 1: {s}"
    return vals


def implode(scrolls):
    """scrolls: dict coord-string -> text. Reference delimiter walk."""
    items = sorted(((parse_coord(k), v) for k, v in scrolls.items()))
    out = bytearray()
    state = [1] * 9
    for target, text in items:
        for lvl in range(9):
            while state[lvl] < target[lvl]:
                out.append(LEVEL_BYTES[lvl])
                state[lvl] += 1
                for j in range(lvl + 1, 9):
                    state[j] = 1
        assert tuple(state) == target, (state, target)
        out += text.encode()
    return bytes(out)


def parse_source(path):
    if not os.path.exists(path):
        return []
    with open(path) as f:
        raw = f.read()
    blocks, current = [], []
    for line in raw.splitlines():
        if line.strip() == "===":
            if current:
                blocks.append(current)
            current = []
        elif line.lstrip().startswith("#"):
            continue
        else:
            current.append(line)
    if current:
        blocks.append(current)
    records = []
    for block in blocks:
        rec = {}
        for line in block:
            if not line.strip():
                continue
            key, sep, value = line.partition(":")
            assert sep, f"bad source line (want key: value): {line!r}"
            rec[key.strip()] = value.strip()
        if rec:
            records.append(rec)
    return records


def flag_coord(i):
    return f"1.1.1/1.1.1/1.1.{i + 2}"


def render_flag(fl):
    lines = [f"# Flag {fl['id']} — baseline {fl['baseline']}", ""]
    lines.append(f"Observed: {fl['observed']}")
    lines.append(f"Baseline: {fl['baseline']}")
    lines.append(f"Evidence: {fl['evidence']}")
    lines.append(f"Source record: {fl['source']}")
    lines.append(f"Timestamp: {fl['timestamp']}")
    lines.append(f"Disposition: {fl['disposition']}")
    lines.append("")
    return "\n".join(lines)


def render_home(flags):
    open_count = sum(1 for fl in flags if fl["disposition"] == "open")
    per_baseline = Counter(fl["baseline"] for fl in flags)
    lines = [
        "# review.phext — the Automatic Shields review register",
        "",
        "Every flag here is a deviation from a baselines.phext baseline,",
        "found by shields.py in the activity records and recorded for a",
        "mind to disposition: Will, or Emise acting for him. A flag is a",
        "notice, not a verdict — Automatic Shields never blocks. Source",
        "of truth: review.txt beside the builder (build_review.py);",
        "never hand-edit the .phext. Counts below are calculated from",
        "the flag atoms by the builder.",
        "",
        f"Flags recorded: {len(flags)}",
        f"Open flags: {open_count}",
        "",
        "Flags per baseline:",
    ]
    if per_baseline:
        for bid in sorted(per_baseline):
            lines.append(f"- {bid}: {per_baseline[bid]}")
    else:
        lines.append("- (none)")
    lines.append("")
    lines.append("Index (coordinate — flag — baseline — disposition):")
    for i, fl in enumerate(flags):
        lines.append(f"- {flag_coord(i)} — {fl['id']} — {fl['baseline']} — {fl['disposition']}")
    lines.append("")
    return "\n".join(lines)


def build(src_path=SRC_PATH):
    flags = parse_source(src_path)
    ids = [fl["id"] for fl in flags]
    assert len(ids) == len(set(ids)), "duplicate flag ids"
    for fl in flags:
        for field in FIELDS:
            assert fl.get(field), f"flag {fl.get('id')} missing field {field}"
    scrolls = {HOME_COORD: render_home(flags)}
    for i, fl in enumerate(flags):
        scrolls[flag_coord(i)] = render_flag(fl)
    for coord, text in scrolls.items():
        bad = DELIM_SET & set(text.encode())
        assert not bad, f"raw delimiter bytes in scroll {coord}: {bad}"
    return implode(scrolls), flags


def write(blob, out_path=OUT_PATH):
    with open(out_path, "wb") as f:
        f.write(blob)


def main():
    check = "--check" in sys.argv
    blob, flags = build()
    digest = hashlib.sha256(blob).hexdigest()
    if check:
        if os.path.exists(OUT_PATH):
            with open(OUT_PATH, "rb") as f:
                current = hashlib.sha256(f.read()).hexdigest()
            if current == digest:
                print(f"CURRENT: review.phext matches review.txt (sha256 {digest})")
                return 0
        print(f"DRIFT: review.phext does not match review.txt (rebuilt sha256 {digest})")
        return 1
    write(blob)
    print(f"review.phext: {len(flags)} flags + home, {len(blob)} bytes, sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
