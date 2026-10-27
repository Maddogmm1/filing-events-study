"""Small-cap data layer for the filing-events study: database schema, SEC bulk-file parsers, exclusions and price
masks, SEC acceptance-time parsing, and the one-ticker-per-company rule shared with the engine.

Extracted from the author's private research terminal; network download and raw-snapshot code are not included (see
docs/DATA.md)."""
import json
import re
import zipfile
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path

import duckdb
import pandas as pd
import requests

from fe.snapshot import write_parquet_snapshot


def connect(path, read_only: bool = False):
    path = Path(path)
    if not read_only:
        path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(path), read_only=read_only)


NT_FORMS = {"NT 10-K", "NT 10-Q", "NT 10-K/A", "NT 10-Q/A"}


EIGHT_K = {"8-K", "8-K/A"}


WANTED_ITEMS = ("2.02", "4.01", "4.02")


LISTED_EXCHANGES = ("Nasdaq", "NYSE")


LISTING_FORMS = {"25", "25-NSE", "15-12B", "15-12G", "15-15D"}


LISTING_ITEMS = ("1.03", "2.01", "3.01", "5.01")


EXCLUSION_REASONS = {"TICKER_REUSE", "BAD_PRICES", "SPLIT_ERROR", "OTHER"}


MASK_REASONS = {"BAD_PRINT", "SPLICE", "OTHER"}


INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik}/{nodash}/{acc}-index.htm"


ACCEPTED_RE = re.compile(r"Accepted</div>\s*<div[^>]*>\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", re.I)


ACCEPTED_RE2 = re.compile(r"ACCEPTANCE-DATETIME>\s*(\d{14})")


MAIN_RE = re.compile(r"^CIK(\d{10})\.json$")


PAGE_RE = re.compile(r"^CIK(\d{10})-submissions-\d+\.json$")


def open_smallcap(path: Path | str):
    con = connect(path)
    con.execute(resources.files("fe").joinpath("smallcap_schema.sql").read_text(encoding="utf-8"))
    return con


def _events_from_columns(cols: dict, cik: int) -> pd.DataFrame:
    n = len(cols.get("accessionNumber") or [])
    if not n:
        return pd.DataFrame(columns=["accession", "cik", "form", "filed", "accepted_at", "items"])
    get = lambda k: cols.get(k) or [None] * n
    df = pd.DataFrame({"accession": get("accessionNumber"), "cik": cik, "form": get("form"), "filed": get("filingDate"),
                       "accepted_at": get("acceptanceDateTime"), "items": get("items")})
    df["items"] = df["items"].replace("", None)
    is_nt = df["form"].isin(NT_FORMS)
    is_8k = df["form"].isin(EIGHT_K) & df["items"].fillna("").str.contains("|".join(re.escape(i) for i in WANTED_ITEMS))
    df = df[is_nt | is_8k].copy()
    df["filed"] = pd.to_datetime(df["filed"], errors="coerce").dt.date
    # published as e.g. 2024-02-01T16:30:12.000Z; kept as the wall-clock value without converting (see docs)
    df["accepted_at"] = pd.to_datetime(df["accepted_at"].astype(str).str.slice(0, 19), errors="coerce")
    return df.dropna(subset=["accession", "filed"])


def _listing_from_columns(cols: dict, cik: int) -> pd.DataFrame:
    """Delisting/deregistration forms, plus 8-Ks carrying bankruptcy, acquisition, listing-notice or control-change items."""
    n = len(cols.get("accessionNumber") or [])
    out_cols = ["accession", "cik", "form", "filed", "accepted_at", "items"]
    if not n:
        return pd.DataFrame(columns=out_cols)
    get = lambda k: cols.get(k) or [None] * n
    df = pd.DataFrame({"accession": get("accessionNumber"), "cik": cik, "form": get("form"), "filed": get("filingDate"),
                       "accepted_at": get("acceptanceDateTime"), "items": get("items")})
    df["items"] = df["items"].replace("", None)
    is_listing = df["form"].isin(LISTING_FORMS)
    is_8k = df["form"].isin(EIGHT_K) & df["items"].fillna("").str.contains("|".join(re.escape(i) for i in LISTING_ITEMS))
    df = df[is_listing | is_8k].copy()
    df["filed"] = pd.to_datetime(df["filed"], errors="coerce").dt.date
    df["accepted_at"] = pd.to_datetime(df["accepted_at"].astype(str).str.slice(0, 19), errors="coerce")
    return df.dropna(subset=["accession", "filed"])[out_cols]


