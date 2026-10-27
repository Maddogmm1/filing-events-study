"""Event-study engine for the filing-events protocol (Phase 5).

Everything is measured as daily abnormal return: the stock's return minus the equal-weight return, that day, of eligible
stocks in the same dollar-volume quintile the stock was in on the day before the event. Positions are summed into a
calendar-time portfolio so the statistics reflect what an account holding them would have seen, with costs spread over
each position's life. Development and validation runs never read prices on or after the sealed start."""
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from fe import stats as S
from fe.protocol import ProtocolError, file_hash

H1 = "H1_reaction_continuation"          # long: top-decile 3-day abnormal reaction to an earnings 8-K
H1S = "H1S_continuation_screened"       # H1 excluding companies with any bad filing in the previous 365 days
H2A = "H2A_late_filing"                 # short: NT 10-K / NT 10-Q
H2B = "H2B_non_reliance"                # short: 8-K Item 4.02
H2C = "H2C_auditor_change"              # short: 8-K Item 4.01 (without 4.02 in the same filing)
H2 = "H2_bad_filings_combined"
H3 = "H3_long_short_combined"           # H1 long and H2 combined short, held together
SHORT_KINDS = {H2A: ("late",), H2B: ("nonrel",), H2C: ("auditor",), H2: ("late", "nonrel", "auditor")}


@dataclass(frozen=True)
class EventProtocol:
    name: str
    min_price: float
    min_adv_usd: float
    max_adv_usd: float
    exclude_sic: tuple
    hold_sessions: int
    entry_offset: int
    dev_start: pd.Timestamp
    dev_end: pd.Timestamp
    validation_end: pd.Timestamp
    sealed_start: pd.Timestamp
    hypotheses: tuple
    cost_bps_one_way: float
    short_financing_annual: float
    sensitivity_cost_bps_one_way: float
    max_dev_trials: int
    min_events: dict
    fx_fee_bps: float
    sha256: str
    path: Path
    # D10b options; the defaults reproduce draft r3 behaviour exactly
    calendar: str = ""                          # "XNYS": sessions and close times from the NYSE calendar (D3c)
    dissemination_buffer_minutes: int = 0       # same-session day 0 only if accepted this long before the close (D3c)
    combined_short_kinds: tuple = ("late", "nonrel", "auditor")   # short leg of H2 and H3; ("late", "nonrel") if D2a
    dedupe_by: str = "kind"                     # "kind" (r3) or "side": one open position per company and side (D6b)
    h3_side_weighting: str = "position"         # "position" (r3) or "equal_sides": 0.5 long leg + 0.5 short leg (D6b)
    economic_threshold_net: float = 0.02        # smallest net 60-session effect worth acting on (D5); used by the bounds
    acceptance_time_source: str = "stored"      # "stored" (r3) or "sec_index": SEC's index-page time; events without one excluded (D10c)
    short_financing_stress_annual: tuple = ()   # extra short-financing scenarios reported with every result, e.g. (0.10, 0.20)
    open_entry_cost_stress_bps_one_way: float = 0.0   # extra one-way cost scenario for the open-entry variant (e.g. 150)
    survivorship_label_error_allowance: float = 0.0   # D10d: adverse bound moves this share of the side-favourable exit class
                                                      # (acquired for longs, failure for shorts) to the unfavourable outcome


UNAVAILABLE = ["historical bid-ask quotes (spreads are estimated from daily highs and lows instead)",
               "Trading 212 historical CFD financing rates (a flat assumption is used)",
               "historical borrow availability for shorting small companies",
               "delisting returns for companies that left the exchange (a frozen last price is used: abnormal return = minus the benchmark)",
               "prices for companies no longer listed (they are counted, not traded)",
               "which instruments Trading 212 offered at each past date",
               "financing on long CFD positions (not charged: longs are assumed to be bought as shares in the Invest or ISA account)"]


def load_event_protocol(path) -> EventProtocol:
    path = Path(path)
    d = tomllib.loads(path.read_text(encoding="utf-8"))
    if d.get("kind") != "event_study":
        raise ProtocolError(f"{path.name} is not an event-study protocol")
    ts = lambda k: pd.Timestamp(d[k])
    p = EventProtocol(name=d["name"], min_price=float(d["min_price"]), min_adv_usd=float(d["min_adv_usd"]),
                      max_adv_usd=float(d["max_adv_usd"]), exclude_sic=tuple(d.get("exclude_sic", [])),
                      hold_sessions=int(d["hold_sessions"]), entry_offset=3, dev_start=ts("dev_start"), dev_end=ts("dev_end"),
                      validation_end=ts("validation_end"), sealed_start=ts("sealed_start"), hypotheses=tuple(d["hypotheses"]),
                      cost_bps_one_way=float(d["cost_bps_one_way"]), short_financing_annual=float(d["short_financing_annual"]),
                      sensitivity_cost_bps_one_way=float(d.get("sensitivity_cost_bps_one_way", d["cost_bps_one_way"])),
                      max_dev_trials=int(d["max_dev_trials"]), min_events={k: int(v) for k, v in d["min_events"].items()},
                      fx_fee_bps=float(d.get("fx_fee_bps", 15)), sha256=file_hash(path), path=path,
                      calendar=str(d.get("calendar", "")),
                      dissemination_buffer_minutes=int(d.get("dissemination_buffer_minutes", 0)),
                      combined_short_kinds=tuple(d.get("combined_short_kinds", ["late", "nonrel", "auditor"])),
                      dedupe_by=str(d.get("dedupe_by", "kind")), h3_side_weighting=str(d.get("h3_side_weighting", "position")),
                      economic_threshold_net=float(d.get("economic_threshold_net", 0.02)),
                      acceptance_time_source=str(d.get("acceptance_time_source", "stored")),
                      short_financing_stress_annual=tuple(float(x) for x in d.get("short_financing_stress_annual", [])),
                      open_entry_cost_stress_bps_one_way=float(d.get("open_entry_cost_stress_bps_one_way", 0.0)),
                      survivorship_label_error_allowance=float(d.get("survivorship_label_error_allowance", 0.0)))
    if not 0.0 <= p.survivorship_label_error_allowance <= 1.0:
        raise ProtocolError("survivorship_label_error_allowance must be between 0 and 1")
    if p.acceptance_time_source not in ("stored", "sec_index"):
        raise ProtocolError("acceptance_time_source must be stored or sec_index")
    if not set(p.combined_short_kinds) <= {"late", "nonrel", "auditor"} or not p.combined_short_kinds:
        raise ProtocolError("combined_short_kinds must be a non-empty subset of late, nonrel, auditor")
    if p.dedupe_by not in ("kind", "side") or p.h3_side_weighting not in ("position", "equal_sides"):
        raise ProtocolError("dedupe_by must be kind or side; h3_side_weighting must be position or equal_sides")
    if p.calendar not in ("", "XNYS"):
        raise ProtocolError(f"unknown calendar {p.calendar!r}; use \"XNYS\" or leave it out")
    if not (p.dev_start < p.dev_end < p.validation_end < p.sealed_start):
        raise ProtocolError("dates must run dev_start < dev_end < validation_end < sealed_start")
    return p


