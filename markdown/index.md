# venv-patcher

<img src="https://raw.githubusercontent.com/thorsten-klein/venv-patcher/main/doc/_static/logo.svg" alt="venv-patcher logo" width="500"/>

Patch the packages in your Python virtual environment. See what you
patched. Undo it at any time.

> [!NOTE]
> This site is also published as **plain Markdown**, one file per page.
> It is meant for AI tools. Start at
> <a href="markdown/index.md">markdown/index.md</a>.

## Introduction

Start here if you are new to venv-patcher.

- [About venv-patcher](introduction/index.md)
- [Install venv-patcher](introduction/install.md)

## Quickstart

Try it out in a few minutes.

- [venv-patcher in 5 minutes](quickstart/05-minutes.md)
- [Everyday tasks](quickstart/everyday.md)

## Concepts

The words venv-patcher uses, and how it works inside.

- [Glossary](concepts/glossary.md)
- [How it works](concepts/how-it-works.md)
- [Compared to other ways](concepts/comparison.md)

## `venv-patcher` command

The full reference of the command line. There is one page per command.

- [Overview and common options](cli/index.md)

| Command                 | What it does                        |
|-------------------------|-------------------------------------|
| [`apply`](cli/apply.md) | Apply the patches of a patches file |
| [`list`](cli/list.md)   | Show what is patched                |
| [`reset`](cli/reset.md) | Undo all patches                    |

## Configuration

What venv-patcher reads, and what it stores.

- [The patches file](configuration/patches-file.md)
- [The manifest](configuration/manifest.md)

## Guides

Step by step help for one task each.

- [Write a patch](guides/write-a-patch.md)
- [Use a patch from upstream](guides/upstream-patch.md)
- [Pin a patch with sha256sum](guides/pin-sha256.md)
- [Work on a patch](guides/iterate.md)
- [Many packages and files](guides/many.md)
- [Upgrade a patched package](guides/upgrade.md)
- [Use it in CI](guides/ci.md)

## Architecture

How the code is built, and which git commands each command runs.

- [Architecture](architecture/index.md)
- [Git call diagrams](architecture/diagrams.md)

## Contributing

- [Development](contributing/development.md)
- [Documentation](contributing/documentation.md)
