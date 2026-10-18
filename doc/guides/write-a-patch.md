# Write a patch

You want to change a package. This page shows how to make the patch file.

The paths in the patch must be relative to the **package folder**. For
`requests`, that is the folder with `requests/__init__.py` in it. So a
change to `requests/utils.py` shows up as `utils.py` in the patch.

## 1. Copy the package

Work on a copy, not on the venv:

```bash
PKG=$(python -c 'import requests, pathlib; print(pathlib.Path(requests.__file__).parent)')
cp -r "$PKG" /tmp/requests-work
cd /tmp/requests-work
rm -rf __pycache__
git init -q
git add .
git commit -qm base
```

> [!TIP]
> Copy it from a venv that has no patches yet. Then your patch fits the
> package as it is installed.

## 2. Change it

Edit the files. Then commit, with a clear message:

```bash
git commit -am "Fix the timeout handling"
```

Make one commit per patch.

## 3. Save it

```bash
git format-patch -1 -o ~/project/patches/requests
```

This writes `0001-Fix-the-timeout-handling.patch`. For more commits, use
`-2`, `-3` and so on. Each commit becomes its own file.

## 4. Add it to the patches file

```yaml
version: 1
patches:
  - package: requests
    path: patches/requests/0001-Fix-the-timeout-handling.patch
```

The default `apply-command` is `git am`, which reads exactly this kind of
file.

## 5. Try it

```bash
venv-patcher apply -f patches.yml
python -c 'import requests'   # still imports?
```

To change the patch and try again, see [Work on a patch](iterate.md).

## A plain diff

You can also use a plain diff, for example from `diff -u` or `git diff`.
Then set `apply-command`:

```yaml
version: 1
patches:
  - package: requests
    path: patches/requests/fix.diff
    apply-command: git apply
    comments: Fix the timeout handling
```

A plain diff has no message or author. `comments` gives the commit message.
`author`, `email` and `date` give the rest. See
[The patches file](../configuration/patches-file.md).

## Many patches for one package

List them in order. Each one builds on the one before:

```yaml
version: 1
patches:
  - package: requests
    path: patches/requests/0001-Fix-the-timeout-handling.patch
  - package: requests
    path: patches/requests/0002-Log-retries.patch
```

## See also

- [Use a patch from upstream](upstream-patch.md)
- [Pin a patch with sha256sum](pin-sha256.md)
