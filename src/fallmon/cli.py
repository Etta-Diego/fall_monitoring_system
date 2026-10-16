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
    logging.basicConfig(level=logging.INFO if verbose else logging.WARNING, format="%(levelname)s %(message)s")


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


if __name__ == "__main__":
    app()
