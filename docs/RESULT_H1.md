---
title: "Filing-Events Study — Result P1: H1 on the Development Window"
subtitle: "Trial 1 of 17 under the locked protocol filing_events_v1 · version 1"
date: "27 October 2026"
---

**Verdict under the pre-registered rule: FAIL.** H1 (buy small companies after a top-decile 3-day reaction to an earnings 8-K and hold 60 sessions) loses money after costs in 2005–2017. H1 can no longer be "supported", because that requires a pass in development **and** validation.

Run: experiment 8, 27 Oct 2026 17:53, code `bda7cfe` (clean), protocol hash `e3f4a2fd…fe67d`, 617 price masks applied, verified acceptance times. Raw: `results/2026-10-27_FE_Run_P1_H1_dev_v2.json` and the run log. (`_v1` is the empty export from the first attempt that did not run.)

# Numbers

| Measure | Value | Rule |
|---|---|---|
| Positions | 4,442 (minimum 1,840) | enough for a verdict |
| Mean 60-session abnormal return, **gross** | **+0.51%** | — |
| Mean net of 100 bps each way (primary) | **−1.49%** | — |
| 95% interval (month-clustered block bootstrap) | [−2.42%, −0.60%] | must exclude 0 on the positive side: **fails** (it excludes 0 on the negative side) |
| Calendar-time monthly Newey–West t | −1.36 | must exceed 2: **fails** |
| Deflated Sharpe (N = 17) | 0.001 | must be ≥ 0.95: **fails** |
| Annualised Sharpe of the monthly series | −0.39 | — |

**Costs.** At the 200 bps stress the mean is −3.49%. With the estimated spreads instead (Corwin–Schultz, 0.68% one way on average) it is still −0.85%, so the loss does not hinge on the conservative cost assumption.

**Not an outlier story.** The 1%-winsorised mean is −1.48%, the same as the raw mean. Ten of 13 years are negative net (positive: 2008, 2013, 2017).

**Survivorship bounds** (net mean if the unpriced events had been tradable): favourable −1.24%, central −1.60%, adverse −2.48%, label-free adverse −3.09%. Every scenario is negative, so the missing companies cannot rescue the result. The engine's "robust to survivorship" flag is false only because that test asks whether a *positive* result survives.

**The two tests disagree on strength, not on direction.** The position-level interval is clearly negative; the calendar-time t (−1.36) is weaker because it weights months, not positions. Both say no positive drift.

# Reading

- The gross continuation is about half a percent over three months. That is too small to show up against the noise, and a small fraction of the ~2% round-trip cost of trading these stocks.
- Post-earnings drift in microcaps, measured this way (top-decile 3-day reaction, enter at day +3, 60 sessions, dollar-volume-band benchmark, true acceptance times), is not a tradable edge in 2005–2017. This is consistent with published evidence that the drift has weakened since the 2000s and survives mainly where trading costs absorb it (e.g. Chordia, Goyal, Sadka, Sadka and Shivakumar 2009).
- Caveat already written into the protocol: this applies to "companies with surviving price history" (42% of listed-at-event earnings events in development).

# What follows under the protocol

- **No validation run for H1**: it cannot change the verdict, and validation is single-use per configuration.
- **H1S (P2) is H1 minus companies with a recent bad filing**, a subset of the same trades. It is likely to fail too, but it is pre-registered and next in the frozen order.
- **H2 hypotheses cannot reach a verdict** (counts below 1,840); their runs give the descriptive and negative-screen results the protocol promised.
- **H3 combines H1 long with the H2 short leg**; with H1 negative it is unlikely to pass.
- Variations V1, V4, V5, V8 tweak H1/H1S (shorter hold, tighter decile, open entry, longer hold). The protocol allows them, but each is another draw on the 17-trial budget, and the deflated Sharpe already accounts for all 17.
