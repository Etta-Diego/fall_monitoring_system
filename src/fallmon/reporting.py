"""Write result tables (CSV + Markdown) and figures for the thesis."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RESULTS_DIR = Path("results")
TABLES_DIR = RESULTS_DIR / "tables"
FIGURES_DIR = RESULTS_DIR / "figures"
FIGURE_DPI = 300
DATA_SOURCE = "SisFall dataset replay (simulated IoT stream)"


def write_table(df: pd.DataFrame, stem: str, title: str, notes: str = "", out_dir: Path | None = None,
                frozen_hash: str | None = None) -> tuple[Path, Path]:
    """Save `df` as <out_dir>/<stem>.csv and <stem>.md (the .md carries title and notes).

    With `frozen_hash`, both files start with the frozen-config hash (PRD 11.5); in the CSV it is a
    `#` comment line (read back with `pd.read_csv(path, comment="#")`).
    """
    out_dir = out_dir or TABLES_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path, md_path = out_dir / f"{stem}.csv", out_dir / f"{stem}.md"
    with open(csv_path, "w") as f:
        if frozen_hash:
            f.write(f"# frozen_config_sha256: {frozen_hash}\n")
        df.to_csv(f, index=False)
    lines = [f"# {title}", ""]
    if frozen_hash:
        lines += [f"Frozen config SHA-256: `{frozen_hash}`", ""]
    lines += [f"Data source: {DATA_SOURCE}.", ""]
    if notes:
        lines += [notes, ""]
    lines.append(df.to_markdown(index=False))
    md_path.write_text("\n".join(lines) + "\n")
    return csv_path, md_path


def save_figure(fig, path: Path, frozen_hash: str | None = None) -> Path:
    """Save a matplotlib figure at thesis resolution; stamp the frozen hash in a footer and the PNG metadata."""
    path.parent.mkdir(parents=True, exist_ok=True)
    meta = {"Description": DATA_SOURCE}
    if frozen_hash:
        fig.text(0.995, 0.003, f"frozen config {frozen_hash[:12]}", ha="right", va="bottom", fontsize=5, color="grey")
        meta["Comment"] = f"frozen_config_sha256: {frozen_hash}"
    fig.savefig(path, dpi=FIGURE_DPI, metadata=meta)
    return path
