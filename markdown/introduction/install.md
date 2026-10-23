# Install venv-patcher

## Requirements

- Python 3.9 or newer. TOML patches files need Python 3.11 or newer.
- git, on your `PATH`.
- A virtual environment. venv-patcher does not run outside one.

## Install it into the venv you want to patch

venv-patcher patches the venv it runs in. So install it **into that venv**:

```bash
python -m venv .venv
source .venv/bin/activate
pip install venv-patcher
```

With uv:

```bash
uv venv
uv pip install venv-patcher
```

To get the newest code from GitHub instead of a release:

```bash
pip install git+https://github.com/thorsten-klein/venv-patcher.git
```

> [!WARNING]
> Do not install it with `pipx` or `uv tool install`. Those put it into a
> venv of its own. It would then patch that venv, not yours.

## Check the install

```bash
venv-patcher --help
```

You do not have to activate the venv. Calling its own entry point works
too, because it runs with that venv’s Python:

```bash
.venv/bin/venv-patcher list
```

Outside of a venv, venv-patcher stops with an error:

```text
error: venv-patcher must be run from inside a virtual environment (none detected). ...
```

## From source

```bash
git clone https://github.com/thorsten-klein/venv-patcher
pip install -e ./venv-patcher
```

Changes to the code work right away. See
[Development](../contributing/development.md) to work on venv-patcher.

## Next steps

- [venv-patcher in 5 minutes](../quickstart/05-minutes.md)
