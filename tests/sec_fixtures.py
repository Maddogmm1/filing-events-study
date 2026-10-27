"""Synthetic SEC bulk-file fixtures."""
import json
import zipfile


def _cols(rows):
    keys = ["accessionNumber", "filingDate", "acceptanceDateTime", "form", "items"]
    return {k: [r[i] for r in rows] for i, k in enumerate(keys)}


def make_zip(path):
    live = {"cik": "0000000101", "name": "Small  Widget Co", "entityType": "operating", "sic": "3559", "sicDescription": "Machinery",
            "tickers": ["SWID"], "exchanges": ["Nasdaq"], "filings": {"recent": _cols([
                ("0000101-24-000001", "2024-02-01", "2024-02-01T16:30:12.000Z", "8-K", "2.02,9.01"),
                ("0000101-24-000002", "2024-03-01", "2024-03-01T09:00:00.000Z", "8-K", "5.02"),      # not wanted
                ("0000101-24-000003", "2024-04-01", "2024-04-01T17:05:00.000Z", "NT 10-Q", ""),
                ("0000101-24-000004", "2024-05-01", "2024-05-01T10:00:00.000Z", "10-Q", "")])},          # not wanted
            "files": [{"name": "CIK0000000101-submissions-001.json"}]}
    page = _cols([("0000101-12-000009", "2012-08-01", "2012-08-01T16:10:00.000Z", "8-K", "4.02")])
    gone = {"cik": "0000000202", "name": "Bankrupt Gadgets Inc", "entityType": "operating", "sic": "3674", "tickers": [], "exchanges": [],
            "filings": {"recent": _cols([("0000202-15-000001", "2015-03-01", "2015-03-01T18:00:00.000Z", "8-K", "2.02")])}}
    person = {"cik": "0000000303", "name": "A Person", "entityType": "other", "sic": "", "filings": {"recent": _cols([
        ("0000303-20-000001", "2020-01-01", "2020-01-01T10:00:00.000Z", "8-K", "2.02")])}}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("CIK0000000101.json", json.dumps(live))
        z.writestr("CIK0000000101-submissions-001.json", json.dumps(page))
        z.writestr("CIK0000000202.json", json.dumps(gone))
        z.writestr("CIK0000000303.json", json.dumps(person))
