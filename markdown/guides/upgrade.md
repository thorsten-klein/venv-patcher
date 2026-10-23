# Upgrade a patched package

You upgraded, downgraded or reinstalled a patched package with pip. pip
put its own files back, so your patches are gone. venv-patcher notices
this.

## How it notices

venv-patcher commits every change it makes. So when the files of a package
differ from its last commit, someone else changed them. Most often that is
pip.

## Apply the patches again

```bash
pip install -U requests
venv-patcher apply --force -p requests -f patches.yml
```

`--force -p requests` starts again from the installed files:

1. It drops the old git history of `requests`. The files stay as pip
   installed them.
2. It makes a new initial commit from them.
3. It applies the patches of `requests` on top.

If a patch does not fit the new version, `apply` fails for it. Make a new
patch for that version. See [Write a patch](write-a-patch.md).

## Without `--force`

A plain `apply` stops for that package:

```text
error: requests changed since venv-patcher patched it, for example by a pip upgrade; use --force -p requests to start again from the installed files
```

It does not skip the patches as “already applied”. They are not, any more.

## Reset

`reset` on a changed package keeps the installed files. It drops the git
history and the patch list:

```text
warning: requests changed since venv-patcher patched it; kept the installed files
```

The next `apply` starts again with a new initial commit.

> [!NOTE]
> This also happens when you change files in the package folder by hand
> and do not commit. `reset` only undoes what venv-patcher did.

## A new venv works too

```bash
rm -rf .venv
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
venv-patcher apply -f patches.yml
```

## Uninstall

`pip uninstall` leaves `.git` and `.gitignore` behind in the package
folder. That does no harm. Delete the folder by hand if you like.
