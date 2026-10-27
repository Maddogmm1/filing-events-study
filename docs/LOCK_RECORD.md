---
title: "Filing-Events Study — Protocol Lock Record"
subtitle: "filing_events_v1 pre-registered · version 1"
date: "27 October 2026"
---

**Locked:** 27 Oct 2026 17:47 (UK), by the owner, with approval recorded at 17:39 (Owner Decisions Record v4).

| Item | Value |
|---|---|
| Protocol | `research/filing_events_v1.toml` (byte-identical copy in this repository) |
| SHA-256 | `e3f4a2fd392ed012268c559bc46de4b0f4be43bcc7174c3ef3d8b6ed1b2fe67d` (checked: the file's hash equals the lock entry) |
| Lock entry | `config/protocols.lock` (the existing `m6_replication_v1` entry is unchanged) |
| Commits | branch `fe/d10-data-readiness`: lock candidate (protocol file), then `bda7cfe` "Lock FE protocol filing_events_v1" (lock file). `main` untouched |
| Status after lock | locked: True; development trials used 0 of 17; sealed window SEALED |
| Source | draft r7 body, unchanged; only the header comments differ |
| Code it depends on | D10a–D10e on `fe/d10-data-readiness`; 617 rows in `config/smallcap_price_masks.csv` |

**Preconditions met:** verified acceptance times 100%; G7 replaced by the r6 label-error allowance; identity and spike review done (617 masks, no whole ticker excluded); readiness re-run with every change applied (v4, clean).

**Frozen run order (17 development trials):** P1 H1, P2 H1S, P3 H2A, P4 H2B, P5 H2, P6 H3, E1 H2C (exploratory); V1 H1 hold 20, V2 H2A hold 20, V3 H2B hold 20, V4 H1 decile 0.95, V5 H1 entry at open, V6 placebo (random 10% of eligible earnings events), V7 placebo other 8-Ks (lapses: those filings were not built before lock), V8 H1S hold 120, V9–V10 reserve. A lapsed slot is never reassigned.

**What the lock means:** any edit to the protocol file voids it; every run is recorded in the trial registry and counts against the 17; validation is used only after development, and the 2022+ window can be opened once, only for a hypothesis that passed both. Expected verdicts from readiness: H1/H1S testable; every H2 cell below the 1,840 minimum, so H2 results are a negative screen and description only.
