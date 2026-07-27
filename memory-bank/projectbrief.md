# Project Brief

## Current Verified State

This repository snapshot currently contains AI-agent workflow infrastructure, not the full application source tree.

Verified items:

- Root instructions file: `AGENTS.md`
- Local skill installation: `.agents/skills/`
- Mirrored upstream skill source: `vendor/mattpocock-skills/`
- Mirrored upstream memory source: `vendor/agent-memory/`
- Project-local memory docs: `memory-bank/`
- Project-local machine memory layout: `.agent-memory/`

## Scope Of This Setup

The current integration establishes:

1. persistent project memory
2. mandatory agent startup rules
3. a place to record recurring bugs and constraints
4. a documented path to use `axiomhq/agent-memory` locally

## Unverified Areas

The actual application source layout and runtime stack are not present in the current workspace snapshot, so they must not be assumed without further inspection.
