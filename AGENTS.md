# Instructions for AI tools

## Write short and easy

This applies to all docs, code comments, docstrings, commit messages,
issues and pull requests.

- Use short sentences and common words.
- Say one thing per sentence.
- Leave out what the reader does not need.
- Show a command, then say what it does.
- No long intros, no filler, no marketing words.

## Checks

Run every check before you commit:

```bash
uv sync
uv run poe all
```

Tests need 100% line coverage. Python 3.9 is the oldest supported version.
