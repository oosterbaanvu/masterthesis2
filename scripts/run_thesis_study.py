#!/usr/bin/env python
"""Frozen, resumable execution of the integrated study using the existing pilot runner."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import resource
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

from threadpoolctl import threadpool_info, threadpool_limits

from dq_framework import paths
from dq_framework.acquisition import sha256_file
from dq_framework.pilot.runner import load_config, run_replication


def execute(job):
    config, seed, scheme, out_root, digest = job
    cfg = load_config(config)
    # Imported native libraries may already have initialized before main() sets environment
    # variables, especially after fork. Enforce the limit through their runtime APIs too.
    with threadpool_limits(limits=2):
        pools = [{k: p[k] for k in ("internal_api", "num_threads", "version")} for p in threadpool_info()]
        out = run_replication(cfg, seed, scheme=scheme, out_root=Path(out_root))
    files = {p.name: sha256_file(p) for p in out.iterdir() if p.is_file()}
    record = {"input_digest": digest, "outputs": files,
              "worker_peak_rss_mb_upper_bound": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
              "threadpools": pools}
    (out / "complete.json").write_text(json.dumps(record, indent=2) + "\n")
    return str(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dataset")
    ap.add_argument("--seed", type=int)
    ap.add_argument("--scheme")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--out", type=Path, default=paths.RESULTS_DIR / "runs/thesis_integrated")
    args = ap.parse_args()
    if not 1 <= args.workers <= 2:
        raise ValueError("study compute policy permits one or two workers")
    for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[name] = "2"
    os.environ["DBT_SEND_ANONYMOUS_USAGE_STATS"] = "false"
    files = []
    for folder in (paths.CONFIG_DIR / "thesis", paths.CONFIG_DIR / "contracts", paths.ROOT / "src/dq_framework", paths.DBT_DIR):
        files += [p for p in folder.rglob("*") if p.is_file() and p.suffix in (".py", ".yaml", ".yml", ".sql")
                  and not {"__pycache__", "target", "logs", "dbt_packages"}.intersection(p.parts)]
    files += [Path(__file__).resolve(), paths.ROOT / "uv.lock", paths.CONFIG_DIR / "datasets.yaml"]
    hashes = {str(p.relative_to(paths.ROOT)): sha256_file(p) for p in sorted(files)}
    digest = hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest()
    args.out.mkdir(parents=True, exist_ok=True)
    frozen = args.out / "frozen_inputs.json"
    if frozen.exists() and json.loads(frozen.read_text())["digest"] != digest:
        raise ValueError("Frozen inputs changed. Use a new output root; do not overwrite prior experiments.")
    frozen.write_text(json.dumps({"digest": digest, "files": hashes}, indent=2) + "\n")
    jobs = []
    for config in sorted((paths.CONFIG_DIR / "thesis").glob("uci_*.yaml")):
        cfg = load_config(config)
        if args.dataset and cfg["dataset"] != args.dataset:
            continue
        for scheme in cfg["schemes"]:
            if args.scheme and scheme != args.scheme:
                continue
            for seed in cfg.get(f"{scheme}_seeds", cfg["pilot_seeds"]):
                if args.seed and args.seed != seed:
                    continue
                name = f"{cfg['dataset']}-{scheme}-{'d' if scheme == 'delivery' else 's'}{seed}"
                out = args.out / name
                complete = out / "complete.json"
                if complete.exists():
                    record = json.loads(complete.read_text())
                    if record["input_digest"] == digest and all((out / k).exists() and sha256_file(out / k) == v
                                                               for k, v in record["outputs"].items()):
                        print(f"REUSED {name}", flush=True)
                        continue
                    raise ValueError(f"Completed run changed: {out}")
                jobs.append((str(config), seed, scheme, str(args.out), digest))
    print(f"FROZEN {digest}; {len(jobs)} pending jobs; workers={args.workers}", flush=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(execute, j): j for j in jobs}
        for f in as_completed(futures):
            print(f"COMPLETED {f.result()}", flush=True)


if __name__ == "__main__":
    main()
