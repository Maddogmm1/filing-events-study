"""D10b (conditional on the owner's choices in the FE Owner Decision Pack v1). Defaults reproduce draft r3 exactly."""
import numpy as np
import pandas as pd
import pytest

from fe import events as E
from tests.test_events import build, main_db, proto, root, PROTO, ROOT  # noqa: F401


def _ev(ts):
    return pd.DataFrame({"accepted_at": [pd.Timestamp(t) if t else pd.NaT for t in ts],
                         "filed": [pd.Timestamp(t).normalize() if t else pd.Timestamp("2019-11-29") for t in ts]})


def test_half_day_close_moves_late_filing_to_next_session():
    sessions, closes = E.nyse_calendar("2019-11-01", "2019-12-31")
    assert closes.loc["2019-11-29"].hour == 13 and closes.loc["2019-11-27"].hour == 16
    ev = _ev(["2019-11-29 14:00", "2019-11-29 12:00", "2019-11-29 12:45", "2019-11-27 15:45", "2019-11-27 15:15", None])
    d0 = E.day_zero(sessions, ev, closes, buffer_minutes=30)
    got = [sessions[i].strftime("%m-%d") for i in d0]
    # 14:00 after a 13:00 close; 12:45 inside the 30-minute buffer; 15:45 inside the buffer; 15:15 in time; no time -> next
    assert got == ["12-02", "11-29", "12-02", "11-29", "11-27", "12-02"]
    old = E.day_zero(sessions, ev)                       # draft r3 rule: 16:00 cut-off, no buffer
    assert sessions[old[0]].strftime("%m-%d") == "11-29"   # the old rule wrongly gives a filing after a half-day close the same day


def test_weekend_and_holiday_acceptance_go_to_next_session():
    sessions, closes = E.nyse_calendar("2019-12-01", "2020-01-10")
    ev = _ev(["2019-12-25 09:00", "2019-12-28 10:00"])
    assert [sessions[i].strftime("%m-%d") for i in E.day_zero(sessions, ev, closes, 30)] == ["12-26", "12-30"]


def test_stray_weekend_price_row_is_not_a_session():
    idx = pd.DatetimeIndex(["2019-12-26", "2019-12-27", "2019-12-28", "2019-12-30"])      # 28th is a Saturday
    f = pd.DataFrame({"X": [1.0, 1.1, 1.2, 1.3]}, index=idx)
    sessions, _ = E.nyse_calendar("2019-12-01", "2020-01-10")
    (g,), dropped = E.align_to_calendar([f], sessions)
    assert dropped == 1 and pd.Timestamp("2019-12-28") not in g.index and len(g) == 3


def test_protocol_defaults_reproduce_r3_and_calendar_is_validated(tmp_path):
    f0 = tmp_path / "r3like.toml"
    f0.write_text(PROTO.format(name="r3like", m=10), encoding="utf-8")          # a protocol without the new keys
    p = E.load_event_protocol(f0)
    assert p.calendar == "" and p.dissemination_buffer_minutes == 0 and p.acceptance_time_source == "stored"
    f = tmp_path / "x.toml"
    f.write_text(PROTO.format(name="x", m=10).replace('kind = "event_study"', 'kind = "event_study"\ncalendar = "LSE"'), encoding="utf-8")
    with pytest.raises(Exception, match="calendar"):
        E.load_event_protocol(f)


def test_run_with_calendar_records_it(tmp_path, root):
    con = build(tmp_path, n=40)
    f = root / "research" / "cal.toml"
    f.write_text(PROTO.format(name="cal", m=10).replace('kind = "event_study"', 'kind = "event_study"\ncalendar = "XNYS"\ndissemination_buffer_minutes = 30'),
                 encoding="utf-8")
    from fe.protocol import write_lock
    p = E.load_event_protocol(f); write_lock(root, p)
    res = E.run(main_db(tmp_path), con, root, p, E.H2A, "dev", log=lambda m: None)
    assert res["detail"]["calendar"]["name"] == "XNYS" and res["detail"]["calendar"]["dissemination_buffer_minutes"] == 30


def test_one_short_per_company_across_categories():
    pos = pd.DataFrame({"accession": ["a", "b", "c"], "kind": ["late", "nonrel", "late"], "cik": [1, 1, 1], "side": [-1, -1, -1],
                        "entry": [100, 110, 200], "exit": [160, 170, 260]})
    assert E.dedupe_positions(pos)["accession"].tolist() == ["a", "b", "c"]               # r3: per category -> double short
    assert E.dedupe_positions(pos, by="side")["accession"].tolist() == ["a", "c"]        # D6b: one short per company


def _market_two_sides():
    T = 300
    idx = pd.bdate_range("2010-01-04", periods=T)
    m = E.Market(idx, pd.Index(["L", "S1", "S2", "S3"]), np.zeros((T, 4)), np.ones((T, 4), bool), np.ones((T, 4), bool),
                 np.ones((T, 4), np.int8), np.zeros((T, 6)), np.full((T, 4), np.nan))
    m.ret[:, 0] = 0.001          # the long stock rises 0.1% a day
    m.ret[:, 1:] = -0.001        # the three short stocks fall 0.1% a day
    return m


