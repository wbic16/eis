#!/usr/bin/env python3
"""Build baselines.phext: the Automatic Shields baseline register (eis).

Source of truth: baselines.txt beside this script — plain-text blocks
separated by a line of ===, fields as key: value. Edit the text source,
never the .phext; rebuild after every edit.

Regenerate:  python3 build_baselines.py
Check:       python3 build_baselines.py --check
             (rebuilds in memory; prints CURRENT / DRIFT, exit 0/1)

The Home scroll (1.1.1/1.1.1/1.1.1) is generated: it carries the founding
line and an index of every baseline. Counts are calculated here from the
source atoms, never hand-written. Baseline N (1-based, in source order)
sits at scroll 1.1.1/1.1.1/1.1.(N+1). Phext implode follows the reference
delimiter walk (the 9 phext delimiters, coordinates 1-indexed), the same
state machine as the house register builders.
"""
import hashlib
import os
import sys

LEVEL_BYTES = [0x01, 0x1F, 0x1E, 0x1D, 0x1C, 0x1A, 0x19, 0x18, 0x17]  # library..scroll
DELIM_SET = set(LEVEL_BYTES)

HERE = os.path.dirname(os.path.abspath(__file__))
SRC_PATH = os.path.join(HERE, "baselines.txt")
OUT_PATH = os.path.join(HERE, "baselines.phext")
HOME_COORD = "1.1.1/1.1.1/1.1.1"


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


def baseline_coord(i):
    return f"1.1.1/1.1.1/1.1.{i + 2}"


def render_baseline(b):
    lines = [f"# Baseline {b['id']} — {b['name']}", ""]
    lines.append(f"Expected: {b['expected']}")
    lines.append(f"Deviation: {b['deviation']}")
    lines.append(f"Source: {b['source']}")
    lines.append(f"Check: {b['check']}")
    lines.append("")
    return "\n".join(lines)


def render_home(baselines):
    lines = [
        "# baselines.phext — the Automatic Shields baseline register",
        "",
        "Automatic Shields (eis, founded by Will 2026-11-21) watches usage",
        "patterns and dispatches against the baselines recorded here, and",
        "flags deviations for review. It never blocks. Each baseline is one",
        "scroll: what is expected, what counts as a deviation, and the",
        "source rule it came from. Source of truth: baselines.txt beside",
        "the builder (build_baselines.py); never hand-edit the .phext.",
        "",
        f"Baselines recorded: {len(baselines)}",
        "",
        "Index (coordinate — id — name — check):",
    ]
    for i, b in enumerate(baselines):
        lines.append(f"- {baseline_coord(i)} — {b['id']} — {b['name']} — {b['check'].split(' — ')[0]}")
    lines.append("")
    return "\n".join(lines)


def build():
    baselines = parse_source(SRC_PATH)
    ids = [b["id"] for b in baselines]
    assert len(ids) == len(set(ids)), "duplicate baseline ids"
    for b in baselines:
        for field in ("id", "name", "expected", "deviation", "source", "check"):
            assert b.get(field), f"baseline {b.get('id')} missing field {field}"
    scrolls = {HOME_COORD: render_home(baselines)}
    for i, b in enumerate(baselines):
        scrolls[baseline_coord(i)] = render_baseline(b)
    for coord, text in scrolls.items():
        bad = DELIM_SET & set(text.encode())
        assert not bad, f"raw delimiter bytes in scroll {coord}: {bad}"
    return implode(scrolls), baselines


def main():
    check = "--check" in sys.argv
    blob, baselines = build()
    digest = hashlib.sha256(blob).hexdigest()
    if check:
        if os.path.exists(OUT_PATH):
            with open(OUT_PATH, "rb") as f:
                current = hashlib.sha256(f.read()).hexdigest()
            if current == digest:
                print(f"CURRENT: baselines.phext matches baselines.txt (sha256 {digest})")
                return 0
        print(f"DRIFT: baselines.phext does not match baselines.txt (rebuilt sha256 {digest})")
        return 1
    with open(OUT_PATH, "wb") as f:
        f.write(blob)
    print(f"baselines.phext: {len(baselines)} baselines + home, {len(blob)} bytes, sha256 {digest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
