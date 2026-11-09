# Host Configuration Templates

These are reference templates for a future Codex CLI host. They do not configure ChatGPT's hosted runtime. Validate all keys against the exact installed Codex version before use.

- `base.config.toml.example`: least-privilege baseline.
- `blind-sniper.config.toml.example`: default orchestration profile.
- `research.config.toml.example`: read-only research.
- `engineering.config.toml.example`: workspace-write with on-request approval.
- `review.config.toml.example`: read-only independent review.
- `recovery.config.toml.example`: read-only diagnosis first.

Do not commit tokens, provider credentials or environment values.

## Validating the templates

`python scripts/validate_codex_config.py` parses every template with `tomllib` and
proves it is valid TOML, least-privilege (`approval_policy = "on-request"`, sandbox
`read-only` or `workspace-write`, no dangerous bypass, no credential-like value),
and consistent with the profile that references it (each profile's declared
`sandbox` posture must match its template's `sandbox_mode`). It runs in the
environment-validation workflow. A passing template is still a template: it does
not mean a Codex host is installed or that these settings are active.
