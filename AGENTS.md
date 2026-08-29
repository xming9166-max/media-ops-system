# AGENTS.md

## Project

This is a long-term, modular self-media operations system.

The project consists of:

- Frontend: React + TypeScript
- Backend: Python + FastAPI
- Database: MySQL
- Cache: Redis
- Async tasks: Celery
- Infrastructure: Docker

## Architecture Principles

- High cohesion, low coupling.
- Modular architecture.
- Keep business modules independent.
- Prefer simple and maintainable solutions.
- Avoid unnecessary abstractions.
- Do not introduce technologies without a clear reason.

## Backend Principles

Use the following dependency direction:

Router → Service → Repository → Database

Responsibilities:

- Router: HTTP layer only.
- Service: business logic.
- Repository: database access.
- Schema: request/response validation.
- Model: database ORM models.

Routers must not directly access the database.

## Frontend Principles

Use:

- React
- TypeScript

Keep:

- Pages responsible for page composition.
- Components responsible for UI.
- Features responsible for business functionality.
- Services responsible for API communication.
- Hooks responsible for reusable logic.
- Stores responsible for global state.

Avoid `any` unless there is a strong reason.

## Development Rules

Before modifying code:

1. Read AGENTS.md.
2. Inspect the existing project structure.
3. Understand related code.
4. Make the smallest reasonable change.
5. Do not modify unrelated files.

After implementing a feature:

1. Run relevant tests.
2. Check for errors.
3. Review the changes.
4. Report what was changed and what was tested.

Do not implement multiple unrelated features in one task.
