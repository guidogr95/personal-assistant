---
name: senior-engineer-javascript
description: "Enforce JavaScript and TypeScript code quality. Use when: writing JavaScript code, writing TypeScript code, reviewing JS/TS PRs, TypeScript type safety, JavaScript anti-patterns, TypeScript best practices, JS refactoring, TS refactoring, Node.js, React, async/await."
requires:
  - path: "instructions/senior-engineer-core.instructions.md"
    reason: "language-agnostic standards (SOLID, DDD, naming, error handling, logging, testing) that apply to all JS/TS code"
---

# Senior Engineer — JavaScript & TypeScript

Language-specific enforcement for JavaScript and TypeScript. Language-agnostic rules (SOLID, DDD, naming, error handling, logging, testing, security) are in `senior-engineer-core.instructions.md`.

---

## TypeScript Type Safety Rules

- Enable `strict: true` in `tsconfig.json`. This is non-negotiable.
- All functions must have complete type annotations (parameters + return type).
- Never use `any` — use `unknown` and narrow, or use specific types. If unavoidable, document with a comment.
- Use `T | null` for nullable values. Avoid implicit `undefined` returns — declare them explicitly.
- Use `interface` for object shapes; use `type` for unions and aliases.
- Use `enum` or `as const` for fixed sets of values.
- Use `unknown` in catch blocks, not `any`. Narrow with `instanceof` before accessing properties.
- Prefer `readonly` on properties that should not change after construction.

```typescript
// WRONG
function getOrder(orderId) { ... }

// RIGHT
function getOrder(orderId: string): Promise<Order | null> { ... }

// WRONG
function process(data: any): any { ... }

// RIGHT
interface OrderData {
  orderId: string;
  customerId: string;
  total: number;
}
function process(data: OrderData): ProcessingResult { ... }

// WRONG
const STATUS_PENDING = "pending";

// RIGHT
const ORDER_STATUS = { PENDING: "pending", CONFIRMED: "confirmed" } as const;
type OrderStatus = typeof ORDER_STATUS[keyof typeof ORDER_STATUS];

// WRONG
try { ... } catch (e: any) { console.log(e.message); }

// RIGHT
try { ... } catch (e: unknown) {
  if (e instanceof Error) logger.error("failed", { message: e.message });
}
```

---

## JavaScript/TypeScript Anti-Patterns

**Vague intermediate variables:**
```typescript
// WRONG
const result = getOrders();
const data = process(result);

// RIGHT
const pendingOrders = orderRepo.findPending();
const confirmedOrders = confirmAll(pendingOrders);
```

**Catch-all error handlers:**
```typescript
// WRONG
try {
  processOrder(orderId);
} catch (e) {
  console.log("Error:", e);
}

// RIGHT
try {
  processOrder(orderId);
} catch (e: unknown) {
  if (e instanceof OrderNotFoundError) {
    logger.warn("order_not_found", { orderId });
    throw e;
  }
  logger.error("unexpected_error", {
    orderId,
    error: e instanceof Error ? e.message : String(e),
  });
  throw new InfrastructureError("Failed to process order");
}
```

**Boolean trap parameters:**
```typescript
// WRONG
function getOrders(includeCancelled: boolean): Order[] { ... }

// RIGHT
function getActiveOrders(): Order[] { ... }
function getAllOrdersIncludingCancelled(): Order[] { ... }
```

**Unnecessary `else` after `return`/`throw`:**
```typescript
// WRONG
function getStatus(order: Order): string {
  if (order.isPending()) {
    return "pending";
  } else {
    return "active";
  }
}

// RIGHT
function getStatus(order: Order): string {
  if (order.isPending()) return "pending";
  return "active";
}
```

**Implicit `undefined` returns:**
```typescript
// WRONG
function findOrder(id: string): Order {
  const order = orders.find(o => o.id === id);
  return order; // could be undefined!
}

// RIGHT
function findOrder(id: string): Order | undefined {
  return orders.find(o => o.id === id);
}
```

**`console.log` in production:**
```typescript
// WRONG
console.log("Processing order", orderId);

// RIGHT
logger.info("processing_order", { orderId });
```

**Mutating function arguments:**
```typescript
// WRONG
function addDiscount(order: Order, discount: number): void {
  order.total -= discount; // mutates caller's object
}

// RIGHT
function applyDiscount(order: Order, discount: number): Order {
  return { ...order, total: order.total - discount };
}
```

**Bare filesystem catch blocks (Node.js):**
```typescript
// WRONG — swallows all errors including permissions failures
try {
  await fs.readdir(dir);
} catch {
  // silent
}

// RIGHT — only swallow ENOENT; re-throw everything else
try {
  await fs.readdir(dir);
} catch (e: unknown) {
  if ((e as NodeJS.ErrnoException).code !== 'ENOENT') throw e;
}
```

**Inline object types repeated across signatures:**
```typescript
// WRONG — same shape written three times
function get(name: string): { readonly sha: string; readonly ts: string } | undefined { ... }
function set(name: string, record: { sha: string; ts: string }): Promise<void> { ... }
function all(): Record<string, { sha: string; ts: string }> { ... }

// RIGHT — one named interface, used everywhere
interface ConsentRecord {
  readonly sha: string;
  readonly ts: string;
}
function get(name: string): ConsentRecord | undefined { ... }
function set(name: string, record: ConsentRecord): Promise<void> { ... }
function all(): Record<string, ConsentRecord> { ... }
```

