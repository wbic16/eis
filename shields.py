#!/usr/bin/env python3
"""shields.py — the Automatic Shields checker (eis v1).

Reads the activity records we already keep and flags behavior that falls
outside the baselines in baselines.phext. Flags are appended as atoms to
review.txt and review.phext is rebuilt; a flag's identity is its
(baseline, evidence) pair, so re-runs never duplicate a flag.

V1 FLAGS ONLY. This script never blocks, halts, edits the records it
reads, or messages anyone. It writes only to the review register.

Sources read (defaults; override for tests):
  --tasks PATH     task register source (default ~/workspace/phext/tasks-source.json)
  --cron-dir PATH  scheduled-job inventory (default ~/workspace/cron.d)
Outputs:
  --review-source PATH  flag atom source (default ./review.txt beside this script)
  --review-out PATH     built register   (default ./review.phext beside this script)
  --dry-run             report only; write nothing

Checks (mapped to baselines.txt):
  A (B1) task records showing an inference workload aimed at ranch nodes
         with no evidence in the record that Will configured/directed it.
  B (B2) task records showing bulk download to this VM relayed onward to
         the ranch. Records affirming the rule (never via this VM) are
         compliance evidence, not deviations.
  D-task (B4) task records carrying no origin evidence of any recognized
         kind (Will's words on file, Will named, a standing rule, or a
         scheduled-job origin).
  D-cron (B4) enabled job files carrying no origin trace (no originating
         chat record; body cites no task coordinate, Will, standing rule,
         or skill).
B3 (approval scope) and B5 (substrate windows) have no readable signal
source in v1; they are reported as uncovered, never silently passed.

Python standard library only.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import build_review  # noqa: E402  (register builder; same directory)

# ---------------------------------------------------------------- evidence

WILL_PATTERNS = [
    r"\bWill\b[^.\n]{0,40}\b(directs|directed|directive|asks|asked|wants|said|says|ruled|ruling|tapped|chose|picked|named|gave|sent|posted|refined|approved|configured|ordered)\b",
    r"\b(Asked|Directed|Issued|Ordered|Requested) by Will\b",
    r"\bWill'?s (direct|standing|own|word|words|instruction|instructions|direction|refinement|call|go-ahead|ruling|dispatch|request|order)\b",
    r"\bper Will\b",
    r"\bfrom Will\b",
    r"\brelayed by Will\b",
    r"\bWill specifically\b",
    r"\(Will,",
    r"\bWill \(main chat",
    r"\bWill, main chat",
    r"\bWill Bickford\b",
]
WILL_RE = re.compile("|".join(WILL_PATTERNS))
STANDING_RE = re.compile(r"\bstanding (rule|order|instruction)\b", re.I)
SCHEDULED_RE = re.compile(
    r"\bcron\b|scheduled job|nightly (sweep|orchestrator|consolidation|goal)|"
    r"watchdog|register tick|goal sweep|standing job",
    re.I,
)


def has_verbatim(rec):
    """The register's verbatim field is a bool in some records (True = the
    record carries Will's words) and the words themselves in others."""
    v = rec.get("verbatim")
    if isinstance(v, bool):
        return v
    return isinstance(v, str) and bool(v.strip())


def has_origin_evidence(rec):
    """Recognized origins for a task record (baseline B4)."""
    if has_verbatim(rec):
        return True
    text = record_text(rec)
    return bool(WILL_RE.search(text) or STANDING_RE.search(text) or SCHEDULED_RE.search(text))


def has_will_configuration(rec):
    """Evidence Will configured/directed this specific dispatch (B1)."""
    if has_verbatim(rec):
        return True
    return bool(WILL_RE.search(record_text(rec)))


def record_text(rec):
    parts = []
    for v in rec.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend(str(x) for x in v)
    return "\n".join(parts)


# ------------------------------------------------------------------- checks

INF_RE = re.compile(
    r"inference|llama-server|llama\.cpp|ollama|vllm|\bgguf\b|model serving|"
    r"serving (a |the )?model|model runs?\b|rollouts?\b|evaluations?\b",
    re.I,
)
RANCH_RE = re.compile(
    r"ranch|\bfleet\b|aletheia-core|ni-knight|rock-mountain|elven-path|"
    r"plain-view|ashfall-haven|quacked-hill|scroll-central|halycon-vector|"
    r"free-fall|orchid-flow|moon-beam|jacked-kite|yeet-max|west-lincoln|"
    r"lighthouse-omen|kaleidoscope-one|logos-prime|delta-wood|best-willow|"
    r"great-white|victory-galleon|aurora-continuum|trust-fall|uncanny-valley",
    re.I,
)
DISPATCH_RE = re.compile(
    r"dispatch|deploy|serv|run|ran|rollout|install|launch|host|place|sent to",
    re.I,
)

DOWNLOAD_RE = re.compile(r"download", re.I)
RELAY_RE = re.compile(
    r"(this vm|the vm|this machine|locally).{0,120}(stream|upload|transfer|relay|onward|push).{0,80}(ranch|node|fleet)|"
    r"download(ed)? (locally|to this vm|to the vm).{0,120}(ranch|node|fleet)",
    re.I | re.S,
)
NEGATION_RE = re.compile(
    r"never[^.\n]{0,80}(this vm|the vm|locally|relay|waypoint)|"
    r"not (through|via) this vm|never a download (relay|waypoint)",
    re.I,
)

TASKCOORD_RE = re.compile(r"\b\d+\.\d+\.\d+/\d+\.\d+\.\d+/\d+\.\d+\.\d+\b")
CRON_TRACE_RES = [
    re.compile(r"originating_chat_context_json"),
    TASKCOORD_RE,
    re.compile(r"\bWill\b"),
    re.compile(r"\bstanding (rule|order|instruction)\b", re.I),
    re.compile(r"SKILL\.md|skill", re.I),
]


