#!/usr/bin/env python3
"""AI Runtime CLI."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

_RUNTIME_ROOT = Path(__file__).resolve().parent.parent
_AI_ROOT = _RUNTIME_ROOT.parent
if str(_AI_ROOT) not in sys.path:
    sys.path.insert(0, str(_AI_ROOT))

from runtime.config.loader import load_runtime_config  # noqa: E402
from runtime.core.runtime import AIRuntime  # noqa: E402

app = typer.Typer(
    name="runtime",
    help="AI Runtime — orchestration layer for AI capabilities.",
    add_completion=False,
)
console = Console()


def _load_runtime(config: Path | None) -> AIRuntime:
    return AIRuntime.from_config_path(config)


@app.command("health")
def health(
    config: Path | None = typer.Option(None, "--config", help="Runtime config YAML path."),
    json_output: bool = typer.Option(False, "--json", help="Emit JSON output."),
) -> None:
    """Check provider health."""
    runtime = _load_runtime(config)
    statuses = runtime.refresh_health()
    if json_output:
        payload = [
            {
                "provider_id": item.provider_id,
                "available": item.available,
                "latency_ms": item.latency_ms,
                "failure_count": item.failure_count,
                "last_success_at": item.last_success_at.isoformat() if item.last_success_at else None,
                "last_failure_at": item.last_failure_at.isoformat() if item.last_failure_at else None,
                "last_error": item.last_error,
            }
            for item in statuses
        ]
        console.print_json(json.dumps(payload))
        return

    table = Table(title="Provider Health")
    table.add_column("Provider")
    table.add_column("Available")
    table.add_column("Latency (ms)")
    table.add_column("Failures")
    table.add_column("Last Error")
    for item in statuses:
        table.add_row(
            item.provider_id,
            "yes" if item.available else "no",
            f"{item.latency_ms:.2f}" if item.latency_ms is not None else "-",
            str(item.failure_count),
            item.last_error or "-",
        )
    console.print(table)


@app.command("providers")
def providers(
    config: Path | None = typer.Option(None, "--config"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List configured providers."""
    runtime = _load_runtime(config)
    rows = []
    for provider_id in providers.list_provider_ids():
        provider = providers.get(provider_id)
        rows.append(
            {
                "provider_id": provider_id,
                "type": provider.provider_type,
                "configured": provider.is_configured(),
            }
        )
    if json_output:
        console.print_json(json.dumps(rows))
        return

    table = Table(title="Configured Providers")
    table.add_column("Provider")
    table.add_column("Type")
    table.add_column("Configured")
    for row in rows:
        table.add_row(row["provider_id"], row["type"], "yes" if row["configured"] else "no")
    console.print(table)


@app.command("tasks")
def tasks(
    config: Path | None = typer.Option(None, "--config"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """List registered tasks."""
    runtime = _load_runtime(config)
    rows = [
        {
            "name": task.name,
            "prompt_id": task.prompt_id,
            "schema_id": task.schema_id,
            "model_alias": task.model_alias,
            "preferred_provider": task.preferred_provider,
        }
        for task in runtime.tasks.list_tasks()
    ]
    if json_output:
        console.print_json(json.dumps(rows))
        return

    table = Table(title="Registered Tasks")
    table.add_column("Task")
    table.add_column("Prompt")
    table.add_column("Schema")
    table.add_column("Model Alias")
    table.add_column("Preferred Provider")
    for row in rows:
        table.add_row(
            row["name"],
            row["prompt_id"],
            row["schema_id"],
            row["model_alias"],
            row["preferred_provider"] or "-",
        )
    console.print(table)


@app.command("validate")
def validate(
    task: str = typer.Option(..., "--task", help="Task name to validate."),
    input: str = typer.Option(..., "--input", help="Input text or path to input file."),
    config: Path | None = typer.Option(None, "--config"),
) -> None:
    """Execute a task against the mock/default runtime."""
    runtime = _load_runtime(config)
    input_path = Path(input)
    payload = input_path.read_text(encoding="utf-8") if input_path.exists() else input
    result = runtime.run_task(task, payload)
    console.print_json(json.dumps(result.output, indent=2, default=str))


@app.command("config")
def show_config(
    config: Path | None = typer.Option(None, "--config"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show effective runtime configuration."""
    loaded = load_runtime_config(config)
    payload = loaded.model_dump(mode="json")
    if json_output:
        console.print_json(json.dumps(payload, indent=2, default=str))
        return
    console.print_json(json.dumps(payload, indent=2, default=str))


def main() -> None:
    app()


if __name__ == "__main__":
    main()