**Loop-body allocations:**
```typescript
// WRONG — new Set allocated on every iteration
for (const file of files) {
  const KNOWN = new Set(['a', 'b', 'c']);
  if (KNOWN.has(file.type)) { ... }
}

// RIGHT — hoisted outside the loop
const KNOWN = new Set(['a', 'b', 'c']);
for (const file of files) {
  if (KNOWN.has(file.type)) { ... }
}
```

**Write/delete loops without per-iteration error handling:**
```typescript
// WRONG — one failure aborts the loop with no partial-failure reporting
for (const filePath of paths) {
  await fs.unlink(filePath);
}

// RIGHT — each iteration is independently guarded; caller knows what succeeded
const failures: string[] = [];
for (const filePath of paths) {
  try {
    await fs.unlink(filePath);
  } catch (e: unknown) {
    failures.push(filePath);
    logger.error('delete_failed', { filePath, error: String(e) });
  }
}
if (failures.length > 0) {
  // Surface the partial failure — do not silently continue as if all succeeded.
  throw new Error(`Failed to delete ${failures.length} file(s): ${failures.join(', ')}`);
}
```

**Union type validation arrays that fall out of sync:**
```typescript
// WRONG — ArtifactType gains 'hook' but VALID_TYPES is not updated
type ArtifactType = 'instruction' | 'skill' | 'prompt' | 'agent' | 'hook';
const VALID_TYPES = ['instruction', 'skill', 'prompt', 'agent']; // 'hook' missing!

// RIGHT — whenever the union is extended, grep and update every mirror
const VALID_TYPES: readonly ArtifactType[] = ['instruction', 'skill', 'prompt', 'agent', 'hook'];
```
> **Rule:** Whenever you add a member to a union type, grep the codebase for arrays, Sets, and switch statements that list its members and update them all in the same step.

**Magic strings in logic:**
```typescript
// WRONG — same literal appears in filter, error message, and docs separately
const hookFiles    = files.filter(f =>  f.path.includes('/hooks/'));
const nonHookFiles = files.filter(f => !f.path.includes('/hooks/'));

// RIGHT — one named constant, used everywhere
const HOOKS_PATH_SEGMENT = '/hooks/';
const hookFiles    = files.filter(f =>  f.path.includes(HOOKS_PATH_SEGMENT));
const nonHookFiles = files.filter(f => !f.path.includes(HOOKS_PATH_SEGMENT));
```
> **Rule:** Any string literal used in `.includes()`, `.filter()`, `.startsWith()`, `.endsWith()`, or a switch case must be a named `const` if it appears more than once or represents a domain concept.

---

## JavaScript/TypeScript Standards

**Promises:** Always `await` or chain `.then`/`.catch`. Never fire-and-forget without explicit tracking. Always handle rejections — unhandled rejections are bugs.

**Imports:** Use named imports, not `import *`. Prefer `import type` for type-only imports. Group: node modules → local modules. Keep imports at the top of the file.

**Immutability:** Prefer `const` over `let`. Prefer `readonly` on interfaces and class properties. Use spread operator or `Object.freeze` for immutable value objects.

**Null checks:** Use optional chaining (`?.`) for safe access. Use nullish coalescing (`??`) for defaults. Never access properties without a null check when the value could be undefined.

**Config loading:** Load from environment variables (`process.env.X`). Fail fast if required config is missing. Never silently fall back to insecure defaults. Validate at startup.

---

## Success Checklist

**Verified by `tsc` / `get_errors()` — always caught at compile time:**
- [ ] `strict: true` in tsconfig
- [ ] All functions have complete type annotations
- [ ] No `any` types — use `unknown` or specific types
- [ ] `T | null` used for nullable values
- [ ] `enum` or `as const` for fixed value sets

**Requires manual inspection — grep or read the code:**
- [ ] No catch-all `catch (e) { console.log(e) }`
- [ ] Every filesystem `catch` narrows to `ENOENT` before swallowing — bare `catch {}` is never acceptable (Node.js)
- [ ] No boolean trap parameters
- [ ] No unnecessary `else` after `return`/`throw`
- [ ] No `console.log` in production paths
- [ ] No mutating function arguments
- [ ] No floating promises — every rejected promise is `await`ed or has `.catch()`; never `void fn()` on a rejectable promise
- [ ] No inline object types used in more than one signature — extract a named `interface`
- [ ] No magic string literals in logic (`.includes()`, `.filter()`, switch cases) — extract named `const`
- [ ] No `new Set(` / `new Map(` / `new RegExp(` inside loop bodies when the value is constant — hoist to module or function scope
- [ ] Every write/delete loop has per-iteration error handling and surfaces failures to the caller
- [ ] Whenever a union type gains a new member, all validation arrays/Sets/switch cases that mirror it are updated in the same step
- [ ] No N+1 queries in loops
- [ ] No secrets in source code
- [ ] No sensitive data in logs
- [ ] All external input validated at boundary
- [ ] Config loaded from environment, validated at startup
