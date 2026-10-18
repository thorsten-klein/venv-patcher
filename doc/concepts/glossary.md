# Glossary

The words venv-patcher uses, in short.

**venv**
: A Python virtual environment. venv-patcher only works inside one, and
  only patches the venv it runs in.

**site-packages**
: The folder of the venv where packages are installed. The manifest lives
  here too.

**package**
: An importable name, such as `requests`. venv-patcher imports it to find
  its folder. It must be a folder, not a single `.py` file.

**package folder**
: The folder a package is installed in, for example
  `.venv/lib/python3.12/site-packages/requests/`. venv-patcher turns it into
  a git repository.

**patch**
: A file with changes to a package. Either from `git format-patch` (for
  `git am`) or a plain diff (for `git apply`). Its paths are relative to the
  package folder.

**patches file**
: A YAML or TOML file that lists patches and the package each one is for.
  You write it. See [The patches file](../configuration/patches-file.md).

**entry**
: One item in the `patches` list of a patches file. It names one patch and
  one package.

**apply command**
: The command that applies a patch. `git am` by default. Set with
  `apply-command`.

**initial commit**
: The first commit in a package folder. It holds the package as it was
  installed. `reset` goes back to it.

**patch commit**
: The commit a patch makes on top of the initial commit.

**manifest**
: The file `.venv-patcher-manifest.json` in site-packages. It records each
  package, its initial commit and each patch result. See
  [The manifest](../configuration/manifest.md).

**pinned identity**
: The fixed author, email and date that venv-patcher gives to its commits.
  It makes them the same on every run.

**sha256sum**
: The SHA-256 hash of a patch file. If you set it, venv-patcher only applies
  a patch file with exactly that hash.
