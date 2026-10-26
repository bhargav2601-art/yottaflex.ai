# Architecture

`frontend/` is a responsive administrative shell served by FastAPI. `backend/app/main.py` exposes the API; `domain.py` contains transactional lifecycle logic; `db.py` owns schema initialization. SQLite foreign keys are enabled on every connection. Business tables use restrictive deletion so credential and audit history survive normal administration.

Frequent lookup indexes cover completion eligibility and credential lookups. A learner can have multiple completions because completion IDs are independent attempt records; issuance binds exactly one completion with a unique constraint.
