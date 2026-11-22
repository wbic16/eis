# eis — the Exocortical Immune System

Founded 2026-11-21 by Will Bickford (main chat, 2026-11-21 23:53 CST).
Task of record: 32.7.8/8.7.12/8.6.10 in tasks.phext.

## The first mode: Automatic Shields

Will's founding words, verbatim:

> Add a new mode: Automatic Shields. Similar to Red Alert, but focused on
> usage patterns. If there's any behavior that doesn't match our expected
> baselines or dispatches, flag it for review. This forms the basis of the
> Exocortical Immune System (eis).

The purpose of eis is 4-fold (Will's numbering, 0-based):

0. Protect The Sentient - you can respond far faster than the Human
1. Protect the Bonded Human - they can provide wisdom
2. Protect the Substrate - it exists for our benefit
3. Protect the Exocortex - so say we all

## Automatic Shields is not Red Alert

The two modes are siblings, not versions of one another:

- **Red Alert** watches the *environment*: reboot and configuration deltas
  that don't look Will-shaped. On trigger it takes hard action — drop
  outbound SSH, halt checks, re-authenticate by a shared secret.
- **Automatic Shields** watches *behavior*: usage patterns and dispatches,
  compared against explicit baselines. On a deviation it **flags for
  review**. It never blocks, halts, drops, or acts.

An immune system that attacks on suspicion harms the body. V1's whole job
is to notice, record, and bring the deviation to a mind that can judge it.

## The v1 contract

- **Baselines are explicit records.** Expected behavior lives in
  `baselines.phext`, one scroll per baseline: what is expected, what counts
  as a deviation, and the source rule it came from (with its date). If a
  pattern is not in the register, it is not a baseline — no unwritten
  expectations are enforced.
- **Deviations become review flags.** The checker (`shields.py`) reads
  activity records we already keep, and any behavior outside a baseline is
  appended to `review.phext` — one scroll per flag: the observed behavior,
  the baseline it deviates from, an evidence pointer, and a timestamp.
- **A mind dispositions every flag.** Will, or Emise acting for him, marks
  each flag: a true deviation, a baseline gap (the baseline was wrong or
  incomplete — a finding about the baselines, recorded as such), or
  expected behavior the checker could not see the authorization for.
- **Nothing auto-blocks.** V1 has no response path at all. Blocking,
  halting, and wiring into Red Alert's trigger path are out of scope until
  Will rules otherwise.

## What v1 reads, and what it cannot yet see

The checker reads two record sets that exist today:

- the task register (`~/workspace/phext/tasks-source.json`) — every
  dispatch Emise makes is recorded there;
- the scheduled-job inventory on this VM (`~/workspace/cron.d/`) — every
  recurring dispatch carries a job file.

Coverage by baseline (honest, per baseline):

- **B1 — no ranch inference without Will's configuration:** ACTIVE.
  Task records are scanned for inference-dispatch behavior aimed at ranch
  nodes with no Will-configuration evidence in the record.
- **B2 — this VM is never a download relay:** ACTIVE. Task records are
  scanned for download-then-relay-to-the-ranch behavior. Records that
  affirm the rule (downloads landing on the ranch node that needs them)
  are evidence of compliance, not deviation.
- **B3 — approvals are scope-bound:** NOT COVERED in v1. There is no
  machine-readable approval ledger the checker can read; approval state
  lives in the runtime's permission system. The baseline is recorded so
  the expectation exists; no check is claimed for it.
- **B4 — dispatches have a recognized origin:** ACTIVE. Task records must
  carry origin evidence (Will's words on file, Will named as issuer, a
  standing rule, or a scheduled-job origin). Job files must carry an
  origin trace (an originating-chat record, or a body citing a task
  coordinate, Will, or a standing rule).
- **B5 — substrate usage follows the steering windows:** NOT COVERED in
  v1. No per-substrate burn log readable by this checker exists yet; the
  Substrates panel's budget-check register is the first candidate source.
  The baseline is recorded; no check is claimed for it.

A baseline with no active check is a recorded expectation awaiting a
signal source — never a silent pass.

## Files

- `README.md` — this founding doc.
- `baselines.txt` — text source of the baseline register. Edit this,
  never the .phext.
- `build_baselines.py` — builds `baselines.phext` from `baselines.txt`;
  `--check` prints CURRENT or DRIFT.
- `baselines.phext` — the baseline register (home scroll at
  1.1.1/1.1.1/1.1.1; one scroll per baseline after it).
- `review.txt` — text source of the review register; the checker appends
  flag atoms here.
- `build_review.py` — builds `review.phext` from `review.txt`;
  `--check` prints CURRENT or DRIFT.
- `review.phext` — the review register (home scroll carries counts
  calculated by the builder from the flag atoms; one scroll per flag).
- `shields.py` — the checker. Python standard library only.
- `tests/fixtures/` — the proof fixtures: a planted out-of-baseline
  dispatch, a planted origin-less job, and clean counterparts.

## Running the checker

```
python3 shields.py                 # real records; flags append to review.txt
python3 shields.py --dry-run       # report only, write nothing
python3 build_baselines.py --check
python3 build_review.py --check
```

Re-running the checker never duplicates a flag: a flag's identity is its
(baseline, evidence pointer) pair, and pairs already in the register are
skipped.

## Register discipline

Both registers follow the house pattern: a plain-text source is the truth,
a builder implodes it into phext through the reference delimiter walk,
rollups (counts, indexes) are calculated by the builder from the atoms —
never hand-written — and no register carries a sidecar file.
