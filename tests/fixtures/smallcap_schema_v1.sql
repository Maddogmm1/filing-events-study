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
INSERT INTO schema_info VALUES ('smallcap_schema_version', '1') ON CONFLICT (key) DO UPDATE SET value = '1';
