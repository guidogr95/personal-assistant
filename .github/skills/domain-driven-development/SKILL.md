---
name: domain-driven-development
description: >
  Provides authoritative Domain-Driven Design (DDD) guidance covering strategic
  patterns, tactical building blocks, layered architecture, and implementation
  examples for any programming language. Use when the user asks how to structure
  a domain model, design bounded contexts, define aggregates, entities, or value
  objects, map relationships between services or modules, apply DDD to a
  codebase, refactor toward a richer domain model, or avoid an anemic model.
  Also triggers on: "how do I model this domain", "what's the difference between
  an entity and a value object", "how should I structure my bounded contexts",
  "should this be an aggregate root", "we need ubiquitous language", "our domain
  logic is leaking into services", "help me apply DDD to this project", "how do
  I split this monolith into bounded contexts", "what is CQRS", "should I use
  event sourcing", "how do I avoid over-engineering with DDD", "how do I start
  applying DDD incrementally". Do NOT use for: generic OOP design patterns
  unrelated to DDD, DevOps, CI/CD pipelines, database schema design without
  domain modelling intent, or UI/frontend architecture.
version: "1.0.0"
category: software-design
tags:
  - ddd
  - domain-driven-development
  - architecture
  - software-development
  - language-agnostic
  - bounded-context
  - aggregates
  - cqrs
  - event-sourcing
  - refactoring
sources:
  - "Eric Evans — DDD Reference 2015 (CC BY 4.0): https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf"
  - "awesome-ddd (⭐ 12.3k): https://github.com/heynickc/awesome-ddd"
  - "Dan Does Code — Modelling Aggregates vs Entities: https://www.dandoescode.com/blog/ddd-modelling-aggregates-vs-entities"
  - "Software Architecture Guild — Applying DDD in Practice: https://software-architecture-guild.com/guide/architecture/domains/applying-ddd-in-practice/"
  - "Colla & Acerbis — Domain-Driven Refactoring at Scale: https://medium.com/deep-engineering/deep-engineering-4-alessandro-colla-and-alberto-acerbis-on-domain-driven-refactoring-at-scale-eb87b3dee1e6"
  - "Rico Fritzsche — Avoiding Over-Engineering: https://ricofritzsche.me/avoiding-over-engineering-focus-on-real-problems-in-software-development/"
applies_to:
  languages: ["*"]
  paradigms: ["OOP", "functional", "hybrid"]
  scales: ["monolith", "modular-monolith", "microservices"]
updated: "2026-06"
---

# Domain-Driven Design (DDD) — Coding Agent Skill

