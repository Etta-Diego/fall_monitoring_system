"""Leakage guards and test lock (PRD Section 11)."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

FROZEN_CONFIG = Path("results/frozen_config.yaml")
FROZEN_HASH = Path("results/frozen_config.sha256")


class LeakageError(AssertionError):
    """Raised when a data-leakage rule is broken. Never catch and ignore this."""


def assert_no_subject_overlap(splits: dict) -> None:
    """Guard 1: every subject appears in exactly one of train / val / test."""
    seen: dict[str, str] = {}
    for part in ("train", "val", "test"):
        for subject in splits[part]:
            if subject in seen:
                raise LeakageError(f"subject {subject} is in both {seen[subject]} and {part}")
            seen[subject] = part


def assert_no_unknown_in_training(train_windows_index, splits: dict, known_adls: list[str]) -> None:
    """Guard 2: training windows come only from known ADLs of train-split subjects.

    `train_windows_index` has one row per training window with `activity_code` and `subject_id`.
    """
    bad_codes = set(train_windows_index["activity_code"]) - set(known_adls)
    if bad_codes:
        raise LeakageError(f"training windows contain non-known-ADL activities: {sorted(bad_codes)}")
    bad_subjects = set(train_windows_index["subject_id"]) - set(splits["train"])
    if bad_subjects:
        raise LeakageError(f"training windows contain subjects outside the train split: {sorted(bad_subjects)}")


def assert_scaler_fit_on_train(scaler_meta: dict, splits: dict) -> None:
    """Guard 3: the normalisation scaler was fitted on train-split subjects only."""
    fit_subjects = set(scaler_meta["fit_subjects"])
    if not fit_subjects:
        raise LeakageError("scaler metadata lists no fit subjects")
    outside = fit_subjects - set(splits["train"])
    if outside:
        raise LeakageError(f"scaler was fitted on subjects outside the train split: {sorted(outside)}")


class TestLockError(RuntimeError):
    """Raised when test-split data is requested before the test split is unlocked (PRD 11.5)."""


def assert_not_test(subject_ids, splits: dict, context: str) -> None:
    """Refuse to touch test-split subjects. The frozen-config unlock for Phase 6 is added in Phase 5."""
    locked = sorted(set(subject_ids) & set(splits["test"]))
    if locked:
        raise TestLockError(
            f"{context}: subjects {locked} are in the test split, which is locked until Phase 6 "
            "(run `fallmon freeze` first; see PRD Section 11)."
        )


def assert_verifier_tuned_without_test_or_unknown(tuning_index, splits: dict) -> None:
    """Guard 4: verifier tuning used validation-split known ADLs and falls only."""
    bad_groups = set(tuning_index["activity_group"]) - {"known_adl", "fall"}
    if bad_groups:
        raise LeakageError(f"verifier tuning data contains {sorted(bad_groups)}")
    outside = set(tuning_index["subject_id"]) - set(splits["val"])
    if outside:
        raise LeakageError(f"verifier tuning data contains non-validation subjects: {sorted(outside)}")


# ----- test lock: freeze config + models before the test split is opened (PRD 11.5) ------------

def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalise(obj):
    return json.loads(json.dumps(obj, sort_keys=True, default=str))


def freeze_payload(cfg, model_dir: Path = Path("models")) -> dict:
    """Everything that determines test results: merged config, verifier parameters, and file hashes."""
    verifier_path = model_dir / "verifier_config.json"
    if not verifier_path.exists():
        raise FileNotFoundError(f"{verifier_path} missing: run `fallmon tune-verifier` before freezing")
    files = sorted(model_dir.glob("dte_w*.pt")) + [model_dir / "dte_meta.json", model_dir / "scaler.json",
                                                   verifier_path, Path(cfg.dataset.splits_path)]
    missing = [str(f) for f in files if not f.exists()]
    if missing:
        raise FileNotFoundError(f"cannot freeze, missing files: {missing}")
    return _normalise({
        "config": cfg.model_dump(mode="json"),
        "verifier_params": json.loads(verifier_path.read_text())["params"],
        "files_sha256": {str(f): _sha256(f) for f in files},
    })


def write_freeze(cfg, git_hash: str, force: bool = False, model_dir: Path = Path("models"),
                 frozen_config: Path = FROZEN_CONFIG, frozen_hash: Path = FROZEN_HASH) -> str:
    """Write the frozen config (YAML) and its SHA-256. Returns the hash."""
    if frozen_config.exists() and not force:
        raise FileExistsError(f"{frozen_config} already exists; pass --force to re-freeze")
    doc = {"frozen_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "git_hash": git_hash,
           "data_source": "SisFall dataset replay (simulated IoT stream)", **freeze_payload(cfg, model_dir)}
    text = yaml.safe_dump(doc, sort_keys=True)
    frozen_config.parent.mkdir(parents=True, exist_ok=True)
    frozen_config.write_text(text)
    digest = hashlib.sha256(text.encode()).hexdigest()
    frozen_hash.write_text(f"{digest}  {frozen_config.name}\n")
    return digest


def check_frozen(cfg, model_dir: Path = Path("models"), frozen_config: Path = FROZEN_CONFIG,
                 frozen_hash: Path = FROZEN_HASH) -> str:
    """Unlock check for the test split: the frozen file exists, is untampered, and matches the current
    config and model files. Returns the frozen hash; raises TestLockError otherwise."""
    if not frozen_config.exists() or not frozen_hash.exists():
        raise TestLockError(f"{frozen_config} not found: run `fallmon freeze` first (PRD 11.5)")
    text = frozen_config.read_text()
    digest = hashlib.sha256(text.encode()).hexdigest()
    recorded = frozen_hash.read_text().split()[0]
    if digest != recorded:
        raise TestLockError(f"{frozen_config} does not match {frozen_hash}: the frozen file was edited")
    frozen = yaml.safe_load(text)
    current = freeze_payload(cfg, model_dir)
    problems = [k for k in ("config", "verifier_params") if _normalise(frozen.get(k)) != current[k]]
    problems += [f"file {f}" for f in sorted(set(frozen.get("files_sha256", {})) | set(current["files_sha256"]))
                 if frozen.get("files_sha256", {}).get(f) != current["files_sha256"].get(f)]
    if problems:
        raise TestLockError("current setup differs from the frozen one (" + ", ".join(problems) +
                            "). Re-freezing after looking at test results is not allowed.")
    return digest
