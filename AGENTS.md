# AGENTS.md

Instructions for any AI coding agent working in this repository.

## Mandatory Startup

Before starting any task, the agent must read these files in order:

1. `AGENTS.md`
2. `docs/agent-rules.md`
3. `docs/agent-memory-integration.md`
4. `memory-bank/quick-start.md`
5. `memory-bank/activeContext.md`
6. `memory-bank/progress.md`
7. `memory-bank/projectRules.md`
8. `memory-bank/techContext.md`

If the task touches architecture, recurring bugs, or cross-cutting behavior, also read:

1. `memory-bank/systemPatterns.md`
2. `memory-bank/bugPatterns.md`
3. Relevant files in `docs/`

If any required file is missing, stale, or contradicted by the codebase, the agent must say so explicitly and update the Memory Bank as part of the task.

Before making any substantive change, the agent must explicitly confirm in its working notes or user update:

- which required files were read
- what is verified versus unverified
- whether `memory-bank/bugPatterns.md` contains relevant prior failures
- whether a `.agent-memory` capture will be written at the end of the task

## Non-Negotiable Rules

1. Do not guess.
If something is not verified from code, tests, commands, or a cited document, mark it as unverified and inspect first.

2. Reuse before creating.
Search for existing files, patterns, and commands before proposing new structure.

3. Read old bugs before changing behavior.
Consult `memory-bank/bugPatterns.md` before fixing or extending logic in an area with prior defects.

4. Convert every fixed bug into memory.
After resolving a bug, add the trigger, root cause, fix, and regression guard to `memory-bank/bugPatterns.md`.

5. Keep project memory current.
When a task changes architecture, constraints, workflow, or known risks, update the relevant Memory Bank files in the same task.

6. Cite evidence.
When making technical claims, prefer file references, command output, or source links over generic statements.

7. Follow the project tech stack source of truth.
Use `memory-bank/techContext.md`. If the stack in code differs from that document, update the document instead of silently assuming.

8. Preserve coding style.
Match naming, file placement, framework conventions, and test patterns already used in the repository.

## Memory System

This project integrates the ideas from `axiomhq/agent-memory` as a project-local memory workflow:

- Project memory root: `.agent-memory/`
- Long-lived documentation root: `memory-bank/`
- Upstream source mirror: `vendor/agent-memory/`
- Operator guide: `docs/agent-memory-integration.md`

Agents should treat the Memory Bank as the durable project brain and `AGENTS.md` as the always-in-context startup contract.

Companion entrypoints for editor plugins:

- `CLAUDE.md`
- `GEMINI.md`

These files defer back to `AGENTS.md` so Codex, Claude Code, and Gemini can share one canonical contract.

## Mandatory Memory Actions

At task start, the agent must:

1. read `docs/agent-rules.md`
2. read `docs/agent-memory-integration.md`
3. read `memory-bank/activeContext.md`
4. read `memory-bank/progress.md`
5. check whether `memory-bank/bugPatterns.md` is relevant
6. read `.agent-memory/orgs/default/output-agents.md` if it contains generated memory

At task end, if the task produced durable knowledge, the agent must do both:

1. update the relevant files in `memory-bank/`
2. write a journal entry into `.agent-memory/inbox/`

Preferred command for journal capture:

```bash
scripts/agent-memory-capture.sh --title "<task title>" --body "<durable summary>"
```

Preferred wrapper for task close:

```bash
bash scripts/agent-task-close.sh --agent codex --title "<task title>" --summary "<durable summary>"
```

If the agent skips journal capture, it must state why the task did not create durable knowledge.

## Skills

Local skills are installed in `.agents/skills/`.
Each skill directory may contain:

- `SKILL.md`
- `agents/openai.yaml`

Notable installed skills:

- `diagnose`
- `grill-with-docs`
- `handoff`
- `improve-codebase-architecture`
- `setup-matt-pocock-skills`
- `tdd`
- `to-issues`
- `to-prd`
- `triage`
- `zoom-out`

## Session Output Expectations

At the start of substantial work, the agent should confirm:

- which Memory Bank files were read
- what is verified vs unverified
- which prior bug patterns are relevant
- what constraints from `projectRules.md` apply

At the end of substantial work, the agent should update Memory Bank files if new durable knowledge was learned.
