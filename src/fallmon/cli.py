"""Command-line interface (PRD Section 16). Commands are added phase by phase."""

from __future__ import annotations

import logging

import typer

app = typer.Typer(
    help="Fall monitoring system. Data source: SisFall dataset replay (simulated IoT stream).",
    no_args_is_help=True,
)

ConfigOpt = typer.Option(None, "--config", help="Path to a YAML config file (default: config/default.yaml).")


@app.callback()
def main(verbose: bool = typer.Option(False, "--verbose", "-v")) -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(message)s")
    if verbose:
        logging.getLogger("fallmon").setLevel(logging.INFO)


@app.command("show-config")
def show_config(config: str = ConfigOpt) -> None:
    """Validate the config file and print it."""
    from fallmon.config import load_config

    typer.echo(load_config(config).model_dump_json(indent=2))


@app.command("prepare-data")
def prepare_data(
    config: str = ConfigOpt,
    force: bool = typer.Option(False, "--force", help="Regenerate data/splits.json even if it exists."),
) -> None:
    """Build the trial index, dataset summary, participant-level split and example plots."""
    from fallmon import splits as sp
    from fallmon.config import load_config
    from fallmon.data_loader import build_index, dataset_summary
    from fallmon.phase1_report import plot_examples, rest_check
    from fallmon.reporting import write_table

    cfg = load_config(config)
    index = build_index(cfg.dataset.raw_dir, cfg)
    cfg.dataset.processed_dir.mkdir(parents=True, exist_ok=True)
    index.to_parquet(cfg.dataset.processed_dir / "index.parquet", index=False)
    typer.echo(f"Indexed {len(index)} trial files from {len(index['subject_id'].unique())} subjects.")

    mismatched = index.loc[index["filename_subject_mismatch"], "path"].tolist()
    if mismatched:
        typer.echo(f"Note: {len(mismatched)} files have a subject in the name that differs from their folder; "
                   f"folder used (D-005): {', '.join(mismatched)}")

    summary = dataset_summary(index)
    write_table(summary, "dataset_summary", "Dataset summary",
                f"{len(index)} trial files. Subject taken from folder (decision D-005).")
    typer.echo("\n" + summary.to_string(index=False))

    if cfg.dataset.splits_path.exists() and not force:
        splits = sp.load_splits(cfg.dataset.splits_path)
        typer.echo(f"\nUsing existing {cfg.dataset.splits_path} (pass --force to regenerate).")
    else:
        splits = sp.make_splits(index, cfg)
        sp.save_splits(splits, cfg.dataset.splits_path, force=force)
        typer.echo(f"\nWrote {cfg.dataset.splits_path}. {splits['notes']}")

    split_table = sp.splits_summary(index, splits)
    write_table(split_table, "splits_summary", "Participant-level split",
                f"Seed {splits['seed']}. {splits['notes']}")
    typer.echo("\n" + split_table.to_string(index=False))

    rest = rest_check(index, splits, cfg)
    typer.echo(f"\nConversion check (Am, first 1 s of D07 standing, train subjects): "
               f"mean {rest['mean']:.3f} g, min {rest['min']:.3f} g, max {rest['max']:.3f} g over {rest['n']} trials")

    fig_path = plot_examples(index, splits, cfg)
    typer.echo(f"Saved {fig_path}")


@app.command("train")
def train(config: str = ConfigOpt) -> None:
    """Fit the scaler and train the three DTE models on train-split known ADLs (early stopping on val)."""
    import pandas as pd

    from fallmon.config import load_config
    from fallmon.splits import load_splits
    from fallmon.train import run_training

    logging.getLogger("fallmon").setLevel(logging.INFO)
    cfg = load_config(config)
    index = pd.read_parquet(cfg.dataset.processed_dir / "index.parquet")
    splits = load_splits(cfg.dataset.splits_path)
    meta = run_training(index, splits, cfg)

    vm = meta["val_metrics"]
    typer.echo("\nValidation results (development evidence, not final):")
    for row in vm["per_model"]:
        typer.echo(f"  {row['model']:<26} macro F1 {row['val_macro_f1']:.4f}")
    typer.echo(f"  Ensemble step accuracy     {vm['ensemble_step_accuracy']:.4f}")
    for k, v in vm["ood"].items():
        typer.echo(f"  {k:<40} {v:.4f}" if isinstance(v, float) else f"  {k:<40} {v}")
    typer.echo(f"Saved models to models/ in {meta['training_seconds']} s")


