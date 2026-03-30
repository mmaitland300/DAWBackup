"""Command-line interface for Smart Project Backup."""

from __future__ import annotations

from pathlib import Path

import click

from spb.core.backup import run_backup


@click.group()
def cli() -> None:
    """Smart Project Backup."""


@cli.command("backup")
@click.argument("source", type=click.Path(exists=True, file_okay=False, path_type=Path))
@click.argument("dest", type=click.Path(file_okay=False, path_type=Path))
def backup_command(source: Path, dest: Path) -> None:
    """Back up SOURCE into DEST using content hashing and a SQLite manifest."""
    try:
        result = run_backup(source=source, destination=dest)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    for warning in result.warnings:
        click.echo(f"Warning: {warning}", err=True)
    for error in result.errors:
        click.echo(f"Error: {error}", err=True)

    click.echo(result.summary.to_output_line())

    if result.errors:
        raise click.exceptions.Exit(1)
