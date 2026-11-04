# Repository tools

[English](repository-tools.md) · [简体中文](zh-CN/repository-tools.md) · [Documentation](README.md)

Give a coding agent its own Git worktree and a named test command. The source checkout stays available while the agent reads files, writes changes, runs checks and returns a patch.

Install Git on the worker's `PATH`. Set an environment variable to your local repository, then configure a `repository` binding for each operation:

```yaml
tools:
  repository.check:
    kind: repository
    name: repository.check
    operation: check
    repository_env: AGENT_REPOSITORY
    checks:
      unit: [python, -m, pytest, -q]
    timeout_seconds: 120
```

| Operation | Input | Result |
| --- | --- | --- |
| `open` | `{}` | Worktree ID and pinned base commit |
| `list` | `workspace` | Tracked and new files |
| `read` | `workspace`, `path` | UTF-8 content and SHA-256 |
| `write` | `workspace`, `path`, `content`, `expected_sha256` | Saved file hash; use `null` for a new file |
| `diff` | `workspace` | Patch including new files, with its hash |
| `check` | `workspace`, `check` | Exit status, bounded output and hash of the tested patch |

Set `editable_paths` on write bindings to filenames or directory prefixes ending in `/`. `base` defaults to `HEAD`; the first `open` pins its commit. Worktrees and operation receipts live in the application workspace and survive restarts. Replaying a completed write or check returns its original receipt. An interrupted check requires reconciliation before another attempt.

Check commands are argv lists configured by the deployer. The tool starts them without a shell, limits execution time and captured output, and terminates their process group when they finish. It forwards `PATH`, `SYSTEMROOT` and `LD_LIBRARY_PATH`; configure required test settings in the worker. Tests execute repository code: deploy the worker inside your container or sandbox when that code is untrusted. Git worktrees separate changes; the container supplies process and filesystem isolation.

Use [event triggers](triggers.md) to accept repository tasks once per delivery, and human nodes to review the resulting patch. The [repository agent](../examples/repository-agent/) combines these tools with triage, implementation and review agents.

`timeout_seconds` limits each configured check. `git_timeout_seconds` separately limits Git operations; both default to 120 seconds. A short check budget therefore still allows time to collect its patch and result.
