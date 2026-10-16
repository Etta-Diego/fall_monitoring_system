import pytest
import yaml
from pydantic import ValidationError

from fallmon.config import DEFAULT_CONFIG_PATH, Config, load_config


def test_default_config_loads():
    cfg = load_config()
    assert cfg.decimation_factor == 4
    assert cfg.activities.group_of("D10") == "unknown_adl"
    assert cfg.activities.group_of("F05") == "fall"


def _raw():
    with open(DEFAULT_CONFIG_PATH) as f:
        return yaml.safe_load(f)


def test_overlapping_activity_groups_rejected():
    raw = _raw()
    raw["activities"]["unknown_adls"].append("D01")
    with pytest.raises(ValidationError):
        Config.model_validate(raw)


def test_unknown_key_rejected():
    raw = _raw()
    raw["ood"]["thresh"] = 0.5
    with pytest.raises(ValidationError):
        Config.model_validate(raw)
