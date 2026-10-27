---
title: "Filing-Events Study (FE) — Final Report"
subtitle: "Do SEC filing events give a tradable edge in US small caps at retail costs? · version 1"
date: "27 October 2026"
---

# Answer

**No.** Under a protocol fixed and locked before any return was computed, none of the seven main hypotheses produced a tradable edge in 2005–2017. Every one lost money after costs, under every cost and survivorship scenario tested. A placebo of random earnings events earned the same as the "signal" before costs, so the selection rules add essentially nothing. The validation (2018–2021) and sealed (2022+) windows were never needed and remain unused.

# What was tested

Protocol `filing_events_v1` (SHA-256 `e3f4a2fd…fe67d`, locked 27 Oct 2026 17:47), on US exchange-listed common stocks with a $2 price floor and $200k–$20m average daily dollar volume, 60-session holds, abnormal returns against a dollar-volume-quintile benchmark.

- **H1** long after a top-decile 3-day abnormal reaction to an earnings 8-K, entry at day +3; **H1S** the same excluding companies with a bad filing in the prior year.
- **H2A** short after a late-filing notice (NT 10-K/Q); **H2B** short after a non-reliance restatement (8-K 4.02); **H2** both; **H2C** auditor change (4.01, exploratory). Entry at day +1.
- **H3** 50/50 portfolio of H1 long and H2 short.
- **Costs:** longs as shares (Invest/ISA), 100 bps each way; shorts as CFDs, 100 bps each way plus 6% a year financing. Stresses at 200 bps, estimated spreads, and 10%/20% short financing.
- **Pass rule (all required):** 95% interval of net return above zero, Newey–West t > 2, deflated Sharpe ≥ 0.95 over the 17-trial budget; then the same in validation.

# Results (development window, 2005–2017)

| Trial | Hypothesis | Positions | Gross | Net | Verdict |
|---|---|---|---|---|---|
| P1 | H1 | 4,442 | +0.51% | −1.49% | FAIL |
| P2 | H1S | 3,918 | +0.40% | −1.60% | FAIL |
| P3 | H2A | 811 | +1.52% | −1.91% | Inconclusive (count) |
| P4 | H2B | 354 | +0.06% | −3.37% | Inconclusive (count) |
| P5 | H2 | 994 | +1.03% | −2.40% | Inconclusive (count) |
| P6 | H3 | 5,436 | +0.61% | −0.72% per month | FAIL |
| E1 | H2C (exploratory) | 636 | +0.13% | −3.30% | Inconclusive (count) |
| V6 | Placebo: random 10% of eligible earnings events | 4,500 | +0.29% | −1.71% | FAIL (as expected) |

Returns are 60-session abnormal returns per position, signed so that positive means the trade made money. "Inconclusive (count)" means fewer than the 1,840 positions needed for a fair test, as readiness predicted; each of those is negative net as well.

**Robustness:** every hypothesis stays negative at estimated spreads (0.6–0.7% each way), at the 200 bps stress, with the top and bottom 1% trimmed, and in every survivorship scenario (best to worst bound, for example H1 −1.24% to −3.09%). Shorts get worse at 10% and 20% financing.

**Placebo (engine check):** random earnings events earn +0.29% before costs. The gross interval, about −0.3% to +0.9%, includes zero. The benchmark is therefore not biased, and the negative net results are costs. H1's top-decile rule beats random selection by only about 0.2 points before costs.

# Why

1. **The effects are small relative to retail costs.** The largest gross effect, shorting late filers, is about +1.5% over three months and is not reliably above zero. Round-trip costs are about 2% for longs and 3.4% for CFD shorts.
2. **Bad news is priced within a day.** By the day after a restatement or auditor change the price has moved; little is left to short.
3. **Earnings drift in small caps is weak in this period.** This is consistent with published evidence that post-earnings drift has weakened since the 2000s.

# What made the result trustworthy

- **Timestamps:** SEC's own acceptance times replaced stored ones that were wrong for over 99% of filings (UTC or double-converted). Without the fix, 27.7% of event days would have been one session late.
- **Survivorship:** a delisting table, cause rule r2 with a 10% label-error allowance, and favourable/central/adverse bounds on every result.
- **Price data:** 617 masks for one-day reversals and shell or SPAC eras, chosen by rules fixed before the evidence was seen.
- **Discipline:** the protocol was pre-registered and locked; trials were run in a frozen order; a deflated Sharpe over all 17 trials; nothing read from 2022 onward.

# Limits

- **Survivorship of the price source.** Only companies with surviving price history are priced: 42% of listed-at-event earnings events in development, 67% in validation. The bounds show this cannot turn the results positive.
- **Not modelled:** which instruments Trading 212 offered at each date, borrow availability, historical CFD financing rates, and intraday entry.
- **Scope.** The result covers these definitions only. It does not rule out effects at shorter horizons, at entry speeds faster than one trading day, or for traders with institutional costs.

# Closing state

- **Trials used: 8 of 17** (P1–P6, E1, V6). The remaining variations (V1–V5, V8–V10; V7 lapsed) are left unused. They tweak hypotheses whose gross effect is far below cost, and running them would only add data-mining exposure.
- Validation and sealed windows: unused; the sealed window is still sealed.
- Code: the engine in `fe/` of this repository (extracted from the author's private research terminal, where the runs were made at commit `bda7cfe`). Experiments 8–15 are in `results/experiments_dev.json`.
- Full record: `docs/` (readiness reports, delisting audits, price review, lock record, result write-ups).

# Recommendation

Close FE as a negative result and do not deploy capital on these signals. If filing events are revisited, it should be under a new, separately locked protocol aimed at what this study could not test: intraday entry on the filing, which needs intraday data, or a cost base well below 1% round trip. It should not reuse these hypotheses on the validation window.
