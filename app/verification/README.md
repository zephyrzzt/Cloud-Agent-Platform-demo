# Verification

The verification layer checks task evidence before the orchestrator marks a run as successful.

The first implementation is rule-based and deterministic:

- Confirm the agent reached a completed state.
- Require `finish_task` for tool-backed tasks.
- Require artifacts when the prompt or metadata asks for reports, files, summaries, or saved output.
- Require a successful controlled command tool (`run_test`, `run_lint`, `run_build`, `run_compile`, or `run_program`) when the prompt or metadata asks to run commands or tests.
- Store verification checks in task result metadata.

Keyword detection intentionally uses English ASCII keywords only. For non-English prompts, set metadata flags explicitly so verification remains deterministic.

Task metadata can override detection:

```json
{
  "requires_artifact": true,
  "requires_command": true,
  "expected_artifacts": ["report.md"]
}
```

This module is intentionally provider-neutral. It validates platform evidence such as tool results and artifact files, not model self-assessments.
