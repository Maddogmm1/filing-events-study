---
title: "Filing-Events Study — Data-Readiness Report"
subtitle: "Gates G0–G10 on the real database · version 1"
date: "26 October 2026"
---

**Status:** DRAFT FOR OWNER REVIEW. **Not ready to lock.** One blocking defect (acceptance timestamps) needs a data fix; everything else is either acceptable or settled by rules fixed before any return was computed.

**What was run:** three read-only passes on `data/smallcap.duckdb` (`fe_readiness_v1`, `v1.1`, `v1.2`), all queries limited to dates before 2022-01-01, counts and data quality only. No strategy return, abnormal return or backtest was computed. Raw outputs are in `results/`.

# Bottom line

1. **Acceptance timestamps are wrong for about half of all events (blocking).** Compared with SEC's own filing pages, a stratified sample of 300 earnings 8-Ks splits three ways, and the split explains all 300:
    - **correct New York time** (offset 0): 116 in the sample, about 53% of the population;
    - **UTC** (+4 h in summer, +5 h in winter): 66, about 18%;
    - **double-converted** (+8 h in summer, +10 h in winter, i.e. the UTC offset applied twice): 118, about 30%.

   It does not follow the filing agent (only 38% of agents with two or more sampled filings showed one pattern), so no simple rule repairs it. Under draft r3's day-0 rule, about **88% of events still land on the correct session and 12% land one session late (never early)**. So there is no look-ahead, but H1's reaction window and every entry date are mis-timed for roughly one event in eight. Recovering the true time from the stored time and the filing date settles day 0 for only 67% of the sample, which is not enough. **Fix: read the acceptance time from SEC's index page for every event in scope** (proposed change D10c, below).
2. **Only H1 and H1S have enough events for a verdict.** Expected positions against the 1,840 minimum (2% net effect, design effect 1.5):