# ---------------------------------------------------------------- data ---------------------------------------------------

def load_inputs(sc_con, p: EventProtocol, include_sealed: bool, exclusions: pd.DataFrame | None = None,
                masks: pd.DataFrame | None = None):
    """exclusions (D10a): rows of config/smallcap_exclusions.csv. Excluded tickers lose their prices; excluded companies
    lose their events and prices. Each exclusion carries a reason and evidence in the file."""
    from fe.data import ticker_choice_sql
    upper = "" if include_sealed else f"AND date < DATE '{p.sealed_start:%Y-%m-%d}'"
    px = sc_con.execute(f"SELECT ticker, date, adj_close, close, high, low, volume FROM sc_prices WHERE adj_close IS NOT NULL {upper}").df()
    ex_tickers, ex_ciks = set(), set()
    if exclusions is not None and len(exclusions):
        ex_tickers = {t for t in exclusions["ticker"] if t}
        ex_ciks = {int(c) for c in exclusions["cik"] if str(c).strip()}
        if ex_ciks:
            ex_tickers |= {r[0] for r in sc_con.execute(
                f"SELECT ticker FROM sc_tickers WHERE cik IN ({','.join(map(str, ex_ciks))})").fetchall()}
        px = px[~px["ticker"].isin(ex_tickers)]
    px["date"] = pd.to_datetime(px["date"])
    if masks is not None and len(masks):
        # D10e: masked days become missing prices (one-day bad prints, or the part of a spliced history before the splice)
        drop = pd.Series(False, index=px.index)
        for r in masks.itertuples():
            drop |= (px["ticker"] == r.ticker) & (px["date"] >= r.from_date) & (px["date"] <= r.to_date)
        px = px[~drop]
    adj = px.pivot(index="date", columns="ticker", values="adj_close").sort_index().astype("float64")
    dv = (px.assign(dv=px["close"] * px["volume"]).pivot(index="date", columns="ticker", values="dv")
          .reindex(index=adj.index, columns=adj.columns))
    close = px.pivot(index="date", columns="ticker", values="close").reindex(index=adj.index, columns=adj.columns)
    # Yahoo's close is adjusted for splits that happened LATER. Undo them so the $2 test sees the price as it traded.
    sp = sc_con.execute(f"SELECT ticker, ex_date, ratio FROM sc_splits WHERE ratio > 0 {upper.replace('date', 'ex_date')}").df()
    if len(sp):
        sp["ex_date"] = pd.to_datetime(sp["ex_date"])
        for t, g in sp.groupby("ticker"):
            if t not in close.columns:
                continue
            f = pd.Series(1.0, index=close.index)
            for _, r in g.iterrows():
                f[f.index < r["ex_date"]] *= r["ratio"]          # before a 4-for-1 split the traded price was 4x the adjusted one
            close[t] = close[t] * f
    high = px.pivot(index="date", columns="ticker", values="high").reindex(index=adj.index, columns=adj.columns)
    low = px.pivot(index="date", columns="ticker", values="low").reindex(index=adj.index, columns=adj.columns)
    excl = ",".join(str(int(x)) for x in p.exclude_sic) or "-1"
    has_truth = bool(sc_con.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'sc_acceptance_truth'").fetchone()[0])
    truth_col = "tr.accepted_ny AS accepted_truth" if has_truth else "CAST(NULL AS TIMESTAMP) AS accepted_truth"
    truth_join = "LEFT JOIN (SELECT accession, accepted_ny FROM sc_acceptance_truth WHERE status = 'ok') tr USING (accession)" if has_truth else ""
    ev = sc_con.execute(f"""
        SELECT e.accession, e.cik, e.form, e.filed, e.accepted_at, e.items, t.ticker, {truth_col}
        FROM sc_events e JOIN sc_filers f USING (cik)
        LEFT JOIN ({ticker_choice_sql("WHERE " + upper[4:] if upper else "")}) t USING (cik)
        {truth_join}
        WHERE coalesce(f.sic, 0) NOT IN ({excl}) {upper.replace('date', 'e.filed')}""").df()
    if ex_ciks:
        ev = ev[~ev["cik"].isin(ex_ciks)].copy()
    if ex_tickers:
        ev.loc[ev["ticker"].isin(ex_tickers), "ticker"] = None
    return adj, close, dv, ev, high, low


def classify(ev: pd.DataFrame) -> pd.DataFrame:
    """Original filings only (amendments do not create new events). Non-reliance outranks auditor change, which outranks earnings."""
    items = ev["items"].fillna("")
    eight_k = ev["form"] == "8-K"
    kind = np.select([ev["form"].isin(["NT 10-K", "NT 10-Q"]), eight_k & items.str.contains(r"4\.02"),
                      eight_k & items.str.contains(r"4\.01"), eight_k & items.str.contains(r"2\.02")],
                     ["late", "nonrel", "auditor", "earn"], "")
    return ev.assign(kind=kind)[kind != ""]


def nyse_calendar(start, end) -> tuple[pd.DatetimeIndex, pd.Series]:
    """NYSE sessions and each session's close as New York wall-clock time (13:00 on half-days). D3c."""
    import exchange_calendars as xc
    c = xc.get_calendar("XNYS", start=pd.Timestamp(start).strftime("%Y-%m-%d"), end=pd.Timestamp(end).strftime("%Y-%m-%d"))
    sessions = pd.DatetimeIndex(c.sessions).tz_localize(None) if c.sessions.tz is not None else pd.DatetimeIndex(c.sessions)
    closes = c.closes.dt.tz_convert("America/New_York").dt.tz_localize(None)
    closes.index = sessions
    return sessions, closes


def align_to_calendar(frames: list, sessions: pd.DatetimeIndex) -> tuple[list, int]:
    """Re-index price frames to exchange sessions: rows on non-session dates (stray weekend or holiday prints) are
    dropped and sessions with no price for anyone appear as empty rows. Returns the frames and the dropped-row count."""
    idx = frames[0].index
    keep = sessions[(sessions >= idx.min()) & (sessions <= idx.max())]
    dropped = int((~idx.isin(sessions)).sum())
    return [f.reindex(keep) for f in frames], dropped


def day_zero(sessions: pd.DatetimeIndex, ev: pd.DataFrame, closes: pd.Series | None = None,
             buffer_minutes: int = 0) -> np.ndarray:
    """Index of the first session in which the market could react to the filing.
    Without closes (draft r3): accepted at or after 16:00, or on a non-session day, moves to the next session.
    With closes (D3c): same session only if accepted at least buffer_minutes before that session's actual close
    (13:00 on half-days). With no acceptance time, the filing is treated as after the close (the later choice)."""
    acc = pd.to_datetime(ev["accepted_at"])
    filed = pd.to_datetime(ev["filed"])
    day = acc.dt.normalize().where(acc.notna(), filed)
    if closes is None:
        after = (acc.dt.hour >= 16) | acc.isna()
    else:
        cutoff = pd.Series(closes.reindex(day.values).values, index=acc.index) - pd.Timedelta(minutes=buffer_minutes)
        after = acc.isna() | ~(acc <= cutoff)
    idx = sessions.searchsorted(day.values)                         # first session on or after the day
    same = (idx < len(sessions)) & (sessions[np.minimum(idx, len(sessions) - 1)] == day.values)
    idx = np.where(same & after.values, idx + 1, idx)
    return idx


@dataclass
class Market:
    sessions: pd.DatetimeIndex
    cols: pd.Index
    ret: np.ndarray        # daily return, NaN where no price
    price_ok: np.ndarray   # a price exists that day
    elig: np.ndarray       # eligible on that day (price and dollar-volume band), judged with data up to that day
    quint: np.ndarray      # 1..5 dollar-volume quintile among eligible stocks, 0 if not eligible
    bench: np.ndarray      # (T, 6): equal-weight daily return of each quintile, using quintiles from the day before
    spread: np.ndarray     # 20-day mean Corwin-Schultz spread estimate up to that day (NaN where unavailable)


def build_market(adj, close, dv, p: EventProtocol, high=None, low=None) -> Market:
    # Return from the last traded price, so a move across a missing day is kept, not lost. Days without a price after the
    # first one count as 0 (price frozen); before the first price there is no return.
    P = adj.to_numpy(copy=True)
    Pf = adj.ffill().to_numpy()
    prevf = np.vstack([np.full((1, P.shape[1]), np.nan), Pf[:-1]])
    started = ~np.isnan(prevf)
    traded = ~np.isnan(P)
    ret = np.where(traded & started, P / prevf - 1.0, np.where(started, 0.0, np.nan))
    adv = dv.rolling(20).mean().values
    cl = close.values
    elig = (cl >= p.min_price) & (adv >= p.min_adv_usd) & (adv <= p.max_adv_usd)
    pct = pd.DataFrame(np.where(elig, adv, np.nan)).rank(axis=1, pct=True).values
    quint = np.where(elig, np.ceil(np.nan_to_num(pct) * 5).clip(1, 5), 0).astype(np.int8)
    prev = np.vstack([np.zeros((1, quint.shape[1]), np.int8), quint[:-1]])
    bench = np.full((len(adj), 6), np.nan)
    r0 = np.nan_to_num(ret)
    has = traded & started                                  # the benchmark uses stocks that actually traded that day
    for q in range(1, 6):
        m = (prev == q) & has
        n = m.sum(axis=1)
        bench[:, q] = np.where(n > 0, (r0 * m).sum(axis=1) / np.maximum(n, 1), np.nan)
    if high is not None and low is not None:
        spread = corwin_schultz_spread(high.where(high > 0), low.where(low > 0)).rolling(20, min_periods=10).mean().values
    else:
        spread = np.full(adj.shape, np.nan)
    return Market(adj.index, adj.columns, ret, traded, elig, quint, bench, spread)


def events_frame(m: Market, ev: pd.DataFrame, p: EventProtocol, closes: pd.Series | None = None) -> pd.DataFrame:
    """One row per usable event: column index, day 0, quintile on day -1, EAR, entry and exit indexes."""
    ev = classify(ev)
    ev = ev[ev["ticker"].isin(m.cols)].copy()
    if ev.empty:
        return ev.assign(col=[], d0=[], q=[], ear=[], entry=[], exit=[])
    ev["col"] = m.cols.get_indexer(ev["ticker"])
    ev["d0"] = day_zero(m.sessions, ev, closes, p.dissemination_buffer_minutes)
    T = len(m.sessions)
    ev = ev[(ev["d0"] >= 21) & (ev["d0"] + 2 < T)]
    pre = ev["d0"].values - 1
    ev["q"] = m.quint[pre, ev["col"].values]
    ev = ev[ev["q"] > 0]                                               # eligible on day -1 (price and dollar-volume band)
    d0, c, q = ev["d0"].values, ev["col"].values, ev["q"].values
    # reaction = abnormal return over days 0, +1, +2; known only after day +2 closes
    ear = sum(m.ret[d0 + k, c] - m.bench[d0 + k, q] for k in (0, 1, 2))
    ev["ear"] = ear
    # earnings: enter at the close of day +3, the first session after the signal exists.
    # bad filings: the filing itself is the signal, known by the close of day 0, so enter at the close of day +1.
    ev["entry"] = np.where(ev["kind"].values == "earn", d0 + 3, d0 + 1)
    ev["exit"] = ev["entry"] + p.hold_sessions
    ev["date0"] = m.sessions[np.minimum(d0, T - 1)]
    ev = ev.sort_values(["d0", "accession"])
    return ev


def dedupe_positions(pos: pd.DataFrame, by: str = "kind") -> pd.DataFrame:
    """One open position per company, side and category (by="kind", draft r3), or per company and side across all
    categories (by="side", D6b): a new one is taken only after the previous one has exited."""
    if pos.empty:
        return pos
    pos = pos.sort_values(["entry", "accession"])
    keep, last_exit = [], {}
    for i, k, c, side, a, b in zip(pos.index, pos["kind"], pos["cik"], pos["side"], pos["entry"], pos["exit"]):
        key = (k, c, side) if by == "kind" else (c, side)
        if key in last_exit and a <= last_exit[key]:
            continue
        last_exit[key] = b
        keep.append(i)
    return pos.loc[keep]


def select(evf: pd.DataFrame, hypothesis: str, decile: float = 0.9, lookback_days: int = 365, min_prior: int = 200,
           bad_filings: pd.DataFrame | None = None, combined_kinds: tuple | None = None, dedupe_by: str = "kind",
           placebo: str | None = None) -> pd.DataFrame:
    """Top-decile reactions are judged against the previous year of earnings events only, so the cut-off uses no future data."""
    out = []
    if hypothesis in (H1, H1S, H3):
        earn = evf[(evf["kind"] == "earn") & evf["ear"].notna()].sort_values("d0")
        dates, ears, longs = earn["date0"].values, earn["ear"].values, []
        for j in range(len(earn)):
            lo = np.searchsorted(dates, dates[j] - np.timedelta64(lookback_days, "D"))
            hi = np.searchsorted(dates, dates[j])                    # strictly earlier days only
            if hi - lo >= min_prior and (ears[j] > np.quantile(ears[lo:hi], decile) if placebo is None else True):
                longs.append(earn.index[j])
        if placebo == "random_earnings_10pct":
            # V6: the same eligibility and history requirement, but a random 10% (seed 0) instead of the top decile
            rng = np.random.default_rng(0)
            longs = list(np.array(longs)[rng.random(len(longs)) < 0.10]) if longs else []
        elif placebo is not None:
            raise ValueError(f"unknown placebo {placebo!r}")
        L = evf.loc[longs].assign(side=1)
        if hypothesis == H1S and len(L):
            # screen against EVERY bad filing the company made, priced or not, eligible or not
            bad = bad_filings if bad_filings is not None else evf[evf["kind"] != "earn"].assign(when=evf["date0"])[["cik", "when"]]
            by = {c: np.sort(pd.to_datetime(g["when"]).values) for c, g in bad.groupby("cik")}
            def flagged(row):
                b = by.get(row.cik)
                if b is None:
                    return False
                t = np.datetime64(row.date0)
                lo = np.searchsorted(b, t - np.timedelta64(365, "D"))
                hi = np.searchsorted(b, t)
                return hi > lo
            L = L[[not flagged(r) for r in L.itertuples()]]
        out.append(L)
    if hypothesis in (H2, H3):
        kinds = tuple(combined_kinds) if combined_kinds else SHORT_KINDS[H2]
    else:
        kinds = SHORT_KINDS.get(hypothesis, ())
    if kinds:
        out.append(evf[evf["kind"].isin(kinds)].assign(side=-1))
    return dedupe_positions(pd.concat(out), by=dedupe_by) if out else evf.iloc[0:0].assign(side=[])


def window_mask(m: Market, evf: pd.DataFrame, p: EventProtocol, window: str) -> np.ndarray:
    T = len(m.sessions)
    start = m.sessions[np.minimum(evf["d0"].values, T - 1)]
    has_exit = evf["exit"].values < T
    end = m.sessions[np.minimum(evf["exit"].values, T - 1)]
    if window == "dev":
        return (start >= p.dev_start) & has_exit & (end <= p.dev_end)
    if window == "validation":
        return (start > p.dev_end) & has_exit & (end <= p.validation_end)
    return (start >= p.sealed_start) & has_exit


def position_costs(m: Market, pos: pd.DataFrame, p: EventProtocol, scenario: str) -> tuple[np.ndarray, int]:
    """One-way cost per position. 'primary' and 'stress' are flat assumptions; 'estimated' is half the Corwin-Schultz spread
    at entry plus the FX fee, falling back to the primary assumption where no estimate exists (the count is reported)."""
    n = len(pos)
    if scenario == "primary":
        return np.full(n, p.cost_bps_one_way / 1e4), 0
    if scenario == "stress":
        return np.full(n, p.sensitivity_cost_bps_one_way / 1e4), 0
    est = m.spread[pos["d0"].values - 1, pos["col"].values] / 2 + p.fx_fee_bps / 1e4    # estimated from data before day 0
    missing = int(np.isnan(est).sum())
    return np.where(np.isnan(est), p.cost_bps_one_way / 1e4, est), missing


@dataclass
class OpenEntry:
    """Same-day open-to-close data for the day +3 open-entry variant (D4 / V5). Built from Yahoo's open and close of the
    same row (both on the same split basis)."""
    oc: np.ndarray        # (T, N) close / open - 1 on each day
    valid: np.ndarray     # (T, N) open present, > 0, within [low, high], volume > 0
    bench: np.ndarray     # (T, 6) equal-weight open-to-close return of each dollar-volume quintile (quintiles from the day before)


def build_open_entry(sc_con, m: Market, p: EventProtocol, include_sealed: bool = False) -> OpenEntry:
    upper = "" if include_sealed else f"AND date < DATE '{p.sealed_start:%Y-%m-%d}'"
    px = sc_con.execute(f"SELECT ticker, date, open, high, low, close, volume FROM sc_prices WHERE close IS NOT NULL {upper}").df()
    px["date"] = pd.to_datetime(px["date"])
    piv = {c: px.pivot(index="date", columns="ticker", values=c).reindex(index=m.sessions, columns=m.cols).to_numpy()
           for c in ("open", "high", "low", "close", "volume")}
    o = piv["open"]
    with np.errstate(invalid="ignore", divide="ignore"):
        valid = (o > 0) & (o >= piv["low"] * 0.999) & (o <= piv["high"] * 1.001) & (piv["volume"] > 0) & (piv["close"] > 0)
        oc = np.where(valid, piv["close"] / o - 1.0, np.nan)
    prev = np.vstack([np.zeros((1, m.quint.shape[1]), np.int8), m.quint[:-1]])
    bench = np.full((len(m.sessions), 6), np.nan)
    for q in range(1, 6):
        mk = (prev == q) & valid
        n = mk.sum(axis=1)
        bench[:, q] = np.where(n > 0, np.nansum(np.where(mk, oc, 0.0), axis=1) / np.maximum(n, 1), np.nan)
    return OpenEntry(oc, valid, bench)


def evaluate(m: Market, pos: pd.DataFrame, p: EventProtocol, n_trials: int, scenario: str = "primary",
             side_weighting: str = "position", open_entry: OpenEntry | None = None) -> dict:
    """side_weighting="equal_sides" (H3 under D6b): each session the portfolio is 0.5 x the equal-weight mean of open long
    positions plus 0.5 x that of open short positions; a side with nothing open contributes 0 (cash). The primary
    estimand is then the mean monthly net return of that portfolio, with a 3-month block-bootstrap interval."""
    costs, cost_missing = position_costs(m, pos, p, scenario)
    fin = p.short_financing_annual / 252
    T = len(m.sessions)
    tot = np.zeros(T)
    cnt = np.zeros(T)
    tot_s = {1: np.zeros(T), -1: np.zeros(T)}
    cnt_s = {1: np.zeros(T), -1: np.zeros(T)}
    per_event, gross_event, trunc, open_used, open_fallback = [], [], 0, 0, 0
    # last session with a traded price, per stock (finding F1: returns after the last price are stored as 0, not NaN,
    # so truncation must be read from the traded-price mask, not from NaN returns)
    traded_idx = np.where(m.price_ok, np.arange(len(m.sessions))[:, None], -1)
    last_traded = traded_idx.max(axis=0)
    kinds = pos["kind"].values if "kind" in pos else np.array(["?"] * len(pos))
    for c, q, a, b, side, cost, kind in zip(pos["col"].values, pos["q"].values, pos["entry"].values, pos["exit"].values,
                                           pos["side"].values, costs, kinds):
        if open_entry is not None and kind == "earn" and bool(open_entry.valid[a, c]):
            # enter at the open of the entry day: that day's open-to-close return, then 59 more closes (60 sessions held)
            s0, s1 = a, a + (b - a) - 1
            r = np.r_[open_entry.oc[a, c], m.ret[a + 1:s1 + 1, c]]
            bm = np.r_[open_entry.bench[a, q], m.bench[a + 1:s1 + 1, q]]
            open_used += 1
        else:
            s0, s1 = a + 1, b
            r, bm = m.ret[a + 1:b + 1, c], m.bench[a + 1:b + 1, q]
            open_fallback += int(open_entry is not None and kind == "earn")
        alive = ~np.isnan(r)
        trunc += int(last_traded[c] < s1)
        abn = np.where(alive, r - bm, 0.0)                              # after the last price the position is frozen (zero)
        daily_cost = 2 * cost / len(abn) + (fin if side < 0 else 0.0)
        net = side * np.nan_to_num(abn) - daily_cost
        tot[s0:s1 + 1] += net
        cnt[s0:s1 + 1] += 1
        tot_s[int(np.sign(side))][s0:s1 + 1] += net
        cnt_s[int(np.sign(side))][s0:s1 + 1] += 1
        per_event.append(net.sum())
        gross_event.append(side * np.nan_to_num(abn).sum())
    per_event = np.array(per_event)
    if len(per_event) == 0:
        raise ValueError("no events in this window")
    if side_weighting == "equal_sides":
        legs = [np.where(cnt_s[k] > 0, tot_s[k] / np.maximum(cnt_s[k], 1), 0.0) for k in (1, -1)]
        port = pd.Series(0.5 * legs[0] + 0.5 * legs[1], index=m.sessions)
    else:
        port = pd.Series(np.where(cnt > 0, tot / np.maximum(cnt, 1), 0.0), index=m.sessions)
    active = port[(cnt > 0)]
    monthly = port.loc[active.index.min():active.index.max()].groupby(pd.Grouper(freq="ME")).sum()
    months = pos["date0"].dt.to_period("M").values
    lo, hi = cluster_bootstrap(per_event, months)
    estimand, centre = "mean net abnormal return per position", float(per_event.mean())
    if side_weighting == "equal_sides":
        estimand, centre = "mean monthly net return of the 50/50 long-short portfolio", float(monthly.mean())
        lo, hi = S.block_bootstrap_ci(monthly.values, block=3)
    by_year = pd.Series(per_event, index=pos["date0"].dt.year.values).groupby(level=0).mean()
    conc = concentration(per_event)
    return {"n_dates": int(len(monthly)), "first_date": monthly.index.min().date(), "last_date": monthly.index.max().date(),
            "mean_ic": centre, "ic_ci_low": lo, "ic_ci_high": hi,
            "nw_t": S.newey_west_t(monthly.values, 3), "spread_gross": float(np.mean(gross_event)), "spread_net": float(per_event.mean()),
            "sharpe": S.sharpe(monthly.values, 12), "dsr": S.deflated_sharpe(monthly.values, n_trials),
            "detail": {"estimand": estimand, "side_weighting": side_weighting, "cost_scenario": scenario,
                       "entry": "open of day +3 where valid" if open_entry is not None else "close",
                       "open_entries": open_used, "open_entry_fallbacks_to_close": open_fallback, "cost_estimate_missing": cost_missing, "mean_one_way_cost": float(costs.mean()),
                       "n_events": int(len(per_event)), "n_long": int((pos["side"] > 0).sum()), "n_short": int((pos["side"] < 0).sum()),
                       "truncated_share": trunc / len(per_event), "mean_open_positions": float(cnt[cnt > 0].mean()),
                       "monthly_mean": float(monthly.mean()), "concentration": conc, "by_year_mean_net": {int(k): round(float(v), 5) for k, v in by_year.items()},
                       "monthly": {d.strftime("%Y-%m"): round(float(v), 5) for d, v in monthly.items()}}}


def required_positions(effect: float, sd: float = 0.25, alpha: float = 0.05, power: float = 0.80,
                       design_effect: float = 1.0) -> int:
    """Positions needed to detect a mean `effect` (two-sided test at alpha, given power), assuming per-position standard
    deviation `sd`, inflated by a design effect for overlap and clustering. Always rounded UP (finding F7)."""
    from statistics import NormalDist
    z = NormalDist().inv_cdf(1 - alpha / 2) + NormalDist().inv_cdf(power)
    return int(np.ceil(((z * sd / effect) ** 2) * design_effect - 1e-9))


def concentration(x: np.ndarray) -> dict:
    """Reporting only (D10a): how much of the total net return comes from the best 5% of positions, and the mean with
    the top and bottom 1% winsorised. A long book in small companies is often carried by a handful of names."""
    x = np.asarray(x, float)
    n = len(x)
    if n == 0:
        return {"top5pct_share_of_total": float("nan"), "mean_winsorised_1pct": float("nan"), "n_top5pct": 0}
    k = max(1, int(np.ceil(0.05 * n)))
    tot = float(x.sum())
    top = float(np.sort(x)[-k:].sum())
    lo, hi = np.quantile(x, [0.01, 0.99])
    return {"top5pct_share_of_total": top / tot if tot > 0 else float("nan"), "n_top5pct": k,
            "mean_winsorised_1pct": float(np.clip(x, lo, hi).mean()), "total_net": tot}


# Survivorship stress outcomes (D10a; values fixed in the FE Owner Decision Pack v1, section C4): the STOCK's raw return
# over the holding period for a company that left the exchange inside the window. Assumptions, not measurements;
# -0.55 is Shumway and Warther (1999)'s corrected return for performance-related Nasdaq delistings.
STRESS_OUTCOMES = {
    1:  {"failure": {"favourable": -0.30, "central": -0.55, "adverse": -1.00},
         "acquired": {"favourable": 0.30, "central": 0.15, "adverse": 0.00}},
    -1: {"failure": {"favourable": -1.00, "central": -0.55, "adverse": -0.30},
         "acquired": {"favourable": 0.00, "central": 0.15, "adverse": 0.30}},
}


def survivorship_bounds(m: Market, ev_all: pd.DataFrame, delist: pd.DataFrame | None, pos: pd.DataFrame, res: dict,
                        p: EventProtocol, hypothesis: str, window: str, economic_threshold: float = 0.02) -> dict:
    """Bounds on the mean net abnormal return per position if the events whose company has no price had been tradable.
    Point estimate only; intervals and test statistics are not recomputed. See the decision pack, section C4."""
    if hypothesis == H3:
        return {"not_computed": "H3 mixes sides; read the bounds of its components"}
    if delist is None:
        return {"not_available": "no delisting table (run smallcap-refresh-listing-events)"}
    side = 1 if hypothesis in (H1, H1S) else -1
    kinds = ("earn",) if side == 1 else SHORT_KINDS[hypothesis]
    cls = classify(ev_all)
    filed = pd.to_datetime(cls["filed"])
    lo, hi = (p.dev_start, p.dev_end) if window == "dev" else (p.dev_end + pd.Timedelta(days=1), p.validation_end)
    w = cls[cls["kind"].isin(kinds) & (filed >= lo) & (filed <= hi)].copy()
    priced_mask = w["ticker"].isin(m.cols)
    n_priced_events, unpriced = int(priced_mask.sum()), w[~priced_mask].copy()
    n_p = int(len(pos))
    if n_priced_events == 0 or n_p == 0:
        return {"not_available": "no priced events in the window"}
    rate = n_p / n_priced_events             # positions per priced event: eligibility, decile and de-duplication together
    d = delist[["cik", "exit_date", "cause"]].copy()
    d["exit_date"] = pd.to_datetime(d["exit_date"])
    unpriced["filed"] = pd.to_datetime(unpriced["filed"])
    u = unpriced.merge(d, on="cik", how="left")
    horizon = pd.Timedelta(days=int(np.ceil((p.hold_sessions + 3) * 7 / 5)) + 5)   # calendar span of entry plus holding
    inside = u["exit_date"].notna() & (u["exit_date"] >= u["filed"]) & (u["exit_date"] <= u["filed"] + horizon)
    u["cls"] = np.where(~inside, "no_exit", np.where(u["cause"].isin(["bankruptcy", "listing_failure"]), "failure",
                        np.where(u["cause"] == "acquired", "acquired", "unknown")))
    counts = u["cls"].value_counts().to_dict()
    m_p = float(res["spread_net"])
    se = (res["ic_ci_high"] - res["ic_ci_low"]) / (2 * 1.96) if np.isfinite(res["ic_ci_high"]) else 0.0
    cost = 2 * p.cost_bps_one_way / 1e4 + (p.short_financing_annual / 252 * p.hold_sessions if side < 0 else 0.0)
    a_err = float(p.survivorship_label_error_allowance)
    out = {}
    for scen in ("favourable", "central", "adverse"):
        o = STRESS_OUTCOMES[side]
        fail, acq = o["failure"][scen], o["acquired"][scen]
        if scen == "central":
            unk = 0.5 * (fail + acq)
        elif scen == "favourable":
            unk = acq if side > 0 else fail
        else:
            unk = fail if side > 0 else acq
        net = {"failure": side * fail - cost, "acquired": side * acq - cost, "unknown": side * unk - cost,
               "no_exit": m_p - (se if scen == "adverse" else 0.0)}
        if scen == "adverse" and a_err:
            # D10d: cause labels can be wrong; in the adverse scenario a share of the class that favours the position takes
            # the unfavourable outcome (acquired -> failure for longs, failure -> acquired for shorts)
            fav, unf = ("acquired", "failure") if side > 0 else ("failure", "acquired")
            net[fav] = (1 - a_err) * net[fav] + a_err * net[unf]
        variants = [("", net)]
        if scen == "adverse":
            worst = min(side * fail - cost, side * acq - cost)
            variants.append(("label_free_", {"failure": worst, "acquired": worst, "unknown": worst, "no_exit": net["no_exit"]}))
        for prefix, nv in variants:
            for label, r in (("rate", rate), ("half_rate", rate / 2)):
                add_n = sum(r * counts.get(k, 0) for k in nv)
                add_sum = sum(r * counts.get(k, 0) * v for k, v in nv.items())
                key = f"{scen}_{label}" if not prefix else f"{scen}_{prefix}{label}"
                out[key] = (n_p * m_p + add_sum) / (n_p + add_n) if (n_p + add_n) else float("nan")
    return {"side": side, "priced_events": n_priced_events, "positions": n_p, "positions_per_priced_event": rate,
            "unpriced_events": int(len(u)), "unpriced_by_class": {k: int(v) for k, v in counts.items()},
            "bounded_mean_net": out, "economic_threshold": economic_threshold,
            "robust_to_survivorship": bool(out["adverse_rate"] >= economic_threshold / 2),
            "label_error_allowance": a_err,
            "label_free_note": "adverse_label_free_*: every exit inside the window takes the worst outcome whatever its cause "
                               "label; a sensitivity, not the robustness test (D10d)",
            "limitations": "point estimate only; imputed outcomes are raw stock returns, not benchmark-adjusted; outcome "
                           "values and the positions-per-event rate are assumptions; companies that changed CIK count as unpriced"}


def cluster_bootstrap(x: np.ndarray, groups, n_boot: int = 2000, seed: int = 0, block: int = 3) -> tuple[float, float]:
    """Moving-block bootstrap over calendar months of entry. Positions held 60 sessions overlap about three months, so
    blocks of three consecutive months are resampled together rather than single months."""
    g = pd.Series(x).groupby(pd.PeriodIndex(pd.Series(groups).values, freq="M"))
    months = pd.period_range(g.sum().index.min(), g.sum().index.max(), freq="M")
    sums = g.sum().reindex(months, fill_value=0.0).values
    ns = g.count().reindex(months, fill_value=0).values
    k = len(months)
    if k < 6:
        return float("nan"), float("nan")
    block = min(block, k)
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(k / block))
    vals = np.empty(n_boot)
    off = np.arange(block)
    for i in range(n_boot):
        idx = ((rng.integers(0, k, n_blocks)[:, None] + off[None, :]) % k).ravel()[:k]
        n = ns[idx].sum()
        vals[i] = sums[idx].sum() / n if n else np.nan
    return float(np.nanquantile(vals, 0.025)), float(np.nanquantile(vals, 0.975))


