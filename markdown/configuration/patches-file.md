# The patches file

The patches file lists your patches. You write it, and pass it to
[`apply`](../cli/apply.md) with `-f`.

- It is YAML or TOML. A file ending in `.toml` is TOML. Any other file is
  YAML.
- TOML needs Python 3.11 or newer. On older Pythons a `.toml` file stops
  with an error.
- It has a `version` and a list of `patches`.

## YAML

```yaml
version: 1
patches:
  - package: requests
    path: patches/requests/0001-fix.patch
    sha256sum: 625d70c05b1268bb99b5efbc82eaaf76ef615ecd20e3ace58048a608dad26f3e
    apply-command: git am
    author: Jane Doe
    email: jane@example.com
    date: 2024-01-01T00:00:00+00:00
    comments: Fix the timeout handling
```

## TOML

```toml
version = 1

[[patches]]
package = "requests"
path = "patches/requests/0001-fix.patch"
sha256sum = "625d70c05b1268bb99b5efbc82eaaf76ef615ecd20e3ace58048a608dad26f3e"
apply-command = "git am"
author = "Jane Doe"
email = "jane@example.com"
date = "2024-01-01T00:00:00+00:00"
comments = "Fix the timeout handling"
```

Both files mean the same. The repository has a full example of each:
[`example.yml`](https://github.com/thorsten-klein/venv-patcher/blob/main/example.yml)
and [`example.toml`](https://github.com/thorsten-klein/venv-patcher/blob/main/example.toml).

## Top level

| Field     | Required   | Meaning                                                   |
|-----------|------------|-----------------------------------------------------------|
| `version` | yes        | the format version. Must be `1`                           |
| `patches` | no         | the list of entries. Empty or missing means nothing to do |

## Fields of an entry

| Field               | Required   | Default                           |
|---------------------|------------|-----------------------------------|
| [`package`]()       | yes        |                                   |
| [`path`]()          | no         | no patch: only set up git         |
| [`sha256sum`]()     | no         | no check                          |
| [`apply-command`]() | no         | `git am`                          |
| [`author`]()        | no         | `venv-patcher`                    |
| [`email`]()         | no         | `venv-patcher@localhost`          |
| [`date`]()          | no         | `1970-01-01T00:00:00+00:00`       |
| [`comments`]()      | no         | `venv-patcher: apply <file name>` |

Other fields are ignored.

### `package`

The importable name of the package, for example `requests` or `yaml`. This
is the name you `import`, not always the name you `pip install`.

venv-patcher imports it to find its folder. It must be a package folder. A
single `.py` file right in site-packages, like `six.py`, does not work.

### `path`

The patch file. A relative path is relative to the folder of the patches
file. An absolute path is used as it is.

Leave `path` out to only set up git for the package, with no patch:

```yaml
version: 1
patches:
  - package: requests
```

`apply` then runs `git init` in the package folder and makes the initial
commit. Nothing else changes. Use this to start a new patch right in the
package folder. See [Write a patch](../guides/write-a-patch.md#in-the-package-folder).

The paths inside the patch must be relative to the package folder. See
[Write a patch](../guides/write-a-patch.md).

### `sha256sum`

The SHA-256 hash of the patch file. If set, `apply` refuses a patch file
with another hash:

```text
error: sha256 mismatch for patches/0001-fix.patch (expected 625d…, got 9a1f…)
```

Get it with:

```bash
sha256sum patches/requests/0001-fix.patch
```

See [Pin a patch with sha256sum](../guides/pin-sha256.md).

### `apply-command`

The command that applies the patch. venv-patcher runs it in the package
folder and adds the patch file path at the end.

| Value           | Use it for                                             |
|-----------------|--------------------------------------------------------|
| `git am`        | a patch from `git format-patch`. The default           |
| `git apply`     | a plain diff, for example from `diff -u` or `git diff` |
| `git apply -p3` | a diff whose paths have 2 extra folders in front       |

The value is split like a shell command line, so you can add options. It
is not run in a shell: pipes and `$VARS` do not work.

### `author`

The name for the commits. See [`date`]().

### `email`

The email for the commits. See [`date`]().

### `date`

The date for the commits, for example `2024-01-01T00:00:00+00:00`.

A date alone, like `2024-01-01`, gets the time `00:00:00` UTC. So it
becomes `2024-01-01T00:00:00+00:00`.

`author`, `email` and `date` are pinned for the commit. So the same patch
always gives the same commit hash.

- With `git apply`, they set the author and the committer.
- With `git am`, the author and the author date come from the patch file.
  These fields then only set the committer.

### `comments`

The commit message. It is only used when venv-patcher makes the commit
itself, for example with `git apply`. `git am` takes the message from the
patch.

## Several files

You can pass more than one file:

```bash
venv-patcher apply -f base.yml -f local.toml
```

They are applied in that order. Each file can use YAML or TOML. See
[Many packages and files](../guides/many.md).