def load_listing_events(con, zpath: Path, snapshot_id: int, log=print) -> int:
    """D10a. Reads the STORED bulk snapshot again and fills sc_listing_events only. sc_filers and sc_events are not
    touched, so events already loaded stay exactly as they were. Only operating companies (the same rule as load_bulk)."""
    parts, keep = [], set()
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        for name in names:
            m = MAIN_RE.match(name)
            if not m:
                continue
            obj = json.loads(z.read(name))
            if obj.get("entityType") != "operating" or not str(obj.get("sic") or "").isdigit():
                continue
            cik = int(obj["cik"])
            keep.add(cik)
            parts.append(_listing_from_columns((obj.get("filings") or {}).get("recent") or {}, cik))
        for name in names:
            m = PAGE_RE.match(name)
            if m and int(m.group(1)) in keep:
                parts.append(_listing_from_columns(json.loads(z.read(name)), int(m.group(1))))
    df = pd.concat(parts, ignore_index=True).drop_duplicates("accession") if parts else pd.DataFrame()
    con.execute("BEGIN")
    try:
        con.execute("DELETE FROM sc_listing_events")
        if len(df):
            con.register("l_in", df.assign(snapshot_id=snapshot_id))
            con.execute("INSERT INTO sc_listing_events SELECT accession, cik, form, filed, accepted_at, items, snapshot_id FROM l_in")
            con.unregister("l_in")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    log(f"listing events loaded from snapshot {snapshot_id}: {len(df):,} rows")
    return len(df)


def load_exclusions(path: Path | str | None) -> pd.DataFrame:
    """config/smallcap_exclusions.csv: cik,ticker,reason_code,evidence,added_on. Every row needs a known reason and evidence."""
    cols = ["cik", "ticker", "reason_code", "evidence", "added_on"]
    if path is None or not Path(path).exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(path, dtype=str, comment="#").fillna("")
    missing = set(cols) - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    bad = df[~df["reason_code"].isin(EXCLUSION_REASONS) | (df["evidence"].str.strip() == "")
             | ((df["cik"].str.strip() == "") & (df["ticker"].str.strip() == ""))]
    if len(bad):
        raise ValueError(f"{path}: rows need a cik or ticker, a reason in {sorted(EXCLUSION_REASONS)} and evidence: "
                         f"{bad.to_dict('records')[:3]}")
    df["ticker"] = df["ticker"].str.strip().str.upper()
    return df


def load_price_masks(path: Path | str | None) -> pd.DataFrame:
    """config/smallcap_price_masks.csv (D10e): ticker,from_date,to_date,reason_code,evidence,added_on. Prices of the ticker
    on days from_date..to_date (inclusive) are treated as missing: the engine sees an untraded day, so the return is frozen
    and then measured from the last good price. Every row needs a known reason and evidence."""
    cols = ["ticker", "from_date", "to_date", "reason_code", "evidence", "added_on"]
    if path is None or not Path(path).exists():
        return pd.DataFrame(columns=cols)
    df = pd.read_csv(path, dtype=str, comment="#").fillna("")
    missing = set(cols) - set(df.columns)
    if missing:
        raise ValueError(f"{path}: missing columns {sorted(missing)}")
    df["ticker"] = df["ticker"].str.strip().str.upper()
    f, t = pd.to_datetime(df["from_date"], errors="coerce"), pd.to_datetime(df["to_date"], errors="coerce")
    bad = df[(df["ticker"] == "") | ~df["reason_code"].isin(MASK_REASONS) | (df["evidence"].str.strip() == "")
             | f.isna() | t.isna() | (t < f)]
    if len(bad):
        raise ValueError(f"{path}: rows need a ticker, from_date <= to_date, a reason in {sorted(MASK_REASONS)} and evidence: "
                         f"{bad.to_dict('records')[:3]}")
    df["from_date"], df["to_date"] = f, t
    return df


def parse_index_page(html: str):
    """SEC's acceptance time (New York wall clock) from a filing index page, or None."""
    m = ACCEPTED_RE.search(html)
    if m:
        return pd.Timestamp(m.group(1))
    m = ACCEPTED_RE2.search(html)
    return pd.Timestamp(datetime.strptime(m.group(1), "%Y%m%d%H%M%S")) if m else None


