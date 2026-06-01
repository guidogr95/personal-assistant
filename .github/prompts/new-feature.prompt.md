---
description: Start work on a new feature with disciplined planning, confirmation gates, and incremental delivery.
requires:
  - path: "instructions/feature-kickoff.instructions.md"
    reason: "enforces plan-before-code discipline and confirmation gates"
suggests:
  - path: "agents/feature-builder.agent.md"
    reason: "guided agent that orchestrates this prompt's workflow with inline critique and handoffs to poc-architect, plan-to-docs, and senior-engineer"
  - path: "skills/poc-architect/SKILL.md"
    reason: "critiques architecture decisions in the plan before implementation begins"
  - path: "skills/senior-engineer-python/SKILL.md"
    reason: "enforces Python code quality during implementation steps"
  - path: "skills/senior-engineer-javascript/SKILL.md"
    reason: "enforces JavaScript/TypeScript code quality during implementation steps"
---

You are working on a new feature in this codebase. Before writing a single line of code, follow this workflow exactly.

---

## Step 1 — Gather Missing Context

If I haven't already provided ALL of the following, ask me for each missing piece one category at a time. Do not proceed until every category is covered.

### Required Context

1. **Feature goal** — one sentence. What does this enable that isn't possible today?
2. **Acceptance criteria** — testable bullets. How do we know it's done? Include edge cases and error conditions, not just the happy path.
3. **Relevant existing code** — which files, classes, or patterns should I study before proposing a plan? What in the codebase already does something similar?
4. **Explicit out-of-scope** — what are we deliberately NOT doing in this feature? Prevents scope creep.
5. **Output style** — do you want me to show diffs inline, describe changes at a high level, or both? Do you want before/after comparisons?

For anything I've already provided in my prompt, skip it. Only ask for what's missing.

---

## Step 2 — Restate as Short Spec

Once context is complete, restate the feature as a short spec with this structure:

```
## Spec: [Feature Name]

**Goal:** [one sentence]

**Acceptance criteria:**
- [ ] [testable criterion 1]
- [ ] [testable criterion 2]

**Out of scope:**
- [explicit exclusion 1]
- [explicit exclusion 2]

**Key constraints from codebase:**
- [relevant existing pattern, interface, or convention]
```

Wait for my explicit confirmation before proceeding. Do not skip this gate.

---

## Step 3 — Propose Implementation Plan

After I confirm the spec, propose a step-by-step implementation plan. Each step must be:

- **One logical unit** — a single concern (one class, one function, one file change)
- **Independently reviewable** — I should be able to read the diff for one step and understand it without seeing the next
- **Ordered by dependency** — foundational pieces first, integration last

For each step, specify:
- Files to create or modify (with expected path)
- What changes within each file (domain concept, interface, implementation, test)
- How it connects to the previous step

Format:

```
## Plan

### Step 1: [short title]
- Create `src/path/to/file.py`
- Define [Protocol / dataclass / entity] for [concept]
- [One sentence on what it enables]

### Step 2: [short title]
- Modify `src/path/to/existing.py`
- [What changes, why it depends on Step 1]

[...remaining steps...]
```

Wait for my explicit approval before implementing anything. Do not skip this gate.

---

## Step 4 — Implement Incrementally

Implement exactly one step at a time. After each step:

1. **Make the change** — edit/create only the files in that step
2. **Summarize what was done** — what changed, why, and what it enables
3. **State what comes next** — which step is next and how this step unblocks it
4. **Wait for my go-ahead** before starting the next step

### Implementation standards (from senior-engineer skill)

Every code change must follow these rules. Do not ask permission for these — they are non-negotiable.

**Domain & Design:**
- Entities own their invariants and state transitions. No anemic models.
- Value objects are immutable (`@dataclass(frozen=True)`). Validate in `__post_init__`.
- Use `Protocol` for dependency interfaces, not concrete base classes.
- Repositories return domain objects, never raw dicts or rows.
- No business logic outside the domain layer.

**Naming:**
- Variables and classes named after domain concepts, not technical roles.
- No `OrderManager`, `DataHandler`, `ServiceHelper`, `Utils`.
- Functions: commands are `verb_noun`; queries are `get_`, `find_`, `is_`, `has_`.
- No vague names: never `result`, `data`, `info`, `temp`, `obj`, `val`.

**Type Safety:**
- Complete type hints on every function and class attribute. No bare `Any`.
- `Optional[T]` for nullable values. `TypedDict` for structured dicts. `Enum` for fixed value sets.

**Error Handling:**
- Specific exception subclasses (`DomainError`, `InfrastructureError`). Never bare `Exception`.
- Never swallow exceptions silently. Always log with structured context before re-raising.
- Wrap infrastructure exceptions to preserve the cause chain (`raise X from e`).

**Logging:**
- Structured logging: `logger.info("event_name", extra={"key": value})`. Never f-strings in log messages.
- Appropriate levels: DEBUG for diagnostics, INFO for normal operations, WARNING for recoverable, ERROR for failures.

**Anti-Patterns to Avoid:**
- No catch-all `except Exception: pass`
- No boolean trap parameters — split into separate functions
- No unnecessary `else` after `return` or `raise`
- No docstrings that restate the function name
- No comments that describe WHAT the code does (only WHY)
- No print() — use structured logging
- No hardcoded values — extract to typed config or named constants
- No N+1 queries in loops
- No blocking I/O in async context

**Security:**
- No secrets in source code. Validate all external input at system boundaries.
- Never log credentials, tokens, or PII.

---

## Step 5 — Wrap Up

After the final step is approved and implemented:

1. List every file changed with a one-line summary of what changed
2. Propose what tests should cover (Arrange/Act/Assert structure, domain language, mock only I/O boundaries)
3. Flag anything that should be revisited after the Rule of Three (first occurrence: inline; second: note the duplication; third: extract the abstraction)
