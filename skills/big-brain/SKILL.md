---
name: big-brain
description: Use automatic project memory in coding-agent sessions. Loads context from the Big Brain global Markdown vault and captures durable rules, decisions, requests, bugs, features, and project context.
---

# Big Brain

Use Big Brain automatically during development conversations when the
`big-brain` command is available.

## Automatic Hooks

The plugin hooks run without user action:

- `SessionStart`: initializes the project if needed and refreshes
  `~/.big-brain/agent-context.md`.
- `SessionEnd`: captures durable notes from the session transcript when the
  agent runtime provides a transcript path.
- `PreCompact`: captures durable notes before automatic compaction.

## Agent Behavior

At the start of a repository task, run Big Brain yourself before reading or
editing code:

```bash
big-brain context
```

Use that output and `~/.big-brain/agent-context.md` as project memory. When the
user states something durable, immediately capture the exact relevant text:

```bash
printf '%s\n' "Decidimos usar SQLite local." | big-brain capture --stdin
```

Before the final answer, capture any durable rule, decision, request, bug, or
feature that was not saved yet.

Do not ask the user to run Big Brain. Do not start `big-brain chat` inside an
existing agent conversation.