> Language-agnostic. Apply these concepts regardless of stack (Python, TypeScript, Go, Java, C#, Ruby, Rust, etc.).  
> Source: Eric Evans' DDD Reference (2015, CC BY 4.0) + community best practices.

---

## 🧠 Philosophy

DDD is a **mindset**, not a framework. Design is *driven* by the business **domain**:

1. Focus on the **core domain** and its logic.
2. Explore models through **creative collaboration** between domain experts and developers.
3. Speak a **ubiquitous language** within an explicitly bounded context.

---

## 🗺️ Strategic Patterns (the "What & Where")

### Domain & Subdomains
- **Domain** — the sphere of knowledge the software addresses (e.g., e-commerce, logistics).
- **Core Subdomain** — your competitive advantage; invest most here. Build it, don't buy it.
- **Supporting Subdomain** — necessary but not differentiating. Custom-built if needed.
- **Generic Subdomain** — commodity logic (auth, email, payments). Use off-the-shelf solutions.

### Bounded Context
A **hard boundary** within which a single domain model is defined and consistently applied.
- Each bounded context has its own **ubiquitous language**.
- The same word (e.g., `Customer`) can mean different things in different contexts — and that's intentional.
- Maps directly to: a microservice, a module, a package, a team's codebase.

### Ubiquitous Language
A shared vocabulary between developers and domain experts within one bounded context.
- Terms appear **in code** — class names, method names, module names.
- When the domain language evolves, the code evolves with it.
- No translation layer between what the business says and what the code does.

### Context Map
Explicit documentation of how bounded contexts relate to each other:

| Pattern | Description |
|---|---|
| **Partnership** | Two teams coordinate tightly; both succeed or fail together |
| **Shared Kernel** | A subset of the model is shared between contexts; changes require joint agreement |
| **Customer/Supplier** | Upstream context serves downstream; upstream prioritizes downstream needs |
| **Conformist** | Downstream adopts upstream's model as-is; no translation |
| **Anti-Corruption Layer (ACL)** | Downstream translates upstream's model to protect its own — the most important integration pattern |
| **Open Host Service** | Upstream publishes a formal, versioned protocol for downstream consumers |
| **Published Language** | Shared exchange format (e.g., JSON schema, Protobuf, event schema) |
| **Separate Ways** | No integration; contexts solve problems independently |

---

## 🧱 Tactical Patterns (the "How")

### Entity
An object defined by **identity**, not its attributes. Identity persists through state changes.
```
# Identity is stable; attributes can change
Order(id=42, status="pending") → Order(id=42, status="confirmed")  # same entity
```
- Give it a unique `id` (UUID, domain-meaningful key).
- Encapsulate behavior; avoid anemic (data-only) entities.

### Value Object
An object defined by its **value**, not identity. Always **immutable**.
```
Money(amount=100, currency="USD") == Money(amount=100, currency="USD")  # equality by value
```
- No identity field needed.
- Replace, never mutate: create a new instance when value changes.
- Great for: money, dates, coordinates, email addresses, quantities, status enums.

### Aggregate
A **cluster of entities and value objects** treated as a single transactional unit.
- Has one **Aggregate Root** (an Entity) — the only public entry point.
- External objects may only hold references to the root, never internal members.
- All business invariants (rules that must always be true) are enforced within the aggregate boundary.
- Keep aggregates small; design around true transactional consistency needs.

```
# Only Order (root) is accessible from outside
Order → [OrderLine, OrderLine, ShippingAddress(VO), Money(VO)]
       ↑ Aggregate Root
```

### Domain Event
A record that something **significant happened** in the domain. Named in past tense.
```
OrderPlaced, PaymentFailed, CustomerRegistered, InventoryDepleted
```
- Immutable facts; never modified after creation.
- Enable loose coupling: other parts of the system react without direct dependency.
- Carry enough data to describe what happened (no need to re-query).

### Repository
An abstraction over persistence that **speaks the domain language**.
```
# Domain interface (no ORM/SQL leaking in)
interface OrderRepository:
    find_by_id(id: OrderId) → Order
    find_pending_for_customer(customer_id: CustomerId) → List[Order]
    save(order: Order) → void
```
- One repository per Aggregate Root.
- Implementation details (SQL, NoSQL, HTTP) live *outside* the domain layer.

### Domain Service
Stateless logic that **doesn't naturally belong** to any single entity or value object.
```
# E.g., transferring funds crosses two Account aggregates
FundsTransferService.transfer(from: Account, to: Account, amount: Money)
```
- Use sparingly; if logic can go on an entity or VO, put it there.
- Named after domain activities, not technical operations.

### Factory
Encapsulates complex **creation logic** for aggregates or entities.
- Ensures objects are always created in a valid state.
- Use when constructors become complex or require domain logic.

### Modules (Packages/Namespaces)
Organize code around **domain concepts**, not technical layers.
```
# ✅ Domain-organized
/orders, /payments, /inventory, /customers

# ❌ Technical-layered (avoid as primary structure)
/controllers, /services, /repositories
```

---

## 🏛️ Layered Architecture (canonical)

```
┌──────────────────────────────┐
│       Interface / API        │  ← HTTP, CLI, events; thin; delegates to application layer
├──────────────────────────────┤
│      Application Layer       │  ← Orchestrates use cases; no business logic here
├──────────────────────────────┤
│        Domain Layer          │  ← Entities, VOs, Aggregates, Domain Events, Services
│     (the heart of DDD)       │    Pure domain logic. No infrastructure dependencies.
├──────────────────────────────┤
│    Infrastructure Layer      │  ← DB, messaging, external APIs; implements domain interfaces
└──────────────────────────────┘
```

**Dependency rule:** outer layers depend on inner layers. The domain layer depends on nothing.

---

## 🔄 CQRS (Command Query Responsibility Segregation)

Separate **write** (Command) from **read** (Query) models.

| Side | Purpose | Characteristics |
|---|---|---|
| **Command** | Mutate state | Goes through domain model, aggregates, validates invariants |
| **Query** | Return data | Can bypass domain model; optimized read projections, DTOs |

- Commands are imperatives: `PlaceOrder`, `CancelShipment`
- Queries are questions: `GetOrderSummary`, `ListPendingShipments`

---

## ⚡ Event Sourcing (optional, pairs with CQRS)

Store **all state changes as a sequence of domain events** rather than current state.
```
# Instead of: UPDATE orders SET status='confirmed' WHERE id=42
# Store:
OrderPlaced     {id:42, customer:7, items:[...]}
PaymentReceived {id:42, amount:99.99}
OrderConfirmed  {id:42}
```
- Current state = replay of all past events.
- Full audit log for free.
- Enables temporal queries ("what was the state on date X?").
- Trade-off: added complexity; use only when audit/history needs justify it.

---

## 🔍 Supple Design Principles

| Principle | Meaning |
|---|---|
| **Intention-Revealing Interfaces** | Names should express *what*, not *how* (`calculateShippingCost`, not `processData`) |
| **Side-Effect-Free Functions** | Prefer pure functions/methods that return values without mutating state |
| **Assertions** | Make invariants explicit in code (preconditions, postconditions) |
| **Standalone Classes** | Minimize dependencies; classes should be understandable in isolation |
| **Conceptual Contours** | Decompose along natural domain boundaries, not arbitrary technical ones |

---

## ✅ When to Apply DDD

**Good fit:**
- Complex domain with rich business rules
- Multiple teams / bounded contexts
- Domain logic changes frequently based on business evolution
- Long-lived systems with high investment

**Avoid or simplify for:**
- Simple CRUD apps with no real domain logic
- Short-lived prototypes
- Pure infrastructure / data-pipeline services

---

## 🚫 Common Anti-Patterns to Avoid

| Anti-Pattern | Problem |
|---|---|
| **Anemic Domain Model** | Entities are data bags; all logic lives in services — DDD in name only |
| **Big Ball of Mud** | No explicit boundaries; everything depends on everything |
| **Leaking Infrastructure into Domain** | Domain layer imports ORM models, HTTP clients, etc. |
| **One Model to Rule Them All** | Forcing a single shared model across all contexts kills clarity |
| **Overusing Domain Services** | Logic that belongs on entities delegated out, making entities anemic |

---

## 🪜 Applying DDD Incrementally (Avoiding Over-Abstraction)

> "Think big, change small." — [Software Architecture Guild](https://software-architecture-guild.com/guide/architecture/domains/applying-ddd-in-practice/)

DDD does not need to be applied all at once. Over-applying patterns prematurely is itself an anti-pattern. Follow this staged approach:

### Stage 1 — Understand Before You Model
Before touching code, invest in domain discovery:
- Interview domain experts; recover lost business knowledge.
- Run an **EventStorming** session on one painful flow (e.g. "customer onboarding").
- Watch where people hesitate or disagree — those are your hot spots.
- Map the *current* system: sketch proto-bounded contexts, data stores, key integrations.

**Rule:** Start with ubiquitous language and bounded context identification. Do **not** jump to aggregates, CQRS, or event sourcing.

### Stage 2 — Stabilise Logical Boundaries (No Infra Changes Yet)
- Create **modules/namespaces/packages** that mirror subdomains, even inside a monolith.
- Move code to match domain labels before touching infrastructure.
- Treat each module as a mini bounded context: its own language, its own invariants.

**Rule:** Do not split deployments yet. Get language and invariant boundaries right first.

### Stage 3 — Apply Tactical Patterns Where Pain Is Highest
- Identify where consistency actually matters — those are candidates for aggregates.
- Incrementally:
  - Extract **Value Objects** from repeated primitive field clusters.
  - Pull core invariants into methods **on** entities (eliminate anemic models).
  - Replace global validations with explicit domain concepts.
- Use ACL / OHS to protect refactors: keep the external contract stable while moving logic inside.

**Rule:** Don't convert everything. Fix mismatches, not everything. Advocate baby steps tied directly to feature work.

### Stage 4 — Modular Monolith Before Microservices
- A well-structured **modular monolith** often delivers all the agility needed.
- Decompose into separate deployable services only when scale or team autonomy demands it — not because of hype.
- A practical test: *"Can I explain what this service owns and why it exists in one sentence?"* If not, the boundary is probably wrong.

### Stage 5 — Weave Refactoring Into Feature Delivery
- Do not pause feature development for months of cleanup.
- If a new feature touches an area, refactor that area at the same time — baby steps.
- Build a **safety net of tests** first: start with end-to-end tests to confirm behaviour doesn't change, then add architectural fitness tests to enforce module boundaries, then unit tests for new domain logic.

### The "Undercover DDD" Approach
Start even without organisational buy-in:
- **Clean up language**: rename classes and methods to domain terms. Delete vague words like `Manager`, `Handler`, `Data` from anything domain-facing.
- **Draw a local context map**: even if only your team uses it, map your upstreams, downstreams, and interfaces.
- **Model one tiny slice well**: pick one flow, run a small EventStorming session, refactor that slice, show the before/after impact.

### Over-Abstraction Warning Signs

| Smell | Fix |
|---|---|
| Building a generic "framework" for a single use case | Solve the concrete problem first; generalise only when the second use case appears |
| 5 layers of abstraction around simple CRUD | Ask: does this area have real invariants? If not, skip tactical patterns |
| Every object is an aggregate root | `OrderLine` should be inside `Order`, not its own root |
| Designing for millions of users before first user | Scale progressively in step with real growth |
| Jumping to microservices from a monolith | Move to a modular monolith first; microservices may never be needed |

---

## 💻 Language Examples, Technical Background & Tips

### Value Object — pseudocode

```python
# ✅ Good: immutable, equality by value, enforces invariants on creation
class Money:
    def __init__(self, amount: Decimal, currency: str):
        if amount < 0:
            raise ValueError("Amount cannot be negative")
        if not currency:
            raise ValueError("Currency required")
        self._amount = amount
        self._currency = currency.upper()

    @property
    def amount(self): return self._amount

    @property
    def currency(self): return self._currency

    def add(self, other: "Money") -> "Money":
        if self._currency != other._currency:
            raise ValueError("Cannot add different currencies")
        return Money(self._amount + other._amount, self._currency)  # new instance — never mutate

    def __eq__(self, other):
        return isinstance(other, Money) and \
               self._amount == other._amount and \
               self._currency == other._currency

    def __repr__(self):
        return f"Money({self._amount} {self._currency})"
```

**Key rules:**
- Never mutate; always return a new instance.
- Use `__init__` validation to ensure no invalid state at creation.
- Equality is structural (by value), not by reference/identity.

---

### Entity — pseudocode

```python
class CustomerId:
    def __init__(self, value: str): self.value = value
    def __eq__(self, other): return isinstance(other, CustomerId) and self.value == other.value

class Customer:
    def __init__(self, id: CustomerId, email: str):
        self._id = id
        self._email = email

    @property
    def id(self): return self._id

    def change_email(self, new_email: str):
        if "@" not in new_email:
            raise ValueError("Invalid email")
        self._email = new_email
        # raise domain event: CustomerEmailChanged(self._id, new_email)

    def __eq__(self, other):
        return isinstance(other, Customer) and self._id == other._id  # identity only
```

**Key rules:**
- Two entities are equal if their IDs match — not their attributes.
- Use strongly-typed IDs (e.g., `CustomerId` wrapper) to prevent passing wrong IDs across aggregates.
- Business behaviour lives **on** the entity — not in a service.

---

### Aggregate — pseudocode

```python
class Order:  # Aggregate Root
    def __init__(self, id: OrderId, customer_id: CustomerId):
        self._id = id
        self._customer_id = customer_id  # reference by ID only — never embed Customer
        self._lines: list[OrderLine] = []
        self._status = "draft"
        self._events: list = []

    def add_line(self, product_id: ProductId, qty: int, unit_price: Money):
        if self._status != "draft":
            raise Exception("Cannot modify a confirmed order")
        if qty <= 0:
            raise ValueError("Quantity must be positive")
        self._lines.append(OrderLine(product_id, qty, unit_price))

    def confirm(self):
        if not self._lines:
            raise Exception("Cannot confirm an empty order")
        self._status = "confirmed"
        self._events.append(OrderConfirmed(self._id, self._customer_id))

    @property
    def total(self) -> Money:
        return sum((l.subtotal for l in self._lines), Money(Decimal(0), "USD"))

    def pop_events(self):
        events, self._events = self._events, []
        return events


class OrderLine:  # Internal entity — not accessible from outside the aggregate
    def __init__(self, product_id, qty: int, unit_price: Money):
        self.product_id = product_id
        self.qty = qty
        self.unit_price = unit_price

    @property
    def subtotal(self) -> Money:
        return Money(self.unit_price.amount * self.qty, self.unit_price.currency)
```

**Key rules:**
- Only the aggregate root is accessible from outside; internal entities have restricted constructors.
- One transaction per aggregate — coordinate cross-aggregate changes via **domain events**, not direct calls.
- Reference other aggregate roots by ID only.
- Keep aggregates small; overloading them causes concurrency and performance issues.

---

### Repository — pseudocode

```python
# Domain layer defines the contract — no infrastructure details here
class OrderRepository(ABC):
    @abstractmethod
    def find_by_id(self, id: OrderId) -> Optional[Order]: ...

    @abstractmethod
    def find_pending_for_customer(self, customer_id: CustomerId) -> list[Order]: ...

    @abstractmethod
    def save(self, order: Order) -> None: ...


# Infrastructure layer provides the implementation
class SqlOrderRepository(OrderRepository):
    def save(self, order: Order):
        # map domain object → persistence model
        # persist to DB, write outbox events in same transaction
        ...
```

---

### Domain Event — pseudocode

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass(frozen=True)
class OrderConfirmed:
    order_id: OrderId
    customer_id: CustomerId
    occurred_at: datetime = field(default_factory=datetime.utcnow)


# Handler lives in the application layer — fully decoupled from the aggregate
class OnOrderConfirmed:
    def handle(self, event: OrderConfirmed):
        self._email_service.notify_customer(event.customer_id)
        self._inventory_service.reserve_items(event.order_id)
```

---

### Technical Background & Tips & Tricks

#### Strongly-typed IDs
Avoid primitive obsession on identifiers. A plain `str` or `int` can be silently passed to the wrong method:
```python
# ❌ no protection — easy to swap customer_id for order_id accidentally
def find_order(customer_id: str): ...

# ✅ compiler/type-checker will catch wrong ID types
class OrderId:
    def __init__(self, value: str): self.value = value

class CustomerId:
    def __init__(self, value: str): self.value = value
```

#### Protect domain invariants at construction time
Objects should **never** exist in an invalid state:
```python
# ❌ allows invalid state to be created silently
email = Email("")

# ✅ raises immediately — invalid state is impossible
class Email:
    def __init__(self, value: str):
        if not re.match(r"[^@]+@[^@]+\.[^@]+", value):
            raise ValueError(f"Invalid email: {value}")
        self.value = value
```

#### Avoid the Anemic Domain Model trap
If all your entities are data bags and all logic lives in `*Service` classes, you have a hollow model:
```python
# ❌ Anemic — entity is just a struct; logic leaked into service
class Order:
    status: str
    lines: list

class OrderService:
    def confirm(self, order: Order): ...

# ✅ Rich — behaviour and invariants live on the entity
class Order:
    def confirm(self): ...
```

#### Use `internal` / package-private constructors for aggregate internals
In Java/C#/Go: mark `OrderLine`'s constructor as `internal` or package-private so only `Order` can instantiate it. This enforces the aggregate boundary at compile time, not just by convention.

#### Persistence tips
- **Value Objects → inline columns** (simplest): `orders.shipping_street`, `orders.shipping_city`.
- **Entities inside aggregates → same or child table**: never expose them through their own repository.
- **Do not leak ORM models into the domain layer**: map to/from a separate persistence model in the infrastructure layer.
- **Outbox pattern for domain events**: write events to an outbox table in the same transaction as the aggregate save; a background worker dispatches them. Prevents lost events on failure.

#### EventStorming in 5 minutes
A lightweight discovery session for any team size:
1. Everyone writes **domain events** on orange stickies (past tense: `OrderPlaced`, `PaymentFailed`).
2. Arrange them on a timeline left → right.
3. Add **commands** (blue) that cause each event, **actors** (yellow) who issue commands, **policies** (purple: "when X, then Y"), and **external systems** (pink).
4. Cluster stickies — natural clusters reveal bounded context candidates.

#### Decision table: Entity vs Value Object vs Domain Service

| Scenario | Use |
|---|---|
| Needs identity, tracked over time | **Entity** |
| Defined purely by its values, immutable | **Value Object** |
| Logic spans multiple entities, stateless | **Domain Service** |
| Crosses aggregate boundaries (e.g. fund transfer) | **Domain Service** |
| Commodity concept (email address, money, date range) | **Value Object** |
| Has its own lifecycle and can exist independently | **Entity / Aggregate Root** |

---

## 📚 Canonical References

- [DDD Reference — Eric Evans (free PDF, CC BY 4.0)](https://www.domainlanguage.com/wp-content/uploads/2016/05/DDD_Reference_2015-03.pdf)
- [awesome-ddd — curated community resource list ⭐ 12.3k](https://github.com/heynickc/awesome-ddd)
- [Domain-Driven Design Quickly — free eBook](https://www.infoq.com/minibooks/domain-driven-design-quickly/)
- [Dan Does Code — Modelling Aggregates vs Entities](https://www.dandoescode.com/blog/ddd-modelling-aggregates-vs-entities)
- [Milan Jovanović — Value Objects in DDD](https://www.milanjovanovic.tech/blog/value-objects-in-dotnet-ddd-fundamentals)
- [Domain-Driven Refactoring at Scale — Colla & Acerbis](https://medium.com/deep-engineering/deep-engineering-4-alessandro-colla-and-alberto-acerbis-on-domain-driven-refactoring-at-scale-eb87b3dee1e6)