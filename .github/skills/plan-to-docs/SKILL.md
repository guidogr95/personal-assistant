---
name: plan-to-docs
description: Break down implementation plans into structured, well-organized documentation (folders, documents, and specifications)
---

# Plan-to-Docs Skill

## What This Skill Does

The **plan-to-docs** skill helps you transform high-level implementation plans into a comprehensive set of structured documentation artifacts. Instead of having a single monolithic plan, this skill guides you through creating a modular, hierarchical documentation structure that:

- **Improves clarity** by breaking complex plans into focused, manageable documents
- **Enhances discoverability** through logical folder organization
- **Facilitates collaboration** by clearly assigning responsibilities and context
- **Ensures maintainability** by treating documentation as code (versioned, reviewed, updated)
- **Accelerates onboarding** by providing clear, well-organized technical artifacts

## How to Use This Skill with VSCode Copilot

### Method 1: Automatic Invocation

Simply describe your need in the Copilot Chat (`Ctrl+Alt+I`), and the skill will be automatically discovered:

```
I have an implementation plan for a new user authentication system. 
Help me break it down into structured documentation.
```

### Method 2: Manual Reference

Reference the skill explicitly in your prompt:

```
@workspace Using the plan-to-docs skill, help me organize my 
implementation plan for [project name] into proper documentation structure.
```

### Method 3: With Context

Provide your implementation plan as context:

```
#file:implementation-plan.md

Break this implementation plan into a structured documentation tree.
Show me what folders and documents I should create.
```

## Core Prompt Templates

### Template 1: Full Documentation Structure Generation

```markdown
I have an implementation plan for [PROJECT_NAME] that includes:
- [Component/Feature 1]
- [Component/Feature 2]
- [Component/Feature 3]

Using the plan-to-docs approach:
1. Analyze this plan and identify the key components
2. Recommend a folder structure based on best practices
3. List all documentation artifacts I should create
4. For each artifact, explain:
   - What it should contain
   - Who the target audience is
   - How it maps to the implementation plan
5. Provide a creation order/priority
```

### Template 2: Specific Document Type Generation

```markdown
I need to create [DOCUMENT_TYPE] for [COMPONENT/FEATURE].

Based on the plan-to-docs templates:
- Show me the recommended structure for this document type
- What sections should it include?
- What level of detail is appropriate?
- What related documents should I reference or link to?
```

### Template 3: Existing Plan Transformation

```markdown
#file:my-plan.md

This is my current implementation plan. Using plan-to-docs best practices:
1. Identify which parts map to which documentation types (PRD, TDD, ADR, API docs, etc.)
2. Suggest how to decompose this into separate documents
3. Recommend a folder structure
4. Create a table of contents showing the documentation hierarchy
```

### Template 4: Documentation Audit and Improvement

```markdown
#folder:docs

Audit my existing documentation structure against plan-to-docs best practices:
1. What's missing?
2. What's duplicated or should be consolidated?
3. How can I improve the organization?
4. Which documents need to be split or merged?
5. Recommend specific actions to align with best practices
```

## Step-by-Step Usage Examples

### Example 1: New Microservice Documentation

**User Input:**
```
I'm building a payment processing microservice. The plan includes:
- RESTful API with 5 endpoints
- Integration with Stripe and PayPal
- Async event processing with RabbitMQ
- PostgreSQL database
- Docker deployment

Help me structure the documentation.
```

**Expected Copilot Output:**
```markdown
## Recommended Documentation Structure

### Folder Structure
```
docs/
├── README.md                          # Project overview and navigation
├── architecture/
│   ├── overview.md                    # High-level architecture
│   ├── decisions/                     # ADR folder
│   │   ├── 001-use-postgresql.md
│   │   ├── 002-async-with-rabbitmq.md
│   │   └── 003-payment-gateway-strategy.md
│   └── diagrams/
│       ├── system-context.png
│       └── component-diagram.png
├── api/
│   ├── overview.md                    # API introduction
│   ├── authentication.md
│   ├── endpoints/
│   │   ├── create-payment.md
│   │   ├── get-payment-status.md
│   │   ├── refund-payment.md
│   │   ├── list-payments.md
│   │   └── webhook-handler.md
│   └── error-codes.md
├── integration/
│   ├── stripe-integration.md
│   └── paypal-integration.md
├── deployment/
│   ├── docker-setup.md
│   ├── environment-variables.md
│   └── kubernetes-manifests.md
├── database/
│   ├── schema.md
│   └── migrations.md
└── guides/
    ├── getting-started.md
    ├── local-development.md
    └── testing.md
