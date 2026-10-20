"""Evaluate completed dirty-only service scans against published pairs, without injection.

The scan phase cannot read clean.csv. Contracts, dirty entity groups, model parameters and review
ordering are frozen before scoring. The evaluator never fits a model or a threshold.
"""

from __future__ import annotations

import hashlib
import json
import time
import unicodedata
from pathlib import Path

import pandas as pd
import yaml

from dq_framework import paths
from dq_framework.acquisition import load_registry, sha256_file, verify
from dq_framework.contracts import load_contract
from dq_framework.datasets import load_contract_table, load_pair, load_raw_table
from dq_framework.service.partitioning import grouped_partitions
from dq_framework.service.review import review_order


def scan_config(protocol, dataset, seed):
    contract = load_contract(dataset)
    detectors = dict(protocol["detectors"])
    if contract.numeric_columns:
        detectors.update(protocol["numeric_detectors"])
    selection = {"select": "group_split", "seed": seed,
                 "history_fraction": protocol["history_fraction"],
                 "group_columns": protocol["datasets"][dataset]["group_columns"]}
    return {"name": f"published_{dataset}_{seed}", "dataset": dataset,
            "history": {**selection, "partition": "history"}, "batch": {**selection, "partition": "batch"},
            "exclude_research_holdout": False,  # group_split reserves and expands the seed-1 holdout itself
            "research_scope": "design_pool_only", "baseline": "full", "evidence": None,
            "budget_per_1k": protocol["primary_budget_per_1k"], "review_seed": protocol["review_seed"],
            "detectors": detectors, "continue_on_detector_error": True}


def fingerprints(protocol_path):
    """Configuration/code fingerprint, excluding reports, tests and generated runtime files."""
    files = [protocol_path, paths.CONFIG_DIR / "datasets.yaml", paths.ROOT / "uv.lock"]
    for folder in (paths.ROOT / "src/dq_framework", paths.CONFIG_DIR / "contracts", paths.DBT_DIR):
        files += [p for p in folder.rglob("*") if p.is_file() and p.suffix in (".py", ".sql", ".yml", ".yaml")
                  and not {"target", "logs", "__pycache__", "dbt_packages"}.intersection(p.parts)]
    return {str(p.relative_to(paths.ROOT)): sha256_file(p) for p in sorted(set(files))}


