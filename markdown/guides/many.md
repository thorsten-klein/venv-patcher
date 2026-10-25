# Many packages and files

## One file, many packages

One patches file can patch many packages:

```yaml
version: 1
patches:
  - package: requests
    path: patches/requests/0001-fix.patch
  - package: urllib3
    path: patches/urllib3/0001-fix.patch
```

Entries are applied in order. Each package gets its own git repository and
its own initial commit.

A folder for each package keeps it tidy:

```text
patches.yml
patches/
  requests/
    0001-fix.patch
  urllib3/
    0001-fix.patch
```

## Many files

Pass `-f` more than once:

```bash
venv-patcher apply -f patches/base.yml -f patches/dev.yml
```

Files are applied in that order. Each `path` is relative to its own
patches file. YAML and TOML can be mixed.

One use: a base file for every venv, and an extra file only for
development.

## Only some packages

```bash
venv-patcher apply -f patches.yml -p requests -p urllib3
venv-patcher reset -p requests
```

`-p` uses the `package` name, the name you import.

## A package that is not always installed

By default, `apply` stops at the first package it can not import. Use
`--skip-missing` to skip it and go on:

```bash
venv-patcher apply -f patches.yml --skip-missing
```

The exit status is still `1`, and `list` shows the skipped entry as
`[FAIL]`. If that is a problem in a script, split the file and pass only
the files that fit that venv.
