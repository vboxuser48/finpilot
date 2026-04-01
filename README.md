# FinPilot AI

A production-quality async FastAPI backend for finance data processing with
role-based access control, dashboard analytics, and an AI-ready insight engine.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Framework | FastAPI (async) |
| ORM | SQLAlchemy 2.0 async |
| Database | PostgreSQL via asyncpg · SQLite fallback for local dev |
| Auth | JWT — python-jose + passlib[bcrypt] |
| Validation | Pydantic v2 + pydantic-settings |
| Logging | Loguru structured logging |

---

## Project Structure
```
finpilot/
├── app/
│   ├── main.py               # App factory, lifespan, router registration
│   ├── api/
│   │   ├── deps.py           # get_db, get_current_user, require_role()
│   │   └── routes/           # auth, users, records, dashboard, insights
│   ├── core/                 # config.py, security.py
│   ├── db/                   # base.py, session.py
│   ├── models/               # user.py, record.py
│   ├── schemas/              # user, record, dashboard, insights
│   └── services/             # all business logic lives here
├── tests/
├── .env.example
└── requirements.txt
```

---

## Getting Started

**Prerequisites:** Python 3.11+, PostgreSQL 14+ (or skip for SQLite fallback)
```bash
# 1. Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# 2. Install dependencies
pip install -r finpilot/requirements.txt

# 3. Configure environment
cp finpilot/.env.example finpilot/.env
# Edit .env — set DATABASE_URL, JWT secrets, and admin seed credentials

# 4. Run the server
cd finpilot
uvicorn app.main:app --reload
```

- Tables are auto-created on startup
- A default admin is seeded from `.env` if the users table is empty
- Interactive docs: http://localhost:8000/docs

---

## Running Tests
```bash
cd finpilot
pytest
```

Uses async SQLite in-memory fixtures. Covers auth helpers, record filtering,
dashboard aggregations, and the insight NL parser.

---

## Role & Access Control Matrix

Access is enforced centrally via the `require_role(*roles)` dependency in `deps.py`.