```

### Priority Order for Document Creation

1. **High Priority (Week 1)**
   - `README.md` - Project entry point
   - `architecture/overview.md` - System design
   - `api/overview.md` - API introduction
   - `guides/getting-started.md` - Quick start

2. **Medium Priority (Week 2)**
   - `architecture/decisions/` - All ADRs
   - `api/endpoints/` - Each endpoint specification
   - `database/schema.md` - Data model

3. **Lower Priority (Week 3+)**
   - Integration guides
   - Deployment documentation
   - Detailed testing guides

### Document Type Mapping

| Implementation Plan Component | Document Type | Location |
|------------------------------|---------------|----------|
| System design & technology choices | Architecture Overview + ADRs | `/architecture/` |
| API specification | API Documentation | `/api/` |
| Payment gateway integrations | Integration Guides | `/integration/` |
| Database design | Technical Design Doc (TDD) | `/database/` |
| Deployment strategy | Deployment Guide | `/deployment/` |
| Developer workflow | How-To Guides | `/guides/` |
```

### Example 2: Splitting a Monolithic Plan Document

**User Input:**
```
#file:monolithic-plan.md

This 50-page document contains everything about our e-commerce platform rewrite.
It's too large and hard to navigate. Help me break it down.
```

**Expected Copilot Approach:**
```markdown
## Analysis of Current Plan

I've identified these distinct sections in your monolithic document:

1. **Product Requirements** (Pages 1-10)
2. **System Architecture** (Pages 11-18)
3. **API Specifications** (Pages 19-30)
4. **Database Design** (Pages 31-35)
5. **Security Requirements** (Pages 36-40)
6. **Deployment Strategy** (Pages 41-45)
7. **Testing Strategy** (Pages 46-50)

## Recommended Decomposition

### Create These Documents:

1. **`requirements/PRD.md`**
   - Extract: User stories, acceptance criteria, business goals
   - Target audience: Product managers, stakeholders
   - Content from: Pages 1-10

2. **`architecture/SAD.md`** (Software Architecture Document)
   - Extract: High-level design, component interactions
   - Target audience: Architects, senior developers
   - Content from: Pages 11-18

3. **`architecture/decisions/`** (Multiple ADRs)
   - Split architectural choices into individual ADRs
   - Each decision gets its own file
   - Content from: Scattered throughout Pages 11-18

4. **`api/reference.md`** + Individual endpoint files
   - Extract: All API contracts
   - Target audience: Backend developers, integrators
   - Content from: Pages 19-30

5. **`database/design.md`** (Technical Design Document)
   - Extract: Schema, relationships, indexes
   - Target audience: Database engineers, backend developers
   - Content from: Pages 31-35

6. **`security/requirements.md`**
   - Extract: Security controls, compliance needs
   - Target audience: Security team, DevOps
   - Content from: Pages 36-40

7. **`deployment/strategy.md`**
   - Extract: Infrastructure, CI/CD, rollout plan
   - Target audience: DevOps, SREs
   - Content from: Pages 41-45

8. **`testing/strategy.md`**
   - Extract: Testing approach, coverage requirements
   - Target audience: QA engineers, developers
   - Content from: Pages 46-50

### Master Index to Create: `docs/README.md`

```markdown
# E-Commerce Platform Documentation

## Overview
Brief project description

## Documentation Map
- [Product Requirements](requirements/PRD.md) - What we're building
- [Architecture](architecture/SAD.md) - How it's designed
- [API Reference](api/reference.md) - API contracts
- [Database Design](database/design.md) - Data model
- [Security](security/requirements.md) - Security controls
- [Deployment](deployment/strategy.md) - How we ship it
- [Testing](testing/strategy.md) - Quality assurance
```
```

