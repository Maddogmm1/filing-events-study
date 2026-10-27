---
title: "G7 Delisting-Cause Audit — Hand Classification"
subtitle: "50 companies from readiness v2 · version 1"
date: "27 October 2026"
---

**Source:** the filing excerpts printed by `fe_readiness_v2.py` (G7), from `results/2026-10-27_FE_Readiness_Report_v2.json`. Each case was classified by reading the 8-K excerpts and the sequence of Forms 25 / 25-NSE / 15 / 8-K. **Evidence column** says where the judgement comes from: *filing* = the excerpt in the sample shows it; *timing* = the order of filings shows it; *knowledge* = general knowledge of a well-known deal, not shown by the sample (owner can check on EDGAR).

The engine's survivorship bounds use only three classes: **failure** (bankruptcy or listing failure), **acquired**, **unknown** (`events.py`, `survivorship_bounds`). Both a strict label check and a class check are reported.

# Results

| Reading | Agree | Cases | Share | vs 90% target |
|---|---|---|---|---|
| A. Engine class (failure / acquired), cases where the rule gave a cause | 38 | 39 | **97.4%** | pass |
| B. Strict cause label, cases where the rule gave a cause | 34 | 39 | **87.2%** | fail |
| C. All 50, rule "unknown" counted as a miss when the true cause is identifiable | 34 (B) or 38 (A) | 50 | 68–76% | fail |

The precondition in draft r5 says only ">= 90% agreement on 50 hand-checked cases"; it does not say which reading. **The owner should decide the reading; this note does not pick the one that passes.** See the recommendation at the end.

# Case table