| Hypothesis | Development | Validation | Verdict possible? |
|---|---|---|---|
| H1 / H1S (top-decile earnings reactions) | 4,592 | 1,973 | **Yes** (validation margin thin; 1,973 is an upper estimate before de-duplication) |
| H2A late filings | 815 | 393 | No |
| H2B non-reliance | 355 | 128 | No (128 misses even the draft's 306) |
| H2C auditor change | 636 | 379 | No |

   H2 goes ahead as a negative screen (inside H1S) plus a descriptive event study, never as evidence of a profitable short. A confirmatory H2 test needs more observations: a delisted-price source, if the D10a delisting table shows the gaps are companies that left an exchange, or a longer sample.
3. **Entry stays at the close of day +3, by the rule fixed in advance.** Opens exist on 99.9% of day +3 rows (G8), but **7.6% simply repeat the previous close** (G8b), above the 5% limit set before the check. Under the provisional D4 rule, close is primary and the day +3 open runs as variation V5.
4. **The 100 bps cost assumption stays.** Three spread estimators computed from daily highs, lows and closes agree on a median half-spread of about 31–42 bps one way. None rises clearly from the most liquid fifth of stocks to the least liquid (Abdi–Ranaldo only slightly, 36 → 42 bps). Real spreads widen as liquidity falls, so these estimates reflect the limits of daily data rather than real trading costs. They cannot justify a cost below 100 bps.
5. **The survivorship hole is large and its makeup is still unknown.** Share of SEC events with a price (development / validation): late filings 4.6% / 12.9%; non-reliance 13.2% / 37.2%; auditor changes 10.2% / 28.6%; earnings 37.3% / 63.1%. The denominator includes many OTC companies that were never listed on an exchange Trading 212 offers. Only the D10a delisting table can split "never listed" from "left the exchange".

# Gate results

| Gate | Result | Evidence |
|---|---|---|
| G0 Identity | PASS | `Terminal` branch `main`, commit `c2f2d345`; draft r3 SHA-256 `68ea27df…`; only `m6_replication_v1` locked |
| G1 Snapshot integrity | PASS (v1.1) | 41 snapshots, 0 missing, 0 hash mismatches. (v1 crashed on a missing row count: script bug, fixed) |
| G2 Exchange labels | Owner review | SEC file: Nasdaq 4,359, NYSE 3,276, OTC 2,574, none 164, Cboe 44, Texas 12. NYSE American appears under "NYSE", so it is included. **Recommendation: keep Nasdaq + NYSE; Cboe and Texas are negligible** |
| G3 Acceptance-time zone | v1 rule PASS, **superseded** | The v1 rule (after-close cluster at 16–17 h) was too weak to see a mixed population |
| G3b Time zone by year | **FAIL** | 17.9% of earnings-8-K stamps fall in hours EDGAR is closed; no midnight placeholders |
| G3c Truth sample (300) | **Diagnostic: defect confirmed** | 0 / +1 / +2 conversions explain 300 of 300; not agent-specific; population about 53 / 18 / 30% |
| G4 Coverage | Reported | Table above; 875 issuers have more than one current ticker; every listed ticker fetched |
| G5 Price quality | PASS | 13.8 m pre-2022 rows, 5,117 tickers, 24 bad-OHLC rows; 2,692 daily moves above 80% (287 reverse the next day: likely bad prints, listed for review); 643 fractional "splits" (stock dividends and spin-offs, as already documented for the S&P 500 side) |
| G6 / G6b Identity of price histories | Owner review | 266 flagged: 105 have issuer filings near the price start (probably no earnings-8-K habit); 161 go to documented manual review (reorganisation, ticker reuse or unclear). **No automatic exclusion** |
| G7 Delisting-cause classifier | Not run | Needs D10a |
| G8 Opens valid | PASS | 99.89% of 45,925 day +3 rows |
| G8b Repeated opens | **FAIL (rule: < 5%)** | Open = previous close 7.56%; flat bar 0.05%. Therefore close entry is primary (D4) |
| G9 Expected positions | Reported | Table above |
| G10 Spread estimators | Reported | Corwin–Schultz 32–35 bps, Abdi–Ranaldo 36–42 bps, Roll 25–36 bps (median half-spread by quintile); no credible liquidity gradient |

# Consequences for the decisions

| Decision | Effect of the readiness results |
|---|---|
| D1 Survivorship | Unchanged: build D10a, report bounds. Coverage is low enough that, for H2, the bounds will dominate the conclusions |
| D2 H2C | Exploratory (D2a) confirmed by counts as well as by sign ambiguity |
| D3 Day 0 | **Now also needs D10c (true acceptance times).** The calendar and buffer (D3c) are still right, but they act on correct times only after D10c |
| D4 Entry | **Settled by the pre-set rule: close primary, open as V5** |
| D5 Minimums | 2% net with design effect 1.5 (1,840) leaves H1/H1S testable and H2 inconclusive; picking a smaller minimum to make H2 testable would be choosing the test to fit the data |
| Costs | 100 bps primary; 150 bps open-entry stress (for V5); 200 bps broad stress; add short-financing stress at 10% and 20% |
| D9 Data sources | Higher priority for H2 only; H1 does not depend on it |

# Proposed change D10c: true acceptance times (needs approval)

- **What:** a new table `sc_acceptance_truth` (accession, acceptance time in New York, source URL, fetch time, page hash), filled by reading SEC's filing index page for every event in scope. The engine uses the true time when present and **excludes** (and counts) any in-scope event without one, never falling back silently to the stored time.
- **Scope:** pre-2022 events whose company has prices and that pass the eligibility screen on day −1 under any of the three candidate times. That is about 70,000 filings, roughly 4 hours at 5 requests a second; it can be stopped and resumed. Sealed-window events are deferred until (and unless) the sealed window is opened.
- **Validation:** the 300-filing sample becomes a test fixture; the loader must reproduce SEC's time for all 300.
- **Safety:** additive table only; raw pages snapshotted (gzip, hashed); no change to `sc_events`. Rollback: drop the table.
- **Why not infer:** stored time plus filing date settles day 0 for only 67% of the sample.

# Uncertainties remaining

- Why SEC's published times carry 0, 1 or 2 conversions (SEC-side or bulk-file construction); irrelevant once D10c is in place, but worth a note to SEC data support.
- Whether NT 10-K/Q timestamps follow the same split (G3b shows 6–7% in closed hours, versus 17.6% for 8-Ks). D10c covers them anyway.
- H1's expected validation count after de-duplication (could fall slightly below 1,840; reported, not adjusted).
- The 161 identity cases and the 287 reversing price spikes, until reviewed.
