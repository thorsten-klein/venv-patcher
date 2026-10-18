# `venv-patcher reset`

Revert all patches applied in the current environment.

```text
venv-patcher reset [-p <package> ...]
```

## What it does

For each package in the manifest:

1. End a `git am` that stopped half way, if there is one.
2. `git reset --hard` to its initial commit.
3. `git clean -fd`, to remove files that patches added.
4. Empty its patch list in the manifest.

The package is then as it was installed.

## Options

| Option | Meaning |
|---|---|
| `-p`, `--package <package>` | only reset this package. Give it more than once for more packages |

## Examples

```bash
venv-patcher reset
venv-patcher reset -p requests
venv-patcher reset -p requests -p urllib3
```

```text
reset idna to initial state (0918fb5d)
```

## Notes

- The git repository in the package folder stays. So does the initial
  commit in the manifest. The next `apply` uses them again.
- A package with no initial commit yet is skipped. This happens when its
  first `apply` failed before `git init`.
- A package whose folder is gone gets a warning and is skipped.
- A `-p` name that is not in the manifest does nothing.
- With an empty manifest, `reset` prints `No patches to reset.`

## A package that changed

If the files differ from the last commit, someone else changed them, for
example pip during an upgrade. Then a hard reset would put back old files.
So `reset` keeps the installed files instead. It drops the git history and
the patch list:

```text
warning: requests changed since venv-patcher patched it; kept the installed files
```

See [Upgrade a patched package](../guides/upgrade.md).

## See also

- [`apply --force`](apply.md#--force): reset and apply in one step.
