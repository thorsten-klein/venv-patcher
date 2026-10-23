# `venv-patcher list`

List patches applied in the current environment.

```text
venv-patcher list
```

## What it does

It prints each package in the manifest, sorted by name:

- the package folder;
- the initial commit, short;
- each patch result, with the patches file it came from and the time.

It runs no git command. It only reads the manifest.

## Options

`list` has no options of its own.

## Example

```bash
venv-patcher list
```

```text
idna (.venv/lib/python3.12/site-packages/idna)
  initial commit: 0918fb5d
  [OK] patches/idna/0001-Mark-idna-as-patched.patch  (from /home/me/demo/patches.yml, 2026-10-18T09:37:20.615286+00:00)
  [FAIL] patches/idna/0002-other.patch  (from /home/me/demo/patches.yml, 2026-10-18T09:40:02.294112+00:00)
        error: error: patch failed: package_data.py:1
error: package_data.py: patch does not apply
hint: Use 'git am --show-current-patch=diff' to see the failed patch
```

The time is in UTC. The error is the output of the apply command, as it
was. Only its first line is indented.

| Marker   | Meaning                                      |
|----------|----------------------------------------------|
| `[OK]`   | the patch is applied                         |
| `[FAIL]` | the patch failed. The error follows below it |

A package that was reset shows `(no patches applied)`.

With no manifest yet:

```text
No patches applied in this environment.
```

## Notes

- Failed results stay in the list until the next `reset` of the package.
- `list` shows what the manifest says. After a pip upgrade, the patches
  are gone, but still listed until the next `apply` or `reset`. See
  [Upgrade a patched package](../guides/upgrade.md).
- `list` always exits with `0`.

## See also

- [The manifest](../configuration/manifest.md)