def _load_runtime(cfg):
    """Trained ensemble + scaler from models/."""
    from pathlib import Path

    from fallmon.dte import DeepTimeEnsemble
    from fallmon.preprocessing import Scaler

    ens, meta = DeepTimeEnsemble.load(Path("models"))
    return ens, Scaler.load(meta["scaler_path"])


@app.command("stream")
def stream(
    trial: str = typer.Option(..., "--trial", help="Trial id, e.g. F05_SA01_R01."),
    mode: str = typer.Option("baseline", "--mode", help="baseline | proposed | both"),
    speed: float = typer.Option(None, "--speed", help="Replay speed (1 = real time). Default: stream.default_speed."),
    realtime: bool = typer.Option(True, "--realtime/--fast", help="Pace to wall clock, or run as fast as possible."),
    config: str = ConfigOpt,
) -> None:
    """Replay one trial through the stream processor, print decisions and log to SQLite."""
    from pathlib import Path

    import pandas as pd

    from fallmon.config import load_config
    from fallmon.data_loader import load_trial
    from fallmon.guards import assert_not_test
    from fallmon.notifier import build_notifier
    from fallmon.pipeline import StreamProcessor, run_config
    from fallmon.reporting import DATA_SOURCE
    from fallmon.splits import load_splits
    from fallmon.storage import Storage
    from fallmon.stream_simulator import StreamSimulator
    from fallmon.verifier import load_params

    cfg = load_config(config)
    index = pd.read_parquet(cfg.dataset.processed_dir / "index.parquet").set_index("trial_id")
    if trial not in index.index:
        raise typer.BadParameter(f"unknown trial id {trial!r}")
    row = index.loc[trial]
    assert_not_test([row["subject_id"]], load_splits(cfg.dataset.splits_path), "stream")
    modes = ["baseline", "proposed"] if mode == "both" else [mode]

    ens, scaler = _load_runtime(cfg)
    storage = Storage(cfg.logging.db_path)
    notifier = build_notifier(cfg)
    params = load_params(cfg)
    procs = {m: StreamProcessor(m, cfg, ens, scaler, storage, notifier,
                                storage.start_run(m, "adhoc", run_config(cfg, params)), params=params) for m in modes}
    speed = speed or cfg.stream.default_speed
    typer.echo(f"Data source: {DATA_SOURCE}. No physical device.")
    typer.echo(f"Trial {trial} ({row['activity_group'].replace('_', ' ')}), mode {mode}, speed {speed}x")
    for m, p in procs.items():
        typer.echo(f"  run {m}: {p.run_id}")

    def show(m, d):
        if d.predicted_activity:
            flag = "OOD" if d.is_ood else "   "
            typer.echo(f"[{m:<8}] {d.t_s:6.2f} s  {d.predicted_activity:<10} conf {d.confidence:.3f} {flag} "
                       f"{d.status:<8} {d.latency_ms:6.2f} ms" + ("  <- ALERT" if d.new_alert else ""))
        else:
            typer.echo(f"[{m:<8}] {d.t_s:6.2f} s  end of trial: pending verification decided -> {d.status}")
        if d.verification is not None:
            typer.echo(f"[{m:<8}]          verification: {d.verification.reason}")

    sim = StreamSimulator([load_trial(Path(cfg.dataset.raw_dir) / row["path"], cfg)], speed=speed, realtime=realtime)
    for sample in sim:
        for m, p in procs.items():
            for d in p.push(sample):
                show(m, d)
    for m, p in procs.items():
        for d in p.finish():
            show(m, d)
    storage.close()
    typer.echo(f"Logged to {cfg.logging.db_path}")


