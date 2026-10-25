# Work on a patch

You are still changing a patch. You want to try each version in your venv.

## The loop

1. Change the patch file.
2. Apply it again, with `--force`:
   ```bash
   venv-patcher apply --force -f patches.yml -p requests
   ```
3. Test. Back to step 1.

`--force` first resets `requests` to its initial commit. Then it applies
all entries for `requests` from the start. Without `--force`, `apply` stops,
because the patch file changed:

```text
error: patches/requests/0001-fix.patch was already applied to requests but its content has changed since then; use --force to reset requests and apply it again
```

> [!WARNING]
> Always add `-p`. Without it, `--force` resets **every** patched package
> in the venv, also those in other patches files.

## Edit in the package, then save the patch

You can also change the files right in the package folder. It is a git
repository, so you can commit there and save the patch. For a package with
no patch yet, list it without `path` first. See
[Write a patch](write-a-patch.md#in-the-package-folder).

```bash
cd "$(python -c 'import requests, pathlib; print(pathlib.Path(requests.__file__).parent)')"
venv-patcher reset -p requests      # start from the initial commit
# edit files ...
git add -A
git commit -m "Fix the timeout handling"
git format-patch -1 -o ~/project/patches/requests
```

Then apply it the normal way, so the manifest knows about it:

```bash
cd ~/project
venv-patcher apply --force -f patches.yml -p requests
```

`--force` drops your manual commit and applies the saved patch instead.

## When it is done

Pin it, so it can not change by mistake. See
[Pin a patch with sha256sum](pin-sha256.md).
