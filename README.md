# venv-patcher

<img src="https://raw.githubusercontent.com/thorsten-klein/venv-patcher/main/doc/_static/logo.svg" alt="logo" width="500"/>

> Apply and track patches to packages installed in a Python virtual environment.

[![Run Tests](https://github.com/thorsten-klein/venv-patcher/actions/workflows/test.yml/badge.svg)](https://github.com/thorsten-klein/venv-patcher/actions/workflows/test.yml)
[![Docs](https://github.com/thorsten-klein/venv-patcher/actions/workflows/docs.yml/badge.svg)](https://thorsten-klein.github.io/venv-patcher/)
[![codecov](https://codecov.io/gh/thorsten-klein/venv-patcher/branch/main/graph/badge.svg)](https://codecov.io/gh/thorsten-klein/venv-patcher)
[![Quality Gate Status](https://sonarcloud.io/api/project_badges/measure?project=thorsten-klein_venv-patcher&metric=alert_status)](https://sonarcloud.io/summary/new_code?id=thorsten-klein_venv-patcher)
[![PyPI](https://img.shields.io/pypi/v/venv-patcher.svg)](https://pypi.org/project/venv-patcher/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

**📖 Documentation: <https://thorsten-klein.github.io/venv-patcher/>**

## What is venv-patcher?

venv-patcher applies patches to packages in your venv. It remembers what it
did. So you can list your patches, and undo them at any time.

```bash
venv-patcher apply -f patches.yml   # apply your patches
venv-patcher list                   # see what is patched
venv-patcher reset                  # undo all patches
```

The patches file says which patch goes to which package:

```yaml
version: 1
patches:
  - package: requests
    path: patches/0001-fix.patch
```

It can also be TOML, with Python 3.11 or newer. See
[`example.yml`](example.yml) and [`example.toml`](example.toml).

## How does it work?

- The first time, it turns the package folder into a git repository, and
  commits the files as they are.
- It applies each patch with `git am` (or `git apply`) as a new commit.
  Names and dates are fixed, so the commits are the same on every run.
- It records each result in a manifest in the venv's site-packages.
- `reset` goes back to the first commit.

## Install

Install it **into the venv you want to patch**:

```bash
pip install venv-patcher
```

Python 3.9 and git are needed. It does not run outside a venv. Do not
install it with `pipx` or `uv tool`: it would patch that tool's own venv.
See [Install venv-patcher](https://github.com/thorsten-klein/venv-patcher/blob/main/doc/introduction/install.md).

## Documentation

The full documentation is in [`doc/`](https://github.com/thorsten-klein/venv-patcher/blob/main/doc/README.md), and online at
<https://thorsten-klein.github.io/venv-patcher/>.

- [About venv-patcher](https://github.com/thorsten-klein/venv-patcher/blob/main/doc/introduction/index.md)
- [venv-patcher in 5 minutes](https://github.com/thorsten-klein/venv-patcher/blob/main/doc/quickstart/05-minutes.md)
- [How it works](https://github.com/thorsten-klein/venv-patcher/blob/main/doc/concepts/how-it-works.md)
- [Command reference](https://github.com/thorsten-klein/venv-patcher/blob/main/doc/cli/index.md)
- [The patches file](https://github.com/thorsten-klein/venv-patcher/blob/main/doc/configuration/patches-file.md)
- [Guides](https://github.com/thorsten-klein/venv-patcher/blob/main/doc/README.md#guides): writing patches, pinning,
  upgrades, CI and more

## Contributing

Pull requests are welcome. See [Development](https://github.com/thorsten-klein/venv-patcher/blob/main/doc/contributing/development.md)
for the setup and the checks. The short version:

```bash
uv sync          # install everything
uv run poe all   # every check CI runs
```

## License

MIT. See [LICENSE](LICENSE).
