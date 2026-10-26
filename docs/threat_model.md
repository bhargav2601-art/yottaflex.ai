# Threat model and limitations

The service validates typed inputs, avoids interpolating values in data queries, uses SQLite constraints, and does not expose signing material through the API. Public verification logs only the submitted ID and local requester marker. A gitignored local Ed25519 key is intentionally educational; production requires key isolation and rotation, authenticated roles, HTTPS, rate limits, monitoring, and an external immutable audit sink.
