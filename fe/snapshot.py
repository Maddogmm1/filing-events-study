"""Immutable raw snapshots. Every fetch is written once, hashed, made read-only and registered
in the `snapshots` table, so any number in the database can be traced to a file that cannot
have changed since. Layout: <snapshot_dir>/<source>/<dataset>/<UTC timestamp>/<filename>."""
import hashlib
import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _register(con, root: Path, source: str, dataset: str, filename: str, now: datetime,
              writer, params: dict | None, rows: int | None) -> int:
    folder = Path(root) / source / dataset / now.strftime("%Y%m%dT%H%M%S.%fZ")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / filename
    if path.exists():
        raise FileExistsError(f"snapshot already exists and snapshots are immutable: {path}")
    writer(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    os.chmod(path, stat.S_IREAD)
    return con.execute(
        "INSERT INTO snapshots (source, dataset, fetched_at, path, sha256, row_count, params) "
        "VALUES (?, ?, ?, ?, ?, ?, ?) RETURNING snapshot_id",
        [source, dataset, now.replace(tzinfo=None), str(path), digest, rows,
         json.dumps(params or {}, sort_keys=True, default=str)]).fetchone()[0]


def write_bytes_snapshot(con, root, source, dataset, filename, data: bytes,
                         params=None, rows=None, now=None) -> int:
    return _register(con, root, source, dataset, filename, now or _utc_now(),
                     lambda p: p.write_bytes(data), params, rows)


def write_parquet_snapshot(con, root, source, dataset, filename, df: pd.DataFrame,
                           params=None, now=None) -> int:
    return _register(con, root, source, dataset, filename, now or _utc_now(),
                     lambda p: df.to_parquet(p, index=False, compression="zstd"), params, len(df))
