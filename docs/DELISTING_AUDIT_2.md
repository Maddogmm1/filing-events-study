---
title: "G7 Delisting-Cause Audit, Rule r2 — Hand Classification"
subtitle: "Fresh 50-company sample (seed 1) from readiness v2.1 · version 1"
date: "27 October 2026"
---

**Result: G7 FAILS under the criteria fixed before this sample was drawn** (Owner Decisions Record v2). Both readings fall short of 90% on the 36 cases where r2 names a cause:

| Reading | Agree | Cases | Share | Criterion | Result |
|---|---|---|---|---|---|
| (a) Engine class (failure / acquired) | 32 | 36 | **88.9%** | ≥ 90% | FAIL |
| (b) Exact label | 30 | 36 | **83.3%** | ≥ 90% | FAIL |

Per the record, r2 is **not** tuned further on this sample.

Also from readiness v2.1: **T1 now 100%** (96,439 of 96,439 in-scope filings verified after the rerun). Across the 5,207-company population r2 changed the cause of 64 companies relative to r1 (36 bankruptcy → listing failure, 20 listing failure → acquired, 5 bankruptcy → acquired, 3 unknown → a named cause) and split the rest of r1's 1,122 "unknown" into 499 `acquired_inferred` and 620 unknown.

Source: `results/2026-10-27_FE_Readiness_Report_v2_1.{md,json}`. Evidence: *filing* = shown by the excerpt; *timing* = order of filings; *knowledge* = general knowledge of the deal, not in the sample (checkable on EDGAR). Hand labels use the definitions in the record: acquired = corporate transaction at market value; bankruptcy = the company itself in Chapter 7/11 on the exit date; listing failure = failed listing standards, or voluntary withdrawal after deficiency notices; other = anything else.

# Disagreements (6 of 36)

| # | Company | r2 | Hand | Class agrees? | Why |
|---|---|---|---|---|---|
| 9 | Williams Coal Seam Gas Royalty Trust | acquired | other (trust termination, assets sold) | N | filing: liquidation of the trust; 2.01 was the asset sale |
| 23 | Midwest Banc Holdings | bankruptcy | listing failure | Y | filing: the 1.03 was the **bank subsidiary's** FDIC receivership; the holding company filed Chapter 11 only in Aug 2010, after the June delisting |
| 27 | Storm Cat Energy | bankruptcy | listing failure | Y | filing: subsidiaries filed Chapter 11; the 8-K says the parent was not included |
| 35 | General Maritime Subsidiary Corp | listing failure | acquired (reorganised into a listed successor in the Arlington Tankers combination) | **N** | filing + knowledge: the merger-day 8-K carried 3.01 + 1.01; r2's guard blocked it because of a July 2008 3.01 about board composition, a technical notice, not distress |
| 41 | United States Diesel-Heating Oil Fund | listing failure | other (fund liquidation) | N | filing: plan of liquidation; not an operating company |
| 43 | Heritage Southeast Bancorporation | listing failure | other (voluntary going-dark, no deficiency notice) | N | filing: board chose to delist to save costs |

# Agreements (30 of 36)

- **Acquired (13 of 14):** CoBiz, G&K Services, Financial Federal, Golf Galaxy, Market Leader, Boykin Lodging, Cephalon, MEDecision, Factory Card & Party Outlet, Cardiac Science, Western Refining Logistics, Dionex, Loxo Oncology. All filing evidence (completion 8-Ks).
- **Bankruptcy (8 of 10):** FTD (GUE Liquidation), Achaogen, South Texas Oil, Circuit City, Libbey, SFX Entertainment, Grubb & Ellis (in Chapter 11 on the Form 25 date), Inland Fiber Group. All filing evidence.
- **Listing failure (9 of 12):** Odimo, Superior Energy Services, Transmeridian, Mercantile Bancorp (voluntary after notices), First Acceptance (voluntary after NYSE notice), Vicon, PreVu (Wilsons Leather), Telkonet, Saba Software (late SEC filings).

# Not scored (reported only)

- **`acquired_inferred` (8):** 5 corporate transactions (eCollege → Pearson, Caremark → CVS, Insightful → TIBCO, Golden Cycle Gold → Newmont, 10X Capital SPAC → REE Automotive; knowledge), 3 not operating-company equity (CABCO trust preferred, Boeing Capital debt, Regalwood SPAC liquidation). 5 of 8 is too low to treat the label as acquired.
- **Unknown (6):** Community Banks (PA) and Premcor were acquired (knowledge); Action Performance probably acquired (knowledge, less sure); CORTS Dow trust and Lehman ABS note series are debt securities; First Republic Bancorp unclear.

# What the failure shows

1. **Half the errors are not operating companies:** a royalty trust, a commodity fund, a going-dark bank (and 3 of 8 inferred, 2 of 6 unknown are debt or trust securities). The audit population (every exchange delisting) is wider than the companies the study can ever hold. The bounds only touch companies with priced events in the study universe.
2. **Bankruptcy of a subsidiary is filed under item 1.03** and looks the same as the parent's. Item codes alone cannot separate them; it needs the text.
3. **The "no earlier 3.01" guard is too blunt:** technical notices (board composition, late filings later cured) block real mergers.
4. **Sampling noise is large at n = 36–39.** The first audit's class reading was 97.4% (r1), this one 88.9% (r2). Both are consistent with a true class accuracy around 90%. A 50-case audit cannot settle a 90% threshold precisely (95% interval roughly ±10 points).

# Which errors matter

The engine uses cause labels only for **unpriced events whose company left the exchange inside the holding window** (`survivorship_bounds`; for H1 development that is 2,695 events in S1). A label error matters only if it makes the bound *less* conservative:

- **H1 (long):** the risk is an exit labelled *acquired* that was really a failure. Across both audits (first under r1, second under r2): **0 of 35** acquired-labelled cases (the one miss was a trust termination, which is not a failure).
- **H2 (short):** the risk is an exit labelled *failure* that was really an acquisition. Across both audits: **2 of 40** (Brookfield Property REIT, General Maritime).
- The other errors (bankruptcy versus listing failure, failure labels on trusts, funds and going-dark companies) either stay inside the failure class or make the bound harsher.

This split was worked out after seeing the results, so it is used below only together with a safety margin and a classifier-free check, not as a reason to pass G7.

# Options (owner decision)

- **Option A (recommended): error allowance in the bounds instead of a label gate.** Protocol r6 (draft) and a small engine patch: in the adverse scenario, 10% of the exits in the class that favours the position (acquired for longs, failure for shorts) take the unfavourable outcome. 10% is at least twice any error rate seen in the dangerous direction (0/35 long, 2/40 short). Also report a **classifier-free bound** (adverse scenario: every inside-window exit takes the unfavourable outcome) as a sensitivity, not as the robustness test. G7 becomes a reported check, not a lock gate. Effect on the bounds is measured in the next readiness run.
- **Option B: third rule and third fresh sample.** r3 restricted to operating companies with at least one study event, text checks for subsidiary bankruptcies and technical 3.01s, seed 2. More work and another chance of a marginal miss at n ≈ 40.
- **Option C: accept 88.9% as close enough.** Not recommended: it relaxes a criterion after seeing the result.
