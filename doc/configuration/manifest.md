# The manifest

The manifest is where venv-patcher records what it did. It is a JSON file
in the site-packages folder of the venv:

```text
.venv/lib/python3.12/site-packages/.venv-patcher-manifest.json
```

You do not edit it. [`apply`](../cli/apply.md) and
[`reset`](../cli/reset.md) write it. [`list`](../cli/list.md) shows it.

Because it lives in the venv, each venv has its own manifest. Delete the
venv, and the manifest is gone too.

## Example

```json
{
  "packages": {
    "idna": {
      "initial_commit": "0918fb5dfcf7de56319409d7e853cdf7b8c18a8b",
      "location": "/home/me/demo/.venv/lib/python3.12/site-packages/idna",
      "patches": [
        {
          "applied_at": "2026-10-18T09:37:20.615286+00:00",
          "apply_command": "git am",
          "patch_sha256": "625d70c05b1268bb99b5efbc82eaaf76ef615ecd20e3ace58048a608dad26f3e",
          "path": "patches/idna/0001-Mark-idna-as-patched.patch",
          "resolved_path": "/home/me/demo/patches/idna/0001-Mark-idna-as-patched.patch",
          "source_file": "/home/me/demo/patches.yml",
          "status": "applied"
        }
      ]
    }
  }
}
```

## Fields of a package

| Field | Meaning |
|---|---|
| `location` | the package folder |
| `initial_commit` | the commit with the package as installed. `null` until the first `git init` worked |
| `patches` | one result per apply, oldest first |

## Fields of a patch result

| Field | Meaning |
|---|---|
| `status` | `applied` or `failed` |
| `path` | `path` as written in the patches file |
| `resolved_path` | the full path of the patch file |
| `source_file` | the full path of the patches file |
| `apply_command` | the apply command that was used |
| `applied_at` | when, in UTC |
| `patch_sha256` | the hash of the patch file. Only for `applied` |
| `error` | what went wrong. Only for `failed` |

Older manifests name `source_file` as `source_yaml`. `list` reads both.

## How it is used

- `apply` and `reset` first check that the package files still match the
  last commit. If not, pip or someone else changed them.
- `apply` skips a patch when there is an `applied` result with the same
  `resolved_path` and the same `patch_sha256`.
- `apply` does `git init` only when `initial_commit` is `null`.
- `reset` goes back to `initial_commit` and empties `patches`.

The file is written to a temporary file first, then renamed. So it is never
half written.
