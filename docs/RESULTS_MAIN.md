---
title: "Filing-Events Study — Development Results, Main Hypotheses"
subtitle: "Trials 1–7 of 17 under the locked protocol filing_events_v1 · version 1"
date: "27 October 2026"
---

**Bottom line: no main hypothesis passes, and every one loses money after costs in 2005–2017.** H1, H1S and H3 had enough positions for a verdict and FAIL. Every H2 hypothesis was INCONCLUSIVE by count, as readiness predicted, and each is negative net as well. No configuration qualifies for validation, so the validation and sealed windows stay untouched.

Runs: experiments 8–14, 27 Oct 2026 17:53–18:07, code `bda7cfe` (clean), protocol `e3f4a2fd…fe67d`, 617 price masks, verified acceptance times. Raw: `results/` (logs and exports). All figures are 60-session abnormal returns per position, signed so that positive means the trade made money; "net" uses the primary cost (100 bps each way; shorts also pay the protocol's financing rate).

# Results

| Trial | Hypothesis | Positions | Gross | Net | 95% interval (net) | NW t | DSR | Verdict |
|---|---|---|---|---|---|---|---|---|
| P1 | H1 long after top-decile earnings reaction | 4,442 | +0.51% | −1.49% | [−2.42%, −0.60%] | −1.36 | 0.001 | **FAIL** |
| P2 | H1S = H1 without recent bad filers | 3,918 | +0.40% | −1.60% | [−2.55%, −0.68%] | −1.35 | 0.001 | **FAIL** |
| P3 | H2A short late filers (NT 10-K/Q) | 811 | +1.52% | −1.91% | [−3.87%, −0.13%] | −2.91 | 0.000 | INCONCLUSIVE (811 < 1,840) |
| P4 | H2B short non-reliance (4.02) | 354 | +0.06% | −3.37% | [−5.68%, −1.04%] | −2.51 | 0.000 | INCONCLUSIVE |
| P5 | H2 short late + non-reliance | 994 | +1.03% | −2.40% | [−4.20%, −0.83%] | −2.91 | 0.000 | INCONCLUSIVE |
| P6 | H3 50/50 H1 long + H2 short | 5,436 | +0.61% | −1.65% per position; **−0.72% per month** (portfolio) | [−1.11%, −0.32%] per month | −3.54 | 0.000 | **FAIL** |
| E1 | H2C short auditor change (4.01), exploratory | 636 | +0.13% | −3.30% | [−5.22%, −1.40%] | −2.25 | 0.000 | INCONCLUSIVE (exploratory) |

H3's primary measure is the monthly return of the 50/50 long-short portfolio (protocol D6b); the run log prints the per-position mean next to that interval, which looks inconsistent but is not. The verdict uses the right pair.

**Robustness (all negative):**

| | H1 | H1S | H2A | H2B | H2 | H2C | H3 |
|---|---|---|---|---|---|---|---|
| Net at estimated spreads (0.65–0.71% one way) | −0.85% | −0.95% | −1.33% | −2.67% | −1.80% | −2.67% | −1.02% |
| Net at 200 bps stress | −3.49% | −3.60% | −3.91% | −5.37% | −4.40% | −5.30% | −3.65% |
| Survivorship: best / worst bound | −1.24 / −3.09% | −1.36 / −3.22% | −0.41 / −3.33% | −1.78 / −4.93% | −0.96 / −3.69% | −2.12 / −4.56% | (read the legs) |
| 1%-winsorised net | −1.48% | −1.55% | −1.79% | −3.19% | −2.25% | −3.21% | −1.61% |
| Years with positive net | 3 of 13 | 3 of 13 | 3 of 13 | 1 of 13 | 3 of 13 | 2 of 13 | 3 of 13 |

# What it means

1. **Earnings-reaction continuation (H1) is about +0.5% gross over three months**, a quarter of the ~2% round-trip cost of trading these stocks. It is not an edge at retail costs.
2. **The negative screen does not help.** Removing companies with a recent bad filing (H1S) leaves the result unchanged (−1.60% against −1.49%).
3. **Bad filings are mostly priced in by the day after.** Shorting from day +1 earns +1.5% gross for late filers and essentially nothing for restatements (+0.06%) or auditor changes (+0.13%), before a cost of about 3.4% round trip including short financing. Even the best case, late filers, shows no reliable gross drift: the gross interval includes zero.
4. **Combining the two sides (H3) only adds costs.** It fails more clearly than either leg (t −3.54).
5. **No position was cut short by a delisting** (truncated share 0 in every run). This is the survivorship mechanism from readiness in action: the price source holds companies that survived, so failures inside holding windows are missing rather than measured. The bounds show the conclusions hold either way: every scenario is negative.

# Scope

The result applies to the protocol's design: US exchange-listed common stocks with a $2 price floor and $200k–$20m daily dollar volume; entry at day +3 (earnings) or +1 (filings); 60-session holds; a dollar-volume-quintile benchmark; companies with surviving price history; 2005–2017. It does not rule out effects at shorter horizons, at entry speeds faster than one session, or for traders with institutional costs.

# What remains under the protocol (10 trials)

The variations (V1 H1 hold 20, V2 H2A hold 20, V3 H2B hold 20, V4 H1 decile 0.95, V5 H1 open entry, V6 placebo, V8 H1S hold 120, V9–V10 reserve; V7 lapsed) all tweak hypotheses whose gross effect is well below cost. None can realistically pass (the deflated Sharpe already counts all 17 trials), and running them would mainly add data-mining exposure.

**Recommendation:** run only **V6, the placebo** (random 10% of eligible earnings events), as an engine check. Its gross return should be close to zero. If it is, the negative net results above are cost, not a benchmark bias. Then close the study with a final report and leave the other variations unused.
