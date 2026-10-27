"""D10d (FE G7 decision, 27 Oct 2026): delisting-cause rule r2 in sc_delistings, label-error allowance and label-free
sensitivity in the survivorship bounds, in-scope count of unverified exclusions. All on synthetic data."""
import pandas as pd
import pytest

from fe import data as sc
from fe import events as E
from fe.protocol import ProtocolError, write_lock
from tests.test_events import PROTO, build, main_db, proto, root  # noqa: F401  (root is a fixture)


def proto_with(root, name, extra):
    f = root / "research" / f"{name}.toml"
    f.write_text(extra.strip() + "\n" + PROTO.format(name=name, m=300), encoding="utf-8")  # top level, before any [table]
    p = E.load_event_protocol(f)
    write_lock(root, p)
    return p

R2_CASES = {  # cik: rows (form, filed, items), expected cause under r2
    101: ([("8-K", "2017-12-01", "1.03"), ("8-K", "2018-05-25", "3.01"), ("8-K", "2018-11-06", "3.01"), ("25-NSE", "2018-11-21", None)],
          "listing_failure"),                       # old bankruptcy, recent listing notices
    102: ([("8-K", "2019-03-27", "3.01"), ("25-NSE", "2019-04-11", None), ("8-K", "2019-05-10", "1.01,1.03")], "listing_failure"),
    103: ([("8-K", "2021-07-30", "1.01,3.01,3.02,5.02"), ("25-NSE", "2021-08-18", None)], "acquired"),   # merger-related 3.01
    104: ([("25-NSE", "2013-10-10", None), ("15-12B", "2013-10-15", None)], "acquired_inferred"),
    105: ([("8-K", "2011-01-10", "3.01"), ("8-K", "2011-06-01", "1.01,3.01"), ("25-NSE", "2011-06-20", None)], "listing_failure"),
    106: ([("8-K", "2012-10-18", "1.03,2.04,3.01"), ("25-NSE", "2012-11-16", None)], "bankruptcy"),
    107: ([("8-K", "2012-10-09", "2.01,3.01,5.01"), ("25-NSE", "2012-10-09", None)], "acquired"),
    108: ([("25-NSE", "2010-01-19", None)], "unknown"),
}


def test_schema_v4_rule_r2(tmp_path):
    con = sc.open_smallcap(tmp_path / "s.duckdb")
    assert con.execute("SELECT value FROM schema_info WHERE key='smallcap_schema_version'").fetchone()[0] == "4"
    for cik, (rows, _) in R2_CASES.items():
        for j, (f, d, it) in enumerate(rows):
            con.execute("INSERT INTO sc_listing_events VALUES (?, ?, ?, ?, NULL, ?, 1)", [f"L{cik}-{j}", cik, f, d, it])
    got = con.execute("SELECT cik, cause FROM sc_delistings").df().set_index("cik")["cause"].to_dict()
    assert got == {cik: c for cik, (_, c) in R2_CASES.items()}


def _with_unpriced(con, cause_items, n=40):
    for k in range(n):
        cik = 9000 + k
        d = pd.Timestamp("2008-03-03") + pd.Timedelta(days=30 * k)
        con.execute("INSERT INTO sc_filers VALUES (?, 'gone', 'operating', 3559, 'x', '', '', 1)", [cik])
        con.execute("INSERT INTO sc_events VALUES (?, ?, 'NT 10-Q', ?, ?, '', 1)", [f"U{k}", cik, d.date(), d + pd.Timedelta(hours=17)])
        con.execute("INSERT INTO sc_listing_events VALUES (?, ?, '8-K', ?, NULL, ?, 1)", [f"N{k}", cik, (d + pd.Timedelta(days=5)).date(), cause_items])
        con.execute("INSERT INTO sc_listing_events VALUES (?, ?, '25-NSE', ?, NULL, NULL, 1)", [f"D{k}", cik, (d + pd.Timedelta(days=20)).date()])


@pytest.mark.parametrize("items,cls", [("3.01", "failure"), ("2.01,5.01", "acquired")])
def test_allowance_only_moves_adverse_and_label_free_is_worst(tmp_path, root, items, cls):
    con = build(tmp_path, n=60)
    _with_unpriced(con, items)
    p0 = proto(root, name="a0")
    p1 = proto_with(root, "a1", "\nsurvivorship_label_error_allowance = 0.10\n")
    b0 = E.run(main_db(tmp_path), con, root, p0, E.H2A, "dev", log=lambda m: None)["detail"]["survivorship_bounds"]
    b1 = E.run(main_db(tmp_path), con, root, p1, E.H2A, "dev", log=lambda m: None)["detail"]["survivorship_bounds"]
    assert b0["unpriced_by_class"] == {cls: 40} and b1["label_error_allowance"] == 0.10
    m0, m1 = b0["bounded_mean_net"], b1["bounded_mean_net"]
    for k in ("favourable_rate", "central_rate", "favourable_half_rate", "central_half_rate"):
        assert m1[k] == pytest.approx(m0[k])
    if cls == "failure":          # H2A is a short: failure is the favourable class, so the allowance must lower the bound
        assert m1["adverse_rate"] < m0["adverse_rate"]
    else:                         # acquired is already the unfavourable class for a short: nothing to move
        assert m1["adverse_rate"] == pytest.approx(m0["adverse_rate"])
    assert m1["adverse_label_free_rate"] <= m1["adverse_rate"] + 1e-12
    assert m1["adverse_label_free_rate"] == pytest.approx(m0["adverse_label_free_rate"])   # independent of the allowance


def test_allowance_validated(tmp_path, root):
    with pytest.raises(ProtocolError):
        proto_with(root, "bad", "\nsurvivorship_label_error_allowance = 1.5\n")
