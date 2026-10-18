# venv-patcher in 5 minutes

This walk through patches the small package `idna`. It changes its
version string, so you can see the patch work.

## 1. Make a venv

```bash
mkdir demo && cd demo
python -m venv .venv
source .venv/bin/activate
pip install venv-patcher idna==3.20
```

## 2. Write a patch

Copy the package to a work folder. Make it a git repository:

```bash
PKG=$(python -c 'import idna, pathlib; print(pathlib.Path(idna.__file__).parent)')
cp -r "$PKG" /tmp/idna-work
cd /tmp/idna-work
rm -rf __pycache__
git init -q && git add . && git commit -qm base
```

Change a file and commit it:

```bash
sed -i 's/^__version__ = "3.20"/__version__ = "3.20+patched"/' package_data.py
git commit -qam "Mark idna as patched"
```

Save the commit as a patch file in your project:

```bash
git format-patch -1 -o ~/demo/patches/idna
cd ~/demo
```

You now have `patches/idna/0001-Mark-idna-as-patched.patch`.

The paths in the patch are relative to the package folder, for example
`package_data.py`. That is what venv-patcher expects.

## 3. Write the patches file

Create `patches.yml`:

```yaml
version: 1
patches:
  - package: idna
    path: patches/idna/0001-Mark-idna-as-patched.patch
```

`path` is relative to the patches file.

## 4. Apply it

```bash
venv-patcher apply -f patches.yml
```

```text
initialized git tracking for idna at .../site-packages/idna (0918fb5d)
applied patches/idna/0001-Mark-idna-as-patched.patch to idna
```

Check it:

```bash
python -c 'import idna; print(idna.__version__)'
```

```text
3.20+patched
```

## 5. See what is patched

```bash
venv-patcher list
```

```text
idna (.../site-packages/idna)
  initial commit: 0918fb5d
  [OK] patches/idna/0001-Mark-idna-as-patched.patch  (from .../demo/patches.yml, 2026-10-18T09:37:20.615286+00:00)
```

The package folder is now a git repository. Look inside:

```bash
git -C "$PKG" log --oneline
```

```text
7bb8978 Mark idna as patched
0918fb5 initial
```

The initial commit is the same everywhere. The patch commit differs:
`git am` keeps the date of your patch.

## 6. Apply again

```bash
venv-patcher apply -f patches.yml
```

```text
warning: patches/idna/0001-Mark-idna-as-patched.patch already applied to idna, skipping
```

Running `apply` twice is safe. A patch that is already applied is skipped.

## 7. Undo it

```bash
venv-patcher reset
```

```text
reset idna to initial state (0918fb5d)
```

```bash
python -c 'import idna; print(idna.__version__)'
```

```text
3.20
```

## Next steps

- [Everyday tasks](everyday.md)
- [Write a patch](../guides/write-a-patch.md)
- [The patches file](../configuration/patches-file.md)
