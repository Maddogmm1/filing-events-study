"""A pre-registered protocol: what will be tested, how it is judged, and how much trying is allowed.
The file is hashed and the hash is written to config/protocols.lock before any result exists. If the file changes
afterwards the lab refuses to run, because a protocol edited after seeing results is not a protocol."""
import hashlib
import json
import tomllib
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REQUIRED = ["name", "universe", "start", "dev_end", "validation_end", "sealed_start", "horizon_periods", "embargo_periods",
            "max_dev_trials", "cost_bps_one_way", "models", "feature_sets"]


class ProtocolError(RuntimeError):
    pass


@dataclass(frozen=True)
class Protocol:
    name: str
    universe: str
    start: pd.Timestamp
    dev_end: pd.Timestamp
    validation_end: pd.Timestamp
    sealed_start: pd.Timestamp
    horizon_periods: int
    embargo_periods: int
    max_dev_trials: int
    cost_bps_one_way: float
    models: tuple[str, ...]
    feature_sets: tuple[str, ...]
    min_history_sessions: int
    min_names_per_date: int
    pass_rule: str
    sha256: str
    path: Path


def file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_protocol(path: Path | str) -> Protocol:
    path = Path(path)
    d = tomllib.loads(path.read_text(encoding="utf-8"))
    missing = [k for k in REQUIRED if k not in d]
    if missing:
        raise ProtocolError(f"protocol {path.name} is missing: {', '.join(missing)}")
    ts = lambda k: pd.Timestamp(d[k])
    p = Protocol(name=d["name"], universe=d["universe"], start=ts("start"), dev_end=ts("dev_end"),
                 validation_end=ts("validation_end"), sealed_start=ts("sealed_start"),
                 horizon_periods=int(d["horizon_periods"]), embargo_periods=int(d["embargo_periods"]),
                 max_dev_trials=int(d["max_dev_trials"]), cost_bps_one_way=float(d["cost_bps_one_way"]),
                 models=tuple(d["models"]), feature_sets=tuple(d["feature_sets"]),
                 min_history_sessions=int(d.get("min_history_sessions", 252)), min_names_per_date=int(d.get("min_names_per_date", 50)),
                 pass_rule=str(d.get("pass_rule", "")), sha256=file_hash(path), path=path)
    if not (p.start < p.dev_end < p.validation_end < p.sealed_start):
        raise ProtocolError("dates must run start < dev_end < validation_end < sealed_start")
    if p.horizon_periods < 1 or p.max_dev_trials < 1:
        raise ProtocolError("horizon_periods and max_dev_trials must be at least 1")
    return p


def lock_path(root: Path) -> Path:
    return Path(root) / "config" / "protocols.lock"


def read_lock(root: Path) -> dict[str, str]:
    p = lock_path(root)
    if not p.exists():
        return {}
    return {a: b for a, b in (ln.split() for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip() and not ln.startswith("#"))}


def write_lock(root: Path, protocol: Protocol) -> str:
    """Pre-register. Refuses to overwrite a different hash for the same protocol name."""
    cur = read_lock(root)
    if protocol.name in cur and cur[protocol.name] != protocol.sha256:
        raise ProtocolError(f"{protocol.name} is already locked with a different hash. Create a new protocol file with a new name instead of editing this one.")
    cur[protocol.name] = protocol.sha256
    lp = lock_path(root)
    lp.parent.mkdir(parents=True, exist_ok=True)
    lp.write_text("# protocol name, sha256 of the protocol file when it was pre-registered. Commit this file to git.\n"
                  + "".join(f"{k} {v}\n" for k, v in sorted(cur.items())), encoding="utf-8")
    return protocol.sha256


def require_locked(root: Path, protocol: Protocol) -> None:
    cur = read_lock(root)
    if protocol.name not in cur:
        raise ProtocolError(f"{protocol.name} has not been locked. Run: python -m fe.run lock {protocol.path}")
    if cur[protocol.name] != protocol.sha256:
        raise ProtocolError(f"{protocol.path.name} has changed since it was locked (hash {protocol.sha256[:12]} vs locked {cur[protocol.name][:12]}). "
                            "Results from an edited protocol cannot be trusted. Restore the file or register a new protocol under a new name.")


def describe(p: Protocol) -> str:
    return json.dumps({"name": p.name, "sha256": p.sha256, "development": f"{p.start:%Y-%m-%d} to {p.dev_end:%Y-%m-%d}",
                       "validation": f"{p.dev_end + pd.Timedelta(days=1):%Y-%m-%d} to {p.validation_end:%Y-%m-%d}",
                       "sealed_from": f"{p.sealed_start:%Y-%m-%d}", "horizon_periods": p.horizon_periods,
                       "max_dev_trials": p.max_dev_trials}, indent=2)
