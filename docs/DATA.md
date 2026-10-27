# Data

Nothing in this repository is market data apart from aggregated results. To rebuild the database (`data/smallcap.duckdb`, schema in `fe/smallcap_schema.sql`):

| Table | Source | How |
|---|---|---|
| `sc_filers`, `sc_events` | SEC EDGAR bulk submissions file (`submissions.zip`, public) | `fe.data.load_bulk(con, zip_path, snapshot_id)`: operating companies only; earnings 8-Ks (2.02), auditor changes (4.01), non-reliance (4.02), late-filing notices (NT 10-K/Q) |
| `sc_listing_events` → view `sc_delistings` | Same bulk file | `fe.data.load_listing_events(...)`: Forms 25/25-NSE/15 and 8-Ks with items 1.03/2.01/3.01/5.01; the view applies delisting-cause rule r2 |
| `sc_acceptance_truth` | SEC filing index pages (public) | `fe.data.refresh_acceptance_truth(con, snapshot_dir, user_agent, fe.data.acceptance_scope(...))`; SEC asks for a contact e-mail in the User-Agent and at most 10 requests a second (the code uses about 5) |
| `sc_tickers` | SEC `company_tickers_exchange.json` (public) | ticker, CIK, name, exchange |
| `sc_prices`, `sc_splits` | Your own daily price source | ticker, date, open, high, low, close, split-adjusted close, volume; split ratios. Not included: the free source used for the study does not allow redistribution |

Important: SEC's bulk-file `acceptanceDateTime` is not reliably New York time (see `docs/READINESS_v2.md`). The engine uses `sc_acceptance_truth` when the protocol sets `acceptance_time_source = "sec_index"` and excludes events without a verified time.
