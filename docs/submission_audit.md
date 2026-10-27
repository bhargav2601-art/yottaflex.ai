# Final submission audit

Audit date: 2026-10-27. The original standalone YottaFlex problem statement was not present in this repository. This checklist uses the candidate requirements supplied with the audit request; that missing source document is the only requirements-traceability limitation.

| Requirement | Implementation evidence | Status | Required action |
| --- | --- | --- | --- |
| Learner, course, rule, completion, credential, issuer, verification, revocation, audit entities | `backend/app/db.py` schema; seed and API use each entity | PASS | None |
| Eligibility and idempotent issuance | `domain.eligible`, `domain.issue`; lifecycle tests | PASS | None |
| Unique credential IDs | `credentials.id` primary key; atomic `credential_sequence` | PASS | None |
| Deterministic payload integrity/authenticity | `canonical`, `digest`, `sign`, `signature_valid` | PASS | None |
| Known, revoked, tampered, untrusted, and unknown decisions | `domain.verify`; regression tests | PASS | None |
| Expired credentials | No expiry field or policy exists | PARTIAL | Add an expiry model only if the original brief requires it |
| Third-party verification | Explicit adapter boundary; no provider shipped | PASS | Configure and test a provider only with authorization |
| Revocation and audit trail | `domain.revoke`, `audit`; lifecycle tests | PASS | None |
| Four anomaly scenarios | Isolated labelled fixtures, validation checks, regression tests | PASS | None |
| Full-scale synthetic data | `seed('full', 20261022)` generated 20,000 learners, 1,000 courses, 10,000 credentials, and 5,000 verification requests | PASS | None |
| Responsive browser checks | Desktop live-browser smoke test passed; tablet and mobile were not checked in this audit | PARTIAL | Run tablet and mobile browser checks before submission |
| Production security controls | Local demo uses SQLite and a development signing key; no authentication, rate limiting, HTTPS, or immutable audit sink | PARTIAL | Do not represent this as production ready |

## Verified commands and observed results

```bash
pytest -q
# 16 passed in 1.56s; 0 warnings (migrated to FastAPI lifespan handler).

node --check frontend/app.js
# passed (valid syntax)

python3 -m backend.app.seed --scale full --seed 20261022
# learners 20000, courses 1000, credentials 10000, verification_requests 5000 (14.5s wall time)

python3 -m backend.app.validate
# 62,006 records checked; 0 duplicate IDs, eligibility violations, issuance-before-completion cases,
# foreign-key violations, and payload-integrity failures (2.19s wall time)
```

The isolated full-scale generation measured 14.5 seconds seed time and 2.19 seconds validation time on the audit machine. Its generated validation report is `docs/validation_report.json`.


## Anomaly evidence

| Scenario | Expected outcome | Actual regression evidence |
| --- | --- | --- |
| Issued before completion | Rejected and detectable | `test_issuance_before_completion_is_rejected`; `test_validation_detects_issued_before_completion_without_corrupting_seed_data` |
| Duplicate credential ID | Database rejects it | `test_unknown_and_unique_identifier` |
| Revoked credential shown as active | Public verifier returns `REVOKED` | `test_valid_then_revoked` |
| Altered payload hash accepted | Public verifier returns `TAMPERED` | `test_tampering_is_detected` |

Fixture rows in `anomaly_fixtures` are labels and ground-truth metadata; they are not injected into ordinary operational data. The tests above create their state in a disposable test database.

## Security and operational boundaries

The local signing key is generated in a gitignored path and must not be reused for production. SQLite audit rows are append-only through the application, not tamper-proof if the database host is compromised. Public verification intentionally discloses no learner details for non-valid outcomes. No trusted external provider is configured, so `EXTERNAL_UNSUPPORTED` is not a failure or fake verdict.
