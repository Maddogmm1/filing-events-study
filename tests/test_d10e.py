"""D10e: price masks (config/smallcap_price_masks.csv) turn masked days into missing prices. Synthetic data."""
import numpy as np
import pandas as pd
import pytest

from fe import data as sc
from fe import events as E
from tests.test_events import build, main_db, proto, root  # noqa: F401  (root is a fixture)

HEADER = "ticker,from_date,to_date,reason_code,evidence,added_on\n"


def test_masks_validated(tmp_path):
    f = tmp_path / "m.csv"
    assert len(sc.load_price_masks(tmp_path / "none.csv")) == 0
    f.write_text(HEADER + "abc,2010-01-04,2010-01-04,BAD_PRINT,review pack #1,2026-10-27\n")
    m = sc.load_price_masks(f)
    assert m.loc[0, "ticker"] == "ABC" and m.loc[0, "from_date"] == pd.Timestamp("2010-01-04")
    for bad in ["abc,2010-01-05,2010-01-04,BAD_PRINT,x,2026-10-27\n", "abc,2010-01-04,2010-01-04,WHATEVER,x,2026-10-27\n",
                "abc,2010-01-04,2010-01-04,BAD_PRINT,,2026-10-27\n", ",2010-01-04,2010-01-04,BAD_PRINT,x,2026-10-27\n"]:
        f.write_text(HEADER + bad)
        with pytest.raises(ValueError):
            sc.load_price_masks(f)


def test_bad_print_masked_gives_frozen_then_true_return(tmp_path, root):
    con = build(tmp_path, n=30)
    p = proto(root)
    t, d = con.execute("SELECT ticker, date FROM sc_prices ORDER BY ticker, date LIMIT 1 OFFSET 100").fetchone()
    before = con.execute("SELECT adj_close FROM sc_prices WHERE ticker = ? AND date < ? ORDER BY date DESC LIMIT 1", [t, d]).fetchone()[0]
    con.execute("UPDATE sc_prices SET adj_close = adj_close * 3, close = close * 3 WHERE ticker = ? AND date = ?", [t, d])
    raw = E.load_inputs(con, p, include_sealed=False)
    masks = pd.DataFrame([{"ticker": t, "from_date": pd.Timestamp(d), "to_date": pd.Timestamp(d), "reason_code": "BAD_PRINT",
                           "evidence": "test", "added_on": "2026-10-27"}])
    fixed = E.load_inputs(con, p, include_sealed=False, masks=masks)
    m0, m1 = E.build_market(*raw[:3], p, raw[4], raw[5]), E.build_market(*fixed[:3], p, fixed[4], fixed[5])
    i, c = m1.sessions.get_loc(pd.Timestamp(d)) if pd.Timestamp(d) in m1.sessions else None, m1.cols.get_loc(t)
    i0 = m0.sessions.get_loc(pd.Timestamp(d))
    assert m0.ret[i0, c] > 1.5                                   # the planted print
    assert pd.Timestamp(d) not in fixed[0].index or np.isnan(fixed[0].loc[pd.Timestamp(d), t])
    if i is not None:
        assert m1.ret[i, c] == 0.0 and not m1.price_ok[i, c]     # untraded: frozen
    nxt = fixed[0][t].loc[fixed[0].index > pd.Timestamp(d)].dropna().iloc[0]
    j = m1.sessions.get_loc(fixed[0][t].loc[fixed[0].index > pd.Timestamp(d)].dropna().index[0])
    assert m1.ret[j, c] == pytest.approx(nxt / before - 1.0)     # measured from the last good price


def test_run_reports_masks(tmp_path, root):
    con = build(tmp_path, n=40)
    p = proto(root)
    (root / "config" / "smallcap_price_masks.csv").write_text(HEADER + "ZZZZ,2010-01-04,2010-01-05,OTHER,test,2026-10-27\n")
    res = E.run(main_db(tmp_path), con, root, p, E.H2A, "dev", log=lambda m: None)
    assert res["detail"]["price_masks_applied"] == 1
