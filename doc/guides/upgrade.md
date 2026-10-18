# Upgrade a patched package

venv-patcher does not notice when you upgrade, downgrade or reinstall a
patched package with pip. Plan for it.

## The safe way: a new venv

```bash
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt     # with the new version
venv-patcher apply -f patches.yml
```

If a patch does not fit the new version, `apply` fails for it. Make a new
patch for that version. See [Write a patch](write-a-patch.md).

## Why not upgrade in place?

pip only knows the files it installed. It does not know about `.git`,
`.gitignore` or the manifest. After `pip install -U requests`:

- The package folder has the new files, but the old `.git`. The initial
  commit is still the one of the **old** version.
- The manifest still says the patches are applied. So `apply` skips them,
  but the new files have no patches.
- `reset` would go back to the initial commit. That puts the files of the
  **old** version back, under the new version's metadata. The package is
  then broken.

> [!WARNING]
> Never run `reset` or `apply --force` on a package you upgraded in
> place. Make a new venv instead.

## Uninstall

`pip uninstall` also leaves `.git` and `.gitignore` behind in the package
folder. That does no harm. Delete the folder by hand if you like.
