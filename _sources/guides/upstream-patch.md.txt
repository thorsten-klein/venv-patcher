# Use a patch from upstream

The fix you want is already in the package's own repository. It is just
not released yet. You can use that commit as your patch.

## The problem: other paths

In the upstream repository, files are often in a sub folder:

```text
src/idna/core.py
```

In the venv, the package folder is `idna/`. So the patch must say just
`core.py`. The paths do not fit.

## Get the patch

On GitHub, add `.patch` to the commit URL:

```bash
curl -L https://github.com/kjd/idna/commit/<sha>.patch -o patches/idna/0001-fix.patch
```

Or from a clone:

```bash
git format-patch -1 <sha> -o patches/idna
```

## Strip the front of the paths

`git am` and `git apply` have `-p<n>`. It removes `n` parts from the front
of each path. Normally `n` is 1, which removes `a/` and `b/`.

| Path in the patch | Option | Path used |
|---|---|---|
| `a/core.py` | `-p1` (default) | `core.py` |
| `a/idna/core.py` | `-p2` | `core.py` |
| `a/src/idna/core.py` | `-p3` | `core.py` |

So for `src/idna/core.py`:

```yaml
version: 1
patches:
  - package: idna
    path: patches/idna/0001-fix.patch
    apply-command: git am -p3
```

## Leave out other files

An upstream commit often also changes tests or docs. Those files are not in
the venv, so the patch fails. `-p3` also fails on a short path like
`tests/test_core.py`.

So make the patch from the package files only. Add the folder at the end of
`git format-patch`:

```bash
git format-patch -1 <sha> -o patches/idna -- src/idna
```

Now the patch only has files under `src/idna/`, and `git am -p3` works.

## Check that it fits

The fix was made against the newest upstream code. Your venv may have an
older release. If `apply` fails, the patch does not fit your version. Then
make your own patch. See [Write a patch](write-a-patch.md).
