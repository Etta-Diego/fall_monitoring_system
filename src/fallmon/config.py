"""Load and validate config/default.yaml with pydantic.

Every tunable value in the system comes from here (PRD Section 17).
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "default.yaml"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class AccSensor(_Strict):
    range_g: float = Field(gt=0)
    bits: int = Field(gt=0)


class GyroSensor(_Strict):
    range_dps: float = Field(gt=0)
    bits: int = Field(gt=0)


class Sensors(_Strict):
    adxl345: AccSensor
    itg3200: GyroSensor


class DatasetConfig(_Strict):
    raw_dir: Path
    processed_dir: Path
    splits_path: Path
    fs_raw: int = Field(gt=0)
    sensors: Sensors


class ActivitiesConfig(_Strict):
    known_adls: list[str]
    unknown_adls: list[str]
    falls: list[str]

    @model_validator(mode="after")
    def _groups_disjoint(self) -> ActivitiesConfig:
        groups = [set(self.known_adls), set(self.unknown_adls), set(self.falls)]
        total = sum(len(g) for g in groups)
        if len(set().union(*groups)) != total:
            raise ValueError("activity groups must not overlap")
        return self

    def group_of(self, code: str) -> str:
        """Return 'known_adl' | 'unknown_adl' | 'fall' for an activity code."""
        if code in self.known_adls:
            return "known_adl"
        if code in self.unknown_adls:
            return "unknown_adl"
        if code in self.falls:
            return "fall"
        raise KeyError(f"activity code {code!r} is not in any configured group")


class PartitionSizes(_Strict):
    train: int = Field(ge=0)
    val: int = Field(ge=0)
    test: int = Field(ge=0)


class SplitConfig(_Strict):
    young: PartitionSizes
    elderly: PartitionSizes
    force_test: list[str] = []


class PreprocessingConfig(_Strict):
    lowpass_hz: float = Field(gt=0)
    filter_order: int = Field(gt=0)
    target_fs: int = Field(gt=0)
    offline_zero_phase: bool
    channels: list[str]


class DTEConfig(_Strict):
    window_lengths_s: list[float]
    train_stride_s: float = Field(gt=0)
    max_windows_per_trial: int = Field(gt=0)
    batch_size: int = Field(gt=0)
    lr: float = Field(gt=0)
    weight_decay: float = Field(ge=0)
    epochs: int = Field(gt=0)
    patience: int = Field(gt=0)
    dropout: float = Field(ge=0, lt=1)


class OODConfig(_Strict):
    threshold: float = Field(gt=0, lt=1)


class StreamConfig(_Strict):
    decision_stride_s: float = Field(gt=0)
    default_speed: float = Field(gt=0)


class EventsConfig(_Strict):
    merge_gap_s: float = Field(gt=0)
    cooldown_s: float = Field(ge=0)


CombineMode = Literal["impact_and_any", "impact_and_k_of_3", "all"]


class VerifierThresholds(_Strict):
    impact_g: float
    orient_deg: float
    still_std_g: float
    rest_s: float


class VerifierGrid(_Strict):
    impact_g: list[float]
    orient_deg: list[float]
    still_std_g: list[float]
    rest_s: list[float]
    combine: list[CombineMode]
    k: list[int]
    post_window_s: list[float]


class VerifierConfig(_Strict):
    impact_search_pre_s: float = Field(ge=0)
    impact_search_post_s: float = Field(ge=0)
    post_window_s: float = Field(gt=0)
    pre_interval_s: tuple[float, float]
    post_interval_start_s: float = Field(ge=0)
    still_std_g: float = Field(gt=0)
    combine: CombineMode
    k: int = Field(ge=1, le=3)
    thresholds: VerifierThresholds
    min_fall_recall: float = Field(gt=0, le=1)
    grid: VerifierGrid


class LoggingConfig(_Strict):
    db_path: Path
    activity_log_interval_s: float = Field(gt=0)


class NotifierConfig(_Strict):
    channels: list[Literal["console", "email", "telegram"]]
    enabled_in_eval: bool


class EvaluationConfig(_Strict):
    bootstrap_resamples: int = Field(gt=0)
    sweep_post_window_s: list[float]


class Config(_Strict):
    seed: int
    dataset: DatasetConfig
    activities: ActivitiesConfig
    split: SplitConfig
    preprocessing: PreprocessingConfig
    dte: DTEConfig
    ood: OODConfig
    stream: StreamConfig
    events: EventsConfig
    verifier: VerifierConfig
    logging: LoggingConfig
    notifier: NotifierConfig
    evaluation: EvaluationConfig

    @model_validator(mode="after")
    def _decimation_is_integer(self) -> Config:
        if self.dataset.fs_raw % self.preprocessing.target_fs != 0:
            raise ValueError("fs_raw must be an integer multiple of target_fs")
        return self

    @property
    def decimation_factor(self) -> int:
        return self.dataset.fs_raw // self.preprocessing.target_fs


def load_config(path: str | Path | None = None) -> Config:
    """Read a YAML config file and return a validated, immutable Config."""
    path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return Config.model_validate(raw)
