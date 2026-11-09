# Host Configuration Templates

These are reference templates for a future Codex CLI host. They do not configure ChatGPT's hosted runtime. Validate all keys against the exact installed Codex version before use.

- `base.config.toml.example`: least-privilege baseline.
- `blind-sniper.config.toml.example`: default orchestration profile.
- `research.config.toml.example`: read-only research.
- `engineering.config.toml.example`: workspace-write with on-request approval.
- `review.config.toml.example`: read-only independent review.
- `recovery.config.toml.example`: read-only diagnosis first.

Do not commit tokens, provider credentials or environment values.
