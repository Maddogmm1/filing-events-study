"""Command line: pre-register a protocol, run one hypothesis of a locked protocol, show status.

  python -m fe.run lock     research/filing_events_v1.toml
  python -m fe.run status   research/filing_events_v1.toml --db data/smallcap.duckdb
  python -m fe.run run      research/filing_events_v1.toml --db data/smallcap.duckdb --hypothesis H1_reaction_continuation

The lock hash goes into config/protocols.lock under the project root (the current folder). Every run is recorded in
the database's experiments table and counts against the protocol's development-trial budget."""
import argparse
import sys
from pathlib import Path

from fe import data as sc
from fe import events as E
from fe import registry as reg
from fe.protocol import ProtocolError, read_lock, write_lock


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m fe.run")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("lock", "status", "run"):
        s = sub.add_parser(name)
        s.add_argument("protocol", type=Path)
        if name != "lock":
            s.add_argument("--db", type=Path, default=Path("data/smallcap.duckdb"))
        if name == "run":
            s.add_argument("--hypothesis", required=True)
            s.add_argument("--window", default="dev", choices=["dev", "validation"])
            s.add_argument("--decile", type=float)
            s.add_argument("--hold", type=int)
            s.add_argument("--entry", choices=["open"])
            s.add_argument("--placebo", choices=["random_earnings_10pct"])
    a = ap.parse_args(argv)
    root = Path.cwd()
    try:
        if a.protocol.name.endswith(".DRAFT.toml"):
            raise ProtocolError("this is a DRAFT. Copy it to a name without .DRAFT once agreed, then lock that file.")
        p = E.load_event_protocol(a.protocol)
        if a.cmd == "lock":
            write_lock(root, p)
            print(f"Locked {p.name}: {p.sha256}\nCommit config/protocols.lock and the protocol file BEFORE running anything.")
            return 0
        con = sc.open_smallcap(a.db)
        if a.cmd == "status":
            print(f"{p.name}  sha256 {p.sha256}")
            print(f"locked: {read_lock(root).get(p.name) == p.sha256}")
            print(f"development trials used: {reg.dev_trials(con, p)} of {p.max_dev_trials}")
            print(f"sealed window: {'SEALED' if reg.sealed_is_sealed(con, p) else 'OPENED'}")
            return 0
        variant = {k: v for k, v in (("decile", a.decile), ("hold_sessions", a.hold), ("entry", a.entry),
                                     ("placebo", a.placebo)) if v is not None}
        res = E.run(con, con, root, p, a.hypothesis, a.window, variant=variant)
        d = res["detail"]
        print(f"experiment {res['experiment_id']}  {a.hypothesis}  window {a.window}  {res['first_date']} to {res['last_date']}")
        print(f"  positions {d['n_events']:,} (long {d['n_long']:,}, short {d['n_short']:,})")
        print(f"  primary estimand ({d['estimand']}): {res['mean_ic']:+.2%}; 95% interval [{res['ic_ci_low']:+.2%}, {res['ic_ci_high']:+.2%}]")
        print(f"  mean per position: gross {res['spread_gross']:+.2%}, net {res['spread_net']:+.2%}")
        print(f"  calendar-time monthly: Newey-West t {res['nw_t']:+.2f}, annualised Sharpe {res['sharpe']:+.2f}, deflated Sharpe {res['dsr']:.3f}")
        print(f"  verdict under the pre-registered rule: {res['verdict']}")
        return 0
    except (ProtocolError, reg.RegistryError, ValueError) as e:
        print(f"REFUSED: {e}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