def test_h3_side_weights_independent_of_event_counts():
    m = _market_two_sides()
    p = E.load_event_protocol(ROOT / "research" / "filing_events_v1.DRAFT.toml")
    p = E.EventProtocol(**{**p.__dict__, "cost_bps_one_way": 0.0, "short_financing_annual": 0.0})
    pos = pd.DataFrame({"col": [0, 1, 2, 3], "q": [1] * 4, "entry": [10] * 4, "exit": [70] * 4, "side": [1, -1, -1, -1],
                        "date0": [m.sessions[7]] * 4, "d0": [7] * 4})
    eq = E.evaluate(m, pos, p, 17, side_weighting="equal_sides")
    pw = E.evaluate(m, pos, p, 17)
    assert eq["detail"]["estimand"].startswith("mean monthly") and pw["detail"]["estimand"].startswith("mean net abnormal")
    # both legs earn +0.1% a day here, so the weighting cannot change the daily return; drop the long leg to see it matter
    pos2 = pos.copy(); pos2.loc[0, "col"] = 1; pos2.loc[0, "side"] = 1          # long leg now LOSES 0.1% a day
    a = E.evaluate(m, pos2, p, 17, side_weighting="equal_sides")["detail"]["monthly_mean"]
    b = E.evaluate(m, pos2, p, 17)["detail"]["monthly_mean"]
    assert abs(a) < 1e-12                       # 0.5 x (-0.1%) + 0.5 x (+0.1%) = 0, whatever the counts
    assert b > 0                                # per-position weighting: three winning shorts outvote one losing long


def test_combined_short_leg_can_exclude_auditor_changes():
    evf = pd.DataFrame({"accession": ["a", "b", "c"], "kind": ["late", "nonrel", "auditor"], "cik": [1, 2, 3],
                        "entry": [10, 10, 10], "exit": [70, 70, 70], "d0": [9] * 3, "date0": pd.to_datetime(["2010-01-01"] * 3),
                        "ear": [np.nan] * 3})
    assert set(E.select(evf, E.H2)["kind"]) == {"late", "nonrel", "auditor"}
    assert set(E.select(evf, E.H2, combined_kinds=("late", "nonrel"))["kind"]) == {"late", "nonrel"}


def test_open_entry_first_return_is_open_to_close(tmp_path):
    m = _market_two_sides()
    p = E.load_event_protocol(ROOT / "research" / "filing_events_v1.DRAFT.toml")
    p = E.EventProtocol(**{**p.__dict__, "cost_bps_one_way": 0.0, "short_financing_annual": 0.0})
    T, N = m.ret.shape
    oc = np.zeros((T, N)); valid = np.ones((T, N), bool)
    oc[10, 0] = 0.05                                  # the stock rises 5% from the open to the close on the entry day
    oe = E.OpenEntry(oc, valid, np.zeros((T, 6)))
    pos = pd.DataFrame({"col": [0], "q": [1], "entry": [10], "exit": [70], "side": [1], "kind": ["earn"],
                        "date0": [m.sessions[7]], "d0": [7]})
    close_entry = E.evaluate(m, pos, p, 17)
    open_entry = E.evaluate(m, pos, p, 17, open_entry=oe)
    assert close_entry["spread_gross"] == pytest.approx(60 * 0.001)                  # days 11..70
    assert open_entry["spread_gross"] == pytest.approx(0.05 + 59 * 0.001)            # day 10 open-to-close, then 11..69
    assert open_entry["detail"]["open_entries"] == 1
    oe.valid[10, 0] = False                                                           # bad open: falls back to the close
    fb = E.evaluate(m, pos, p, 17, open_entry=oe)
    assert fb["spread_gross"] == pytest.approx(close_entry["spread_gross"]) and fb["detail"]["open_entry_fallbacks_to_close"] == 1


def test_open_entry_variant_runs_end_to_end(tmp_path, root):
    con = build(tmp_path, n=60)
    p = proto(root)
    res = E.run(main_db(tmp_path), con, root, p, E.H1, "dev", log=lambda m: None, variant={"entry": "open"})
    assert res["detail"]["open_entries"] > 0 and res["detail"]["entry"].startswith("open")


def test_placebo_random_selection_is_seeded_and_not_the_top_decile(tmp_path, root):
    con = build(tmp_path, n=60)
    p = proto(root)
    adj, close, dv, ev, hi, lo = E.load_inputs(con, p, False)
    m = E.build_market(adj, close, dv, p, hi, lo)
    evf = E.events_frame(m, ev, p)
    a = E.select(evf, E.H1, placebo="random_earnings_10pct")
    b = E.select(evf, E.H1, placebo="random_earnings_10pct")
    top = E.select(evf, E.H1)
    assert list(a.index) == list(b.index) and len(a) > 0                  # reproducible
    assert len(set(a.index) & set(top.index)) < 0.5 * len(a)               # mostly different events from the real signal


def test_min_events_rounds_up():
    # exact z-values (1.95996 + 0.84162); the draft used 1.96 + 0.84 and rounded 306.25 DOWN to 306 (finding F7)
    assert [E.required_positions(e) for e in (0.02, 0.03, 0.04)] == [1227, 546, 307]
    assert [E.required_positions(e, design_effect=1.5) for e in (0.02, 0.03, 0.04)] == [1840, 818, 460]