def run_scans(protocol_path: Path, work: Path):
    from dq_framework.service.scan import run_scan

    protocol = yaml.safe_load(protocol_path.read_text())
    if protocol["scope"] != "design_pool_only" or protocol["label_policy"] != "conservative_v1":
        raise ValueError("Only the frozen exploratory design-pool protocol is implemented")
    work.mkdir(parents=True, exist_ok=True)
    (work / "completed_scans.json").unlink(missing_ok=True)
    registry = load_registry()
    plan = {"protocol": protocol, "fingerprints": fingerprints(protocol_path), "jobs": [], "dirty_sha256": {}}
    for dataset, settings in protocol["datasets"].items():
        contract = load_contract(dataset)
        raw = load_raw_table(registry[dataset])  # dirty.csv only
        typed = load_contract_table(dataset, contract)
        plan["dirty_sha256"][dataset] = sha256_file(registry[dataset].raw_dir / registry[dataset].raw["table"]["file"])
        for seed in protocol["seeds"]:
            part = grouped_partitions(raw, typed, contract, settings["group_columns"], seed,
                                      protocol["history_fraction"])
            job = {"dataset": dataset, "seed": seed, "directory": f"{dataset}_{seed}",
                   "partitions": part["partition"].value_counts().to_dict(),
                   "groups": part.groupby("partition")["group"].nunique().to_dict()}
            plan["jobs"].append(job)
            folder = work / job["directory"]
            folder.mkdir(parents=True, exist_ok=True)
            part.to_csv(folder / "partitions.csv", index=False)
            (folder / "scan.yaml").write_text(yaml.safe_dump(scan_config(protocol, dataset, seed), sort_keys=False))
    frozen = json.dumps(plan, sort_keys=True)
    plan["plan_sha256"] = hashlib.sha256(frozen.encode()).hexdigest()
    (work / "frozen_plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    # All configuration and partitions now exist before the first scan or reference access.
    for job in plan["jobs"]:
        folder = work / job["directory"]
        t0 = time.perf_counter()
        run_scan(folder / "scan.yaml", folder)
        job["output_sha256"] = {name: sha256_file(folder / name) for name in (
            "scan.yaml", "partitions.csv", "control_cells.parquet", "detector_scores.parquet", "scan_summary.json", "findings.csv")}
        print(f"SCANNED {job['dataset']} seed={job['seed']} {time.perf_counter() - t0:.1f}s", flush=True)
    (work / "completed_scans.json").write_text(json.dumps(plan, indent=2) + "\n")
    return plan


def label_cells(dataset, dirty, clean, contract):
    """Conservative evaluator-only taxonomy; a changed string is not automatically a proven error."""
    if dirty.shape != clean.shape or list(dirty) != list(clean):
        raise ValueError("Published pair is not row/column aligned")
    ids = dirty[contract.row_id].astype(int) if contract.row_id else pd.Series(dirty.index + 1, index=dirty.index)
    numeric = set(contract.numeric_columns)
    rows = []
    for col in contract.columns:
        for rid, a, b in zip(ids, dirty[col.name], clean[col.name], strict=True):
            if a == b:
                label = "reference_missing" if b in col.missing_tokens else "agreement"
            elif b in col.missing_tokens or (dataset == "raha_rayyan" and b == "-1"):
                label = "uncertain"
            elif _same_representation(a, b, col.name in numeric):
                label = "formatting"
            elif dataset == "raha_rayyan":
                label = "uncertain"  # no independent adjudication of owner repairs or date permutations
            elif a in col.missing_tokens:
                label = "missing"
            else:
                label = "value_candidate"
            rows.append({"_row_id": int(rid), "column": col.name, "label": label, "changed": a != b})
    return pd.DataFrame(rows)


def _same_representation(a, b, numeric):
    if numeric:
        from decimal import Decimal, InvalidOperation

        try:
            x, y = Decimal(a), Decimal(b)
            if x.is_finite() and y.is_finite() and x == y:
                return True
        except InvalidOperation:
            pass
    return " ".join(unicodedata.normalize("NFC", a).split()) == " ".join(unicodedata.normalize("NFC", b).split())


def keys(frame):
    return set(zip(frame["_row_id"].astype(int), frame["column"], strict=True))


def selection_metrics(selected, labels):
    chosen = keys(selected) & keys(labels)
    categories = {label: keys(g) for label, g in labels.groupby("label")}
    errors = categories.get("missing", set()) | categories.get("value_candidate", set())
    uncertain = categories.get("uncertain", set()) | categories.get("reference_missing", set())
    changed = keys(labels[labels["changed"]])
    known_reviewed = len(chosen - uncertain)
    hits = len(chosen & errors)
    return {"reviews": len(chosen), "reference_error_labels": len(errors), "reference_error_hits": hits,
            "reference_error_recall": hits / len(errors) if errors else None,
            "reference_error_precision": hits / known_reviewed if known_reviewed and errors else None,
            "raw_difference_recall": len(chosen & changed) / len(changed) if changed else None,
            "uncertain_reviews": len(chosen & uncertain),
            **{f"reviews_{label}": len(chosen & categories.get(label, set()))
               for label in ("missing", "value_candidate", "formatting", "uncertain", "reference_missing", "agreement")}}


def evaluate_scans(protocol_path: Path, work: Path, output: Path):
    plan = json.loads((work / "completed_scans.json").read_text())
    if fingerprints(protocol_path) != plan["fingerprints"]:
        raise ValueError("Configuration/code changed since the dirty-only scans; rerun scans before evaluation")
    frozen = json.loads((work / "frozen_plan.json").read_text())
    expected = frozen.pop("plan_sha256")
    if hashlib.sha256(json.dumps(frozen, sort_keys=True).encode()).hexdigest() != expected:
        raise ValueError("Frozen plan changed")
    completed = {**plan, "jobs": [{k: v for k, v in j.items() if k != "output_sha256"} for j in plan["jobs"]]}
    completed.pop("plan_sha256")
    if frozen != completed:
        raise ValueError("Completed scans do not match the frozen plan")
    for job in plan["jobs"]:
        for name, sha in job["output_sha256"].items():
            if sha256_file(work / job["directory"] / name) != sha:
                raise ValueError(f"Scan artifact changed: {job['directory']}/{name}")
    registry = load_registry()
    output.mkdir(parents=True, exist_ok=True)
    metrics, compatibility, label_counts, service_checks = [], [], [], []
    labels_by_dataset = {}
    for dataset in plan["protocol"]["datasets"]:
        verification = verify(registry[dataset])
        if verification["status"] != "VERIFIED":
            raise ValueError(f"{dataset}: {verification}")
        # First reference values used in this workflow, after all nine scans have completed.
        dirty, clean = load_pair(registry[dataset])
        contract = load_contract(dataset)
        eligible = set()
        for job in plan["jobs"]:
            if job["dataset"] == dataset:
                parts = pd.read_csv(work / job["directory"] / "partitions.csv")
                eligible.update(parts.loc[parts["partition"] == "batch", "_row_id"])
        ids = dirty[contract.row_id].astype(int) if contract.row_id else pd.Series(dirty.index + 1)
        mask = ids.isin(eligible)
        labels_by_dataset[dataset] = label_cells(dataset, dirty[mask], clean[mask], contract)
    for job in plan["jobs"]:
        dataset, seed = job["dataset"], job["seed"]
        common = {"dataset": dataset, "seed": seed}
        folder = work / job["directory"]
        partitions = pd.read_csv(folder / "partitions.csv")
        batch_ids = set(partitions.loc[partitions["partition"] == "batch", "_row_id"])
        labels = labels_by_dataset[dataset]
        labels = labels[labels["_row_id"].isin(batch_ids)]
        for label, count in labels["label"].value_counts().items():
            label_counts.append({**common, "label": label, "cells": int(count), "batch_rows": len(batch_ids)})
        summary = json.loads((folder / "scan_summary.json").read_text())
        control = pd.read_parquet(folder / "control_cells.parquet")
        universe = keys(labels)
        control = control.loc[[k in universe for k in keys_in_order(control)]]
        scores = pd.read_parquet(folder / "detector_scores.parquet")
        methods = {"controls_deterministic": (control[control["tier"] == "deterministic"], False),
                   "controls_statistical": (control[control["tier"] == "statistical"], False),
                   "controls_full": (control, False)}
        for detector in summary["detectors"]:
            compatibility.append({**common, **{k: detector.get(k) for k in (
                "detector", "status", "compatibility", "seconds", "scored_cells", "finite_scores", "flags",
                "review_selected", "extra_flags_per_1k")},
                "reasons": json.dumps(detector.get("compatibility_reasons", [])),
                "warnings": json.dumps(detector.get("warnings", []))})
            if detector["status"] == "ok":
                methods[detector["detector"]] = (scores[scores["detector"] == detector["detector"]], detector["provides_scores"])
        if not load_contract(dataset).numeric_columns:
            for detector in plan["protocol"]["numeric_detectors"]:
                compatibility.append({**common, "detector": detector, "status": "not_applicable",
                                      "compatibility": "NO_NUMERIC_COLUMNS", "reasons":
                                      "Text-only contract: SD/IQR have no targets; inferred dBoost duplicates text mode."})
        for method, (cells, ranked) in methods.items():
            native = cells[cells["flag"]] if "flag" in cells else cells
            metrics.append({**common, "method": method, "mode": "native", "baseline": "none", "budget_per_1k": None,
                            "batch_rows": len(batch_ids), **selection_metrics(native, labels)})
            for budget in plan["protocol"]["budgets_per_1k"]:
                k = int(round(budget * len(batch_ids) / 1000))
                picked = review_order(cells, ranked=ranked, seed=plan["protocol"]["review_seed"]).head(k)
                metrics.append({**common, "method": method, "mode": "standalone", "baseline": "none",
                                "budget_per_1k": budget, "slots": k, "batch_rows": len(batch_ids),
                                **selection_metrics(picked, labels)})
                if method.startswith("controls_"):
                    continue
                for baseline in ("controls_deterministic", "controls_full"):
                    base = methods[baseline][0]
                    base_keys = keys(base)
                    available = cells.loc[[x not in base_keys for x in keys_in_order(cells)]]
                    extra = review_order(available, ranked=ranked, seed=plan["protocol"]["review_seed"]).head(k)
                    m = selection_metrics(extra, labels)
                    base_m = selection_metrics(base, labels)
                    union_m = selection_metrics(pd.concat([base, extra]), labels)
                    metrics.append({**common, "method": method, "mode": "additive", "baseline": baseline,
                                    "budget_per_1k": budget, "slots": k, "batch_rows": len(batch_ids), **m,
                                    "baseline_reviews": base_m["reviews"],
                                    "baseline_reference_error_recall": base_m["reference_error_recall"],
                                    "combined_reference_error_recall": union_m["reference_error_recall"]})
        findings = pd.read_csv(folder / "findings.csv", keep_default_na=False)
        service_checks.append({**common, "history_rows": summary["history"]["rows"], "batch_rows": len(batch_ids),
                               "holdout_rows": job["partitions"].get("holdout", 0),
                               "findings": len(findings), "explained_findings": int(findings["explanation"].ne("").sum()),
                               "rule_findings": int(findings["source"].str.startswith("rule:").sum()),
                               "detector_findings": int(findings["source"].str.startswith("detector:").sum()),
                               "dbt_tests": sum(summary["controls"]["tests"].values()),
                               "dbt_statuses": json.dumps(summary["controls"]["tests"]),
                               "recommendations": json.dumps(summary["recommendations"])})
    for name, records in (("metrics", metrics), ("compatibility", compatibility), ("label_counts", label_counts),
                          ("service_checks", service_checks)):
        pd.DataFrame(records).to_csv(output / f"{name}.csv", index=False)
    (output / "protocol.json").write_text(json.dumps(plan, indent=2) + "\n")
    print(f"EVALUATED {len(plan['jobs'])} dirty-only scans; summaries in {output}", flush=True)


def keys_in_order(frame):
    return list(zip(frame["_row_id"].astype(int), frame["column"], strict=True))
