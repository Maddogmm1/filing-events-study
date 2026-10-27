-- Separate database (data/smallcap.duckdb) for the all-filers universe, so the S&P 500 terminal, its checks and its
-- nightly job are untouched by microcap data. Idempotent.
CREATE TABLE IF NOT EXISTS schema_info (key VARCHAR PRIMARY KEY, value VARCHAR);
CREATE SEQUENCE IF NOT EXISTS seq_snapshot START 1;
CREATE TABLE IF NOT EXISTS snapshots (
    snapshot_id BIGINT PRIMARY KEY DEFAULT nextval('seq_snapshot'),
    source VARCHAR NOT NULL, dataset VARCHAR NOT NULL, fetched_at TIMESTAMP NOT NULL, path VARCHAR NOT NULL,
    sha256 VARCHAR NOT NULL, row_count BIGINT, params VARCHAR, pruned_at TIMESTAMP);
CREATE TABLE IF NOT EXISTS sc_filers (               -- every operating-company filer SEC knows, listed or long gone
    cik BIGINT PRIMARY KEY, name VARCHAR, entity_type VARCHAR, sic INTEGER, sic_description VARCHAR,
    tickers VARCHAR, exchanges VARCHAR, snapshot_id BIGINT);
CREATE TABLE IF NOT EXISTS sc_events (               -- only the filing types the protocol uses
    accession VARCHAR PRIMARY KEY, cik BIGINT NOT NULL, form VARCHAR NOT NULL, filed DATE NOT NULL,
    accepted_at TIMESTAMP,                           -- SEC acceptance time as published (see docs: time zone to verify)
    items VARCHAR, snapshot_id BIGINT);
CREATE TABLE IF NOT EXISTS sc_tickers (              -- SEC's current ticker list with exchange
    ticker VARCHAR PRIMARY KEY, cik BIGINT NOT NULL, name VARCHAR, exchange VARCHAR, snapshot_id BIGINT);
CREATE TABLE IF NOT EXISTS sc_prices (
    ticker VARCHAR NOT NULL, date DATE NOT NULL, open DOUBLE, high DOUBLE, low DOUBLE, close DOUBLE,
    adj_close DOUBLE, volume DOUBLE, snapshot_id BIGINT, PRIMARY KEY (ticker, date));
CREATE TABLE IF NOT EXISTS sc_splits (               -- needed to rebuild as-traded prices from Yahoo's split-adjusted ones
    ticker VARCHAR NOT NULL, ex_date DATE NOT NULL, ratio DOUBLE NOT NULL, snapshot_id BIGINT, PRIMARY KEY (ticker, ex_date));
CREATE TABLE IF NOT EXISTS sc_fetch_log (
    ticker VARCHAR NOT NULL, fetched_at TIMESTAMP NOT NULL, status VARCHAR NOT NULL, detail VARCHAR);
-- v2 (D10a): listing events (delisting and deregistration forms, and the 8-K items used to classify why a company left).
-- Additive only: no v1 table changes. Loaded by smallcap-refresh-listing-events from the stored bulk snapshot.
CREATE TABLE IF NOT EXISTS sc_listing_events (
    accession VARCHAR PRIMARY KEY, cik BIGINT NOT NULL, form VARCHAR NOT NULL, filed DATE NOT NULL,
    accepted_at TIMESTAMP, items VARCHAR, snapshot_id BIGINT);
-- One row per company that filed a delisting (25, 25-NSE) or deregistration (15-12B/G, 15-15D) form.
-- exit_date: the LAST delisting form (earlier ones can be exchange transfers), else the first deregistration.
-- cause, checked in this order: bankruptcy (8-K 1.03 within 365 days before to 30 after), acquired (8-K 2.01 or 5.01
-- within 30 days either side), listing_failure (8-K 3.01 within 365 days before), else unknown. still_listed = the
-- company has a current Nasdaq/NYSE ticker, so its delisting form was most likely a transfer between exchanges.
CREATE OR REPLACE VIEW sc_delistings AS
-- cause rule r2 (D10d, 27 Oct 2026; FE readiness v2.1). Audited on a fresh sample: 88.9% class agreement, so the engine
-- adds a label-error allowance to the adverse survivorship bound rather than trusting the labels (protocol r6).
WITH d AS (
    SELECT cik,
           max(filed) FILTER (WHERE form IN ('25', '25-NSE')) AS last_delisting_form,
           min(filed) FILTER (WHERE form LIKE '15-%') AS first_deregistration,
           count(*) FILTER (WHERE form IN ('25', '25-NSE')) AS n_delisting_forms
    FROM sc_listing_events WHERE form IN ('25', '25-NSE') OR form LIKE '15-%' GROUP BY cik),
