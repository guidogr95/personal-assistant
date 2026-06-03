---
name: senior-engineer-python
description: "Enforce Python-specific code quality. Use when: writing Python code, reviewing Python PRs, Python type safety, Python anti-patterns, Python best practices, Python refactoring, Python dataclasses, Python async."
requires:
  - path: "instructions/senior-engineer-core.instructions.md"
    reason: "language-agnostic standards (SOLID, DDD, naming, error handling, logging, testing) that apply to all Python code"
---

# Senior Engineer — Python

Language-specific enforcement for Python. Language-agnostic rules (SOLID, DDD, naming, error handling, logging, testing, security) are in `senior-engineer-core.instructions.md`.

---

## Type Safety Rules

- All functions must have complete type hints (parameters + return type). No exceptions.
- Use `Optional[T]` (or `T | None` in 3.10+) for nullable values. Never implicit `None` return.
- Never use bare `Any` — use specific types or `TypeVar`. If unavoidable, document why with a comment.
- Use `TypedDict` for dicts with known structure.
- Use `Enum` (or `StrEnum`) for fixed sets of string values.
- Use `Protocol` for structural interfaces — prefer over ABC unless shared state is needed.
- Use `@dataclass(frozen=True)` for value objects. Validate in `__post_init__`.
- Enable strict mypy checking for new code.

```python
# WRONG
def get_order(order_id):
    ...

# RIGHT
def get_order(order_id: str) -> Optional[Order]:
    ...

# WRONG
def process(data: dict) -> Any:
    ...

# RIGHT
class OrderData(TypedDict):
    order_id: str
    customer_id: str
    total: Decimal

def process(data: OrderData) -> ProcessingResult:
    ...

# WRONG
STATUS_PENDING = "pending"

# RIGHT
class OrderStatus(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
```

---

## Python Anti-Patterns

**Vague intermediate variables:**
```python
# WRONG
result = get_orders()
data = process(result)

# RIGHT
pending_orders = order_repo.find_pending()
confirmed_orders = confirm_all(pending_orders)
```

**Catch-all exception handlers:**
```python
# WRONG
try:
    process_order(order_id)
except Exception as e:
    print(f"Error: {e}")

# RIGHT
try:
    process_order(order_id)
except OrderNotFoundError:
    logger.warning("order_not_found", extra={"order_id": order_id})
    raise
except DatabaseError as e:
    logger.error("db_failure", extra={"order_id": order_id, "error": str(e)})
    raise InfrastructureError("Failed to process order") from e
```

**Unnecessary `else` after `return`/`raise`:**
```python
# WRONG
def get_status(order: Order) -> str:
    if order.is_pending():
        return "pending"
    else:
        return "active"

# RIGHT
def get_status(order: Order) -> str:
    if order.is_pending():
        return "pending"
    return "active"
```

**Boolean trap parameters:**
```python
# WRONG
def get_orders(include_cancelled: bool) -> list[Order]: ...

# RIGHT
def get_active_orders() -> list[Order]: ...
def get_all_orders_including_cancelled() -> list[Order]: ...
```

**Docstrings that restate the function name:**
```python
# WRONG
def confirm_order(order_id: str) -> None:
    """Confirms the order."""

# RIGHT
def confirm_order(order_id: str) -> None:
    """
    Transitions order to CONFIRMED status.
    Raises InvalidStateTransitionError if order is not PENDING.
    """
```

**Comments that describe WHAT instead of WHY:**
```python
# WRONG
# Loop through orders
for order in orders:
    # Check if order is pending
    if order.status == OrderStatus.PENDING:
        order.confirm()

# RIGHT
# Confirm all pending orders before end-of-day cutoff
for order in orders:
    if order.status == OrderStatus.PENDING:
        order.confirm()
```

---

## Python-Specific Standards

**Imports:** All imports at the top of the file. Group: stdlib → third-party → local → relative. Alphabetically sorted within each group. Never `from module import *`. Never mid-file imports.

**Async:** Never call blocking I/O in async context. Use `asyncio.gather` for concurrent I/O. Always use `async with` for async context managers. Always await coroutines — never fire-and-forget without explicit tracking.

**Generators:** Use generators for large sequences to avoid loading everything in memory. Prefer `yield` in iterators over building full lists.

**Config loading:** Load from environment variables. Use `@dataclass(frozen=True)` for typed config. Validate at startup — fail fast if required config is missing. Never silently fall back to insecure defaults.

**Question existing assumptions:**
Existing code is not immutable architecture. When a design choice (parse mode, data format, API style, module structure) is causing friction, evaluate whether changing the choice is simpler than working around it. Do not treat "this is how it was done" as justification for "this is how it must continue to be done." Before proposing a complex workaround, explicitly state the contrarian hypothesis: "What if we changed X instead?" and evaluate both paths.

---

## Success Checklist

- [ ] All functions have complete type hints
- [ ] No bare `Any` types
- [ ] `Optional[T]` used for all nullable values
- [ ] Enums used for fixed value sets
- [ ] `TypedDict` used for structured dicts
- [ ] No `except Exception: pass` anywhere
- [ ] No boolean trap parameters
- [ ] No unnecessary `else` after `return`/`raise`
- [ ] No comments that describe WHAT (only WHY)
- [ ] No docstrings that restate the function name
- [ ] No `print()` in production paths
- [ ] No N+1 queries in loops
- [ ] No secrets in source code
- [ ] No sensitive data in logs
- [ ] All external input validated at boundary
- [ ] Config loaded from environment, validated at startup
- [ ] All imports at top of file, properly grouped