def verdict(res: dict, min_events: int) -> str:
    """INCONCLUSIVE when there are too few events to have a fair chance of detecting the target effect; otherwise PASS
    only if every check holds."""
    if res["detail"]["n_events"] < min_events:
        return f"INCONCLUSIVE: {res['detail']['n_events']} events, fewer than the {min_events} the protocol requires"
    checks = {"net abnormal return interval excludes zero": res["ic_ci_low"] > 0, "Newey-West t above 2": res["nw_t"] > 2,
              "deflated Sharpe at least 0.95": (res["dsr"] or 0) >= 0.95}
    failed = [k for k, v in checks.items() if not v]
    return "PASS" if not failed else "FAIL: " + "; ".join(failed)


def corwin_schultz_spread(high: pd.DataFrame, low: pd.DataFrame) -> pd.DataFrame:
    """Corwin and Schultz (2012) bid-ask spread estimate from daily highs and lows; negative estimates set to zero.
    Used only for the instrument-specific cost scenario, because no historical quote data is available for free."""
    hl = np.log(high / low) ** 2
    beta = hl + hl.shift(1)
    h2 = np.maximum(high, high.shift(1))
    l2 = np.minimum(low, low.shift(1))
    gamma = np.log(h2 / l2) ** 2
    k = 3 - 2 * np.sqrt(2)
    alpha = (np.sqrt(2 * beta) - np.sqrt(beta)) / k - np.sqrt(gamma / k)
    spread = 2 * (np.exp(alpha) - 1) / (1 + np.exp(alpha))
    return spread.clip(lower=0)


