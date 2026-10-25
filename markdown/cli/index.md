# Overview and common options

```text
venv-patcher [-h] <command> [<options>]
```

Each command has its own page. This page lists what they share.

## Commands

| Command             | What it does                                              |
|---------------------|-----------------------------------------------------------|
| [`apply`](apply.md) | apply patches described in one or more YAML or TOML files |
| [`list`](list.md)   | list patches applied in the current environment           |
| [`reset`](reset.md) | revert all patches applied in the current environment     |

## Getting help

```bash
venv-patcher --help          # all commands
venv-patcher apply --help    # one command and its options
venv-patcher apply -h        # the same
```

## Options for all commands

| Option         | Meaning             |
|----------------|---------------------|
| `-h`, `--help` | print help and stop |

## The venv it works on

venv-patcher always works on the venv of the Python that runs it. It finds
that venv’s site-packages folder and keeps its manifest there.

- It stops with an error if it does not run in a venv.
- `--help` works everywhere, also outside a venv.
- You do not need to activate the venv. `.venv/bin/venv-patcher` works too.

## Output

- Results and progress go to stdout, for example
  `applied patches/0001-fix.patch to requests`.
- Warnings and errors go to stderr. They start with `warning:` or `error:`.

## Exit status

| Code   | Meaning                                           |
|--------|---------------------------------------------------|
| `0`    | success                                           |
| `1`    | at least one step failed; the reason is on stderr |
| `2`    | an unknown option, or a missing argument          |

`list` always exits with `0`.
