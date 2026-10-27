from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fe import data as sc
from fe import events as E
from fe import registry as reg
from fe.protocol import ProtocolError, write_lock
from fe.data import connect, open_smallcap

ROOT = Path(__file__).resolve().parents[1]

PROTO = """name = "{name}"
kind = "event_study"
exclude_sic = [6770]
min_price = 2.0
min_adv_usd = 200000
max_adv_usd = 20000000
hold_sessions = 60
dev_start = "2005-01-01"
dev_end = "2015-12-31"
validation_end = "2019-12-31"
sealed_start = "2020-01-01"
hypotheses = ["H1_reaction_continuation", "H1S_continuation_screened", "H2A_late_filing", "H2B_non_reliance",
              "H2C_auditor_change", "H2_bad_filings_combined", "H3_long_short_combined"]
cost_bps_one_way = 100
sensitivity_cost_bps_one_way = 200
fx_fee_bps = 15
short_financing_annual = 0.06
max_dev_trials = 17
[min_events]
H1_reaction_continuation = {m}
H1S_continuation_screened = {m}
H2A_late_filing = {m}
H2B_non_reliance = 30
H2C_auditor_change = 30
H2_bad_filings_combined = {m}
H3_long_short_combined = {m}
"""


def build(tmp_path, drift_k=0.0, bad_drift=0.0, n=150, seed=3):
    """Synthetic market: quarterly earnings shocks on day 0; with drift_k > 0 the shock keeps going after day +3.
    Late-filing notices with bad_drift > 0 are followed by a decline."""
    rng = np.random.default_rng(seed)
    days = pd.bdate_range("2003-01-01", "2021-12-31")
    T = len(days)
    ret = rng.normal(0.0003, 0.02, (T, n))
    events = []
    for j in range(n):
        for d in range(300, T - 80, 63):
            d = d + int(rng.integers(0, 10))
            shock = rng.normal(0, 0.08)
            ret[d, j] += shock
            ret[d + 4:d + 64, j] += drift_k * shock / 60          # entry is the close of day +3; drift starts on day +4
            events.append((j, d, "8-K", "2.02,9.01"))
        for d in rng.integers(400, T - 80, 3):
            ret[d + 2:d + 62, j] -= bad_drift / 60                # entry is the close of day +1
            events.append((j, int(d), "NT 10-Q", ""))
    px = 20 * np.cumprod(1 + ret, axis=0)
    vol = rng.uniform(5e4, 5e5, (T, n))                           # dollar volume roughly $1m-$10m: inside the band
    con = sc.open_smallcap(tmp_path / "smallcap.duckdb")
    tick = [f"T{j:03d}" for j in range(n)]
    for j, t in enumerate(tick):
        con.execute("INSERT INTO sc_tickers VALUES (?, ?, ?, 'Nasdaq', 1)", [t, 1000 + j, t])
        con.execute("INSERT INTO sc_filers VALUES (?, ?, 'operating', 3559, 'x', ?, 'Nasdaq', 1)", [1000 + j, t, t])
    long = pd.DataFrame({"ticker": np.repeat(np.array(tick)[None, :], T, 0).ravel(), "date": np.repeat(days.date, n),
                         "close": px.ravel(), "volume": vol.ravel()})
    long["adj_close"] = long["close"]
    long["open"] = long["close"]
    long["high"] = long["close"] * 1.01
    long["low"] = long["close"] * 0.99
    con.register("p", long)
    con.execute("INSERT INTO sc_prices SELECT ticker, date, open, high, low, close, adj_close, volume, 1 FROM p")
    con.unregister("p")
    ev = pd.DataFrame([{"accession": f"A{k}", "cik": 1000 + j, "form": f, "filed": days[d - 1].date(),
                        "accepted_at": pd.Timestamp(days[d - 1]) + pd.Timedelta(hours=17), "items": it}
                       for k, (j, d, f, it) in enumerate(events)])
    con.register("e", ev)
    con.execute("INSERT INTO sc_events SELECT accession, cik, form, filed, accepted_at, items, 1 FROM e")
    con.unregister("e")
    return con


@pytest.fixture()
def root(tmp_path):
    (tmp_path / "config").mkdir()
    (tmp_path / "research").mkdir()
    return tmp_path


def proto(root, name="ev", m=300):
    f = root / "research" / f"{name}.toml"
    f.write_text(PROTO.format(name=name, m=m), encoding="utf-8")
    p = E.load_event_protocol(f)
    write_lock(root, p)
    return p


def main_db(tmp_path):
    c = open_smallcap(tmp_path / "terminal.duckdb")
    return c


