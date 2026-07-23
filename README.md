# venv-patcher

Apply and track patches to packages installed in a Python virtual environment.

`venv-patcher` records the pristine state of every package it touches as a git
commit, applies your patches on top as further deterministic commits, and
keeps a manifest (in the venv's site-packages) of everything it has done -
so you can list or fully revert your patches at any time.

## Install

```
pip install venv-patcher
```

Or straight from git:

```
pip install git+https://github.com/thorsten-klein/venv-patcher.git
```

`venv-patcher` refuses to run outside of an active virtual environment.

## Usage

```
venv-patcher apply -f patches.yml [-f <file> ...] [-p <package> ...] [--skip-missing] [--force]
venv-patcher list
venv-patcher reset [-p <package> ...]
```

### `apply`

Use `-p`/`--package` one or more times to only apply the patches that target
those packages, skipping every other entry in the given yaml file(s).

For each patch entry, on first use for a package, `venv-patcher`:

1. Imports the package to find its on-disk directory.
2. Runs `git init`, adds a `.gitignore` for `__pycache__`/`*.pyc`, then
   `git add .` and commits the pristine state as `"initial"`.

It then applies the patch (`git am` by default) on top. The result is
always wrapped in a commit with a pinned author/committer identity and date
(from the yaml, or a fixed fallback), so re-applying the same patch to the
same starting state always produces the exact same commit hash.

Patch results (applied or failed) are recorded in the manifest immediately,
even when a patch fails to apply. The manifest also stores the sha256 of the
patch file content that was actually applied. Running `apply` again for a
patch that was already applied:

- prints a warning and skips it, if the patch file on disk is unchanged;
- errors out and tells you to pass `--force`, if the patch file's content has
  changed since it was applied (e.g. it's still under development and
  doesn't have a `sha256sum` pinned down yet) - `venv-patcher` won't silently
  apply a different patch on top of what's already there.

By default, if a package listed in the yaml can't be imported, `venv-patcher`
records the failure and aborts immediately without processing any further
patches. Pass `--skip-missing` to instead skip just that patch and continue
with the rest.

Pass `--force` to start from a clean slate before applying: `venv-patcher`
hard-resets the affected packages back to their recorded initial commit and
clears their patch history first, then applies the yaml file(s) as usual.
This is meant for iterating on a patch that doesn't have a `sha256sum` pinned
down yet. Combined with `-p`, only the given package(s) are reset.
Without `-p`, *every* package tracked in the manifest is reset - including ones
not mentioned in the yaml file(s) you're currently applying with `-f`.

### `list`

Prints every package with applied patches in the current environment, their
status, and any errors.

### `reset`

Hard-resets every patched package back to its recorded initial commit and
clears the manifest's patch history for it. Use `-p`/`--package` one or more
times to only reset specific packages.

## YAML format

```yaml
version: 1                          # required, currently must be 1
patches:
  - path: patches/0001-fix.patch    # relative to this yaml file, or absolute
    package: requests               # importable package name
    sha256sum: <optional sha256 of the patch file>
    apply-command: git am           # default; use "git apply" for a plain diff
    author: Jane Doe                # used for the commit identity
    email: jane@example.com
    date: "2024-01-01T00:00:00+00:00"
    comments: "commit message for the patch commit"
```

See [`example.yml`](example.yml) for a full annotated example.

## Development

```
uv sync
uv run poe all      # lint, format, test
```
