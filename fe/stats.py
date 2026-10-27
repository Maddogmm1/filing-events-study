"""Statistics for judging a signal. Everything here is deliberately conservative and dependency-free (numpy/pandas only)."""
from statistics import NormalDist

import numpy as np
import pandas as pd

_N = NormalDist()


def rank_ic(panel: pd.DataFrame, pred: str, target: str = "y", min_n: int = 20) -> pd.Series:
    """Spearman correlation of prediction and outcome, computed separately on each date and never pooled.
    Dates with fewer than min_n securities are dropped."""
    def one(g):
        g = g[[pred, target]].dropna()
        if len(g) < min_n:
            return np.nan
        return g[pred].rank().corr(g[target].rank())
    out = panel.groupby(level="date").apply(one)
    return out.dropna().rename("ic")


def newey_west_se(x, lags: int) -> float:
    """Standard error of the mean with Bartlett-weighted autocovariances. Overlapping labels (a 3-month outcome measured
    monthly) make neighbouring dates dependent, so lags should be at least horizon - 1."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 3:
        return float("nan")
    e = x - x.mean()
    lags = int(min(max(lags, 0), n - 2))
    var = float(e @ e) / n
    for k in range(1, lags + 1):
        w = 1.0 - k / (lags + 1.0)
        var += 2.0 * w * float(e[k:] @ e[:-k]) / n
    return float(np.sqrt(max(var, 0.0) / n))


def newey_west_t(x, lags: int) -> float:
    x = np.asarray(x, float)
    se = newey_west_se(x, lags)
    return float(x.mean() / se) if se and se > 0 else float("nan")


def block_bootstrap_ci(x, block: int, n_boot: int = 2000, alpha: float = 0.05, seed: int = 0, stat=np.mean) -> tuple[float, float]:
    """Circular block bootstrap of a time series statistic. Blocks keep the serial dependence that a plain bootstrap destroys."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 4:
        return float("nan"), float("nan")
    block = int(min(max(block, 1), n))
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block))
    idx0 = np.arange(block)
    vals = np.empty(n_boot)
    for b in range(n_boot):
        starts = rng.integers(0, n, n_blocks)
        idx = ((starts[:, None] + idx0[None, :]) % n).ravel()[:n]
        vals[b] = stat(x[idx])
    return float(np.quantile(vals, alpha / 2)), float(np.quantile(vals, 1 - alpha / 2))


def sharpe(x, periods_per_year: float = 1.0) -> float:
    x = np.asarray(x, float)
    sd = x.std(ddof=1) if len(x) > 1 else np.nan
    return float(x.mean() / sd * np.sqrt(periods_per_year)) if sd and sd > 0 else float("nan")


def _moments(x):
    x = np.asarray(x, float)
    m, sd = x.mean(), x.std(ddof=0)
    if sd == 0:
        return 0.0, 3.0
    z = (x - m) / sd
    return float((z ** 3).mean()), float((z ** 4).mean())


def expected_max_sharpe(n_trials: int, sr_variance: float) -> float:
    """Expected best Sharpe among n_trials unskilled strategies (Bailey and Lopez de Prado, 2014)."""
    if n_trials <= 1 or sr_variance <= 0:
        return 0.0
    g = 0.5772156649015329
    return float(np.sqrt(sr_variance) * ((1 - g) * _N.inv_cdf(1 - 1 / n_trials) + g * _N.inv_cdf(1 - 1 / (n_trials * np.e))))


def deflated_sharpe(x, n_trials: int, sr_variance_across_trials: float | None = None) -> float:
    """Probability that the observed (per-period) Sharpe of x exceeds what the best of n_trials chance strategies would show.
    Values near 1 are strong; below 0.95 the result is not distinguishable from luck given how many things were tried.
    If the trials' own Sharpe variance is unknown, the sampling variance of one Sharpe estimate is used."""
    x = np.asarray(x, float)
    n = len(x)
    if n < 8:
        return float("nan")
    sr = x.mean() / x.std(ddof=1)
    skew, kurt = _moments(x)
    v = sr_variance_across_trials if sr_variance_across_trials is not None else (1 + 0.5 * sr * sr) / (n - 1)
    sr0 = expected_max_sharpe(max(int(n_trials), 1), v)
    denom = np.sqrt(max(1 - skew * sr + (kurt - 1) / 4 * sr * sr, 1e-12))
    return float(_N.cdf((sr - sr0) * np.sqrt(n - 1) / denom))


def independent_blocks(n_dates: int, horizon: int) -> int:
    """Roughly how many non-overlapping outcomes a run really contains."""
    return max(int(n_dates // max(horizon, 1)), 0)
