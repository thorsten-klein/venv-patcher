# Development

How to work on venv-patcher.

## Setup

You need [uv](https://docs.astral.sh/uv/) and git.

```bash
git clone https://github.com/YOUR_USERNAME/venv-patcher
cd venv-patcher
uv sync            # installs everything, the docs tools too
uv run poe all     # the full check, to see that your setup works
```

The docs tools need Python 3.11 or newer. On older Pythons `uv sync` leaves
them out.

## Making changes

1. Branch off `main`.
2. Make your change and add tests for it.
3. Update the docs. See [Documentation](documentation.md).
4. Run `uv run poe all`.
5. Open a pull request against `main`.

## Tests

```text
tests/
  conftest.py       fixtures: a fake venv, packages, patch files
  test_cli.py       the commands, end to end, with real git
  test_core.py      the helpers in core.py
  test_manifest.py  reading and writing the manifest
  test_docs.py      the docs cover every command and option
```

The `fake_venv` fixture makes a site-packages folder in a temp folder. So
the tests never touch your own venv.

Tests that use `write_patches` run twice: once with YAML, once with TOML.
The TOML run is skipped before Python 3.11.

```bash
uv run poe test                     # everything, with the coverage check
uv run pytest tests/test_cli.py     # one file
uv run pytest -k reset              # by name
```

`poe test` needs **100% line coverage**. A line that can not be reached gets
a `# pragma: no cover` with a comment that says why.

CI runs the tests on Linux and macOS, with Python 3.9 to 3.13.

## Checks

`uv run poe all` runs every check CI runs. Each has its own task:

```bash
uv run poe pre-commit   # whitespace, YAML, TOML, JSON
uv run poe lint         # ruff lint
uv run poe format       # ruff format
uv run poe mypy         # types
uv run poe pyright      # types, with a second checker
uv run poe bandit       # security lint
uv run poe pip-audit    # known holes in dependencies
uv run poe complexity   # cognitive complexity, at most 8
uv run poe test         # tests with coverage
uv run poe docs         # the docs site, warnings are errors
```

## Adding a command

1. Add a sub parser in `build_parser` in `venv_patcher/cli.py`.
2. Add a `cmd_<name>` function and call it from `main`.
3. Add tests.
4. Add `doc/cli/<name>.md`, a line in `doc/index.md` and `doc/cli/index.md`,
   and a diagram in `doc/architecture/diagrams.md`.

`tests/test_docs.py` fails if a command or an option has no docs.

[Architecture](../architecture/index.md) explains how the parts fit.

## Commit messages

Use the imperative mood ("Add", not "Added"). Keep the first line under 72
characters. Name the issue where it fits.

## Reporting bugs

Open a GitHub issue with:

- the steps to reproduce it,
- what you expected and what happened,
- the output of `venv-patcher list`,
- your Python and git versions.
