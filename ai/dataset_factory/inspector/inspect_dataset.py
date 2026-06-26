#!/usr/bin/env python3
"""CLI entry point for Dataset Inspector v1."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

# Allow running as a script: python inspect_dataset.py
_INSPECTOR_ROOT = Path(__file__).resolve().parent
_AI_ROOT = _INSPECTOR_ROOT.parent.parent
if str(_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT))

from dataset_factory.inspector.config import build_config  # noqa: E402
from dataset_factory.inspector.engine import InspectionEngine  # noqa: E402
from dataset_factory.inspector.logging_setup import log_summary, setup_logging  # noqa: E402
from dataset_factory.inspector.models import LogEvent  # noqa: E402

app = typer.Typer(
    name="inspect_dataset",
    help="Dataset Inspector v1 — read-only analysis for the AI Dataset Factory.",
    add_completion=False,
)


@app.command()
def main(
    input: Path = typer.Option(..., "--input", help="Path to the raw dataset directory."),
    output: Path = typer.Option(..., "--output", help="Path to write inspection artifacts."),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Scan subdirectories."),
    workers: int = typer.Option(4, "--workers", min=1, max=64, help="Concurrent worker count."),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging."),
    config: Path | None = typer.Option(None, "--config", help="Optional YAML config file."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Analyze without writing output files."),
) -> None:
    """Analyze a dataset directory and emit inspection artifacts."""
    try:
        inspector_config = build_config(
            input_path=input,
            output_path=output,
            config_path=config,
            recursive=recursive,
            workers=workers,
            verbose=verbose,
            dry_run=dry_run,
        )
    except (ValueError, FileNotFoundError) as exc:
        typer.secho(f"Configuration error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc

    events: list[LogEvent] = []
    logger = setup_logging(inspector_config, events)
    logger.info("Dataset Inspector v1 starting")
    logger.info("Source: %s", inspector_config.source_path)
    logger.info("Output: %s", inspector_config.output_path)

    engine = InspectionEngine(inspector_config, logger, events=events)
    try:
        result = engine.run()
    except FileNotFoundError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:  # noqa: BLE001
        typer.secho(f"Inspection failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    log_summary(logger, result)

    if dry_run:
        typer.echo("Dry run complete — no artifacts written.")
    else:
        typer.echo(f"Inspection artifacts written to: {inspector_config.output_path}")


if __name__ == "__main__":
    app()
