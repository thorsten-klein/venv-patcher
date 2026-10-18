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
  [OK] patches/idna/0001-Mark-idna-as-patched.patch  (from /home/me/demo/patches.yml, 2026-10-18T09:37:20+00:00)
  [FAIL] patches/idna/0002-other.patch  (from /home/me/demo/patches.yml, 2026-10-18T09:40:02+00:00)
        error: patch failed: core.py:12
```

| Marker | Meaning |
|---|---|
| `[OK]` | the patch is applied |
| `[FAIL]` | the patch failed. The next line has the error |

A package that was reset shows `(no patches applied)`.

With no manifest yet:

```text
No patches applied in this environment.
```

## Notes

- Failed results stay in the list until the next `reset` of the package.
- `list` shows what the manifest says. If you changed the package by hand,
  or upgraded it, the list can be wrong. See
  [Upgrade a patched package](../guides/upgrade.md).
- `list` always exits with `0`.

## See also

- [The manifest](../configuration/manifest.md)
