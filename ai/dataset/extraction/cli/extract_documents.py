#!/usr/bin/env python3
"""CLI entry point for Document Processing Engine Stage 1."""

from __future__ import annotations

import sys
from pathlib import Path

import typer

_ENGINE_ROOT = Path(__file__).resolve().parent.parent
_AI_ROOT = _ENGINE_ROOT.parent
if str(_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT))

from dataset.extraction.engine.config import build_config  # noqa: E402
from dataset.extraction.engine.orchestrator import ExtractionEngine  # noqa: E402

app = typer.Typer(
    name="extract_documents",
    help="Document Processing Engine — deterministic text extraction.",
    add_completion=False,
)


def _setup_logging(verbose: bool):
    import logging

    from rich.logging import RichHandler

    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(show_path=verbose, rich_tracebacks=True)],
    )
    return logging.getLogger("dataset.extraction")


@app.command()
def main(
    input: Path = typer.Option(..., "--input", help="Bronze dataset directory."),
    output: Path = typer.Option(..., "--output", help="Silver output directory."),
    inspection: Path | None = typer.Option(
        None, "--inspection", help="Inspector artifacts directory."
    ),
    workers: int = typer.Option(4, "--workers", min=1, max=64),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive"),
    resume: bool = typer.Option(False, "--resume", help="Skip already extracted documents."),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """Extract text and metadata from raw documents."""
    try:
        engine_config = build_config(
            input_path=input,
            output_path=output,
            config_path=config,
            inspection_path=inspection,
            recursive=recursive,
            workers=workers,
            resume=resume,
            verbose=verbose,
        )
    except ValueError as exc:
        typer.secho(f"Configuration error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=2) from exc

    logger = _setup_logging(verbose)
    logger.info("Document Processing Engine Stage 1")
    logger.info("Source: %s", engine_config.source_path)
    logger.info("Output: %s", engine_config.output_path)
    if engine_config.inspection_path:
        logger.info("Inspection artifacts: %s", engine_config.inspection_path)

    engine = ExtractionEngine(engine_config, logger)
    try:
        result = engine.run()
    except Exception as exc:  # noqa: BLE001
        typer.secho(f"Extraction failed: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(
        f"Processed {result.files_processed} files — "
        f"success={result.successful} failed={result.failed} "
        f"skipped={result.skipped} ocr_candidates={result.ocr_candidates}"
    )
    typer.echo(f"Silver dataset written to: {engine_config.output_path}")


if __name__ == "__main__":
    app()
