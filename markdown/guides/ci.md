# Use it in CI

In CI every run starts with a new venv. So the steps are always the same:
make the venv, install, apply.

## GitHub Actions

```yaml
- uses: actions/setup-python@v5
  with:
    python-version: '3.12'
- name: Install
  run: |
    python -m venv .venv
    .venv/bin/pip install -r requirements.txt venv-patcher
- name: Apply patches
  run: .venv/bin/venv-patcher apply -f patches.yml
- name: Test
  run: .venv/bin/python -m pytest
```

`.venv/bin/venv-patcher` runs with the venv’s Python. So it patches that
venv, without `source .venv/bin/activate`.

## With uv

```bash
uv sync
uv run venv-patcher apply -f patches.yml
uv run pytest
```

`uv run` runs in the project’s `.venv`.

> [!WARNING]
> If `uv sync` installs another version of a patched package, the patches
> are gone. `apply` then stops for that package. See
> [Upgrade a patched package](upgrade.md).

## git is needed

venv-patcher runs git. Most CI images have it. venv-patcher sets the name,
email and date of its own commits. So you do not need `git config user.name` for it.

## Fail the build on a bad patch

`apply` exits with `1` when a patch fails. CI then stops. Print the details
in the log:

```bash
.venv/bin/venv-patcher apply -f patches.yml || { .venv/bin/venv-patcher list; exit 1; }
```

## Pin your patches

In CI, pin each patch with `sha256sum`. Then only the patch you checked can
be applied. See [Pin a patch with sha256sum](pin-sha256.md).
