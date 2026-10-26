# Demo walkthrough

1. Run `make seed && make run`, then open the console.
2. Inspect dashboard metrics, generated audit activity, and the credential registry.
3. Verify `CRD-2026-000001`; the portal returns `VALID`.
4. Open that credential, revoke it with a reason, then verify again to see `REVOKED`.
5. Open Data quality to inspect the four isolated expected anomaly outcomes.
