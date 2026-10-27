---
title: "Filing-Events Study — Data-Readiness Report"
subtitle: "Verified acceptance times, survivorship split and delisting-cause audit · version 2"
date: "27 October 2026"
---

**Status:** DRAFT FOR OWNER REVIEW. **Not ready to lock.** The timestamp defect is fixed and verified. Two lock preconditions remain open (the G7 reading, and the identity and price-spike reviews), and one new finding needs an owner decision before lock: the survivorship gap is first-order for H1, not only for H2.

**What was run:** `fe_readiness_v2.py` on the author's machine (27 Oct 2026, 15:22 UTC), branch `fe/d10-data-readiness` with the D10a/b/c patches, database opened read-only, every query limited to dates before 2022-01-01. Counts and data quality only. **No strategy return, abnormal return or backtest was computed.** Raw output: `results/2026-10-27_FE_Readiness_Report_v2.{md,json}`. G7 hand classification: `2026-10-27_FE_G7_Hand_Classification_v1.md`.

# Bottom line

1. **True acceptance times are in place (T1 PASS).** 96,439 filings in scope; 96,412 (99.97%) carry the time read from SEC's index page. The 109 fixture filings present in the table match SEC's time exactly. 27 filings failed with HTTP 503 (SEC busy) and need a resumable rerun.
2. **The defect was larger than the 300-filing sample suggested.** Across the whole verified population, stored times were **UTC for 38.0%**, **double-converted for 61.9%** and **correct New York time for only 0.13%**. The double-converted share rises steadily from 53% (2004) to 69% (2021). The sample's "53% correct" came from its stratification, not the population.
3. **No look-ahead, but 27.7% of day-0s were one session late.** With true times, 72.3% of events keep their day 0 and 27.7% move one session earlier; none move later (0% look-ahead). The share is similar for every event kind (earnings 27.9%, late filings 24.5%, auditor changes 23.6%, non-reliance 20.0%). So without D10c, H1's reaction window and entry would have been mis-timed for more than one event in four.
4. **H1 is still count-feasible; H2 is not.** Expected positions under r5 with verified times: H1 development 4,614, validation 1,979, against the 1,840 minimum. Every H2 cell, including the late-filing plus non-reliance combination (991 / 439), is below it. H2 stays a negative screen plus descriptive study.
5. **New: the survivorship gap is first-order for H1 too.** Among earnings events of companies that were exchange-listed at the time, **only 42% (development) and 67% (validation) have prices.** Almost all the rest belong to companies that delisted *after* the event window, so the bounds in the engine (which cover exits *inside* the window) do not reach them. See S1 below.
6. **G7 delisting-cause audit:** the rule agrees with the hand classification on **38 of 39** cases at the level the engine uses (failure vs acquired, 97.4%) but on **34 of 39** at the strict cause label (87.2%). The precondition does not say which reading counts; the owner should decide (recommendation below).

# Gate results

| Gate | Result | Evidence |
|---|---|---|
| T1 Verified times | **PASS** | 99.97% verified (rule: ≥ 99%); fixture 109 / 109 identical; 27 HTTP 503 outstanding |
| T2 Stored-versus-SEC offsets | Reported | UTC 38.0%, double conversion 61.9%, New York 0.13%; no other offsets |
| T3 Day-0 changes | Reported; **no look-ahead** | Same session 72.3%, one session late 27.7%, early 0.0% |
| G9v2 Expected positions | H1 enough; H2 inconclusive | Table below |
| S1 Survivorship split | **New finding** | Table below |
| G7 Delisting-cause audit | **Owner decision** | 97.4% (class) / 87.2% (label) on the 39 cases with a rule cause; 11 "unknown" |

## G9v2 Expected positions (r5 settings, verified times only)

| Hypothesis | Development | Validation | Minimum | Verdict possible? |
|---|---|---|---|---|
| H1 / H1S (top-decile earnings) | 4,614 | 1,979 | 1,840 | **Yes** (validation margin 7.6%) |
| H2A late filings | 806 | 392 | 1,840 | No |
| H2B non-reliance | 354 | 128 | 1,840 | No |
| H2C auditor change | 635 | 378 | 1,840 | No (exploratory anyway) |
| H2 combined (late + non-reliance) | 991 | 439 | 1,840 | No |

These match v1 within about 1%, so the verified times did not change feasibility. The report also lists 57,202 events "excluded for lack of a verified time" (earnings 49,662). Only 27 in-scope filings lack a verified time, and the D10c scope was every event that passes the eligibility screen under any of the three candidate times, so these 57,202 fail the screen under every candidate time and would not have been eligible anyway; the eligible counts above are unaffected. **Reporting fix proposed:** the engine should count as "excluded" only events that would otherwise have been eligible, so the log does not overstate the loss.

## S1 Survivorship split (events whose company was exchange-listed at the event)

