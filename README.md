# CREDENTIA

Digital Credential Intelligence & Trust Platform for issuing, independently verifying, revoking, and auditing educational credentials. This is a local candidate demonstration, not a production certification service.

## Quick start

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
make seed
make run
```

Open `http://127.0.0.1:8000`. The public-style verifier is available from the top-right action or at `/verify`; API documentation is at `/docs`.

## Commands actually supported

```bash
make test       # critical lifecycle tests
make seed       # deterministic 80 learner / 12 course starter dataset
python3 -m backend.app.seed --scale full --seed 20261022
make validate   # writes docs/validation_report.json
uvicorn backend.app.main:app --reload
```

## Architecture

FastAPI serves versioned `/api/v1` endpoints and the responsive single-page administrative UI. SQLite uses foreign keys, unique identifiers, check constraints, and restrictive deletion. The domain layer owns eligibility, issuance, verification, revocation, immutable audit writes, canonical hashing, and Ed25519 authenticity checks.

The nine core entities are `learners`, `courses`, `credential_rules`, `completions`, `credentials`, `issuers`, `verification_requests`, `revocations`, and `audit_events`. `anomaly_fixtures` is a deliberately separate labelled evaluation table.

## Business decisions

Issuance checks the effective active course rule and latest completion: status must be `COMPLETED`, and score must meet the rule threshold. Repeating issuance for the same completion returns the existing credential. Verification precedence is issuer validity → payload/signature integrity → revocation → valid (unknown is returned when no credential exists). Revocations are one-way in this demo and create both a revocation and audit record.

Payload hashes use canonical, sorted JSON and SHA-256. Each local environment creates a gitignored Ed25519 development private key and stores only the corresponding public key with the issuer. Hashes detect alteration; signatures additionally authenticate the signer when the private key is protected. This is still not production key management.

### Verification boundary

`/api/v1/public/verify/{credential_id}` is authoritative only for CREDENTIA-issued records. `UNKNOWN` means CREDENTIA has no record; it does not label an external certificate as fake. The optional `/api/v1/public/verify-external` endpoint requires an explicitly authorized provider adapter. This local build configures none, so external requests return `EXTERNAL_UNSUPPORTED`, not a validity claim. CREDENTIA does not treat uploaded files, images, extracted certificate numbers, or unverified QR codes as proof of authenticity.

This data model has no credential-expiry field, so `EXPIRED` is not emitted or implied by the local verifier.

## Data and validation

Starter generation is deterministic for source records and issued credential payloads using seed `20261022`; it creates 80 learners, 12 courses, 40 qualifying completions/credentials and 30 requests. Full scale targets 20,000 learners, 1,000 courses, 10,000 credentials and 5,000 requests. Four isolated labelled anomaly fixtures document the required negative scenarios without corrupting operational records. Ground truth never participates in verification decisions.

`make validate` performs row-count, FK, duplicate-ID, eligibility and fixture checks. Generated operational databases are ignored by Git.

The validator additionally checks whether any persisted credential predates its linked completion. The four labelled anomaly scenarios are executed as disposable-database regression tests; their fixture labels are not injected into normal operational records. See the [final submission audit](docs/submission_audit.md) for the requirements checklist, command evidence, and known limits.

## Operational screens

The registry, learner directory, and audit explorer use server-side pagination. The audit explorer supports entity/event-ID search plus event-type and actor filters. Credential details include the issuer, completion evidence, issuance rule version, verification history, revocation record when present, and append-only audit history. The dashboard derives lifecycle, verification-outcome, and issuance-activity summaries from persisted records; its verification success rate is `VALID` decisions divided by all recorded verification requests.

## Limitations and security

There is no user authentication, distributed rate limiting, Alembic migration chain, background-job queue, CSV export, or production key store in this concise local build. SQLite application controls make audit records append-only through the service/UI but cannot make a compromised database tamper-proof. Do not use the generated development key or synthetic learner data in production.

See [architecture](docs/architecture.md), [business rules](docs/business_rules.md), [threat model](docs/threat_model.md), and [demo walkthrough](docs/demo_script.md).