| Endpoint | viewer | analyst | admin |
|---|:---:|:---:|:---:|
| GET /records | ✓ | ✓ | ✓ |
| POST /records | ✗ | ✓ | ✓ |
| PATCH /records | ✗ | ✓ | ✓ |
| DELETE /records | ✗ | ✗ | ✓ |
| GET /dashboard/* | ✓ | ✓ | ✓ |
| GET /insights | ✗ | ✓ | ✓ |
| POST /insights/query | ✗ | ✓ | ✓ |
| All /users/* | ✗ | ✗ | ✓ |

---

## API Reference

All protected routes require `Authorization: Bearer <access_token>`.

### Auth
```bash
# Login — returns access + refresh token
curl -X POST http://localhost:8000/auth/login \
  -d "username=admin@example.com" \
  -d "password=ChangeMe123!"

# Refresh access token
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "<refresh_token>"}'
```

### Users _(admin only)_
```bash
# List users (paginated)
curl "http://localhost:8000/users/?page=1&page_size=20" \
  -H "Authorization: Bearer <admin_token>"

# Create a new user
curl -X POST http://localhost:8000/users/ \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "analyst@finpilot.ai",
    "full_name": "Fin Analyst",
    "role": "analyst",
    "password": "Secure123!"
  }'

# Update role or status
curl -X PATCH http://localhost:8000/users/<user_id> \
  -H "Authorization: Bearer <admin_token>" \
  -H "Content-Type: application/json" \
  -d '{"role": "viewer", "is_active": false}'
```

### Records
```bash
# List with filters (all roles)
curl "http://localhost:8000/records/?type=expense&category=Food&date_from=2025-03-01&date_to=2025-03-31&page=1&page_size=10" \
  -H "Authorization: Bearer <viewer_token>"

# Create a record (analyst+)
curl -X POST http://localhost:8000/records/ \
  -H "Authorization: Bearer <analyst_token>" \
  -H "Content-Type: application/json" \
  -d '{
    "amount": 120.50,
    "type": "expense",
    "category": "Food",
    "date": "2025-03-14",
    "notes": "Team lunch"
  }'

# Soft delete (admin only)
curl -X DELETE http://localhost:8000/records/<record_id> \
  -H "Authorization: Bearer <admin_token>"
```

### Dashboard _(all roles)_
```bash
# High-level summary
curl http://localhost:8000/dashboard/summary \
  -H "Authorization: Bearer <viewer_token>"

# Category-wise totals
curl http://localhost:8000/dashboard/by-category \
  -H "Authorization: Bearer <viewer_token>"

# Monthly income vs expenses (last 12 months)
curl http://localhost:8000/dashboard/monthly-trend \
  -H "Authorization: Bearer <viewer_token>"

# Recent transactions feed
curl "http://localhost:8000/dashboard/recent?limit=10" \
  -H "Authorization: Bearer <viewer_token>"
```

### Insights _(analyst, admin)_
```bash
# Full insight report (anomalies, MoM comparison, top categories)
curl http://localhost:8000/insights/ \
  -H "Authorization: Bearer <analyst_token>"

# Natural language query
curl -X POST http://localhost:8000/insights/query \
  -H "Authorization: Bearer <analyst_token>" \
  -H "Content-Type: application/json" \
  -d '{"query": "How much did we spend on food last month?"}'
```

---

## Assumptions

1. **Shared ledger** — records belong to the organisation, not individual users.
   Any authenticated user can read all records; writes are role-gated.
2. **Soft delete** — `DELETE /records/{id}` sets `is_deleted = true`.
   Soft-deleted records are excluded from all queries by default.
   Admins can pass `?include_deleted=true` to retrieve them.
3. **Insight period** — `GET /insights` always reports on the previous
   calendar month. The period is included in the response envelope.
4. **NL query scope** — the `/insights/query` parser is keyword-based
   (English only, no NLP libraries). It detects time period, record type,
   and category. The `parse_nl_query()` function is deliberately isolated
   so it can be replaced with an LLM call without touching other code.
5. **Anomaly threshold** — a transaction is flagged if its amount exceeds
   2.5× the category's monthly average for the same period.
6. **Token expiry** — access tokens expire in 24 hours for development
   convenience. Reduce `ACCESS_TOKEN_EXPIRE_MINUTES` in `.env` for production.
7. **Admin seeding** — one admin account is seeded from `.env` on first
   startup. Subsequent startups skip seeding if any user exists.

---

## Design Decisions & Tradeoffs

| Decision | Rationale |
|---|---|
| Async SQLAlchemy | Keeps the entire request path non-blocking; matches FastAPI's async model |
| SQLite fallback | Enables zero-config local dev and in-memory test fixtures without a running Postgres instance |
| Soft delete over hard delete | Preserves audit trail; dashboard aggregations remain historically accurate |
| Rule-based insight engine | No ML dependencies — simpler to deploy, easy to unit-test, and the abstraction layer makes an LLM swap straightforward |
| `require_role` as a dependency | Keeps access control declarative at the route level rather than scattered inside service logic |
| Services layer | Routes are kept thin (parse → call service → return); all business logic is testable without HTTP |

---

## Configuration Reference
```bash
# .env.example
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/finpilot
ASYNC_DATABASE_URL=                  # auto-derived if blank
SECRET_KEY=change-me-in-production
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440     # 24h — reduce for production
REFRESH_TOKEN_EXPIRE_DAYS=7
ADMIN_EMAIL=admin@finpilot.ai
ADMIN_PASSWORD=ChangeMe123!
ADMIN_FULL_NAME=System Admin
LOG_LEVEL=INFO
```

---

## Health Check
```bash
curl http://localhost:8000/health
# → { "status": "ok" }
```# finpilot