## Best Practices from Research

### Principle 1: Docs as Code
- Store documentation in version control (Git) alongside code
- Use Markdown for easy diffing and reviewing
- Make documentation updates part of the definition of done
- Review docs in pull requests just like code

### Principle 2: Single Source of Truth
- **Never duplicate content** across documents
- Use links to reference information in other documents
- If something needs to be updated, it should only be in one place

### Principle 3: Clear Hierarchy and Navigation
- Use consistent heading levels (H1 → H2 → H3, avoid deeper nesting)
- Include a table of contents in longer documents
- Every folder should have an index file (`README.md` or `index.md`)
- Use descriptive, human-readable file and folder names

### Principle 4: Audience-Oriented Organization
Organize by who needs the information:
- `/user/` - End users and administrators
- `/developer/` - Contributors and engineers
- `/api/` - API consumers and integrators
- `/architecture/` - Architects and technical leads

### Principle 5: Document Decomposition via WBS
Use Work Breakdown Structure principles:
1. Start with high-level goals (SMART: Specific, Measurable, Achievable, Relevant, Time-bound)
2. Break down into phases and milestones
3. Decompose phases into tasks
4. Map each task category to a documentation artifact type

### Principle 6: Use Templates for Consistency
Standardize common document types:
- Architecture Decision Records (ADRs) - see `templates/adr-template.md`
- Technical Design Documents (TDDs) - see `templates/tdd-template.md`
- API endpoint specifications - see `templates/api-endpoint-template.md`
- How-to guides - see `templates/howto-template.md`

### Principle 7: The Diátaxis Framework
Organize learning materials by purpose:
- **Tutorials** (learning-oriented) - "How to build your first X"
- **How-To Guides** (goal-oriented) - "How to configure Y"
- **Reference** (information-oriented) - "API documentation"
- **Explanation** (understanding-oriented) - "Why we chose technology Z"

### Principle 8: Progressive Disclosure
- Use the "inverted pyramid" - most critical info first
- Start with a summary or overview
- Provide links to detailed sections for deeper dives
- Don't overwhelm readers with too much information at once

### Principle 9: Keep It Maintainable
- Write in plain, concise language
- One idea per sentence, one theme per paragraph
- Use bullet points and numbered lists
- Include code examples and diagrams
- Update documentation when code changes

### Principle 10: Map Plan to Docs Explicitly

| Plan Component | Documentation Type | Location Example |
|----------------|-------------------|------------------|
| Project goals & scope | PRD | `/requirements/PRD.md` |
| System design | SAD (Software Architecture Doc) | `/architecture/overview.md` |
| Architectural decisions | ADR (Architecture Decision Records) | `/architecture/decisions/` |
| Feature implementation | TDD (Technical Design Doc) | `/design/feature-name.md` |
| API contracts | API Documentation | `/api/endpoints/` |
| User workflows | User Guides / Tutorials | `/user/guides/` |
| Development setup | How-To Guides | `/developer/setup.md` |
| Testing approach | Testing Strategy | `/testing/strategy.md` |
| Deployment process | Deployment Guides | `/deployment/` |

## When to Use This Skill

✅ **Use plan-to-docs when:**
- Starting a new project and need to structure initial documentation
- You have a large implementation plan that's hard to navigate
- Multiple teams need to work from the same plan
- Documentation is scattered or inconsistent
- Onboarding new team members takes too long
- You need to align documentation with agile/sprint workflows

❌ **Don't use this skill when:**
- You only need a quick README for a tiny project
- Documentation already follows a clear, working structure
- The project is experimental/throwaway code

## Tips for Best Results

1. **Provide context**: Use `#file:your-plan.md` to share your existing plan
2. **Specify your stack**: Mention technologies, team size, project phase
3. **Mention constraints**: E.g., "We use Confluence" or "Must work with existing /docs folder"
4. **Ask for priorities**: "What should I create first?"
5. **Request templates**: "Show me what [document type] should look like"
6. **Iterate**: Start with folder structure, then drill into specific documents

## Related Resources

See the `templates/` folder for ready-to-use document templates.
See the `references/` folder for complete examples and quick reference guides.
