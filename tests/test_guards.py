import pytest

from fallmon.guards import LeakageError, assert_no_subject_overlap


def test_overlap_detected():
    with pytest.raises(LeakageError):
        assert_no_subject_overlap({"train": ["SA01", "SA02"], "val": ["SA03"], "test": ["SA02"]})


def test_disjoint_passes():
    assert_no_subject_overlap({"train": ["SA01"], "val": ["SA02"], "test": ["SE06"]})


def test_test_lock():
    from fallmon.guards import TestLockError, assert_not_test

    splits = {"train": ["SA01"], "val": ["SA02"], "test": ["SE06"]}
    assert_not_test(["SA01", "SA02"], splits, "x")
    with pytest.raises(TestLockError):
        assert_not_test(["SA01", "SE06"], splits, "x")


def test_guard4_verifier_tuning_data():
    import pandas as pd

    from fallmon.guards import assert_verifier_tuned_without_test_or_unknown

    splits = {"train": ["SA01"], "val": ["SA02", "SE05"], "test": ["SE06"]}
    ok = pd.DataFrame({"subject_id": ["SA02", "SE05"], "activity_group": ["known_adl", "fall"]})
    assert_verifier_tuned_without_test_or_unknown(ok, splits)
    for bad in (pd.DataFrame({"subject_id": ["SA02"], "activity_group": ["unknown_adl"]}),
                pd.DataFrame({"subject_id": ["SE06"], "activity_group": ["fall"]}),
                pd.DataFrame({"subject_id": ["SA01"], "activity_group": ["known_adl"]})):
        with pytest.raises(LeakageError):
            assert_verifier_tuned_without_test_or_unknown(bad, splits)


def _freeze_setup(tmp_path, cfg):
    models = tmp_path / "models"
    models.mkdir()
    for name in ("dte_w1.0s.pt", "dte_meta.json", "scaler.json"):
        (models / name).write_text(name)
    (models / "verifier_config.json").write_text('{"params": {"impact_g": 3.0}}')
    splits = tmp_path / "splits.json"
    splits.write_text("{}")
    cfg = cfg.model_copy(update={"dataset": cfg.dataset.model_copy(update={"splits_path": splits})})
    paths = dict(model_dir=models, frozen_config=tmp_path / "frozen.yaml", frozen_hash=tmp_path / "frozen.sha256")
    return cfg, models, paths


def test_freeze_then_check_passes(tmp_path, cfg):
    from fallmon.guards import check_frozen, write_freeze

    cfg, _, paths = _freeze_setup(tmp_path, cfg)
    digest = write_freeze(cfg, "abc", **paths)
    assert check_frozen(cfg, **paths) == digest
    with pytest.raises(FileExistsError):
        write_freeze(cfg, "abc", **paths)


def test_check_fails_without_freeze_or_after_changes(tmp_path, cfg):
    from fallmon.guards import TestLockError, check_frozen, write_freeze

    cfg, models, paths = _freeze_setup(tmp_path, cfg)
    with pytest.raises(TestLockError):
        check_frozen(cfg, **paths)
    write_freeze(cfg, "abc", **paths)
    changed_cfg = cfg.model_copy(update={"ood": cfg.ood.model_copy(update={"threshold": 0.8})})
    with pytest.raises(TestLockError, match="config"):
        check_frozen(changed_cfg, **paths)
    (models / "dte_w1.0s.pt").write_text("retrained")
    with pytest.raises(TestLockError, match="dte_w1.0s.pt"):
        check_frozen(cfg, **paths)


def test_check_fails_if_frozen_file_edited(tmp_path, cfg):
    from fallmon.guards import TestLockError, check_frozen, write_freeze

    cfg, _, paths = _freeze_setup(tmp_path, cfg)
    write_freeze(cfg, "abc", **paths)
    paths["frozen_config"].write_text(paths["frozen_config"].read_text() + "\n# edited\n")
    with pytest.raises(TestLockError, match="edited"):
        check_frozen(cfg, **paths)
