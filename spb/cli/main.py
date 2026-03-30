"""Command-line interface for Smart Project Backup."""

from __future__ import annotations

from pathlib import Path

import click

from spb.config import (
    ConfigFileInvalid,
    ConfigFileMissing,
    format_status_lines,
    paths_for_backup,
    persist_config_updates,
    read_config,
)
from spb.constants import config_file_path, resolve_config_dir
from spb.core.backup import BackupResult, run_backup

_BACKUP_CLI_ARG_PAIR = 2


def _emit_backup_result(result: BackupResult) -> None:
    for warning in result.warnings:
        click.echo(f"Warning: {warning}", err=True)
    for error in result.errors:
        click.echo(f"Error: {error}", err=True)

    click.echo(result.summary.to_output_line())

    if result.errors:
        raise click.exceptions.Exit(1)


@click.group()
def cli() -> None:
    """Smart Project Backup."""


@cli.command("backup")
@click.argument(
    "paths",
    nargs=-1,
    type=click.Path(path_type=Path, exists=False),
)
def backup_command(paths: tuple[Path, ...]) -> None:
    """Back up SOURCE into DEST, or use config defaults when given no arguments."""
    if len(paths) not in (0, 2):
        msg = (
            "`spb backup` accepts zero arguments (use configured defaults) "
            "or exactly two (SOURCE and DEST)."
        )
        raise click.UsageError(
            msg,
        )

    if len(paths) == _BACKUP_CLI_ARG_PAIR:
        source, destination = paths[0], paths[1]
        source = source.expanduser()
        destination = destination.expanduser()
        if not source.is_dir():
            msg = f"Source must be an existing directory: {source}"
            raise click.ClickException(msg)
    else:
        outcome = read_config()
        if isinstance(outcome, ConfigFileMissing):
            msg = (
                "No config file found. Set defaults with "
                "`spb configure --source DIR --dest DIR` or pass paths explicitly."
            )
            raise click.ClickException(msg)
        if isinstance(outcome, ConfigFileInvalid):
            raise click.ClickException(outcome.reason)
        try:
            source, destination = paths_for_backup(outcome.config)
        except ValueError as exc:
            raise click.ClickException(str(exc)) from exc

    try:
        result = run_backup(source=source, destination=destination)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    _emit_backup_result(result)


@cli.command("configure")
@click.option(
    "--source",
    "source",
    type=click.Path(file_okay=False, path_type=Path),
    default=None,
)
@click.option(
    "--dest",
    "dest",
    type=click.Path(path_type=Path),
    default=None,
)
def configure_command(source: Path | None, dest: Path | None) -> None:
    """Write or update default source/destination in the user config file."""
    if source is None and dest is None:
        msg = "Specify at least one of --source or --dest."
        raise click.UsageError(msg)

    try:
        persist_config_updates(source=source, dest=dest)
    except (TypeError, ValueError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Updated {config_file_path()}")


@cli.command("status")
def status_command() -> None:
    """Show config file location and current default paths."""
    try:
        path = config_file_path()
    except ValueError as exc:
        click.echo(f"Resolved config directory: {resolve_config_dir()}", err=True)
        click.echo(str(exc), err=True)
        raise click.exceptions.Exit(1) from exc

    outcome = read_config(path)
    if isinstance(outcome, ConfigFileInvalid):
        for line in format_status_lines(outcome, path):
            click.echo(line)
        raise click.exceptions.Exit(1)

    for line in format_status_lines(outcome, path):
        click.echo(line)