def acceptance_scope(con, sealed_start, min_adv: float, max_adv: float, margin: float = 2.0) -> pd.DataFrame:
    """Events whose true acceptance time is needed: original filings of the protocol's kinds, filed before the sealed start,
    whose company has a priced ticker with a 20-session dollar volume within [min_adv / margin, max_adv x margin] at some
    point in the 7 days before filing. Deliberately generous (the $2 test and exact day 0 are applied later by the engine)."""
    cut = f"{pd.Timestamp(sealed_start):%Y-%m-%d}"
    return con.execute(f"""
        WITH tk AS ({ticker_choice_sql(f"WHERE date < DATE '{cut}'")}),
        adv AS (SELECT ticker, date, avg(close * volume) OVER (PARTITION BY ticker ORDER BY date ROWS BETWEEN 19 PRECEDING AND CURRENT ROW) AS adv20
                FROM sc_prices WHERE date < DATE '{cut}'),
        ev AS (SELECT e.accession, e.cik, e.filed, tk.ticker FROM sc_events e JOIN tk USING (cik)
               WHERE e.filed < DATE '{cut}' AND (e.form IN ('NT 10-K', 'NT 10-Q') OR (e.form = '8-K' AND (e.items LIKE '%2.02%'
                     OR e.items LIKE '%4.01%' OR e.items LIKE '%4.02%'))))
        SELECT DISTINCT ev.accession, ev.cik, ev.filed FROM ev JOIN adv ON adv.ticker = ev.ticker
          AND adv.date BETWEEN ev.filed - INTERVAL 7 DAY AND ev.filed
        WHERE adv.adv20 BETWEEN {min_adv / margin} AND {max_adv * margin}
        ORDER BY ev.filed""").df()


def ticker_choice_sql(price_filter: str = "") -> str:
    """One ticker per company: the one with most price rows. Shared by coverage() and the event engine (finding F6)."""
    return (f"SELECT k.cik, arg_max(k.ticker, coalesce(n.rows, 0)) AS ticker FROM sc_tickers k "
            f"LEFT JOIN (SELECT ticker, COUNT(*) AS rows FROM sc_prices {price_filter} GROUP BY 1) n USING (ticker) GROUP BY k.cik")


def parse_main(obj: dict) -> tuple[dict, pd.DataFrame]:
    cik = int(obj["cik"])
    filer = {"cik": cik, "name": " ".join(str(obj.get("name", "")).split()), "entity_type": obj.get("entityType") or "",
             "sic": int(obj["sic"]) if str(obj.get("sic") or "").isdigit() else None,
             "sic_description": obj.get("sicDescription") or "",
             "tickers": ",".join(obj.get("tickers") or []), "exchanges": ",".join(x or "" for x in (obj.get("exchanges") or []))}
    return filer, _events_from_columns((obj.get("filings") or {}).get("recent") or {}, cik)


def is_operating(filer: dict) -> bool:
    return filer["entity_type"] == "operating" and filer["sic"] is not None


def load_bulk(con, zpath: Path, snapshot_id: int, log=print) -> dict:
    """Two passes over the zip: company files first (to choose operating companies), then their older filing pages."""
    filers, events, keep = [], [], set()
    with zipfile.ZipFile(zpath) as z:
        names = z.namelist()
        for i, name in enumerate(names, 1):
            m = MAIN_RE.match(name)
            if m:
                obj = json.loads(z.read(name))
                if obj.get("entityType") != "operating" or not str(obj.get("sic") or "").isdigit():
                    continue                       # individuals, funds and shells without an industry code: skipped cheaply
                f, ev = parse_main(obj)
                if is_operating(f):
                    keep.add(f["cik"])
                    filers.append(f)
                    events.append(ev)
            if i % 100000 == 0:
                log(f"  scanned {i:,} of {len(names):,} files; {len(keep):,} operating companies so far")
        for name in names:
            m = PAGE_RE.match(name)
            if m and int(m.group(1)) in keep:
                events.append(_events_from_columns(json.loads(z.read(name)), int(m.group(1))))
    fdf = pd.DataFrame(filers).assign(snapshot_id=snapshot_id)
    edf = pd.concat(events, ignore_index=True).drop_duplicates("accession").assign(snapshot_id=snapshot_id) if events else pd.DataFrame()
    con.execute("BEGIN")
    try:
        con.execute("DELETE FROM sc_filers")
        con.execute("DELETE FROM sc_events")
        if len(fdf):
            con.register("f_in", fdf)
            con.execute("INSERT INTO sc_filers SELECT cik, name, entity_type, sic, sic_description, tickers, exchanges, snapshot_id FROM f_in")
            con.unregister("f_in")
        if len(edf):
            con.register("e_in", edf)
            con.execute("INSERT INTO sc_events SELECT accession, cik, form, filed, accepted_at, items, snapshot_id FROM e_in")
            con.unregister("e_in")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    log(f"bulk filings loaded: {len(fdf):,} operating companies, {len(edf):,} events (earnings 8-Ks, auditor changes, "
        f"non-reliance notices, late-filing notices)")
    return {"filers": len(fdf), "events": len(edf)}


class SecError(RuntimeError):
    pass


def check_user_agent(ua: str) -> str:
    ua = (ua or "").strip()
    if not ua or not re.search(r"\S+@\S+\.\S+", ua):
        raise SecError("SEC requires a contact in the User-Agent, e.g. 'Your Name you@example.com'")
    return ua


