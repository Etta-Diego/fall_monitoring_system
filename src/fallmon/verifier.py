"""Post-event temporal verification: the contribution of this thesis (PRD Section 9).

When an OOD event opens, the proposed system holds the alert, finds the impact, waits for the
post-impact window, and checks physical evidence of a fall in unnormalised signals (g, deg/s):
a hard impact, plus a change of body orientation and/or stillness afterwards.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from fallmon.config import Config
from fallmon.preprocessing import ALL_CHANNELS

ACC = [ALL_CHANNELS.index(c) for c in ("ax", "ay", "az")]
AM, GM = ALL_CHANNELS.index("Am"), ALL_CHANNELS.index("Gm")
SUPPORT_RULES = ("R_orient", "R_still", "R_rest")
# Simplest first; used to break ties during tuning (PRD 9.5).
COMBINE_SIMPLICITY = ("all", "impact_and_any", "impact_and_k_of_3")


@dataclass(frozen=True)
class VerifierParams:
    impact_g: float
    orient_deg: float
    still_std_g: float  # T_still: threshold on post_am_std_g
    rest_s: float
    combine: str
    k: int
    post_window_s: float
    rearm_after_reject: bool

    @classmethod
    def from_config(cls, cfg: Config) -> VerifierParams:
        v = cfg.verifier
        return cls(v.thresholds.impact_g, v.thresholds.orient_deg, v.thresholds.still_std_g, v.thresholds.rest_s,
                   v.combine, v.k, v.post_window_s, v.rearm_after_reject)

    def save(self, path: str | Path, extra: dict | None = None) -> None:
        Path(path).write_text(json.dumps({"params": asdict(self), **(extra or {})}, indent=2) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> VerifierParams:
        return cls(**json.loads(Path(path).read_text())["params"])


@dataclass
class VerificationResult:
    verified: bool
    features: dict[str, float]
    rules: dict[str, bool]
    t_impact: float
    truncated: bool
    reason: str


def _sl(t0_s: float, t1_s: float, fs: int, n: int) -> slice:
    """Sample slice for the time interval [t0, t1] (seconds), clipped to the available data."""
    a = max(0, int(round(t0_s * fs)))
    b = min(n, int(round(t1_s * fs)) + 1)
    return slice(a, max(a, b))


def localise_impact(phys: np.ndarray, t_event_s: float, cfg: Config) -> int:
    """Index of max Am in [t_event - impact_search_pre_s, t_event + impact_search_post_s] (PRD 9.2)."""
    v, fs = cfg.verifier, cfg.preprocessing.target_fs
    s = _sl(t_event_s - v.impact_search_pre_s, t_event_s + v.impact_search_post_s, fs, len(phys))
    return s.start + int(np.argmax(phys[s, AM]))


def _longest_run(mask: np.ndarray) -> int:
    best = cur = 0
    for m in mask:
        cur = cur + 1 if m else 0
        best = max(best, cur)
    return best


def compute_features(phys: np.ndarray, i_impact: int, post_window_s: float, cfg: Config) -> tuple[dict, dict]:
    """PRD 9.3 features around the impact, using only the samples in `phys`.

    Returns (features, flags). Features are NaN when their interval has no data.
    """
    v, fs, n = cfg.verifier, cfg.preprocessing.target_fs, len(phys)
    ti = i_impact / fs
    half = v.impact_window_s / 2
    imp = _sl(ti - half, ti + half, fs, n)
    pre = _sl(ti + v.pre_interval_s[0], ti + v.pre_interval_s[1], fs, n)
    post = _sl(ti + v.post_interval_start_s, ti + post_window_s, fs, n)

    feats = {
        "impact_peak_g": float(phys[imp, AM].max()),
        "gyro_peak_dps": float(phys[imp, GM].max()),
        "orientation_change_deg": float("nan"),
        "post_am_std_g": float("nan"),
        "post_gm_mean_dps": float("nan"),
        "low_activity_s": float("nan"),
    }
    n_post = post.stop - post.start
    if pre.stop > pre.start and n_post > 0:
        a, b = phys[pre, :][:, ACC].mean(axis=0), phys[post, :][:, ACC].mean(axis=0)
        cos = np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
        feats["orientation_change_deg"] = float(np.degrees(np.arccos(np.clip(cos, -1.0, 1.0))))
    if n_post >= 2:
        am_post = phys[post, AM]
        feats["post_am_std_g"] = float(am_post.std())
        feats["post_gm_mean_dps"] = float(phys[post, GM].mean())
        # Rolling std of Am over a trailing window, evaluated at each post-interval sample.
        w = max(2, int(round(v.rolling_std_s * fs)))
        still = np.array([phys[max(0, i - w + 1): i + 1, AM].std() < v.still_std_g for i in range(post.start, post.stop)])
        feats["low_activity_s"] = _longest_run(still) / fs
    flags = {
        "pre_truncated": pre.start == 0 and int(round((ti + v.pre_interval_s[0]) * fs)) < 0,
        "post_samples": int(n_post),
    }
    return feats, flags


def apply_rules(feats: dict, p: VerifierParams) -> tuple[bool, dict[str, bool]]:
    """PRD 9.4. A rule whose feature is NaN (no data) is false."""
    rules = {
        "R_impact": bool(feats["impact_peak_g"] >= p.impact_g),
        "R_orient": bool(feats["orientation_change_deg"] >= p.orient_deg),
        "R_still": bool(feats["post_am_std_g"] <= p.still_std_g),
        "R_rest": bool(feats["low_activity_s"] >= p.rest_s),
    }
    support = sum(rules[r] for r in SUPPORT_RULES)
    if p.combine == "impact_and_any":
        verified = rules["R_impact"] and support >= 1
    elif p.combine == "impact_and_k_of_3":
        verified = rules["R_impact"] and support >= p.k
    elif p.combine == "all":
        verified = all(rules.values())
    else:
        raise ValueError(f"unknown combine mode {p.combine!r}")
    return verified, rules


def explain(feats: dict, rules: dict, p: VerifierParams, verified: bool, truncated: bool) -> str:
    """Human-readable reason, e.g. 'impact 3.10 g >= 2.50 g; orientation 74 deg < 45 deg ... -> VERIFIED'."""
    def part(name, val, unit, op, thr, ok):
        sym = op if ok else {">=": "<", "<=": ">"}[op]
        return f"{name} {val:.2f} {unit} {sym} {thr:g} {unit}" if not np.isnan(val) else f"{name} n/a"

    parts = [
        part("impact", feats["impact_peak_g"], "g", ">=", p.impact_g, rules["R_impact"]),
        part("orientation change", feats["orientation_change_deg"], "deg", ">=", p.orient_deg, rules["R_orient"]),
        part("post std", feats["post_am_std_g"], "g", "<=", p.still_std_g, rules["R_still"]),
        part("low activity", feats["low_activity_s"], "s", ">=", p.rest_s, rules["R_rest"]),
    ]
    tail = f" [{p.combine}{', k=' + str(p.k) if p.combine == 'impact_and_k_of_3' else ''}]"
    trunc = " (trial ended early: truncated)" if truncated else ""
    return "; ".join(parts) + tail + trunc + (" -> VERIFIED" if verified else " -> REJECTED")


def verify(phys: np.ndarray, i_impact: int, p: VerifierParams, cfg: Config, truncated: bool,
           feats: dict | None = None) -> VerificationResult:
    """Decide one event. `feats` may be passed in when already computed (tuning cache)."""
    if feats is None:
        feats, _ = compute_features(phys, i_impact, p.post_window_s, cfg)
    verified, rules = apply_rules(feats, p)
    return VerificationResult(verified, feats, rules, i_impact / cfg.preprocessing.target_fs, truncated,
                              explain(feats, rules, p, verified, truncated))


def load_params(cfg: Config, path: str | Path = "models/verifier_config.json") -> VerifierParams:
    """Tuned parameters if `fallmon tune-verifier` has run, else the config starting values."""
    return VerifierParams.load(path) if Path(path).exists() else VerifierParams.from_config(cfg)
