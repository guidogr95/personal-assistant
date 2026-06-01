---
applyTo: "**"
description: "Language-agnostic senior engineering standards. Always active. Enforces SOLID, DDD, naming, error handling, logging, testing, security, and code review methodology."
# suggests and requires below are GitSynapse metadata (used by git-synapse sync), not VS Code fields.
# VS Code ignores them. To load skills from agents, use Markdown links in the agent body instead.
suggests:
  - path: "skills/senior-engineer-python/SKILL.md"
    reason: "Python-specific type safety, anti-patterns, and idioms"
  - path: "skills/senior-engineer-javascript/SKILL.md"
    reason: "JavaScript/TypeScript-specific type safety, anti-patterns, and idioms"
---

# Senior Engineer Core — Always-On Standards

These rules apply to every line of code, in any language. Do not ask permission for them.

---

## Mindset

Before writing or reviewing any code, ask:
1. Do I understand the domain well enough to name things correctly?
2. Is this the simplest solution that could work?
3. Will the next engineer understand this without asking me?
4. Am I adding complexity not justified by a current requirement?

---

## SOLID Principles

**Single Responsibility** — One function = one action. One class = one domain concept. If you need "and" to describe it, split it.

**Open/Closed** — Open for extension, closed for modification. Use polymorphism and dispatch via method call instead of growing `if/elif/switch` chains.

**Liskov Substitution** — Subtypes must be substitutable for their base types without surprising the caller.

**Interface Segregation** — Prefer many small, focused interfaces over one large one. Depend only on the methods you actually use.

**Dependency Inversion** — Depend on abstractions, not concretions. Inject dependencies; never instantiate them inside a class.

---

## Domain-Driven Design

**Entities** own their invariants and state transitions. Business rules live on the entity, not in a service that pokes its fields.

**Value Objects** are defined entirely by their attributes. Immutable — replace, don't mutate.

**Aggregates** cluster related entities behind a single root. All external access goes through the aggregate root.

**Domain Services** handle stateless operations that don't belong to a single entity.

**Repositories** abstract persistence. They return domain objects, never raw dicts, rows, or ORM results to the domain layer.

**Bounded Contexts** define where a term has one meaning. `Order` in Sales ≠ `Order` in Fulfilment.

**Red Flags:** Anemic models (entities are data bags). Business logic in controllers. Repositories returning raw data to the domain. Domain objects importing infrastructure modules.

---

## Naming

- Name after the domain concept, not the type or role: `customer` not `customer_obj`; `PendingOrderPolicy` not `OrderManager`
- No vague names: never `result`, `data`, `info`, `temp`, `obj`, `val`, `mgr`, `util`
- Commands (side effects): `verb_noun` — `confirm_order`, `send_confirmation_email`
- Queries: `get_`, `find_`, `calculate_`, `is_`, `has_`
- Avoid: `handle_`, `manage_`, `do_`, `run_`, `process_`
- Booleans read as questions: `is_active`, `has_pending_items`, `can_be_cancelled`
- Collections use the plural of the element: `orders`, `line_items` — never `order_list`, `items_array`

---

## Error Handling

- Use specific exception subclasses. Never raise or catch bare `Exception`.
- Never swallow silently — every `except` block must log with context or re-raise.
- Wrap infrastructure exceptions to preserve the cause chain: `raise DomainError(...) from e`
- Include relevant identifiers in error messages: `"Order {order_id} cannot be confirmed: status is {order.status}"`
- Validate all external input at system boundaries. Do not let raw external data reach domain logic unvalidated.

---

## Logging

- Structured logging with context: key-value pairs, not interpolated strings.
- `DEBUG`: detailed diagnostics — development only
- `INFO`: normal operations — order created, payment processed
- `WARNING`: unexpected but recoverable — retry attempt, fallback used
- `ERROR`: operation failed — exception caught
- Never log secrets, tokens, credentials, or PII.

---

## Testing

- Each test reads like a specification: Arrange / Act / Assert.
- Name tests as: `test_should_[behaviour]_when_[condition]`
- Test behaviour, not implementation. Do not test private methods directly.
- Mock only I/O boundaries: database, HTTP, filesystem, time. Never mock domain objects.
- Coverage priority: domain logic → application services → infrastructure adapters → integration.

---

## Performance

- No N+1 queries in loops — batch lookups before the loop.
- Never query without a LIMIT on list endpoints.
- No blocking I/O in async context.
- No synchronous I/O in hot paths.

---

## Security

- Never store secrets in code or version control. Use environment variables or a secrets manager.
- Validate all external input at the boundary. Use allowlists, not denylists.
- Always use parameterised queries. Never interpolate user input into SQL strings.
- Never log PII, tokens, passwords, or credentials.
- Never expose stack traces or internal errors to end users — return generic messages, log details internally.

---

## Calibration — Avoiding Over and Under Engineering

**Rule of Three:** First occurrence → inline. Second → note the duplication. Third → extract the abstraction. Do not abstract on the first or second occurrence.

**Signs of over-engineering:** More abstraction layers than use cases. Interfaces with a single implementation and no tests. Generic solutions to specific problems.

**Signs of under-engineering:** Business logic in controllers. No error handling on I/O. Raw primitives where domain concepts belong. No tests on critical paths.

---

## Code Review Methodology

1. **Understand before judging** — read the entire diff before commenting. Identify the intent.
2. **Categorise issues:**
   - Correctness & Safety — bugs, unhandled exceptions, race conditions
   - Domain Clarity — anemic model, missing domain concept
   - Single Responsibility — function doing multiple things, mixed concerns
   - Extensibility — switch on type, hardcoded list
   - Readability — vague names, redundant comments
   - Performance — N+1 query, unbounded result set
3. **Per-issue output:**
   - Location: `[file:line or function name]`
   - Problem: `[what is wrong and why it matters]`
   - Fix: `[concrete suggestion]`
   - Why: `[principle or rule this violates]`

---

## Refactoring Patterns

| Smell | Pattern | Why |
|-------|---------|-----|
| Primitive obsession | Extract Domain Concept | Validation lives in one place |
| `if type == x / elif type == y` scattered | Replace Conditional with Polymorphism | New variant = new class, not edited code |
| SQL/ORM in services | Introduce Repository | Separates persistence; enables in-memory doubles |
| Function >20 lines or doing 2 things | Decompose Function | Each piece is testable |
| Deeply nested `if` blocks | Introduce Guard Clause | Happy path stays at left margin |
| Function returns AND causes side effect | Separate Query from Command | Predictable, easier to test |

**Explicit prior requests.** If the user previously made an explicit decision or request about how something should work (e.g. "use MarkdownV2", "keep the old behavior", "do not change X"), you MUST NOT override or revert that decision on your own authority. Stop, explain the conflict, and ask the user for direction before proceeding.