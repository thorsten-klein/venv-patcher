# `venv-patcher apply`

Apply patches described in one or more YAML or TOML files.

```text
venv-patcher apply -f <file> [-f <file> ...] [-p <package> ...] [--skip-missing] [--force]
```

## What it does

For each entry of each patches file, in order:

1. Skip it if it is already applied and the patch file did not change.
2. Import the package and find its folder.
3. The first time: `git init` there and commit the files as `initial`.
4. Check the patch file, and its `sha256sum` if set.
5. Run the apply command, `git am` by default.
6. Commit the result with a pinned identity.
7. Record the result in the manifest.

[How it works](../concepts/how-it-works.md#apply) has the details.

## Options

| Option | Meaning |
|---|---|
| `-f`, `--file <file>` | the patches file to apply. Required. Give it more than once for more files |
| `-p`, `--package <package>` | only apply the entries for this package. Give it more than once for more packages |
| `--skip-missing` | if a package can not be imported, skip its entry and go on. Default: stop |
| `--force` | first reset the packages given with `-p`, or all tracked packages, then apply |

A `.toml` file is read as TOML, any other file as YAML. TOML needs Python
3.11 or newer. See [The patches file](../configuration/patches-file.md).

## Examples

```bash
venv-patcher apply -f patches.yml
venv-patcher apply -f patches.toml
venv-patcher apply -f base.yml -f extra.yml
venv-patcher apply -f patches.yml -p requests -p urllib3
venv-patcher apply -f patches.yml --skip-missing
venv-patcher apply -f patches.yml --force -p requests
```

## Running it again

`apply` is safe to run again. For a patch file that is already applied:

| The patch file | What happens |
|---|---|
| did not change | a warning, the entry is skipped |
| changed | an error, use `--force` |
| is gone | an error |

```text
warning: patches/0001-fix.patch already applied to requests, skipping
```

```text
error: patches/0001-fix.patch was already applied to requests but its content has changed since then; use --force to reset requests and apply it again
```

A patch counts as the same when its full path is the same. Two patches
files that name the same patch file share it.

## A package that is not installed

By default `apply` stops at the first package it can not import. It does
not touch the rest of the entries:

```text
error: package 'nosuchpkg' is not importable in the current environment: No module named 'nosuchpkg'
```

With `--skip-missing` it skips that entry and goes on. The exit status is
still `1`, because the entry failed.

## `--force`

```bash
venv-patcher apply -f patches.yml --force -p requests
```

1. Reset `requests` to its initial commit, and empty its patch list.
2. Apply the file as usual.

> [!WARNING]
> Without `-p`, `--force` resets **every** package in the manifest. That
> includes packages that are not in the files you apply now.

See [Work on a patch](../guides/iterate.md).

## When a patch fails

If the apply command fails, `apply` shows what it ran, where, and what git
said:

```text
error: failed to apply patch
  command:     git am
  package:     idna
  patch:       patches/idna/0002-other.patch
  package-dir: /home/me/demo/.venv/lib/python3.12/site-packages/idna
  stderr:
    error: patch failed: package_data.py:1
    error: package_data.py: patch does not apply
    hint: Use 'git am --show-current-patch=diff' to see the failed patch
```

The result is recorded as failed. `apply` goes on with the next entry, and
exits with `1` at the end.

## Notes

- A missing or broken patches file is an error. `apply` then goes on with
  the next `-f` file.
- A failed entry is still recorded in the manifest. `list` shows it as
  `[FAIL]`.
- A failed patch changes nothing. The package is put back to its last
  commit, and a stopped `git am` is ended.
- Single `.py` files right in site-packages can not be patched. Only
  package folders.

## See also

- [The patches file](../configuration/patches-file.md)
- [Write a patch](../guides/write-a-patch.md)
- [`reset`](reset.md)
