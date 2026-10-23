# Pin a patch with sha256sum

`sha256sum` makes sure a patch file is exactly the one you checked. If the
file changes, `apply` refuses it.

## Pin it

Get the hash:

```bash
sha256sum patches/requests/0001-fix.patch
```

```text
625d70c05b1268bb99b5efbc82eaaf76ef615ecd20e3ace58048a608dad26f3e  patches/requests/0001-fix.patch
```

Add it to the entry:

```yaml
version: 1
patches:
  - package: requests
    path: patches/requests/0001-fix.patch
    sha256sum: 625d70c05b1268bb99b5efbc82eaaf76ef615ecd20e3ace58048a608dad26f3e
```

## When the file changes

```text
error: sha256 mismatch for patches/requests/0001-fix.patch (expected 625d…, got 9a1f…)
```

The patch is not applied. The failure is recorded in the manifest.

Check what changed. If the change is fine, put the new hash into the
patches file.

## When to pin

- **Pin** a patch that is done. It protects you from a patch file that was
  changed by mistake, or on purpose.
- **Do not pin yet** while you still work on a patch. See
  [Work on a patch](iterate.md).

> [!TIP]
> Line endings change the hash. If git may change them on checkout, add
> `*.patch -text` to your `.gitattributes`.

## Without a pin

venv-patcher still records the hash of each patch it applied. On the next
`apply` it compares the file with that hash:

- the same: the patch is skipped;
- changed: `apply` stops and asks for `--force`.

So a changed patch is never applied on top of the old one.