e AS (SELECT cik, coalesce(last_delisting_form, first_deregistration) AS exit_date, * EXCLUDE (cik) FROM d),
k AS (SELECT cik, filed, coalesce(items, '') AS items FROM sc_listing_events WHERE form IN ('8-K', '8-K/A'))
SELECT e.cik, e.exit_date, e.last_delisting_form, e.first_deregistration, e.n_delisting_forms,
       CASE WHEN EXISTS (SELECT 1 FROM k WHERE k.cik = e.cik AND k.items LIKE '%1.03%'
                         AND k.filed BETWEEN e.exit_date - INTERVAL 180 DAY AND e.exit_date) THEN 'bankruptcy'
            WHEN EXISTS (SELECT 1 FROM k WHERE k.cik = e.cik AND (k.items LIKE '%2.01%' OR k.items LIKE '%5.01%')
                         AND k.filed BETWEEN e.exit_date - INTERVAL 30 DAY AND e.exit_date + INTERVAL 30 DAY) THEN 'acquired'
            WHEN EXISTS (SELECT 1 FROM k WHERE k.cik = e.cik AND k.items LIKE '%3.01%' AND (k.items LIKE '%1.01%' OR k.items LIKE '%1.02%')
                         AND k.filed BETWEEN e.exit_date - INTERVAL 30 DAY AND e.exit_date + INTERVAL 30 DAY)
                 AND NOT EXISTS (SELECT 1 FROM k WHERE k.cik = e.cik AND k.items LIKE '%3.01%'
                         AND k.filed BETWEEN e.exit_date - INTERVAL 365 DAY AND e.exit_date - INTERVAL 31 DAY) THEN 'acquired'
            WHEN EXISTS (SELECT 1 FROM k WHERE k.cik = e.cik AND k.items LIKE '%3.01%'
                         AND k.filed BETWEEN e.exit_date - INTERVAL 365 DAY AND e.exit_date) THEN 'listing_failure'
            WHEN EXISTS (SELECT 1 FROM k WHERE k.cik = e.cik AND k.items LIKE '%1.03%'
                         AND k.filed BETWEEN e.exit_date - INTERVAL 365 DAY AND e.exit_date + INTERVAL 90 DAY) THEN 'bankruptcy'
            WHEN e.last_delisting_form IS NOT NULL AND e.first_deregistration
                 BETWEEN e.last_delisting_form AND e.last_delisting_form + INTERVAL 45 DAY THEN 'acquired_inferred'
            ELSE 'unknown' END AS cause,
       EXISTS (SELECT 1 FROM sc_tickers t WHERE t.cik = e.cik) AS still_listed
FROM e;
-- v3 (D10c): SEC's own acceptance time (New York) read from each filing's index page. The bulk file's acceptanceDateTime
-- carries 0, 1 or 2 UTC conversions (FE readiness G3c, 26 Oct 2026), so it is not used when this table has a row.
CREATE TABLE IF NOT EXISTS sc_acceptance_truth (
    accession VARCHAR PRIMARY KEY, accepted_ny TIMESTAMP, status VARCHAR NOT NULL, url VARCHAR, page_sha256 VARCHAR,
    fetched_at TIMESTAMP NOT NULL, snapshot_id BIGINT);
INSERT INTO schema_info VALUES ('smallcap_schema_version', '3') ON CONFLICT (key) DO UPDATE SET value = '3';
-- v4 (D10d): sc_delistings uses cause rule r2.
INSERT INTO schema_info VALUES ('smallcap_schema_version', '4') ON CONFLICT (key) DO UPDATE SET value = '4';

-- v11: research lab. Every experiment is logged, including the failures.
CREATE SEQUENCE IF NOT EXISTS seq_experiment START 1;
CREATE TABLE IF NOT EXISTS experiments (
    experiment_id  BIGINT PRIMARY KEY DEFAULT nextval('seq_experiment'),
    protocol_name  VARCHAR NOT NULL,
    protocol_hash  VARCHAR NOT NULL,
    run_at         TIMESTAMP NOT NULL,
    code_version   VARCHAR,
    model          VARCHAR NOT NULL,
    params         VARCHAR,                    -- JSON
    eval_window    VARCHAR NOT NULL,           -- dev | validation | sealed
    n_dates        INTEGER,
    first_date     DATE,
    last_date      DATE,
    mean_ic        DOUBLE,
    ic_ci_low      DOUBLE,
    ic_ci_high     DOUBLE,
    nw_t           DOUBLE,
    spread_gross   DOUBLE,                     -- mean top-minus-bottom quintile excess return per period
    spread_net     DOUBLE,
    sharpe         DOUBLE,
    dsr            DOUBLE,                     -- deflated Sharpe: probability the Sharpe beats the best of n_trials by chance
    n_trials       INTEGER,                    -- dev trials consumed when this ran
    detail         VARCHAR                     -- JSON: per-date IC, notes, label truncation counts
);
CREATE TABLE IF NOT EXISTS sealed_openings (
    opened_at     TIMESTAMP NOT NULL,
    protocol_name VARCHAR NOT NULL,
    protocol_hash VARCHAR NOT NULL,
    experiment_id BIGINT,
    reason        VARCHAR
);

