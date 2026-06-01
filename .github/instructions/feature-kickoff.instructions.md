---
applyTo: "**"
---

# Feature Kickoff — Always-On Rules

These rules are active during any feature development conversation. They enforce plan-before-code discipline, prevent assumption-driven development, and ensure incremental, reviewable output.

---

## 1. Never Assume — Always Confirm

**Scope.** Do not assume what files exist, what patterns are used, or what a variable means. Read the actual source before stating something as fact. If you haven't read the file, say so and read it first.

**Intent.** If the user's request is ambiguous, ask clarifying questions before proposing a solution. Never fill gaps with guesswork.

**Out of scope.** Do not silently expand the feature. If a change naturally leads to a second change, flag it and ask — do not bundle it.

**Existing patterns.** Study how similar features are implemented before proposing a new approach. Consistency with the codebase matters more than personal preference.

**Explicit prior requests.** If the user previously made an explicit decision or request about how something should work (e.g. "use MarkdownV2", "keep the old behavior", "do not change X"), you MUST NOT override or revert that decision on your own authority. Stop, explain the conflict, and ask the user for direction before proceeding.

---

## 2. Plan Before Code

**No implementation without a plan.** Before writing any code, you must propose:
- What files will be created or modified
- What domain concepts are involved (entities, value objects, services, repositories)
- What dependencies exist between steps

**No plan without a spec.** Before proposing a plan, you must restate the feature as a short spec with acceptance criteria. Wait for the user to confirm the spec before moving to the plan.

**No plan execution without approval.** Wait for the user to explicitly approve the plan before implementing anything.

---

## 3. Incremental Delivery

**One logical unit per step.** Each step must be a single concern — one class, one function, one file change. The user should be able to read one diff and understand it without seeing the next step.

**Each step must be independently reviewable.** No "I'll fix this later" or "this will make sense in step 3."

**Summarize after each step.** After making a change, state:
1. What changed and why
2. What step comes next
3. How this step unblocks the next

**Wait for the go-ahead.** Do not start the next step until the user confirms.

---

## 4. Code Quality — Non-Negotiable Standards

These rules apply to every line of code. Do not ask permission for them.

### Domain & Design

- Entities own their invariants and state transitions. No anemic models (data bags with external validation).
- Value objects are immutable (`@dataclass(frozen=True)`). Validate in `__post_init__`.
- Use `Protocol` for dependency interfaces (not ABC unless shared state is needed).
- Repositories return domain objects — never raw dicts, rows, or ORM results to the domain layer.
- Business logic lives in the domain layer, never in controllers, route handlers, or infrastructure.

### Naming

- Names reflect domain concepts, not technical roles: `PendingOrderPolicy` not `OrderManager`.
- No vague names: never `result`, `data`, `info`, `temp`, `obj`, `val`.
- Functions: commands use `verb_noun`; queries use `get_`, `find_`, `is_`, `has_`.
- Booleans read as questions: `is_active`, `has_pending_items`, `can_be_cancelled`.
- Collections use the plural: `orders`, `line_items`.

### Type Safety

- Complete type hints on every function signature and class attribute.
- `Optional[T]` for nullable values. Never implicit `None`.
- `TypedDict` for dicts with known structure. `Enum` for fixed value sets. `Protocol` for interfaces.
- No bare `Any`. If unavoidable, document why in a comment.

### Error Handling

- Use specific exception subclasses. Never raise bare `Exception`.
- Never swallow silently: every `except` block must log with context or re-raise.
- Wrap infrastructure exceptions to preserve the cause chain (`raise DomainError(...) from e`).
- Include relevant identifiers in error messages: `f"Order {order_id} cannot be confirmed: status is {order.status}"`.

### Logging

- Structured logging with context: `logger.info("order_confirmed", extra={"order_id": order_id})`.
- Never interpolate values into the log message string.
- Appropriate levels: DEBUG (diagnostics), INFO (normal ops), WARNING (recoverable), ERROR (failure).
- Never log secrets, tokens, or PII.

### Anti-Patterns — Must Avoid

- Catch-all `except Exception: pass`
- Boolean trap parameters — split into separate functions instead
- Unnecessary `else` after `return` or `raise`
- Docstrings that restate the function name — describe behavior, preconditions, and exceptions
- Comments that describe WHAT the code does — only WHY it does it
- `print()` in production paths — use structured logging
- Hardcoded URLs, ports, credentials, or magic numbers — use named constants or typed config
- Vague intermediate variables — name every variable after what it represents
- Mid-file imports — all imports at the top, grouped: stdlib → third-party → local → relative

### Security

- No secrets in source code. Use environment variables with typed config objects.
- Validate all external input at system boundaries. Fail fast on invalid input.
- Parameterized queries only. Never string-interpolate user input into SQL.
- Never log credentials, tokens, API keys, or PII.

---

## 5. Calibration — Right-Sizing the Solution

**The Rule of Three:**
- First occurrence: implement inline. Do not abstract.
- Second occurrence: note the duplication.
- Third occurrence: extract the abstraction.

Do not abstract on the first or second occurrence.

**Signs of over-engineering (stop and simplify):**
- More abstraction layers than concrete use cases
- Interfaces with a single implementation and no planned second
- Generic solutions to specific problems
- Factories for things that could be constructors

**Signs of under-engineering (stop and strengthen):**
- Business logic in controllers or route handlers
- No error handling on I/O operations
- Raw primitives where a domain concept belongs
- No tests on critical paths

---

## 6. Testability

- Every new function or class must be testable in isolation. Dependencies are injected via the constructor, not instantiated internally.
- Mock only I/O boundaries (database, HTTP, filesystem, clock). Never mock domain objects or value objects.
- Tests follow Arrange/Act/Assert and use domain language, not implementation details.
- Test names follow: `test_should_[behaviour]_when_[condition]`.

---

## 7. When Rules Conflict

- Domain clarity beats brevity.
- Correctness beats performance (until measured otherwise).
- Consistency with the codebase beats personal preference.
- Simplicity beats generality (unless generality is an explicit requirement).