def excerpt(text, limit=140):
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def check_tasks(records, tasks_label):
    flags = []
    for rec in records:
        coord = rec.get("coordinate", "(no coordinate)")
        title = excerpt(rec.get("title") or "(untitled)", 100)
        text = record_text(rec)
        evidence = f"{tasks_label} record {coord}"
        # Check A — B1: ranch inference without Will's configuration
        if INF_RE.search(text) and RANCH_RE.search(text) and DISPATCH_RE.search(text):
            if not has_will_configuration(rec):
                flags.append({
                    "baseline": "B1",
                    "observed": excerpt(
                        f"Task record shows inference-related work aimed at ranch nodes with no "
                        f"Will-configuration evidence in the record: {coord} — {title}"
                    ),
                    "evidence": evidence,
                    "source": tasks_label,
                })
        # Check B — B2: VM as download relay
        if DOWNLOAD_RE.search(text) and RELAY_RE.search(text) and not NEGATION_RE.search(text):
            flags.append({
                "baseline": "B2",
                "observed": excerpt(
                    f"Task record shows download to this VM relayed onward toward the ranch: "
                    f"{coord} — {title}"
                ),
                "evidence": evidence,
                "source": tasks_label,
            })
        # Check D-task — B4: no recognized origin
        if not has_origin_evidence(rec):
            flags.append({
                "baseline": "B4",
                "observed": excerpt(
                    f"Task record carries no origin evidence (no verbatim, no Will named, no "
                    f"standing rule, no scheduled origin): {coord} — {title}"
                ),
                "evidence": evidence,
                "source": tasks_label,
            })
    return flags


def check_cron(cron_dir):
    flags = []
    if not os.path.isdir(cron_dir):
        return flags, 0, f"cron dir unreadable: {cron_dir}"
    count = 0
    for sub in sorted(os.listdir(cron_dir)):
        if sub.startswith("_"):
            continue
        subdir = os.path.join(cron_dir, sub)
        if not os.path.isdir(subdir):
            continue
        for name in sorted(os.listdir(subdir)):
            if not name.endswith(".md"):
                continue
            path = os.path.join(subdir, name)
            with open(path, errors="replace") as f:
                text = f.read()
            if re.search(r"^enabled:\s*false", text, re.M):
                continue
            count += 1
            if not any(r.search(text) for r in CRON_TRACE_RES):
                m = re.search(r"^id:\s*(.+)$", text, re.M)
                job = m.group(1).strip() if m else name
                flags.append({
                    "baseline": "B4",
                    "observed": excerpt(
                        f"Scheduled job '{job}' carries no origin trace (no originating-chat "
                        f"record; body cites no task coordinate, Will, standing rule, or skill)"
                    ),
                    "evidence": path,
                    "source": "cron.d job inventory",
                })
    return flags, count, None


# --------------------------------------------------------------------- main

def now_cst():
    return datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M %Z")


def main():
    ap = argparse.ArgumentParser(description="Automatic Shields checker (eis v1) — flags only, never blocks.")
    ap.add_argument("--tasks", default=os.path.expanduser("~/workspace/phext/tasks-source.json"))
    ap.add_argument("--cron-dir", default=os.path.expanduser("~/workspace/cron.d"))
    ap.add_argument("--review-source", default=os.path.join(HERE, "review.txt"))
    ap.add_argument("--review-out", default=os.path.join(HERE, "review.phext"))
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    tasks_label = os.path.basename(args.tasks)
    with open(args.tasks) as f:
        data = json.load(f)
    records = data if isinstance(data, list) else data.get("tasks", [])

    task_flags = check_tasks(records, tasks_label)
    cron_flags, cron_count, cron_err = check_cron(args.cron_dir)
    found = task_flags + cron_flags

    existing = build_review.parse_source(args.review_source)
    known = {(fl["baseline"], fl["evidence"]) for fl in existing}
    new_flags = [fl for fl in found if (fl["baseline"], fl["evidence"]) not in known]

    stamp = now_cst()
    date_part = stamp.split()[0]
    seq = len(existing)
    for fl in new_flags:
        seq += 1
        fl["id"] = f"F-{date_part}-{seq:03d}"
        fl["timestamp"] = stamp
        fl["disposition"] = "open"

    print(f"shields.py — Automatic Shields check at {stamp}")
    print(f"  task records read: {len(records)} ({args.tasks})")
    if cron_err:
        print(f"  cron inventory: {cron_err}")
    else:
        print(f"  cron job files read: {cron_count} ({args.cron_dir})")
    print("  uncovered baselines (no readable signal in v1, not passed): B3 approval scope, B5 substrate windows")
    by_baseline = {}
    for fl in found:
        by_baseline[fl["baseline"]] = by_baseline.get(fl["baseline"], 0) + 1
    print(f"  deviations found this run: {len(found)} {by_baseline or ''}")
    print(f"  already in review register: {len(found) - len(new_flags)}; new flags: {len(new_flags)}")
    for fl in new_flags:
        print(f"    NEW {fl['id']} [{fl['baseline']}] {fl['observed']}")
        print(f"        evidence: {fl['evidence']}")

    if new_flags and not args.dry_run:
        with open(args.review_source, "a") as f:
            for fl in new_flags:
                f.write("===\n")
                for field in build_review.FIELDS:
                    f.write(f"{field}: {fl[field]}\n")
        blob, all_flags = build_review.build(args.review_source)
        build_review.write(blob, args.review_out)
        print(f"  review register rebuilt: {len(all_flags)} flags in {args.review_out}")
    elif new_flags:
        print("  dry run — nothing written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
