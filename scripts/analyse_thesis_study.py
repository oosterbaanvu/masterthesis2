#!/usr/bin/env python
"""Case-clustered selection reliability under a shared total review budget.

Selector parameters come only from the frozen study.yaml. Target outcomes never enter choose().
Intervals are conditional error-case bootstrap sensitivity, not population inference over datasets.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from dq_framework import paths
from dq_framework.acquisition import sha256_file
from dq_framework.contracts import load_contract
from dq_framework.datasets import load_contract_table
from dq_framework.pilot.splits import delivery_split, pilot_split

NO_ADDITION = "NO_ADDITION"


def require_complete_study(root):
    expected = set()
    for config in sorted((paths.CONFIG_DIR / "thesis").glob("uci_*.yaml")):
        cfg = yaml.safe_load(config.read_text())
        for scheme in cfg["schemes"]:
            for seed in cfg.get(f"{scheme}_seeds", cfg["pilot_seeds"]):
                expected.add(f"{cfg['dataset']}-{scheme}-{'d' if scheme == 'delivery' else 's'}{seed}")
    actual = {p.parent.name for p in root.glob("*/complete.json")}
    if actual != expected:
        raise ValueError(f"Incomplete/different study: missing={sorted(expected - actual)}, unexpected={sorted(actual - expected)}")


def case_means(frame):
    return frame.groupby(["case_key", "family", "detector"])["utility"].mean().unstack("detector")


def choose(training, rule, robust=False):
    table = case_means(training).dropna()
    if not len(table) or not len(table.columns):
        return NO_ADDITION, "INSUFFICIENT_EVIDENCE", np.nan
    means = table.mean()
    if means.max() <= 0:
        return NO_ADDITION, "NO_ADDITION", float(means.max())
    if not robust:
        return str(means.idxmax()), "SELECT", float(means.max())
    if len(table) < rule["min_cases"]:
        return NO_ADDITION, "INSUFFICIENT_EVIDENCE", np.nan
    rng = np.random.default_rng(rule["seed"])
    draws = rng.integers(0, len(table), size=(rule["bootstrap_replicates"], len(table)))
    lower = np.quantile(table.to_numpy()[draws].mean(axis=1), rule["lower_quantile"], axis=0)
    worst_family = table.groupby(level="family").mean().min().to_numpy()
    eligible = (lower > rule["minimum_lower_gain"]) & (worst_family >= rule["worst_family_floor"])
    if not eligible.any():
        return NO_ADDITION, "INSUFFICIENT_EVIDENCE", float(lower.max())
    best = np.flatnonzero(eligible)[np.argmax(lower[eligible])]
    return str(table.columns[best]), "SELECT", float(lower[best])


def assess(training, target, rule, context):
    eligible = sorted(set(training.detector) & set(target.detector))
    training, target = training[training.detector.isin(eligible)], target[target.detector.isin(eligible)]
    if not len(training) or not len(target):
        return []
    target_means = case_means(target).mean()
    oracle_value = max(0.0, target_means.max())
    oracle = str(target_means.idxmax()) if target_means.max() > 0 else NO_ADDITION
    out = []
    for robust in (False, True):
        choice, decision, training_score = choose(training, rule, robust)
        value = 0.0 if choice == NO_ADDITION else float(target_means[choice])
        net_hits = np.nan
        if "added_hits" in target and "displaced_hits" in target:
            selected = target[target.detector == choice]
            net_hits = 0.0 if choice == NO_ADDITION else float(
                selected.assign(net=selected.added_hits - selected.displaced_hits).groupby("case_key").net.mean().mean())
        out.append({**context, "selector": "robust" if robust else "naive", "choice": choice,
                    "decision": decision, "training_score": training_score, "target_utility": value,
                    "oracle": oracle, "oracle_utility": oracle_value, "regret": max(0.0, oracle_value - value),
                    "exact_agreement": choice == oracle, "within_005": oracle_value - value <= .005,
                    "target_net_added_hits_per_scenario": net_hits,
                    "training_cases": training.case_key.nunique(), "target_cases": target.case_key.nunique()})
    return out


def load_runs(root):
    frames, failures, runtime, overlaps, curves = [], [], [], [], []
    frozen = json.loads((root / "frozen_inputs.json").read_text())
    digest = frozen["digest"]
    for filename, sha in frozen.get("files", {}).items():
        if sha256_file(paths.ROOT / filename) != sha:
            raise ValueError(f"Frozen scientific input changed: {filename}")
    for complete in sorted(root.glob("*/complete.json")):
        folder = complete.parent
        record = json.loads(complete.read_text())
        if record["input_digest"] != digest:
            raise ValueError(f"Run input digest differs: {folder}")
        for filename, sha in record["outputs"].items():
            if not (folder / filename).is_file() or sha256_file(folder / filename) != sha:
                raise ValueError(f"Run output changed or absent: {folder / filename}")
        manifest = json.loads((folder / "manifest.json").read_text())
        common = {"dataset": manifest["dataset"], "pilot_seed": manifest["pilot_seed"], "scheme": manifest["scheme"]}
        scenarios = pd.read_csv(folder / "scenarios.csv")
        metrics = pd.read_csv(folder / "detector_metrics.csv")
        metrics = metrics[~metrics.detector.str.contains("@row")]
        baseline = pd.read_csv(folder / "baseline_metrics.csv")
        baseline = baseline.merge(scenarios[["sid", "n_rows"]], on="sid", validate="many_to_one")
        baseline["native_baseline_flags"] = np.rint(baseline.recall_B * baseline.n_injected
            + baseline.B_alerts_untouched_per_1k * baseline.n_rows / 1000).astype(int)
        metrics = metrics.merge(baseline[["sid", "baseline", "native_baseline_flags"]],
                                on=["sid", "baseline"], validate="many_to_one")
        frames.append(metrics.merge(scenarios, on="sid", validate="many_to_one").assign(**common))
        f = pd.read_csv(folder / "failures.csv")
        if len(f):
            failures.append(f.assign(**common))
        for key, det in manifest["detectors"].items():
            runtime.append({**common, "detector": key, "status": det["status"], "compatibility": det["compatibility"],
                            "fit_seconds": det.get("fit_seconds"), "score_seconds": det.get("score_seconds"),
                            "scenarios": manifest["n_scenarios"], "failed_scenarios": manifest["n_failed_scenarios"],
                            "elapsed_s": manifest["elapsed_s"], "holdout_excluded": manifest["partitions"]["holdout_excluded"],
                            "worker_peak_rss_mb_upper_bound": json.loads(complete.read_text())["worker_peak_rss_mb_upper_bound"]})
        overlaps.append(pd.read_csv(folder / "shared_overlap.csv").merge(
            scenarios[["sid", "partition", "role", "family"]], on="sid", validate="many_to_one").assign(**common))
        curves.append(pd.read_csv(folder / "pr_curves.csv").assign(**common))
    return pd.concat(frames, ignore_index=True), failures, pd.DataFrame(runtime), pd.concat(overlaps), pd.concat(curves)


def audit_partitions(root):
    """Check actual changed-cell logs and SQL input rows against the reserved partition."""
    tables, rows = {}, []
    for complete in sorted(root.glob("*/complete.json")):
        folder = complete.parent
        manifest = json.loads((folder / "manifest.json").read_text())
        ds, seed, scheme = manifest["dataset"], manifest["pilot_seed"], manifest["scheme"]
        contract = load_contract(ds)
        if ds not in tables:
            tables[ds] = load_contract_table(ds, contract)
        df = tables[ds]
        cfg = yaml.safe_load((paths.CONFIG_DIR / f"thesis/{ds}.yaml").read_text())
        if scheme == "delivery":
            part = delivery_split(df, contract, cfg["deliveries"][seed - 1], holdout_seed=cfg["holdout_seed"])
        else:
            part = pilot_split(df, contract, seed, scheme=scheme, fractions=tuple(cfg["fractions"]),
                               holdout_seed=cfg["holdout_seed"], pool_max_rows=cfg["pool_max_rows"])
        assignments = dict(zip(df["_row_id"], part, strict=True))
        logs = pd.read_parquet(folder / "injection_log.parquet")
        scenarios = pd.read_csv(folder / "scenarios.csv").set_index("sid")
        if not logs["_row_id"].map(assignments).eq(logs.sid.map(scenarios.partition)).all():
            raise ValueError(f"Injection outside its permitted partition: {folder}")
        counts = logs.groupby("sid").size().reindex(scenarios.index)
        if not counts.eq(scenarios.realised).all() or logs.duplicated(["sid", "_row_id", "column"]).any():
            raise ValueError(f"Changed-cell counts/uniqueness invalid: {folder}")
        if not set(logs.column) <= set(contract.column_names):
            raise ValueError(f"Excluded prediction target in injection log: {folder}")
        batch_ids = pd.read_parquet(folder / "controls/batch.parquet", columns=["_row_id"])["_row_id"]
        batch_part = batch_ids.map(assignments)
        if not batch_part.isin(["selection", "test"]).all():
            raise ValueError(f"Non-design row in SQL evaluation input: {folder}")
        rows.append({"dataset": ds, "seed": seed, "scheme": scheme, "changed_cells": len(logs),
                     "successful_scenarios": len(scenarios), "sql_input_rows": len(batch_ids),
                     "reserved_rows": int((part == "holdout").sum()), "reserved_injections": 0,
                     "non_design_sql_rows": 0, "count_and_uniqueness_check": "PASS"})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", type=Path, default=paths.RESULTS_DIR / "runs/thesis_integrated")
    ap.add_argument("--out", type=Path, default=paths.RESULTS_DIR / "thesis_integrated")
    args = ap.parse_args()
    require_complete_study(args.root)
    cfg = yaml.safe_load((paths.CONFIG_DIR / "thesis/study.yaml").read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    raw, failures, runtime, overlaps, curves = load_runs(args.root)
    audit_partitions(args.root).to_csv(args.out / "holdout_audit.csv", index=False)
    raw["case_key"] = raw.dataset + "|" + raw.case_id
    shutil.copyfile(args.root / "frozen_inputs.json", args.out / "frozen_inputs.json")
    provenance, burdens, inventory = [], [], []
    for complete in sorted(args.root.glob("*/complete.json")):
        folder = complete.parent
        manifest = json.loads((folder / "manifest.json").read_text())
        common = {k: manifest[k] for k in ("dataset", "pilot_seed", "scheme")}
        provenance.append({"manifest": manifest, "completion": json.loads(complete.read_text())})
        burdens.append(pd.read_csv(folder / "untouched_burden.csv").assign(**common))
        scenarios = pd.read_csv(folder / "scenarios.csv")
        inventory.append(scenarios.groupby(["set", "role", "family", "mechanism_class", "rate"]).agg(
            scenarios=("sid", "size"), intended=("intended", "sum"), realised=("realised", "sum"),
            min_realised=("realised", "min"), max_realised=("realised", "max")).reset_index().assign(**common))
    (args.out / "run_provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    pd.concat(burdens, ignore_index=True).to_csv(args.out / "untouched_workload.csv", index=False)
    pd.concat(inventory, ignore_index=True).to_csv(args.out / "scenario_inventory.csv", index=False)
    runtime.to_csv(args.out / "runtime.csv", index=False)
    pd.concat(failures, ignore_index=True).to_csv(args.out / "failures.csv", index=False) if failures else None
    curves.groupby(["dataset", "detector", "family", "recall"]).precision.mean().reset_index().to_csv(
        args.out / "pr_curves.csv", index=False)
    overlaps.groupby(["dataset", "scheme", "baseline", "partition", "role", "family", "a", "b"])[["a_only", "b_only", "both", "n_injected"]].sum().reset_index().to_csv(
        args.out / "overlap.csv", index=False)
    long = []
    for budget in cfg["total_budgets"]:
        f = raw.copy()
        f["budget"] = budget
        for name, metric in (("utility", "total_delta"), ("recall", "total_recall"),
                             ("base_recall", "total_base_recall"), ("precision_lb", "total_precision_lb"),
                             ("reviews", "total_reviews"), ("added_hits", "total_unique_added_hits"),
                             ("displaced_hits", "total_displaced_hits"), ("solo_recall", "solo_recall")):
            f[name] = f[f"{metric}@{budget}"]
        f["baseline_reviews"] = np.minimum(f.native_baseline_flags, np.rint(budget * f.n_rows / 1000)).astype(int)
        long.append(f)
    data = pd.concat(long, ignore_index=True)
    summary_cols = ["utility", "recall", "base_recall", "precision_lb", "ap_all_scored", "scored_positive_coverage", "recall_L",
                    "reviews", "baseline_reviews", "added_hits", "displaced_hits", "solo_recall"]
    primary = data[(data.role == "primary") & (data.partition == "test")]
    groups = ["dataset", "scheme", "baseline", "budget", "detector", "family", "mechanism_class", "rate"]
    primary.groupby(groups)[summary_cols].mean().reset_index().to_csv(args.out / "family_metrics.csv", index=False)
    case_groups = ["dataset", "baseline", "budget", "detector", "case_id", "column", "family"]
    primary.groupby(case_groups)[summary_cols].mean().reset_index().to_csv(args.out / "case_metrics.csv", index=False)
    mechanism_groups = ["dataset", "pilot_seed", "scheme", "baseline", "budget", "detector", "case_id", "rate", "mechanism_class"]
    matched = primary[primary["set"] == "test_diverse"].groupby(mechanism_groups).utility.mean().reset_index()
    # Retain paired split/period results while keeping individual committed artifacts small.
    for (dataset, scheme), f in matched.groupby(["dataset", "scheme"]):
        f.to_csv(args.out / f"matched_mechanisms_{dataset}_{scheme}.csv", index=False)
    decisions = []
    for (dataset, seed, scheme, baseline, budget), frame in data.groupby(["dataset", "pilot_seed", "scheme", "baseline", "budget"]):
        frame = frame[(frame.role == "primary") & frame.detector.isin(cfg["primary_detectors"])]
        for strategy in ("simple", "diverse"):
            train = frame[frame["set"] == f"sel_{strategy}"]
            common = {"dataset": dataset, "seed": seed, "scheme": scheme, "baseline": baseline,
                      "budget": budget, "strategy": strategy}
            for name in ("simple", "diverse", "heldout"):
                target = frame[frame["set"] == f"test_{name}"]
                decisions += assess(train, target, cfg["robust"], {**common, "condition": f"test_{name}"})
            target = frame[(frame["set"] == "test_heldout") & (frame.rate == .02)
                           & frame.mech_params.map(lambda s: json.loads(s).get("strength", 0) > 4)]
            decisions += assess(train[train.rate == .01], target, cfg["robust"], {**common, "condition": "rate_strength_shift"})
            for family in sorted(train.family.unique()):
                target = frame[(frame.partition == "test") & (frame.family == family)]
                decisions += assess(train[train.family != family], target, cfg["robust"],
                                    {**common, "condition": f"unseen_family:{family}"})
    # Leave an entire source out of selector training; target models still learn only target history.
    for (dataset, baseline, budget), target in data.groupby(["dataset", "baseline", "budget"]):
        target = target[(target["set"] == "test_heldout") & (target.role == "primary")
                        & target.detector.isin(cfg["primary_detectors"])]
        for strategy in ("simple", "diverse"):
            train = data[(data.dataset != dataset) & (data.baseline == baseline) & (data.budget == budget)
                         & (data["set"] == f"sel_{strategy}") & (data.role == "primary")
                         & data.detector.isin(cfg["primary_detectors"])]
            decisions += assess(train, target, cfg["robust"], {"dataset": dataset, "seed": 0, "scheme": "cross_source",
                                "baseline": baseline, "budget": budget, "strategy": strategy, "condition": "unseen_source"})
    decisions = pd.DataFrame(decisions)
    decisions.to_csv(args.out / "selection.csv", index=False)
    paired = decisions.pivot(index=["dataset", "seed", "scheme", "baseline", "budget", "strategy", "condition"],
                             columns="selector", values=["regret", "target_utility"])
    paired.columns = ["_".join(c) for c in paired.columns]
    paired["robust_minus_naive_regret"] = paired.regret_robust - paired.regret_naive
    paired.to_csv(args.out / "paired_selectors.csv")
    designs = decisions.pivot(index=["dataset", "seed", "scheme", "baseline", "budget", "selector", "condition"],
                              columns="strategy", values=["regret", "target_utility"])
    designs.columns = ["_".join(c) for c in designs.columns]
    designs["diverse_minus_simple_regret"] = designs.regret_diverse - designs.regret_simple
    designs.to_csv(args.out / "paired_designs.csv")
    decisions.groupby(["condition", "baseline", "budget", "strategy", "selector"]).agg(
        mean_regret=("regret", "mean"), agreement=("exact_agreement", "mean"), within_005=("within_005", "mean"),
        mean_utility=("target_utility", "mean"), no_addition=("choice", lambda s: (s == NO_ADDITION).mean()),
        insufficient_evidence=("decision", lambda s: (s == "INSUFFICIENT_EVIDENCE").mean()),
        mean_net_added_hits=("target_net_added_hits_per_scenario", "mean"),
        decisions=("choice", "size")).reset_index().to_csv(args.out / "selection_summary.csv", index=False)
    # Family-paired descriptive uncertainty: collapse seeds/rates/mechanisms first, do not count them as datasets.
    cases = primary[primary.budget == 25].groupby(["dataset", "baseline", "detector", "case_key", "family"]).utility.mean().reset_index()
    uncertainty = []
    for (dataset, baseline, detector), f in cases.groupby(["dataset", "baseline", "detector"]):
        values = f.utility.to_numpy()
        rng = np.random.default_rng(0)
        boot = values[rng.integers(0, len(values), (1000, len(values)))].mean(1)
        uncertainty.append({"dataset": dataset, "baseline": baseline, "detector": detector, "cases": len(values),
                            "mean": values.mean(), "conditional_case_ci_lo": np.quantile(boot, .025),
                            "conditional_case_ci_hi": np.quantile(boot, .975)})
    pd.DataFrame(uncertainty).to_csv(args.out / "case_uncertainty.csv", index=False)
    generate_plots(args.out, primary, decisions, curves)
    print(f"Analysed {len(runtime) // 4} runs, {raw.sid.nunique()} scenario IDs; {len(decisions)} selection decisions.")


def generate_plots(out, primary, decisions, curves):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure_dir = paths.ROOT / "docs/figures/thesis"
    figure_dir.mkdir(parents=True, exist_ok=True)
    p = primary[(primary.budget == 25) & (primary.baseline == "full")]
    table = p.groupby(["dataset", "detector", "case_key"]).utility.mean().groupby(["dataset", "detector"]).mean().unstack()
    ax = table.plot.bar(figsize=(9, 4), rot=0)
    ax.axhline(0, color="black", linewidth=.7)
    ax.set_ylabel("Recall difference at shared total budget 25 / 1k")
    ax.set_xlabel("")
    ax.figure.tight_layout()
    ax.figure.savefig(figure_dir / "shared_budget_gain.png", dpi=170)
    plt.close(ax.figure)
    p = decisions[(decisions.budget == 25) & (decisions.condition == "test_heldout")]
    regrets = p.groupby(["dataset", "baseline", "strategy", "selector"]).regret.mean()
    ax = regrets.groupby(["baseline", "strategy", "selector"]).mean().unstack().plot.bar(figsize=(9, 4), rot=25)
    ax.set_ylabel("Mean oracle regret")
    ax.set_xlabel("Baseline and simulation design")
    ax.figure.tight_layout()
    ax.figure.savefig(figure_dir / "selection_regret.png", dpi=170)
    plt.close(ax.figure)
    fig, axes = plt.subplots(1, 3, figsize=(12, 3.5), sharey=True)
    for ax, (dataset, f) in zip(axes, curves.groupby("dataset"), strict=True):
        for detector, d in f.groupby("detector"):
            pr = d.groupby("recall").precision.mean()
            ax.plot(pr.index, pr, label=detector)
        ax.set_title(dataset)
        ax.set_xlabel("Recall on scored scope")
    axes[0].set_ylabel("Interpolated precision vs injection labels")
    axes[-1].legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(figure_dir / "pr_curves.png", dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    main()