@app.command("batch")
def batch(
    split: str = typer.Option("val", "--split", help="train | val (test is locked until Phase 6)"),
    mode: str = typer.Option("baseline", "--mode", help="baseline | proposed | both"),
    config: str = ConfigOpt,
) -> None:
    """Replay every known-ADL and fall trial of a split as fast as possible; report alert rates and latency."""
    from pathlib import Path

    import pandas as pd

    from fallmon.config import load_config
    from fallmon.data_loader import load_trial
    from fallmon.guards import assert_not_test
    from fallmon.notifier import build_notifier
    from fallmon.pipeline import StreamProcessor, run_batch, run_config, summarise_batch
    from fallmon.reporting import write_table
    from fallmon.splits import load_splits
    from fallmon.storage import Storage
    from fallmon.verifier import load_params

    cfg = load_config(config)
    splits = load_splits(cfg.dataset.splits_path)
    if split not in ("train", "val"):
        raise typer.BadParameter("only train or val before Phase 6")
    index = pd.read_parquet(cfg.dataset.processed_dir / "index.parquet")
    # Unknown ADLs are excluded everywhere except the final test evaluation (PRD 7.2).
    rows = index[index["subject_id"].isin(splits[split]) & index["activity_group"].isin(["known_adl", "fall"])]
    assert_not_test(rows["subject_id"], splits, "batch")
    modes = ["baseline", "proposed"] if mode == "both" else [mode]

    ens, scaler = _load_runtime(cfg)
    storage = Storage(cfg.logging.db_path)
    params = load_params(cfg)
    for m in modes:
        run_id = storage.start_run(m, split, run_config(cfg, params))
        notifier = build_notifier(cfg) if cfg.notifier.enabled_in_eval else None  # off by default (PRD 12.4)
        proc = StreamProcessor(m, cfg, ens, scaler, storage, notifier, run_id, params=params)
        trials = (load_trial(Path(cfg.dataset.raw_dir) / p, cfg) for p in rows["path"])
        decisions = run_batch(trials, proc)
        table, stats = summarise_batch(decisions, index)
        notes = (f"Run {run_id}. {split} split, known ADLs and falls only (unknown ADLs excluded). "
                 f"A trial counts as alerted if at least one ALERT was emitted. "
                 f"Step OOD rate known {stats['step_ood_rate_known_adl']:.4f}, fall {stats['step_ood_rate_fall']:.4f}. "
                 f"Latency per decision step: mean {stats['latency_ms_mean']:.2f} ms, "
                 f"p95 {stats['latency_ms_p95']:.2f} ms, max {stats['latency_ms_max']:.2f} ms "
                 f"over {stats['decision_steps']} steps.")
        write_table(table, f"phase3_batch_{split}_{m}", f"Batch replay, {m} mode ({split} split, development evidence)",
                    notes)
        typer.echo(f"\n[{m}] run {run_id}")
        typer.echo(table.to_string(index=False))
        for k, v in stats.items():
            typer.echo(f"  {k:<26} {v:.4f}" if isinstance(v, float) else f"  {k:<26} {v}")
    storage.close()


@app.command("tune-verifier")
def tune_verifier(
    workers: int = typer.Option(0, "--workers", help="Parallel processes (0 = up to 8)."),
    config: str = ConfigOpt,
) -> None:
    """Grid-search the verifier on validation known ADLs and falls only; save models/verifier_config.json."""
    import pandas as pd

    from fallmon.config import load_config
    from fallmon.splits import load_splits
    from fallmon.tune_verifier import run_tuning

    logging.getLogger("fallmon").setLevel(logging.INFO)
    cfg = load_config(config)
    index = pd.read_parquet(cfg.dataset.processed_dir / "index.parquet")
    ens, scaler = _load_runtime(cfg)
    out = run_tuning(index, load_splits(cfg.dataset.splits_path), ens, scaler, cfg, workers)
    typer.echo("\n" + out["selection_note"])
    typer.echo("Selected: " + ", ".join(f"{k}={v}" for k, v in out["params"].items()))
    for label in ("val_proposed", "val_baseline"):
        typer.echo(f"{label}: " + ", ".join(f"{k}={v:.4f}" if isinstance(v, float) else f"{k}={v}"
                                            for k, v in out[label].items()))
    typer.echo(f"Done in {out['seconds']} s")


@app.command("filter-check")
def filter_check(config: str = ConfigOpt) -> None:
    """Report the effect of causal vs zero-phase filtering on validation data (PRD 6.1)."""
    import pandas as pd

    from fallmon.config import load_config
    from fallmon.filter_check import run_filter_check
    from fallmon.splits import load_splits

    cfg = load_config(config)
    index = pd.read_parquet(cfg.dataset.processed_dir / "index.parquet")
    ens, scaler = _load_runtime(cfg)
    table = run_filter_check(index, load_splits(cfg.dataset.splits_path), ens, scaler, cfg)
    typer.echo(table.to_string(index=False))


@app.command("freeze")
def freeze(
    force: bool = typer.Option(False, "--force", help="Overwrite an existing frozen config."),
    config: str = ConfigOpt,
) -> None:
    """Lock config + models + verifier before the test split is unlocked (PRD 11.5)."""
    from fallmon.config import load_config
    from fallmon.guards import FROZEN_CONFIG, FROZEN_HASH, check_frozen, write_freeze
    from fallmon.utils import git_hash

    cfg = load_config(config)
    digest = write_freeze(cfg, git_hash(), force=force)
    check_frozen(cfg)
    typer.echo(f"Wrote {FROZEN_CONFIG} and {FROZEN_HASH}\nFrozen hash: {digest}")


if __name__ == "__main__":
    app()
