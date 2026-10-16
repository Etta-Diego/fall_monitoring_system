"""Write result tables (CSV + Markdown) and figures for the thesis."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

RESULTS_DIR = Path("results")
TABLES_DIR = RESULTS_DIR / "tables"
FIGURES_DIR = RESULTS_DIR / "figures"
FIGURE_DPI = 300
DATA_SOURCE = "SisFall dataset replay (simulated IoT stream)"


def write_table(df: pd.DataFrame, stem: str, title: str, notes: str = "") -> tuple[Path, Path]:
    """Save `df` as results/tables/<stem>.csv and <stem>.md (the .md carries title and notes)."""
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    csv_path, md_path = TABLES_DIR / f"{stem}.csv", TABLES_DIR / f"{stem}.md"
    df.to_csv(csv_path, index=False)
    lines = [f"# {title}", "", f"Data source: {DATA_SOURCE}.", ""]
    if notes:
        lines += [notes, ""]
    lines.append(df.to_markdown(index=False))
    md_path.write_text("\n".join(lines) + "\n")
    return csv_path, md_path
