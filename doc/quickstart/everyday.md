# Everyday tasks

The commands you need most days.

## Apply your patches

```bash
venv-patcher apply -f patches.yml
```

Run it after each `pip install` into a new venv. It is safe to run again.

## Apply the patches of one package

```bash
venv-patcher apply -f patches.yml -p requests
```

All other entries in the file are skipped.

## See what is patched

```bash
venv-patcher list
```

## Undo all patches

```bash
venv-patcher reset
```

## Undo the patches of one package

```bash
venv-patcher reset -p requests
```

## Change a patch and apply it again

```bash
venv-patcher apply --force -f patches.yml -p requests
```

`--force` first undoes the patches of `requests`. Then it applies the file.
See [Work on a patch](../guides/iterate.md).

## Look at a patched package

Each patched package is a git repository:

```bash
cd "$(python -c 'import requests, pathlib; print(pathlib.Path(requests.__file__).parent)')"
git log --oneline
git diff HEAD~1
```

> [!TIP]
> Look, but do not commit there yourself. `reset` goes back to the initial
> commit and drops anything on top.

## Upgrade a patched package

Make a new venv. Then apply your patches again. See
[Upgrade a patched package](../guides/upgrade.md).
