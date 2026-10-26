# Business rules

Rules are versioned per course and apply when their effective interval includes issuance time. Issuance persists the applied `rule_id`, making historical decisions explainable after a rule revision. Scores are percentages in `[0,100]`; completion must precede issuance in the generated baseline. Credential IDs are database-primary-key unique.

The verifier returns `UNKNOWN`, `INVALID_ISSUER`, `TAMPERED`, `REVOKED`, or `VALID`. Diagnostic precedence is issuer, integrity/signature, lifecycle, then valid. Public responses deliberately omit learner identity.