def test_day_zero_rules():
    s = pd.bdate_range("2024-01-01", "2024-01-31")
    ev = pd.DataFrame({"accepted_at": [pd.Timestamp("2024-01-03 09:00"), pd.Timestamp("2024-01-03 16:05"),
                                       pd.Timestamp("2024-01-06 10:00"), pd.NaT],
                       "filed": [pd.Timestamp("2024-01-03")] * 3 + [pd.Timestamp("2024-01-10")]})
    d0 = E.day_zero(s, ev)
    assert [s[i].day for i in d0] == [3, 4, 8, 11]       # before the close: same day; after: next; weekend: Monday; unknown: next


def test_signal_never_uses_the_entry_day_or_earlier(tmp_path, root):
    con = build(tmp_path, n=40)
    p = proto(root)
    adj, close, dv, ev, hi, lo = E.load_inputs(con, p, False)
    m = E.build_market(adj, close, dv, p, hi, lo)
    evf = E.events_frame(m, ev, p)
    earn = evf[evf["kind"] == "earn"]
    assert (earn["entry"] == earn["d0"] + 3).all() and (earn["exit"] == earn["entry"] + 60).all()
    late = evf[evf["kind"] == "late"]
    assert (late["entry"] == late["d0"] + 1).all()
    pos = earn.head(5).assign(side=1)
    base = E.evaluate(m, pos, p, 1)["spread_gross"]
    c, a = pos["col"].values[0], pos["entry"].values[0]
    m.ret[a, c] += 0.5                                      # a jump on the entry day itself is not earned
    assert E.evaluate(m, pos, p, 1)["spread_gross"] == pytest.approx(base)
    m.ret[a + 1, c] += 0.5                                  # the first held day is
    assert E.evaluate(m, pos, p, 1)["spread_gross"] > base


def test_planted_continuation_is_found_and_noise_is_not(tmp_path, root):
    (tmp_path / "a").mkdir()
    c1 = build(tmp_path / "a", drift_k=0.6)
    p = proto(root, "ev1")
    r1 = E.run(main_db(tmp_path / "a"), c1, root, p, E.H1, "dev", log=lambda m: None)
    assert r1["spread_net"] > 0 and r1["ic_ci_low"] > 0 and r1["nw_t"] > 2
    (tmp_path / "b").mkdir()
    c2 = build(tmp_path / "b", drift_k=0.0, seed=9)
    p2 = proto(root, "ev2")
    r2 = E.run(main_db(tmp_path / "b"), c2, root, p2, E.H1, "dev", log=lambda m: None)
    assert r2["ic_ci_low"] < 0 and not r2["verdict"].startswith("PASS")
    assert r2["detail"]["unavailable_data"] and r2["detail"]["stress_net_mean"] < r2["spread_net"]


def test_planted_short_signal_and_category_separation(tmp_path, root):
    con = build(tmp_path, bad_drift=0.10, n=120)
    p = proto(root)
    res = E.run(main_db(tmp_path), con, root, p, E.H2A, "dev", log=lambda m: None)
    assert res["detail"]["n_short"] == res["detail"]["n_events"] > 0 and res["detail"]["n_long"] == 0
    assert res["spread_gross"] > 0.05                         # short profit before costs on a planted 10% decline
    ev = pd.DataFrame({"form": ["8-K", "8-K", "8-K", "NT 10-K", "8-K/A"], "items": ["4.01,4.02", "4.01", "2.02", "", "2.02"]})
    assert E.classify(ev)["kind"].tolist() == ["nonrel", "auditor", "earn", "late"]       # amendments ignored


def test_inconclusive_when_too_few_events(tmp_path, root):
    con = build(tmp_path, n=80)
    p = proto(root, m=100000)
    res = E.run(main_db(tmp_path), con, root, p, E.H1, "dev", log=lambda m: None)
    assert res["verdict"].startswith("INCONCLUSIVE")


def test_development_cannot_read_the_sealed_window_and_rules_hold(tmp_path, root):
    con = build(tmp_path, n=40)
    p = proto(root)
    adj, *_ = E.load_inputs(con, p, False)
    assert adj.index.max() < p.sealed_start
    before = E.load_inputs(con, p, False)[0]
    con.execute("UPDATE sc_prices SET adj_close = adj_close * 100 WHERE date >= DATE '2020-01-01'")
    pd.testing.assert_frame_equal(before, E.load_inputs(con, p, False)[0])
    main = main_db(tmp_path)
    E.run(main, con, root, p, E.H2A, "dev", log=lambda m: None)
    with pytest.raises(reg.RegistryError, match="already run"):
        E.run(main, con, root, p, E.H2A, "dev", log=lambda m: None)
    with pytest.raises(reg.RegistryError, match="closed"):
        E.run(main, con, root, p, E.H2A, "sealed", log=lambda m: None)


