# Compared to other ways

There are other ways to change a package you depend on. This page compares
them.

## At a glance

|                                        | venv-patcher     | fork                | monkey patch   | vendoring   | edit by hand   |
|----------------------------------------|------------------|---------------------|----------------|-------------|----------------|
| Change is a normal patch file          | yes              | no, a repository    | no, code       | no, a copy  | no             |
| Works with the normal `pip install`    | yes              | no, needs your fork | yes            | no          | yes            |
| Easy to see what is changed            | `list`           | `git diff` upstream | read the code  | `git diff`  | no             |
| Easy to undo                           | `reset`          | reinstall           | remove code    | reinstall   | reinstall      |
| Same result on every machine           | yes              | yes                 | yes            | yes         | no             |
| Changes any file, not only Python code | yes              | yes                 | no             | yes         | yes            |
| Work to keep it up to date             | rebase the patch | rebase the fork     | check the code | copy again  | do it again    |

## Fork

You copy the project, fix it, and install from your copy:

```bash
pip install git+https://github.com/you/requests@fix
```

This is fine for big changes. For a small fix it is a lot: a repository to
keep, releases to follow, and a new install source for everyone.

With venv-patcher you keep only the patch file. The package still comes
from PyPI.

## Monkey patch

You replace a function at runtime:

```python
import requests.utils
requests.utils.some_function = my_fixed_function
```

This needs no tools. But it only works for Python code, it runs on every
import, and it breaks quietly when the package changes.

venv-patcher changes the files once. A patch that no longer fits fails
loudly.

## Vendoring

You copy the package into your project. You own every line of it now, and
you have to copy it again for each update.

## Edit by hand

You change the files in site-packages. It is quick. But nobody can see it,
and the next install or a new venv loses it.

venv-patcher is this way, made safe: the change is a file in your project,
it is recorded, and it can be undone.

## When venv-patcher is not the right tool

- The change is large or long-lived. Send it upstream, or fork.
- You need the fix in a package you publish. Your users do not run
  venv-patcher.
- The package is a single `.py` file in site-packages, like `six`.
  venv-patcher only patches package folders.
