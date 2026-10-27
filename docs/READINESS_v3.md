---
title: "Filing-Events Study — Data-Readiness Report"
subtitle: "After change D10d (rule r2, label-error allowance) · version 3"
date: "27 October 2026"
---

**Status:** DRAFT FOR OWNER REVIEW. **Not ready to lock.** D10d is applied and verified. The only open lock precondition is the identity and price-spike review (below).

**What was run:** `APPLY_FE_D10d_and_run_readiness_v3.bat` on the author's machine (27 Oct 2026, 16:51–16:56 UTC). Patch applied as commit `86edd93` on `fe/d10-data-readiness` (`main` untouched; database copied to `smallcap.duckdb.bak-2026-10-27`); 205 tests passed; then `fe_readiness_v3.py`, read-only, counts only. **No strategy return, abnormal return or backtest was computed.** Raw output: `results/2026-10-27_FE_Readiness_Report_v3.{md,json}`; apply log in `05_Proposed_Changes/`.

# Results

| Check | Result |
|---|---|
| P0 Patch | **PASS**: `sc_delistings` uses rule r2 (schema 4); r6 allowance 0.10 loaded. All companies with an exit record: unknown 23,233, acquired 4,346, listing failure 2,350, bankruptcy 870, acquired_inferred 848 |
| T1 Verified times | **PASS**: 96,439 of 96,439 in-scope filings; fixture 109 / 109 |
| Expected positions | Unchanged within 1%: H1 4,615 (development) / 1,979 (validation) against 1,840; every H2 cell still below it |
| Unverified exclusions | 57,175, of which **0 in the D10c scope**: none could have been eligible. The reporting fix confirms the v2 reading |
| B1 Bound shifts | Allowance: **−0.04 to −0.08 points**. Label-free sensitivity: a further **−0.34 to −0.76 points**. Margin: 1 point |

# What B1 means

The adverse survivorship bound must stay at least 1 point (half the 2% threshold) on the predicted side. In percentage points of 60-session net return per position:

| Window | Hypothesis | Inside-window exits (failure / acquired / unknown) | Allowance shift | Label-free extra shift |
|---|---|---|---|---|
| Development | H1 / H1S | 618 / 1,738 / 995 | −0.07 | −0.62 |
| Validation | H1 / H1S | 107 / 580 / 39 | −0.08 | −0.76 |
| Development | H2 combined | 431 / 138 / 586 | −0.04 | −0.35 |
| Validation | H2 combined | 62 / 21 / 62 | −0.04 | −0.36 |

- **The 10% allowance costs almost nothing** (under a tenth of a point everywhere). The decision to use it, rather than gating on label accuracy, has no practical downside.
- **The labels do matter for H1.** If no label were trusted, the adverse bound for H1 would fall by a further 0.6–0.8 points, most of the 1-point margin, because most of H1's inside-window exits are acquisitions (1,738 of 3,351 in development). The two audits found no acquisition label that was really a failure (0 of 35), which is why r6 keeps the labels with an allowance and reports the label-free bound only as a sensitivity.
- Shifts are computed from counts with the engine's own arithmetic; the actual bounds will exist only when the study runs after lock.

# One finding that raises the priority of the spike review

The engine builds abnormal returns as **sums of daily simple returns** against a daily equal-weight benchmark (`events_frame`, `build_market`). A one-day bad print that reverses (for example +100% then −50%) therefore adds about **+50 points** to that stock's summed abnormal return instead of roughly zero. Inside days 0 to +2 it can lift an earnings event into H1's top decile by itself; inside a holding window it distorts the position's return. The 287 reversing spikes from readiness v1 are therefore a correctness issue for H1, not just tidiness. The identity cases matter less: events come only from the current registrant and fall after its first filing, so the main risk there is a spliced price series, which shows up as a large break.

# Next step

A review pack (read-only script plus a proposed engine change) is prepared:

- **`fe_review_v1.py`** collects the evidence for the 287 reversing spikes (bars around each, volume against its 20-day median, whether it reverts to within 15% of the prior close) and for all 266 identity flags (SEC filing history and former names, largest price gap and largest jump), and applies **rules fixed before seeing that evidence**. The output is a proposed mask list for owner sign-off. Nothing is applied.
- **Change D10e (proposed, needs approval):** `config/smallcap_price_masks.csv` (ticker, date range, reason, evidence). Masked days become missing prices, so the engine treats them as untraded (return frozen, then measured from the last good price) instead of dropping whole tickers. Empty file = no effect.

Still no backtests and no 2022+ data until the protocol is locked.
