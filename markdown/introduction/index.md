# About venv-patcher

venv-patcher applies patches to packages that are installed in a Python
virtual environment (venv). It remembers what it did. So you can list your
patches, and undo them at any time.

## What problem does it solve?

Sometimes a package you use has a bug, and the fix is not released yet.
You have a few ways out:

- **Wait** for a release. That can take months.
- **Fork** the package and install your fork. Now you maintain a fork.
- **Monkey patch** it at runtime. That is hard to read and breaks easily.
- **Edit the files** in `site-packages` by hand. Nobody knows you did it,
  and the next `pip install` loses it.

venv-patcher makes the last way safe. You keep the fix as a normal patch
file next to your project. A small patches file says which patch goes to
which package:

```yaml
version: 1
patches:
  - package: requests
    path: patches/0001-fix.patch
```

Then one command applies it:

```bash
venv-patcher apply -f patches.yml
```

## How it works, in short

1. venv-patcher imports the package to find its folder.
2. The first time, it runs `git init` in that folder and commits the files
   as they are. This is the **initial commit**.
3. It applies your patch with `git am` (or `git apply`) and commits the
   result.
4. It writes what it did to a **manifest** in the venv.

`venv-patcher list` shows the manifest. `venv-patcher reset` goes back to
the initial commit.

[How it works](../concepts/how-it-works.md) explains each step.

## Why use it?

- **Plain git underneath.** Each patched package is a small git repository.
  You can look at it with `git log` and `git diff`.
- **Repeatable.** The same patch on the same package always gives the same
  commit. The commit names and dates are fixed.
- **Safe.** It checks the patch with `sha256sum` if you want. It will not
  apply a changed patch on top of an old one.
- **Undo at any time.** `reset` puts the package back as it was installed.
- **Small.** It needs only git and PyYAML.

## Next steps

- [Install venv-patcher](install.md)
- [venv-patcher in 5 minutes](../quickstart/05-minutes.md)
