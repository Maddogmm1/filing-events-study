"""D10a (FE Owner Decision Pack v1): listing events and delisting causes, exclusions, truncation, shared ticker choice,
concentration and survivorship bounds. All on synthetic data."""
import json
import zipfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from fe import data as sc
from fe import events as E
from tests.test_events import build, main_db, proto, root  # noqa: F401  (root is a fixture)
from tests.sec_fixtures import _cols, make_zip

FIX = Path(__file__).resolve().parent / "fixtures"


def test_schema_v2_is_additive(tmp_path):
    db = tmp_path / "s.duckdb"
    c = duckdb.connect(str(db))
    c.execute((FIX / "smallcap_schema_v1.sql").read_text(encoding="utf-8"))
    c.execute("INSERT INTO sc_events VALUES ('A1', 1, '8-K', DATE '2010-01-04', NULL, '2.02', 1)")
    c.execute("INSERT INTO sc_prices VALUES ('X', DATE '2010-01-04', 1, 1, 1, 1, 1, 10, 1)")
    c.close()
    con = sc.open_smallcap(db)                                 # applies v2
    assert con.execute("SELECT value FROM schema_info WHERE key='smallcap_schema_version'").fetchone()[0] == "4"
    assert con.execute("SELECT COUNT(*) FROM sc_events").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM sc_prices").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM sc_listing_events").fetchone()[0] == 0
    assert con.execute("SELECT COUNT(*) FROM sc_delistings").fetchone()[0] == 0
    sc.open_smallcap(db).close()                               # idempotent


def _zip_with_listing(path):
    make_zip(path)
    gone = {"cik": "0000000606", "name": "Failed Gadgets", "entityType": "operating", "sic": "3674", "tickers": [], "exchanges": [],
            "filings": {"recent": _cols([
                ("0000606-15-000001", "2015-01-10", "2015-01-10T08:00:00.000Z", "8-K", "1.03,9.01"),
                ("0000606-15-000002", "2015-02-01", "2015-02-01T08:00:00.000Z", "25-NSE", ""),
                ("0000606-15-000003", "2015-03-01", "2015-03-01T08:00:00.000Z", "15-12G", ""),
                ("0000606-15-000004", "2015-01-05", "2015-01-05T08:00:00.000Z", "8-K", "5.02"),       # not wanted
                ("0000606-14-000005", "2014-11-01", "2014-11-01T16:30:00.000Z", "8-K", "2.02")])}}
    with zipfile.ZipFile(path, "a") as z:
        z.writestr("CIK0000000606.json", json.dumps(gone))


def test_listing_events_from_fixture_and_sc_events_unchanged(tmp_path):
    con = sc.open_smallcap(tmp_path / "s.duckdb")
    zp = tmp_path / "submissions.zip"
    _zip_with_listing(zp)
    sc.load_bulk(con, zp, 1, log=lambda m: None)
    before = con.execute("SELECT * FROM sc_events ORDER BY accession").df()
    n = sc.load_listing_events(con, zp, 1, log=lambda m: None)
    assert n == 3
    forms = sorted(r[0] for r in con.execute("SELECT form FROM sc_listing_events").fetchall())
    assert forms == ["15-12G", "25-NSE", "8-K"]
    pd.testing.assert_frame_equal(before, con.execute("SELECT * FROM sc_events ORDER BY accession").df())
    d = con.execute("SELECT * FROM sc_delistings").df()
    assert len(d) == 1 and d["cause"].iloc[0] == "bankruptcy" and str(d["exit_date"].iloc[0])[:10] == "2015-02-01"
    sc.load_listing_events(con, zp, 1, log=lambda m: None)    # re-running replaces, does not duplicate
    assert con.execute("SELECT COUNT(*) FROM sc_listing_events").fetchone()[0] == 3




def test_delisting_causes_and_transfers(tmp_path):
    con = sc.open_smallcap(tmp_path / "s.duckdb")
    rows = [  # cik, form, filed, items
        (1, "8-K", "2012-01-10", "1.03"), (1, "25-NSE", "2012-03-01", ""),                       # bankruptcy
        (2, "8-K", "2013-05-02", "2.01,3.01,5.01"), (2, "25-NSE", "2013-05-03", ""),             # acquired (3.01 too)
        (3, "8-K", "2014-02-01", "3.01"), (3, "25-NSE", "2014-09-01", ""),                       # listing failure
        (4, "15-12G", "2016-06-01", ""),                                                         # unknown, deregistered
        (5, "25", "2010-01-04", ""), (5, "25", "2018-07-01", ""),                                 # two forms: last one counts
        (6, "25", "2011-01-04", "")]                                                             # transfer: still listed
    for k, (cik, f, d, it) in enumerate(rows):
        con.execute("INSERT INTO sc_listing_events VALUES (?, ?, ?, ?, NULL, ?, 1)", [f"L{k}", cik, f, d, it or None])
    con.execute("INSERT INTO sc_tickers VALUES ('SIX', 6, 'Six', 'NYSE', 1)")
    d = con.execute("SELECT cik, exit_date, cause, still_listed FROM sc_delistings ORDER BY cik").df().set_index("cik")
    assert d.loc[1, "cause"] == "bankruptcy" and d.loc[2, "cause"] == "acquired" and d.loc[3, "cause"] == "listing_failure"
    assert d.loc[4, "cause"] == "unknown" and str(d.loc[4, "exit_date"])[:10] == "2016-06-01"
    assert str(d.loc[5, "exit_date"])[:10] == "2018-07-01"
    assert bool(d.loc[6, "still_listed"]) and not bool(d.loc[1, "still_listed"])