def run(con, sc_con, root, p: EventProtocol, hypothesis: str, window: str, confirm_sealed: bool = False, log=print,
        variant: dict | None = None) -> dict:
    from fe import registry as reg
    from fe.registry import code_version
    from fe.protocol import require_locked
    if hypothesis not in p.hypotheses:
        raise ValueError(f"{hypothesis} is not one of the protocol's hypotheses")
    require_locked(root, p)
    params = {"hypothesis": hypothesis, **(variant or {})}
    reg.check_may_run(con, p, "event_study", params, window, confirm_sealed)
    if window == "sealed":
        reg.record_sealed_opening(con, p, None, f"opened for {hypothesis}")
    from fe.data import load_exclusions
    excl = load_exclusions(Path(root) / "config" / "smallcap_exclusions.csv")
    from fe.data import load_price_masks
    masks = load_price_masks(Path(root) / "config" / "smallcap_price_masks.csv")
    adj, close, dv, ev, high, low = load_inputs(sc_con, p, include_sealed=(window == "sealed"), exclusions=excl, masks=masks)
    log(f"loaded {adj.shape[1]:,} tickers, {adj.shape[0]:,} sessions up to {adj.index.max():%Y-%m-%d}; {len(ev):,} SEC events")
    q = p if not variant or "hold_sessions" not in variant else EventProtocol(**{**p.__dict__, "hold_sessions": int(variant["hold_sessions"])})
    ev_all = ev                     # every filing: the H1S screen and the coverage counts use all of them
    time_detail = {"source": q.acceptance_time_source}
    if q.acceptance_time_source == "sec_index":
        # D10c: use SEC's own acceptance time; an event with a price but no verified time is excluded and counted, never
        # silently given the stored time (which carries 0, 1 or 2 UTC conversions)
        priced = ev["ticker"].isin(adj.columns)
        missing = priced & ev["accepted_truth"].isna()
        time_detail.update({"priced_events": int(priced.sum()), "excluded_no_verified_time": int(missing.sum()),
                            "changed_by_truth": int((priced & ev["accepted_truth"].notna()
                                                     & (pd.to_datetime(ev["accepted_truth"]) != pd.to_datetime(ev["accepted_at"]))).sum())})
        try:   # D10d reporting: of those, how many were in the D10c scope (could have been eligible on some candidate time)
            from fe.data import acceptance_scope
            scope = acceptance_scope(sc_con, q.sealed_start, q.min_adv_usd, q.max_adv_usd)
            time_detail["excluded_no_verified_time_in_scope"] = int((missing & ev["accession"].isin(scope["accession"])).sum())
        except Exception as e:  # reporting only; never blocks a run
            time_detail["excluded_no_verified_time_in_scope"] = f"not computed: {type(e).__name__}"
        ev = ev[~missing].copy()
        ev["accepted_at"] = ev["accepted_truth"].where(ev["accepted_truth"].notna(), ev["accepted_at"])
    closes, dropped = None, 0
    if q.calendar == "XNYS":
        sessions, closes = nyse_calendar(adj.index.min(), adj.index.max())
        (adj, close, dv, high, low), dropped = align_to_calendar([adj, close, dv, high, low], sessions)
    m = build_market(adj, close, dv, q, high, low)
    evf = events_frame(m, ev, q, closes)
    allbad = classify(ev_all)
    allbad = allbad[allbad["kind"] != "earn"].assign(when=pd.to_datetime(allbad["filed"]))[["cik", "when"]]
    pos = select(evf, hypothesis, decile=float((variant or {}).get("decile", 0.9)), bad_filings=allbad,
                 combined_kinds=q.combined_short_kinds, dedupe_by=q.dedupe_by, placebo=(variant or {}).get("placebo"))
    pos = pos[window_mask(m, pos, q, window)]
    if pos.empty:
        raise ValueError(f"no {hypothesis} events in the {window} window")
    n_trials = p.max_dev_trials        # deflate by the whole budget committed in advance, so run order cannot matter
    sw = q.h3_side_weighting if hypothesis == H3 else "position"
    oe = None
    if (variant or {}).get("entry") == "open":
        if hypothesis not in (H1, H1S):
            raise ValueError("the open-entry variant applies to H1 and H1S only")
        oe = build_open_entry(sc_con, m, q, include_sealed=(window == "sealed"))
    elif (variant or {}).get("entry") not in (None, "close"):
        raise ValueError("entry must be close or open")
    res = evaluate(m, pos, q, n_trials, side_weighting=sw, open_entry=oe)
    sens = evaluate(m, pos, q, n_trials, "stress", side_weighting=sw, open_entry=oe)
    est = evaluate(m, pos, q, n_trials, "estimated", side_weighting=sw, open_entry=oe)
    kinds = classify(ev_all)
    in_win = kinds[(pd.to_datetime(kinds["filed"]) >= (p.dev_start if window == "dev" else p.dev_end + pd.Timedelta(days=1) if window == "validation" else p.sealed_start))
                   & (pd.to_datetime(kinds["filed"]) <= (p.dev_end if window == "dev" else p.validation_end if window == "validation" else pd.Timestamp.max))]
    res["detail"]["sec_events_in_window"] = int(len(in_win))
    res["detail"]["usable_events_in_window"] = int(window_mask(m, evf, q, window).sum())
    res["detail"]["stress_net_mean"] = sens["spread_net"]
    res["detail"]["stress_cost_bps"] = p.sensitivity_cost_bps_one_way
    res["detail"]["estimated_cost_net_mean"] = est["spread_net"]
    res["detail"]["estimated_mean_one_way_cost"] = est["detail"]["mean_one_way_cost"]
    res["detail"]["estimated_cost_missing"] = est["detail"]["cost_estimate_missing"]
    res["detail"]["min_events"] = p.min_events.get(hypothesis, 0)
    res["detail"]["unavailable_data"] = UNAVAILABLE
    res["detail"]["exclusions_applied"] = int(len(excl))
    res["detail"]["price_masks_applied"] = int(len(masks))
    res["detail"]["acceptance_time"] = time_detail
    for fs in q.short_financing_stress_annual:
        if (pos["side"] < 0).any():
            alt = EventProtocol(**{**q.__dict__, "short_financing_annual": fs})
            res["detail"].setdefault("short_financing_stress", {})[f"{fs:.0%}"] = evaluate(m, pos, alt, n_trials, side_weighting=sw,
                                                                                            open_entry=oe)["spread_net"]
    if oe is not None and q.open_entry_cost_stress_bps_one_way:
        alt = EventProtocol(**{**q.__dict__, "cost_bps_one_way": q.open_entry_cost_stress_bps_one_way})
        res["detail"]["open_entry_cost_stress"] = {"cost_bps_one_way": q.open_entry_cost_stress_bps_one_way,
                                                   "net_mean": evaluate(m, pos, alt, n_trials, side_weighting=sw, open_entry=oe)["spread_net"]}
    res["detail"]["calendar"] = {"name": q.calendar or "price dates", "non_session_rows_dropped": dropped,
                                 "dissemination_buffer_minutes": q.dissemination_buffer_minutes}
    try:
        delist = sc_con.execute("SELECT cik, exit_date, cause FROM sc_delistings").df()
    except Exception:
        delist = None
    res["detail"]["survivorship_bounds"] = survivorship_bounds(m, ev_all, delist, pos, res, q, hypothesis, window,
                                                               economic_threshold=q.economic_threshold_net)
    res["verdict"] = verdict(res, p.min_events.get(hypothesis, 0))
    eid = reg.record(con, p, "event_study", params, window, res, code_version(Path(root)))
    res["experiment_id"] = eid
    return res


