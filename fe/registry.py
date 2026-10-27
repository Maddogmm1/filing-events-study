"""Experiment registry and the sealed-window rules. Rules are enforced here, in code, not by promise."""
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone

from fe.protocol import Protocol


class RegistryError(RuntimeError):
    pass


def dev_trials(con, protocol: Protocol) -> int:
    return con.execute("SELECT COUNT(*) FROM experiments WHERE protocol_hash = ? AND eval_window = 'dev'", [protocol.sha256]).fetchone()[0]


def check_may_run(con, protocol: Protocol, model: str, params: dict, window: str, confirm_sealed: bool = False) -> None:
    key = json.dumps(params, sort_keys=True)
    if window not in ("dev", "validation", "sealed"):
        raise RegistryError(f"unknown window {window}")
    if window == "dev":
        n = dev_trials(con, protocol)
        same = con.execute("SELECT COUNT(*) FROM experiments WHERE protocol_hash=? AND eval_window='dev' AND model=? AND params=?",
                           [protocol.sha256, model, key]).fetchone()[0]
        if same:
            raise RegistryError("this exact model and parameter set was already run on the development window; re-running it would not be a new trial")
        if n >= protocol.max_dev_trials:
            raise RegistryError(f"trial budget used up ({n} of {protocol.max_dev_trials}). More trying needs a new protocol, written down before running.")
    elif window == "validation":
        if not con.execute("SELECT COUNT(*) FROM experiments WHERE protocol_hash=? AND eval_window='dev' AND model=? AND params=?",
                           [protocol.sha256, model, key]).fetchone()[0]:
            raise RegistryError("a configuration must be run on the development window before it may be validated")
        if con.execute("SELECT COUNT(*) FROM experiments WHERE protocol_hash=? AND eval_window='validation' AND model=? AND params=?",
                       [protocol.sha256, model, key]).fetchone()[0]:
            raise RegistryError("this configuration was already validated once; the validation window is single use per configuration")
    else:
        if not confirm_sealed:
            raise RegistryError("the sealed window is closed. It can be opened once, deliberately: see research-open-sealed.")
        if con.execute("SELECT COUNT(*) FROM sealed_openings WHERE protocol_hash=?", [protocol.sha256]).fetchone()[0]:
            raise RegistryError("the sealed window was already opened for this protocol; it cannot be opened again")
        if not con.execute("SELECT COUNT(*) FROM experiments WHERE protocol_hash=? AND eval_window='validation' AND model=? AND params=?",
                           [protocol.sha256, model, key]).fetchone()[0]:
            raise RegistryError("only a configuration that was validated may be tested on the sealed window")


def record(con, protocol: Protocol, model: str, params: dict, window: str, result: dict, code_version: str,
           run_at: datetime | None = None) -> int:
    run_at = run_at or datetime.now(timezone.utc).replace(tzinfo=None)
    n_trials = dev_trials(con, protocol) + (1 if window == "dev" else 0)
    row = con.execute(
        "INSERT INTO experiments (protocol_name, protocol_hash, run_at, code_version, model, params, eval_window, n_dates, first_date, last_date, "
        "mean_ic, ic_ci_low, ic_ci_high, nw_t, spread_gross, spread_net, sharpe, dsr, n_trials, detail) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) RETURNING experiment_id",
        [protocol.name, protocol.sha256, run_at, code_version, model, json.dumps(params, sort_keys=True), window,
         result.get("n_dates"), result.get("first_date"), result.get("last_date"), result.get("mean_ic"), result.get("ic_ci_low"),
         result.get("ic_ci_high"), result.get("nw_t"), result.get("spread_gross"), result.get("spread_net"), result.get("sharpe"),
         result.get("dsr"), n_trials, json.dumps(result.get("detail", {}), default=str)]).fetchone()
    return int(row[0])


def record_sealed_opening(con, protocol: Protocol, experiment_id: int | None, reason: str) -> None:
    con.execute("INSERT INTO sealed_openings VALUES (?,?,?,?,?)",
                [datetime.now(timezone.utc).replace(tzinfo=None), protocol.name, protocol.sha256, experiment_id, reason])


def sealed_is_sealed(con, protocol: Protocol) -> bool:
    return con.execute("SELECT COUNT(*) FROM sealed_openings WHERE protocol_hash=?", [protocol.sha256]).fetchone()[0] == 0


def code_version(root: Path) -> str:
    try:
        h = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain"], cwd=root, capture_output=True, text=True, timeout=10).stdout.strip()
        return (h or "unknown") + ("+uncommitted" if dirty else "")
    except Exception:
        return "unknown"