def refresh_acceptance_truth(con, snapshot_dir, ua: str, scope: pd.DataFrame, chunk: int = 500, limit: int | None = None,
                             get=requests.get, log=print, min_gap_s: float = 0.21) -> dict:
    """D10c. Reads SEC's index page for each in-scope filing not yet resolved and stores the acceptance time it states.
    Resumable: filings with status 'ok' are skipped. Each chunk is snapshotted (accession, url, page hash, matched text)."""
    import hashlib
    import time as _time
    check_user_agent(ua)
    done = {r[0] for r in con.execute("SELECT accession FROM sc_acceptance_truth WHERE status = 'ok'").fetchall()}
    todo = scope[~scope["accession"].isin(done)]
    if limit:
        todo = todo.head(limit)
    ok = bad = 0
    last = [0.0]
    for k in range(0, len(todo), chunk):
        part, rows = todo.iloc[k:k + chunk], []
        for r in part.itertuples():
            wait = min_gap_s - (_time.monotonic() - last[0])
            if wait > 0:
                _time.sleep(wait)
            last[0] = _time.monotonic()
            url = INDEX_URL.format(cik=int(r.cik), nodash=r.accession.replace("-", ""), acc=r.accession)
            t, status, sha = None, "ok", None
            try:
                resp = get(url, headers={"User-Agent": ua}, timeout=30)
                if resp.status_code == 200:
                    sha = hashlib.sha256(resp.text.encode("utf-8", "ignore")).hexdigest()
                    t = parse_index_page(resp.text)
                    status = "ok" if t is not None else "no acceptance time on page"
                else:
                    status = f"HTTP {resp.status_code}"
            except requests.RequestException as e:
                status = type(e).__name__
            rows.append({"accession": r.accession, "accepted_ny": t, "status": status, "url": url, "page_sha256": sha})
        df = pd.DataFrame(rows)
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        sid = write_parquet_snapshot(con, snapshot_dir, "sec_edgar", "acceptance_truth", f"chunk_{k:06d}.parquet",
                                     df.assign(accepted_ny=df["accepted_ny"].astype(str)), {"n": len(df)})
        con.register("a_in", df.assign(fetched_at=now, snapshot_id=sid))
        con.execute("DELETE FROM sc_acceptance_truth WHERE accession IN (SELECT accession FROM a_in)")
        con.execute("INSERT INTO sc_acceptance_truth SELECT accession, accepted_ny, status, url, page_sha256, fetched_at, snapshot_id FROM a_in")
        con.unregister("a_in")
        ok += int((df["status"] == "ok").sum())
        bad += int((df["status"] != "ok").sum())
        log(f"  acceptance times: {min(k + chunk, len(todo)):,} of {len(todo):,} done this run; {ok:,} ok, {bad:,} not resolved")
    return {"in_scope": int(len(scope)), "already_done": int(len(done & set(scope["accession"]))), "fetched_ok": ok, "unresolved": bad}


def coverage(con, before=None) -> pd.DataFrame:
    """Per year and event type: events SEC recorded, events whose company has a current listed ticker, and events
    where that ticker has a price on the filing date. The last column is what the research can actually see."""
    ev_cut = f"AND e.filed < DATE '{pd.Timestamp(before):%Y-%m-%d}'" if before is not None else ""
    px_cut = f"AND p.date < DATE '{pd.Timestamp(before):%Y-%m-%d}'" if before is not None else ""
    return con.execute(f"""
        WITH ev AS (
            SELECT e.accession, year(e.filed) AS year, e.filed, e.cik,
                   CASE WHEN e.form LIKE 'NT %' THEN 'late filing notice'
                        WHEN e.items LIKE '%4.02%' THEN 'non-reliance (4.02)'
                        WHEN e.items LIKE '%4.01%' THEN 'auditor change (4.01)'
                        ELSE 'earnings (2.02)' END AS kind
            FROM sc_events e JOIN sc_filers f USING (cik) WHERE f.sic <> 6770 {ev_cut}),
        tk AS ({ticker_choice_sql(f"WHERE date < DATE '{pd.Timestamp(before):%Y-%m-%d}'" if before is not None else "")}),
        priced AS (SELECT ev.accession FROM ev JOIN tk USING (cik)
                   JOIN sc_prices p ON p.ticker = tk.ticker AND p.date BETWEEN ev.filed - INTERVAL 5 DAY AND ev.filed {px_cut})
        SELECT year, kind, COUNT(*) AS events,
               COUNT(*) FILTER (WHERE cik IN (SELECT cik FROM tk)) AS with_current_ticker,
               COUNT(*) FILTER (WHERE accession IN (SELECT accession FROM priced)) AS with_price,
               round(100.0 * COUNT(*) FILTER (WHERE accession IN (SELECT accession FROM priced)) / COUNT(*), 1) AS pct_priced
        FROM ev GROUP BY 1, 2 ORDER BY 1, 2""").df()