def readiness(sc_con, p: EventProtocol) -> dict:
    """Data-readiness report. It counts and checks; it computes no strategy return and reads no sealed-window prices."""
    from fe import data as sc
    out: dict = {"protocol": p.name, "unavailable_data": UNAVAILABLE}
    n_tickers = sc_con.execute("SELECT COUNT(*) FROM sc_tickers").fetchone()[0]
    fetch = sc_con.execute("SELECT status, COUNT(*) FROM (SELECT ticker, arg_max(status, fetched_at) AS status FROM sc_fetch_log GROUP BY 1) "
                           "GROUP BY 1").fetchall()
    out["tickers"] = {"listed_tickers": int(n_tickers), "fetch_status": {k: int(v) for k, v in fetch}}
    out["filers"] = int(sc_con.execute("SELECT COUNT(*) FROM sc_filers").fetchone()[0])
    cov = sc.coverage(sc_con, before=p.sealed_start)
    out["coverage_by_year_and_kind"] = cov
    hours = sc_con.execute("SELECT hour(accepted_at) AS h, COUNT(*) AS n FROM sc_events WHERE form = '8-K' AND items LIKE '%2.02%' "
                           "AND accepted_at IS NOT NULL GROUP BY 1 ORDER BY 1").df()
    out["earnings_8k_acceptance_hours"] = hours
    if len(hours):
        tot = hours["n"].sum()
        et_like = hours[hours["h"].between(16, 17)]["n"].sum() / tot      # earnings after the US close, if times are New York time
        utc_like = hours[hours["h"].between(20, 21)]["n"].sum() / tot     # the same releases, if times were UTC
        out["acceptance_time_check"] = {"share_16_to_17h": round(float(et_like), 3), "share_20_to_21h": round(float(utc_like), 3),
                                        "reading": "consistent with New York time" if et_like > 2 * utc_like else
                                        "NOT consistent with New York time: day-zero assignment must be fixed before any run"}
    q = sc_con.execute(f"""SELECT COUNT(*) AS rows, COUNT(DISTINCT ticker) AS tickers, MIN(date) AS first, MAX(date) AS last,
            AVG(CASE WHEN volume = 0 THEN 1 ELSE 0 END) AS zero_volume_share,
            SUM(CASE WHEN high < low OR close > high * 1.001 OR close < low * 0.999 THEN 1 ELSE 0 END) AS bad_ohlc_rows
            FROM sc_prices WHERE date < DATE '{p.sealed_start:%Y-%m-%d}'""").df()
    out["price_quality_before_sealed_start"] = q
    if q["rows"].iloc[0]:
        adj, close, dv, ev, high, low = load_inputs(sc_con, p, include_sealed=False)
        r = adj.pct_change(fill_method=None)
        out["extreme_daily_moves_over_80pct"] = int((r.abs() > 0.8).sum().sum())
        m = build_market(adj, close, dv, p, high, low)
        evf = events_frame(m, ev, p)
        rows = []
        for w in ("dev", "validation"):
            mask = window_mask(m, evf, p, w)
            sub = evf[mask]
            for kind, label in [("earn", "earnings 8-Ks (H1 takes about the top 10%)"), ("late", "late filing notices (H2A)"),
                                ("nonrel", "non-reliance 4.02 (H2B)"), ("auditor", "auditor change 4.01 (H2C)")]:
                n = int((sub["kind"] == kind).sum())
                need_key = {"earn": H1, "late": H2A, "nonrel": H2B, "auditor": H2C}[kind]
                need = p.min_events.get(need_key, 0)
                expected = n // 10 if kind == "earn" else n
                rows.append({"window": w, "events": label, "eligible_with_prices": n, "expected_positions": expected,
                             "protocol_minimum": need, "status": "enough" if expected >= need else "INCONCLUSIVE expected"})
        out["eligible_event_counts"] = pd.DataFrame(rows)
        spread = np.nanmean(m.spread[m.elig]) if m.elig.any() else float("nan")
        out["median_estimated_spread_eligible"] = float(np.nanmedian(m.spread[m.elig])) if m.elig.any() else float("nan")
        out["mean_estimated_spread_eligible"] = float(spread)
    return out