def test_screened_variant_drops_companies_with_recent_bad_filings(tmp_path, root):
    con = build(tmp_path, n=60)
    p = proto(root)
    adj, close, dv, ev, hi, lo = E.load_inputs(con, p, False)
    m = E.build_market(adj, close, dv, p, hi, lo)
    evf = E.events_frame(m, ev, p)
    a, b = E.select(evf, E.H1), E.select(evf, E.H1S)
    assert 0 < len(b) < len(a) and set(b.index) <= set(a.index)


def test_corwin_schultz_is_zero_without_range_and_grows_with_it():
    idx = pd.bdate_range("2024-01-01", periods=30)
    c = pd.DataFrame({"x": 10.0}, index=idx)
    assert (E.corwin_schultz_spread(c, c).dropna() == 0).all().all()
    narrow = E.corwin_schultz_spread(c * 1.005, c * 0.995).iloc[5:].mean().iloc[0]
    wide = E.corwin_schultz_spread(c * 1.02, c * 0.98).iloc[5:].mean().iloc[0]
    assert 0 < narrow < wide


def test_readiness_report_counts_without_returns(tmp_path, root):
    con = build(tmp_path, n=40)
    p = proto(root)
    r = E.readiness(con, p)
    assert r["acceptance_time_check"]["reading"].startswith("consistent")
    counts = r["eligible_event_counts"]
    assert set(counts["window"]) == {"dev", "validation"} and "status" in counts
    md = E.readiness_markdown(r)
    assert "No strategy returns were computed" in md and "Data that is not available" in md


def test_draft_protocol_is_valid_and_cannot_be_locked():
    from fe import run as cli
    p = E.load_event_protocol(ROOT / "research" / "filing_events_v1.DRAFT.toml")
    assert len(p.hypotheses) == 7 and p.min_events["H2B_non_reliance"] == 1840 and p.sealed_start == pd.Timestamp("2022-01-01")
    assert cli.main(["lock", str(ROOT / "research" / "filing_events_v1.DRAFT.toml")]) == 2   # refused: a draft


def _mini(tmp_path, closes, splits=()):
    con = sc.open_smallcap(tmp_path / "m.duckdb")
    days = pd.bdate_range("2010-01-04", periods=len(closes))
    for d, c in zip(days, closes):
        con.execute("INSERT INTO sc_prices VALUES ('X', ?, ?, ?, ?, ?, ?, 1e6, 1)", [d.date(), c, c, c, c, c])
    for d, r in splits:
        con.execute("INSERT INTO sc_splits VALUES ('X', ?, ?, 1)", [days[d].date(), r])
    return con, days


def test_price_filter_sees_the_price_as_traded_not_split_adjusted(tmp_path, root):
    # Yahoo stores $4.00 for a stock that really traded at $0.40 before a 1-for-10 reverse split (ratio 0.1) on day 30
    con, days = _mini(tmp_path, [4.0] * 60, splits=[(30, 0.1)])
    p = proto(root)
    adj, close, *_ = E.load_inputs(con, p, False)
    assert close["X"].iloc[10] == pytest.approx(0.4) and close["X"].iloc[40] == pytest.approx(4.0)


def test_a_move_across_a_missing_day_is_kept():
    adj = pd.DataFrame({"X": [10, 11, np.nan, 5, 5.5]}, index=pd.bdate_range("2024-01-01", periods=5))
    p = E.EventProtocol(**{**E.load_event_protocol(ROOT / "research" / "filing_events_v1.DRAFT.toml").__dict__})
    m = E.build_market(adj, adj, adj * 1e6, p)
    assert np.allclose(m.ret[1:, 0], [0.10, 0.0, 5 / 11 - 1, 0.10])


def test_duplicates_are_removed_by_open_position_not_by_event():
    pos = pd.DataFrame({"accession": ["a", "b", "c"], "kind": ["earn"] * 3, "cik": [1, 1, 1], "side": [1, 1, 1],
                        "entry": [100, 140, 170], "exit": [160, 200, 230]})
    assert E.dedupe_positions(pos)["accession"].tolist() == ["a", "c"]       # b overlaps a; c starts after a exits


def test_screen_uses_bad_filings_that_were_never_tradable(tmp_path, root):
    con = build(tmp_path, n=60)
    p = proto(root)
    adj, close, dv, ev, hi, lo = E.load_inputs(con, p, False)
    m = E.build_market(adj, close, dv, p, hi, lo)
    evf = E.events_frame(m, ev, p)
    longs = E.select(evf, E.H1)
    victim = longs.iloc[0]
    hidden = pd.DataFrame({"cik": [victim["cik"]], "when": [victim["date0"] - pd.Timedelta(days=30)]})   # e.g. filed while under $2
    screened = E.select(evf, E.H1S, bad_filings=hidden)
    assert victim.name not in screened.index and len(screened) == len(longs) - 1
