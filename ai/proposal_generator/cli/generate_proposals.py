#!/usr/bin/env python3
"""CLI entry point for Proposal Generator."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import typer
from rich.logging import RichHandler

_GENERATOR_ROOT = Path(__file__).resolve().parent.parent
_AI_ROOT = _GENERATOR_ROOT.parent
if str(_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT))

from proposal_generator.engine.config import build_config  # noqa: E402
from proposal_generator.engine.orchestrator import ProposalEngine  # noqa: E402

app = typer.Typer(
    name="generate_proposals",
    help="Proposal Generator — Silver Dataset to Proposal Artifacts via AI Runtime.",
    add_completion=False,
)


def _setup_logging(verbose: bool) -> logging.Logger:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(show_path=verbose, rich_tracebacks=True)],
    )
    return logging.getLogger("proposal_generator")


@app.command()
def main(
    input: Path = typer.Option(..., "--input", help="Silver dataset directory."),
    output: Path = typer.Option(..., "--output", help="Proposal output directory."),
    workers: int = typer.Option(4, "--workers", min=1, max=64),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive"),
    resume: bool = typer.Option(False, "--resume", help="Skip already generated proposals."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    config: Path | None = typer.Option(None, "--config"),
    runtime_config: Path | None = typer.Option(
        None, "--runtime-config", help="Optional AI Runtime config YAML path."
    ),
) -> None:
    """Generate proposal artifacts from the Silver Dataset."""
    try:
        generator_config = build_config(
            input_path=input,
            output_path=output,
            config_path=config,
            recursive=recursive,
            workers=workers,
            resume=resume,
            verbose=verbose,
            overrides={"runtime_config_path": runtime_config} if runtime_config else None,
        )
    except ValueError as exc:
        typer.secho(f"Configuration error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc

    logger = _setup_logging(verbose)
    logger.info("Proposal Generator")
    logger.info("Silver source: %s", generator_config.source_path)
    logger.info("Proposal output: %s", generator_config.output_path)
    logger.info("Workers: %d", generator_config.workers)

    engine = ProposalEngine(generator_config, logger)
    try:
        result = engine.run()
    except Exception as exc:  # noqa: BLE001
        typer.secho(f"Proposal generation failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.secho(
        f"Done — processed={result.files_processed} success={result.successful} "
        f"failed={result.failed} skipped={result.skipped}",
        fg=typer.colors.GREEN,
    )


if __name__ == "__main__":
    app()
