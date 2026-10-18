"""The hand-written docs are the ones that can drift away from the parser."""

import argparse
from pathlib import Path

import pytest
import yaml

from venv_patcher.cli import build_parser

_ROOT = Path(__file__).parent.parent
_DOC = _ROOT / "doc"
DIAGRAMS = (_DOC / "architecture" / "diagrams.md").read_text(encoding="utf-8")
CLI_INDEX = (_DOC / "cli" / "index.md").read_text(encoding="utf-8")
SITE_INDEX = (_DOC / "index.md").read_text(encoding="utf-8")
PATCHES_FILE = (_DOC / "configuration" / "patches-file.md").read_text(encoding="utf-8")
EXAMPLE = yaml.safe_load((_ROOT / "example.yml").read_text(encoding="utf-8"))


def _subcommands() -> dict[str, tuple[str, argparse.ArgumentParser]]:
    """Each command name with its help text and its parser."""
    action = next(a for a in build_parser()._actions if isinstance(a, argparse._SubParsersAction))
    helps = {choice.dest: choice.help for choice in action._choices_actions}
    return {name: (helps[name], parser) for name, parser in action.choices.items()}


COMMANDS = _subcommands()


def _command_page(command: str) -> str:
    return (_DOC / "cli" / f"{command}.md").read_text(encoding="utf-8")


@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_every_command_has_a_page(command):
    """Each command has its own page, titled with its name."""
    assert _command_page(command).startswith(f"# `venv-patcher {command}`\n")


@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_every_command_page_has_its_summary(command):
    """The command page opens with the words --help uses."""
    assert f"\n{COMMANDS[command][0]}.\n" in _command_page(command)


@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_every_command_is_listed(command):
    """The command list and the site menu link the page."""
    assert f"]({command}.md)" in CLI_INDEX
    assert f"](cli/{command}.md)" in SITE_INDEX
    assert f"\ncli/{command}\n" in SITE_INDEX


@pytest.mark.parametrize("command", sorted(COMMANDS))
def test_every_command_has_a_call_diagram(command):
    """doc/architecture/diagrams.md is how the git calls behind a command are explained."""
    assert f"\n## {command}\n" in DIAGRAMS


@pytest.mark.parametrize(
    ("command", "flag"),
    [
        (command, flag)
        for command, (_, parser) in sorted(COMMANDS.items())
        for action in parser._actions
        if not isinstance(action, argparse._HelpAction)
        for flag in action.option_strings
    ],
)
def test_every_option_is_documented(command, flag):
    """Each option a command takes is on that command's page."""
    assert f"`{flag}" in _command_page(command)


@pytest.mark.parametrize("field", sorted(EXAMPLE["patches"][0]))
def test_every_patches_file_field_is_documented(field):
    """Each field of an entry has its own section and a row in the table."""
    assert f"\n### `{field}`\n" in PATCHES_FILE
    assert f"| [`{field}`](#{field}) |" in PATCHES_FILE