| # | Company | Form 25 | Rule | Hand | Agree (label / class) | Evidence and note |
|---|---|---|---|---|---|---|
| 1 | Collective Brands | 2012-10-09 | acquired | acquired | Y / Y | filing: 2.01 completion, 3.01, 15-12B |
| 2 | Hilton Hotels | 2007-10-25 | acquired | acquired | Y / Y | filing: "completion of the merger" |
| 3 | Southwest Water | 2010-09-13 | acquired | acquired | Y / Y | filing: merger completed 13 Sep 2010 (earlier 3.01s were Nasdaq filing-delay notices) |
| 4 | PrivateBancorp | 2017-06-22 | acquired | acquired | Y / Y | filing: merger with CIBC closed |
| 5 | Third Coast Midstream | 2019-07-23 | acquired | acquired (take-private) | Y / Y | filing: merger agreement, restated LPA |
| 6 | Williams Pipeline Partners | 2010-09-01 | acquired | acquired | Y / Y | filing: 2.01 merger |
| 7 | Stellent | 2006-12-14 | acquired | acquired | Y / Y | filing: 5.01 change of control, Oracle |
| 8 | XO Group | 2018-12-21 | acquired | acquired | Y / Y | filing: merger closing |
| 9 | Medarex | 2009-09-01 | acquired | acquired | Y / Y | filing: merger completed |
| 10 | LIN TV | 2013-08-01 | acquired | **reorganisation** (merged into own subsidiary LIN Media LLC; holders received successor shares) | N / Y | filing. Exit at market value, so the acquired class is economically right |
| 11 | Nextest Systems | 2008-01-24 | acquired | acquired | Y / Y | filing: Teradyne tender offer, 5.01 |
| 12 | ExOne | 2021-11-12 | acquired | acquired | Y / Y | filing: 2.01 completion |
| 13 | PanAmSat Holding | 2006-07-11 | acquired | acquired | Y / Y | filing: acquisition by Intelsat |
| 14 | Thoma Bravo Advantage | 2021-06-29 | acquired | **SPAC business combination** (holders received ironSource shares) | N / Y | filing. Exit at market value |
| 15 | Dobson Communications | 2007-11-16 | acquired | acquired | Y / Y | filing: merger completed |
| 16 | EMC | 2016-09-07 | acquired | acquired | Y / Y | filing: Dell acquisition |
| 17 | Cadence Bancorporation | 2021-10-29 | acquired | acquired | Y / Y | filing: 2.01, 3.03, 5.01 (excerpt itself is charter text) |
| 18 | Centex | 2009-08-20 | acquired | acquired | Y / Y | filing: Pulte acquisition |
| 19 | Avedro | 2019-11-21 | acquired | acquired | Y / Y | filing: merger completed |
| 20 | Hub International | 2007-06-14 | acquired | acquired | Y / Y | filing: plan of arrangement completed |
| 21 | Interwoven | 2009-03-16 | acquired | acquired | Y / Y | filing: 3.01, 3.03, 5.01 change of control |
| 22 | Ditech Holding | 2018-11-21 | bankruptcy | **listing failure** | N / Y | timing: the 1.03 (first Chapter 11) was Nov 2017–Jan 2018, about 11 months before; the Nov 2018 delisting followed 3.01 notices in May and Nov 2018 |
| 23 | Briggs & Stratton | 2020-08-04 | bankruptcy | bankruptcy | Y / Y | filing: 1.03 July 2020, 3.01 two days later |
| 24 | Satcon Technology | 2012-11-16 | bankruptcy | bankruptcy | Y / Y | filing: 1.03 Oct 2012 |
| 25 | Cagle's | 2011-12-08 | bankruptcy | bankruptcy | Y / Y | filing: 1.03 Oct 2011 |
| 26 | Molycorp | 2015-07-22 | bankruptcy | bankruptcy | Y / Y | filing: 1.03 June 2015 |
| 27 | McDermott International | 2020-02-06 | bankruptcy | bankruptcy | Y / Y | filing: 1.03 Jan 2020 |
| 28 | SCO Group | 2008-02-21 | bankruptcy | bankruptcy | Y / Y | filing: 1.03 Sep 2007, then 3.01s |
| 29 | Cloud Peak Energy | 2019-04-11 | bankruptcy | **listing failure** (bankruptcy one month later) | N / Y | timing: Form 25 on 11 Apr 2019 after 3.01 in Mar; 1.03 only on 10 May 2019. The rule looks after the exit date |
| 30 | Teletouch Communications | 2007-02-27 | listing failure | listing failure | Y / Y | filing: three 3.01 notices |
| 31 | Proxim Wireless | 2009-04-13 | listing failure | listing failure (issuer-filed Form 25 after deficiency notices) | Y / Y | filing + timing: voluntary withdrawal under distress |
| 32 | Capital Trust Holdings | 2011-11-10 | listing failure | listing failure | Y / Y | filing: repeated 3.01 |
| 33 | Tronox | 2008-10-17 | listing failure | listing failure | Y / Y | filing: 3.01 Aug–Sep 2008 |
| 34 | Azure Midstream Partners | 2016-10-06 | listing failure | listing failure | Y / Y | filing: 3.01 June 2016 |
| 35 | SandRidge Mississippian Trust II | 2019-11-26 | listing failure | listing failure | Y / Y | filing: 3.01 notices |
| 36 | Monarch Community Bancorp | 2012-10-15 | listing failure | listing failure (issuer-filed Form 25) | Y / Y | filing: 3.01 "failure to satisfy"; voluntary withdrawal |
| 37 | Sterling Banks | 2010-07-19 | listing failure | listing failure | Y / Y | filing: 3.01 Dec 2009 |
| 38 | DS Healthcare Group | 2017-03-14 | listing failure | listing failure | Y / Y | filing: three 3.01 notices |
| 39 | Brookfield Property REIT | 2021-08-18 | listing failure | **acquired** (merger with Brookfield Property Partners, July 2021) | N / **N** | filing (1.01 + 3.01 in a merger 8-K) + knowledge. The 3.01 was a merger-related delisting, not a failure |
| 40 | Tutogen Medical | 2010-01-19 | unknown | unclear | — | no 8-K in the look-back; merged with Regeneration Technologies in 2008 (knowledge), but a 2010 Form 25 does not fit; leave unknown |
| 41 | TurboChef Technologies | 2009-01-06 | unknown | acquired (Middleby) | — | knowledge; 25-NSE then 15-12B ten days later |
| 42 | Ventana Medical Systems | 2008-02-19 | unknown | acquired (Roche) | — | knowledge |
| 43 | NewPage Holding | 2008-03-10 | unknown | unclear (registrant mainly for debt) | — | the only 8-K is about NewPage's own acquisition of Stora Enso North America |
| 44 | ANR Pipeline | 2007-03-30 | unknown | not common equity (subsidiary sold to TransCanada; delisted security probably debt) | — | filing 5.01 + knowledge |
| 45 | Altiris | 2007-04-09 | unknown | acquired (Symantec) | — | knowledge |
| 46 | MACROshares Oil Up Tradeable Trust | 2008-07-07 | unknown | trust termination (not common equity) | — | knowledge |
| 47 | Valley Bancorp | 2006-10-16 | unknown | acquired (Community Bancorp) | — | knowledge |
| 48 | American Medical Systems | 2011-06-17 | unknown | acquired (Endo) | — | knowledge |
| 49 | TE Products Pipeline | 2008-02-07 | unknown | not common equity (TEPPCO subsidiary) | — | knowledge |
| 50 | rue21 | 2013-10-10 | unknown | acquired (Apax take-private) | — | filing: 3.01 "in connection with" the merger, the day after the 25-NSE |

# What the disagreements show

1. **Timing window for bankruptcy is too loose in both directions.** Ditech's 1.03 was 11 months before the exit; Cloud Peak's came after it. Both are still in the failure class, so the bounds are unaffected.
2. **A 3.01 inside a merger 8-K is read as a listing failure.** Brookfield Property REIT is the one case that flips class (failure instead of acquired). This error makes the adverse bound harsher, not milder.
3. **Reorganisations and SPAC combinations are labelled acquired.** Economically correct for the bounds (holders exit at market value).
4. **"Unknown" is mostly acquisitions or non-equity securities.** Of 11, at least 6 are well-known acquisitions whose completion 8-K was not in the look-back, 3 are not common equity (pipeline subsidiaries, a commodity trust) and 2 are unclear. So treating unknown pessimistically in the bounds is conservative. The equity-only filter should also drop the non-equity securities.

# Recommendation (owner decision)

- **Option 1 (recommended):** fix the rule on these lessons (1.03 must fall within a set number of days *before* the Form 25; a 3.01 filed in the same 8-K as 1.01/2.01/5.01 or with merger wording counts as acquired; a Form 15 within 30 days after a 25-NSE with no earlier 3.01 counts as likely acquired), then audit a **fresh** 50-company sample drawn with a new seed. A rule tuned on these 50 cases cannot be graded on them.
- **Option 2:** accept reading A (97.4%, the classes the engine actually uses) as meeting the precondition, record that reading B fails, and leave the rule unchanged.
- Either way, record the chosen reading in the protocol before lock.