def readiness_markdown(r: dict) -> str:
    def tbl(df):
        return df.to_string(index=False) if isinstance(df, pd.DataFrame) and len(df) else "(none)"
    parts = [f"# Data-readiness report: {r['protocol']}", "", "No strategy returns were computed for this report, and no price on or after the "
             "sealed start was read.", "", f"Operating-company filers known to SEC: {r['filers']:,}",
             f"Listed tickers (Nasdaq/NYSE): {r['tickers']['listed_tickers']:,}; latest fetch status: {r['tickers']['fetch_status']}", "",
             "## Coverage of SEC events by prices", "```", tbl(r["coverage_by_year_and_kind"]), "```", "",
             "## Acceptance-time check", "```", tbl(r.get("earnings_8k_acceptance_hours")), "```", str(r.get("acceptance_time_check", "no data")), "",
             "## Price quality (before the sealed start)", "```", tbl(r["price_quality_before_sealed_start"]), "```",
             f"Daily moves larger than 80%: {r.get('extreme_daily_moves_over_80pct', 'n/a')}",
             f"Estimated spread on eligible stock-days (Corwin-Schultz): median {r.get('median_estimated_spread_eligible', float('nan')):.2%}, "
             f"mean {r.get('mean_estimated_spread_eligible', float('nan')):.2%}", "",
             "## Eligible events per hypothesis and window (counts only)", "```", tbl(r.get("eligible_event_counts")), "```", "",
             "## Data that is not available (reported, not filled in)"] + [f"- {u}" for u in r["unavailable_data"]]
    return "\n".join(parts) + "\n"
