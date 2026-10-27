---
title: "Filing-Events Study — Identity and Price-Spike Review"
subtitle: "Findings from review pack v1 and the proposed price masks · version 1"
date: "27 October 2026"
---

**Status:** proposals for owner sign-off. This is the last lock precondition (r6/r7 item 3). Raw output: `results/2026-10-27_FE_Review_Pack_v1.{md,json}`; rule-based proposals: `results/2026-10-27_FE_Proposed_Price_Masks_v1.csv`. The review pack read the database read-only and computed no returns.

# Bottom line

- **Spikes barely touch the study.** 611 reversing one-day moves found; only **39** fall on a stock that was eligible the day before (so they enter the benchmark), **0** fall inside any event's reaction window (days 0 to +2), and **5** fall inside a holding window. The $2 and dollar-volume screen already keeps almost all of them out.
- **Recommendation: mask all 611 anyway**, as the rule fixed in advance says: one day each, turning each round trip into its compounded two-day return. It removes the 39 benchmark distortions and the 5 holding-window ones at no cost.
- **Identity flags: 6 masks, 260 no action.** The mechanical rule proposed 12 splices, but checking them against SEC's former-name dates showed only 2 breaks in the right place. I corrected 4 to SEC's documented change dates and dropped 6 that are the same company earlier in its life.
- **No whole ticker is excluded.** Total: 617 rows in `config/smallcap_price_masks.csv` (change D10e).

# Spikes (rule S)

| | Count |
|---|---|
| Candidates (up > 80% then down > 40%, or down > 45% then up > 80%) | 611 |
| With bad-print evidence (zero or very low volume, flat bar, decimal shift) | 282 |
| Other reverting moves | 329 |
| Eligible the day before (enter the benchmark) | 39 (1 bad-print, 38 other) |
| Inside an event's reaction window | 0 |
| Inside an event's holding window | 5 (FLNA 2018-10-03, GSAT 2008-12-10, MBRX 2019-04-22, PRPO 2020-07-30, XWEL 2019-06-26) |

The candidate set is wider than readiness v1's 287 because v1 first kept only moves above 80% in size, which dropped falls of 45–80% that rebounded more than 80%. The review-pack rule, written before its run, includes them. Many of the eligible cases are the March 2020 crash and rebound (preferred shares, closed-end funds) or meme-stock days in 2020–21: real prices, but masking only replaces the two-day path with its compounded result, which is the right quantity for a study that sums daily returns.

One side effect: a masked day leaves a gap in the 20-day dollar-volume average, so that stock is ineligible for about 20 sessions afterwards. With 39 eligible cases this costs a handful of events at most.

# Identity flags (rule I, then hand check)

| Ticker | Rule said | Hand check | Mask |
|---|---|---|---|
| ABTC (Akerna) | splice to 2019-06-18 | correct: MTech SPAC era, +235% at the de-SPAC | first price to 2019-06-18 |
| REKR (Rekor) | splice to 2017-09-05 | correct: first sessions after the Novume formation | first price to 2017-09-05 |
| NAUT (Nautilus) | splice to 2021-02-07 | wrong date: SPAC era ran to the merger | to 2021-06-08 (SEC former name ARYA III) |
| CLNN (Clene) | splice to 2021-02-02 | wrong date: masked real Clene trading | to 2020-12-18 (SEC name change) |
| INDP (Indaptus) | splice to 2019-07-21 | wrong date: Intec Pharma history to the merger | to 2021-08-03 (SEC former name Intec Parent) |
| COSM (Cosmos) | splice to 2010-08-22 | wrong date: shell history to the reverse merger | to 2013-10-30 (Cosmos Holdings name from 2013-10-31) |
| OPBK, LFMD, BNTC, OPRX, LILAK, XTIA | splice | same company earlier in its life (OTC trading, ADRs, tracking stock); the "break" was a real move | none |
| 254 others | no break near the first SEC filing | — | none |

Why the remaining flags are harmless: the registrant's events are its own filings, so they can only fall after its first SEC filing. The price history before that belongs to the same security under a predecessor (OTC years, a mid-tier holding company, ADRs) and can only enter the benchmark. Where that history belonged to a different economic entity (SPAC trusts, shells, a merger partner), the six masks remove it.

CLNN's date is SEC's name-change date; the merger closed a few days later (to confirm on EDGAR). The few unmasked SPAC days that leaves are immaterial.

# What the owner is asked to approve (one decision)

1. **Change D10e** (engine reads `config/smallcap_price_masks.csv`) **with the 617 masks** and protocol draft r7 (records this review; comment-only).
2. **Then the lock:** `research/filing_events_v1.toml` = draft r7 body with a pre-registration header (parameters identical, checked), its hash written to `config/protocols.lock`.

Runners: `05_Proposed_Changes/APPLY_FE_D10e_masks_and_run_readiness_v4.bat` (reversible; runs readiness v4 with the masks applied), then, only after I confirm v4, `05_Proposed_Changes/LOCK_FE_protocol_filing_events_v1.bat` (asks you to type LOCK).