"Listed at the event" = priced, plus no price but an exchange delisting (Form 25 / 25-NSE) after the event. Companies already off-exchange, deregistered with no Form 25, or with no exit record are left out: most of those could not have been bought through Trading 212 at the time.

| Window | Kind | Listed at event | With prices | Delisted after the window, no prices | Delisted inside the window |
|---|---|---|---|---|---|
| Development | Earnings (H1) | 228,873 | **42.2%** | 56.6% | 1.2% |
| Development | Late filing | 11,623 | 29.7% | 66.3% | 4.0% |
| Development | Non-reliance | 2,972 | 26.9% | 71.2% | 1.9% |
| Development | Auditor change | 5,596 | 33.7% | 64.3% | 2.0% |
| Validation | Earnings (H1) | 65,119 | **66.9%** | 32.0% | 1.1% |
| Validation | Late filing | 2,304 | 51.1% | 45.7% | 3.2% |
| Validation | Non-reliance | 622 | 48.2% | 50.0% | 1.8% |
| Validation | Auditor change | 1,317 | 60.2% | 38.4% | 1.4% |

Shares are of all events before the dollar-volume screen, which cannot be applied to companies without prices. Pre-2005 delistings have no Form 25 on EDGAR and so are not counted; the true missing share is if anything larger.

**What it means.** The price source (Yahoo) holds mainly companies that still trade or delisted recently. A company that was listed when it reported earnings in, say, 2008 and was acquired or failed in 2012 is missing from the sample entirely, not just at its exit. The current bounds assume every priced event is the population and only widen the result for exits inside the 60-session window (1.2% of listed events). They cannot correct for the 57% of development earnings events that are simply absent.

**Direction is not known in advance.** The missing companies include later acquisitions (often good news) and later failures (bad news). The mechanism, not the sign, is what can be stated: the priced sample conditions on surviving long enough to be in today's price source, and the abnormal-return benchmark is built from the same survivor universe, which absorbs part (not all) of the effect. Validation (2018–2021) is far less affected than development.

**Consequences:**

- The D9 decision (delisted-price source) is now relevant for H1, not only H2. The £0 options are the Norgate free trial (100-company check of how many of the missing companies it covers) and the WRDS enquiry the owner has already sent.
- Before lock, the protocol should state that H1 results describe "companies with surviving price history", and add a **pre-registered check**: the H1 result computed separately on validation (67% coverage) and development (42%). A large gap between the two would be read as survivorship, not as decay. This is a protocol note, not a new trial.

## G7 Delisting-cause audit (50 companies)

Full table and evidence: `2026-10-27_FE_G7_Hand_Classification_v1.md`.

- **Acquired (21):** 21 / 21 in the acquired class; 2 are strictly a reorganisation and a SPAC combination (holders exit at market value).
- **Bankruptcy (8):** 8 / 8 in the failure class; 2 are strictly listing failures (Ditech's bankruptcy was 11 months earlier; Cloud Peak's came a month after the delisting).
- **Listing failure (10):** 9 / 10. Brookfield Property REIT was a merger-related delisting (should be acquired). This is the one class-flipping error, and it makes the adverse bound harsher.
- **Unknown (11):** at least 6 are well-known acquisitions whose completion 8-K was not in the look-back, 3 are not common equity, 2 are unclear. Treating "unknown" pessimistically is therefore conservative.

# Recommended next steps (in order)

1. **Rerun `05_Proposed_Changes/run_FE_acceptance_times.bat`** for the 27 HTTP 503 filings (resumable; minutes). No approval needed beyond D10c.
2. **Owner decides the G7 reading.** Recommended: fix the rule (bankruptcy only if the 1.03 falls within a set window *before* the Form 25; a 3.01 inside a merger 8-K counts as acquired; Form 15 soon after a 25-NSE with no earlier 3.01 counts as likely acquired) and re-audit on a **fresh** 50-company sample, because a rule tuned on these cases cannot be graded on them. Alternative: accept the class reading (97.4%) and record that the strict reading failed.
3. **Identity (161) and price-spike (287) reviews.** I prepare evidence sheets for each case (filings around the price start; the spike day with neighbouring bars); the owner signs off; exclusions go into `config/smallcap_exclusions.csv` with reason and evidence.
4. **Delisted-price source test (D9, £0).** Norgate free trial: check how many of 100 randomly drawn missing H1 companies it covers, before anything else is decided.
5. **Protocol r6 (draft only):** record the G7 reading, the survivorship note and the development-versus-validation coverage check, and the exclusion-count reporting fix. Then re-run readiness once, owner approves, and lock.
6. **Still no backtests** and no 2022+ data until the protocol is locked.

# Uncertainties remaining

- The 27 unresolved filings (0.03%).
- G7 "unknown" cases are classified partly from general knowledge of the deals; the owner can confirm on EDGAR.
- How much of the missing development population a free source can fill (step 4).
- Why SEC's published times carry 0, 1 or 2 conversions, rising over time. Irrelevant now that true times are used.
