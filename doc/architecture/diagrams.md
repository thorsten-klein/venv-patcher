# Git call diagrams

Each diagram shows the git commands one `venv-patcher` command runs, in
order. It is the fastest way to see what a command really does.

Every git call runs in the package folder. Each one also gets
`gc.auto=0` and `maintenance.auto=false`.

---

## apply

```mermaid
sequenceDiagram
    participant User
    participant venv-patcher
    participant Manifest
    participant Git

    User->>venv-patcher: venv-patcher apply -f patches.yml
    Note over venv-patcher: Check: running in a venv
    venv-patcher->>Manifest: load
    opt --force
        Note over venv-patcher,Git: reset, as below, for -p packages or all
    end

    loop For each -f file
        Note over venv-patcher: Read YAML, or TOML on 3.11+<br/>Check version, package, path
        loop For each entry (filtered by -p)
            opt Has a path, package tracked
                venv-patcher->>Git: status --porcelain
                Note over venv-patcher: Changes? Record failure: use --force
            end
            alt No path: only git tracking
                Note over venv-patcher,Git: import package, then init and<br/>initial commit as below, once
            else Already applied (same resolved path)
                Note over venv-patcher: Same hash: warn, skip<br/>Other hash or gone: record failure
            else New
                Note over venv-patcher: import package, find its folder
                opt Not importable
                    venv-patcher->>Manifest: save failure
                    Note over venv-patcher: Stop, unless --skip-missing
                end

                opt No initial commit yet
                    venv-patcher->>Git: init -q
                    Note over venv-patcher: Add __pycache__/, *.pyc, *.pyo<br/>to .gitignore
                    venv-patcher->>Git: add .
                    venv-patcher->>Git: commit -q -m initial --allow-empty
                    Note over Git: name venv-patcher, date 1970-01-01
                    venv-patcher->>Git: rev-parse HEAD
                    venv-patcher->>Manifest: save initial commit
                end

                Note over venv-patcher: Patch file exists?<br/>sha256sum matches?
                venv-patcher->>Git: <apply-command> <patch file>
                Note over Git: default: git am<br/>pinned author, email, date
                venv-patcher->>Git: status --porcelain
                opt Changes left (e.g. git apply)
                    venv-patcher->>Git: add -A
                    venv-patcher->>Git: commit -q -m <comments>
                end
                opt Apply or commit failed
                    Note over venv-patcher: .git/rebase-apply there?
                    venv-patcher->>Git: am --abort
                    venv-patcher->>Git: reset -q --hard HEAD
                    venv-patcher->>Git: clean -q -fd
                end
                venv-patcher->>Manifest: save applied or failed
            end
        end
    end
```

---

## list

`list` runs no git command. It only reads the manifest.

```mermaid
sequenceDiagram
    participant User
    participant venv-patcher
    participant Manifest

    User->>venv-patcher: venv-patcher list
    Note over venv-patcher: Check: running in a venv
    venv-patcher->>Manifest: load
    loop For each package, sorted
        Note over venv-patcher: Print folder, initial commit,<br/>each result [OK] or [FAIL]
    end
```

---

## reset

```mermaid
sequenceDiagram
    participant User
    participant venv-patcher
    participant Manifest
    participant Git

    User->>venv-patcher: venv-patcher reset [-p <package>]
    Note over venv-patcher: Check: running in a venv
    venv-patcher->>Manifest: load
    loop For each package (filtered by -p)
        Note over venv-patcher: Skip if no folder or no initial commit<br/>Warn if the folder is gone
        venv-patcher->>Git: status --porcelain
        alt Changed outside (e.g. pip upgrade)
            Note over venv-patcher: Remove .git, keep the files
            venv-patcher->>Manifest: no initial commit, empty patches, save
        else Unchanged
            opt .git/rebase-apply there
                venv-patcher->>Git: am --abort
            end
            venv-patcher->>Git: reset -q --hard <initial commit>
            venv-patcher->>Git: clean -q -fd
            venv-patcher->>Manifest: empty patches, save
        end
    end
```
