"""Command-line interface: ``dqf <command>``.

  dqf datasets download [KEY ...]      download + verify against pinned hashes
  dqf datasets verify [KEY ...]        re-verify raw files (read-only)
  dqf controls generate [DATASET ...]  regenerate dbt models/tests from contracts
  dqf controls check DATASET           run dbt controls on the untouched table, report failure rates
  dqf profile DATASET                  descriptive profile of the analysed table
  dqf run CONFIG.yaml [--report PATH]  end-to-end evaluation run (controls + injection + detector)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from dq_framework import paths


def _cmd_datasets(args: argparse.Namespace) -> int:
    script = "download_datasets" if args.action == "download" else "verify_datasets"
    sys.path.insert(0, str(paths.ROOT / "scripts"))
    mod = __import__(script)
    return mod.main(args.keys)


def _cmd_controls(args: argparse.Namespace) -> int:
    from dq_framework.contracts import load_contract
    from dq_framework.controls import dbt_gen

    if args.action == "generate":
        names = args.datasets or [p.stem for p in (paths.CONFIG_DIR / "contracts").glob("*.yaml")]
        for ds in names:
            for p in dbt_gen.write(load_contract(ds)):
                print("wrote", p.relative_to(paths.ROOT))
        return 0
    if args.action == "check":
        from dq_framework.controls import fit_reference_stats, run_controls
        from dq_framework.datasets import load_contract_table, make_split

        ds = args.datasets[0]
        c = load_contract(ds)
        df = load_contract_table(ds, c)
        part = make_split(df, c, seed=args.split_seed)
        stats = fit_reference_stats(c, df[part == "reference"])
        run = run_controls(c, df.assign(_scenario_id="untouched"), stats, paths.RESULTS_DIR / "runs" / f"controls-{ds}")
        summ = run.tests[["test_name", "rule_id", "tier", "status", "failures"]]
        print(summ.to_string(index=False))
        print(f"\n{len(run.alerts)} alerts on {len(df)} untouched rows; dbt {run.dbt_version}; {run.elapsed_s:.1f} s")
        return 0
    return 2


def _cmd_profile(args: argparse.Namespace) -> int:
    from dq_framework.contracts import load_contract
    from dq_framework.datasets import load_contract_table
    from dq_framework.profiling import profile_table

    c = load_contract(args.dataset)
    df = load_contract_table(args.dataset, c)
    print(json.dumps(profile_table(df, exclude=["_row_id"]), indent=2, default=str))
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    from dq_framework import pipeline, reporting

    cfg = pipeline.RunConfig.from_yaml(args.config)
    res = pipeline.run(cfg)
    report = Path(args.report) if args.report else res["out_dir"] / "report.md"
    reporting.write(res, report)
    print(f"run {res['manifest']['run_id']}: {len(cfg.scenarios)} scenarios in {res['manifest']['elapsed_s']} s")
    print(f"artefacts: {res['out_dir']}")
    print(f"report:    {report}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="dqf", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("datasets")
    d.add_argument("action", choices=["download", "verify"])
    d.add_argument("keys", nargs="*")
    d.set_defaults(func=_cmd_datasets)
    c = sub.add_parser("controls")
    c.add_argument("action", choices=["generate", "check"])
    c.add_argument("datasets", nargs="*")
    c.add_argument("--split-seed", type=int, default=1)
    c.set_defaults(func=_cmd_controls)
    p = sub.add_parser("profile")
    p.add_argument("dataset")
    p.set_defaults(func=_cmd_profile)
    r = sub.add_parser("run")
    r.add_argument("config")
    r.add_argument("--report")
    r.set_defaults(func=_cmd_run)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
