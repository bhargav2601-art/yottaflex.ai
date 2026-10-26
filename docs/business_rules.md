# Business rules

Rules are versioned per course and apply when their effective interval includes issuance time. Issuance persists the applied `rule_id`, making historical decisions explainable after a rule revision. Scores are percentages in `[0,100]`; completion must precede issuance in the generated baseline. Credential IDs are database-primary-key unique.

For CREDENTIA-issued credentials, the verifier returns `UNKNOWN`, `INVALID_ISSUER`, `TAMPERED`, `REVOKED`, or `VALID`. `UNKNOWN` means only that CREDENTIA has no authoritative record for the supplied identifier; it does not mean fake or invalid. Diagnostic precedence for a known record is issuer, integrity/signature, lifecycle, then valid. Public responses deliberately omit learner identity.

Credentials do not currently carry an expiry date, so the local verifier cannot truthfully emit `EXPIRED`. Expiry is therefore an unsupported workflow rather than an implied success or failure state.

External certificates use the separate optional `/api/v1/public/verify-external` workflow. With no explicitly authorized provider adapter, it returns `EXTERNAL_UNSUPPORTED`; this is not an authenticity verdict. An authorized integration can return `EXTERNAL_VERIFIED` or `EXTERNAL_UNVERIFIED`. Local CREDENTIA ships with no external integrations and does not accept PDF/image/QR uploads as authenticity evidence.