def test_exclusions_are_honoured_and_validated(tmp_path, root):
    con = build(tmp_path, n=40)
    p = proto(root)
    f = tmp_path / "ex.csv"
    f.write_text("cik,ticker,reason_code,evidence,added_on\n,T001,TICKER_REUSE,history starts before issuer existed,2026-10-26\n"
                 "1002,,BAD_PRICES,G5 list row 3,2026-10-26\n", encoding="utf-8")
    ex = sc.load_exclusions(f)
    adj, close, dv, ev, *_ = E.load_inputs(con, p, False, exclusions=ex)
    assert "T001" not in adj.columns and "T002" not in adj.columns and "T003" in adj.columns
    assert ev[ev["cik"] == 1001]["ticker"].isna().all() and (ev["cik"] != 1002).all()
    f.write_text("cik,ticker,reason_code,evidence,added_on\n,T001,BECAUSE,,2026-10-26\n", encoding="utf-8")
    with pytest.raises(ValueError, match="reason"):
        sc.load_exclusions(f)
    assert len(sc.load_exclusions(tmp_path / "absent.csv")) == 0


def test_truncated_share_counts_positions_frozen_after_last_price(tmp_path, root):
    con = build(tmp_path, n=40)
    p = proto(root)

    def positions():
        adj, close, dv, ev, hi, lo = E.load_inputs(con, p, False)
        m = E.build_market(adj, close, dv, p, hi, lo)
        pos = E.select(E.events_frame(m, ev, p), E.H2A)
        return m, pos[(pos["exit"] < len(m.sessions)) & (m.sessions[np.minimum(pos["d0"], len(m.sessions) - 1)] < "2019-01-01")]
    m, pos = positions()
    assert E.evaluate(m, pos, p, 17)["detail"]["truncated_share"] == 0
    victim = pos.iloc[0]
    mid = m.sessions[(victim["entry"] + victim["exit"]) // 2]
    con.execute("DELETE FROM sc_prices WHERE ticker = ? AND date > ?", [victim["ticker"], mid.date()])   # stops trading mid-hold
    m, pos = positions()
    res = E.evaluate(m, pos, p, 17)
    assert res["detail"]["truncated_share"] > 0


def test_coverage_and_engine_choose_same_ticker(tmp_path, root):
    con = build(tmp_path, n=20)
    p = proto(root)
    con.execute("INSERT INTO sc_tickers VALUES ('A000', 1000, 'short history', 'Nasdaq', 1)")   # alphabetically first
    for d in pd.bdate_range("2021-06-01", periods=10):
        con.execute("INSERT INTO sc_prices VALUES ('A000', ?, 5, 5, 5, 5, 5, 1e5, 1)", [d.date()])
    chosen = dict(con.execute(sc.ticker_choice_sql()).fetchall())
    assert chosen[1000] == "T000"
    ev = E.load_inputs(con, p, False)[3]
    assert set(ev[ev["cik"] == 1000]["ticker"]) == {"T000"}
    cov = sc.coverage(con, before=p.sealed_start)
    assert (cov["with_price"] == cov["events"]).all()          # MIN(ticker) would have picked A000 and lost these


def test_concentration_on_planted_outlier():
    x = np.r_[np.full(99, 0.01), 10.0]
    c = E.concentration(x)
    assert c["n_top5pct"] == 5 and c["top5pct_share_of_total"] > 0.9
    assert c["mean_winsorised_1pct"] < x.mean()
    assert np.isnan(E.concentration(np.array([-0.1, -0.2]))["top5pct_share_of_total"])


def test_bounds_reduce_to_point_estimate_when_nothing_unpriced(tmp_path, root):
    con = build(tmp_path, n=60)
    p = proto(root)
    res = E.run(main_db(tmp_path), con, root, p, E.H2A, "dev", log=lambda m: None)
    b = res["detail"]["survivorship_bounds"]
    assert b["unpriced_events"] == 0
    for v in b["bounded_mean_net"].values():
        assert v == pytest.approx(res["spread_net"])
    assert "concentration" in res["detail"] and res["detail"]["exclusions_applied"] == 0


def test_bounds_order_and_direction_with_unpriced_failures(tmp_path, root):
    con = build(tmp_path, n=60)
    p = proto(root)
    # 40 late-filing notices from companies with no price; each delisted for listing failure 20 days later
    for k in range(40):
        cik = 9000 + k
        d = pd.Timestamp("2008-03-03") + pd.Timedelta(days=30 * k)
        con.execute("INSERT INTO sc_filers VALUES (?, 'gone', 'operating', 3559, 'x', '', '', 1)", [cik])
        con.execute("INSERT INTO sc_events VALUES (?, ?, 'NT 10-Q', ?, ?, '', 1)", [f"U{k}", cik, d.date(), d + pd.Timedelta(hours=17)])
        con.execute("INSERT INTO sc_listing_events VALUES (?, ?, '8-K', ?, NULL, '3.01', 1)", [f"N{k}", cik, (d + pd.Timedelta(days=5)).date()])
        con.execute("INSERT INTO sc_listing_events VALUES (?, ?, '25-NSE', ?, NULL, NULL, 1)", [f"D{k}", cik, (d + pd.Timedelta(days=20)).date()])
    res = E.run(main_db(tmp_path), con, root, p, E.H2A, "dev", log=lambda m: None)
    b = res["detail"]["survivorship_bounds"]
    assert b["unpriced_by_class"] == {"failure": 40}
    bm = b["bounded_mean_net"]
    assert bm["favourable_rate"] > bm["central_rate"] > bm["adverse_rate"]
    assert bm["adverse_rate"] > res["spread_net"]              # for a short, unpriced failures can only help
    assert abs(bm["central_half_rate"] - res["spread_net"]) < abs(bm["central_rate"] - res["spread_net"])
