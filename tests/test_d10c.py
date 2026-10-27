"""D10c: SEC's own acceptance times. The fixture holds 300 real filings checked against SEC's index pages on 26 Oct 2026
(FE readiness G3c): stored times carry 0, 1 or 2 UTC conversions; the loader must recover SEC's time for all of them."""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from fe import data as sc
from fe import events as E
from fe.protocol import write_lock
from tests.test_events import PROTO, build, main_db, root  # noqa: F401

FIX = Path(__file__).resolve().parent / "fixtures" / "acceptance_truth_sample_300.csv"


class Resp:
    def __init__(self, code, text=""): self.status_code, self.text = code, text


def page(t):
    return f'<div class="formGrouping"><div class="infoHead">Accepted</div>\n<div class="info">{t:%Y-%m-%d %H:%M:%S}</div></div>'


def test_parse_index_page_both_formats():
    assert sc.parse_index_page(page(pd.Timestamp("2010-08-04 16:36:32"))) == pd.Timestamp("2010-08-04 16:36:32")
    assert sc.parse_index_page("<ACCEPTANCE-DATETIME>20100804163632") == pd.Timestamp("2010-08-04 16:36:32")
    assert sc.parse_index_page("<html>nothing</html>") is None


def test_loader_recovers_sec_time_for_all_300_fixture_filings_and_resumes(tmp_path):
    fx = pd.read_csv(FIX)
    truth = dict(zip(fx["accession"], pd.to_datetime(fx["sec_index_time_ny"])))
    con = sc.open_smallcap(tmp_path / "s.duckdb")
    calls = []

    def get(url, headers=None, timeout=None):
        calls.append(url)
        acc = url.rsplit("/", 1)[1].replace("-index.htm", "")
        return Resp(200, page(truth[acc]))
    scope = fx[["accession", "cik", "filed"]]
    res = sc.refresh_acceptance_truth(con, tmp_path / "snaps", "Test test@example.com", scope, chunk=120, get=get,
                                      log=lambda m: None, min_gap_s=0)
    assert res["fetched_ok"] == 300
    got = con.execute("SELECT accession, accepted_ny FROM sc_acceptance_truth").df()
    got = dict(zip(got["accession"], pd.to_datetime(got["accepted_ny"])))
    assert all(got[a] == t for a, t in truth.items())
    stored = pd.to_datetime(fx["stored"])
    assert (stored != pd.to_datetime(fx["sec_index_time_ny"])).sum() == 184           # the bulk file was wrong for 184 of 300
    assert con.execute("SELECT COUNT(*) FROM snapshots WHERE dataset = 'acceptance_truth'").fetchone()[0] == 3
    n = len(calls)
    sc.refresh_acceptance_truth(con, tmp_path / "snaps", "Test test@example.com", scope, get=get, log=lambda m: None, min_gap_s=0)
    assert len(calls) == n                                                              # resumable: nothing fetched twice


def test_failed_pages_are_recorded_and_retried_next_run(tmp_path):
    con = sc.open_smallcap(tmp_path / "s.duckdb")
    scope = pd.DataFrame({"accession": ["0000000001-10-000001"], "cik": [1], "filed": ["2010-01-04"]})
    sc.refresh_acceptance_truth(con, tmp_path / "s1", "T t@e.com", scope, get=lambda *a, **k: Resp(503), log=lambda m: None, min_gap_s=0)
    assert con.execute("SELECT status FROM sc_acceptance_truth").fetchone()[0] == "HTTP 503"
    sc.refresh_acceptance_truth(con, tmp_path / "s2", "T t@e.com", scope,
                                get=lambda *a, **k: Resp(200, page(pd.Timestamp("2010-01-04 08:00:00"))), log=lambda m: None, min_gap_s=0)
    assert con.execute("SELECT status, accepted_ny FROM sc_acceptance_truth").fetchone()[0] == "ok"


def _proto(root, name, extra):
    f = root / "research" / f"{name}.toml"
    f.write_text(PROTO.format(name=name, m=10).replace('kind = "event_study"', 'kind = "event_study"\n' + extra), encoding="utf-8")
    p = E.load_event_protocol(f); write_lock(root, p)
    return p


def test_engine_uses_sec_time_and_excludes_unverified(tmp_path, root):
    con = build(tmp_path, n=40)
    ev = con.execute("SELECT accession, accepted_at FROM sc_events WHERE form = 'NT 10-Q' AND filed < DATE '2020-01-01'").df()
    half = ev.iloc[: len(ev) // 2]
    # SEC says these were accepted 09:00 the same day (stored says 17:00): day 0 moves one session earlier
    con.register("t", half.assign(accepted_ny=pd.to_datetime(half["accepted_at"]).dt.normalize() + pd.Timedelta(hours=9)))
    con.execute("INSERT INTO sc_acceptance_truth SELECT accession, accepted_ny, 'ok', 'u', 'h', now(), 1 FROM t")
    p = _proto(root, "truth", 'acceptance_time_source = "sec_index"\nshort_financing_stress_annual = [0.10, 0.20]')
    res = E.run(main_db(tmp_path), con, root, p, E.H2A, "dev", log=lambda m: None)
    t = res["detail"]["acceptance_time"]
    assert t["source"] == "sec_index" and t["excluded_no_verified_time"] > 0 and t["changed_by_truth"] == len(half)
    assert set(res["detail"]["short_financing_stress"]) == {"10%", "20%"}
    s = res["detail"]["short_financing_stress"]
    assert s["20%"] < s["10%"] < res["spread_net"]                       # more financing cost, lower net return for a short
    p0 = _proto(root, "stored", "")
    (tmp_path / "x").mkdir()
    r0 = E.run(main_db(tmp_path / "x"), con, root, p0, E.H2A, "dev", log=lambda m: None)
    assert r0["detail"]["acceptance_time"] == {"source": "stored"} and r0["detail"]["n_events"] > res["detail"]["n_events"]


def test_scope_keeps_priced_events_near_the_band(tmp_path):
    con = build(tmp_path, n=20)
    s = sc.acceptance_scope(con, "2022-01-01", 200000, 20000000)
    n_ev = con.execute("SELECT COUNT(*) FROM sc_events").fetchone()[0]
    assert 0 < len(s) <= n_ev and s["accession"].is_unique
